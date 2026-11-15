# SPDX-License-Identifier: LGPL-2.1-or-later
# addon_test without FreeCAD: who may be tested, the binary found beside a
# fake FreeCAD.app, the runner on a folder of unittest and plain-function
# tests (plain python3 standing in for freecadcmd), the answer's cap, and
# the dev group outside the lean list.
import ast
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from agentlink import keep, testrun  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402


class Refusals(unittest.TestCase):
    def setUp(self):
        self.mod = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mod, True)
        for n in ("Mine", "Stray"):
            os.makedirs(os.path.join(self.mod, n))

    def test_agentlink_itself(self):
        self.assertEqual(testrun.root_for("AgentLink", self.mod, "/own", None), "/own")

    def test_installed_one(self):
        self.assertEqual(testrun.root_for("Mine", self.mod, "/own", {"Mine", "AgentLink", "AddonManager"}), os.path.join(self.mod, "Mine"))

    def test_not_installed_by_the_launcher(self):
        for name, installed in (("Stray", {"Mine"}), ("Mine", None), ("AddonManager", {"Mine", "AddonManager"})):
            with self.assertRaises(ToolError) as e:
                testrun.root_for(name, self.mod, "/own", installed)
            self.assertEqual(e.exception.code, "invalid_input")

    def test_paths_refused(self):
        for name in ("../Mine", "Mine/..", "a/b", "a\\b", "..", ""):
            with self.assertRaises(ToolError):
                testrun.root_for(name, self.mod, "/own", {name, "Mine"})

    def test_listed_but_missing(self):
        with self.assertRaises(ToolError) as e:
            testrun.root_for("Gone", self.mod, "/own", {"Gone"})
        self.assertEqual(e.exception.code, "not_found")


class Binary(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)

    def fake_app(self, name="FreeCAD.app", cmd="FreeCADCmd"):
        app = os.path.join(self.d, name)
        b = os.path.join(app, "Contents", "Resources", "bin")
        os.makedirs(b)
        os.makedirs(os.path.join(app, "Contents", "Resources", "lib"))
        for n in ("python3", cmd):
            open(os.path.join(b, n), "w").close()
        return app, b

    def test_beside_the_running_bundle(self):
        app, b = self.fake_app()
        cmd, lib = testrun.find_cmd(exe=os.path.join(b, "python3"), env={}, which=lambda n: None, apps=())
        self.assertEqual(cmd, os.path.join(b, "FreeCADCmd"))
        self.assertEqual(lib, os.path.join(app, "Contents", "Resources", "lib"))

    def test_running_bundle_before_freecad_app(self):
        _, b = self.fake_app("FreeCAD.app", "freecadcmd")
        other, ob = self.fake_app("Other.app")
        cmd, _ = testrun.find_cmd(exe=os.path.join(b, "python3"), env={"FREECAD_APP": other}, which=lambda n: None, apps=())
        self.assertEqual(cmd, os.path.join(b, "freecadcmd"))
        cmd, _ = testrun.find_cmd(exe="/usr/bin/python3x", env={"FREECAD_APP": other}, which=lambda n: None, apps=())
        self.assertEqual(cmd, os.path.join(ob, "FreeCADCmd"))

    def test_path_and_applications(self):
        _, b = self.fake_app()
        cmd, _ = testrun.find_cmd(exe="/nowhere/python", env={}, which=lambda n: os.path.join(b, "FreeCADCmd") if n == "FreeCADCmd" else None, apps=())
        self.assertEqual(cmd, os.path.join(b, "FreeCADCmd"))
        app, b2 = self.fake_app("Apps.app")
        cmd, _ = testrun.find_cmd(exe="/nowhere/python", env={}, which=lambda n: None, apps=(app,))
        self.assertEqual(cmd, os.path.join(b2, "FreeCADCmd"))
        self.assertEqual(testrun.find_cmd(exe="/nowhere/python", env={}, which=lambda n: None, apps=()), (None, None))


SUITE = {
    "test_cases.py": """
        import unittest
        import helper

        class Cases(unittest.TestCase):
            def test_pass(self):
                self.assertEqual(helper.VALUE, 3)

            def test_fail(self):
                self.assertEqual(1, 2, "one is not two")

            @unittest.skip("not today")
            def test_skip(self):
                pass

            def test_home(self):
                import os
                self.assertNotEqual(os.environ["AGENTLINK_HOME"], os.path.expanduser("~/AgentLink"))
        """,
    "test_plain.py": """
        import pytest

        @pytest.fixture
        def three():
            yield 3

        def test_tmp_and_fixture(tmp_path, three):
            (tmp_path / "x").write_text("ok")
            assert three == 3

        def test_monkeypatch(monkeypatch):
            import os
            monkeypatch.setenv("AL_T", "1")
            assert os.environ["AL_T"] == "1"

        def test_after_monkeypatch():
            import os
            assert "AL_T" not in os.environ

        @pytest.mark.parametrize("a,b", [(1, 2), (2, 3)])
        def test_param(a, b):
            assert a + 1 == b

        def test_raises_approx():
            with pytest.raises(ValueError, match="bad"):
                raise ValueError("bad thing")
            assert 0.1 + 0.2 == pytest.approx(0.3)

        def test_plain_fail():
            assert [1] == [2]

        @pytest.mark.skipif(True, reason="never here")
        def test_plain_skip():
            pass

        def test_unsupported(capsys):
            pass

        def test_unsupported_call():
            import warnings
            with pytest.warns(UserWarning):
                warnings.warn("w", UserWarning)

        class TestThings:
            def test_method(self):
                assert True
        """,
    "helper.py": "VALUE = 3\n",
    "test_broken.py": "import nothing_called_this\n",
}


def make_addon(d, files=SUITE):
    root = os.path.join(d, "Mine")
    os.makedirs(os.path.join(root, "tests"))
    for n, text in files.items():
        with open(os.path.join(root, "tests", n), "w") as f:
            f.write(textwrap.dedent(text))
    return root


class Runner(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.root = make_addon(self.d)
        self.log = os.path.join(self.d, "logs", "Mine.log")

    def run_(self, small=True, **k):
        # python3 stands in for freecadcmd; small: the runner used when
        # FreeCAD's Python has no pytest, whether this one has it or not.
        old = os.environ.get("AGENTLINK_TEST_RUNNER")
        os.environ["AGENTLINK_TEST_RUNNER"] = "agentlink" if small else "auto"
        try:
            return testrun.run(sys.executable, "Mine", self.root, HERE, [self.root], None, self.log, **k)
        finally:
            os.environ.pop("AGENTLINK_TEST_RUNNER")
            if old is not None:
                os.environ["AGENTLINK_TEST_RUNNER"] = old

    def test_with_pytest_when_there(self):
        if not _has_pytest():
            self.skipTest("no pytest here")
        out = self.run_(small=False)
        self.assertEqual(out["runner"], "pytest")
        self.assertEqual(out["failed"] + out["errors"], 3, out)
        self.assertGreaterEqual(out["passed"], 10)

    def test_unittest_and_plain_functions(self):
        out = self.run_()
        self.assertEqual(out["runner"], "agentlink")
        ids = {f["id"]: f for f in out["failures"]}
        self.assertTrue(any("test_fail" in i for i in ids), ids)
        self.assertTrue(any("test_plain_fail" in i for i in ids), ids)
        self.assertTrue(any("test_broken" in i for i in ids), ids)
        self.assertIn("one is not two", next(f["trace"] for i, f in ids.items() if "test_fail" in i))
        self.assertEqual(out["passed"], 9)
        self.assertGreaterEqual(out["skipped"], 2)
        self.assertEqual(out["failed"] + out["errors"], 3)
        self.assertTrue(os.path.isfile(out["log"]))
        with open(out["log"]) as f:
            self.assertIn("one is not two", f.read())
        if out["runner"] == "agentlink":
            self.assertEqual(out["skipped"], 4)
            self.assertTrue(any("capsys" in w for w in out["skippedWhy"]), out["skippedWhy"])
            self.assertTrue(any("pytest.warns" in w for w in out["skippedWhy"]), out["skippedWhy"])

    def test_select_and_pattern(self):
        out = self.run_(select="test_pass")
        self.assertEqual((out["passed"], out["failed"], out["errors"]), (1, 0, 0))
        out = self.run_(pattern="test_case*.py")
        self.assertEqual((out["passed"], out["failed"], out["skipped"]), (2, 1, 1))

    def test_no_match(self):
        out = self.run_(pattern="test_none*.py")
        self.assertEqual(out["passed"] + out["failed"], 0)
        self.assertIn("note", out)

    def test_timeout(self):
        shutil.rmtree(self.root)
        self.root = make_addon(self.d, {"test_slow.py": "import time\n\ndef test_ok():\n    pass\n\ndef test_slow():\n    time.sleep(30)\n"})
        out = self.run_(timeout=3)
        self.assertIn("timedOut", out)
        self.assertLess(out["seconds"], 20)

    def test_no_tests_folder(self):
        shutil.rmtree(os.path.join(self.root, "tests"))
        with self.assertRaises(ToolError) as e:
            self.run_()
        self.assertEqual(e.exception.code, "not_found")

    def test_environment(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        env = testrun.child_env("/own", ["/mod/A", "/own"], "/fc/lib", tmp, base={"PYTHONPATH": "/x", "AGENTLINK_SUPERVISED": "1"})
        self.assertEqual(env["PYTHONPATH"].split(os.pathsep), ["/own", "/mod/A", "/x", "/fc/lib"])
        self.assertEqual(env["FREECAD_LIB"], "/fc/lib")
        self.assertEqual(env["AGENTLINK_SRC"], "/own")
        self.assertTrue(env["AGENTLINK_HOME"].startswith(tmp))
        self.assertTrue(env["FREECAD_USER_HOME"].startswith(tmp))
        self.assertNotIn("AGENTLINK_SUPERVISED", env)


def _has_pytest():
    import subprocess

    return subprocess.run([sys.executable, "-c", "import pytest"], capture_output=True, check=False).returncode == 0


class Cap(unittest.TestCase):
    def test_answer_stays_small(self):
        rows = [{"id": f"tests/test_x.py::T::test_{i}", "outcome": "failed", "trace": "\n".join(f"line {j} " + "x" * 200 for j in range(40))} for i in range(60)]
        rows += [{"id": "ok", "outcome": "passed"}, {"id": "s", "outcome": "skipped", "reason": "why"}]
        out = testrun.summarize(rows, "Mine", "agentlink", 1.0, "/log")
        self.assertLessEqual(len(json.dumps(out)), testrun.CAP + 200)
        self.assertEqual(out["failed"], 60)
        self.assertIn("more", out)
        self.assertLessEqual(len(out["failures"][0]["trace"].splitlines()), testrun.TRACE_LINES)


class Group(unittest.TestCase):
    def test_dev_group_outside_lean(self):
        import tool_summary

        gs = tool_summary.groups()
        self.assertEqual(gs["dev"]["tools"], ["addon_test"])
        self.assertFalse(gs["dev"]["lean"])
        self.assertEqual(sorted(g for g, v in gs.items() if v["lean"]), ["core", "view"])
        with open(os.path.join(HERE, "agentlink", "tools.py")) as f:
            tree = ast.parse(f.read())
        lean = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "LEAN")
        self.assertEqual(lean, {"core", "view"})

    def test_heavy_and_deadline(self):
        self.assertTrue(keep.is_heavy("addon_test"))
        self.assertEqual(keep.call_deadline("addon_test", {}), 660.0)
        self.assertEqual(keep.call_deadline("addon_test", {"timeout": 1800}), 1860.0)
        self.assertIsNone(keep.call_deadline("view_render", {}))


if __name__ == "__main__":
    unittest.main()

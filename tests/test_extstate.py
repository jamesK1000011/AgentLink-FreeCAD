# SPDX-License-Identifier: LGPL-2.1-or-later
# An installed add-on that fails to load is never silently absent: where the
# families load it is noted with its error (agentlink/extstate.py), kept on
# disk for the launcher's update, and the smoke test fails when it loaded
# before. Without FreeCAD.
import importlib
import json
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import extstate  # noqa: E402


class Rules(unittest.TestCase):
    def setUp(self):
        extstate.reset()

    def tearDown(self):
        extstate.reset()

    def test_nothing_left_out_says_nothing(self):
        extstate.loaded("good.agentlink_families", "good", 4)
        st = extstate.state()
        self.assertEqual(st["leftOut"], [])
        self.assertEqual(st["noTools"], [])
        self.assertEqual(st["loaded"], [{"extension": "good.agentlink_families", "groups": ["good"], "tools": 4}])
        self.assertIsNone(extstate.warning(st["leftOut"]))

    def test_import_error_is_kept_with_its_words(self):
        try:
            compile("def broken(:\n", "/somewhere/private/pkg/agentlink_families.py", "exec")
        except SyntaxError as e:
            row = extstate.left_out("pkg.agentlink_families", e)
        self.assertIn("SyntaxError", row["error"])
        self.assertIn("agentlink_families.py", row["error"])
        self.assertNotIn("/somewhere/private", row["error"], "a folder is never part of the words")
        st = extstate.state()
        self.assertEqual(st["leftOut"], [{"extension": "pkg.agentlink_families", "error": row["error"]}])
        self.assertEqual(st["noTools"], st["leftOut"])
        w = extstate.warning(st["leftOut"], ["scan"])
        self.assertIn("pkg", w)
        self.assertIn("Tool groups gone: scan", w)
        self.assertIn("agentlink_update", w)  # what to do next

    def test_loaded_with_no_tools_is_named(self):
        extstate.loaded("empty.agentlink_families")
        extstate.loaded("part.agentlink_families", "a", 3)
        extstate.left_out("part.agentlink_families", "its b tools: KeyError: 'x'", "tools")
        st = extstate.state()
        self.assertEqual([r["extension"] for r in st["noTools"]], ["empty.agentlink_families"])
        # One family of an add-on failing leaves it loaded and left out both.
        self.assertEqual([r["extension"] for r in st["leftOut"]], ["part.agentlink_families"])
        self.assertEqual([r["extension"] for r in st["loaded"]], ["part.agentlink_families"])

    def test_lost_groups(self):
        self.assertEqual(extstate.lost_groups({"core": 3, "scan": 133, "zero": 0}, {"core": 3}), ["scan"])
        self.assertEqual(extstate.lost_groups(None, {"core": 3}), [])

    def test_smoke_fails_only_for_what_loaded_before(self):
        left = [{"extension": "scan.agentlink_families", "error": "SyntaxError: x"}, {"extension": "never.agentlink_families", "error": "E"}]
        fails = extstate.smoke_failures(left, extstate.before_list("scan.agentlink_families, other.agentlink_families"))
        self.assertEqual(len(fails), 1)
        self.assertIn("scan", fails[0])
        self.assertIn("SyntaxError: x", fails[0])
        self.assertEqual(extstate.smoke_failures(left, []), [])

    def test_record_on_disk(self):
        with tempfile.TemporaryDirectory() as d:
            old = {k: os.environ.get(k) for k in ("AGENTLINK_HOME", extstate.NO_RECORD)}
            os.environ["AGENTLINK_HOME"] = d
            os.environ.pop(extstate.NO_RECORD, None)
            try:
                extstate.loaded("good.agentlink_families", "good", 2)
                extstate.left_out("bad.agentlink_families", ValueError("no"))
                p = extstate.write({"core": 5, "good": 2}, window=False, version="1")
                self.assertEqual(p, os.path.join(d, "extensions.json"))
                extstate.write({"core": 5}, window=True)
                with open(p, encoding="utf-8") as f:
                    whole = json.load(f)
                self.assertEqual(set(whole), {"hidden", "window"})
                got = extstate.read()
                self.assertEqual(got["groups"], {"core": 5, "good": 2})
                self.assertEqual(got["leftOut"], [{"extension": "bad.agentlink_families", "error": "ValueError: no"}])
                # Under the smoke test nothing is written.
                os.environ[extstate.NO_RECORD] = "1"
                extstate.reset()
                self.assertIsNone(extstate.write({"core": 1}))
                self.assertEqual(extstate.read()["groups"], {"core": 5, "good": 2})
            finally:
                for k, v in old.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v


class Loading(unittest.TestCase):
    """families.load() with add-ons on the path: one whose module raises a
    SyntaxError, one that needs another API, one that loads."""

    def test_load_notes_each_one(self):
        fam_pkg = importlib.import_module("agentlink.families")
        with tempfile.TemporaryDirectory() as d:
            for name, body in (("alx_broken", "def tools(:\n"), ("alx_api", "AGENTLINK_API = '>=999'\nFAMILIES = []\n"),
                               ("alx_good", "import types\nFAMILIES = [types.SimpleNamespace(GROUP='alxgood', INFO='x', tools=lambda s: [])]\n")):
                os.makedirs(os.path.join(d, name))
                open(os.path.join(d, name, "__init__.py"), "w").close()
                with open(os.path.join(d, name, "agentlink_families.py"), "w") as f:
                    f.write(body)
            sys.path.insert(0, d)
            names, fam_pkg.NAMES = fam_pkg.NAMES, []  # core's own need FreeCAD
            err, sys.stderr = sys.stderr, types.SimpleNamespace(write=lambda *_a: None, flush=lambda: None)
            try:
                fams = fam_pkg.load()
                st = extstate.state()
            finally:
                sys.stderr = err
                fam_pkg.NAMES = names
                sys.path.remove(d)
                for m in [m for m in sys.modules if m.startswith("alx_")]:
                    del sys.modules[m]
                extstate.reset()
        left = {r["extension"]: r["error"] for r in st["leftOut"]}
        self.assertIn("alx_broken.agentlink_families", left)
        self.assertIn("SyntaxError", left["alx_broken.agentlink_families"])
        self.assertNotIn(d, left["alx_broken.agentlink_families"])
        self.assertIn("API", left["alx_api.agentlink_families"])
        self.assertNotIn("alx_good.agentlink_families", left)
        good = [f for f in fams if getattr(f, "GROUP", None) == "alxgood"]
        self.assertEqual(getattr(good[0], "EXTENSION", None), "alx_good.agentlink_families")
        # Loaded with no tools yet (build_server counts them): named as such.
        self.assertIn("alx_good.agentlink_families", [r["extension"] for r in st["noTools"]])


try:
    import _fc
except ImportError:
    from tests import _fc


@unittest.skipUnless(_fc.HAVE, "FreeCAD is not importable here")
class InTheServer(unittest.TestCase):
    """With FreeCAD: a server built with a broken add-on on the path says so
    in session_state and tool_groups, and keeps its other tools."""

    def test_session_state_and_tool_groups_say_it(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(d, "alx_broken"))
            open(os.path.join(d, "alx_broken", "__init__.py"), "w").close()
            with open(os.path.join(d, "alx_broken", "agentlink_families.py"), "w") as f:
                f.write("def tools(:\n")
            old_home = os.environ.get("AGENTLINK_HOME")
            os.environ["AGENTLINK_HOME"] = home
            sys.path.insert(0, d)
            try:
                _session, srv = _fc.server()
                call = _fc.caller(srv)
                err, st = call("session_state")
                self.assertFalse(err)
                self.assertIn("alx_broken.agentlink_families", [r["extension"] for r in st["leftOut"]])
                self.assertIn("did not load", st["warning"])
                err, tg = call("tool_groups")
                self.assertFalse(err)
                self.assertIn("alx_broken.agentlink_families", [r["extension"] for r in tg["addonsWithoutTools"]])
                self.assertIn("SyntaxError", tg["addonsWithoutTools"][0]["error"] + "".join(r["error"] for r in tg["addonsWithoutTools"]))
                rec = extstate.read()
                self.assertIn("alx_broken.agentlink_families", [r["extension"] for r in rec["leftOut"]])
                self.assertIn("core", rec["groups"])
            finally:
                sys.path.remove(d)
                sys.modules.pop("alx_broken", None)
                sys.modules.pop("alx_broken.agentlink_families", None)
                if old_home is None:
                    os.environ.pop("AGENTLINK_HOME", None)
                else:
                    os.environ["AGENTLINK_HOME"] = old_home
            # Built again without it: nothing is said any more.
            _session, srv = _fc.server()
            err, st = _fc.caller(srv)("session_state")
            self.assertNotIn("alx_broken.agentlink_families", [r["extension"] for r in st.get("leftOut", [])])


if __name__ == "__main__":
    unittest.main()

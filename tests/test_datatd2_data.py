# SPDX-License-Identifier: LGPL-2.1-or-later
# The last five TechDraw tools (td_list, td_export, td_cosmetic, td_view_more,
# td_lines), families/cam_more.py's six and families/openscad.py's five moved
# from handlers to data (agentlink/data/tools.json): each one built from its
# entry is the tool the code made before — name, description (byte for byte),
# inputSchema, changes, reads, group — and, on a stand-in FreeCAD, does the
# same things in the same order and answers or refuses in the same words as
# the handler it replaces (tests/_datatd2_cases.py: each tool's normal paths
# and each of its refusals). The pattern is tests/test_datatd2_data.py's.
#
# Each family file has its own stand-in, built on an existing one
# (tests/_datatd2_standin.py on _datatd_standin.py, _datatd2_cam_standin.py on
# _datacam_standin.py, _datatd2_scad_standin.py on _datapart_standin.py), so
# each is run in a child process of its own: the stand-in FreeCAD must not be
# seen by the other tests, nor one stand-in by another. tests/_datatd2_before.py
# is what the code made at BASE; where git has that commit the snapshot is
# checked against its source and the old handlers are run beside the new entries.
import ast
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)

BASE = "2097f32"  # the commit whose handlers were converted
sys.path.insert(0, HERE)
import _datatd2_cases  # noqa: E402
from _datatd2_cases import CONVERTED, FILES, KEPT, STANDIN  # noqa: E402


def _git(*args):
    try:
        r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _have_base():
    """Whether the old handlers can be run beside the entries: git has BASE."""
    return _git("cat-file", "-e", f"{BASE}^{{commit}}") is not None


_ran = {}


def _child(mode):
    """What the children answer for a mode, one child for each family file (each on its own stand-in), put together."""
    if mode not in _ran:
        got = None
        for f in FILES:
            r = subprocess.run([sys.executable, os.path.abspath(__file__), mode, f], capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                raise AssertionError(f"child {mode} {f} failed:\n{r.stderr[-3000:]}")
            part = json.loads(r.stdout)
            if got is None:
                got = part
            elif isinstance(got, dict):
                got.update(part)
            else:
                got += part
        _ran[mode] = got
    return _ran[mode]


class Td2Data(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        import _datatd2_before

        self.before = _datatd2_before.BEFORE

    def test_the_tool_is_the_one_the_code_made(self):
        from agentlink import runners

        self.assertEqual(sorted(self.before), sorted(CONVERTED))
        for name, group in CONVERTED.items():
            e = runners.entries()[name]
            t = runners.tool(name, e, {})
            b = self.before[name]
            self.assertEqual(t.name, b["name"], name)
            self.assertEqual(t.description.encode("utf-8"), b["description"].encode("utf-8"), name)
            self.assertEqual(t.schema, b["inputSchema"], name)
            self.assertEqual(json.dumps(t.schema), json.dumps(b["inputSchema"]), name)  # the order of every key too
            self.assertIs(t.changes, b["changes"], name)
            self.assertEqual(t.reads, b["reads"], name)
            self.assertEqual(t.group, b["group"], name)
            self.assertEqual(t.group, group, name)
            self.assertIsNone(t.activity, name)

    def test_no_handler_is_left_beside_the_entry(self):
        left = set()
        for f in FILES:
            with open(os.path.join(ROOT, "agentlink", "families", f + ".py"), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Tool" and node.args and isinstance(node.args[0], ast.Constant):
                    self.assertNotIn(node.args[0].value, CONVERTED, f)
                    left.add(node.args[0].value)
                if isinstance(node, ast.FunctionDef):
                    self.assertNotIn(node.name, CONVERTED, f)
        # Every tool of these files is either data or kept as code with its reason.
        self.assertEqual(left, set(KEPT))

    def test_every_converted_tool_is_a_steps_or_wrapper_entry_with_its_words(self):
        from agentlink import runners, tooldata

        with open(os.path.join(runners.DATA, "tools.json"), encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(tooldata.check(doc), [])
        for name in CONVERTED:
            self.assertIn(doc["entries"][name]["runner"], runners.RUNNERS, name)

    @unittest.skipUnless(_have_base(), f"git has no {BASE} here")
    def test_the_snapshot_is_the_code_at_base(self):
        self.assertEqual(_child("--before"), self.before)

    @unittest.skipUnless(_have_base(), f"git has no {BASE} here")
    def test_each_entry_calls_only_what_its_family_has(self):
        self.assertEqual(_child("--helpers"), {})

    @unittest.skipUnless(_have_base(), f"git has no {BASE} here")
    def test_same_steps_and_words_as_the_handlers(self):
        got = _child("--behave")
        self.assertEqual(sorted({c["tool"] for c in got}), sorted(CONVERTED))
        # Meant differences from the handler: td_view_more { kind: symbol | image } looks
        # for a relative path in the session's folder, as the other tools' files are (the
        # handler took it as it was: a bare file name was refused "no such SVG" from
        # wherever FreeCAD was started). One that is there is placed; one that is not is
        # refused in the handler's words, with the place that was looked in.
        meant = {("td_view_more", "symbol, a bare name in the session's folder"): ("ok", "DrawViewSymbol"),
                 ("td_view_more", "image, a bare name in the session's folder"): ("ok", "DrawViewImage"),
                 ("td_view_more", "symbol, a bare name that is not there"): ("refused", "path '<out>/rel-none.svg': no such SVG."),
                 ("td_view_more", "image, a bare name that is not there"): ("refused", "path '<out>/rel-none.png': no such image.")}
        seen, shared = set(), []
        for c in got:
            want = meant.get((c["tool"], c["case"]))
            if want:
                seen.add((c["tool"], c["case"]))
                self.assertEqual(c["old"]["result"][:2], ["refused", "not_found"], f"{c['case']}: {c['old']['result']}")
                self.assertIn("'rel-", c["old"]["result"][2], c["case"])
                self.assertEqual(c["new"]["result"][0], want[0], f"{c['case']}: {c['new']['result']}")
                if want[0] == "ok":
                    self.assertEqual(c["new"]["result"][1]["type"], want[1], c["case"])
                    # the file in the session's folder is the one read (a symbol keeps its text, an image its path)
                    self.assertIn("r='3'" if want[1] == "DrawViewSymbol" else "<out>/rel-mark.svg", json.dumps(c["new"]["trace"]), c["case"])
                else:
                    self.assertEqual(c["new"]["result"][1:], ["not_found", want[1]], c["case"])
                    self.assertEqual(c["new"]["trace"], c["old"]["trace"], c["case"])
                continue
            # Meant difference, td_view_more { kind: share }: FreeCAD's addView puts a view it is
            # given in the middle of the page (TechDraw DrawPage::addView: "position all new views
            # without owners in center of Page"), so sharing a view moved it on its first page too
            # (seen live: BracketTop from [100, 200] to the second sheet's middle). The entry puts
            # its X and Y back right after: two more lines in the trace, nothing else.
            if c["tool"] == "td_view_more" and c["case"] in ("share", "share with its dimensions"):
                shared.append(c["case"])
                t = c["new"]["trace"]
                i = next(n for n, line in enumerate(t) if ".addView(<View>)" in line)
                self.assertEqual(t[i + 1:i + 3], ["View.X = 100", "View.Y = 120"], c["case"])
                c = {**c, "new": {**c["new"], "trace": t[:i + 1] + t[i + 3:]}}
            self.assertEqual(c["new"]["result"], c["old"]["result"], f"{c['tool']} {c['case']}")
            self.assertEqual(c["new"], c["old"], f"{c['tool']} {c['case']}")
        self.assertEqual(seen, set(meant))
        self.assertEqual(shared, ["share", "share with its dimensions"])
        for c in got:
            self.assertNotEqual(c["new"]["result"][0], "crashed" if not c["crash"] else None, f"{c['tool']} {c['case']}: {c['new']['result']}")
        # Each tool: a case that answers.
        for name in CONVERTED:
            kinds = {c["new"]["result"][0] for c in got if c["tool"] == name}
            self.assertIn("ok", kinds, name)
        by = {(c["tool"], c["case"]): c["new"] for c in got}
        from _datatd2_cases import EXPECT

        # Not two empty runs alike: what some of them must have done.
        for (tool, case), want in EXPECT.items():
            res = by[(tool, case)]["result"]
            if isinstance(want, dict):
                self.assertEqual(res[0], "ok", f"{tool} {case}: {res}")
                self.assertEqual({k: res[1].get(k) for k in want}, want, f"{tool} {case}")
            else:
                self.assertEqual(res, want, f"{tool} {case}")

    @unittest.skipUnless(_have_base(), f"git has no {BASE} here")
    def test_every_refusal_in_the_data_is_reached(self):
        """Each refusal message written in a converted entry is raised by at
        least one case (so each is compared with the handler's words)."""
        from agentlink import runners

        got = _child("--behave")
        said = {}
        for c in got:
            if c["new"]["result"][0] == "refused":
                said.setdefault(c["tool"], []).append(c["new"]["result"][2])
        missing = []
        for name in CONVERTED:
            for msg in _refusals(runners.entries()[name]):
                # A template's fixed parts, in order, must all be in one refusal a case got.
                parts = [p for p in _fixed(msg) if p]
                if not any(_in_order(parts, text) for text in said.get(name, [])):
                    missing.append(f"{name}: {msg[:70]}")
        from _datatd2_cases import UNREACHED

        self.assertEqual(sorted(missing), sorted(UNREACHED))


def _refusals(e):
    out = []

    def walk(x):
        if isinstance(x, dict):
            if "refuse" in x:
                out.append(x["refuse"]["fmt"] if isinstance(x["refuse"], dict) else x["refuse"])
            if "check" in x and "message" in x:
                out.append(x["message"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for k in ("rules", "steps", "answer"):
        walk(e.get(k))
    return out


def _fixed(msg):
    import string

    if msg.startswith("="):
        return []
    try:
        return [t.replace("{{", "{").replace("}}", "}") for t, _f, _s, _c in string.Formatter().parse(msg)]
    except ValueError:
        return [msg]


def _in_order(parts, text):
    at = 0
    for p in parts:
        at = text.find(p, at)
        if at < 0:
            return False
        at += len(p)
    return True


# ---- the child: a stand-in FreeCAD, the old handlers and the new entries ----------------------

def _old(name):
    """A family module as it was at BASE, loaded beside today's."""
    import importlib.util
    import tempfile

    src = _git("show", f"{BASE}:agentlink/families/{name}.py")
    for other in FILES:  # one of these files importing another: the old one of it
        src = src.replace(f"from . import {other}\n", f"from . import {other}_before as {other}\n").replace(f"from .{other} import", f"from .{other}_before import")
    d = tempfile.mkdtemp()
    path = os.path.join(d, f"{name}_before.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location(f"agentlink.families.{name}_before", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _tool(mod, session, name, code):
    """The module's tool of that name: the handler's (code) or the entry's."""
    hits = [t for t in mod.tools(session) if t.name == name and (t.fn.__module__ != "agentlink.runners") is code]
    if len(hits) != 1:
        raise AssertionError(f"{name}: {len(hits)} tools in {mod.__name__}")
    return hits[0]


def _coded(mod):
    """The names a family module's own code makes tools of."""
    with open(mod.__file__, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return [n.args[0].value for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "Tool" and n.args and isinstance(n.args[0], ast.Constant)]


def _main(mode, file):
    """One family file's part, on that file's own stand-in."""
    import importlib
    import tempfile

    fc = importlib.import_module(STANDIN[file]).install()
    from agentlink import runners
    from agentlink.protocol import ToolError

    FILES = (file,)  # noqa: N806 - this child's own
    CONVERTED = {k: g for k, (f, g) in _datatd2_cases.TOOLS.items() if f == file}  # noqa: N806
    old = {m: _old(m) for m in FILES}
    where = {name: m for m in FILES for name in _coded(old[m])}  # tool -> the family file it was in at BASE
    if mode == "--before":
        out = {}
        for name in CONVERTED:
            t = _tool(old[where[name]], fc.Session(), name, True)
            out[name] = {"name": t.name, "description": t.description, "inputSchema": t.schema, "changes": t.changes, "reads": t.reads, "group": old[where[name]].GROUP}
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    new = {m: importlib.import_module(f"agentlink.families.{m}") for m in FILES}
    if mode == "--helpers":
        seen, real = {}, runners.tools

        def spy(group, session, helpers, data=None, family=None):
            seen.setdefault((group, family), {}).update(helpers)
            return real(group, session, helpers, data, family)

        runners.tools = spy
        for m in FILES:
            new[m].tools(fc.Session())
        runners.tools = real
        missing = {}
        for name in CONVERTED:
            e = runners.entries()[name]
            lost = sorted(runners.calls(e) - set(seen.get((e["group"], e.get("family")), {})))
            if lost:
                missing[name] = lost
        print(json.dumps(missing))
        return
    rows = []
    for tool, case, prepare, args in _datatd2_cases.cases(file, fc, tempfile.mkdtemp()):
        row = {"tool": tool, "case": case, "crash": case.startswith("crash:")}
        for which, mods in (("old", old), ("new", new)):
            del fc.trace[:]
            fc.state["flags"] = {}
            fc.fresh()  # the stand-in's own counters and modules as at the start
            s = fc.Session(tempfile.mkdtemp())
            prepare(s)
            fc.trace.append("---- the call")
            t = _tool(mods[where[tool]], s, tool, which == "old")
            try:
                res = ["ok", t.fn(json.loads(json.dumps(args)))]
            except ToolError as e:
                res = ["refused", e.code, e.message]
            except Exception as e:  # noqa: BLE001 - a crash is compared as one
                res = ["crashed", type(e).__name__, str(e)]
            text = json.dumps({"result": res, "trace": list(fc.trace), "objects": [o.Label for o in s.doc.Objects]}, ensure_ascii=False, default=repr)
            row[which] = json.loads(text.replace(s.out_dir, "<out>"))
        rows.append(row)
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--before", "--behave", "--helpers"):
        _main(sys.argv[1], sys.argv[2])
    else:
        unittest.main()

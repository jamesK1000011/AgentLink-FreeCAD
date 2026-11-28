# SPDX-License-Identifier: LGPL-2.1-or-later
# The BIM tools moved from handlers to data (agentlink/data/tools.json):
# each one built from its entry is the tool the code made before — name,
# description (byte for byte), inputSchema, changes, reads, group — and, on a
# stand-in FreeCAD (tests/_bim_standin.py), does the same things in the same
# order and answers or refuses in the same words as the handler it replaces
# (tests/_bim_cases.py: each tool's normal paths and each of its refusals).
#
# Plain Python. tests/_bim_before.py is what the code made at
# BASE; where git has that commit the snapshot is checked against its source
# and the old handlers are run beside the new entries (in a child process:
# the stand-in FreeCAD must not be seen by the other tests).
import ast
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)

BASE = "b2d3dbd"  # the commit whose handlers were converted (the three family files are the same at 9b4bc52)
sys.path.insert(0, HERE)
import _meant  # noqa: E402
from _bim_cases import CONVERTED, KEPT  # noqa: E402


def _git(*args):
    try:
        r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _have_base():
    return _git("cat-file", "-e", f"{BASE}^{{commit}}") is not None


_ran = {}


def _child(mode):
    if mode not in _ran:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), mode], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise AssertionError(f"child {mode} failed:\n{r.stderr[-3000:]}")
        _ran[mode] = json.loads(r.stdout)
    return _ran[mode]


class BimData(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        import _bim_before

        self.before = _bim_before.BEFORE

    def test_the_tool_is_the_one_the_code_made(self):
        from agentlink import runners

        self.assertEqual(sorted(self.before), sorted(CONVERTED))
        for name, group in CONVERTED.items():
            e = runners.entries()[name]
            t = runners.tool(name, e, {})
            b = self.before[name]
            self.assertEqual(t.name, b["name"], name)
            self.assertEqual(_meant.word_gap(t.description, t.schema, _meant.expected_words(name, b["description"], b["inputSchema"]), b["inputSchema"]), ([], []), name)  # words: the card and the inputs' meanings (tests/_meant.py)  # meant changes: tests/_meant.py
            self.assertEqual(_meant.bare(t.schema), _meant.bare(b["inputSchema"]), name)
            self.assertEqual(json.dumps(_meant.bare(t.schema)), json.dumps(_meant.bare(b["inputSchema"])), name)  # the order of every key too
            self.assertIs(t.changes, b["changes"], name)
            self.assertEqual(t.reads, b["reads"], name)
            self.assertEqual(t.group, b["group"], name)
            self.assertEqual(t.group, group, name)
            self.assertIsNone(t.activity, name)

    def test_no_handler_is_left_beside_the_entry(self):
        left = set()
        for f in ("bim.py", "bim_more.py", "bim_gaps.py"):
            with open(os.path.join(ROOT, "agentlink", "families", f), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Tool" and node.args and isinstance(node.args[0], ast.Constant):
                    self.assertNotIn(node.args[0].value, CONVERTED, f)
                    left.add(node.args[0].value)
                if isinstance(node, ast.FunctionDef):
                    self.assertNotIn(node.name, CONVERTED, f)
        # Every tool of the three files is either data or kept as code with its reason.
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
        # Meant differences from the handler, bim_nest: FreeCAD's nester gives up on the whole
        # run when one of the rotations leaves a piece no place (three rectangles on a sheet with
        # room to spare stopped so live, with [0, 90]). The handler then refused, pointing at the
        # report view. The entry tries each rotation alone, in the order given, takes the first
        # that lays the pieces out and says so (rotationsUsed, rotationsNote); when none does, the
        # refusal carries the nester's own printed reason.
        old_words = ("The pieces would not nest: FreeCAD's nester stopped (its reason is in the report view; report_read shows it). "
                     "Check each piece is a flat face lying the same way up as the sheet, and that the largest fits the sheet.")
        runs = "Nester.run(rotations="
        seen = 0
        for c in got:
            if c["tool"] == "bim_nest" and c["case"].startswith("stops "):
                seen += 1
                self.assertEqual(c["old"]["result"], ["refused", "failed", old_words], c["case"])
                self.assertEqual(sum(runs in t for t in c["old"]["trace"]), 1, c["case"])
                tried = [t for t in c["new"]["trace"] if runs in t]
                if "one alone" in c["case"]:
                    self.assertEqual(c["new"]["result"][0], "ok", c["new"]["result"])
                    out = c["new"]["result"][1]
                    self.assertEqual((out["sheets"], out["placed"], out["of"], out["rotations"], out["rotationsUsed"]), (1, 2, 2, [0, 90], [90.0]))
                    self.assertIn("each was tried alone", out["rotationsNote"])
                    self.assertEqual([t[len(runs):] for t in tried], ["[0, 90])", "[0])", "[90])"])
                    self.assertTrue(any("Nester.apply" in t for t in c["new"]["trace"]))
                else:
                    self.assertEqual(c["new"]["result"], ["refused", "failed", "The pieces would not nest: FreeCAD's nester stopped — it said: Could not determine location on sheet. "
                                                          "(rotations: together, then each alone). Check each piece is a flat face lying the same way up as the sheet, "
                                                          "and that the largest fits the sheet."])
                    self.assertEqual(len(tried), 3, tried)
                    self.assertFalse(any("Nester.apply" in t for t in c["new"]["trace"]))
                continue
            # Meant difference, bim_library { insert } of an .FCStd Agent Link worked on: the file's
            # hidden records object came in with the model ("Agent Link records001", seen live) and
            # was answered as one of the objects. The entry leaves it out, as doc_merge does.
            if (c["tool"], c["case"]) == ("bim_library", "insert a document that carries Agent Link's records"):
                seen += 1
                self.assertEqual(c["old"]["result"][1]["objects"], ["Merged", "Agent Link records001"])
                self.assertIn("Agent Link records001", c["old"]["objects"])
                self.assertEqual(c["new"]["result"], ["ok", {"inserted": "Table.FCStd", "objects": ["Merged"]}])
                self.assertNotIn("Agent Link records001", c["new"]["objects"])
                self.assertIn("Merged", c["new"]["objects"])
                continue
            self.assertEqual(c["new"]["result"], c["old"]["result"], f"{c['tool']} {c['case']}")
            self.assertEqual(c["new"], c["old"], f"{c['tool']} {c['case']}")
            self.assertNotEqual(c["new"]["result"][0], "crashed" if not c["crash"] else None, f"{c['tool']} {c['case']}: {c['new']['result']}")
        self.assertEqual(seen, 3)
        # Each tool: a case that answers, and (where it can refuse) one that is refused.
        for name in CONVERTED:
            kinds = {c["new"]["result"][0] for c in got if c["tool"] == name}
            self.assertIn("ok", kinds, name)
        by = {(c["tool"], c["case"]): c["new"] for c in got}
        from _bim_cases import EXPECT

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
        from _bim_cases import UNREACHED

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

    src = _git("show", f"{BASE}:agentlink/families/{name}.py").replace("from .bim import", "from .bim_before import")
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


def _main(mode):
    import tempfile

    import _bim_standin

    fc = _bim_standin.install()
    from agentlink import runners
    from agentlink.protocol import ToolError

    files = ("bim", "bim_more", "bim_gaps")
    old = {m: _old(m) for m in files}
    where = {name: m for m in files for name in _coded(old[m])}  # tool -> the family file it was in at BASE
    if mode == "--before":
        out = {}
        for name in CONVERTED:
            t = _tool(old[where[name]], fc.Session(), name, True)
            out[name] = {"name": t.name, "description": t.description, "inputSchema": t.schema, "changes": t.changes, "reads": t.reads, "group": old[where[name]].GROUP}
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    import importlib

    new = {m: importlib.import_module(f"agentlink.families.{m}") for m in files}
    if mode == "--helpers":
        seen, real = {}, runners.tools

        def spy(group, session, helpers, data=None, family=None):
            seen.setdefault((group, family), {}).update(helpers)
            return real(group, session, helpers, data, family)

        runners.tools = spy
        for m in files:
            new[m].tools(fc.Session())
        runners.tools = real
        missing = {}
        for name, e in runners.entries().items():
            key = (e["group"], e.get("family"))
            if e["group"] in ("bim", "bim_gaps") and e.get("family") != "ifc":  # ifc.py's own: tests/test_datamisc_data.py
                lost = sorted(runners.calls(e) - set(seen.get(key, {})))
                if lost:
                    missing[name] = lost
        print(json.dumps(missing))
        return
    from _bim_cases import cases

    rows = []
    # What a stand-in prints as FreeCAD would (the nester's "… Aborting.") goes to stderr: stdout carries the rows.
    out, sys.stdout = sys.stdout, sys.stderr
    for tool, case, prepare, args in cases(fc, tempfile.mkdtemp()):
        row = {"tool": tool, "case": case, "crash": case.startswith("crash:")}
        for which, mods in (("old", old), ("new", new)):
            del fc.trace[:]
            fc.state["flags"] = {}
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
    sys.stdout = out
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--before", "--behave", "--helpers"):
        _main(sys.argv[1])
    else:
        unittest.main()

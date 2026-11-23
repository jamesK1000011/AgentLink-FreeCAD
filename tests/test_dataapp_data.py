# SPDX-License-Identifier: LGPL-2.1-or-later
# The hub's application tools (families/app.py: settings, commands, menus,
# workbenches, what is shown and selected, the window's picture, the person's
# screenshots) and the Addon Manager's tool (`addon`, families/unattended.py)
# moved from handlers to data (agentlink/data/tools.json): each one built from
# its entry is the tool the code made before — name, description (byte for
# byte), inputSchema, changes, reads, group — and, on a stand-in FreeCAD
# (tests/_dataapp_standin.py, on tests/_dataapp_standin.py), does the same
# things in the same order and answers or refuses in the same words as the
# handler it replaces (tests/_dataapp_cases.py: each tool's normal paths and
# each of its refusals). The pattern is tests/test_dataapp_data.py's. The
# tools of app.py that are one run of the machine's own state stay code (KEPT,
# with the reason for each).
#
# Plain Python. tests/_dataapp_before.py is what the code made at BASE;
# where git has that commit the snapshot is checked against its source and
# the old handlers are run beside the new entries (in a child process: the
# stand-in FreeCAD must not be seen by the other tests).
import ast
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)

BASE = "a399f58"  # the commit whose handlers were converted
# `addon` was changed on main after BASE (an add-on copied into Mod by hand: its first update takes url): it was converted from that handler.
OLD_AT = {"unattended": "bb7ddfe"}
sys.path.insert(0, HERE)
import _meant  # noqa: E402
from _dataapp_cases import CONVERTED, FILES, KEPT  # noqa: E402


def _git(*args):
    try:
        r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _have_base():
    """Whether the old handlers can be run beside the entries: git has BASE."""
    return all(_git("cat-file", "-e", f"{c}^{{commit}}") is not None for c in (BASE, *OLD_AT.values()))


_ran = {}


def _child(mode):
    if mode not in _ran:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), mode], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise AssertionError(f"child {mode} failed:\n{r.stderr[-3000:]}")
        _ran[mode] = json.loads(r.stdout)
    return _ran[mode]


class AppData(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        import _dataapp_before

        self.before = _dataapp_before.BEFORE

    def test_the_tool_is_the_one_the_code_made(self):
        from agentlink import runners

        self.assertEqual(sorted(self.before), sorted(CONVERTED))
        for name, group in CONVERTED.items():
            e = runners.entries()[name]
            t = runners.tool(name, e, {})
            b = self.before[name]
            self.assertEqual(t.name, b["name"], name)
            self.assertEqual(t.description.encode("utf-8"), _meant.description(name, b["description"]).encode("utf-8"), name)  # meant changes and the STE rewrite: tests/_meant.py
            want = _meant.schema(name, b["inputSchema"])  # meant changes: tests/_meant.py SCHEMAS
            self.assertEqual(t.schema, want, name)
            self.assertEqual(json.dumps(t.schema), json.dumps(want), name)  # the order of every key too
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
        # Every tool of app.py is either data or kept as code with its reason.
        self.assertLessEqual(set(KEPT), left)

    def test_every_converted_tool_is_a_steps_or_wrapper_entry_with_its_words(self):
        from agentlink import runners, tooldata

        with open(os.path.join(runners.DATA, "tools.json"), encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(tooldata.check(doc), [])
        for name in CONVERTED:
            self.assertIn(doc["entries"][name]["runner"], runners.RUNNERS, name)

    @unittest.skipUnless(_have_base(), f"git has no {BASE} or {sorted(OLD_AT.values())} here")
    def test_the_snapshot_is_the_code_at_base(self):
        self.assertEqual(_child("--before"), self.before)

    @unittest.skipUnless(_have_base(), f"git has no {BASE} or {sorted(OLD_AT.values())} here")
    def test_each_entry_calls_only_what_its_family_has(self):
        self.assertEqual(_child("--helpers"), {})

    @unittest.skipUnless(_have_base(), f"git has no {BASE} or {sorted(OLD_AT.values())} here")
    def test_same_steps_and_words_as_the_handlers(self):
        got = _child("--behave")
        self.assertEqual(sorted({c["tool"] for c in got}), sorted(CONVERTED))
        # Meant differences from the handler the entry was converted from:
        # the address named at a hand-installed add-on's first update is
        # recorded (the handler said so and did not), and one with a
        # recorded source of any kind, an addressless catalog one too, takes
        # no url (the handler let that one be pointed elsewhere).
        # workbench { activate } on the workbench that is active already: FreeCAD's
        # activateWorkbench answers False for it (Application.cpp: "already active"),
        # which the handler took for a workbench that failed to load and refused
        # ("did not switch to PartDesignWorkbench (still PartDesignWorkbench)", seen live).
        # The entry answers without calling FreeCAD (tests/test_hubfix4.py reads the answer).
        meant = {("addon", "update one put there by hand, its address given"): "ok",
                 ("addon", "update one put there by hand, a source with no address"): "refused",
                 ("workbench", "by its menu name with a space"): "ok"}
        with_keys = 0
        for c in got:
            if (c["tool"], c["case"]) in meant:
                self.assertEqual(c["new"]["result"][0], meant[(c["tool"], c["case"])], f"{c['tool']} {c['case']}: {c['new']['result']}")
                if c["tool"] == "workbench":
                    self.assertEqual(c["old"]["result"][:2], ["refused", "failed"], c["old"]["result"])
                    self.assertEqual({k: c["new"]["result"][1].get(k) for k in ("active", "was", "note")},
                                     {"active": "PartDesignWorkbench", "was": "PartDesignWorkbench", "note": "Already active."})
                    self.assertNotIn("activateWorkbench", json.dumps(c["new"]["trace"]))
                continue
            # Meant difference, cmd_list: a command's shortcut. FreeCAD's Command.getInfo() names
            # it "shortcut" (the stand-in now does too); the handler read "shortcutText", which no
            # FreeCAD gives, so live no row ever had one (Std_ViewFitAll: V, F). Rows are alike
            # but for that field.
            if c["tool"] == "cmd_list" and c["new"]["result"][0] == "ok" and any("shortcut" in r for r in c["new"]["result"][1]["commands"]):
                with_keys += 1
                rows = c["new"]["result"][1]["commands"]
                self.assertEqual([r["shortcut"] for r in rows if "shortcut" in r], ["V, F"], c["case"])
                self.assertFalse(any("shortcut" in r for r in c["old"]["result"][1]["commands"]), c["case"])
                bare = {**c["new"]["result"][1], "commands": [{k: v for k, v in r.items() if k != "shortcut"} for r in rows]}
                c = {**c, "new": {**c["new"], "result": ["ok", bare]}}
            self.assertEqual(c["new"]["result"], c["old"]["result"], f"{c['tool']} {c['case']}")
            self.assertEqual(c["new"], c["old"], f"{c['tool']} {c['case']}")
            self.assertNotEqual(c["new"]["result"][0], "crashed" if not c["crash"] else None, f"{c['tool']} {c['case']}: {c['new']['result']}")
        self.assertGreaterEqual(with_keys, 1)
        # Each tool: a case that answers.
        for name in CONVERTED:
            kinds = {c["new"]["result"][0] for c in got if c["tool"] == name}
            self.assertIn("ok", kinds, name)
        by = {(c["tool"], c["case"]): c["new"] for c in got}
        from _dataapp_cases import EXPECT

        # Not two empty runs alike: what some of them must have done.
        for (tool, case), want in EXPECT.items():
            res = by[(tool, case)]["result"]
            if isinstance(want, dict):
                self.assertEqual(res[0], "ok", f"{tool} {case}: {res}")
                self.assertEqual({k: res[1].get(k) for k in want}, want, f"{tool} {case}")
            else:
                self.assertEqual(res, want, f"{tool} {case}")

    @unittest.skipUnless(_have_base(), f"git has no {BASE} or {sorted(OLD_AT.values())} here")
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
        from _dataapp_cases import UNREACHED

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
    """A family module as it was at BASE (OLD_AT for one changed since), loaded beside today's."""
    import importlib.util
    import tempfile

    src = _git("show", f"{OLD_AT.get(name, BASE)}:agentlink/families/{name}.py")
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


def _files(folder):
    """Every file and empty folder under folder, as it stands after a call."""
    out = []
    for at, dirs, files in os.walk(folder):
        rel = os.path.relpath(at, folder)
        out += [os.path.join(rel, f) for f in files] + ([rel + os.sep] if not dirs and not files else [])
    return sorted(out)


def _main(mode):
    import tempfile

    import _dataapp_standin

    fc = _dataapp_standin.install()
    from agentlink import runners
    from agentlink.protocol import ToolError

    old = {m: _old(m) for m in FILES}
    where = {name: m for m in FILES for name in _coded(old[m])}  # tool -> the family file it was in at BASE
    for m in FILES:  # what the old code finds beside itself (the repository's preference packs, the add-on's folder) is what today's finds
        old[m].__file__ = os.path.abspath(os.path.join(ROOT, "agentlink", "families", m + ".py"))
    if mode == "--before":
        out = {}
        for name in CONVERTED:
            t = _tool(old[where[name]], fc.Session(), name, True)
            out[name] = {"name": t.name, "description": t.description, "inputSchema": t.schema, "changes": t.changes, "reads": t.reads, "group": old[where[name]].GROUP}
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    import importlib

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
    from _dataapp_cases import cases

    rows = []
    for tool, case, prepare, args in cases(fc, tempfile.mkdtemp(), old, new):
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
            text = json.dumps({"result": res, "trace": list(fc.trace), "objects": [o.Label for o in s.doc.Objects], "document": s.doc.Name,
                               "shown": {o.Label: bool(o.ViewObject.Visibility) for o in s.doc.Objects if getattr(o, "ViewObject", None) is not None},
                               "settings": fc.state["params"], "selected": [x.ObjectName for x in fc.state["selected"]], "editing": fc.state["editing"] is not None,
                               "files": _files(s.out_dir)}, ensure_ascii=False, default=repr)
            row[which] = json.loads(text.replace(s.out_dir, "<out>"))
        rows.append(row)
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--before", "--behave", "--helpers"):
        _main(sys.argv[1])
    else:
        unittest.main()

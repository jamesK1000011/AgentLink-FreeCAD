# SPDX-License-Identifier: LGPL-2.1-or-later
# The hub's faults from the third hardening pass, on stand-ins (plain
# Python, no FreeCAD):
#   - the session's own record of a document (steps, meta, tx, calls,
#     checks) belongs to that document (agentlink/docstates.py own());
#   - a read that drives the document, the window or the selection on the
#     way never runs as a job (agentlink/jobs.py IN_PLACE), and a scan of
#     every read's code pins the list;
#   - the hang trace covers a job's thread and a batch's wait, several at
#     once, and leaves no file open (agentlink/protocol.py hang_trace);
#   - a batch's compact lines: refusals whole, and what a line costs.
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentlink import batchrec, docstates, jobs, outputs, protocol  # noqa: E402
from agentlink.protocol import Tool, compact  # noqa: E402
from test_hubfix2 import FAKE, Doc, in_a_process  # noqa: E402


# ---- 1. the session's own record per document -----------------------------------------------

class S:
    """A session as docstates sees it: a doc and a __dict__."""

    def __init__(self, doc):
        self._doc = doc
        docstates.settle(self, doc)

    @property
    def doc(self):
        return self._doc

    @doc.setter
    def doc(self, d):
        self._doc = d
        docstates.settle(self, d)

    def own(self):
        return docstates.own(self, self._doc)


class OwnRecordPerDocument(unittest.TestCase):
    def setUp(self):
        self.docs = {}
        self._open = docstates.open_documents
        docstates.open_documents = lambda: dict(self.docs)

    def tearDown(self):
        docstates.open_documents = self._open

    def new(self, name):
        self.docs[name] = Doc(name)
        return self.docs[name]

    def test_a_new_document_starts_at_nothing_and_going_back_finds_its_own(self):
        a = self.new("A")
        s = S(a)
        s.own()["steps"].append({"step": 1, "tool": "part_primitive"})
        s.own()["tx"] = 3
        s.own()["calls"].append({"tool": "part_primitive", "tx": 3, "step": 1})
        b = self.new("B")
        s.doc = b
        self.assertEqual(s.own(), docstates.fresh())
        s.own()["tx"] = 1
        s.doc = a
        self.assertEqual((s.own()["tx"], len(s.own()["steps"]), len(s.own()["calls"])), (3, 1, 1))
        s.doc = b
        self.assertEqual(s.own()["tx"], 1)

    def test_a_closed_document_is_let_go_and_a_reopened_one_starts_afresh(self):
        a = self.new("A")
        s = S(a)
        s.own()["tx"] = 5
        b = self.new("B")
        s.doc = b
        del self.docs["A"]              # closed while the session is elsewhere
        again = self.new("A")           # reopened, or reverted: another document of that name
        s.doc = again
        self.assertEqual(s.own()["tx"], 0)
        self.assertIsNone(docstates.own_of(s, a))

    def test_the_record_of_a_document_left_open_is_reached_from_elsewhere(self):
        a = self.new("A")
        s = S(a)
        s.own()["tx"] = 4
        s.doc = self.new("B")
        self.assertEqual(docstates.own_of(s, a)["tx"], 4)   # a batch takes back its steps there
        self.assertIs(docstates.own_of(s, s.doc), s.own())
        self.assertIsNone(docstates.own_of(s, Doc("Never")))

    def test_the_family_state_still_goes_its_own_way(self):
        a = self.new("A")
        s = S(a)
        docstates.settle(s, a)["mine"] = {"n": 1}
        s.own()["tx"] = 2
        s.doc = self.new("B")
        self.assertEqual(docstates.settle(s, s.doc), {})
        s.doc = a
        self.assertEqual((docstates.settle(s, a), s.own()["tx"]), ({"mine": {"n": 1}}, 2))


class TheSessionsRecord(unittest.TestCase):
    """The real Session on a stand-in FreeCAD, in a process of its own."""

    def test_steps_tx_and_calls_are_each_documents_own_by_every_route(self):
        got = in_a_process('''
            from agentlink import tools
            class T:
                name, changes = "part_primitive", True
            s = tools.Session(out_dir=".")
            a = s.doc
            s._step_of = lambda doc, previous=None, cached=True: {"bodies": {doc.Name: {"volume": len(s.steps)}}, "at": {}, "features": {}}
            for _ in range(2):
                s.execute(T, lambda: a.change()); s.snapshot("part_primitive"); s.record_call(T, {"kind": "box"})
            in_a = (s.tx, len(s.steps), [c["tx"] for c in s.calls])
            b = new("B")
            s.doc = b                         # as doc_new, doc_open and doc_close set it
            fresh = (s.tx, len(s.steps), list(s.calls), dict(s.checks), dict(s.meta))
            s.execute(T, lambda: b.change()); s.snapshot("part_primitive"); s.record_call(T, {"kind": "cone"})
            in_b = (s.tx, len(s.steps), [c["args"]["kind"] for c in s.calls])
            diff_b = s.history_diff({"since": 0})["steps"]
            s.switch(a)                       # as doc_switch does
            back = (s.tx, len(s.steps), [c["args"]["kind"] for c in s.calls])
            diff_a = s.history_diff({"since": 0})["steps"]
            c = new("C")
            s.switch(c)                       # a document reopened (doc_revert): another document
            kept = (s.steps, s.meta, s.calls)
            s.steps, s.meta, s.calls = [{"step": 1}], {"x": 1}, [{"tool": "t", "tx": 0, "step": 1}]   # an add-on puts its copy's record back
            put = (len(s.steps), s.meta, len(s.calls), s.tx)
            s.switch(b)
            b_again = (s.tx, len(s.steps))
            print(json.dumps({"in_a": in_a, "fresh": fresh, "in_b": in_b, "diff_b": diff_b, "back": back, "diff_a": diff_a, "put": put, "b_again": b_again}))
        ''')
        self.assertEqual(got["in_a"], [2, 2, [1, 2]])
        self.assertEqual(got["fresh"], [0, 0, [], {}, {}])
        self.assertEqual(got["in_b"], [1, 1, ["cone"]])
        self.assertEqual(got["diff_b"], ["part_primitive"])          # one document's steps, not three
        self.assertEqual(got["back"], [2, 2, ["box", "box"]])        # a macro saved here replays this document's calls
        self.assertEqual(got["diff_a"], ["part_primitive", "part_primitive"])
        self.assertEqual(got["put"], [1, {"x": 1}, 1, 0])
        self.assertEqual(got["b_again"], [1, 1])

    def test_a_document_closed_meanwhile_starts_afresh_under_its_name(self):
        got = in_a_process('''
            from agentlink import tools
            s = tools.Session(out_dir=".")
            a = s.doc
            s.tx = 7
            s.doc = new("B")
            del docs[a.Name]                  # closed
            a2 = new(a.Name)                  # one of the same name opened
            s.doc = a2
            print(json.dumps({"tx": s.tx, "steps": s.steps}))
        ''')
        self.assertEqual(got, {"tx": 0, "steps": []})


# ---- 3. reads that run in place: the list, pinned by a scan ---------------------------------
#
# The scan reads the source, not FreeCAD: every read (a Tool("name", …)
# call of the hub's with no changes, an entry of data/tools.json with
# changes false or with read-only calls) with the code it runs — its handler,
# the family helpers its entry names, and what those call in the hub — for
# the signs of driving the document or the window: a recompute, a solve, an
# object made or removed, a property set (o.Placement = …), a transaction,
# undo, the selection, the view, Qt, a document opened or made active, a
# setting written. What it flags must be kept from jobs (jobs.IN_PLACE, a
# name NOT_JOBS_PREFIX or outputs.SHOT_TOOLS covers) or be listed in
# LOOKED_AT with why it is safe. It cannot see into FreeCAD's own modules
# (asm_export, bim_export are in IN_PLACE from reading FreeCAD's source) nor
# into an add-on (which says jobs.in_place(name, why) for its own).

ROOT = HERE
PKG = os.path.join(ROOT, "agentlink")
FAM = os.path.join(PKG, "families")

# method calls that drive the document, the window or the view
CALLS = {"recompute", "removeObject", "addObject", "openTransaction", "commitTransaction", "abortTransaction", "undo", "redo",
         "setEdit", "resetEdit", "touch", "purgeTouched", "setExpression", "newDocument", "openDocument", "closeDocument", "setActiveDocument",
         "processEvents", "runCommand", "doCommand", "sendMsgToActiveView", "fitAll", "saveImage", "activateWorkbench", "addSelection",
         "clearSelection", "removeSelection", "getSelection", "getSelectionEx", "updateGui", "copyObject", "moveObject", "addProperty",
         "removeProperty", "enforceRecompute", "solve", "singleShot", "saveAs", "saveCopy", "getMainWindow", "activeView", "setCamera",
         "mergeProject", "SetBool", "SetInt", "SetFloat", "SetString", "SetUnsigned", "RemBool", "RemInt", "RemFloat", "RemString", "RemGroup", "Import"}
NAMES = {"FreeCADGui", "Gui", "QtWidgets", "QtCore", "QtGui", "QApplication", "ImportGui", "QTimer"}

_mods = {}

def module(path):
    if path not in _mods:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        funcs = {}
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef,)):
                funcs.setdefault(n.name, []).append(n)
        aliases = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.level >= 1:
                for al in n.names:
                    for base in (FAM if n.level == 1 and os.path.dirname(path) == FAM else PKG, PKG):
                        p = os.path.join(base, *( (n.module or "").split(".") if n.module else []), al.name + ".py")
                        if os.path.isfile(p):
                            aliases[al.asname or al.name] = p
                            break
        helpers = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "helpers" for t in n.targets) and isinstance(n.value, ast.Dict):
                for k, v in zip(n.value.keys, n.value.values):
                    if isinstance(k, ast.Constant):
                        helpers[k.value] = v
            # helpers.update({...}) / helpers["x"] = y
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "update" and isinstance(n.func.value, ast.Name) and n.func.value.id == "helpers":
                for arg in n.args:
                    if isinstance(arg, ast.Dict):
                        for k, v in zip(arg.keys, arg.values):
                            if isinstance(k, ast.Constant):
                                helpers[k.value] = v
        _mods[path] = {"tree": tree, "funcs": funcs, "aliases": aliases, "helpers": helpers, "src": src}
    return _mods[path]


def hits_in(node, path, seen, depth=0):
    """[(what, file, line)] for node's body, following calls to functions of the same module and of sibling modules."""
    m = module(path)
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in CALLS:
                out.append((ast.unparse(f)[-60:] + "()", path, n.lineno))
            if isinstance(f, ast.Name) and f.id == "setattr":
                out.append(("setattr()", path, n.lineno))
        if isinstance(n, (ast.Assign, ast.AugAssign)):
            ts = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in ts:
                for tt in (t.elts if isinstance(t, ast.Tuple) else [t]):
                    if isinstance(tt, ast.Attribute) and tt.attr[:1].isupper() and not (isinstance(tt.value, ast.Name) and tt.value.id == "self"):
                        out.append((ast.unparse(tt)[-50:] + " =", path, n.lineno))
        if isinstance(n, ast.Name) and n.id in NAMES:
            out.append((n.id, path, n.lineno))
    if depth > 6:
        return out
    for n in ast.walk(node):
        tgt = None
        if isinstance(n, ast.Name) and n.id in m["funcs"]:
            tgt = [(path, fn) for fn in m["funcs"][n.id]]
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in m["aliases"]:
            p2 = m["aliases"][n.value.id]
            tgt = [(p2, fn) for fn in module(p2)["funcs"].get(n.attr, [])]
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in ("s", "session", "self") :
            p2 = os.path.join(PKG, "tools.py")
            tgt = [(p2, fn) for fn in module(p2)["funcs"].get(n.attr, []) if True]
        for p2, fn in tgt or []:
            key = (p2, fn.name, fn.lineno)
            if key in seen or fn is node:
                continue
            seen.add(key)
            out += hits_in(fn, p2, seen, depth + 1)
    return out


IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")

def entry_names(e):
    """Identifiers an entry's expressions use, and its direct step kinds."""
    names, kinds = set(), []
    def walk(v, key=None, where=""):
        if isinstance(v, str):
            if v.startswith("="):
                names.update(IDENT.findall(v))
            elif key in ("call", "via", "helper", "maker", "method", "command"):
                names.update(IDENT.findall(v))
            elif key == "fmt" or "{" in v:
                for part in re.findall(r"\{([^{}]*)\}", v):
                    names.update(IDENT.findall(part))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, key, f"{where}[{i}]")
        elif isinstance(v, dict):
            for k in ("make", "add", "set"):
                if k in v and where.startswith("steps"):
                    kinds.append((k, where, json.dumps(v[k])[:80]))
            for k, x in v.items():
                if k in ("description", "inputSchema", "source", "date", "words", "commands", "activity"):
                    continue
                walk(x, k, f"{where}.{k}" if where else k)
    walk(e)
    return names, kinds


def group_modules():
    """group → [(module path, family or None)] from each family's runners.tools(GROUP, s, helpers, family=…)."""
    out = {}
    for f in sorted(os.listdir(FAM)):
        if not f.endswith(".py"):
            continue
        p = os.path.join(FAM, f)
        m = module(p)
        grp = None
        for n in ast.walk(m["tree"]):
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GROUP" for t in n.targets) and isinstance(n.value, ast.Constant):
                grp = n.value.value
        for n in ast.walk(m["tree"]):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "tools" and isinstance(n.func.value, ast.Name) and n.func.value.id == "runners":
                fam = next((k.value.value for k in n.keywords if k.arg == "family"), None)
                g = n.args[0]
                g = g.value if isinstance(g, ast.Constant) else grp
                out.setdefault(g, []).append((p, fam))
    return out


def scan():
    data = json.load(open(os.path.join(PKG, "data", "tools.json"), encoding="utf-8"))["entries"]
    gm = group_modules()
    res = {}
    for name, e in data.items():
        if e.get("changes") and not e.get("reads"):
            continue
        names, kinds = entry_names(e)
        hits = [(f"step {k}: {txt}", "tools.json", w) for k, w, txt in kinds]
        if e.get("runner") in ("make", "apply", "command"):
            hits.append((f"runner {e['runner']}", "tools.json", ""))
        for n in sorted(names & CALLS):
            hits.append((f"expression calls .{n}", "tools.json", ""))
        mods = [p for p, fam in gm.get(e["group"], []) if fam == e.get("family")]
        if not mods:
            hits.append(("NO MODULE for group " + e["group"], "", ""))
        for p in mods:
            m = module(p)
            for h in sorted(names & set(m["helpers"])):
                node = m["helpers"][h]
                seen = set()
                if isinstance(node, ast.Name) and node.id in m["funcs"]:
                    hs = []
                    for fn in m["funcs"][node.id]:
                        seen.add((p, fn.name, fn.lineno))
                        hs += hits_in(fn, p, seen)
                else:
                    hs = hits_in(node, p, seen)
                hits += [(f"{h} → {w}", os.path.relpath(f, ROOT), ln) for w, f, ln in hs]
        res[name] = {"read_calls_only": bool(e.get("changes")), "hits": hits}
    res.update(hub_reads())
    return res


def hub_reads():
    """The hub's own Tool("name", description, schema, handler) calls that are reads."""
    out = {}
    for folder in (PKG, FAM):
        for f in sorted(os.listdir(folder)):
            if not f.endswith(".py"):
                continue
            p = os.path.join(folder, f)
            m = module(p)
            for node in ast.walk(m["tree"]):
                fn = getattr(node, "func", None)
                if not (isinstance(node, ast.Call) and (getattr(fn, "id", None) == "Tool" or getattr(fn, "attr", None) == "Tool")):
                    continue
                if len(node.args) < 4 or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                    continue
                ch = node.args[4] if len(node.args) > 4 else next((k.value for k in node.keywords if k.arg == "changes"), None)
                reads = any(k.arg == "reads" for k in node.keywords)
                if ch is not None and not (isinstance(ch, ast.Constant) and ch.value is False) and not reads:
                    continue
                seen = set()
                hs = hits_in(node.args[3], p, seen)
                out[node.args[0].value] = {"read_calls_only": ch is not None and reads, "hits": [(w, os.path.relpath(f2, ROOT), ln) for w, f2, ln in hs]}
    return out


# Flagged by the scan and safe on a worker thread, each with why.
LOOKED_AT = {
    "bim_profiles": "its one maker step is ArchProfile.readPresets, which reads FreeCAD's profile table (a CSV) and makes nothing",
    "bim_schedule": "a changing tool; its read (no sheet) is quantities() alone — the sheet and its recompute are the changing call's",
    "bim_library": "a changing tool; its read (no insert) lists the library's files",
    "bim_trash": "a changing tool; its read (action list) reads the Trash group's labels",
    "param_list": "sheet() is called without make: it finds the Params sheet and makes none",
}


def kept_from_jobs(name):
    return (name in outputs.SHOT_TOOLS or name.startswith(jobs.NOT_JOBS_PREFIX) or name == "batch"
            or name in jobs.IN_PLACE or name in jobs.IN_PLACE_WHEN)


class ReadsThatRunInPlace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = scan()

    def test_the_scan_sees_the_reads(self):
        # It reads what it should: the data's reads, the hub's own, and the
        # two that hung FreeCAD's window live.
        for name in ("asm_sweep", "sketch_state", "session_state", "history_undo", "measure", "body_check", "export"):
            self.assertIn(name, self.found)
        self.assertGreater(len(self.found), 100)
        self.assertTrue(any("Placement =" in w for w, _f, _l in self.found["asm_sweep"]["hits"]))
        self.assertTrue(any("recompute" in w for w, _f, _l in self.found["asm_sweep"]["hits"]))
        self.assertTrue(any("solve" in w for w, _f, _l in self.found["asm_list"]["hits"]))
        self.assertTrue(any("undo" in w for w, _f, _l in self.found["history_undo"]["hits"]))

    def test_every_read_that_drives_the_document_or_the_window_is_kept_from_jobs(self):
        loose = {}
        for name, r in self.found.items():
            if r["hits"] and not kept_from_jobs(name) and name not in LOOKED_AT:
                loose[name] = sorted({f"{w} [{f}:{ln}]" for w, f, ln in r["hits"]})[:6]
        self.assertEqual(loose, {}, "These reads drive the document or the window on the way (the signs are listed): add each to jobs.IN_PLACE with what it does, "
                                    "or, read and found safe on a worker thread, to LOOKED_AT here with why.")

    def test_the_lists_hold_nothing_stale(self):
        # A name in LOOKED_AT that the scan no longer flags, or that is kept
        # from jobs anyway, is looked at again rather than left to cover a
        # later change.
        for name in LOOKED_AT:
            self.assertIn(name, self.found, name)
            self.assertTrue(self.found[name]["hits"], f"{name}: the scan flags nothing now — take it out of LOOKED_AT")
            self.assertFalse(kept_from_jobs(name), f"{name}: kept from jobs and in LOOKED_AT")
        # Every tool of the hub's in IN_PLACE is a tool, and a read (asm_motion:
        # a changing tool, whose list call reads; kept as it was).
        entries = json.load(open(os.path.join(PKG, "data", "tools.json"), encoding="utf-8"))["entries"]
        for name in list(jobs.IN_PLACE) + list(jobs.IN_PLACE_WHEN):
            self.assertTrue(name in self.found or name in entries, f"{name}: no such tool of the hub's")

    def test_what_is_kept_from_jobs_by_name(self):
        for name in ("asm_sweep", "asm_motion", "asm_list", "asm_check", "sketch_state", "td_list", "td_export", "td_geometry", "cam_list", "cam_post",
                     "robot_run", "scad_export", "bim_export", "note_list", "addon_test", "history_undo", "history_redo", "selection", "workbench",
                     "session_state", "history_diff", "live_run"):
            self.assertFalse(jobs.eligible(Tool(name, "does", {"type": "object"}, lambda a: {}), {}), name)
        for name in ("measure", "body_check", "clearance", "steps_render", "meshobj_info", "export"):
            self.assertTrue(jobs.eligible(Tool(name, "does", {"type": "object"}, lambda a: {}), {}), name)
        self.assertIs(jobs.MOVES_PARTS, jobs.IN_PLACE)  # the set's first name still answers

    def test_the_refusal_says_what_it_does_and_what_to_do(self):
        t = Tool("asm_list", "does", {"type": "object"}, lambda a: {})
        for in_batch in (False, True):
            w = jobs.background_refusal(t, {}, in_batch)
            self.assertIn("cannot run as a job", w)
            self.assertIn("solves the assembly", w)
            self.assertIn("Leave background out", w)
        self.assertIn("runs as a plain call", jobs.background_refusal(t, {}, False))
        self.assertIn("in the batch's order", jobs.background_refusal(t, {}, True))

    def test_a_study_of_one_solid_keeps_its_solve_in_place(self):
        from agentlink import store

        class D:
            Name = "D"
            Objects = ()

            def __init__(self, study):
                self.Meta = {store.KEY + "fea": json.dumps(study)} if study is not None else {}

        class Ses:
            def __init__(self, study):
                self.doc = D(study)

        t = Tool("fea_heat", "does", {"type": "object"}, lambda a: {})
        self.assertTrue(jobs.eligible(t, {}))                                   # by its name alone: a job
        self.assertTrue(jobs.eligible(t, {}, Ses({"body": "Bracket"})))        # a whole body: it only reads
        self.assertTrue(jobs.eligible(t, {}, Ses(None)))
        one = Ses({"body": "Bracket solid 2 (study)", "of": {"body": "Bracket", "solid": 2}})
        self.assertFalse(jobs.eligible(t, {}, one))                             # its hidden helper is refreshed first
        self.assertIn("helper", jobs.background_refusal(t, {}, False, one))

    def test_an_add_on_says_its_own(self):
        name = "addon_pose_read_t"
        try:
            jobs.in_place(name, "moves the parts and puts them back")
            t = Tool(name, "does", {"type": "object"}, lambda a: {})
            self.assertFalse(jobs.eligible(t, {}))
            self.assertIn("moves the parts and puts them back", jobs.background_refusal(t, {}, False))
        finally:
            jobs.IN_PLACE.pop(name, None)


# ---- 4. the hang trace ------------------------------------------------------------------------

def _held(seconds):
    time.sleep(seconds)


class HangTrace(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.crash = os.path.join(self.out, "crash")

    def files(self):
        return sorted(os.listdir(self.crash)) if os.path.isdir(self.crash) else []

    def idle(self):
        H = protocol._hang_trace
        self.assertIsNone(H._armed)     # no timer set, no file open
        self.assertEqual(H._live, [])

    def test_a_call_that_ends_in_time_leaves_nothing(self):
        with protocol.hang_trace(self.out, "quick_read", after=5):
            f = protocol._hang_trace._armed[1]
            self.assertFalse(f.closed)
        self.assertTrue(f.closed)
        self.assertEqual(self.files(), [])
        self.idle()

    def test_a_batch_itself_is_not_watched_and_no_folder_is_no_watch(self):
        with protocol.hang_trace(self.out, "batch"):
            self.assertIsNone(protocol._hang_trace._armed)
        with protocol.hang_trace(None, "anything"):
            self.assertIsNone(protocol._hang_trace._armed)

        class Ses:
            out_dir = self.out

        with protocol.hang_trace(Ses(), "by_session", after=5):   # a session, or its folder
            self.assertEqual(protocol._hang_trace._armed[0].name, "by_session")
        self.assertEqual(self.files(), [])
        self.idle()

    def test_a_job_thread_still_running_leaves_every_threads_stack(self):
        def worker():
            with protocol.hang_trace(self.out, "wall_read", "job", after=0.2):
                _held(0.7)

        t = threading.Thread(target=worker, name="agentlink-job-wall_read")
        t.start()
        # The GUI thread's side: a batch waiting for it, and a call inside
        # the batch that comes and goes meanwhile.
        with protocol.hang_trace(self.out, "wall_read", "batch wait", after=5):
            with protocol.hang_trace(self.out, "inner_call", after=5):
                time.sleep(0.05)
            time.sleep(0.4)
            self.assertEqual(self.files(), ["hang-job-wall_read.txt"])
            text = open(os.path.join(self.crash, "hang-job-wall_read.txt"), encoding="utf-8").read()
            t.join()
        self.assertIn("job wall_read (thread agentlink-job-wall_read", text.splitlines()[0])
        self.assertIn("still running after 0.2 s", text.splitlines()[0])
        self.assertIn("_held", text)                                   # where the job's thread was
        self.assertIn("test_a_job_thread_still_running", text)         # and the thread that waited for it
        self.assertEqual(self.files(), ["hang-job-wall_read.txt"])     # the waits that ended in time left nothing
        self.assertIn("ended after", open(os.path.join(self.crash, "hang-job-wall_read.txt"), encoding="utf-8").read())
        self.idle()

    def test_the_one_due_first_is_timed_and_the_next_after_it_ends(self):
        with protocol.hang_trace(self.out, "outer", after=0.5):
            with protocol.hang_trace(self.out, "inner", after=0.15):
                self.assertEqual(protocol._hang_trace._armed[0].name, "inner")
                time.sleep(0.3)
            # The inner one fired and ended; the timer is the outer one's again.
            self.assertEqual(protocol._hang_trace._armed[0].name, "outer")
            time.sleep(0.4)
        self.assertEqual(self.files(), ["hang-inner.txt", "hang-outer.txt"])
        self.idle()

    def test_one_overdue_while_another_held_the_timer_is_written_when_the_timer_is_free(self):
        with protocol.hang_trace(self.out, "long_a", after=0.15):
            with protocol.hang_trace(self.out, "long_b", after=0.2):
                time.sleep(0.35)          # a's fires; b is overdue with the timer spent
                with protocol.hang_trace(self.out, "passing", after=5):
                    pass                  # any watch coming or going sets the timer again
                time.sleep(0.2)
        self.assertEqual(self.files(), ["hang-long_a.txt", "hang-long_b.txt"])
        self.idle()

    def test_a_job_started_by_jobs_start_is_watched(self):
        # jobs.start's worker in a process of its own (its queue files go to
        # a folder of the test's).
        home = tempfile.mkdtemp()
        body = textwrap.dedent(f'''
            import json, os, sys, time
            sys.path.insert(0, {HERE!r})
            os.environ["AGENTLINK_HOME"] = {home!r}
            from agentlink import jobs, protocol
            from agentlink.protocol import Tool
            protocol._hang_trace.AFTER = 0.2

            class Doc:
                Name, Objects = "D", ()

            class Ses:
                out_dir, doc = {self.out!r}, Doc()

            def slow_reading(a):
                time.sleep(0.6)
                return {{"read": 1}}

            job = jobs.start(Tool("wall_read", "does", {{"type": "object"}}, slow_reading), {{}}, Ses())
            waited = jobs.wait_for(job, 0.1)          # the call gives up; the job goes on
            jobs.wait_for(job, 5)
            print(json.dumps({{"waited": waited, "status": job["status"], "armed": protocol._hang_trace._armed is None}}))
        ''')
        r = subprocess.run([sys.executable, "-c", body], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1]), {"waited": False, "status": "done", "armed": True})
        text = open(os.path.join(self.crash, "hang-job-wall_read.txt"), encoding="utf-8").read()
        self.assertIn("slow_reading", text)
        self.assertIn("long, not hung", text)

    def test_the_batch_arms_its_wait_for_a_heavy_read(self):
        # The batch itself needs FreeCAD to run; here, that its wait is inside the watch.
        src = open(os.path.join(PKG, "tools.py"), encoding="utf-8").read()
        at = src.index('with _hang(s, c["tool"], "batch wait"):')
        self.assertIn("_jobs.wait_for(job, max(left, 1))", src[at:at + 200])


class QueueFile(unittest.TestCase):
    """A job's thread and the call's both change the queue's file: one at a
    time (a job ending as a slow read's time was logged put the old file back)."""

    def test_a_time_is_logged_only_once_the_other_writer_is_done(self):
        from agentlink import keep

        old = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp(prefix="agentlink-hubfix3-")
        try:
            class T:
                name, changes = "slow_read_stand_in_3", False

                def changes_for(self, a):
                    return False

            class Ses:
                class doc:
                    Name, Objects = "D", ()

            with jobs._queue_lock:
                t = threading.Thread(target=jobs.note_slow, args=(T(), {}, Ses(), 95.0))
                t.start()
                time.sleep(0.15)
                self.assertFalse(jobs.past_slow(T.name, 1))   # waiting its turn
            t.join(5)
            self.assertTrue(jobs.past_slow(T.name, 1))
        finally:
            if old is None:
                os.environ.pop("AGENTLINK_HOME", None)
            else:
                os.environ["AGENTLINK_HOME"] = old


try:
    import FreeCAD  # noqa: F401

    HAVE = True
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class BatchWaitWithFreeCAD(unittest.TestCase):
    """Written without a FreeCAD to run it in: a heavy read inside a batch,
    slower than the watch's time, leaves its job's stack."""

    def test_a_heavy_read_in_a_batch_that_runs_long_leaves_its_stack(self):
        from _fc import caller, server
        from agentlink import keep

        session, srv = server()
        name = "wall_read_t"

        def slow_reading(a):
            time.sleep(0.7)
            return {"read": 1}

        t = Tool(name, "does", {"type": "object", "properties": {}}, slow_reading)
        t.group = "core"
        srv.add(t)
        keep.HEAVY.add(name)
        was = protocol._hang_trace.AFTER
        protocol._hang_trace.AFTER = 0.2
        try:
            err, b = caller(srv)("batch", {"calls": [{"tool": name, "arguments": {}}]})
        finally:
            protocol._hang_trace.AFTER = was
            keep.HEAVY.discard(name)
        self.assertFalse(err, b)
        self.assertTrue(b["results"][0]["ok"], b)
        text = open(os.path.join(session.out_dir, "crash", f"hang-job-{name}.txt"), encoding="utf-8").read()
        self.assertIn("slow_reading", text)
        self.assertIsNone(protocol._hang_trace._armed)


# ---- 5. a batch's compact lines ---------------------------------------------------------------

class CompactLineSizes(unittest.TestCase):
    def reply(self, rows):
        return batchrec.to_reply({"results": rows, "ran": len(rows)}, 0, "run/batch.json", 1000)

    def test_identical_refusals_stay_whole_each(self):
        e = {"code": "not_found", "message": "body 'Lid': not here — the bodies: Base, Bracket, Cover, Pin."}
        rep = self.reply([{"tool": "object_get", "ok": False, "error": dict(e)} for _ in range(5)])
        for row in rep["results"]:
            self.assertEqual(row["error"], "not_found: " + e["message"])
        self.assertNotIn("healthNote", rep)

    def test_what_a_line_costs(self):
        # A line is its index, tool and ok, and only then what it has to
        # say: nothing rides on every line beyond those three.
        name = "part_primitive"
        read = {"tool": name, "ok": True, "result": {"volume": 1000.0, "faces": list(range(200)), "ms": 12}}
        made = {"tool": name, "ok": True, "result": {"body": "Bracket", "around": {"wall": 900}, "health": {"ok": True, "verdict": "Bracket: valid, closed, 1 solid", "msBy": {"shapes": 700}}}}
        rep = self.reply([read, made] * 50)
        sizes = [len(compact(r).encode()) for r in rep["results"]]
        self.assertEqual(set(rep["results"][0]), {"i", "tool", "ok"})
        self.assertEqual(set(rep["results"][1]), {"i", "tool", "ok", "health"})
        self.assertLessEqual(max(sizes[0::2]), len(name) + 30)
        self.assertLessEqual(max(sizes[1::2]), len(name) + 30 + len(',"health":""') + len("Bracket: valid, closed, 1 solid"))
        fixed = len(compact(rep).encode()) - sum(sizes)
        self.assertLess(fixed, 500)   # the notes and the file, once


if __name__ == "__main__":
    unittest.main()

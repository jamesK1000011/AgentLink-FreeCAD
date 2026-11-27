# SPDX-License-Identifier: LGPL-2.1-or-later
# Fault 81b (live, FreeCAD 1.1.3): in one batch, a gui_input whose step opens
# a menu (QMenu.exec: a nested event loop inside the gui_input call) answered
# the batch early, and the calls after it in the same batch never ran. Now
# those calls run inside the menu's (or dialog's) loop, in order, and the
# batch is answered once with every result. When the menu closes between two
# calls, the rest runs at the batch's own level after the loop ends. Nothing
# runs twice and no second answer goes out when the gui_input returns.
#
# The real batch tool (agentlink/tools.py) runs here on a stand-in FreeCAD
# (every module a mock), in a child process, so no other test sees it. The
# window link is a real gui_link.Link with fakes round it; gui_input is a
# stand-in that "opens" a menu and answers through gui_link.answer_now from
# inside its "loop", as gui_input.Run._finish does.
import io
import json
import os
import subprocess
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


# ---- the child: the real batch on a stand-in FreeCAD --------------------------------------------

def _child(case):
    import tempfile
    from unittest import mock

    class Auto(types.ModuleType):
        def __getattr__(self, k):
            if k.startswith("__"):
                raise AttributeError(k)
            m = mock.MagicMock(name=f"{self.__name__}.{k}")
            setattr(self, k, m)
            return m

    for n in ("FreeCAD", "FreeCADGui", "Part", "Mesh", "MeshPart", "Sketcher", "Import", "TechDraw", "Draft", "Spreadsheet", "PySide", "PySide.QtCore", "PySide.QtGui"):
        sys.modules[n] = Auto(n)
    fc = sys.modules["FreeCAD"]
    fc.GuiUp = False
    fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d)
    os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp(prefix="agentlink-81b-")

    import agentlink_state
    from agentlink import gui_link
    from agentlink.protocol import Tool, ToolError
    from agentlink.tools import Session, build_server

    s = Session(out_dir=tempfile.mkdtemp())

    class Doc:
        Name = Label = "Doc81b"
        UndoCount = 0
        FileName = ""
        Objects = []
        undone = 0

        def undo(self):
            Doc.undone += 1
            self.UndoCount -= 1

        def recompute(self):
            pass

        def openTransaction(self, name=""):
            pass

        def commitTransaction(self):
            pass

        def abortTransaction(self):
            pass

        def isTouched(self):
            return False

    s.doc = Doc()
    srv = build_server(s, lean=False)
    s.server = srv

    # What is open in front: the stand-in menu.
    front = {"menu": None}
    gui_link.modal_info = lambda: None
    gui_link.popup_info = lambda: front["menu"]
    gui_link.wake = lambda: ran.append("wake")
    ran = []
    lvl = {"depth": 0, "max": 0, "inside": []}

    def gui_input(a):
        steps = a.get("steps") or []
        ran.append("gui_input:" + ",".join(sorted(k for st in steps for k in st)))
        body = {"steps": [{"i": i, **st} for i, st in enumerate(steps)]}
        for st in steps:
            if st.get("key") == "Escape" or st.get("menu_item"):
                front["menu"] = None
        opens = [st["open"] for st in steps if st.get("open")]
        if not opens:
            body["open"] = None if front["menu"] is None else {"kind": "menu"}
            return body
        front["menu"] = {"class": "QMenu", "kind": "menu", "title": opens[-1], "items": ["A", "B"], "buttons": []}
        body["open"] = {"kind": "menu", "title": opens[-1]}
        # Inside the menu's own loop (QMenu.exec): the answer goes out from
        # here (gui_input.Run._finish), and the loop then runs until the
        # menu is closed.
        lvl["depth"] += 1
        lvl["max"] = max(lvl["max"], lvl["depth"])
        try:
            answered = gui_link.answer_now("gui_input", body)
            body["answeredNow"] = answered
        finally:
            lvl["depth"] -= 1
        return body

    def probe(a):
        ran.append(f"probe:{a.get('n')}")
        lvl["inside"].append((a.get("n"), lvl["depth"], front["menu"] is not None))
        if a.get("fail"):
            raise ToolError("invalid_input", "probe: told to fail")
        return {"n": a.get("n"), "menuOpen": front["menu"] is not None}

    def change(a):
        ran.append(f"change:{a.get('n')}")
        s.doc.UndoCount += 1
        return {"n": a.get("n")}

    srv.tools["gui_input"].fn = gui_input
    obj = {"type": "object", "properties": {"n": {}, "fail": {"type": "boolean"}}}
    srv.tools["probe_state"] = Tool("probe_state", "A read for the 81b tests.", obj, probe)
    srv.tools["probe_change"] = Tool("probe_change", "A change for the 81b tests.", obj, change, changes=True)

    link = gui_link.Link.__new__(gui_link.Link)
    link.calls, link.front, link.going, link.in_call, link.busy = [], None, False, True, "batch"
    link.session, link._dialog = s, None
    import threading

    link._lock = threading.Lock()
    link._writes = lambda: link._lock
    agentlink_state.link = link
    f = io.StringIO()
    call = {"id": 81, "name": "batch", "f": f, "answered": False}
    link.calls.append(call)

    def gi(*steps):
        return {"tool": "gui_input", "steps": list(steps)}

    def pr(n, **kw):
        return {"tool": "probe_state", "n": n, **kw}

    args = {
        "menu_read_escape": {"calls": [gi({"click": 1, "open": "Part"}), pr(1), gi({"key": "Escape"})]},
        "escape_then_more": {"calls": [gi({"click": 1, "open": "Part"}), gi({"key": "Escape"}), pr(2), {"tool": "probe_change", "n": 3}]},
        "menu_left_open": {"calls": [gi({"click": 1, "open": "Part"}), pr(1)]},
        "submenu": {"calls": [gi({"click": 1, "open": "Part"}), gi({"click": 2, "open": "Sub"}), pr(1), gi({"key": "Escape"})]},
        "refused_inside": {"calls": [{"tool": "probe_change", "n": 0}, gi({"click": 1, "open": "Part"}),
                                     {"tool": "probe_change", "n": 1}, pr(2, fail=True), pr(3)]},
        "refused_outside": {"calls": [{"tool": "probe_change", "n": 0}, gi({"click": 1, "open": "Part"}), gi({"key": "Escape"}),
                                      {"tool": "probe_change", "n": 1}, pr(2, fail=True)]},
        "no_menu": {"calls": [gi({"click": 1}), pr(1)]},
    }[case]
    args.setdefault("rollback", True)
    r = srv.handle({"jsonrpc": "2.0", "id": 81, "method": "tools/call", "params": {"name": "batch", "arguments": args}})
    returned = json.loads(r["result"]["content"][0]["text"])
    written = [json.loads(x) for x in f.getvalue().splitlines() if x.strip()]
    return {"returned": returned, "written": [json.loads(w["result"]["content"][0]["text"]) for w in written],
            "writtenIds": [w["id"] for w in written], "answered": call["answered"], "ran": ran, "inside": lvl["inside"], "maxDepth": lvl["max"],
            "undone": Doc.undone, "menuOpen": front["menu"] is not None, "nestedSince": getattr(link, "nested_since", None), "callDeadline": call.get("deadline")}


_cache = {}


def run_case(case):
    if case not in _cache:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "child", case], capture_output=True, text=True, timeout=120, cwd=ROOT)
        if r.returncode != 0:
            raise AssertionError(f"child {case} failed:\n{r.stderr[-4000:]}")
        _cache[case] = json.loads(r.stdout.strip().splitlines()[-1])
    return _cache[case]


class NestedBatch(unittest.TestCase):
    def test_calls_after_the_menu_run_inside_it_and_one_answer_goes_out(self):
        got = run_case("menu_read_escape")
        # One answer, written from inside the menu's loop, with all three results.
        self.assertEqual(got["writtenIds"], [81])
        body = got["written"][0]
        self.assertEqual([x["tool"] for x in body["results"]], ["gui_input", "probe_state", "gui_input"])
        self.assertTrue(all(x["ok"] for x in body["results"]), body)
        self.assertIn("nested", body)
        self.assertNotIn("not_run", body)
        self.assertEqual(body["results"][1]["result"]["menuOpen"], True)
        # Each call ran once; the read ran inside the menu's loop.
        self.assertEqual(got["ran"].count("probe:1"), 1)
        self.assertEqual(sum(1 for x in got["ran"] if x.startswith("gui_input")), 2)
        self.assertEqual(got["inside"], [[1, 1, True]])
        self.assertFalse(got["menuOpen"])
        self.assertTrue(got["answered"])
        # The batch's own return (dropped by the link: answered) is that same answer.
        self.assertEqual([x["tool"] for x in got["returned"]["results"]], [x["tool"] for x in body["results"]])
        self.assertEqual(got["returned"]["nested"], body["nested"])
        # The heartbeat's working mark is off again, and gui_input's own deadline is lifted.
        self.assertIsNone(got["nestedSince"])
        self.assertIsNone(got["callDeadline"])

    def test_menu_closed_between_calls_rest_runs_at_the_batch_level(self):
        got = run_case("escape_then_more")
        # Not answered from inside: the batch returned by itself, whole.
        self.assertEqual(got["writtenIds"], [])
        self.assertFalse(got["answered"])
        body = got["returned"]
        self.assertEqual([x["tool"] for x in body["results"]], ["gui_input", "gui_input", "probe_state", "probe_change"])
        self.assertEqual(body["ran"], 4)
        self.assertNotIn("nested", body)
        # probe 2 ran after the menu closed, outside its loop; nothing twice.
        self.assertEqual(got["inside"], [[2, 0, False]])
        # The menu's loop is woken when it is seen closed, so it ends now.
        self.assertEqual(got["ran"], ["gui_input:click,open", "gui_input:key", "wake", "probe:2", "change:3"])

    def test_menu_left_open_at_the_end(self):
        got = run_case("menu_left_open")
        self.assertEqual(got["writtenIds"], [81])
        body = got["written"][0]
        self.assertEqual([x["tool"] for x in body["results"]], ["gui_input", "probe_state"])
        self.assertEqual(body["results"][0]["result"]["open"]["kind"], "menu")
        self.assertTrue(got["menuOpen"])  # left for the next call (gui_input menu_item, Escape, gui_unstick)

    def test_submenu_inside_the_menu(self):
        got = run_case("submenu")
        self.assertEqual(got["writtenIds"], [81])
        body = got["written"][0]
        self.assertEqual([x["tool"] for x in body["results"]], ["gui_input", "gui_input", "probe_state", "gui_input"])
        self.assertEqual(got["maxDepth"], 2)
        self.assertEqual(got["ran"].count("probe:1"), 1)
        self.assertEqual(got["inside"], [[1, 2, True]])

    def test_refused_inside_the_menu_is_not_rolled_back(self):
        got = run_case("refused_inside")
        self.assertEqual(got["writtenIds"], [81])
        body = got["written"][0]
        self.assertEqual((body["refused"]["call"], body["notRun"]), (3, [4]))
        self.assertEqual(body["undone"], 0)
        self.assertIn("rollbackNote", body)
        self.assertEqual(got["undone"], 0)
        self.assertNotIn("probe:3", got["ran"])

    def test_refused_after_the_menu_closed_rolls_back(self):
        got = run_case("refused_outside")
        self.assertEqual(got["writtenIds"], [])
        body = got["returned"]
        self.assertEqual((body["refused"]["call"], body["notRun"]), (4, []))
        self.assertEqual(body["undone"], 2)  # both changes, the one before the menu too
        self.assertNotIn("rollbackNote", body)

    def test_gui_input_that_opens_nothing(self):
        got = run_case("no_menu")
        self.assertEqual(got["writtenIds"], [])
        self.assertEqual([x["tool"] for x in got["returned"]["results"]], ["gui_input", "probe_state"])


class LinkHook(unittest.TestCase):
    """Link.answer_now with the batch's hook (session.batch_now cont)."""

    def link(self, cont, live=False):
        from test_gui_link_dialog import gui_link

        link = gui_link.Link.__new__(gui_link.Link)
        import threading

        lock = threading.Lock()
        link._writes = lambda: lock
        link.calls = []
        link.session = types.SimpleNamespace(batch_now={"results": [], "i": 0, "n": 2, "tool": "gui_input", "answered": False, "cont": cont}, live_now=live)
        f = io.StringIO()
        link.calls.append({"id": 9, "name": "batch", "f": f, "answered": False})
        return link, f

    def test_whole_answer_written_once(self):
        link, f = self.link(lambda t, b: {"results": [{"tool": t, "ok": True, "result": b}], "ran": 1})
        self.assertTrue(link.answer_now("gui_input", {"x": 1}))
        self.assertEqual(json.loads(json.loads(f.getvalue())["result"]["content"][0]["text"])["ran"], 1)
        self.assertFalse(link.answer_now("gui_input", {"x": 1}))  # no second answer
        self.assertEqual(len(f.getvalue().splitlines()), 1)

    def test_answered_deeper(self):
        link, f = self.link(lambda t, b: True)
        self.assertTrue(link.answer_now("gui_input", {}))
        self.assertEqual(f.getvalue(), "")

    def test_closed_meanwhile(self):
        link, f = self.link(lambda t, b: None)
        self.assertFalse(link.answer_now("gui_input", {}))
        self.assertEqual(f.getvalue(), "")
        self.assertFalse(link.calls[-1]["answered"])

    def test_live_run_batch_keeps_its_own_way(self):
        seen = []
        link, f = self.link(lambda t, b: seen.append(t), live=True)
        self.assertFalse(link.answer_now("gui_input", {}))
        self.assertEqual(seen, [])


class Watchdog(unittest.TestCase):
    """The supervisor's rule: a menu or dialog that a batch works inside
    (working in the heartbeat) is not closed as one that holds the call."""

    def test_rule_reads_working(self):
        src = open(os.path.join(ROOT, "agentlink", "supervise.py"), encoding="utf-8").read()
        self.assertIn('if pop and not pop.get("working") and held >', src)
        self.assertIn('not dlg.get("working") and waited >', src)

    def test_heartbeat_marks_working(self):
        src = open(os.path.join(ROOT, "agentlink", "gui_link.py"), encoding="utf-8").read()
        self.assertIn('work = {"working": self.nested_since}', src)
        self.assertIn('"popup": {**pop, **work} if pop else None', src)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "child":
        out = _child(sys.argv[2])
        sys.stdout.write("\n" + json.dumps(out, default=str) + "\n")
    else:
        unittest.main()

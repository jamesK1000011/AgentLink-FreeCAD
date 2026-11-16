# SPDX-License-Identifier: LGPL-2.1-or-later
# The Activity tab reads for a layman: each call's Did is a short plain
# sentence (never raw arguments, brackets or folders), its Result a short
# outcome with no path, lines cut at the right end with the whole line and
# the raw call in the tooltip, and the columns fitted to a narrow dock.
# All headless, with stand-ins for Qt; with FreeCAD, every tool the server
# lists is checked too.
import glob
import json
import os
import re
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentlink import activity, echo, panel_tabs, tooldata  # noqa: E402
from _fc import HAVE  # noqa: E402

BRACKETS = re.compile(r"[\[\]{}]")
HOME = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\?Users)")
FOLDER = re.compile(r"(?<![\w.])(?:~|[A-Za-z]:)?[\\/][^\s]*[\\/]")


def every_tool():
    """Every tool Agent Link defines, read from its sources: the core's and
    every listed family's Tool(...) calls and the data-defined tools."""
    names = set()
    for f in glob.glob(os.path.join(ROOT, "agentlink", "**", "*.py"), recursive=True):
        with open(f, encoding="utf-8") as fh:
            names |= set(re.findall(r'Tool\(\s*"([a-z0-9_]+)"', fh.read()))
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as fh:
        names |= set(json.load(fh)["entries"])
    return sorted(names)


# Arguments of the kinds tools take, paths among them.
SAMPLE = {"object": "Pad", "body": "Body", "sketch": "Sketch", "feature": "Pad", "page": "Page", "document": "WindowTest",
          "path": "/Users/someone/AgentLink/out/WindowTest.FCStd", "objects": ["Box", "Cylinder"], "name": "Std_ViewIsometric",
          "topic": "reverse", "values": {"Length": 24}, "steps": [{"click": {"widget": {"text": "Pin a Note"}}}, {"wait": 3000}],
          "kind": "cylinder", "length": 20, "at": [20, 20, 0], "faces": [{"at": [0, 0, 1]}], "calls": [{"tool": "x"}]}


class EveryTool(unittest.TestCase):
    def test_the_scan_finds_the_core_and_the_families(self):
        names = every_tool()
        self.assertGreater(len(names), 300)
        for n in ("gui_input", "doc_save", "pd_pad", "td_balloon", "meshobj_decimate", "dialog_answer", "session_state"):
            self.assertIn(n, names)

    def check(self, name, did, bare=False):
        self.assertTrue(did.strip(), name)
        self.assertIsNone(BRACKETS.search(did), f"{name}: {did}")
        self.assertIsNone(HOME.search(did), f"{name}: {did}")
        self.assertIsNone(FOLDER.search(did), f"{name}: {did}")
        if bare:  # no arguments: nothing but the table's words or the friendly name
            self.assertNotIn("_", did, f"{name}: a raw name in {did!r}")
        self.assertLessEqual(len(did), activity.MAX_TEXT)

    def test_every_tool_has_words_without_brackets_or_paths(self):
        for name in every_tool():
            for args in ({}, SAMPLE):
                self.check(name, activity.did(name, args), bare=not args)
                self.check(name, activity.did(name, args, {"path": SAMPLE["path"], "document": "WindowTest"}))

    def test_every_tools_result_has_no_path(self):
        for name in every_tool():
            for body in ({}, {"path": SAMPLE["path"]}, {"note": "Saved to /home/someone/AgentLink/x.FCStd. Reopen it."}):
                r = activity.outcome(name, True, body, SAMPLE)
                self.assertIsNone(HOME.search(r), f"{name}: {r}")
                self.assertIsNone(FOLDER.search(r), f"{name}: {r}")
                self.assertFalse(re.match(r"^(?:note|path):", r), f"{name}: {r}")

    def test_the_data_names_real_tools(self):
        names = set(every_tool())
        self.assertEqual(sorted(set(activity.PHRASES) - names), [])
        self.assertEqual(sorted(set(activity.RESULTS) - names), [])

    @unittest.skipUnless(HAVE, "FreeCAD is not importable here")
    def test_every_listed_tool(self):
        from _fc import server

        _s, srv = server()
        for name in srv.tools:
            self.check(name, activity.did(name, {}), bare=True)


class Phrases(unittest.TestCase):
    def test_gui_input_steps_summarised(self):
        args = {"steps": [{"click": {"widget": {"text": "Pin a &Note"}}}, {"wait": 3000}, {"click": {"view_world": [0, 0, 10]}},
                          {"shot": "after"}]}
        self.assertEqual(activity.did("gui_input", args), "Clicked Pin a Note, clicked the part, took a picture of the window")
        self.assertEqual(activity.did("gui_input", {"steps": [{"wait": 3000}]}), "Waited")
        self.assertEqual(activity.did("gui_input", {"steps": [{"type": "hi", "target": {"widget": {"class": "QLineEdit"}}},
                                                              {"drag": {"from": {"view": [1, 2]}, "to": {"view": [3, 4]}}}]}),
                         "Typed into a text field, dragged on the view")
        self.assertEqual(activity.did("gui_input", {"steps": [{"key": "Escape"}, {"click": {"tab": {"text": "Activity"}}},
                                                              {"click": {"item": {"text": "Pad"}, "check": True}},
                                                              {"scroll": {"view": [5, 5]}, "dy": 2}]}),
                         "Pressed Esc, opened the Activity tab, ticked Pad and 1 more step")
        self.assertEqual(activity.did("gui_input", {"steps": [{"click": {"view": [1, 1]}}, {"click": {"view": [2, 2]}}]}),
                         "Clicked the 3D view")  # repeats folded

    def test_the_wanted_phrases(self):
        cases = [
            (("dialog_answer", {"button": "OK"}, {"pressed": "OK", "dialog": {"title": "Note"}}), "Answered the Note dialog: OK"),
            (("doc_save", {}, {"document": "WindowTest", "path": "/Users/someone/AgentLink/WindowTest.FCStd"}), "Saved WindowTest"),
            (("doc_close", {"documents": ["WindowTest"], "discard": True}, {}), "Closed WindowTest (not saved)"),
            (("object_set", {"object": "Pad", "values": {"Length": 24}}, {}), "Set Pad Length to 24 mm"),
            (("object_set", {"object": "Pad", "values": {"Placement": {"at": [0, 0, 1]}}}, {}), "Moved Pad"),
            (("cmd_run", {"name": "Std_ViewIsometric"}, {}), "Ran Isometric"),
            (("workbench", {"activate": "PartDesignWorkbench"}, {}), "Switched to Part Design"),
            (("workbench", {"activate": "Part Design"}, {}), "Switched to Part Design"),
            (("guide_read", {"topic": "reverse"}, {}), "Read the reverse guide"),
            (("session_state", {}, {}), "Read the session"),
            (("report_read", {}, {}), "Read the Report view"),
            (("note_list", {}, {}), "Read the notes"),
            (("selection", {"objects": ["Box"]}, {}), "Selected Box"),
            (("selection", {"clear": True}, {}), "Cleared the selection"),
            (("menu_list", {}, {}), "Read the menus"),
            (("menu_run", {"path": ["View", "Standard views", "&Isometric"]}, {}), "Chose Isometric from the View menu"),
            (("pd_pad", {"sketch": "Sketch", "length": 20}, {}), "Padded Sketch by 20 mm"),
            (("show", {"objects": ["Box"], "visible": False}, {}), "Hid Box"),
            (("object_group", {"action": "list"}, {}), "Read the groups"),
        ]
        for (name, args, body), want in cases:
            self.assertEqual(activity.did(name, args, body), want, name)

    def test_fallback_is_a_friendly_name_and_main_argument(self):
        self.assertEqual(activity.did("meshobj_smooth", {"object": "Scan", "iterations": [3]}), "Mesh smooth on Scan")
        self.assertEqual(activity.did("sheet_import", {"path": "/home/someone/x.csv"}), "Imported Spreadsheet on x.csv")
        self.assertEqual(activity.did("zz_frob_list", {}), "Listed Zz frob")

    def test_command_text_from_its_name(self):
        self.assertEqual(activity.command_text("Std_ViewFitAll"), "Fit all")
        self.assertEqual(activity.command_text("PartDesign_Pad"), "Pad")
        self.assertEqual(activity.command_text("Part_Primitives"), "Primitives")


class Results(unittest.TestCase):
    def test_plain_outcomes(self):
        self.assertEqual(activity.outcome("pd_pad", True, {"feature": "Pad", "volume": 24000.0}), "Pad made, 24000 mm³")
        self.assertEqual(activity.outcome("doc_save", True, {"path": "/Users/someone/AgentLink/WindowTest.FCStd"}), "Saved as WindowTest.FCStd")
        self.assertEqual(activity.outcome("cmd_run", True, {"ran": "Std_ViewIsometric"}), "Done")
        self.assertEqual(activity.outcome("dialog_answer", True, {"dialog": None, "note": "No dialog or task panel is open."}), "No dialog open")
        self.assertEqual(activity.outcome("workbench", True, {"active": "PartDesignWorkbench"}, {"activate": "PartDesign"}), "Part Design in front")
        self.assertEqual(activity.outcome("x_note", True, {"note": "The change is kept if saved. Undo with history_undo."}),
                         "The change is kept if saved")
        self.assertEqual(activity.outcome("view_render", True, {"path": "/Users/someone/AgentLink/shots/a.png"}), "Wrote a.png")

    def test_refused_in_plain_words(self):
        r = activity.outcome("doc_open", False, {"error": {"code": "not_found", "message": "input.path: /Users/someone/x.FCStd is not there. Look again."}})
        self.assertEqual(r, "Refused: path: x.FCStd is not there")
        self.assertEqual(activity.outcome("x", False, {}), "Refused")


class Privacy(unittest.TestCase):
    def test_paths_cut_to_file_names_and_homes_gone(self):
        self.assertEqual(activity.plain("see /Users/someone and ~/AgentLink/crash/x.log"), "see home folder and x.log")
        self.assertEqual(activity.plain("C:\\Users\\someone\\out\\a.step, /home/someone"), "a.step, home folder")
        self.assertEqual(activity.plain("1/2 of a/b and /tmp"), "1/2 of a/b and tmp")
        self.assertEqual(activity.raw_call("doc_save", {"path": "/Users/someone/AgentLink/a.FCStd"}), 'doc_save {"path": "a.FCStd"}')

    def test_activity_row_is_plain_and_the_tooltip_has_the_call(self):
        e = {"time": "10:01:02", "ok": True, "what": "Saved WindowTest", "result": "path: /Users/someone/AgentLink/WindowTest.FCStd",
             "call": 'doc_save {"path": "/Users/someone/AgentLink/WindowTest.FCStd"}'}
        cols, tip = panel_tabs.activity_row(e)
        self.assertEqual(cols, ["10:01:02", "Saved WindowTest", "path: WindowTest.FCStd"])
        self.assertEqual(tip, '10:01:02 — Saved WindowTest — path: WindowTest.FCStd\n\nCall: doc_save {"path": "WindowTest.FCStd"}')
        self.assertIsNone(HOME.search(tip))


class Declared(unittest.TestCase):
    def setUp(self):
        self.saved = dict(activity.DECLARED)

    def tearDown(self):
        activity.DECLARED.clear()
        activity.DECLARED.update(self.saved)

    def test_an_addons_phrases(self):
        activity.declare(types.SimpleNamespace(PHRASES={"mine_slice": ["Sliced {object}", "Sliced the part"], "mine_": "Did a mine thing"}))
        self.assertEqual(activity.did("mine_slice", {"object": "Lid"}), "Sliced Lid")
        self.assertEqual(activity.did("mine_slice", {}), "Sliced the part")
        self.assertEqual(activity.did("mine_other", {}), "Did a mine thing")

    def test_echo_declare_passes_them_on(self):
        saved = (echo.SHOWN, echo.OPENS)
        try:
            echo.declare(types.SimpleNamespace(PHRASES={"mine_paint": "Painted {object}"}))
            self.assertEqual(activity.did("mine_paint", {"object": "Lid"}), "Painted Lid")
        finally:
            echo.SHOWN, echo.OPENS = saved

    def test_a_tools_own_template_comes_first(self):
        self.assertEqual(activity.did("pd_pad", {"sketch": "S"}, None, "Grew {sketch}"), "Grew S")

    def test_tool_data_takes_an_activity_template(self):
        doc = {"dataVersion": "1.0.0", "entries": {"mine_slice": {"group": "mine", "description": "Slice a part for printing, with presets.",
                                                                  "inputSchema": {"type": "object", "properties": {}}, "changes": False,
                                                                  "source": "here", "date": "2026-11-15", "activity": "Sliced {object}"}}}
        self.assertEqual(tooldata.check(doc), [])
        doc["entries"]["mine_slice"]["activity"] = 3
        self.assertTrue(tooldata.check(doc))


class Rec:
    """A stand-in that records every call made on it."""

    def __init__(self, width=355):
        self.calls = []
        self.width = width
        self._head = None

    def __getattr__(self, name):
        def call(*a):
            self.calls.append((name, a))
            return None

        return call

    def header(self):
        if self._head is None:
            self._head = Rec()
        return self._head

    def viewport(self):
        return types.SimpleNamespace(width=lambda: self.width)


QtCore = types.SimpleNamespace(Qt=types.SimpleNamespace(ElideRight="ElideRight", ElideMiddle="ElideMiddle",
                                                        ScrollBarAlwaysOff="AlwaysOff"))
QtWidgets = types.SimpleNamespace(QHeaderView=types.SimpleNamespace(
    ResizeMode=types.SimpleNamespace(ResizeToContents="Contents", Stretch="Stretch", Interactive="Interactive")))


class Columns(unittest.TestCase):
    def test_elided_at_the_right_and_fitted_to_a_narrow_dock(self):
        tree = Rec(width=355)
        panel_tabs.setup_activity(tree, QtCore, QtWidgets)
        calls = dict(tree.calls)
        self.assertEqual(calls["setTextElideMode"], ("ElideRight",))
        self.assertEqual(calls["setHorizontalScrollBarPolicy"], ("AlwaysOff",))
        self.assertEqual(calls["setHeaderLabels"], (["Time", "Did", "Result"],))
        head = tree.header().calls
        self.assertIn(("setStretchLastSection", (False,)), head)
        modes = {a[0]: a[1] for n, a in head if n == "setSectionResizeMode"}
        self.assertEqual(modes, {0: "Contents", 1: "Stretch", 2: "Interactive"})
        widths = [a for n, a in tree.calls if n == "setColumnWidth"]
        self.assertEqual(widths, [(2, panel_tabs.result_width(355))])
        # Time (about 60) + Result leave Did over a third of 355 px.
        self.assertGreater(355 - 60 - panel_tabs.result_width(355), 355 // 3)
        self.assertEqual(panel_tabs.result_width(100), panel_tabs.ACTIVITY_RESULT_MIN)

    def test_no_middle_elision_left_in_the_panel(self):
        with open(os.path.join(ROOT, "agentlink", "panel.py"), encoding="utf-8") as f:
            self.assertNotIn("ElideMiddle", f.read())


if __name__ == "__main__":
    unittest.main()

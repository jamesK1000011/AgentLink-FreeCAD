# SPDX-License-Identifier: LGPL-2.1-or-later
# Window round 9 (17 Nov), stand-ins for:
#   - the call's selection sent once more at the end of its echo (round 8:
#     Foot.Face6, Post.Face1 and a channel's trace held selected but not
#     drawn lit); an add-on's declared read selection framed and uncovered
#     (pcb_order_package's board inside its enclosure).
#   - the Mesh Info box hidden, never deleted; a see-through cover's edges
#     put out (a sphere's seam edge across the unwrapped cap).
#   - a batch's own words at its end, its row, the rings put out; job_start,
#     pref_import, td_centermarks and report_read in plain words.
#   - the caption top left on a TechDraw page (the title block is bottom
#     right); td_table's text the asked size on the paper.
import json
import os
import sys
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import activity, echo, report_watch  # noqa: E402
from test_echo_hold import Replay as _Replay, Tool  # noqa: E402
from test_echo_maps import WithStandIns  # noqa: E402


def src(*parts):
    with open(os.path.join(HERE, "..", *parts), encoding="utf-8") as f:
        return f.read()


class _SelEx:
    def __init__(self, doc, obj, subs=()):
        self.DocumentName, self.ObjectName, self.SubElementNames = doc, obj, tuple(subs)


class Reselect(WithStandIns):
    def setUp(self):
        super().setUp()
        self.log = []
        self.now = []
        self.gui.Selection = types.SimpleNamespace(
            getSelectionEx=lambda doc="", resolve=1: list(self.now),
            clearSelection=lambda: self.log.append(("clear",)),
            addSelection=lambda *a: self.log.append(("add",) + a))

    def test_the_same_entries_sent_again_unresolved(self):
        self.now = [_SelEx("Hub", "Post", ["Face1"]), _SelEx("Hub", "Pattern")]
        got = echo.reselect()
        self.assertEqual(got, ["Post.Face1", "Pattern"])
        self.assertEqual(self.log, [("clear",), ("add", "Hub", "Post", "Face1"), ("add", "Hub", "Pattern")])

    def test_nothing_selected_or_too_many(self):
        self.assertIsNone(echo.reselect())
        self.now = [_SelEx("Hub", f"B{i}") for i in range(echo.RESELECT_MOST + 1)]
        self.assertIsNone(echo.reselect())
        self.assertEqual(self.log, [])

    def test_wired_last_and_the_mesh_box_hidden_again(self):
        e = src("agentlink", "echo.py")
        at = e.index('self._step(tr, "reselected", reselect)')
        self.assertLess(e.index('self._step(tr, "seeThrough", see_through'), at)
        self.assertLess(e.index('self._step(tr, "modelTab", _model_tab_back)'), at)
        self.assertLess(at, e.index('self._step(tr, "viewsFollow", views_follow)', at))
        self.assertIn('self._step(tr, "meshInfo", mesh_info_box)', e[at:at + 400])


class MeshInfoBox(WithStandIns):
    def setUp(self):
        super().setUp()
        self.sel = []
        self.gui.Selection = types.SimpleNamespace(getSelection=lambda: list(self.sel))
        self.gui.Control = types.SimpleNamespace(activeDialog=lambda: None,
                                                 clearTaskWatcher=lambda: self.fail("never deleted"))
        self.gui.activeWorkbench = lambda: types.SimpleNamespace(name=lambda: "MeshWorkbench")
        self.box = types.SimpleNamespace(shown=True)
        self.box.setVisible = lambda on: setattr(self.box, "shown", on)

    def test_hidden_then_shown(self):
        with mock.patch.object(echo, "mesh_info_widgets", lambda mw=None: [self.box]):
            self.sel = [types.SimpleNamespace(TypeId="Part::Feature")]
            self.assertEqual(echo.mesh_info_box(), "hidden")
            self.assertFalse(self.box.shown)
            self.sel = [types.SimpleNamespace(TypeId="Mesh::Feature")]
            self.assertTrue(echo.mesh_info_box().startswith("kept"))
            self.assertTrue(self.box.shown)

    def test_gone_says_so(self):
        with mock.patch.object(echo, "mesh_info_widgets", lambda mw=None: []):
            self.sel = [types.SimpleNamespace(TypeId="Mesh::Feature")]
            self.assertTrue(echo.mesh_info_box().startswith("not there"))
            self.sel = []
            self.assertIsNone(echo.mesh_info_box())

    def test_other_workbench_left_alone(self):
        self.gui.activeWorkbench = lambda: types.SimpleNamespace(name=lambda: "PartWorkbench")
        self.assertIsNone(echo.mesh_info_box())


class EdgesOff(unittest.TestCase):
    def test_flat_lines_to_shaded_and_put_back(self):
        del echo._view_props[:]
        self.addCleanup(echo._view_props.clear)
        vo = types.SimpleNamespace(DisplayMode="Flat Lines", PropertiesList=["DisplayMode"],
                                   listDisplayModes=lambda: ["Flat Lines", "Shaded", "Wireframe"])
        globe = types.SimpleNamespace(Label="Globe", Name="Sphere", ViewObject=vo, Document=types.SimpleNamespace(Name="M"))
        plain = types.SimpleNamespace(Label="Wire", Name="Wire", Document=types.SimpleNamespace(Name="M"),
                                      ViewObject=types.SimpleNamespace(DisplayMode="Wireframe", PropertiesList=["DisplayMode"],
                                                                       listDisplayModes=lambda: ["Wireframe"]))
        self.assertEqual(echo.edges_off([globe, plain]), ["Globe"])
        self.assertEqual(vo.DisplayMode, "Shaded")
        self.assertEqual(echo._view_props, [("M", "Sphere", "DisplayMode", "Flat Lines")])  # put back at the next change


class _O:
    def __init__(self, name):
        self.Name = self.Label = name
        self.TypeId = "Part::Feature"
        self.ViewObject = types.SimpleNamespace(Visibility=True)


class DeclaredReadFramed(WithStandIns):
    def test_the_board_selected_framed_and_uncovered(self):
        board = _O("PCB test")
        doc = types.SimpleNamespace(Name="E", Objects=[board, _O("Block plain")], getObject=lambda n: None)
        session = types.SimpleNamespace(doc=doc)
        echo.FreeCAD.ActiveDocument = types.SimpleNamespace(Name="E")
        e = echo.Echo(session)
        calls = []
        with mock.patch.object(echo, "declared_selection", lambda *a: ["PCB test"]), \
                mock.patch.object(echo, "front_3d", lambda d: None), \
                mock.patch.object(echo, "_select", lambda objs: calls.append(("select", [o.Label for o in objs]))), \
                mock.patch.object(echo, "fit", lambda animate=True, selection=False: calls.append(("fit", selection)) or "selection"), \
                mock.patch.object(echo, "uncover", lambda d, objs, *a: ["PCB enclosure"]), \
                mock.patch.object(echo, "reselect", lambda: ["PCB test"]), \
                mock.patch.object(echo, "views_follow", lambda: 0):
            self.gui.Selection = types.SimpleNamespace(getSelection=lambda: [board])  # already selected: framed all the same
            got = e._read_shown("pcb_order_package", {"board": "PCB test"}, {"package": "/o/PCB_test_order.zip"})
        self.assertEqual(got, {"selected": ["PCB test"], "framed": "the read's object", "uncovered": ["PCB enclosure"],
                               "reselected": ["PCB test"]})
        self.assertEqual(calls, [("select", ["PCB test"]), ("fit", True)])


class BatchEnd(_Replay):
    def test_the_batch_says_its_own_words_and_puts_the_rings_out(self):
        self.session.echo_look = None
        self.call(Tool("batch", False), {"title": "Peg plate", "calls": [{}] * 6},
                  {"ran": 6, "results": [{"tool": "part_primitive", "ok": True}] * 6})
        kinds = [e[0] for e in self.events]
        self.assertIn("ringsOff", kinds)
        caps = [e[1] for e in self.events if e[0] == "caption"]
        self.assertEqual(caps, ["Peg plate — ran 6 calls in one batch: 6 ok"])
        self.assertEqual(self.session.echo_look["tool"], "batch")

    def test_inside_another_batch_it_waits(self):
        self.session.batch_now = {"i": 0, "n": 2}
        self.call(Tool("batch", False), {"calls": [{}]}, {"ran": 1, "results": [{"ok": True}]})
        self.assertEqual([e for e in self.events if e[0] == "caption"], [])

    def test_words(self):
        self.assertEqual(activity.batch_words({}, {"ran": 6, "results": [{"ok": True}] * 5 + [{"ok": False}]}),
                         "Ran 6 calls in one batch: 5 ok, 1 refused")
        self.assertEqual(activity.batch_words({}, {"lines": [{"ok": True}], "notRun": 3}), "Ran 1 call in one batch: 1 ok, 3 not run")
        self.assertIsNone(activity.batch_words({}, {"results": []}))
        self.assertIn('"title": {"type": "string"}', src("agentlink", "tools.py"))


class PlainWords(unittest.TestCase):
    def read(self, name, args, body):
        return echo.read_words(activity.did(name, args, body), activity.outcome(name, True, body, args))

    def change(self, name, args, body):
        return echo.change_words(activity.did(name, args, body), body, name)

    def test_job_start(self):
        a = {"tool": "measure_mass", "arguments": {"body": "Peg"}}
        got = self.read("job_start", a, {"volume": 6000, "job": "job-0123abcd"})
        # round 10: the inner read's own words after "Ran a job:"
        self.assertTrue(got.startswith("Ran a job: "), got)
        self.assertNotIn("Job start", got)
        a = {"tool": "meshobj_info", "arguments": {"mesh": "Globe fine"}}
        got = self.read("job_start", a, {"job": "job-0123abcd", "status": "running", "tool": "meshobj_info", "running": 2})
        self.assertTrue(got.startswith("Started a job: "), got)
        self.assertTrue(got.endswith(": running, 2 s so far"), got)
        self.assertNotIn("meshobj_info", got)

    def test_pref_import_counts(self):
        body = {"from": "/x/1.0/user.cfg", "groups": ["BaseApp", "Mod"], "settings": 412,
                "note": "Merged: the file's values win, this one's other settings stay — except the guarded ones"}
        got = self.change("pref_import", {}, body)
        self.assertEqual(got, "Brought in settings from user.cfg: 412 settings in 2 groups")

    def test_td_centermarks_grammar(self):
        body = {"views": [{"view": "Plate", "circles": 2}], "extend": 2}
        self.assertEqual(self.change("td_centermarks", {}, body), "Drew centre marks on the drawing's holes: 2 circles on 1 view")
        self.assertEqual(activity.key_value({"views": ["A"]}), "1 view")
        self.assertEqual(activity.key_value({"views": ["A", "B"]}), "2 views")
        self.assertEqual(activity.key_value({"axes": ["A"]}), "1 axis")

    def test_report_read_names_the_first(self):
        body = {"found": True, "count": 798, "problems": 1, "first": "Traceback: KeyError: 'deadline' (gui_link.py)"}
        got = self.read("report_read", {"problems": True}, body)
        self.assertIn("1 problem, 798 lines; first: Traceback: KeyError: 'deadline'", got)  # round 10: counts first
        self.assertEqual(report_watch.first_problem(["15:00:05  <Exception> Shape index 29 out of bound 0"]),
                         "<Exception> Shape index 29 out of bound 0")


class PageCaption(unittest.TestCase):
    def test_top_left_on_a_page(self):
        most, x, y = echo.caption_box(1200, 800, 300, 60, page=True)
        self.assertEqual((x, y), (echo.CAPTION_MARGIN, echo.CAPTION_MARGIN))
        _m, x, y = echo.caption_box(1200, 800, 300, 60)
        self.assertGreater(x, 600)
        self.assertGreater(y, 600)  # a 3D view: bottom right, as before
        page = types.SimpleNamespace(metaObject=lambda: types.SimpleNamespace(className=lambda: "TechDrawGui::MDIViewPage"))
        self.assertTrue(echo.is_page_view(page))
        self.assertFalse(echo.is_page_view(object()))


class TableFit(unittest.TestCase):
    def test_wired(self):
        t = json.loads(src("agentlink", "data", "tools.json"))["entries"]["td_table"]
        steps = json.dumps(t["steps"])
        self.assertLess(steps.index("table_fit("), steps.index("page.addView(t)"))
        self.assertLess(steps.index("ss.recompute()"), steps.index("TechDraw::DrawViewSpreadsheet"))
        self.assertIn('"scale": "=tscale"', json.dumps(t["answer"]))
        self.assertIn('"table_fit": table_fit', src("agentlink", "families", "techdraw.py"))

    def test_the_text_its_size_on_the_paper(self):
        import ast

        code = src("agentlink", "families", "techdraw.py")
        tree = ast.parse(code)
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "table_fit")
        ns = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "techdraw", "exec"), ns)
        t = types.SimpleNamespace(ScaleType="Page", Scale=1.0, TextSize=3.5)
        ss = types.SimpleNamespace(getRowHeight=lambda r: 30)
        sc = ns["table_fit"](t, ss, ((1, 1), (2, 3)), 3.5)
        self.assertEqual(t.ScaleType, "Custom")
        self.assertAlmostEqual(sc, 0.1983, places=4)
        self.assertAlmostEqual(t.TextSize * t.Scale, 3.5, places=2)  # 3.5 mm on the paper
        self.assertIsNone(ns["table_fit"](t, types.SimpleNamespace(), ((1, 1), (1, 1)), 3.5))


if __name__ == "__main__":
    unittest.main()


class BatchCounts(unittest.TestCase):
    def test_counts_win_over_rows(self):
        from agentlink import activity
        w = activity.batch_words({}, {"ran": 6, "results": [], "counts": {"ok": 6, "refused": 0}})
        self.assertIn("6 ok", w)
        self.assertNotIn("refused", w)
        w = activity.batch_words({}, {"ran": 6, "results": [{"i": 2, "ok": False}], "counts": {"ok": 5, "refused": 1}})
        self.assertIn("5 ok, 1 refused", w)

    def test_only_refused_rows_without_counts_say_no_ok_count(self):
        from agentlink import activity
        w = activity.batch_words({}, {"ran": 6, "results": [{"i": 2, "ok": False}]})
        self.assertNotIn("0 ok", w)

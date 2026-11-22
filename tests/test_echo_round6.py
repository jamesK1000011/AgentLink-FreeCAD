# SPDX-License-Identifier: LGPL-2.1-or-later
# The echo's sixth window pass (docs/hardening/round6-findings.md): a heavy
# read run as a job is shown when its answer comes (a batch's, a job's end),
# add-ons' SELECTS, OUT_MORE, WORDS and SELECTS_FOR, never a hidden object
# selected, never a sheet's double-click (an Assembly BOM's opens a task
# dialog) and a dialog the echo opened closed at the next call, a drawing's
# page found from its view, BIM labels left out of the framing, lines of
# sight from a result's corners, the figures of strength and CAM answers, a
# CAM path's facts, scene-only marks and colours. Without FreeCAD: plain
# rules and stand-ins.
import json
import os
import sys
import threading
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import activity, annotate, echo, jobs  # noqa: E402
from test_gui_link_dialog import gui_link  # noqa: E402,F401  (gui_link with its FreeCAD stand-in)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cowork_legacy  # noqa: E402  (the old camera and selection behaviour: FollowAgent on, EchoSelects select)

setUpModule, tearDownModule = _cowork_legacy.on, _cowork_legacy.off


def vo(shown=True, **kw):
    return types.SimpleNamespace(Visibility=shown, PropertiesList=list(kw), **kw)


def obj(name, type_id="Part::Feature", shown=True, **kw):
    o = types.SimpleNamespace(Name=name, Label=name, TypeId=type_id, InList=[], Parents=[], PropertiesList=[], ViewObject=vo(shown))
    for k, v in kw.items():
        setattr(o, k, v)
    return o


class Doc:
    def __init__(self, objs, name="D"):
        self.Name = self.Label = name
        self.Objects = list(objs)
        for o in self.Objects:
            o.Document = self

    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)


class Jobs(unittest.TestCase):
    def test_a_job_end_is_heard_and_its_args_kept(self):
        heard = []
        jobs.listen(heard.append)
        self.addCleanup(lambda: jobs.LISTENERS.remove(heard.append))
        tool = types.SimpleNamespace(name="probe_read", fn=lambda a: {"read": a["x"]})
        session = types.SimpleNamespace(doc=None, out_dir=None)
        job = jobs.start(tool, {"x": 3}, session)
        self.assertTrue(jobs.wait_for(job, 5))
        for _ in range(50):
            if heard:
                break
            threading.Event().wait(0.02)
        self.assertEqual(heard[0]["job"], job["job"])
        self.assertEqual(job["args"], {"x": 3})
        self.assertNotIn("args", jobs.summary(job))
        jobs.answered(job)
        self.assertTrue(job["answered"])

    def test_an_answered_job_is_not_shown_again(self):
        posted = []
        saved = (echo._JOB_ECHO[0], echo._on)
        echo._JOB_ECHO[0], echo._on = object(), lambda: True
        stand_in = types.ModuleType("agentlink.gui_link")
        stand_in._POSTER = [types.SimpleNamespace(post=posted.append)]
        had = sys.modules.get("agentlink.gui_link")
        import agentlink

        had_attr = getattr(agentlink, "gui_link", None)
        sys.modules["agentlink.gui_link"] = stand_in
        agentlink.gui_link = stand_in
        try:
            echo.job_listener({"job": "j1", "answered": True})
            self.assertEqual(posted, [])
            echo.job_listener({"job": "j2"})
            self.assertEqual(len(posted), 1)
        finally:
            if had is None:
                sys.modules.pop("agentlink.gui_link", None)
            else:
                sys.modules["agentlink.gui_link"] = had
            if had_attr is None:
                try:
                    del agentlink.gui_link
                except AttributeError:
                    pass
            else:
                agentlink.gui_link = had_attr
            echo._JOB_ECHO[0], echo._on = saved

    def test_job_done_shows_its_answer_as_a_read(self):
        seen = []

        class T:
            name, changes, activity = "probe_read", False, None

            def for_call(self, a):
                return self

        e = echo.Echo(types.SimpleNamespace(doc=None))
        e.server = types.SimpleNamespace(tools={"probe_read": T()})
        e.after = lambda tool, args, reply: seen.append((tool.name, args, json.loads(reply["content"][0]["text"]), reply.get("isError")))
        self.assertEqual(e.job_done({"job": "j", "tool": "probe_read", "args": {"body": "B"}, "status": "done", "result": {"ok": 1}}), "shown")
        self.assertEqual(seen, [("probe_read", {"body": "B"}, {"ok": 1}, None)])
        e.job_done({"job": "j", "tool": "probe_read", "args": {}, "status": "failed", "error": {"code": "failed", "message": "no"}})
        self.assertTrue(seen[-1][3])

    def test_the_batch_shows_its_heavy_read(self):
        """The batch's heavy-read branch calls the echo before and after
        (agentlink/tools.py _echo_job): the source says so."""
        with open(os.path.join(HERE, "..", "agentlink", "tools.py"), encoding="utf-8") as f:
            src = f.read()
        i = src.index("if heavy_read:")
        part = src[i:i + 6000]
        self.assertLess(part.index("_echo_job(tt, hargs, None)"), part.index("_jobs.start(tt, dict(hargs), s)"))
        self.assertIn("_jobs.answered(job)", part)
        self.assertIn('_echo_job(tt, hargs, {"isError": not hok', part)


class Declared(unittest.TestCase):
    def setUp(self):
        self.saved = (dict(echo.OUT_MORE), dict(echo.SELECTS), list(echo.WORDS_FNS), list(echo.SELECT_FNS))

    def tearDown(self):
        echo.OUT_MORE.clear()
        echo.OUT_MORE.update(self.saved[0])
        echo.SELECTS.clear()
        echo.SELECTS.update(self.saved[1])
        echo.WORDS_FNS[:] = self.saved[2]
        echo.SELECT_FNS[:] = self.saved[3]

    def test_declare_merges(self):
        fam = types.SimpleNamespace(OUT_MORE={"gen_make": ("bodies",), "asm_bom": "table"}, SELECTS={"dfm_check": "body"},
                                    WORDS=lambda n, a, b: "Measured 3 mm" if n == "probe" else None,
                                    SELECTS_FOR=lambda n, a, b, d: ["Scan"] if n == "probe" else None)
        echo.declare(fam)
        self.assertEqual(echo.OUT_MORE["gen_make"], ("bodies",))
        self.assertEqual(echo.OUT_MORE["asm_bom"], ("sheet", "table"))  # merged, the hub's own kept first
        self.assertEqual(echo.out_names("gen_make", {}, {"bodies": ["Bin", "Lid"]}), ["Bin", "Lid"])
        self.assertEqual(echo.selects_names("dfm_check", {"body": "Bracket"}), ["Bracket"])
        self.assertEqual(echo.declared_words("probe", {}, {}), "Measured 3 mm")
        self.assertIsNone(echo.declared_words("other", {}, {}))
        self.assertEqual(echo.declared_selection("probe", {}, {}, None), ["Scan"])

    def test_a_failing_hook_is_passed_over(self):
        echo.WORDS_FNS.append(lambda *a: 1 / 0)
        echo.SELECT_FNS.append(lambda *a: 1 / 0)
        self.assertIsNone(echo.declared_words("x", {}, {}))
        self.assertIsNone(echo.declared_selection("x", {}, {}, None))


class Selection(unittest.TestCase):
    def test_hidden_never_selected(self):
        added = []
        gui = types.ModuleType("FreeCADGui")
        gui.Selection = types.SimpleNamespace(clearSelection=lambda: added.append("clear"),
                                              addSelection=lambda *a: added.append(a[1] if len(a) > 1 else a[0].Name))
        had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        try:
            d = Doc([obj("Shown"), obj("Hidden", shown=False)])
            echo._select(d.Objects)
            self.assertEqual(added, ["clear", "Shown"])
            added.clear()
            echo._select([d.getObject("Hidden")])
            self.assertEqual(added, [])  # nothing at all: the selection is left as it was
        finally:
            if had is None:
                sys.modules.pop("FreeCADGui", None)
            else:
                sys.modules["FreeCADGui"] = had


class Dialogs(unittest.TestCase):
    def setUp(self):
        self.rec, self.up = [], [False]
        gui = types.ModuleType("FreeCADGui")
        content = [types.SimpleNamespace(windowTitle=lambda: "Bill of Materials")]
        gui.Control = types.SimpleNamespace(activeDialog=lambda: self.up[0],
                                            activeTaskDialog=lambda: types.SimpleNamespace(getDialogContent=lambda: content) if self.up[0] else None,
                                            closeDialog=lambda: self.rec.append("closeDialog") or self.up.__setitem__(0, False))
        gui.editDocument = lambda: None
        self.had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        self.saved = echo.foreign_task
        echo.foreign_task = lambda gd=None: None
        echo._own_dialog[0] = None

    def tearDown(self):
        echo.foreign_task = self.saved
        echo._own_dialog[0] = None
        if self.had is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = self.had

    def test_a_sheet_never_double_clicked(self):
        d = Doc([obj("Bills_of_Materials", "Assembly::BomObject")])
        bom = d.Objects[0]
        bom.isDerivedFrom = lambda t: t == "Spreadsheet::Sheet"
        bom.ViewObject = types.SimpleNamespace(showSheetMdi=lambda: self.rec.append("showSheetMdi"),
                                               doubleClicked=lambda: self.rec.append("doubleClicked"))
        self.assertEqual(echo.show_view_of(bom), "Bills_of_Materials")
        self.assertEqual(self.rec, ["showSheetMdi"])

    def test_own_dialog_closed_at_the_next_call(self):
        d = Doc([obj("Thing", "App::FeaturePython")])
        t = d.Objects[0]
        t.ViewObject = types.SimpleNamespace(doubleClicked=lambda: self.up.__setitem__(0, True))
        echo.show_view_of(t)
        self.assertIsNotNone(echo._own_dialog[0])
        self.assertEqual(echo.close_own_dialog(), "Thing")
        self.assertEqual(self.rec, ["closeDialog"])
        self.assertIsNone(echo.close_own_dialog())  # once

    def test_a_dialog_already_up_is_not_the_echos(self):
        self.up[0] = True
        d = Doc([obj("Thing", "App::FeaturePython")])
        d.Objects[0].ViewObject = types.SimpleNamespace(doubleClicked=lambda: None)
        echo.show_view_of(d.Objects[0])
        self.assertIsNone(echo._own_dialog[0])
        self.assertIsNone(echo.close_own_dialog())
        self.assertEqual(self.rec, [])


class Pages(unittest.TestCase):
    def test_the_page_of_a_view(self):
        page = obj("Page", "TechDraw::DrawPage")
        view = obj("PlateTop", "TechDraw::DrawViewPart", InList=[page])
        dim = obj("Dimension", "TechDraw::DrawViewDimension", InList=[view])
        self.assertEqual(echo.pages_of([view]), [page])
        self.assertEqual(echo.pages_of([dim]), [page])
        self.assertEqual(echo.pages_of([page, view]), [page])
        self.assertEqual(echo.pages_of([obj("Box")]), [])


class Bb:
    def __init__(self, *b):
        self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax = b
        self.DiagonalLength = sum((b[i + 3] - b[i]) ** 2 for i in range(3)) ** 0.5

    def isValid(self):
        return True


class Framing(unittest.TestCase):
    def test_labels_left_out(self):
        wall = obj("Wall", Shape=types.SimpleNamespace(BoundBox=Bb(0, 0, 0, 10000, 200, 3000)))
        label = obj("Label", "App::FeaturePython", Proxy=types.SimpleNamespace(Type="Label"),
                    Shape=types.SimpleNamespace(BoundBox=Bb(-5e4, -5e4, 0, 5e4, 5e4, 1)))

        class BuildingPart:
            Type = "BuildingPart"

        level = obj("Ground floor", "Part::FeaturePython", Proxy=BuildingPart(), Group=[wall, label],
                    Shape=types.SimpleNamespace(BoundBox=Bb(0, 0, 0, 65, 42, 0.1)))
        self.assertTrue(echo.is_annotation(label))
        self.assertTrue(echo.is_bim_container(level))
        self.assertEqual(echo.members_box([level]), (0, 0, 0, 10000, 200, 3000))
        d = Doc([wall, label, level])
        self.assertEqual(echo.model_box(d), (0, 0, 0, 10000, 200, 3000))

    def test_edge_on_cover(self):
        """A plate seen edge-on beside a sketch hides its right part only:
        the middle's line of sight misses it, a corner's hits it."""
        sketch = (0.0, 0.0, 0.0, 100.0, 100.0, 0.0)
        plate = (70.0, 40.0, 5.0, 110.0, 60.0, 50.0)
        down = (0.0, 0.0, -1.0)  # looking down at the sketch
        mid = (50.0, 50.0, 0.0)
        self.assertFalse(echo.sight_hits(plate, mid, down))
        self.assertEqual(echo.covers_in_view([sketch], [("Plate", plate)], down), ["Plate"])
        self.assertEqual(echo.covers_in_view([sketch], [("Far", (200.0, 200.0, 5.0, 210.0, 210.0, 9.0))], down), [])
        self.assertEqual(len(echo.sight_points(sketch)), 9)  # a flat box: 3 x 3


class Figures(unittest.TestCase):
    def test_strength(self):
        self.assertEqual(activity.key_value({"vonMisesMax": {"MPa": 41.2}, "safety": 6.1}), "max 41.2 MPa, safety 6.1")
        self.assertEqual(activity.key_value({"vonMisesMaxMPa": 12.5}), "max 12.5 MPa")
        self.assertEqual(activity.key_value({"modes": [{"mode": 1, "hz": 12.3}, {"mode": 2, "hz": 45.6}, {"mode": 3, "hz": 78.9}]}),
                         "3 modes: 12.3, 45.6, 78.9 Hz")
        self.assertEqual(activity.key_value({"hottest": {"celsius": 81.5}}), "hottest 81.5 °C")

    def test_cam_sim(self):
        b = {"verdict": "clear", "removedMm3": 12300.0, "part": {"left": {"share": 0.75, "most": 9.0}}}
        self.assertEqual(activity.key_value(b), "clear, 12300 mm³ removed, 75 % left, up to 9 mm")


class CamPath(unittest.TestCase):
    def test_path_seen(self):
        cam = _cam_family()
        if cam is None:
            self.skipTest("cam family not importable here")

        def c(name, **p):
            return types.SimpleNamespace(Name=name, Parameters=p)

        cmds = [c("G0", X=0.0, Y=0.0, Z=5.0), c("G1", X=0.0, Y=0.0, Z=0.0), c("G1", X=10.0, Y=0.0, Z=0.0)]
        job = types.SimpleNamespace(Label="Job", PropertiesList=["Operations", "Stock"], Visibility=False)
        op = types.SimpleNamespace(Label="Profile", Path=types.SimpleNamespace(Commands=cmds), Visibility=True, Active=True, InListRecursive=[job])
        got = cam.path_seen(op)
        self.assertEqual(got["path"], {"moves": 3, "length": 15.0})
        self.assertFalse(got["shown"])
        self.assertIn("job Job is hidden", got["shownWhy"])
        job.Visibility = True
        self.assertTrue(cam.path_seen(op)["shown"])
        op.Visibility = False
        self.assertEqual(cam.path_seen(op)["shownWhy"], "Profile is hidden")


def _cam_family():
    """agentlink.families.cam, with stand-ins for FreeCAD and its CAM
    modules where FreeCAD is not importable; the modules swapped are put
    back."""
    names = ("FreeCAD", "Part", "Path", "Path.Main", "Path.Main.Job", "Path.Tool", "Path.Tool.Controller")
    had = {n: sys.modules.get(n) for n in names + ("agentlink.families.cam",)}
    try:
        try:
            import FreeCAD  # noqa: F401
        except ImportError:
            for n in names:
                if sys.modules.get(n) is None:
                    sys.modules[n] = types.ModuleType(n)
            fc = sys.modules["FreeCAD"]
            fc.Vector = getattr(fc, "Vector", lambda *a: a)
            fc.Console = getattr(fc, "Console", types.SimpleNamespace(PrintLog=lambda *a: None, PrintWarning=lambda *a: None,
                                                                      PrintMessage=lambda *a: None))
        from agentlink.families import cam

        return cam
    except Exception:  # noqa: BLE001
        return None
    finally:
        for n, m in had.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m


class Field:
    def __init__(self):
        self.vals = None

    def setValues(self, i, n, v):
        self.vals = list(v)

    def setValue(self, *v):
        self.vals = v


class SceneNode:
    def __init__(self, kind):
        self.kind, self.children = kind, []
        for k in ("point", "coordIndex", "materialIndex", "diffuseColor"):
            setattr(self, k, Field())
        self.numVertices = Field()

    def addChild(self, c):
        self.children.append(c)

    def removeChild(self, c):
        self.children.remove(c)

    def setName(self, n):
        self.name = n


class SceneCoin:
    def __getattr__(self, k):
        if k.startswith("So"):
            return lambda: SceneNode(k)
        raise AttributeError(k)


class Scene(unittest.TestCase):
    def test_marks_and_field(self):
        coin = SceneCoin()
        scene = SceneNode("root")
        ann = annotate.Annotations(coin=_Maker(coin), scene=lambda: scene)
        self.assertEqual(ann.marks("echo-scene", [(0, 0, 0), (100, 0, 0)], [[(0, 0, 0), (100, 0, 0)]]), 3)
        self.assertEqual(ann.field("echo-scene", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], [(1, 0, 0)] * 3), 1)
        root = scene.children[0]
        fs = root.children[-1].children[-1]
        self.assertEqual(fs.coordIndex.vals, [0, 1, 2, -1])
        self.assertEqual(fs.materialIndex.vals, [0, 1, 2, -1])
        ann.clear("echo-scene")
        self.assertEqual(scene.children, [])


class _Maker:
    """Coin with nodes made on call and the enums as attributes."""

    def __init__(self, coin):
        self._c = coin

    def __getattr__(self, k):
        if k == "SoMaterialBinding":
            return _Enum(SceneNode, k, PER_FACE="PER_FACE", PER_VERTEX_INDEXED="PER_VERTEX_INDEXED")
        if k == "SoShapeHints":
            return _Enum(SceneNode, k, COUNTERCLOCKWISE="CCW")
        if k == "SoMarkerSet":
            return _Enum(SceneNode, k, CIRCLE_FILLED_9_9=7)
        return getattr(self._c, k)


class _Enum:
    def __init__(self, make, kind, **vals):
        self._make, self._kind = make, kind
        self.__dict__.update(vals)

    def __call__(self):
        return self._make(self._kind)


class Rings(unittest.TestCase):
    def test_sheet_typing_lights_no_alias(self):
        for n in ("sheet_set", "sheet_rows", "sheet_clear", "param_set", "param_remove"):
            self.assertIsNone(echo.command_for(n, {}), n)
        self.assertEqual(echo.command_for("sheet_cells", {}), "Spreadsheet_MergeCells")

    def test_the_overflow_is_told_not_lit(self):
        self.assertTrue(echo._NO_LIGHT.flash(object(), 1))
        with open(os.path.join(HERE, "..", "agentlink", "echo.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("overflow_flash(unseen, _NO_LIGHT, ms, QtW)", src)
        self.assertNotIn("overflow_flash(unseen, painter, ms, QtW)", src)


if __name__ == "__main__":
    unittest.main()

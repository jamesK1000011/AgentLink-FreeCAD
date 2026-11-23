# SPDX-License-Identifier: LGPL-2.1-or-later
# The echo's second window pass (private records: echo2-findings.md): the
# Model tab back in front of an empty Tasks tab (P3), a body left showing its
# tip (P4), the view framed on what was made (P5), the feature selected and
# not its body (P6), the right button lit and the last one put out (P7),
# datums put away once used (P8), the words of reads, checks and refusals,
# a sketch never closed under a call that works in it (A1/S9), the camera
# turned to face a sketch (S1), new sketches opened (S5), exploded-view
# lines cleared (A9). Without FreeCAD: stand-ins record what the echo asks.
import json
import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import activity, echo  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cowork_legacy  # noqa: E402  (the old camera and selection behaviour: FollowAgent on, EchoSelects select)

setUpModule, tearDownModule = _cowork_legacy.on, _cowork_legacy.off

HERE = os.path.dirname(os.path.abspath(__file__))
COMMANDS = os.path.join(HERE, "..", "tests", "data", "freecad-1.1.0-commands.txt")


# ---- stand-ins ----------------------------------------------------------------------------

class Vec:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class ViewObject:
    def __init__(self, owner, visible=True, log=None):
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_log", log if log is not None else [])
        object.__setattr__(self, "Visibility", visible)
        object.__setattr__(self, "Proxy", None)

    def __setattr__(self, k, v):
        self._log.append(("view", self._owner, k, v))
        object.__setattr__(self, k, v)


class Shape:
    def __init__(self, solids=1, size=10.0):
        self.Solids = [object()] * solids
        self.BoundBox = types.SimpleNamespace(isValid=lambda: size > 0, DiagonalLength=size)

    def isNull(self):
        return False


class Obj:
    """A document object: every property set on it is a document write."""

    def __init__(self, name, type_id="Part::Feature", solids=0, visible=True, log=None, feature=False, datum=False):
        d = self.__dict__
        d["log"] = log if log is not None else []
        d["Name"] = d["Label"] = name
        d["TypeId"] = type_id
        d["Shape"] = Shape(solids) if solids else None
        d["ViewObject"] = ViewObject(name, visible, d["log"])
        d["InList"] = []
        d["Parents"] = []
        d["Group"] = []
        d["Document"] = types.SimpleNamespace(Name="Doc")
        d["_feature"], d["_datum"] = feature, datum

    def __setattr__(self, k, v):
        self.log.append(("doc", self.Name, k, v))
        self.__dict__[k] = v

    def isDerivedFrom(self, t):
        return (t == "PartDesign::Feature" and self._feature) or (t == "Part::Datum" and self._datum)


class Doc:
    def __init__(self, objs, name="Doc"):
        self.Name, self.Label = name, name
        self.Objects = list(objs)

    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)


def body_with(log, tip_visible=False, others_visible=True):
    """A body whose tip is hidden and whose earlier features (and a
    MultiTransform's shapeless steps) are shown: the Plate of P4."""
    pad = Obj("Pad", "PartDesign::Pad", 1, others_visible, log, feature=True)
    mt = Obj("MultiTransform", "PartDesign::MultiTransform", 1, tip_visible, log, feature=True)
    step = Obj("LinearPattern", "PartDesign::LinearPattern", 0, True, log, feature=True)
    sk = Obj("Sketch", "Sketcher::SketchObject", 0, False, log)
    body = Obj("Plate", "PartDesign::Body", 1, True, log)
    body.__dict__["Group"] = [sk, pad, mt, step]
    body.__dict__["Tip"] = mt
    for o in (pad, mt, step, sk):
        o.__dict__["InList"] = [body]
    return body, pad, mt, step


# ---- P7: the button ---------------------------------------------------------------------

class Buttons(unittest.TestCase):
    def known(self):
        with open(COMMANDS, encoding="utf-8") as f:
            return set(re.findall(r"^([A-Za-z]+_\w+)\s*$", f.read(), re.M))

    def test_every_command_is_freecads(self):
        known = self.known()
        named = set(echo.COMMAND.values()) | set(echo.SKETCH_ADD.values()) | set(echo.SKETCH_CONSTRAIN.values())
        named |= {c for _k, c in echo.SKETCH_EDIT} | set(echo.PD_DATUM.values()) | set(echo.PD_SUBTRACTIVE.values())
        for name, args in (("sketch_copy", {"rotate": {}}), ("sketch_copy", {"scale": {}}), ("sketch_array", {}),
                           ("sketch_array", {"polar": {}}), ("sketch_bspline", {"op": "degree", "by": -1}),
                           ("sketch_bspline", {"param": 0.5}), ("sketch_bspline", {"knot": 2, "by": 1})):
            named.add(echo.command_for(name, args))
        self.assertEqual(sorted(c for c in named if c not in known), [])

    def test_part_design_buttons(self):
        want = {"pd_multitransform": "PartDesign_MultiTransform", "pd_thickness": "PartDesign_Thickness",
                "pd_binder": "PartDesign_SubShapeBinder", "pd_clone": "PartDesign_Clone",
                "pd_move_feature": "PartDesign_MoveFeature", "pd_linear_pattern": "PartDesign_LinearPattern",
                "pd_chamfer": "PartDesign_Chamfer", "pd_draft": "PartDesign_Draft", "pd_polar_pattern": "PartDesign_PolarPattern",
                "pd_groove": "PartDesign_Groove", "pd_datum_plane": "Part_DatumPlane"}
        for tool, cmd in want.items():
            self.assertEqual(echo.command_for(tool, {}), cmd, tool)
        self.assertEqual(echo.command_for("pd_datum", {"kind": "line"}), "Part_DatumLine")
        self.assertIsNone(echo.command_for("pd_tip", {"body": "Hist"}))  # a read
        self.assertEqual(echo.command_for("pd_tip", {"body": "Hist", "feature": "H1"}), "PartDesign_MoveTip")

    def test_sketcher_buttons(self):
        self.assertEqual(echo.command_for("sketch_new", {}), "Sketcher_NewSketch")
        self.assertEqual(echo.command_for("sketch_add", {"items": [{"kind": "rounded_rectangle"}]}), "Sketcher_CreateOblong")
        self.assertEqual(echo.command_for("sketch_constrain", {"constraints": [{"type": "distance_x"}]}), "Sketcher_ConstrainDistanceX")
        self.assertEqual(echo.command_for("sketch_array", {"rows": 2}), "Sketcher_Translate")
        self.assertEqual(echo.command_for("sketch_mirror", {}), "Sketcher_MirrorSketch")
        self.assertEqual(echo.command_for("sketch_merge", {}), "Sketcher_MergeSketches")
        self.assertEqual(echo.command_for("sketch_project", {}), "Sketcher_Projection")
        self.assertEqual(echo.command_for("sketch_join", {}), "Sketcher_JoinCurves")

    def test_every_changing_sketch_tool_has_a_button(self):
        with open(os.path.join(HERE, "..", "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        examples = {"sketch_add": {"items": [{"kind": "line"}]}, "sketch_constrain": {"constraints": [{"type": "horizontal"}]},
                    "sketch_edit": {"trim": {"geo": 1}}}
        missing = [n for n, t in entries.items() if n.startswith("sketch_") and t.get("changes")
                   and not echo.command_for(n, examples.get(n, {}))]
        self.assertEqual(missing, [])

    def test_the_last_ring_goes_out_on_a_changing_call_only(self):
        """Round 3: a read (or a picture of the window) leaves the last
        change's ring lit; the next changing call puts it out."""
        cleared = []
        saved = echo.rings_off, echo.enabled
        echo.rings_off = lambda: cleared.append(1)
        echo.enabled = lambda: True
        try:
            e = echo.Echo(types.SimpleNamespace(doc=None))
            e.before(types.SimpleNamespace(name="feature_list", changes=False), {})  # a read: the ring stays
            self.assertEqual(cleared, [])
            e.before(types.SimpleNamespace(name="note_add", changes=True), {})  # a change: put out
        finally:
            echo.rings_off, echo.enabled = saved
        self.assertEqual(cleared, [1])

    def test_a_button_behind_the_overflow_lights_the_overflow(self):
        """Round 4: only a button Qt moved into its shown toolbar's "»"
        list lights the "»" (in_overflow): not one on a toolbar the person
        hid, nor a hidden button with a shown one after it."""
        class Act:
            def __init__(self, shown=True):
                self.shown = shown

            def isVisible(self):
                return self.shown

            def isSeparator(self):
                return False

        class ToolBar:
            def __init__(self, shown=True):
                self.shown, self.rows = shown, []

            def isVisible(self):
                return self.shown

            def actions(self):
                return [a for a, _w in self.rows]

            def widgetForAction(self, a):
                return next(w for x, w in self.rows if x is a)

        class ToolButton:
            def __init__(self, parent=None, shown=True):
                self.parent, self.shown = parent, shown

            def parentWidget(self):
                return self.parent

            def isVisible(self):
                return self.shown

        def bar_with(shown_bar, *shown_buttons):
            bar = ToolBar(shown_bar)
            ext = ToolButton(bar)
            bar.findChild = lambda cls, name: ext if name == "qt_toolbar_ext_button" else None
            buttons = [ToolButton(bar, sh) for sh in shown_buttons]
            bar.rows = [(Act(), b) for b in buttons]
            return bar, ext, buttons

        lit = []
        painter = types.SimpleNamespace(flash=lambda w, ms: lit.append(w) or True)
        QtW = types.SimpleNamespace(QToolBar=ToolBar, QToolButton=ToolButton)
        _bar, ext, (shown, hidden) = bar_with(True, True, False)
        self.assertTrue(echo.overflow_flash([hidden], painter, 900, QtW))
        self.assertEqual(lit, [ext])
        self.assertFalse(echo.overflow_flash([ToolButton(None)], painter, 900, QtW))
        _bar, _ext, (gone,) = bar_with(False, False)  # a toolbar the person hid
        self.assertFalse(echo.overflow_flash([gone], painter, 900, QtW))
        _bar, _ext, (mid, after) = bar_with(True, False, True)  # hidden for another reason
        self.assertFalse(echo.overflow_flash([mid], painter, 900, QtW))
        self.assertEqual(lit, [ext])

    def test_in_overflow_rule(self):
        self.assertTrue(echo.in_overflow([(True, True), (True, False), (True, False)], 1))
        self.assertFalse(echo.in_overflow([(True, False), (True, True)], 0))
        self.assertFalse(echo.in_overflow([(True, True), (False, False)], 1))  # its action hidden
        self.assertFalse(echo.in_overflow([(True, True)], 0))
        self.assertFalse(echo.in_overflow([], 0))


# ---- P3: the Model tab ------------------------------------------------------------------

class ModelTab(unittest.TestCase):
    def test_rule(self):
        self.assertEqual(echo.model_tab_index(["Model", "Tasks", "Agent Link"], 1), 0)
        self.assertEqual(echo.model_tab_index(["&Model", "&Tasks"], 1), 0)
        self.assertIsNone(echo.model_tab_index(["Model", "Tasks", "Agent Link"], 2))  # the person's tab
        self.assertIsNone(echo.model_tab_index(["Model", "Tasks"], 0))
        self.assertIsNone(echo.model_tab_index(["Report view", "Python console"], 0))

    def run_back(self, current, dialog=None, edit_elsewhere=False):
        class TabBar:
            def __init__(self, titles, cur):
                self.titles, self.cur = titles, cur

            def count(self):
                return len(self.titles)

            def tabText(self, i):
                return self.titles[i]

            def currentIndex(self):
                return self.cur

            def setCurrentIndex(self, i):
                self.cur = i

        bar = TabBar(["Model", "Tasks", "Agent Link"], current)
        shown = []
        gui = types.ModuleType("FreeCADGui")
        gui.Control = types.SimpleNamespace(activeDialog=lambda: dialog, showModelView=lambda: shown.append(1))
        gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: None)
        ed = types.SimpleNamespace(getInEdit=lambda: object()) if edit_elsewhere else None
        gui.editDocument = lambda: ed
        gui.getMainWindow = lambda: types.SimpleNamespace(findChildren=lambda cls: [bar])
        had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        saved = echo._qt
        echo._qt = lambda: (None, None, types.SimpleNamespace(QTabBar=TabBar))
        try:
            got = echo._model_tab_back()
        finally:
            echo._qt = saved
            if had is None:
                sys.modules.pop("FreeCADGui", None)
            else:
                sys.modules["FreeCADGui"] = had
        return got, bar.cur, shown

    def test_tabbed_docks_model_raised(self):
        self.assertEqual(self.run_back(1), (True, 0, [1]))

    def test_left_alone(self):
        self.assertEqual(self.run_back(2)[:2], (False, 2))                     # Agent Link's tab in front
        self.assertEqual(self.run_back(1, dialog=object())[:2], (False, 1))    # a task dialog is open
        self.assertEqual(self.run_back(1, edit_elsewhere=True)[:2], (False, 1))  # a sketch open in another document


# ---- A1/S9: a sketch is never closed under a call that works in it ------------------

class KeepTheSketch(unittest.TestCase):
    def test_rule(self):
        sk = types.SimpleNamespace(Name="Sketch001", Label="Cuts")
        for name in ("cmd_run", "menu_run", "gui_input", "dialog_answer", "sketch_add", "view_render", "history_undo", "selection"):
            self.assertFalse(echo.closes_edit(name, {}, sk), name)
        self.assertFalse(echo.closes_edit("object_set", {"object": "Cuts", "values": {}}, sk))
        self.assertFalse(echo.closes_edit("lesson_step", {"sketch": "Sketch001"}, sk))
        self.assertTrue(echo.closes_edit("object_set", {"object": "Pad"}, sk))
        self.assertTrue(echo.closes_edit("pd_pad", {"sketch": "Cuts"}, sk))  # a pad builds on it: a person leaves the sketch first

    def test_cmd_run_keeps_the_sketch_open(self):
        resets = []
        gd = types.SimpleNamespace(getInEdit=lambda: types.SimpleNamespace(Object=types.SimpleNamespace(Name="S", Label="S")),
                                   resetEdit=lambda: resets.append(1), ActiveView=None, Document=types.SimpleNamespace(Name="D"))
        gui = types.ModuleType("FreeCADGui")
        gui.ActiveDocument = gd
        had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        try:
            e = echo.Echo(types.SimpleNamespace(doc=None, batch_now=None))
            e.tr = {}
            e._mode("cmd_run", {"name": "Sketcher_LeaveSketch"})
            self.assertEqual(resets, [])
            e._mode("pd_pad", {"sketch": "S"})
            self.assertEqual(resets, [])  # round 5: a sketch the agent did not open is never closed by the echo
            self.assertEqual(e.tr["edit"], "left open: not opened by the agent")
            echo._agent_edits.add(("D", "S"))
            self.addCleanup(echo._agent_edits.discard, ("D", "S"))
            e._mode("pd_pad", {"sketch": "S"})
            self.assertEqual(resets, [1])  # the agent's own: a pad builds on it
        finally:
            if had is None:
                sys.modules.pop("FreeCADGui", None)
            else:
                sys.modules["FreeCADGui"] = had


# ---- S1: the camera faces the sketch -----------------------------------------------------

class FaceTheSketch(unittest.TestCase):
    def test_faces_plane(self):
        self.assertTrue(echo.faces_plane((0, 0, -1), (0, 0, 1)))
        self.assertTrue(echo.faces_plane((0, 1, 0), (0, -2, 0)))
        self.assertFalse(echo.faces_plane((-0.577, -0.577, -0.577), (0, 0, 1)))
        self.assertFalse(echo.faces_plane((0, 0, 0), (0, 0, 1)))

    def test_opened_with_the_camera_turned_at_once(self):
        log = []

        class View:
            anim = True
            d = Vec(-0.577, 0.577, -0.577)  # isometric, a solid in front

            def isAnimationEnabled(self):
                return self.anim

            def setAnimationEnabled(self, on):
                log.append(("anim", on))
                self.anim = on

            def getViewDirection(self):
                return self.d

            def setCameraOrientation(self, rot):
                log.append(("camera", rot, self.anim))

        rot = types.SimpleNamespace(multVec=lambda v: Vec(0, -1, 0))  # an XZ sketch: its normal along -y
        sk = types.SimpleNamespace(Name="RingProfile", getGlobalPlacement=lambda: types.SimpleNamespace(Rotation=rot))
        v = View()
        gd = types.SimpleNamespace(ActiveView=v, setEdit=lambda n: log.append(("edit", n, v.anim)))
        saved = echo.FreeCAD
        echo.FreeCAD = types.SimpleNamespace(Vector=Vec)
        try:
            did = echo.enter_edit(gd, sk)
        finally:
            echo.FreeCAD = saved
        self.assertEqual(did, "opened, camera turned to it")
        self.assertIn(("edit", "RingProfile", False), log)   # FreeCAD's own turn made without animation
        self.assertIn(("camera", rot, False), log)
        self.assertTrue(v.anim)                              # put back as it was


# ---- P4, P8, A9: view state only ----------------------------------------------------------

class ViewStateOnly(unittest.TestCase):
    def test_tip_shown(self):
        log = []
        body, pad, mt, step = body_with(log)
        self.assertTrue(echo.tip_shown(body))
        self.assertTrue(mt.ViewObject.Visibility)
        self.assertFalse(pad.ViewObject.Visibility)
        self.assertFalse(step.ViewObject.Visibility)
        self.assertEqual([x for x in log if x[0] == "doc"], [])  # nothing saved was written
        self.assertFalse(echo.tip_shown(body))                    # already right: nothing done

    def test_a_hidden_body_is_left(self):
        log = []
        body, _pad, mt, _step = body_with(log)
        body.ViewObject.Visibility = False
        del log[:]
        self.assertFalse(echo.tip_shown(body))
        self.assertEqual(log, [])

    def test_bodies_of_a_move(self):
        log = []
        a, *_ = body_with(log)
        b = Obj("Hist2", "PartDesign::Body", 1, True, log)
        doc = Doc([a, b])
        got = echo.bodies_of(doc, {"feature": "Pad 3", "to": "Hist2"}, {"from": "Plate", "to": "Hist2"}, [])
        self.assertEqual({o.Name for o in got}, {"Plate", "Hist2"})

    def test_datums_hidden_once_used(self):
        log = []
        echo._fresh_datums.clear()
        plane = Obj("DatumPlane", "PartDesign::Plane", 0, True, log, datum=True)
        mine = Obj("MyPlane", "PartDesign::Plane", 0, True, log, datum=True)   # the person's own
        sketch = Obj("Sketch", "Sketcher::SketchObject", 0, True, log)
        pad = Obj("Pad", "PartDesign::Pad", 1, True, log, feature=True)
        doc = Doc([plane, mine, sketch, pad])
        self.assertEqual(echo.datums_after(doc, [plane]), [])   # just made: shown
        self.assertEqual(echo.datums_after(doc, [sketch]), [])  # a sketch on it: still shown
        self.assertEqual(echo.datums_after(doc, [pad]), ["DatumPlane"])
        self.assertFalse(plane.ViewObject.Visibility)
        self.assertTrue(mine.ViewObject.Visibility)
        plane.ViewObject.Visibility = True                       # the person shows it again
        self.assertEqual(echo.datums_after(doc, [pad]), [])      # and it stays
        self.assertEqual([x for x in log if x[0] == "doc"], [])

    def test_exploded_lines_cleared(self):
        drawn = []
        step = Obj("Move", "App::FeaturePython")
        step.ViewObject.__dict__["Proxy"] = types.SimpleNamespace(redrawLines=lambda o, pos: drawn.append((o.Name, pos)))
        other = Obj("Base")
        self.assertEqual(echo.explode_lines_off(Doc([step, other])), 1)
        self.assertEqual(drawn, [("Move", [])])
        self.assertEqual([x for x in step.log if x[0] == "doc"], [])


# ---- P6, S4: what is selected ------------------------------------------------------------

class Selected(unittest.TestCase):
    def test_the_feature_not_its_body(self):
        log = []
        body, pad, *_ = body_with(log)
        self.assertEqual(echo.result_of([pad, body]), [pad])
        self.assertEqual(echo.result_of([body]), [body])  # a new body: the body

    def test_selected_by_its_path(self):
        pad = Obj("Pad")
        body = Obj("Body", "PartDesign::Body")
        pad.__dict__["Parents"] = [(body, "Pad.")]
        self.assertEqual(echo.sel_path(pad), ("Doc", "Body", "Pad."))
        self.assertEqual(echo.sel_path(Obj("Box")), ("Doc", "Box", ""))
        link = Obj("Link", "App::Link")
        asm = Obj("Assembly", "Assembly::AssemblyObject")
        j = Obj("Joint")
        j.__dict__["Parents"] = [(link, "x.Joints.Joint."), (asm, "Joints.Joint.")]
        self.assertEqual(echo.sel_path(j), ("Doc", "Assembly", "Joints.Joint."))

    def test_sketch_parts_selected_by_path(self):
        got = []
        gui = types.ModuleType("FreeCADGui")
        gui.Selection = types.SimpleNamespace(clearSelection=lambda: None, addSelection=lambda *a: got.append(a))
        had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        try:
            sk = Obj("Sketch")
            sk.__dict__["Parents"] = [(Obj("Body", "PartDesign::Body"), "Sketch.")]
            self.assertTrue(echo._select_subs(sk, ["Edge3", "Constraint1"]))
        finally:
            if had is None:
                sys.modules.pop("FreeCADGui", None)
            else:
                sys.modules["FreeCADGui"] = had
        self.assertEqual(got, [("Doc", "Body", "Sketch.Edge3"), ("Doc", "Body", "Sketch.Constraint1")])

    def test_sub_names(self):
        self.assertEqual(echo.sub_names("sketch_join", {"bspline": 4}), ["Edge5"])
        self.assertEqual(echo.sub_names("sketch_extend", {}, {"geo": 2}), ["Edge3"])
        self.assertEqual(echo.sub_names("sketch_to_bspline", {}, {"geometry": [0, 1]}), ["Edge1", "Edge2"])
        self.assertEqual(echo.sub_names("sketch_add", {"added": [{"ids": [0, 1]}]}), ["Edge1", "Edge2"])
        self.assertEqual(echo.sub_names("sketch_constrain", {"added": [3]}), ["Constraint4"])
        self.assertEqual(echo.sub_names("sketch_external", {"ids": [-3, -4]}), ["ExternalEdge1", "ExternalEdge2"])

    def test_out_names(self):
        self.assertEqual(echo.out_names("pd_move_feature", {"feature": "Pad 3", "to": "Hist2"}, {"moved": ["Island", "Pad 3"]}), ["Island", "Pad 3"])
        self.assertEqual(echo.out_names("asm_new_part", {}, {"inAssembly": "Guard", "part": "GuardPart", "body": "Body"}),
                         ["Guard", "GuardPart", "Body"])


# ---- words ----------------------------------------------------------------------------------

class Words(unittest.TestCase):
    def test_what_was_done(self):
        self.assertEqual(activity.did("asm_ground", {"part": "Base", "grounded": False}), "Let Base move again")
        self.assertEqual(activity.did("asm_ground", {"part": "Base"}), "Fixed Base in place")
        self.assertEqual(activity.did("pd_tip", {"body": "Hist"}), "Read Hist's tip")
        self.assertEqual(activity.did("pd_tip", {"body": "Hist", "feature": "H1"}), "Set Hist's tip to H1")
        self.assertEqual(activity.did("feature_edit", {"feature": "Pocket 2", "set": {"Refine": True}}), "Set Pocket 2 Refine to on")
        self.assertEqual(activity.did("sketch_edit", {"sketch": "PlateSketch", "set": [{"constraint": "plate_width", "value": 70}]}),
                         "Set plate_width to 70 in PlateSketch")
        self.assertEqual(activity.did("sketch_merge", {"sketches": ["A", "B"], "name": "TourBoth"}), "Merged A and B into TourBoth")
        self.assertEqual(activity.did("pd_multitransform", {"body": "Plate", "features": ["Bore"]}), "Repeated Bore in Plate")
        self.assertEqual(activity.did("asm_limits", {"joint": "CrankPivot", "min": -90, "max": 90}), "Limited CrankPivot to -90 … 90")

    def test_no_caption_is_only_the_tools_name(self):
        """Every Part Design, Sketcher and Assembly tool has words of its
        own, not its name turned into words."""
        with open(os.path.join(HERE, "..", "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            names = [n for n in json.load(f)["entries"] if n.startswith(("pd_", "sketch_", "asm_", "feature_"))]
        bare = [n for n in names if n not in activity.PHRASES]
        self.assertEqual(bare, [])

    def test_read_and_refused(self):
        self.assertEqual(echo.read_words("Checked CrankSlider for overlaps", "Clear"), "Checked CrankSlider for overlaps: clear")
        self.assertEqual(echo.read_words("Listed the features", "Done"), "Listed the features")
        self.assertEqual(echo.read_words("Exported CrankSlider for the solver", activity.outcome("asm_export", True, {"path": "crank.asmt", "note": "x"})),
                         "Exported CrankSlider for the solver: wrote crank.asmt")
        self.assertEqual(echo.refused_words("Cut a groove", "Refused: Ring has no solid"), "Cut a groove: refused (Ring has no solid)")


# ---- the echo after a call, end to end against stand-ins ----------------------------------

class After(unittest.TestCase):
    def setUp(self):
        self.said, self.log, self.fits = [], [], []
        self.doc = Doc([])
        gui = types.ModuleType("FreeCADGui")
        gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: None, ActiveView=None, Document=self.doc)
        gui.Selection = types.SimpleNamespace(clearSelection=lambda: None, addSelection=lambda *a: self.log.append(("sel",) + a))
        gui.getMainWindow = lambda: types.SimpleNamespace(statusBar=lambda: types.SimpleNamespace(showMessage=lambda *a: None))
        self.had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        keys = ("FreeCAD", "enabled", "say", "_paint", "_qt", "_model_tab_back", "fit", "fit_on")
        self.saved = {k: getattr(echo, k) for k in keys}
        params = types.SimpleNamespace(GetBool=lambda k, d=True: d, GetInt=lambda k, d=0: d)
        echo.FreeCAD = types.SimpleNamespace(GuiUp=True, ActiveDocument=self.doc, ParamGet=lambda p: params,
                                             Console=types.SimpleNamespace(PrintLog=lambda *a: None))
        echo.enabled = lambda: True
        echo.say = lambda words, ms=2600, where="": self.said.append(words) or words
        echo._paint = lambda *a, **k: None
        timer = types.SimpleNamespace(singleShot=lambda ms, fn: None)
        echo._qt = lambda: (types.SimpleNamespace(QTimer=timer), None, None)
        echo._model_tab_back = lambda: False
        echo.fit = lambda animate=True, selection=False: self.fits.append("selection" if selection else "all") or ("selection" if selection else "all")
        echo.fit_on = lambda objs, animate=True: self.fits.append(("on", [o.Name for o in objs])) or ("selection" if objs else False)
        self.session = types.SimpleNamespace(doc=self.doc, batch_now=None)
        self.echo = echo.Echo(self.session)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(echo, k, v)
        if self.had is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = self.had

    def reply(self, body, error=False):
        return {"isError": error, "content": [{"type": "text", "text": json.dumps(body)}]}

    def test_a_read_says_its_own_words(self):
        tool = types.SimpleNamespace(name="asm_check", changes=False)
        self.echo.after(tool, {"assembly": "CrankSlider"}, self.reply({"assembly": "CrankSlider", "verdict": "clear"}))
        self.assertEqual(self.said, ["Checked CrankSlider for overlaps: clear"])
        self.assertEqual(self.fits, [])

    def test_a_refusal_says_so(self):
        tool = types.SimpleNamespace(name="pd_groove", changes=True)
        self.echo.after(tool, {"body": "Ring", "sketch": "G"}, self.reply({"error": {"message": "Ring has no solid to groove"}}, error=True))
        self.assertEqual(self.said, ["Grooved with G: refused (Ring has no solid to groove)"])

    def test_words_come_even_when_a_step_fails(self):
        """N3: pd_groove showed no words at all. A failing step is noted
        and the rest still runs."""
        log = []
        body, *_ = body_with(log)
        groove = Obj("Groove", "PartDesign::Groove", 1, True, log, feature=True)
        groove.__dict__["InList"] = [body]
        self.doc.Objects += [body, groove]
        tool = types.SimpleNamespace(name="pd_groove", changes=True)

        def broken(*a):
            raise RuntimeError("a view that is gone")

        self.echo._views = broken
        self.echo.after(tool, {"body": "Plate", "sketch": "G"}, self.reply({"feature": "Groove", "body": "Plate"}))
        self.assertEqual(self.said, ["Grooved with G"])
        tr = self.session.echo_trace
        self.assertIn("viewsError", tr)
        self.assertEqual(tr["made"], ["Groove"])                 # the feature, not the body (P6)
        self.assertEqual(self.fits, ["selection"])                # framed on it (P5)
        self.assertIn(("sel", "Doc", "Groove"), self.log)

    def test_a_multitransform_leaves_its_body_shown(self):
        log = []
        body, pad, mt, step = body_with(log)
        self.doc.Objects += [body, pad, mt, step]
        tool = types.SimpleNamespace(name="pd_multitransform", changes=True)
        self.echo.after(tool, {"body": "Plate", "features": ["Bore"]}, self.reply({"feature": "MultiTransform"}))
        self.assertEqual(self.session.echo_trace.get("tipShown"), ["Plate"])
        self.assertTrue(mt.ViewObject.Visibility)
        self.assertFalse(step.ViewObject.Visibility)
        self.assertEqual([x for x in log if x[0] == "doc"], [])
        self.assertEqual(self.said, ["Repeated Bore in Plate"])

    def test_off_without_a_window(self):
        echo.enabled = self.saved["enabled"]
        echo.FreeCAD = None
        tool = types.SimpleNamespace(name="pd_pad", changes=True)
        self.echo.before(tool, {"sketch": "S"})
        self.echo.after(tool, {"sketch": "S"}, self.reply({"feature": "Pad"}))
        self.assertEqual(self.said, [])
        self.assertEqual(self.fits, [])


if __name__ == "__main__":
    unittest.main()

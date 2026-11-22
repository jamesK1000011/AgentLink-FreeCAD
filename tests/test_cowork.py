# SPDX-License-Identifier: LGPL-2.1-or-later
"""Co-work in one window (design E5): the camera and the selection stay the
person's. FollowAgent (off by default) and the 3D view's input watch; the
highlight in place of FreeCAD's selection (EchoSelects); a command's own
selection, held for its run and the person's put back. No FreeCAD: stand-ins."""
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import annotate, cowork, echo, hooks, panel_tabs, runners  # noqa: E402
from test_overlay import Node  # noqa: E402
from test_overlay import FakeCoin as _FakeCoin  # noqa: E402


class FakeCoin(_FakeCoin):
    """The annotation tests' stand-in, with a line set's many counts."""

    def __getattr__(self, k):
        make = _FakeCoin.__getattr__(self, k)

        def node():
            n = make()
            n.numVertices.setValues = lambda *a: setattr(n, "counts", a[2])
            return n

        return node


class Params:
    def __init__(self, store):
        self.s = store

    def GetBool(self, k, d=False):  # noqa: N802 (FreeCAD)
        return self.s.get(k, d)

    def GetString(self, k, d=""):  # noqa: N802
        return self.s.get(k, d)

    def GetFloat(self, k, d=0.0):  # noqa: N802
        return self.s.get(k, d)

    def GetUnsigned(self, k, d=0):  # noqa: N802
        return self.s.get(k, d)

    def SetBool(self, k, v):  # noqa: N802
        self.s[k] = v


class V:
    def __init__(self, *p):
        self.x, self.y, self.z = p


class Face:
    def tessellate(self, tol):
        return [V(0, 0, 0), V(1, 0, 0), V(0, 1, 0)], [(0, 1, 2)]


class Edge:
    def discretize(self, Number):
        return [V(i, 0, 0) for i in range(Number)]


class Box:
    DiagonalLength = 10.0
    XMin = YMin = ZMin = 0.0
    XMax = YMax = ZMax = 10.0

    def isValid(self):
        return True


class Shape:
    def __init__(self, faces=2, edges=3):
        self.Faces = [Face() for _ in range(faces)]
        self.Edges = [Edge() for _ in range(edges)]
        self.BoundBox = Box()

    def isNull(self):
        return False


class Obj:
    def __init__(self, name, doc):
        self.Name = self.Label = name
        self.Document = doc
        self.Shape = Shape()
        self.TypeId = "Part::Feature"

    def getSubObject(self, path, retType=0):
        return self


class Doc:
    def __init__(self, name="Doc", names=("Block", "Lid")):
        self.Name = self.Label = name
        self.objs = {n: Obj(n, self) for n in names}

    def getObject(self, n):
        return self.objs.get(n)

    def getObjectsByLabel(self, label):
        return [o for o in self.objs.values() if o.Label == label]


class Selection:
    """FreeCAD's selection, as a list of (document, object, sub)."""

    def __init__(self):
        self.rows, self.calls = [], []

    def clearSelection(self, doc=None):  # noqa: N802
        self.calls.append(("clear", doc))
        self.rows = [r for r in self.rows if doc is not None and r[0] != doc]

    def addSelection(self, *a):  # noqa: N802
        self.calls.append(("add",) + tuple(getattr(x, "Name", x) for x in a))
        if isinstance(a[0], str):
            self.rows.append((a[0], a[1], a[2] if len(a) > 2 else ""))
        else:
            self.rows.append((a[0].Document.Name, a[0].Name, a[1] if len(a) > 1 else ""))

    def getSelectionEx(self, *a):  # noqa: N802
        out = {}
        for d, o, s in self.rows:
            x = out.setdefault((d, o), types.SimpleNamespace(DocumentName=d, ObjectName=o, SubElementNames=[]))
            if s:
                x.SubElementNames.append(s)
        return list(out.values())

    def getSelection(self, *a):  # noqa: N802
        return [types.SimpleNamespace(Name=o) for _d, o, _s in self.rows]


class World(unittest.TestCase):
    """A FreeCAD, a FreeCADGui and a Part of stand-ins in sys.modules; the
    preferences in self.prefs."""

    def setUp(self):
        self.prefs = {}
        self.doc = Doc()
        self.sel = Selection()
        fc = types.ModuleType("FreeCAD")
        fc.GuiUp = True
        fc.ParamGet = lambda group: Params(self.prefs)
        fc.getDocument = lambda n: self.doc if n == self.doc.Name else (_ for _ in ()).throw(NameError(n))
        fc.ActiveDocument = self.doc
        fc.Console = types.SimpleNamespace(PrintLog=lambda *a: None)
        gui = types.ModuleType("FreeCADGui")
        gui.Selection = self.sel
        gui.ActiveDocument = None
        part = types.ModuleType("Part")
        self.got_shapes = []

        def get_shape(o, sub="", needSubElement=False, transform=True):
            self.got_shapes.append((o.Name, sub, needSubElement))
            if needSubElement:
                return Face() if "Face" in sub else Edge()
            return o.Shape

        part.getShape = get_shape
        self.had = {k: sys.modules.get(k) for k in ("FreeCAD", "FreeCADGui", "Part")}
        sys.modules.update({"FreeCAD": fc, "FreeCADGui": gui, "Part": part})
        self.scene = Node("root")
        self.had_service = annotate._SERVICE
        annotate._SERVICE = annotate.Annotations(coin=FakeCoin(), scene=lambda: self.scene)
        cowork._hl["entries"], cowork._hl["triangles"] = [], 0
        self.input0 = dict(cowork._input)
        cowork._input.update(down=False, last=0.0, on={})

    def tearDown(self):
        for k, v in self.had.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        annotate._SERVICE = self.had_service
        cowork._hl["entries"], cowork._hl["triangles"] = [], 0
        cowork._input.clear()
        cowork._input.update(self.input0)
        del cowork._held[:]


# ---- #2, #4: the camera ---------------------------------------------------------------------

class Follow(World):
    def test_off_by_default_and_the_panels_box_turns_it_on(self):
        self.assertFalse(cowork.follow_on())
        self.assertFalse(cowork.follows())
        panel_tabs.follow_toggled(True)
        self.assertTrue(self.prefs["FollowAgent"])
        self.assertTrue(cowork.follows())
        panel_tabs.follow_toggled(False)
        self.assertFalse(cowork.follows())
        self.assertEqual(panel_tabs.FOLLOW_LABEL, "Follow agent")

    def test_no_frame_and_no_turn_while_off(self):
        moved = []
        view = types.SimpleNamespace(getCameraNode=lambda: moved.append("camera"), fitAll=lambda: moved.append("fit"),
                                     getSceneGraph=lambda: None, viewIsometric=lambda: moved.append("iso"),
                                     viewTop=lambda: moved.append("top"), getViewDirection=lambda: V(0, 0, -1),
                                     isAnimationEnabled=lambda: False)
        self.assertFalse(echo.fit())
        self.assertFalse(echo.fit(selection=True))
        self.assertFalse(echo.frame_box(view, (0, 0, 0, 1, 1, 1)))
        sys.modules["FreeCADGui"].ActiveDocument = types.SimpleNamespace(getInEdit=lambda: None, ActiveView=view)
        e = echo.Echo.__new__(echo.Echo)
        self.assertIsNone(e._turn([types.SimpleNamespace(Shape=Shape(), TypeId="Part::Feature")]))
        self.assertIsNone(e._plan([object()]))
        self.assertEqual(moved, [])

    def test_a_frame_is_skipped_while_the_person_works_the_view(self):
        self.assertFalse(cowork.busy(100.0, False, 0.0, 3.0))
        self.assertTrue(cowork.busy(100.0, True, 0.0, 3.0))
        self.assertTrue(cowork.busy(100.0, False, 98.5, 3.0))
        self.assertFalse(cowork.busy(100.0, False, 96.0, 3.0))
        self.prefs["FollowAgent"] = True
        self.assertTrue(cowork.follows())
        cowork.note_input("press")
        self.assertFalse(cowork.follows())  # a button down on the view
        cowork.note_input("release", buttons=0)
        self.assertFalse(cowork.follows())  # within FollowAgentQuiet of it
        cowork._input["last"] -= 10
        self.assertTrue(cowork.follows())
        cowork.note_input("move", buttons=0)  # the pointer passing over: not work on the view
        self.assertTrue(cowork.follows())
        cowork.note_input("wheel")
        self.assertFalse(cowork.follows())
        self.prefs["FollowAgentQuiet"] = 0.0
        self.assertTrue(cowork.follows())

    def test_the_watch_goes_on_each_view_once_and_never_without_a_window(self):
        put = []
        w = types.SimpleNamespace(installEventFilter=lambda f: put.append(f), objectName=lambda: "")
        had = cowork._filter
        cowork._filter = lambda: "filter"
        try:
            self.assertEqual(cowork.watch_view([w]), 1)
            self.assertEqual(cowork.watch_view([w]), 1)
            self.assertEqual(put, ["filter"])
            sys.modules["FreeCAD"].GuiUp = False
            self.assertEqual(cowork.watch_view(), 0)
        finally:
            cowork._filter = had

    def test_on_the_view_frames_the_highlight_not_freecads_selection(self):
        self.prefs["FollowAgent"] = True
        boxes = []
        view = types.SimpleNamespace(getSceneGraph=lambda: None, fitAll=lambda: boxes.append("all"),
                                     isAnimationEnabled=lambda: False)
        gui = sys.modules["FreeCADGui"]
        gui.ActiveDocument = types.SimpleNamespace(ActiveView=view, Document=self.doc)
        sys.modules["FreeCAD"].listDocuments = lambda: {"Doc": self.doc}
        had = echo.frame_box, echo.FreeCAD
        echo.frame_box = lambda v, box: boxes.append(box) or True
        echo.FreeCAD = sys.modules["FreeCAD"]
        try:
            echo._select([self.doc.objs["Block"]])
            self.assertEqual(echo.fit(selection=True), "selection")
        finally:
            echo.frame_box, echo.FreeCAD = had
        self.assertEqual(boxes, [(0.0, 0.0, 0.0, 10.0, 10.0, 10.0)])
        self.assertEqual(self.sel.calls, [])

    def test_no_view_no_watch(self):
        self.assertEqual(cowork.watch_view(), 0)  # no 3D view in front: nothing, no error


# ---- #7: the highlight ------------------------------------------------------------------------

class Highlight(World):
    def test_highlight_is_the_default_and_select_keeps_the_old_way(self):
        self.assertEqual(cowork.mode(), "highlight")
        self.prefs["EchoSelects"] = "select"
        self.assertEqual(cowork.mode(), "select")
        self.prefs["EchoSelects"] = "nonsense"
        self.assertEqual(cowork.mode(), "highlight")

    def test_the_selection_colour(self):
        self.assertEqual(cowork.selection_hex(), "#1cad1c")
        self.prefs["SelectionColor"] = 0xFF000000
        self.assertEqual(cowork.selection_rgb(), (1.0, 0.0, 0.0))
        self.assertEqual(cowork.selection_rgb("bad"), cowork.selection_rgb(cowork.SELECTION_COLOUR))

    def test_the_echo_lights_without_touching_the_persons_selection(self):
        self.sel.rows = [("Doc", "Lid", "Face2")]
        block = self.doc.objs["Block"]
        echo._select([block])
        self.assertEqual(self.sel.calls, [])
        self.assertEqual(self.sel.rows, [("Doc", "Lid", "Face2")])
        self.assertEqual(cowork.sel_names(), ["Block"])
        self.assertEqual(cowork.sel_count(), 1)
        root = self.scene.children[0]
        self.assertEqual(root.name, "AgentLinkAnnotations")
        whole = root.children[0]
        kinds = [c.kind for c in whole.children]
        self.assertEqual(kinds[:5], ["SoPickStyle", "SoMaterial", "SoPolygonOffset", "SoCoordinate3", "SoIndexedFaceSet"])
        self.assertIn("SoLineSet", kinds)
        self.assertEqual(whole.children[1].diffuseColor, cowork.selection_rgb())
        # A face: the annotation layer's own SoAnnotation.
        echo._select_subs(block, ["Face6"])
        self.assertEqual(cowork.sel_rows(), [("Doc", "Block", "Face6")])
        self.assertEqual([n.kind for n in self.scene.children[0].children], ["SoAnnotation"])
        self.assertEqual(self.sel.calls, [])
        # Cleared: the drawing goes, the person's selection stays.
        self.assertEqual(echo.selection_cleared(), 1)
        self.assertEqual(self.scene.children, [])
        self.assertEqual(self.sel.rows, [("Doc", "Lid", "Face2")])

    def test_highlight_by_names_replaces_the_last(self):
        got = echo.highlight(["Block.Face6", "Lid", "Nope"])
        self.assertEqual(got["lit"], ["Block.Face6", "Lid"])
        self.assertEqual(got["missing"], ["Nope"])
        got = echo.highlight([self.doc.objs["Lid"]])
        self.assertEqual(cowork.sel_rows(), [("Doc", "Lid", "")])
        self.assertEqual(len(self.scene.children[0].children), 1)
        self.assertEqual(self.sel.calls, [])

    def test_reselect_draws_again_and_a_change_clears_it(self):
        echo._select([self.doc.objs["Block"]])
        self.assertEqual(echo.reselect(), ["Block"])
        self.assertEqual(len(self.scene.children[0].children), 1)
        self.assertEqual(cowork.clear_highlight(), 1)
        self.assertEqual(cowork.sel_rows(), [])
        self.assertIsNone(echo.reselect())

    def test_select_mode_sets_freecads_selection_as_before(self):
        self.prefs["EchoSelects"] = "select"
        echo._select([self.doc.objs["Block"]])
        self.assertEqual(self.sel.rows, [("Doc", "Block", "")])
        self.assertEqual(self.scene.children, [])
        self.assertEqual(cowork.sel_names(), ["Block"])

    def test_a_sketch_constraint_is_held_but_not_drawn(self):
        self.assertTrue(cowork.sel_add("Doc", "Block", "Constraint1"))
        self.assertEqual(cowork.sel_rows(), [("Doc", "Block", "Constraint1")])
        self.assertEqual(self.scene.children, [])
        with self.assertRaises(ValueError):
            cowork.sel_add("Doc", "Missing")

    def test_whole_node_keeps_to_its_budget(self):
        node, tris = cowork.whole_node(FakeCoin(), Shape(faces=5, edges=0), (0, 1, 0), budget=2)
        self.assertEqual(tris, 2)
        self.assertNotIn("SoLineSet", [c.kind for c in node.children])

    def test_no_window_draws_nothing(self):
        sys.modules["FreeCAD"].GuiUp = False
        echo._select([self.doc.objs["Block"]])
        self.assertEqual(self.scene.children, [])
        self.assertEqual(cowork.sel_names(), ["Block"])


# ---- #7b: a command's own selection ----------------------------------------------------------

class Held(World):
    def test_set_for_the_run_and_the_persons_put_back(self):
        self.sel.rows = [("Doc", "Lid", "Face2")]
        seen = []
        with cowork.held([self.doc.objs["Block"], (self.doc.objs["Lid"], "Edge1")]):
            seen.append((list(self.sel.rows), hooks.selection_is_muted()))
        self.assertEqual(seen, [([("Doc", "Block", ""), ("Doc", "Lid", "Edge1")], True)])
        self.assertEqual(self.sel.rows, [("Doc", "Lid", "Face2")])
        self.assertFalse(hooks.selection_is_muted())

    def test_put_back_after_an_error(self):
        self.sel.rows = [("Doc", "Lid", "")]
        with self.assertRaises(RuntimeError):
            with cowork.held([self.doc.objs["Block"]]):
                raise RuntimeError("the command failed")
        self.assertEqual(self.sel.rows, [("Doc", "Lid", "")])
        self.assertFalse(hooks.selection_is_muted())
        self.assertEqual(cowork.depth(), 0)

    def test_a_steps_run_puts_it_back_on_a_refusal_and_an_answer(self):
        self.sel.rows = [("Doc", "Lid", "")]
        block = self.doc.objs["Block"]
        during = []
        helpers = {"hold": lambda: cowork.hold([block]), "look": lambda: during.append(list(self.sel.rows)) or True}
        refusing = {"steps": [{"do": "=hold()"}, {"do": "=look()"}, {"refuse": "no"}], "answer": {"fields": {}}}
        from agentlink.protocol import ToolError

        with self.assertRaises(ToolError):
            runners.run_steps("t", refusing, {}, helpers)
        self.assertEqual(self.sel.rows, [("Doc", "Lid", "")])
        answering = {"steps": [{"do": "=hold()"}, {"do": "=look()"}, {"answer": {"fields": {"ok": True}}}]}
        self.assertEqual(runners.run_steps("t", answering, {}, helpers), {"ok": True})
        self.assertEqual(during, [[("Doc", "Block", "")]] * 2)
        self.assertEqual(self.sel.rows, [("Doc", "Lid", "")])
        self.assertFalse(hooks.selection_is_muted())

    def test_no_window_holds_nothing(self):
        sys.modules.pop("FreeCADGui")
        self.assertEqual(cowork.hold(["x"]), 0)
        self.assertEqual(cowork.depth(), 0)


class CmdRunEntry(unittest.TestCase):
    def test_select_is_held_before_the_active_check(self):
        with open(os.path.join(HERE, "..", "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]["cmd_run"]
        self.assertIn("select", e["inputSchema"]["properties"])
        steps = json.dumps(e["steps"])
        self.assertLess(steps.index("hold_selection"), steps.index("is_active"))


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
# Window round 8 (17 Nov), stand-ins for:
#   - meshobj_unwrap: its piece selected and framed (the face it laid flat,
#     its pattern), what covers it see-through, the Mesh Info box put away
#     when no mesh is selected; its caption with the areas and the stretch.
#   - a sliced print's figures (gcode_read, orca_slice) and a read's file
#     said as what it read from.
#   - an add-on's SEE_THROUGH: the body it cut inside made see-through.
#   - bim_reorder's order in the caption and the tree's rows in sight.
#   - td_projection's views in the caption.
#   - td_centermarks: FreeCAD's own crosses off (they mark a slot's ends),
#     the chain lines drawn on whole circles only.
import json
import os
import sys
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentlink import activity, echo  # noqa: E402
from test_echo_maps import WithStandIns  # noqa: E402
from test_famfix import TechDrawPaper  # noqa: E402
from test_hubfix2 import in_a_process  # noqa: E402


class UnwrapWords(unittest.TestCase):
    def words(self, args, body):
        return echo.change_words(activity.did("meshobj_unwrap", args, body), body, "meshobj_unwrap")

    def test_a_flat_face(self):
        body = {"of": "Foot.Face6", "surface": "plane", "exact": True, "area3d": 400.0, "areaFlat": 400.0,
                "stretch": {"mean": 0.0, "max": 0.0, "unit": "%"}, "outlines": 1, "size": [20, 20], "path": "/u/o/unproven_foot_top.svg"}
        got = self.words({"of": "Foot.Face6", "path": "unproven_foot_top.svg", "make": False}, body)
        self.assertEqual(got, "Laid Foot.Face6 flat: area 400 mm², flat 400 mm², stretch max 0 %")

    def test_a_pattern_and_a_mesh(self):
        got = self.words({"of": "Post.Face1", "name": "Post flat"}, {"area3d": 942.478, "areaFlat": 942.478, "stretch": {"mean": 0, "max": 0}, "pattern": "Post flat"})
        self.assertEqual(got, "Laid Post.Face1 flat as Post flat: area 942 mm², flat 942 mm², stretch max 0 %")
        got = self.words({"of": "Cap", "make": False}, {"area3d": 313.6, "areaFlat": 314.7, "stretch": {"mean": 1.0, "max": 3.8}})
        self.assertEqual(got, "Laid Cap flat: area 314 mm², flat 315 mm², stretch max 3.8 % (mean 1 %)")


class PrintWords(unittest.TestCase):
    def read(self, name, args, body):
        return echo.read_words(activity.did(name, args, body), activity.outcome(name, True, body, args))

    def test_gcode_read_whole_print_and_one_layer(self):
        a = {"path": "alink-rest-sliced.3mf"}
        whole = {"layers": 25, "z": [0.2, 5.0], "slicer": {}, "features": [{"feature": "Outer wall"}, {}, {}]}
        self.assertEqual(self.read("gcode_read", a, whole), "Read G-code from alink-rest-sliced.3mf: 25 layers, z 0.2 to 5 mm, 3 features")
        one = {"layers": 25, "z": [0.2, 5.0], "layer": {"layer": 2, "z": 0.6, "moves": [1, 2, 3]}, "move": {"kind": "extrude"},
               "svg": "/u/o/alink-rest-sliced-plate_1-layer2-feature.svg"}
        got = self.read("gcode_read", dict(a, layer=2, move=0, svg=True), one)
        self.assertEqual(got, "Read G-code from alink-rest-sliced.3mf: layer 2 of 25 at z 0.6 mm, 3 moves, move: extrude, "
                              "drew alink-rest-sliced-plate_1-layer2-feature.svg")
        self.assertNotIn("/u/o/", got)

    def test_a_slice_and_answers_that_are_not_prints(self):
        self.assertEqual(activity.print_value({"gcode": ["/o/a.gcode"], "layers": 25, "filamentG": 1.23}), "25 layers, 1.23 g of filament")
        self.assertIsNone(activity.print_value({"maps": [], "layers": [{}]}))   # view_maps: a list of layers
        self.assertIsNone(activity.print_value({"layers": 3}))                  # no heights, no filament
        self.assertEqual(activity.did("doc_save", {"path": "/x/a.FCStd"}), activity.did("doc_save", {"path": "/x/a.FCStd"}))


class ViewsAndOrder(unittest.TestCase):
    def test_projection_views(self):
        b = {"view": "ProjGroup", "type": "DrawProjGroup", "projection": "Third angle",
             "items": [{"view": "Front"}, {"view": "Top"}, {"view": "Right"}]}
        got = echo.change_words(activity.did("td_projection", {"page": "Tut A4", "bodies": ["Tut"]}, b), b, "td_projection")
        self.assertEqual(got, "Put the standard views of Tut on Tut A4: 3 views (Front, Top and Right), third angle")
        self.assertIsNone(activity.views_value({"items": [{"view": "Front"}]}))  # no projection: not a group's answer

    def test_reorder_says_the_order(self):
        b = {"group": "Ground floor", "order": ["Door", "Floor slab", "Roof", "Stairs", "Wall", "Window"]}
        got = echo.change_words(activity.did("bim_reorder", {"group": "Ground floor", "sort": True}, b), b, "bim_reorder")
        self.assertEqual(got, "Put Ground floor's contents in order: Door, Floor slab, Roof and 3 more")


class _Obj:
    def __init__(self, name, type_id="Part::Feature", box=(0, 0, 0, 20, 20, 10)):
        self.Name = self.Label = name
        self.TypeId = type_id
        self.ViewObject = types.SimpleNamespace(Visibility=True, Transparency=0, PropertiesList=["Transparency"])
        self.Document = types.SimpleNamespace(Name="D")
        self._box = box


class _Doc:
    def __init__(self, objs):
        self.Objects = objs

    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)

    def getObjectsByLabel(self, lb):
        return [o for o in self.Objects if o.Label == lb]


class UnwrapShown(WithStandIns):
    def setUp(self):
        super().setUp()
        self.sel = []
        self.gui.Selection = types.SimpleNamespace(clearSelection=lambda: self.sel.clear(),
                                                   getSelection=lambda: [o for o, _s in self.sel])
        self.cleared = []
        self.gui.Control = types.SimpleNamespace(activeDialog=lambda: None, clearTaskWatcher=lambda: self.cleared.append(1))
        self.gui.activeWorkbench = lambda: types.SimpleNamespace(name=lambda: "MeshWorkbench")

        def add(o, sub=""):
            self.sel.append((o, sub))
            return True

        def box(o):
            b = o._box
            return types.SimpleNamespace(XMin=b[0], YMin=b[1], ZMin=b[2], XMax=b[3], YMax=b[4], ZMax=b[5])

        for target, fn in (("_add_sel", add), ("_box", box), ("fit", lambda animate=True, selection=False: "selection"),
                           ("uncover", lambda doc, made, *a: ["Sphere"] if made and made[0].TypeId == "Mesh::Feature" else [])):
            p = mock.patch.object(echo, target, fn)
            p.start()
            self.addCleanup(p.stop)

    def test_a_face_with_make_false_is_framed_and_the_empty_box_put_away(self):
        foot, wall = _Obj("Foot"), _Obj("Wall", box=(0, 0, 0, 9600, 200, 3000))
        got = echo.unwrap_shown(_Doc([foot, wall]), {"of": "Foot.Face6", "make": False}, {"of": "Foot.Face6", "area3d": 400}, [])
        self.assertEqual(got["selected"], ["Foot.Face6"])
        self.assertEqual(self.sel, [(foot, "Face6")])
        self.assertEqual(got["framed"], "the piece")
        self.assertEqual(got["size"], [20.0, 20.0, 10.0])  # the piece's box, not the 9.6 m wall's
        self.assertEqual(got["meshInfo"], "put away")
        self.assertEqual(self.cleared, [1])

    def test_a_mesh_and_its_pattern(self):
        cap = _Obj("Cap", "Mesh::Feature", (0, 0, 8, 10, 10, 10))
        flat = _Obj("Cap flat", box=(-20, -20, 0, 20, 20, 0))
        got = echo.unwrap_shown(_Doc([cap, flat]), {"of": "Cap"}, {"pattern": "Cap flat"}, [flat])
        self.assertEqual(got["selected"], ["Cap", "Cap flat"])
        self.assertEqual(got["uncovered"], ["Sphere"])
        self.assertTrue(got["meshInfo"].startswith("kept"))  # a mesh selected: the box shows its values
        self.assertEqual(self.cleared, [])

    def test_nothing_named(self):
        self.assertIsNone(echo.unwrap_shown(_Doc([]), {"of": "Gone.Face1"}, {}, []))


class SeeThrough(WithStandIns):
    def setUp(self):
        super().setUp()
        self.sel = []
        self.gui.Selection = types.SimpleNamespace(clearSelection=lambda: self.sel.clear())
        p = mock.patch.object(echo, "_add_sel", lambda o, sub="": self.sel.append(o) or True)
        p.start()
        self.addCleanup(p.stop)
        echo.SEE_THROUGH["x_channel"] = "body"
        self.addCleanup(echo.SEE_THROUGH.pop, "x_channel", None)
        del echo._covers[:]
        self.addCleanup(echo._covers.clear)

    def test_the_cut_body_see_through_and_the_trace_selected(self):
        block, trace = _Obj("Block plain"), _Obj("Block plain trace")
        got = echo.see_through(_Doc([block, trace]), "x_channel", {"body": "Block plain", "bodies": ["Block plain", "Block plain trace"]}, [block, trace])
        self.assertEqual(got, {"body": "Block plain", "transparency": echo.COVER_ALPHA, "selected": ["Block plain trace"]})
        self.assertEqual(self.sel, [trace])
        self.assertEqual(echo._covers, [("D", "Block plain", 0)])  # put back at the next change

    def test_declared_by_a_family_and_other_tools_untouched(self):
        fam = types.SimpleNamespace(SEE_THROUGH={"y_cavity": "body"})
        echo.declare(fam)
        self.addCleanup(echo.SEE_THROUGH.pop, "y_cavity", None)
        self.assertEqual(echo.SEE_THROUGH["y_cavity"], "body")
        self.assertIsNone(echo.see_through(_Doc([]), "part_box", {"body": "B"}, []))


class _Item:
    def __init__(self, text, kids=(), parent=None):
        self._t, self._kids, self._p, self.expanded = text, list(kids), parent, False
        for k in self._kids:
            k._p = self

    def text(self, _c):
        return self._t

    def parent(self):
        return self._p

    def child(self, i):
        return self._kids[i]

    def childCount(self):
        return len(self._kids)

    def setExpanded(self, on):
        self.expanded = on


class TreeRows(unittest.TestCase):
    def test_the_groups_rows_in_sight_in_their_order(self):
        rows = [_Item(x) for x in ("Door", "Floor slab", "Roof")]
        level = _Item("Ground floor", rows)
        scrolled = []

        class Tree:
            def metaObject(self):
                return types.SimpleNamespace(className=lambda: "Gui::TreeWidget")

            def isVisible(self):
                return True

            def selectedItems(self):
                return rows

            def scrollToItem(self, it, hint):
                scrolled.append((it, hint))

        class Other(Tree):
            def metaObject(self):
                return types.SimpleNamespace(className=lambda: "QTreeWidget")  # the BIM panel's own list

        QtW = types.SimpleNamespace(QTreeWidget=object, QAbstractItemView=types.SimpleNamespace(PositionAtTop=1))
        mw = types.SimpleNamespace(findChildren=lambda cls: [Other(), Tree()])
        got = echo.tree_rows(mw, QtW, types.SimpleNamespace(Label="Ground floor"))
        self.assertEqual(got, {"rows": ["Door", "Floor slab", "Roof"], "scrolled": True})
        self.assertTrue(level.expanded)
        self.assertEqual(scrolled, [(level, 1)])


class CentreMarks(unittest.TestCase):
    def test_freecads_crosses_off_and_lines_on_whole_circles(self):
        got = in_a_process(TechDrawPaper.BODY + '''
    fc.GuiUp = True
    fc.Vector = lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z)
    made, removed = [], []
    class CE:
        Format = (1, 0.18, None, True)
    class V:
        PropertiesList = []
        ViewObject = types.SimpleNamespace(ArcCenterMarks=True)
        Scale = 1.0
        Rotation = 0
        def getScale(self):
            return 1.0
        def addProperty(self, t, n, g, d):
            self.PropertiesList.append(n)
            setattr(self, n, "")
        def setEditorMode(self, n, m):
            pass
        def makeCosmeticLine(self, p, q):
            made.append(((round(p.x, 2), round(p.y, 2)), (round(q.x, 2), round(q.y, 2))))
            return "t%d" % len(made)
        def getCosmeticEdge(self, t):
            return CE()
        def removeCosmeticEdge(self, t):
            removed.append(t)
    v = V()
    td.circle_centres = lambda view: [((10.0, 0.0), 5.0)]   # the hole; a slot's half-turn ends are not in this list
    on = td.native_marks(v, True, 2.0)
    first = list(made)
    again = td.native_marks(v, True, 2.0)                    # a second call replaces the lines
    keys = sorted(td.cosmetic_keys(v))
    print(json.dumps([on, v.ViewObject.ArcCenterMarks, first, removed, len(json.loads(getattr(v, td.MARKS_TAGS_PROP))), len(keys)]))
''')
        on, crosses, first, removed, rows, keys = got
        self.assertTrue(on)
        self.assertFalse(crosses)
        # y is turned up for FreeCAD's cosmetic frame: (cx - r - ext, cy) to (cx + r + ext, cy), then the upright line
        self.assertEqual(first, [[[3.0, 0.0], [17.0, 0.0]], [[10.0, 7.0], [10.0, -7.0]]])
        self.assertEqual(removed, ["t1", "t2"])
        self.assertEqual(rows, 2)
        self.assertEqual(keys, 2)  # td_export leaves them out of the visible lines


if __name__ == "__main__":
    unittest.main()

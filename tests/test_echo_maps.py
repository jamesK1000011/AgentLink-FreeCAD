# SPDX-License-Identifier: LGPL-2.1-or-later
# The echo's maps, round 7 (private records: window-r6-cam-fem-td-mesh-findings.md
# FEM and Mesh): a scene map pulled in front of its surface and never
# picked, a colour scale in screen space left out of the bounding box, the
# selection cleared and the body hidden under a stress map, a read's map
# framed and its range in the words, a mesh's segments drawn where the mesh
# is (its placement applied once), fea_hold's faces marked. Without
# FreeCAD: stand-ins.
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import annotate, echo, render  # noqa: E402
from test_echo_round6 import SceneNode, _Maker  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cowork_legacy  # noqa: E402  (the old camera and selection behaviour: FollowAgent on, EchoSelects select)

setUpModule, tearDownModule = _cowork_legacy.on, _cowork_legacy.off


class Coin:
    """Scene nodes made on call; the enums as attributes; SoType knows no
    FreeCAD node (a plain group stands in)."""

    def __init__(self, skip=False):
        self.skip = skip

    def __getattr__(self, k):
        if k == "SoType":
            skip = self.skip

            class T:
                @staticmethod
                def fromName(n):
                    return types.SimpleNamespace(isBad=lambda: not skip, createInstance=lambda: Skip())
            return T
        return getattr(_Maker(_Plain()), k)


class _Plain:
    def __getattr__(self, k):
        if k.startswith("So"):
            return lambda: SceneNode(k)
        raise AttributeError(k)


class Skip(SceneNode):
    def __init__(self):
        super().__init__("SoSkipBoundingGroup")
        self.mode = None

    def getField(self, n):
        node = self
        return types.SimpleNamespace(set=lambda v: setattr(node, n, v))


def kinds(node, out=None):
    out = [] if out is None else out
    out.append(node.kind)
    for c in getattr(node, "children", ()):
        kinds(c, out)
    return out


def find(node, kind):
    if node.kind == kind:
        return node
    for c in getattr(node, "children", ()):
        got = find(c, kind)
        if got is not None:
            return got
    return None


class View:
    @staticmethod
    def getSize():
        return (1600, 1000)


class FieldInFront(unittest.TestCase):
    def test_pulled_in_front_and_never_picked(self):
        scene = SceneNode("root")
        ann = annotate.Annotations(coin=Coin(), scene=lambda: scene)
        self.assertEqual(ann.field("o", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], [(1, 0, 0)] * 3), 1)
        sep = scene.children[0].children[-1]
        off = find(sep, "SoPolygonOffset")
        # negative: towards the camera (a plain offset pushed the map behind a
        # Shaded mesh and level with a Part body's faces)
        self.assertLess(off.factor, 0)
        self.assertLess(off.units, 0)
        self.assertEqual(find(sep, "SoPickStyle").style, 2)


class Proxy:
    """What pivy hands back at each getSceneGraph(): a new proxy for the
    same node (so "is" is never true between two calls)."""

    def __init__(self, node):
        self._n = node

    def addChild(self, c):
        self._n.addChild(c)

    def removeChild(self, c):
        self._n.removeChild(c)

    def findChild(self, c):
        return next((i for i, k in enumerate(self._n.children) if k is c), -1)

    @property
    def children(self):
        return self._n.children


class OneRootPerOwner(unittest.TestCase):
    def test_the_scale_keeps_the_map(self):
        # Round 8 (fem 034, mesh 012): the scale drawn after the map took the
        # map away; the scene graph's proxy is new at every call.
        scene = SceneNode("root")
        ann = annotate.Annotations(coin=Coin(skip=True), scene=lambda: Proxy(scene), view=View)
        self.assertEqual(ann.field("o", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], [(1, 0, 0)] * 3), 1)
        self.assertTrue(ann.legend("o", "VON MISES", "MPa", 0, 444, echo.FEM_STOPS))
        self.assertEqual(len(scene.children), 1)
        ks = [c.kind for c in scene.children[0].children]
        self.assertEqual(ks, ["SoSeparator", "SoSkipBoundingGroup"])
        facts = ann.field_facts("o")
        self.assertEqual(facts["annotationRoots"], 1)  # one root: the map and the scale in it
        self.assertTrue(facts["rootInScene"])
        ann.clear("o")
        self.assertEqual(scene.children, [])

    def test_a_new_scene_starts_again(self):
        a, b = SceneNode("a"), SceneNode("b")
        now = [a]
        ann = annotate.Annotations(coin=Coin(), scene=lambda: Proxy(now[0]))
        ann.field("o", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], [(1, 0, 0)] * 3)
        now[0] = b
        ann.field("o", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], [(1, 0, 0)] * 3)
        self.assertEqual((len(a.children), len(b.children)), (0, 1))

    def test_holds(self):
        sep = SceneNode("s")
        root = SceneNode("r")
        root.addChild(sep)
        self.assertTrue(annotate.holds(Proxy(root), object(), sep))
        self.assertFalse(annotate.holds(Proxy(SceneNode("x")), object(), sep))
        self.assertFalse(annotate.holds(None, None, sep))


class FieldFacts(unittest.TestCase):
    def test_chain_switches_hidden_and_drawing(self):
        top = SceneNode("SoSeparator")
        sel = SceneNode("SoFCUnifiedSelection")
        sel.name = "Selection"
        vp = SceneNode("SoFCSelectionRoot")
        sw = SceneNode("SoFCSwitch")
        sw.whichChild = -1
        top.addChild(sel)
        sel.addChild(vp)
        vp.addChild(sw)
        ann = annotate.Annotations(coin=Coin(), scene=lambda: sw, view=lambda: None)
        ann._full_scene = lambda: top
        ann.field("o", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], [(1, 0, 0)] * 3)
        f = ann.field_facts("o", [("Box", vp)])
        self.assertTrue(f["inScene"])
        self.assertEqual(f["chain"][:4], ["SoSeparator", "SoFCUnifiedSelection:Selection", "SoFCSelectionRoot", "SoFCSwitch"])
        self.assertEqual(f["chain"][-1], "SoSeparator")
        self.assertEqual(f["switches"], [{"node": "SoFCSwitch:", "whichChild": -1}])
        self.assertEqual(f["throughHidden"], ["Box"])
        self.assertEqual(f["binding"], "PER_VERTEX_INDEXED")
        self.assertEqual((f["colours"], f["points"], f["indices"], f["materialIndex"]), (3, 3, 4, 4))
        self.assertEqual(f["offset"], list(annotate.FIELD_OFFSET))

    def test_no_field(self):
        ann = annotate.Annotations(coin=Coin(), scene=lambda: None)
        self.assertEqual(ann.field_facts("o"), {"field": None})


class Legend(unittest.TestCase):
    def test_values_and_layout(self):
        self.assertEqual([t for _y, t in annotate.legend_labels(0, 444, 5)], ["0", "111", "222", "333", "444"])
        self.assertEqual(annotate.legend_value(0.01234), "0.0123")
        self.assertEqual(annotate.legend_value(-0.1), "-0.1")
        self.assertEqual(annotate.legend_value(1.2e-5), "1.2e-05")
        lay = annotate.legend_layout(1.6)
        self.assertLess(lay["x1"], 8.0)  # inside the right edge (5 x 1.6)
        self.assertLess(lay["x0"], lay["x1"])
        self.assertLess(lay["y0"], lay["y1"])
        self.assertLess(lay["title_y"], 5.0)
        tall = annotate.legend_layout(0.5)
        self.assertLess(tall["x1"], 5.0)

    def test_drawn_in_screen_space_out_of_the_box(self):
        scene = SceneNode("root")
        ann = annotate.Annotations(coin=Coin(skip=True), scene=lambda: scene, view=View, ratio=lambda: 2.0)
        got = ann.legend("o", "VON MISES", "MPa", 0, 444, echo.FEM_STOPS)
        self.assertEqual(got["labels"], ["0", "111", "222", "333", "444"])
        self.assertEqual(got["title"], "VON MISES (MPa)")
        group = scene.children[0].children[-1]
        self.assertEqual(group.kind, "SoSkipBoundingGroup")
        self.assertEqual(group.mode, "EXCLUDE_BBOX")
        ks = kinds(group)
        for k in ("SoAnnotation", "SoOrthographicCamera", "SoPickStyle", "SoLightModel", "SoText2"):
            self.assertIn(k, ks)
        cam = find(group, "SoOrthographicCamera")
        self.assertEqual((cam.height, cam.position), (10.0, (0.0, 0.0, 5.0)))
        self.assertEqual(ks.count("SoText2"), 6)  # five ticks and the title
        self.assertEqual(find(group, "SoFont").size, 26)  # 13 px times the pixel ratio
        ann.clear("o")
        self.assertEqual(scene.children, [])

    def test_a_plain_group_without_freecads_node(self):
        scene = SceneNode("root")
        ann = annotate.Annotations(coin=Coin(skip=False), scene=lambda: scene)
        self.assertTrue(ann.legend("o", "T", "", -1, 1, [(0, (0, 0, 1)), (1, (1, 0, 0))]))
        self.assertEqual(scene.children[0].children[-1].kind, "SoGroup")

    def test_no_view(self):
        ann = annotate.Annotations(coin=Coin(), scene=lambda: None)
        self.assertIsNone(ann.legend("o", "T", "", 0, 1, []))

    def test_map_stops_follow_render(self):
        st = echo.map_stops("jet", 3)
        self.assertEqual([t for t, _c in st], [0.0, 0.5, 1.0])
        self.assertEqual(st[0][1], tuple(float(c) for c in render.jet(0.0)))
        self.assertEqual(st[-1][1], tuple(float(c) for c in render.jet(1.0)))


class Words(unittest.TestCase):
    def test_map_range_in_the_words(self):
        w = echo.map_words("Curvature of Globe fine: 5301 points", {"range": [-0.1, 0.1], "label": "CURVATURE (MEAN)", "unit": "1/mm"})
        self.assertEqual(w, "Curvature of Globe fine: 5301 points; CURVATURE (MEAN) -0.1 … 0.1 1/mm")
        self.assertEqual(echo.map_words("x", None), "x")


class _Svc:
    def __init__(self):
        self.calls = []

    def field(self, owner, V, F, colours, per_face=False):
        self.calls.append(("field", list(V), list(F), per_face))
        return len(F)

    def legend(self, owner, title, unit, lo, hi, stops):
        self.calls.append(("legend", title, unit, lo, hi))
        return {"labels": ["a"], "title": title}

    def field_facts(self, owner, hidden=()):
        return {"inScene": True, "throughHidden": [lb for lb, _n in hidden]}

    def light(self, obj, subs, owner="", colour="", shape=None, badge=None):
        self.calls.append(("light", obj.Label, list(subs), colour))
        return {"lit": list(subs), "missing": []}

    def marks(self, owner, points=(), lines=(), colour=""):
        self.calls.append(("marks", list(points)))
        return len(points)

    def clear(self, owner=None):
        self.calls.append(("clear",))


class _Gui:
    def __init__(self, selected=1):
        self.cleared = 0
        self.Selection = types.SimpleNamespace(getSelectionEx=lambda: [object()] * selected, clearSelection=self._clear)
        self.ActiveDocument = None

    def _clear(self):
        self.cleared += 1


class WithStandIns(unittest.TestCase):
    def setUp(self):
        self.svc = _Svc()
        self.gui = _Gui()
        self._had = {k: sys.modules.get(k) for k in ("FreeCADGui",)}
        sys.modules["FreeCADGui"] = self.gui
        self._fc, self._svc0 = echo.FreeCAD, annotate._SERVICE
        annotate._SERVICE = self.svc
        echo.FreeCAD = types.SimpleNamespace(ActiveDocument=None, ParamGet=lambda p: types.SimpleNamespace(GetBool=lambda k, d: d),
                                             listDocuments=lambda: {})
        del echo._hid_for_scene[:]

    def tearDown(self):
        echo.FreeCAD, annotate._SERVICE = self._fc, self._svc0
        del echo._hid_for_scene[:]
        for k, v in self._had.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


class Segments(WithStandIns):
    def test_drawn_where_the_mesh_is(self):
        class P:
            def __init__(self, x, y, z):
                self.Vector = types.SimpleNamespace(x=x, y=y, z=z)

        class Mesh:
            CountFacets = 2
            Points = [P(10, 0, 0), P(11, 0, 0), P(10, 1, 0), P(11, 1, 0)]
            Facets = [types.SimpleNamespace(PointIndices=(0, 1, 2)), types.SimpleNamespace(PointIndices=(1, 3, 2))]

            @staticmethod
            def getPlanarSegments(dev, least):
                return [[0, 1]]

        class Placement:
            @staticmethod
            def multVec(v):  # would move it 100 along x: Points are placed already
                return types.SimpleNamespace(x=v.x + 100, y=v.y, z=v.z)

        o = types.SimpleNamespace(Name="Cube_mesh", Label="Cube mesh", Mesh=Mesh, Placement=Placement)
        doc = types.SimpleNamespace(getObject=lambda n: o if n == "Cube_mesh" else None,
                                    getObjectsByLabel=lambda lb: [o] if lb == "Cube mesh" else [], Objects=[o])
        got = echo.segments_drawn(doc, {"mesh": "Cube mesh", "kind": "planar", "minFacets": 2}, {"mesh": "Cube mesh"})
        self.assertEqual(got["regions"], 1)
        self.assertEqual(got["triangles"], 2)
        V = self.svc.calls[0][1]
        self.assertEqual(V[0], (10, 0, 0))


class Stress(WithStandIns):
    def test_own_deck_hides_the_body_and_draws_the_scale(self):
        body = types.SimpleNamespace(Label="Box", Name="Box", Document=types.SimpleNamespace(Name="D"),
                                     ViewObject=types.SimpleNamespace(Visibility=True))
        s = types.SimpleNamespace(_agentlink_fea={"body": "Box", "field": {}}, body=lambda n: body)
        V = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        had = render.MAPS.get("stress")
        render.MAPS["stress"] = (lambda s_, a: {"layers": [{"V": V, "F": [(0, 1, 2)], "values": [0.0, 200.0, 444.0]}],
                                               "unit": "MPa", "cmap": "jet", "label": "VON MISES"}, "")
        try:
            doc = types.SimpleNamespace(Objects=[], getObject=lambda n: None, getObjectsByLabel=lambda lb: [])
            got = echo.fem_result_shown(doc, {"solvedBy": "Agent Link's own CalculiX deck"}, s)
        finally:
            if had is None:
                render.MAPS.pop("stress", None)
            else:
                render.MAPS["stress"] = had
        self.assertEqual(got["triangles"], 1)
        self.assertEqual(got["hidden"], ["Box"])
        self.assertFalse(body.ViewObject.Visibility)
        self.assertTrue(got["legend"])
        self.assertEqual(got["selectionCleared"], 1)
        self.assertEqual(self.gui.cleared, 1)
        leg = [c for c in self.svc.calls if c[0] == "legend"][0]
        self.assertEqual(leg[1:3], ("VON MISES", "MPa"))
        self.assertEqual(got["range"], [0.0, 444.0])
        self.assertEqual(got["selectedAfter"], 1)  # the stand-in keeps its one
        self.assertTrue(got["scene"]["inScene"])

    def test_scale_tops_at_the_solves_peak(self):
        # fem 034 round 8: the scale's 406 against the caption's 432.
        body = types.SimpleNamespace(Label="Box", Name="Box", Document=types.SimpleNamespace(Name="D"),
                                     ViewObject=types.SimpleNamespace(Visibility=True, RootNode="vp"))
        s = types.SimpleNamespace(_agentlink_fea={"body": "Box", "field": {"vonMises": [0.0, 120.0, 432.4]}}, body=lambda n: body)
        V = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        had = render.MAPS.get("stress")
        render.MAPS["stress"] = (lambda s_, a: {"layers": [{"V": V, "F": [(0, 1, 2)], "values": [0.0, 200.0, 405.7]}],
                                               "unit": "MPa", "cmap": "jet", "label": "VON MISES"}, "")
        try:
            doc = types.SimpleNamespace(Objects=[], getObject=lambda n: None, getObjectsByLabel=lambda lb: [])
            got = echo.fem_result_shown(doc, {"solvedBy": "Agent Link's own CalculiX deck"}, s)
        finally:
            if had is None:
                render.MAPS.pop("stress", None)
            else:
                render.MAPS["stress"] = had
        self.assertEqual(got["range"], [0.0, 432.4])
        leg = [c for c in self.svc.calls if c[0] == "legend"][0]
        self.assertEqual(leg[4], 432.4)
        self.assertEqual(got["scene"]["throughHidden"], ["Box"])


class Curvature(WithStandIns):
    def test_framed_scaled_and_nothing_selected(self):
        framed = []
        had_frame = echo.frame_box
        echo.frame_box = lambda v, box: framed.append(box) or True
        had = render.MAPS.get("curvature")
        V = [(50, 0, 0), (60, 0, 0), (50, 10, 0)]
        render.MAPS["curvature"] = (lambda s_, a: {"layers": [{"V": V, "F": [(0, 1, 2)], "values": [-0.1, 0.0, 0.1]}],
                                                  "range": [-0.1, 0.1], "unit": "1/mm", "cmap": "jet", "label": "CURVATURE (MEAN)"}, "")
        try:
            got = echo.map_shown(types.SimpleNamespace(doc=None), "curvature", {"mesh": "Globe fine"})
        finally:
            echo.frame_box = had_frame
            if had is None:
                render.MAPS.pop("curvature", None)
            else:
                render.MAPS["curvature"] = had
        self.assertEqual(got["triangles"], 1)
        self.assertEqual(got["range"], [-0.1, 0.1])
        self.assertTrue(got["legend"] and got["framed"])
        self.assertEqual(got["selectionCleared"], 1)
        self.assertEqual(framed[0], (50.0, 0.0, 0.0, 60.0, 10.0, 0.0))
        self.assertIn("scene", got)
        self.assertIn("selectedAfter", got)

    def test_not_on_the_persons_document(self):
        echo.FreeCAD.ActiveDocument = types.SimpleNamespace(Name="Theirs")
        got = echo.map_shown(types.SimpleNamespace(doc=types.SimpleNamespace(Name="Mine")), "curvature", {})
        self.assertIsNone(got)
        self.assertEqual(self.svc.calls, [])


class Hold(WithStandIns):
    def _doc(self, o):
        return types.SimpleNamespace(getObject=lambda n: o if n == o.Name else None,
                                     getObjectsByLabel=lambda lb: [o] if lb == o.Label else [], Objects=[o])

    def test_held_face_and_its_edges_lit(self):
        from agentlink import store

        e1, e2, e3 = (types.SimpleNamespace(n=i) for i in (1, 2, 3))
        for e in (e1, e2, e3):
            e.isSame = (lambda me: lambda other: other is me)(e)
        face = types.SimpleNamespace(Edges=[e1, e3])
        shape = types.SimpleNamespace(Edges=[e1, e2, e3], getElement=lambda n: face)
        o = types.SimpleNamespace(Name="Box", Label="Box", Shape=shape, ViewObject=types.SimpleNamespace(Visibility=True))
        had_read, had_gs = store.read, annotate.global_shape
        store.read = lambda doc, key, default=None: {"body": "Box"}
        annotate.global_shape = lambda obj: shape
        try:
            got = echo.hold_marked(self._doc(o), {"held": [{"face": "Face1", "centre": [0, 500, 500]}]})
        finally:
            store.read, annotate.global_shape = had_read, had_gs
        self.assertEqual(got, {"body": "Box", "lit": ["Face1", "Edge1", "Edge3"]})
        self.assertEqual(self.svc.calls[0][3], echo.HOLD_COLOUR)

    def test_a_solid_studied_alone_gets_marks(self):
        from agentlink import store

        o = types.SimpleNamespace(Name="Box", Label="Box", ViewObject=types.SimpleNamespace(Visibility=True))
        had_read = store.read
        store.read = lambda doc, key, default=None: {"body": "Box", "of": {"body": "Box", "solid": 1}}
        try:
            got = echo.hold_marked(self._doc(o), {"held": [{"face": "Face1", "centre": [0, 500, 500]}]})
        finally:
            store.read = had_read
        self.assertEqual(got, {"marks": 1})

    def test_nothing_held(self):
        self.assertIsNone(echo.hold_marked(None, {"holds": []}))


if __name__ == "__main__":
    unittest.main()

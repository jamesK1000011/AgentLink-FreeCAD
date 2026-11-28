# SPDX-License-Identifier: LGPL-2.1-or-later
# The faults window review round 7 (pass 3) found in TechDraw, BIM and CAM,
# on stand-ins (plain Python, no FreeCAD):
#   - TechDraw: td_hatch makes FreeCAD's own hatch on the view face that
#     shows the part's face; labels kept off dimension lines and leaders;
#     td_dimset's texts at each pair's middle; td_dim_repair moves the text
#     with its reference; "1×" before the ⌀; the words carry the values;
#   - BIM: grid lines, cut outlines and nested pieces drawn over the model
#     and framed; the tree shown after bim_reorder; the curtain wall's
#     DiffuseColor traceback folded as FreeCAD's own;
#   - CAM: a pocket on walls that close round nothing is refused before
#     FreeCAD's PocketShape raises "EdgeWalker has no edges to load".
import ast
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_famfix import TechDrawPaper, entries  # noqa: E402
from test_hubfix2 import in_a_process  # noqa: E402

TD = TechDrawPaper.BODY


def _cw(entry):
    """Every word of a tools.json entry: its card and its inputs' meanings (agentlink.tooldata.card_words)."""
    from agentlink.tooldata import card_words
    return card_words(entry)


def src(*parts):
    with open(os.path.join(HERE, *parts), encoding="utf-8") as f:
        return f.read()


class TechDrawPlacing(unittest.TestCase):
    def test_count_goes_before_the_diameter_sign(self):
        got = in_a_process(TD + '''
    print(json.dumps([td.prefixed("⌀%.2f", "count", 2), td.prefixed("1× ⌀%.1f", "count", 3), td.prefixed("%.2f", "count", 4),
                      td.prefixed("%.2f", "diameter", 1), td.prefixed("R%.1f", "square", 1)]))
''')
        self.assertEqual(got, ["2× ⌀%.2f", "3× ⌀%.1f", "4× %.2f", "⌀%.2f", "R□%.1f"])

    def test_labels_keep_off_lines_and_leaders_do_not_cross(self):
        got = in_a_process(TD + '''
    lane = [((50, 50), (150, 50))]                       # a chain's dimension line
    on_line = td.free_spot([], (297, 210), (100, 50), 14, 5.5, lines=lane)
    other = [((120, 80), (80, 120))]                     # another leader
    crossing = td.free_spot([], (297, 210), (110, 110), 10, 5, lines=other, src=(90, 90))
    free = td.free_spot([], (297, 210), (60, 100), 10, 5, lines=other, src=(50, 90))
    print(json.dumps([on_line, crossing, free, td.seg_in_box((0, 0), (10, 0), (5, 0, 2, 2)), td.seg_in_box((0, 5), (10, 5), (5, 0, 2, 2)),
                      td._cross((0, 0), (10, 10), (0, 10), (10, 0)), td._cross((0, 0), (5, 5), (5, 5), (10, 0))]))
''')
        on_line, crossing, free, through, beside, x, touching = got
        self.assertGreater(abs(on_line[1] - 50), 2.75 + 0.5)  # the box no longer sits on the line
        self.assertNotEqual(crossing, [110, 110])              # its leader from (90, 90) crossed the other
        self.assertEqual(free, [60, 100])
        self.assertEqual([through, beside, x, touching], [True, False, True, False])

    def test_a_moved_reference_takes_its_text_along_outside(self):
        got = in_a_process(TD + '''
    print(json.dumps([td.moved_text((-8, -20), (-40, -20), (10, -30)), td.moved_text((0, 0), (0, 10), (5, 3)), td.moved_text((0, 0), (0, 0), (5, 3))]))
''')
        # R3 on the slot's right end (text lower right) moved to the left end:
        # the text goes lower LEFT of the left end, not across the slot
        self.assertEqual(got, [[-58, -30], [5, 13], [5, 3]])

    def test_the_view_face_that_shows_a_part_face(self):
        got = in_a_process(TD + '''
    sq = [(0, 0), (60, 0), (60, 40), (0, 40)]
    a, c = td.poly_area_centre(sq)
    faces = [(2400.0, (30.0, -20.0)), (124.3, (18.0, 10.0)), (78.5, (30.0, 20.0)), (28.3, (45.0, 30.0))]
    print(json.dumps([a, c, td.pick_view_face(faces, 2400.0, (30.0, 20.0)), td.pick_view_face(faces, 78.0, (30.0, 20.0)), td.pick_view_face(faces, 500.0, (0, 0))]))
''')
        self.assertEqual(got, [2400.0, [30.0, 20.0], 0, 2, None])

    def test_native_hatch_on_stand_ins(self):
        got = in_a_process(TD + '''
    import TechDraw
    made = []
    class Hatch:
        TypeId = "TechDraw::DrawHatch"
        Name = "Hatch"
        HatchPattern = "/x/Mod/TechDraw/Patterns/simple.svg"
        State = []
        def __init__(self):
            self.PropertiesList = []
        def addProperty(self, t, n, g, d):
            self.PropertiesList.append(n)
    class Doc:
        def addObject(self, t, n):
            h = Hatch()
            made.append(h)
            return h
        def removeObject(self, n):
            made.append("removed " + n)
        def recompute(self):
            pass
    class P:
        def __init__(self, x, y, z=0.0):
            self.x, self.y, self.z = x, y, z
    class W:
        def __init__(self, pts):
            self.pts = pts
        def isClosed(self):
            return True
        def discretize(self, Deflection=0.02):
            return [P(*p) for p in self.pts]
    rect = [(-30, -20), (30, -20), (30, 20), (-30, 20)]
    hole = [(-5, -5), (5, -5), (5, 5), (-5, 5)]
    TechDraw.edgeWalker = lambda es, big: [W(rect), W(hole)]
    old = Hatch()
    old.PropertiesList = [td.HATCH_OWN]
    old.Name = "Hatch001"
    v = types.SimpleNamespace(Name="V", Scale=1.0, getScale=lambda: 1.0, InList=[old], getVisibleEdges=lambda: [1], touch=lambda: None, requestPaint=lambda: None)
    face = types.SimpleNamespace(OuterWire=W([(0, 0, 8), (60, 0, 8), (60, 40, 8), (0, 40, 8)]))
    src = types.SimpleNamespace(getElement=lambda f: face)
    td.frame_of = lambda v, cache: (1.0, 1, 0.0, 0.0)
    td.to_view = lambda fr, v, p: (p.x - 30, p.y - 20)
    out = td.native_hatch(Doc(), v, src, ["Face6"])
    if len(made) < 2:
        raise SystemExit(json.dumps(out))
    h = made[1]
    print(json.dumps([made[0], out, list(h.Source[1]), json.loads(getattr(h, td.HATCH_OWN))]))
''')
        self.assertEqual(got[0], "removed Hatch001")
        self.assertEqual(got[1]["viewFace"], ["Face0"])
        self.assertEqual(got[1]["viewFaces"], 2)
        self.assertEqual(got[1]["pattern"], "simple.svg")
        self.assertEqual(got[2:], [["Face0"], ["Face6"]])

    def test_the_entries(self):
        e = entries()
        hatch = json.dumps(e["td_hatch"])
        self.assertIn("native_hatch(v, src, [f for f in faces if f not in flat])", hatch)
        self.assertIn('"hatch": {"when": "=native.get(\'object\')"', hatch)
        self.assertIn("in the window as FreeCAD's own hatch", _cw(e["td_hatch"]))
        self.assertIn("('textAt', [num(nx, 2), num(ny, 2)])", json.dumps(e["td_dimset"]["steps"]))
        self.assertIn("else mid[0]", json.dumps(e["td_dimset"]["steps"]))
        repair = json.dumps(e["td_dim_repair"])
        self.assertIn('"a0": "=dim_anchor(d)"', repair)
        self.assertIn("moved_text(a0, a1, (float(d.X), float(d.Y)))", repair)
        self.assertIn("textMoved", repair)
        self.assertIn("nudge_out(d)", json.dumps(e["td_dim_format"]["steps"]))
        self.assertIn('"moved"', json.dumps(e["td_dim_align"]["answer"]))
        self.assertIn('"wrote"', json.dumps(e["td_export"]["answer"]))
        for t in ("td_area", "td_leader", "td_finish", "td_gdt", "td_weld", "td_dim_special"):
            self.assertIn("src=", json.dumps(e[t]["steps"]), t)
        self.assertIn('"storeyNames"', json.dumps(e["ifc_open"]["answer"]))
        self.assertIn('"edges": "=sum(', json.dumps(e["bim_panel_out"]))
        self.assertIn('"names": "=[basename(h) for h in hits[:50]]"', json.dumps(e["bim_library"]))
        self.assertIn('"xCount"', json.dumps(e["bim_grid"]["answer"]))
        self.assertIn("open_walls(src.Shape, names) if kind == 'pocket' else []", json.dumps(e["cam_op"]["steps"]))


class Words(unittest.TestCase):
    def test_the_words_carry_the_values(self):
        from agentlink import activity

        did = activity.did
        self.assertEqual(did("td_export", {"page": "Plate drawing"}, {"page": "Plate drawing", "wrote": "Plate-drawing .svg 12 kB, .pdf 8 kB, .dxf 30 kB"}),
                         "Exported Plate drawing: Plate-drawing .svg 12 kB, .pdf 8 kB, .dxf 30 kB")
        self.assertEqual(did("td_hatch", {"view": "PlateTop", "faces": ["Face3"]}, {"view": "PlateTop", "faces": ["Face3"]}), "Hatched Face3 of PlateTop")
        self.assertEqual(did("td_dim_align", {}, {"count": 2, "moved": 0}), "Lined up 2 dimensions (0 moved)")
        self.assertEqual(did("td_dim_format", {}, {"texts": ["1× ⌀6.0"]}), "Set the dimension to read 1× ⌀6.0")
        self.assertEqual(did("td_dim_repair", {}, {"label": "Dimension002", "text": "R3.00"}), "Moved Dimension002 onto new edges: it reads R3.00")
        self.assertEqual(did("bim_nest", {"container": "Sheet", "pieces": ["A", "B", "C"]}, {"placed": 3, "of": 3, "sheets": 1}), "Nested 3 of 3 pieces on Sheet")
        self.assertEqual(did("bim_grid", {}, {"xCount": 3, "yCount": 3, "length": 8000}), "Made grid lines, 3 along X and 3 along Y, 8000 mm long")
        self.assertEqual(did("bim_panel_out", {"panels": ["Shelf"]}, {"edges": 6}), "Made the cut outline of Shelf: 6 edges")
        self.assertEqual(did("bim_library", {"search": "shelf"}, {"names": ["shelf-block.FCStd"], "count": 1}), "Searched the library for shelf: shelf-block.FCStd")
        self.assertEqual(did("bim_library", {"search": "zzz"}, {"names": [], "count": 0}), "Searched the library for zzz: none found")
        self.assertEqual(did("ifc_open", {"path": "~/x/house.ifc"}, {"path": "/u/x/house.ifc"}), "Opened house.ifc")
        self.assertEqual(activity.outcome("ifc_open", True, {"schema": "IFC4", "storeyNames": ["Ground floor", "Roof level"], "elements": 12, "path": "/a/house.ifc"}),
                         "IFC IFC4, storeys Ground floor and Roof level, 12 elements")


class Bim(unittest.TestCase):
    def test_outline_names_and_words(self):
        from agentlink import echo

        names = echo.outline_names("bim_panel_out", {"panels": ["Shelf"]}, {"cuts": [{"panel": "Shelf", "cut": "ShelfCut"}]})
        nest = echo.outline_names("bim_nest", {"container": "Sheet", "pieces": ["A", "B"]}, {"placed": 2})
        grid = echo.outline_names("bim_grid", {}, {"axes": ["Grid X", "Grid Y"]})
        self.assertEqual(names, [("ShelfCut", "cuts")])
        self.assertEqual(nest, [("Sheet", "container"), ("A", "pieces"), ("B", "pieces")])
        self.assertEqual(grid, [("Grid X", "axes"), ("Grid Y", "axes")])
        self.assertEqual([echo.outline_words("bim_grid", "axes", "Grid Y", 1, 3), echo.outline_words("bim_nest", "container", "Sheet", 0, 4),
                          echo.outline_words("bim_panel_out", "cuts", "ShelfCut", 0, 6), echo.outline_words("bim_nest", "pieces", "A", 0, 4)],
                         ["Grid Y 2", "sheet Sheet", "ShelfCut: 6 edges", "A"])

    def test_the_echo_wiring(self):
        from agentlink import echo

        self.assertEqual(echo.OUT_MORE["bim_nest"], ("pieces", "container"))
        self.assertEqual(echo.out_names("td_dim_align", {}, {"dims": [{"dimension": "Dimension005", "at": [0, -50]}]}), ["Dimension005"])
        self.assertIn("bim_reorder", echo.TREE_TOOLS)
        e = src("agentlink", "echo.py")
        self.assertIn('self._step(tr, "outlines", outlines_shown, doc, name, args, body)', e)
        self.assertIn('self._step(tr, "tree", tree_shown, doc, args, body)', e)

    def test_the_curtain_wall_traceback_is_folded_as_freecads_own(self):
        from agentlink import report_watch as rw

        lines = ["12:49:55  pyException: Traceback (most recent call last):",
                 '  File "/Applications/FreeCAD.app/Contents/Resources/Mod/BIM/ArchCurtainWall.py", line 738, in updateData',
                 "    self.colorize(obj, force=True)",
                 '  File "/Applications/FreeCAD.app/Contents/Resources/Mod/BIM/ArchCurtainWall.py", line 794, in colorize',
                 "    if self.areDifferentColors(colors, obj.ViewObject.DiffuseColor) or force:",
                 "<class 'AttributeError'>: 'Gui.ViewProviderGeometryObject' object has no attribute 'DiffuseColor'",
                 "12:49:56  Wall: something else failed"]
        kept, counts = rw.fold_known(lines)
        self.assertEqual(kept, ["12:49:56  Wall: something else failed"])
        self.assertEqual(list(counts.values()), [1])
        self.assertIn("ArchCurtainWall.py", next(iter(counts)))


class CamOpenWalls(unittest.TestCase):
    """open_walls on stand-ins for Part and TechDraw: the function's own code
    taken out of cam.py (the family imports FreeCAD's CAM)."""

    def run_walls(self, outline):
        tree = ast.parse(src("agentlink", "families", "cam.py"))
        code = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_upright", "_touching", "open_walls")]
        mod = ast.Module(body=code, type_ignores=[])

        class Plane:
            def __init__(self, z):
                self.Axis = types.SimpleNamespace(z=z)

        class Face:
            def __init__(self, z, name):
                self.Surface, self.name, self.Edges = Plane(z), name, []

            def isSame(self, o):
                return o is self

            def distToShape(self, o):
                return (0.0 if {self.name, o.name} <= {"Face1", "Face2"} else 5.0,)

        class Compound:
            def __init__(self, faces):
                self.Faces = faces

        part = types.ModuleType("Part")
        part.Plane, part.Cylinder, part.SurfaceOfExtrusion = Plane, type("Cyl", (), {}), type("Ext", (), {})
        part.makeCompound = Compound
        part.Face = lambda w: types.SimpleNamespace(Area=w)
        tdm = types.ModuleType("TechDraw")
        tdm.findShapeOutline = outline
        fcm = types.ModuleType("FreeCAD")
        fcm.Vector = lambda *a: a
        faces = {"Face1": Face(0.0, "Face1"), "Face2": Face(0.0, "Face2"), "Face5": Face(1.0, "Face5")}
        shape = types.SimpleNamespace(getElement=lambda n: faces[n])
        saved = {k: sys.modules.get(k) for k in ("Part", "TechDraw")}
        sys.modules.update(Part=part, TechDraw=tdm)
        try:
            ns = {"FreeCAD": fcm}
            exec(compile(mod, "cam.py", "exec"), ns)
            return ns["open_walls"](shape, ["Block.Face1", "Face2", "Face5"]), ns["open_walls"](shape, ["Face5"])
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    def test_walls_that_close_round_nothing_are_named(self):
        def raises(g, k, d):
            raise ValueError("EdgeWalker has no edges to load")

        self.assertEqual(self.run_walls(raises), (["Face1", "Face2"], []))
        self.assertEqual(self.run_walls(lambda g, k, d: 120.0), ([], []))


if __name__ == "__main__":
    unittest.main()

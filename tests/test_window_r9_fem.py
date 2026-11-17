# SPDX-License-Identifier: LGPL-2.1-or-later
# Window round 9, FEM (live 17 Nov, r8fem-1…8): after fea_solve no von Mises
# map and no scale (the window's FEM mesh views are plain geometry views, so
# FreeCAD's setNodeColorByScalars was not there and show_result raised);
# fem_linearize showed the result mesh grey with no map and no line; the FEM
# mesh and the solid drawn over each other (z-fighting) on every picture.
# The result's own node values are now drawn on its solid in the scene, as
# fea_probe and fea_chart draw theirs, with one surface shown. Without
# FreeCAD: stand-ins.
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import activity, echo  # noqa: E402
from test_echo_maps import WithStandIns  # noqa: E402


class _PlainVO:
    """The window's view of a FEM mesh in FreeCAD 1.1.3 (live): a plain
    geometry view, with no setNodeColorByScalars."""

    def __init__(self, visible=True):
        self.Visibility = visible


class _FemVO(_PlainVO):
    def __init__(self, visible=True):
        super().__init__(visible)
        self.colours = None

    def setNodeColorByScalars(self, ids, vals):
        self.colours = (list(ids), list(vals))


def _v(x, y, z):
    return types.SimpleNamespace(x=float(x), y=float(y), z=float(z))


class _BoxShape:
    """An 8000 x 1000 x 1000 box's surface, as Shape.tessellate gives it."""
    P = [(0, 0, 0), (8000, 0, 0), (8000, 1000, 0), (0, 1000, 0), (0, 0, 1000), (8000, 0, 1000), (8000, 1000, 1000), (0, 1000, 1000)]
    T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (3, 7, 6), (3, 6, 2), (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5)]

    def tessellate(self, tol):
        return [_v(*p) for p in self.P], list(self.T)


def _obj(name, type_id, label=None, vo=None, **kw):
    return types.SimpleNamespace(Name=name, Label=label or name, TypeId=type_id, Document=types.SimpleNamespace(Name="D"),
                                 ViewObject=vo if vo is not None else _PlainVO(), **kw)


def _doc(objs):
    return types.SimpleNamespace(Objects=objs, getObject=lambda n: next((o for o in objs if o.Name == n), None),
                                 getObjectsByLabel=lambda lb: [o for o in objs if o.Label == lb])


def _study(field="vonMises", vals=(433.0, 0.0), res_vo=None):
    """FreeCAD's CalculiX route in the window: the Box, its analysis with a
    Gmsh mesh (Shape: the Box), the result, its mesh (hidden) and the
    pipeline, all views plain."""
    box = _obj("Box", "Part::Box", Shape=_BoxShape())
    gmsh = _obj("Mesh", "Fem::FemMeshObjectPython", "Mesh", Shape=box)
    fm = types.SimpleNamespace(Nodes={1: _v(0, 0, 1000), 2: _v(8000, 500, 500)})
    res_mesh = _obj("ResultMesh", "Fem::FemMeshObjectPython", "CCX_Results_Mesh", vo=res_vo or _PlainVO(False), FemMesh=fm)
    kw = {"vonMises": list(vals) if field == "vonMises" else [1.0, 2.0], "NodeNumbers": [1, 2]}
    if field != "vonMises":
        kw[field] = list(vals)
    res = _obj("CCX_Results", "Fem::FemResultObjectPython", "CCX_Results", Mesh=res_mesh, **kw)
    pipe = _obj("Pipeline", "Fem::FemPostPipeline", "Pipeline_CCX_Results")
    an = _obj("Analysis", "Fem::FemAnalysis", "Box strength (fea_solve)", Group=[gmsh, res, pipe])
    return _doc([box, an, gmsh, res, res_mesh, pipe]), box, gmsh, res, res_mesh, pipe


class SolveMap(WithStandIns):
    def test_von_mises_drawn_with_a_plain_mesh_view(self):
        # r8fem-1: a plain mesh view (no setNodeColorByScalars) left no map.
        doc, box, gmsh, res, res_mesh, pipe = _study()
        got = echo.fem_result_shown(doc, {"solvedBy": "FreeCAD FEM (CalculiX)"}, None, "fea_solve")
        self.assertEqual(got["map"], "VON MISES on CCX_Results_Mesh")
        self.assertEqual(got["result"], "CCX_Results")
        self.assertEqual((got["unit"], got["range"]), ("MPa", [0.0, 433.0]))
        self.assertTrue(got["legend"])
        leg = [c for c in self.svc.calls if c[0] == "legend"]
        self.assertEqual(leg, [("legend", "VON MISES", "MPa", 0.0, 433.0)])
        self.assertTrue([c for c in self.svc.calls if c[0] == "field"])
        # One surface: the solid, its Gmsh mesh and the pipeline hidden under the map.
        self.assertEqual(sorted(got["hidden"]), ["Box", "Mesh", "Pipeline_CCX_Results"])
        self.assertFalse(box.ViewObject.Visibility or gmsh.ViewObject.Visibility or pipe.ViewObject.Visibility)
        self.assertFalse(res_mesh.ViewObject.Visibility)

    def test_freecad_colours_where_no_solid_is_found(self):
        doc, box, gmsh, res, res_mesh, pipe = _study(res_vo=_FemVO(False))
        del gmsh.Shape  # no solid to draw on
        got = echo.fem_result_shown(_doc([o for o in doc.Objects if o is not box]), {}, None, "fea_solve")
        self.assertEqual(got["colouredBy"], "FreeCAD")
        self.assertEqual(res_mesh.ViewObject.colours, ([1, 2], [433.0, 0.0]))
        self.assertTrue(res_mesh.ViewObject.Visibility)
        self.assertIn("Mesh", got["hidden"])

    def test_node_colours_say_why_not(self):
        m = _obj("ResultMesh", "Fem::FemMeshObjectPython", "CCX_Results_Mesh", vo=_PlainVO(False))
        self.assertIn("cannot colour nodes", echo.fem_node_colours(m, [1], [1.0]))
        self.assertFalse(m.ViewObject.Visibility)
        m.ViewObject = _FemVO(False)
        self.assertIsNone(echo.fem_node_colours(m, [1], [1.0]))
        self.assertTrue(m.ViewObject.Visibility)


class LinearizeMap(WithStandIns):
    def test_stress_xx_drawn_and_the_line_marked(self):
        # r8fem-5: no STRESS XX map, no line, the result mesh grey on the Box.
        doc, box, gmsh, res, res_mesh, pipe = _study("NodeStressXX", (-216.0, 216.0))
        self.svc.marks = lambda owner, points=(), lines=(), colour="", labels=(): self.svc.calls.append(("marks", list(points), [t for _p, t in labels])) or len(points)
        got = echo.fem_read_map(doc, "fem_linearize", {"result": "CCX_Results", "from": [4000, 500, 0], "to": [4000, 500, 1000]},
                                {"result": "CCX_Results", "field": "NodeStressXX"}, None)
        self.assertEqual(got["map"], "STRESS XX on CCX_Results_Mesh")
        self.assertEqual((got["label"], got["unit"], got["range"]), ("STRESS XX", "MPa", [-216.0, 216.0]))
        self.assertTrue(got["legend"] and got["lineMarked"])
        self.assertEqual(sorted(got["hidden"]), ["Box", "Mesh", "Pipeline_CCX_Results"])
        self.assertIn(("marks", [(4000, 500, 0), (4000, 500, 1000)], ["from", "to"]), self.svc.calls)
        self.assertFalse(res_mesh.ViewObject.Visibility)  # not shown grey over the map

    def test_neither_way_says_why(self):
        doc, box, gmsh, res, res_mesh, pipe = _study("NodeStressXX", (-1.0, 1.0))
        del gmsh.Shape
        got = echo.fem_read_map(_doc([o for o in doc.Objects if o is not box]), "fem_linearize", {"result": "CCX_Results"},
                                {"field": "NodeStressXX"}, None)
        self.assertIsNone(got["map"])
        self.assertIn("cannot colour nodes", got["why"])


class OneSurface(WithStandIns):
    def test_mesh_hidden_off_its_solid_or_the_solid_for_a_mesh_just_made(self):
        # r8fem-6/7: the Gmsh mesh and the Box drawn over each other.
        # Round 10: the result's mesh and the pipeline on the same solid are
        # hidden too (they lie on its surface as well).
        doc, box, gmsh, res, res_mesh, pipe = _study()
        res_mesh.ViewObject.Visibility = True
        got = echo.fem_one_surface(doc)
        self.assertEqual(got["kept"], {"Box": "Box"})
        self.assertEqual(sorted(got["hidden"]), ["CCX_Results_Mesh", "Mesh", "Pipeline_CCX_Results"])
        self.assertTrue(box.ViewObject.Visibility)
        gmsh.ViewObject.Visibility = True
        got = echo.fem_one_surface(doc, [gmsh])
        self.assertEqual((got["kept"], got["hidden"]), ({"Box": "Mesh"}, ["Box"]))
        self.assertTrue(gmsh.ViewObject.Visibility)
        # Nothing over anything: nothing hidden.
        self.assertEqual(echo.fem_one_surface(doc)["hidden"], [])

    def test_the_echo_calls_it_when_no_map_is_drawn(self):
        src = open(os.path.join(HERE, "..", "agentlink", "echo.py"), encoding="utf-8").read()
        self.assertIn('self._step(tr, "femOneSurface", fem_one_surface, doc, named)', src)
        self.assertNotIn("resulttools.show_result(res", src)


class Captions(unittest.TestCase):
    def test_heat_caption_reads_hottest_and_coolest_from_the_answer(self):
        b = {"body": "Box", "hottest": {"celsius": 100.0, "x": 0}, "coolest": {"celsius": 20.0, "x": 8000}}
        self.assertEqual(activity.key_value(b), "hottest 100 °C, coolest 20 °C")

    def test_chart_line_is_the_callers(self):
        # r8fem-4: fea_chart kind line has no default line (it is refused
        # without one): the line given runs where the caller put it.
        text = open(os.path.join(HERE, "..", "agentlink", "data", "tools.json"), encoding="utf-8").read()
        self.assertIn("\"when\": \"=kind == 'line' and not a.line\"", text)


if __name__ == "__main__":
    unittest.main()

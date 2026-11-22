# SPDX-License-Identifier: LGPL-2.1-or-later
# Window round 10 (17 Nov, r9 pictures), stand-ins for:
#   - one surface per solid after a FEM call with no map (r9fem-4/5: the Gmsh
#     mesh and the Box still drawn over each other). FreeCAD 1.1's Gmsh mesh
#     is a Fem::FemMeshShapeBaseObjectPython, which the round 9 test (a
#     TypeId starting "Fem::FemMeshObject") did not take for a mesh.
#   - the result map coloured from the nodes on the solid's faces, and
#     fea_chart's line said to be read from the nearest nodes (r9fem-3).
#   - job_start's words: the inner read's value, its note only after
#     (r9echo-7); measure_mass says its mass.
#   - report_read: the counts, then the first problem's words with its tag
#     off, cut at a word; a read never leaves another document in front
#     (r9echo-11).
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import activity, echo  # noqa: E402
from test_echo_maps import WithStandIns  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cowork_legacy  # noqa: E402  (the old camera and selection behaviour: FollowAgent on, EchoSelects select)

setUpModule, tearDownModule = _cowork_legacy.on, _cowork_legacy.off

GMSH_11 = "Fem::FemMeshShapeBaseObjectPython"  # FreeCAD 1.1's Gmsh and Netgen meshes


class _VO:
    def __init__(self, visible=True):
        self.Visibility = visible


def _obj(name, type_id, label=None, visible=True, **kw):
    return types.SimpleNamespace(Name=name, Label=label or name, TypeId=type_id, Document=types.SimpleNamespace(Name="D"),
                                 ViewObject=_VO(visible), **kw)


def _fm(nodes):
    return types.SimpleNamespace(NodeCount=nodes)


def _r9fem4():
    """SheetFemModel9 at r9fem-4: the Box; fea_solve's analysis (its Gmsh
    mesh meshed, the result, the result's mesh and the pipeline, all shown
    again by the change's scene_clear); fea_native's new analysis with its
    Gmsh mesh not meshed yet."""
    box = _obj("Box", "Part::Box")
    gmsh = _obj("Mesh", GMSH_11, Shape=box, FemMesh=_fm(4200))
    res_mesh = _obj("ResultMesh", "Fem::FemMeshObjectPython", "CCX_Results_Mesh", FemMesh=_fm(4200))
    res = _obj("CCX_Results", "Fem::FemResultObjectPython", Mesh=res_mesh)
    clip = _obj("Clip", "Fem::FemPostClipFilter", "Clip")
    pipe = _obj("Pipeline", "Fem::FemPostPipeline", "Pipeline_CCX_Results", Group=[clip])
    an = _obj("Analysis", "Fem::FemAnalysis", "Box strength (fea_solve)", Group=[gmsh, res, res_mesh, pipe])
    native_mesh = _obj("Mesh001", GMSH_11, Shape=box, FemMesh=_fm(0))
    native = _obj("Analysis001", "Fem::FemAnalysis", "Box native", Group=[native_mesh])
    objs = [box, an, gmsh, res, res_mesh, pipe, clip, native, native_mesh]
    doc = types.SimpleNamespace(Objects=objs, getObject=lambda n: next((o for o in objs if o.Name == n), None),
                                getObjectsByLabel=lambda lb: [o for o in objs if o.Label == lb])
    return doc, box, gmsh, res_mesh, pipe, clip, native_mesh


class MeshKind(unittest.TestCase):
    def test_every_fem_mesh_kind(self):
        for t in (GMSH_11, "Fem::FemMeshObject", "Fem::FemMeshObjectPython", "Fem::FemMeshShapeNetgenObject", "Fem::FemMeshShapeObject"):
            self.assertTrue(echo._is_fem_mesh(types.SimpleNamespace(TypeId=t)), t)
        for t in ("Fem::FemAnalysis", "Fem::FemResultObjectPython", "Fem::FemPostPipeline", "Part::Box", "Fem::FeaturePython"):
            self.assertFalse(echo._is_fem_mesh(types.SimpleNamespace(TypeId=t)), t)

    def test_freecads_own_kind_test_first(self):
        o = types.SimpleNamespace(TypeId="Fem::SomethingNew", isDerivedFrom=lambda k: k == "Fem::FemMeshObject")
        self.assertTrue(echo._is_fem_mesh(o))
        self.assertTrue(echo._is_fem_view(_obj("M", GMSH_11)))


class OneSurface(WithStandIns):
    def test_r9fem4_the_box_alone(self):
        doc, box, gmsh, res_mesh, pipe, clip, native_mesh = _r9fem4()
        # fea_native named its own (empty) mesh: the Box stays, not the mesh
        # that draws nothing.
        got = echo.fem_one_surface(doc, [native_mesh])
        self.assertEqual(got["kept"], {"Box": "Box"})
        self.assertEqual(sorted(got["hidden"]), ["CCX_Results_Mesh", "Clip", "Mesh", "Pipeline_CCX_Results"])
        self.assertTrue(box.ViewObject.Visibility)
        self.assertTrue(native_mesh.ViewObject.Visibility)  # left as it is: it draws nothing
        for o in (gmsh, res_mesh, pipe, clip):
            self.assertFalse(o.ViewObject.Visibility, o.Label)

    def test_a_named_mesh_with_nodes_is_the_one_kept(self):
        doc, box, gmsh, res_mesh, pipe, clip, native_mesh = _r9fem4()
        got = echo.fem_one_surface(doc, [gmsh])
        self.assertEqual(got["kept"], {"Box": "Mesh"})
        self.assertIn("Box", got["hidden"])
        self.assertTrue(gmsh.ViewObject.Visibility)
        self.assertFalse(box.ViewObject.Visibility or res_mesh.ViewObject.Visibility)

    def test_the_solid_hidden_by_hand_leaves_one_view(self):
        doc, box, gmsh, res_mesh, pipe, clip, native_mesh = _r9fem4()
        box.ViewObject.Visibility = False
        got = echo.fem_one_surface(doc)
        self.assertEqual(got["kept"], {"Box": "Mesh"})
        shown = [o.Label for o in (box, gmsh, res_mesh, pipe, clip) if o.ViewObject.Visibility]
        self.assertEqual(shown, ["Mesh"])

    def test_shown_again_at_the_next_change(self):
        doc, box, gmsh, res_mesh, pipe, clip, native_mesh = _r9fem4()
        echo.fem_one_surface(doc)
        self.assertEqual(len(echo._hid_for_scene), 4)

    def test_no_fem_views_says_nothing(self):
        box = _obj("Box", "Part::Box")
        doc = types.SimpleNamespace(Objects=[box])
        self.assertEqual(echo.fem_one_surface(doc), [])

    def test_wired_after_changes_and_reads_with_no_map(self):
        src = open(os.path.join(HERE, "..", "agentlink", "echo.py"), encoding="utf-8").read()
        self.assertIn('self._step(tr, "femOneSurface", fem_one_surface, doc, named)', src)
        self.assertIn('self._step(tr, "femOneSurface", fem_one_surface, self.s.doc)', src)


class SurfaceNodes(unittest.TestCase):
    def test_only_the_nodes_on_the_faces(self):
        # nodes 1, 2 on the faces; 3 inside the part (lower in bending)
        fm = types.SimpleNamespace(getNodesByFace=lambda f: {"top": [1], "side": [2]}[f])
        res = types.SimpleNamespace(Mesh=types.SimpleNamespace(FemMesh=fm), NodeNumbers=[1, 2, 3])
        solid = types.SimpleNamespace(Shape=types.SimpleNamespace(Faces=["top", "side"]))
        P, V, on = echo._surface_nodes(res, solid, [(0, 0, 1), (0, 1, 0), (0, 0.5, 0.5)], [400.0, 300.0, 5.0])
        self.assertFalse(on)  # fewer than 3: every node
        fm.getNodesByFace = lambda f: {"top": [1, 4], "side": [2, 4]}[f]
        res.NodeNumbers = [1, 2, 3, 4]
        P, V, on = echo._surface_nodes(res, solid, [(0, 0, 1), (0, 1, 0), (0, 0.5, 0.5), (0, 1, 1)], [400.0, 300.0, 5.0, 350.0])
        self.assertTrue(on)
        self.assertEqual(V, [400.0, 300.0, 350.0])
        self.assertEqual(len(P), 3)

    def test_every_node_where_freecad_cannot_say(self):
        res = types.SimpleNamespace(Mesh=types.SimpleNamespace(FemMesh=types.SimpleNamespace()), NodeNumbers=[1, 2])
        solid = types.SimpleNamespace(Shape=types.SimpleNamespace(Faces=["f"] * (echo.SURFACE_FACES_MOST + 1)))
        self.assertEqual(echo._surface_nodes(res, solid, [(0, 0, 0), (1, 1, 1)], [1.0, 2.0]), ([(0, 0, 0), (1, 1, 1)], [1.0, 2.0], False))


class ChartWords(unittest.TestCase):
    def test_a_line_is_read_from_the_nearest_nodes(self):
        b = {"body": "Box", "kind": "line", "field": "vonMises", "unit": "MPa", "nodes": 9000, "samples": 9, "max": 377.2}
        got = echo.read_words(activity.did("fea_chart", {"name": "cantilever-top-edge"}, b), activity.outcome("fea_chart", True, b, {}))
        self.assertTrue(got.endswith("line of von Mises up to 377 MPa, 9 samples from the nearest nodes"), got)


class JobWords(unittest.TestCase):
    A = {"tool": "measure_mass", "arguments": {"body": "Plate"}}

    def words(self, a, b):
        return echo.read_words(activity.did("job_start", a, b), activity.outcome("job_start", True, b, a))

    def test_the_mass_first_the_note_not_in_its_place(self):
        # r9echo-7: the answer of an add-on that owns mass, done within the call
        b = {"bodies": [{"body": "Plate", "mass": 14.88, "material": "PLA (assumed; set the material to change it)", "volume": 12000.0}],
             "units": "mm, g", "note": "A body with no material is taken as PLA: set its material to change that.", "job": "job-1"}
        self.assertEqual(self.words(self.A, b), "Ran a job: mass of Plate 14.9 g (PLA assumed)")

    def test_the_hubs_own_answer(self):
        b = {"body": "Plate", "density": 1.24, "densityFrom": "assumed pla: printed, and no material_set", "volume": 12000.0, "mass": 14.88}
        self.assertEqual(self.words(self.A, b), "Ran a job: mass of Plate 14.9 g (PLA assumed)")
        got = echo.read_words(activity.did("measure_mass", {"body": "Plate"}, b), activity.outcome("measure_mass", True, b, {"body": "Plate"}))
        self.assertEqual(got, "Weighed Plate: mass of Plate 14.9 g (PLA assumed)")

    def test_a_read_with_no_value_of_its_own_then_its_outcome(self):
        a = {"tool": "meshobj_info", "arguments": {"mesh": "Globe"}}
        got = self.words(a, {"mesh": "Globe", "note": "A mesh with open edges."})
        self.assertTrue(got.startswith("Ran a job: "), got)
        self.assertNotIn("done", got)

    def test_running_unchanged(self):
        got = self.words(self.A, {"job": "job-2", "status": "running", "tool": "measure_mass", "running": 2})
        self.assertEqual(got, "Started a job: weighed Plate: running, 2 s so far")


class ReportWords(unittest.TestCase):
    LINE = '(qt.qpa.fonts) Populating font family aliases took 33 ms. Replace uses of missing font family "Sans" with one that exists to avoid this cost.'

    def test_tag_off_cut_at_a_word(self):
        got = activity.problem_words(self.LINE)
        self.assertTrue(got.startswith("Populating font family aliases took 33 ms."), got)
        self.assertIn('"Sans"', got)
        self.assertLessEqual(len(got), activity.PROBLEM_MOST)
        self.assertTrue(got.endswith("…") and not got.endswith(" …"), got)
        self.assertEqual(activity.problem_words("[Gui] short one"), "short one")

    def test_caption_counts_then_the_first(self):
        b = {"found": True, "problems": 1, "count": 45, "first": self.LINE}
        got = echo.read_words(activity.did("report_read", {"problems": True}, b), activity.outcome("report_read", True, b, {"problems": True}))
        self.assertIn('1 problem, 45 lines; first: Populating font family aliases took 33 ms. Replace uses of missing font family "Sans"', got)
        self.assertNotIn("qt.qpa", got)


class _Tool:
    def __init__(self, name, changes=False):
        self.name, self.changes = name, changes


class FrontKept(WithStandIns):
    def setUp(self):
        super().setUp()
        self.calls = []
        docs = {"JobProbe": object(), "SheetFemModel9": object()}
        fc = echo.FreeCAD
        fc.ActiveDocument = types.SimpleNamespace(Name="JobProbe")
        fc.listDocuments = lambda: docs

        def set_active(n):
            self.calls.append(("app", n))
            fc.ActiveDocument = types.SimpleNamespace(Name=n)

        fc.setActiveDocument = set_active
        self.gui.setActiveDocument = lambda n: self.calls.append(("gui", n))

    def test_which_calls_keep_the_front(self):
        self.assertTrue(echo.keeps_front(_Tool("report_read")))
        self.assertTrue(echo.keeps_front(_Tool("session_state")))
        self.assertTrue(echo.keeps_front(_Tool("measure_mass")))
        for t in (_Tool("doc_switch"), _Tool("doc_open"), _Tool("batch"), _Tool("gui_input"), _Tool("part_primitive", True)):
            self.assertFalse(echo.keeps_front(t), t.name)

    def test_put_back_after_a_read(self):
        ec = echo.Echo(types.SimpleNamespace(doc=None))
        ec.before(_Tool("report_read"), {"problems": True})
        echo.FreeCAD.ActiveDocument = types.SimpleNamespace(Name="SheetFemModel9")  # something brought it forward
        ec.after(_Tool("report_read"), {"problems": True}, {"content": [{"type": "text", "text": "{}"}]})
        self.assertEqual(ec.front_kept, {"was": "JobProbe", "came": "SheetFemModel9"})
        self.assertEqual(self.calls, [("app", "JobProbe"), ("gui", "JobProbe")])
        self.assertEqual(echo.FreeCAD.ActiveDocument.Name, "JobProbe")

    def test_nothing_done_when_nothing_changed_or_on_purpose(self):
        self.assertIsNone(echo.front_kept("JobProbe"))
        self.assertIsNone(echo.front_kept("Closed meanwhile"))
        ec = echo.Echo(types.SimpleNamespace(doc=None))
        ec.before(_Tool("doc_switch"), {"document": "SheetFemModel9"})
        echo.FreeCAD.ActiveDocument = types.SimpleNamespace(Name="SheetFemModel9")
        ec.after(_Tool("doc_switch"), {"document": "SheetFemModel9"}, {"content": [{"type": "text", "text": "{}"}]})
        self.assertEqual(self.calls, [])

    def test_reselect_clears_only_the_active_documents_selection(self):
        log = []
        self.gui.Selection = types.SimpleNamespace(
            getSelectionEx=lambda doc="", resolve=1: [types.SimpleNamespace(DocumentName="JobProbe", ObjectName="Peg", SubElementNames=())],
            clearSelection=lambda *a: log.append(("clear",) + a), addSelection=lambda *a: log.append(("add",) + a))
        self.assertEqual(echo.reselect(), ["Peg"])
        self.assertEqual(log, [("clear", "JobProbe"), ("add", "JobProbe", "Peg")])


if __name__ == "__main__":
    unittest.main()

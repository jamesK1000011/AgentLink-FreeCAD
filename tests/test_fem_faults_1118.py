# SPDX-License-Identifier: LGPL-2.1-or-later
# Faults of the 17 Nov handoff (FEM and window), stand-ins for:
#   1. the Von Mises map read in patches: each surface point took its
#      nearest node's value. Now blended from the nearest nodes on the
#      mesh's outside (render.smooth_values, render.surface_nodes).
#   2. the Model tree kept another document's row lit (blue).
#   3. a hidden result map kept an open eye on its result's row.
#   4. after fea_buckle the last call's selection stayed.
#   5. FEM captions began with the tool's name ("FEM buckle: …").
#   6. an add-on's captions come from its own CAPTIONS, never the hub.
import json
import os
import sys
import types
import unittest
from unittest import mock

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import activity, echo, render  # noqa: E402
from test_echo_maps import WithStandIns  # noqa: E402


def src(*parts):
    with open(os.path.join(HERE, "..", *parts), encoding="utf-8") as f:
        return f.read()


# ---- 1. smooth maps ------------------------------------------------------------------------

class SmoothValues(unittest.TestCase):
    S = np.array([[0.0, 0, 0], [10.0, 0, 0], [0, 10.0, 0], [10.0, 10.0, 0], [5.0, 5.0, 8.0]])
    V = np.array([0.0, 100.0, 50.0, 400.0, 200.0])

    def test_a_node_keeps_its_value(self):
        got = render.smooth_values(self.S, self.S, self.V)
        np.testing.assert_allclose(got, self.V)

    def test_between_nodes_it_runs_smoothly(self):
        # Along the edge from 0 to 100: the nearest node's value jumped
        # once in the middle; blended values rise step by step.
        line = np.array([[x, 0.0, 0.0] for x in np.linspace(0.5, 9.5, 19)])
        got = render.smooth_values(line, self.S, self.V)
        near = render.nearest_values(line, self.S, self.V)
        self.assertEqual(len(set(np.round(near, 6))), 2)  # the old map: two flat patches
        self.assertGreater(len(set(np.round(got, 6))), 10)
        self.assertTrue(np.all(np.diff(got[:9]) > 0), got)

    def test_never_past_the_nodes(self):
        rng = np.random.default_rng(3)
        P = rng.random((500, 3)) * 10
        got = render.smooth_values(P, self.S, self.V)
        self.assertTrue(np.all(got >= self.V.min() - 1e-9) and np.all(got <= self.V.max() + 1e-9))

    def test_without_scipy_the_same(self):
        rng = np.random.default_rng(4)
        S = rng.random((300, 3))
        vals = rng.random(300) * 50
        P = rng.random((200, 3))
        with_tree = render.smooth_values(P, S, vals)
        with mock.patch.dict(sys.modules, {"scipy": None, "scipy.spatial": None}):
            brute = render.smooth_values(P, S, vals, chunk=37)
        np.testing.assert_allclose(brute, with_tree, rtol=1e-9, atol=1e-9)

    def test_empty_and_one_source(self):
        self.assertEqual(len(render.smooth_values(np.zeros((0, 3)), self.S, self.V)), 0)
        self.assertTrue(np.isnan(render.smooth_values(np.zeros((2, 3)), np.zeros((0, 3)), np.zeros(0))).all())
        np.testing.assert_allclose(render.smooth_values(np.ones((3, 3)), [[0, 0, 0]], [7.0]), [7.0, 7.0, 7.0])


class SurfaceNodes(unittest.TestCase):
    def test_two_tetrahedra_share_a_face(self):
        # 0-1-2 shared; 3 and 4 the tips: every node is on the outside
        self.assertEqual(render.surface_nodes([[0, 1, 2, 3], [0, 2, 1, 4]]), [0, 1, 2, 3, 4])

    def test_an_inner_node_is_left_out(self):
        # Four tetrahedra round node 4 inside the tetrahedron 0-1-2-3.
        elems = [[0, 1, 2, 4], [0, 3, 1, 4], [1, 3, 2, 4], [2, 3, 0, 4]]
        self.assertEqual(render.surface_nodes(elems), [0, 1, 2, 3])

    def test_ten_node_tetrahedra_keep_their_mid_side_nodes(self):
        self.assertEqual(render.surface_nodes([list(range(10))]), list(range(10)))
        self.assertEqual(render.surface_nodes([[1, 2, 3]]), [])

    def test_the_maps_use_them(self):
        view = src("agentlink", "families", "view.py")
        self.assertIn("render.surface_nodes(f.get(\"elements\") or ())", view)
        self.assertIn("V, F, vals, fit = render.blend_fit(V, F, SP, SV, budget=render.map_budget(s))", view)  # smooth_values inside, on the surface nodes (test drive of 20 Nov)
        e = src("agentlink", "echo.py")
        self.assertIn("sv = render.smooth_values(layer[\"V\"], SP, SV)", e)
        self.assertIn("render.smooth_values(layer[\"V\"], SP, SU)", e)


class OuterNodes(unittest.TestCase):
    def test_from_the_result_meshs_volumes(self):
        # node 5 inside: four tetrahedra round it
        vols = {1: (1, 2, 3, 5), 2: (1, 4, 2, 5), 3: (2, 4, 3, 5), 4: (3, 4, 1, 5)}
        fm = types.SimpleNamespace(Volumes=list(vols), getElementNodes=lambda v: vols[v])
        res = types.SimpleNamespace(NodeNumbers=[1, 2, 3, 4, 5])
        P = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.2, 0.2, 0.2)]
        got = echo._outer_nodes(res, fm, P, [1.0, 2.0, 3.0, 4.0, 0.5])
        self.assertEqual(got, (P[:4], [1.0, 2.0, 3.0, 4.0], True))

    def test_every_node_where_freecad_cannot_say(self):
        res = types.SimpleNamespace(NodeNumbers=[1, 2])
        self.assertEqual(echo._outer_nodes(res, types.SimpleNamespace(), [(0, 0, 0), (1, 1, 1)], [1.0, 2.0])[2], False)


# ---- 2. the tree's document rows ----------------------------------------------------------

class TreeDocuments(unittest.TestCase):
    def test_only_other_documents_rows_are_put_out(self):
        D, O = echo.TREE_DOCUMENT_TYPE, echo.TREE_DOCUMENT_TYPE + 1
        rows = [(0, "Application", False, False), (D, "Model", True, False), (D, "Other", True, False),
                (D, "Third", False, True), (O, "Box", True, False)]
        self.assertEqual(echo.docs_to_unlight(rows, "Model"), [2, 3])
        self.assertEqual(echo.docs_to_unlight(rows, None), [1, 2, 3])

    def test_run_after_every_call(self):
        self.assertIn('self._step(tr, "treeDocsUnlit", tree_docs_unlit)', src("agentlink", "echo.py"))


# ---- 3. eyes in the tree --------------------------------------------------------------------

class _VO:
    def __init__(self, visible=True, children=()):
        self._v = visible
        self.children = children

    @property
    def Visibility(self):
        return self._v

    @Visibility.setter
    def Visibility(self, v):
        # FreeCAD's result row passes its Visibility to its mesh
        # (view_result_mechanical.py onChanged).
        self._v = bool(v)
        for c in self.children:
            c.ViewObject.Visibility = v


def _result(mesh_visible, row_visible):
    doc = types.SimpleNamespace(Name="D", Objects=[])
    mesh = types.SimpleNamespace(Name="ResultMesh", Label="ResultMesh", TypeId="Fem::FemMeshObjectPython", Document=doc,
                                 ViewObject=_VO(mesh_visible))
    res = types.SimpleNamespace(Name="CCX_Results", Label="CCX_Results", TypeId="Fem::FemResultObjectPython", Document=doc,
                                Mesh=mesh, ViewObject=_VO(row_visible, (mesh,)))
    mesh.InList = [res]
    doc.Objects += [res, mesh]
    doc.getObject = lambda n: next((o for o in doc.Objects if o.Name == n), None)
    return doc, res, mesh


class Eyes(WithStandIns):
    def test_the_row_follows_its_hidden_map(self):
        doc, res, mesh = _result(False, True)  # as FreeCAD's importer leaves them
        self.assertEqual(echo.fem_eyes_synced(doc), ["CCX_Results"])
        self.assertFalse(res.ViewObject.Visibility)
        self.assertEqual(echo.fem_eyes_synced(doc), [])

    def test_a_shown_map_shows_its_row(self):
        doc, res, mesh = _result(True, False)
        echo.fem_eyes_synced(doc)
        self.assertTrue(res.ViewObject.Visibility and mesh.ViewObject.Visibility)

    def test_hidden_with_its_mesh_and_back_in_order(self):
        doc, res, mesh = _result(True, True)
        self.assertEqual(echo.hide_for_scene([mesh]), ["ResultMesh"])
        self.assertFalse(res.ViewObject.Visibility)
        self.assertEqual(echo._hid_for_scene, [("D", "ResultMesh"), ("D", "CCX_Results")])
        echo.FreeCAD.listDocuments = lambda: {"D": doc}
        echo.FreeCAD.getDocument = lambda n: doc
        echo.scene_clear()
        self.assertTrue(res.ViewObject.Visibility and mesh.ViewObject.Visibility)

    def test_wired(self):
        self.assertEqual(src("agentlink", "echo.py").count('self._step(tr, "femEyes", fem_eyes_synced,'), 2)


# ---- 4. the selection after a FEM read with no map -----------------------------------------

class ReadSelection(WithStandIns):
    def test_cleared_and_noted(self):
        echo._read_sel[0] = False
        self.assertEqual(echo.fem_read_unselected(), 1)
        self.assertEqual(self.gui.cleared, 1)
        self.assertTrue(echo._read_sel[0])
        echo._read_sel[0] = False

    def test_wired_for_reads_that_select_nothing(self):
        e = src("agentlink", "echo.py")
        self.assertIn('self._step(tr, "selectionCleared", fem_read_unselected)', e)
        self.assertIn("not name.startswith(FEM_READS)", e)


# ---- 5. FEM captions ------------------------------------------------------------------------

class FemWords(unittest.TestCase):
    def test_every_fem_tool_has_its_own_words(self):
        tools = json.loads(src("agentlink", "data", "tools.json"))["entries"]
        words = json.loads(src("agentlink", "data", "activity.json"))["entries"]
        bare = [k for k in tools if k.startswith(("fea_", "fem_")) and k not in words and not tools[k].get("activity")]
        self.assertEqual(bare, [])
        for k in tools:
            if k.startswith(("fea_", "fem_")):
                for a in ({}, {"body": "Box", "action": "netgen"}):
                    w = activity.did(k, a, {})
                    self.assertFalse(w.lower().startswith(("fem ", "fea ")), (k, w))

    def test_the_caption_after_fea_buckle(self):
        b = {"body": "Box", "modes": [{"factor": 3.21}, {"factor": 5.0}]}
        got = echo.read_words(activity.did("fea_buckle", {"count": 2}, b), activity.outcome("fea_buckle", True, b, {"count": 2}))
        self.assertEqual(got, "Checked Box for buckling: lowest load factor 3.21")
        b = {"body": "Box", "modes": [{"hz": 12.3}, {"hz": 40.0}]}
        got = echo.read_words(activity.did("fea_modes", {}, b), activity.outcome("fea_modes", True, b, {}))
        self.assertEqual(got, "Found the vibration modes of Box: 2 modes: 12.3, 40 Hz")


# ---- 6. an add-on's own captions ------------------------------------------------------------

class Captions(unittest.TestCase):
    def setUp(self):
        self._caps = dict(echo.CAPTIONS)

    def tearDown(self):
        echo.CAPTIONS.clear()
        echo.CAPTIONS.update(self._caps)

    def test_declared_by_the_add_on(self):
        fam = types.SimpleNamespace(CAPTIONS={"mine_share": ["Shared {document} with {to}", "Shared the work"],
                                              "mine_": lambda name, a, b: "Mine: " + name[5:] if b else None})
        echo.declare(fam)
        self.assertEqual(echo.declared_caption("mine_share", {"document": "Lid", "to": "a friend"}, {}), "Shared Lid with a friend")
        self.assertEqual(echo.declared_caption("mine_share", {}, {}), "Shared the work")
        self.assertEqual(echo.declared_caption("mine_pull", {}, {"ok": 1}), "Mine: pull")
        self.assertIsNone(echo.declared_caption("part_box", {}, {}))
        self.assertIsNone(echo.captioned("minecraft"))

    def test_neutral_words_never_the_tools_name(self):
        echo.declare(types.SimpleNamespace(CAPTIONS={"mine_do": "Did it to {body}", "mine_x": lambda n, a, b: None}))
        self.assertEqual(echo.declared_caption("mine_do", {}, {}), echo.CAPTION_DONE)
        self.assertEqual(echo.declared_caption("mine_do", {}, None, "before"), echo.CAPTION_BEFORE)
        self.assertEqual(echo.declared_caption("mine_x", {}, {}, "refused"), echo.CAPTION_REFUSED)
        self.assertEqual(echo._describe("mine_x", {}), echo.CAPTION_BEFORE)

    def test_said_at_the_end_even_for_a_quiet_tool(self):
        e = src("agentlink", "echo.py")
        self.assertIn("or captioned(name) is not None) and _on() and self.live():", e)
        self.assertIn('cap = declared_caption(name, args, body, "after" if ok else "refused") if not own else None', e)

    def test_documented(self):
        self.assertIn("CAPTIONS = {", src("docs", "hooks.md"))
        self.assertIn("**Your captions.**", src("docs", "hooks.md"))


if __name__ == "__main__":
    unittest.main()

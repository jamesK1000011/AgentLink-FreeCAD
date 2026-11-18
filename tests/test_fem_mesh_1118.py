# SPDX-License-Identifier: LGPL-2.1-or-later
# Live 77: object_list failed in a FEM document ("'FeaturePython' object has
# no attribute 'CountFacets'"): a FEM result's Mesh property links the FEM
# mesh object, and it was read as a Mesh::Feature's mesh. A mesh object is
# now one whose Mesh is a real mesh (geometry.mesh_of). Stand-ins only.
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from test_core_check import _geometry  # noqa: E402

geo = _geometry()


class Kernel:
    CountFacets = 12

    def isSolid(self):
        return True


def obj(type_id, mesh, derived=()):
    return types.SimpleNamespace(TypeId=type_id, Mesh=mesh, isDerivedFrom=lambda t: t == type_id or t in derived)


class MeshOf(unittest.TestCase):
    def test_a_mesh_feature(self):
        o = obj("Mesh::Feature", Kernel())
        self.assertIs(geo.mesh_of(o), o.Mesh)
        self.assertEqual(geo.mesh_row(o), {"triangles": 12, "closed": True})

    def test_fem_objects_are_not_meshes(self):
        fem_mesh = obj("Fem::FemMeshObjectPython", None)
        fem_mesh.FemMesh = object()
        result = obj("Fem::FemResultObjectPython", fem_mesh)  # Mesh links the FEM mesh object
        self.assertIsNone(geo.mesh_of(result))
        self.assertIsNone(geo.mesh_row(result))
        self.assertIsNone(geo.mesh_of(fem_mesh))
        # A FEM type with a mesh-like value is still not taken unless it is a Mesh::Feature.
        self.assertIsNone(geo.mesh_of(obj("Fem::Odd", Kernel())))
        self.assertIsNotNone(geo.mesh_of(obj("Fem::Odd", Kernel(), derived=("Mesh::Feature",))))

    def test_no_mesh(self):
        self.assertIsNone(geo.mesh_of(types.SimpleNamespace(TypeId="Part::Feature")))

    def test_object_list_reads_through_mesh_row(self):
        with open(os.path.join(HERE, "..", "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            entry = json.load(f)["entries"]["object_list"]
        text = json.dumps(entry)
        self.assertIn("mesh_row(o)", text)
        self.assertNotIn("o.Mesh.CountFacets", text)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
# Live 65: an STL export of one smooth loft face made 3.77 M triangles and
# read back closed: false for a valid closed solid. The export now meshes
# with an angular deflection beside the chord error (EXPORT_ANGULAR), and
# merges the coincident points of a periodic face's seam before it writes
# (welded_mesh); the check merges duplicate points before it says open.
# Stand-ins only (no FreeCAD).
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from test_core_check import _geometry  # noqa: E402

geo = _geometry()


def tube(n=8, split_seam=True):
    """A closed tube (two rings of n points, capped by two fans) whose seam
    points are given twice, the copies 1e-11 mm apart, as a periodic face's
    mesh has them."""
    import math

    V, F = [], []
    rings = []
    for z in (0.0, 10.0):
        ring = [len(V) + k for k in range(n)]
        for k in range(n):
            a = 2 * math.pi * k / n
            V.append((5 * math.cos(a), 5 * math.sin(a), z))
        if split_seam:
            V.append((5.0 + 1e-11, 0.0, z))  # the seam point again, at 2 pi
            ring.append(len(V) - 1)
        else:
            ring.append(ring[0])
        rings.append(ring)
    lo, hi = rings
    for k in range(n):
        F += [(lo[k], lo[k + 1], hi[k + 1]), (lo[k], hi[k + 1], hi[k])]
    for ring, z in ((lo, 0.0), (hi, 10.0)):
        V.append((0.0, 0.0, z))
        c = len(V) - 1
        F += [(c, ring[k + 1], ring[k]) if z == 0.0 else (c, ring[k], ring[k + 1]) for k in range(n)]
    return V, F


def open_edges(F):
    from collections import Counter

    c = Counter()
    for a, b, d in F:
        for e in ((a, b), (b, d), (d, a)):
            c[tuple(sorted(e))] += 1
    return sum(1 for v in c.values() if v != 2)


class Weld(unittest.TestCase):
    def test_seam_merged_and_closed(self):
        V, F = tube()
        self.assertGreater(open_edges(F), 0)
        V2, F2, merged = geo.weld_arrays(V, F, 1e-6)
        self.assertEqual(merged, 2)
        self.assertEqual(open_edges(F2.tolist()), 0)
        self.assertEqual(len(F2), len(F))

    def test_degenerate_triangles_dropped(self):
        V = [(0, 0, 0), (1, 0, 0), (1e-12, 0, 0), (0, 1, 0)]
        F = [(0, 1, 3), (0, 2, 3)]
        _V2, F2, merged = geo.weld_arrays(V, F, 1e-6)
        self.assertEqual((merged, len(F2)), (1, 1))

    def test_nothing_to_merge(self):
        V, F = tube(split_seam=False)
        _V2, _F2, merged = geo.weld_arrays(V, F, 1e-6)
        self.assertEqual(merged, 0)

    def test_angular_deflection(self):
        self.assertEqual(geo.EXPORT_ANGULAR, 0.5)

    def test_welded_mesh_on_a_stand_in(self):
        V, F = tube()

        class M:
            def __init__(self, topo, solid=False):
                self.Topology, self.solid = topo, solid
                self.CountFacets = len(topo[1])

            def isSolid(self):
                return self.solid

        made = []
        mesh_mod = types.SimpleNamespace(Mesh=lambda topo: made.append(topo) or M(topo, True))
        old = sys.modules.get("Mesh")
        sys.modules["Mesh"] = mesh_mod
        old_vec = geo.FreeCAD
        geo.FreeCAD = types.SimpleNamespace(Vector=lambda *a: a)
        try:
            shape = types.SimpleNamespace(BoundBox=types.SimpleNamespace(DiagonalLength=20.0))
            out = geo.welded_mesh(M((V, F)), shape)
            self.assertTrue(out.isSolid())
            self.assertEqual(len(made[0][0]), len(V) - 2)
            closed = M((V, F), True)
            self.assertIs(geo.welded_mesh(closed, shape), closed)  # closed already: as it is
        finally:
            geo.FreeCAD = old_vec
            if old is None:
                sys.modules.pop("Mesh", None)
            else:
                sys.modules["Mesh"] = old

    def test_mesh_closed_after_merge(self):
        class Back:
            def __init__(self):
                self.merged = False

            def isSolid(self):
                return self.merged

            def removeDuplicatedPoints(self):
                self.merged = True
        self.assertEqual(geo.mesh_closed(Back()), {"closed": True, "closedAfterMerge": True})
        b = Back()
        b.merged = True
        self.assertEqual(geo.mesh_closed(b), {"closed": True})


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
# meshbool, meshobj_boolean's own kernel (numpy only): a dense noisy
# scan-like mesh (139,968 triangles, the size of a large scan whose cut
# FreeCAD's Mesh.difference left open) cut by a solid with large faces and a
# bore through it; the triangles away from the cut kept exactly; boxes with
# faces on the mesh's own planes; and an open mesh refused, never cut.
import importlib.util
import os
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("meshbool", os.path.join(HERE, "..", "agentlink", "meshbool.py"))
MB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MB)


def grid_box(n, half=(1.0, 1.0, 1.0)):
    """A closed, welded box surface, n x n quads a face, wound outward."""
    V, F, idx = [], [], {}

    def vid(p):
        k = tuple(np.round(p, 9))
        if k not in idx:
            idx[k] = len(V)
            V.append(p)
        return idx[k]

    g = np.linspace(-1, 1, n + 1)
    for ax in range(3):
        u, w = [(1, 2), (2, 0), (0, 1)][ax]
        for sign in (-1, 1):
            for i in range(n):
                for j in range(n):
                    q = []
                    for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        p = np.zeros(3)
                        p[ax], p[u], p[w] = sign, g[a], g[b]
                        q.append(vid(p))
                    if sign < 0:
                        q = q[::-1]
                    F += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
    return np.array(V) * np.asarray(half), np.array(F, dtype=np.int64)


def scan_like(n=108, half=(40.0, 15.0, 60.0), r=6.0, noise=0.03):
    V, F = grid_box(n)
    h = np.array(half)
    core = np.clip(V * h, -(h - r), h - r)
    d = V * h - core
    L = np.linalg.norm(d, axis=1, keepdims=True)
    L[L == 0] = 1
    return core + d / L * (r + np.random.default_rng(0).normal(scale=noise, size=(len(V), 1))), F


def box(lo, hi):
    V, F = grid_box(1)
    return (V + 1) / 2 * (np.asarray(hi, float) - lo) + lo, F


def cylinder(r, z0, z1, n=48):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.stack([np.cos(t) * r, np.sin(t) * r], 1)
    V = np.vstack([np.c_[ring, np.full(n, z0)], np.c_[ring, np.full(n, z1)], [[0, 0, z0], [0, 0, z1]]])
    F = []
    for i in range(n):
        j = (i + 1) % n
        F += [[i, j, n + j], [i, n + j, n + i], [2 * n, j, i], [2 * n + 1, n + i, n + j]]
    return V, np.array(F, dtype=np.int64)


def rotation(axis, angle):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K


class DenseScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scan = scan_like()
        cls.cutter = MB.boolean(*box([-30] * 3, [30] * 3), *cylinder(8, -100, 100), "add")[:2]

    def test_closed_and_adding_up(self):
        V, F = self.scan
        self.assertEqual(len(F), 139968)
        whole = MB.volume(V, F)
        B = (self.cutter[0] @ rotation([0, 1, 1], np.pi).T + [10, 0, 50], self.cutter[1])
        vol = {}
        for op in MB.OPS:
            RV, RF, _, info = MB.boolean(V, F, *B, op)
            self.assertEqual(MB.closed_report(RF), {"open": 0, "bad": 0}, op)
            vol[op] = MB.volume(RV, RF)
        self.assertAlmostEqual(vol["subtract"] + vol["intersect"], whole, delta=whole * 1e-9)
        self.assertAlmostEqual(vol["add"] + vol["intersect"], whole + MB.volume(*B), delta=whole * 1e-9)
        self.assertGreater(vol["intersect"], 1000)

    def test_away_from_the_cut_untouched(self):
        V, F = self.scan
        RV, RF, vmap, _ = MB.boolean(V, F, self.cutter[0] + [0, 0, 60], self.cutter[1], "subtract")
        far = V[:, 2] < -10
        self.assertTrue((vmap[far] >= 0).all())
        np.testing.assert_array_equal(RV[vmap[far]], V[far])


class Small(unittest.TestCase):
    def test_coplanar_faces(self):
        C = grid_box(20, (20, 20, 20))
        for (lo, hi), common in ((([-30, -5, -5], [0, 5, 5]), 2000), (([0, 0, 0], [20, 20, 20]), 8000), (([30, 30, 30], [40, 40, 40]), 0)):
            B = box(lo, hi)
            RV, RF, _, _ = MB.boolean(*C, *B, "intersect")
            self.assertEqual(MB.closed_report(RF), {"open": 0, "bad": 0})
            self.assertAlmostEqual(MB.volume(RV, RF), common, delta=0.05)
            RV, RF, _, _ = MB.boolean(*C, *B, "subtract")
            self.assertAlmostEqual(MB.volume(RV, RF), 64000 - common, delta=0.05)

    def test_open_mesh_refused(self):
        V, F = grid_box(4, (10, 10, 10))
        with self.assertRaises(MB.BooleanError):
            MB.boolean(V, F[1:], *box([0, 0, 0], [20, 20, 20]), "subtract")


if __name__ == "__main__":
    unittest.main()

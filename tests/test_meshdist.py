# SPDX-License-Identifier: LGPL-2.1-or-later
# The nearest triangle within a reach: exact against brute force, and the
# signed distance to a box's faces.
import importlib.util
import os
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("meshdist", os.path.join(HERE, "..", "agentlink", "meshdist.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def box(n=6, s=10.0):
    V, F = [], []
    g = np.linspace(-s, s, n + 1)
    for ax in range(3):
        for sign in (-1, 1):
            u, v = (ax + 1) % 3, (ax + 2) % 3
            base = len(V)
            for a in g:
                for b in g:
                    p = [0.0, 0.0, 0.0]
                    p[ax], p[u], p[v] = sign * s, a, b
                    V.append(p)
            for i in range(n):
                for j in range(n):
                    a, b, c, d = base + i * (n + 1) + j, base + (i + 1) * (n + 1) + j, base + (i + 1) * (n + 1) + j + 1, base + i * (n + 1) + j + 1
                    F += [[a, b, c], [a, c, d]] if sign > 0 else [[a, c, b], [a, d, c]]
    return np.array(V), np.array(F)


class Nearest(unittest.TestCase):
    def test_box(self):
        V, F = box()
        P = np.random.default_rng(0).uniform(-12, 12, (20000, 3))
        best, d, s = M.nearest(P, V, F, 1.0)
        q = np.abs(P) - 10
        true = np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(1), 0)
        near = np.abs(true) <= 1
        self.assertTrue((best[near] >= 0).all())
        self.assertTrue((best[~near] < 0).all())
        self.assertLess(np.abs(s[near] - true[near]).max(), 1e-9)

    def test_brute(self):
        rng = np.random.default_rng(1)
        V = rng.uniform(-5, 5, (60, 3))
        F = rng.integers(0, 60, (40, 3))
        F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
        P = rng.uniform(-6, 6, (500, 3))
        _b, d, _s = M.nearest(P, V, F, 100.0)
        T = V[F]
        for i in range(0, 500, 7):
            Q = M.closest_on_triangles(np.repeat(P[i][None], len(T), 0), T[:, 0], T[:, 1], T[:, 2])
            self.assertAlmostEqual(d[i], np.linalg.norm(P[i] - Q, axis=1).min(), 9)


class Polylines(unittest.TestCase):
    """What FreeCAD's mesh cuts hand back, tidied (live runs, 16 Nov 2026)."""

    def ring(self, n=12, r=10.0):
        pts = [(r * np.cos(2 * np.pi * i / n), r * np.sin(2 * np.pi * i / n), 0.0) for i in range(n)]
        return pts + [pts[0]]

    def length(self, pl):
        return sum(float(np.linalg.norm(np.subtract(b, a))) for a, b in zip(pl, pl[1:]))

    def test_a_loop_answered_twice_is_kept_once(self):
        loop = self.ring()
        twice = loop + loop[1:]  # a sphere's equator through its own edges: one loop, twice round
        out, dropped = M.once_each([twice])
        self.assertEqual(dropped, 12)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(self.length(out[0]), self.length(loop), 9)
        self.assertEqual(out[0][0], out[0][-1])  # still closed
        # the second copy running the other way, as its own polyline
        out, dropped = M.once_each([loop, loop[::-1]])
        self.assertEqual((len(out), dropped), (1, 12))
        self.assertAlmostEqual(self.length(out[0]), self.length(loop), 9)

    def test_polylines_with_no_repeat_come_back_as_given(self):
        loop, other = self.ring(), [(0.0, 0.0, 5.0), (1.0, 0.0, 5.0), (1.0, 1.0, 5.0)]
        out, dropped = M.once_each([loop, other])
        self.assertEqual(dropped, 0)
        self.assertEqual(out, [loop, other])

    def test_a_spur_out_and_back_is_dropped(self):
        # FreeCAD's answer for a 6 mm line over a cube's diagonal: 16 mm with the spur to x = 0
        got = [(2, 5, 10), (3.5, 5, 10), (3.5, 5, 10), (5, 5, 10), (5, 5, 10), (0, 5, 10), (5, 5, 10), (6.5, 5, 10), (6.5, 5, 10), (8, 5, 10)]
        self.assertAlmostEqual(self.length(got), 16.0, 9)
        clean = M.no_spurs(got)
        self.assertAlmostEqual(self.length(clean), 6.0, 9)
        self.assertEqual((clean[0], clean[-1]), ((2.0, 5.0, 10.0), (8.0, 5.0, 10.0)))

    def test_corners_and_closed_loops_are_left_alone(self):
        sq = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0)]
        self.assertEqual(M.no_spurs(sq), sq)
        ring = self.ring()
        self.assertEqual(len(M.no_spurs(ring)), len(ring))


if __name__ == "__main__":
    unittest.main()

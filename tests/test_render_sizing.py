# SPDX-License-Identifier: LGPL-2.1-or-later
# A render sized before it draws (numpy only): a map of an inspection on a
# fine body's mesh (230,896 points against a 140k-triangle scan, four views
# at 1400 x 800) froze the window past the watchdog. Big layers are thinned
# to fit, nearest-value lookups stay bounded, and the drawing stops at its
# time limit instead of running into the watchdog.
import os
import sys
import time
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import render  # noqa: E402


def grid(n, values=True):
    """An n x n grid of squares (2 n^2 triangles) on z = 0, with a value per vertex."""
    xs, ys = np.meshgrid(np.arange(n + 1, dtype=float), np.arange(n + 1, dtype=float))
    V = np.stack([xs.ravel(), ys.ravel(), np.zeros(xs.size)], 1)
    i = np.arange(n)
    a = (i[:, None] * (n + 1) + i[None, :]).ravel()
    F = np.concatenate([np.stack([a, a + 1, a + n + 2], 1), np.stack([a, a + n + 2, a + n + 1], 1)])
    out = {"name": "g", "V": V, "F": F, "creases": True}
    if values:
        out["values"] = V[:, 0] / n
    return out


class Thin(unittest.TestCase):
    def test_under_cap_is_untouched(self):
        g = grid(10)
        self.assertIs(render.thin(g, 1000), g)

    def test_thinned_fits_and_keeps_values(self):
        g = grid(300)  # 180,000 triangles
        t = render.thin(g, 20000)
        self.assertLessEqual(len(t["F"]), 20000)
        self.assertGreater(len(t["F"]), 2000)
        self.assertEqual(t["thinnedFrom"], 180000)
        self.assertEqual(len(t["values"]), len(t["V"]))
        self.assertTrue(int(t["F"].max()) < len(t["V"]))
        # the values still run 0 .. 1 across x
        self.assertLess(float(np.nanmin(t["values"])), 0.05)
        self.assertGreater(float(np.nanmax(t["values"])), 0.95)
        # the extent is kept
        self.assertAlmostEqual(float(np.ptp(t["V"][:, 0])), 300.0, delta=10.0)

    def test_unmeasured_stay_unmeasured(self):
        g = grid(200)
        g["values"] = np.where(g["V"][:, 0] < 100, np.nan, 1.0)
        t = render.thin(g, 8000)
        left = t["V"][:, 0] < 90
        self.assertTrue(np.isnan(t["values"][left]).all())
        self.assertTrue((t["values"][t["V"][:, 0] > 110] == 1.0).all())

    def test_fit_layers_shares_the_cap(self):
        small = grid(20, values=False)  # 800: never thinned
        big = grid(250)  # 125,000
        scan = grid(200, values=False)  # 80,000
        out, said = render.fit_layers([small, big, scan], 40000)
        self.assertIs(out[0], small)
        self.assertEqual([s["from"] for s in said], [125000, 80000])
        self.assertLessEqual(sum(len(l["F"]) for l in out), 44000)

    def test_triangle_cap(self):
        # the live render: four views at 1400 x 800, 40 s at 1e-4 s a unit
        cap = render.triangle_cap(["right", "iso", "top", "front"], 1400, 800, 1e-4, 40.0)
        self.assertTrue(60000 < cap < 90000, cap)
        self.assertEqual(render.triangle_cap(["iso"], 800, 600, 1.0, 40.0), 2000)


class Nearest(unittest.TestCase):
    def test_brute_force_is_bounded_and_right(self):
        rng = np.random.default_rng(1)
        S = rng.random((5000, 3))
        vals = np.arange(5000, dtype=float)
        P = S[::7] + 1e-6
        with mock.patch.dict(sys.modules, {"scipy": None, "scipy.spatial": None}):
            got = render.nearest_values(P, S, vals)
        np.testing.assert_array_equal(got, vals[::7])

    def test_many_sources_are_sampled(self):
        S = np.zeros((render.NEAREST_SOURCES * 3, 3))
        S[:, 0] = np.arange(len(S))
        vals = S[:, 0].copy()
        with mock.patch.dict(sys.modules, {"scipy": None, "scipy.spatial": None}), \
                mock.patch.object(render, "NEAREST_CELLS", 2_000_000):
            got = render.nearest_values(np.array([[1000.0, 0, 0], [150000.0, 0, 0]]), S, vals)
        self.assertTrue(abs(got[0] - 1000) < 5 and abs(got[1] - 150000) < 5, got)

    def test_empty(self):
        self.assertEqual(len(render.nearest_values(np.zeros((0, 3)), np.zeros((3, 3)), np.zeros(3))), 0)
        self.assertTrue(np.isnan(render.nearest_values(np.zeros((2, 3)), np.zeros((0, 3)), np.zeros(0))).all())


class StopAt(unittest.TestCase):
    def test_views_past_the_limit_are_left_and_named(self):
        g = grid(20, values=False)
        g["color"] = (0.8, 0.5, 0.3)
        cut = []
        img, across, drawn = render.compose([g], ["top", "iso"], 400, 300, stop_at=time.time() - 1, cut=cut)
        self.assertEqual(cut, ["top", "iso"])
        self.assertFalse(drawn)
        cut = []
        img, across, drawn = render.compose([g], ["top", "iso"], 400, 300, stop_at=time.time() + 60, cut=cut)
        self.assertEqual(cut, [])
        self.assertTrue(drawn)


if __name__ == "__main__":
    unittest.main()

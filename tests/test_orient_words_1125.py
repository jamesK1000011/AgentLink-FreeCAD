# SPDX-License-Identifier: LGPL-2.1-or-later
# 25 Nov orientation fixes (owner-approved: audit issues 1-4 and 7, peer
# ideas 1-3 and 5). Small local models did not read the frame vectors: each
# answer that makes or moves a sketch now says its frame in words (axes),
# never left out as said before; the sketch_new card has the plane table;
# up turns a sketch so its y runs along a world axis, and a standing face
# sketch has y up by default; on gives the face centre and the sketch origin;
# a { side } selector says which face it took when it had a choice; the view
# cards say what each view name shows. Plain Python with stand-ins: no
# FreeCAD here. What FreeCAD itself does (the planes' axes, the attacher's
# reversed) is checked live.
import json
import math
import os
import random
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import facesel, orient  # noqa: E402

X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
# The planes' frames as FreeCAD 1.1 answered them in the 25 Nov local-model runs (sketch_new frame).
PLANES = {"XY": (X, Y, Z), "XZ": (X, Z, (0.0, -1.0, 0.0)), "YZ": (Y, Z, X)}


def fr(x, y, n, o=(0, 0, 0)):
    return {"origin": o, "xAxis": x, "yAxis": y, "normal": n}


def neg(v):
    return tuple(-c for c in v)


def close(a, b, tol=1e-9):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


def tools_json():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


class AxesInWords(unittest.TestCase):
    def test_the_xz_plane_offset_15(self):
        self.assertEqual(orient.axes_line(fr(*PLANES["XZ"], o=(0, -15, 0))),
                         "x runs +X; y runs +Z (up); the normal points -Y: a pad grows toward -Y, a pocket or hole cuts toward +Y. "
                         "[0, 0] is at world (0, -15, 0).")

    def test_xy_and_yz(self):
        self.assertEqual(orient.axes_line(fr(*PLANES["XY"])),
                         "x runs +X; y runs +Y; the normal points +Z: a pad grows toward +Z, a pocket or hole cuts toward -Z. [0, 0] is at world (0, 0, 0).")
        self.assertTrue(orient.axes_line(fr(*PLANES["YZ"])).startswith("x runs +Y; y runs +Z (up); the normal points +X: a pad grows toward +X"))

    def test_down_is_said(self):
        # the old +y face frame of the runs: y [0, 0, -1]
        self.assertIn("y runs -Z (down)", orient.axes_line(fr(X, (0, 0, -1), Y, o=(0, 15, 0))))

    def test_a_tilted_frame_is_mostly(self):
        n = (0.8, 0.0, 0.6)
        line = orient.axes_line(fr(Y, (-0.6, 0.0, 0.8), n))
        self.assertIn("y runs mostly +Z (37° off)", line)
        self.assertIn("the normal points mostly +X (37° off): a pad grows along it, a pocket or hole cuts against it.", line)

    def test_numbers(self):
        self.assertEqual(orient.num(-0.0004), "0")
        self.assertEqual(orient.num(2.5), "2.5")
        self.assertEqual(orient.num(-15.0), "-15")


class FaceAxes(unittest.TestCase):
    SIDES = {"+z": (Z, X, Y), "-z": (neg(Z), X, neg(Y)),          # flat faces: as before (x the first world axis in the face)
             "+y": (Y, neg(X), Z), "-y": (neg(Y), X, Z),          # standing faces: y up, x level to the right
             "+x": (X, Y, Z), "-x": (neg(X), neg(Y), Z)}

    def test_each_side(self):
        for side, (n, x, y) in self.SIDES.items():
            gx, gy = orient.face_axes(n)
            self.assertTrue(close(gx, x) and close(gy, y), (side, gx, gy))

    def test_right_handed_and_never_down_on_a_standing_face(self):
        rnd = random.Random(7)
        for _ in range(300):
            n = orient._unit(tuple(rnd.uniform(-1, 1) for _ in range(3)))
            for up in (None, "x", "y", "z"):
                try:
                    x, y = orient.face_axes(n, up)
                except ValueError:
                    continue
                self.assertTrue(close(orient._cross(x, y), n, 1e-9), (n, up))
                self.assertAlmostEqual(orient._dot(x, n), 0.0, places=9)
                if up is None and orient.standing(n):
                    self.assertGreater(y[2], 0.0, n)

    def test_up_on_a_face_and_on_a_plane(self):
        x, y = orient.face_axes(Z, "x")          # on top: y along +X, x then -Y
        self.assertTrue(close(y, X) and close(x, neg(Y)))
        x, y = orient.up_axes(PLANES["XZ"][2], "x")   # XZ turned: y along +X, x then -Z, normal still -Y
        self.assertTrue(close(y, X) and close(x, neg(Z)))
        x, y = orient.up_axes(PLANES["YZ"][2], "z")   # YZ with up z: as it is
        self.assertTrue(close(x, Y) and close(y, Z))

    def test_up_along_the_normal_is_refused(self):
        with self.assertRaises(ValueError) as e:
            orient.up_axes(Z, "z")
        self.assertIn("up z: that axis is along this plane's normal (+Z)", str(e.exception))
        with self.assertRaises(ValueError):
            orient.up_key("w")


def plane_face(center, normal, area=100.0):
    return {"center": list(center), "at": list(center), "normal": list(normal), "area": area, "type": "plane"}


class PickedWords(unittest.TestCase):
    # An L: base top at z 5 (large), upright top at z 20 (small), a bottom at z 0.
    FACES = [plane_face((10, 0, 5), Z, 1500.0), plane_face((-27.5, 0, 20), Z, 150.0), plane_face((0, 0, 0), neg(Z), 1800.0)]

    def test_the_farthest_says_so_and_the_pick_is_the_same(self):
        q = {"side": "+z"}
        i = facesel.select(self.FACES, q)
        self.assertEqual(i, 1)
        self.assertEqual(facesel.pick_words(self.FACES, i, q),
                         "picked the +z face at z 20, the farthest of the +z faces (z 5, z 20). For another, give face { at, normal } or { side, of }.")

    def test_largest(self):
        q = {"side": "+z", "largest": True}
        i = facesel.select(self.FACES, q)
        self.assertEqual(i, 0)
        self.assertIn("picked the +z face at z 5, the largest of 2 +z faces (1500 mm²; they lie at z 5, z 20)", facesel.pick_words(self.FACES, i, q))

    def test_no_choice_no_words(self):
        self.assertIsNone(facesel.pick_words(self.FACES, 2, {"side": "-z"}))
        self.assertIsNone(facesel.pick_words(self.FACES, 1, {"at": [0, 0, 20], "normal": [0, 0, 1]}))
        two_on_one_plane = [plane_face((10, 0, 5), Z), plane_face((-10, 0, 5), Z, 50.0)]
        self.assertIsNone(facesel.pick_words(two_on_one_plane, 0, {"side": "+z"}))  # one plane: farthest had no choice


class Cards(unittest.TestCase):
    def test_the_plane_table_matches_the_words(self):
        tj = tools_json()
        new = tj["sketch_new"]["description"]
        for name, (x, y, n) in PLANES.items():
            self.assertIn(f"{name}: {orient.axis_word(x)}, {orient.axis_word(y)}, {orient.axis_word(n)}.", new)
        for words in ("A pad grows along the normal, and a pocket or a hole cuts against it.", "XZ with offset 15 is at y -15.",
                      "not the face centre", "On a standing face, y runs up +Z.", "up: x | y | z", "axes: the frame in words.", "picked:"):
            self.assertIn(words, new)
        self.assertEqual(tj["sketch_new"]["inputSchema"]["properties"]["up"]["enum"], ["x", "y", "z"])

    def test_the_guide_line_is_true(self):
        with open(os.path.join(ROOT, "agentlink", "guides", "sketch.md"), encoding="utf-8") as f:
            g = f.read()
        self.assertNotIn("On this face the sketch x/y are the world x/y.", g)
        self.assertIn("On a +z face the sketch x/y are the world x/y.", g)

    def test_axes_on_every_answer_that_makes_or_moves_a_sketch(self):
        tj = tools_json()
        for name in ("sketch_new", "sketch_attach", "sketch_mirror", "sketch_merge", "sketch_state"):
            self.assertIn("=axes(sk.Placement)", json.dumps(tj[name]), name)

    def test_view_names_in_words_follow_the_camera(self):
        from agentlink import render

        eye = {k: v[0] for k, v in render.VIEWS.items()}
        self.assertEqual((eye["front"], render.VIEWS["front"][1]), ((0, -1, 0), (0, 0, 1)))
        self.assertEqual((eye["top"], render.VIEWS["top"][1]), ((0, 0, 1), (0, 1, 0)))
        self.assertEqual(eye["right"], (1, 0, 0))
        self.assertEqual(eye["iso"], (1, -1, 1))
        with open(os.path.join(ROOT, "agentlink", "families", "view.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("front looks from -Y toward +Y (it shows the -Y side), with Z up. top looks down -Z, with +Y up the screen.", src)
        tj = tools_json()
        for name in ("view_snapshot", "steps_render", "td_view"):
            self.assertIn("front looks from -Y", tj[name]["description"], name)


class NeverSaidBefore(unittest.TestCase):
    def test_axes_stays_and_the_note_goes(self):
        import types

        from agentlink import once, runners

        t = runners.tool("sketch_new", runners.entries()["sketch_new"], {})
        s = types.SimpleNamespace()
        note = "Coordinates are the sketch's: x along xAxis, y along yAxis, from origin (world mm)."
        a = orient.axes_line(fr(*PLANES["XY"]))
        first = once.thin_reply(s, t, {"sketch": "Sketch", "axes": a, "note": note})
        second = once.thin_reply(s, t, {"sketch": "Sketch001", "axes": a, "note": note})
        self.assertEqual(first["axes"], a)
        self.assertEqual(second["axes"], a)
        self.assertNotIn("note", second)


# ---- the placements: face_frame and up_frame on a stand-in FreeCAD with real rotations -----------

CHILD = '''
import json, math, sys
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()

class Vec:
    def __init__(s, x=0.0, y=0.0, z=0.0):
        if isinstance(x, Vec): x, y, z = x.x, x.y, x.z
        s.x, s.y, s.z = float(x), float(y), float(z)
    def __add__(s, o): return Vec(s.x + o.x, s.y + o.y, s.z + o.z)
    def __sub__(s, o): return Vec(s.x - o.x, s.y - o.y, s.z - o.z)
    def __mul__(s, k): return Vec(s.x * k, s.y * k, s.z * k)
    __rmul__ = __mul__
    def __neg__(s): return s * -1
    def dot(s, o): return s.x * o.x + s.y * o.y + s.z * o.z
    def __iter__(s): return iter((s.x, s.y, s.z))
    def __getitem__(s, i): return (s.x, s.y, s.z)[i]

class Rot:
    def __init__(s, *a):
        s.c = [list(a[0]), list(a[1]), list(a[2])] if len(a) == 4 else [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    def multVec(s, v):
        return Vec(*[s.c[0][i] * v.x + s.c[1][i] * v.y + s.c[2][i] * v.z for i in range(3)])
    def multiply(s, o):
        r = Rot(); r.c = [list(s.multVec(Vec(*col))) for col in o.c]; return r
    def inverted(s):
        r = Rot(); r.c = [[s.c[j][i] for j in range(3)] for i in range(3)]; return r

class Pl:
    def __init__(s, base=None, rot=None):
        s.Base, s.Rotation = Vec(*(base or (0, 0, 0))), rot or Rot()
    def multVec(s, v): return s.Rotation.multVec(v) + s.Base
    def multiply(s, o): return Pl(s.Base + s.Rotation.multVec(o.Base), s.Rotation.multiply(o.Rotation))
    def inverse(s):
        r = s.Rotation.inverted(); return Pl(-r.multVec(s.Base), r)

fc.fc.Vector, fc.fc.Rotation, fc.fc.Placement = Vec, Rot, Pl
from agentlink.families import sketch
sketch.V = Vec
from agentlink.protocol import ToolError

def world(P, AO):
    W = P.multiply(AO)
    f = sketch.frame(W)
    return {"frame": f, "axes": sketch.axes(W), "on": sketch.on_words("the face +y at y 15", W)}

out = {}
# the +y face of a part: the attacher's own x is any axis in the face (here +Z), its origin the face centre
P = Pl((3, 15, 2.5), Rot(Vec(0, 0, 1), Vec(1, 0, 0), Vec(0, 1, 0), "ZXY"))
out["+y"] = world(P, sketch.face_frame(P))
out["+y up x"] = world(P, sketch.face_frame(P, "x"))
# the XZ plane as FreeCAD 1.1 attaches a sketch to it, turned with up x
Q = Pl((0, 0, 0), Rot(Vec(1, 0, 0), Vec(0, 0, 1), Vec(0, -1, 0), "ZXY"))
out["XZ up x"] = world(Q, sketch.up_frame(Q, "x"))
try:
    sketch.up_frame(Pl(), "z")
except ToolError as e:
    out["XY up z"] = [e.code, e.message]
print(json.dumps(out))
''' % (ROOT, HERE)


def child():
    r = subprocess.run([sys.executable, "-c", CHILD], capture_output=True, text=True, timeout=120, cwd=HERE)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class Placements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.got = child()

    def test_a_plus_y_face_has_y_up_and_its_origin_off_the_centre(self):
        g = self.got["+y"]
        self.assertEqual(g["frame"], {"origin": [0.0, 15.0, 0.0], "xAxis": [-1.0, 0.0, 0.0], "yAxis": [0.0, 0.0, 1.0], "normal": [0.0, 1.0, 0.0]})
        self.assertEqual(g["axes"], "x runs -X; y runs +Z (up); the normal points +Y: a pad grows toward +Y, a pocket or hole cuts toward -Y. "
                                    "[0, 0] is at world (0, 15, 0).")
        # 27 Nov QA (F10): the face by its side (sketch.face_said), not by its centre
        self.assertEqual(g["on"], "the face +y at y 15; sketch origin at [0, 15, 0]")

    def test_up_x_on_the_face(self):
        f = self.got["+y up x"]["frame"]
        self.assertEqual((f["xAxis"], f["yAxis"], f["normal"]), ([0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]))

    def test_up_x_on_xz_keeps_the_origin_and_the_normal(self):
        f = self.got["XZ up x"]["frame"]
        self.assertEqual(f, {"origin": [0.0, 0.0, 0.0], "xAxis": [0.0, 0.0, -1.0], "yAxis": [1.0, 0.0, 0.0], "normal": [0.0, -1.0, 0.0]})
        self.assertIn("x runs -Z (down); y runs +X", self.got["XZ up x"]["axes"])

    def test_up_along_the_normal_refused(self):
        code, msg = self.got["XY up z"]
        self.assertEqual(code, "invalid_input")
        self.assertTrue(msg.endswith("Nothing was made."), msg)


if __name__ == "__main__":
    unittest.main()

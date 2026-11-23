# SPDX-License-Identifier: LGPL-2.1-or-later
"""22 Nov (owner-approved): semantic face selectors with a cardinality check.
face: { side: "+z", of, largest } must match exactly one face, else the call
is refused with the faces there and the selector that picks each. Plain
Python over stand-in face descriptions; no FreeCAD."""
import math
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import facesel  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402


def face(center, normal, area, kind="plane", owners=("Body",), at=None):
    d = {"center": list(center), "normal": list(normal) if normal is not None else None, "area": area, "type": kind, "owners": set(owners)}
    if at is not None:
        d["at"] = list(at)
    return d


def block():
    """A 40x20x10 block (Pad) with a 10x10x10 boss on top (Pad001) and a
    hole through the boss (a cylinder)."""
    base, boss = ("Body", "Pad"), ("Body", "Pad001")  # the faces each one made
    return [
        face((20, 10, 10), (0, 0, 1), 700, owners=base, at=(5, 5, 10)),   # 0 top of the block, round the boss
        face((15, 10, 20), (0, 0, 1), 100, owners=boss),                   # 1 top of the boss
        face((20, 10, 0), (0, 0, -1), 800, owners=base),                   # 2 bottom
        face((0, 10, 5), (-1, 0, 0), 200, owners=base),                    # 3 block -x
        face((40, 10, 5), (1, 0, 0), 200, owners=base),                    # 4 block +x
        face((20, 0, 5), (0, -1, 0), 400, owners=base),                    # 5 block -y
        face((20, 20, 5), (0, 1, 0), 400, owners=base),                    # 6 block +y
        face((10, 10, 15), (-1, 0, 0), 100, owners=boss),                  # 7 boss -x
        face((20, 10, 15), (1, 0, 0), 100, owners=boss),                   # 8 boss +x
        face((15, 5, 15), (0, -1, 0), 100, owners=boss),                   # 9 boss -y
        face((15, 15, 15), (0, 1, 0), 100, owners=boss),                   # 10 boss +y
        face((15, 10, 15), (1, 0, 0), 62.83, kind="cylinder", owners=boss, at=(17, 10, 15)),  # 11 the hole
    ]


def refused(test, faces, q):
    with test.assertRaises(ToolError) as e:
        facesel.select(faces, q)
    return e.exception


class Sides(unittest.TestCase):
    def test_each_side(self):
        f = block()
        want = {"+z": 1, "-z": 2, "+x": 4, "-x": 3, "+y": 6, "-y": 5}
        for side, i in want.items():
            self.assertEqual(facesel.select(f, {"side": side}), i, side)

    def test_sign_case_is_read(self):
        self.assertEqual(facesel.select(block(), {"side": "+Z"}), 1)

    def test_no_sign_or_a_word_refused(self):
        for s in ("z", "top", "up", 3):
            e = refused(self, block(), {"side": s})
            self.assertEqual(e.code, "invalid_input")
            self.assertIn("+x, -x, +y, -y, +z, -z", e.message)

    def test_cylinder_is_never_a_side(self):
        # the hole's normal points +x at its point, but it is not a flat face
        hits, _ = facesel.matches(block(), {"side": "+x", "of": "Pad001"})
        self.assertEqual(hits, [8])

    def test_unknown_field_and_largest_alone_refused(self):
        self.assertIn("face.top", refused(self, block(), {"side": "+z", "top": True}).message)
        self.assertIn("give side", refused(self, block(), {"largest": True}).message)


class Of(unittest.TestCase):
    def test_of_feature_filters(self):
        f = block()
        self.assertEqual(facesel.select(f, {"side": "+z", "of": "Pad"}), 0)
        self.assertEqual(facesel.select(f, {"side": "+x", "of": "Pad001"}), 8)
        self.assertEqual(facesel.select(f, {"side": "+z", "of": "Body"}), 1)

    def test_of_nothing_refused_with_the_list(self):
        e = refused(self, block(), {"side": "+z", "of": "Pocket"})
        self.assertEqual(e.code, "not_found")
        self.assertIn('No face matches { side: "+z", of: "Pocket" }', e.message)
        self.assertIn('"pick"', e.message)

    def owned(self, faces, theirs):
        return {i for i, j in facesel.owner_pairs(faces, theirs) if facesel.same_whole(faces[i], theirs[j])}

    def test_owner_pairs_whole_face(self):
        f = [face((0, 0, 1), (0, 0, 1), 4, owners=()), face((0, 0, 0), (0, 0, -1), 4, owners=())]
        theirs = [{"center": [0, 0, 1.00001], "normal": [0, 0, 1], "area": 4.0, "type": "plane"}]
        new = facesel.with_owner(f, self.owned(f, theirs), "Pad")
        self.assertEqual((new[0]["owners"], new[1]["owners"]), ({"Pad"}, set()))
        self.assertEqual(f[0]["owners"], set())  # the input is left as it was

    def test_pocket_faces_face_the_other_way(self):
        floor = [face((0, 0, 5), (0, 0, 1), 4, owners=())]  # the pocket's floor faces up
        tool = [{"center": [0, 0, 5], "normal": [0, 0, -1], "area": 4.0, "type": "plane"}]  # the cut's bottom faces down
        self.assertEqual(self.owned(floor, tool), {0})

    def test_pairs_only_in_the_plane(self):
        f = [face((0, 0, 10), (0, 0, 1), 700, owners=()), face((0, 0, 20), (0, 0, 1), 100, owners=()),
             face((0, 0, 10), (1, 0, 0), 700, owners=())]
        theirs = [{"center": [0, 0, 10], "normal": [0, 0, 1], "area": 800.0, "type": "plane"}]
        self.assertEqual(facesel.owner_pairs(f, theirs), [(0, 0)])  # z 20 is not in their plane; +x is across it


class Largest(unittest.TestCase):
    def test_largest_takes_area_not_distance(self):
        self.assertEqual(facesel.select(block(), {"side": "+z", "largest": True}), 0)

    def test_largest_tie_refused(self):
        # +x faces: the block's 200 mm² and the boss's 100 mm²: one largest
        self.assertEqual(facesel.select(block(), {"side": "+x", "largest": True}), 4)
        f2 = [face((0, 0, 5), (0, 0, 1), 50), face((9, 0, 2), (0, 0, 1), 50)]
        e = refused(self, f2, {"side": "+z", "largest": True})
        self.assertIn("2 faces match", e.message)


class Ties(unittest.TestCase):
    def two_bosses(self):
        f = block()
        f.append(face((30, 10, 20), (0, 0, 1), 64, owners=("Body", "Pad002")))
        return f

    def test_tie_refused_with_the_list(self):
        f = self.two_bosses()
        e = refused(self, f, {"side": "+z"})
        self.assertEqual(e.code, "invalid_input")
        self.assertTrue(e.message.startswith('2 faces match { side: "+z" }'), e.message)
        self.assertIn("copy a pick", e.message)
        items = facesel.listing(f, {"side": "+z"}, facesel.matches(f, {"side": "+z"})[0])
        self.assertEqual([it["center"] for it in items[:2]], [[15.0, 10.0, 20.0], [30.0, 10.0, 20.0]])
        self.assertEqual(len(items), facesel.LIST)

    def test_within_a_micron_is_a_tie_and_past_it_is_not(self):
        f = [face((0, 0, 5), (0, 0, 1), 10), face((9, 0, 5 + 5e-7), (0, 0, 1), 20)]
        self.assertIn("2 faces match", refused(self, f, {"side": "+z"}).message)
        f[1]["center"][2] = 5.001
        self.assertEqual(facesel.select(f, {"side": "+z"}), 1)

    def test_of_breaks_the_tie(self):
        self.assertEqual(facesel.select(self.two_bosses(), {"side": "+z", "of": "Pad002"}), 12)


class Picks(unittest.TestCase):
    def test_every_listed_pick_picks_its_face(self):
        f = Ties().two_bosses()
        for q in ({"side": "+z"}, {"side": "-y", "of": "Nope"}):
            hits, _ = facesel.matches(f, q)
            for it in facesel.listing(f, q, hits):
                p = it["pick"]
                if "side" in p:
                    got, _ = facesel.matches(f, p)
                    self.assertEqual(len(got), 1, p)
                    self.assertEqual(f[got[0]]["center"], it["center"])
                else:
                    self.assertEqual(set(p), {"at", "normal"})

    def test_entry_shape(self):
        f = block()
        it = facesel.entry(f, 1)
        self.assertEqual(it, {"side": "+z", "center": [15.0, 10.0, 20.0], "normal": [0.0, 0.0, 1.0], "area": 100.0, "type": "plane", "pick": {"side": "+z"}})
        cyl = facesel.entry(f, 11)
        self.assertNotIn("side", cyl)
        self.assertEqual(cyl["type"], "cylinder")
        self.assertEqual(cyl["pick"], {"at": [17.0, 10.0, 15.0], "normal": [1.0, 0.0, 0.0]})

    def test_copyable_prefers_side_then_largest_then_at(self):
        f = Ties().two_bosses()
        self.assertEqual(facesel.copyable(f, 2), {"side": "-z"})
        self.assertEqual(facesel.copyable(f, 0), {"side": "+z", "largest": True})
        self.assertEqual(facesel.copyable(f, 12, {"side": "+z", "of": "Pad002"}), {"side": "+z", "of": "Pad002"})
        self.assertEqual(facesel.copyable(f, 1), {"at": [15.0, 10.0, 20.0], "normal": [0.0, 0.0, 1.0]})

    def test_the_list_is_capped(self):
        f = [face((i, 0, 0), (0, 0, 1), 1 + i) for i in range(20)]
        e = refused(self, f, {"side": "-z"})
        self.assertIn("(12 more not shown)", e.message)

    def test_normal_off_axis_has_no_side(self):
        s = math.sqrt(0.5)
        self.assertIsNone(facesel.side_word([s, 0, s]))
        self.assertEqual(facesel.side_word([0, 0, -3]), "-z")
        self.assertIsNone(facesel.side_word(None))


class Forms(unittest.TestCase):
    def test_at_normal_is_not_a_selector(self):
        self.assertFalse(facesel.is_selector({"at": [0, 0, 10], "normal": [0, 0, 1]}))
        self.assertFalse(facesel.is_selector({"at": [0, 0, 10], "side": "+z"}))
        self.assertFalse(facesel.is_selector("Face6"))
        self.assertTrue(facesel.is_selector({"side": "+z"}))
        self.assertTrue(facesel.is_selector({"largest": True}))


# ---- the glue in pd_common, on FreeCAD stand-ins -------------------------------------------

class Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __sub__(self, o):
        return Vec(self.x - o.x, self.y - o.y, self.z - o.z)

    def dot(self, o):
        return self.x * o.x + self.y * o.y + self.z * o.z

    @property
    def Length(self):
        return math.sqrt(self.dot(self))


class Plane:
    """Part.Plane's stand-in: a class named Plane."""

    def __init__(self, f):
        self.f = f

    def parameter(self, p):
        return (0.0, 0.0)


class Rect:
    """An axis-aligned flat face: lo/hi corners, outward normal."""

    def __init__(self, lo, hi, n):
        self.lo, self.hi, self.n = lo, hi, Vec(*n)
        self.Surface = Plane(self)
        self.CenterOfMass = Vec(*[(a + b) / 2 for a, b in zip(lo, hi)])
        sides = sorted(b - a for a, b in zip(lo, hi))
        self.Area = sides[1] * sides[2]

    def distToShape(self, v):
        q = [min(max(c, a), b) for c, a, b in zip((v.x, v.y, v.z), self.lo, self.hi)]
        p = Vec(*q)
        return (p - v).Length, [(p, v)], None

    def normalAt(self, u, v):
        return self.n


class Ident:
    """A placement that is the identity."""
    Rotation = types.SimpleNamespace(multVec=lambda v: v)

    def __mul__(self, o):
        return self

    def inverse(self):
        return self

    def multVec(self, v):
        return v


class Box:
    Solids = [1]
    Placement = Ident()

    def isNull(self):
        return False

    def __init__(self, a, b):
        (x0, y0, z0), (x1, y1, z1) = a, b
        self.Faces = [Rect((x0, y0, z1), (x1, y1, z1), (0, 0, 1)), Rect((x0, y0, z0), (x1, y1, z0), (0, 0, -1)),
                      Rect((x1, y0, z0), (x1, y1, z1), (1, 0, 0)), Rect((x0, y0, z0), (x0, y1, z1), (-1, 0, 0)),
                      Rect((x0, y1, z0), (x1, y1, z1), (0, 1, 0)), Rect((x0, y0, z0), (x1, y0, z1), (0, -1, 0))]


class Glue(unittest.TestCase):
    def setUp(self):
        fc = types.ModuleType("FreeCAD")
        fc.Vector = Vec
        fc.ActiveDocument = None
        part = types.ModuleType("Part")
        part.Vertex = lambda p: p
        names = ("FreeCAD", "Part")
        self._old = {n: sys.modules.get(n) for n in names}
        for n, m in (("FreeCAD", fc), ("Part", part)):
            sys.modules.setdefault(n, m)
        self.addCleanup(self.restore)
        try:
            from agentlink.families import pd_common
        except ImportError as e:
            self.skipTest(f"needs FreeCAD: {e}")
        self.pc = pd_common
        # The module may come from another test's stand-ins: these, for this test only.
        self._globals = {k: getattr(pd_common, k) for k in ("FreeCAD", "Part", "vec3")}
        pd_common.FreeCAD, pd_common.Part, pd_common.vec3 = fc, part, (lambda v, what: Vec(*v))
        self.shape = Box((0, 0, 0), (40, 20, 10))

    def restore(self):
        for k, v in getattr(self, "_globals", {}).items():
            setattr(self.pc, k, v)
        for n, m in self._old.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m

    def test_descs_and_side(self):
        d = self.pc.face_descs(self.shape)
        self.assertEqual([x["type"] for x in d], ["plane"] * 6)
        self.assertEqual(d[0]["area"], 800)
        i, f = self.pc.find_face(self.shape, {"side": "+z"})
        self.assertEqual(i, 0)
        self.assertIs(f, self.shape.Faces[0])
        self.assertEqual(self.pc.find_face(self.shape, {"side": "-x"})[0], 3)

    def test_at_normal_untouched(self):
        self.assertEqual(self.pc.find_face(self.shape, {"at": [40, 5, 5], "normal": [1, 0, 0]})[0], 2)
        self.assertEqual(self.pc.find_face(self.shape, {"at": [5, 5, 0]})[0], 1)

    def test_text_refused_as_before(self):
        for q in ("Face6", "Pad1", {"normal": [0, 0, 1]}):
            with self.assertRaises(self.pc.ToolError) as e:
                self.pc.find_face(self.shape, q)
            self.assertEqual(e.exception.code, "invalid_input")
            self.assertIn("not its index or name", e.exception.message)
            self.assertIn('side: +z', e.exception.message)

    def test_answer_gives_the_form_to_copy(self):
        body = types.SimpleNamespace(Tip=types.SimpleNamespace(Shape=self.shape), Label="Body")
        self.assertEqual(self.pc.face_pick(body, {"at": [5, 5, 10], "normal": [0, 0, 1]}), {"side": "+z"})
        self.assertEqual(self.pc.face_pick(body, {"side": "-y"}), {"side": "-y"})

    def test_of_a_feature_takes_the_faces_it_made(self):
        boss = Box((10, 5, 10), (20, 15, 20))
        shape = Box((0, 0, 0), (40, 20, 10))
        shape.Faces = shape.Faces + [f for f in boss.Faces if f.n.z != -1]
        feat = types.SimpleNamespace(Label="Pad001", Name="Pad001", TypeId="PartDesign::Pad", AddSubShape=boss)
        body = types.SimpleNamespace(Label="Body", Name="Body", Group=[feat])
        self.assertEqual(self.pc.find_face(shape, {"side": "+x"}, body=body)[0], 2)
        self.assertEqual(self.pc.find_face(shape, {"side": "+x", "of": "Pad001"}, body=body)[0], 7)
        with self.assertRaises(self.pc.ToolError) as e:
            self.pc.find_face(shape, {"side": "+x", "of": "Pad009"}, body=body)
        self.assertIn("Pad001", e.exception.message)  # the features there

    def test_of_the_body_names_keeps_all(self):
        self.assertEqual(self.pc.find_face(self.shape, {"side": "+y", "of": "Body"}, names=("Body", "Body"))[0], 4)


if __name__ == "__main__":
    unittest.main()

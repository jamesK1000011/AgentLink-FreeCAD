# SPDX-License-Identifier: LGPL-2.1-or-later
# A note pinned on a face keeps to that face when a later step renumbers the
# faces (a hole made the top Face5 where it was Face6): found by FreeCAD
# 1.x's mapped name, else by its point and normal, and flagged as lost —
# never moved to a guess — when neither finds it. In a separate Python with
# stand-in FreeCAD modules and stand-in geometry.
import os
import subprocess
import sys
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = textwrap.dedent("""
    import sys, types
    sys.path.insert(0, ROOT)
    fc = types.ModuleType("FreeCAD")
    fc.Vector = lambda *a: a
    fc.GuiUp = False
    fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d)
    sys.modules["FreeCAD"] = fc
    sys.modules["Part"] = types.ModuleType("Part")
    from agentlink.families import notes as N

    class Face:
        # a flat face: z = level, facing up or down (hole: a round gap at the middle)
        def __init__(self, z, up=True, hole=0):
            self.z, self.up, self.hole = z, up, hole

    class Side:
        # a wall at x, facing +X
        def __init__(self, x):
            self.x, self.up, self.z = x, None, None

    class Shape:
        def __init__(self, faces, maps=None, volume=1000.0):
            self.F = faces  # [(name, Face)]
            self.Faces = [f for _, f in faces]
            self.Volume, self.Area = volume, 600.0
            if maps is not None:  # indexed -> mapped (toponaming)
                self.ElementReverseMap = dict(maps)
                self.ElementMap = {v: k for k, v in maps.items()}
        def getElement(self, name):
            return dict(self.F)[name]

    class G:
        @staticmethod
        def face(shape, name):
            return dict(shape.F).get(name)
        @staticmethod
        def faces(shape):
            return list(shape.F)
        @staticmethod
        def dist(f, p):
            return abs(p[2] - f.z), [p[0], p[1], f.z]
        @staticmethod
        def project(f, p):
            if isinstance(f, Side):
                return abs(p[0] - f.x), [f.x, p[1], p[2]]
            if f.hole and (p[0] ** 2 + p[1] ** 2) ** 0.5 < f.hole:
                return None  # lands in the hole: off the face
            return abs(p[2] - f.z), [p[0], p[1], f.z]
        @staticmethod
        def size(shape):
            return 0.0
        @staticmethod
        def normal(f, p):
            if isinstance(f, Side):
                return [1, 0, 0]
            return [0, 0, 1 if f.up else -1]

    store = {}
    N.notes_of = lambda doc: store.setdefault("notes", {"next": 1, "notes": []})
    N.save_notes = lambda doc, data: store.__setitem__("notes", data)
    shapes = {}
    shape_of = lambda doc, label: shapes[label]

    # Pinned on the top (Face6) of a pad; FreeCAD 1.x names it PadTop.
    shapes["Body"] = Shape([("Face5", Face(0, up=False)), ("Face6", Face(20))], {"Face6": "PadTop;:H1", "Face5": "PadBottom;:H1"})
    n = {"id": 1, "body": "Body", "face": "Face6", "at": [5, 5, 20]}
    n["anchor"] = N.anchor(shapes["Body"], "Face6", n["at"], G)
    assert n["anchor"]["mapped"] == "PadTop;:H1" and n["anchor"]["normal"] == [0, 0, 1], n["anchor"]
    store["notes"] = {"next": 2, "notes": [n]}

    # A hole renumbers: the top is Face5 now, the bottom Face6 — by the mapped name.
    shapes["Body"] = Shape([("Face5", Face(20)), ("Face6", Face(0, up=False)), ("Face7", Face(10))], {"Face5": "PadTop;:H1", "Face6": "PadBottom;:H1"}, volume=900)
    assert N.follow(None, shape_of, G) == [1]
    assert n["face"] == "Face5" and "lost" not in n, n

    # No element map (an older FreeCAD): by its point and normal; the pad grew, the pin moves up with it.
    shapes["Body"] = Shape([("Face2", Face(0, up=False)), ("Face3", Face(20.3))], volume=950)
    n["anchor"].pop("mapped")
    assert N.follow(None, shape_of, G) == [1]
    assert n["face"] == "Face3" and n["at"] == [5, 5, 20.3], n

    # The face is gone (cut away): flagged, the face name left as it was.
    shapes["Body"] = Shape([("Face2", Face(0, up=False)), ("Face3", Face(8))], volume=500)
    n["anchor"].pop("mapped", None)
    assert N.follow(None, shape_of, G) == [1]
    assert n["face"] == "Face3" and "not found" in n["lost"], n
    # A downward face at the same height is not taken for it.
    shapes["Body"] = Shape([("Face2", Face(20.3, up=False))], volume=400)
    N.follow(None, shape_of, G)
    assert "lost" in n, n

    # Unchanged shape: nothing to do.
    shapes["Body"] = Shape([("Face3", Face(20.3))], volume=950)
    N.follow(None, shape_of, G)
    assert n["face"] == "Face3" and "lost" not in n
    assert N.follow(None, shape_of, G) == []
    # A note from before anchors (no mapped name, no normal), on the top
    # (Face6, z = 20) of a pad: a hole makes the top Face5 and a side Face6,
    # the pad goes 20 -> 22. Its first re-find follows it to the new top,
    # the pin moves up, and the mapped name is kept from then on.
    old = {"id": 2, "body": "Pad", "face": "Face6", "at": [-9.77, -5.21, 20.0]}
    store["notes"] = {"next": 3, "notes": [old]}
    shapes["Pad"] = Shape([("Face1", Side(21)), ("Face4", Face(0, up=False, hole=3)), ("Face5", Face(22, hole=3)), ("Face6", Side(-21))],
                          {"Face5": "PadTop;:H2", "Face4": "PadBottom;:H2"}, volume=8000)
    assert N.follow(None, shape_of, G) == [2]
    assert old["face"] == "Face5" and old["at"] == [-9.77, -5.21, 22.0] and "lost" not in old, old
    assert old["anchor"]["mapped"] == "PadTop;:H2" and old["anchor"]["normal"] == [0, 0, 1], old["anchor"]
    # Nothing near any more (cut down to 10): lost, not guessed.
    shapes["Pad"] = Shape([("Face1", Side(21)), ("Face2", Face(10, hole=3))], volume=4000)
    old["anchor"].pop("mapped")
    N.follow(None, shape_of, G)
    assert "lost" in old and old["face"] == "Face5", old
    print("OK")
""")


class NoteFaces(unittest.TestCase):
    def test_follows_renumbering_and_flags_what_is_gone(self):
        r = subprocess.run([sys.executable, "-c", f"ROOT = {ROOT!r}\n" + SCRIPT], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["OK"], r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

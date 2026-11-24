# SPDX-License-Identifier: LGPL-2.1-or-later
# A lost face in plain words (local fixes, 23 Nov, decision 5): FreeCAD's
# "AttachEngine3D: subshape not found Pad.Face3" becomes "Sketch 3 lost its
# face Pad.Face3 after the last change; attach it to a face again" in the
# health's verdict and errors, with a todo that names history_undo and
# sketch_attach with its real inputs. Nothing re-attaches by itself.
# sketch_new checks the face's feature before it binds a sketch to it, and
# its own refusal leads with plain words.
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import fusehint, health  # noqa: E402
from test_hubfix2 import in_a_process  # noqa: E402

RAW = "AttachEngine3D: subshape not found Pad.Face3"


class Doc:
    def __init__(self, name="D"):
        self.Name = name
        self.Objects = []

    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)


class Vec:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Rot:
    def __init__(self, n):
        self.n = n

    def multVec(self, _v):
        return Vec(*self.n)


class Obj:
    TypeId = "Part::Feature"

    def __init__(self, doc, name, label=None, error=None, type_id=None, normal=(0, 0, 1)):
        self.Document, self.Name, self.Label = doc, name, label or name
        self._error, self.State = error, []
        self.InList, self.InListRecursive, self.OutList = [], [], []
        if type_id:
            self.TypeId = type_id
        self.Placement = type("P", (), {"Rotation": Rot(normal)})()
        doc.Objects.append(self)

    def isValid(self):
        return self._error is None

    def getStatusString(self):
        return self._error or "Valid"


class Session:
    def __init__(self, doc):
        self.doc = doc


class T:
    name, group, changes = "pd_pad", "feature", True


def run(doc, change):
    s = Session(doc)
    m = health.mark(s)
    for o in change() or []:
        health._observer_note(o)
    return health.check(s, T, m)


class PlainWords(unittest.TestCase):
    def test_a_lost_face_of_a_sketch(self):
        d = Doc()
        Obj(d, "Pad", type_id="PartDesign::Pad")
        sk = Obj(d, "Sketch002", "Sketch 3", error=RAW, type_id="Sketcher::SketchObject")
        got = fusehint.lost_ref(sk, RAW)
        self.assertEqual(got["words"], "Sketch 3 lost its face Pad.Face3 after the last change; attach it to a face again")
        self.assertEqual(got["todo"], 'history_undo takes the last change back; or sketch_attach { sketch: "Sketch 3", '
                                      'face: { side: "+z", feature: "Pad" } } attaches it to a face again')
        self.assertEqual(got["element"], "Pad.Face3")

    def test_the_owner_by_its_label_and_a_slanted_sketch(self):
        d = Doc()
        Obj(d, "Pad001", "Pad 2", type_id="PartDesign::Pad")
        sk = Obj(d, "Sketch", error="x", type_id="Sketcher::SketchObject", normal=(0.6, 0, 0.8))
        got = fusehint.lost_ref(sk, "AttachEngine3D: subshape not found Pad001.Face12")
        self.assertIn("lost its face Pad 2.Face12", got["words"])
        self.assertIn('face: { at: [x, y, z], normal: [x, y, z] }', got["todo"])

    def test_a_reversed_sketch_and_a_lost_edge(self):
        d = Doc()
        sk = Obj(d, "Sketch", error="x", type_id="Sketcher::SketchObject")
        sk.MapReversed = True
        self.assertIn('side: "-z"', fusehint.lost_ref(sk, RAW)["todo"])
        got = fusehint.lost_ref(sk, "AttachEngine3D: subshape not found Pad.Edge7")
        self.assertEqual(got["words"], "Sketch lost its edge Pad.Edge7 after the last change; attach it to an edge again")
        self.assertIn('sketch_attach { sketch: "Sketch", edge: "Pad.Edge…" }', got["todo"])
        got = fusehint.lost_ref(sk, "missing element reference Binder010 ;Edge1;:H10f,E")
        self.assertIn("lost its edge Binder010.Edge1", got["words"])

    def test_not_a_sketch_and_other_words(self):
        d = Doc()
        dp = Obj(d, "DatumPlane", error="x", type_id="PartDesign::Plane")
        got = fusehint.lost_ref(dp, RAW)
        self.assertEqual(got["todo"], "history_undo takes the last change back; or attach DatumPlane to a face again")
        self.assertIsNone(fusehint.lost_ref(dp, "Pad: Result has multiple solids"))
        self.assertIsNone(fusehint.lost_ref(dp, None))
        self.assertEqual(fusehint.plain_error(dp, "Pad: Result has multiple solids"), "Pad: Result has multiple solids")
        self.assertEqual(fusehint.plain_error(dp, RAW), "DatumPlane lost its face Pad.Face3 after the last change; attach it to a face again")


class InTheHealth(unittest.TestCase):
    def test_verdict_errors_and_todo_in_plain_words(self):
        d = Doc()
        Obj(d, "Pad", type_id="PartDesign::Pad")

        def change():
            sk = Obj(d, "Sketch002", "Sketch 3", error=RAW, type_id="Sketcher::SketchObject")
            pocket = Obj(d, "Pocket", error="Pocket: Linked object is not valid", type_id="PartDesign::Pocket")
            return [sk, pocket]

        h = run(d, change)
        self.assertFalse(h["ok"])
        self.assertIn("2 objects failed to recompute: Sketch 3 lost its face Pad.Face3 after the last change; attach it to a face again; "
                      "Pocket (Pocket: Linked object is not valid)", h["verdict"])
        self.assertNotIn("AttachEngine3D", json.dumps(h))
        self.assertNotIn("subshape", json.dumps(h))
        self.assertEqual(h["errors"][0]["error"], "Sketch 3 lost its face Pad.Face3 after the last change; attach it to a face again")
        self.assertNotIn("plain", h["errors"][0])
        self.assertTrue(h["todo"].startswith('history_undo takes the last change back; or sketch_attach { sketch: "Sketch 3", '
                                             'face: { side: "+z", feature: "Pad" } } attaches it to a face again'), h["todo"])

    def test_an_old_lost_face_gives_no_new_todo(self):
        d = Doc()
        Obj(d, "Sketch", error=RAW, type_id="Sketcher::SketchObject")
        h = run(d, lambda: [Obj(d, "Box")])
        self.assertIn("still failing from before", h["verdict"])
        self.assertNotIn("sketch_attach", h.get("todo", ""))


# The sketch family's helpers on the stand-in FreeCAD.
PC = '''
    from agentlink.families import pd_common as pc
    from agentlink.protocol import ToolError
    class O:
        def __init__(self, name, type_id, valid=True, faces=3):
            self.Name = self.Label = name
            self.TypeId, self._valid, self.InList = type_id, valid, []
            self.Document = None
            n = faces
            class S:
                def getElement(self, sub):
                    if int(sub[4:]) > n:
                        raise ValueError(sub)
                    return object()
            self.Shape = S()
        def isValid(self):
            return self._valid
        def getStatusString(self):
            return "Valid" if self._valid else "AttachEngine3D: subshape not found Pad.Face3"
    class B:
        Label = Name = "Body"
        TypeId = "PartDesign::Body"
        def __init__(self, group):
            self.Group = group
        def hasObject(self, o):
            return o in self.Group
    def refuse(f):
        try:
            f()
        except ToolError as e:
            return [e.code, e.message]
        return None
'''


class SketchNewCheck(unittest.TestCase):
    def test_a_broken_or_missing_face_is_refused_before_binding(self):
        got = in_a_process(PC + '''
    pad, bad = O("Pad", "PartDesign::Pad"), O("Pad001", "PartDesign::Pad", valid=False)
    pad.Label, bad.Label = "Pad", "Pad 2"
    b = B([pad, bad])
    out = {}
    out["broken"] = refuse(lambda: pc.plane_ref(b, "Pad 2.Face1"))
    out["ok"] = pc.plane_ref(b, "Pad.Face3")[1]
    out["gone"] = refuse(lambda: pc.plane_ref(b, "Pad.Face9"))
    # the face query branch: its owner checked, then its face
    pc.tip_shape = lambda body, need=True: (bad, bad.Shape)
    pc.find_face = lambda shape, q, tol=0.5, body=None, names=(): (2, type("F", (), {"CenterOfMass": None})())
    pc.face_owner = lambda body, ref, tip, f: (bad, 2)
    out["dictBroken"] = refuse(lambda: pc.plane_ref(b, {"side": "+z"}))
    few = O("Pad002", "PartDesign::Pad", faces=2)
    few.Label = "Pad 3"
    pc.face_owner = lambda body, ref, tip, f: (few, 2)
    out["dictGone"] = refuse(lambda: pc.plane_ref(b, {"side": "+z"}))
    out["status"] = pc.status_words(type("S", (), {"Label": "Sketch 3", "Name": "Sketch002", "TypeId": "Sketcher::SketchObject",
                                                   "getStatusString": lambda self: "AttachEngine3D: subshape not found Pad.Face3"})())
    print(json.dumps(out))
''')
        self.assertEqual(got["broken"], ["invalid_state", "plane: Pad 2 is broken now (it failed to recompute). So its Face1 cannot hold a sketch. "
                                                          "Repair Pad 2 first, or use a plane: XY, XZ or YZ."])
        self.assertEqual(got["ok"], "Pad.Face3")
        self.assertEqual(got["gone"][0], "invalid_input")
        self.assertEqual(got["dictBroken"][0], "invalid_state")
        self.assertIn("Pad 2 is broken now", got["dictBroken"][1])
        self.assertEqual(got["dictGone"][0], "invalid_state")
        self.assertTrue(got["dictGone"][1].startswith("plane: Pad 3 has no Face3 now. Its faces changed. Find the face again: face: { side: +z }"),
                        got["dictGone"][1])
        self.assertEqual(got["status"], "Sketch 3 lost its face Pad.Face3 after the last change; attach it to a face again")

    def test_sketch_new_refusal_leads_with_plain_words(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            steps = json.load(f)["entries"]["sketch_new"]["steps"]
        r = next(s for s in steps if s.get("when") == "=not sk.isValid()")
        fmt = r["refuse"]["fmt"]
        self.assertTrue(fmt.startswith("The sketch would not attach to {what}. Nothing was made. A sketch needs a flat face or a plane"), fmt)
        self.assertTrue(fmt.endswith("FreeCAD said: {status_words(sk)}"), fmt)
        self.assertNotIn("getStatusString", fmt)
        # no automatic re-attach anywhere: the todo only names the tools
        self.assertNotIn("sketch_attach", json.dumps([s for s in steps if "do" in s]))


if __name__ == "__main__":
    unittest.main()

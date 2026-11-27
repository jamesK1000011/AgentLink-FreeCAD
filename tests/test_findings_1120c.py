# SPDX-License-Identifier: LGPL-2.1-or-later
# Bicycle test drive of 20 Nov (FreeCAD 1.1.3), the hub's findings 3, 5 and 6,
# without FreeCAD:
#   3  sketch_new takes an LCS's plane ("Rear LCS.XZ_Plane", the plane's own
#      name), a whole LCS (its XY plane), a Part::DatumPlane, and a
#      PartDesign::CoordinateSystem (no planes of its own: ObjectXY | XZ | YZ).
#      FreeCAD 1.1 attaches a sketch to an LCS plane with FlatFace (src/App/
#      Datums.h: the LCS keeps its planes in OriginFeatures, with a Role).
#      The answer's on names the plane used.
#   5  pd_gear on a plane (body plane, datum plane, LCS plane or LCS) with
#      at and rotate; the teeth kept on the profile (a sprocket, a plain
#      sketch: AgentLinkTeeth, AgentLinkPitch, AgentLinkKind; an involute
#      gear: its own NumberOfTeeth), named in stored; asm_joint kind chain
#      reads them, the chain pitch too.
#   6  sketch_add: a line with dims: true and a name gets <name>_length; a
#      kind with no size says so (dimsNote).
# The tools run on the data tests' stand-ins in a child process.
import json
import os
import subprocess
import sys
import textwrap
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)

PD = '''
import json, sys, tempfile
sys.path[:0] = [ROOT, TESTS]
import _datask2_standin
fc = _datask2_standin.install()
fc.patch()
from agentlink.protocol import ToolError
from agentlink.families import feature_more, sketch

def run(mod, s, name, args):
    t = next(t for t in mod.tools(s) if t.name == name)
    try:
        return ["ok", t.fn(json.loads(json.dumps(args)))]
    except ToolError as e:
        return ["refused", e.code, e.message]

def lcs(s, label, b=None, planes=True, type_="Part::LocalCoordinateSystem"):
    """A coordinate system as FreeCAD 1.1 makes it: its planes in OriginFeatures with a Role, labelled "XY-plane" …"""
    feats = []
    if planes:
        for r, l in (("XY_Plane", "XY-plane"), ("XZ_Plane", "XZ-plane"), ("YZ_Plane", "YZ-plane")):
            feats.append(s.doc.new("App::Plane", r, Role=r, Label=l))
    o = s.doc.new(type_, "LCS", Label=label, OriginFeatures=feats, kinds=("App::LocalCoordinateSystem",) if planes else ())
    if b is not None:
        b._place(o)
    return o

def frame():
    del fc.trace[:]
    fc.state["flags"] = {}
    s = fc.Session(tempfile.mkdtemp())
    b = fc.body(s)  # FreeCAD's names: the body's planes XY_Plane …, an LCS's XY_Plane001 …
    fc.settle(s)
    return s, b

def support(o):
    d = o.__dict__
    return [[t.Name, sub] for t, sub in d.get("AttachmentSupport") or d.get("Support") or []]
'''

ASM = '''
import json, sys, tempfile
sys.path[:0] = [ROOT, TESTS]
import _dataasm_standin
fc = _dataasm_standin.install()
from agentlink.protocol import ToolError
from agentlink.families import assembly as A
fc.fc.GuiUp = False
fc.fc.Version = lambda: ["1", "1", "3"]
fc.state["solves"] = 0
s = fc.Session(tempfile.mkdtemp())

def run(name, args):
    t = next(t for t in A.tools(s) if t.name == name)
    try:
        return ["ok", t.fn(json.loads(json.dumps(args)))]
    except ToolError as e:
        return ["refused", e.code, e.message]

a = fc.an_object("Assembly::AssemblyObject", "Assembly", "Assembly")
a.__dict__["Type"] = "Assembly"
jg = fc.into(a, fc.an_object("Assembly::JointGroup", "Joints"))
fc.a_part("Base", (0, 0, 0), (10, 10, 10), name="Base")
fc.a_part("Lid", (0, 0, 10), (10, 10, 12), name="Lid")
for p in ("Base", "Lid"):
    fc.into(a, fc.doc().getObject(p))
g = fc.into(jg, fc.an_object("App::FeaturePython", "GroundedJoint"))
g.__dict__["ObjectToGround"] = fc.doc().getObject("Base")
'''


def child(head, body):
    code = head.replace("ROOT, TESTS", f"{ROOT!r}, {TESTS!r}") + textwrap.dedent(body)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class SketchOnLcs(unittest.TestCase):
    """Finding 3."""

    def test_planes_of_an_lcs_a_whole_lcs_and_a_part_datum_plane(self):
        got = child(PD, '''
            out = {}
            s, b = frame()
            rear = lcs(s, "Rear LCS", b)
            seat = s.doc.new("Part::DatumPlane", "DatumPlane", Label="Seat plane", kinds=("App::Plane",))
            def made(label):
                sk = s.doc.getObjectsByLabel(label)[0]
                return {"support": support(sk), "mode": sk.__dict__.get("MapMode")}
            out["dotted"] = run(sketch, s, "sketch_new", {"plane": "Rear LCS.XZ_Plane", "name": "Stay"})
            out["dottedMade"] = made("Stay")
            out["label"] = run(sketch, s, "sketch_new", {"plane": "Rear LCS.YZ-plane", "name": "Side"})
            out["labelMade"] = made("Side")
            out["whole"] = run(sketch, s, "sketch_new", {"plane": "Rear LCS", "name": "Flat"})
            out["wholeMade"] = made("Flat")
            out["own"] = run(sketch, s, "sketch_new", {"plane": "XZ_Plane", "name": "Body XZ"})
            out["ownMade"] = made("Body XZ")
            out["byName"] = run(sketch, s, "sketch_new", {"plane": "XZ_Plane001", "name": "By name"})
            out["byNameMade"] = made("By name")
            out["part"] = run(sketch, s, "sketch_new", {"plane": "Seat plane", "name": "Seat", "offset": 2})
            out["partMade"] = made("Seat")
            # PartDesign's own coordinate system: no planes, ObjectXZ
            cs = lcs(s, "Old CS", b, planes=False, type_="PartDesign::CoordinateSystem")
            out["pdcs"] = run(sketch, s, "sketch_new", {"plane": "Old CS", "name": "On old"})
            from agentlink.families import pd_common as pc
            out["pdcsXZ"] = pc.plane_mode(*pc.plane_ref(b, "Old CS.XZ_Plane"))
            out["lcsXZ"] = pc.plane_mode(*pc.plane_ref(b, "Rear LCS.XZ_Plane"))
            out["pdcsMade"] = made("On old")
            out["nothing"] = run(sketch, s, "sketch_new", {"plane": "Nope"})
            out["noSystem"] = run(sketch, s, "sketch_new", {"plane": "Nope.XZ_Plane"})
            # two systems of one label: the name says which
            two = lcs(s, "Rear LCS", b)
            out["twoLabels"] = run(sketch, s, "sketch_new", {"plane": "Rear LCS.XZ_Plane"})
            out["byItsName"] = run(sketch, s, "sketch_new", {"plane": two.Name + ".XZ_Plane", "name": "Second"})
            out["secondMade"] = made("Second")
            out["xyLabel"] = run(sketch, s, "sketch_new", {"plane": "XY-plane", "name": "Still XY"})
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["dotted"][0], "ok", got["dotted"])
        self.assertEqual(got["dotted"][1]["on"], "Rear LCS.XZ_Plane")
        self.assertEqual(got["dottedMade"], {"support": [["XZ_Plane001", ""]], "mode": "FlatFace"})
        self.assertEqual(got["label"][1]["on"], "Rear LCS.YZ_Plane")
        self.assertEqual(got["labelMade"]["support"], [["YZ_Plane001", ""]])
        # a whole LCS: its XY plane, said
        self.assertEqual(got["whole"][1]["on"], "Rear LCS.XY_Plane")
        self.assertEqual(got["wholeMade"], {"support": [["XY_Plane001", ""]], "mode": "FlatFace"})
        # the body's own planes as before
        self.assertEqual(got["own"][1]["on"], "XZ")
        self.assertEqual(got["ownMade"]["support"], [["XZ_Plane", ""]])
        # an LCS plane by its own name: the LCS is named
        self.assertEqual(got["byName"][1]["on"], "Rear LCS.XZ_Plane")
        self.assertEqual(got["byNameMade"]["support"], [["XZ_Plane001", ""]])
        # a Part datum plane outside the body
        self.assertEqual(got["part"][0], "ok", got["part"])
        self.assertEqual(got["part"][1]["on"], "Seat plane (outside Body: a cross-reference)")
        self.assertEqual(got["partMade"], {"support": [["DatumPlane", ""]], "mode": "FlatFace"})
        self.assertEqual(got["part"][1]["offset"], 2.0)
        self.assertEqual(got["pdcs"][0], "ok", got["pdcs"])
        self.assertEqual(got["pdcsMade"], {"support": [["LCS001", ""]], "mode": "ObjectXY"})
        self.assertEqual(got["pdcs"][1]["on"], "Old CS.XY_Plane (Old CS has no planes: ObjectXY)")
        self.assertEqual(got["pdcsXZ"], "ObjectXZ")
        self.assertEqual(got["lcsXZ"], "FlatFace")
        self.assertEqual(got["nothing"][:2], ["refused", "not_found"])
        self.assertIn("there: XY, XZ, YZ", got["nothing"][2])
        self.assertIn("Rear LCS.XY_Plane", got["nothing"][2])
        self.assertIn("Seat plane", got["nothing"][2])
        self.assertEqual(got["noSystem"][:2], ["refused", "not_found"])
        self.assertIn("no coordinate system or body 'Nope'", got["noSystem"][2])
        self.assertEqual(got["twoLabels"][:2], ["refused", "invalid_input"])
        self.assertIn("2 objects are labelled 'Rear LCS' (LCS, LCS002) — give the name.", got["twoLabels"][2])
        self.assertEqual(got["byItsName"][1]["on"], "Rear LCS.XZ_Plane")
        self.assertEqual(got["secondMade"]["support"], [["XZ_Plane002", ""]])
        # "XY-plane" (FreeCAD 1.1's label of a plane) alone is the body's own XY
        self.assertEqual(got["xyLabel"][1]["on"], "XY")

    def test_the_card_says_it(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            d = json.load(f)["entries"]["sketch_new"]["description"]
        self.assertIn('An LCS plane is "LCS.XZ_Plane"; a whole LCS gives its XY plane.', d)


class GearOnAPlane(unittest.TestCase):
    """Finding 5: pd_gear's side."""

    def test_sprocket_on_an_lcs_plane_keeps_its_teeth(self):
        got = child(PD, '''
            out = {}
            s, b = frame()
            rear = lcs(s, "Rear LCS", b)
            out["r"] = run(feature_more, s, "pd_gear", {"kind": "sprocket", "teeth": 16, "pitch": 12.7, "bore": 10, "plane": "Rear LCS.XZ_Plane",
                                                       "at": [5, 0, 0], "rotate": {"axis": [0, 0, 1], "angle": 90}, "name": "Cog"})
            prof = s.doc.getObjectsByLabel("Cog profile")[0]
            hole = s.doc.getObjectsByLabel("Cog bore")[0]
            out["prof"] = {"support": support(prof), "mode": prof.__dict__.get("MapMode"), "teeth": prof.AgentLinkTeeth,
                           "pitch": str(prof.AgentLinkPitch), "kind": prof.AgentLinkKind, "at": [prof.AttachmentOffset.Base.x, prof.AttachmentOffset.Base.y]}
            out["hole"] = support(hole)
            s, b = frame()
            out["gear"] = run(feature_more, s, "pd_gear", {"teeth": 24, "plane": "YZ"})
            g = [o for o in s.doc.Objects if o.Label == "Gear 24T"][0]
            out["gearSupport"] = support(g)
            out["gearProps"] = [p for p in g.PropertiesList if p.startswith("AgentLink")]
            s, b = frame()
            n = len(s.doc.Objects)
            out["bad"] = run(feature_more, s, "pd_gear", {"kind": "sprocket", "plane": "Nope"})
            out["same"] = len(s.doc.Objects) == n
            print(json.dumps(out, default=str))
        ''')
        ok, r = got["r"]
        self.assertEqual(ok, "ok", got["r"])
        self.assertEqual(r["on"], "Rear LCS.XZ_Plane")
        self.assertEqual(r["stored"], {"teeth": "Cog profile.AgentLinkTeeth", "pitch": "Cog profile.AgentLinkPitch"})
        self.assertEqual(r["chainPitch"], 12.7)
        self.assertEqual(got["prof"]["support"], [["XZ_Plane001", ""]])
        self.assertEqual(got["prof"]["mode"], "FlatFace")
        self.assertEqual(got["prof"]["teeth"], 16)
        self.assertEqual(got["prof"]["pitch"], "12.7 mm")
        self.assertEqual(got["prof"]["kind"], "sprocket")
        self.assertEqual(got["prof"]["at"], [5.0, 0.0])
        self.assertEqual(got["hole"], [["XZ_Plane001", ""]])
        ok, g = got["gear"]
        self.assertEqual(ok, "ok", got["gear"])
        self.assertEqual(g["on"], "YZ")
        self.assertEqual(g["stored"], {"teeth": "Gear 24T.NumberOfTeeth", "module": "Gear 24T.Modules"})
        self.assertEqual(got["gearSupport"], [["YZ_Plane", ""]])
        self.assertEqual(got["gearProps"], [])
        self.assertEqual(got["bad"][:2], ["refused", "not_found"])
        self.assertTrue(got["same"])

    def test_the_card_says_it(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]["pd_gear"]
        self.assertIn("AgentLinkTeeth and AgentLinkPitch. asm_joint kind chain reads them.", e["description"])
        self.assertIn("plane", e["inputSchema"]["properties"])
        self.assertIn("rotate", e["inputSchema"]["properties"])


class ChainReadsPdGear(unittest.TestCase):
    """Finding 5: asm_joint's side reads what pd_gear keeps."""

    def test_teeth_and_pitch_from_pd_gear_profiles(self):
        got = child(ASM, '''
            for part, label, n in (("Base", "Chainring profile", 48), ("Lid", "Cog profile", 16)):
                sk = fc.an_object("Sketcher::SketchObject", "Sketch", label)
                sk.__dict__.update(AgentLinkTeeth=n, AgentLinkPitch=9.525, AgentLinkKind="sprocket")
                fc.doc().getObject(part).__dict__["Group"] = [sk]
            r = run("asm_joint", {"kind": "chain", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Face1"}})
            j = next(x for x in jg.Group if getattr(x, "JointType", None) == "Belt")
            given = run("asm_joint", {"kind": "chain", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Face1"}, "pitch": 12.7, "name": "Chain2"})
            j2 = [x for x in jg.Group if getattr(x, "JointType", None) == "Belt"][-1]
            print(json.dumps([r, j.Distance, given, j2.Distance]))
        ''')
        r, r1, given, r1given = got
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["ratio"], 3.0)
        self.assertEqual(r[1]["teeth"], [48, 16])
        self.assertIn("Chainring profile (AgentLinkTeeth)", r[1]["ratioFrom"])
        self.assertIn("pitch 9.525 mm read from the sprockets (AgentLinkPitch)", r[1]["ratioFrom"])
        self.assertAlmostEqual(r1, 48 * 9.525 / (2 * 3.141592653589793), places=6)
        # a pitch given wins
        self.assertEqual(given[0], "ok", given)
        self.assertAlmostEqual(r1given, 48 * 12.7 / (2 * 3.141592653589793), places=6)


class NamedLineDimension(unittest.TestCase):
    """Finding 6."""

    def test_a_named_line_gets_its_length(self):
        got = child(PD, '''
            s, b = frame()
            sk = fc.drawing(s, b, "Frame sketch")
            shapes = [{"kind": "line", "from": [0, 0], "to": [300, 400], "dims": True, "name": "seat"},
                      {"kind": "line", "from": [0, 0], "to": [0, 50], "dims": True},
                      {"kind": "line", "from": [0, 0], "to": [10, 0], "name": "plain"},
                      {"kind": "point", "at": [1, 1], "dims": True}]
            rs = [run(sketch, s, "sketch_add", {"sketch": "Frame sketch", **shape}) for shape in shapes]
            cons = [[c.Type, c.Name, c.Value] for c in sk.__dict__["Constraints"]]
            print(json.dumps([rs, cons], default=str))
        ''')
        rs, cons = got
        for r in rs:
            self.assertEqual(r[0], "ok", r)
        added = [r[1]["added"][0] for r in rs]  # one shape for each call (27 Nov)
        self.assertEqual(added[0]["dims"], {"seat_length": 0})
        self.assertEqual(added[1]["dims"], {"length": 1})
        self.assertNotIn("dims", added[2])  # no dims asked
        self.assertNotIn("dimsNote", added[2])
        self.assertEqual(added[3]["dimsNote"], "point: no size to dimension here; sketch_constrain adds one.")
        self.assertEqual(cons[0], ["Distance", "seat_length", 500.0])
        self.assertEqual(cons[1][0], "Distance")
        self.assertEqual(cons[1][2], 50.0)
        self.assertEqual(len(cons), 2)


if __name__ == "__main__":
    unittest.main()

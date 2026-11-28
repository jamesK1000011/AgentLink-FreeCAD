# SPDX-License-Identifier: LGPL-2.1-or-later
# The skeleton workflow of the design kickoff (20 Nov 2026), without FreeCAD:
# parameters -> a master sketch -> a SubShapeBinder in each part's Body ->
# datums (an LCS) attached to the binder's vertices and edges -> Assembly
# joints on them. What Agent Link adds for it:
#   pd_datum / part_datum refs: one to four references of any object, in
#     order, with a FreeCAD MapMode or the default for the combination
#     (one vertex: Translate; vertex + edge: OZX, the origin at the vertex
#     and Z along the edge — Attacher.cpp of FreeCAD 1.1);
#   offset { at, rotate }: the AttachmentOffset;
#   part_datum body | part: the Body or App::Part that holds the datum;
#   pd_datum kind lcs: Part::LocalCoordinateSystem (an
#     App::LocalCoordinateSystem: a Body takes it in 1.1, Assembly reads its
#     origin, axes and planes);
#   param_bind on a nested path ("LCS.AttachmentOffset.Base.x") answers the
#     value at that path;
#   show (and the session's body lookup): a hidden PartDesign Body by its
#     Label (Workshop finding 13).
# The default modes are plain Python (pd_common.default_mode); the tools run
# on the data tests' stand-in FreeCAD in a child process.
import json
import os
import subprocess
import sys
import textwrap
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)

MODES = ["Deactivated", "Translate", "ObjectXY", "ObjectXZ", "ObjectYZ", "FlatFace", "TangentPlane", "NormalToEdge", "FrenetNB", "FrenetTN",
         "FrenetTB", "Concentric", "SectionOfRevolution", "ThreePointsPlane", "ThreePointsNormal", "Folding", "ObjectX", "ObjectY", "ObjectZ",
         "AxisOfCurvature", "TwoPointLine", "IntersectionLine", "ObjectOrigin", "CenterOfCurvature", "CenterOfMass", "Vertex",
         "OZX", "OZY", "OXY", "OXZ", "OYZ", "OYX"]  # FreeCAD 1.1's eMapModeStrings (Attacher.cpp), the stand-in's datums share one list

SETUP = '''
import json, sys, tempfile
sys.path[:0] = [ROOT, TESTS]
import _datask2_standin
fc = _datask2_standin.install()
fc.patch()
from agentlink.protocol import ToolError
from agentlink.families import feature_more, param, app, part_more

V = fc.Vec
MODES = MODES_

class Curve:
    pass

class Line(Curve):
    pass

class Circle(Curve):
    pass

class El:
    def __init__(self, kind, curve=None):
        self.kind, self.Curve = kind, curve

class Sh:
    """A shape with its vertices, edges and faces by FreeCAD's names."""
    def __init__(self, v=0, e=(), f=0):
        self.Vertexes = [El("Vertex") for _ in range(v)]
        self.Edges = [El("Edge", c) for c in e]
        self.Faces = [El("Face") for _ in range(f)]
        self.Solids = []
    def isNull(self):
        return False
    def getElement(self, sub):
        for k, xs in (("Vertex", self.Vertexes), ("Edge", self.Edges), ("Face", self.Faces)):
            if sub.startswith(k):
                return xs[int(sub[len(k):]) - 1]

# A datum has the attacher's link and offset, as FreeCAD 1.1 gives them (AttachExtension); its MapMode is
# left out here: the stand-in checks an enumeration against its own short list.
DATUM_TYPES = ("Part::LocalCoordinateSystem", "Part::DatumPoint", "Part::DatumLine", "Part::DatumPlane", "PartDesign::CoordinateSystem",
               "PartDesign::Line", "PartDesign::Point")
first_doc_new = type(fc.Session().doc).new
def doc_new(self, type_, _name=None, **kw):
    o = first_doc_new(self, type_, _name, **kw)
    if type_ in DATUM_TYPES:
        o.__dict__.setdefault("AttachmentSupport", None)
        o.__dict__.setdefault("AttachmentOffset", fc.Placement())
    if type_ in ("Part::LocalCoordinateSystem", "PartDesign::CoordinateSystem"):
        o.__dict__.setdefault("kinds", ("App::LocalCoordinateSystem",))  # FreeCAD 1.1: both are an App::LocalCoordinateSystem
    return o
type(fc.Session().doc).new = doc_new

first_enums = fc.Obj.getEnumerationsOfProperty
fc.Obj.getEnumerationsOfProperty = lambda self, p: MODES if p == "MapMode" else first_enums(self, p)

def run(mod, s, name, args):
    t = next(t for t in mod.tools(s) if t.name == name)
    try:
        return ["ok", t.fn(json.loads(json.dumps(args)))]
    except ToolError as e:
        return ["refused", e.code, e.message]

def skeleton():
    """A Body with a binder of the master sketch (two points and a line: 2 vertices, a line and a circle edge), the
    master sketch "Skeleton" outside it, and a variable set."""
    del fc.trace[:]
    fc.state["flags"] = {}
    s = fc.Session(tempfile.mkdtemp())
    b = fc.body(s, "Frame")
    sk = s.doc.new("Sketcher::SketchObject", "Skeleton")
    sk.__dict__["Shape"] = Sh(v=2, e=[Line(), Circle()])
    bd = s.doc.new("PartDesign::SubShapeBinder", "Binder")
    bd.__dict__.update(Label="Skeleton binder", Shape=Sh(v=2, e=[Line(), Circle()]), Support=[(sk, ("",))])
    b._place(bd)
    fc.settle(s)
    return s, b, sk, bd

def support(o):
    d = o.__dict__
    return [[t.Label, sub] for t, sub in d.get("AttachmentSupport") or d.get("Support") or []]
'''


def _cw(entry):
    """Every word of a tools.json entry: its card and its inputs' meanings (agentlink.tooldata.card_words)."""
    from agentlink.tooldata import card_words
    return card_words(entry)


def child(body):
    code = SETUP.replace("ROOT, TESTS", f"{ROOT!r}, {TESTS!r}").replace("MODES_", repr(MODES)) + textwrap.dedent(body)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class DefaultModes(unittest.TestCase):
    """The default mode for a datum and its references (Attacher.cpp, FreeCAD 1.1: modeRefTypes)."""

    def test_modes(self):
        cases = [("lcs", "V"), ("lcs", "VE"), ("lcs", "EV"), ("csys", "VV"), ("csys", "EVV"), ("plane", "VC"), ("csys", "O"), ("csys", "C"),
                 ("line", "VV"), ("line", "C"), ("point", "V"), ("point", "VV"), ("csys", "KK"), ("line", "VE")]
        got = child(f"""
            from agentlink.families import pd_common as pc
            print(json.dumps([list(pc.default_mode(k, sig)) for k, sig in {cases!r}]))
        """)
        want = [["Translate", [0]], ["OZX", [0, 1]],
                ["OZX", [1, 0]],  # the origin vertex goes first
                ["OZX", [0, 1]], ["OZX", [1, 0, 2]], ["Concentric", [0, 1]], ["ObjectXY", [0]], ["Concentric", [0]],
                ["TwoPointLine", [0, 1]], ["AxisOfCurvature", [0]], ["Vertex", [0]], ["CenterOfMass", [0, 1]],
                [None, None],  # no plain choice: mode is asked for
                [None, None]]
        self.assertEqual(got, want)


class SkeletonTools(unittest.TestCase):
    def test_pd_datum_lcs_on_binder_vertex_and_edge(self):
        got = child('''
            out = {}
            s, b, sk, bd = skeleton()
            out["lcs"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Edge1", "Skeleton binder.Vertex1"],
                                                          "offset": {"at": [0, 0, 5]}, "name": "Seat LCS"})
            o = s.doc.getObjectsByLabel("Seat LCS")[0]
            out["type"], out["support"], out["mode"] = o.TypeId, support(o), o.__dict__.get("MapMode")
            out["offset"] = [o.AttachmentOffset.Base.x, o.AttachmentOffset.Base.y, o.AttachmentOffset.Base.z]
            out["inBody"] = o in b.__dict__["Group"]
            s, b, sk, bd = skeleton()
            out["one"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "point", "refs": ["Skeleton binder.Vertex2"]})
            out["sketch"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton"], "mode": "ObjectXY"})
            out["given"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Edge2"], "mode": "Concentric"})
            out["badmode"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Vertex1"], "mode": "Sideways"})
            out["nomode"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Edge2", "Skeleton binder.Edge1"]})
            out["noobj"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Nope.Vertex1"]})
            out["nosub"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Vertex9"]})
            out["bare"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Vertex1"]})
            out["both"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "line", "refs": ["Skeleton binder.Edge1"], "on": {"near": [0, 0, 0]}})
            out["offbad"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Vertex1"], "offset": 5})
            out["many"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Vertex1"] * 5})
            fc.state["flags"] = {"invalid_after": {"Bad": "Attachment failed"}}
            fc.trace.append("---- the call")
            out["fails"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Vertex1"], "name": "Bad"})
            # A FreeCAD with no Part::LocalCoordinateSystem: PartDesign's own coordinate system.
            s, b, sk, bd = skeleton()
            first_new = type(s.doc).new
            def no_part_lcs(self, type_, _name=None, **kw):
                if type_ == "Part::LocalCoordinateSystem":
                    raise TypeError("No document object type called Part::LocalCoordinateSystem")
                return first_new(self, type_, _name, **kw)
            type(s.doc).new = no_part_lcs
            out["fallback"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "at": [1, 2, 3]})
            out["fallbackType"] = s.doc.getObjectsByLabel("LCS")[0].TypeId
            def nothing(self, type_, _name=None, **kw):
                if type_ in ("Part::LocalCoordinateSystem", "PartDesign::CoordinateSystem"):
                    raise TypeError("No document object type called " + type_)
                return first_new(self, type_, _name, **kw)
            type(s.doc).new = nothing
            out["none"] = run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs"})
            type(s.doc).new = first_new
            print(json.dumps(out, default=str))
        ''')
        ok, a = got["lcs"]
        self.assertEqual(ok, "ok", got["lcs"])
        self.assertEqual(got["type"], "Part::LocalCoordinateSystem")
        self.assertTrue(got["inBody"])
        # The origin vertex first, then the edge: OZX (Z along the edge).
        self.assertEqual(got["support"], [["Skeleton binder", "Vertex1"], ["Skeleton binder", "Edge1"]])
        self.assertEqual(got["mode"], "OZX")
        self.assertEqual(got["offset"], [0.0, 0.0, 5.0])
        self.assertEqual(a["refs"], ["Skeleton binder.Vertex1", "Skeleton binder.Edge1"])
        self.assertEqual(a["mode"], "OZX")
        self.assertEqual(a["how"], "attached to Skeleton binder.Vertex1, Skeleton binder.Edge1 as OZX")
        self.assertEqual(a["offset"]["at"], [0.0, 0.0, 5.0])
        self.assertIn("world", a)
        self.assertEqual(a["type"], "Part::LocalCoordinateSystem")
        self.assertEqual(got["one"][1]["mode"], "Vertex")
        self.assertEqual(got["sketch"][1]["refs"], ["Skeleton"])
        self.assertEqual(got["sketch"][1]["mode"], "ObjectXY")
        self.assertEqual(got["given"][1]["mode"], "Concentric")
        self.assertEqual(got["badmode"][:2], ["refused", "invalid_input"])
        self.assertIn("OZX", got["badmode"][2])
        self.assertEqual(got["nomode"][:2], ["refused", "invalid_input"])
        self.assertIn("give mode", got["nomode"][2])
        self.assertEqual(got["noobj"][:2], ["refused", "not_found"])
        self.assertEqual(got["nosub"][:2], ["refused", "not_found"])
        self.assertEqual(got["bare"][:2], ["refused", "invalid_input"])
        self.assertEqual(got["both"], ["refused", "invalid_input", "refs or on, not both: on finds one round edge, refs names the references."])
        self.assertEqual(got["offbad"], ["refused", "invalid_input", "offset: { at: [x,y,z], rotate: { axis, angle } }."])
        self.assertEqual(got["many"][:2], ["refused", "invalid_input"])
        self.assertEqual(got["fails"][:2], ["refused", "failed"])
        self.assertIn("would not attach to Skeleton binder.Vertex1 as Translate: Attachment failed", got["fails"][2])
        self.assertEqual(got["fallback"][0], "ok", got["fallback"])
        self.assertEqual(got["fallbackType"], "PartDesign::CoordinateSystem")
        self.assertEqual(got["none"][:2], ["refused", "invalid_state"])
        self.assertIn("This FreeCAD makes no lcs datum in a body", got["none"][2])

    def test_part_datum_refs_offset_and_container(self):
        got = child('''
            out = {}
            s, b, sk, bd = skeleton()
            prt = s.doc.new("App::Part", "Part")
            prt.__dict__.update(Label="Frame part", Group=[])
            def add(o, g=prt):
                g.__dict__["Group"] = g.__dict__["Group"] + [o]
            prt.addObject = add
            out["csys"] = run(part_more, s, "part_datum", {"kind": "csys", "refs": ["Skeleton binder.Vertex2", "Skeleton binder.Edge1"], "body": "Frame",
                                                          "offset": {"at": [1, 0, 0], "rotate": {"axis": [0, 0, 1], "angle": 90}}, "name": "Joint frame"})
            o = s.doc.getObjectsByLabel("Joint frame")[0]
            out["support"], out["inBody"] = support(o), o in b.__dict__["Group"]
            out["plane"] = run(part_more, s, "part_datum", {"kind": "plane", "refs": ["Skeleton.Vertex1"], "part": "Frame part", "name": "P"})
            out["inPart"] = s.doc.getObjectsByLabel("P")[0] in prt.__dict__["Group"]
            out["both"] = run(part_more, s, "part_datum", {"kind": "csys", "refs": ["Skeleton.Vertex1"], "to": "Skeleton.Vertex1"})
            out["two"] = run(part_more, s, "part_datum", {"kind": "csys", "refs": ["Skeleton.Vertex1"], "body": "Frame", "part": "Frame part"})
            out["nopart"] = run(part_more, s, "part_datum", {"kind": "csys", "refs": ["Skeleton.Vertex1"], "part": "Nope"})
            out["offbad"] = run(part_more, s, "part_datum", {"kind": "csys", "refs": ["Skeleton.Vertex1"], "offset": [1, 2, 3]})
            fc.state["flags"] = {"invalid_after": {"Bad": "Attachment failed"}}
            fc.trace.append("---- the call")
            out["fails"] = run(part_more, s, "part_datum", {"kind": "csys", "refs": ["Skeleton.Vertex1"], "name": "Bad"})
            print(json.dumps(out, default=str))
        ''')
        ok, a = got["csys"]
        self.assertEqual(ok, "ok", got["csys"])
        self.assertEqual(got["support"], [["Skeleton binder", "Vertex2"], ["Skeleton binder", "Edge1"]])
        self.assertTrue(got["inBody"])
        self.assertEqual(a["mode"], "OZX")
        self.assertEqual(a["refs"], ["Skeleton binder.Vertex2", "Skeleton binder.Edge1"])
        self.assertEqual(a["in"], "Frame")
        self.assertEqual(a["offset"]["at"], [1.0, 0.0, 0.0])
        self.assertEqual(a["offset"]["angle"], 90.0)
        self.assertIn("world", a)
        self.assertEqual(got["plane"][0], "ok", got["plane"])
        self.assertEqual(got["plane"][1]["mode"], "Translate")
        self.assertTrue(got["inPart"])
        self.assertEqual(got["both"][:2], ["refused", "invalid_input"])
        self.assertEqual(got["two"], ["refused", "invalid_input", "body or part, not both: the datum goes in one container."])
        self.assertEqual(got["nopart"][:2], ["refused", "not_found"])
        self.assertEqual(got["offbad"][:2], ["refused", "invalid_input"])
        self.assertEqual(got["fails"][:2], ["refused", "failed"])

    def test_param_bind_a_nested_placement_path(self):
        got = child('''
            s, b, sk, bd = skeleton()
            fc.varset(s, "Dims", seat=("App::PropertyLength", (120, "mm")))
            run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Vertex1", "Skeleton binder.Edge1"], "name": "Seat LCS"})
            o = s.doc.getObjectsByLabel("Seat LCS")[0]
            o.AttachmentOffset.Base.x = 120.0  # what FreeCAD's expression engine leaves after the recompute
            r = run(param, s, "param_bind", {"target": "Seat LCS.AttachmentOffset.Base.x", "expression": "Dims.seat"})
            print(json.dumps({"r": r, "engine": o.__dict__.get("ExpressionEngine")}, default=str))
        ''')
        self.assertEqual(got["r"][0], "ok", got["r"])
        self.assertEqual(got["r"][1]["target"], "Seat LCS.AttachmentOffset.Base.x")
        self.assertEqual(got["r"][1]["value"], 120.0)  # read at the nested path (it was None)
        # On an LCS the variable set is written by its label: FreeCAD's parser reads <<Dims>> as an object of the
        # document only. "VarSet.seat" was looked up as a sub-object of the LCS too, and FreeCAD 1.1 logged
        # 'LocalCoordinateSystem ... doesn't contain feature with role "VarSet."' (live, 20 Nov).
        self.assertEqual(got["engine"], [["AttachmentOffset.Base.x", "<<Dims>>.seat"]])
        self.assertEqual(got["r"][1]["expression"], "<<Dims>>.seat")

    def test_param_bind_writes_other_objects_by_label_on_an_lcs_only(self):
        got = child('''
            s, b, sk, bd = skeleton()
            fc.varset(s, "Dims", seat=("App::PropertyLength", (120, "mm")), lift=("App::PropertyLength", (20, "mm")))
            run(feature_more, s, "pd_datum", {"body": "Frame", "kind": "lcs", "refs": ["Skeleton binder.Vertex1", "Skeleton binder.Edge1"], "name": "Seat LCS"})
            o = s.doc.getObjectsByLabel("Seat LCS")[0]
            o.AttachmentOffset.Base.z = 30.0
            r = run(param, s, "param_bind", {"target": "Seat LCS.AttachmentOffset.Base.z", "expression": "Dims.lift + VarSet.seat / 12"})
            pad = s.doc.new("PartDesign::Pad", "Pad")
            pad.__dict__["Length"] = 120.0
            r2 = run(param, s, "param_bind", {"target": "Pad.Length", "expression": "Dims.seat"})
            print(json.dumps({"r": r, "r2": r2, "lcs": o.__dict__.get("ExpressionEngine"), "pad": pad.__dict__.get("ExpressionEngine")}, default=str))
        ''')
        self.assertEqual(got["r"][0], "ok", got["r"])
        self.assertEqual(got["lcs"], [["AttachmentOffset.Base.z", "<<Dims>>.lift + <<Dims>>.seat / 12"]])
        # Not on an LCS: the object's name, as before (no sub-object lookup there).
        self.assertEqual(got["r2"][0], "ok", got["r2"])
        self.assertEqual(got["pad"], [["Length", "VarSet.seat"]])

    def test_labels_in_an_expression_pure(self):
        from agentlink import exprs

        labels = {"VarSet": "Dims", "Params": "Params", "Odd": "a>>b"}
        self.assertEqual(exprs.by_label("VarSet.lift", labels), ("<<Dims>>.lift", {"VarSet": "<<Dims>>"}))
        self.assertEqual(exprs.by_label("Params.width / 2 + VarSet.lift", labels)[0], "<<Params>>.width / 2 + <<Dims>>.lift")
        for same in ("<<Dims>>.lift", "lift", "Body.VarSet.x", "Doc#VarSet.lift", "'VarSet.lift'", "VarSet", "VarSet001.lift", "Odd.x", "2 * VarSet"):
            self.assertEqual(exprs.by_label(same, labels)[0], same, same)
        self.assertEqual(exprs.by_label("VarSet.lift", {}), ("VarSet.lift", {}))

    def test_show_and_body_find_a_hidden_body_by_its_label(self):
        got = child('''
            from agentlink.families import picks
            s, b, sk, bd = skeleton()
            ring = fc.body(s, "Chainring")
            ring.__dict__["Visibility"] = False
            tip = s.doc.new("PartDesign::Pad", "Pad")
            tip.__dict__["Label"] = "chainring"  # its tip feature's label differs in case only
            ring.__dict__["Tip"] = tip
            out = {"exact": picks.named(s.doc, "Chainring").Name, "case": picks.named(s.doc, "CHAINRING").Name,
                   "name": picks.named(s.doc, "Pad").Name, "none": picks.named(s.doc, "Nope")}
            objs, unknown = app.named_objects(s.doc, ["chainring", "Chainring", "Nope"])
            out["show"] = [[o.Name for o in objs], unknown]
            print(json.dumps(out))
        ''')
        self.assertEqual(got["exact"], "Chainring")
        self.assertEqual(got["case"], "Chainring")  # the Body before its tip
        self.assertEqual(got["name"], "Pad")
        self.assertIsNone(got["none"])
        # "chainring" is the tip's exact label; "Chainring" the Body's.
        self.assertEqual(got["show"], [["Pad", "Chainring"], ["Nope"]])

    def test_the_cards_say_it(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]
        for name in ("pd_datum", "part_datum"):
            d = _cw(e[name])
            for word in ("refs", "OZX", "Translate", "offset", "AttachmentOffset", "param_bind", "AttachmentOffset.Base.x"):
                self.assertIn(word, d, (name, word))
            self.assertIn("refs", e[name]["inputSchema"]["properties"])
            self.assertIn("offset", e[name]["inputSchema"]["properties"])
        self.assertIn("body", e["part_datum"]["inputSchema"]["properties"])
        self.assertIn("part", e["part_datum"]["inputSchema"]["properties"])
        self.assertIn("Part::LocalCoordinateSystem", json.dumps(e["pd_datum"]["steps"]))


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
# Fixes from the blind QA of series s1127a (27 Nov). Each one states a
# measured fact, removes a false fact or closes a gap, by one rule for every
# part and every tool where it applies. No test here uses the numbers of a
# QA test part as a special case.
#   Group A: refusals say what arrived (F2), a place taken by default is
#            said (F3), and a document from doc_new is an agent's at once (F5).
#   Group B: where a new sketch shape lies against the face and the body
#            (F1), the measured change of a body whose sketch was edited (F6),
#            a partial cut in the result line (F7), removal calls written from
#            the state (F9), which face a sketch is on (F10), and a true
#            pd_body_new example.
#   Group C: the sketch todo gives each open end and the measured distance to
#            the nearest other open end. No threshold decides the words.
# The FreeCAD-facing code runs on the stand-in (tests/_datapd_standin.py) in
# a child process. Real shapes need a real FreeCAD.
import json
import os
import re
import subprocess
import sys
import textwrap
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import protocol, runners  # noqa: E402
from agentlink import resultline as rl  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402

CHILD = '''
import json, sys, tempfile, types
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()
fc.patch()
from agentlink.protocol import ToolError
from agentlink.families import sketch
from agentlink.families import pd_common as pc
def tool(fam, s, name): return next(t for t in fam.tools(s) if t.name == name)
def refusal(fn):
    try:
        fn()
    except ToolError as e:
        return e.message
    return None
''' % (ROOT, HERE)


def child(body):
    r = subprocess.run([sys.executable, "-c", CHILD + textwrap.dedent(body)], capture_output=True, text=True, timeout=120, cwd=HERE)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def schema(name):
    return runners.entries()[name]["inputSchema"]


def refused(name, args):
    try:
        protocol.check_input(schema(name), args, name)
    except ToolError as e:
        return e.message
    return None


def fake_tool(name):
    return types.SimpleNamespace(name=name, schema=schema(name))


# ---- F2: refusals say what arrived -----------------------------------------------------------

class UnknownFields(unittest.TestCase):
    def test_every_unknown_field_is_named_in_one_refusal(self):
        got = refused("sketch_constrain", {"kind": "tangent", "object1": "Line1", "object2": "Circle1"})
        self.assertTrue(got.startswith("input.kind, object1, object2: not known fields — the fields here: sketch, type, refs, value, name."), got)
        self.assertIn("The constraint's kind goes in type.", got)

    def test_shared_words_are_said_once(self):
        got = refused("sketch_constrain", {"type": "distance", "a": 0, "b": 1, "length": 5})
        self.assertTrue(got.startswith("input.a, b, length: not known fields"), got)
        self.assertEqual(got.count("Its geometry ids and points go in refs"), 1)
        self.assertEqual(got.count("A size goes in value"), 1)
        self.assertEqual(got.count("A constraint has only type, refs, value and name."), 1)
        self.assertTrue(got.rstrip().endswith('"refs": [0, 1] }.'), got)  # the form and its example come last

    def test_one_unknown_field_keeps_its_words(self):
        got = refused("feature_remove", {"feature": "Pad", "thing": 1})
        self.assertTrue(got.startswith("input.thing: not a known field — the fields here: body, feature, keepSketch, force"), got)

    def test_the_rule_is_the_same_for_every_tool(self):
        for name, e in runners.entries().items():
            sch = e["inputSchema"]
            if sch.get("additionalProperties") is not False or name in protocol.FORGIVING_READS or name in protocol.STRICT_SHAPE:
                continue
            args = {"zzQa1": 1, "zzQa2": 2}
            try:
                protocol.check_input(sch, args, name)
            except ToolError as x:
                self.assertTrue(x.message.startswith("input.zzQa1, zzQa2: not known fields"), (name, x.message))
            else:
                self.fail(name)


class NotGiven(unittest.TestCase):
    def test_a_required_input_says_what_arrived(self):
        self.assertEqual(refused("feature_remove", {"body": "B"}), "input.feature: required. The call did not give it. The call gave: body.")
        self.assertEqual(refused("sketch_add", {}), "input.kind: required. The call did not give it. The call gave no inputs.")

    def test_every_missing_required_input_is_named(self):
        sch = {"type": "object", "properties": {"a": {}, "b": {}, "c": {}}, "required": ["a", "b"], "additionalProperties": False}
        try:
            protocol.check_input(sch, {"c": 1})
        except ToolError as e:
            self.assertEqual(e.message, "input.a, b: required. The call did not give them. The call gave: c.")
        else:
            self.fail()

    def test_a_tools_own_refusal_of_an_input_not_given(self):
        t = fake_tool("pd_pocket")
        msg = "length: mm, over 0 — or extent up_to_face | up_to_first | through_all."
        self.assertEqual(protocol.arrived_words(t, "invalid_input", msg, {"sketch": "S"}), " The call did not give length. The call gave: sketch.")
        # given: nothing is added; another code: nothing; said already: nothing
        self.assertEqual(protocol.arrived_words(t, "invalid_input", msg, {"sketch": "S", "length": -1}), "")
        self.assertEqual(protocol.arrived_words(t, "not_found", msg, {"sketch": "S"}), "")
        self.assertEqual(protocol.arrived_words(t, "invalid_input", refused("feature_remove", {}), {}), "")
        # words that name no input of the tool: nothing
        self.assertEqual(protocol.arrived_words(t, "invalid_input", "The sketch has no closed outline.", {"sketch": "S"}), "")

    def test_a_kind_tool_adds_the_inputs_of_the_kind(self):
        t = fake_tool("sketch_add")
        got = protocol.arrived_words(t, "invalid_input", "center: an arc needs its centre [x, y].", {"kind": "arc", "radius": 4, "start": 0, "end": 90})
        self.assertEqual(got, " The call did not give center. The call gave: kind, radius, start, end. arc takes center, radius, start, end.")


class KindInputs(unittest.TestCase):
    TABLE = runners.entries()["sketch_add"]["kindInputs"]

    def test_the_table_is_the_cards(self):
        sch = schema("sketch_add")
        props, kinds = sch["properties"], sch["properties"]["kind"]["enum"]
        self.assertEqual(sorted(self.TABLE), sorted(kinds))
        desc = runners.entries()["sketch_add"]["description"]
        for kind, fields in self.TABLE.items():
            said = " ".join(re.findall(r"(?<![\w_])%s \{([^}]*)\}" % re.escape(kind), desc))
            for f in fields:
                self.assertIn(f, props, (kind, f))
                if kind == "rounded_rectangle" and f != "radius":
                    continue  # the card says "…": a rectangle's inputs
                self.assertRegex(said, r"\b%s\b" % f, (kind, f))
        common = [p for p in props if not any(p in v for v in self.TABLE.values())]
        self.assertEqual(common, ["sketch", "kind", "construction", "dims", "name"])

    def test_an_input_of_another_kind_is_refused_with_the_kinds_inputs(self):
        got = refused("sketch_add", {"kind": "line", "start": [0, 20], "end": [170, 12.5]})
        self.assertEqual(got, "input.start, end: not inputs of kind line. line takes from, to. start, end: inputs of arc, arc_slot.")
        got = refused("sketch_add", {"kind": "line", "start": 20, "end": 150})  # the right type for an arc: still not a line's
        self.assertTrue(got.startswith("input.start, end: not inputs of kind line."), got)
        got = refused("sketch_add", {"kind": "circle", "center": [0, 0], "radius": 3, "size": [4, 4], "at": [1, 1]})
        self.assertEqual(got, "input.size, at: not inputs of kind circle. circle takes center, radius, diameter. "
                              "size: an input of rectangle, rounded_rectangle. at: an input of point.")

    def test_each_kinds_own_inputs_and_the_common_ones_pass_this_check(self):
        for kind, fields in self.TABLE.items():
            args = {"kind": kind, "sketch": "S", "construction": True, "dims": True, "name": "n", **{f: None for f in fields}}
            protocol.other_kind("sketch_add", args)  # no refusal

    def test_a_tool_with_no_kinds_is_not_checked(self):
        protocol.other_kind("pd_pad", {"kind": "line", "start": 1})
        protocol.other_kind(None, {"kind": "line", "start": 1})
        self.assertEqual(protocol.kind_inputs("pd_pad"), {})


class RefsRead(unittest.TestCase):
    def test_vertex_0_is_said_as_the_code_read_it(self):
        got = child('''
        s = fc.Session(tempfile.mkdtemp())
        sk = fc.drawing(s, fc.body(s, "B"), "S")
        add = tool(sketch, s, "sketch_add")
        add.fn({"sketch": "S", "kind": "line", "from": [0, 0], "to": [10, 0]})
        add.fn({"sketch": "S", "kind": "circle", "center": [20, 0], "radius": 3})
        add.fn({"sketch": "S", "kind": "arc", "center": [0, 5], "radius": 5, "start": 0, "end": 90})
        mk = lambda c: refusal(lambda: sketch.make_constraint(sk, c))
        print(json.dumps([mk({"type": "coincident", "refs": [[2, 0], [0, 1]]}), mk({"type": "coincident", "refs": [2, [0, 2]]}),
                          mk({"type": "parallel", "refs": [[0, 1], [2, 2]]}), mk({"type": "radius", "refs": [], "value": 2}),
                          mk({"type": "coincident", "refs": [[1, 0], "origin"]}), mk({"type": "coincident", "refs": [[0, 2], [2, 1]]})]))
        ''')
        self.assertEqual(got[0], "coincident: refs two points [[g, v], [g, v]]. The call gave 2 refs: [2, 0] is arc 2 as a whole "
                                 "(vertex 0 is the whole curve; its points are [2, 1] start point, [2, 2] end point, [2, 3] centre); [0, 1] is the start of line 0.")
        # a bare id is the whole curve too; its points are listed only for a ref written with vertex 0
        self.assertEqual(got[1], "coincident: refs two points [[g, v], [g, v]]. The call gave 2 refs: 2 is arc 2 as a whole; [0, 2] is the end of line 0.")
        self.assertEqual(got[2], "parallel: refs two geometries [g, g] (no vertices). The call gave 2 refs: [0, 1] is the start of line 0; [2, 2] is the end of arc 2.")
        self.assertEqual(got[3], "radius: refs one circle or arc [g]. The call gave no refs.")
        self.assertIn('[1, 0] is circle 1 as a whole (vertex 0 is the whole curve; its points are [1, 3] centre); "origin" is the sketch origin.', got[4])
        self.assertIsNone(got[5])  # two points: taken


# ---- F3: a place taken by default is said ----------------------------------------------------

class Defaults(unittest.TestCase):
    def test_the_sentence(self):
        self.assertEqual(rl.default_text({"center": [0, 0]}), "center not given, so center is [0, 0]")
        got = rl.shape_text("circle", [4], circle=((0, 0), 3), xr=(-3, 3), yr=(-3, 3), default={"center": [0, 0]})
        self.assertEqual(got, "circle, id 4: center not given, so center is [0, 0]; centre (0, 0), radius 3; sketch x -3..3, y -3..3.")
        self.assertNotIn("not given", rl.shape_text("circle", [4], circle=((0, 0), 3)))

    def test_on_the_stand_in(self):
        got = child('''
        s = fc.Session(tempfile.mkdtemp())
        fc.drawing(s, fc.body(s, "B"), "S")
        add = tool(sketch, s, "sketch_add")
        out = {"none": add.fn({"sketch": "S", "kind": "rectangle", "size": [7, 9]}),
               "center": add.fn({"sketch": "S", "kind": "rectangle", "center": [0, 0], "size": [7, 9]}),
               "corner": add.fn({"sketch": "S", "kind": "rectangle", "corner": [1, 2], "size": [7, 9]}),
               "circle": add.fn({"sketch": "S", "kind": "circle", "radius": 2})}
        out = {k: [v["result"], v["added"][0].get("byDefault")] for k, v in out.items()}
        out["arc"] = refusal(lambda: add.fn({"sketch": "S", "kind": "arc", "radius": 4, "start": 10, "end": 80}))
        out["arcOk"] = add.fn({"sketch": "S", "kind": "arc", "center": [3, 3], "radius": 4, "start": 10, "end": 80})["result"]
        out["table"] = {k: [sketch.by_default({"kind": k}), sketch.by_default({"kind": k, f: [1, 1]})] for k, f in sketch.ORIGIN_DEFAULT.items()}
        out["others"] = [k for k in ("line", "polyline", "arc", "arc3", "circle3", "bspline", "slot", "point") if sketch.by_default({"kind": k})]
        print(json.dumps(out))
        ''')
        self.assertTrue(got["none"][0].startswith("rectangle, ids 0-3: center not given, so center is [0, 0]; construction not given, so construction is false; sketch x -3.5..3.5, y -4.5..4.5"), got["none"][0])
        self.assertEqual(got["none"][1], {"center": [0, 0], "construction": False})
        for k in ("center", "corner"):  # the place was given: only what was not given is said (27 Nov: every such value)
            self.assertNotIn("center not given", got[k][0])
            self.assertEqual(got[k][1], {"construction": False})
        self.assertIn("center not given, so center is [0, 0]", got["circle"][0])
        self.assertEqual(got["arc"], "center: an arc needs its centre [x, y].")
        self.assertNotIn("center not given", got["arcOk"])
        self.assertNotIn("start not given", got["arcOk"])
        for k, (missing, given) in got["table"].items():
            self.assertEqual(list(missing.values())[0], [0, 0], k)
            self.assertNotIn([0, 0], list(given.values()), k)
        # every kind says the values it filled: at least construction false
        self.assertEqual(got["others"], ["line", "polyline", "arc", "arc3", "circle3", "bspline", "slot", "point"])


# ---- F5: the agent's own document ------------------------------------------------------------

class OwnDocument(unittest.TestCase):
    def test_doc_new_makes_an_agents_document_before_its_answer_is_built(self):
        got = child('''
        import FreeCAD
        from agentlink import options, tools as T
        from agentlink.families import doc
        made = {}
        class D:
            def __init__(s, name): s.Name = s.Label = name; s.Objects = []; s.FileName = ""
        def new(name, **kw):
            made[name] = D(name)
            return made[name]
        FreeCAD.newDocument, FreeCAD.listDocuments, FreeCAD.setActiveDocument = new, (lambda: dict(made)), (lambda n: None)
        s = fc.Session(tempfile.mkdtemp())
        server = types.SimpleNamespace(tools={"doc_new": None})
        before = options.theirs_first(s, server)
        out = tool(doc, s, "doc_new").fn({"name": "Own Work"})
        print(json.dumps({"before": before and before["why"], "doc": out["document"], "mine": out["document"] in s.agent_docs,
                          "docNew": options.theirs_first(s, server), "isCurrent": s.doc.Name == out["document"]}))
        ''')
        self.assertIn("is the person's", got["before"])  # the stand-in's first document is not an agent's
        self.assertTrue(got["mine"] and got["isCurrent"], got)
        self.assertIsNone(got["docNew"])  # no "doc_new: … is the person's" option after the agent's own doc_new

    def test_the_orientation_reads_the_same_list(self):
        # agentlink.tools needs FreeCAD: its source is read as text.
        with open(os.path.join(ROOT, "agentlink", "tools.py"), encoding="utf-8") as f:
            src = f.read()
        body = src[src.index("    def orientation(self):"):src.index("    def session_state(self, a):")]
        self.assertIn("mine = self.doc.Name in self.agent_docs", body)
        self.assertIn("The agent's document is one an agent made.", body)


# ---- F1: where a new shape lies --------------------------------------------------------------

FAKES0 = """
class BB:
    def __init__(s, b): s.XMin, s.XMax, s.YMin, s.YMax, s.ZMin, s.ZMax = b; s.DiagonalLength = 100.0
class Shp:
    def __init__(s, b, solids=1, vol=100.0):
        s.BoundBox = BB(b); s.Solids = [s] * solids; s.Faces = [object()] * 6; s.Volume = vol
    def isNull(s): return False
class Pl:
    def __init__(s, ident=True): s.ident = ident
    def isIdentity(s): return s.ident
    def toMatrix(s): return "M"
"""
FAKES = textwrap.indent(FAKES0, "        ")


class Lies(unittest.TestCase):
    BODY = (-4, 8, -3, 3, 0, 2)

    def test_the_sentence_uses_the_words_of_a_features_answer(self):
        got = rl.lies_text("the body", (-6, -1, 1, 5, 2, 2), self.BODY)
        self.assertEqual(got, "Against the body (x -4..8, y -3..3, z 0..2): x past -x by 2; y past +y by 2; z inside (2 from -z, 0 from +z).")
        self.assertIn(rl.against((-6, -1, 1, 5, 2, 2), self.BODY), got)  # one set of words

    def test_inside_gives_the_distance_to_each_side(self):
        for i, ax in enumerate("xyz"):
            lo, hi = self.BODY[2 * i], self.BODY[2 * i + 1]
            new = list(self.BODY)
            new[2 * i], new[2 * i + 1] = lo + 0.25, hi - 1.5
            self.assertIn(f"{ax} inside (0.25 from -{ax}, 1.5 from +{ax})", rl.against(tuple(new), self.BODY))

    def test_a_flat_face_leaves_out_the_axis_it_has_no_size_on(self):
        face = (-4, 8, -3, 3, 2, 2)
        got = rl.lies_text("the face", (-6, -1, 1, 2, 2, 2), face, flat=True)
        self.assertEqual(got, "Against the face (x -4..8, y -3..3, z 2): x past -x by 2; y inside (4 from -y, 1 from +y).")
        for i in range(3):  # the same on each axis
            f = [0, 10, 0, 10, 0, 10]
            f[2 * i + 1] = 0
            said = rl.lies_text("the face", (1, 2, 1, 2, 1, 2), tuple(f), flat=True)
            self.assertNotIn(f"{'xyz'[i]} inside", said)
            self.assertNotIn(f"past -{'xyz'[i]}", said)
            self.assertEqual(said.count("inside") + said.count("past"), 2)

    def test_a_sketch_plane_inside_the_body(self):
        got = rl.lies_text("the body", (0, 0, -1, 1, 0, 1), (-7, 5, -3, 3, 0, 2))
        self.assertIn("x inside (7 from -x, 5 from +x)", got)

    def test_measured_from_the_face_and_the_body_on_stand_ins(self):
        got = child(FAKES + """
        face = Shp((-4, 8, -3, 3, 2, 2))
        feat = types.SimpleNamespace(Shape=types.SimpleNamespace(getElement=lambda n: face), Label="Pad")
        body = types.SimpleNamespace(Shape=Shp((-4, 8, -3, 3, 0, 2)), Placement=Pl())
        empty = types.SimpleNamespace(Shape=Shp((0, 0, 0, 0, 0, 0), solids=0), Placement=Pl())
        on_face = types.SimpleNamespace(PropertiesList=["AttachmentSupport"], AttachmentSupport=[(feat, ("Face6",))])
        on_plane = types.SimpleNamespace(PropertiesList=["AttachmentSupport"], AttachmentSupport=[(feat, ("",))])
        world = (-6, -1, 1, 2, 2, 2)
        out = {}
        pc.body_of = lambda o: body
        out["face"] = sketch.lies_words(on_face, world)
        out["plane"] = sketch.lies_words(on_plane, world)
        pc.body_of = lambda o: empty
        out["noSolid"] = sketch.lies_words(on_plane, world)
        pc.body_of = lambda o: None
        out["noBody"] = sketch.lies_words(on_plane, world)
        pc.body_of = lambda o: body
        on_face.Document = types.SimpleNamespace(RecomputesFrozen=True)
        out["held"] = sketch.lies_words(on_face, world)
        on_face.Document = types.SimpleNamespace(RecomputesFrozen=False)
        body.getGlobalPlacement = lambda: types.SimpleNamespace(isSame=lambda other, tol: False)   # a moved Part holds the body
        out["twoFrames"] = sketch.lies_words(on_face, world)
        body.getGlobalPlacement = lambda: types.SimpleNamespace(isSame=lambda other, tol: True)
        out["oneFrame"] = len(sketch.lies_words(on_face, world))
        print(json.dumps(out))
        """)
        self.assertEqual(got["face"], ["Against the face (x -4..8, y -3..3, z 2): x past -x by 2; y inside (4 from -y, 1 from +y).",
                                       "Against the body (x -4..8, y -3..3, z 0..2): x past -x by 2; y inside (4 from -y, 1 from +y); z inside (2 from -z, 0 from +z)."])
        self.assertEqual(len(got["plane"]), 1)
        self.assertTrue(got["plane"][0].startswith("Against the body"))
        self.assertEqual((got["noSolid"], got["noBody"], got["held"], got["twoFrames"]), ([], [], [], []))  # nothing measured: nothing said
        self.assertEqual(got["oneFrame"], 2)

    def test_the_result_line_has_it_after_the_shape_and_before_the_wires(self):
        line = rl.sketch_add_result(["circle, id 0: centre (1, 1), radius 2."], 1, 1, 0, ["Against the body (x 0..1, y 0..1, z 0..1): x inside (0 from -x, 0 from +x)."])
        self.assertEqual(line, "circle, id 0: centre (1, 1), radius 2. Against the body (x 0..1, y 0..1, z 0..1): x inside (0 from -x, 0 from +x). The sketch has 1 wire, 1 closed, 0 open ends.")
        self.assertEqual(rl.sketch_add_result(["a."], 1, 1, 0), "a. The sketch has 1 wire, 1 closed, 0 open ends.")

    def test_sketch_add_on_the_stand_in_has_the_sentence_in_result(self):
        got = child(FAKES + """
        s = fc.Session(tempfile.mkdtemp())
        b = fc.body(s, "B")
        fc.drawing(s, b, "S")
        solid = types.SimpleNamespace(Shape=Shp((-4, 8, -3, 3, 0, 2)), Placement=Pl())
        pc.body_of = lambda o: solid
        r = tool(sketch, s, "sketch_add").fn({"sketch": "S", "kind": "rectangle", "corner": [6, 1], "size": [4, 1]})
        print(json.dumps([list(r)[0], r["result"]]))
        """)
        self.assertEqual(got[0], "result")
        self.assertIn("Against the body (x -4..8, y -3..3, z 0..2): x past +x by 2; y inside (4 from -y, 1 from +y); z inside (0 from -z, 2 from +z).", got[1])
        self.assertLess(got[1].index("Against the body"), got[1].index("The sketch has"))


# ---- F10: which face a sketch is on ----------------------------------------------------------

class WhichFace(unittest.TestCase):
    def test_the_face_is_said_by_its_side_not_by_its_centre(self):
        got = child("""
        V = fc.Vec if hasattr(fc, "Vec") else __import__("FreeCAD").Vector
        def face(n, c):
            return types.SimpleNamespace(ParameterRange=(0, 1, 0, 1), normalAt=lambda u, v: V(*n), CenterOfMass=V(*c))
        def link(n, c, label="Pad"):
            f = face(n, c)
            return types.SimpleNamespace(Shape=types.SimpleNamespace(getElement=lambda name: f), Label=label), ["Face6"]
        out = []
        for n, c in (((0, 0, 1), (7, 4, 2.5)), ((0, 0, -1), (7, 4, 0)), ((1, 0, 0), (9, 4, 1)), ((0, -1, 0), (7, -3, 1))):
            l = link(n, c)
            out.append(sketch.face_said(types.SimpleNamespace(Tip=l[0]), l, "face at [7.0, 4.0, 2.5]"))
        l = link((0, 0, 1), (7, 4, 2.5), "Base")
        out.append(sketch.face_said(types.SimpleNamespace(Tip=None), l, "x"))
        out.append(sketch.face_said(types.SimpleNamespace(Tip=None), (None, ["Face1"]), "face at [1, 2, 3]"))
        pl = types.SimpleNamespace(Base=V(0, 0, 2.5), Rotation=types.SimpleNamespace(multVec=lambda v: v))
        out.append(sketch.on_words(out[0], pl))
        print(json.dumps(out))
        """)
        self.assertEqual(got[:4], ["the face +z at z 2.5", "the face -z at z 0", "the face +x at x 9", "the face -y at y -3"])
        self.assertEqual(got[4], "the face +z at z 2.5 (Base's)")
        self.assertEqual(got[5], "face at [1, 2, 3] (its centre)")  # not read: plane_ref's words, marked as the centre
        self.assertEqual(got[6], "the face +z at z 2.5; sketch origin at [0, 0, 2.5]")
        self.assertNotIn("centre", " ".join(got[:5] + got[6:]))

    def test_the_result_line_and_on_use_it(self):
        e = runners.entries()["sketch_new"]
        f = e["answer"]["fields"]
        self.assertEqual(f["result"], "=new_result(sk, b, said, link)")
        self.assertEqual(f["on"], "=on_words(said, sk.Placement) if 'face' in a else what")
        self.assertEqual(rl.sketch_new_result("S", "the face +z at z 2.5", "x runs +X.", None, ((0, 4), (0, 2), (0, 0)))[:46], "Sketch S is on the face +z at z 2.5. x runs +X")


# ---- F6: the measured change of a body whose sketch was edited --------------------------------

class UsedSketch(unittest.TestCase):
    def test_the_sentences(self):
        box = (0, 9, 0, 4, 0, 2)
        self.assertEqual(rl.body_change_text("Body", 72.0, 65.75, box, box, 1, 1), "This call changed Body: volume change -6.25 mm³, now 65.75 mm³.")
        self.assertEqual(rl.body_change_text("Body", 72.0, 72.004, box, box, 1, 1), "After this call the volume of Body is 72 mm³: volume change 0 mm³.")
        got = rl.body_change_text("Body", 72.0, 80.0, box, (0, 10, 0, 4, 0, 2), 1, 2)
        self.assertEqual(got, "This call changed Body: volume change +8 mm³, now 80 mm³. The body before is x 0..9, y 0..4, z 0..2. "
                              "The body now is x 0..10, y 0..4, z 0..2. The body is 2 solids (was 1).")

    def test_measured_before_and_after_on_stand_ins(self):
        got = child(FAKES + """
        pad = types.SimpleNamespace(TypeId="PartDesign::Pad", Label="Pad", State=[], Profile=None)
        doc = types.SimpleNamespace(RecomputesFrozen=False)
        sk = types.SimpleNamespace(Name="Sketch", Label="Base", InList=[pad], Document=doc, State=[], TypeId="Sketcher::SketchObject")
        pad.Profile = sk
        free = types.SimpleNamespace(Name="Sketch001", Label="Free", InList=[], Document=doc, State=[], TypeId="Sketcher::SketchObject")
        body = types.SimpleNamespace(Name="Body", Label="Body", Shape=Shp((0, 9, 0, 4, 0, 2), vol=72.0), Group=[sk, pad], State=[], TypeId="PartDesign::Body")
        pc.body_of = lambda o: body
        out = {}
        mark = pc.used_mark(sk)
        out["mark"] = [mark["volume"], list(mark["box"]), mark["solids"]]
        out["unusedHasNoMark"] = pc.used_mark(free)
        body.Shape = Shp((0, 9, 0, 4, 0, 2), vol=65.75)
        out["changed"] = pc.used_change(sk, mark)
        out["note"] = pc.used_sketch_note(sk, tool="sketch_add", change=out["changed"])
        out["forecast"] = pc.used_sketch_note(sk, tool="sketch_add")
        body.Group.append(free)
        out["noteFree"] = pc.used_sketch_note(sk, tool="sketch_add", change=out["changed"])
        body.Group.pop()
        doc.RecomputesFrozen = True
        out["held"] = pc.used_change(sk, mark)
        doc.RecomputesFrozen = False
        pad.State = ["Touched"]
        out["touched"] = pc.used_change(sk, mark)
        pad.State = []
        out["noMark"] = pc.used_change(sk, None)
        out["otherSketch"] = pc.used_change(free, mark)
        body.Shape = Shp((0, 9, 0, 4, 0, 2), vol=72.0)
        out["same"] = pc.used_change(sk, mark)
        out["sameOnlyChanged"] = pc.used_change(sk, mark, only_changed=True)
        body.Shape = Shp((0, 9.5, 0, 4, 0, 2), vol=72.0)
        out["boxOnlyChanged"] = pc.used_change(sk, mark, only_changed=True)
        body.Shape = Shp((0, 9, 0, 4, 0, 2), vol=72.0)
        # the session keeps the reading of the first sketch a call works on
        s = types.SimpleNamespace(sketch_now=None, filled_now=[], sketch_before=None)
        pc.note_named(s, sk)
        out["kept"] = s.sketch_before["volume"]
        print(json.dumps(out))
        """)
        self.assertEqual(got["mark"], [72.0, [0, 9, 0, 4, 0, 2], 1])
        self.assertIsNone(got["unusedHasNoMark"])
        self.assertEqual(got["changed"], "This call changed Body: volume change -6.25 mm³, now 65.75 mm³.")
        self.assertEqual(got["note"], "Note: Base is the profile of Pad. This call changed Body: volume change -6.25 mm³, now 65.75 mm³.")
        self.assertEqual(got["forecast"], "Note: Base is the profile of Pad; adding to it changes Pad.")  # not measured: the words as before
        self.assertTrue(got["noteFree"].startswith("Base is used by Pad. This call changed Body: volume change -6.25 mm³, now 65.75 mm³. Body also has a sketch that no feature uses: Free."), got["noteFree"])
        for k in ("held", "touched"):  # 27 Nov: not recomputed is said plainly
            self.assertEqual(got[k], "Body is not recomputed yet (its features are Touched), so its change is not measured here.", k)
        for k in ("noMark", "otherSketch"):  # not measured: not said
            self.assertIsNone(got[k], k)
        self.assertEqual(got["same"], "After this call the volume of Body is 72 mm³: volume change 0 mm³.")
        self.assertEqual(got["kept"], 72.0)
        self.assertIsNone(got["sameOnlyChanged"])  # a constraint that changed nothing of the body: no note
        self.assertEqual(got["boxOnlyChanged"], "After this call the volume of Body is 72 mm³: volume change 0 mm³. The body before is x 0..9, y 0..4, z 0..2. The body now is x 0..9.5, y 0..4, z 0..2.")

    def test_a_constraint_is_a_change_to_a_used_sketch_too(self):
        self.assertIn("sketch_constrain", protocol.SKETCH_CHANGE_TOOLS)
        self.assertLessEqual(protocol.SKETCH_GEOMETRY_TOOLS, protocol.SKETCH_CHANGE_TOOLS)


# ---- F7: a partial cut in the result line ----------------------------------------------------

class PartialCut(unittest.TestCase):
    def test_the_sentence(self):
        self.assertEqual(rl.profiles_text(2, 2, [62.5, 37.5], 0), "2 of 2 profiles cut in part (62.5% and 37.5% of the volume that each area gives over the same depth).")
        self.assertEqual(rl.profiles_text(1, 1, [40], 0), "1 of 1 profile cut in part (40% of the volume that its area gives over the same depth).")
        self.assertEqual(rl.profiles_text(3, 3, [40], 1), "1 of 3 profiles cut in part (40% of the volume that its area gives over the same depth). 1 of 3 profiles cut nothing.")
        self.assertEqual(rl.profiles_text(3, 3, [], 0), "")  # every profile did all of it: nothing is said
        self.assertEqual(rl.profiles_text(2, 2, [10], 0, cut=False), "1 of 2 profiles added in part (10% of the volume that its area gives over the same depth).")
        self.assertIn("12 of 20 profiles were measured.", rl.profiles_text(20, 12, [], 3))

    def test_it_stands_in_the_result_line_before_the_solids(self):
        old = (0, 9, 0, 4, 0, 2)
        got = rl.feature_result("Pocket", "pd_pocket", -3.0, region=[(8, 9, 1, 2, 0, 2)], old_box=old, cut=True, faces=["+z at z 2"], solids=1, solids_was=1,
                                profiles=rl.profiles_text(1, 1, [50], 0))
        self.assertTrue(got.endswith("It opens on +z at z 2. 1 of 1 profile cut in part (50% of the volume that its area gives over the same depth). The body is 1 solid (was 1)."), got)

    def test_measured_by_the_profile_code_for_one_profile_and_for_several(self):
        got = child(FAKES + """
        V = __import__("FreeCAD").Vector
        class Hit:
            def __init__(s, vol, depth): s.Volume = vol; s.Vertexes = [types.SimpleNamespace(Point=V(0, 0, 0)), types.SimpleNamespace(Point=V(0, 0, depth))]
        class Face:
            def __init__(s, area, took, depth, in_old=1.0): s.Area, s.took, s.depth, s.in_old = area, took, depth, in_old
            def normalAt(s, u, v): return V(0, 0, 1)
            def translated(s, v): return s
            def extrude(s, v): return s
            def common(s, other): return Hit(s.took, s.depth) if other is reg else Hit(s.in_old, 1.0)
        old = Shp((0, 9, 0, 4, 0, 2)); old.BoundBox.Center = V(0, 0, 0)
        reg = Shp((0, 1, 0, 1, 0, 2)); reg.BoundBox.Center = V(0, 0, 0)
        feat = types.SimpleNamespace(TypeId="PartDesign::Pocket", Label="Pocket")
        out = {}
        def run(faces, cut=True):
            got = [(f"the outline {i}", x) for i, x in enumerate(faces)]
            pc.profile_faces = lambda f: got if len(got) > 1 else []
            pc.one_profile = lambda f: got if len(got) == 1 else []
            rec = {}
            return [pc.profile_results(feat, reg, old, 0.01, cut=cut, rec=rec), rec, pc._profiles_line({"profiles": rec}, cut)]
        out["onePart"] = run([Face(4.0, 5.0, 2.0)])                       # 5 of 8 mm³
        out["oneFull"] = run([Face(4.0, 8.0, 2.0)])
        out["two"] = run([Face(4.0, 6.0, 2.0), Face(4.0, 2.0, 2.0)])     # 75% and 25% of each one's 8 mm³
        out["none"] = run([Face(4.0, 8.0, 2.0), Face(4.0, 0.0, 2.0)])
        out["pad"] = run([Face(4.0, 4.0, 2.0)], cut=False)
        print(json.dumps(out))
        """)
        field, rec, line = got["onePart"]
        self.assertEqual(field, {})  # the profiles field stays for a sketch of several profiles
        self.assertEqual((rec["n"], rec["part"], rec["none"]), (1, [62.5], 0))
        self.assertEqual(line, "1 of 1 profile cut in part (62.5% of the volume that its area gives over the same depth).")
        self.assertEqual(got["oneFull"][2], "")
        field, rec, line = got["two"]
        self.assertIn("2 profiles", field["profiles"])
        self.assertEqual(line, "2 of 2 profiles cut in part (75% and 25% of the volume that each area gives over the same depth).")
        self.assertEqual(got["none"][2], "1 of 2 profiles cut nothing.")
        self.assertEqual(got["pad"][2], "1 of 1 profile added in part (50% of the volume that its area gives over the same depth).")


# ---- F9: removal calls written from the state ------------------------------------------------

# ---- the pd_body_new example -----------------------------------------------------------------

class BodyExample(unittest.TestCase):
    def test_the_example_marks_name_as_a_value_to_give(self):
        from agentlink import examples

        got = examples.for_tool("pd_body_new", {}, how="null")
        self.assertEqual(got["plain"], {"tool": "pd_body_new", "name": None})
        self.assertEqual(got["ready"], {"tool": "pd_body_new", "name": None})
        self.assertEqual(got["fill"], ["name: the label of the body; without name, the label is Body."])
        self.assertIn("'Body'", json.dumps(runners.entries()["pd_body_new"]["steps"]))  # the label without name, as the tool has it
        self.assertIsNone(refused("pd_body_new", {}))
        self.assertIn("input.name: give the value", refused("pd_body_new", {"name": None}))


# ---- Group C: open ends are facts ------------------------------------------------------------

class OpenEndFacts(unittest.TestCase):
    TAIL = ""

    def words(self, ends, curves=(0, 1), size=100.0, on=()):
        """open_end_words for ends; on: the (gid, pos) of the ends that lie on another curve."""
        return child("""
        ends = [tuple(e[:3]) + (tuple(e[3]),) for e in %r]
        on = {tuple(p) for g, k, s, p in ends if [g, s] in %r}
        dist = lambda i, p: 0.0 if tuple(p) in on else 50.0
        print(json.dumps(sketch.open_end_words(ends, %r, %r, dist)))
        """ % ([list(e) for e in ends], [list(x) for x in on], list(curves), size))

    def test_one_form_of_words_at_every_distance(self):
        # the same two ends, a little apart and far apart: the same words, with the measured number
        for gap in (0.0004, 0.02, 0.75, 6.0, 240.0):
            got = self.words([(0, "line", 2, (10, 0)), (1, "arc", 1, (10, gap))])
            self.assertEqual(len(got), 1, gap)
            m = re.fullmatch(r"the end of line 0 \[0, 2\] \(10, 0\) and the start of arc 1 \[1, 1\] \(10, ([\d.e-]+)\) are open ends, ([\d.e-]+) mm apart" + re.escape(self.TAIL), got[0])
            self.assertTrue(m, got[0])
            self.assertAlmostEqual(float(m.group(2)), gap, places=6)  # a distance that is not zero is never said as 0

    def test_the_size_of_the_outline_decides_nothing(self):
        ends = [(0, "line", 2, (10, 0)), (1, "line", 1, (10, 3)), (1, "line", 2, (90, 3))]
        self.assertEqual(len({json.dumps(self.words(ends, size=sz)) for sz in (0.5, 30.0, 400.0, 90000.0)}), 1)

    def test_each_open_end_has_the_distance_to_its_nearest_other_end(self):
        ends = [(0, "line", 1, (0, 0)), (0, "line", 2, (10, 0)), (1, "line", 1, (10, 3)), (1, "line", 2, (90, 3))]
        got = self.words(ends)
        self.assertEqual(got, ["the start of line 0 [0, 1] (0, 0) is an open end; the nearest other open end is the end of line 0 [0, 2] (10, 0), 10 mm away",
                               "the end of line 0 [0, 2] (10, 0) and the start of line 1 [1, 1] (10, 3) are open ends, 3 mm apart",
                               "the end of line 1 [1, 2] (90, 3) is an open end; the nearest other open end is the start of line 1 [1, 1] (10, 3), 80 mm away" + self.TAIL])

    def test_the_only_open_end_and_an_end_on_another_curve(self):
        self.assertEqual(self.words([(0, "line", 2, (10, 0))]), ["the end of line 0 [0, 2] (10, 0) is an open end, the only one" + self.TAIL])
        # an end on another curve is a branch (branch_words says it): no phrase of its own, still a nearest end of others
        got = self.words([(0, "line", 2, (10, 0)), (1, "line", 1, (10, 3))], on=[(1, 1)])
        self.assertEqual(got, ["the end of line 0 [0, 2] (10, 0) is an open end; the nearest other open end is the start of line 1 [1, 1] (10, 3), 3 mm away" + self.TAIL])
        self.assertEqual(self.words([(0, "line", 2, (10, 0))], on=[(0, 2)]), [])

    def test_the_words_say_nothing_of_what_was_meant(self):
        ends = [(g, "line", s, (g * 7.0, s * 0.01)) for g in range(4) for s in (1, 2)]
        got = self.words(ends, curves=(0, 1, 2, 3))
        text = " ".join(got)
        for banned in ("probably", "meant", "should", "remove it", "joins them", "sketch_constrain", "near ", "close to", "not a full circle"):
            self.assertNotIn(banned, text)
        self.assertNotIn("A closed outline has no open end", text)  # facts only (27 Nov)

    def test_a_cap_says_how_many_are_not_shown(self):
        ends = [(g, "line", 1, (g * 100.0, 0)) for g in range(7)]  # no two are each other's nearest but the first two
        got = self.words(ends, curves=tuple(range(7)))
        self.assertEqual(len(got), 5)
        self.assertEqual(got[-1], "and 2 more open ends (openVertices)" + self.TAIL)

    def test_the_one_tolerance_is_freecads(self):
        got = child("""
        print(json.dumps([sketch.SAME_POINT, pc.TOUCH, [n for n in ("NEAR_GAP", "ROUND_NEAR", "ROUND_NEAR_MM", "TINY_GAP_MM", "TINY_GAP") if hasattr(sketch, n)]]))
        """)
        self.assertEqual(got, [1e-7, 1e-7, []])


if __name__ == "__main__":
    unittest.main()

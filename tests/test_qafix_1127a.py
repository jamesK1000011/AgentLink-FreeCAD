# SPDX-License-Identifier: LGPL-2.1-or-later
# Fixes from the blind QA of series s1127a (27 Nov). Each one states a
# measured fact, removes a false fact or closes a gap, by one rule for every
# part and every tool where it applies. No test here uses the numbers of a
# QA test part as a special case.
#   Group A: refusals say what arrived (F2), a place taken by default is
#            said (F3), and a document from doc_new is an agent's at once (F5).
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
        self.assertTrue(got["none"][0].startswith("rectangle, ids 0-3: center not given, so center is [0, 0]; sketch x -3.5..3.5, y -4.5..4.5"), got["none"][0])
        self.assertEqual(got["none"][1], {"center": [0, 0]})
        for k in ("center", "corner"):  # the place was given: nothing is said
            self.assertNotIn("not given", got[k][0])
            self.assertIsNone(got[k][1])
        self.assertIn("center not given, so center is [0, 0]", got["circle"][0])
        self.assertEqual(got["arc"], "center: an arc needs its centre [x, y].")
        self.assertNotIn("not given", got["arcOk"])
        for k, (missing, given) in got["table"].items():
            self.assertEqual(list(missing.values()), [[0, 0]], k)
            self.assertIsNone(given, k)
        self.assertEqual(got["others"], [])


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


if __name__ == "__main__":
    unittest.main()

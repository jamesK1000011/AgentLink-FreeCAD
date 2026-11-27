# SPDX-License-Identifier: LGPL-2.1-or-later
# State -> options -> checked run (agentlink/options.py; efficiency design A):
# the likely next steps as numbered, ready calls bound to the step, their
# arguments filled from the document's real names by the rules' data
# (data/nexthint.json "arguments", "ask", "choices"), each one checked by the
# tool's own schema and leading checks before it is shown; pick runs one
# through the normal call path; a stale step is refused with the new
# options; the switch turns it all off; the static tool list never changes.
# Plain Python with stand-ins: no FreeCAD here.
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)

from agentlink import expr, nexthint, options, staticbase  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402

DATA = os.path.join(ROOT, "agentlink", "data")


# ---- stand-ins ---------------------------------------------------------------------------

class Obj:
    def __init__(self, type_id, name, bases=(), **more):
        self.TypeId, self.Name, self.Label = type_id, name, name
        self._bases = set(bases) | {type_id}
        self.State, self.InList, self.Group = [], [], []
        for k, v in more.items():
            setattr(self, k, v)

    def isDerivedFrom(self, t):
        return t in self._bases


def body_with(name, *members, tip=None):
    b = Obj("PartDesign::Body", name)
    b.Group = list(members)
    for m in members:
        m.InList.append(b)
    b.Tip = tip
    return b


def sketch(name, closed=True):
    return Obj("Sketcher::SketchObject", name, GeometryCount=4, Shape=types.SimpleNamespace(Wires=[types.SimpleNamespace(isClosed=lambda: closed)]))


def feature(kind, name, profile=None):
    f = Obj(f"PartDesign::{kind}", name, bases=("PartDesign::Feature",))
    if profile is not None:
        profile.InList.append(f)
    return f


def doc_of(*objs):
    return types.SimpleNamespace(Name="Unnamed", Objects=list(objs))


def schema_of(name):
    """The tool's real inputSchema (data/tools.json), or an open one for a tool written in code."""
    with open(os.path.join(DATA, "tools.json"), encoding="utf-8") as f:
        e = json.load(f)["entries"].get(name)
    return e["inputSchema"] if e else {"type": "object", "properties": {"body": {"type": "string"}}, "required": []}


class Session:
    def __init__(self, doc):
        self.doc, self.steps, self.tx, self.batch_now = doc, [], 0, None
        self.calls = []


def make(doc, refuse=None):
    """A server of stand-in tools with the real schemas. refuse: { tool: [steps] }
    — leading checks (a steps entry) that needs.of_tool reads dry."""
    names = sorted({s["tool"] for r in nexthint.load().values() for s in r["suggest"]})
    s = Session(doc)
    tools = []
    for n in names:
        def fn(a, _n=n):
            s.calls.append((_n, dict(a)))
            s.steps.append({"step": len(s.steps) + 1, "tool": _n})
            s.tx += 1
            return {"made": _n, "health": {"ok": True, "verdict": "nothing red"}}
        t = Tool(n, f"{n}.", schema_of(n), fn, changes=not n.startswith(("sketch_state", "feature_list", "td_list", "asm_check", "asm_bom", "body_check", "recompute")))
        if refuse and n in refuse:
            t.entry = {"runner": "steps", "steps": refuse[n]}
            t.helpers = {}
        tools.append(t)
    tools.append(Tool("session_state", "s.", {"type": "object", "properties": {}}, lambda a: {"step": len(s.steps), **options.state_field(s)}))
    tools.append(Tool("tool_find", "f.", {"type": "object", "properties": {}}, lambda a: {}, group="find"))
    pick = Tool("pick", "p.", {"type": "object", "properties": {"option": {"type": ["integer", "string"]}, "fill": {}}, "required": ["option"]}, options.pick_fn)
    pick.group = "find"
    tools.append(pick)
    server = Server("t", "0", tools, groups={"core"})
    server.session, s.server = s, server
    return s, server


def facts_reader(test, session):
    """options._read on the stand-in: the facts of the session's document."""
    orig = options._read
    options._read = lambda sess: (nexthint.facts(sess.doc, getattr(sess, "state", {}) or {}), getattr(sess, "state", {}) or {})
    test.addCleanup(setattr, options, "_read", orig)


def call(server, name, args):
    r = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
    return json.loads(r["content"][0]["text"]), bool(r.get("isError"))


class Base(unittest.TestCase):
    def setUp(self):
        os.environ.pop("AGENTLINK_OPTIONS", None)
        self.addCleanup(os.environ.pop, "AGENTLINK_OPTIONS", None)


# ---- the data ------------------------------------------------------------------------------

class Data(Base):
    def test_every_option_names_inputs_its_tool_has(self):
        for rid, rule in nexthint.load().items():
            for s in rule["suggest"]:
                if "arguments" not in s:
                    continue
                props = schema_of(s["tool"]).get("properties") or {}
                for k in list(s["arguments"]) + [a["arg"] for a in s.get("ask") or ()] + list(s.get("choices") or {}):
                    self.assertIn(k, props, f"{rid}: {s['tool']} has no input {k}")
                for a in s.get("ask") or ():
                    for word, more in (a.get("or") or {}).items():
                        for k in more:
                            self.assertIn(k, props, f"{rid}: {s['tool']} {word}")

    def test_every_expression_is_checked_and_reads_an_empty_state(self):
        n = 0
        for rid, rule in nexthint.load().items():
            for s in rule["suggest"]:
                for part in ("arguments", "choices"):
                    for k, v in (s.get(part) or {}).items():
                        if isinstance(v, str) and v.startswith("="):
                            self.assertIsNone(expr.check(v[1:]), rid)
                            expr.evaluate(v[1:], {"facts": {}})  # no fact: None, never an error
                            n += 1
        self.assertGreater(n, 40)

    def test_a_bad_expression_leaves_the_rule_out(self):
        bad = {"when": {"body": "empty"}, "suggest": [{"tool": "sketch_new", "why": "why not", "arguments": {"body": "=__import__('os')"}}],
               "weight": 1, "source": "test", "date": "2026-11-22"}
        self.assertTrue(nexthint.problems(bad))
        self.assertTrue(nexthint.declare({"bad": bad}, "test"))


# ---- building ------------------------------------------------------------------------------

class Build(Base):
    def opts(self, doc, state=None, refuse=None):
        s, server = make(doc, refuse)
        s.state = state or {}
        facts_reader(self, s)
        return options.build(s), s, server

    def test_empty_body(self):
        o, _s, _ = self.opts(doc_of(body_with("Body")))
        first = o["list"][0]
        self.assertEqual((first["n"], first["tool"], first["arguments"]), (1, "sketch_new", {"body": "Body", "plane": "XY"}))
        self.assertEqual(first["choices"], {"plane": ["XY", "XZ", "YZ"]})
        self.assertNotIn("ask", first)
        prim = next(x for x in o["list"] if x["tool"] == "pd_primitive")
        self.assertEqual((prim["arguments"], prim["ask"][0]["arg"]), ({"body": "Body"}, "kind"))

    def test_closed_sketch_without_feature(self):
        old, new = sketch("Sketch"), sketch("Sketch001")
        o, _s, _ = self.opts(doc_of(body_with("Body", old, new), old, new))
        pad = o["list"][0]
        self.assertEqual((pad["tool"], pad["arguments"]), ("pd_pad", {"sketch": "Sketch001", "body": "Body"}))
        self.assertEqual(options.ask_words(pad["ask"][0]), "length mm")
        self.assertEqual(pad["choices"], {"sketch": ["Sketch001", "Sketch"]})  # live choices, the newest first
        self.assertLessEqual(len(o["list"]), options.MAX_OPTIONS)

    def test_after_a_pad(self):
        sk = sketch("Sketch")
        pad = feature("Pad", "Pad", sk)
        o, _s, _ = self.opts(doc_of(body_with("Body", sk, pad, tip=pad), sk, pad))
        tools = [x["tool"] for x in o["list"]]
        self.assertEqual(tools[0], "sketch_new")
        # No pattern option by default after a pad (24 Nov blind QA): nothing says the part repeats.
        self.assertNotIn("pd_polar_pattern", tools)

    def test_sketch_open_in_edit(self):
        sk = sketch("Sketch")
        b = body_with("Body", sk)
        o, _s, _ = self.opts(doc_of(b, sk), {"editing": "sketch", "sketch": {"name": "Sketch", "obj": "Sketch", "dof": 0}})
        self.assertEqual(o["list"][0], {"n": 1, "tool": "sketch_state", "arguments": {"sketch": "Sketch"}, "why": o["list"][0]["why"]})
        pad = next(x for x in o["list"] if x["tool"] == "pd_pad")
        self.assertEqual(pad["arguments"], {"sketch": "Sketch", "body": "Body"})
        o, _s, _ = self.opts(doc_of(b, sk), {"editing": "sketch", "sketch": {"name": "Sketch", "obj": "Sketch", "dof": 3}})
        self.assertEqual(o["list"][0]["tool"], "sketch_constrain")
        self.assertEqual(o["list"][0]["ask"], [{"arg": "type"}, {"arg": "refs"}])

    def test_a_picked_edge(self):
        sk = sketch("Sketch")
        pad = feature("Pad", "Pad", sk)
        b = body_with("Body", sk, pad, tip=pad)
        s, server = make(doc_of(b, sk, pad))
        f = nexthint.facts(s.doc, {"selSubs": {"edge"}, "selected": 1})
        f.update({"selectionIn": "body", "picked": "Pad", "pickedEdges": ["Edge3", "Edge7"]})
        o = options.build(s, facts=f, state={})
        self.assertEqual(o["list"][0]["arguments"], {"body": "Body", "edges": ["Edge3", "Edge7"]})

    def test_the_needs_check_drops_an_option_that_would_refuse(self):
        sk, used = sketch("Sketch001"), sketch("Sketch")
        pad = feature("Pad", "Pad", used)
        doc = doc_of(body_with("Body", used, pad, sk), used, pad, sk)
        refuse = {"pd_pocket": [{"refuse": "Body has no solid to pocket: pd_pad first.", "code": "invalid_state", "when": "=a.sketch == 'Sketch001'"}],
                  "pd_pad": [{"refuse": "length: mm, over 0.", "when": "=not is_num(a.length) or a.length <= 0"}]}
        o, _s, _ = self.opts(doc, refuse=refuse)
        tools = [x["tool"] for x in o["list"]]
        self.assertIn("pd_pad", tools)  # its check reads the sample length (10): it passes
        self.assertNotIn("pd_pocket", tools)  # it would refuse with these arguments: left out
        self.assertEqual([x["n"] for x in o["list"]], list(range(1, len(tools) + 1)))

    def test_an_ask_without_a_sample_does_not_drop_its_option(self):
        sk = sketch("Sketch", closed=False)
        refuse = {"sketch_add": [{"refuse": "kind: the shape to add.", "when": "=not a.kind"}]}
        o, _s, _ = self.opts(doc_of(body_with("Body", sk), sk), refuse=refuse)
        self.assertIn("sketch_add", [x["tool"] for x in o["list"]])
        refuse = {"sketch_add": [{"refuse": "Sketch is not in a body.", "when": "=a.sketch == 'Sketch'"}]}
        o, _s, _ = self.opts(doc_of(body_with("Body", sk), sk), refuse=refuse)
        self.assertNotIn("sketch_add", [x["tool"] for x in o["list"]])

    def test_a_tool_that_is_not_here_is_no_option(self):
        sk = sketch("Sketch")
        s, server = make(doc_of(body_with("Body", sk), sk))
        del server.tools["pd_pad"]
        o = options.build(s, facts=nexthint.facts(s.doc, {}), state={})
        self.assertNotIn("pd_pad", [x["tool"] for x in o["list"]])

    def test_an_error_leaves_the_options_out(self):
        s, server = make(doc_of(body_with("Body")))
        s.server = None
        self.assertIsNone(options.build(s, facts={"body": "empty"}, state={}))
        s, server = make(doc_of(body_with("Body")))

        def boom(_s):
            raise RuntimeError("no")
        orig = options._read
        options._read = boom
        self.addCleanup(setattr, options, "_read", orig)
        self.assertIsNone(options.build(s))
        self.assertEqual(options.push(s, {"made": 1}), {"made": 1})


# ---- the words -----------------------------------------------------------------------------

class Words(Base):
    def test_line_is_short(self):
        used, old, new = sketch("Sketch"), sketch("Sketch001"), sketch("Sketch002")
        pad = feature("Pad", "Pad", used)
        s, server = make(doc_of(body_with("Body", used, pad, old, new), used, pad, old, new))
        o = options.build(s, facts=nexthint.facts(s.doc, {}), state={})
        ln = options.line(o)
        self.assertTrue(ln.startswith("step 0: 1 pd_pad sketch=Sketch002 or Sketch001 body=Body ask length mm; 2 pd_pocket"), ln)
        self.assertIn("ask length mm|through_all", ln)
        self.assertLessEqual(len(ln), options.MAX_LINE)
        print(f"\n  options line, closed sketch: {len(ln)} chars: {ln}")
        many = {"step": 7, "list": [{"n": i, "tool": "x" * 30, "arguments": {"a": "y" * 30, "b": "z" * 30}} for i in range(1, 5)]}
        self.assertLessEqual(len(options.line(many)), options.MAX_LINE)

    def test_public_form(self):
        sk = sketch("Sketch")
        s, server = make(doc_of(body_with("Body", sk), sk))
        p = options.public(options.build(s, facts=nexthint.facts(s.doc, {}), state={}))
        self.assertEqual(p["list"][0]["ask"], ["length mm"])
        self.assertIn("pick", p)


# ---- pick ----------------------------------------------------------------------------------

class Pick(Base):
    def setUp(self):
        super().setUp()
        used, sk = sketch("Base"), sketch("Sketch")
        pad = feature("Pad", "Pad", used)
        self.s, self.server = make(doc_of(body_with("Body", used, pad, sk), used, pad, sk))
        facts_reader(self, self.s)
        got, _ = call(self.server, "session_state", {})
        self.opts = got["options"]
        self.assertEqual(self.opts["list"][0]["step"]["tool"], "pd_pad")
        self.assertEqual(self.opts["list"][1]["step"]["tool"], "pd_pocket")

    def test_pick_fills_and_runs_the_call_through_the_normal_path(self):
        got, err = call(self.server, "pick", {"option": 1, "fill": {"length": 4}})
        self.assertFalse(err, got)
        self.assertEqual(self.s.calls, [("pd_pad", {"sketch": "Sketch", "body": "Body", "length": 4})])
        self.assertEqual(got["picked"], "1 pd_pad sketch=Sketch body=Body length=4")
        self.assertEqual(got["made"], "pd_pad")
        # A changing answer carries the options of the new step in one short line, beside the health's next.
        self.assertTrue(got["health"]["options"].startswith("step 1: 1 "), got["health"])

    def test_plain_text(self):
        call(self.server, "pick", {"option": "1, 4mm"})
        self.assertEqual(self.s.calls[-1][1]["length"], 4.0)
        call(self.server, "session_state", {})
        call(self.server, "pick", {"option": "2, through_all"})
        self.assertEqual(self.s.calls[-1], ("pd_pocket", {"sketch": "Sketch", "body": "Body", "extent": "through_all"}))

    def test_units_and_words(self):
        a = {"arg": "length", "unit": "mm", "or": {"through_all": {"extent": "through_all"}}}
        self.assertEqual(options.read_value(a, "4mm"), {"length": 4.0})
        self.assertEqual(options.read_value(a, "1 in"), {"length": 25.4})
        self.assertEqual(options.read_value(a, "2cm"), {"length": 20.0})
        self.assertEqual(options.read_value(a, "4"), {"length": 4.0})
        self.assertEqual(options.read_value(a, 4), {"length": 4})
        self.assertEqual(options.read_value(a, "Through All"), {"extent": "through_all"})
        self.assertEqual(options.read_value({"arg": "angle", "unit": "deg"}, "90°"), {"angle": 90.0})
        self.assertEqual(options.read_value({"arg": "count"}, "6"), {"count": 6})
        self.assertEqual(options.read_value({"arg": "kind"}, "box"), {"kind": "box"})
        with self.assertRaises(Exception):
            options.read_value(a, "4deg")
        self.assertEqual(options.parse_text("1, 4mm"), (1, ["4mm"]))
        self.assertEqual(options.parse_text(" 2 ,through_all"), (2, ["through_all"]))
        self.assertEqual(options.parse_text("3"), (3, []))
        self.assertEqual(options.parse_text("pad"), (None, []))

    def test_fill_in_order_and_a_choice(self):
        call(self.server, "pick", {"option": 1, "fill": ["5 mm"]})
        self.assertEqual(self.s.calls[-1][1]["length"], 5.0)
        call(self.server, "session_state", {})
        call(self.server, "pick", {"option": 1, "fill": {"length": 2, "sketch": "Other"}})
        self.assertEqual(self.s.calls[-1][1]["sketch"], "Other")

    def test_a_missing_ask_is_refused_and_nothing_runs(self):
        got, err = call(self.server, "pick", {"option": 1})
        self.assertTrue(err)
        self.assertEqual(got["error"]["code"], "invalid_input")
        self.assertIn("asks length mm", got["error"]["message"])
        self.assertEqual(self.s.calls, [])
        got, err = call(self.server, "pick", {"option": 9, "fill": 4})
        self.assertTrue(err)
        got, err = call(self.server, "pick", {"option": 1, "step": 3})
        self.assertIn("input.step", got["error"]["message"])

    def test_a_stale_step_is_refused_with_the_new_options(self):
        self.s.steps.append({"step": 1, "tool": "someone"})  # the document moved on after the options were given
        got, err = call(self.server, "pick", {"option": 1, "fill": 4})
        self.assertTrue(err)
        self.assertEqual(got["error"]["code"], "invalid_state")
        self.assertIn("step 0 are old", got["error"]["message"])
        self.assertEqual(got["error"]["options"]["step"], 1)
        self.assertEqual(got["error"]["options"]["list"][0]["step"]["tool"], "pd_pad")
        self.assertEqual(self.s.calls, [])
        # The new options are kept: a pick from them runs.
        got, err = call(self.server, "pick", {"option": "1, 3mm"})
        self.assertFalse(err, got)

    def test_pick_inside_a_batch_goes_the_same_way(self):
        # A batch runs its calls through server.call: pick is resolved there too.
        r = self.server.call({"name": "pick", "arguments": {"option": 1, "fill": 2}})
        self.assertFalse(r.get("isError"))
        self.assertEqual(self.s.calls[-1][0], "pd_pad")


# ---- the switch and the list ---------------------------------------------------------------

class Switch(Base):
    def test_off_removes_options(self):
        sk = sketch("Sketch")
        s, server = make(doc_of(body_with("Body", sk), sk))
        facts_reader(self, s)
        os.environ["AGENTLINK_OPTIONS"] = "off"
        got, _ = call(server, "session_state", {})
        self.assertNotIn("options", got)
        got, _ = call(server, "pd_pad", {"length": 3})
        self.assertNotIn("options", got["health"])
        self.assertNotIn("options", got)
        got, err = call(server, "pick", {"option": 1, "fill": 4})
        self.assertTrue(err)
        self.assertEqual(got["error"]["code"], "unavailable")
        os.environ["AGENTLINK_OPTIONS"] = "on"
        got, _ = call(server, "pd_pad", {"length": 3})
        # The same health as the last pad's is "nothing new" (once.quiet_health):
        # its options then stand in the answer itself.
        self.assertEqual(got["health"], "nothing new")
        self.assertIn("options", got)

    def test_the_static_list_does_not_change(self):
        self.assertNotIn("pick", staticbase.BASE)
        sk = sketch("Sketch")
        s, server = make(doc_of(body_with("Body", sk), sk))
        server.lean_groups = {"core"}
        facts_reader(self, s)

        def listing():
            r = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})["result"]["tools"]
            return json.dumps(r, sort_keys=True)

        os.environ["AGENTLINK_TOOLLIST"] = "static"
        self.addCleanup(os.environ.pop, "AGENTLINK_TOOLLIST", None)
        before = listing()
        self.assertNotIn('"pick"', before)
        call(server, "session_state", {})
        call(server, "pick", {"option": 1, "fill": 4})
        s.doc.Objects.append(sketch("Sketch009"))
        self.assertEqual(listing(), before)
        self.assertEqual(server.outbox, [])  # no list_changed


class NamesFromTheDocument(Base):
    def test_facts_give_the_real_names(self):
        a, b = sketch("Sketch"), sketch("Sketch001")
        body = body_with("Body", a, b)
        other = body_with("Body001")
        f = nexthint.facts(doc_of(other, body, a, b), {"sketch": {"name": "My sketch", "obj": "Sketch001", "dof": 0}, "editing": "sketch"})
        # Without an active body the newest one is taken; the others are its choices.
        # Labels, as every answer names objects (a Haiku run, 23 Nov): the sketch in edit by its label.
        self.assertEqual((f["bodyName"], f["bodies"], f["sketchName"], f["editSketch"]), ("Body", ["Body", "Body001"], "Sketch001", "My sketch"))
        f = nexthint.facts(doc_of(body, a, b), {})
        self.assertEqual((f["bodyName"], f["sketchName"], f["sketches"]), ("Body", "Sketch001", ["Sketch001", "Sketch"]))
        bad = Obj("Part::Feature", "Broken", State=["Invalid"])
        bad.State = ["Invalid"]
        self.assertEqual(nexthint.facts(doc_of(bad), {})["failingName"], "Broken")


if __name__ == "__main__":
    unittest.main()

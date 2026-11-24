# SPDX-License-Identifier: LGPL-2.1-or-later
# Seven setup fixes from local-model runs (gpt-oss-20b, LFM2.5, Qwen3; 23
# Nov), and one from a Haiku run: (1) a made-up tool name that names a
# sketch_add kind points to sketch_add with a worked item; (2) tool_find
# answers carry no "listed"; (3) batch says its calls run one at a time, in
# order; (4) the pick example fits the option it names; (5) the connect
# text gives only the basic batch form; (6) answers end with the live names,
# a first refusal orients, and every answer names objects by label; (7) a
# batch keeps what ran before a refusal by default.
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import livenames, nexthint, options  # noqa: E402
from test_hubfix2 import in_a_process  # noqa: E402
from test_hubfix4 import SETUP  # noqa: E402

# A server on the stand-in FreeCAD, with a probe that makes an object (one
# undo step, as a real change) and refuses when told to.
SERVER = SETUP + '''
    import os
    def _undo(self):
        self.UndoNames.pop(0)
        self.Objects.pop()
    Doc.undo = _undo
    Doc.removeObject = lambda self, n: self.Objects.remove(self.getObject(n))
    from agentlink import tools
    from agentlink.protocol import Tool, ToolError
    import tempfile
    s = tools.Session(out_dir=tempfile.mkdtemp(prefix="agentlink-1123-"))
    srv = tools.build_server(s, lean=False)
    s.server = srv
    def make(a):
        if a.get("fail"):
            raise ToolError("invalid_input", "fail: told to refuse.")
        o = Obj(s.doc, a["name"])
        o.TypeId = a.get("type", "Part::Box")
        s.doc.Objects.append(o)
        s.doc.change()
        return {"made": a["name"]}
    srv.tools["probe_make"] = Tool("probe_make", "Make an object.", {"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string"},
                                   "fail": {"type": "boolean"}}, "required": ["name"], "additionalProperties": False}, make, changes=True)
    def call(name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
        return [r.get("isError", False), json.loads(r["content"][0]["text"]), r["content"][0]["text"]]
    def mk(n, **kw):
        return {"tool": "probe_make", "arguments": {"name": n, **kw}}
    def labels():
        return [o.Label for o in s.doc.Objects]
    if "sketch_add" not in srv.tools:
        # The sketch family needs FreeCAD's Part: its card, as the data gives it.
        _sa = json.load(open(os.path.join(%r, "agentlink", "data", "tools.json"), encoding="utf-8"))["entries"]["sketch_add"]
        srv.tools["sketch_add"] = Tool("sketch_add", _sa["description"], _sa["inputSchema"], lambda a: {}, changes=True, group="sketch")
''' % ROOT


def run(body):
    return in_a_process(SERVER + body)


# ---- stand-in objects for the live names and the facts ----------------------------------------

class O:
    def __init__(self, type_id, name, label=None, **kw):
        self.TypeId, self.Name, self.Label = type_id, name, label or name
        self.InList, self.OutList, self.State = [], [], []
        self.__dict__.update(kw)

    def isDerivedFrom(self, t):
        return self.TypeId == t or (t == "PartDesign::Feature" and self.TypeId.startswith("PartDesign::") and self.TypeId != "PartDesign::Body")


class D:
    def __init__(self, objs):
        self.Objects = objs
        self.Name = self.Label = "Doc"


def body_doc():
    """Body: Sketch→Pad, Sketch 2→Pad 2 (Name Pad001), Sketch 3 not used."""
    sk1, sk2, sk3 = O("Sketcher::SketchObject", "Sketch"), O("Sketcher::SketchObject", "Sketch001", "Sketch 2"), O("Sketcher::SketchObject", "Sketch002", "Sketch 3")
    pad1 = O("PartDesign::Pad", "Pad", Profile=(sk1, [""]))
    pad2 = O("PartDesign::Pad", "Pad001", "Pad 2", Profile=(sk2, [""]))
    sk1.InList, sk2.InList = [pad1], [pad2]
    body = O("PartDesign::Body", "Body", Group=[sk1, pad1, sk2, pad2, sk3])
    for o in (sk1, sk2, sk3, pad1, pad2):
        o.InList = o.InList + [body]
    return D([body, sk1, pad1, sk2, pad2, sk3]), body


class SketchKindNames(unittest.TestCase):
    """Fix 1: models made up sketch_rectangle, circle, line; a rectangle is one item."""

    def test_a_made_up_name_points_to_sketch_add_with_a_worked_item(self):
        got = run('''
    out = {}
    for n in ("sketch_rectangle", "circle", "Sketcher_CreateCircle", "sketch_spline", "draw_rounded_rectangle", "sketch_polyline", "pd_zzz"):
        out[n] = call(n, {})[1]["error"]["message"]
    from agentlink import protocol
    out["kinds"] = protocol.sketch_kinds(srv)
    out["examples"] = {k: protocol.kind_example(srv, k) for k in out["kinds"]}
    out["does"] = call("tool_find", {"words": "rectangle sketch"})[1]
    out["batch"] = call("batch", {"calls": [{"tool": "sketch_circle", "arguments": {}}]})[1]
    print(json.dumps(out))
''')
        m = got["sketch_rectangle"]
        self.assertIn('use sketch_add with items [{ kind: "rectangle", … }]', m)
        self.assertIn('{"tool": "sketch_add", "arguments": {"items": [{"kind": "rectangle", "center": [0, 0], "size": [40, 20]}]}}', m)
        self.assertIn('kind: "circle"', got["circle"])
        self.assertIn('"radius": 10', got["circle"])
        self.assertIn('kind: "circle"', got["Sketcher_CreateCircle"])
        self.assertIn('kind: "bspline"', got["sketch_spline"])
        self.assertIn('kind: "rounded_rectangle"', got["draw_rounded_rectangle"])
        self.assertIn('"radius": 4', got["draw_rounded_rectangle"])  # under half the short side
        self.assertIn('kind: "polyline"', got["sketch_polyline"])
        self.assertNotIn("sketch_add with items", got["pd_zzz"])
        # Each worked item has only fields that the card names for its kind.
        for kind, ex in got["examples"].items():
            if ex is not None:
                self.assertEqual(ex["kind"], kind)
                self.assertLessEqual(set(ex) - {"kind"}, set(got["kinds"][kind]), kind)
        self.assertIsNotNone(got["examples"]["slot"])
        # The one line tool_find gives names the main kinds.
        does = next(h["does"] for h in got["does"]["tools"] if h["tool"] == "sketch_add")
        self.assertTrue(does.startswith("Add geometry to a sketch: rectangle, circle, line, arc, slot, polygon"), does)
        # In a batch too, on the refused call.
        self.assertIn('kind: "circle"', got["batch"]["refused"]["error"])


class NoListedInFind(unittest.TestCase):
    """Fix 2: "listed": false was read as "not available"."""

    def test_find_hits_and_cards_have_no_listed(self):
        got = run('''
    print(json.dumps({"find": call("tool_find", {"words": "pad"})[2], "card": call("tool_find", {"tool": "pd_pad"})[2],
                      "both": call("tool_find", {"queries": ["fillet", "pd_pad"]})[2]}))
''')
        for k, text in got.items():
            self.assertNotIn('"listed"', text, k)


class BatchOrder(unittest.TestCase):
    """Fix 3: a model took the calls of a batch to run in parallel."""

    def test_description_guide_and_answer_say_one_at_a_time(self):
        from agentlink import staticbase

        self.assertIn("one at a time, in order", staticbase.ste_descriptions()["batch"])
        with open(os.path.join(ROOT, "agentlink", "guides", "batch.md"), encoding="utf-8") as f:
            self.assertIn("one at a time, in order", f.read())
        got = run('''
    first = call("batch", {"calls": [mk("A")]})[1]
    second = call("batch", {"calls": [mk("B")]})[1]
    print(json.dumps({"first": first, "second": second, "desc": srv.tools["batch"].description}))
''')
        self.assertIn("one at a time, in order", got["desc"])
        self.assertIn("one at a time, in order", got["first"]["order"])
        # Said once a conversation; later answers name it in saidBefore.
        self.assertNotIn("order", got["second"])
        self.assertIn("order", json.dumps(got["second"].get("saidBefore")))


class PickExample(unittest.TestCase):
    """Fix 4: option 1 was doc_new, and the example filled length."""

    def test_the_example_fits_option_one(self):
        # The classic list's short form (the static list shows a batch call: test_connect_1124).
        from unittest import mock

        doc_new = {"step": 0, "list": [{"n": 1, "tool": "doc_new", "args": {}, "ask": [{"arg": "name"}]}]}
        with mock.patch.dict(os.environ, {"AGENTLINK_TOOLLIST": "classic"}):
            got = options.public(doc_new)["pick"]
        self.assertEqual(got, 'pick { option: 1, fill: { name: "Part" } } runs option 1; the text "1, Part" also works')
        pad = {"step": 3, "list": [{"n": 1, "tool": "pd_pad", "args": {"sketch": "Sketch 2"}, "ask": [{"arg": "length", "unit": "mm", "sample": 10}]}]}
        self.assertEqual(options.pick_how(pad, static=False), 'pick { option: 1, fill: { length: 10 } } runs option 1; the text "1, 10mm" also works')
        none = {"step": 3, "list": [{"n": 1, "tool": "body_check", "args": {}}]}
        self.assertEqual(options.pick_how(none, static=False), "pick { option: 1 } runs option 1")
        # A label with a space stays one value in the option line.
        self.assertEqual(options.option_words(pad["list"][0]), '1 pd_pad sketch="Sketch 2" ask length mm')


class ConnectText(unittest.TestCase):
    """Fix 5: small models put every optional batch field in their first batch."""

    def test_only_the_basic_batch_form_at_connect(self):
        texts = run('''
    print(json.dumps([tools.instructions(True, False, static=True), tools.instructions(True, True, static=False)]))
''')
        for text in texts:
            self.assertIn("batch { calls: [{ tool, arguments }] }", text)
            self.assertIn('guide_read { topic: "batch" }', text)
            for field in ("$from", "$file", "build: ", "(writeTo)", "lines", "record_read"):
                self.assertNotIn(field, text, field)
        with open(os.path.join(ROOT, "agentlink", "guides", "batch.md"), encoding="utf-8") as f:
            guide = f.read()
        for field in ("$from", "$file", 'build: "end"', "lines:", "record_read {", "writeTo:", "rollback: true", "The basic form"):
            self.assertIn(field, guide, field)

    def test_a_batch_refused_whole_says_nothing_ran_and_gives_the_basic_form(self):
        got = run('''
    print(json.dumps({"read": call("batch", {"read": "batches/x.json", "calls": [mk("A")]}), "labels": labels()}))
''')
        err, body, _text = got["read"]
        self.assertTrue(err)
        self.assertIn("Nothing was run.", body["error"]["message"])
        self.assertIn("The basic form: batch { calls: [{ tool, arguments }] }.", body["error"]["message"])
        self.assertNotIn("A", got["labels"])


class LiveNames(unittest.TestCase):
    """Fix 6: models lost track of names after refusals."""

    def test_bodies_features_and_the_sketch_each_uses(self):
        doc, _body = body_doc()
        self.assertEqual(livenames.names(doc), {"Body": ["Sketch→Pad", "Sketch 2→Pad 2", "Sketch 3 (not used)"]})

    def test_capped_for_a_big_document(self):
        feats = [O("PartDesign::Fillet", f"F{i}") for i in range(30)]
        body = O("PartDesign::Body", "Body", Group=feats)
        got = livenames.names(D([body] + feats))["Body"]
        self.assertEqual(len(got), livenames.MAX_ITEMS + 1)
        self.assertEqual(got[0], f"… {30 - livenames.MAX_ITEMS} before")
        self.assertEqual(got[-1], "F29")

    def test_outside_a_body(self):
        sk = O("Sketcher::SketchObject", "Sketch")
        ext = O("Part::Extrusion", "Extrude", Base=sk)
        sk.InList = [ext]
        free = O("Sketcher::SketchObject", "Sketch001", "Sketch 2")
        self.assertEqual(livenames.names(D([sk, ext, free])), {"(no body)": ["Sketch→Extrude", "Sketch 2 (not used)"]})
        self.assertIsNone(livenames.names(D([])))
        self.assertIsNone(livenames.names(None))

    def test_changing_answers_refusals_and_a_batch_end_with_now(self):
        got = run('''
    out = {}
    out["first"] = call("probe_make", {"name": "A", "fail": True})
    out["change"] = call("probe_make", {"name": "B"})
    out["read"] = call("tool_groups", {})
    out["batch"] = call("batch", {"calls": [mk("C"), mk("D", fail=True), mk("E")]})
    out["unknown"] = call("sketch_rectangle", {})
    out["second"] = call("probe_make", {"name": "F", "fail": True})
    print(json.dumps(out))
''')
        err, first, _ = got["first"]
        self.assertTrue(err)
        # The first answer of the conversation orients, also when it is a refusal.
        self.assertIn("whereYouAre", first)
        self.assertNotIn("whereYouAre", got["second"][1])
        err, change, text = got["change"]
        self.assertFalse(err)
        self.assertEqual(change["now"], {"(no body)": ["B"]})
        self.assertEqual(list(change)[-1], "now")  # the answer ends on it
        self.assertNotIn("now", got["read"][1])  # a read changes nothing
        self.assertEqual(got["batch"][1]["now"], {"(no body)": ["B", "C"]})
        self.assertEqual(got["unknown"][1]["now"], {"(no body)": ["B", "C"]})
        self.assertEqual(got["second"][1]["now"], {"(no body)": ["B", "C"]})

    def test_facts_and_options_name_objects_by_label(self):
        doc, body = body_doc()
        f = nexthint.facts(doc, {"sketch": {"name": "Sketch 3", "obj": "Sketch002", "dof": 2}, "editing": "sketch"})
        self.assertEqual((f["bodyName"], f["sketchName"], f["editSketch"]), ("Body", "Sketch 3", "Sketch 3"))
        body.Tip = body.Group[3]
        body.Group = body.Group[:4]
        f = nexthint.facts(D(doc.Objects[:5]), {})
        self.assertEqual(f["tipName"], "Pad 2")
        # The live names and the facts agree: the same labels.
        self.assertIn("Sketch 2→Pad 2", livenames.names(D(doc.Objects[:5]))["Body"])


class BatchKeepsWhatRan(unittest.TestCase):
    """Fix 7 (owner decision, 23 Nov): a refused call keeps the calls before it."""

    def test_a_refusal_keeps_what_ran_and_names_done_refused_and_not_run(self):
        got = run('''
    undo0 = s.doc.UndoCount
    r = call("batch", {"calls": [mk("A"), mk("B"), mk("C"), mk("D", fail=True), mk("E"), mk("F")]})
    print(json.dumps({"r": r, "labels": labels(), "undo": s.doc.UndoCount - undo0}))
''')
        err, b, _ = got["r"]
        self.assertFalse(err)
        self.assertEqual(b["done"], [0, 1, 2])
        self.assertEqual({k: b["refused"][k] for k in ("call", "tool", "code", "kind")}, {"call": 3, "tool": "probe_make", "code": "invalid_input", "kind": "fixable"})
        self.assertIn("fail: told to refuse.", b["refused"]["error"])
        self.assertEqual((b["notRun"], b["next"]), ([4, 5], 3))
        self.assertIn("Calls 0, 1, 2 (probe_make, probe_make, probe_make) ran and stay: do not send them again.", b["note"])
        self.assertIn("in order: probe_make (fixed), probe_make, probe_make. Leave start out.", b["note"])
        self.assertEqual((b["result"], b["refused"]["status"]), ("kept", "not_started"))
        self.assertNotIn("outcome", b)
        self.assertEqual([x for x in got["labels"] if x in "ABCDEF"], ["A", "B", "C"])
        self.assertEqual(got["undo"], 3)  # each call its own undo step
        self.assertNotIn("undone", b)

    def test_a_form_error_refuses_only_its_call(self):
        got = run('''
    out = {}
    out["field"] = call("batch", {"calls": [mk("A"), {"tool": "probe_make", "arguments": {"name": "B", "bogus": 1}}, mk("C")]})
    out["shape"] = call("batch", {"calls": [mk("D"), {"arguments": {"name": "E"}}, mk("F")]})
    out["tool"] = call("batch", {"calls": [mk("G"), {"tool": "no_such_tool", "arguments": {}}]})
    out["labels"] = labels()
    out["on"] = call("batch", {"stopOnError": False, "calls": [{"tool": "no_such_tool", "arguments": {}}, mk("H")]})
    print(json.dumps(out))
''')
        b = got["field"][1]
        self.assertEqual((b["done"], b["refused"]["call"], b["notRun"]), ([0], 1, [2]))
        self.assertIn("input.bogus", b["refused"]["error"])
        b = got["shape"][1]
        self.assertEqual((b["done"], b["refused"]["call"], b["notRun"]), ([0], 1, [2]))
        self.assertIn("calls.1 has arguments and no tool.", b["refused"]["error"])
        b = got["tool"][1]
        self.assertEqual((b["done"], b["refused"]["call"], b["refused"]["code"]), ([0], 1, "not_found"))
        self.assertEqual([x for x in got["labels"] if len(x) == 1], ["A", "D", "G"])
        b = got["on"][1]
        self.assertEqual((b["done"], b["refusedCalls"]), ([1], [0]))

    def test_rollback_true_is_all_or_nothing_as_before(self):
        got = run('''
    out = {}
    out["form"] = call("batch", {"rollback": True, "calls": [mk("A"), {"tool": "no_such_tool", "arguments": {}}]})
    out["labelsForm"] = labels()
    out["refused"] = call("batch", {"rollback": True, "calls": [mk("B"), mk("C", fail=True)]})
    print(json.dumps(out))
''')
        err, e, _ = got["form"]
        self.assertTrue(err)
        self.assertIn("nothing was run", e["error"]["message"].lower())
        self.assertIn("The basic form: batch { calls: [{ tool, arguments }] }.", e["error"]["message"])
        self.assertNotIn("A", got["labelsForm"])
        err, b, _ = got["refused"]
        self.assertFalse(err)
        self.assertEqual(b["refused"]["call"], 1)
        self.assertEqual(b["done"], [])  # taken back
        self.assertEqual(b["takenBack"], [0])


if __name__ == "__main__":
    unittest.main()

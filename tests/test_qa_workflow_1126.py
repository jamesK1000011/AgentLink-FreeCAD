# SPDX-License-Identifier: LGPL-2.1-or-later
# Blind QA of nine local-model runs (26 Nov, series s1126b), the workflow
# fixes:
#   1. a resent batch refused as a repeat names every call of it that ran
#      before and is kept, and its next list leaves them out (fix 6);
#   2. a refusal that names a document or an object, a short time after
#      FreeCAD started and with nothing made yet, says when it started (fix 12);
#   3. a refusal of a bad input shows the card's ready value of it (fix 10);
#   4. noise: the fixable sentence only where the error names an input; no
#      readAs for an empty value; "Leave start out" only when start was
#      sent; the sketchNote on sketch tools only; the start document's
#      doc_new option agrees with the note; a pocket's reversed words not
#      beside the side words.
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import examples, protocol  # noqa: E402
from agentlink.protocol import KIND_WORDS, Tool, names_input, set_kind  # noqa: E402
from test_hubfix2 import in_a_process  # noqa: E402
from test_local_fixes_1123 import run  # noqa: E402
from test_qa_sketch_1124 import SERVER as QA_SERVER  # noqa: E402


# A batch as the QA's: doc_new first, so the repeat guard catches the resent list at call 0.
RESEND = QA_SERVER + '''
    from agentlink.protocol import ToolError
    def picky(a):
        if a.get("name"):
            raise ToolError("invalid_input", "input.name: not taken here.")
        return make(a)
    srv.tools["probe_pad"] = Tool("probe_pad", "Pad.", SCH, picky, changes=True)
    def c(tool, **kw):
        return {"tool": tool, **kw}
'''


class AResentBatch(unittest.TestCase):
    def test_the_note_names_what_ran_and_sends_only_the_rest(self):
        got = in_a_process(RESEND + '''
    out = {}
    out["first"] = call("batch", {"calls": [c("doc_new", name="P"), c("probe_make", x=1), c("probe_make", x=2), c("probe_pad", name="Base"), c("probe_make", x=3)]})[1]
    again = [c("doc_new", name="P"), c("probe_make", x=1), c("probe_make", x=2), c("probe_pad", x=5), c("probe_make", x=3)]
    out["again"] = call("batch", {"calls": again})[1]
    out["third"] = call("batch", {"calls": again})[1]
    out["docs"] = len(docs)
    print(json.dumps(out))
''')
        self.assertEqual(got["first"]["done"], [0, 1, 2])
        b = got["again"]
        self.assertEqual(b["refused"]["call"], 0)
        self.assertTrue(b["refused"]["error"].startswith(protocol.AGAIN_WORDS), b["refused"]["error"])
        note = b["note"]
        self.assertIn("Calls 0-2 (doc_new, probe_make, probe_make) ran before and are kept: do not send them again.", note)
        self.assertIn("Next: send a new batch with only calls 3, 4, in order: probe_pad, probe_make.", note)
        self.assertNotIn("(fixed)", note)
        # The record stays after a refused batch that made nothing: the same list again is caught again.
        self.assertTrue(got["third"]["refused"]["error"].startswith(protocol.AGAIN_WORDS))
        self.assertIn("only calls 3, 4", got["third"]["note"])

    def test_a_list_of_only_calls_that_ran(self):
        got = in_a_process(RESEND + '''
    calls = [c("doc_new", name="Q"), c("probe_make", x=1)]
    call("batch", {"calls": calls})
    print(json.dumps(call("batch", {"calls": calls})[1]))
''')
        self.assertIn("Calls 0, 1 (doc_new, probe_make) ran before and are kept", got["note"])
        self.assertIn("Next: nothing of this list is left to send.", got["note"])

    def test_a_plain_refusal_keeps_its_note(self):
        _, b, _ = run('''
    print(json.dumps(call("batch", {"calls": [mk("A"), mk("B", fail=True), mk("C")]})))
''')
        self.assertNotIn("last batch", b["note"])
        self.assertIn("Next: send a new batch with these calls, in order: probe_make (fixed), probe_make.", b["note"])


class StartWords(unittest.TestCase):
    def test_only_when_start_was_sent(self):
        got = run('''
    out = {"no": call("batch", {"calls": [mk("A"), mk("B", fail=True)]})[1]["note"],
           "yes": call("batch", {"start": 0, "calls": [mk("C"), mk("D", fail=True)]})[1]["note"]}
    print(json.dumps(out))
''')
        self.assertNotIn("start", got["no"].split("Next:")[1])
        self.assertIn("Leave start out", got["yes"])


class FixableSentence(unittest.TestCase):
    def test_only_where_the_error_names_an_input(self):
        self.assertEqual(KIND_WORDS["fixable"], "Change what the error names and call again.")
        named = set_kind({"code": "invalid_input", "message": "input.depth: a number, not text."})
        self.assertTrue(named["message"].endswith(KIND_WORDS["fixable"]))
        lead = set_kind({"code": "invalid_input", "message": "edges: no edge there."})
        self.assertTrue(lead["message"].endswith(KIND_WORDS["fixable"]))
        plain = set_kind({"code": "invalid_state", "message": "No strength study: fea_setup { body } first."})
        self.assertEqual(plain["message"], "No strength study: fea_setup { body } first.")
        self.assertEqual(plain["kind"], "fixable")
        self.assertFalse(names_input("Pad (PartDesign::Pad) failed: it broke."))
        # The words before 26 Nov are taken out where a message still carries them.
        self.assertEqual(protocol.strip_kind("x: y. " + protocol.OLD_KIND_WORDS[0]), "x: y.")


class CardExample(unittest.TestCase):
    def tool(self, name, props):
        return Tool(name, "", {"type": "object", "properties": {k: {"type": "string"} for k in props}}, lambda a: {})

    def test_the_cards_ready_value_once(self):
        t = self.tool("pd_fillet", ("edges", "radius"))
        w = protocol.example_words(t, "invalid_input", "edges: 'vertical' is not an edge here.")
        self.assertTrue(w.startswith(" Example: edges: "), w)
        self.assertIn('"axis"', w)
        self.assertIn('"line"', w)
        # once: a message with an example already gets none
        self.assertEqual(protocol.example_words(t, "invalid_input", "edges: bad." + w), "")
        # only for a bad input, and only for a field with a ready value
        self.assertEqual(protocol.example_words(t, "failed", "edges: bad."), "")
        self.assertEqual(protocol.example_words(t, "invalid_input", "input.radius: a number, not text."), "")

    def test_a_worked_value_of_the_example(self):
        t = self.tool("sketch_new", ("plane", "body"))
        self.assertEqual(protocol.example_words(t, "invalid_input", "input.plane: one of XY, XZ, YZ — not text of 3 characters."), ' Example: plane: "XY".')
        # a value filled from the document is no ready value
        self.assertIsNone(examples.field_example("sketch_new", "body"))
        self.assertIsNone(examples.field_example("pd_fillet", "radius"))

    def test_on_a_refusal_through_the_server(self):
        got = in_a_process(QA_SERVER + '''
    from agentlink.protocol import ToolError
    def bad(a):
        raise ToolError("invalid_input", "edges: 'vertical' is not an edge here.")
    srv.tools["pd_fillet"] = Tool("pd_fillet", "Round.", {"type": "object", "properties": {"edges": {}}, "additionalProperties": False}, bad, changes=True)
    print(json.dumps(msg(call("pd_fillet", {"edges": "vertical"}))))
''')
        self.assertEqual(got.count("Example: edges: "), 1, got)


class StartedWords(unittest.TestCase):
    def test_a_missing_name_soon_after_the_start(self):
        got = in_a_process(QA_SERVER + '''
    from agentlink.protocol import ToolError
    def gone(a):
        raise ToolError("not_found", "no object 'LidBody' in Part.")
    srv.tools["probe_get"] = Tool("probe_get", "Read.", {"type": "object", "properties": {"object": {"type": "string"}}}, gone)
    out = {"made": msg(call("probe_get", {"object": "LidBody"}))}
    for d in list(docs.values()) if isinstance(docs, dict) else list(docs):
        d.Objects = []
    out["empty"] = msg(call("probe_get", {"object": "LidBody"}))
    out["noName"] = msg(call("probe_get", {}))
    out["otherName"] = msg(call("probe_get", {"object": "Other"}))  # the refusal does not name it
    print(json.dumps(out))
''')
        self.assertNotIn("FreeCAD started at", got["made"])
        self.assertIn("FreeCAD started at ", got["empty"])
        self.assertIn("and nothing is made in it yet: documents and objects from before then are not open", got["empty"])
        self.assertNotIn("FreeCAD started at", got["noName"])
        self.assertNotIn("FreeCAD started at", got["otherName"])


class Noise(unittest.TestCase):
    def test_no_read_as_for_an_empty_value(self):
        a = {"words": "", "tool": "pd_pad"}
        said = protocol.check_input({"type": "object", "properties": {"words": {"type": "string"}, "tool": {"type": "string"}}}, a, "tool_find")
        self.assertEqual((a, said), ({"tool": "pd_pad"}, []))

    def test_sketch_note_on_sketch_tools_only(self):
        got = in_a_process(QA_SERVER + '''
    from agentlink import once
    once.health_said = lambda s: {"sketchNote": "N degrees of freedom", "broken": "history_undo"}
    out = {}
    for n in ("history_undo", "sketch_add"):
        r = call("tool_find", {"tool": n})[1]
        cards = r.get("tools") or [r]
        out[n] = (cards[0].get("said") or {}).get("health")
    print(json.dumps(out))
''')
        self.assertEqual(got["history_undo"], {"broken": "history_undo"})
        self.assertEqual(got["sketch_add"], {"sketchNote": "N degrees of freedom", "broken": "history_undo"})

    def test_the_start_documents_option_agrees_with_the_note(self):
        got = in_a_process(QA_SERVER + '''
    from agentlink import options
    s.doc = tools.new_start_doc()
    o = options.theirs_first(s, srv)
    s.doc = new("Theirs")
    p = options.theirs_first(s, srv)
    print(json.dumps([o["why"], p["why"]]))
''')
        self.assertIn("is an empty start document that Agent Link made", got[0])
        self.assertNotIn("the person's", got[0])
        self.assertTrue(got[1].endswith("is the person's"), got[1])

    def test_pocket_reversed_words_not_beside_the_side_words(self):
        got = in_a_process(QA_SERVER + '''
    from agentlink.families import pd_common as pc
    from agentlink.protocol import ToolError
    pc.newly_broken = lambda doc: []
    pc.fit_hint = lambda h, e=None: h
    pc.body_reading = lambda b: {"volume": 100.0}
    pc.where_went = lambda *a: {}
    HINT = "Check the sketch with sketch_state (closed wires, no open vertices); reversed: true goes the other way into the body."
    out = {}
    for name, side in (("beside", "The sketch S's outline is beside the body, not over it: x 50 to 60. Move the outline over the body (its position, not its direction)."),
                       ("way", "The sketch S's normal is +z, and the body is on the side its normal points to. reversed: true sends the cut that way."),
                       ("none", "")):
        pc.cut_side_words = lambda f, b, side=side: side
        f = Obj(D, "Pocket")
        f.TypeId = "PartDesign::Pocket"
        D.recompute = lambda: None
        try:
            pc.settle(s, Obj(D, "Body"), f, "pd_pocket", before=100.0, must_change="cut", hint=HINT)
        except ToolError as e:
            out[name] = e.message
    print(json.dumps(out))
''')
        self.assertNotIn("goes the other way", got["beside"])
        self.assertIn("Check the sketch with sketch_state (closed wires, no open vertices).", got["beside"])
        self.assertEqual(got["way"].count("reversed: true"), 1, got["way"])
        self.assertIn("goes the other way", got["none"])


if __name__ == "__main__":
    unittest.main()

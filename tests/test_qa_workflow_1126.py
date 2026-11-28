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

    def test_a_plain_refusal_keeps_its_note(self):
        _, b, _ = run('''
    print(json.dumps(call("batch", {"calls": [mk("A"), mk("B", fail=True), mk("C")]})))
''')
        self.assertNotIn("last batch", b["note"])
        self.assertIn("Call 2 (probe_make) was not run.", b["note"])


class StartWords(unittest.TestCase):
    def test_only_when_start_was_sent(self):
        got = run('''
    out = {"no": call("batch", {"calls": [mk("A"), mk("B", fail=True)]})[1]["note"],
           "yes": call("batch", {"start": 0, "calls": [mk("C"), mk("D", fail=True)]})[1]["note"]}
    print(json.dumps(out))
''')
        self.assertNotIn("start", got["no"])
        self.assertIn("start counts in the list that is sent", got["yes"])


class FixableSentence(unittest.TestCase):
    def test_only_where_the_error_names_an_input(self):
        self.assertEqual(KIND_WORDS["fixable"], "")  # 27 Nov live proof: no advice sentence
        named = set_kind({"code": "invalid_input", "message": "input.depth: a number, not text."})
        self.assertEqual(named["message"], "input.depth: a number, not text.")
        lead = set_kind({"code": "invalid_input", "message": "edges: no edge there."})
        self.assertEqual(lead["message"], "edges: no edge there.")
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
    def test_an_empty_value_is_read_as_left_out_and_said(self):
        # 27 Nov, facts only: an input that the hub drops is named each time
        a = {"words": "", "tool": "pd_pad"}
        said = protocol.check_input({"type": "object", "properties": {"words": {"type": "string"}, "tool": {"type": "string"}}}, a, "tool_find")
        self.assertEqual((a, said), ({"tool": "pd_pad"}, ["words: an empty value, read as left out"]))

    def test_sketch_note_on_sketch_tools_only(self):
        got = in_a_process(QA_SERVER + '''
    from agentlink import once
    once.health_said = lambda s: {"sketchNote": "N degrees of freedom", "broken": "history_undo"}
    out = {}
    for n in ("history_undo", "sketch_add"):
        r = call("tool_find", {"card": n})[1]
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

if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
"""Refusals that help a small model recover (22 Nov, research on small
local models): every refusal has a kind and its fixed sentence; a batch
refusal describes the call and does not paste it back; the server stops a
server keeps no count of equal refusals (27 Nov, facts only). Plain Python: no FreeCAD."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import protocol  # noqa: E402
from agentlink.protocol import (KIND_WORDS, Server, Tool, ToolError, failing_keys,  # noqa: E402
                                refusal_kind, set_kind)

FIX = KIND_WORDS["fixable"]
RETRY = KIND_WORDS["retry"]
STOP = KIND_WORDS["stop"]


def call(srv, name, args):
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
    return r, json.loads(r["content"][0]["text"])


class Kinds(unittest.TestCase):
    def test_words_are_fixed(self):
        self.assertEqual(FIX, "Change what the error names and call again.")
        self.assertEqual(RETRY, "")  # 27 Nov review: no guessed cause; the error's own words stand
        self.assertEqual(STOP, "Do not call it again. Report what happened.")

    def test_kind_per_code(self):
        self.assertEqual(refusal_kind("invalid_input", "input.x: required."), "fixable")
        self.assertEqual(refusal_kind("not_found", "sketch 'S': no such sketch."), "fixable")
        self.assertEqual(refusal_kind("failed", "pd_pad failed: the shape is not valid."), "fixable")
        self.assertEqual(refusal_kind("invalid_state", "No 3D view in front."), "fixable")

    def test_transient_is_retry(self):
        for words in ("The window is busy.", "The call timed out after 30 s.", "The view is not ready.", "The file is locked."):
            self.assertEqual(refusal_kind("failed", words), "retry", words)
        self.assertEqual(refusal_kind("busy", "The window took no queued call in 5 s."), "retry")
        # A dialog holds the window: the words say what closes it, so not a plain retry.
        self.assertEqual(refusal_kind("busy", "FreeCAD's window has a menu or dialog open: X."), "fixable")

    def test_approval_and_hold_are_stop(self):
        for code in ("held_person_editing", "not_allowed", "refused", "denied"):
            self.assertEqual(refusal_kind(code, "Held: the person is editing Body."), "stop", code)

    def test_sentence_once_at_the_end(self):
        err = set_kind({"code": "invalid_input", "message": "input.x: required."})
        self.assertEqual(err["kind"], "fixable")
        self.assertEqual(err["message"], "input.x: required. " + FIX)
        set_kind(err)
        self.assertEqual(err["message"].count(FIX), 1)
        # Wrapped words (a fast block's step) keep one sentence, at the end.
        err = set_kind({"code": "failed", "message": "step do.1 (pd_pad): input.x: required. " + FIX + " Ran before it: do.0."})
        self.assertTrue(err["message"].endswith("Ran before it: do.0. " + FIX), err["message"])
        self.assertEqual(err["message"].count(FIX), 1)

    def test_server_refusal_keeps_code_and_outcome(self):
        r = Server.refusal("held_person_editing", "Held: the person is editing Pad.", outcome="not_started")
        self.assertTrue(r["isError"])
        err = json.loads(r["content"][0]["text"])["error"]
        self.assertEqual((err["code"], err["kind"], err["status"]), ("held_person_editing", "stop", "not_started"))
        self.assertTrue(err["message"].startswith("Held: the person is editing Pad."))
        self.assertTrue(err["message"].endswith(STOP))


class Extractor(unittest.TestCase):
    def test_places(self):
        self.assertEqual(failing_keys("input.depth: not a known field — the fields here: length."), ("input.depth",))
        self.assertEqual(failing_keys("constraints[2]: kind, point: not fields."), ("constraints[2]",))
        self.assertEqual(failing_keys("calls.0: { tool, arguments }. calls.0 has arguments and no tool."), ("calls.0",))
        self.assertEqual(failing_keys("step do.3 (pd_pad): input.length: required."), ("do.3", "input.length"))
        self.assertEqual(failing_keys("input.a: required. input.b: a number."), ("input.a", "input.b"))

    def test_lead_field_and_words(self):
        self.assertEqual(failing_keys("rectangle: size [w, h] (step 4)."), ("rectangle",))
        self.assertEqual(failing_keys("The shape is 3 mm thin."), failing_keys("The shape is 5 mm thin."))

    def test_kind_sentence_is_not_a_key(self):
        self.assertEqual(failing_keys("input.x: required. " + FIX), ("input.x",))


class BatchShape(unittest.TestCase):
    """The batch tool's refusal of a call that is not { tool, <inputs> },
    and a refused step's row, through the hub's own tools (stand-ins)."""

    def setUp(self):
        try:
            from agentlink import tools  # noqa: F401
        except ImportError as e:
            self.skipTest(f"needs FreeCAD: {e}")

    def test_described_not_echoed(self):
        from agentlink import callshape

        class Srv:
            tools = {}

        def said(c, i):
            try:
                callshape.steps_of(Srv, c, f"calls.{i}", "batch")
            except callshape.Refused as e:
                return e.words
            self.fail("not refused")

        sent = {"plane": "XZ", "name": "Sketch_unusual_name_42"}
        words = said(sent, 0)
        self.assertIn('calls.0: a step has no "tool"', words)
        self.assertNotIn(json.dumps(sent), words)
        self.assertNotIn("Sketch_unusual_name_42", words)
        self.assertIn("calls.1 is a list of 2 items, not an object.", said([1, 2], 1))
        self.assertIn("not a tool's name", said({"tool": 5}, 2))


class BatchInAProcess(unittest.TestCase):
    """A real batch on the hub's stand-ins (tests/test_hubfix2.in_a_process)."""

    def test_batch_refusal_describes_and_a_refused_row_has_kind(self):
        import tempfile

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from test_hubfix2 import in_a_process
        from test_hubfix4 import SETUP

        out = tempfile.mkdtemp(prefix="agentlink-kinds-")
        got = in_a_process(SETUP + '''
    from agentlink import tools
    s = tools.Session(out_dir=%r)
    srv = tools.build_server(s, lean=False)
    def call(name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
        return [r.get("isError", False), json.loads(r["content"][0]["text"])]
    shape = call("batch", {"calls": [{"plane": "XZ", "label": "Odd_label_77"}]})
    rows = call("batch", {"calls": [{"tool": "sketch_new", "bogus": 1}], "rollback": False, "stopOnError": False})
    print(json.dumps({"shape": shape, "rows": rows}))
''' % out)
        err, body = got["shape"]
        # A call with a wrong form is refused by itself, in its order (23 Nov).
        self.assertFalse(err)
        self.assertEqual((body["done"], body["notRun"], body["refused"]["call"]), ([], [], 0))
        e = body["results"][0]["error"]
        self.assertEqual((e["code"], e["kind"]), ("invalid_input", "fixable"))
        self.assertIn('calls.0 has no "tool": every call names its tool, and its inputs stand beside it.', e["message"])
        self.assertIn("The calls run in order", e["message"])
        self.assertIn('"tool": "sketch_new"', e["message"])  # the worked example stays
        self.assertNotIn("Odd_label_77", e["message"])
        self.assertNotIn('"XZ"', e["message"])
        self.assertIn("results", got["rows"][1], got["rows"])
        row = got["rows"][1]["results"][0]
        self.assertFalse(row["ok"])
        self.assertEqual(row["error"]["kind"], "fixable")


class BatchShapeWords(unittest.TestCase):
    """The same, read from the source: tools.py needs FreeCAD to load."""

    def test_no_sent_echo_in_source(self):
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink", "tools.py"), encoding="utf-8").read()
        self.assertNotIn("was {sent}", src)
        self.assertIn("_cs.steps_of(", src)
        self.assertIn("The calls run in order", src)

    def test_batch_row_carries_kind(self):
        from agentlink.protocol import kinded

        row_err = kinded({"code": "invalid_input", "message": "calls.1 (pd_pad): input.a: required. The call was not run."})
        self.assertEqual(row_err["kind"], "fixable")
        # A row from a step's own refusal has its kind already: it stays.
        self.assertEqual(kinded({"code": "x", "kind": "stop", "message": "m"})["message"], "m")


class Describe(unittest.TestCase):
    def test_describe(self):
        from agentlink.protocol import describe, short_or_described

        self.assertEqual(describe("abc"), "text of 3 characters")
        self.assertEqual(describe([1, 2, 3]), "a list of 3 items")
        self.assertEqual(describe({"x": 1, "y": 2}), "an object with keys x, y")
        self.assertEqual(short_or_described("Xy"), "'Xy'")
        self.assertEqual(short_or_described("z" * 80), "text of 80 characters")

    def test_enum_refusal_does_not_paste_a_long_value(self):
        from agentlink.protocol import check_input

        with self.assertRaises(ToolError) as e:
            check_input({"type": "object", "properties": {"mode": {"type": "string", "enum": ["a", "b"]}}}, {"mode": "q" * 90})
        self.assertNotIn("q" * 90, e.exception.message)
        self.assertIn("text of 90 characters", e.exception.message)


if __name__ == "__main__":
    unittest.main()



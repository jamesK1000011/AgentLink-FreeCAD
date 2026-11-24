# SPDX-License-Identifier: LGPL-2.1-or-later
"""Refusals that help a small model recover (22 Nov, research on small
local models): every refusal has a kind and its fixed sentence; a batch
refusal describes the call and does not paste it back; the server stops a
tool after REPEAT_STOP refusals with no progress. Plain Python: no FreeCAD."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import protocol  # noqa: E402
from agentlink.protocol import (KIND_WORDS, REPEAT_STOP, Server, Tool, ToolError, failing_keys,  # noqa: E402
                                refusal_kind, set_kind)

FIX = KIND_WORDS["fixable"]
RETRY = KIND_WORDS["retry"]
STOP = KIND_WORDS["stop"]


def call(srv, name, args):
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
    return r, json.loads(r["content"][0]["text"])


class Kinds(unittest.TestCase):
    def test_words_are_fixed(self):
        self.assertEqual(FIX, "This call cannot succeed as written. The error says what to change; call the tool again with the corrected value.")
        self.assertEqual(RETRY, "Retrying the same call is expected to succeed.")
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


class Ladder(unittest.TestCase):
    def server(self, fn=None):
        def bad(a):
            missing = [k for k in ("a", "b", "c") if k not in a]
            if missing:
                raise ToolError("invalid_input", " ".join(f"input.{k}: required." for k in missing))
            return {"ok": True}

        obj = {"type": "object", "properties": {k: {"type": "number"} for k in ("a", "b", "c", "n")}}
        return Server("t", "0", [Tool("pd_pad", "pad.", obj, fn or bad, changes=True),
                                 Tool("get", "read.", obj, lambda a: (_ for _ in ()).throw(ToolError("invalid_input", "what: required.")))])

    def test_progress_resets_the_count(self):
        srv = self.server()
        _, one = call(srv, "pd_pad", {})
        self.assertNotIn("repeat", one["error"])
        _, two = call(srv, "pd_pad", {"n": 1})
        self.assertEqual(two["error"]["repeat"], 2)
        _, three = call(srv, "pd_pad", {"a": 1})  # a fixed: progress
        self.assertNotIn("repeat", three["error"])
        self.assertIn("Progress: 1 of 3 named problems fixed.", three["error"]["message"])
        self.assertTrue(three["error"]["message"].endswith(FIX))

    def test_reordered_keys_are_the_same_call(self):
        def fixed_words(a):
            raise ToolError("not_found", "Sketch 2 has no geometry.")

        srv = self.server(fixed_words)
        call(srv, "pd_pad", {"a": 1, "b": 2})
        _, two = call(srv, "pd_pad", {"b": 2, "a": 1})
        self.assertEqual(two["error"]["repeat"], 2)

    def test_same_call_new_reason_is_progress(self):
        # 1i (24 Nov, gpt-oss bracket): the same pd_pad call refused for two
        # different reasons is not "the same refusal".
        said = iter(["Linked shape object is empty: Sketch 2 has no geometry.", "Pad 2 added no material: it lies inside the body already."])

        def two_reasons(a):
            raise ToolError("invalid_state", next(said))

        srv = self.server(two_reasons)
        call(srv, "pd_pad", {"a": 5})
        _, two = call(srv, "pd_pad", {"a": 5})
        self.assertNotIn("repeat", two["error"])
        self.assertNotIn("same refusal", two["error"]["message"])

    def test_fifth_same_refusal_is_stop(self):
        srv = self.server()
        for n in range(1, REPEAT_STOP):
            _, got = call(srv, "pd_pad", {"n": n})
            self.assertNotEqual(got["error"]["kind"], "stop", n)
        r, five = call(srv, "pd_pad", {"n": 99})
        self.assertTrue(r["isError"])
        err = five["error"]
        self.assertEqual((err["kind"], err["code"], err["repeat"]), ("stop", "invalid_input", 5))
        self.assertEqual(err["message"], "No progress after 5 tries of pd_pad. Do not call it again. Report it: input.a: required.")
        self.assertNotIn("person", err["message"])

    def test_hint_names_the_place_again(self):
        srv = self.server()
        for n in range(3):
            _, got = call(srv, "pd_pad", {"n": n})
        m = got["error"]["message"]
        self.assertIn("Refused the same way 3 times: input.a is still wrong.", m)
        self.assertIn("Try this:", m)
        self.assertTrue(m.endswith(FIX))

    def test_success_clears(self):
        srv = self.server()
        for n in range(4):
            call(srv, "pd_pad", {"n": n})
        r, ok = call(srv, "pd_pad", {"a": 1, "b": 2, "c": 3})
        self.assertFalse(r.get("isError"))
        _, again = call(srv, "pd_pad", {})
        self.assertNotIn("repeat", again["error"])

    def test_reads_never_stop(self):
        srv = self.server()
        for _ in range(REPEAT_STOP + 1):
            _, got = call(srv, "get", {})
        self.assertNotEqual(got["error"]["kind"], "stop")
        self.assertNotIn("No progress", got["error"]["message"])

    def test_thresholds_are_constants(self):
        self.assertEqual((protocol.REPEAT_SAME, protocol.REPEAT_HINT, protocol.REPEAT_STOP), (2, 3, 5))


class BatchShape(unittest.TestCase):
    """The batch tool's refusal of a call that is not { tool, arguments },
    and a refused step's row, through the hub's own tools (stand-ins)."""

    def setUp(self):
        try:
            from agentlink import tools  # noqa: F401
        except ImportError as e:
            self.skipTest(f"needs FreeCAD: {e}")

    def test_described_not_echoed(self):
        from agentlink.tools import _call_shape

        sent = {"arguments": {"plane": "XZ", "name": "Sketch_unusual_name_42"}}
        words = _call_shape(sent, 0)
        self.assertEqual(words, "calls.0 has arguments and no tool.")
        self.assertNotIn(json.dumps(sent), words)
        self.assertNotIn("Sketch_unusual_name_42", words)
        self.assertEqual(_call_shape([1, 2], 1), "calls.1 is a list of 2 items, not an object.")
        self.assertIn("not a tool's name", _call_shape({"tool": 5}, 2))


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
    shape = call("batch", {"calls": [{"arguments": {"plane": "XZ", "label": "Odd_label_77"}}]})
    rows = call("batch", {"calls": [{"tool": "job_start", "arguments": {"tool": "session_state"}}], "rollback": False, "stopOnError": False})
    print(json.dumps({"shape": shape, "rows": rows}))
''' % out)
        err, body = got["shape"]
        # A call with a wrong form is refused by itself, in its order (23 Nov).
        self.assertFalse(err)
        self.assertEqual((body["done"], body["notRun"], body["refused"]["call"]), ([], [], 0))
        e = body["results"][0]["error"]
        self.assertEqual((e["code"], e["kind"]), ("invalid_input", "fixable"))
        self.assertIn("calls.0 has arguments and no tool.", e["message"])
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
        self.assertIn("_call_shape(c, i)", src)
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

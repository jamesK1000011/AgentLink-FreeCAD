# SPDX-License-Identifier: LGPL-2.1-or-later
# One shape (24 Nov): the batch answer's result and each call's status (1f),
# next-step words that list the calls to send (1g), and the batch call form.
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_local_fixes_1123 import run  # noqa: E402

READ = '''
    srv.tools["probe_read"] = Tool("probe_read", "Read.", {"type": "object", "properties": {}}, lambda a: {"ok": 1})
'''


def _text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class ResultAndStatus(unittest.TestCase):
    def test_kept_from_the_rows_not_the_undo_count(self):
        # A call that went through but made no undo step in the start
        # document (doc_new moves the session) still makes the result kept.
        got = run(READ + '''
    print(json.dumps(call("batch", {"calls": [{"tool": "probe_read", "arguments": {}}, mk("X", fail=True)]})))
''')
        _, b, _ = got
        self.assertEqual(b["result"], "kept")
        self.assertEqual(b["done"], [0])
        self.assertNotIn("outcome", b)

    def test_ran_none_when_the_first_call_is_refused(self):
        _, b, _ = run('''
    print(json.dumps(call("batch", {"calls": [mk("X", fail=True), mk("Y")]})))
''')
        self.assertEqual((b["result"], b["done"], b["notRun"]), ("ran_none", [], [1]))
        self.assertEqual(b["refused"]["status"], "not_started")
        self.assertIn("Call 0 (probe_make) was refused; it changed nothing.", b["note"])
        self.assertIn("in order: probe_make (fixed), probe_make. Leave start out.", b["note"])

    def test_rollback_result_and_resend_list(self):
        _, b, _ = run('''
    print(json.dumps(call("batch", {"rollback": True, "calls": [mk("A"), mk("B", fail=True), mk("C")]})))
''')
        self.assertEqual(b["result"], "rolled_back")
        self.assertIn("Calls 0 (probe_make) were taken back (rollback: true).", b["note"])
        self.assertIn("in order: probe_make, probe_make (fixed), probe_make.", b["note"])

    def test_a_refused_row_has_status_not_outcome(self):
        _, b, _ = run('''
    print(json.dumps(call("batch", {"calls": [mk("A"), mk("B", fail=True)]})))
''')
        row = b["results"][1]
        self.assertNotIn("outcome", row["error"])
        self.assertEqual(row["error"]["status"], "not_started")

    def test_from_on_an_inline_list_says_leave_it_out(self):
        _, b, _ = run('''
    print(json.dumps(call("batch", {"start": 1, "calls": [mk("A"), mk("B"), mk("C", fail=True)]})))
''')
        self.assertIn("start counts in the list you send. In a new, shorter list, leave start out.", b["note"])

    def test_direct_refusal_has_status(self):
        _, b, _ = run('''
    print(json.dumps(call("probe_make", {"name": "A", "fail": True})))
''')
        self.assertEqual(b["error"]["status"], "not_started")
        self.assertNotIn("outcome", b["error"])


class Texts(unittest.TestCase):
    def test_no_from_next_for_inline_calls(self):
        root = os.path.join(os.path.dirname(HERE), "agentlink")
        ste, guide = (_text(os.path.join(root, *p)) for p in (("data", "ste.json"), ("guides", "batch.md")))
        self.assertNotIn("from: next continues", ste)
        self.assertNotIn("send the same calls with from: next", guide)


if __name__ == "__main__":
    unittest.main()


class BesideTool(unittest.TestCase):
    """1a (owner decision 1): exact card fields beside tool move inside
    arguments, said in readAs; wrappers, unknown keys and as are refused."""

    def test_an_exact_field_is_moved_and_said(self):
        b = run('''
    r = call("batch", {"calls": [{"tool": "probe_make", "name": "A"}]})
    print(json.dumps([r[0], r[1], labels()]))
''')
        err, ans, labs = b
        self.assertIn("A", labs)
        row = ans["results"][0]
        self.assertTrue(row["ok"])
        self.assertIn("calls.0: name was beside tool: read inside arguments. Put every input inside arguments.", row["readAs"])

    def test_a_wrapper_refuses_only_its_call(self):
        b = run('''
    print(json.dumps(call("batch", {"calls": [mk("A"), {"tool": "probe_make", "options": {"name": "B"}}, mk("C")]})))
''')
        b = b[1]
        self.assertEqual((b["done"], b["refused"]["call"]), ([0], 1))
        self.assertIn("options is not part of a call", b["refused"]["error"])
        self.assertIn("options holds name: put it inside arguments.", b["refused"]["error"])
        self.assertIn("The fields of probe_make: name, type, fail.", b["refused"]["error"])

    def test_given_twice(self):
        b = run('''
    out = {}
    out["other"] = call("batch", {"calls": [{"tool": "probe_make", "name": "A", "arguments": {"name": "B"}}]})
    out["same"] = call("batch", {"calls": [{"tool": "probe_make", "name": "C", "arguments": {"name": "C"}}]})
    print(json.dumps(out))
''')
        self.assertIn('name is given twice (beside tool: "A", in arguments: "B")', b["other"][1]["refused"]["error"])
        self.assertTrue(b["same"][1]["results"][0]["ok"])
        self.assertIn("the same as in arguments: dropped", b["same"][1]["results"][0]["readAs"])

    def test_as_and_profile_and_wrapped_tool(self):
        b = run('''
    out = {}
    out["as"] = call("batch", {"calls": [{"tool": "probe_make", "arguments": {"name": "A"}, "as": "p"}]})
    out["profile"] = call("batch", {"calls": [{"tool": "probe_make", "arguments": {"name": "A"}, "profile": True}]})
    out["inside"] = call("batch", {"calls": [{"arguments": {"tool": "probe_make", "name": "A"}}]})
    print(json.dumps(out))
''')
        self.assertIn("as is a key of fast steps, not of batch calls", b["as"][1]["refused"]["error"])
        self.assertIn('{ "$from": 0, "$at": "feature" }', b["as"][1]["refused"]["error"])
        self.assertIn("profile is not part of a call", b["profile"][1]["refused"]["error"])
        self.assertIn("tool is inside arguments. tool goes beside arguments", b["inside"][1]["refused"]["error"])

    def test_rollback(self):
        b = run('''
    out = {}
    out["moved"] = call("batch", {"rollback": True, "calls": [{"tool": "probe_make", "name": "A"}]})
    out["wrapper"] = call("batch", {"rollback": True, "calls": [mk("B"), {"tool": "probe_make", "params": {}}]})
    out["labels"] = labels()
    print(json.dumps(out))
''')
        self.assertTrue(b["moved"][1]["results"][0]["ok"])
        self.assertTrue(b["wrapper"][0])
        self.assertIn("Nothing was run.", b["wrapper"][1]["error"]["message"])
        self.assertNotIn("B", b["labels"])


class FastShape(unittest.TestCase):
    """Decision 3: fast's tool step is a batch call's shape, { tool,
    arguments, as, when }; the old { call, … } is refused, no alias."""

    def test_old_form_refused_before_step_one(self):
        b = run('''
    print(json.dumps([call("fast", {"do": [mk("A"), {"call": "probe_make", "name": "B"}]}), labels()]))
''')
        (err, ans, _t), labs = b
        self.assertTrue(err)
        self.assertIn("{ call, … } is the old form of a fast step", ans["error"]["message"])
        self.assertIn('{ "tool": "probe_make", "arguments": { … }, "as": "name" }', ans["error"]["message"])
        self.assertNotIn("A", labs)

    def test_tool_step_runs_and_a_field_beside_tool_is_moved(self):
        b = run('''
    print(json.dumps([call("fast", {"do": [{"tool": "probe_make", "arguments": {"name": "A"}, "as": "a"}, {"tool": "probe_make", "name": "B"}]}), labels()]))
''')
        (err, ans, _t), labs = b
        self.assertFalse(err, ans)
        self.assertTrue({"A", "B"} <= set(labs))
        self.assertIn("do.1: name was beside tool: read inside arguments.", ans["readAs"])


class ListedSchema(unittest.TestCase):
    """1b (owner decision 2): in the static list the batch schema shows
    calls (required, items typed { tool, arguments }), rollback and
    stopOnError; the server still takes the other fields."""

    def test_listed_batch_and_fast(self):
        got = run('''
    tl = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})["result"]["tools"]
    print(json.dumps({t["name"]: t["inputSchema"] for t in tl if t["name"] in ("batch", "fast")}))
''')
        b = got["batch"]
        self.assertEqual(sorted(b["properties"]), ["calls", "rollback", "stopOnError"])
        self.assertEqual(b["required"], ["calls"])
        self.assertEqual(b["properties"]["calls"]["items"]["required"], ["tool", "arguments"])
        self.assertNotIn("additionalProperties", b)
        if "fast" in got:
            self.assertEqual(sorted(got["fast"]["properties"]["do"]["items"]["properties"]), ["arguments", "as", "tool"])

    def test_hidden_fields_still_work_and_unknown_is_refused(self):
        got = run('''
    out = {}
    out["lines"] = call("batch", {"calls": [mk("A")], "lines": "counts"})
    out["steps"] = call("batch", {"steps": [mk("B")]})
    print(json.dumps(out))
''')
        self.assertFalse(got["lines"][0])
        self.assertTrue(got["steps"][0])

    def test_classic_keeps_the_full_schema(self):
        os.environ["AGENTLINK_TOOLLIST"] = "classic"
        self.addCleanup(os.environ.pop, "AGENTLINK_TOOLLIST", None)
        got = run('''
    tl = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})["result"]["tools"]
    print(json.dumps([t["inputSchema"] for t in tl if t["name"] == "batch"]))
''')
        if got:
            self.assertIn("path", got[0]["properties"])


class RecordRead(unittest.TestCase):
    """Decision 12 and rename set 2: record_read { path, at }; batch path,
    start and writeTo; read, at, file, from and to are gone."""

    def test_record_read_and_old_names(self):
        got = run('''
    out = {}
    b = call("batch", {"calls": [mk("A")]})
    out["rec"] = call("record_read", {"path": b[1]["record"], "at": "results.0.ok"})
    out["write"] = call("batch", {"calls": [{"tool": "probe_make", "arguments": {"name": "B"}, "writeTo": "b.json"}]})
    for k, v in (("read", "x.json"), ("file", "x.json"), ("from", 0), ("to", "y.json")):
        out[k] = call("batch", {"calls": [mk("C")], k: v})
    print(json.dumps(out))
''')
        self.assertFalse(got["rec"][0], got["rec"])
        self.assertEqual(got["rec"][1]["value"], True)
        self.assertIn("written", got["write"][1]["results"][0])
        for k in ("read", "file", "from", "to"):
            self.assertTrue(got[k][0], k)
            self.assertIn(f"input.{k}: not a known field", got[k][1]["error"]["message"])


class StartDocument(unittest.TestCase):
    """24 Nov: the headless start document is Agent Link's, not the person's."""

    def test_start_document_words(self):
        got = run('''
    print(json.dumps(call("session_state", {"orient": True})))
''')
        note = got[1]["note"]
        self.assertNotIn("is the person's document", note)
        self.assertIn("empty start document that Agent Link made", note)
        self.assertTrue(got[1]["documents"][0].get("start"))


class NoToolKey(unittest.TestCase):
    """24 Nov (LFM): a batch call with arguments and no tool is refused with
    "no tool" first and the tools whose cards take those inputs."""

    def test_no_tool_words(self):
        got = run('''
    print(json.dumps(call("batch", {"calls": [mk("A"), {"arguments": {"name": "B", "fail": False}}]})))
''')
        err = got[1]["refused"]["error"]
        self.assertTrue(err.startswith('calls.1 has no "tool": every call names its tool beside arguments.'), err)
        self.assertIn("Tools whose cards take name, fail: probe_make", err)
        self.assertIn('Form: { "tool": "probe_make"', err)
        self.assertEqual(err.count("The call was not run."), 1)
        self.assertNotIn('"B"', err)


class DressupValid(unittest.TestCase):
    """24 Nov QA: a fillet that FreeCAD computed without an error left a shape
    that is not valid, and the answer said ok. dressup_valid reads that."""

    def test_reads_the_check(self):
        got = run('''
    from agentlink.families import pd_common
    class Sh:
        def __init__(self, ok, n=10): self.ok, self.Faces = ok, [0] * n
        def isNull(self): return False
        def isValid(self): return self.ok
    class B:
        def __init__(self, sh): self.Shape = sh
    print(json.dumps([pd_common.dressup_valid(B(Sh(True))), pd_common.dressup_valid(B(Sh(False))),
                      pd_common.dressup_valid(B(Sh(False, 5000))), pd_common.dressup_valid(B(None))]))
''')
        self.assertEqual(got, [True, False, True, True])

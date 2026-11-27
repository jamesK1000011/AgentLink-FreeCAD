# SPDX-License-Identifier: LGPL-2.1-or-later
# One shape (24 Nov): the batch answer's result and each call's status (1f),
# next-step words that list the calls to send (1g), and the batch call form.
import json
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
    print(json.dumps(call("batch", {"calls": [{"tool": "probe_read"}, mk("X", fail=True)]})))
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
        self.assertTrue(b["note"].endswith("in order: probe_make (fixed), probe_make."), b["note"])  # no start sent: no start words (26 Nov)

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
        self.assertIn("Leave start out: start counts in the list you send, and the new list starts at its first call.", b["note"])

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
    """26 Nov (owner decisions): a step is flat, { tool, <its inputs> }. The old forms
    (arguments, as, a wrapper under another name) are refused, no alias."""

    def test_flat_inputs_run(self):
        b = run('''
    r = call("batch", {"calls": [{"tool": "probe_make", "name": "A"}]})
    print(json.dumps([r[0], r[1], labels()]))
''')
        err, ans, labs = b
        self.assertIn("A", labs)
        row = ans["results"][0]
        self.assertTrue(row["ok"])
        self.assertNotIn("readAs", row)

    def test_a_wrapper_refuses_only_its_call(self):
        b = run('''
    print(json.dumps(call("batch", {"calls": [mk("A"), {"tool": "probe_make", "options": {"name": "B"}}, mk("C")]})))
''')
        b = b[1]
        self.assertEqual((b["done"], b["refused"]["call"]), ([0], 1))
        # The inputs are checked by the tool's own schema, as a direct call is.
        self.assertIn("input.name: required", b["refused"]["error"])

    def test_arguments_is_the_old_form(self):
        b = run('''
    out = {}
    out["other"] = call("batch", {"calls": [{"tool": "probe_make", "name": "A", "arguments": {"name": "B"}}]})
    out["alone"] = call("batch", {"calls": [{"tool": "probe_make", "arguments": {"name": "C"}}]})
    print(json.dumps(out))
''')
        for k in ("other", "alone"):
            err = b[k][1]["refused"]["error"]
            self.assertIn("arguments is the old form. Put the inputs beside tool", err, k)
            self.assertIn('{ "tool": "probe_make", "plane": "XY" }', err, k)
        self.assertEqual(b["other"][1]["done"], [])

    def test_as_and_profile_and_wrapped_tool(self):
        b = run('''
    out = {}
    out["as"] = call("batch", {"calls": [{"tool": "probe_make", "name": "A", "as": "p"}]})
    out["profile"] = call("batch", {"calls": [{"tool": "probe_make", "name": "A", "profile": True}]})
    out["inside"] = call("batch", {"calls": [{"arguments": {"tool": "probe_make", "name": "A"}}]})
    print(json.dumps(out))
''')
        self.assertIn("as is not part of a step", b["as"][1]["refused"]["error"])
        self.assertIn('{ "$from": 0, "$at": "feature" }', b["as"][1]["refused"]["error"])
        self.assertIn("input.profile: not a known field", b["profile"][1]["refused"]["error"])
        self.assertIn("arguments is the old form", b["inside"][1]["refused"]["error"])

    def test_rollback(self):
        b = run('''
    out = {}
    out["moved"] = call("batch", {"rollback": True, "calls": [{"tool": "probe_make", "name": "A"}]})
    out["wrapper"] = call("batch", {"rollback": True, "calls": [mk("B"), {"tool": "probe_make", "arguments": {}}]})
    out["labels"] = labels()
    print(json.dumps(out))
''')
        self.assertTrue(b["moved"][1]["results"][0]["ok"])
        self.assertTrue(b["wrapper"][0])
        self.assertIn("Nothing was run.", b["wrapper"][1]["error"]["message"])
        self.assertNotIn("B", b["labels"])


class FastShape(unittest.TestCase):
    """fast's step is a batch step; the old { call, … } and do are refused, no alias."""

    def test_old_form_refused_before_step_one(self):
        b = run('''
    print(json.dumps([call("fast", {"calls": [mk("A"), {"call": "probe_make", "name": "B"}]}), labels()]))
''')
        (err, ans, _t), labs = b
        self.assertTrue(err)
        self.assertIn("{ call, … } is the old form of a step", ans["error"]["message"])
        self.assertIn('{ "tool": "probe_make", <the inputs> }', ans["error"]["message"])
        self.assertNotIn("A", labs)

    def test_tool_step_runs(self):
        b = run('''
    print(json.dumps([call("fast", {"calls": [{"tool": "probe_make", "name": "A"}, {"tool": "probe_make", "name": "B"}]}), labels()]))
''')
        (err, ans, _t), labs = b
        self.assertFalse(err, ans)
        self.assertTrue({"A", "B"} <= set(labs))
        self.assertNotIn("readAs", ans)


class ListedSchema(unittest.TestCase):
    """1b (owner decision 2): in the static list the batch schema shows
    calls (required, items typed { tool } and open for the inputs), rollback and
    stopOnError; the server still takes the other fields."""

    def test_listed_batch_and_fast(self):
        got = run('''
    tl = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})["result"]["tools"]
    print(json.dumps({t["name"]: t["inputSchema"] for t in tl if t["name"] in ("batch", "fast", "run")}))
''')
        b = got["batch"]
        # 27 Nov (QA s1127a F8): batch and fast list only calls; the server still takes the other fields.
        self.assertEqual(sorted(b["properties"]), ["calls"])
        self.assertEqual(b["required"], ["calls"])
        # 27 Nov: the step declares no key (tests/test_step_no_key_1127.py says why).
        self.assertNotIn("required", b["properties"]["calls"]["items"])
        self.assertNotIn("properties", b["properties"]["calls"]["items"])
        # true, said in full: a server that writes to the schema lets the inputs through only then (27 Nov).
        self.assertIs(b["properties"]["calls"]["items"].get("additionalProperties"), True)
        self.assertNotIn("additionalProperties", b)
        self.assertEqual(sorted(got["fast"]["properties"]), ["calls"])
        self.assertNotIn("required", got["fast"]["properties"]["calls"]["items"])
        # 27 Nov: run takes the same calls list as batch and fast, and no other key.
        self.assertEqual(sorted(got["run"]["properties"]), ["calls"])
        self.assertEqual(got["run"]["required"], ["calls"])
        self.assertEqual(got["run"]["properties"]["calls"]["items"], b["properties"]["calls"]["items"])
        self.assertIs(got["run"]["properties"]["calls"]["items"].get("additionalProperties"), True)
        self.assertNotIn("additionalProperties", got["run"])

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
    out["write"] = call("batch", {"calls": [{"tool": "probe_make", "name": "B", "writeTo": "b.json"}]})
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
    """24 Nov (LFM): a batch call with inputs and no tool is refused with
    "no tool" first and the tools whose cards take those inputs."""

    def test_no_tool_words(self):
        got = run('''
    print(json.dumps(call("batch", {"calls": [mk("A"), {"name": "B", "fail": False}]})))
''')
        err = got[1]["refused"]["error"]
        self.assertTrue(err.startswith('calls.1 has no "tool": every call names its tool, and its inputs stand beside it.'), err)
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


class CascadeNotCounted(unittest.TestCase):
    """24 Nov QA: with stopOnError: false, the refusals after the first in a
    batch are not counted toward the repeat stop; the first is."""

    def test_counts(self):
        got = run('''
    calls = [mk("A", fail=True)] + [mk("B%d" % i, fail=True) for i in range(6)]
    b = call("batch", {"calls": calls, "stopOnError": False})
    print(json.dumps([b[1]["refusedCalls"], srv._repeats.get("probe_make", {}).get("n"), [r["error"].get("repeat") for r in b[1]["results"]]]))
''')
        self.assertEqual(got[0], list(range(7)))
        self.assertEqual(got[1], 1)
        self.assertEqual(got[2], [None] * 7)


class QA1125Words(unittest.TestCase):
    """24 Nov blind QA of series 1125: four refusals that were missing or
    sent the model the wrong way. Read from the data and the source (the
    tools need FreeCAD to run)."""

    def setUp(self):
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink")
        with open(os.path.join(here, "data", "tools.json"), encoding="utf-8") as f:
            self.tools = json.load(f)["entries"]
        with open(os.path.join(here, "families", "pd_common.py"), encoding="utf-8") as f:
            self.pd = f.read()
        with open(os.path.join(here, "fastpath.py"), encoding="utf-8") as f:
            self.fast = f.read()

    def test_face_with_length_is_refused(self):
        for n in ("pd_pad", "pd_pocket"):
            steps = json.dumps(self.tools[n]["steps"])
            i, j = steps.find("face is the face to go up to"), steps.find('"types"')
            self.assertTrue(0 < i < j, n)  # refused before the extent is chosen
            self.assertIn("a.face is not None and not a.extent and a.get('length') is not None", steps, n)

    def test_no_change_uses_a_tolerance(self):
        self.assertIn("tol = max(0.01, 1e-7 * max(abs(before), abs(out[\"volume\"])))", self.pd)
        for k in ('must_change == "add" and delta <= tol', 'must_change == "cut" and delta >= -tol', 'must_change == "changed" and abs(delta) <= tol'):
            self.assertIn(k, self.pd)
        self.assertNotIn("delta >= -1e-6", self.pd)

    def test_unknown_edge_key_is_named(self):
        self.assertIn('is not a key of an edge query. Keys: {', self.pd)

    def test_get_names_real_objects(self):
        self.assertNotIn("Name it: \\\"{parts[0].capitalize()}", self.fast)
        self.assertIn("Name the {parts[0]} by its label, then the property", self.fast)


class EdgeKeys(unittest.TestCase):
    """The unknown key refusal, run (a stand-in shape)."""

    def test_position_is_refused(self):
        got = run('''
    from agentlink.families import pd_common
    from agentlink.protocol import ToolError
    try:
        pd_common._edges_legacy(None, {"face": {"side": "-z"}, "kind": "line", "position": "outer"})
        print(json.dumps("no refusal"))
    except ToolError as e:
        print(json.dumps([e.code, e.message]))
''')
        self.assertEqual(got[0], "invalid_input")
        self.assertTrue(got[1].startswith("edges: position is not a key of an edge query."), got[1])
        self.assertIn("Nothing was changed.", got[1])

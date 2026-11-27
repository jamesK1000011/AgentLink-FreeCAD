# SPDX-License-Identifier: LGPL-2.1-or-later
# One flat step shape everywhere (26 Nov): { tool, <inputs beside it> }, with no
# arguments wrapper. run, batch and fast take calls of steps (run: calls: [step], 27 Nov).
# A loop is an each key on the step; the old forms are refused with the new
# form in the words. The server runs on stand-ins in a child process (the
# "flat" case of test_fastpath.py).
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

_got = []


def flat():
    if not _got:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_fastpath.py"), "child", "flat"], capture_output=True, text=True,
                           timeout=180, cwd=ROOT)
        if r.returncode != 0:
            raise AssertionError("child flat failed:\n" + r.stderr[-4000:])
        _got.append(json.loads(r.stdout.strip().splitlines()[-1]))
    return _got[0]


def words(r):
    b = r["body"]
    if "error" in b:
        return b["error"]["message"]
    return b["refused"]["error"]


class Run(unittest.TestCase):
    def test_run_with_one_step_gives_the_answer_of_a_direct_call(self):
        g = flat()
        self.assertFalse(g["run"]["isError"])
        self.assertEqual(g["run"]["body"]["n"], 7)
        self.assertEqual(sorted(g["run"]["body"]), sorted(g["direct"]["body"]))
        self.assertNotIn("results", g["run"]["body"])

    def test_run_refuses_the_approvals_and_itself(self):
        g = flat()
        for r in g["approve"]:
            self.assertTrue(r["isError"])
            self.assertEqual(r["body"]["error"]["code"], "not_allowed")
            self.assertIn("takes only a direct call from the client", r["body"]["error"]["message"])
        self.assertTrue(g["runInRun"]["isError"])

    def test_run_is_the_ninth_listed_tool(self):
        g = flat()
        self.assertIn("run", g["listed"])

    def test_run_refuses_the_old_forms(self):
        g = flat()
        self.assertIn("arguments is the old form", words(g["oldRun"][0]))
        self.assertIn('"tool": "probe_change"', words(g["oldRun"][0]))
        self.assertIn("try is not part of a step", words(g["oldRun"][1]))


class SameCalls(unittest.TestCase):
    def test_batch_and_fast_take_the_same_calls(self):
        g = flat()
        self.assertEqual([r["result"]["n"] for r in g["batchSame"]["body"]["results"]], [1, 2])
        self.assertFalse(g["fastSame"]["isError"])
        self.assertTrue(g["fastSame"]["body"]["fast"].startswith("ok 2 calls"))
        self.assertEqual(len(g["fastSame"]["body"]["made"]), 2)

    def test_fast_and_batch_refuse_do(self):
        g = flat()
        self.assertTrue(g["do"]["isError"])
        self.assertIn("do is now calls", g["do"]["body"]["error"]["message"])
        self.assertIn("Nothing was run", g["do"]["body"]["error"]["message"])
        self.assertIn("do is the old name", g["batchDo"]["body"]["error"]["message"])
        self.assertNotIn("P3", [x for x in g["labelsBatch"]])


class Loops(unittest.TestCase):
    def test_each_gives_one_call_for_each_value_in_run_batch_and_fast(self):
        g = flat()
        self.assertEqual([r["result"]["n"] for r in g["eachRun"]["body"]["results"]], [15, 45])
        self.assertEqual(g["eachBatch"]["body"]["done"], [0, 1])
        self.assertEqual(g["eachFast"]["body"]["fast"].split(" calls")[0], "ok 3")

    def test_the_variable_is_set_as_a_scalar_and_inside_a_list(self):
        seen = {(t, json.dumps(a, sort_keys=True)) for t, a in g_seen()}
        self.assertIn(("probe_change", json.dumps({"n": 15})), seen)
        self.assertIn(("probe_change", json.dumps({"n": 45})), seen)
        for x in (15, 45):
            self.assertIn(("sketch_add", json.dumps({"kind": "circle", "center": [x, 15], "radius": 5, "sketch": "Sketch"}, sort_keys=True)), seen)
        for x in (3, 4, 5):
            self.assertIn(("sketch_add", json.dumps({"kind": "circle", "center": [x, 0], "radius": 1, "sketch": "Sketch"}, sort_keys=True)), seen)

    def test_a_second_pass_that_is_refused_keeps_the_first(self):
        g = flat()["badLoop"]["body"]
        self.assertEqual(g["done"], [0, 1])
        self.assertEqual(g["refused"]["call"], 2)
        self.assertEqual(g["notRun"], [3])
        labels = flat()["labelsLoop"]
        self.assertIn("P11", labels)
        self.assertIn("P12", labels)
        self.assertNotIn("P13", labels)

    def test_each_takes_one_variable(self):
        g = flat()
        self.assertIn("each takes one variable, not 2", words(g["twoVars"]))


def g_seen():
    return flat()["seenEach"]


class BatchOnly(unittest.TestCase):
    def test_from_in_batch(self):
        g = flat()["from"]["body"]
        self.assertEqual(g["done"], [0, 1])
        self.assertEqual(g["results"][1]["result"]["sketch"], "FromSk")

    def test_writeto_is_a_key_of_batch_steps(self):
        g = flat()
        self.assertTrue(g["writeFile"])
        self.assertIn("written", g["writeBatch"]["body"]["results"][0])
        self.assertIn("writeTo is a key of batch steps", words(g["writeFast"]))
        self.assertIn("writeTo does not go with each", words(g["writeEach"]))


class OldForms(unittest.TestCase):
    def test_each_old_form_is_refused_with_the_new_form_in_the_words(self):
        old = flat()["oldBatch"]
        self.assertIn("arguments is the old form", words(old["arguments"]))
        self.assertIn("There is no arguments wrapper", words(old["arguments"]))
        self.assertIn("$from", words(old["as"]))
        for k in ("as", "when", "let"):
            self.assertIn(f"{k} is not part of a step", words(old[k]), k)
        for m in (words(old[k]) for k in old):
            self.assertIn("was not run", m)

    def test_refusals_by_the_parser(self):
        from agentlink import callshape

        class Srv:
            tools = {}

        for bad, word in (({"call": "pd_pad"}, "call"), ({"each": "x", "in": [1], "steps": []}, "each"), ({"choose": "=1"}, "choose"),
                          ({"try": []}, "try"),):
            try:
                callshape.steps_of(Srv, bad, "calls.0", "batch")
            except callshape.Refused as e:
                self.assertTrue(e.words, word)
            else:
                self.assertEqual(bad, "was refused")


class Collisions(unittest.TestCase):
    """No tool has an input named like a step key (tool, each, writeTo). The old
    five (part_join, cam_job, cam_op, robot_new, robot_tool) were renamed on 26 Nov with no alias."""

    KNOWN_PENDING = ()

    def test_no_data_tool_input_has_a_step_key(self):
        from agentlink import callshape

        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        found = []
        for name, e in entries.items():
            if not isinstance(e, dict):
                continue
            for k in (e.get("inputSchema") or {}).get("properties", {}):
                if k in callshape.RESERVED and (name, k) not in self.KNOWN_PENDING:
                    found.append(f"{name}.{k}")
        self.assertEqual(found, [])

    def test_no_tool_input_of_the_server_has_a_step_key(self):
        g = flat()
        self.assertEqual(g["reserved"], ["each", "tool", "writeTo"])
        # Two hub inputs keep a step key, each for its own reason (27 Nov: tool_find, tool_groups and job_start now say card and job):
        # batch.writeTo is the batch's own top-level key (the file of the whole record). run has only calls (27 Nov).
        self.assertEqual(g["collide"], ["batch.writeTo"])

    def test_the_five_renamed_inputs(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        for name, new in (("part_join", "cutter"), ("cam_job", "toolbit"), ("cam_op", "toolbit"), ("robot_new", "endTool"), ("robot_tool", "endTool")):
            props = entries[name]["inputSchema"]["properties"]
            self.assertIn(new, props, name)
            self.assertNotIn("tool", props, name)


class CookbookArguments(unittest.TestCase):
    def test_arguments_is_a_normal_input_where_the_tool_has_one(self):
        from agentlink import callshape

        class T:
            schema = {"type": "object", "properties": {"name": {"type": "string"}, "arguments": {"type": "object"}}}

        class Srv:
            tools = {"cookbook_run": T()}

        got = callshape.steps_of(Srv, {"tool": "cookbook_run", "name": "x", "arguments": {"a": 1}}, "calls.0", "batch")
        self.assertEqual(got[0]["inputs"], {"name": "x", "arguments": {"a": 1}})


if __name__ == "__main__":
    unittest.main()


class StepSchemaLetsInputsThrough(unittest.TestCase):
    """A server that makes the model write to the schema (llama.cpp with tools)
    lets a key through only when the schema says additionalProperties: true
    (live run, 27 Nov: every step came as { "tool": name } with no inputs)."""

    def test_listed_step_schemas_say_additional_properties_true(self):
        from agentlink import staticbase
        from agentlink.families import fast as fast_family

        for name in ("run", "batch", "fast"):
            self.assertIs(staticbase.LISTED_SCHEMAS[name]["properties"]["calls"]["items"].get("additionalProperties"), True)
        self.assertIs(fast_family.STEP_SCHEMA.get("additionalProperties"), True)

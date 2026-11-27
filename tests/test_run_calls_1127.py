# SPDX-License-Identifier: LGPL-2.1-or-later
# run takes { calls: [step] }, the same list as batch and fast (owner decision,
# 27 Nov: a client can force additionalProperties: false on the top level of a
# tool, so the steps stand one level down). run runs the first step only and
# says so in a notice. The server runs on stand-ins in a child process (the
# "flat" and "result1127" cases of test_fastpath.py).
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from test_flat_call_1126 import flat, words  # noqa: E402

_res = []


def result_case():
    if not _res:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_fastpath.py"), "child", "result1127"], capture_output=True, text=True, timeout=180, cwd=ROOT)
        if r.returncode != 0:
            raise AssertionError(r.stderr[-3000:])
        _res.append(json.loads(r.stdout.strip().splitlines()[-1]))
    return _res[0]


class OneStep(unittest.TestCase):
    def test_one_step_gives_the_answer_of_a_direct_call(self):
        g = flat()
        self.assertFalse(g["runOne"]["isError"])
        self.assertEqual(g["runOne"]["body"]["n"], 31)
        self.assertEqual(sorted(g["runOne"]["body"]), sorted(g["directOne"]["body"]))
        for k in ("results", "done", "refused", "notRun", "ran", "record", "notice"):
            self.assertNotIn(k, g["runOne"]["body"])

    def test_result_stays_first_and_the_notice_is_next(self):
        body = result_case()["runMany"]["body"]
        self.assertEqual(list(body)[:2], ["result", "notice"])

    def test_one_step_has_result_first_and_no_notice(self):
        body = result_case()["run"]["body"]
        self.assertEqual(list(body)[0], "result")
        self.assertNotIn("notice", body)


class MoreSteps(unittest.TestCase):
    def test_three_steps_run_the_first_only(self):
        g = flat()
        self.assertFalse(g["runThree"]["isError"])
        self.assertEqual(g["runThree"]["body"]["n"], 41)
        self.assertEqual(g["runThreeNew"], ["P41"])  # the stand-in document shows the first step's effect only

    def test_the_notice_is_a_fact_that_names_the_steps_not_run(self):
        n = flat()["runThree"]["body"]["notice"]
        self.assertEqual(n, "run takes one call. It ran calls.0 only. 2 steps were not run and not checked: 1 (sketch_new), 2 (probe_change). batch runs several calls.")

    def test_the_notice_is_near_the_top(self):
        self.assertEqual(list(flat()["runThree"]["body"])[0], "notice")  # this stand-in has no result line

    def test_one_step_left_over_is_said_in_the_singular(self):
        self.assertIn("1 step was not run and not checked: 1 (probe_change).", flat()["eachExtra"]["body"]["notice"])

    def test_a_later_step_is_not_checked(self):
        g = flat()
        self.assertFalse(g["runBadLater"]["isError"])
        self.assertIn("1 (no tool), 2 (no tool)", g["runBadLater"]["body"]["notice"])
        self.assertEqual(g["runBadLaterNew"], ["P51"])

    def test_a_refused_first_step_runs_nothing(self):
        r = flat()["wrongFirst"]
        self.assertTrue(r["isError"])
        self.assertIn("arguments is the old form", words(r))


class Refused(unittest.TestCase):
    def test_the_old_flat_form_is_refused_with_the_new_form(self):
        g = flat()
        r = g["oldFlat"]
        self.assertTrue(r["isError"])
        self.assertEqual(r["body"]["error"]["code"], "invalid_input")
        self.assertIn('run { "calls": [ { "tool": "pd_pad"', words(r))
        self.assertIn("Nothing was run", words(r))
        self.assertEqual(g["oldFlatNew"], [])

    def test_empty_calls_is_refused_with_the_form(self):
        g = flat()
        for k in ("emptyCalls", "noCalls", "notList"):
            self.assertTrue(g[k]["isError"], k)
            self.assertIn('run { "calls": [ { "tool": "pd_pad"', words(g[k]), k)
            self.assertIn("Nothing was run", words(g[k]), k)

    def test_another_top_level_key_is_refused(self):
        r = flat()["extraKey"]
        self.assertTrue(r["isError"])
        self.assertIn("run takes only calls, not rollback", words(r))
        self.assertIn("batch has rollback and stopOnError", words(r))

    def test_approvals_batch_and_fast_are_not_steps_of_run(self):
        g = flat()
        self.assertEqual(g["approveInRun"]["body"]["error"]["code"], "not_allowed")
        self.assertIn("takes only a direct call from the client", words(g["approveInRun"]))
        for k, name in (("batchInRun", "batch"), ("fastInRun", "fast")):
            self.assertTrue(g[k]["isError"], k)
            self.assertIn(f"{name} is not a step of run", words(g[k]))
        for r in flat()["approve"]:
            self.assertEqual(r["body"]["error"]["code"], "not_allowed")
        self.assertTrue(flat()["runInRun"]["isError"])


class Loop(unittest.TestCase):
    def test_each_on_the_single_step_runs_the_passes_as_a_batch(self):
        b = flat()["eachCalls"]["body"]
        self.assertEqual([r["result"]["n"] for r in b["results"]], [71, 72])
        self.assertEqual(b["done"], [0, 1])
        self.assertNotIn("notice", b)

    def test_each_with_more_steps_runs_the_first_step_only(self):
        b = flat()["eachExtra"]["body"]
        self.assertEqual([r["result"]["n"] for r in b["results"]], [73])
        self.assertIn("notice", b)


class Schema(unittest.TestCase):
    def test_listed_run_is_the_calls_of_batch(self):
        from agentlink import staticbase

        run = staticbase.LISTED_SCHEMAS["run"]
        batch = staticbase.LISTED_SCHEMAS["batch"]
        self.assertEqual(sorted(run["properties"]), ["calls"])
        self.assertEqual(run["required"], ["calls"])
        self.assertEqual(run["properties"]["calls"]["items"], batch["properties"]["calls"]["items"])
        self.assertEqual(run["properties"]["calls"]["minItems"], 1)
        self.assertEqual(run["properties"]["calls"]["type"], "array")
        self.assertIs(run["properties"]["calls"]["items"].get("additionalProperties"), True)
        self.assertNotIn("additionalProperties", run)

    def test_the_real_schema_of_run_is_the_same(self):
        from agentlink import staticbase
        from agentlink.families import fast as fast_family

        real = fast_family.RUN_SCHEMA
        listed = staticbase.LISTED_SCHEMAS["run"]
        self.assertEqual(real["required"], ["calls"])
        self.assertEqual(sorted(real["properties"]), ["calls"])
        self.assertEqual(real["properties"]["calls"]["items"], listed["properties"]["calls"]["items"])
        self.assertEqual(real["properties"]["calls"]["minItems"], 1)


class NoOldForm(unittest.TestCase):
    """No text of the hub gives the old flat form of run: run { tool, … }."""

    OLD = re.compile(r'''\brun\s*\{\s*\\*["']?tool\b''')
    OLD_KEY = re.compile(r'''"run"\s*:\s*\{\s*"tool"''')

    def files(self):
        for top in ("agentlink", "docs", "skills"):
            for d, _dirs, names in os.walk(os.path.join(ROOT, top)):
                if "__pycache__" in d:
                    continue
                for n in names:
                    if n.endswith((".py", ".json", ".md", ".txt")):
                        yield os.path.join(d, n)
        for n in ("README.md", "SETUP.md", "ROADMAP.md"):
            yield os.path.join(ROOT, n)

    def test_no_hub_text_gives_the_old_flat_run_form(self):
        found = []
        for path in self.files():
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if self.OLD.search(line) or self.OLD_KEY.search(line):
                        found.append(f"{os.path.relpath(path, ROOT)}:{i}")
        self.assertEqual(found, [])

    def test_the_scan_finds_the_old_form(self):
        self.assertTrue(self.OLD.search('use run { "tool": name } for one call'))
        self.assertTrue(self.OLD.search('run { \\"tool\\": \\"doc_new\\" }'))
        self.assertTrue(self.OLD.search("`run { tool: \"pd_pad\" }`"))
        self.assertFalse(self.OLD.search('run { "calls": [ { "tool": "pd_pad" } ] }'))

    def test_the_run_texts_give_the_new_form(self):
        from agentlink import staticbase
        from agentlink.families import fast as fast_family

        ste = staticbase.ste_descriptions()["run"]
        self.assertIn('run { "calls": [ { "tool": "pd_pad"', ste)
        self.assertIn("the same calls list", ste)
        self.assertIn("run runs the first step only", ste)
        full = [t for t in fast_family.tools(type("S", (), {"server": None})()) if t.name == "run"][0]
        self.assertIn("the same calls list", full.description)


if __name__ == "__main__":
    unittest.main()

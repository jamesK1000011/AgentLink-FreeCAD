# SPDX-License-Identifier: LGPL-2.1-or-later
# Noise fixes from a blind QA of small-local-model runs (24 Nov): "right
# context, not more context". A batch's calls carry no ms (its record keeps
# them); doc_new's card agrees with doc_save's measure gate; pd_body_new's
# card starts with what a beginner needs; session_state gives the machine
# only on request.
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import batchrec  # noqa: E402
from test_local_fixes_1123 import run  # noqa: E402


def card(name):
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"][name]


class BatchTimes(unittest.TestCase):
    def test_the_reply_has_no_per_call_ms_and_the_record_keeps_them(self):
        got = run('''
    a = call("batch", {"calls": [mk("A"), mk("B")]})[1]
    rec = json.load(open(a["record"], encoding="utf-8"))
    print(json.dumps({"a": a, "rec": rec}))
''')
        for row in got["a"]["results"]:
            self.assertNotIn("ms", row["result"])
        self.assertTrue(all("ms" in r["result"] for r in got["rec"]["results"]))
        self.assertEqual(sum(1 for k in got["a"] if k == "record"), 1)

    def test_untimed_reaches_a_batch_inside_a_batch(self):
        reply = {"results": [{"ok": True, "result": {"ms": 3, "results": [{"ok": True, "result": {"ms": 1, "x": 1}}]}}, {"ok": False, "error": {}}]}
        out = batchrec.untimed(reply)
        self.assertEqual(out, {"results": [{"ok": True, "result": {"results": [{"ok": True, "result": {"x": 1}}]}}, {"ok": False, "error": {}}]})
        self.assertEqual(batchrec.untimed("x"), "x")


class Cards(unittest.TestCase):
    def test_doc_new_agrees_with_the_measure_gate(self):
        d = card("doc_new")["description"]
        self.assertNotIn("Save it at once", d)
        self.assertIn("built and measured", d)
        self.assertIn("body_check, measure or get", d)
        self.assertIn("measured since the last change", card("doc_save")["description"])  # the rule it agrees with

    def test_pd_body_new_starts_with_what_a_beginner_needs(self):
        d = card("pd_body_new")["description"]
        first_two = d.split(". ")[:2]
        self.assertIn("sketch_new", " ".join(first_two))
        self.assertNotIn("pd_binder", " ".join(first_two))
        self.assertIn("pd_binder", d)  # the skeleton advice stays, later

    def test_session_state_takes_machine(self):
        with open(os.path.join(ROOT, "agentlink", "tools.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"machine": {"type": "boolean"}', src)
        self.assertIn("machine: true adds the machine", src)


if __name__ == "__main__":
    unittest.main()

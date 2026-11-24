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
        self.assertIn("in order: probe_make (fixed), probe_make. Leave from out.", b["note"])

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
    print(json.dumps(call("batch", {"from": 1, "calls": [mk("A"), mk("B"), mk("C", fail=True)]})))
''')
        self.assertIn("from counts in the list you send. In a new, shorter list, leave from out.", b["note"])

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

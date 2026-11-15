# SPDX-License-Identifier: LGPL-2.1-or-later
# New Report view problem lines ride on the answer to the call in hand.
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentlink import report_watch  # noqa: E402
from agentlink.protocol import add_report  # noqa: E402

TEXT = ("FreeCAD 1.1.3 started\n"
        "Traceback (most recent call last):\n"
        "  File \"echo.py\", line 335, in <lambda>\n"
        "RuntimeError: Internal C++ object (PySide6.QtGui.QAction) already deleted.\n"
        "Agent Link: link on\n"
        "qt.qpa.fonts: Populating font family aliases took 50 ms. Replace uses of missing font family \"Sans-serif\"\n")


class ReportWatch(unittest.TestCase):
    def test_problems_since_start(self):
        out, end = report_watch.problems(TEXT, 0)
        self.assertEqual(end, len(TEXT))
        self.assertTrue(any(l.startswith("Traceback") for l in out))
        self.assertTrue(any("already deleted" in l for l in out))
        self.assertFalse(any("link on" in l for l in out))

    def test_only_new_lines_and_a_cleared_view(self):
        _, end = report_watch.problems(TEXT, 0)
        self.assertEqual(report_watch.problems(TEXT, end)[0], [])
        self.assertTrue(report_watch.problems("Error: x\n", end)[0])

    def test_capped(self):
        out, _ = report_watch.problems("Error\n" * 20, 0)
        self.assertEqual(len(out), report_watch.MAX_LINES)
        self.assertIn("more lines", out[-1])

    def test_onto_the_answer(self):
        reply = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps({"ok": True})}]}}
        add_report(reply, ["Error: x"])
        self.assertEqual(json.loads(reply["result"]["content"][0]["text"])["report"], ["Error: x"])
        add_report(reply, [])


if __name__ == "__main__":
    unittest.main()

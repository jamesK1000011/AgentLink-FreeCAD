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
    def test_what_the_mac_showed(self):
        text = ("12:53:59  Agent Link: listening on 127.0.0.1:7318\n"
                "12:54:24  Cannot find icon: Std_DlgMacroExecute\n"
                "12:54:24  (qt.qpa.fonts) Populating font family aliases took 147 ms. Replace uses of missing font family \"Sans-serif\"\n")
        out, _ = report_watch.problems(text, 0)
        # Qt's font-alias line is written at every start and is nothing to
        # act on: off the answers, still in the Report view (report_read).
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].endswith("Std_DlgMacroExecute"))

    def test_the_font_alias_line_is_off_the_answers_and_still_readable(self):
        font = "12:54:24  (qt.qpa.fonts) Populating font family aliases took 147 ms. Replace uses of missing font family \"Sans-serif\""
        rows = [(font, "#ffaa00"), ("12:54:25  (qt.qpa.fonts) another font problem", "#ffaa00"), ("12:54:26  Error: x", "#ff0000")]

        saved = (report_watch._report_widget, report_watch._blocks, report_watch._problem_colours, report_watch._report_text, dict(report_watch._state))
        report_watch._report_widget = lambda: object()
        report_watch._blocks = lambda w, start: (rows[start:], len(rows))
        report_watch._problem_colours = lambda: {"#ffaa00", "#ff0000"}
        report_watch._report_text = lambda: "\n".join(t for t, _c in rows)
        report_watch._state["seen"] = 0
        try:
            took = report_watch.take()
            self.assertEqual(len(took), 2)
            self.assertFalse(any("Populating font family" in t for t in took))
            self.assertEqual(report_watch.take(), [])
            read = report_watch.read(40, True)
            self.assertTrue(any("Populating font family" in t for t in read["lines"]), read)
            self.assertEqual(read["problems"], 3)
        finally:
            report_watch._report_widget, report_watch._blocks, report_watch._problem_colours, report_watch._report_text = saved[:4]
            report_watch._state.update(saved[4])

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

    def test_a_red_line_without_words_is_a_problem(self):
        rows = [("13:22:03  Workshop Make · Pauses: box is in no print setup", "#ff0000"),
                ("13:21:49  Agent Link: listening", "#ffffff"), ("", None)]
        out = report_watch.coloured(rows, {"#ff0000", "#ffaa00"})
        self.assertEqual(len(out), 1)
        self.assertIn("Pauses", out[0])

    def test_onto_the_answer(self):
        reply = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps({"ok": True})}]}}
        add_report(reply, ["Error: x"])
        self.assertEqual(json.loads(reply["result"]["content"][0]["text"])["report"], ["Error: x"])
        add_report(reply, [])


if __name__ == "__main__":
    unittest.main()

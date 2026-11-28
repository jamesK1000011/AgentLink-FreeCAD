# SPDX-License-Identifier: LGPL-2.1-or-later
"""batch { to, lines: "refused" }: the reply keeps only what needs reading."""
import unittest

from agentlink import batchrec


class Lines(unittest.TestCase):
    GOT = {"ran": 4, "results": [
        {"tool": "a", "ok": True, "result": {"health": {"recompute": "ok", "fault": False}}},
        {"tool": "b", "ok": False, "error": {"code": "invalid_input", "message": "m"}},
        {"tool": "c", "ok": True, "result": {"health": {"recompute": {"failing": [{"object": "Pad", "error": "x"}]}, "fault": True}}},
        {"tool": "d", "ok": True, "result": {"health": {"recompute": "ok", "fault": False, "shapes": [{"object": "Cube", "valid": True, "closed": True, "solids": 1}], "addons": {"Asm": ["assembly solved"]}}}},
    ]}

    def test_all_keeps_a_line_a_call(self):
        out = batchrec.to_reply(self.GOT, 10, "p", 1)
        self.assertEqual([r["i"] for r in out["results"]], [10, 11, 12, 13])
        self.assertNotIn("counts", out)

    def test_refused_keeps_refusals_and_recompute_errors(self):
        out = batchrec.to_reply(self.GOT, 10, "p", 1, lines="refused")
        self.assertEqual([r["i"] for r in out["results"]], [11, 12])
        self.assertEqual(out["counts"], {"ok": 3, "refused": 1})

    def test_counts_gives_no_line(self):
        out = batchrec.to_reply(self.GOT, 10, "p", 1, lines="counts")
        self.assertEqual(out["results"], [])
        self.assertEqual(out["counts"], {"ok": 3, "refused": 1})

if __name__ == "__main__":
    unittest.main()

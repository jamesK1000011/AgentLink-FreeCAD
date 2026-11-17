# SPDX-License-Identifier: LGPL-2.1-or-later
"""batch { to, lines: "refused" }: the reply keeps only what needs reading."""
import unittest

from agentlink import batchrec


class Lines(unittest.TestCase):
    GOT = {"ran": 4, "results": [
        {"tool": "a", "ok": True, "result": {"health": {"verdict": "nothing red"}}},
        {"tool": "b", "ok": False, "error": {"code": "invalid_input", "message": "m"}},
        {"tool": "c", "ok": True, "result": {"health": {"verdict": "S: 4 DoF left on line 0"}}},
        {"tool": "d", "ok": True, "result": {"health": {"verdict": "Cube: valid, closed, 1 solid; Asm: assembly solved"}}},
    ]}

    def test_all_keeps_a_line_a_call(self):
        out = batchrec.to_reply(self.GOT, 10, "p", 1)
        self.assertEqual([r["i"] for r in out["results"]], [10, 11, 12, 13])
        self.assertNotIn("counts", out)

    def test_refused_keeps_refusals_and_unclean_health(self):
        out = batchrec.to_reply(self.GOT, 10, "p", 1, lines="refused")
        self.assertEqual([r["i"] for r in out["results"]], [11, 12])
        self.assertEqual(out["counts"], {"ok": 3, "refused": 1})

    def test_clean_verdicts(self):
        for v in ("nothing red", "as before", "Hist: valid, closed, 2 solids (AllowCompound)", "3 parts valid, closed, 1 solid", "Master: empty", None):
            self.assertTrue(batchrec.clean_verdict(v), v)
        for v in ("Pad: valid, closed, 1 solid; Pad interferes with Cup: 66 mm³", "Tee: valid, closed, 1 solid, a tolerance finding", "1 check not run here"):
            self.assertFalse(batchrec.clean_verdict(v), v)


if __name__ == "__main__":
    unittest.main()

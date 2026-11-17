# SPDX-License-Identifier: LGPL-2.1-or-later
# The hub's tool descriptions in ASD-STE100 (branch explore/full-ste): every
# sentence at most 20 words (lists of names and literals aside), and nothing
# of the original lost — numbers, units, input names, other tools' names and
# the guard words (copy, undo, refuse, never, only, must, approval, restart,
# sign-off, feasibility). The originals are main's, kept in
# scripts/ste_originals.json. Plain Python, read with ast: no FreeCAD needed.
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import ste_check  # noqa: E402


class SteDescriptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = ste_check.check(ROOT)

    def test_every_tool_is_checked(self):
        self.assertEqual(self.result["missing"], [])
        self.assertGreaterEqual(self.result["tools"], 400)

    def test_sentences_are_short(self):
        self.assertEqual([f"{n} ({k}): {s}" for n, s, k in self.result["long"]], [])

    def test_nothing_of_the_original_is_lost(self):
        self.assertEqual([f"{n}: {kind} {tok!r}" for n, kind, tok in self.result["lost"]], [])

    def test_passive_is_a_warning_only(self):
        self.assertIsInstance(self.result["passive"], int)

    def test_waivers_have_a_reason_and_are_still_needed(self):
        import json

        with open(ste_check.ORIGINALS, encoding="utf-8") as f:
            orig = json.load(f)["tools"]
        now = ste_check.collect(ROOT)
        for (name, tok), why in ste_check.WAIVERS.items():
            self.assertTrue(why.strip(), (name, tok))
            saved = dict(ste_check.WAIVERS)
            try:
                ste_check.WAIVERS.clear()
                lost = ste_check.lost(name, orig[name]["description"], now[name]["description"], orig[name]["inputs"], sorted(now))
            finally:
                ste_check.WAIVERS.update(saved)
            self.assertIn(tok, [t for _k, t in lost], f"waiver {name}/{tok} is no longer needed")


class Checker(unittest.TestCase):
    """The checker itself catches what it is for."""

    def test_a_list_of_names_or_a_literal_counts_little(self):
        s = "Pick faces, edges or objects with a, b, c and d only."
        self.assertEqual(ste_check.count(s, {"a", "b", "c", "d"}), 8)  # the four names count as one
        self.assertEqual(ste_check.count('Use e.g. { tool, arguments, to: "x.json" } here.'), 3)

    def test_long_sentences_are_found(self):
        long, _ = ste_check.lint(" ".join(["word"] * 21) + ". Short one.")
        self.assertEqual(len(long), 1)

    def test_a_lost_number_unit_input_tool_or_guard_fails(self):
        old = "Round edges by radius mm (1); refused on a copy. Then pd_pad."
        new = "Round edges."
        lost = {t for _k, t in ste_check.lost("x", old, new, ["radius"], ["x", "pd_pad"])}
        self.assertEqual(lost, {"1", "mm", "radius", "pd_pad", "refuse", "copy"})

    def test_units_need_a_number_or_a_bracket(self):
        self.assertEqual(ste_check.units("height 20 mm, angle in deg, (N), 5 s, 0 in the order"), {"mm", "deg", "N", "s"})
        self.assertIn("in", ste_check.units('"1 in", "30 deg"'))


if __name__ == "__main__":
    unittest.main()

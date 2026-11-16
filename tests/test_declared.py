# SPDX-License-Identifier: LGPL-2.1-or-later
# What add-ons declare of their own tools reaches the echo's tables, so no
# table in Agent Link names them; the densities live once, in Agent Link's data.
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import echo, materials  # noqa: E402


class Declared(unittest.TestCase):
    def setUp(self):
        self.saved = (echo.SHOWN, dict(echo.PREFIX_NAME), list(echo.WORKBENCH), list(echo.PAGES))

    def tearDown(self):
        echo.SHOWN, names, wb, pages = self.saved
        echo.PREFIX_NAME.clear()
        echo.PREFIX_NAME.update(names)
        echo.WORKBENCH[:] = wb
        echo.PAGES[:] = pages

    def test_family_declares_for_the_echo(self):
        self.assertNotIn("mine", echo.PREFIX_NAME)
        fam = types.SimpleNamespace(SHOWN=("mine_check",), AREAS={"mine": "Mine"}, WORKBENCHES={"mine_": "PartDesignWorkbench"}, PAGES=("mine_page_",))
        echo.declare(fam)
        self.assertTrue("mine_check_all".startswith(echo.SHOWN))
        self.assertTrue(echo._describe("mine_do", {}).startswith("Mine › Do"))
        self.assertEqual(echo._workbench_for("mine_do"), "PartDesignWorkbench")
        self.assertIn("mine_page_", echo.PAGES)
        echo.declare(types.SimpleNamespace())  # nothing declared: nothing changes

    def test_did_names_one_form(self):
        echo.declare(types.SimpleNamespace(AREAS={"app_recover": "SafetyNet", "pref_": "Settings"}))
        for name, want in (("gui_input", "Window › Input"), ("report_read", "Report › Read"), ("session_state", "Session › State"),
                           ("dialog_answer", "Dialog › Answer"), ("app_recover", "SafetyNet › Recover"), ("doc_save", "Document › Save"),
                           ("note_list", "Note › List"), ("pref_set", "Settings › Set"), ("batch", "Batch"),
                           ("pd_pad", "Part Design › Pad"), ("zz_new_thing", "Zz › New thing")):
            self.assertEqual(echo.did_name(name), want)

    def test_densities_once(self):
        self.assertEqual(materials.MASS_DENSITY["pla"], materials.DENSITY["pla"])
        self.assertEqual(materials.MASS_DENSITY["steel"], 7.85)
        for k, v in materials.STOCK.items():
            self.assertTrue(v["source"] and v["date"], k)


if __name__ == "__main__":
    unittest.main()

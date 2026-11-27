# SPDX-License-Identifier: LGPL-2.1-or-later
# The spreadsheet tools on a real FreeCAD: skipped where it cannot be imported.
import os
import unittest

from _pd_base import HAVE, Base


@unittest.skipUnless(HAVE, "FreeCAD with PartDesign and Sketcher is not importable here")
class SheetTools(Base):
    def test_1_cells(self):
        m = self.ok("sheet_new", {"name": "Sizes"})
        self.assertEqual(m["made"], "Sizes")
        out = self.ok("sheet_set", {"sheet": "Sizes", "cells": {"A1": 40, "B1": "=A1 / 2", "C1": "3 mm", "D1": "note"}, "aliases": {"A1": "length"}})
        got = {c["cell"]: c for c in out["cells"]}
        self.assertEqual(got["B1"]["value"], 20)
        self.assertEqual(got["C1"]["unit"], "mm")
        self.assertEqual(got["A1"]["alias"], "length")
        self.ok("sheet_set", {"sheet": "Sizes", "at": "A3", "rows": [["x", "y"], [1, 2], [3, "=A4 + B4"]]})
        r = self.ok("sheet_read", {"sheet": "Sizes", "range": "A3:B5"})
        self.assertEqual([c["cell"] for c in r["cells"]], ["A3", "B3", "A4", "B4", "A5", "B5"])
        self.assertEqual(r["cells"][-1]["value"], 3)
        self.assertEqual(self.ok("sheet_set", {"sheet": "Sizes", "cells": {"E1": "12"}, "text": True})["cells"][0]["value"], "12")

    def test_2_refusals(self):
        self.refused("sheet_set", {"sheet": "Sizes", "cells": {"A1": "=nothere * 2"}})
        self.assertEqual(self.ok("sheet_read", {"sheet": "Sizes", "cells": ["A1"]})["cells"][0]["value"], 40)
        self.refused("sheet_set", {"sheet": "Sizes", "cells": {"AAA1": 1}})
        self.refused("sheet_set", {"sheet": "Sizes", "aliases": {"B1": "C3"}})
        self.refused("sheet_read", {"sheet": "Nope"})

    def test_3_drives_a_part(self):
        self.ok("pd_body_new", {"name": "Bar"})
        self.ok("sketch_new", {"plane": "XY", "name": "Outline"})
        self.ok("sketch_add", {"sketch": "Outline", "kind": "rectangle", "corner": [0, 0], "size": [40, 10], "dims": True, "name": "bar"})
        self.ok("pd_pad", {"sketch": "Outline", "length": 5})
        name = self.ok("sheet_list")["sheets"][0]["name"]
        self.ok("param_bind", {"target": "Pad.Length", "expression": f"{name}.length"})
        out = self.ok("sheet_set", {"sheet": "Sizes", "cells": {"A1": 8}})
        self.assertIn("Pad.Length", out["drives"])
        self.assertAlmostEqual(out["bodies"][0]["volume"], 40 * 10 * 8, delta=0.5)
        self.refused("sheet_clear", {"sheet": "Sizes", "range": "A1"})
        self.refused("sheet_set", {"sheet": "Sizes", "cells": {"A1": 0}})
        self.ok("param_bind", {"target": "Pad.Length", "expression": None})

    def test_4_format_rows_csv(self):
        f = self.ok("sheet_format", {"sheet": "Sizes", "range": "A3:B3", "style": ["bold"], "background": "#eeeeee", "align": ["center"]})
        self.assertIn("bold", f["cells"][0]["style"])
        self.assertEqual(f["cells"][0]["background"], "#eeeeee")
        self.refused("sheet_format", {"sheet": "Sizes", "range": "A3", "style": ["blink"]})
        self.ok("sheet_rows", {"sheet": "Sizes", "action": "insert", "rows": 3, "count": 1})
        self.assertEqual(self.ok("sheet_read", {"sheet": "Sizes", "cells": ["B6"]})["cells"][0]["value"], 3)
        self.ok("sheet_rows", {"sheet": "Sizes", "action": "remove", "rows": 3, "count": 1})
        e = self.ok("sheet_export", {"sheet": "Sizes"})
        self.assertTrue(os.path.isfile(e["file"]))
        i = self.ok("sheet_import", {"path": e["file"]})
        self.assertNotEqual(i["sheet"], "Sizes")
        self.assertGreater(i["cells"], 6)

    def test_5_design_table(self):
        t = self.ok("sheet_table", {"action": "make", "name": "Variants", "params": ["blen", "bwid"], "config": "S", "values": [30, 10]})
        self.ok("sheet_table", {"action": "add", "sheet": "Variants", "config": "L", "values": {"blen": 60, "bwid": 20}})
        self.assertEqual(t["active"], "S")
        self.assertEqual(t["current"]["blen"]["value"], 30)
        sheet = t["refAs"].split(".")[0]
        self.ok("param_bind", {"target": "Outline.bar_width", "expression": f"{sheet}.blen"})
        self.ok("param_bind", {"target": "Outline.bar_height", "expression": f"{sheet}.bwid"})
        u = self.ok("sheet_table", {"action": "use", "sheet": "Variants", "config": "L"})
        self.assertEqual(u["current"]["bwid"]["value"], 20)
        # the pad stays 8 mm deep from test 3 (unbinding keeps the value)
        self.assertAlmostEqual(u["bodies"][0]["volume"], 60 * 20 * 8, delta=0.5)
        self.ok("sheet_table", {"action": "add", "sheet": "Variants", "config": "XL", "values": [90, 30]})
        u = self.ok("sheet_table", {"action": "use", "sheet": "Variants", "config": "XL"})
        self.assertAlmostEqual(u["bodies"][0]["volume"], 90 * 30 * 8, delta=0.5)
        self.refused("sheet_table", {"action": "use", "sheet": "Variants", "config": "XXL"})
        self.refused("sheet_set", {"sheet": "Variants", "cells": {"B2": 5}})
        lst = self.ok("sheet_list")
        dt = next(x for x in lst["sheets"] if x["sheet"] == "Variants")["designTables"][0]
        self.assertEqual(dt["configs"], ["S", "L", "XL"])

    def test_6_hardening(self):
        # From FreeCAD's source (Sheet.cpp, PropertySheet.cpp, Cell.cpp), 16 Nov 2026.
        self.ok("sheet_new", {"name": "Hard"})
        # null clears a cell: Sheet.get raises for an empty cell, which is not an error
        self.ok("sheet_set", {"sheet": "Hard", "cells": {"A1": 5, "B1": "=A1 * 2"}})
        out = self.ok("sheet_set", {"sheet": "Hard", "cells": {"B1": None}})
        self.assertTrue(out["cells"][0].get("empty"))
        r = self.ok("sheet_read", {"sheet": "Hard", "cells": ["B1", "A1"]})
        got = {c["cell"]: c for c in r["cells"]}
        self.assertTrue(got["B1"].get("empty"))
        self.assertNotIn("error", got["B1"])
        self.assertEqual(got["A1"]["value"], 5)
        # a formula FreeCAD cannot parse is kept by it as text, silently: refused here
        msg = self.refused("sheet_set", {"sheet": "Hard", "cells": {"C1": "=(A1 + 2"}})
        self.assertIn("C1", msg["message"] if isinstance(msg, dict) else str(msg))
        self.assertTrue(self.ok("sheet_read", {"sheet": "Hard", "cells": ["C1"]})["cells"][0].get("empty"))
        # a cell that fails is named with FreeCAD's reason (its value is the text "ERR: …")
        msg = self.refused("sheet_set", {"sheet": "Hard", "cells": {"D1": "=nothere * 2"}})
        self.assertIn("D1", msg["message"] if isinstance(msg, dict) else str(msg))
        # alias rules: a unit, a constant, a leading underscore, one taken
        for bad in ("mm", "e", "_x", "W"):
            self.refused("sheet_set", {"sheet": "Hard", "aliases": {"A1": bad}})
        self.ok("sheet_set", {"sheet": "Hard", "aliases": {"A1": "base"}})
        self.refused("sheet_set", {"sheet": "Hard", "cells": {"A2": 1}, "aliases": {"A2": "base"}})
        # an alias on an empty cell is FreeCAD's to allow
        self.ok("sheet_set", {"sheet": "Hard", "aliases": {"A3": "later"}})
        # merging clears all but the first cell: refused while an alias there is in use
        self.ok("sheet_set", {"sheet": "Hard", "cells": {"A5": 1, "B5": 7}, "aliases": {"B5": "seven"}})
        self.ok("sheet_set", {"sheet": "Hard", "cells": {"C5": "=seven + 1"}})
        self.refused("sheet_format", {"sheet": "Hard", "range": "A5:B5", "merge": True})
        self.assertEqual(self.ok("sheet_read", {"sheet": "Hard", "cells": ["C5"]})["cells"][0]["value"], 8)
        self.ok("sheet_format", {"sheet": "Hard", "range": "A7:B7", "merge": True})
        self.ok("sheet_format", {"sheet": "Hard", "range": "A7", "merge": False})
        self.refused("sheet_clear", {"sheet": "Hard", "range": "A1:ZZ16384"})
        self.refused("sheet_import", {"path": "no-such-file.csv"})
        # the same rules for parameters and variable sets
        self.refused("param_set", {"name": "m", "value": 1})
        self.refused("param_set", {"name": "_w", "value": 1})
        self.refused("param_set", {"name": "hardp", "value": "(2 +"})
        self.assertNotIn("hardp", [x["name"] for x in self.ok("param_list")["params"]])
        self.refused("varset_new", {"name": "HardSet", "values": {"mm": 1}})
        v = self.ok("varset_new", {"name": "HardSet", "values": {"size": "55 mm", "count": 3}})
        self.assertEqual(v["set"]["size"]["type"], "PropertyLength")
        self.refused("varset_set", {"varset": "HardSet", "values": {"size": "wide"}})


if __name__ == "__main__":
    unittest.main()

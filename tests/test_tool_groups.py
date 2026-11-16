# SPDX-License-Identifier: LGPL-2.1-or-later
# Each tool is listed with its own group (enabling one group lists only what
# it says), export is core's with export_file kept as an unlisted alias, and
# a group an add-on replaces is left out of the listing but stays callable.
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import tool_summary  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402

MOVED = {"surface_loft": "surface", "surface_points": "surface", "surface_thicken": "surface", "surface_fill": "surface",
         "surface_polynomial": "surface", "draft_fix": "draft", "asm_rigid_group": "assembly", "asm_new_part": "assembly",
         "scad_tidy": "openscad", "points_structure": "points", "robot_tool": "robot", "sheet_cells": "sheet", "pd_shaft": "feature",
         "export": "core"}


class Groups(unittest.TestCase):
    def test_tools_in_their_own_groups(self):
        gs = tool_summary.groups()
        where = {n: g for g, v in gs.items() for n in v["tools"]}
        for n, g in MOVED.items():
            self.assertEqual(where.get(n), g, n)
        self.assertNotIn("export_file", where)  # an alias: callable, not listed

    def test_alias_not_listed(self):
        fn = lambda a: {}  # noqa: E731
        ex, old = Tool("export", "Write objects to a file in any format.", {"type": "object", "properties": {}}, fn), \
            Tool("export_file", "Write a body as STEP or STL.", {"type": "object", "properties": {}}, fn)
        old.alias_of = "export"
        srv = Server("t", "1", [ex, old])
        self.assertEqual([t.name for t in srv.listed()], ["export"])
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "export_file", "arguments": {}}})
        self.assertFalse(r["result"].get("isError"))


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
# The tool-data format add-ons publish (agentlink/tooldata.py), and Agent
# Link's own data files: plain Python, no FreeCAD.
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import datafiles, hooks, keep, paths, tooldata  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402

_HOME = os.environ.get("AGENTLINK_HOME")


def setUpModule():
    os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp()  # declared heavy tools are written there


def tearDownModule():
    if _HOME is None:
        os.environ.pop("AGENTLINK_HOME", None)
    else:
        os.environ["AGENTLINK_HOME"] = _HOME


ENTRY = {"group": "g", "description": "A tool for the test, long enough.", "inputSchema": {"type": "object", "properties": {}},
         "changes": False, "source": "test", "date": "2026-11-14"}


def folder(entries, version="1.0.0"):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "tools.json"), "w") as f:
        json.dump({"dataVersion": version, "licence": "CC-BY-4.0", "about": "test", "entries": entries}, f)
    return d


class Refusal(Exception):
    def __init__(self, message, code="invalid_input"):
        super().__init__(message)
        self.code, self.message = code, message


class ToolData(unittest.TestCase):
    def test_binds_in_order_and_refuses(self):
        d = folder({"t_ok": ENTRY, "t_no": {**ENTRY, "heavy": True, "writes": True}})

        def no(a):
            raise Refusal("not that", "invalid_state")

        made = hooks.tools_from_data(d, "g", {"t_ok": lambda a: {"ok": 1}, "t_no": no})
        self.assertEqual([t.name for t in made], ["t_ok", "t_no"])
        self.assertEqual(made[0].fn({}), {"ok": 1})
        self.assertEqual(made[0].group, "g")
        with self.assertRaises(ToolError) as e:
            made[1].fn({})
        self.assertEqual(e.exception.code, "invalid_state")
        self.assertIn("t_no", keep.HEAVY)
        self.assertTrue(keep.is_heavy("t_no"))
        self.assertIn("t_no", paths.WRITERS)
        keep.HEAVY.discard("t_no")
        paths.WRITERS.discard("t_no")

    def test_the_supervisor_learns_heavy_tools_from_the_file(self):
        keep.declare_heavy({"addon_solve"})
        keep.HEAVY.discard("addon_solve")
        self.assertTrue(keep.is_heavy("addon_solve"))
        self.assertFalse(keep.is_heavy("addon_read"))

    def test_every_tool_needs_a_handler(self):
        d = folder({"t_ok": ENTRY, "t_no": ENTRY})
        with self.assertRaises(tooldata.FormatError):
            hooks.tools_from_data(d, "g", {"t_ok": lambda a: 1})

    def test_format_problems_are_named(self):
        self.assertTrue(tooldata.check({"dataVersion": "2.0.0", "entries": {"t": ENTRY}}))
        self.assertTrue(tooldata.check({"dataVersion": "1.0.0", "entries": {"t": {**ENTRY, "extra": 1}}}))
        self.assertTrue(tooldata.check({"dataVersion": "1.0.0", "entries": {"T-x": ENTRY}}))
        self.assertEqual(tooldata.check({"dataVersion": "1.0.0", "entries": {"t": ENTRY}}), [])

    def test_own_data_files_check(self):
        here = os.path.join(os.path.dirname(__file__), "..", "agentlink", "data")
        self.assertEqual(datafiles.check_folder(here), [])


if __name__ == "__main__":
    unittest.main()

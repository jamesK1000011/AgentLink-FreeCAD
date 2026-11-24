# SPDX-License-Identifier: LGPL-2.1-or-later
# Rename sets 5, 6, 10 and 11 of 24 Nov (owner rule R5: a renamed input keeps
# no alias). Each set: the old name is refused like any unknown field, and
# the new name works, on the stand-in FreeCAD of the data tests (a case of
# tests/_data*_cases.py, given by the new names).
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import protocol, runners  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402

# The data tests' stand-ins: harness -> (its family files, does install() need patch()).
HARNESS = {"datask2": ("param", "feature_more", "sketch_more"), "datapd": ("feature", "std_more", "sketch"),
           "dataasm": ("assembly", "assembly_more"), "datacore": ("view", "unattended", "dev", "doc")}

CHILD = r'''
import importlib, inspect, json, sys, tempfile
sys.path[:0] = [%(root)r, %(here)r]
harness, tool, case, args = json.loads(sys.argv[1])
stand = importlib.import_module("_" + harness + "_standin")
fc = stand.install()
if hasattr(fc, "patch"):
    fc.patch()
from agentlink.protocol import ToolError
files = %(files)r[harness]
new = {m: importlib.import_module("agentlink.families." + m) for m in files}
cases = importlib.import_module("_" + harness + "_cases").cases
n = len(inspect.signature(cases).parameters)
found = [c for c in (cases(fc, tempfile.mkdtemp()) if n == 2 else cases(fc, tempfile.mkdtemp(), new, new)) if c[0] == tool and c[1] == case]
assert len(found) == 1, (tool, case, len(found))
_t, _c, prepare, _a = found[0]
fc.state["flags"] = {}
s = fc.Session(tempfile.mkdtemp())
prepare(s)
t = [x for m in files for x in new[m].tools(s) if x.name == tool and x.fn.__module__ == "agentlink.runners"][0]
try:
    res = ["ok", t.fn(args)]
except ToolError as e:
    res = ["refused", e.code, e.message]
print(json.dumps(res, default=repr))
''' % {"root": ROOT, "here": HERE, "files": HARNESS}


def run_case(harness, tool, case, args):
    """The new entry of tool, called with args on the stand-in prepared as the named case."""
    r = subprocess.run([sys.executable, "-c", CHILD, json.dumps([harness, tool, case, args])], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def checked(tool, args):
    """protocol.check_input on the tool's card: the inputs as read, or the refusal's words."""
    schema = runners.entries()[tool]["inputSchema"]
    try:
        a = dict(args)
        protocol.check_input(schema, a, tool)
        return a
    except ToolError as e:
        return e.message


class Base(unittest.TestCase):
    maxDiff = None

    def refused_by_name(self, tool, args, old, new):
        said = checked(tool, args)
        self.assertIsInstance(said, str, f"{tool}: {old} was read")
        self.assertIn(f"input.{old}: not a known field", said)
        self.assertIn(new, said.split("the fields here:")[1])
        props = runners.entries()[tool]["inputSchema"]["properties"]
        self.assertNotIn(old, props)
        self.assertIn(new, props)
        self.assertNotIn(old, protocol.FIELD_ALIASES.get(tool, {}))
        self.assertNotIn(old, protocol.GOES_WITH.get(tool, {}))


class Set5Geometry(Base):
    """geo -> geometry: sketch_extend, sketch_bspline, sketch_edit's keys."""

    def test_old_name_refused(self):
        self.refused_by_name("sketch_extend", {"sketch": "S", "geo": 0, "by": 2}, "geo", "geometry")
        self.refused_by_name("sketch_bspline", {"sketch": "S", "geo": 0, "op": "degree"}, "geo", "geometry")

    def test_new_name_works(self):
        r = run_case("datask2", "sketch_extend", "sketcher call 42", {"sketch": "TourSketch", "geometry": 3, "end": 2, "by": 15.708})
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["extended"], 3)
        r = run_case("datask2", "sketch_extend", "geo it has not", {"sketch": "TourSketch", "geometry": 9, "by": 2})
        self.assertEqual(r[0], "refused")
        self.assertTrue(r[2].startswith("geometry: the id of a line"), r)
        r = run_case("datask2", "sketch_bspline", "sketcher call 49", {"sketch": "TourSketch", "geometry": 6, "op": "degree", "by": 1})
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["geometry"], 6)
        self.assertNotIn("geo", r[1])

    def test_sketch_edit_keys(self):
        r = run_case("datapd", "sketch_edit", "sketcher call 57", {"sketch": "PlateSketch", "trim": {"geometry": 1, "at": [-13, 0]}})
        self.assertEqual(r[0], "ok", r)
        r = run_case("datapd", "sketch_edit", "sketcher call 44", {"sketch": "PlateSketch", "mirror": {"geometry": [4], "about": "y"}})
        self.assertEqual(r[0], "ok", r)
        # The old key is not read: nothing to mirror.
        r = run_case("datapd", "sketch_edit", "sketcher call 44", {"sketch": "PlateSketch", "mirror": {"geos": [4], "about": "y"}})
        self.assertEqual(r[:2], ["refused", "invalid_input"])
        self.assertIn("mirror.geometry", r[2])
        d = runners.entries()["sketch_edit"]["description"]
        self.assertNotRegex(d, r"\bgeos?\b")


if __name__ == "__main__":
    unittest.main()

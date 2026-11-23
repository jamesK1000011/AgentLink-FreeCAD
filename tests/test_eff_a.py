# SPDX-License-Identifier: LGPL-2.1-or-later
# Efficiency design, dev round 1a (claude/agent-link-design-efficiency-2026-11-22.md):
#   D1  window_snapshot and view_snapshot keep the picture to the file unless inline: true;
#       window_snapshot takes a width (smaller, the same shape) and refuses one out of range.
#   C2  fields given by another common name are read as the tool's own (FIELD_ALIASES) and the
#       answer says so (readAs); a batch inside a batch's calls runs in its place, in order,
#       with each $from moved to count through the whole list.
# Plain Python: the batch helpers run in a child process on a stand-in FreeCAD.
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from agentlink import protocol  # noqa: E402
from agentlink.protocol import ToolError, check_input  # noqa: E402

CHILD = r'''
import json, sys, types
from unittest import mock
class Auto(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        m = mock.MagicMock(name=f"{self.__name__}.{k}")
        setattr(self, k, m)
        return m
for n in ("FreeCAD", "FreeCADGui", "Part", "Mesh", "MeshPart", "Sketcher", "Import", "TechDraw", "Draft", "Spreadsheet", "PySide", "PySide.QtCore", "PySide.QtGui"):
    sys.modules[n] = Auto(n)
sys.path.insert(0, sys.argv[1])
from agentlink.tools import _flatten_batches
print(json.dumps(_flatten_batches(json.loads(sys.argv[2]))))
'''


def flatten(calls):
    r = subprocess.run([sys.executable, "-c", CHILD, ROOT, json.dumps(calls)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


class Pictures(unittest.TestCase):
    def test_inline_is_asked_for(self):
        e = entries()
        for name in ("window_snapshot", "view_snapshot"):
            text = json.dumps(e[name])
            self.assertNotIn("a.get('inline', True)", text, name)
            self.assertIn("a.get('inline', False)", text, name)
            self.assertIn("inline: true", e[name]["description"], name)

    def test_window_width(self):
        w = entries()["window_snapshot"]
        self.assertEqual(w["inputSchema"]["properties"]["width"], {"type": "integer"})
        steps = json.dumps(w["steps"])
        self.assertIn("width: 16 to 8192 px.", steps)
        self.assertIn("scaled(pix, a.width)", steps)


class Aliases(unittest.TestCase):
    def schema(self, name):
        return entries()[name]["inputSchema"]

    def test_object_set_values(self):
        args = {"object": "Box", "set": {"Length": 5}}
        self.assertEqual(check_input(self.schema("object_set"), args, "object_set"), ["set as values"])
        self.assertEqual(args, {"object": "Box", "values": {"Length": 5}})

    def test_varset_and_doc_close(self):
        args = {"values": {"W": 2}}
        self.assertEqual(check_input(self.schema("varset_set"), args, "varset_set"), ["values as properties"])
        self.assertEqual(args, {"properties": {"W": 2}})
        args = {"document": "Part1"}
        self.assertEqual(check_input(self.schema("doc_close"), args, "doc_close"), ["document as documents"])
        self.assertEqual(args, {"documents": ["Part1"]})

    def test_object_get_filter(self):
        args = {"object": "Pad", "properties": ["Length", "Type"]}
        check_input(self.schema("object_get"), args, "object_get")
        self.assertEqual(args, {"object": "Pad", "filter": "Length|Type"})

    def test_the_own_field_wins_and_others_still_refuse(self):
        args = {"object": "Box", "values": {"A": 1}, "set": {"B": 2}}
        with self.assertRaises(ToolError):
            check_input(self.schema("object_set"), args, "object_set")
        with self.assertRaises(ToolError):
            check_input(self.schema("object_set"), {"object": "Box", "set": {}})  # no tool: no alias
        with self.assertRaises(ToolError):
            check_input(self.schema("object_set"), {"object": "Box", "vals": {}}, "object_set")

    def test_every_alias_names_a_real_field(self):
        e = entries()
        for tool, pairs in protocol.FIELD_ALIASES.items():
            if tool not in e:
                continue  # a tool written in code
            props = e[tool]["inputSchema"]["properties"]
            for given, to in pairs.items():
                self.assertNotIn(given, props, f"{tool}.{given} is a field of its own")
                self.assertIn(to, props, f"{tool}: {to}")


class Flatten(unittest.TestCase):
    def test_inner_calls_in_place(self):
        calls = [{"tool": "a", "arguments": {}},
                 {"tool": "batch", "arguments": {"calls": [{"tool": "b", "arguments": {}}, {"tool": "c", "arguments": {"x": {"$from": 0}}}]}},
                 {"tool": "d", "arguments": {"y": {"$from": 1}, "z": {"$from": 0}}}]
        out, n = flatten(calls)
        self.assertEqual(n, 1)
        self.assertEqual([c["tool"] for c in out], ["a", "b", "c", "d"])
        self.assertEqual(out[2]["arguments"], {"x": {"$from": 1}})  # b, now call 1
        self.assertEqual(out[3]["arguments"], {"y": {"$from": 2}, "z": {"$from": 0}})  # the inner batch's last call, and a

    def test_two_deep_and_strings(self):
        inner = json.dumps([{"tool": "c", "arguments": {}}])
        calls = [{"tool": "batch", "arguments": {"calls": [{"tool": "b", "arguments": {}}, {"tool": "batch", "arguments": {"calls": inner}}]}}]
        out, n = flatten(calls)
        self.assertEqual([c["tool"] for c in out], ["b", "c"])
        self.assertEqual(n, 2)

    def test_a_file_batch_stays(self):
        calls = [{"tool": "batch", "arguments": {"file": "x.json"}}]
        out, n = flatten(calls)
        self.assertEqual((out, n), (calls, 0))


try:
    from _fc import HAVE, caller, server
except Exception:  # noqa: BLE001
    HAVE = False


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class OnFreeCAD(unittest.TestCase):
    def setUp(self):
        self.session, srv = server()
        self.call = caller(srv)
        self.call("doc_new", {"name": "EffA"})

    def box(self, name):
        return {"tool": "part_primitive", "arguments": {"kind": "box", "size": [5, 5, 5], "name": name}}

    def test_a_batch_in_a_batch(self):
        err, b = self.call("batch", {"calls": [self.box("A"), {"tool": "batch", "arguments": {"calls": [self.box("B"), self.box("C")]}}]})
        self.assertFalse(err, b)
        self.assertIn("flattened", b)
        self.assertEqual(len(self.call("session_state")[1]["bodies"]), 3)

    def test_read_as(self):
        self.call("part_primitive", self.box("Box")["arguments"])
        err, r = self.call("object_set", {"object": "Box", "set": {"Length": 7}})
        self.assertFalse(err, r)
        self.assertEqual(r.get("readAs"), "read set as values")


if __name__ == "__main__":
    unittest.main()

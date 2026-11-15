# SPDX-License-Identifier: LGPL-2.1-or-later
# The runners' own data handling (agentlink/runners.py): plain Python, no
# FreeCAD. The tools they run are checked on FreeCAD by each family's tests.
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import runners, tooldata  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402


class Thing:
    def __init__(self, label, **kw):
        self.Label = label
        self.__dict__.update(kw)


class Doc:
    def __init__(self):
        self.Objects = []

    def addObject(self, t, base):
        o = Thing(base, TypeId=t)
        self.Objects.append(o)
        return o


ENTRY = {"group": "g", "description": "A tool for the test, long enough.", "inputSchema": {"type": "object", "properties": {}},
         "changes": True, "source": "test", "date": "2026-11-14"}


class Runners(unittest.TestCase):
    def setUp(self):
        self.doc = Doc()
        self.log = []
        self.helpers = {"doc": lambda: self.doc, "find": lambda ref: Thing(ref, Size=3),
                        "named": lambda o, n: setattr(o, "Label", n),
                        "finish": lambda o, tool, extra: {"object": o.Label, **extra, "tool": tool},
                        "setprops": lambda o, d: self.log.append(dict(d))}

    def run_entry(self, e, a):
        return runners.tools("g", None, self.helpers, {"t": {**ENTRY, **e}})[0].fn(a)

    def test_make_in_order(self):
        e = {"runner": "make", "target": {"type": "X::Thing", "base": "Thing"},
             "args": {"from": {"helper": "find"},
                      "name": {"then": {"call": "named", "with": ["$o", {"or": ["$a.name", {"fmt": "{from.Label} copy"}]}]}},
                      "size": {"prop": "Size"}, "colour": {"prop": "Colour"}, "kind": {"prop": "Kind", "when": "truthy", "alone": True}},
             "rules": [{"check": "range", "of": "$a.count", "min": 1, "max": 3, "after": "start", "message": "count: 1 … 3."}],
             "answer": {"via": "finish", "with": ["$o", "$tool", "$fields"], "fields": {"from": "$from.Label", "n": {"len": "$doc_objects"}}}}
        e["args"]["=doc_objects"] = {"value": [1, 2]}
        out = self.run_entry(e, {"from": "Box", "count": 2, "size": 5, "kind": "k"})
        self.assertEqual(out, {"object": "Box copy", "from": "Box", "n": 2, "tool": "t"})
        self.assertEqual(self.log, [{"Size": 5, "Colour": None}, {"Kind": "k"}])
        self.assertEqual(self.doc.Objects[0].TypeId, "X::Thing")
        with self.assertRaises(ToolError) as c:
            self.run_entry(e, {"from": "Box", "count": 9})
        self.assertEqual((c.exception.code, c.exception.message), ("invalid_input", "count: 1 … 3."))
        self.assertEqual(len(self.doc.Objects), 1)  # refused before anything was made

    def test_apply_and_read(self):
        class Data:
            def __init__(self, n):
                self.n = n

            def copy(self):
                return Data(self.n)

            def grow(self, by):
                self.n += by

        target = Thing("M", Data=Data(4))
        self.helpers["find"] = lambda ref: target
        e = {"runner": "apply", "target": {"on": "mesh", "copy": "Data", "method": "grow", "call": ["$by"]},
             "args": {"mesh": {"helper": "find"}, "by": {"default": 0, "as": "float"}},
             "rules": [{"check": "nonzero", "of": "$by", "message": "by: not zero."}],
             "answer": {"fields": {"was": "$o.Data.n", "now": "$m.n"}}}
        self.assertEqual(self.run_entry(e, {"mesh": "M", "by": 2}), {"was": 4, "now": 6.0})
        with self.assertRaises(ToolError):
            self.run_entry(e, {"mesh": "M"})
        self.doc.Objects = [Thing("a", Group=[Thing("b")]), Thing("c", Group=[]), Thing("d")]
        r = {"runner": "read", "target": {"from": "$doc.Objects", "where": "keep",
                                          "each": {"object": "$o.Label", "holds": {"when": "$o.Group?", "value": "$o.Group[].Label"}}},
             "answer": {"fields": {"objects": "$rows", "count": {"len": "$rows"}}}}
        self.helpers["keep"] = lambda o: o.Label != "d"
        self.assertEqual(self.run_entry(r, {}), {"objects": [{"object": "a", "holds": ["b"]}, {"object": "c"}], "count": 2})

    def test_format_check(self):
        good = {**ENTRY, "runner": "read", "target": {}, "answer": {"fields": {}}}
        doc = {"dataVersion": "1.0.0", "entries": {"t": good}}
        self.assertEqual(tooldata.check(doc), [])
        for bad in ({"runner": "paint", "target": {}}, {"runner": "make", "target": {}}, {"target": {}},
                    {"runner": "read", "target": {}, "rules": [{"check": "range"}]}, {"runner": "read", "target": {}, "answer": {"say": 1}}):
            self.assertTrue(tooldata.check({"dataVersion": "1.0.0", "entries": {"t": {**ENTRY, **bad}}}), bad)

    def test_own_data_is_well_formed(self):
        path = os.path.join(runners.DATA, "tools.json")
        if not os.path.isfile(path):
            self.skipTest("no data-defined tools yet")
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(tooldata.check(doc), [])
        for name, e in doc["entries"].items():
            self.assertIn(e["runner"], runners.RUNNERS, name)
            self.assertIs(e["inputSchema"].get("additionalProperties"), False, name)


if __name__ == "__main__":
    unittest.main()

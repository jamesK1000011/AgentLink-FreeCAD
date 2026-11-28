# SPDX-License-Identifier: LGPL-2.1-or-later
# Cards in fields and the hub-level what (owner, 27 Nov: selectable data,
# decisions 1-12). These tests pin:
#   - every tool of agentlink/data/tools.json has a card in fields (does,
#     rules, returns, hint) and no one-text description; the data check
#     passes;
#   - tool_find's card gives the fields: does, inputs (the schema, each
#     input's meaning in it), rules, returns; hint only at help level 1 or
#     when what names it;
#   - the tool list carries one does line;
#   - what narrows a card, refuses an unknown card field with the names,
#     narrows an answer, keeps health with a fault, and gives the whole
#     answer with whatNotFound for a name the answer does not have;
#   - in a batch, what narrows the row and $from reads the whole answer.
# The server runs on stand-ins in a child process (as tests/test_fastpath.py).
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

CHILD = r'''
import json, os, sys, tempfile, types
from unittest import mock
sys.path.insert(0, %(root)r)
level = %(level)r
if level is not None:
    os.environ["AGENTLINK_HELP_LEVEL"] = str(level)

class Auto(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        m = mock.MagicMock(name=f"{self.__name__}.{k}")
        setattr(self, k, m)
        return m

for n in ("FreeCAD", "FreeCADGui", "Part", "Mesh", "MeshPart", "Sketcher", "Import", "TechDraw", "Draft", "Spreadsheet", "PySide", "PySide.QtCore", "PySide.QtGui"):
    sys.modules[n] = Auto(n)
fc = sys.modules["FreeCAD"]
fc.GuiUp = False
fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d)
os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp(prefix="agentlink-cards-")
from agentlink.tools import Session, build_server
from agentlink.protocol import Tool
class Doc:
    Name = Label = "CardDoc"
    FileName = ""
    def __init__(self):
        self.Objects, self.UndoNames, self.steps, self.open = [], [], [], None
    @property
    def UndoCount(self):
        return len(self.steps)
    def getObject(self, name):
        return None
    def getObjectsByLabel(self, label):
        return []
    def openTransaction(self, name=""):
        self.open = {"name": name}
    def commitTransaction(self):
        self.open = None
    def abortTransaction(self):
        self.open = None
    def undo(self):
        pass
    def recompute(self):
        pass
    def isTouched(self):
        return False
s = Session(out_dir=tempfile.mkdtemp())
s.doc = Doc()
srv = build_server(s, lean=False)
srv._oriented = True
s.server = srv
# A read with a fixed answer, for what on an answer.
def fixed(a):
    h = {"facts": a.get("facts", "recompute: FreeCAD reports no recompute error")}
    if "facts" in a:
        return {"got": a["facts"], "health": h}
    if a.get("errors"):
        h["errors"] = [{"object": "Pad", "error": "x"}]
    return {"volume": 10.0, "faces": 6, "box": [1, 2, 3], "health": h}
srv.tools["t_fixed"] = Tool("t_fixed", "A fixed answer, for the tests.", {"type": "object", "properties": {"facts": {}, "errors": {"type": "boolean"}}, "additionalProperties": False}, fixed)

def call(name, args):
    r = srv.call({"name": name, "arguments": args})
    t = r["content"][0]["text"]
    return {"isError": bool(r.get("isError")), "body": json.loads(t)}

out = {}
out["card"] = call("tool_find", {"card": "pd_chamfer"})
out["cardHint"] = call("tool_find", {"card": "doc_save_all", "what": ["does", "hint"]})
out["cardHintDefault"] = call("tool_find", {"card": "doc_save_all"})
out["cardWhat"] = call("tool_find", {"card": "pd_chamfer", "what": ["does", "rules"]})
out["cardBad"] = call("tool_find", {"card": "pd_chamfer", "what": ["nosuch"]})
out["ansWhat"] = call("t_fixed", {"what": ["volume"]})
out["ansFault"] = call("t_fixed", {"what": ["volume"], "errors": True})
out["ansMissing"] = call("t_fixed", {"what": ["volume", "nosuch"]})
out["batch"] = call("batch", {"calls": [{"tool": "t_fixed", "what": "faces"}, {"tool": "t_fixed", "facts": {"$from": 0, "$at": "box.0"}}]})
out["listing"] = [srv.tools[n].listing() for n in ("pd_chamfer", "doc_save_all")]
print(json.dumps(out, default=str))
'''

_got = {}


def child(level=None):
    if level not in _got:
        r = subprocess.run([sys.executable, "-c", CHILD % {"root": ROOT, "level": level}], capture_output=True, text=True, timeout=180, cwd=ROOT)
        if r.returncode != 0:
            raise AssertionError("child failed:\n" + r.stderr[-4000:])
        _got[level] = json.loads(r.stdout.strip().splitlines()[-1])
    return _got[level]


def card(r):
    b = r["body"]
    return b["tools"][0] if "tools" in b else b["card"]


class Data(unittest.TestCase):
    def test_every_entry_has_a_card_in_fields_and_the_check_passes(self):
        from agentlink import tooldata

        doc = json.load(open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8"))
        self.assertEqual(tooldata.check(doc), [])
        for n, e in doc["entries"].items():
            self.assertNotIn("description", e, n)
            self.assertTrue(e["card"]["does"], n)
            self.assertEqual(set(e["card"]) - {"does", "rules", "returns", "hint"}, set(), n)

    def test_card_text_has_every_field(self):
        from agentlink.tooldata import card_text

        e = {"card": {"does": "Do a.", "rules": ["R."], "returns": ["Answer: x."], "hint": ["Then b."]}}
        self.assertEqual(card_text(e), "Do a. R. Answer: x. Then b.")
        self.assertEqual(card_text({"description": "Old words."}), "Old words.")


class Cards(unittest.TestCase):
    def test_card_gives_fields_not_one_text(self):
        c = card(child()["card"])
        self.assertEqual(c["does"], "Bevel edges of the body.")
        self.assertIn("inputs", c)
        self.assertNotIn("description", c)
        self.assertNotIn("inputSchema", c)
        self.assertIn("size: mm (default 1).", c["inputs"]["properties"]["size"]["description"])
        self.assertTrue(c["rules"] and c["returns"])

    def test_hint_only_when_asked_or_at_level_1(self):
        self.assertNotIn("hint", card(child()["cardHintDefault"]))
        self.assertIn("hint", card(child()["cardHint"]))
        self.assertIn("hint", card(child(1)["cardHintDefault"]))

    def test_what_narrows_a_card_and_refuses_an_unknown_field(self):
        c = card(child()["cardWhat"])
        self.assertEqual(set(c), {"tool", "does", "rules"})
        bad = child()["cardBad"]
        self.assertTrue(bad["isError"])
        self.assertIn("nosuch is not a card field", bad["body"]["error"]["message"])
        self.assertIn("does", bad["body"]["error"]["message"])

    def test_the_list_carries_one_does_line(self):
        ls = child()["listing"]
        self.assertEqual(ls[0]["description"], "Bevel edges of the body.")
        self.assertIn("properties", ls[0]["inputSchema"])


class Answers(unittest.TestCase):
    def test_what_narrows_an_answer_and_drops_health_without_a_fault(self):
        self.assertEqual(child()["ansWhat"]["body"], {"volume": 10.0})

    def test_health_with_a_fault_always_comes_back(self):
        b = child()["ansFault"]["body"]
        self.assertEqual(b["volume"], 10.0)
        self.assertIn("errors", b["health"])

    def test_a_name_the_answer_has_not_gives_the_whole_answer(self):
        b = child()["ansMissing"]["body"]
        self.assertEqual(b["whatNotFound"], ["nosuch"])
        self.assertIn("box", b)
        self.assertIn("box", b["whatNames"])

    def test_batch_narrows_the_row_and_from_reads_the_whole_answer(self):
        b = child()["batch"]["body"]
        rows = b["results"]
        self.assertEqual(set(rows[0]["result"]) - {"ms"}, {"faces"})
        self.assertTrue(rows[1]["ok"], rows[1])
        self.assertEqual(rows[1]["result"]["got"], 1)  # box.0: a part the row of call 0 did not show


if __name__ == "__main__":
    unittest.main()

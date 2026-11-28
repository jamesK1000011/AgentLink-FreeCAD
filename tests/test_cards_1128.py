# SPDX-License-Identifier: LGPL-2.1-or-later
# Cards as records and the hub-level what (owner, 27-28 Nov: selectable
# data; agentlink/cards.py). These tests pin:
#   - every tool of agentlink/data/tools.json has a card of records (one
#     kind of fact per field) and a bare schema; the data check passes;
#     the hub tools' cards (data/hubcards.json) name only their own inputs;
#   - tool_find's card gives every kind but hints and refusals; those come
#     when what names them (hints also at help level 1); what takes one
#     subject of a kind (inputNotes.size2);
#   - the tool list carries one does line and a bare schema;
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

srv.tools["t_sound"] = Tool("t_sound", "A sound shape's answer, for the tests.", {"type": "object", "properties": {}, "additionalProperties": False},
                            lambda a: {"volume": 5.0, "health": {"facts": "shape: B: valid, closed, 1 solid", "next": "workbench PartWorkbench"}})

def call(name, args):
    r = srv.call({"name": name, "arguments": args})
    t = r["content"][0]["text"]
    return {"isError": bool(r.get("isError")), "body": json.loads(t)}

out = {}
out["card"] = call("tool_find", {"card": "pd_chamfer"})
hint_tool = next(n for n, t in srv.tools.items() if (getattr(t, "fields", None) or {}).get("hints") and getattr(t, "entry", None))
out["cardHint"] = call("tool_find", {"card": hint_tool, "what": ["does", "hints"]})
out["cardHintDefault"] = call("tool_find", {"card": hint_tool})
out["cardRefusals"] = call("tool_find", {"card": "pd_chamfer", "what": ["refusals", "refusalNotes"]})
out["cardSub"] = call("tool_find", {"card": "pd_chamfer", "what": ["inputNotes.size2", "links.size2"]})
out["cardBad"] = call("tool_find", {"card": "pd_chamfer", "what": ["nosuch"]})
out["ansWhat"] = call("t_fixed", {"what": ["volume"]})
out["ansFault"] = call("t_fixed", {"what": ["volume"], "errors": True})
out["ansMissing"] = call("t_fixed", {"what": ["volume", "nosuch"]})
out["batch"] = call("batch", {"calls": [{"tool": "t_fixed", "what": "faces"}, {"tool": "t_fixed", "facts": {"$from": 0, "$at": "box.0"}}]})
out["batchHint"] = call("batch", {"calls": [{"tool": "tool_find", "card": hint_tool, "what": ["does", "hints"]}]})
out["noHintAsked"] = call("tool_find", {"card": "pd_chamfer", "what": ["does", "hints"]})
out["sound"] = call("t_sound", {"what": "volume"})
out["listing"] = [srv.tools[n].listing() for n in ("pd_chamfer", "doc_save_all")]
from agentlink import staticbase
out["hubListing"] = next(e for e in staticbase.listing(srv, [srv.tools["session_state"]]))
out["hubInputs"] = {n: list(((srv.tools[n].schema or {}).get("properties") or {})) for n in srv.tools}
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
    def test_every_entry_has_a_card_of_records_and_a_bare_schema(self):
        from agentlink import cards, tooldata

        doc = json.load(open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8"))
        self.assertEqual(tooldata.check(doc), [])
        for n, e in doc["entries"].items():
            self.assertNotIn("description", e, n)
            self.assertEqual(cards.check(n, e["card"], e["inputSchema"]), [], n)

    def test_hub_cards_name_only_their_own_inputs(self):
        from agentlink import cards

        child()  # the server builds
        hub = cards.hub_cards()
        got = child()["hubInputs"]
        for n, c in hub.items():
            self.assertEqual(cards.check(n, c, None), [], n)
            self.assertTrue(set(c.get("inputNotes", {})) <= set(got[n]), (n, set(c.get("inputNotes", {})) - set(got[n])))

    def test_refusals_are_read_from_the_steps(self):
        from agentlink import cards

        e = {"steps": [{"refuse": "a: over 0.", "when": "=a.a <= 0"}, {"each": "x", "in": "=[]", "steps": [{"refuse": {"fmt": "x {x}"}, "code": "not_found"}]}]}
        self.assertEqual(cards.refusals(e), [{"code": "invalid_input", "when": "=a.a <= 0", "message": "a: over 0."},
                                             {"code": "not_found", "message": "x {x}"}])

    def test_bare_keeps_an_input_named_description(self):
        from agentlink import cards

        s = {"type": "object", "description": "x", "properties": {"description": {"type": "string", "description": "y"},
                                                                  "calls": {"type": "array", "items": {"type": "object", "description": "z"}}}}
        self.assertEqual(cards.bare(s), {"type": "object", "properties": {"description": {"type": "string"}, "calls": {"type": "array", "items": {"type": "object"}}}})


class Cards(unittest.TestCase):
    def test_card_gives_every_kind_but_hints_and_refusals(self):
        c = card(child()["card"])
        self.assertEqual(c["does"], json.load(open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8"))["entries"]["pd_chamfer"]["card"]["does"])
        for k in ("inputs", "inputNotes", "links", "effects", "returns", "examples"):
            self.assertIn(k, c)
        for k in ("refusals", "refusalNotes", "hints", "description", "inputSchema", "rules"):
            self.assertNotIn(k, c)
        self.assertNotIn("description", json.dumps(c["inputs"]))

    def test_refusals_and_hints_when_asked(self):
        c = card(child()["cardRefusals"])
        self.assertEqual(set(c), {"tool", "refusals", "refusalNotes"})
        self.assertTrue(any("size2 or angle" in r["message"] for r in c["refusals"]))
        self.assertIn("hints", card(child()["cardHint"]))
        self.assertIn("hints", card(child(1)["cardHintDefault"]))
        self.assertNotIn("hints", card(child()["cardHintDefault"]))

    def test_what_takes_one_subject(self):
        c = card(child()["cardSub"])
        self.assertEqual(set(c), {"tool", "inputNotes", "links"})
        self.assertEqual(set(c["inputNotes"]), {"size2"})
        self.assertTrue(all("size2" in L["inputs"] for L in c["links"]))

    def test_what_refuses_an_unknown_kind(self):
        bad = child()["cardBad"]
        self.assertTrue(bad["isError"])
        self.assertIn("nosuch is not a card field", bad["body"]["error"]["message"])

    def test_hints_in_a_batch_row_and_a_kind_this_card_has_not(self):
        row = child()["batchHint"]["body"]["results"][0]["result"]
        self.assertIn("hints", row["tools"][0])
        r = child()["noHintAsked"]
        self.assertFalse(r["isError"], r)

    def test_the_list_carries_does_and_a_bare_schema(self):
        ls = child()["listing"]
        self.assertTrue(ls[0]["description"])
        self.assertNotIn("description", json.dumps(ls[0]["inputSchema"]))
        hub = child()["hubListing"]
        from agentlink import cards

        self.assertEqual(hub["description"], cards.hub_cards()["session_state"]["does"])
        self.assertNotIn("description", json.dumps(hub["inputSchema"]))


class Answers(unittest.TestCase):
    def test_what_narrows_an_answer_and_drops_health_without_a_fault(self):
        self.assertEqual(child()["ansWhat"]["body"], {"volume": 10.0})

    def test_health_of_a_sound_shape_goes_when_not_asked(self):
        self.assertEqual(child()["sound"]["body"], {"volume": 5.0})

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

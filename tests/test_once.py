# SPDX-License-Identifier: LGPL-2.1-or-later
"""Standing words said once a conversation (agentlink/once.py), a batch from
a file answered from its record, batch { read, at }, and batch's schema
listing every argument it reads. Each cut proves (a) the fact is still
reachable and (b) the reply got smaller."""
import ast
import copy
import json
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import batchrec, chain, once  # noqa: E402
from agentlink.protocol import Server, Tool, compact  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")

NOTE = "The previous document stays open: doc_switch { document } returns to it (doc_open { path } when it was saved and closed)."
OVERLAP = once.HEALTH_TODOS["overlap"]


def data_tool(name, entry, fn):
    t = Tool(name, "d", {"type": "object", "properties": {}}, fn)
    t.entry = entry
    return t


class Thin(unittest.TestCase):
    def setUp(self):
        self.s = types.SimpleNamespace()
        self.entry = {"answer": {"fields": {"document": "=d.Name", "note": NOTE, "made": {"fmt": "{n} made by the call, a fmt template of at least sixty characters"}}}}
        self.tool = data_tool("doc_new", self.entry, None)

    def answer(self, doc="A"):
        return {"document": doc, "note": NOTE, "made": "3 made by the call, a fmt template of at least sixty characters"}

    def test_a_literal_note_is_said_once_then_named(self):
        first = once.thin_reply(self.s, self.tool, self.answer("A"))
        self.assertEqual(first["note"], NOTE)
        self.assertNotIn("saidBefore", first)
        full = len(compact(self.answer("B")))
        second = once.thin_reply(self.s, self.tool, self.answer("B"))
        self.assertNotIn("note", second)
        self.assertEqual(second["saidBefore"], ["note"])
        self.assertEqual(second["document"], "B")  # the call's own facts stay
        self.assertEqual(second["made"], self.answer()["made"])  # a fmt value is the call's: never left out
        self.assertLess(len(compact(second)), full - 80)  # (b) smaller
        self.assertEqual(once.said(self.s, "doc_new"), {"note": NOTE})  # (a) reachable

    def test_other_words_are_said_again_and_a_new_conversation_says_all(self):
        once.thin_reply(self.s, self.tool, self.answer())
        other = dict(self.answer(), note="Another standing text of this tool, long enough to count as one.")
        self.entry["answer"]["fields"]["other"] = other["note"]
        once._literals.clear()
        self.assertIn("note", once.thin_reply(self.s, self.tool, other))
        once.reset(self.s)
        self.assertEqual(once.thin_reply(self.s, self.tool, self.answer())["note"], NOTE)

    def test_a_value_not_written_in_the_entry_is_never_left_out(self):
        words = "words the call itself put together from what it found, sixty characters or more"
        for _ in range(3):
            self.assertEqual(once.thin_reply(self.s, self.tool, {"note": words})["note"], words)

    def test_a_tool_written_in_code_keeps_its_words_unless_registered(self):
        t = Tool("coded_x", "d", {}, None)
        words = "A coded tool's note that nobody registered as standing, long enough to count."
        for _ in range(2):
            self.assertEqual(once.thin_reply(self.s, t, {"note": words})["note"], words)
        machine = {"chip": "Apple M5", "perfCores": 4, "memoryGB": 24.0}
        once.thin_reply(self.s, "session_state", {"bodies": [], "machine": dict(machine)})
        again = once.thin_reply(self.s, "session_state", {"bodies": [], "machine": dict(machine)})
        self.assertNotIn("machine", again)
        self.assertEqual(once.said(self.s, "session_state")["machine"], machine)

    def test_health_advice_once_and_the_standing_failure_while_it_stands(self):
        def h(verdict, todo):
            return {"health": {"ok": False, "verdict": verdict, "todo": todo}}

        v = "2 objects still failing from before this call: Left, Dimension002"
        a = once.thin_reply(self.s, "part_transform", h("Trim: valid, closed, 1 solid; Trim interferes with Cube: 5 mm³; " + v, OVERLAP))
        self.assertEqual(a["health"]["todo"], OVERLAP)
        self.assertIn(v, a["health"]["verdict"])
        b = once.thin_reply(self.s, "part_transform", h("Trim: valid, closed, 1 solid; Trim interferes with Cube: 9 mm³; " + v,
                                                         "fix the input of the first failed object; " + OVERLAP))
        self.assertEqual(b["health"]["todo"], "fix the input of the first failed object")  # other advice stays
        self.assertNotIn("still failing", b["health"]["verdict"])
        self.assertIn("interferes with Cube: 9", b["health"]["verdict"])  # the reading itself stays
        self.assertEqual(b["health"]["saidBefore"], ["failing", "overlap"])
        c = once.thin_reply(self.s, "x", {"health": {"verdict": v}})
        self.assertEqual(c["health"]["verdict"], "as before")
        once.thin_reply(self.s, "x", {"health": {"verdict": "nothing red"}})  # fixed: the next failure is news
        self.assertEqual(once.thin_reply(self.s, "x", {"health": {"verdict": v}})["health"]["verdict"], v)
        self.assertEqual(once.health_said(self.s)["overlap"], OVERLAP)  # reachable

    def test_a_sketch_readings_dof_note_once(self):
        def reading(dof):
            return {"sketch": "S", "state": {"sketch": "S", "dof": dof, "readyForFeature": True, "note": f"{dof} degrees of freedom: {once.DOF_NOTE}"}}

        self.assertIn("note", once.thin_reply(self.s, "sketch_add", reading(4))["state"])
        later = once.thin_reply(self.s, "sketch_constrain", reading(3))
        self.assertNotIn("note", later["state"])
        self.assertEqual(later["state"]["dof"], 3)  # the count stays, as dof
        self.assertEqual(later["state"]["saidBefore"], ["note"])
        top = once.thin_reply(self.s, "sketch_state", reading(2)["state"])  # sketch_state's own answer is the reading
        self.assertNotIn("note", top)
        self.assertIn(once.DOF_NOTE, once.health_said(self.s)["sketchNote"])  # reachable

    def test_a_batch_thins_its_calls_in_order_and_never_a_refusal(self):
        tools = {"doc_new": self.tool}
        reply = {"results": [{"tool": "doc_new", "ok": True, "result": self.answer("A")},
                             {"tool": "doc_new", "ok": False, "error": {"code": "invalid_input", "message": NOTE}},
                             {"tool": "doc_new", "ok": True, "result": self.answer("B")}], "ran": 3}
        out = once.thin_reply(self.s, "batch", reply, tools)
        self.assertEqual(out["results"][0]["result"]["note"], NOTE)
        self.assertEqual(out["results"][1]["error"]["message"], NOTE)
        self.assertEqual(out["results"][2]["result"]["saidBefore"], ["note"])

    def test_the_batch_notes_once(self):
        got = {"ran": 1, "results": [{"tool": "a", "ok": True, "result": {}}]}
        one = once.thin_reply(self.s, "batch", batchrec.to_reply(copy.deepcopy(got), 0, "p", 1))
        two = once.thin_reply(self.s, "batch", batchrec.to_reply(copy.deepcopy(got), 0, "p", 1))
        self.assertEqual(one["note"], batchrec.TO_NOTE)
        self.assertNotIn("note", two)
        self.assertEqual(two["saidBefore"], ["note"])
        stopped = dict(copy.deepcopy(got), note="Stopped after 70 s (budget 60 s): the rest from: 1.")
        three = once.thin_reply(self.s, "batch", batchrec.to_reply(stopped, 0, "p", 1))
        self.assertTrue(three["note"].startswith("Stopped after"))  # the batch's own note: always


class ThroughTheServer(unittest.TestCase):
    """The same through protocol.Server: a call's answer, and initialize."""

    def test_initialize_starts_a_new_conversation(self):
        entry = {"answer": {"fields": {"note": NOTE}}}
        t = data_tool("doc_new", entry, lambda a: {"document": "D", "note": NOTE})
        srv = Server("t", "0", [t])
        srv.session = types.SimpleNamespace()

        def call():
            r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "doc_new", "arguments": {}}})
            return json.loads(r["result"]["content"][0]["text"])

        self.assertEqual(call()["note"], NOTE)
        self.assertEqual(call()["saidBefore"], ["note"])
        srv.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}})
        self.assertEqual(call()["note"], NOTE)

    def test_inside_a_batch_nothing_is_thinned(self):
        t = data_tool("doc_new", {"answer": {"fields": {"note": NOTE}}}, lambda a: {"note": NOTE})
        srv = Server("t", "0", [t])
        srv.session = types.SimpleNamespace(batch_now={"i": 0})
        for _ in range(2):
            r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "doc_new", "arguments": {}}})
            self.assertEqual(json.loads(r["result"]["content"][0]["text"])["note"], NOTE)


class FileBatch(unittest.TestCase):
    """A batch from a file answers from its record; read gives any part back."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.got = {"ran": 3, "results": [{"tool": "part_primitive", "ok": True, "result": {"body": f"B{i}", "volume": 1000.0 * i, "area": 600.0,
                                                                                            "box": [10.0, 10.0, 10.0], "health": {"ok": True, "verdict": f"B{i}: valid, closed, 1 solid"}}}
                                          for i in range(3)], "record": "r"}
        self.path = os.path.join(self.d, "rec.json")
        with open(self.path, "w") as f:
            json.dump(self.got, f)

    def test_a_file_batch_answers_a_line_a_call(self):
        short = batchrec.record_reply(copy.deepcopy(self.got), 0, self.path, True, None)
        self.assertEqual([r["health"] for r in short["results"]], [f"B{i}: valid, closed, 1 solid" for i in range(3)])
        self.assertEqual(short["written"]["path"], self.path)
        self.assertNotIn("record", short)  # written is the record
        self.assertLess(len(compact(short)) - len(batchrec.TO_NOTE), len(compact(self.got)))  # (b), the note once a conversation
        # (a) every answer is still there, read back with read and at.
        part = batchrec.read_part(self.path, "rec.json", "results.2.result.volume")
        self.assertEqual(part["value"], 2000.0)
        self.assertEqual(batchrec.read_part(self.path, "rec.json")["value"], self.got)

    def test_full_and_a_batch_of_calls_answer_whole(self):
        self.assertIs(batchrec.record_reply(self.got, 0, self.path, True, "full"), self.got)
        self.assertIs(batchrec.record_reply(self.got, 0, self.path, False, None), self.got)
        self.assertIs(batchrec.record_reply(self.got, 0, None, True, None), self.got)  # no record: whole
        self.assertEqual(batchrec.record_reply(copy.deepcopy(self.got), 0, self.path, False, "counts")["counts"], {"ok": 3, "refused": 0})

    def test_read_refuses_saying_what_is_there(self):
        with self.assertRaises(chain.Miss) as e:
            batchrec.read_part(self.path, "rec.json", "results.7")
        self.assertIn("a list of 3", e.exception.message)
        self.assertTrue(e.exception.message.startswith("at "))
        with self.assertRaises(chain.Miss) as e:
            batchrec.read_part(os.path.join(self.d, "nope.json"), "nope.json", None)
        self.assertTrue(e.exception.message.startswith("read: nope.json"))


class BatchSchema(unittest.TestCase):
    """Every argument batch reads is in its inputSchema (a client sends only
    what the schema lists), read from tools.py's source."""

    def test_every_argument_is_listed(self):
        with open(os.path.join(ROOT, "agentlink", "tools.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        read, listed = set(), None
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and fn.name in ("batch", "_batch_read"):
                for n in ast.walk(fn):
                    if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "get" and getattr(n.func.value, "id", None) == "a" \
                            and n.args and isinstance(n.args[0], ast.Constant):
                        read.add(n.args[0].value)
            if isinstance(fn, ast.Call) and getattr(fn.func, "id", None) == "Tool" and fn.args and getattr(fn.args[0], "value", None) == "batch":
                listed = set(ast.literal_eval(fn.args[2].args[0]))
        self.assertTrue(read >= {"calls", "file", "to", "lines", "from", "build", "read", "at"}, read)
        self.assertEqual(sorted(read - listed), [])


class Guides(unittest.TestCase):
    def test_the_index_names_each_section_once(self):
        from agentlink import guideidx

        folder = os.path.join(ROOT, "agentlink", "guides")
        old = new = 0
        for n in sorted(os.listdir(folder)):
            if not n.endswith(".md"):
                continue
            with open(os.path.join(folder, n), encoding="utf-8") as f:
                e = guideidx.entry(n[:-3], f.read())
            new += len(compact(e))
            was = dict(e, sections=list(e["sectionTokens"]))
            if "later" in e:
                was["later"] = [dict(x, tokens=e["sectionTokens"][x["section"]]) for x in e["later"]]
            old += len(compact(was))
            for x in e.get("later", []):
                self.assertIn(x["section"], e["sectionTokens"])  # (a) its cost is still there
        self.assertLess(new, old * 0.8)  # (b)


if __name__ == "__main__":
    unittest.main()

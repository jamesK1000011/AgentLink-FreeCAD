# SPDX-License-Identifier: LGPL-2.1-or-later
# Measure before claim (owner, 22 Nov 2026; agentlink/measured.py): doc_save
# of the agent's own document is refused while a change to its geometry came
# after its last measure. The rule's logic in plain Python, then the
# session's glue, doc_save through the call path and a fast block on
# stand-in FreeCAD modules.
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentlink import measured  # noqa: E402

LABELS = ["Bracket", "Body"]


class Sess:
    """A session as measured.py sees it: a __dict__ for the order numbers."""


def sigs(vol):
    return {"Bracket": [vol, 50.0, 6, 1, [10, 10, 10], [0, 0, 0]]}


class Rule(unittest.TestCase):
    def setUp(self):
        self.s, self.rec = Sess(), {}
        os.environ.pop("AGENTLINK_MEASURE_GATE", None)

    def change(self, before, step=3):
        measured.before_change(self.rec, lambda: before)
        measured.changed(self.s, self.rec, step)

    def test_change_then_save_refused(self):
        self.change({})
        w = measured.gate_words(self.rec, "Part1", sigs(1000.0), True)
        self.assertIsNotNone(w)
        for x in ("Part1 changed after it was last measured (step 3)", "read its geometry first, then save",
                  "Changed: Bracket", 'body_check { body: "Bracket" }', 'get { what: "Bracket.volume" }', "volume, box and solids"):
            self.assertIn(x, w)

    def test_change_measure_save_ok(self):
        self.change({})
        measured.measured(self.s, self.rec, sigs(1000.0))
        self.assertIsNone(measured.gate_words(self.rec, "Part1", sigs(1000.0), True))

    def test_measure_then_change_refused(self):
        measured.measured(self.s, self.rec, sigs(1000.0))
        self.change(sigs(1000.0), step=5)
        w = measured.gate_words(self.rec, "Part1", sigs(1025.7), True)
        self.assertIn("(step 5)", w)

    def test_person_document_never_refused(self):
        self.change({})
        self.assertIsNone(measured.gate_words(self.rec, "Theirs", sigs(1000.0), False))

    def test_env_off(self):
        self.change({})
        for v in ("0", "off"):
            with mock.patch.dict(os.environ, {"AGENTLINK_MEASURE_GATE": v}):
                self.assertIsNone(measured.gate_words(self.rec, "Part1", sigs(1000.0), True))

    def test_no_bodies_or_nothing_changed(self):
        self.assertIsNone(measured.gate_words(self.rec, "Part1", sigs(1000.0), True))  # nothing changed since open
        self.change({})
        self.assertIsNone(measured.gate_words(self.rec, "Part1", {}, True))  # no body

    def test_change_that_left_geometry_alone(self):
        self.change(sigs(1000.0))  # a label or a colour: the numbers are as before
        self.assertIsNone(measured.gate_words(self.rec, "Part1", sigs(1000.0), True))

    def test_names_each_changed_body(self):
        before = {"A": [1], "B": [2], "C": [3]}
        self.change(before)
        w = measured.gate_words(self.rec, "Asm", {"A": [1], "B": [9], "D": [4]}, True)
        self.assertIn("Changed: B, C, D.", w)

    def test_what_counts_as_a_measure(self):
        m = measured.is_measure
        self.assertTrue(m("body_check", {"body": "Bracket"}, LABELS))
        self.assertTrue(m("body_check", {}, LABELS))
        self.assertTrue(m("session_state", {}, LABELS))
        self.assertTrue(m("measure", {"a": "Bracket"}, LABELS))
        self.assertTrue(m("measure", {"a": "Pad"}, LABELS, lambda r: r == "Pad"))  # a PartDesign feature
        self.assertTrue(m("measure_mass", {"body": "Bracket"}, LABELS))
        self.assertTrue(m("object_get", {"object": "Bracket"}, LABELS))
        self.assertTrue(m("object_get", {"object": "Bracket", "filter": "Shape"}, LABELS))
        self.assertTrue(m("object_get", {"object": "Bracket", "filter": ["Shape"]}, LABELS))
        self.assertTrue(m("get", {"what": "Bracket.volume"}, LABELS))
        self.assertTrue(m("get", {"what": ["Pad.Length", "body.area"]}, LABELS))

    def test_reads_that_are_not_measures(self):
        m = measured.is_measure
        self.assertFalse(m("measure", {"a": "Bracket.Edge7"}, LABELS))  # an edge
        self.assertFalse(m("measure", {"a": "Bracket", "b": "Body"}, LABELS))  # a distance
        self.assertFalse(m("measure", {"a": "Sketch"}, LABELS, lambda r: False))
        self.assertFalse(m("object_get", {"object": "Bracket", "filter": "Placement"}, LABELS))
        self.assertFalse(m("object_get", {"object": "Sketch"}, LABELS))
        self.assertFalse(m("get", {"what": "Pad.Length"}, LABELS))
        self.assertFalse(m("get", {"what": "Bracket.Edge7.length"}, LABELS))
        self.assertFalse(m("get", {"what": "sketch.dof"}, LABELS))
        self.assertFalse(m("object_list", {}, LABELS))
        self.assertFalse(m("view_render", {}, LABELS))
        self.assertFalse(m("body_check", {}, []))  # no body: nothing measured


# ---- the session's glue, the call path and a fast block, on stand-ins -------------------------

from test_stem_findings_more import run_stub  # noqa: E402

SETUP = """
    import os, tempfile
    from agentlink.tools import Session
    from agentlink import protocol, fastpath
    from agentlink.protocol import Tool
    body = Obj("Body", "PartDesign::Body", Shape(1), "Bracket")
    doc = Doc([body])
    doc.getObject = lambda n: next((x for x in doc.Objects if x.Name == n), None)
    doc.getObjectsByLabel = lambda n: [x for x in doc.Objects if x.Label == n]
    s = Session.__new__(Session)
    s.doc, s.agent_docs, s.out_dir = doc, {"Stem"}, tempfile.mkdtemp()
    s.__dict__["last_step"] = None

    def grow(a):
        body.Shape = Shape(1)
        body.Shape.Volume = 10.0 + float(a.get("by", 25.7))
        s.note_change()
        return {"ok": True}

    def relabel(a):
        s.note_change()  # a change that leaves the geometry as it is
        return {"ok": True}

    saved = []
    def save(a):
        saved.append(1)
        return {"path": "/tmp/Stem.FCStd", "bytes": 1}

    def measure(a):
        o = [x for x in doc.Objects if x.Name == a.get("a") or x.Label == a.get("a")][0]
        return {"a": {"volume": o.Shape.Volume, "area": o.Shape.Area}}

    obj = {"type": "object", "properties": {}, "additionalProperties": True}
    tools = [Tool("grow", "Grow the body.", obj, grow), Tool("relabel", "Relabel.", obj, relabel),
             Tool("doc_save", "Save.", obj, save), Tool("measure", "Measure.", obj, measure),
             Tool("body_check", "Check.", obj, lambda a: {"valid": True}),
             Tool("fast", "Fast.", obj, lambda a: fastpath.fast_tool(srv, s, a))]
    srv = protocol.Server("standin", "0", tools, "")
    srv.session, s.server = s, srv
    srv.on_call = s.record_call

    def call(name, args=None):
        r = srv.call({"name": name, "arguments": args or {}})
        return json.loads(r["content"][0]["text"]) | ({"isError": True} if r.get("isError") else {})
"""


def stub(body):
    import textwrap

    return run_stub(textwrap.dedent(SETUP) + textwrap.dedent(body))


class OnStandIns(unittest.TestCase):
    def test_call_path(self):
        out = stub("""
            r = {}
            call("grow")
            r["refused"] = call("doc_save")
            r["savedAfterRefusal"] = len(saved)
            call("body_check", {"body": "Bracket"})
            r["afterCheck"] = call("doc_save")
            call("grow", {"by": 5})
            r["again"] = call("doc_save")
            call("measure", {"a": "Bracket", "b": "Bracket"})  # a distance: not a measure
            r["afterDistance"] = call("doc_save").get("isError", False)
            call("measure", {"a": "Bracket"})
            r["afterMeasure"] = call("doc_save").get("isError", False)
            call("relabel")
            r["afterRelabel"] = call("doc_save").get("isError", False)
            call("grow", {"by": 7})
            s.agent_docs = set()
            r["persons"] = call("doc_save").get("isError", False)
            s.agent_docs = {"Stem"}
            os.environ["AGENTLINK_MEASURE_GATE"] = "0"
            r["envOff"] = call("doc_save").get("isError", False)
            print(json.dumps(r, default=repr))
        """)
        ref = out["refused"]
        self.assertTrue(ref["isError"])
        self.assertEqual(ref["error"]["code"], "invalid_input")
        self.assertEqual(ref["error"].get("status"), "not_started")
        self.assertIn("Stem changed after it was last measured", ref["error"]["message"])
        self.assertIn("Changed: Bracket", ref["error"]["message"])
        self.assertEqual(out["savedAfterRefusal"], 0)
        self.assertNotIn("isError", out["afterCheck"])
        self.assertTrue(out["again"]["isError"])
        self.assertTrue(out["afterDistance"])
        self.assertFalse(out["afterMeasure"])
        self.assertFalse(out["afterRelabel"])
        self.assertFalse(out["persons"])
        self.assertFalse(out["envOff"])

    def test_fast_block(self):
        out = stub("""
            r = {}
            r["withGet"] = call("fast", {"do": [{"tool": "grow", "arguments": {}}, {"get": "Bracket.volume", "as": "v"}, {"tool": "doc_save", "arguments": {}}]})
            r["saved"] = len(saved)
            r["without"] = call("fast", {"do": [{"tool": "grow", "arguments": {"by": 3}}, {"tool": "doc_save", "arguments": {}}]})
            r["getFirst"] = call("fast", {"do": [{"get": "Bracket.volume"}, {"tool": "grow", "arguments": {"by": 4}}, {"tool": "doc_save", "arguments": {}}]})
            print(json.dumps(r, default=repr))
        """)
        self.assertNotIn("isError", out["withGet"], out["withGet"])
        self.assertEqual(out["saved"], 1)
        for k in ("without", "getFirst"):
            self.assertTrue(out[k].get("isError"), out[k])
            self.assertIn("changed after it was last measured", out[k]["error"]["message"])


if __name__ == "__main__":
    unittest.main()

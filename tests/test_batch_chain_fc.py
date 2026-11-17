# SPDX-License-Identifier: LGPL-2.1-or-later
# batch's answer chaining (a call's to, $file, $from), build: "end" (one
# recompute for a run of sketch edits and property sets) and guide_read's
# index, through the server on a real document.
import json
import os
import unittest

from _fc import HAVE, caller, server


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class BatchChain(unittest.TestCase):
    def setUp(self):
        self.session, srv = server()
        self.call = caller(srv)
        self.call("doc_new", {"name": "Chain"})

    def ok(self, name, args=None):
        err, out = self.call(name, args)
        self.assertFalse(err, out)
        return out

    def box(self, name):
        return {"tool": "part_primitive", "arguments": {"kind": "box", "size": [5, 6, 7], "name": name}}

    def test_a_calls_answer_to_a_file_and_back(self):
        b = self.ok("batch", {"calls": [
            {**self.box("Lid"), "to": "lid.json"},
            {"tool": "session_state", "arguments": {}, "to": "state.json"},
            {"tool": "object_get", "arguments": {"object": {"$file": "state.json", "$at": "bodies.0.name"}, "filter": "Length"}},
            {"tool": "object_get", "arguments": {"object": {"$from": 1, "$at": "bodies.-1.name"}, "filter": "Width"}},
        ]})
        self.assertEqual(b["ran"], 4, b)
        first = b["results"][0]
        self.assertNotIn("result", first)
        self.assertTrue(os.path.isfile(first["written"]["path"]))
        self.assertEqual(first["written"]["bytes"], os.path.getsize(first["written"]["path"]))
        self.assertIn("keys", first)
        with open(os.path.join(self.session.out_dir, "state.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["bodies"][0]["name"], "Lid")
        self.assertIn("Length", b["results"][2]["result"]["properties"])
        self.assertIn("Width", b["results"][3]["result"]["properties"])

    def test_a_reference_that_is_not_there_refuses_that_call(self):
        n = len(self.ok("session_state")["bodies"])
        err, b = self.call("batch", {"calls": [self.box("A"), {"tool": "object_get", "arguments": {"object": {"$from": 0, "$at": "nothere.0"}}}]})
        self.assertFalse(err, b)
        self.assertEqual(b["stopped"], 1)
        e = b["results"][1]["error"]
        self.assertEqual(e["code"], "not_found")
        self.assertIn("the keys:", e["message"])
        self.assertIn("was not run", e["message"])
        # It counts as a refusal: the batch is rolled back whole.
        self.assertEqual(len(self.ok("session_state")["bodies"]), n)
        err, b = self.call("batch", {"calls": [{"tool": "object_get", "arguments": {"object": {"$file": "missing.json"}}}]})
        self.assertIn("no such file", b["results"][0]["error"]["message"])

    def test_paths_are_checked(self):
        err, e = self.call("batch", {"calls": [{**self.box("A"), "to": "/etc/agentlink-test.json"}]})
        self.assertTrue(err)
        self.assertIn("Nothing was run", e["error"]["message"])
        err, e = self.call("batch", {"calls": [{**self.box("A"), "to": "answer.py"}]})
        self.assertTrue(err)
        err, b = self.call("batch", {"calls": [{"tool": "object_get", "arguments": {"object": {"$file": "~/.ssh/known.json"}}}]})
        self.assertIn("off limits", b["results"][0]["error"]["message"])
        self.assertEqual(len(self.ok("session_state")["bodies"]), 0)

    def test_calls_without_references_are_as_before(self):
        b = self.ok("batch", {"calls": [self.box("A"), {"tool": "session_state", "arguments": {}}]})
        self.assertEqual(b["ran"], 2)
        self.assertIn("result", b["results"][0])
        for k in ("build", "builds", "buildNote"):
            self.assertNotIn(k, b)

    def sketch_calls(self):
        return [
            {"tool": "sketch_add", "arguments": {"sketch": "Sk", "items": [{"kind": "rectangle", "center": [0, 0], "size": [40, 20]}]}},
            {"tool": "sketch_add", "arguments": {"sketch": "Sk", "items": [{"kind": "circle", "center": [0, 0], "radius": 4}]}},
            {"tool": "sketch_constrain", "arguments": {"sketch": "Sk", "constraints": [
                # The circle's id from the call before, not through the conversation.
                {"type": "radius", "refs": [[{"$from": 1, "$at": "added.0.ids.0"}]], "value": 4}]}},
        ]

    def new_sketch(self):
        self.ok("pd_body_new", {"name": "B"})
        self.ok("sketch_new", {"body": "B", "plane": "XY", "name": "Sk"})

    def test_build_end_recomputes_once(self):
        from agentlink import health

        self.new_sketch()
        doc = self.session.doc
        seen = []

        class Obs:
            def slotRecomputedDocument(self, d):
                seen.append(d.Name)

        import FreeCAD

        obs = Obs()
        FreeCAD.addDocumentObserver(obs)
        try:
            b = self.ok("batch", {"build": "end", "calls": self.sketch_calls()})
        finally:
            FreeCAD.removeDocumentObserver(obs)
        self.assertEqual(b["ran"], 3, b)
        self.assertEqual(len(seen), 1, seen)
        self.assertFalse(doc.RecomputesFrozen)
        self.assertEqual(b["build"], "end")
        self.assertEqual(len(b["builds"]), 1)
        build = b["builds"][0]
        self.assertEqual((build["when"], build["held"], build["calls"]), ("end", 3, [0, 2]))
        self.assertGreater(build["recomputed"], 0)
        for r in b["results"]:
            res = r["result"]
            self.assertEqual(res["build"], "held")
            self.assertEqual(res["health"]["build"], "held")
            # The solver's reading is fresh; the wires are the build's.
            self.assertIn("dof", res["state"])
            self.assertNotIn("closedWires", res["state"])
            self.assertNotIn("readyForFeature", res["state"])
        if health.enabled():
            self.assertIn("verdict", build["health"])
        # After the build the sketch reads as built: both profiles closed.
        st = self.ok("sketch_state", {"sketch": "Sk", "detail": False})
        self.assertEqual(st["closedWires"], 2, st)
        self.assertEqual([o.Label for o in doc.Objects if "Touched" in o.State and o.TypeId == "Sketcher::SketchObject"], [])

    def test_a_tool_that_builds_for_itself_builds_first(self):
        self.new_sketch()
        b = self.ok("batch", {"build": "end", "calls": self.sketch_calls()[:1] + [
            {"tool": "sketch_state", "arguments": {"sketch": "Sk", "detail": False}},
            {"tool": "pd_pad", "arguments": {"sketch": "Sk", "length": 5}},
            {"tool": "object_set", "arguments": {"object": "Pad", "values": {"Length": 8}}},
        ]})
        self.assertEqual(b["ran"], 4, b)
        self.assertEqual([x["when"] for x in b["builds"]], ["before call 1 (sketch_state)", "end"])
        # The read after the held call saw the built sketch, and the pad a real volume.
        self.assertEqual(b["results"][1]["result"]["closedWires"], 1)
        self.assertNotIn("build", b["results"][2]["result"])
        self.assertAlmostEqual(b["results"][2]["result"]["volume"], 40 * 20 * 5, delta=1)
        self.assertEqual(b["results"][3]["result"]["build"], "held")
        # The property set was built at the end: the body is 8 thick.
        body = next(x for x in self.ok("session_state")["bodies"] if x["name"] == "B")
        self.assertAlmostEqual(body["volume"], 40 * 20 * 8, delta=1)

    def test_a_refusal_in_a_held_run_rolls_back(self):
        self.new_sketch()
        doc = self.session.doc
        sk = doc.getObjectsByLabel("Sk")[0]
        err, b = self.call("batch", {"build": "end", "calls": self.sketch_calls()[:2] + [{"tool": "sketch_add", "arguments": {"sketch": "Sk", "items": [{"kind": "nope"}]}}]})
        self.assertFalse(err, b)
        self.assertEqual(b["stopped"], 2)
        self.assertEqual(len(sk.Geometry), 0)
        self.assertFalse(doc.RecomputesFrozen)

    def test_a_build_that_breaks_a_feature_stops_the_batch(self):
        self.new_sketch()
        self.ok("sketch_add", {"sketch": "Sk", "items": [{"kind": "rectangle", "center": [0, 0], "size": [40, 20]}]})
        self.ok("pd_pad", {"sketch": "Sk", "length": 5})
        doc = self.session.doc
        sk = doc.getObjectsByLabel("Sk")[0]
        n = len(sk.Geometry)
        # One side of the pad's profile deleted: only the rebuild shows it.
        err, b = self.call("batch", {"build": "end", "calls": [{"tool": "sketch_edit", "arguments": {"sketch": "Sk", "delete": [0]}}]})
        self.assertFalse(err, b)
        self.assertTrue(b.get("buildFailed"), b)
        self.assertFalse(b["builds"][-1]["health"]["ok"])
        self.assertEqual(len(sk.Geometry), n)
        self.assertFalse(doc.RecomputesFrozen)
        body = next(x for x in self.ok("session_state")["bodies"] if x["name"] == "B")
        self.assertAlmostEqual(body["volume"], 40 * 20 * 5, delta=1)

    def test_the_persons_own_switch(self):
        self.new_sketch()
        doc = self.session.doc
        doc.RecomputesFrozen = True
        try:
            b = self.ok("batch", {"build": "end", "calls": self.sketch_calls()[:1]})
            self.assertIn("already switched off", b["buildNote"])
            self.assertNotIn("builds", b)
            self.assertTrue(doc.RecomputesFrozen)
        finally:
            doc.RecomputesFrozen = False

    def test_build_is_end_or_each(self):
        err, e = self.call("batch", {"build": "later", "calls": []})
        self.assertTrue(err)


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class GuideRead(unittest.TestCase):
    def setUp(self):
        self.session, srv = server()
        self.call = caller(srv)

    def test_the_index_and_the_ways_to_read(self):
        err, idx = self.call("guide_read")
        self.assertFalse(err, idx)
        by = {g["topic"]: g for g in idx["guides"]}
        self.assertEqual(list(by["model"]["sectionTokens"])[0], "Start here")
        self.assertTrue(by["model"]["later"])
        self.assertNotIn("sections", by["sketch"])  # the names once: sectionTokens' keys
        err, one = self.call("guide_read", {"topic": "model", "section": "traps"})
        self.assertTrue(one["text"].startswith("## traps"))
        err, two = self.call("guide_read", {"topic": "model", "section": ["Start here", "workflow"]})
        self.assertIn("## workflow", two["text"])
        self.assertNotIn("## traps", two["text"])
        err, whole = self.call("guide_read", {"topic": "model"})
        self.assertNotIn("<!-- later", whole["text"])
        err, many = self.call("guide_read", {"topic": list(by)})
        self.assertFalse(err, many)
        self.assertTrue(many["next"])
        self.assertEqual(many["read"][0]["topic"], list(by)[0])
        err, rest = self.call("guide_read", {"topic": many["next"]})
        self.assertFalse(err, rest)
        err, e = self.call("guide_read", {"topic": ["model", "nope"]})
        self.assertTrue(err)
        self.assertIn("nope", e["error"]["message"])


if __name__ == "__main__":
    unittest.main()

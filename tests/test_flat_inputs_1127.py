# SPDX-License-Identifier: LGPL-2.1-or-later
# One shape or one item for each call (27 Nov): sketch_add takes one shape
# (kind and its inputs beside tool), sketch_constrain one constraint, the
# edge inputs of the fillet and chamfer tools one selector or a list of
# references. tool_find, tool_groups and job_start say card and card and
# job (a step has the key tool). Each card gives two flat examples, plain
# and ready; an option row and the pick how-to are flat steps.
# Three groups of tests:
#   - plain Python (schemas, the cards, the options, the text scan);
#   - the hub on stand-ins (the "flat1127" case of test_fastpath.py): the
#     tools by run, batch and fast;
#   - the sketch tools on the stand-in FreeCAD of tests/_datapd_standin.py
#     (a child process): sketch_add and sketch_constrain make what they
#     are told. This is not FreeCAD: see the notes of that file.
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import callshape, examples, options, protocol, runners  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402

KINDS = ["line", "polyline", "arc", "arc3", "circle", "circle3", "ellipse", "parabola", "hyperbola", "bspline", "rectangle", "rounded_rectangle",
         "polygon", "slot", "arc_slot", "point"]


def schema(name):
    return runners.tool(name, runners.entries()[name], {}).schema


def refused(name, args):
    try:
        protocol.check_input(schema(name), args, name)
    except ToolError as e:
        return e.message
    return None


# ---- the stand-in server (tests/test_fastpath.py, case flat1127) --------------------------

_server = []


def hub():
    if not _server:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_fastpath.py"), "child", "flat1127"], capture_output=True, text=True, timeout=180, cwd=ROOT)
        if r.returncode != 0:
            raise AssertionError("child flat1127 failed:\n" + r.stderr[-4000:])
        _server.append(json.loads(r.stdout.strip().splitlines()[-1]))
    return _server[0]


def said(r):
    b = r["body"]
    return b["error"]["message"] if "error" in b else json.dumps(b)


# ---- the stand-in FreeCAD (a child process) -----------------------------------------------

def _child():
    import tempfile

    import _datapd_standin

    fc = _datapd_standin.install()
    fc.patch()
    from agentlink.families import sketch

    def tool(session, name):
        return next(t for t in sketch.tools(session) if t.name == name)

    out = {}
    s = fc.Session(tempfile.mkdtemp())
    fc.drawing(s, fc.body(s, "Plate"), "PlateSketch")
    add = tool(s, "sketch_add")
    out["one"] = add.fn({"sketch": "PlateSketch", "kind": "rectangle", "center": [0, 0], "size": [40, 20], "dims": True, "name": "plate"})
    out["circle"] = add.fn({"sketch": "PlateSketch", "kind": "circle", "center": [5, 5], "diameter": 6})
    try:
        add.fn({"sketch": "PlateSketch", "kind": "rectangle", "center": [0, 0]})
    except ToolError as e:
        out["noSize"] = e.message
    con = tool(s, "sketch_constrain")
    out["con"] = con.fn({"sketch": "PlateSketch", "type": "radius", "refs": [4], "value": 3, "name": "hole_r"})
    from agentlink.families import pd_common

    out["edges"] = {"string": pd_common.edges_form("Edge3"), "selector": pd_common.edges_form({"type": "line", "axis": "z", "outside": True}),
                    "list": pd_common.edges_form(["Edge1", "Edge2"]), "form": pd_common.EDGES_FORM}
    bad = {}
    for k, v in (("objects", [{"near": [0, 0, 0]}]), ("nested", [["Edge1"]]), ("number", [3]), ("mixed", ["Edge1", {"near": [0, 0, 0]}])):
        try:
            pd_common.edges_form(v)
        except ToolError as e:
            bad[k] = e.message
    out["edgesBad"] = bad
    out["geometry"] = [type(g).__name__ for g in s.doc.getObject("PlateSketch").Geometry]
    print(json.dumps(out, default=repr))


_stand = []


def stand():
    if not _stand:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "child"], capture_output=True, text=True, timeout=180, cwd=ROOT)
        if r.returncode != 0:
            raise AssertionError("child failed:\n" + r.stderr[-4000:])
        _stand.append(json.loads(r.stdout.strip().splitlines()[-1]))
    return _stand[0]


# ---- sketch_add ---------------------------------------------------------------------------

class SketchAdd(unittest.TestCase):
    def test_the_shape_is_a_flat_typed_input_with_a_kind_enum(self):
        sch = schema("sketch_add")
        self.assertNotIn("items", sch["properties"])
        self.assertEqual(sch["properties"]["kind"]["enum"], KINDS)
        self.assertEqual(sch["required"], ["kind"])
        self.assertIs(sch["additionalProperties"], False)
        for k in ("center", "size", "radius", "diameter", "from", "to", "points", "closed", "construction", "dims", "name"):
            self.assertIn(k, sch["properties"], k)
            self.assertIn("description", sch["properties"][k], k)

    def test_one_rectangle_is_one_call(self):
        self.assertIsNone(refused("sketch_add", {"sketch": "S", "kind": "rectangle", "center": [0, 0], "size": [40, 20]}))

    def test_items_is_refused_with_the_flat_form(self):
        msg = refused("sketch_add", {"sketch": "S", "items": [{"kind": "circle", "center": [0, 0], "radius": 3}]})
        self.assertIn("sketch_add adds one shape for each call, so it has no items", msg)
        self.assertIn('{ "tool": "sketch_add", "kind": "rectangle", "center": [0, 0], "size": [40, 20] }', msg)
        self.assertIn("Several shapes are several calls: in a batch, or with each.", msg)

    def test_a_kind_it_has_not_is_refused_with_the_list(self):
        msg = refused("sketch_add", {"kind": "squiggle"})
        self.assertIn("one of " + ", ".join(KINDS), msg)

    def test_the_stand_in_makes_what_it_is_told(self):
        got = stand()
        self.assertEqual(got["one"]["added"][0]["kind"], "rectangle")
        self.assertEqual(got["one"]["added"][0]["ids"], [0, 1, 2, 3])
        self.assertEqual(len(got["one"]["added"]), 1)
        self.assertEqual(got["circle"]["added"][0]["kind"], "circle")
        self.assertEqual(got["geometry"].count("LineSegment"), 4)
        self.assertIn("noSize", got)

    def test_several_shapes_are_several_calls_in_a_batch_or_with_each(self):
        g = hub()
        self.assertFalse(g["twoBatch"]["isError"], g["twoBatch"])
        self.assertEqual([r["result"]["kind"] for r in g["twoBatch"]["body"]["results"]], ["rectangle", "circle"])
        self.assertEqual(g["eachBatch"]["body"]["done"], [0, 1])
        self.assertEqual([r["result"]["center"] for r in g["eachBatch"]["body"]["results"]], [[15, 15], [45, 15]])
        kinds = [a["kind"] for _t, a in g["seenSketch"] if a.get("kind") in KINDS]
        self.assertEqual(sorted(kinds), ["circle", "circle", "circle", "rectangle", "rectangle"])
        self.assertTrue(all("items" not in a for _t, a in g["seenSketch"] if a.get("kind") in KINDS))

    def test_by_run_and_through_the_hub(self):
        g = hub()
        self.assertFalse(g["addRun"]["isError"], g["addRun"])
        self.assertEqual(g["addRun"]["body"]["kind"], "rectangle")
        self.assertTrue(g["itemsRun"]["isError"])
        self.assertIn("has no items", said(g["itemsRun"]))
        self.assertTrue(g["badKind"]["isError"])


# ---- sketch_constrain ---------------------------------------------------------------------

class SketchConstrain(unittest.TestCase):
    def test_one_constraint_is_the_top_level_inputs(self):
        sch = schema("sketch_constrain")
        self.assertEqual(sorted(sch["properties"]), ["name", "refs", "sketch", "type", "value"])
        self.assertEqual(sch["required"], ["type"])
        self.assertIsNone(refused("sketch_constrain", {"sketch": "S", "type": "distance", "refs": [0], "value": 40}))

    def test_a_list_of_constraints_is_refused_with_the_flat_form(self):
        msg = refused("sketch_constrain", {"constraints": [{"type": "horizontal", "refs": [0]}]})
        self.assertIn("sketch_constrain adds one constraint for each call, so it has no constraints", msg)
        self.assertIn('{ "tool": "sketch_constrain", "type": "tangent", "refs": [0, 1] }', msg)
        self.assertIn("Several constraints are several calls: in a batch, or with each.", msg)

    def test_the_hub_refuses_the_list_and_the_stand_in_adds_one(self):
        g = hub()
        self.assertTrue(g["consRun"]["isError"])
        self.assertIn("has no constraints", said(g["consRun"]))
        con = stand()["con"]
        self.assertEqual(len(con["added"]), 1, con)


# ---- the edge inputs ----------------------------------------------------------------------

class Edges(unittest.TestCase):
    """One selector (a reference, or an object of filters) or a list of references. A list of selector objects is refused."""

    def test_the_schema_takes_a_string_an_object_or_a_list_of_strings(self):
        for n in ("pd_fillet", "pd_chamfer"):
            e = schema(n)["properties"]["edges"]
            self.assertEqual([x["type"] for x in e["anyOf"]], ["string", "object", "array"], n)
            self.assertEqual(e["anyOf"][2]["items"], {"type": "string"}, n)

    def test_the_form(self):
        got = stand()
        self.assertEqual(got["edges"]["string"], ["Edge3"])
        self.assertEqual(got["edges"]["selector"], [{"type": "line", "axis": "z", "outside": True}])  # one selector rounds several edges
        self.assertEqual(got["edges"]["list"], ["Edge1", "Edge2"])
        self.assertEqual(sorted(got["edgesBad"]), ["mixed", "nested", "number", "objects"])
        for k, msg in got["edgesBad"].items():
            self.assertEqual(msg, got["edges"]["form"], k)
        self.assertIn("one selector", got["edges"]["form"])
        self.assertIn("list of references", got["edges"]["form"])

    def test_the_other_tools_that_take_edges_use_the_same_form(self):
        for n in ("sketch_project", "sketch_external"):
            e = schema(n)["properties"]["edges"]
            self.assertIn("anyOf", e, n)
        for n in ("pd_fillet", "pd_chamfer", "sketch_project", "sketch_external"):
            steps = json.dumps(runners.entries()[n]["steps"])
            self.assertIn("edges_form(a.edges)", steps, n)


# ---- the cards ----------------------------------------------------------------------------

class Cards(unittest.TestCase):
    def test_plain_and_ready_are_both_flat_steps(self):
        for n in ("sketch_add", "sketch_constrain", "pd_pad", "pd_fillet", "pd_chamfer"):
            got = examples.for_tool(n, {"bodyName": "Body", "editSketch": "Sk"})
            self.assertEqual(sorted(got), ["fill", "plain", "ready"], n)
            for k in ("plain", "ready"):
                self.assertEqual(got[k]["tool"], n, (n, k))
                self.assertNotIn("arguments", got[k], (n, k))
                self.assertFalse([v for v in got[k].values() if isinstance(v, dict) and "tool" in v], (n, k))
            self.assertEqual(list(got["plain"]), list(got["ready"]), n)

    def test_ready_fills_from_the_document_and_marks_what_it_could_not_fill(self):
        got = examples.for_tool("pd_fillet", {"bodyName": "Body"})
        self.assertEqual(got["plain"], {"tool": "pd_fillet", "body": None, "edges": None, "radius": None})
        self.assertEqual(got["ready"], {"tool": "pd_fillet", "body": "Body", "edges": None, "radius": None})
        full = examples.for_tool("pd_fillet", {"bodyName": "Body", "pickedEdges": ["Edge3"]})
        self.assertEqual(full["ready"]["edges"], ["Edge3"])
        self.assertIsNone(full["ready"]["radius"])
        self.assertIsNone(full["plain"]["edges"])

    def test_the_sketch_cards_use_the_flat_inputs(self):
        add = examples.for_tool("sketch_add", {"editSketch": "PlateSketch"})
        self.assertEqual(add["plain"]["sketch"], None)
        self.assertEqual(add["ready"]["sketch"], "PlateSketch")
        self.assertEqual(add["ready"]["kind"], "rectangle")
        self.assertNotIn("items", add["ready"])
        self.assertEqual(refused("sketch_add", {k: v for k, v in add["ready"].items() if k != "tool"}), None)
        con = examples.for_tool("sketch_constrain", {"editSketch": "PlateSketch"})
        self.assertNotIn("constraints", con["ready"])
        self.assertEqual(refused("sketch_constrain", {k: v for k, v in con["ready"].items() if k != "tool"}), None)

    def test_the_fill_words_are_the_fact_about_the_input(self):
        for n in ("sketch_add", "sketch_constrain", "pd_fillet", "pd_chamfer"):
            for w in examples.for_tool(n, {}).get("fill", []):
                self.assertLess(len(w), 260, w)

    def test_the_card_of_tool_find_has_the_two_fields_and_no_old_shape(self):
        g = hub()
        card = g["findRun"]["body"]["tools"][0]
        self.assertEqual(card["tool"], "sketch_add")
        ex = card["example"] if "example" in card else card
        self.assertIn("plain", json.dumps(ex))
        self.assertIn("ready", json.dumps(ex))
        self.assertNotIn('"arguments"', json.dumps(card))
        note = g["findRun"]["body"].get("note", "")
        self.assertIn("plain", note)
        self.assertIn("ready", note)


# ---- pick and the options ------------------------------------------------------------------

class Options(unittest.TestCase):
    def test_a_row_is_a_flat_step(self):
        opts = {"step": 3, "list": [{"n": 1, "tool": "pd_pad", "arguments": {"sketch": "Sk", "body": "Body"}, "ask": [{"arg": "length", "unit": "mm"}]}]}
        row = options.public(opts)["list"][0]
        self.assertEqual(row["step"], {"tool": "pd_pad", "sketch": "Sk", "body": "Body"})
        self.assertNotIn("arguments", row)
        self.assertNotIn("tool", row)
        self.assertNotIn("run", row)  # 27 Nov: the key run is the name of a tool, so a row says step

    def test_the_pick_how_to_is_a_run_step(self):
        opts = {"step": 3, "list": [{"n": 1, "tool": "pd_pad", "arguments": {}, "ask": [{"arg": "length", "unit": "mm", "sample": 4}]}]}
        self.assertEqual(options.pick_how(opts, static=True),
                         'run { "calls": [ { "tool": "pick", "option": 1, "fill": { "length": 4 } } ] } runs option 1; option: "1, 4mm" also works')
        self.assertTrue(options.pick_how(None, static=True).startswith('run { "calls": [ { "tool": "pick", "option": 1'))

    def test_pick_runs_through_run(self):
        import test_options as t

        sk = t.sketch("Sketch")
        used = t.sketch("Base")
        pad = t.feature("Pad", "Pad", used)
        s, server = t.make(t.doc_of(t.body_with("Body", used, pad, sk), used, pad, sk))
        t.facts_reader(self, s)
        os.environ.pop("AGENTLINK_OPTIONS", None)
        t.call(server, "session_state", {})
        r = callshape.run_call(server, {"name": "run", "arguments": {"calls": [{"tool": "pick", "option": 1, "fill": {"length": 4}}]}})
        self.assertFalse(r.get("isError"), r)
        self.assertEqual(s.calls, [("pd_pad", {"sketch": "Sketch", "body": "Body", "length": 4})])


# ---- the renamed inputs --------------------------------------------------------------------

class Renames(unittest.TestCase):
    def test_the_three_work_in_run_batch_and_fast(self):
        g = hub()
        for k in ("findRun", "findBatch", "findFast", "groupsRun", "groupsBatch", "groupsFast"):
            self.assertFalse(g[k]["isError"], (k, g[k]))
        self.assertEqual(g["findBatch"]["body"]["results"][0]["result"]["tools"][0]["tool"], "pd_pad")
        self.assertEqual(g["groupsRun"]["body"]["tools"][0]["tool"], "pd_pad")
        self.assertTrue(g["findFast"]["body"]["fast"].startswith("ran 1 call"))
        self.assertTrue(g["groupsFast"]["body"]["fast"].startswith("ran 1 call"))

    def test_job_start_takes_job_in_run_and_its_own_words_in_batch_and_fast(self):
        g = hub()
        self.assertFalse(g["jobRun"]["isError"], g["jobRun"])
        self.assertIn("job", g["jobRun"]["body"])
        self.assertIn('job_start { job: "measure_mass", arguments } on its own', g["jobBatch"]["body"]["results"][0]["error"]["message"])
        self.assertTrue(g["jobFast"]["isError"])
        self.assertIn("job_start does not run in a fast block", said(g["jobFast"]))

    def test_the_old_names_are_refused_with_the_new_form(self):
        g = hub()
        for k, new in (("oldFind", 'tool_find { card: "pd_pad" }'), ("oldGroups", 'tool_groups { card: "pd_pad" }'), ("oldJob", 'job_start { job: "body_check" }')):
            self.assertTrue(g[k]["isError"], k)
            self.assertIn("The input is now called", said(g[k]), k)
            self.assertIn(new, said(g[k]), k)

    def test_the_schemas_have_the_new_names_and_not_the_old(self):
        props = hub()["props"]
        for n, new in (("tool_find", "card"), ("tool_groups", "card"), ("job_start", "job")):
            self.assertIn(new, props[n], n)
            self.assertNotIn("tool", props[n], n)

    def test_only_two_inputs_keep_a_step_key(self):
        g = hub()  # the real list is read in test_flat_call_1126.py (collide); here the new names only
        self.assertNotIn("tool_find.tool", json.dumps(g))


# ---- the texts ----------------------------------------------------------------------------

CALL_FORM = re.compile(r"""\{\s*"?tool"?\s*:\s*"?[\w-]+"?\s*,\s*"?arguments"?\s*:""")
OLD_NAME = re.compile(r"\{ *tool, *arguments *\}")


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def _skip(line):
    low = line.lower()
    # the old form named so that it is refused; the approve tools' own pending answer (approve: { tool, arguments })
    return "refus" in low or "old form" in low or "approve" in low


class NoOldCallShape(unittest.TestCase):
    def test_no_guide_or_workflow_doc_gives_a_call_with_arguments(self):
        bad = []
        for sub in ("agentlink/guides", "docs/workflow"):
            d = os.path.join(ROOT, sub)
            for f in sorted(os.listdir(d)):
                if not f.endswith(".md"):
                    continue
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    for i, line in enumerate(fh, 1):
                        if (CALL_FORM.search(line) or OLD_NAME.search(line)) and not _skip(line):
                            bad.append(f"{sub}/{f}:{i}")
        self.assertEqual(bad, [])

    def test_no_data_text_gives_a_call_with_arguments(self):
        bad = []
        d = os.path.join(ROOT, "agentlink", "data")
        for f in sorted(os.listdir(d)):
            if not f.endswith(".json") or f.endswith("schema.json"):
                continue
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                doc = json.load(fh)
            for s in _strings(doc):
                if (CALL_FORM.search(s) or OLD_NAME.search(s)) and not _skip(s):
                    bad.append(f"{f}: {s[:80]}")
        self.assertEqual(bad, [])

    def test_no_generated_example_or_option_has_an_arguments_key(self):
        for n in sorted(examples.load()):
            got = examples.for_tool(n, {"bodyName": "Body", "editSketch": "Sk", "sketchName": "Sk"})
            if got is None:
                continue
            for k in ("plain", "ready"):
                self.assertNotIn("arguments", got[k], (n, k))
                self.assertEqual(got[k]["tool"], n, (n, k))
            self.assertFalse(any(CALL_FORM.search(w) for w in got.get("fill", [])), n)
        opts = {"step": 1, "list": [{"n": 1, "tool": "doc_new", "arguments": {}, "ask": [{"arg": "name"}]}]}
        pub = options.public(opts)
        self.assertNotIn("arguments", json.dumps(pub["list"]))
        self.assertNotIn("arguments", pub["pick"])
        self.assertNotIn("arguments", options.pick_how(opts, static=True))

    def test_the_hub_texts_choose_between_run_batch_and_fast(self):
        texts = hub()["texts"]
        for k, text in texts.items():
            self.assertNotIn("only way", text, k)
            self.assertNotIn("batch only", text, k)
        self.assertIn("one call", texts["STATIC_NOTE"])
        for word in ("run", "batch", "fast"):
            self.assertIn(word, texts["STATIC_NOTE"])
        self.assertIn('"tool"', texts["BASIC_FORM"])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        _child()
    else:
        unittest.main()

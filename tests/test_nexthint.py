# SPDX-License-Identifier: LGPL-2.1-or-later
# The "next" hint ranks the likely next tools from the document's own state
# (agentlink/nexthint.py, data/nexthint.json) instead of listing the active
# ones by name: each state the rules cover names the step a person would
# take, the selection weighs most after a failing recompute, add-ons add
# rules as data, and what FreeCAD says cannot run now is passed over.
# Without FreeCAD; the facts' reading is tested against stand-in objects.
import os
import sys
import types
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from agentlink import datafiles, nexthint, toolindex  # noqa: E402

DATA = os.path.join(ROOT, "agentlink", "data")


def top(facts, n=3):
    return [p["tool"] for p in nexthint.rank(facts)[:n]]


class Table(unittest.TestCase):
    def test_the_file_fits_its_schema(self):
        self.assertEqual(datafiles.check(os.path.join(DATA, "nexthint.json")), [])
        self.assertGreaterEqual(len(nexthint.load()), 20)

    def test_every_tool_named_is_one_of_agent_links_own(self):
        index = toolindex.load()
        for rid, rule in nexthint.load().items():
            for s in rule["suggest"]:
                self.assertIn(s["tool"], index, f"{rid}: {s['tool']} is not a tool of this repository")
                self.assertLessEqual(len(s["why"]), nexthint.MAX_WHY, rid)

    def test_every_fact_and_value_is_one_the_reader_gives(self):
        known = {"document": {"empty", "objects"}, "failing": {True, False}, "selection": {"edge", "face", "vertex", "object"},
                 "selectionIn": {"body", "other"}, "editing": {"sketch", "other"}, "dof": {"free", "full"}, "page": {True},
                 "assembly": {"empty", "unjointed", "jointed"}, "body": {"none", "empty", "sketch-empty", "sketch-open", "sketch-closed", "features"},
                 "features": {"none", "some"}, "lastFeature": None, "workbench": None}
        for rid, rule in nexthint.load().items():
            for cond in (rule["when"], rule.get("unless") or {}):
                for k, v in cond.items():
                    self.assertIn(k, known, f"{rid}: no such fact {k}")
                    if known[k] is not None:
                        for x in (v if isinstance(v, list) else [v]):
                            self.assertIn(x, known[k], f"{rid}: {k} is never {x!r}")


class Ranking(unittest.TestCase):
    def test_the_states_the_owner_named(self):
        # a body with no sketch
        self.assertEqual(top({"document": "objects", "body": "empty", "features": "none"})[0], "sketch_new")
        # a sketch open in edit with DoF left
        self.assertEqual(top({"editing": "sketch", "dof": "free", "body": "sketch-open"})[:2], ["sketch_constrain", "sketch_state"])
        # a closed sketch not yet used by a feature
        self.assertEqual(top({"body": "sketch-closed", "features": "none"})[:2], ["pd_pad", "pd_revolution"])
        self.assertEqual(top({"body": "sketch-closed", "features": "some"}), ["pd_pad", "pd_pocket", "pd_revolution"])
        # a body whose last feature is a pad or a pocket: the next feature, holes, patterns; fillets last (21 Nov: modelling principles)
        self.assertEqual(top({"body": "features", "features": "some", "lastFeature": "pad"}), ["sketch_new", "pd_hole", "pd_polar_pattern"])
        self.assertEqual(top({"body": "features", "features": "some", "lastFeature": "pocket"})[0], "sketch_new")
        # a primitive as the last feature: a sketch first
        self.assertEqual(top({"body": "features", "features": "some", "lastFeature": "additivebox"})[:2], ["sketch_new", "pd_pad"])
        self.assertEqual(top({"body": "features", "features": "some", "lastFeature": "fillet"})[0], "body_check")
        self.assertIn("body_check", [p["tool"] for p in nexthint.rank({"body": "features", "features": "some", "lastFeature": "pad"})])
        # a drawing page open
        self.assertEqual(top({"page": True, "body": "features", "lastFeature": "pad"})[0], "td_view")
        # an assembly
        self.assertEqual(top({"assembly": "unjointed", "workbench": "AssemblyWorkbench", "body": "features", "lastFeature": "pad"})[0], "asm_joint")
        self.assertEqual(top({"assembly": "jointed", "workbench": "AssemblyWorkbench"})[:2], ["asm_check", "asm_joint"])
        # nothing at all
        self.assertEqual(top({"document": "empty", "body": "none"})[0], "pd_body_new")

    def test_a_failing_recompute_comes_first(self):
        got = top({"failing": True, "selection": "edge", "selectionIn": "body", "body": "features", "lastFeature": "pad"})
        self.assertEqual(got[0], "recompute")
        self.assertEqual(nexthint.rank({"failing": True})[0]["rule"], "recompute-failing")

    def test_the_selection_weighs_most(self):
        base = {"body": "features", "features": "some", "lastFeature": "fillet", "document": "objects"}
        self.assertEqual(top({**base, "selection": "edge", "selectionIn": "body"})[:2], ["pd_fillet", "pd_chamfer"])
        self.assertEqual(top({**base, "selection": "face", "selectionIn": "body"}), ["sketch_new", "pd_draft", "pd_thickness"])
        # a picked edge of a shape that is no body: Part's own tools
        self.assertEqual(top({"body": "none", "selection": "edge", "selectionIn": "other"})[:2], ["part_fillet", "part_chamfer"])
        # in an open sketch the picked edge is sketch geometry: the sketch's tools
        self.assertEqual(top({**base, "selection": "edge", "selectionIn": "body", "editing": "sketch", "dof": "free"})[0], "sketch_constrain")

    def test_each_tool_once_with_its_reason(self):
        got = nexthint.rank({"body": "features", "features": "some", "lastFeature": "pad", "selection": "edge", "selectionIn": "body"})
        names = [p["tool"] for p in got]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(p["why"] for p in got))
        self.assertEqual(got[0]["why"], "round the picked edge")

    def test_nothing_fits_nothing_said(self):
        self.assertEqual(nexthint.rank({}), [])
        self.assertEqual(nexthint.rank({"workbench": "StartWorkbench"}), [])

    def test_matching(self):
        rule = {"when": {"a": 1, "b": ["x", "y"]}, "unless": {"c": True, "d": ["p"]}}
        self.assertTrue(nexthint.matches(rule, {"a": 1, "b": "y"}))
        self.assertFalse(nexthint.matches(rule, {"a": 1}))
        self.assertFalse(nexthint.matches(rule, {"a": 1, "b": "x", "c": True}))
        self.assertFalse(nexthint.matches(rule, {"a": 1, "b": "x", "d": "p"}))
        self.assertFalse(nexthint.matches({"when": {}}, {"a": 1}))


class AddOns(unittest.TestCase):
    def tearDown(self):
        nexthint.EXTRA.clear()

    def test_an_add_on_adds_rules_as_data(self):
        rule = {"when": {"body": "features"}, "suggest": [{"tool": "addon_review", "why": "the add-on's own review"}], "weight": 49, "source": "t", "date": "2026-11-16"}
        self.assertEqual(nexthint.declare({"review-after-features": rule}, "addon"), [])
        got = [p["tool"] for p in nexthint.rank({"body": "features", "features": "some", "lastFeature": "pad"})]
        self.assertEqual(got[:5], ["sketch_new", "pd_hole", "pd_polar_pattern", "pd_fillet", "addon_review"])
        # Not installed: passed over, and costs nothing.
        picks = nexthint.available(nexthint.rank({"body": "features", "lastFeature": "fillet"}), {}, exists=lambda n: n != "addon_review")
        self.assertNotIn("addon_review", [p["tool"] for p in picks])

    def test_a_rule_that_does_not_fit_the_schema_is_left_out_and_said(self):
        bad = nexthint.declare({"x": {"when": {"body": "features"}, "suggest": [{"tool": "Bad Name", "why": "w"}], "weight": 500, "source": "t", "date": "2026-11-16"}}, "addon")
        self.assertTrue(bad and "addon" in bad[0])
        self.assertEqual(nexthint.EXTRA, {})
        self.assertTrue(nexthint.declare("nope", "addon"))

    def test_a_file_rule_is_never_replaced(self):
        rule = {"when": {"failing": True}, "suggest": [{"tool": "addon_fix", "why": "the add-on's fixer"}], "weight": 10, "source": "t", "date": "2026-11-16"}
        nexthint.declare({"recompute-failing": rule}, "addon")
        self.assertIn("addon:recompute-failing", nexthint.EXTRA)
        self.assertEqual(top({"failing": True})[0], "recompute")


class Line(unittest.TestCase):
    def test_three_tools_each_with_why_under_the_limit(self):
        picks = nexthint.available(nexthint.rank({"body": "sketch-closed", "features": "some"}), {})
        self.assertEqual(len(picks), 3)
        line = nexthint.compose({"window": True, "workbench": "PartDesignWorkbench", "status": "s" * 300}, picks)
        self.assertTrue(line.startswith("likely next: pd_pad (a closed sketch no feature uses yet), pd_pocket (cut it out of the body), pd_revolution ("))
        self.assertLessEqual(len(line), nexthint.MAX)
        self.assertNotIn("active now", line)


# ---- the facts, read from stand-in objects ------------------------------------------------

class Obj:
    def __init__(self, type_id, name, bases=(), state=(), **more):
        self.TypeId, self.Name, self.Label = type_id, name, name
        self._bases = set(bases) | {type_id}
        self.State = list(state)
        self.InList, self.Group = [], []
        for k, v in more.items():
            setattr(self, k, v)

    def isDerivedFrom(self, t):
        return t in self._bases


def body_with(*members, tip=None):
    b = Obj("PartDesign::Body", "Body")
    b.Group = list(members)
    for m in members:
        m.InList.append(b)
    b.Tip = tip
    return b


def sketch(name="Sketch", closed=True, geometry=4):
    wires = [types.SimpleNamespace(isClosed=lambda: closed)] if geometry else []
    return Obj("Sketcher::SketchObject", name, GeometryCount=geometry, Shape=types.SimpleNamespace(Wires=wires))


def feature(kind, name=None, profile=None):
    f = Obj(f"PartDesign::{kind}", name or kind, bases=("PartDesign::Feature",))
    if profile is not None:
        profile.InList.append(f)
    return f


def doc_of(*objs):
    return types.SimpleNamespace(Objects=list(objs))


class Facts(unittest.TestCase):
    def facts(self, doc, state=None):
        return nexthint.facts(doc, state or {})

    def test_body_progress(self):
        b = body_with()
        self.assertEqual(self.facts(doc_of(b))["body"], "empty")
        sk = sketch(closed=False)
        self.assertEqual(self.facts(doc_of(body_with(sk), sk))["body"], "sketch-open")
        sk = sketch(geometry=0)
        self.assertEqual(self.facts(doc_of(body_with(sk), sk))["body"], "sketch-empty")
        sk = sketch()
        f = self.facts(doc_of(body_with(sk), sk))
        self.assertEqual((f["body"], f["features"]), ("sketch-closed", "none"))
        sk = sketch()
        pad = feature("Pad", profile=sk)
        f = self.facts(doc_of(body_with(sk, pad, tip=pad), sk, pad))
        self.assertEqual((f["body"], f["features"], f["lastFeature"], f["failing"]), ("features", "some", "pad", False))

    def test_failing_and_empty(self):
        self.assertEqual(self.facts(doc_of()), {"document": "empty", "failing": False, "body": "none"})
        bad = Obj("Part::Feature", "X", state=["Touched", "Invalid"])
        self.assertTrue(self.facts(doc_of(bad))["failing"])
        self.assertEqual(self.facts(None), {})

    def test_assembly(self):
        part = Obj("App::Part", "P")
        joints = Obj("Assembly::JointGroup", "Joints")
        asm = Obj("Assembly::AssemblyObject", "Assembly")
        asm.Group = [joints]
        self.assertEqual(self.facts(doc_of(asm, joints))["assembly"], "empty")
        asm.Group = [joints, part]
        self.assertEqual(self.facts(doc_of(asm, joints, part))["assembly"], "unjointed")
        joints.Group = [Obj("App::FeaturePython", "Joint")]
        self.assertEqual(self.facts(doc_of(asm, joints, part))["assembly"], "jointed")

    def test_selection_and_sketch_from_the_window_state(self):
        f = self.facts(doc_of(), {"workbench": "SketcherWorkbench", "editing": "sketch", "sketch": {"name": "S", "dof": 3}, "selSubs": {"edge", "face"}, "selected": 1})
        self.assertEqual((f["editing"], f["dof"], f["selection"], f["workbench"]), ("sketch", "free", "edge", "SketcherWorkbench"))
        self.assertEqual(self.facts(doc_of(), {"selected": 2})["selection"], "object")

    def test_a_big_document_is_not_walked(self):
        many = [Obj("Part::Feature", f"o{i}") for i in range(nexthint.MAX_OBJECTS + 1)]
        self.assertEqual(self.facts(doc_of(*many)), {"document": "objects"})


class NeverAsksOutsideTheToolbars(unittest.TestCase):
    """The crash seen live: isActive() on a command outside the active
    workbench's toolbars. The source asks in one place only, behind the
    shown-commands filter."""

    def test_one_guarded_place(self):
        with open(os.path.join(ROOT, "agentlink", "tools.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertEqual(src.count(".isActive()"), 1)
        i = src.index("def ask_active(")
        body = src[i:src.index("\ndef ", i + 10)]
        self.assertIn(".isActive()", body)
        self.assertLess(body.index("if name not in shown"), body.index(".isActive()"))
        with open(os.path.join(ROOT, "agentlink", "nexthint.py"), encoding="utf-8") as f:
            self.assertNotIn("isActive()", f.read().split('"""', 2)[2])


if __name__ == "__main__":
    unittest.main()

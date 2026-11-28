# SPDX-License-Identifier: LGPL-2.1-or-later
# 28 Nov: the health of an answer as typed records (no "facts" text):
# recompute, sketches, shapes, measured, window, addons, fault. Plain Python
# with stand-ins (no FreeCAD), in the style of test_health.py.
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import health, once, selectwhat  # noqa: E402
from agentlink.protocol import Tool  # noqa: E402


class Doc:
    def __init__(self, name="D"):
        self.Name = name
        self.Objects = []


class Obj:
    TypeId = "Part::Feature"

    def __init__(self, doc, name, error=None, state=()):
        self.Document, self.Name, self.Label = doc, name, name
        self._error, self.State = error, list(state)
        self.InList, self.InListRecursive, self.OutList = [], [], []
        doc.Objects.append(self)

    def isValid(self):
        return self._error is None

    def getStatusString(self):
        return self._error or "Valid"


class Line:
    pass


Line.__name__ = "LineSegment"


class Sketch(Obj):
    TypeId = "Sketcher::SketchObject"

    def __init__(self, doc, name, dof=0, free=(), n=4):
        super().__init__(doc, name)
        self.DoF, self._free = dof, list(free)
        self.ConflictingConstraints = self.RedundantConstraints = []
        self.PartiallyRedundantConstraints, self.MalformedConstraints = [], []
        self.GeometryCount, self.Geometry = n, [Line() for _ in range(n)]

    def getGeometryWithDependentParameters(self):
        return self._free


class Plane:
    pass


class Face:
    Surface = Plane()


class Shape:
    ShapeType = "Solid"

    def __init__(self, valid=True, solids=1, volume=100.0):
        self.Faces = [Face()] * 6
        self.Solids = [self] * solids
        self.Shells = [self]
        self.Volume, self._valid = volume, valid

    def isNull(self):
        return False

    def countElement(self, kind):
        return 6 if kind == "Face" else 0

    def isValid(self):
        return self._valid

    def isClosed(self):
        return True


class Body(Obj):
    TypeId = "PartDesign::Body"

    def __init__(self, doc, name, shape):
        super().__init__(doc, name)
        self.Shape = shape


class Session:
    def __init__(self, doc):
        self.doc = doc


class Feature:
    name, group, changes = "pd_pad", "pd", True


class SketchTool:
    name, group, changes = "sketch_add", "sketch", True


class Reading:
    name, group, changes = "body_check", "pd", False


class Stubbed(unittest.TestCase):
    """health.check on stand-ins: geometry and the Session's bodies stood in."""

    def setUp(self):
        import agentlink

        health._slow.clear()
        self._key = health._key
        health._key = lambda o: ("Solid", len(o.Shape.Faces), 0, 0, 0, 0, 0, 1, 1, 1, o.Shape.Volume)
        self._mods = {k: sys.modules.get(k) for k in ("agentlink.geometry", "agentlink.tools")}
        self._attrs = {k: agentlink.__dict__.get(k) for k in ("geometry", "tools")}
        geo = types.ModuleType("agentlink.geometry")
        geo.core_check = lambda sh: (True, [])
        geo.soft_bop = lambda lines: False
        geo.shape_key = lambda sh: ("hash", id(sh), sh.Volume)
        geo.CHECK_LINES = 10
        tools = types.ModuleType("agentlink.tools")
        tools.Session = types.SimpleNamespace(bodies_in=staticmethod(lambda doc: [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]))
        sys.modules["agentlink.geometry"] = agentlink.geometry = geo
        sys.modules["agentlink.tools"] = agentlink.tools = tools
        self.geo = geo

    def tearDown(self):
        import agentlink

        health._key = self._key
        health._slow.clear()
        for k, mod in self._mods.items():
            if mod is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = mod
        for k, attr in self._attrs.items():
            if attr is None:
                agentlink.__dict__.pop(k, None)
            else:
                setattr(agentlink, k, attr)

    def run_call(self, doc, change, tool=Feature, args=None):
        s = Session(doc)
        m = health.mark(s)
        for o in change() or []:
            health._observer_note(o)
        return health.check(s, tool, m, args)

    def test_a_clean_pad_is_typed_records(self):
        d = Doc()
        h = self.run_call(d, lambda: [Body(d, "Body", Shape())])
        self.assertEqual(h, {"recompute": "ok", "fault": False, "shapes": [{"object": "Body", "valid": True, "closed": True, "solids": 1}]})
        self.assertNotIn("facts", h)
        self.assertFalse(health.last_fault())
        self.assertFalse(health.fault_in(h))

    def test_a_shape_with_no_volume_or_several_solids_has_the_numbers(self):
        d = Doc()
        h = self.run_call(d, lambda: [Body(d, "Body", Shape(solids=2, volume=-5.0))])
        rec = h["shapes"][0]
        self.assertEqual((rec["solids"], rec["volume"]), (2, -5.0))
        self.assertIs(h["fault"], True)  # a volume that is not above 0 is red
        d = Doc()
        h = self.run_call(d, lambda: [Body(d, "Body", Shape())])
        self.assertNotIn("volume", h["shapes"][0])  # given only when not above 0

    def test_a_shape_that_is_not_valid_is_a_fault(self):
        d = Doc()
        h = self.run_call(d, lambda: [Body(d, "Body", Shape(valid=False))])
        self.assertEqual(h["shapes"][0]["valid"], False)
        self.assertIs(h["fault"], True)
        self.assertTrue(health.fault_in(h))

    def test_check_geometrys_own_lines_are_a_field(self):
        self.geo.core_check = lambda sh: (False, ["BOPAlgo_SelfIntersect Face3", "found the following errors:", "second line"])
        d = Doc()
        h = self.run_call(d, lambda: [Body(d, "Body", Shape())])
        self.assertEqual(h["shapes"][0]["checkErrors"], ["BOPAlgo_SelfIntersect Face3", "second line"])
        self.assertTrue(health.fault_in(h))

    def test_a_sketch_with_dof_left_is_a_record(self):
        d = Doc()
        h = self.run_call(d, lambda: [Sketch(d, "Sketch", dof=4, free=[(0, 1), (1, 1), (2, 1), (3, 1)])], SketchTool)
        self.assertEqual(h["sketches"], [{"sketch": "Sketch", "dof": 4, "free": ["the start of lines 0, 1, 2, 3"]}])
        self.assertEqual((h["recompute"], h["fault"]), ("ok", False))
        self.assertNotIn("needRecompute", h)

    def test_a_failing_recompute_is_a_fault_with_the_object_and_freecads_error(self):
        d = Doc()
        Obj(d, "Old", error="Old broke")
        h = self.run_call(d, lambda: [Obj(d, "Pad", error="Pad: Result has multiple solids")])
        self.assertEqual(h["recompute"], {"failing": [{"object": "Pad", "error": "Pad: Result has multiple solids"}], "failingBefore": ["Old"]})
        self.assertIs(h["fault"], True)
        self.assertTrue(health.last_fault())
        self.assertNotIn("errors", h)

    def test_an_object_left_waiting_is_in_recompute(self):
        d = Doc()
        pad = Obj(d, "Pad", state=["Touched"])
        pad.TypeId = "PartDesign::Pad"
        h = self.run_call(d, lambda: [Obj(d, "Other")])
        self.assertEqual(h["recompute"], {"notRecomputed": ["Pad"]})

    def test_shared_volume_is_measured_numbers(self):
        was = health.overlaps
        health.overlaps = lambda *a, **k: ([{"a": "A", "b": "B", "volume": 12.5, "box": [1.0, 2.0, 3.0], "line": "words"}], [])
        try:
            d = Doc()
            h = self.run_call(d, lambda: [Body(d, "A", Shape()), Body(d, "B", Shape())])
        finally:
            health.overlaps = was
        self.assertEqual(h["measured"], [{"parts": ["A", "B"], "sharedVolume": 12.5, "box": [1.0, 2.0, 3.0]}])

    def test_an_addons_lines_stay_text_under_its_name(self):
        health.register("fam", lambda s, t, changed: [{"line": "Assembly: solved"}])
        try:
            d = Doc()
            h = self.run_call(d, lambda: [Obj(d, "X")])
        finally:
            health.unregister("fam")
        self.assertEqual(h["addons"], {"fam": ["Assembly: solved"]})

    def test_the_window_is_one_record(self):
        was = health.window
        health.window = lambda: {"dialog": "Missing link", "task": ["Pad: Error x", "fully constrained"], "status": "Warning y"}
        try:
            d = Doc()
            h = self.run_call(d, lambda: [Obj(d, "X")])
        finally:
            health.window = was
        self.assertEqual(h["window"], {"dialog": "Missing link", "taskPanel": ["Pad: Error x"], "statusBar": "Warning y"})
        self.assertIs(h["fault"], True)
        self.assertNotIn("taskPanel", h)
        self.assertNotIn("statusBar", h)

    def test_no_document_and_a_failed_check_are_not_read_records(self):
        self.assertEqual(health.check(Session(None), Feature, health.mark(Session(Doc()))), {"notRead": "no document", "fault": False})
        s = Session(Doc())
        m = health.mark(s)
        was = health.check
        health.check = lambda *a: 1 / 0
        try:
            out = health.attach(s, Feature, m, {})
        finally:
            health.check = was
            health.drop(m)
        self.assertTrue(out["health"]["notRead"].startswith("the health check did not run (ZeroDivisionError"))
        self.assertIs(out["health"]["fault"], True)
        self.assertTrue(health.fault_in(out["health"]))

    def test_a_call_with_nothing_new_says_so_in_fields(self):
        d = Doc()
        s = Session(d)
        out = health.attach(s, Feature, health.mark(s), {})
        self.assertEqual(out["health"], {"recompute": "ok", "fault": False})


def answer(h):
    return {"feature": "Pad", "health": json.loads(json.dumps(h))}


CLEAN = {"recompute": "ok", "fault": False, "shapes": [{"object": "Body", "valid": True, "closed": True, "solids": 1}]}


class NothingNew(unittest.TestCase):
    def setUp(self):
        self.s = types.SimpleNamespace()
        self.tool = Tool("pd_pad", "d", {"type": "object", "properties": {}}, None, changes=True)

    def test_the_same_health_is_nothing_new_and_a_change_is_whole(self):
        self.assertEqual(once.thin_reply(self.s, self.tool, answer(CLEAN))["health"], CLEAN)
        self.assertEqual(once.thin_reply(self.s, self.tool, answer({**CLEAN, "ms": 300}))["health"], once.NOTHING_NEW)
        two = {**CLEAN, "shapes": [{"object": "Body", "valid": True, "closed": True, "solids": 2}]}
        self.assertEqual(once.thin_reply(self.s, self.tool, answer(two))["health"], two)

    def test_it_is_told_per_subject(self):
        sk = {"recompute": "ok", "fault": False, "sketches": [{"sketch": "Sketch", "dof": 2}]}
        self.assertEqual(once.subject(CLEAN), "Body")
        self.assertEqual(once.subject(sk), "Sketch")
        once.thin_reply(self.s, self.tool, answer(CLEAN))
        once.thin_reply(self.s, self.tool, answer(sk))
        self.assertEqual(once.thin_reply(self.s, self.tool, answer(CLEAN))["health"], once.NOTHING_NEW)
        self.assertEqual(once.thin_reply(self.s, self.tool, answer(sk))["health"], once.NOTHING_NEW)

    def test_the_status_bar_does_not_make_a_reading_new(self):
        once.thin_reply(self.s, self.tool, answer(CLEAN))
        got = once.thin_reply(self.s, self.tool, answer({**CLEAN, "window": {"statusBar": "Pad001"}}))
        self.assertEqual(got["health"], once.NOTHING_NEW)

    def test_a_fault_always_comes_back_in_full(self):
        faults = [
            {"recompute": {"failing": [{"object": "Pad", "error": "x"}]}, "fault": True},
            {"recompute": {"failingBefore": ["Pad"]}, "fault": True},
            {"recompute": {"notRecomputed": ["Pad"]}, "fault": False},
            {"recompute": "ok", "fault": True, "sketches": [{"sketch": "S", "conflicting": [1]}]},
            {"recompute": "ok", "fault": True, "shapes": [{"object": "B", "valid": False, "closed": True, "solids": 1}]},
            {"recompute": "ok", "fault": True, "window": {"dialog": "Missing link"}},
            {"notRead": "no document", "fault": False},
        ]
        for h in faults:
            for _ in range(3):
                got = once.thin_reply(self.s, self.tool, answer(h))["health"]
                self.assertIsInstance(got, dict, h)
                self.assertEqual(got.get("fault"), h["fault"])

    def test_the_standing_failure_is_given_again_only_when_it_changes(self):
        def h(more):
            return {"health": {"recompute": {"failingBefore": ["Left", "Dim"]}, "fault": True, "measured": [{"parts": ["A", "B"], "sharedVolume": more}]}}

        a = once.thin_reply(self.s, "x", h(5))
        self.assertEqual(a["health"]["recompute"]["failingBefore"], ["Left", "Dim"])
        b = once.thin_reply(self.s, "x", h(9))
        self.assertEqual(b["health"]["recompute"], "as before")
        self.assertEqual(b["health"]["saidBefore"], ["failing"])
        self.assertEqual(b["health"]["measured"][0]["sharedVolume"], 9)
        self.assertEqual(once.health_said(self.s), {"failingNow": {"failingBefore": ["Left", "Dim"]}})


class Readers(unittest.TestCase):
    def setUp(self):
        self._last = dict(health._last)
        health._last["fault"] = False

    def tearDown(self):
        health._last.update(self._last)

    def test_selectwhat_keeps_a_health_with_a_fault_and_drops_a_clean_one(self):
        self.assertFalse(selectwhat.health_has_fault(CLEAN))
        self.assertFalse(selectwhat.health_has_fault(health.nothing()))
        self.assertTrue(selectwhat.health_has_fault({"recompute": {"failing": [{"object": "Pad", "error": "x"}]}, "fault": True}))
        self.assertTrue(selectwhat.health_has_fault({"recompute": {"notRecomputed": ["Pad"]}, "fault": False}))
        self.assertTrue(selectwhat.health_has_fault({"recompute": "ok", "window": {"taskPanel": ["Error x"]}}))
        self.assertTrue(selectwhat.health_has_fault({"notRead": "no document", "fault": False}))
        self.assertTrue(selectwhat.health_has_fault({"recompute": "ok", "fault": True}))
        health._last["fault"] = True  # the last check read a fault
        self.assertTrue(selectwhat.health_has_fault(CLEAN))

    def test_selectwhat_answer_narrows_and_keeps_a_fault(self):
        body = {"volume": 10.0, "faces": 6, "health": CLEAN}
        self.assertEqual(selectwhat.answer(body, ["volume"]), {"volume": 10.0})
        bad = {"recompute": {"failing": [{"object": "Pad", "error": "x"}]}, "fault": True}
        self.assertEqual(selectwhat.answer({**body, "health": bad}, ["volume"]), {"volume": 10.0, "health": bad})

    def test_batch_rows_and_fast_read_the_fields(self):
        from agentlink import batchrec, fastpath

        bad = {"recompute": {"failing": [{"object": "Pad", "error": "x"}]}, "fault": True, "ms": 5}
        got = {"results": [{"tool": "a", "ok": True, "result": {"health": CLEAN}},
                           {"tool": "b", "ok": True, "result": {"health": bad}}]}
        out = batchrec.to_reply(got, 0, "p", 1, lines="refused")
        self.assertEqual([r["i"] for r in out["results"]], [1])
        self.assertEqual(out["results"][0]["health"], {"recompute": bad["recompute"], "fault": True})
        self.assertEqual(json.loads(fastpath._health_words({"health": bad})), {"recompute": bad["recompute"], "fault": True})
        self.assertIsNone(fastpath._health_words({"health": CLEAN}))

    def test_a_held_build_and_a_build_that_did_not_run_are_records(self):
        from agentlink import hold

        out = hold.held_answer("sketch_edit", {"sketch": "S", "state": {"solver": "solved", "dof": 2, "wires": 1}, "bodyAfter": {"volume": 1}})
        self.assertEqual(out["health"]["build"], "held")
        self.assertIn("bodyAfter", out["health"]["leftOut"])
        self.assertNotIn("facts", out["health"])
        self.assertTrue(hold.build_failed({"health": {"recompute": {"failing": [{"object": "Pad", "error": "x"}]}}}))
        self.assertFalse(hold.build_failed({"health": {"recompute": {"failingBefore": ["Pad"]}}}))

    def test_the_time_is_a_field(self):
        from agentlink import timelimit

        try:
            timelimit.configure("30")
            timelimit.started(now=1000.0)
            h = timelimit.mark_health({"recompute": "ok"}, now=1000.0 + 60 * 16)
            self.assertEqual(h["time"], "16 of 30 minutes used since the first tool call")
        finally:
            timelimit.configure("")

    def test_pd_common_reads_no_health_text(self):
        # 28 Nov merge: Check Geometry's finding stays in health.shapes[].checkErrors; the result record does not repeat it.
        src = open(os.path.join(ROOT, "agentlink", "families", "pd_common.py"), encoding="utf-8").read()
        self.assertNotIn('h.get("facts")', src)
        self.assertNotIn("def check_in_result", src)


class NoFactsText(unittest.TestCase):
    def test_no_reader_of_the_old_text_is_left(self):
        import glob

        for path in glob.glob(os.path.join(ROOT, "agentlink", "*.py")) + glob.glob(os.path.join(ROOT, "agentlink", "families", "*.py")):
            src = open(path, encoding="utf-8").read()
            for old in ('h.get("facts")', 'h["facts"]', 'health.NOTHING', "health.NOT_READ", "once.FAULT", "_once.FAULT"):
                self.assertNotIn(old, src, f"{os.path.basename(path)}: {old}")


if __name__ == "__main__":
    unittest.main()

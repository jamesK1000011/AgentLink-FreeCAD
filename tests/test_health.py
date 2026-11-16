# SPDX-License-Identifier: LGPL-2.1-or-later
# The shared health check's own logic on stand-in objects (plain Python):
# what it reads, how it words the verdict, its limits. Its readings of a
# real FreeCAD document are in test_health_fc.py.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import health  # noqa: E402


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

    def __init__(self, doc, name, dof=0, free=(), conflicting=(), redundant=(), n=4):
        super().__init__(doc, name)
        self.DoF, self._free = dof, list(free)
        self.ConflictingConstraints, self.RedundantConstraints = list(conflicting), list(redundant)
        self.PartiallyRedundantConstraints, self.MalformedConstraints = [], []
        self.GeometryCount, self.Geometry = n, [Line() for _ in range(n)]

    def getGeometryWithDependentParameters(self):
        return self._free


class Session:
    def __init__(self, doc):
        self.doc = doc


class T:
    name, group, changes = "t", "sketch", True


def run(doc, change):
    s = Session(doc)
    m = health.mark(s)
    for o in change() or []:
        health._observer_note(o)
    return health.check(s, T, m)


def test_nothing_changed_nothing_said():
    d = Doc()
    Obj(d, "Box")
    assert run(d, lambda: None) is None


def test_new_failure_named_with_freecads_reason_and_old_ones_counted():
    d = Doc()
    Obj(d, "Old", error="Old broke")
    h = run(d, lambda: [Obj(d, "Pad", error="Pad: Result has multiple solids")])
    assert h["ok"] is False
    assert "1 object failed to recompute: Pad (Pad: Result has multiple solids)" in h["verdict"]
    assert "1 more were failing before" in h["verdict"]
    assert h["errors"][0]["new"] is True and h["todo"]


def test_only_old_failures_say_so():
    d = Doc()
    Obj(d, "Old", error="broke")
    h = run(d, lambda: [Obj(d, "Fine")])
    assert h["ok"] is False and "still failing from before this call: Old" in h["verdict"]
    assert "errors" not in h


def test_touched_objects_the_call_left_alone_want_a_recompute():
    d = Doc()
    pad = Obj(d, "Pad", state=["Touched"])
    pad.TypeId = "PartDesign::Pad"
    Obj(d, "Records", state=["Touched"])  # a plain holder with no inputs: not out of date
    h = run(d, lambda: [Obj(d, "Other")])
    assert h["ok"] is True and h["needRecompute"] == ["Pad"] and "recompute" in h["todo"]


def test_still_touched_after_its_own_recompute_is_not_asked_again():
    d = Doc()
    assert run(d, lambda: [Obj(d, "Screw", state=["Touched"])]) is None


def test_many_clean_sketches_are_counted_and_yellow_ones_capped():
    d = Doc()

    def change():
        out = [Sketch(d, f"Full{i}") for i in range(5)]
        out += [Sketch(d, f"Free{i}", dof=1, free=[(0, 0)]) for i in range(5)]
        out.append(Sketch(d, "Bad", conflicting=[1]))
        return out

    h = run(d, change)
    v = h["verdict"]
    assert v.startswith("Bad: conflicting constraints #0")
    assert v.count("DoF left") == 3 and "2 more with freedom left" in v
    assert "5 sketches fully constrained" in v and "Full0" not in v


def test_sketch_fully_constrained():
    d = Doc()
    h = run(d, lambda: [Sketch(d, "Sketch")])
    assert h == {"ok": True, "verdict": "Sketch: fully constrained"}


def test_sketch_dof_names_the_free_geometry():
    d = Doc()
    # line 3 whole (its edge, 0), line 1 by its end point only
    h = run(d, lambda: [Sketch(d, "Sketch", dof=2, free=[(3, 0), (3, 1), (1, 2)])])
    assert h["ok"] is True
    assert h == {"ok": True, "verdict": "Sketch: 2 DoF left on the end of line 1, line 3"}


def test_free_points_of_one_kind_are_named_together():
    d = Doc()
    h = run(d, lambda: [Sketch(d, "Sketch", dof=4, free=[(0, 1), (1, 1), (2, 1), (3, 1)])])
    assert h["verdict"] == "Sketch: 4 DoF left on the start of lines 0, 1, 2, 3"


def test_sketch_conflict_is_red_and_counts_from_zero():
    d = Doc()
    h = run(d, lambda: [Sketch(d, "Sketch", dof=0, conflicting=[5, 8])])
    assert h["ok"] is False and "conflicting constraints #4, #7" in h["verdict"]
    assert h["sketches"][0]["conflicting"] == [4, 7] and "sketch_edit" in h["todo"]


def test_a_failed_sketch_is_not_read_twice():
    d = Doc()

    def change():
        sk = Sketch(d, "Sketch", dof=1)
        sk._error = "Sketch: over-constrained"
        return [sk]

    h = run(d, change)
    assert "sketches" not in h and "failed to recompute" in h["verdict"]


def test_marks_nest_as_a_batch_and_its_calls_do():
    d = Doc()
    s = Session(d)
    outer = health.mark(s)
    inner = health.mark(s)
    a = Sketch(d, "A")
    health._observer_note(a)
    assert "A: fully constrained" in health.check(s, T, inner)["verdict"]
    b = Sketch(d, "B", dof=1, free=[(0, 0)])
    health._observer_note(b)
    v = health.check(s, T, outer)["verdict"]
    assert "A: fully constrained" in v and "B: 1 DoF left on line 0" in v
    assert health._seen["depth"] == 0 and health._seen["log"] == []


def test_refused_call_closes_its_mark():
    d = Doc()
    m = health.mark(Session(d))
    health.drop(m)
    assert health._seen["depth"] == 0


def test_family_reading_joins_the_verdict():
    d = Doc()
    health.register("fam", lambda s, t, changed: [{"line": "Assembly: assembly conflicting constraints", "red": True, "todo": "asm_check"}])
    try:
        h = run(d, lambda: [Obj(d, "X")])
    finally:
        health.unregister("fam")
    assert h["ok"] is False and "Assembly: assembly conflicting" in h["verdict"] and h["todo"] == "asm_check"


def test_report_lines_counted_in_the_verdict():
    body = {"health": {"ok": True, "verdict": "Sketch: fully constrained"}}
    health.note_report(body, ["Warning: x", "Error: y"])
    assert body["health"]["verdict"].endswith("2 new Report view lines (see report)")


def test_attach_never_raises_and_leaves_other_answers_alone():
    d = Doc()
    s = Session(d)
    assert health.attach(s, T, health.mark(s), "text") == "text"
    assert health.attach(s, T, None, {"a": 1}) == {"a": 1}
    assert health._seen["depth"] == 0


def test_switched_off_by_the_environment():
    os.environ["AGENTLINK_HEALTH"] = "0"
    try:
        assert health.mark(Session(Doc())) is None
    finally:
        del os.environ["AGENTLINK_HEALTH"]

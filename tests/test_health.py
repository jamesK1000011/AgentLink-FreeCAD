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
    assert "ok" not in h and "verdict" not in h and "todo" not in h  # facts only (27 Nov)
    assert h["recompute"]["failing"] == [{"object": "Pad", "error": "Pad: Result has multiple solids"}]
    assert h["recompute"]["failingBefore"] == ["Old"]
    assert "facts" not in h and "errors" not in h and h["fault"] is True


def test_only_old_failures_say_so():
    d = Doc()
    Obj(d, "Old", error="broke")
    h = run(d, lambda: [Obj(d, "Fine")])
    assert h["recompute"] == {"failingBefore": ["Old"]} and h["fault"] is True


def test_touched_objects_the_call_left_alone_want_a_recompute():
    d = Doc()
    pad = Obj(d, "Pad", state=["Touched"])
    pad.TypeId = "PartDesign::Pad"
    Obj(d, "Records", state=["Touched"])  # a plain holder with no inputs: not out of date
    h = run(d, lambda: [Obj(d, "Other")])
    assert h["recompute"] == {"notRecomputed": ["Pad"]} and "needRecompute" not in h


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
    by = {x["sketch"]: x for x in h["sketches"]}
    assert len(by) == 11  # every reading is a record: no cap, no tally
    assert by["Bad"]["conflicting"] == [0] and h["fault"] is True
    assert by["Free0"] == {"sketch": "Free0", "dof": 1, "free": ["line 0"]}
    assert by["Full0"] == {"sketch": "Full0", "dof": 0, "state": "fully constrained"}


def test_sketch_fully_constrained():
    d = Doc()
    h = run(d, lambda: [Sketch(d, "Sketch")])
    assert h == {"recompute": "ok", "fault": False, "sketches": [{"sketch": "Sketch", "dof": 0, "state": "fully constrained"}]}


def test_sketch_dof_names_the_free_geometry():
    d = Doc()
    # line 3 whole (its edge, 0), line 1 by its end point only
    h = run(d, lambda: [Sketch(d, "Sketch", dof=2, free=[(3, 0), (3, 1), (1, 2)])])
    assert h["sketches"] == [{"sketch": "Sketch", "dof": 2, "free": ["the end of line 1", "line 3"]}] and h["fault"] is False


def test_free_points_of_one_kind_are_named_together():
    d = Doc()
    h = run(d, lambda: [Sketch(d, "Sketch", dof=4, free=[(0, 1), (1, 1), (2, 1), (3, 1)])])
    assert h["sketches"][0]["free"] == ["the start of lines 0, 1, 2, 3"]


def test_sketch_conflict_is_red_and_counts_from_zero():
    d = Doc()
    h = run(d, lambda: [Sketch(d, "Sketch", dof=0, conflicting=[5, 8])])
    assert h["sketches"][0]["conflicting"] == [4, 7] and "todo" not in h and h["fault"] is True


def test_a_failed_sketch_is_not_read_twice():
    d = Doc()

    def change():
        sk = Sketch(d, "Sketch", dof=1)
        sk._error = "Sketch: over-constrained"
        return [sk]

    h = run(d, change)
    assert "sketches" not in h and h["recompute"]["failing"][0]["object"] == "Sketch"


def test_marks_nest_as_a_batch_and_its_calls_do():
    d = Doc()
    s = Session(d)
    outer = health.mark(s)
    inner = health.mark(s)
    a = Sketch(d, "A")
    health._observer_note(a)
    assert [x["sketch"] for x in health.check(s, T, inner)["sketches"]] == ["A"]
    b = Sketch(d, "B", dof=1, free=[(0, 0)])
    health._observer_note(b)
    v = {x["sketch"]: x for x in health.check(s, T, outer)["sketches"]}
    assert v["A"]["state"] == "fully constrained" and v["B"]["dof"] == 1 and v["B"]["free"] == ["line 0"]
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
    assert h["addons"] == {"fam": ["Assembly: assembly conflicting constraints"]} and "todo" not in h  # the add-on's own text, under its name


def test_report_lines_counted_in_the_verdict():
    body = {"health": {"recompute": "ok"}}
    health.note_report(body, ["Warning: x", "Error: y"])
    assert body["health"]["reportView"] == 2


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


# ---- sketches: news only (live, 16 Nov: sheet_format repeated a sketch's standing freedom) ----

class Other:
    name, group, changes = "sheet_format", "sheet", True


def run_as(tool, doc, change):
    s = Session(doc)
    m = health.mark(s)
    for o in change() or []:
        health._observer_note(o)
    return health.check(s, tool, m)


def test_a_recomputed_sketch_that_reads_as_before_is_passed_over():
    d = Doc()
    nut = Sketch(d, "NutSketch", dof=1, free=[(0, 0)])
    assert run_as(Other, d, lambda: [nut]) is None


def test_a_sketch_whose_reading_changed_is_said_after_any_call():
    d = Doc()
    nut = Sketch(d, "NutSketch", dof=1, free=[(0, 0)])

    def change():
        nut.DoF, nut._free = 2, [(0, 0), (1, 1)]
        return [nut]

    assert run_as(Other, d, change)["sketches"][0]["dof"] == 2

    def solved():
        nut.DoF, nut._free = 0, []
        return [nut]

    assert run_as(Other, d, solved)["sketches"] == [{"sketch": "NutSketch", "dof": 0, "state": "fully constrained"}]


def test_fully_constrained_is_no_news_after_a_call_that_is_not_a_sketch_tools():
    d = Doc()
    assert run_as(Other, d, lambda: [Sketch(d, "Made")]) is None
    assert run_as(Other, d, lambda: [Sketch(d, "Blank", n=0)]) is None
    # freedom left on a sketch the call made is still said
    assert run_as(Other, d, lambda: [Sketch(d, "Loose", dof=1, free=[(0, 0)])])["sketches"][0]["dof"] == 1
    # and a sketch tool's own call reads its sketch out as before
    assert run_as(T, d, lambda: [Sketch(d, "Mine")])["sketches"][0]["state"] == "fully constrained"


def test_a_sketch_tool_reads_an_unchanged_sketch_out():
    d = Doc()
    sk = Sketch(d, "Sketch", dof=1, free=[(0, 0)])
    assert run_as(T, d, lambda: [sk])["sketches"] == [{"sketch": "Sketch", "dof": 1, "free": ["line 0"]}]


def test_a_sketch_tool_that_names_its_sketch_reads_out_only_that_one_and_changed_ones():
    # 24 Nov blind QA: each sketch's freedom piled up in every verdict.
    d = Doc()
    a = Sketch(d, "A", dof=4, free=[(0, 0), (1, 1)])
    b = Sketch(d, "B", dof=4, free=[(0, 0), (1, 1)])
    s = Session(d)
    m = health.mark(s)
    for o in (a, b):
        health._observer_note(o)
    v = [x["sketch"] for x in health.check(s, T, m, {"sketch": "B"})["sketches"]]
    assert v == ["B"]
    # a sketch it names nothing about but changed is still said
    m = health.mark(s)
    a.DoF, a._free = 3, [(0, 0)]
    for o in (a, b):
        health._observer_note(o)
    v = {x["sketch"]: x["dof"] for x in health.check(s, T, m, {"sketch": "B"})["sketches"]}
    assert v == {"A": 3, "B": 4}


def test_every_free_sketch_names_its_free_geometry():
    d = Doc()
    made = lambda: [Sketch(d, "A", dof=4, free=[(0, 0)]), Sketch(d, "B", dof=2, free=[(0, 0)])]
    v = {x["sketch"]: x for x in run_as(T, d, made)["sketches"]}
    assert v["A"]["free"] == ["line 0"] and v["B"]["free"] == ["line 0"] and v["B"]["dof"] == 2


def test_a_red_sketch_is_said_however_it_read_before():
    d = Doc()
    sk = Sketch(d, "Sketch", conflicting=[2])
    h = run_as(Other, d, lambda: [sk])
    assert h["sketches"][0]["conflicting"] == [1]


def test_a_cam_tool_bits_own_sketch_is_passed_over():
    class Body(Obj):
        TypeId = "PartDesign::Body"

    class Bit(Obj):
        TypeId = "Part::FeaturePython"
        PropertiesList = ["BitBody", "ShapeType"]

    def change(d):
        body, bit = Body(d, "Body"), Bit(d, "ToolBit")
        bit.BitBody = body
        body.InList = [bit]
        sk = Sketch(d, "Sketch001", dof=1, free=[(0, 0)])
        sk.getParentGeoFeatureGroup = lambda: body
        own = Sketch(d, "Profile", dof=1, free=[(0, 0)])
        return [sk, own]

    for tool in (T, Other):
        d = Doc()
        v = [x["sketch"] for x in run_as(tool, d, lambda: change(d))["sketches"]]
        assert v == ["Profile"]


def test_sketch_sig_tells_readings_apart():
    d = Doc()
    a, b = Sketch(d, "A", dof=1), Sketch(d, "B", dof=1)
    assert health.sketch_sig(a) == health.sketch_sig(b)
    b.RedundantConstraints = [3]
    assert health.sketch_sig(a) != health.sketch_sig(b)
    assert health.sketch_tool(T) and not health.sketch_tool(Other) and not health.sketch_tool(None)

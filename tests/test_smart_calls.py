# SPDX-License-Identifier: LGPL-2.1-or-later
# The plain-Python halves of the cheaper, smarter answers: history_diff's
# moved / features / recheck (agentlink/diffing.py), the "next" hint
# (agentlink/nexthint.py) and the stale tool list flag (protocol.Server).
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import diffing, nexthint  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402


# ---- stand-ins for FreeCAD's objects ---------------------------------------------------

class Q:
    Unit = "mm"

    def __init__(self, v):
        self.Value = v


class C:
    def __init__(self, type_, value=0.0, name="", first=0):
        self.Type, self.Value, self.Name, self.First, self.FirstPos = type_, value, name, first, 0
        self.Second = self.SecondPos = self.Third = self.ThirdPos = -2000
        self.Driving = True


class Box:
    XLength, YLength, ZLength = 40.0, 20.0, 0.0


class Shape:
    Length, BoundBox = 120.0, Box()

    def isNull(self):
        return False


class Feat:
    def __init__(self, name, type_id, body=None, **props):
        self.Name, self.Label, self.TypeId, self._body = name, name, type_id, body
        self._types = {}
        for k, v in props.items():
            setattr(self, k, v)
            self._types[k] = "App::PropertyLength" if isinstance(v, Q) else "App::PropertyString"
        self.ExpressionEngine = []

    @property
    def PropertiesList(self):
        return list(self._types) + ["Shape", "Label"]

    def getTypeIdOfProperty(self, p):
        return self._types.get(p, "Part::PropertyPartShape")

    def getParentGeoFeatureGroup(self):
        return self._body


class Body:
    Label = "Block"


class Doc:
    def __init__(self, *objs):
        self.Objects = list(objs)


def sketch(constraints):
    sk = Feat("Sketch", "Sketcher::SketchObject", Body())
    sk.Constraints, sk.GeometryCount, sk.Shape = constraints, 4, Shape()
    return sk


# ---- features ----------------------------------------------------------------------------

def test_an_edited_property_is_named_from_and_to():
    pad = Feat("Pad", "PartDesign::Pad", Body(), Length=Q(10.0), Type="Length")
    doc = Doc(pad, Feat("Plain", "Part::Feature"), Feat("Body", "PartDesign::Body"))
    a = diffing.fingerprint(doc)
    assert set(a) == {"Pad"}  # a plain shape and a Body are not features
    pad.Length = Q(12.5)
    b = diffing.fingerprint(doc, a)
    assert diffing.features_diff(a, b) == {"edited": {"Pad (Block)": {"Length": {"from": 10.0, "to": 12.5}}}}
    assert diffing.features_diff(b, diffing.fingerprint(doc, b)) == {}


def test_an_unchanged_feature_keeps_its_record_between_steps():
    pad = Feat("Pad", "PartDesign::Pad", Body(), Length=Q(10.0))
    doc = Doc(pad)
    a = diffing.fingerprint(doc)
    assert diffing.fingerprint(doc, a)["Pad"] is a["Pad"]


def test_added_and_removed_features_by_name():
    pad, pocket = Feat("Pad", "PartDesign::Pad", Body(), Length=Q(10.0)), Feat("Pocket", "PartDesign::Pocket", Body(), Length=Q(3.0))
    a = diffing.fingerprint(Doc(pad))
    b = diffing.fingerprint(Doc(pocket))
    assert diffing.features_diff(a, b) == {"added": ["Pocket (Block)"], "removed": ["Pad (Block)"]}


def test_a_sketchs_dimension_and_an_expression_are_named():
    sk = sketch([C("Coincident"), C("DistanceX", 40.0, "width"), C("Angle", 1.5707963267948966)])
    doc = Doc(sk)
    a = diffing.fingerprint(doc)
    sk.Constraints = [C("Coincident"), C("DistanceX", 42.0, "width"), C("Angle", 0.7853981633974483)]
    sk.ExpressionEngine = [("Constraints.width", "Params.width")]
    d = diffing.features_diff(a, diffing.fingerprint(doc, a))["edited"]["Sketch (Block)"]
    assert d["constraintValues"] == [{"index": 1, "type": "DistanceX", "name": "width", "from": 40.0, "to": 42.0},
                                     {"index": 2, "type": "Angle", "from": 90.0, "to": 45.0}]
    assert d["Constraints.width (expression)"] == {"from": None, "to": "Params.width"}
    sk.Constraints = sk.Constraints + [C("Horizontal")]
    sk.GeometryCount = 5
    e = diffing.features_diff(a, diffing.fingerprint(doc))["edited"]["Sketch (Block)"]
    assert e["constraints"] == {"from": 3, "to": 4} and e["geometry"] == {"count": {"from": 4, "to": 5}}


def test_too_many_or_too_slow_is_said_not_guessed():
    many = Doc(*[Feat(f"P{i}", "PartDesign::Pad") for i in range(diffing.MAX_FEATURES + 1)])
    got = diffing.fingerprint(many)
    assert "over 600" in got["_unchecked"]
    assert "unchecked" in diffing.features_diff({}, got)
    ticks = iter([0.0, 1.0])
    slow = diffing.fingerprint(Doc(Feat("Pad", "PartDesign::Pad")), clock=lambda: next(ticks))
    assert slow["_slow"] and diffing.fingerprint(Doc(), slow) is slow  # not tried again each step


# ---- moved, recheck ----------------------------------------------------------------------

def test_moved_is_the_lowest_corners_shift_and_only_when_it_moved():
    got = diffing.moved({"A": [0, 0, 0], "B": [1, 1, 1], "Gone": [0, 0, 0]}, {"A": [3, 4, 0], "B": [1, 1, 1], "New": [0, 0, 0]})
    assert got == {"A": {"by": [3.0, 4.0, 0.0], "distance": 5.0}}


def test_recheck_names_only_checks_that_ran_before_the_change():
    log = {}
    labels = ["Block", "Lid"]
    diffing.note_check(log, "body_check", {"body": "block"}, labels, 2)
    diffing.note_check(log, "body_check", {"body": "Lid"}, labels, 2)
    diffing.note_check(log, "asm_check", {}, labels, 3)
    diffing.note_check(log, "shape_query", {"body": "Block"}, labels, 3)  # a query is no check
    diffing.note_check(log, "gone_check", {"body": "Block"}, labels, 1)
    extra = [{"tool": "td_list", "page": "Page", "why": "its views draw Block"}, {"tool": "asm_check", "why": "Block is in an assembly"}]
    got = diffing.recheck({"Block"}, log, 5, lambda body, step: True, known={"body_check", "asm_check", "td_list"}, extra=extra)
    assert got == [{"tool": "body_check", "body": "Block", "ranAt": 2}, {"tool": "asm_check", "ranAt": 3},
                   {"tool": "td_list", "page": "Page", "why": "its views draw Block"}]
    # a check that ran at the newest step, or whose body is as it was then, is not stale
    assert diffing.recheck({"Block"}, {("body_check", "Block"): 5}, 5, lambda b, s: True) == []
    assert diffing.recheck({"Block"}, {("body_check", "Block"): 2}, 5, lambda b, s: False) == []
    assert diffing.recheck(set(), log, 5, lambda b, s: True) == []


def test_a_check_without_a_body_is_the_one_bodys():
    log = {}
    diffing.note_check(log, "body_check", {}, ["Only"], 1)
    assert log == {("body_check", "Only"): 1}


# ---- the next hint -----------------------------------------------------------------------

def test_no_window_no_hint():
    assert nexthint.compose({"window": False}) is None and nexthint.compose(None) is None


def test_the_hint_puts_the_pressing_first_and_stays_short():
    state = {"window": True, "workbench": "SketcherWorkbench", "editing": "sketch", "sketch": {"name": "Outline", "dof": 2},
             "panel": {"buttons": ["Close"]}, "status": "x" * 500, "dialog": {"title": "Unsaved document", "buttons": ["Save", "Discard", "Cancel"]}}
    line = nexthint.compose(state, ["sketch_add", "sketch_constrain", "a", "b", "c", "d"])
    assert line.startswith("a dialog is in front: Unsaved document [Save, Discard, Cancel]")
    assert "sketch Outline is open in edit, 2 DoF left; a task panel is open [Close]; workbench SketcherWorkbench" in line
    assert len(line) <= nexthint.MAX
    short = nexthint.compose({"window": True, "workbench": "PartDesignWorkbench"}, ["pd_pad", "pd_pocket", "a", "b", "c", "d"])
    assert short == "workbench PartDesignWorkbench; active now: pd_pad, pd_pocket, a, b, c"


def test_only_the_active_workbenchs_tools_with_an_active_command_are_named():
    index = {"pd_pad": {"workbench": "PartDesignWorkbench", "commands": ["PartDesign_Pad"], "words": []},
             "pd_pocket": {"workbench": "PartDesignWorkbench", "commands": ["PartDesign_Pocket"], "words": []},
             "td_view": {"workbench": "TechDrawWorkbench", "commands": ["TechDraw_View"], "words": []},
             "pd_note": {"workbench": "PartDesignWorkbench", "commands": [], "words": []}}
    rows = nexthint.candidates(list(index), "PartDesignWorkbench", entry=lambda n: index[n])
    assert [n for n, _e in rows] == ["pd_pad", "pd_pocket"]
    state = {"window": True, "workbench": "PartDesignWorkbench", "active": {"PartDesign_Pad": True, "PartDesign_Pocket": False}}
    assert nexthint.active_tools(rows, state) == ["pd_pad"]
    assert nexthint.candidates(list(index), None, entry=lambda n: index[n]) == []


def test_the_hints_key_ignores_the_status_bar():
    a = {"window": True, "workbench": "W", "status": "one"}
    assert nexthint.key(a) == nexthint.key({**a, "status": "two"})
    assert nexthint.key(a) != nexthint.key({**a, "sketch": {"name": "S", "dof": 1}})


# ---- the stale tool list -----------------------------------------------------------------

def tool(name, group="core", text="does"):
    return Tool(name, text, {"type": "object", "properties": {}}, lambda a: {}, group=group)


def test_a_changed_tool_list_is_said_once_in_full_then_counted():
    srv = Server("s", "1", [tool("a"), tool("b", "model"), tool("c", "model")], groups={"core"})
    assert srv.list_stale() is None  # never listed: nothing to be stale against
    srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert srv.list_stale() is None
    srv.set_groups({"core", "model"})
    srv.add(tool("d", "extra"))
    first = srv.list_stale()
    assert first["added"] == ["b", "c"] and first["callable"] == ["d"] and "tools/list" in first["note"]
    again = srv.list_stale()
    assert again["added"] == 2 and again["callable"] == 1
    srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert srv.list_stale() is None
    srv.tools["b"].description = "does more"  # an add-on updated
    srv.set_groups({"core"})
    srv.set_groups({"core", "model"})
    assert srv.list_stale()["updated"] == ["b"]
    del srv.tools["c"]
    assert srv.list_stale()["removed"] == ["c"]


# ---- a batch's record --------------------------------------------------------------------

def test_a_batch_record_is_rewritten_as_calls_end_and_the_newest_twenty_kept(tmp_path):
    import json

    from agentlink import batchrec

    out = str(tmp_path)
    for i in range(23):
        r = batchrec.BatchRecord(out, 3, 0, now=1_800_000_000 + i)
        r.write({"running": True, "results": []})
    names = sorted(os.listdir(os.path.join(out, batchrec.BATCH_DIR)))
    assert len(names) == batchrec.BATCH_KEEP and all(n.endswith(".json") for n in names)
    r.write({"running": True, "ran": 1, "results": [{"tool": "a", "ok": True, "result": {"x": 1}}]})
    with open(r.path, encoding="utf-8") as f:
        got = json.load(f)
    assert got["calls"] == 3 and got["running"] is True and got["results"][0]["result"] == {"x": 1}
    r.write({"results": [{"tool": "a", "ok": True}], "ran": 1}, final=True)
    with open(r.path, encoding="utf-8") as f:
        assert "running" not in json.load(f)
    # two batches in one second get names of their own
    a = batchrec.BatchRecord(out, 1, 0, now=1_900_000_000)
    a.write({"results": []})
    b = batchrec.BatchRecord(out, 1, 0, now=1_900_000_000)
    assert a.path != b.path and b.path.endswith("-2.json")


def test_a_record_that_cannot_be_written_never_fails_the_batch(tmp_path):
    from agentlink import batchrec

    blocked = tmp_path / "file"
    blocked.write_text("x")
    r = batchrec.BatchRecord(str(blocked), 1, 0)
    r.write({"results": []})
    assert r.ok is False


# ---- why a picture is empty --------------------------------------------------------------

def test_nothing_to_draw_says_which_kind_of_nothing():
    from agentlink import emptywhy as ew

    assert "document is empty" in ew.nothing_to_draw(objects=0)
    assert "every part is hidden (Lid, Box)" in ew.nothing_to_draw(hidden=["Lid", "Box"], objects=2)
    assert "Sketch has no solid shape" in ew.nothing_to_draw(shapeless=["Sketch"], objects=3, named=True)
    assert "no object here has a solid shape (Sketch, Scan" in ew.nothing_to_draw(shapeless=["Sketch", "Scan"], objects=2, layers=["scan"])
    assert "session_state" in ew.nothing_to_draw(objects=4)


def test_a_frame_that_misses_the_model_is_said_with_the_parts_box():
    from agentlink import emptywhy as ew

    box = {"min": [0, 0, 0], "max": [10, 10, 10]}
    assert ew.off_frame({"iso": 0.4}, None, None, box) is None
    assert ew.off_frame({}, None, None, box) is None
    miss = ew.off_frame({"iso": 0.0}, {"at": [500, 0, 0], "size": 20}, None, box)
    assert miss.startswith("Nothing landed") and "outside the parts" in miss and "[10.0, 10.0, 10.0]" in miss
    inside = ew.off_frame({"iso": 0.0}, {"at": [5, 5, 5], "size": 2}, None, box)
    assert "no surface facing the view" in inside
    assert "flip: true" in ew.off_frame({"front": 0.0}, None, {"axis": "x", "offset": 99}, box)
    assert ew.off_frame({"iso": 0.001, "top": 0.0005}, None, None, box).startswith("Almost nothing")
    # one view with something in it is a picture worth looking at
    assert ew.off_frame({"iso": 0.3, "top": 0.0}, None, None, box) is None
    assert ew.no_map("stress", "No stress to show: fea_solve first.").startswith("No stress map to draw: No stress to show")


def test_the_windows_view_empty_missed_or_a_speck():
    from agentlink import emptywhy as ew

    assert "everything is hidden (Box)" in ew.off_screen([], (800, 600), shown=0, hidden=["Box"])
    assert "nothing with a shape" in ew.off_screen([], (800, 600), shown=0)
    assert "misses the model" in ew.off_screen([(900, 100), (950, 200)], (800, 600))
    assert "speck" in ew.off_screen([(400, 300), (402, 301)], (800, 600))
    assert ew.off_screen([(100, 100), (500, 400)], (800, 600)) is None
    assert ew.off_screen([(-50, 100), (500, 400)], (800, 600)) is None  # partly in frame
    assert ew.off_screen([], None) is None


def test_a_views_cover_is_measured():
    import numpy as np

    from agentlink import render

    V = np.array([[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]], dtype=float)
    F = np.array([[0, 1, 2], [0, 2, 3]])
    layer = {"name": "b", "V": V, "F": F, "color": (0.8, 0.5, 0.3)}
    cover = {}
    render.compose([layer], ["top"], 200, 200, cover=cover)
    assert cover["top"] > 0.3
    cover = {}
    render.compose([layer], ["top"], 200, 200, frame={"at": [500.0, 500.0, 0.0], "size": 5.0}, cover=cover)
    from agentlink import emptywhy

    assert cover["top"] <= emptywhy.ALMOST  # a stray pixel may land: still an empty picture
    assert emptywhy.off_frame(cover, {"at": [500.0, 500.0, 0.0], "size": 5.0}, None, {"min": [0, 0, 0], "max": [10, 10, 0]})

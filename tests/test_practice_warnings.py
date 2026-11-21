# SPDX-License-Identifier: LGPL-2.1-or-later
# Modelling-practice warnings (agentlink/practice.py) in the health reading
# of a changing call and in body_check, on stand-in objects (plain Python):
# a Body of mostly primitives, a long boolean chain, Refine on in a weldment,
# many bodies in one file, a modelled thread. Advice only: never red, said
# once for each object and kind, nothing added when nothing fires.
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import fusehint, health, practice  # noqa: E402
from test_health import Doc, Obj, Session  # noqa: E402

LINE_TOKENS = 45  # tests/test_needs.py BOUNDS["line"]


class T:
    name, group, changes = "t", "model", True


class PB:
    name, group, changes = "part_boolean", "model", True


def obj(doc, name, type_, **kw):
    o = Obj(doc, name)
    o.TypeId = type_
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def body(doc, name, feats, **kw):
    b = obj(doc, name, "PartDesign::Body", **kw)
    b.Group = feats
    return b


def run(s, doc, change, tool=T):
    m = health.mark(s)
    for o in change() or []:
        health._observer_note(o)
    return health.check(s, tool, m)


def tokens(x):
    return round(len(json.dumps(x, ensure_ascii=False)) / 3.5)


def test_body_mostly_primitives():
    d = Doc()
    feats = [obj(d, f"Box{i}", "PartDesign::AdditiveBox") for i in range(3)] + [obj(d, "Pad", "PartDesign::Pad")]
    b = body(d, "Frame", feats)
    h = run(Session(d), d, lambda: [b])
    assert h["ok"] is True and h["verdict"] == "nothing red"
    assert h["practice"] == ["Body Frame: 3 of 4 features are primitives. A sketch with a pad, pocket or revolution keeps sizes as constraints."]
    assert all(tokens(x) <= LINE_TOKENS for x in h["practice"])


def test_no_warning_on_a_clean_sketch_based_body():
    d = Doc()
    sk = obj(d, "Sketch", "Sketcher::SketchObject")
    b = body(d, "Bracket", [sk, obj(d, "Pad", "PartDesign::Pad"), obj(d, "Pocket", "PartDesign::Pocket"),
                            obj(d, "Hole", "PartDesign::Hole", ModelThread=False, Threaded=True)])
    h = run(Session(d), d, lambda: [b])
    assert h is None or "practice" not in h
    assert practice.findings(d.Objects) == []


def test_long_part_boolean_chain():
    d = Doc()
    c = [obj(d, "A", "Part::Box"), obj(d, "B", "Part::Box")]
    prev = c[0]
    for i in range(4):
        prev = obj(d, f"Cut{i}", "Part::Cut", Base=prev, Tool=obj(d, f"T{i}", "Part::Cylinder"))
    assert [(o.Label, n) for o, n in practice.chains(d.Objects)] == [("Cut3", 4)]
    h = run(Session(d), d, lambda: [prev])
    assert "Cut3: 4 booleans in a chain." in h["practice"][0]


def test_part_boolean_results_counted_on_one_label():
    d = Doc()
    base = obj(d, "Plate", "Part::Feature")
    s = Session(d)
    said = []
    for _ in range(4):
        h = run(s, d, lambda: [base], tool=PB)
        said.append((h or {}).get("practice"))
    assert said[:3] == [None, None, None]
    assert said[3] == ["Plate: 4 part_boolean steps. Sketch-based features in one PartDesign body keep each step small and editable."]


def test_refine_on_in_a_weldment_one_rule():
    d = Doc()
    tubes = [obj(d, f"Tube{i}", "PartDesign::Body") for i in range(4)]
    fuse = obj(d, "Fuse", "PartDesign::Boolean", Type="Fuse", Group=tubes, PropertiesList=["Refine"], Refine=True)
    b = body(d, "Frame", [obj(d, "Pad", "PartDesign::Pad", PropertiesList=["Refine"], Refine=False), fuse])
    assert fusehint.members(b) == 4
    h = run(Session(d), d, lambda: [b])
    assert h["practice"] == ["Body Frame: Refine is on in a weldment of 4 members. Set Refine off on its features, or the body can become unorientable."]
    # the todo on an invalid shape counts the same members (more than 8)
    assert fusehint.refine_todo(b, "") is None
    fuse.Group = [obj(d, f"T{i}", "PartDesign::Body") for i in range(9)]
    assert "many tube members (9)" in fusehint.refine_todo(b, "")
    # Refine off: nothing
    fuse.Refine = False
    assert practice.weldment(b) is None


def test_many_bodies_in_one_file():
    d = Doc()
    for i in range(9):
        body(d, f"Part{i}", [obj(d, f"Pad{i}", "PartDesign::Pad")])
    h = run(Session(d), d, lambda: [d.Objects[-1]])
    assert "9 bodies in one file. One file for each part, linked into an assembly file, keeps rebuilds small." in h["practice"]
    # other files open and no assembly: no warning
    assert not [f for f in practice.findings(d.Objects, others=2) if f[0] == "bodies"]
    obj(d, "Assembly", "Assembly::AssemblyObject")
    assert [f for f in practice.findings(d.Objects, others=2) if f[0] == "bodies"]


def test_modelled_thread_and_thread_not_made():
    d = Doc()
    hole = obj(d, "Hole", "PartDesign::Hole", ModelThread=True, Reversed=False, DepthType="ThroughAll")
    b = body(d, "Block", [obj(d, "Pad", "PartDesign::Pad"), hole],
             Shape=types.SimpleNamespace(BoundBox=types.SimpleNamespace(XLength=40, YLength=30, ZLength=10)))
    s = Session(d)
    h = run(s, d, lambda: [b])
    assert h["practice"] == ["Hole Hole has a modelled thread. A thread as data (threaded, no modelThread) is enough unless the part is printed."]
    hole.DepthType, hole.Depth = "Dimension", 6.0  # blind: shorter than the part
    h = run(s, d, lambda: [b])
    assert h["practice"] == ["Hole Hole: the thread is not made with Reversed or a blind depth. Turn off modelThread, or make the hole through all."]
    hole.DepthType, hole.Reversed = "ThroughAll", True
    assert practice.thread(hole, b) == "not made"
    assert all(tokens(x) <= LINE_TOKENS for x in h["practice"])


def test_fires_once_not_again_until_the_state_changes():
    d = Doc()
    feats = [obj(d, f"Cyl{i}", "PartDesign::AdditiveCylinder") for i in range(3)]
    b = body(d, "Post", feats)
    s = Session(d)
    first = run(s, d, lambda: [b])
    assert first["practice"]
    again = run(s, d, lambda: [b])
    assert again is None or "practice" not in again  # said before: not again
    b.Group = feats + [obj(d, f"Pad{i}", "PartDesign::Pad") for i in range(3)]  # now clean
    clean = run(s, d, lambda: [b])
    assert clean is None or "practice" not in clean
    b.Group = feats + [obj(d, "Box9", "PartDesign::AdditiveBox")]  # back again: said again
    back = run(s, d, lambda: [b])
    assert back["practice"][0].startswith("Body Post: 4 of 4 features")


def test_every_line_inside_the_line_bound():
    long = "L" * 24
    d = Doc()
    b = body(d, long, [obj(d, f"Box{i}", "PartDesign::AdditiveBox") for i in range(3)])
    for _k, _o, _s, line in practice.findings(d.Objects):
        assert tokens(line) <= LINE_TOKENS, line
    for i in range(9):
        body(d, f"P{i}", [])
    for _k, _o, _s, line in practice.findings(d.Objects):
        assert tokens(line) <= LINE_TOKENS, line
    assert b

# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tests T1 and T2 of claude/tool-research-2026-11-21.md, without FreeCAD:
a partly loaded document refuses changes and saves; a bind through a link
property (Body.Tip.Length) is refused with the object to bind instead."""
import ast
import os

from agentlink import partialdoc

HERE = os.path.dirname(os.path.abspath(__file__))


class Doc:
    def __init__(self, partial):
        self.Partial = partial
        self.Label = "ResP"


def test_partial_refuses_changes_and_save():
    d = Doc(True)
    said = partialdoc.refusal(d, "object_set")
    assert said and "doc_revert" in said and "nothing would be kept" in said
    assert "nothing would be saved" in partialdoc.refusal(d, "doc_save")


def test_partial_lets_the_way_out_run():
    d = Doc(True)
    for name in ("doc_revert", "doc_open", "doc_switch", "doc_close", "doc_new", "batch"):
        assert partialdoc.refusal(d, name) is None


def test_full_document_is_not_refused():
    assert partialdoc.refusal(Doc(False), "object_set") is None
    assert partialdoc.refusal(object(), "object_set") is None


def _through_link():
    src = open(os.path.join(HERE, "..", "agentlink", "families", "param.py")).read()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "through_link")
    ns = {}
    exec(compile(ast.Module([fn], []), "param.py", "exec"), ns)
    return ns["through_link"]


class Feature:
    Name = "Pad001"
    Label = "Pad 2"


class Body:
    Label = "BodyB"
    Tip = Feature()
    KINDS = {"Tip": "App::PropertyLink", "Placement": "App::PropertyPlacement",
             "Constraints": "Sketcher::PropertyConstraintList"}

    def getTypeIdOfProperty(self, name):
        return self.KINDS[name]


def test_bind_through_tip_is_refused_with_the_feature():
    said = _through_link()(Body(), "Tip.Length")
    assert said and "Pad001.Length" in said and "'Pad 2'" in said


def test_other_paths_pass():
    f = _through_link()
    for path in ("Tip", "Placement.Base.x", "Constraints.half_w"):
        assert f(Body(), path) is None
    assert f(Body(), "NoSuch.Length") is None

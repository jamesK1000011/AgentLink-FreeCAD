# SPDX-License-Identifier: LGPL-2.1-or-later
# app_restart leaves out copies opened from an add-on's temporary folder,
# so a restart no longer chains "_recovered" copies.
import ast
import os
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "agentlink" / "families" / "app.py"


def _temp_copy():
    tree = ast.parse(SRC.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_temp_copy")
    ns = {"os": os}
    exec(compile(ast.Module([fn], []), str(SRC), "exec"), ns)
    return ns["_temp_copy"]


def test_temp_copies_are_not_reopened():
    f = _temp_copy()
    assert f("/var/folders/x/T/agentlink-recovered-ab12/Part_recovered.FCStd")
    assert f("/tmp/agentlink-restore-zz/Part.FCStd")
    assert not f("/Users/me/Parts/Part.FCStd")
    assert not f("")


def _fns(tmp):
    """_temp_copy, _scratch, unsaved_path and restart_plan from app.py, with
    ~/AgentLink/unsaved at tmp."""
    import re

    tree = ast.parse(SRC.read_text())
    want = ("_temp_copy", "_scratch", "unsaved_path", "restart_plan")
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
    ns = {"os": os, "re": re}
    exec(compile(ast.Module(fns, []), str(SRC), "exec"), ns)
    ns["_unsaved_dir"] = lambda: tmp
    return ns


class Doc:
    def __init__(self, name, file="", changed=True):
        self.Name, self.Label, self.FileName, self.changed = name, name, file, changed


def test_restart_reopens_an_agents_unsaved_document_once(tmp_path=None):
    """An agent's never-saved document is kept in ~/AgentLink/unsaved and
    reopened by path; at the next restart that file, and a copy reopened
    from a temporary folder, are saved in place — never copied again as a
    "(recovered …)" copy of a copy. The person's documents keep the rule."""
    import tempfile

    tmp = tempfile.mkdtemp()
    ns = _fns(tmp)
    plan = ns["restart_plan"]
    changed = lambda d: d.changed  # noqa: E731
    lesson = Doc("PocketLesson")
    theirs_new = Doc("Unnamed1")
    theirs = Doc("Bracket", "/Users/me/Bracket.FCStd")
    mine_file = Doc("Plate", "/Users/me/Plate.FCStd")
    same = Doc("Base", "/Users/me/Base.FCStd", changed=False)
    got = {d.Name: how for d, how in plan([lesson, theirs_new, theirs, mine_file, same], changed, "agent", {"PocketLesson", "Plate"})}
    assert got == {"PocketLesson": "unsaved", "Unnamed1": "copy", "Bracket": "copy", "Plate": "save"}
    # Kept once: the next restart saves that file in place.
    p = ns["unsaved_path"]("PocketLesson")
    assert p == os.path.join(tmp, "PocketLesson.FCStd")
    open(p, "w").close()
    assert ns["unsaved_path"]("PocketLesson") == os.path.join(tmp, "PocketLesson-2.FCStd")
    assert ns["unsaved_path"]("PocketLesson (recovered 00:17)", [os.path.join(tmp, "PocketLesson-2.FCStd")]) == os.path.join(tmp, "PocketLesson-3.FCStd")
    again = Doc("PocketLesson", p)
    copy = Doc("Bracket001", "/var/folders/x/T/agentlink-recovered-ab12/Bracket.FCStd")
    got = {d.Name: how for d, how in plan([again, copy], changed, "agent", set())}  # a new session: mine is empty
    assert got == {"PocketLesson": "keep", "Bracket001": "keep"}
    # save: none leaves an agent's never-saved document to the copy add-on;
    # discard drops it.
    assert plan([Doc("PocketLesson")], changed, "none", {"PocketLesson"})[0][1] == "copy"
    assert plan([Doc("PocketLesson")], changed, "agent", {"PocketLesson"}, True)[0][1] == "drop"
    assert ns["_scratch"](p) and not ns["_scratch"]("/Users/me/Bracket.FCStd") and not ns["_scratch"]("")


def test_the_restart_note_names_what_app_recover_reopened():
    """app_recover's own "reopened" list (documents opened again from their
    files) is in the restart's words, each once, beside the supervisor's."""
    from agentlink import supervise

    got = {"recovered": [], "reopened": [{"document": "M18Skin", "label": "M18Skin", "why": "saved, unchanged"}, {"document": "Stem"}]}
    assert supervise.reopened_by_recover(got) == ["M18Skin", "Stem"]
    assert supervise.reopened_by_recover(None) == [] and supervise.reopened_by_recover({"recovered": []}) == []
    assert supervise.once(["M18Skin"] + supervise.reopened_by_recover(got)) == ["M18Skin", "Stem"]

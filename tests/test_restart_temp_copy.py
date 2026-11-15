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

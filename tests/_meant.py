# SPDX-License-Identifier: LGPL-2.1-or-later
# Meant changes to tool descriptions since the data tests' snapshots were taken
# (docs/hardening/famfix-findings.md): each tool's old words and the true facts
# added or changed. The data tests apply them to the snapshot before comparing
# byte for byte, so any other change to a description still fails.

DESCRIPTIONS = {
    'bim_import': ('Type, read (which reader)',
        "Type, read (which reader), and a note when what was read lies over the document's own model: the file is read in its own coordinates into this document (doc_new first for a document of its own)"),
    'bim_rebar': (', totalLength_m, mass_kg.',
        ", totalLength_m, mass_kg. FreeCAD's rebar is laid on a hidden Draft wire (its base, from which FreeCAD reads the bar's length)."),
    'fea_buckle': ('nd gmsh (timeout s, 300).',
        "nd gmsh (timeout s, 300). Its results are the answer and files in the out folder (files): it makes no FEM objects in the document's tree."),
    'fea_heat': ('300); needs ccx and gmsh.',
        "300); needs ccx and gmsh. Its results are the answer and files in the out folder (files): it makes no FEM objects in the document's tree."),
    'fea_modes': ('nd gmsh (timeout s, 300).',
        "nd gmsh (timeout s, 300). Its results are the answer and files in the out folder (files): it makes no FEM objects in the document's tree."),
    'fea_native': ('ElmerSolver is installed.',
        'ElmerSolver is installed. Refused, with nothing made, in a FreeCAD session that can no longer draw a FEM mesh ("Cannot add static property", FreeCAD\'s own fault): restart FreeCAD.'),
    'fea_results': (' (kept with the session, not the file), with stale: true and staleWhy when the body or the study changed since.',
        " (kept with the session, not the file), with solvedFor { document, body } and stale: true and staleWhy when the body or the study changed since. Only the solve of this document's study: one kept from another study or document is refused, named (fea_solve first)."),
    'fea_export': (' (both by default), name.',
        " (both by default), name. Only the solve of this document's study (solvedFor names it; another study's is refused)."),
    'fea_setup': ('rary figures are typical.',
        "rary figures are typical. The study is Agent Link's, kept with the document: fea_setup, fea_hold and fea_load add no FEM objects to the tree (fea_native builds it as FreeCAD's own analysis, fea_solve where its FEM route runs)."),
    'fea_solve': ('s ccx and gmsh installed.',
        's ccx and gmsh installed. When FreeCAD\'s FEM route fails, what it had made is taken out again and the own deck\'s results are the answer and files only (solvedBy says so). In a FreeCAD session where FreeCAD can no longer draw a FEM mesh ("Cannot add static property", a FreeCAD fault left by the first FEM mesh made while a window observer listened) the route fails until FreeCAD is restarted.'),
    'meshobj_segments': (': true makes those meshes',
        ": true makes those meshes, each in a colour of its own in the window (as FreeCAD's Mesh_Segmentation colours its segments)"),
    'pd_multitransform': ('t: stepOf) and go with it',
        "t: stepOf) and go with it; as FreeCAD's own command leaves them, the steps are hidden and listed after the MultiTransform, which is the tip and the one shown"),
    'td_balloon': ("ext number), at [dx, dy] from the view's centre",
        "ext number), at [dx, dy] paper mm from the view's centre. Its tip and bubble are kept as FreeCAD keeps them, in the view's own unscaled frame (OriginX/Y, X/Y over the view's scale)"),
    'td_centermarks': (' only. Drawn by td_export, not in the window',
        " only. Drawn by td_export; in the window the same chain lines are drawn as FreeCAD's own cosmetic centre lines on those circles only, and FreeCAD's own crosses of the view (its ArcCenterMarks, which mark every arc's centre, a slot's ends too) are switched off"),
    'td_export': ("notes says what was skipped.",
        "notes says what was skipped; stacked names dimensions whose texts lie on one spot (td_dim_align or object_set X, Y moves one)."),
    'td_hatch': ('Drawn by td_export, not in the window;',
        "Drawn by td_export, and in the window as FreeCAD's own hatch (TechDraw::DrawHatch, its default pattern) on the view's face that shows each (window says which, or why none);"),
    'td_table': ('an empty sheet is refused.',
        "an empty sheet is refused. size: the text's height on the paper, mm (3.5): the table's scale is set for it (reply: scale)."),
    'td_weld': ('page), drawn by td_export (the window shows the leader only',
        "page), drawn by td_export, and in the window as FreeCAD's own weld symbol on the leader (TechDraw::DrawWeldSymbol, with FreeCAD's own symbol for fillet, square, v, plug and surfacing; the other kinds show their words only, and window says which"),
    # 18 Nov live build, 18 Nov: heavy changes estimated first, a big export a job.
    'part_from_mesh': ('omes the solid (note says so).',
        'omes the solid (note says so). refine about doubles the time; an estimate over a minute: the first call answers with the time and runs nothing, the same call again runs it.'),
    'insp_run': ('st [{ at, distance }], health.',
        'st [{ at, distance }], health. An estimate over a minute: the first call answers with the time and runs nothing, the same call again runs it.'),
    'export': ('nce: the chord error, 0.01 mm.',
        'nce: the chord error, 0.01 mm. Meshing B-spline faces can be slow: an estimate over 20 s runs as a job (job_status); in a batch an estimate over a minute answers with the time first, the same call again runs it.'),
}



# Branch explore/full-ste: every hub tool's description is rewritten in ASD-STE100, in place. A snapshot's
# words (with the meant changes above) must still be main's original word for word (scripts/ste_originals.json);
# the tool's words are then the STE text, which tests/test_ste_lint.py checks against that original: every
# number, unit, input name, other tool's name and guard word kept, every sentence 20 words at most.
_STE = {}


def _ste():
    if not _STE:
        import json
        import os

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "scripts", "ste_originals.json"), encoding="utf-8") as f:
            _STE["orig"] = json.load(f)["tools"]
        with open(os.path.join(root, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            _STE["now"] = {n: e["description"] for n, e in json.load(f)["entries"].items()}
    return _STE


def _meant_only(name, old):
    if name not in DESCRIPTIONS:
        return old
    was, now = DESCRIPTIONS[name]
    assert old.count(was) == 1, (name, was)
    return old.replace(was, now)


def description(name, old):
    """The snapshot's description of a tool with its meant change made, and
    then the STE rewrite when the result is main's original word for word."""
    text = _meant_only(name, old)
    s = _ste()
    if name in s["now"] and s["orig"].get(name, {}).get("description") == text:
        return s["now"][name]
    return text


# Meant changes to what a converted tool does on the stand-in FreeCAD since
# its handler (the trace line at BASE, the line now, why). The data tests put
# the new line in place of the old one before they compare the traces.
TRACES = [
    (", 0.0873, False)", ", 0.5, False)",
     "Live 65: an exported mesh is made with an angular deflection of 0.5 rad (geometry.EXPORT_ANGULAR), not 0.0873: one loft face made 3.77 M triangles."),
]


def trace_as_meant(lines):
    """A trace from BASE with the meant changes (TRACES) made."""
    out = []
    for ln in lines:
        if isinstance(ln, str):
            for old, new, _why in TRACES:
                ln = ln.replace(old, new)
        out.append(ln)
    return out

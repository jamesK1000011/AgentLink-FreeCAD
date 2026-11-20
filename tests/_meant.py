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
    # Test drive of 20 Nov (findings 1, 2, 3, 9, 11, 12).
    'object_delete': ('Again, renamed). Reply: deleted, errors, health.',
        "Again, renamed). Reply: deleted, errors, health. A container that only holds the object is not a user (a Body, an App::Part, a group): an unused sketch or the tip feature of a Body deletes without force, and the Body's tip moves back."),
    'object_get': ('— use it, a feature has dozens. Changes nothing.',
        '— use it, a feature has dozens. Changes nothing. Several words go in one filter with | between them ("Length|Width"): a property that has one of them matches.'),
    'object_set': ('only Placement; Label is set with object_rename.',
        'only Placement; Label is set with object_rename. For one property, property and value also work: { property: "Length", value: 20 }.'),
    'asm_joint': [
        # Test drive of 20 Nov (bicycle, findings 4, 3, 5): no flip by itself, keep, chain by teeth.
        ("gears and belt (radius1, radius2 — read off round edges when left out).",
         "gears and belt (radius1, radius2 — read off round edges when left out); chain, FreeCAD's belt joint with the ratio teeth1 / teeth2 (50 / 16 = 3.125): "
         "the teeth given, or read from a PartDesign Sprocket (NumberOfTeeth) in each part, pitch the chain pitch mm (12.7); gears and belt take teeth1, teeth2 too; "
         "reply ratio and ratioFrom."),
        ("(false keeps FreeCAD's way; left out, it is turned over when that stops parts overlapping).",
         "(false keeps FreeCAD's way; left out, no part is turned over by itself: parts that overlap after the solve get a warning naming them, with how to flip; "
         "autoFlip: true turns the moved part over when that stops the overlap, the old way, and flipWarning says when the flip put a part's centre on the other "
         "side of the joint's plane). keep: true, for parts already placed: the offset (and the turn about the joint) that holds them where they stand, so nothing "
         "moves — reply kept { property, at, axis, angle, moved }; not with offset, rotate, gap, reverse or autoFlip."),
        (': asm_check and asm_sweep show what still moves.',
        ": asm_check and asm_sweep show what still moves. near in a query is in document coordinates (where the part is now); nearLocal is a point in the part's own frame, as modelled. offset's direction depends on which part moves; gap: mm between the two joined faces after the solve, positive apart, negative overlapping — the tool finds the offset for it (gap or offset, not both). Reply also: gap (the result across the joint, mm, negative for overlap) and at (the centre of each element when picked, in document coordinates)."),
    ],
    'asm_sweep': ("Each step cuts every pair of parts (a call is dropped after about 80 s): with many parts, fewer steps or a shorter range, not a job.",
        "Each step cuts every pair of parts (a call is dropped after about 80 s): the sweep stops in time (about 60 s), and then answers the steps done with "
        "partial: true, stepsDone and continueWith { joint, from, to, steps } for the next call; with many parts, fewer steps or a shorter range, not a job. "
        "Overlaps there at the first step with the same volume at every step are static (a press fit, parts modelled into each other): staticOverlaps lists "
        "them with their volume, and verdict, collidesAt and clearFromStart count only the contacts the motion makes."),
    'asm_bom': (' volume }]; a part with no material has no mass.',
        " volume }]; a part with no material has no mass. A part can be in a print setup: then mass is the printed estimate (walls and infill) of an installed add-on that owns mass, massAs tells how and solidMass is the solid mass; without that add-on, massAs marks the mass as solid, not as printed. slice gives the slicer's own figure."),
    'material_set': ('bject_rename does not carry it to the new label.',
        "bject_rename does not carry it to the new label. The short ids of measure_mass also work (steel, stainless, aluminium, brass …): the tool sets a FreeCAD library card for one, or Agent Link's stock figures; mapped tells which."),
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
    pairs = DESCRIPTIONS[name]
    for was, now in (pairs if isinstance(pairs, list) else [pairs]):
        assert old.count(was) == 1, (name, was)
        old = old.replace(was, now)
    return old


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
    (".newObject('PartDesign::CoordinateSystem', 'LCS')", ".newObject('Part::LocalCoordinateSystem', 'LCS')",
     "20 Nov, skeleton workflow: pd_datum kind lcs makes FreeCAD 1.1's Part::LocalCoordinateSystem (an App::LocalCoordinateSystem, which a Body "
     "takes and Assembly joints read with its own origin, axes and planes); PartDesign::CoordinateSystem only where that type is not there."),
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


# Meant changes to a converted tool's inputSchema since its snapshot (test
# drive of 20 Nov): per tool, new descriptions of inputs, inputs put
# in after a named one (in that order), and the required list.
# a: near's frame said, nearLocal (20 Nov); b said as a, so the card holds at 900 tokens (bicycle drive).
_NEAR_A = "{ part, element }: element \"Face6\" or a shape_query query { kind: face|edge, normal, near, nearLocal, radius, type }; near picks the closest."
SCHEMAS = {
    "asm_joint": {"why": "findings 2, 3: gap across the joint; near's frame said, nearLocal. Bicycle 3, 4, 5: keep, autoFlip, chain by teeth",
                  "describe": {"a": _NEAR_A, "b": "As a."},
                  "enum_add": {"kind": ["chain"]},
                  "after": [("offset", "gap", {"type": "number", "description": "mm between the joined faces after the solve: positive apart, negative overlap. Not with offset."}),
                            ("reverse", "autoFlip", {"type": "boolean"}), ("autoFlip", "keep", {"type": "boolean"}), ("keep", "teeth1", {"type": "integer"}),
                            ("teeth1", "teeth2", {"type": "integer"})]},
    "object_set": {"why": "finding 12: { property, value } as well as { values }",
                   "after": [("values", "property", {"type": "string", "description": "One property's name, with value: the same as values { property: value }."}),
                             ("property", "value", {})],
                   "required": ["object"]},
    # 20 Nov, the skeleton workflow of the design kickoff: a datum on several references of any object,
    # its mode, its AttachmentOffset, and (part_datum) the Body or App::Part that holds it.
    "pd_datum": {"why": "skeleton workflow: refs, mode, offset",
                 "after": [("rotate", "refs", {"type": "array", "items": {"type": "string"},
                                               "description": "One to four references in order, any object: \"Binder.Vertex1\", \"Skeleton.Edge2\", a whole \"Skeleton\". Not with on."}),
                           ("refs", "mode", {"type": "string", "description": "With refs: a FreeCAD MapMode (OZX, ObjectXY, Translate, Concentric, NormalToEdge …)."}),
                           ("mode", "offset", {"type": "object", "description": "With refs: { at: [x,y,z], rotate: { axis, angle } }, the AttachmentOffset in the frame that the references give."})]},
    "part_datum": {"why": "skeleton workflow: refs, offset, body, part",
                   "after": [("to", "refs", {"type": "array", "items": {"type": "string"},
                                             "description": "One to four references in order, any object: \"Binder.Vertex3\", \"Skeleton.Edge2\", a whole \"LCS\". Not with to."}),
                             ("mode", "offset", {"type": "object", "description": "{ at: [x,y,z], rotate: { axis, angle } }: the AttachmentOffset, in the frame that the references give."}),
                             ("offset", "body", {"type": "string", "description": "A PartDesign Body to hold the datum."}),
                             ("body", "part", {"type": "string", "description": "An App::Part to hold the datum."})]},
}


def schema(name, old):
    """The snapshot's inputSchema of a tool with its meant change made."""
    import copy

    m = SCHEMAS.get(name)
    if not m:
        return old
    new = copy.deepcopy(old)
    props = new["properties"]
    for k, text in m.get("describe", {}).items():
        props[k]["description"] = text
    for k, more in m.get("enum_add", {}).items():
        props[k]["enum"] = list(props[k]["enum"]) + list(more)
    for at, key, val in m.get("after", []):
        out = {}
        for k, v in props.items():
            out[k] = v
            if k == at:
                out[key] = val
        props = out
    new["properties"] = props
    if "required" in m:
        new["required"] = list(m["required"])
    # the keys in the order the entry keeps them
    return {k: new[k] for k in old}


# Answer fields a converted tool now adds to what its handler answered (the
# data tests take them out of the new answer before they compare): per tool,
# the field names and why.
RESULTS = {
    "asm_joint": (("gap", "gapIs", "gapWarning", "offset", "at", "flipWarning", "crossedPlane", "kept", "keepWarning", "ratio", "ratioFrom", "teeth"),
                  "findings 2, 3: the gap across the joint and where each element was picked; bicycle 3, 4, 5: keep, the flip's plane, a coupling's ratio"),
    "asm_sweep": (("staticOverlaps", "staticNote", "partial", "stepsDone", "continueWith", "partialNote"), "bicycle 6, 7: a sweep in time, static overlaps apart"),
    "asm_bom": ((), "finding 11: rows of parts in a print setup carry massAs and solidMass (none in the stand-in's cases)"),
    "pd_datum": (("refs", "mode", "offset", "world", "type"), "skeleton workflow (20 Nov): a datum attached by refs says them, its mode, offset and world placement"),
    "part_datum": (("refs", "offset", "in", "world"), "skeleton workflow (20 Nov): refs, the container and the world placement"),
}


def result_as_meant(tool, new):
    """A case's new run with the fields RESULTS names taken out of its answer."""
    names = RESULTS.get(tool, ((),))[0]
    res = new.get("result")
    if not names or not (isinstance(res, list) and res and res[0] == "ok" and isinstance(res[1], dict)):
        return new
    return {**new, "result": [res[0], {k: v for k, v in res[1].items() if k not in names}] + res[2:]}

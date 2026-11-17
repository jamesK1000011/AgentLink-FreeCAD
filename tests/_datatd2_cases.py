# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datatd2_data.py runs through the old handler and the
# new data entry of each converted tool, on that family file's stand-in: its
# normal paths and each of its refusals. A case is (tool, case name,
# prepare(session), arguments).
import json
import os

# tool -> (the family file it was in, its group)
TOOLS = {**{k: ("techdraw", "techdraw") for k in ("td_list", "td_export", "td_cosmetic", "td_view_more", "td_lines")},
         **{k: ("cam_more", "cam_more") for k in ("cam_path", "cam_property_bag", "cam_template_export", "draft_fix", "asm_rigid_group", "asm_new_part")},
         **{k: ("openscad", "openscad") for k in ("scad_status", "scad_import", "scad_code", "scad_export", "scad_op")}}
# The family files whose tools were converted, and each one's stand-in.
STANDIN = {"techdraw": "_datatd2_standin", "cam_more": "_datatd2_cam_standin", "openscad": "_datatd2_scad_standin"}
FILES = tuple(STANDIN)
CONVERTED = {k: g for k, (f, g) in TOOLS.items()}
# Tools of those files kept as code, and why: none.
KEPT = {}
# Refusals written in an entry that no case reaches, each with its reason.
UNREACHED = []
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("td_list", "a page with everything"): {"page": "Drawing", "gdt": [{"symbol": "Frame", "kind": "frame", "reads": "⏥ | 0.05", "on": "Edge0"}, {"symbol": "Datum", "kind": "datum", "reads": "datum A", "on": "Edge1"},
                                                                        {"symbol": "Finish", "kind": "finish", "reads": "ra 1.6 lay =", "on": "Edge2"}, {"symbol": "Odd", "kind": "odd", "reads": "odd", "on": None}],
                                            "other": [{"object": "Note", "type": "DrawViewAnnotation"}]},
    ("td_list", "views just opened, worked out"): {"computed": "3 views had no lines yet (a document just opened keeps a view's settings, not its lines): worked out here in 0 s before reading."},
    ("td_list", "views that stay without lines"): {"notReady": "No lines yet for Front, Front, Top: their edge counts and the dimensions on them are left out, not zero. "
                                                               "A view whose source has no shape or whose page has KeepUpdated off stays so; otherwise recompute, then td_list again."},
    ("td_export", "TechDraw's DXF writer stops"): {"files": {"dxf": {"path": "<out>/Drawing.dxf", "bytes": 1619}},
                                                   "notes": ["Front: 'Shape' object has no attribute 'discretize'", "TechDraw's DXF writer failed (no DXF here): written here instead"]},
    ("td_export", "svg, named"): {"page": "Drawing", "files": {"svg": {"path": "<out>/plate-drawing.svg", "bytes": 1349}}},
    ("td_cosmetic", "a line"): {"view": "Front", "made": [{"kind": "line", "length_mm": 44.721}], "total": 1, "native": 1},
    ("td_cosmetic", "a centerline, extended"): {"made": [{"kind": "centerline", "length_mm": 31.0}]},
    ("td_cosmetic", "a tapped hole, end on, pitch given"): {"made": [{"kind": "thread", "end": True, "diameter": 11.534, "pitch": 1.25}], "native": 36},
    ("td_cosmetic", "a tapped hole, side view, its length"): {"made": [{"kind": "thread", "end": False, "nominal": 22.454, "pitch": 2.0, "note": "M22.5x2"}], "total": 2},
    ("td_cosmetic", "three more beside the earlier ones"): {"total": 6, "native": 38},
    ("td_cosmetic", "a FreeCAD before 1.1"): {"native": 0, "note": "This FreeCAD made no cosmetic edges of its own: the lines show in td_export only."},
    ("td_cosmetic", "a centerline of a vertex"): ["refused", "invalid_input", "Vertex1: an edge of the view (td_geometry lists them)."],
    ("td_view_more", "broken"): {"kind": "broken", "view": "BrokenView", "type": "DrawBrokenView", "at": [150.0, 60.0]},
    ("td_view_more", "stack bottom"): {"kind": "stack", "view": "Front", "stackOrder": 6},
    ("td_view_more", "move a group's item"): {"view": "Views", "from": "Drawing", "page": "Second", "note": "Moved with its projection group."},
    ("td_view_more", "move to where it is"): {"kind": "move", "view": "Front", "page": "Drawing", "note": "Already on that page.", "step": None},
    ("td_view_more", "draft, a name taken"): {"view": "Front 2", "type": "DrawViewDraft"},
    ("td_view_more", "clip_remove"): {"clip": "Window", "views": []},
    ("td_view_more", "share with its dimensions"): {"view": "Front", "alsoOn": "Second", "with": ["Length"]},
    ("td_lines", "align_h by two points of the part"): {"rotation": 36.565, "turned": 26.565},
    ("td_lines", "style"): {"styled": ["Edge0", "Edge4"], "style": "dashed", "weight": 0.5},
    ("td_lines", "shorten"): {"shortened": [0], "by": 1.0},
    ("td_lines", "erase some, and tags"): {"erased": [0, 2, 7], "left": 1},
    ("td_lines", "shorten to nothing"): ["refused", "invalid_input", "item 1 is 1.00 mm long: it cannot shorten by 0.5 at each end."],
    ("cam_path", "area of two, named, with props"): {"object": "Sections", "kind": "area", "wires": 2, "area": 24.691, "job": None, "commands": None},
    ("cam_path", "area with no faces"): {"object": "Area", "wires": 1, "area": None},
    ("cam_path", "from_shape in a job"): {"object": "PathShape", "kind": "from_shape", "job": "Job", "commands": 7, "first": ["G0 Z25", "G0 X0 Y0", "G1 Z-1", "G1 X10 Y0", "G1 X10 Y10", "G1 X0 Y10"]},
    ("cam_path", "compound"): {"object": "Both", "kind": "compound", "job": "Job", "commands": 4},
    ("cam_path", "fixture in small letters"): {"object": "Second vice", "kind": "fixture"},
    ("cam_path", "fixture it has not"): ["refused", "invalid_input", "fixture 'G99': one of G53, G54, G55, G56, G57, G58, G59, G59.1."],
    ("cam_path", "array with a count in parts"): ["refused", "invalid_input", "props.Copies = 2.5: type must be int"],
    ("cam_path", "compound with two that are no paths"): ["refused", "invalid_input", "ops: Sketch, Plate are not CAM paths (cam_list lists a job's operations)."],
    ("cam_property_bag", "three properties, named"): {"bag": "Shop values", "name": "Shop_values", "properties": ["Depth", "Passes", "Spare"], "use": "In an operation's expression it is Shop_values.<property>."},
    ("cam_property_bag", "a value that does not fit"): ["refused", "invalid_input", "properties.Passes.value 2.5 does not fit a Integer: type must be int"],
    ("cam_template_export", "into the output folder"): {"template": "<out>/job_Job.json", "bytes": 247, "tools": 1},
    ("draft_fix", "flip one with no normal"): {"dimension": "Flat", "normal": [0.0, 0.0, -1.0]},
    ("draft_fix", "heal one named, rebuilt"): {"healed": ["Old wire"], "rebuilt": 1, "removed": 1, "now": ["Old wire"]},
    ("draft_fix", "heal named, none rebuilt"): {"rebuilt": 0, "note": "None of them is a kind Draft can rebuild (dimension, rectangle, wire, B-spline, circle, polygon)."},
    ("asm_rigid_group", "two parts, named"): {"joint": "Welded", "parts": ["Base", "Arm"]},
    ("asm_rigid_group", "on FreeCAD 1.1"): ["refused", "unavailable", "Rigid groups came in FreeCAD 1.2; this is 1.1.3. asm_joint kind fixed between each pair does the same."],
    ("asm_new_part", "named and placed"): {"part": "Bracket", "body": "Bracket body", "inAssembly": "Bracket 2"},
    ("scad_status", "no OpenSCAD"): {"openscad": None, "csgParser": True, "version": None,
                                     "note": "OpenSCAD is not installed: .csg import (not a file's hull, minkowski or text), CSG export and hull work; .scad files, scad_code and Minkowski need it."},
    ("scad_status", "it does not answer"): {"version": "unknown (it gave no answer to -v in 20 s)", "csgParser": True},
    ("scad_status", "it will not run"): {"version": "unknown (Exec format error)"},
    ("scad_status", "no parser"): {"csgParser": False, "warning": "The CSG parser (ply) is missing from FreeCAD's Python: CSG import will not run."},
    ("scad_import", "a csg file, relative, in the window"): {"path": "<out>/rel.csg", "objects": 3, "top": ["difference"], "step": 1},
    ("scad_import", "a csg file with a mesh beside"): {"objects": 4, "top": ["difference", "hull"]},
    ("scad_import", "a csg with hull, no OpenSCAD"): ["refused", "unavailable", "hulled.csg uses hull, minkowski, text, which FreeCAD works out through the OpenSCAD program, not found on this computer: the person installs it "
                                                      "(openscad.org) or sets its path in FreeCAD's OpenSCAD preferences. Nothing was read. scad_op { op: \"hull\" } makes a hull of bodies without it."],
    ("scad_import", "no reader in this FreeCAD"): ["refused", "unavailable", "FreeCAD's CSG importer is not loadable here (No module named 'importCSG'): scad_status says whether its parser (ply) is in FreeCAD's Python."],
    ("scad_code", "code, a name taken, in the window"): {"top": ["Knob 2"], "objects": 3},
    ("scad_code", "code with two tops, named"): {"top": ["difference", "hull"], "objects": 4},
    ("scad_export", "one by a word, as scad, with polyhedra"): {"objects": ["Pin"], "path": "<out>/pin.scad", "bytes": 73, "lines": 4,
                                                                "note": "2 object(s) went out as polyhedra (triangles): OpenSCAD has no equivalent for those features."},
    ("scad_export", "the one body"): {"objects": ["Block"], "path": "<out>/Block.csg", "note": None},
    ("scad_op", "hull here"): {"object": "Hull", "op": "hull", "of": ["Block", "Pin"], "made": "here (OpenSCAD not installed): the hull of the bodies' points", "step": 1},
    ("scad_op", "a flat result"): {"made": "OpenSCAD", "volume": None, "faces": 5},
    ("scad_op", "minkowski through OpenSCAD, named"): {"object": "Rounded", "op": "minkowski", "volume": 1500.0},
}


def cases(file, fc, tmp):
    out = []

    def C(tool, case, args, prep=None, **flags):
        def prepare(s):
            fc.state["flags"].update(flags)
            if prep is not None:
                prep(s)

        out.append((tool, case, prepare, args))

    {"techdraw": techdraw, "cam_more": cam_more, "openscad": openscad}[file](fc, tmp, C)
    return out


def techdraw(fc, tmp, C):
    svg = os.path.join(tmp, "mark.svg")
    with open(svg, "w", encoding="utf-8") as f:
        f.write("<svg><circle r='2'/></svg>")
    LINE = {"pts": [[0.0, 0.0], [10.0, 0.0]], "style": "thin"}
    RING = {"pts": [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]], "style": "thin", "closed": True}

    def body(s):
        s.box()

    def drawing(s, **kw):
        b = s.box()
        p = s.page()
        return p, s.view(p, "Front", body=b, **kw)

    def full(s):
        p, v = drawing(s)
        s.dim(v, ["Edge0"], "Length")
        s.dim(v, ["Edge4"], "Bore", "Diameter")
        s.symbol(p, {"kind": "frame", "rows": [{"characteristic": "flatness", "tolerance": 0.05}], "on": "Edge0"}, "Frame")
        s.symbol(p, {"kind": "datum", "letter": "A", "on": "Edge1"}, "Datum")
        s.symbol(p, {"kind": "finish", "ra": 1.6, "lay": "=", "text": "", "on": "Edge2"}, "Finish")
        s.symbol(p, {"kind": "odd"}, "Odd")
        n = s.doc.new("TechDraw::DrawViewAnnotation", "Note")
        p.__dict__["Views"] = p.Views + [n]
        s.group(p, s.doc.getObject("Box"))
        return p, v

    def lined(s):
        p, v = drawing(s)
        s.cosmetic(v, [dict(LINE, tags=["ce1"]), dict(LINE, pts=[[0.0, 0.0], [0.0, 1.0]]), dict(RING)])
        s.centerline(v, "cl1")
        return p, v

    def two_pages(s):
        p, v = drawing(s, LockPosition=False)
        s.dim(v, ["Edge0"], "Length")
        s.page("Second")
        s.clip(p)
        s.doc.new("Part::Feature", "Sketch").__dict__["Label"] = "Break lines"
        return p, v

    def stacked(s):
        p, v = two_pages(s)
        s.provider(v, 3)
        w = s.view(p, "Side", body=s.doc.getObject("Box"))
        s.provider(w, 7)
        s.view(p, "Plain", body=s.doc.getObject("Box"))

    def grouped(s):
        b = s.box()
        p = s.page()
        s.group(p, b)
        s.page("Second")

    def clipped(s):
        p, v = two_pages(s)
        c = s.doc.getObject("Clip")
        c.__dict__["Views"] = [v]

    def shared(s):
        p, v = two_pages(s)
        v.InList.append(s.doc.getObject("Dimension"))

    def replacing(s):
        p, v = lined(s)
        v.__dict__["replaceCenterLine"] = lambda cl: fc.trace.append(f"replaceCenterLine({cl.tag})")

    # ---- td_list
    C("td_list", "a page with everything", {"page": "Drawing"}, full)
    C("td_list", "the only page", {}, drawing)
    C("td_list", "views just opened, worked out", {"page": "Drawing"}, full, late_edges=True)
    C("td_list", "views that stay without lines", {"page": "Drawing"}, full, no_edges=True)
    C("td_list", "no such page", {"page": "Nowhere"}, drawing)
    C("td_list", "no page at all", {}, body)
    # ---- td_export
    C("td_export", "every format", {"page": "Drawing"}, full)
    C("td_export", "svg, named", {"formats": ["svg"], "name": "plate drawing"}, lined)
    C("td_export", "a format it has not", {"formats": ["svg", "png"]}, drawing)
    C("td_export", "TechDraw's DXF writer stops", {"formats": ["dxf"]}, drawing, dxf="raises")
    C("td_export", "TechDraw's DXF writer writes nothing", {"formats": ["dxf", "pdf"]}, drawing, dxf="nothing")
    C("td_export", "TechDraw's DXF comes out empty", {"formats": ["dxf"]}, drawing, dxf="empty")
    C("td_export", "views without lines yet", {"formats": ["svg"]}, full, late_edges=True)
    C("td_export", "no such page", {"page": "Nowhere"}, drawing)
    # ---- td_cosmetic
    V = {"view": "Front"}
    C("td_cosmetic", "a line", {**V, "items": [{"kind": "line", "from": [0, 0, 0], "to": [40, 0, 20]}]}, drawing)
    C("td_cosmetic", "a line, visible, on a scaled view", {**V, "items": [{"kind": "line", "from": [0, 0, 0], "to": [40, 0, 0], "style": "visible"}]}, lambda s: drawing(s, Scale=2.0))
    C("td_cosmetic", "a circle", {**V, "items": [{"kind": "circle", "center": [20, 0, 10], "radius": 4}]}, drawing)
    C("td_cosmetic", "a circle, an older format", {**V, "items": [{"kind": "circle", "center": [20, 0, 10], "radius": 4, "style": "hidden"}]}, drawing, format_dict=True)
    C("td_cosmetic", "a circle of no radius", {**V, "items": [{"kind": "circle", "center": [20, 0, 10]}]}, drawing)
    C("td_cosmetic", "a centerline", {**V, "items": [{"kind": "centerline", "edges": ["Edge0", "Edge2"]}]}, drawing)
    C("td_cosmetic", "a centerline, extended", {**V, "items": [{"kind": "centerline", "edges": ["Edge1", "Edge3"], "extend": 5.5}]}, drawing)
    C("td_cosmetic", "a centerline of one edge", {**V, "items": [{"kind": "centerline", "edges": ["Edge0"]}]}, drawing)
    C("td_cosmetic", "a centerline of a vertex", {**V, "items": [{"kind": "centerline", "edges": ["Edge0", "Vertex1"]}]}, drawing)
    C("td_cosmetic", "a centerline of an edge it has not", {**V, "items": [{"kind": "centerline", "edges": ["Edge0", "Edge9"]}]}, drawing)
    C("td_cosmetic", "a thread, end on", {**V, "items": [{"kind": "thread", "circle": "Edge4"}]}, drawing)
    C("td_cosmetic", "a tapped hole, end on, pitch given", {**V, "items": [{"kind": "thread", "circle": "Edge4", "internal": True, "pitch": 1.25}]}, drawing)
    C("td_cosmetic", "a thread, end on, by size", {**V, "items": [{"kind": "thread", "edges": [{"circle": {"diameter": 10}}]}]}, drawing)
    C("td_cosmetic", "a thread on a straight edge", {**V, "items": [{"kind": "thread", "circle": "Edge0"}]}, drawing)
    C("td_cosmetic", "a thread on a vertex", {**V, "items": [{"kind": "thread", "circle": "Vertex0"}]}, drawing)
    C("td_cosmetic", "a thread, side view", {**V, "items": [{"kind": "thread", "edges": ["Edge0", "Edge2"]}]}, drawing)
    C("td_cosmetic", "a tapped hole, side view, its length", {**V, "items": [{"kind": "thread", "edges": ["Edge2", "Edge0"], "internal": True, "length": 12, "pitch": 2}]}, lambda s: drawing(s, Scale=2.0))
    C("td_cosmetic", "a thread of three edges", {**V, "items": [{"kind": "thread", "edges": ["Edge0", "Edge1", "Edge2"]}]}, drawing)
    C("td_cosmetic", "a thread of nothing", {**V, "items": [{"kind": "thread"}]}, drawing)
    C("td_cosmetic", "a kind it has not", {**V, "items": [{"kind": "arc"}]}, drawing)
    C("td_cosmetic", "a style it has not", {**V, "items": [{"kind": "line", "from": [0, 0, 0], "to": [1, 0, 0], "style": "bold"}]}, drawing)
    C("td_cosmetic", "the second of two refused", {**V, "items": [{"kind": "circle", "center": [20, 0, 10], "radius": 4}, {"kind": "circle", "center": [20, 0, 10], "radius": -1}]}, drawing)
    C("td_cosmetic", "three more beside the earlier ones", {**V, "items": [{"kind": "line", "from": [0, 0, 0], "to": [40, 0, 20]}, {"kind": "centerline", "edges": ["Edge0", "Edge2"]},
                                                              {"kind": "thread", "circle": "Edge4"}]}, lined)
    C("td_cosmetic", "the earlier ones cleared", {**V, "clear": True, "items": [{"kind": "circle", "center": [20, 0, 10], "radius": 2}]}, lined)
    C("td_cosmetic", "cleared, nothing new", {**V, "clear": True}, lined)
    C("td_cosmetic", "nothing asked", dict(V), drawing)
    C("td_cosmetic", "a FreeCAD before 1.1", {**V, "items": [{"kind": "line", "from": [0, 0, 0], "to": [40, 0, 20]}]}, drawing, version=["1", "0", "2"])
    C("td_cosmetic", "a FreeCAD that makes no cosmetic lines", {**V, "items": [{"kind": "line", "from": [0, 0, 0], "to": [40, 0, 20]}]}, drawing, no_cosmetic=True)
    C("td_cosmetic", "a view whose lines come late", {**V, "items": [{"kind": "centerline", "edges": ["Edge0", "Edge2"]}]}, drawing, late_edges=True)
    C("td_cosmetic", "a view with no lines", {**V, "items": [{"kind": "line", "from": [0, 0, 0], "to": [40, 0, 20]}]}, drawing, no_edges=True)
    C("td_cosmetic", "a point that is no point", {**V, "items": [{"kind": "line", "from": [0, 0], "to": [40, 0, 20]}]}, drawing)
    C("td_cosmetic", "no such view", {"view": "Back", "items": []}, drawing)
    C("td_cosmetic", "crash: an item that is a word", {**V, "items": ["line"]}, drawing)
    # ---- td_view_more
    C("td_view_more", "broken", {"kind": "broken", "view": "Front", "breaks": ["Break lines"], "gap": 4, "at": [150, 60]}, two_pages)
    C("td_view_more", "broken, placed below", {"kind": "broken", "view": "Front", "breaks": ["Sketch"]}, two_pages)
    C("td_view_more", "broken with no breaks", {"kind": "broken", "view": "Front"}, two_pages)
    C("td_view_more", "broken by an object that is not here", {"kind": "broken", "view": "Front", "breaks": ["Missing"]}, two_pages)
    C("td_view_more", "broken, no such view", {"kind": "broken", "view": "Back", "breaks": ["Sketch"]}, two_pages)
    C("td_view_more", "lock", {"kind": "lock", "view": "Front"}, two_pages)
    C("td_view_more", "unlock", {"kind": "lock", "view": "Front", "locked": False}, two_pages)
    C("td_view_more", "lock on a FreeCAD without it", {"kind": "lock", "view": "Front"}, drawing)
    C("td_view_more", "lock, no such view", {"kind": "lock", "view": "Back"}, drawing)
    for to in ("top", "bottom", "up", "down"):
        C("td_view_more", f"stack {to}", {"kind": "stack", "view": "Front", "to": to}, stacked)
    C("td_view_more", "stack, the default", {"kind": "stack", "view": "Side"}, stacked)
    C("td_view_more", "stack sideways", {"kind": "stack", "view": "Front", "to": "left"}, stacked)
    C("td_view_more", "stack with no window", {"kind": "stack", "view": "Front", "to": "top"}, two_pages)
    C("td_view_more", "move", {"kind": "move", "view": "Front", "page": "Second"}, two_pages)
    C("td_view_more", "move to where it is", {"kind": "move", "view": "Front", "page": "Drawing"}, two_pages)
    C("td_view_more", "move a group's item", {"kind": "move", "view": "Top", "page": "Second"}, grouped)
    C("td_view_more", "move to no such page", {"kind": "move", "view": "Front", "page": "Third"}, two_pages)
    C("td_view_more", "draft", {"kind": "draft", "page": "Drawing", "object": "Break lines", "direction": [0, 0, 1], "name": "Plan", "at": [50, 50]}, two_pages)
    C("td_view_more", "draft, a name taken", {"kind": "draft", "page": "Drawing", "object": "Sketch", "name": "Front"}, two_pages)
    C("td_view_more", "draft of nothing", {"kind": "draft", "page": "Drawing"}, two_pages)
    C("td_view_more", "clip", {"kind": "clip", "page": "Second"}, two_pages)
    C("td_view_more", "clip, sized, no frame", {"kind": "clip", "page": "Drawing", "width": 80, "height": 30, "frame": False, "at": [10, 10]}, two_pages)
    C("td_view_more", "clip off the paper", {"kind": "clip", "page": "Drawing", "at": [500, 10]}, two_pages)
    C("td_view_more", "crash: clip of a width in words", {"kind": "clip", "page": "Drawing", "width": "wide"}, two_pages)
    C("td_view_more", "clip_add", {"kind": "clip_add", "page": "Drawing", "clip": "Window", "view": "Front"}, two_pages)
    C("td_view_more", "clip_remove", {"kind": "clip_remove", "page": "Drawing", "clip": "Window", "view": "Front"}, clipped)
    C("td_view_more", "clip_add to what is no clip", {"kind": "clip_add", "page": "Drawing", "clip": "Front", "view": "Front"}, two_pages)
    C("td_view_more", "image", {"kind": "image", "page": "Drawing", "path": svg, "width": 30}, two_pages)
    C("td_view_more", "image not there", {"kind": "image", "page": "Drawing", "path": os.path.join(tmp, "none.png")}, two_pages)
    C("td_view_more", "image with no path", {"kind": "image", "page": "Drawing"}, two_pages)
    C("td_view_more", "symbol", {"kind": "symbol", "page": "Drawing", "path": svg, "scale": 2}, two_pages)
    C("td_view_more", "symbol, plain", {"kind": "symbol", "page": "Drawing", "path": svg}, two_pages)
    C("td_view_more", "symbol not there", {"kind": "symbol", "page": "Drawing", "path": os.path.join(tmp, "none.svg")}, two_pages)
    # A relative path is looked for in the session's folder (tests/test_datatd2_data.py: the meant differences from the handlers).

    def with_file(name):
        def prep(s):
            two_pages(s)
            with open(os.path.join(s.out_dir, name), "w", encoding="utf-8") as f:
                f.write("<svg><circle r='3'/></svg>")

        return prep

    C("td_view_more", "symbol, a bare name in the session's folder", {"kind": "symbol", "page": "Drawing", "path": "rel-mark.svg"}, with_file("rel-mark.svg"))
    C("td_view_more", "image, a bare name in the session's folder", {"kind": "image", "page": "Drawing", "path": "rel-mark.svg", "width": 30}, with_file("rel-mark.svg"))
    C("td_view_more", "symbol, a bare name that is not there", {"kind": "symbol", "page": "Drawing", "path": "rel-none.svg"}, two_pages)
    C("td_view_more", "image, a bare name that is not there", {"kind": "image", "page": "Drawing", "path": "rel-none.png"}, two_pages)
    C("td_view_more", "share", {"kind": "share", "page": "Second", "view": "Front"}, two_pages)
    C("td_view_more", "share with its dimensions", {"kind": "share", "page": "Second", "view": "Front"}, shared)
    C("td_view_more", "share what is no view", {"kind": "share", "page": "Second", "view": "Box"}, two_pages)
    C("td_view_more", "a kind it has not", {"kind": "exploded", "page": "Drawing"}, two_pages)
    C("td_view_more", "no kind", {"page": "Drawing"}, two_pages)
    C("td_view_more", "no such page", {"kind": "clip", "page": "Third"}, two_pages)
    # ---- td_lines
    C("td_lines", "align_h by an edge", {**V, "action": "align_h", "refs": ["Edge1"]}, drawing)
    C("td_lines", "align_v by two points", {**V, "action": "align_v", "refs": ["Vertex0", "Vertex2"]}, drawing)
    C("td_lines", "align_h by two points of the part", {**V, "action": "align_h", "refs": [{"point": [0, 0, 0]}, {"point": [40, 0, 20]}]}, lambda s: drawing(s, Rotation=10.0))
    C("td_lines", "align by nothing", {**V, "action": "align_h"}, drawing)
    C("td_lines", "align by three", {**V, "action": "align_v", "refs": ["Vertex0", "Vertex1", "Vertex2"]}, drawing)
    C("td_lines", "align by one point", {**V, "action": "align_v", "refs": ["Vertex0"]}, drawing)
    C("td_lines", "crash: align by two edges", {**V, "action": "align_v", "refs": ["Edge0", "Edge1"]}, drawing)
    C("td_lines", "style", {**V, "action": "style", "refs": ["Edge0", "Edge4"], "style": "dashed", "weight": 0.5, "color": "#ff0000"}, drawing)
    C("td_lines", "style, the defaults, again", {**V, "action": "style", "refs": ["Edge1"]}, lambda s: drawing(s, AgentLinkEdgeStyles='{"Edge0": {"style": "dotted", "weight": 0.2, "color": "#000000"}}'))
    C("td_lines", "style none before 1.1", {**V, "action": "style", "refs": ["Edge1"], "style": "none"}, drawing, version=["1", "0", "2"])
    C("td_lines", "a style it has not", {**V, "action": "style", "refs": ["Edge1"], "style": "wavy"}, drawing)
    C("td_lines", "style of a point", {**V, "action": "style", "refs": ["Edge1", "Vertex1"]}, drawing)
    C("td_lines", "style of nothing", {**V, "action": "style"}, drawing)
    C("td_lines", "extend all", {**V, "action": "extend"}, lined)
    C("td_lines", "extend one by 5", {**V, "action": "extend", "items": [1], "by": 5}, lined)
    C("td_lines", "shorten", {**V, "action": "shorten", "items": [0, 2], "by": 1}, lined)
    C("td_lines", "shorten to nothing", {**V, "action": "shorten", "items": [0, 1], "by": 0.5}, lined)
    C("td_lines", "extend one it has not", {**V, "action": "extend", "items": [3]}, lined)
    C("td_lines", "extend where there are none", {**V, "action": "extend", "items": [0]}, drawing)
    C("td_lines", "extend a centerline of FreeCAD's", {**V, "action": "extend", "items": [], "centerlines": ["cl1"], "by": 1.5}, lined)
    C("td_lines", "shorten a centerline on a FreeCAD that puts it back", {**V, "action": "shorten", "items": [], "centerlines": ["cl1"]}, replacing)
    C("td_lines", "shorten a centerline it has not", {**V, "action": "shorten", "items": [], "centerlines": ["cl9"]}, lined)
    C("td_lines", "erase all", {**V, "action": "erase"}, lined)
    C("td_lines", "erase some, and tags", {**V, "action": "erase", "items": [2, 0, 7, 0], "tags": ["ce1", "cl1", "cv4", "zz"]}, lined)
    C("td_lines", "erase where there are none", {**V, "action": "erase"}, drawing)
    C("td_lines", "an action it has not", {**V, "action": "bend"}, lined)
    C("td_lines", "no such view", {"view": "Back", "action": "erase"}, drawing)
    C("td_lines", "a view whose lines come late", {**V, "action": "align_h", "refs": ["Edge1"]}, drawing, late_edges=True)


def cam_more(fc, tmp, C):
    def shop(s):
        job = s.job()
        s.op(job, "profile", "Outline")
        s.op(job, "pocket", "Pocket")
        s.block("Plate", (0, 0, 0), (30, 30, 2))
        s.plain("Loose", Path=fc.moves(3))
        s.plain("Sketch", Shape=fc.BoxShape((0, 0, 0), (5, 5, 0)))
        s.plain("Empty", Shape=fc.BoxShape((0, 0, 0), (0, 0, 0)))
        return job

    def bare(s):
        s.block()

    def no(*mods):
        def prep(s):
            shop(s)
            fc.gone(*mods)

        return prep

    def drafts(s):
        s.dimension("Width")
        s.dimension("Flat", (0, 0, 0))
        s.plain("Old wire")
        s.plain("Old circle")

    def asm(s):
        s.assembly()
        s.block("Stray")

    NO_CAM = {"missing": ("Path",)}
    # ---- cam_path
    C("cam_path", "area of two, named, with props", {"kind": "area", "sources": ["Plate", "Sketch"], "name": "Sections", "props": {"Offset": 2.0, "PocketMode": "ZigZag"}}, shop)
    C("cam_path", "area on a workplane, a job named", {"kind": "area", "sources": ["Plate"], "workplane": "Plate.Face3", "job": "Job"}, shop)
    C("cam_path", "area with no faces", {"kind": "area", "sources": ["Plate"]}, shop, area_open=True)
    C("cam_path", "area that came out empty", {"kind": "area", "sources": ["Plate"]}, shop, area_null=True)
    C("cam_path", "area on a FreeCAD whose area has no shape", {"kind": "area", "sources": ["Plate"]}, shop, area_shapeless=True)
    C("cam_path", "area of nothing", {"kind": "area"}, shop)
    C("cam_path", "area of what is not here", {"kind": "area", "sources": ["Missing"]}, shop)
    C("cam_path", "area on a whole body", {"kind": "area", "sources": ["Plate"], "workplane": "Plate"}, shop)
    C("cam_path", "area on an edge", {"kind": "area", "sources": ["Plate"], "workplane": "Plate.Edge2"}, shop)
    C("cam_path", "area on a face it has not", {"kind": "area", "sources": ["Plate"], "workplane": "Plate.Face9"}, shop)
    C("cam_path", "area with a property it has not", {"kind": "area", "sources": ["Plate"], "props": {"Offset": 1.0, "Depth": 3}}, shop)
    C("cam_path", "area with a value FreeCAD refuses", {"kind": "area", "sources": ["Plate"], "props": {"PocketMode": "Spiral"}}, shop)
    C("cam_path", "from_shape in a job", {"kind": "from_shape", "sources": ["Sketch"], "job": "Job"}, shop)
    C("cam_path", "from_shape, no job", {"kind": "from_shape", "sources": ["Sketch", "Plate"]}, shop)
    C("cam_path", "from_shape of nothing", {"kind": "from_shape", "sources": []}, shop)
    C("cam_path", "edges with the job's tool", {"kind": "edges", "sources": ["Sketch"], "job": "Job", "name": "Trace"}, shop)
    C("cam_path", "edges with no job", {"kind": "edges", "sources": ["Sketch"]}, shop)
    C("cam_path", "edges on a FreeCAD without the command", {"kind": "edges", "sources": ["Sketch"], "job": "Job"}, no("Path.Op.Gui.PathShape"))
    C("cam_path", "compound", {"kind": "compound", "ops": ["Outline", "Pocket"], "job": "Job", "name": "Both"}, shop)
    C("cam_path", "compound of nothing", {"kind": "compound"}, shop)
    C("cam_path", "compound with one that is no path", {"kind": "compound", "ops": ["Outline", "Plate"]}, shop)
    C("cam_path", "compound with two that are no paths", {"kind": "compound", "ops": ["Sketch", "Plate"]}, shop)
    C("cam_path", "compound of what is not here", {"kind": "compound", "ops": ["Missing"]}, shop)
    C("cam_path", "array", {"kind": "array", "ops": ["Outline"], "job": "Job", "props": {"Type": "Polar", "Copies": 3}}, shop)
    C("cam_path", "array of nothing", {"kind": "array", "ops": []}, shop)
    C("cam_path", "array of a path with no tool", {"kind": "array", "ops": ["Loose"]}, shop)
    C("cam_path", "array with a count in parts", {"kind": "array", "ops": ["Outline"], "props": {"Copies": 2.5}}, shop)
    C("cam_path", "crash: array on a FreeCAD without it", {"kind": "array", "ops": ["Outline"]}, no("Path.Op.Gui.Array"))
    C("cam_path", "stop, optional", {"kind": "stop", "job": "Job"}, shop)
    C("cam_path", "stop, mandatory, named", {"kind": "stop", "mandatory": True, "name": "Turn the part"}, shop)
    C("cam_path", "fixture, the default", {"kind": "fixture", "job": "Job"}, shop)
    C("cam_path", "fixture in small letters", {"kind": "fixture", "fixture": "g55", "name": "Second vice"}, shop)
    C("cam_path", "fixture it has not", {"kind": "fixture", "fixture": "G99", "job": "Job"}, shop)
    C("cam_path", "a kind it has not", {"kind": "spiral"}, shop)
    C("cam_path", "no kind", {}, shop)
    C("cam_path", "a job that is not here", {"kind": "stop", "job": "Other"}, shop)
    C("cam_path", "a name taken", {"kind": "stop", "name": "Outline"}, shop)
    C("cam_path", "no CAM here", {"kind": "stop"}, shop, **NO_CAM)
    # ---- cam_property_bag
    BAG = [{"name": "Depth", "type": "Length", "value": 4.5, "group": "Cut", "info": "how deep"}, {"name": "Passes", "type": "Integer", "value": 3}, {"name": "Spare"}]
    C("cam_property_bag", "three properties, named", {"name": "Shop values", "properties": BAG}, shop)
    C("cam_property_bag", "empty", {}, shop)
    C("cam_property_bag", "a name taken", {"name": "Plate", "properties": [{"name": "A", "type": "Bool", "value": True}]}, shop)
    C("cam_property_bag", "a name with a space", {"properties": [{"name": "cut depth"}]}, shop)
    C("cam_property_bag", "a property with no name", {"properties": [{"type": "Float"}]}, shop)
    C("cam_property_bag", "a property that is a word", {"properties": ["Depth"]}, shop)
    C("cam_property_bag", "a type it has not", {"properties": [{"name": "Depth"}, {"name": "Tilt", "type": "Vector"}]}, shop)
    C("cam_property_bag", "a name twice", {"properties": [{"name": "Depth"}, {"name": "Depth", "type": "Length"}]}, shop)
    C("cam_property_bag", "a value that does not fit", {"properties": [{"name": "Passes", "type": "Integer", "value": 2.5}]}, shop)
    C("cam_property_bag", "no CAM here", {"properties": BAG}, shop, **NO_CAM)
    # ---- cam_template_export
    C("cam_template_export", "into the output folder", {}, shop)
    C("cam_template_export", "described, to a path", {"job": "Job", "description": "The plate job", "path": os.path.join(tmp, "made", "plate")}, shop)
    C("cam_template_export", "a path already named so", {"path": os.path.join(tmp, "job_plate.json")}, shop)
    C("cam_template_export", "a job that is not here", {"job": "Other"}, shop)
    C("cam_template_export", "no job", {}, bare)
    C("cam_template_export", "no CAM here", {}, shop, **NO_CAM)
    # ---- draft_fix
    C("draft_fix", "flip", {"action": "flip_dimension", "dimension": "Width"}, drafts)
    C("draft_fix", "flip one with no normal", {"action": "flip_dimension", "dimension": "Flat"}, drafts)
    C("draft_fix", "flip what is no dimension", {"action": "flip_dimension", "dimension": "Old wire"}, drafts)
    C("draft_fix", "flip what is not here", {"action": "flip_dimension", "dimension": "Height"}, drafts)
    C("draft_fix", "flip nothing", {"action": "flip_dimension"}, drafts)
    C("draft_fix", "heal all, nothing to do", {"action": "heal"}, drafts)
    C("draft_fix", "heal all, two rebuilt", {"action": "heal"}, drafts, heals=("Old wire", "Old circle"))
    C("draft_fix", "heal one named, rebuilt", {"action": "heal", "objects": ["Old wire"]}, drafts, heals=("Old wire",))
    C("draft_fix", "heal named, none rebuilt", {"action": "heal", "objects": ["Width", "Old wire"]}, drafts)
    C("draft_fix", "heal what is not here", {"action": "heal", "objects": ["Old wire", "Missing"]}, drafts)
    C("draft_fix", "crash: heal on a FreeCAD without Draft", {"action": "heal"}, drafts, missing=("Draft",))
    C("draft_fix", "an action it has not", {"action": "mend"}, drafts)
    # ---- asm_rigid_group
    C("asm_rigid_group", "two parts, named", {"parts": ["Base", "Arm"], "name": "Welded"}, asm, rigid=True)
    C("asm_rigid_group", "by the assembly's name, a second group", {"assembly": "Assembly", "parts": ["arm", "Base"]}, asm, rigid=True)
    C("asm_rigid_group", "on FreeCAD 1.1", {"parts": ["Base", "Arm"]}, asm)
    C("asm_rigid_group", "one part", {"parts": ["Base"]}, asm, rigid=True)
    C("asm_rigid_group", "no parts", {}, asm, rigid=True)
    C("asm_rigid_group", "a part not in it", {"parts": ["Base", "Stray"]}, asm, rigid=True)
    C("asm_rigid_group", "no assembly", {"parts": ["Base", "Arm"]}, bare, rigid=True)
    # ---- asm_new_part
    C("asm_new_part", "the default", {}, asm)
    C("asm_new_part", "named and placed", {"name": "Bracket", "at": [10, 0, 5], "axis": [0, 0, 1], "angle": 90}, asm)
    C("asm_new_part", "a name taken", {"assembly": "Assembly", "name": "Base"}, asm)
    C("asm_new_part", "placed nowhere a point", {"name": "Bracket", "at": [1]}, asm)
    C("asm_new_part", "an assembly that is not here", {"assembly": "Other"}, asm)
    C("asm_new_part", "no assembly", {}, bare)


def openscad(fc, tmp, C):
    prog = os.path.join(tmp, "openscad")
    files = {"plain.csg": "difference() { cube(10); sphere(6); }\n", "hulled.csg": "// hull( of nothing\nhull() { cube(1); }\nminkowski() { cube(1); sphere(1); }\ntext(\"hull(\");\n",
             "lettered.csg": "text(\"A\");\n", "model.scad": "cube(10);\n", "mesh.stl": "solid\n", "bare": "cube(1);\n", prog: ""}
    for name, text in files.items():
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
            f.write(text)
    HAVE = {"openscad": prog}

    def at(name):
        return os.path.join(tmp, name)

    def bodies(s):
        fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10), 1000.0))
        fc.body("Pin", fc.solid("pin", (20, 0, 0), (22, 2, 30), 120.0), Visibility=False)
        fc.body("Note", None, type_="App::Annotation")
        fc.body("Hollow", fc.Shape("nothing", "Compound", null=True, solids=0))

    def one(s):
        fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10), 1000.0))

    def none(s):
        pass

    def window(s):
        one(s)
        fc.fc.GuiUp = True

    def taken(s):
        one(s)
        fc.body("Knob", fc.solid("knob", (0, 0, 0), (1, 1, 1), 1.0), Visibility=False)

    # ---- scad_status
    C("scad_status", "no OpenSCAD", {}, none)
    C("scad_status", "OpenSCAD here", {}, none, **HAVE)
    C("scad_status", "its version on the other stream", {}, none, version="stdout", **HAVE)
    C("scad_status", "it says nothing", {}, none, version="silent", **HAVE)
    C("scad_status", "it does not answer", {}, none, version="timeout", **HAVE)
    C("scad_status", "it will not run", {}, none, version="raises", **HAVE)
    C("scad_status", "no parser", {}, none, missing=("ply",))
    # ---- scad_import
    C("scad_import", "a csg file", {"path": at("plain.csg")}, one)
    C("scad_import", "a csg file, relative, in the window", {"path": "rel.csg"}, lambda s: (window(s), open(os.path.join(s.out_dir, "rel.csg"), "w").close()), views=True)
    C("scad_import", "a csg file with a mesh beside", {"path": at("plain.csg")}, one, csg="two")
    C("scad_import", "a scad file, OpenSCAD here", {"path": at("model.scad")}, one, **HAVE)
    C("scad_import", "a scad file, no OpenSCAD", {"path": at("model.scad")}, one)
    C("scad_import", "a csg with hull, no OpenSCAD", {"path": at("hulled.csg")}, one)
    C("scad_import", "a csg with text, no OpenSCAD", {"path": at("lettered.csg")}, one)
    C("scad_import", "a csg with hull, OpenSCAD here", {"path": at("hulled.csg")}, one, **HAVE)
    C("scad_import", "no path", {}, one)
    C("scad_import", "a path of spaces", {"path": "  "}, one)
    C("scad_import", "a file not there", {"path": at("gone.csg")}, one)
    C("scad_import", "an STL", {"path": at("mesh.stl")}, one)
    C("scad_import", "a file with no extension", {"path": at("bare")}, one)
    C("scad_import", "no reader in this FreeCAD", {"path": at("plain.csg")}, one, missing=("importCSG",))
    C("scad_import", "the reader stops", {"path": at("plain.csg")}, one, csg="raises")
    C("scad_import", "the reader stops without a word", {"path": at("plain.csg")}, one, csg="silent")
    C("scad_import", "nothing comes in", {"path": at("plain.csg")}, one, csg="nothing")
    # ---- scad_code
    CODE = {"code": "difference() { cube(10); sphere(6); }"}
    C("scad_code", "code, named", {**CODE, "name": "Knob"}, one, **HAVE)
    C("scad_code", "code, a name taken, in the window", {**CODE, "name": "Knob"}, lambda s: (taken(s), window(s)), views=True, **HAVE)
    C("scad_code", "code with two tops, named", {**CODE, "name": "Knob"}, one, csg="two", **HAVE)
    C("scad_code", "code, plain", dict(CODE), one, **HAVE)
    C("scad_code", "no code", {}, one, **HAVE)
    C("scad_code", "code of spaces", {"code": " \n"}, one, **HAVE)
    C("scad_code", "no OpenSCAD", dict(CODE), one)
    C("scad_code", "OpenSCAD refuses it", dict(CODE), one, code="raises", **HAVE)
    C("scad_code", "OpenSCAD makes nothing", dict(CODE), one, code="nothing", **HAVE)
    C("scad_code", "OpenSCAD's file is not there", dict(CODE), one, code="gone", **HAVE)
    C("scad_code", "the reader stops", dict(CODE), one, csg="raises", **HAVE)
    C("scad_code", "no geometry", dict(CODE), one, csg="nothing", **HAVE)
    C("scad_code", "crash: no OpenSCAD workbench", dict(CODE), one, missing=("OpenSCADUtils",), **HAVE)
    # ---- scad_export
    C("scad_export", "the one body", {}, bodies)
    C("scad_export", "two by name, to a path", {"objects": ["Block", "Pin"], "path": at(os.path.join("out", "pair"))}, bodies)
    C("scad_export", "one by a word, as scad, with polyhedra", {"objects": "Pin", "path": "pin.scad"}, bodies, polyhedra=2)
    C("scad_export", "one with no shape", {"objects": ["Block", "Note"]}, bodies)
    C("scad_export", "one with an empty shape", {"objects": ["Hollow"]}, bodies)
    C("scad_export", "one not here", {"objects": ["Missing"]}, bodies)
    C("scad_export", "no body to take", {}, none)
    C("scad_export", "a path that is no path", {"objects": ["Block"], "path": 7}, bodies)
    C("scad_export", "the exporter stops", {"objects": ["Block"]}, bodies, export="raises")
    # ---- scad_op
    C("scad_op", "hull here", {"objects": ["Block", "Pin"]}, bodies)
    C("scad_op", "hull here of one, named", {"op": "hull", "objects": "Block", "name": "Wrap"}, bodies)
    C("scad_op", "hull through OpenSCAD", {"op": "hull", "objects": ["Block", "Pin"]}, bodies, **HAVE)
    C("scad_op", "minkowski through OpenSCAD, named", {"op": "minkowski", "objects": ["Block", "Pin"], "name": "Rounded"}, bodies, **HAVE)
    C("scad_op", "a flat result", {"op": "hull", "objects": ["Block", "Pin"]}, bodies, program="flat", **HAVE)
    C("scad_op", "minkowski, no OpenSCAD", {"op": "minkowski", "objects": ["Block", "Pin"]}, bodies)
    C("scad_op", "minkowski of one", {"op": "minkowski", "objects": ["Block"]}, bodies, **HAVE)
    C("scad_op", "hull of nothing", {"objects": []}, bodies)
    C("scad_op", "an op it has not", {"op": "offset", "objects": ["Block"]}, bodies)
    C("scad_op", "an object with no shape", {"objects": ["Block", "Note"]}, bodies)
    C("scad_op", "OpenSCAD stops", {"op": "minkowski", "objects": ["Block", "Pin"]}, bodies, program="raises", **HAVE)
    C("scad_op", "OpenSCAD makes nothing", {"op": "hull", "objects": ["Block", "Pin"]}, bodies, program="nothing", **HAVE)

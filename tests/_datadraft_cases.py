# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datadraft_data.py runs through the old handler and
# the new data entry of each converted Draft tool (and the surface tools
# beside them in draft.py), on the stand-in FreeCAD
# (tests/_datapart_standin.py): its normal paths and each of its refusals.
# (The live models under private records: models are run on FreeCAD, not here:
# datadraft-findings.md lists which of their calls reach each tool.)

# The family files whose tools were converted.
FILES = ("draft",)
# Each converted tool and its group.
CONVERTED = {k: "draft" for k in ("surface_fill", "surface_loft", "surface_points", "surface_thicken", "draft_text", "draft_outline", "draft_array", "draft_fonts")}
# Each tool of those files kept as code, and why: none.
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("surface_fill", "a sketch's outline"): {"object": "Surface", "area": 120.0, "solid": False, "step": 1},
    ("surface_fill", "thickened, named"): {"object": "Lid", "solid": True, "volume": 240.0},
    ("surface_fill", "two runs"): ["refused", "invalid_input", "edges: they form 2 separate runs, not one closed boundary — give the edges of one loop (an inner loop cannot be a hole here; part_face makes a flat face with holes)."],
    ("surface_fill", "open"): ["refused", "invalid_input", "edges: they do not close into one boundary (its ends are 14.14 mm apart): add the missing edge, or snap the ends together."],
    ("surface_loft", "two curves from points"): {"object": "Surface", "curves": 2, "through": "open curves (a sheet)", "solid": False},
    ("surface_loft", "open and closed"): ["refused", "invalid_input", "curves: all open or all closed — curves [1] are closed, the rest open."],
    ("surface_points", "through a grid"): {"grid": [3, 3], "fitted": "through every point", "farthestPoint": 7.0},
    ("surface_points", "within a tolerance, thickened thin"): {"fitted": "within 0.5 mm", "solid": True,
                                                              "warnings": ["0.4 mm is under two printed lines (0.8 mm with a 0.4 mm nozzle): it may print with gaps or not at all."]},
    ("surface_thicken", "a face of a body, both ways"): {"from": "Block.Face6", "solid": True},
    ("draft_fonts", "as it comes"): {"fonts": ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "osifont.ttf"], "found": 3, "default": "DejaVuSans.ttf"},
    ("draft_text", "embossed"): {"body": "Block", "text": "AB", "mode": "emboss", "font": "DejaVuSans.ttf", "size": 6.0, "depth": 0.6, "volumeChange": 0.0, "box": {"min": [1.4, 2.0, 10.0], "max": [8.6, 8.0, 10.6]}},
    ("draft_text", "small letters cut in, off the face"): {"mode": "engrave", "warning": "The lettering runs past the face's edge: smaller size, or shorter text.",
                                                           "printNote": "Strokes about 0.24 mm wide: under a 0.4 mm nozzle's line — print letters at least 4 mm tall, or expect them to blur."},
    ("draft_outline", "a part of its own"): {"outlines": 1, "size": [40.0, 20.0], "scale": 1.0, "mode": "extrude", "body": "Outline", "volume": 480.0},
    ("draft_outline", "on a body, scaled to a width"): {"scale": 0.5, "mode": "emboss", "body": "Block"},
    ("draft_array", "a grid"): {"kind": "grid", "copies": 2, "body": "Block", "solids": 2, "volume": 2000.0, "note": "The copies do not touch: one body of 2 separate solids. separate: true makes each its own body (to print or move apart)."},
    ("draft_array", "polar, apart, separate"): {"kind": "polar", "copies": 3, "bodies": ["Block", "Block 2", "Block 3"]},
    ("draft_array", "kind wrong"): ["refused", "invalid_input", "kind: grid (count [nx, ny, nz], gap or spacing), polar (count, angle, center, axis) or path (path, count, align)."],
}
# Refusals written in the data that no case here reaches: none.
UNREACHED = []

SQ = [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]]


def cases(fc, tmp, old, new):
    mods = [old["draft"], new["draft"]]
    flag, log = fc.flag, fc.log
    FONTS = ["/fonts/DejaVuSans.ttf", "/fonts/DejaVuSans-Bold.ttf", "/fonts/osifont.ttf"]

    # Reading fonts, setting text, reading an SVG or DXF and a face's frame are draft.py's module-level
    # code, unchanged by the conversion: here they answer what a case says.
    def text_faces(text, font, size, tracking=0.0):
        log("text_faces", text, font.rsplit("/", 1)[-1], size, tracking)
        w = 0.6 * size * len(text)
        return fc.Shape(f"letters {text!r}", "Compound", (0, 0, 0), (w, size, 0), area=flag("letters_area", 50.0), faces=len(text), edges=4 * len(text), solids=0, shells=0)

    def face_frame(face, point=None):
        log("face_frame", face, point)
        if flag("curved_face"):
            from agentlink.protocol import ToolError

            raise ToolError("invalid_input", "face: lettering goes on a flat face.")
        at = point if point is not None else fc.Vec(*flag("frame_at", (5, 5, 10)))
        return fc.fc.Placement(at, fc.fc.Rotation()), fc.Vec(0, 0, 1)

    def outline_faces(path):
        log("outline_faces", path)
        return fc.Shape(f"outline of {path}", "Face", (0, 0, 0), (40, 20, 0), area=flag("art_area", 800.0), faces=2, edges=8, solids=0, shells=0), flag("open_curves", 0)

    stubs = {"fonts": lambda: list(flag("fonts", FONTS)), "text_faces": text_faces, "face_frame": face_frame, "outline_faces": outline_faces}

    def prep(*fns, **flags):
        def prepare(s):
            for m in mods:
                for k, v in stubs.items():
                    setattr(m, k, v)
            fc.fc.GuiUp = False
            fc.state["flags"].update(flags)
            for fn in fns:
                fn(s)
        return prepare

    def block(s):
        fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10)))

    def pin(s):
        fc.body("Pin", fc.solid("pin", (5, 5, 5), (15, 15, 15)))

    def sketch(s):
        fc.body("Sketch", fc.wire("sketch outline", SQ), type_="Sketcher::SketchObject", name="Sketch")

    def open_sketch(s):
        fc.body("Open", fc.wire("open line", SQ[:3], closed=False), type_="Sketcher::SketchObject", name="Open")

    def sheet(s):
        fc.body("Sheet", fc.Shape("sheet", "Face", (0, 0, 0), (10, 10, 0), area=100.0, faces=1, edges=4, solids=0, shells=0), name="Sheet")

    def dot(s):
        fc.body("Dot", fc.Shape("dot", "Compound", (0, 0, 0), (0, 0, 0), solids=0), name="Dot")

    none = prep()
    T = "surface_fill"
    yield T, "a sketch's outline", prep(sketch), {"edges": ["Sketch"]}
    yield T, "edges of a body, thickened, named", prep(block), {"edges": ["Block.Edge1", "Block.Edge2", "Block.Edge3"], "thickness": -1.5, "name": "My lid"}
    yield T, "thickened, named", prep(sketch), {"edges": ["Sketch"], "thickness": 2, "name": "Lid"}
    yield T, "a face", prep(block), {"edges": ["Block.Face1"]}
    yield T, "an object with no edges", prep(dot), {"edges": ["Dot"]}
    yield T, "no edges", none, {}
    yield T, "two runs", prep(sketch, runs=2), {"edges": ["Sketch"]}
    yield T, "open", prep(open_sketch), {"edges": ["Open"]}
    yield T, "no wire of them", prep(sketch, fail=("Wire",)), {"edges": ["Sketch"]}
    yield T, "no fill", prep(sketch, fail=("makeFilledFace",)), {"edges": ["Sketch"]}
    yield T, "empty", prep(sketch, filled_area=0), {"edges": ["Sketch"]}
    yield T, "thickness 0", prep(sketch), {"edges": ["Sketch"], "thickness": 0}
    yield T, "thickness not a number", prep(sketch), {"edges": ["Sketch"], "thickness": "thick"}
    yield T, "not thickened", prep(sketch, fail=("makeOffsetShape",)), {"edges": ["Sketch"], "thickness": 30}

    T = "surface_loft"
    line = lambda z: {"points": [[0, 0, z], [10, 0, z]]}
    arc = lambda z, closed=False: {"points": [[0, 0, z], [5, 3, z], [10, 0, z]], "closed": closed}
    yield T, "two curves from points", none, {"curves": [line(0), arc(5)]}
    yield T, "a tube back to the first, ruled, thickened both ways, named", none, {"curves": [arc(0, True), arc(5, True), arc(9, True)], "closed": True, "ruled": True, "thickness": 2, "side": "both", "name": "Duct 1"}
    yield T, "a sketch and an edge", prep(open_sketch, block), {"curves": ["Open", "Block.Edge3"], "thickness": 0.5, "side": "in"}
    yield T, "one curve", none, {"curves": [line(0)]}
    yield T, "none", none, {}
    yield T, "closed with two", none, {"curves": [line(0), line(5)], "closed": True}
    yield T, "open and closed", none, {"curves": [line(0), arc(5, True)]}
    yield T, "one point", none, {"curves": [line(0), {"points": [[0, 0, 0]]}]}
    yield T, "an object with no edges", prep(dot), {"curves": [line(0), "Dot"]}
    yield T, "edges that do not join", prep(open_sketch, fail=("Wire",)), {"curves": ["Open", "Open"]}
    yield T, "no loft", prep(loft={"all": "raise"}), {"curves": [line(0), line(5)]}
    yield T, "thickness under 0", none, {"curves": [line(0), line(5)], "thickness": -1}
    yield T, "side wrong", none, {"curves": [line(0), line(5)], "thickness": 1, "side": "up"}
    yield T, "not thickened", prep(fail=("makeOffsetShape",)), {"curves": [line(0), line(5)], "thickness": 1}
    yield T, "thickened to no solid, then made one", prep(offset="shell"), {"curves": [line(0), line(5)], "thickness": 1}
    yield T, "thickened, not valid", prep(thick_invalid=True), {"curves": [line(0), line(5)], "thickness": 1}

    T = "surface_points"
    grid = [[[x, y, 0.1 * x * y] for x in (0, 5, 10)] for y in (0, 5, 10)]
    yield T, "through a grid", none, {"rows": grid}
    yield T, "within a tolerance, thickened thin", none, {"rows": grid, "tolerance": 0.5, "thickness": 0.4, "name": "Skin"}
    yield T, "rows not a list", none, {"rows": "grid"}
    yield T, "one row", none, {"rows": grid[:1]}
    yield T, "rows of different lengths", none, {"rows": [grid[0], grid[1][:2]]}
    yield T, "rows of one point", none, {"rows": [[[0, 0, 0]], [[1, 1, 1]]]}
    yield T, "a point that is not one", none, {"rows": [grid[0], [[0, 0, 0], 5, [1, 1, 1]]]}
    yield T, "no fit", prep(fail=("surface_fit",)), {"rows": grid}
    yield T, "crash: tolerance not a number", none, {"rows": grid, "tolerance": "loose"}

    T = "surface_thicken"
    yield T, "an object", prep(sheet), {"surface": "Sheet", "thickness": 1}
    yield T, "a face of a body, both ways", prep(block), {"surface": "Block.Face6", "thickness": 2, "side": "both"}
    yield T, "a whole body's faces, named", prep(block), {"surface": "Block", "thickness": 1, "side": "in", "name": "Skin"}
    yield T, "no surface", none, {"thickness": 1}
    yield T, "no faces", prep(dot), {"surface": "Dot", "thickness": 1}
    yield T, "no thickness", prep(sheet), {"surface": "Sheet"}
    yield T, "thickness 0", prep(sheet), {"surface": "Sheet", "thickness": 0}

    T = "draft_fonts"
    yield T, "as it comes", none, {}
    yield T, "by name, with paths", none, {"name": "bold", "paths": True}
    yield T, "more than the limit", none, {"limit": 2}
    yield T, "none on this computer", prep(fonts=[]), {}

    T = "draft_text"
    yield T, "embossed", prep(block), {"text": "AB"}
    yield T, "small letters cut in, off the face", prep(block, frame_at=(50, 5, 10)), {"text": "No. 7", "size": 2, "depth": 0.3, "mode": "engrave", "tracking": 0.2, "rotate": 90, "font": "osifont", "name": "Tag"}
    yield T, "on a face by name, at a point", prep(block, pin), {"body": "Block", "text": "A", "face": "Face2", "at": [0, 5, 5]}
    yield T, "on a face by query, the nearest", prep(block, query_hits=[2, 5]), {"text": "A", "face": {"normal": "+z", "near": [0, 0, 10]}}
    yield T, "on a face by query, the largest", prep(block, query_hits=[2, 5]), {"text": "A", "face": {"area": [50, 200]}}
    yield T, "no text", prep(block), {"text": " "}
    yield T, "size 0", prep(block), {"text": "A", "size": 0}
    yield T, "depth not a number", prep(block), {"text": "A", "depth": "deep"}
    yield T, "mode wrong", prep(block), {"text": "A", "mode": "print"}
    yield T, "no such face", prep(block), {"text": "A", "face": "Face9"}
    yield T, "no face matches", prep(block, query_hits=[]), {"text": "A", "face": {"normal": "+x"}}
    yield T, "a curved face", prep(block, curved_face=True), {"text": "A"}
    yield T, "no font by that name", prep(block), {"text": "A", "font": "Comic"}
    yield T, "no fonts", prep(block, fonts=[]), {"text": "A"}
    yield T, "not joined", prep(block, fail=("fuse",)), {"text": "A"}
    yield T, "not cut", prep(block, fail=("cut",)), {"text": "A", "mode": "engrave"}
    yield T, "not a valid solid", prep(block, bool_invalid=True), {"text": "A"}
    yield T, "no body", none, {"text": "A"}

    T = "draft_outline"
    yield T, "a part of its own", none, {"path": "logo.svg"}
    yield T, "a part of its own, by height, mirrored, named, open curves left out", prep(open_curves=2), {"path": "logo.svg", "height": 10, "mirror": True, "depth": 2, "name": "My logo"}
    yield T, "on a body, scaled to a width", prep(block), {"path": "logo.dxf", "body": "Block", "width": 20}
    yield T, "cut into a body, turned, at a point, off the face, named", prep(block, frame_at=(50, 5, 10)), {"path": "logo.svg", "body": "Block", "mode": "engrave", "rotate": 45, "at": [50, 5, 10], "name": "Marked"}
    yield T, "thin strokes", prep(thin_share=0.3), {"path": "logo.svg"}
    yield T, "strokes that cannot be thinned", prep(fail=("makeOffset2D",)), {"path": "logo.svg"}
    yield T, "no path", none, {}
    yield T, "width not a number", none, {"path": "logo.svg", "width": "wide"}
    yield T, "depth 0", none, {"path": "logo.svg", "depth": 0}
    yield T, "mode wrong", none, {"path": "logo.svg", "mode": "stamp"}
    yield T, "emboss without a body", none, {"path": "logo.svg", "mode": "emboss"}
    yield T, "not joined", prep(block, fail=("fuse",)), {"path": "logo.svg", "body": "Block"}
    yield T, "not cut", prep(block, fail=("cut",)), {"path": "logo.svg", "body": "Block", "mode": "engrave"}
    yield T, "not a valid solid", prep(block, bool_invalid=True), {"path": "logo.svg", "body": "Block"}

    T = "draft_array"
    yield T, "a grid", prep(block), {}
    yield T, "a grid by spacing, three ways, named", prep(block), {"kind": "grid", "count": [2, 2, 2], "spacing": [5, 5, 5], "name": "Stack"}
    yield T, "a grid apart", prep(block, fuse_solids=3), {"count": [3], "gap": 4}
    yield T, "a grid apart, allowed", prep(block, fuse_solids=3), {"count": [3], "allowApart": True}
    yield T, "a grid of one", prep(block), {"count": [1, 1, 1]}
    yield T, "a grid with a count of 0", prep(block), {"count": [2, 0]}
    yield T, "crash: a grid's count that is a number", prep(block), {"count": 3}
    yield T, "gap not a number", prep(block), {"gap": "wide"}
    yield T, "polar", prep(block), {"kind": "polar"}
    yield T, "polar, apart, separate", prep(block), {"kind": "polar", "count": 3, "angle": 90, "center": [20, 0, 0], "axis": [0, 0, 1], "separate": True}
    yield T, "polar of one", prep(block), {"kind": "polar", "count": 1}
    yield T, "along points", prep(block), {"kind": "path", "path": {"points": [[0, 0, 0], [20, 0, 0], [40, 10, 0]]}, "count": 3}
    yield T, "along a sketch, aligned", prep(block, sketch), {"body": "Block", "kind": "path", "path": "Sketch", "count": 4, "align": True}
    yield T, "along an edge of another body", prep(block, pin), {"body": "Block", "kind": "path", "path": "Edge2", "bodyOfPath": "Pin"}
    yield T, "no path", prep(block), {"kind": "path"}
    yield T, "one along a path", prep(block), {"kind": "path", "path": {"points": [[0, 0, 0], [20, 0, 0]]}, "count": 1}
    yield T, "kind wrong", prep(block), {"kind": "spiral"}
    yield T, "not joined", prep(block, fail=("fuse",)), {}
    yield T, "joined, the refining fails", prep(block, fail=("removeSplitter",)), {}
    yield T, "no body", none, {}

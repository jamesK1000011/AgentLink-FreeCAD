# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datadraftmore_data.py runs through the old handler and
# the new data entry of each of draft_more.py's tools, on the stand-in FreeCAD
# and Draft (tests/_datadraftmore_standin.py): its normal paths and each of
# its refusals. (The live model private records: models/draftmesh-draft-model.json
# is run on FreeCAD, not here.)

# The family file whose tools were converted.
FILES = ("draft_more",)
# Each converted tool and its group.
CONVERTED = {k: "draft" for k in ("draft_plane", "draft_style", "draft_shape", "draft_dimension", "draft_label", "draft_link_array", "draft_clone", "draft_modify",
                                  "draft_layer", "draft_hatch", "draft_from_sketch", "draft_2d_view", "draft_facebinder")}
# Each tool of that file kept as code, and why: none.
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("draft_from_sketch", "one name, a block, the original deleted"): {"object": "Wire001", "type": "Wire", "step": 1},
    ("draft_from_sketch", "no edges"): ["refused", "invalid_input", "objects: Dot has no edges to turn into Draft objects — a sketch, a wire or a shape with edges."],
    ("draft_facebinder", "a skin, moved off, named"): {"object": "Gasket", "type": "Facebinder", "area": 100.0, "note": "It follows the faces; extrusion makes a skin of that thickness (a gasket, a pad on a face)."},
    ("draft_facebinder", "an edge"): ['refused', 'invalid_input', 'Block.Edge1: a face ("Body.Face6").'],
    ("draft_2d_view", "empty"): {"object": "Block 2D view", "type": "Shape2DView", "warning": "The view came out empty: nothing of the object shows from that direction, or FreeCAD could not project it (see the report view)."},
    ("draft_2d_view", "cut faces of a body"): ["refused", "invalid_input", "section: Draft draws cut faces only of a BIM section plane (bim_section makes one; give it as object), and Block is not one. For a cut through a body: part_section, or td_section on a drawing."],
    ("draft_clone", "scaled by a factor, moved, named"): {"object": "Twin", "of": "Block", "volume": 1000.0},
    ("draft_clone", "a BIM object, scaled"): ["refused", "invalid_input", "scale: Block is a BIM object, and its clone cannot be scaled — leave scale out, or draft_modify op scale with copy: true."],
    ("draft_layer", "a new one with a width and objects"): {"layer": "Walls", "made": True, "objects": ["Block", "Wire"], "note": "No window here: the layer groups the objects, but its line width and colours show only once the file is open in FreeCAD.", "step": 1},
    ("draft_layer", "a layer on a layer"): ["refused", "invalid_input", "objects: Layer is a layer itself — layers do not nest."],
    ("draft_hatch", "a pattern by name, scaled, turned, named"): {"object": "Lines", "pattern": "Square", "file": "FCPAT.pat", "length": 28.2843},
    ("draft_hatch", "no lines drawn"): {"pattern": "Diagonal4", "warning": "The hatch drew no lines (see the report view): a larger face or a smaller scale, and check the pattern file."},
    ("draft_hatch", "a pattern not in the file"): ["refused", "invalid_input", "pattern: one of Diagonal4, Square (in FCPAT.pat)."],
    ("draft_label", "two lines, at a point, named"): {"object": "Note", "text": ["a", "b"]},
    ("draft_label", "a release that left the area empty"): {"text": ["100.00 mm²"]},
    ("draft_label", "show without an object"): ['refused', 'invalid_input', 'show area: needs object ("Body", or "Body.Face6" / "Body.Edge3" for the area or length of one element); show custom takes text instead.'],
    ("draft_plane", "at a point, turned, named"): {"plane": "Top", "origin": [1.0, 2.0, 3.0], "normal": [0.0, 0.0, 1.0], "xAxis": [1.0, 0.0, 0.0], "step": 1},
    ("draft_plane", "a Draft without one"): ['refused', 'unavailable', "This FreeCAD's Draft has no working-plane proxy."],
    ("draft_plane", "another tab in front"): ['refused', 'invalid_state', "Draft stores the 3D view's camera with a working plane, and the tab in front is not a 3D view ('NoneType' object has no attribute 'getViewDirection'): bring the model's 3D view to the front in FreeCAD, then call this again. Nothing was kept."],
    ("draft_shape", "a closed B-spline, outline only, named"): {"object": "Curve", "type": "BSpline", "step": 1},
    ("draft_shape", "a rectangle, placed"): {"object": "Rectangle", "type": "Rectangle", "area": 200.0},
    ("draft_shape", "an ellipse of no minor"): ["refused", "invalid_input", "minor: the short axis, end to end, mm, over 0."],
    ("draft_shape", "made broken"): ["refused", "failed", "Draft refused it: Radius of cylinder too small — nothing was kept."],
    ("draft_link_array", "ortho along x, named, real shapes"): {"object": "Row", "count": 4, "of": "Block", "note": "Parametric: object_set changes its counts and spacing; the copies follow the original (hidden in the window while the array shows it)."},
    ("draft_link_array", "polar of one"): ["refused", "invalid_input", "count: a whole number, 2 or more."],
    ("draft_dimension", "between two vertices"): {"object": "Dimension", "measures": 12.5, "unit": "mm"},
    ("draft_dimension", "an angle through 0"): {"measures": 20.0, "unit": "deg"},
    ("draft_dimension", "an edge that is straight, with round ones"): ["refused", "invalid_input", "edge: Edge1 of Block is not a circle or an arc — its round edges: 2, 3."],
    ("draft_dimension", "another tab in front"): ['refused', 'invalid_state', "Draft needs the model's 3D view in front to make a dimension, and another tab is (a drawing page, a spreadsheet, the start page): bring the 3D view's tab to the front in FreeCAD, then call this again. Nothing was kept."],
    ("draft_style", "a new style"): {"style": "Big", "values": {"FontSize": 6.0, "ArrowTypeStart": 3, "ArrowTypeEnd": 3, "ArrowSizeStart": 2.0, "ArrowSizeEnd": 2.0, "Decimals": 2, "ShowUnit": False, "FontName": "osifont", "TextColor": 255, "LineWidth": 2}},
    ("draft_style", "apply without a window"): {'applied': [], 'recorded': ['Thing', 'Noted'], 'note': "No window here to show styles: the name is recorded on them (property AgentLinkStyle); call apply again once the file is open in FreeCAD's window."},
    ("draft_style", "an arrow it has not"): ["refused", "invalid_input", "values.ArrowType: one of Dot, Circle, Arrow, Tick, Tick-2, None (or its index 0 … 5)."],
    ("draft_modify", "upgraded to two wires a hair apart"): {"op": "upgrade", "note": "Upgraded and Upgraded001 end 0.001 mm apart and were not joined: FreeCAD joins ends that meet within 1e-7 mm. Give their points with every decimal (or move one end onto the other), then upgrade again."},
    ("draft_modify", "split at a point"): {"op": "split", "step": 1},
    ("draft_modify", "no chamfer fits"): ["refused", "failed", "No chamfer of 5 mm fits between Wire, Wire001: they must be two single edges (lines or arcs) that share an end point, and the radius must fit on both. Nothing was changed."],
    ("draft_modify", "offset that fails"): ['refused', 'failed', "Draft could not offset Wire by that: offset: Draft could not — a smaller distance, the other side, or part_offset2d for a shape Draft's offset does not take."],
}
# Refusals written in the data that no case here reaches: none.
UNREACHED = []


def cases(fc, tmp, old, new):
    import os

    Vec, Shape = fc.Vec, fc.Shape
    PTS = [(0, 0, 0), (10, 0, 0), (10, 10, 0)]

    class StyleView:
        """An annotation's view provider: what is set on it is written down."""

        def __init__(self, owner, style="", props=(), refuses=False, unread=False):
            self.__dict__.update(owner=owner, props=list(props), refuses=refuses, unread=unread, style=style)

        def __getattr__(self, k):
            if k == "PropertiesList":
                return ["AnnotationStyle"] + self.props
            if k == "AnnotationStyle":
                if self.unread:
                    raise RuntimeError("no such enumeration")
                return self.style
            raise AttributeError(k)

        def __setattr__(self, k, v):
            fc.trace.append(f"{self.owner}.ViewObject.{k} = {v!r}")
            if self.refuses and k == "AnnotationStyle" and isinstance(v, str):
                raise ValueError("not a style of this annotation")
            self.__dict__["style" if k == "AnnotationStyle" else k] = v

        def getTypeIdOfProperty(self, k):
            if k == "LineWidth":
                raise RuntimeError("no such property")
            return "App::PropertyColor" if k.endswith("Color") else "App::PropertyFloat"

    def prep(*fns, gui=False, meta=None, **flags):
        def prepare(s):
            fc.fc.GuiUp = gui
            fc.fc.ActiveDocument = None
            fc.state["flags"].update(flags)
            s.doc.Meta = dict(meta or {})
            for fn in fns:
                fn(s)
        return prepare

    def block(s):
        fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10)), name="Block")

    def sheet(s):
        fc.body("Sheet", Shape("sheet", "Face", (0, 0, 0), (10, 10, 0), area=100.0, faces=1, edges=4, solids=0, shells=0), name="Sheet")

    def curved(s):
        fc.body("Curved", Shape("curved", "Face", (0, 0, 0), (10, 10, 5), area=120.0, faces=1, edges=4, solids=0, shells=0, flat=False), name="Curved")

    def dot(s):
        fc.body("Dot", Shape("dot", "Compound", (0, 0, 0), (0, 0, 0), solids=0), name="Dot")

    def group(s):
        fc.doc().new("App::DocumentObjectGroup", "Group", Group=[])

    def thing(s):
        fc.new("Thing", "Thing")

    def section(s):
        fc.new("SectionPlane", "Section")

    def wire(pts=PTS, closed=False, kind="Wire"):
        def make(s):
            fc.new(kind, kind, fc.line(f"a {kind.lower()}", pts, closed), Points=[Vec(*p) for p in pts], Closed=closed)
        return make

    def circle(vertex=True):
        def make(s):
            sh = fc.line("a circle", [(5, 0, 0), (-5, 0, 0)]) if vertex else Shape("a circle", "Wire", (-5, -5, 0), (5, 5, 0), edges=1, solids=0, shells=0)
            fc.new("Circle", "Circle", sh, Radius=5.0)
        return make

    def layer(view=True):
        def make(s):
            o = fc.new("Layer", "Layer", Group=[])
            if view:
                v = fc.View("Layer")
                v.__dict__["LineWidth"] = 1.0
                o.__dict__["ViewObject"] = v
        return make

    def annotation(name, style="", **kw):
        def make(s):
            o = fc.new("LinearDimension", name)
            o.__dict__["ViewObject"] = StyleView(name, style, **kw)
        return make

    def recorded(s):
        o = fc.new("Label", "Noted")
        o.__dict__["AgentLinkStyle"] = "Old"

    def pat(name, text):
        def make(s):
            with open(os.path.join(s.out_dir, name), "w", encoding="utf-8") as f:
                f.write(text)
        return make

    none = prep()

    T = "draft_from_sketch"
    yield T, "two objects", prep(wire(), wire()), {"objects": ["Wire", "Wire001"]}
    yield T, "one name, a block, the original deleted", prep(wire(), draftify="one"), {"objects": "Wire", "block": True, "delete": True}
    yield T, "no edges", prep(wire(), dot), {"objects": ["Wire", "Dot"]}
    yield T, "nothing made", prep(wire(), draftify="none"), {"objects": ["Wire"]}
    yield T, "no objects", none, {}
    yield T, "not here", prep(wire()), {"objects": ["Nope"]}

    T = "draft_facebinder"
    two = {"faces": ["Block.Face6", "Block.Face1"]}
    yield T, "two faces", prep(block), two
    yield T, "a skin, moved off, named", prep(block), {**two, "extrusion": 2, "offset": 1, "name": "Gasket"}
    yield T, "a Draft that takes tuples", prep(block, binder_wants_tuples=True), two
    yield T, "an older facebinder: no extrusion to set", prep(block, old_binder=True), {**two, "extrusion": 2, "offset": 1}
    yield T, "an edge", prep(block), {"faces": ["Block.Face6", "Block.Edge1"]}
    yield T, "a whole object", prep(block), {"faces": ["Block"]}
    yield T, "a point", prep(block), {"faces": [[0, 0, 0]]}
    yield T, "none", prep(block), {}
    yield T, "extrusion not a number", prep(block), {**two, "extrusion": "thick"}
    yield T, "nothing made", prep(block, none=("make_facebinder",)), two

    T = "draft_2d_view"
    yield T, "from above", prep(block), {"object": "Block"}
    yield T, "from the side, hidden lines, named", prep(block), {"object": "Block", "direction": [1, 0, 0], "hidden": True, "name": "Side"}
    yield T, "Draft's older name for it", prep(block, missing=("Draft.make_shape_2d_view",)), {"object": "Block"}
    yield T, "a Draft that takes the direction by keyword", prep(block, type_error=("make_shape_2d_view",)), {"object": "Block"}
    yield T, "empty", prep(block, view_empty=True), {"object": "Block"}
    yield T, "cut faces of a body", prep(block), {"object": "Block", "section": True}
    yield T, "cut faces of a section plane", prep(section), {"object": "Section", "section": True, "hidden": True}
    yield T, "an older view: no properties to set", prep(section, old_view=True), {"object": "Section", "section": True, "hidden": True}
    yield T, "no shape", prep(thing), {"object": "Thing"}
    yield T, "a group", prep(group), {"object": "Group"}
    yield T, "no direction", prep(block), {"object": "Block", "direction": [0, 0, 0]}
    yield T, "not here", prep(block), {"object": "Nope"}

    T = "draft_clone"
    yield T, "as it is", prep(block), {"object": "Block"}
    yield T, "scaled by a factor, moved, named", prep(block), {"object": "Block", "scale": 2, "move": [5, 0, 0], "name": "Twin"}
    yield T, "scaled three ways", prep(block), {"object": "Block", "scale": [1, 2.5, 3]}
    yield T, "scale 0", prep(block), {"object": "Block", "scale": 0}
    yield T, "scale a word", prep(block), {"object": "Block", "scale": "big"}
    yield T, "scale of two", prep(block), {"object": "Block", "scale": [1, 2]}
    yield T, "scale true", prep(block), {"object": "Block", "scale": True}
    yield T, "no shape", prep(group), {"object": "Group"}
    yield T, "a BIM object", prep(block, bim_clone=True), {"object": "Block"}
    yield T, "a BIM object, scaled", prep(block, bim_clone=True), {"object": "Block", "scale": 2}
    yield T, "move that is not a vector", prep(block), {"object": "Block", "move": "up"}
    yield T, "no object", prep(block), {}

    T = "draft_layer"
    yield T, "a new one", none, {"name": "Walls"}
    yield T, "a new one with a width and objects", prep(block, wire()), {"name": "Walls", "lineWidth": 3, "objects": ["Block", "Wire", "Block"]}
    yield T, "one that is there, in the window, its width", prep(block, layer(), gui=True), {"name": "Layer", "lineWidth": 2, "objects": ["Block"]}
    yield T, "one that is there, no window", prep(block, layer()), {"name": "Layer", "lineWidth": 2}
    yield T, "one that is there, in the window, no view", prep(layer(False), gui=True), {"name": "Layer", "lineWidth": 2}
    yield T, "a new one in the window", prep(gui=True), {"name": "Walls"}
    yield T, "a layer on a layer", prep(block, layer()), {"name": "Other", "objects": ["Block", "Layer"]}
    yield T, "no name", none, {}
    yield T, "a blank name", none, {"name": " "}
    yield T, "width 0", none, {"name": "Walls", "lineWidth": 0}
    yield T, "width a word", none, {"name": "Walls", "lineWidth": "thick"}
    yield T, "width true", none, {"name": "Walls", "lineWidth": True}
    yield T, "an object not here", none, {"name": "Walls", "objects": ["Nope"]}

    T = "draft_hatch"
    mine = pat("mine.pat", "".join(f"*P{i}, pattern {i}\n0,0,0,0,{i + 1}\n" for i in range(25)))
    yield T, "as it comes", prep(sheet), {"object": "Sheet"}
    yield T, "a pattern by name, scaled, turned, named", prep(sheet), {"object": "Sheet", "pattern": "Square", "scale": 2, "rotation": 45, "name": "Lines"}
    yield T, "a body's flat faces", prep(block), {"object": "Block"}
    yield T, "a file of one's own", prep(sheet, mine), {"object": "Sheet", "file": "mine.pat", "pattern": "P3"}
    yield T, "a pattern not in a long file", prep(sheet, mine), {"object": "Sheet", "file": "mine.pat"}
    yield T, "a pattern not in the file", prep(sheet), {"object": "Sheet", "pattern": "Nope"}
    yield T, "no such file", prep(sheet), {"object": "Sheet", "file": "none.pat"}
    yield T, "not a .pat file", prep(sheet, pat("mine.txt", "*P1\n")), {"object": "Sheet", "file": "mine.txt"}
    yield T, "no face", prep(dot), {"object": "Dot"}
    yield T, "no flat face", prep(curved), {"object": "Curved"}
    yield T, "no shape", prep(group), {"object": "Group"}
    yield T, "scale 0", prep(sheet), {"object": "Sheet", "scale": 0}
    yield T, "scale a word", prep(sheet), {"object": "Sheet", "scale": "big"}
    yield T, "rotation a word", prep(sheet), {"object": "Sheet", "rotation": "round"}
    yield T, "no lines drawn", prep(sheet, hatch_empty=True), {"object": "Sheet"}

    T = "draft_label"
    yield T, "custom", none, {"target": [0, 0, 0]}
    yield T, "two lines, at a point, named", none, {"target": [1, 2, 3], "at": [9, 9, 0], "text": "a\nb", "name": "Note"}
    yield T, "the area of a face", prep(block), {"target": [0, 0, 0], "object": "Block.Face6", "show": "area"}
    yield T, "custom text on an object", prep(block), {"target": [0, 0, 0], "object": "Block", "text": "here"}
    yield T, "a release that left the area empty", prep(block, label_reads=[]), {"target": [0, 0, 0], "object": "Block.Face6", "show": "area"}
    yield T, "a release that left the length empty", prep(block, label_reads=[]), {"target": [0, 0, 0], "object": "Block.Edge1", "show": "length"}
    yield T, "a release that left the position empty", prep(block, label_reads=[]), {"target": [0, 0, 0], "object": "Block", "show": "position"}
    yield T, "a release that left the name empty", prep(block, label_reads=[]), {"target": [0, 0, 0], "object": "Block", "show": "name"}
    yield T, "a material that reads nothing", prep(block, label_reads=[""]), {"target": [0, 0, 0], "object": "Block", "show": "material"}
    yield T, "show wrong", none, {"target": [0, 0, 0], "show": "weight"}
    yield T, "show without an object", none, {"target": [0, 0, 0], "show": "area"}
    yield T, "no target", none, {}
    yield T, "an object not here", prep(block), {"target": [0, 0, 0], "object": "Nope.Face1"}
    yield T, "nothing made", prep(none=("make_label",)), {"target": [0, 0, 0]}

    T = "draft_plane"
    yield T, "at the origin", none, {}
    yield T, "at a point, turned, named", none, {"at": [1, 2, 3], "normal": [0, 0, 2], "rotate": 30, "name": "Top"}
    yield T, "on a face", prep(block), {"face": "Block.Face6"}
    yield T, "an edge", prep(block), {"face": "Block.Edge1"}
    yield T, "a whole object", prep(block), {"face": "Block"}
    yield T, "a face that is not flat", prep(curved), {"face": "Curved.Face1"}
    yield T, "Draft's older name for it", prep(missing=("Draft.make_workingplaneproxy",)), {}
    yield T, "a Draft without one", prep(missing=("Draft.make_workingplaneproxy", "Draft.makeWorkingPlaneProxy")), {}
    yield T, "another tab in front", prep(gui=True, attr_error=("make_workingplaneproxy",)), {}
    yield T, "crash: the same without a window", prep(attr_error=("make_workingplaneproxy",)), {}
    yield T, "no normal", none, {"normal": [0, 0, 0]}
    yield T, "at that is not a point", none, {"at": "here"}

    T = "draft_shape"
    yield T, "a wire", none, {"kind": "wire", "points": PTS}
    yield T, "a wire closed by its ends", none, {"kind": "wire", "points": [list(p) for p in PTS] + [[0, 0, 0]]}
    yield T, "a closed B-spline, outline only, named", none, {"kind": "bspline", "points": PTS, "closed": True, "face": False, "name": "Curve"}
    yield T, "a Bezier curve whose ends meet", none, {"kind": "bezier", "points": [list(p) for p in PTS] + [[0, 0, 0]]}
    yield T, "one point for a wire", none, {"kind": "wire", "points": [[0, 0, 0]]}
    yield T, "no points", none, {"kind": "wire"}
    yield T, "the same point twice", none, {"kind": "wire", "points": [[1, 1, 0], [1, 1, 0]]}
    yield T, "closed with two", none, {"kind": "bspline", "points": [[0, 0, 0], [1, 1, 0]], "closed": True}
    yield T, "a point that is not one", none, {"kind": "wire", "points": [[0, 0, 0], "there"]}
    yield T, "a rectangle, placed", none, {"kind": "rectangle", "length": 20, "height": 10, "at": [5, 5, 0], "normal": [0, 0, 1], "face": True}
    yield T, "a rectangle of no length", none, {"kind": "rectangle", "length": 0, "height": 10}
    yield T, "a rectangle of no height", none, {"kind": "rectangle", "length": 5, "height": -1}
    yield T, "a rectangle without a height", none, {"kind": "rectangle", "length": 5}
    yield T, "a circle", none, {"kind": "circle", "radius": 5}
    yield T, "a circle of no radius", none, {"kind": "circle", "radius": 0}
    yield T, "an arc", none, {"kind": "arc", "radius": 5, "start": 10, "end": 100}
    yield T, "an arc as it comes", none, {"kind": "arc", "radius": 5}
    yield T, "an arc that is a circle", none, {"kind": "arc", "radius": 5, "start": 0, "end": 360}
    yield T, "an arc whose end is a word", none, {"kind": "arc", "radius": 5, "end": "round"}
    yield T, "an ellipse", none, {"kind": "ellipse", "major": 20, "minor": 10}
    yield T, "an ellipse of no major", none, {"kind": "ellipse", "major": 0, "minor": 10}
    yield T, "an ellipse of no minor", none, {"kind": "ellipse", "major": 20, "minor": 0}
    yield T, "a hexagon", none, {"kind": "polygon", "radius": 5}
    yield T, "a triangle, flats on the radius", none, {"kind": "polygon", "sides": 3, "radius": 5, "inscribed": False}
    yield T, "two sides", none, {"kind": "polygon", "sides": 2, "radius": 5}
    yield T, "sides true", none, {"kind": "polygon", "sides": True, "radius": 5}
    yield T, "a polygon of no radius", none, {"kind": "polygon", "radius": 0}
    yield T, "a point", none, {"kind": "point", "at": [1, 2, 3]}
    yield T, "a point nowhere", none, {"kind": "point"}
    yield T, "kind wrong", none, {"kind": "star"}
    yield T, "kind a list", none, {"kind": ["wire"]}
    yield T, "no kind", none, {}
    yield T, "face that is not yes or no", none, {"kind": "circle", "radius": 5, "face": "yes"}
    yield T, "no normal", none, {"kind": "circle", "radius": 5, "normal": [0, 0, 0]}
    yield T, "nothing made", prep(none=("make_rectangle",)), {"kind": "rectangle", "length": 5, "height": 5}
    yield T, "made broken", prep(objects_invalid=True), {"kind": "circle", "radius": 5}

    T = "draft_link_array"
    yield T, "ortho as it comes", prep(block), {"object": "Block"}
    yield T, "ortho along x, named, real shapes", prep(block), {"object": "Block", "kind": "ortho", "count": [3], "spacing": [15], "link": False, "name": "Row"}
    yield T, "a count of 0", prep(block), {"object": "Block", "count": [2, 0]}
    yield T, "a count that is a number", prep(block), {"object": "Block", "count": 3}
    yield T, "a spacing that is a word", prep(block), {"object": "Block", "spacing": ["wide"]}
    yield T, "no spacing where there are two", prep(block), {"object": "Block", "count": [2, 1, 1], "spacing": [0, 5, 5]}
    yield T, "polar as it comes", prep(block), {"object": "Block", "kind": "polar"}
    yield T, "polar about a centre", prep(block), {"object": "Block", "kind": "polar", "count": 3, "angle": 90, "center": [20, 0, 0]}
    yield T, "polar of one", prep(block), {"object": "Block", "kind": "polar", "count": 1}
    yield T, "polar count true", prep(block), {"object": "Block", "kind": "polar", "count": True}
    yield T, "polar angle a word", prep(block), {"object": "Block", "kind": "polar", "angle": "round"}
    yield T, "circular as it comes", prep(block), {"object": "Block", "kind": "circular"}
    yield T, "circular, set", prep(block), {"object": "Block", "kind": "circular", "rings": 4, "ringSpacing": 30, "tangentSpacing": 12, "symmetry": 3}
    yield T, "no ring spacing", prep(block), {"object": "Block", "kind": "circular", "ringSpacing": 0}
    yield T, "one ring", prep(block), {"object": "Block", "kind": "circular", "rings": 1}
    yield T, "no symmetry", prep(block), {"object": "Block", "kind": "circular", "symmetry": 0}
    yield T, "along a path, turned with it", prep(block, wire()), {"object": "Block", "kind": "path", "path": "Wire", "align": True}
    yield T, "a path without edges", prep(block, dot), {"object": "Block", "kind": "path", "path": "Dot"}
    yield T, "none along a path", prep(block, wire()), {"object": "Block", "kind": "path", "path": "Wire", "count": 0}
    yield T, "no path", prep(block), {"object": "Block", "kind": "path"}
    yield T, "at points", prep(block, wire()), {"object": "Block", "kind": "points", "points": "Wire"}
    yield T, "points that are none", prep(block, group), {"object": "Block", "kind": "points", "points": "Group"}
    yield T, "kind wrong", prep(block), {"object": "Block", "kind": "spiral"}
    yield T, "kind a list", prep(block), {"object": "Block", "kind": ["ortho"]}
    yield T, "an array that has no count", prep(block, no_count=True), {"object": "Block"}
    yield T, "nothing made", prep(block, none=("make_ortho_array",)), {"object": "Block"}
    yield T, "no object", prep(block), {}

    T = "draft_dimension"
    ft = {"from": [0, 0, 0], "to": [10, 0, 0]}
    yield T, "between two points", none, ft
    yield T, "its line through a point, named", none, {**ft, "kind": "linear", "at": [5, 5, 0], "name": "Width"}
    yield T, "the same point twice", none, {"from": [1, 1, 1], "to": [1, 1, 1]}
    yield T, "no from", none, {"to": [1, 1, 1]}
    yield T, "between two vertices", prep(wire()), {"object": "Wire", "vertices": [1, 3], "at": [5, 5, 0]}
    yield T, "between an object's first two vertices", prep(wire()), {"object": "Wire"}
    yield T, "one vertex twice", prep(wire()), {"object": "Wire", "vertices": [1, 1]}
    yield T, "a vertex it has not", prep(wire()), {"object": "Wire", "vertices": [0, 2]}
    yield T, "vertices a word", prep(wire()), {"object": "Wire", "vertices": "ends"}
    yield T, "an object without a shape", prep(thing), {"object": "Thing"}
    yield T, "a radius", prep(block, round=(2,)), {"kind": "radius", "object": "Block", "edge": 2}
    yield T, "a diameter of the first edge", prep(block, round=(1,)), {"kind": "diameter", "object": "Block", "at": [3, 3, 0]}
    yield T, "an edge it has not", prep(block), {"kind": "radius", "object": "Block", "edge": 99}
    yield T, "edge true", prep(block), {"kind": "radius", "object": "Block", "edge": True}
    yield T, "an edge that is straight, with round ones", prep(block, round=(2, 3)), {"kind": "radius", "object": "Block", "edge": 1}
    yield T, "an edge that is straight, with none round", prep(block), {"kind": "diameter", "object": "Block", "edge": 1}
    yield T, "a radius of what has no shape", prep(thing), {"kind": "radius", "object": "Thing"}
    yield T, "a radius of nothing", none, {"kind": "radius"}
    yield T, "an angle as it comes", none, {"kind": "angular"}
    yield T, "an angle through 0", none, {"kind": "angular", "angles": [350, 10], "center": [1, 1, 0], "normal": [0, 0, 1], "at": [5, 5, 0]}
    yield T, "angles that are words", none, {"kind": "angular", "angles": ["a", "b"]}
    yield T, "one angle", none, {"kind": "angular", "angles": [30]}
    yield T, "an angle Draft keeps no angles of", prep(angular_props={"Other": 1}), {"kind": "angular"}
    yield T, "kind wrong", none, {"kind": "slope"}
    yield T, "another tab in front", prep(gui=True, attr_error=("make_linear_dimension",)), ft
    yield T, "crash: another error in the window", prep(gui=True, attr_error=("make_linear_dimension",), attr_msg="'NoneType' object has no attribute 'Proxy'"), ft
    yield T, "crash: the view's error without a window", prep(attr_error=("make_linear_dimension",)), ft
    yield T, "nothing made", prep(none=("make_linear_dimension",)), ft

    T = "draft_style"
    M = {"Draft_Style_Old": "{\"FontSize\": 3.5, \"ArrowType\": \"Tick\", \"ArrowTypeStart\": \"Bogus\"}", "Draft_Style_Torn": "{not json", "Title": "a part"}
    big = {"FontSize": 6, "ArrowType": "tick", "ArrowSize": 2, "Decimals": 2.0, "ShowUnit": False, "FontName": "osifont", "TextColor": 255, "ArrowTypeEnd": 3, "LineWidth": 2}
    yield T, "none to list", none, {}
    yield T, "the styles", prep(meta=M), {"action": "list"}
    yield T, "no name", prep(meta=M), {"action": "set"}
    yield T, "a name that is a number", prep(meta=M), {"action": "apply", "name": 5}
    yield T, "a new style", none, {"action": "set", "name": "Big", "values": big}
    yield T, "one that is there, changed", prep(meta=M), {"action": "set", "name": "Old", "values": {"Decimals": 1}}
    yield T, "one that is there, nothing given: an older arrow name put right", prep(meta=M), {"action": "set", "name": "Old"}
    yield T, "a new style without values", prep(meta=M), {"action": "set", "name": "New"}
    yield T, "values that are a word", prep(meta=M), {"action": "set", "name": "Old", "values": "big"}
    yield T, "a key it has not", none, {"action": "set", "name": "Big", "values": {"FontSize": 6, "Colour": 1}}
    yield T, "an arrow it has not", none, {"action": "set", "name": "Big", "values": {"ArrowType": "Spear"}}
    yield T, "an arrow number it has not", none, {"action": "set", "name": "Big", "values": {"ArrowTypeStart": 9}}
    yield T, "an arrow that is true", none, {"action": "set", "name": "Big", "values": {"ArrowType": True}}
    yield T, "a switch that is a word", none, {"action": "set", "name": "Big", "values": {"ShowUnit": "yes"}}
    yield T, "a font that is a number", none, {"action": "set", "name": "Big", "values": {"FontName": 5}}
    yield T, "a size that is a word", none, {"action": "set", "name": "Big", "values": {"FontSize": "big"}}
    yield T, "a colour that is a word", none, {"action": "set", "name": "Big", "values": {"TextColor": "red"}}
    yield T, "a size that is true", none, {"action": "set", "name": "Big", "values": {"FontSize": True}}
    worn = annotation("Dim", "Old", props=["FontSize", "TextColor", "LineWidth"])
    yield T, "what wears it follows", prep(worn, annotation("Other", "Else"), thing, gui=True, meta=M), {"action": "set", "name": "Old", "values": {"FontSize": 5, "TextColor": 0x10203000, "LineWidth": 3, "Decimals": 0}}
    yield T, "deleted", prep(meta=M), {"action": "delete", "name": "Old"}
    yield T, "deleted from under what wears it", prep(worn, annotation("Lost", "Old", unread=True), gui=True, meta=M), {"action": "delete", "name": "Torn"}
    yield T, "deleted, worn", prep(worn, annotation("Other", "Torn"), gui=True, meta=M), {"action": "delete", "name": "Old"}
    yield T, "delete one that is not there", prep(meta=M), {"action": "delete", "name": "Nope"}
    yield T, "delete where there are none", none, {"action": "delete", "name": "Nope"}
    yield T, "apply one that is not there", prep(thing, meta=M), {"action": "apply", "name": "Nope", "objects": ["Thing"]}
    yield T, "apply to nothing", prep(meta=M), {"action": "apply", "name": "Old"}
    yield T, "apply without a window", prep(thing, recorded, meta=M), {"action": "apply", "name": "Old", "objects": ["Thing", "Noted"]}
    yield T, "apply in the window", prep(worn, annotation("Fresh"), gui=True, meta=M), {"action": "apply", "name": "Torn", "objects": ["Dim", "Fresh"]}
    yield T, "apply to what is no annotation", prep(worn, thing, gui=True, meta=M), {"action": "apply", "name": "Old", "objects": ["Dim", "Thing"]}
    yield T, "apply refused by FreeCAD", prep(annotation("Stiff", refuses=True), worn, gui=True, meta=M), {"action": "apply", "name": "Old", "objects": ["Stiff", "Dim"]}
    yield T, "apply to one not here", prep(meta=M), {"action": "apply", "name": "Old", "objects": ["Nope"]}
    yield T, "action wrong", prep(meta=M), {"action": "paint", "name": "Old"}

    T = "draft_modify"
    W, WW = {"objects": ["Wire"]}, {"objects": ["Wire", "Wire001"]}
    one, two_ = prep(wire()), prep(wire(), wire([(10, 10, 0), (20, 10, 0)]))
    yield T, "moved", two_, {"op": "move", **WW, "by": [5, 0, 0]}
    yield T, "moved, a copy", one, {"op": "move", **W, "by": [5, 0, 0], "copy": True}
    yield T, "moved nowhere said", one, {"op": "move", **W}
    yield T, "not moved", prep(wire(), modify_answers=None), {"op": "move", **W, "by": [5, 0, 0]}
    yield T, "moved: Draft answers one object", prep(wire(), wire(), modify_answers="first"), {"op": "move", **WW, "by": [1, 0, 0]}
    yield T, "turned as it comes", one, {"op": "rotate", **W}
    yield T, "turned about a point and an axis, a copy", one, {"op": "rotate", **W, "angle": 45, "center": [1, 1, 0], "axis": [0, 1, 0], "copy": True}
    yield T, "turned by a word", one, {"op": "rotate", **W, "angle": "round"}
    yield T, "turned about no axis", one, {"op": "rotate", **W, "axis": [0, 0, 0]}
    yield T, "not turned", prep(wire(), modify_answers=None), {"op": "rotate", **W}
    yield T, "scaled as it comes", one, {"op": "scale", **W}
    yield T, "scaled three ways about a point, a copy", one, {"op": "scale", **W, "factor": [1, 2, -1], "center": [1, 1, 0], "copy": True}
    yield T, "scaled by 0", one, {"op": "scale", **W, "factor": 0}
    yield T, "scaled two ways", one, {"op": "scale", **W, "factor": [1, 2]}
    yield T, "scaled by a word", one, {"op": "scale", **W, "factor": "big"}
    yield T, "not scaled", prep(wire(), modify_answers=None), {"op": "scale", **W}
    yield T, "mirrored", one, {"op": "mirror", **W, "from": [0, 0, 0], "to": [0, 10, 0]}
    yield T, "mirrored in a point", one, {"op": "mirror", **W, "from": [0, 0, 0], "to": [0, 0, 0]}
    yield T, "not mirrored", prep(wire(), none=("mirror",)), {"op": "mirror", **W, "from": [0, 0, 0], "to": [0, 10, 0]}
    yield T, "offset", one, {"op": "offset", **W, "by": [0, 2, 0]}
    yield T, "offset, a copy", one, {"op": "offset", **W, "by": [0, 2, 0], "copy": True}
    yield T, "offset of two", two_, {"op": "offset", **WW, "by": [0, 2, 0]}
    yield T, "offset by nothing", one, {"op": "offset", **W, "by": [0, 0, 0]}
    yield T, "offset of a B-spline", prep(wire(kind="BSpline")), {"op": "offset", "objects": ["BSpline"], "by": [0, 2, 0]}
    yield T, "offset of a circle", prep(circle()), {"op": "offset", "objects": ["Circle"], "by": [2, 0, 0]}
    yield T, "offset of a circle that has no vertex", prep(circle(False)), {"op": "offset", "objects": ["Circle"], "by": [2, 0, 0], "copy": True}
    yield T, "offset of a circle onto its centre", prep(circle()), {"op": "offset", "objects": ["Circle"], "by": [-5, 0, 0]}
    yield T, "offset that fails", prep(wire(), fail=("offset",)), {"op": "offset", **W, "by": [0, 2, 0]}
    yield T, "offset that answers nothing", prep(wire(), none=("offset",)), {"op": "offset", **W, "by": [0, 2, 0]}
    yield T, "upgraded", two_, {"op": "upgrade", **WW}
    yield T, "upgraded, the originals kept", two_, {"op": "upgrade", **WW, "delete": False}
    yield T, "upgraded: closed in place", prep(wire(), grade="closes"), {"op": "upgrade", **W}
    yield T, "nothing to upgrade", prep(wire(), wire(), grade="nothing"), {"op": "upgrade", **WW}
    yield T, "nothing to upgrade: Draft answers nothing", prep(wire(), grade="odd"), {"op": "upgrade", **W}
    yield T, "nothing to downgrade", prep(wire(), grade="nothing"), {"op": "downgrade", **W}
    yield T, "downgraded", one, {"op": "downgrade", **W}
    yield T, "upgraded to two wires a hair apart", prep(wire(), wire(), grade_makes=[((0, 0, 0), (10, 0, 0)), ((10.001, 0, 0), (20, 0, 0))]), {"op": "upgrade", **WW}
    yield T, "upgraded to two wires well apart", prep(wire(), wire(), grade_makes=[((0, 0, 0), (10, 0, 0)), ((15, 0, 0), (20, 0, 0))]), {"op": "upgrade", **WW}
    yield T, "joined", two_, {"op": "join", **WW}
    yield T, "join of one", one, {"op": "join", **W}
    yield T, "join of what is no wire", prep(wire(), block), {"op": "join", "objects": ["Wire", "Block"]}
    yield T, "nothing joined", prep(wire(), wire(), join="same"), {"op": "join", **WW}
    yield T, "join that answers nothing", prep(wire(), wire(), join="none"), {"op": "join", **WW}
    yield T, "a fillet", two_, {"op": "fillet", **WW}
    yield T, "a chamfer, the lines deleted", two_, {"op": "fillet", **WW, "radius": 2, "chamfer": True, "delete": True}
    yield T, "a fillet of one", one, {"op": "fillet", **W}
    yield T, "a fillet of no radius", two_, {"op": "fillet", **WW, "radius": 0}
    yield T, "no fillet fits", prep(wire(), wire(), none=("make_fillet",)), {"op": "fillet", **WW, "radius": 2.5}
    yield T, "no chamfer fits", prep(wire(), wire(), none=("make_fillet",)), {"op": "fillet", **WW, "chamfer": True}
    yield T, "split in the middle", one, {"op": "split", **W, "edge": 1}
    yield T, "split at a point", one, {"op": "split", **W, "edge": 2, "at": [12, 4, 0]}
    yield T, "split beyond the segment", one, {"op": "split", **W, "edge": 1, "at": [30, 0, 0]}
    yield T, "split on no edge", one, {"op": "split", **W}
    yield T, "split of two", two_, {"op": "split", **WW, "edge": 1}
    yield T, "split of what holds no points", prep(block), {"op": "split", "objects": ["Block"], "edge": 1}
    yield T, "a closed wire split", prep(wire(closed=True)), {"op": "split", **W, "edge": 2}
    yield T, "a closed wire split on its last segment", prep(wire(closed=True)), {"op": "split", **W, "edge": 3}
    yield T, "stretched", two_, {"op": "stretch", **WW, "box": [[9, -1, -1], [11, 11, 1]], "by": [5, 0, 0]}
    yield T, "stretched with no box", one, {"op": "stretch", **W, "by": [5, 0, 0]}
    yield T, "stretched where no point is", one, {"op": "stretch", **W, "box": [[50, 50, 0], [60, 60, 0]], "by": [5, 0, 0]}
    yield T, "stretched nowhere said", one, {"op": "stretch", **W, "box": [[9, -1, -1], [11, 11, 1]]}
    yield T, "extended at its end", one, {"op": "extend", **W, "length": 5}
    yield T, "trimmed at its start", one, {"op": "extend", **W, "length": -4, "end": "start"}
    yield T, "trimmed past its start", one, {"op": "extend", **W, "length": -10, "end": "start"}
    yield T, "trimmed past its end", one, {"op": "extend", **W, "length": -10}
    yield T, "to a B-spline", prep(wire(), block), {"op": "to_bspline", **W}
    yield T, "to wires, the curves kept", prep(wire(kind="BSpline"), wire(closed=True, kind="BezCurve")), {"op": "to_wire", "objects": ["BSpline", "BezCurve"], "delete": False}
    yield T, "op wrong", one, {"op": "bend", **W}
    yield T, "op a list", one, {"op": ["move"], **W}
    yield T, "no op", one, W
    yield T, "no objects", one, {"op": "move"}
    yield T, "an object not here", one, {"op": "move", "objects": ["Nope"], "by": [1, 0, 0]}
    yield T, "made broken", prep(wire(), objects_invalid=True), {"op": "move", **W, "by": [5, 0, 0], "copy": True}

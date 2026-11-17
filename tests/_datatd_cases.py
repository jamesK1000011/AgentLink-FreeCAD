# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datatd_data.py runs through the old handlers and the
# new data entries on the stand-in TechDraw (tests/_datatd_standin.py): for
# each converted tool its normal paths and each of its refusals. A case is
# (tool, case name, prepare(session), arguments).
import os

FILES = ("techdraw",)

# tool -> its group
CONVERTED = {k: "techdraw" for k in (
    "td_page", "td_title", "td_view", "td_centermarks", "td_hatch", "td_weld", "td_bim", "td_projection", "td_section", "td_detail", "td_geometry",
    "td_dim", "td_dimset", "td_tolerance", "td_gdt", "td_datum", "td_note", "td_balloon", "td_table", "td_section_position", "td_leader", "td_finish",
    "td_area", "td_dim_format", "td_dim_special", "td_dim_align", "td_dim_repair")}

# tool -> why it is still code
NOT_YET = "not converted yet: the work stopped before it (docs/hardening: datacam-findings)"
KEPT = {k: NOT_YET for k in (
    "td_list", "td_cosmetic", "td_view_more", "td_lines", "td_export")}

# Refusals written in an entry that no case reaches, each with its reason.
UNREACHED = [
    # The arc was read a few steps before (it has a radius): its length is there unless the view changes in between.
    "td_dim_special: {names[0]} could not be read.",
]

# What some cases must have answered (so that two empty runs alike do not pass).
EXPECT = {
    ("td_page", "new"): {"page": "Drawing", "paper": [297.0, 210.0], "template": "A4_Landscape_ISO5457_minimal.svg", "cleared": ["AUTHOR_NAME", "DRAWING_TITLE", "FC-DATE"]},
    ("td_view", "front"): {"view": "View 2", "scale": 1.0, "edges": 5, "vertices": 4},
    ("td_projection", "three"): {"projection": "Third angle"},
    ("td_centermarks", "all views"): {"views": [{"view": "Front", "circles": 1}], "extend": 2.0},
    ("td_hatch", "a face"): {"view": "Front", "faces": ["Face1"], "note": "Drawn by td_export."},
    ("td_title", "set"): {"page": "Drawing"},
    ("td_dim", "an edge's length"): {"type": "Distance", "refs": ["Edge0"], "measured": 40.0, "text": "40.00"},
    ("td_dim", "a diameter"): {"type": "Diameter", "measured": 10.0},
    ("td_dimset", "a chain"): {"style": "chain", "overall": 80.0},
    ("td_section", "along x"): {"symbol": "A", "base": "Front"},
    ("td_geometry", "edges"): {"view": "Front", "scale": 1.0},
    ("td_note", "two lines"): {"note": "Note", "lines": 2, "at": [40.0, 40.0]},
    ("td_table", "the filled cells"): {"sheet": "Parts", "range": "A1:B2"},
    ("td_area", "a face"): {"face": "Box.Face1", "area": 800.0, "unit": "mm2", "text": "A = 800.0 mm²"},
    ("td_dim_format", "decimals and a prefix"): {"dims": [{"dimension": "Bore", "format": "⌀%.3f", "reads": "⌀10.000"}]},
    ("td_leader", "with text"): {"leader": "Leader", "on": "Edge1", "note": "Note"},
    ("td_dim_special", "the whole width"): {"kind": "extent_h", "type": "DistanceX", "measured": 40.0},
    ("td_dim_special", "a chamfer"): {"kind": "chamfer_h", "text": "40.00 x27°"},
    ("td_dim_align", "horizontal"): {"dims": [{"dimension": "Length", "at": [5.0, -20.0]}, {"dimension": "Bore", "at": [30.0, -20.0]}, {"dimension": "Third", "at": [60.0, -20.0]}]},
    ("td_dim_repair", "new references"): {"label": "Length", "refs": ["Vertex0", "Vertex1"]},
}


def cases(fc, tmp):
    out = []

    def C(tool, case, args, prep=None, **flags):
        def prepare(s):
            fc.state["flags"].update(flags)
            (prep or drawing)(s)

        out.append((tool, case, prepare, args))

    def none(s):
        pass

    def body(s):
        s.box()

    def page(s):
        s.box()
        s.page()

    def drawing(s):
        b = s.box()
        s.view(s.page(), "Front", body=b)

    def two_pages(s):
        s.box()
        s.page("One")
        s.page("Two")

    # ---- pages ----
    C("td_page", "list, none", {}, none)
    C("td_page", "list", {"action": "list"})
    C("td_page", "templates", {"action": "templates"}, none)
    C("td_page", "read", {"action": "read"})
    C("td_page", "read, no page", {"action": "read"}, none)
    C("td_page", "read, which", {"action": "read"}, two_pages)
    C("td_page", "read, not found", {"action": "read", "page": "Nope"}, two_pages)
    C("td_page", "bad action", {"action": "delete"}, none)
    C("td_page", "new", {"action": "new"}, none)
    C("td_page", "new, set", {"action": "new", "paper": "A4", "orientation": "portrait", "projection": "first", "scale": 0.5, "name": "Sheet"}, none)
    C("td_page", "new, third angle, A3", {"action": "new", "paper": "A3", "projection": "third"}, none)
    C("td_page", "new, blank", {"action": "new", "blank": True}, none)
    C("td_page", "new, a standard there is", {"action": "new", "standard": "iso"}, none)
    C("td_page", "new, a standard there is not", {"action": "new", "standard": "asme"}, none)
    C("td_page", "new, bad paper", {"action": "new", "paper": "B5"}, none)
    C("td_page", "new, no template for it", {"action": "new", "paper": "A0"}, none)
    C("td_page", "new, a template by name", {"action": "new", "template": os.path.join("ASME", "ANSIA_Landscape.svg")}, none)
    C("td_page", "new, no such template", {"action": "new", "template": "mine.svg"}, none)
    C("td_page", "new, a second one", {"action": "new"}, page)

    # ---- the title block ----
    def blank(s):
        s.page("Plain", os.path.join("ISO", "A4_Landscape_blank.svg"))

    def presets(s):
        page(s)
        import json

        with open(os.path.join(fc.state["appdata"], "AgentLink", "titleblocks.json") if os.path.isdir(os.path.join(fc.state["appdata"], "AgentLink")) else os.path.join(_mk(fc.state["appdata"]), "titleblocks.json"), "w") as f:
            json.dump({"shop": {"AUTHOR_NAME": "A. Maker", "COMPANY": "The Shop"}}, f)
        with open(os.path.join(s.out_dir, "theirs.json"), "w") as f:
            json.dump({"theirs": {"PM": "P. Lead"}}, f)
        with open(os.path.join(s.out_dir, "empty.json"), "w") as f:
            f.write("[]")

    def _mk(d):
        p = os.path.join(d, "AgentLink")
        os.makedirs(p, exist_ok=True)
        return p

    C("td_title", "read", {}, page)
    C("td_title", "set", {"fields": {"DRAWING_TITLE": "Bracket", "author_name": "J", "PM": 3}}, page)
    C("td_title", "unknown field", {"fields": {"Nope": "x"}}, page)
    C("td_title", "blank template", {"fields": {"A": "b"}}, blank)
    C("td_title", "export", {"export": "presets.json"}, presets)
    C("td_title", "import", {"import": "theirs.json"}, presets)
    C("td_title", "import, nothing in it", {"import": "empty.json"}, presets)
    C("td_title", "preset", {"preset": "shop"}, presets)
    C("td_title", "preset with fields", {"preset": "shop", "fields": {"PM": "Me"}}, presets)
    C("td_title", "no such preset", {"preset": "nope"}, presets)
    C("td_title", "save a preset", {"preset": "mine", "save": True, "fields": {"PM": "Me"}}, presets)
    C("td_title", "save a preset, nothing to set", {"preset": "mine", "save": True}, presets)
    C("td_title", "delete a preset", {"preset": "shop", "delete": True}, presets)
    C("td_title", "delete, no such preset", {"preset": "nope", "delete": True}, presets)

    # ---- views ----
    C("td_view", "front", {}, page)
    C("td_view", "top, scaled, placed, hidden, named", {"direction": "top", "scale": 2, "at": [50, 60], "hidden": True, "name": "Plan", "bodies": ["Box"]}, page)
    C("td_view", "a direction", {"direction": [1, 1, 0]}, page)
    C("td_view", "up", {"direction": [0, 0, 5]}, page)
    C("td_view", "no page", {}, body)
    C("td_view", "no body", {}, lambda s: s.page())
    C("td_view", "no such body", {"bodies": ["Nope"]}, page)
    C("td_view", "bad direction", {"direction": "sideways"}, page)
    C("td_view", "direction not a vector", {"direction": [1, 2]}, page)
    C("td_view", "zero direction", {"direction": [0, 0, 0]}, page)
    C("td_view", "at off the paper", {"at": [500, 10]}, page)
    C("td_view", "bad at", {"at": [1]}, page)
    C("td_view", "lines come late", {}, page, late_edges=True)

    def plane(s):
        page(s)
        o = s.doc.new("Part::FeaturePython", "Section", Proxy=type("_SectionPlane", (), {})())
        o.__dict__["Label"] = "Plan cut"

    C("td_bim", "a plan", {"section": "Plan cut"}, plane)
    C("td_bim", "set", {"section": "Plan cut", "render": "Solid", "fill": False, "spaces": True, "hidden": True, "scale": 0.01, "at": [100, 100], "name": "Ground floor"}, plane)
    C("td_bim", "a render mode it has not", {"section": "Plan cut", "render": "Coin"}, plane)
    C("td_bim", "draws nothing", {"section": "Plan cut"}, plane, arch_draws_nothing=True)
    C("td_bim", "not a section plane", {"section": "Box"}, plane)
    C("td_bim", "no such object", {"section": "Nope"}, plane)
    C("td_bim", "no page", {"section": "Plan cut"}, body)

    C("td_centermarks", "all views", {})
    C("td_centermarks", "one, by name, off", {"views": "Front", "on": False})
    C("td_centermarks", "a list, longer", {"views": ["Front"], "extend": 4})
    C("td_centermarks", "again", {"extend": 1}, lambda s: (drawing(s), s.doc.Objects[-1].__dict__.update(AgentLinkCenterMarks=2.0)))
    C("td_centermarks", "no such view", {"views": ["Nope"]})
    C("td_centermarks", "lines come late", {}, None, late_edges=True)
    C("td_centermarks", "no views", {}, page)

    C("td_hatch", "a face", {"view": "Front", "faces": ["Face1"]})
    C("td_hatch", "one by name, set", {"view": "Front", "faces": "Face1", "spacing": 1.5, "angle": 30})
    C("td_hatch", "edge-on", {"view": "Front", "faces": ["Face2", "Face1"]})
    C("td_hatch", "taken off", {"view": "Front"}, lambda s: (drawing(s), s.doc.Objects[-1].__dict__.update(AgentLinkHatch="{}")))
    C("td_hatch", "not a face", {"view": "Front", "faces": ["Edge1"]})
    C("td_hatch", "no such face", {"view": "Front", "faces": ["Face9"]})
    C("td_hatch", "no shape", {"view": "Empty"}, lambda s: s.view(s.page(), "Empty"))
    C("td_hatch", "no such view", {"view": "Nope"})
    C("td_hatch", "lines come late", {"view": "Front", "faces": ["Face1"]}, None, late_edges=True)

    C("td_weld", "fillet", {"view": "Front", "on": "Edge1"})
    C("td_weld", "set", {"view": "Front", "on": "Vertex0", "kind": "fillet", "size": 5, "length": "50", "side": "other", "allAround": True, "field": True, "tail": "GTAW", "textSize": 5, "at": [150, 150], "name": "W1"})
    C("td_weld", "bad kind", {"view": "Front", "on": "Edge1", "kind": "glue"})
    C("td_weld", "bad side", {"view": "Front", "on": "Edge1", "side": "top"})
    C("td_weld", "bad reference", {"view": "Front", "on": "Edge99"})
    C("td_weld", "bad at", {"view": "Front", "on": "Edge1", "at": [1]})
    C("td_weld", "no such view", {"view": "Nope", "on": "Edge1"})

    C("td_projection", "three", {}, page)
    C("td_projection", "chosen, first angle, scaled, placed", {"views": ["front", "left", "iso", "left"], "projection": "first", "scale": 0.5, "at": [100, 100], "bodies": ["Box"]}, page)
    C("td_projection", "third angle asked", {"projection": "third", "views": ["top"]}, page)
    C("td_projection", "front turned", {"front": "right"}, page)
    C("td_projection", "front by a vector, no anchor", {"front": [1, 0, 0]}, page, no_anchor=True)
    C("td_projection", "the page's own angle not offered", {}, lambda s: (page(s), s.doc.Objects[1].__dict__.update(ProjectionType="Default")))
    C("td_projection", "bad view", {"views": ["front", "under"]}, page)
    C("td_projection", "bad front", {"front": "under"}, page)
    C("td_projection", "no body", {}, lambda s: s.page())
    C("td_projection", "no page", {}, body)
    C("td_projection", "at off the paper", {"at": [-1, 0]}, page)
    # ================= batch B: sections, details, geometry, dimensions, GD&T, notes =================
    C("td_section", "along x", {"view": "Front", "normal": "x"})
    C("td_section", "set", {"view": "Front", "normal": [0, 0, -2], "through": [20, 5, 3], "symbol": "K", "at": [200, 60], "hatch": False})
    C("td_section", "second letter", {"view": "Front", "normal": "-x"}, lambda s: (drawing(s), s.view(s.doc.Objects[1], "Section A", "TechDraw::DrawViewSection", SectionSymbol="A")))
    C("td_section", "askew", {"view": "Front", "normal": [1, 0, 1]})
    C("td_section", "bad normal", {"view": "Front", "normal": "up"})
    C("td_section", "no normal", {"view": "Front"})
    C("td_section", "normal not a vector", {"view": "Front", "normal": [1, 0]})
    C("td_section", "in the paper", {"view": "Front", "normal": "y"})
    C("td_section", "bad through", {"view": "Front", "normal": "x", "through": [1]})
    C("td_section", "at off the paper", {"view": "Front", "normal": "x", "at": [0, 999]})
    C("td_section", "no geometry", {"view": "Front", "normal": "z"}, None, no_edges=True)
    C("td_section", "no such view", {"view": "Nope", "normal": "x"})

    C("td_detail", "at a point of the part", {"view": "Front", "center": [30, 0, 15], "radius": 4})
    C("td_detail", "by anchor, set", {"view": "Front", "anchor": [5, 5], "radius": 3, "symbol": "Q", "scale": 4, "at": [220, 50]})
    C("td_detail", "at3d, lines late", {"view": "Front", "at3d": [1, 2, 3], "radius": 2}, None, late_edges=True)
    C("td_detail", "default anchor", {"view": "Front", "radius": 2})
    C("td_detail", "no radius", {"view": "Front"})
    C("td_detail", "bad center", {"view": "Front", "center": [1, 2], "radius": 2})
    C("td_detail", "bad anchor", {"view": "Front", "anchor": [1], "radius": 2})
    C("td_detail", "empty", {"view": "Front", "radius": 2}, None, no_edges=True)

    C("td_geometry", "edges", {"view": "Front"})
    C("td_geometry", "circles", {"view": "Front", "kind": "circles"})
    C("td_geometry", "lines, capped", {"view": "Front", "kind": "lines", "limit": 2})
    C("td_geometry", "vertices", {"view": "Front", "kind": "vertices"})
    C("td_geometry", "bad kind", {"view": "Front", "kind": "faces"})
    C("td_geometry", "lines late", {"view": "Front"}, None, late_edges=True)
    C("td_geometry", "no such view", {"view": "Nope"})

    C("td_dim", "an edge's length", {"view": "Front", "refs": ["Edge0"]})
    C("td_dim", "two vertices, horizontal, placed", {"view": "Front", "type": "horizontal", "refs": ["Vertex0", "Vertex2"], "at": [0, -20]})
    C("td_dim", "vertical by its FreeCAD name", {"view": "Front", "type": "DistanceY", "refs": ["Vertex0", "Vertex2"]})
    C("td_dim", "by a point of the part", {"view": "Front", "refs": [{"point": [0, 0, 0]}, {"point": [40, 0, 20]}]})
    C("td_dim", "a diameter", {"view": "Front", "type": "diameter", "refs": ["Edge4"]})
    C("td_dim", "a diameter by its size", {"view": "Front", "type": "diameter", "refs": [{"circle": {"diameter": 10}}]})
    C("td_dim", "a radius", {"view": "Front", "type": "radius", "refs": ["Edge4"]})
    C("td_dim", "a radius of a straight edge", {"view": "Front", "type": "radius", "refs": ["Edge0"]})
    C("td_dim", "a diameter of two", {"view": "Front", "type": "diameter", "refs": ["Edge4", "Edge0"]})
    C("td_dim", "a diameter of a vertex", {"view": "Front", "type": "diameter", "refs": ["Vertex1"]})
    C("td_dim", "an angle", {"view": "Front", "type": "angle", "refs": ["Edge0", "Edge1"]})
    C("td_dim", "an angle of one", {"view": "Front", "type": "angle", "refs": ["Edge0"]})
    C("td_dim", "a distance of three", {"view": "Front", "refs": ["Vertex0", "Vertex1", "Vertex2"]})
    C("td_dim", "a distance of one vertex", {"view": "Front", "refs": ["Vertex0"]})
    C("td_dim", "no refs", {"view": "Front"})
    C("td_dim", "bad type", {"view": "Front", "type": "length", "refs": ["Edge0"]})
    C("td_dim", "bad reference", {"view": "Front", "refs": ["Edge77"]})
    C("td_dim", "bad at", {"view": "Front", "refs": ["Edge0"], "at": 5})
    C("td_dim", "cannot be measured", {"view": "Front", "refs": ["Edge0"]}, None, cannot_measure=True)
    C("td_dim", "a fit", {"view": "Front", "type": "diameter", "refs": ["Edge4"], "fit": "H7"})
    C("td_dim", "a bad fit", {"view": "Front", "type": "diameter", "refs": ["Edge4"], "fit": "Q99"})
    C("td_dim", "plus and minus", {"view": "Front", "refs": ["Edge0"], "plus": 0.1, "minus": 0.05, "format": "%.1f"})
    C("td_dim", "plus alone, basic, labelled", {"view": "Front", "refs": ["Edge0"], "plus": 0.2, "basic": True, "label": "REF"})
    C("td_dim", "lines late, no text", {"view": "Front", "refs": ["Edge0"]}, None, late_edges=True, no_text=True)

    C("td_dimset", "a chain", {"view": "Front", "refs": ["Vertex0", "Vertex1", "Vertex0"]})
    C("td_dimset", "a baseline, vertical, set", {"view": "Front", "type": "vertical", "style": "baseline", "refs": ["Vertex0", "Vertex3", "Vertex2", "Vertex1"], "offset": 12, "spacing": 8, "format": "%.1f"})
    C("td_dimset", "too few", {"view": "Front", "refs": ["Vertex0", "Vertex1"]})
    C("td_dimset", "bad type", {"view": "Front", "type": "angle", "refs": ["Vertex0", "Vertex1", "Vertex2"]})
    C("td_dimset", "bad style", {"view": "Front", "style": "ladder", "refs": ["Vertex0", "Vertex1", "Vertex2"]})
    C("td_dimset", "no such view", {"view": "Nope", "refs": ["Vertex0", "Vertex1", "Vertex2"]})
    C("td_dimset", "a bad reference midway", {"view": "Front", "refs": ["Vertex0", "Vertex1", "Vertex99"]})
    C("td_dimset", "lines late", {"view": "Front", "refs": ["Vertex0", "Vertex1", "Vertex2"]}, None, late_edges=True)

    def dimensioned(s):
        b = s.box()
        v = s.view(s.page(), "Front", body=b)
        s.dim(v, ["Edge0"], "Length")
        s.dim(v, ["Edge4"], "Bore", "Diameter")

    C("td_tolerance", "plus minus", {"dimension": "Length", "plus": 0.1}, dimensioned)
    C("td_tolerance", "a fit", {"dimension": "Bore", "fit": "H7"}, dimensioned)
    C("td_tolerance", "a fit again", {"dimension": "Bore", "fit": "H7", "format": "%.2f H7"}, dimensioned)
    C("td_tolerance", "bad fit", {"dimension": "Bore", "fit": "nonsense"}, dimensioned)
    C("td_tolerance", "cleared", {"dimension": "Length", "clear": True}, dimensioned)
    C("td_tolerance", "cleared and set", {"dimension": "Length", "clear": True, "plus": 0.3, "minus": 0.1, "basic": False, "label": ""}, dimensioned)
    C("td_tolerance", "no such dimension", {"dimension": "Nope", "plus": 1}, dimensioned)
    C("td_tolerance", "not a dimension", {"dimension": "Front", "plus": 1}, dimensioned)

    C("td_gdt", "on a feature", {"view": "Front", "on": "Edge1", "characteristic": "flatness", "tolerance": 0.05})
    C("td_gdt", "a frame of two, placed", {"view": "Front", "on": {"point": [40, 0, 20]}, "at": [200, 150], "height": 5,
                                           "frame": [{"characteristic": "position", "tolerance": 0.1, "diameter": True, "modifier": "M", "datums": ["A", "B"]}, {"characteristic": "perpendicularity", "tolerance": 0.02, "datums": ["A"]}]})
    C("td_gdt", "under a dimension", {"dimension": "Bore", "characteristic": "circularity", "tolerance": 0.01}, dimensioned)
    C("td_gdt", "under a dimension, placed off the paper", {"dimension": "Bore", "characteristic": "circularity", "tolerance": 0.01, "at": [999, 0]}, dimensioned)
    C("td_gdt", "nothing to say", {"view": "Front", "on": "Edge1"})
    C("td_gdt", "bad characteristic", {"view": "Front", "on": "Edge1", "characteristic": "wobble", "tolerance": 1})
    C("td_gdt", "no feature", {"view": "Front", "characteristic": "flatness", "tolerance": 0.05})
    C("td_gdt", "bad feature", {"view": "Front", "on": "Edge50", "characteristic": "flatness", "tolerance": 0.05})
    C("td_gdt", "no such view", {"view": "Nope", "on": "Edge1", "characteristic": "flatness", "tolerance": 0.05})
    C("td_gdt", "lines late", {"view": "Front", "on": "Edge1", "characteristic": "flatness", "tolerance": 0.05}, None, late_edges=True)

    for ref in ("Edge0", "Edge1", "Edge2", "Edge3"):
        C("td_datum", f"on {ref}", {"view": "Front", "letter": "A", "on": ref})
    C("td_datum", "placed, taller", {"view": "Front", "letter": "B", "on": "Vertex0", "at": [50, 50], "height": 5})
    C("td_datum", "no letter", {"view": "Front", "on": "Edge0"})
    C("td_datum", "bad letter", {"view": "Front", "letter": "AB3", "on": "Edge0"})
    C("td_datum", "bad feature", {"view": "Front", "letter": "A", "on": "Nope"})
    C("td_datum", "no such view", {"view": "Nope", "letter": "A", "on": "Edge0"})

    C("td_note", "two lines", {"text": "DEBURR ALL EDGES\nRa 3.2"}, page)
    C("td_note", "placed, sized", {"text": 5, "at": [100, 20], "size": 3.5, "page": "Drawing"}, page)
    C("td_note", "no text", {}, page)
    C("td_note", "at off the paper", {"text": "x", "at": [0, -1]}, page)
    C("td_note", "no page", {"text": "x"}, none)

    C("td_balloon", "numbered", {"view": "Front", "on": "Edge4"})
    C("td_balloon", "with text, placed", {"view": "Front", "on": "Vertex2", "text": 7, "at": [10, 12]})
    C("td_balloon", "a page that keeps no number", {"view": "Front", "on": "Edge4"}, lambda s: (drawing(s), s.doc.Objects[1].__dict__.pop("NextBalloonIndex")))
    C("td_balloon", "bad feature", {"view": "Front", "on": "Face1"})
    C("td_balloon", "bad at", {"view": "Front", "on": "Edge4", "at": "there"})
    C("td_balloon", "lines late", {"view": "Front", "on": "Edge4"}, None, late_edges=True)

    def tabled(s):
        page(s)
        s.sheet("Parts", {"A1": "Item", "B1": "Qty", "A2": "Bracket", "B2": "2"})

    C("td_table", "the filled cells", {}, tabled)
    C("td_table", "a range, placed, sized", {"sheet": "Parts", "range": "A1:B1", "at": [200, 180], "size": 5}, tabled)
    C("td_table", "bad range", {"range": "A1:??"}, tabled)
    C("td_table", "empty sheet", {}, lambda s: (page(s), s.sheet("Empty")))
    C("td_table", "no sheet", {}, page)
    C("td_table", "which sheet", {}, lambda s: (tabled(s), s.sheet("Other")))
    C("td_table", "no page", {}, lambda s: s.sheet("Parts", {"A1": "x"}))

    def sectioned(dx, dy):
        def prep(s):
            b = s.box()
            p = s.page()
            v = s.view(p, "Front", body=b)
            s.view(p, "Section A", "TechDraw::DrawViewSection", body=b, BaseView=v, X=100.0 + dx, Y=120.0 + dy)

        return prep

    C("td_section_position", "beside", {"section": "Section A"}, sectioned(80, 3))
    C("td_section_position", "above", {"section": "Section A"}, sectioned(4, 60))
    C("td_section_position", "not a section", {"section": "Front"}, sectioned(80, 3))
    C("td_section_position", "no such view", {"section": "Nope"}, sectioned(80, 3))

    def grouped(s):
        b = s.box()
        p = s.page()
        g = s.doc.new("TechDraw::DrawProjGroup", "ProjGroup")
        g.__dict__.update(X=100.0, Y=100.0, Source=[b])
        item = s.doc.new("TechDraw::DrawProjGroupItem", "Front")
        item.__dict__.update(Label="Front", Source=[b], X=0.0, Y=0.0)
        item.InList.append(g)
        g.__dict__["Views"] = [item]
        p.__dict__["Views"] = [g]
        g.InList.append(p)
        s.view(p, "Section A", "TechDraw::DrawViewSection", body=b, BaseView=item, X=180.0, Y=95.0)

    C("td_section_position", "of a view in a group", {"section": "Section A"}, grouped)
    C("td_dim", "in a group", {"view": "Front", "refs": ["Edge0"]}, grouped)
    # ================= batch C: leaders, finishes, areas, dimension text =================
    C("td_leader", "bare", {"view": "Front", "on": "Edge1"})
    C("td_leader", "with text", {"view": "Front", "on": "Edge1", "text": "BREAK EDGE\n0.5 MAX"})
    C("td_leader", "to the left, sized", {"view": "Front", "on": "Edge3", "text": "x", "at": [20, 150], "size": 5})
    C("td_leader", "bad feature", {"view": "Front", "on": 7})
    C("td_leader", "at off the paper", {"view": "Front", "on": "Edge1", "at": [300, 0]})
    C("td_leader", "lines late", {"view": "Front", "on": "Edge1"}, None, late_edges=True)
    C("td_leader", "no such view", {"view": "Nope", "on": "Edge1"})

    C("td_finish", "on a leader", {"view": "Front", "on": "Edge0", "ra": 3.2})
    C("td_finish", "on an upper edge", {"view": "Front", "on": "Edge2", "ra": "1.6", "removal": "prohibited"})
    C("td_finish", "on the surface", {"view": "Front", "on": "Edge0", "ra": 0.8, "onSurface": True, "process": "ground", "lay": "=", "allowance": "0.2", "height": 5})
    C("td_finish", "placed", {"view": "Front", "on": "Edge0", "at": [150, 60]})
    C("td_finish", "placed off the paper", {"view": "Front", "on": "Edge0", "at": [150, 600]})
    C("td_finish", "bad removal", {"view": "Front", "on": "Edge0", "removal": "maybe"})
    C("td_finish", "no feature", {"view": "Front", "ra": 3.2})
    C("td_finish", "bad feature", {"view": "Front", "on": "Edge40"})
    C("td_finish", "lines late", {"view": "Front", "on": "Edge0"}, None, late_edges=True)

    C("td_area", "a face", {"view": "Front", "face": "Box.Face1"})
    C("td_area", "set", {"view": "Front", "face": "Box.Face2", "unit": "cm2", "decimals": 3, "format": "{value} {unit} wetted", "at": [200, 100], "size": 5})
    C("td_area", "another unit", {"view": "Front", "face": "Box.Face1", "unit": "in2"})
    C("td_area", "a whole body", {"view": "Front", "face": "Box"})
    C("td_area", "no such face", {"view": "Front", "face": "Box.Face9"})
    C("td_area", "no such body", {"view": "Front", "face": "Nope.Face1"})
    C("td_area", "at off the paper", {"view": "Front", "face": "Box.Face1", "at": [-5, 5]})
    C("td_area", "no geometry yet", {"view": "Front", "face": "Box.Face1"}, None, no_edges=True)
    C("td_area", "lines late", {"view": "Front", "face": "Box.Face1"}, None, late_edges=True)

    C("td_dim_format", "decimals and a prefix", {"dims": "Bore", "decimals": 3, "prefix": "diameter"}, dimensioned)
    C("td_dim_format", "a format, both", {"dims": ["Length", "Bore"], "format": "L %.1f mm"}, dimensioned)
    C("td_dim_format", "prefix off, one more decimal", {"dims": ["Length"], "format": "L %.1f mm", "removePrefix": True, "more": 1}, dimensioned)
    C("td_dim_format", "fewer decimals", {"dims": ["Length"], "more": -5}, dimensioned)
    C("td_dim_format", "decimals where none are named", {"dims": ["Length"], "format": "%g", "decimals": 1}, dimensioned)
    C("td_dim_format", "a count", {"dims": ["Bore"], "prefix": "count", "count": 4}, dimensioned)
    C("td_dim_format", "a count of two, square, text", {"dims": ["Bore"], "prefix": "count"}, dimensioned)
    C("td_dim_format", "square", {"dims": ["Length"], "prefix": "square"}, dimensioned)
    C("td_dim_format", "a text prefix on a label", {"dims": ["Length"], "format": "REF", "prefix": "2 PLACES "}, dimensioned)
    C("td_dim_format", "bad decimals", {"dims": ["Length", "Bore"], "decimals": 12}, dimensioned)
    C("td_dim_format", "no dims", {}, dimensioned)
    C("td_dim_format", "no such dimension", {"dims": ["Nope"]}, dimensioned)
    C("td_dim_format", "no text yet", {"dims": ["Length"], "decimals": 0}, dimensioned, no_text=True)
    # ================= special dimensions, aligning, repair =================
    C("td_dim_special", "the whole width", {"view": "Front", "kind": "extent_h"})
    C("td_dim_special", "the height of two edges", {"view": "Front", "kind": "extent_v", "refs": ["Edge0", "Edge2"]})
    C("td_dim_special", "no extent made", {"view": "Front", "kind": "extent_h"}, None, no_extent=True)
    C("td_dim_special", "a chamfer", {"view": "Front", "kind": "chamfer_h", "refs": ["Vertex0", "Vertex2"]})
    C("td_dim_special", "a chamfer, upright, placed", {"view": "Front", "kind": "chamfer_v", "refs": ["Vertex0", "Vertex2"], "at": [10, 10]})
    C("td_dim_special", "a chamfer of one point", {"view": "Front", "kind": "chamfer_h", "refs": ["Vertex0"]})
    C("td_dim_special", "an arc's length", {"view": "Front", "kind": "arc_length", "refs": ["Edge4"], "decimals": 1})
    C("td_dim_special", "an arc's length of a line", {"view": "Front", "kind": "arc_length", "refs": ["Edge0"]})
    C("td_dim_special", "an arc's length of two", {"view": "Front", "kind": "arc_length", "refs": ["Edge4", "Edge0"]})
    C("td_dim_special", "an axonometric length", {"view": "Front", "kind": "axo_length", "refs": ["Edge0", "Edge1"]})
    C("td_dim_special", "an axonometric length of one", {"view": "Front", "kind": "axo_length", "refs": ["Edge0"]})
    C("td_dim_special", "an axonometric length of a circle", {"view": "Front", "kind": "axo_length", "refs": ["Edge4", "Edge1"]})
    C("td_dim_special", "bad kind", {"view": "Front", "kind": "ordinate"})
    C("td_dim_special", "no kind", {"view": "Front"})
    C("td_dim_special", "bad reference", {"view": "Front", "kind": "chamfer_h", "refs": ["Vertex0", "Vertex44"]})
    C("td_dim_special", "bad at", {"view": "Front", "kind": "chamfer_h", "refs": ["Vertex0", "Vertex2"], "at": "left"})
    C("td_dim_special", "lines late", {"view": "Front", "kind": "extent_h"}, None, late_edges=True)
    C("td_dim_special", "no such view", {"view": "Nope", "kind": "extent_h"})

    def three_dims(s):
        dimensioned(s)
        v = s.doc.Objects[3]
        s.doc.Objects[5].__dict__.update(X=30.0, Y=-10.0)
        d = s.dim(v, ["Edge1"], "Third")
        d.__dict__.update(X=60.0, Y=40.0)

    C("td_dim_align", "horizontal", {"dims": ["Length", "Bore", "Third"]}, three_dims)
    C("td_dim_align", "vertical", {"dims": ["Bore", "Third"], "direction": "vertical"}, three_dims)
    C("td_dim_align", "oblique", {"dims": ["Length", "Bore", "Third"], "direction": "oblique"}, three_dims)
    C("td_dim_align", "oblique of two", {"dims": ["Length", "Bore"], "direction": "oblique"}, three_dims)
    C("td_dim_align", "bad direction", {"dims": ["Length", "Bore"], "direction": "radial"}, three_dims)
    C("td_dim_align", "no dims", {}, three_dims)
    C("td_dim_align", "no such dimension", {"dims": ["Length", "Nope"]}, three_dims)

    C("td_dim_repair", "new references", {"dimension": "Length", "refs": ["Vertex0", "Vertex1"]}, dimensioned)
    C("td_dim_repair", "on a named view", {"dimension": "Length", "view": "Front", "refs": ["Edge2"]}, dimensioned)
    C("td_dim_repair", "no refs", {"dimension": "Length"}, dimensioned)
    C("td_dim_repair", "cannot be measured", {"dimension": "Length", "refs": ["Edge2"]}, dimensioned, cannot_measure=True)
    C("td_dim_repair", "bad reference", {"dimension": "Length", "refs": ["Edge99"]}, dimensioned)
    C("td_dim_repair", "no such dimension", {"dimension": "Nope", "refs": ["Edge2"]}, dimensioned)
    C("td_dim_repair", "no dimension named", {"refs": ["Edge2"]}, dimensioned)
    C("td_dim_repair", "lines late", {"dimension": "Length", "refs": ["Edge2"]}, dimensioned, late_edges=True)
    return out

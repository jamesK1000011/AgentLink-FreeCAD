# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_bim_data.py runs through the old handler and the new
# data entry of each converted BIM tool, on the stand-in FreeCAD
# (tests/_bim_standin.py): its normal paths and each of its refusals.
# "model call N" is call N of docs/hardening/models/bimcam-bim-model.json.

# Each converted tool and its group.
CONVERTED = {
    "bim_wall": "bim", "bim_section": "bim", "bim_reference": "bim_gaps",
    "bim_opening": "bim", "bim_structure": "bim", "bim_profiles": "bim", "bim_member": "bim", "bim_roof": "bim", "bim_stairs": "bim",
    "bim_space": "bim", "bim_building": "bim", "bim_schedule": "bim", "bim_export": "bim", "bim_import": "bim", "bim_curtain_wall": "bim",
    "bim_rebar": "bim", "bim_panel": "bim", "bim_grid": "bim", "bim_material": "bim",
    "bim_frame": "bim", "bim_truss": "bim", "bim_fence": "bim", "bim_covering": "bim", "bim_layers": "bim", "bim_ifc": "bim", "bim_quantities": "bim",
    "bim_preflight": "bim", "bim_edit": "bim",
    "bim_component": "bim_gaps", "bim_panel_out": "bim_gaps", "bim_nest": "bim_gaps", "bim_ifc_brep": "bim_gaps", "bim_views": "bim_gaps",
    "bim_image_plane": "bim_gaps", "bim_library": "bim_gaps", "bim_reextrude": "bim_gaps", "bim_rewire": "bim_gaps", "bim_glue": "bim_gaps",
    "bim_trash": "bim_gaps", "bim_reorder": "bim_gaps",
}
# Each tool of the three family files kept as code, and why: none. (docs/data-tools.md has the line where code is still right.)
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("bim_wall", "model call 1"): {"object": "Outer walls", "length": 28000.0, "width": 250.0, "height": 2600.0, "align": "right", "base": "Outer walls line", "step": 1},
    ("bim_wall", "neither"): ["refused", "invalid_input", "points [[x, y] …] (the wall's line, mm) or base (a sketch or wire's label): one of them."],
    ("bim_wall", "base without edges"): ["refused", "invalid_input", "base: Empty has no edges to run a wall along; give a sketch or wire, or points [[x, y] …]."],
    ("bim_wall", "base with edges"): {"length": 7000.0},
    ("bim_section", "model call 41"): {"cuts": ["Bare", "Hollow", "Plot"], "object": "Plan cut"},
    ("bim_section", "nothing to cut"): ["refused", "invalid_input", "Nothing to cut: no BIM objects here; give objects, or make some first (bim_wall …)."],
    ("bim_reference", "part and name"): {"reference": "Xref", "file": "other.FCStd", "part": "Body", "step": None},
    ("bim_reference", "no file"): ["refused", "not_found", "path '/nowhere/x.FCStd': no such file. Give the full path of an .FCStd (or .ifc, .dxf) to reference."],
    ("bim_opening", "model call 3"): {"object": "Front door", "ifc": "Door", "wall": "Outer walls", "wallCut_m3": 0.6615, "opening": "Front door opening", "at": 1500.0,
                                      "preset": "door: a 50 mm frame round a panel (FreeCAD's window presets need its window)"},
    ("bim_opening", "model call 6"): ["refused", "invalid_input", "The opening runs past the end of that straight stretch of wall (8000 mm long, the opening 7500 … 9000 along it): a smaller at or width; an opening cannot cross a corner."],
    ("bim_opening", "sill and height above the wall"): ["refused", "invalid_input", "sill + height is 3000 mm, above the wall's 2600 mm: a lower sill or height."],
    ("bim_opening", "not cut"): {"wallCut_m3": 0.0, "warning": "The wall was not cut: the opening may be outside it (a wall moved after it was made, or a sill above its top). view_render shows where it landed; object_delete removes it and its opening."},
    ("bim_structure", "model call 8"): {"object": "Floor slab", "ifc": "Slab", "kind": "slab", "volume_m3": 7.2},
    ("bim_structure", "kind wrong"): ["refused", "invalid_input", "kind: column, beam, slab, footing."],
    ("bim_profiles", "model call 13"): {"count": 2, "categories": ["HEB", "IPE", "Timber"]},
    ("bim_member", "model call 14"): {"object": "Steel beam", "profile": "HEB200", "category": "HEB", "length": 2000.0, "ifc": "Beam", "mass_kg": 122.5, "kgPerM": 61.2},
    ("bim_member", "not in the library, near"): ["refused", "invalid_input", "profile: 'HEB999' is not in the library — near: HEB200, HEB220 (bim_profiles lists them)."],
    ("bim_roof", "model call 15"): {"object": "Roof", "edges": 4, "angles": [30.0, 90.0, 30.0, 90.0], "runs": [3000.0, 4000.0, 3000.0, 4000.0], "ridge": 1732.1, "flipped": None},
    ("bim_roof", "model call 16"): {"object": "Hip roof cw", "flipped": True, "ridge": 1154.7, "runs": [3000.0, 2000.0, 3000.0, 2000.0]},
    ("bim_stairs", "model call 17"): {"object": "Stairs", "steps": 15, "riser": 173.3, "going": 280.0, "blondel": 626.7, "note": None},
    ("bim_space", "model call 18"): {"object": "Living room", "area_m2": 20.212, "use": "Room", "ifc": "Space"},
    ("bim_space", "model call 19"): ["refused", "invalid_input", "use 'Bedroom': not one of FreeCAD's space types. Near: Room, Office, Corridor / Transition, Restrooms, Dining Area, Food Preparation, Stairs, Lobby. Leave use out for Undefined; put a free name in name."],
    ("bim_building", "model call 22"): {"object": "House", "levels": ["Ground floor", "Roof level"], "site": "Plot", "ifc": "Building"},
    ("bim_schedule", "a sheet by name"): {"sheet": "House schedule", "step": 1},
    ("bim_export", "model call 60"): {"schema": "IFC4", "objects": ["House"], "readBack": {"IfcWall": 2, "IfcSlab": 1}, "bytes": 52},
    ("bim_export", "a bare classification"): ["refused", "invalid_state", "classification of Outer walls: FreeCAD's IFC export needs \"<system> <code>\" (\"Uniclass Ss_25_10_30\") — bim_ifc { objects, classification } sets it so, \"\" clears it. Nothing was written."],
    ("bim_import", "model call 68"): {"objects": 3, "byType": {"Wall": 2, "Slab": 1}, "read": "FreeCAD's IFC importer"},
    ("bim_curtain_wall", "model call 46"): {"object": "Glazing", "length": 6000.0, "stretches": 1, "height": 3000.0},
    ("bim_rebar", "model call 30"): {"object": "Slab bars", "made": "FreeCAD's rebar", "bars": 31, "spacing": 197.6, "totalLength_m": 246.14, "mass_kg": 218.53},
    ("bim_rebar", "FreeCAD's rebar needs its window"): {"made": "bars made here (FreeCAD's rebar needs its window)", "ifc": "Reinforcing Bar", "bars": 4},
    ("bim_panel", "model call 47"): {"object": "Shelf", "thickness": 18.0, "volume_m3": 0.013},
    ("bim_grid", "model call 37"): {"axes": ["Grid X", "Grid Y"], "lines": {"x": [0.0, 4000.0, 8000.0], "y": [0.0, 3000.0, 6000.0]}, "length": 8000.0, "step": 1},
    ("bim_ifc", "a bare classification"): ["refused", "invalid_input", "classification 'Ss_25_10_30': the system's name, a space, the code — \"Uniclass Ss_25_10_30\", \"OmniClass 21-02 10\" (FreeCAD's IFC export reads it so); \"\" clears it."],
    ("bim_ifc", "model call 27"): {"objects": [{"object": "Outer walls", "ifc": "Wall", "classification": "Uniclass Ss_25_10_30",
                                                "properties": {"Pset_WallCommon": {"IsExternal": "True", "FireRating": "REI60"}}}]},
    ("bim_edit", "model call 35"): {"object": "Inner wall", "op": "cut"},
    ("bim_fence", "model call 44"): {"object": "Fence", "pathLength_mm": 10000.0, "NumberOfSections": 5, "NumberOfPosts": 6},
    ("bim_grid", "count of one"): ["refused", "invalid_input", "count: 2 or more grid lines (count - 1 spaces of spacing mm)."],
    ("bim_trash", "model call 57"): {"trash": ["Post", "Held"], "step": None},
    ("bim_reorder", "model call 58"): {"group": "Ground floor", "order": ["Floor slab", "Inner wall", "Outer walls"]},
    ("bim_material", "model call 24"): {"material": "Brick", "data": {"Density": "1800 kg/m^3", "Description": "Clay brick", "DiffuseColor": "(0.7098, 0.3255, 0.2353)"}, "on": ["Inner wall"]},
}
# Refusals written in the data that no case here reaches: none.
UNREACHED = []

SQUARE = [[0, 0], [8000, 0], [8000, 6000], [0, 6000]]


def cases(fc, tmp):
    import os

    Obj, Shape, V, arch = fc.Obj, fc.Shape, fc.Vec, fc.arch

    def flags(**kw):
        fc.state["flags"].update(kw)

    def without(*names):
        flags(missing=set(names))

    def lines(*lengths):
        """A wire of straight stretches of these lengths, end to end along X."""
        pts, x = [V(0, 0, 0)], 0.0
        for n in lengths:
            x += n
            pts.append(V(x, 0, 0))
        return Shape("wire", pts, edges=[fc.edge(pts[i], pts[i + 1]) for i in range(len(lengths))])

    def thing(s, name, type_="Part::Feature", **kw):
        return s.doc.new(type_, name, **kw)

    def outline(pts, z=0.0):
        return fc.polygon([V(p[0], p[1], p[2] if len(p) > 2 else z) for p in pts + pts[:1]])

    def wall(s, name, pts, width=200.0, height=3000.0, align="Center", closed=False):
        base = thing(s, name + " line", Shape=fc.polygon([V(*p) for p in pts + (pts[:1] if closed else [])]))
        w = arch.makeWall(base, width=width, height=height, align=align)
        w.__dict__["Label"] = name
        return w

    def slab(s, name, pts=SQUARE, t=150.0, ifc="Slab"):
        base = thing(s, name + " outline", Shape=fc.face(outline(pts)))
        o = arch.makeStructure(base, height=t)
        o.__dict__.update(Label=name, IfcType=ifc)
        return o

    def empty(s):
        pass

    def bases(s):
        s.doc.add(Obj("Sketch", "Sketcher::SketchObject", Shape=lines(4000, 3000)))
        s.doc.add(Obj("Empty", "Part::Feature", Shape=Shape("wire")))
        s.doc.add(Obj("Null", "Part::Feature", Shape=Shape("wire", edges=[fc.edge(V(), V(5, 0, 0))], null=True)))
        s.doc.add(Obj("Sheet", "Spreadsheet::Sheet"))
        s.doc.add(Obj("Wall", "Part::Feature"))
        thing(s, "Closed", Shape=fc.face(outline(SQUARE)))
        thing(s, "ClosedWire", Shape=outline(SQUARE))
        thing(s, "Solid", Shape=fc.box(1000, 2000, 300))

    def walls(s):
        wall(s, "Outer walls", SQUARE, 250.0, 2600.0, "Right", closed=True)
        wall(s, "Inner wall", [[4000, 250], [4000, 5750]], 150.0, 2600.0)
        thing(s, "Box", Shape=fc.box(10, 10, 10))
        s.doc.add(Obj("Bare", "Part::FeaturePython", IfcType="Wall", Base=None, Height=3000.0))
        s.doc.add(Obj("Hollow", "Part::FeaturePython", IfcType="Wall", Subtractions=[], Shape=fc.face(outline(SQUARE))))

    def house(s):
        walls(s)
        sl = slab(s, "Floor slab")
        level = arch.makeFloor([s.doc.getObject("Wall"), s.doc.getObject("Wall001"), sl])
        level.__dict__["Label"] = "Ground floor"
        roof = arch.makeFloor([])
        roof.__dict__["Label"] = "Roof level"
        b = arch.makeBuilding([level, roof])
        b.__dict__["Label"] = "House"
        site = arch.makeSite([b])
        site.__dict__["Label"] = "Plot"
        s.doc.add(Obj("Sheet", "Spreadsheet::Sheet", IfcType="x", Label="Schedule"))

    def levels(s):
        for n in ("Ground floor", "Roof level"):
            arch.makeFloor([]).__dict__["Label"] = n

    def model(s):
        """One of each kind the schedule reads."""
        house(s)
        w = s.doc.getObject("Wall")
        hole = thing(s, "Hole", Shape=fc.box(1000, 270, 2450))
        w.__dict__["Subtractions"] = [hole]
        s.doc.add(Obj("Door", "Part::FeaturePython", IfcType="Door", Width=1000.0, Height=2450.0, Shape=fc.box(1000, 100, 2450)))
        s.doc.add(Obj("Win", "Part::FeaturePython", IfcType="Window", Width=1200.0, Height=1200.0, Shape=fc.box(1200, 100, 1200), Proxy=fc.proxy("_Window")))
        slab(s, "Pad", [[0, 0], [500, 0], [500, 500], [0, 500]], 400.0, "Footing")
        col = arch.makeStructure(None, length=250.0, width=250.0, height=2250.0)
        col.__dict__.update(Label="Porch column", IfcType="Column")
        room = thing(s, "Room solid", Shape=fc.face(outline(SQUARE)).extrude(V(0, 0, 2600)))
        arch.makeSpace([room]).__dict__.update(Label="Living room", SpaceType="Room")
        s.doc.add(Obj("Bars", "Part::FeaturePython", IfcType="Reinforcing Bar", Shape=fc.box(10, 10, 1000)))
        s.doc.add(Obj("Roof", "Part::FeaturePython", IfcType="Roof", Shape=fc.box(8000, 6000, 100)))
        s.doc.add(Obj("Flight", "Part::FeaturePython", IfcType="Stair", Shape=fc.box(4000, 1000, 100)))
        s.doc.add(Obj("NullThing", "Part::FeaturePython", IfcType="Beam", Shape=Shape(null=True)))
        s.doc.recompute()

    def then(setup, **kw):
        def run(s):
            setup(s)
            flags(**kw)

        return run

    def less(setup, *names):
        def run(s):
            setup(s)
            without(*names)

        return run


    def floor(s):
        thing(s, "Floor slab", Shape=fc.box(1200, 1200, 150, V(-600, -600, -150)))
        thing(s, "Far slab", Shape=fc.box(1200, 1200, 150, V(50000, 0, 500)))
        dome = fc.box(100, 100, 100)
        dome.Faces[0].flat = False
        thing(s, "Dome", Shape=dome)

    def tagged(s):
        walls(s)
        s.doc.getObject("Wall").__dict__.update(StandardCode="Uniclass Ss_25", IfcProperties={"FireRating": "Pset_WallCommon;;IfcLabel;;REI60", "Odd": "x;;y"})

    def weighed(s):
        """The schedule's model with materials: one with a density, one without, a build-up."""
        model(s)
        brick = arch.makeMaterial("Brick")
        brick.__dict__.update(Label="Brick", Material={"Density": "1800 kg/m^3"})
        bare = arch.makeMaterial("Paint")
        bare.__dict__.update(Label="Paint", Material={"Density": "heavy"})
        mix = arch.makeMultiMaterial()
        mix.__dict__.update(Label="Build-up", Materials=[brick, brick], Thicknesses=[100.0, fc.Quantity(50.0)])
        thin = arch.makeMultiMaterial()
        thin.__dict__.update(Label="Unknown build-up", Materials=[brick, bare], Thicknesses=[100.0, 50.0])
        s.doc.getObject("Wall").__dict__.update(Material=mix, VerticalArea=fc.Quantity(72.8e6), PerimeterLength=fc.Quantity(28000.0))
        s.doc.getObject("Wall001").__dict__["Material"] = brick
        s.doc.getObject("Structure").__dict__["Material"] = bare
        s.doc.getObject("Structure001").__dict__["Material"] = thin

    def shown(s):
        walls(s)
        s.doc.add(Obj("Top", "Part::FeaturePython", IfcType="Roof", Proxy=fc.proxy("_Roof"), Visibility=True))

    def looped(s):
        a = slab(s, "Floor slab")
        b = slab(s, "Pad")
        b.OutList.append(a)

    def three_walls(s):
        for i, n in enumerate("ABC"):
            wall(s, n, [[0, i * 1000], [3000, i * 1000]])
        wall(s, "Thick", [[0, 9000], [3000, 9000]], width=400.0)

    def comps(s):
        src = arch.makeComponent(thing(s, "Solid", Shape=fc.box(1000, 2000, 300)))
        src.__dict__.update(Label="Comp", Height=300.0, IfcType="Furniture", Description="a block")
        c = arch.cloneComponent(src)
        c.__dict__.update(Label="Copy", Description="", Stays="only here")
        thing(s, "Plain", Shape=fc.box(1, 1, 1))

    def panels(s):
        for n in ("Shelf", "Side"):
            arch.makePanel(thing(s, n + " outline", Shape=fc.face(outline([[0, 0], [1200, 0], [1200, 600], [0, 600]]))), thickness=18.0).__dict__["Label"] = n
        thing(s, "Box", Shape=fc.box(10, 10, 10))
        thing(s, "Lid", Shape=fc.box(10, 10, 10))

    def flats(s):
        thing(s, "Sheet", Shape=fc.face(outline([[0, 0], [2440, 0], [2440, 1220], [0, 1220]])))
        for n in ("P1", "P2"):
            thing(s, n, Shape=fc.face(outline([[0, 0], [600, 0], [600, 300], [0, 300]])))
        thing(s, "Block", Shape=fc.box(10, 10, 10))
        thing(s, "Line", Shape=lines(100))
        s.doc.add(Obj("Bare", "App::FeaturePython"))

    def solids(s):
        blk = arch.makeStructure(None, length=400.0, width=300.0, height=2000.0)
        blk.__dict__.update(Label="Block", StandardCode="Uniclass X", Material=None)
        lv = arch.makeFloor([blk])
        lv.__dict__["Label"] = "Ground floor"
        s.doc.add(Obj("Loose", "App::FeaturePython")).__dict__["Group"] = []
        arch.makePanel(None, length=1000.0, width=500.0, thickness=18.0).__dict__["Label"] = "Board"
        holed = fc.box(500, 500, 100)
        holed.Faces[0].Wires = holed.Faces[0].Wires * 2
        thing(s, "Holed", Shape=holed)

    def loose_lines(s):
        thing(s, "L1", Shape=fc.part.makeLine(V(0, 0, 0), V(1000, 0, 0)))
        thing(s, "L2", Shape=fc.part.makeLine(V(1000, 0, 0), V(1000, 500, 0)))
        thing(s, "L3", Shape=fc.part.makeLine(V(5000, 0, 0), V(6000, 0, 0)))
        arc = fc.part.makeLine(V(0, 0, 0), V(10, 10, 0))
        arc.curved = True
        thing(s, "Arc", Shape=arc)
        thing(s, "Dot", Shape=Shape("vertex", [V(1, 1, 1)]))
        thing(s, "Blank", Shape=Shape(null=True))
        s.doc.add(Obj("Other", "Mesh::Feature", Shape=fc.box(1, 1, 1)))

    def binned(s):
        house(s)
        bin_ = s.doc.addObject("App::DocumentObjectGroup", "Trash")
        post = thing(s, "Post", Shape=fc.box(1, 1, 1))
        own = thing(s, "Post sketch")
        shared = thing(s, "Shared sketch")
        post.OutList.extend([own, shared])
        own.InList.append(post)
        shared.InList.extend([post, s.doc.getObject("Wall")])
        bin_.addObject(post)
        held = thing(s, "Held", Shape=fc.box(1, 1, 1))
        bin_.addObject(held)
        held.InList.append(s.doc.getObject("Wall"))

    def grouped_box(s):
        walls(s)
        box = s.doc.getObject("Box")
        g = s.doc.add(Obj("Folder", "App::DocumentObjectGroup", Group=[box]))
        g.__dict__["removeObject"] = None  # a group this FreeCAD gives no removeObject
        del g.__dict__["removeObject"]
        box.InList.append(g)
        plain = s.doc.add(Obj("Holder", "App::FeaturePython", Group=[box], refuses=()))
        box.InList.append(plain)

    image = os.path.join(tmp, "plan.png")
    with open(image, "w") as f:
        f.write("not really a picture")
    library = os.path.join(tmp, "parts")
    os.makedirs(os.path.join(library, "sub"))
    for n in ("chair wood.step", "chair steel.stl", "notes.txt", os.path.join("sub", "Table.FCStd")):
        with open(os.path.join(library, n), "w") as f:
            f.write("x")
    file = os.path.join(tmp, "other.FCStd")
    with open(file, "w") as f:
        f.write("x")
    ifc_file = os.path.join(tmp, "house_edited.ifc")
    with open(ifc_file, "w") as f:
        f.write("ISO-10303-21;")
    sq = SQUARE
    out = [
        ("bim_wall", "model call 1", empty, {"points": sq, "closed": True, "width": 250, "height": 2600, "align": "right", "name": "Outer walls"}),
        ("bim_wall", "model call 2", empty, {"points": [[4000, 250], [4000, 5750]], "width": 150, "height": 2600, "align": "center", "name": "Inner wall"}),
        ("bim_wall", "defaults", empty, {"points": [[0, 0], [1000, 0, 500]]}),
        ("bim_wall", "label taken", bases, {"points": [[0, 0], [1000, 0]]}),
        ("bim_wall", "base with edges", bases, {"base": "Sketch", "align": "left", "height": 2400}),
        ("bim_wall", "base and points", bases, {"base": "sketch", "points": sq, "closed": True}),
        ("bim_wall", "base without edges", bases, {"base": "Empty"}),
        ("bim_wall", "base with a null shape", bases, {"base": "Null"}),
        ("bim_wall", "base with no shape", bases, {"base": "Sheet"}),
        ("bim_wall", "base not there", bases, {"base": "Nope"}),
        ("bim_wall", "base not a name", bases, {"base": 5}),
        ("bim_wall", "empty base, points", bases, {"base": "", "points": [[0, 0], [0, 900]]}),
        ("bim_wall", "neither", empty, {}),
        ("bim_wall", "empty points", empty, {"points": []}),
        ("bim_wall", "one point", empty, {"points": [[0, 0]]}),
        ("bim_wall", "points not a list", empty, {"points": "here"}),
        ("bim_wall", "a point not numbers", empty, {"points": [[0, 0], ["a", 1]]}),
        ("bim_wall", "the same point twice", empty, {"points": [[0, 0], [0, 0], [5, 5]]}),
        ("bim_wall", "closed on two points", empty, {"points": [[0, 0], [10, 0]], "closed": True}),
        ("bim_wall", "closed, already closed", empty, {"points": sq + [[0, 0]], "closed": 1}),
        ("bim_wall", "align wrong", empty, {"points": sq, "align": "middle"}),
        ("bim_wall", "align not a word", empty, {"points": sq, "align": 3}),
        ("bim_wall", "width zero", empty, {"points": sq, "width": 0}),
        ("bim_wall", "width not a number", empty, {"points": sq, "width": "wide"}),
        ("bim_wall", "height below zero", empty, {"points": sq, "height": -1}),
        ("bim_wall", "width before align", empty, {"width": 0, "align": "middle"}),
        ("bim_wall", "height before align", empty, {"height": True, "align": "middle"}),
        ("bim_wall", "align before the line", empty, {"align": "middle"}),
        ("bim_section", "model call 41", house, {"at": [0, 0, 1200], "normal": [0, 0, 1], "name": "Plan cut"}),
        ("bim_section", "defaults", house, {}),
        ("bim_section", "objects named", house, {"objects": ["Outer walls", "Box"], "normal": [0, 1, 0], "at": [0, 2000]}),
        ("bim_section", "an object not there", house, {"objects": ["Nope"]}),
        ("bim_section", "objects empty", house, {"objects": []}),
        ("bim_section", "label taken", house, {"name": "Plot"}),
        ("bim_section", "nothing to cut", bases, {}),
        ("bim_section", "normal zero", house, {"normal": [0, 0, 0]}),
        ("bim_section", "normal not a direction", house, {"normal": "up"}),
        ("bim_section", "at not a point", house, {"at": [1]}),
        ("bim_section", "normal zero before nothing to cut", bases, {"normal": [0, 0]}),
        ("bim_section", "nothing to cut before at", bases, {"at": "x"}),
        ("bim_section", "an object not there before normal", house, {"objects": ["Nope"], "normal": [0, 0, 0]}),
        ("bim_section", "no maker", less(house, "Arch.makeSectionPlane"), {"objects": ["Nope"], "normal": [0, 0, 0]}),
        ("bim_reference", "the file", empty, {"path": file}),
        ("bim_reference", "part and name", empty, {"path": file, "part": "Body", "name": "Xref"}),
        ("bim_reference", "label taken", bases, {"path": file, "name": "Sketch"}),
        ("bim_reference", "no file", empty, {"path": "/nowhere/x.FCStd"}),
        ("bim_reference", "a folder", empty, {"path": tmp, "name": "x"}),
        ("bim_reference", "no path", empty, {}),
        ("bim_reference", "an empty path", empty, {"path": "", "part": "Body"}),

        ("bim_opening", "model call 3", walls, {"wall": "Outer walls", "kind": "door", "width": 1000, "height": 2450, "at": 1500, "name": "Front door"}),
        ("bim_opening", "model call 4", walls, {"wall": "Outer walls", "kind": "window", "width": 1200, "height": 1200, "at": 5000, "sill": 900, "name": "Front window"}),
        ("bim_opening", "model call 5", walls, {"wall": "Outer walls", "kind": "window", "width": 1500, "height": 1200, "at": 10000, "sill": 900, "name": "Side window"}),
        ("bim_opening", "model call 6", walls, {"wall": "Outer walls", "kind": "window", "width": 1500, "at": 7500}),
        ("bim_opening", "model call 7", walls, {"wall": "Inner wall", "kind": "door", "width": 700, "height": 2100, "at": 2000, "name": "Inner door"}),
        ("bim_opening", "defaults", walls, {"wall": "Inner wall"}),
        ("bim_opening", "a glass door by preset", walls, {"wall": "Inner wall", "preset": "Glass door", "frame": 40, "depth": 80}),
        ("bim_opening", "label taken", walls, {"wall": "Inner wall", "name": "Box"}),
        ("bim_opening", "no wall", walls, {}),
        ("bim_opening", "wall not there", walls, {"wall": "Nope"}),
        ("bim_opening", "preset wrong", walls, {"wall": "Inner wall", "preset": "Porthole"}),
        ("bim_opening", "width zero", walls, {"wall": "Inner wall", "width": 0}),
        ("bim_opening", "height not a number", walls, {"wall": "Inner wall", "height": "tall"}),
        ("bim_opening", "kind wrong", walls, {"wall": "Inner wall", "kind": "gate"}),
        ("bim_opening", "sill not a number", walls, {"wall": "Inner wall", "sill": "low"}),
        ("bim_opening", "at below zero", walls, {"wall": "Inner wall", "at": -1}),
        ("bim_opening", "not a wall", walls, {"wall": "Box"}),
        ("bim_opening", "a wall with no baseline", walls, {"wall": "Bare"}),
        ("bim_opening", "sill and height above the wall", walls, {"wall": "Inner wall", "sill": 1800}),
        ("bim_opening", "at past the end", walls, {"wall": "Inner wall", "at": 6000, "width": 500}),
        ("bim_opening", "frame too wide", walls, {"wall": "Inner wall", "frame": 600}),
        ("bim_opening", "depth zero", walls, {"wall": "Inner wall", "depth": 0}),
        ("crash: bim_opening", "frame not a number", walls, {"wall": "Inner wall", "frame": "thin"}),
        ("bim_opening", "no component maker", less(walls, "Arch.makeComponent"), {"wall": "Inner wall", "kind": "door"}),
        ("bim_opening", "the component maker fails", then(walls, gui={"makeComponent"}), {"wall": "Inner wall"}),
        ("bim_opening", "not cut", then(walls, no_cut=True), {"wall": "Inner wall"}),
        ("bim_opening", "a run of no length", lambda s: wall(s, "Dot wall", [[0, 0], [0, 0]]), {"wall": "Dot wall", "height": 1000}),

        ("bim_structure", "model call 8", empty, {"kind": "slab", "points": [[0, 6000, -150], [8000, 6000, -150], [8000, 0, -150], [0, 0, -150]], "thickness": 150, "name": "Floor slab"}),
        ("bim_structure", "model call 9", empty, {"kind": "footing", "points": [[9250, 750, 0], [9750, 750, 0], [9750, 1250, 0], [9250, 1250, 0]], "thickness": 400, "name": "Porch footing"}),
        ("bim_structure", "model call 10", empty, {"kind": "column", "at": [9500, 1000, 0], "width": 250, "depth": 250, "height": 2250, "name": "Porch column"}),
        ("bim_structure", "model call 11", empty, {"kind": "column", "at": [9500, 5000, 0], "width": 600, "depth": 600, "height": 300, "name": "Plinth"}),
        ("bim_structure", "model call 12", empty, {"kind": "beam", "from": [9500, 1000, 2450], "to": [9500, 5000, 2450], "width": 200, "depth": 400, "name": "Porch beam"}),
        ("bim_structure", "defaults: a column", empty, {}),
        ("bim_structure", "a slab on a closed sketch", bases, {"kind": "slab", "base": "Closed"}),
        ("bim_structure", "a slab on a closed wire", bases, {"kind": "slab", "base": "ClosedWire", "name": "Sketch"}),
        ("bim_structure", "kind wrong", empty, {"kind": "wall"}),
        ("bim_structure", "thickness zero", empty, {"kind": "slab", "points": sq, "thickness": 0}),
        ("bim_structure", "base a solid", bases, {"kind": "slab", "base": "Solid"}),
        ("bim_structure", "base an open line", bases, {"kind": "footing", "base": "Sketch"}),
        ("bim_structure", "base with no shape", bases, {"kind": "slab", "base": "Sheet"}),
        ("bim_structure", "base not there", bases, {"kind": "slab", "base": "Nope"}),
        ("bim_structure", "no outline", empty, {"kind": "footing"}),
        ("bim_structure", "points too few", empty, {"kind": "slab", "points": [[0, 0], [1, 1]]}),
        ("bim_structure", "points not flat", empty, {"kind": "slab", "points": [[0, 0, 0], [1000, 0, 0], [1000, 1000, 500], [0, 1000, 0]]}),
        ("bim_structure", "column width zero", empty, {"kind": "column", "width": 0}),
        ("bim_structure", "column at wrong", empty, {"kind": "column", "at": "here"}),
        ("bim_structure", "beam with one end", empty, {"kind": "beam", "from": [0, 0, 0]}),
        ("bim_structure", "beam ends not points", empty, {"kind": "beam", "from": [0, 0, 0], "to": "there"}),
        ("bim_structure", "beam of no length", empty, {"kind": "beam", "from": [0, 0, 0], "to": [0, 0, 0]}),
        ("bim_structure", "beam straight up", empty, {"kind": "beam", "from": [0, 0, 0], "to": [0, 0, 3000]}),
        ("bim_structure", "beam depth zero", empty, {"kind": "beam", "from": [0, 0, 0], "to": [1000, 0, 0], "depth": 0}),
        ("bim_structure", "a short beam", empty, {"kind": "beam", "from": [0, 0, 0], "to": [100, 0, 0]}),

        ("bim_profiles", "model call 13", empty, {"search": "HEB2", "limit": 10}),
        ("bim_profiles", "all", empty, {}),
        ("bim_profiles", "a category, one shown", empty, {"category": "heb", "limit": 1}),
        ("bim_profiles", "no library", less(empty, "ArchProfile"), {}),

        ("bim_member", "model call 14", empty, {"profile": "HEB200", "from": [8000, 5500, 2800], "to": [10000, 5500, 2800], "name": "Steel beam"}),
        ("bim_member", "upright, turned, timber", empty, {"profile": "t 50x100", "from": [0, 0, 0], "to": [0, 0, 2400], "rotate": 90}),
        ("bim_member", "density given", empty, {"profile": "IPE100", "from": [0, 0, 0], "to": [1000, 0, 0], "density": 7000}),
        ("bim_member", "not in the library, near", empty, {"profile": "HEB999", "from": [0, 0, 0], "to": [1000, 0, 0]}),
        ("bim_member", "not in the library", empty, {"profile": "XY", "from": [0, 0, 0], "to": [1000, 0, 0]}),
        ("bim_member", "no profile", empty, {"from": [0, 0, 0], "to": [1000, 0, 0]}),
        ("bim_member", "an end missing", empty, {"profile": "HEB200", "from": [0, 0, 0]}),
        ("bim_member", "ends together", empty, {"profile": "HEB200", "from": [0, 0, 0], "to": [0, 0, 0]}),
        ("bim_member", "no section made", then(empty, none={"makeProfile"}), {"profile": "HEB200", "from": [0, 0, 0], "to": [1000, 0, 0]}),
        ("bim_member", "no library", less(empty, "ArchProfile"), {"profile": "HEB200", "from": [0, 0, 0], "to": [1000, 0, 0]}),

        ("bim_roof", "model call 15", empty, {"points": [[0, 0, 2600], [8000, 0, 2600], [8000, 6000, 2600], [0, 6000, 2600]], "angle": [30, 90, 30, 90], "thickness": 150, "overhang": 300, "name": "Roof"}),
        ("bim_roof", "model call 16", then(empty, hip=577.4), {"points": [[12000, 0, 0], [12000, 4000, 0], [18000, 4000, 0], [18000, 0, 0]], "angle": 30, "name": "Hip roof cw"}),
        ("bim_roof", "on a closed wire, runs given", bases, {"base": "ClosedWire", "run": [2000, 1000, 2000, 1000], "angle": 45}),
        ("bim_roof", "one run for all", empty, {"points": sq, "run": 1500}),
        ("bim_roof", "no heights from FreeCAD", then(empty, no_heights=True), {"points": sq}),
        ("bim_roof", "base an open line", bases, {"base": "Sketch"}),
        ("bim_roof", "base a solid", bases, {"base": "Solid"}),
        ("bim_roof", "base with no shape", bases, {"base": "Sheet"}),
        ("bim_roof", "neither", empty, {}),
        ("bim_roof", "points too few", empty, {"points": [[0, 0], [1, 0]]}),
        ("bim_roof", "an edge not straight", lambda s: thing(s, "Curvy", Shape=curvy()), {"base": "Curvy"}),
        ("bim_roof", "angle not a number", empty, {"points": sq, "angle": "steep"}),
        ("bim_roof", "angles of the wrong count", empty, {"points": sq, "angle": [30, 30]}),
        ("bim_roof", "angle zero", empty, {"points": sq, "angle": [30, 0, 30, 90]}),
        ("bim_roof", "every edge a gable", empty, {"points": sq, "angle": 90}),
        ("bim_roof", "thickness zero", empty, {"points": sq, "thickness": 0}),
        ("bim_roof", "overhang not a number", empty, {"points": sq, "overhang": "wide"}),
        ("bim_roof", "run not a number", empty, {"points": sq, "run": ["a", 1, 2, 3]}),
        ("bim_roof", "runs of the wrong count", empty, {"points": sq, "run": [1000]}),
        ("bim_roof", "clockwise and no flip", then(empty, no_flip=True), {"points": list(reversed(sq))}),
        ("bim_roof", "clockwise base and no flip", then(lambda s: thing(s, "Cw", Shape=outline(list(reversed(sq)))), no_flip=True), {"base": "Cw"}),

        ("bim_stairs", "model call 17", empty, {"at": [10500, 2000, 0], "direction": [1, 0], "length": 3920, "width": 1000, "height": 2600, "steps": 15, "name": "Stairs"}),
        ("bim_stairs", "defaults (outside Blondel)", empty, {}),
        ("bim_stairs", "label taken", bases, {"name": "Sketch", "direction": [0, -2, 5]}),
        ("bim_stairs", "length zero", empty, {"length": 0}),
        ("bim_stairs", "one step", empty, {"steps": 1}),
        ("bim_stairs", "direction straight up", empty, {"direction": [0, 0, 1]}),
        ("bim_stairs", "direction not a point", empty, {"direction": "north"}),
        ("bim_stairs", "at not a point", empty, {"at": [1]}),
        ("crash: bim_stairs", "steps not a number", empty, {"steps": "many"}),

        ("bim_space", "model call 18", empty, {"points": [[250, 250], [3925, 250], [3925, 5750], [250, 5750]], "height": 2600, "use": "room", "name": "Living room"}),
        ("bim_space", "model call 19", empty, {"points": [[4075, 250], [7750, 250], [7750, 5750], [4075, 5750]], "height": 2600, "use": "Bedroom"}),
        ("bim_space", "clockwise, no use", empty, {"points": list(reversed(sq))}),
        ("bim_space", "from a solid", bases, {"base": "Solid", "use": "Office"}),
        ("bim_space", "use near, from a solid", bases, {"base": "Solid", "use": "dining"}),
        ("bim_space", "no space types in this FreeCAD", then(empty, no_space_type=True), {"points": sq, "use": "Bedroom"}),
        ("bim_space", "base not a solid", bases, {"base": "Closed"}),
        ("bim_space", "base with no shape", bases, {"base": "Sheet"}),
        ("bim_space", "neither", empty, {"height": 0}),
        ("bim_space", "height zero", empty, {"points": sq, "height": 0}),
        ("bim_space", "points not flat", empty, {"points": [[0, 0, 0], [1000, 0, 0], [1000, 1000, 500], [0, 1000, 0]]}),

        ("bim_building", "model call 22", levels, {"levels": ["Ground floor", "Roof level"], "name": "House", "siteName": "Plot"}),
        ("bim_building", "defaults", levels, {}),
        ("bim_building", "one level by name, no site", levels, {"levels": "Roof level", "site": False}),
        ("bim_building", "a level not there", levels, {"levels": ["Cellar"]}),
        ("bim_building", "label taken", levels, {"name": "Ground floor", "siteName": "Ground floor"}),

        ("bim_schedule", "model call 32", model, {}),
        ("bim_schedule", "model call 33: a sheet by name", model, {"sheet": "House schedule"}),
        ("bim_schedule", "a sheet by name", model, {"sheet": "House schedule"}),
        ("bim_schedule", "a sheet", model, {"sheet": True}),
        ("bim_schedule", "nothing here", empty, {"sheet": ""}),

        ("bim_export", "model call 60", house, {"path": "house.ifc"}),
        ("bim_export", "objects, the default name", house, {"objects": ["Inner wall", "Floor slab"]}),
        ("bim_export", "no site: the loose objects", walls, {"path": os.path.join(tmp, "deep", "walls")}),
        ("bim_export", "nothing to write", bases, {}),
        ("bim_export", "an object not there", house, {"objects": ["Nope"]}),
        ("bim_export", "no IfcOpenShell", less(house, "ifcopenshell"), {}),
        ("bim_export", "no exporter", less(house, "importers", "exportIFC"), {}),
        ("bim_export", "a bare classification", lambda s: (house(s), s.doc.getObject("Wall").__dict__.update(StandardCode="Ss_25_10_30")), {"path": "house.ifc"}),
        ("bim_export", "the exporter stops", then(house, export_fails=True), {"path": "house.ifc"}),

        ("bim_import", "model call 68", empty, {"path": ifc_file}),
        ("bim_import", "no file", empty, {"path": "nowhere.ifc"}),
        ("bim_import", "no path", empty, {}),
        ("bim_import", "no IfcOpenShell", less(empty, "ifcopenshell"), {"path": ifc_file}),
        ("bim_import", "FreeCAD's importer fails, nothing read", then(bases, import_fails=True), {"path": ifc_file}),
        ("bim_import", "no importer, nothing read", less(empty, "importers", "importIFC"), {"path": ifc_file}),

        ("bim_curtain_wall", "model call 46", empty, {"points": [[12000, 6000, 0], [18000, 6000, 0]], "height": 3000, "vertical": 1500, "horizontal": 1500, "name": "Glazing"}),
        ("bim_curtain_wall", "two stretches, defaults", empty, {"points": [[0, 0], [4000, 0], [4000, 2000]], "glass": 24}),
        ("bim_curtain_wall", "no maker", less(empty, "Arch.makeCurtainWall"), {"points": [[0, 0], [4000, 0]]}),
        ("bim_curtain_wall", "height zero before no maker", less(empty, "Arch.makeCurtainWall"), {"points": [[0, 0], [4000, 0]], "height": 0}),
        ("bim_curtain_wall", "mullion zero", empty, {"points": [[0, 0], [4000, 0]], "mullion": 0}),
        ("bim_curtain_wall", "one point", empty, {"points": [[0, 0]]}),
        ("bim_curtain_wall", "no points", empty, {}),

        ("bim_rebar", "model call 30", lambda s: slab(s, "Floor slab"), {"structure": "Floor slab", "along": "x", "layer": "bottom", "diameter": 12, "cover": 30, "spacing": 200, "name": "Slab bars"}),
        ("bim_rebar", "defaults", lambda s: slab(s, "Floor slab"), {"structure": "Floor slab"}),
        ("bim_rebar", "along y, on top", lambda s: slab(s, "Floor slab"), {"structure": "Floor slab", "along": "y", "layer": "top", "amount": 1}),
        ("bim_rebar", "along z", bases, {"structure": "Solid", "along": "z", "amount": 3}),
        ("bim_rebar", "FreeCAD's rebar needs its window", then(bases, gui={"makeRebar"}), {"structure": "Solid"}),
        ("bim_rebar", "its window, and no component maker", less(then(bases, gui={"makeRebar"}), "Arch.makeComponent"), {"structure": "Solid", "amount": 1, "name": "Sketch"}),
        ("bim_rebar", "no structure", bases, {}),
        ("bim_rebar", "no solid", bases, {"structure": "Closed"}),
        ("bim_rebar", "no shape", bases, {"structure": "Sheet"}),
        ("bim_rebar", "no maker", less(bases, "Arch.makeRebar"), {"structure": "Solid", "layer": "side"}),
        ("bim_rebar", "layer wrong", bases, {"structure": "Solid", "layer": "side", "cover": "x"}),
        ("bim_rebar", "cover not a number", bases, {"structure": "Solid", "cover": "x", "diameter": 0}),
        ("bim_rebar", "diameter zero", bases, {"structure": "Solid", "diameter": 0, "along": "w"}),
        ("bim_rebar", "along wrong", bases, {"structure": "Solid", "along": "w", "cover": -1}),
        ("bim_rebar", "cover below zero", bases, {"structure": "Solid", "cover": -1}),
        ("bim_rebar", "cover leaves no length", bases, {"structure": "Solid", "cover": 500}),
        ("bim_rebar", "no room across", bases, {"structure": "Solid", "along": "y", "cover": 495, "diameter": 20}),
        ("bim_rebar", "spacing zero", bases, {"structure": "Solid", "spacing": -5}),
        ("bim_rebar", "no bars", bases, {"structure": "Solid", "amount": 0}),
        ("bim_rebar", "too many bars", bases, {"structure": "Solid", "spacing": 0.1}),

        ("bim_panel", "model call 47", empty, {"points": [[20000, 0], [21200, 0], [21200, 600], [20000, 600]], "thickness": 18, "name": "Shelf"}),
        ("bim_panel", "a rectangle at a point", empty, {"length": 800, "at": [100, 200, 300]}),
        ("bim_panel", "no maker", less(empty, "Arch.makePanel"), {"thickness": 0}),
        ("bim_panel", "thickness zero", empty, {"thickness": 0}),
        ("bim_panel", "points not flat", empty, {"points": [[0, 0, 0], [1000, 0, 0], [1000, 1000, 500], [0, 1000, 0]]}),
        ("bim_panel", "points too few", empty, {"points": [[0, 0], [1, 1]]}),
        ("bim_panel", "width zero", empty, {"width": 0}),
        ("bim_panel", "at not a point", empty, {"at": "there"}),

        ("bim_grid", "model call 37", empty, {"xSpacing": [4000, 4000], "ySpacing": [3000, 3000], "length": 8000, "name": "Grid"}),
        ("bim_grid", "one spacing and a count", empty, {"spacing": 2500, "count": 3}),
        ("bim_grid", "x only, defaults", empty, {"xSpacing": 5000}),
        ("bim_grid", "nothing asked", empty, {"count": 1}),
        ("bim_grid", "no maker", less(empty, "Arch.makeAxis"), {}),
        ("bim_grid", "count of one", empty, {"spacing": 1000, "count": 1}),
        ("bim_grid", "spacing not a number", empty, {"spacing": "wide"}),
        ("bim_grid", "a gap not a number", empty, {"ySpacing": [1000, "a"]}),
        ("bim_grid", "a gap of zero", empty, {"xSpacing": [1000, 0]}),
        ("bim_grid", "length zero", empty, {"spacing": 1000, "length": 0}),
        ("bim_grid", "the second way refused after the first is made", empty, {"xSpacing": 1000, "ySpacing": [0]}),

        ("bim_material", "model call 24", walls, {"name": "Brick", "density": 1800, "color": "#b5533c", "description": "Clay brick", "objects": ["Inner wall"]}),
        ("bim_material", "model call 25", lambda s: [slab(s, n) for n in ("Floor slab", "Porch footing")], {"name": "Concrete", "density": 2400, "objects": ["Floor slab", "Porch footing"]}),
        ("bim_material", "one already there", lambda s: arch.makeMaterial("Brick").__dict__.update(Label="Brick", Material={"Density": "1 kg/m^3", "Kept": "yes"}), {"name": "Brick", "color": "0.5, 0.5, 0.5"}),
        ("bim_material", "no name", empty, {}),
        ("bim_material", "label taken by another kind", bases, {"name": "Sketch"}),
        ("bim_material", "no maker", less(empty, "Arch.makeMaterial"), {"name": "Brick"}),
        ("bim_material", "density zero", empty, {"name": "Brick", "density": 0}),
        ("bim_material", "color wrong", empty, {"name": "Brick", "color": "reddish"}),
        ("bim_material", "an object not there", empty, {"name": "Brick", "objects": ["Nope"]}),
        ("bim_material", "objects that carry no material", walls, {"name": "Brick", "objects": ["Inner wall", "Box", "Bare"]}),

        ("bim_frame", "model call 45", empty, {"profile": "IPE100", "points": [[0, -2000, 0], [0, -2000, 2500], [4000, -2000, 2500], [4000, -2000, 0]], "name": "Portal"}),
        ("bim_frame", "along a sketch, turned, timber", bases, {"profile": "t 50x100", "path": "Sketch", "rotate": 45, "align": False}),
        ("bim_frame", "not in the library, near", empty, {"profile": "HEB999", "points": [[0, 0], [1, 1]]}),
        ("bim_frame", "no profile", empty, {"points": [[0, 0], [1, 1]]}),
        ("bim_frame", "path without edges", bases, {"profile": "HEB200", "path": "Empty"}),
        ("bim_frame", "path with no shape", bases, {"profile": "HEB200", "path": "Sheet"}),
        ("bim_frame", "no path", empty, {"profile": "HEB200"}),
        ("bim_frame", "one point", empty, {"profile": "HEB200", "points": [[0, 0]]}),
        ("bim_frame", "a point not numbers", empty, {"profile": "HEB200", "points": [[0, 0], "x"]}),
        ("bim_frame", "no frame made", then(empty, none={"makeFrame"}), {"profile": "HEB200", "points": [[0, 0], [1000, 0]]}),

        ("bim_truss", "model call 43", empty, {"from": [0, 7000, 0], "to": [6000, 7000, 0], "height": 800, "strut": 100, "rod": 20, "panels": 6, "pattern": "warren", "name": "Truss"}),
        ("bim_truss", "defaults", empty, {"from": [0, 0, 0], "to": [3000, 0, 0]}),
        ("bim_truss", "pitched, howe, density", empty, {"from": [0, 0, 0], "to": [3000, 0, 0], "heightStart": 200, "heightEnd": 900, "pattern": "howe", "density": 500}),
        ("bim_truss", "a pattern this FreeCAD names otherwise", then(empty, rod_modes=["a", "b"]), {"from": [0, 0, 0], "to": [3000, 0, 0], "pattern": "howe"}),
        ("bim_truss", "an older truss: skipped", then(empty, old_truss=True), {"from": [0, 0, 0], "to": [3000, 0, 0], "panels": 4, "pattern": "pratt"}),
        ("bim_truss", "ends together", empty, {"from": [0, 0, 0], "to": [0, 0, 0.5]}),
        ("bim_truss", "an end missing", empty, {"from": [0, 0, 0]}),
        ("bim_truss", "pattern wrong", less(empty, "Arch.makeTruss"), {"from": [0, 0, 0], "to": [3000, 0, 0], "pattern": "fink"}),
        ("bim_truss", "no maker", less(empty, "Arch.makeTruss"), {"from": [0, 0, 0], "to": [3000, 0, 0]}),

        ("bim_fence", "model call 44", empty, {"points": [[-1000, -1000, 0], [9000, -1000, 0]], "height": 1200, "post": 100, "spacing": 2000, "panel": 20, "name": "Fence"}),
        ("bim_fence", "along a sketch, defaults", bases, {"path": "Sketch"}),
        ("bim_fence", "no maker", less(empty, "Arch.makeFence"), {"height": 0}),
        ("bim_fence", "height zero", empty, {"height": 0, "post": 0}),
        ("bim_fence", "post not a number", empty, {"post": "thick", "spacing": 0}),
        ("bim_fence", "post zero", empty, {"post": 0}),
        ("bim_fence", "spacing zero", empty, {"spacing": 0, "panel": 0}),
        ("bim_fence", "panel zero", empty, {"panel": 0, "spacing": 50}),
        ("bim_fence", "spacing within the post", empty, {"spacing": 100}),
        ("bim_fence", "no path", empty, {}),
        ("bim_fence", "path without edges", bases, {"path": "Empty"}),

        ("bim_covering", "model call 31", less(floor, "Arch.makeCovering"), {"face": "Floor slab.Face6", "finish": "tiles", "tile": [600, 600], "joint": 5, "thickness": 10, "name": "Floor tiles"}),
        ("bim_covering", "default tiles, no component maker", less(floor, "Arch.makeCovering", "Arch.makeComponent"), {"face": "Floor slab.Face6"}),
        ("bim_covering", "solid", less(floor, "Arch.makeCovering"), {"face": "Floor slab.Face6", "finish": "solid"}),
        ("bim_covering", "hatch becomes solid", less(floor, "Arch.makeCovering"), {"face": "Floor slab.Face6", "finish": "hatch", "thickness": 5}),
        ("bim_covering", "FreeCAD's own covering", floor, {"face": "Floor slab.Face6", "finish": "pattern", "tile": [200, 100], "joint": 2}),
        ("bim_covering", "FreeCAD's own covering, skipped", floor, {"face": "Floor slab.Face6", "finish": "solid"}),
        ("bim_covering", "no face", floor, {}),
        ("bim_covering", "an object, not a face", floor, {"face": "Floor slab"}),
        ("bim_covering", "an edge", floor, {"face": "Floor slab.Edge1"}),
        ("bim_covering", "a face it has not", floor, {"face": "Floor slab.Face9"}),
        ("bim_covering", "object not there", floor, {"face": "Nope.Face1"}),
        ("bim_covering", "finish wrong", floor, {"face": "Floor slab.Face6", "finish": "paint", "thickness": 0}),
        ("bim_covering", "thickness zero", floor, {"face": "Floor slab.Face6", "thickness": 0, "tile": [1]}),
        ("bim_covering", "tile wrong", floor, {"face": "Floor slab.Face6", "tile": [300, 0]}),
        ("bim_covering", "a face not flat", less(floor, "Arch.makeCovering"), {"face": "Dome.Face1"}),
        ("bim_covering", "too many tiles", less(floor, "Arch.makeCovering"), {"face": "Floor slab.Face6", "tile": [2, 2]}),
        ("bim_covering", "no tile lands", less(floor, "Arch.makeCovering"), {"face": "Far slab.Face6", "tile": [600, 600]}),

        ("bim_layers", "model call 26", walls, {"layers": [{"material": "Brick", "thickness": 115}, {"material": "Insulation", "thickness": 100, "density": 30},
                                                           {"material": "Plaster", "thickness": 35, "density": 1200}], "objects": ["Outer walls", "Box"], "name": "Outer build-up"}),
        ("bim_layers", "unnamed layers, a slab, a material there", lambda s: (slab(s, "Floor slab"), arch.makeMaterial("Layer 1").__dict__.update(Label="Layer 1")),
         {"layers": [{"thickness": 10}, {"thickness": 20.5, "name": "Screed"}], "objects": ["Floor slab"]}),
        ("bim_layers", "no layers", walls, {}),
        ("bim_layers", "a layer without thickness", walls, {"layers": [{"material": "Brick"}]}),
        ("bim_layers", "layers not a list", walls, {"layers": {"thickness": 5}}),
        ("bim_layers", "no maker", less(walls, "Arch.makeMultiMaterial"), {"layers": [{"thickness": 5}]}),
        ("bim_layers", "an object not there", walls, {"layers": [{"thickness": 5}], "objects": ["Nope"]}),

        ("bim_ifc", "model call 27", walls, {"objects": ["Outer walls"], "classification": "Uniclass Ss_25_10_30", "properties": {"Pset_WallCommon.IsExternal": True, "Pset_WallCommon.FireRating": "REI60"}}),
        ("bim_ifc", "model call 28", walls, {"objects": ["Inner wall"], "type": "IfcFooting"}),
        ("bim_ifc", "model call 29", walls, {"objects": ["Inner wall"], "type": "Plinth"}),
        ("bim_ifc", "read alone", tagged, {"objects": ["Outer walls", "Inner wall"]}),
        ("bim_ifc", "numbers, cleared classification", tagged, {"objects": ["Outer walls"], "classification": "", "properties": {"Qto.Count": 3, "Qto.Length": 2.5}}),
        ("bim_ifc", "no objects", walls, {}),
        ("bim_ifc", "an object not there", walls, {"objects": ["Nope"]}),
        ("bim_ifc", "not a BIM object", walls, {"objects": ["Inner wall", "Box"], "type": "Wall"}),
        ("bim_ifc", "a bare classification", walls, {"objects": ["Outer walls"], "classification": "Ss_25_10_30", "type": "Wall"}),
        ("bim_ifc", "no property sets on a level", house, {"objects": ["Ground floor"], "properties": {"Pset_X.Y": 1}}),
        ("bim_ifc", "a property without its set", walls, {"objects": ["Outer walls"], "properties": {"Pset_WallCommon.FireRating": "REI60", "FireRating": "x"}}),
        ("bim_ifc", "the second object refused", walls, {"objects": ["Inner wall", "Bare"], "properties": {"Pset_X.Y": 1}}),

        ("bim_quantities", "model call 34", weighed, {"by": "material", "detail": True}),
        ("bim_quantities", "by type", weighed, {}),
        ("bim_quantities", "by both", weighed, {"by": "both"}),
        ("bim_quantities", "nothing here", bases, {"detail": True}),

        ("bim_preflight", "model call 59", model, {}),
        ("bim_preflight", "invalid shapes", then(model, invalid_shapes=True), {}),
        ("bim_preflight", "no BIM objects", bases, {}),
        ("bim_preflight", "walls and no storey", walls, {}),
        ("bim_preflight", "many issues", lambda s: [wall(s, "W", [[0, i], [1000, i]]) for i in range(65)], {}),

        ("bim_edit", "model call 35", walls, {"op": "cut", "object": "Inner wall", "at": [0, 0, 2400], "normal": [0, 0, 1]}),
        ("bim_edit", "model call 36", lambda s: arch.makeStructure(None, length=250.0, width=250.0, height=2250.0).__dict__.update(Label="Porch column", IfcType="Column"),
         {"op": "clone", "object": "Porch column", "move": [0, 3000, 0], "name": "Porch column 2"}),
        ("bim_edit", "clone by Draft", then(walls, none={"cloneComponent"}), {"op": "clone", "object": "Inner wall"}),
        ("bim_edit", "clone with no clone maker", less(walls, "Arch.cloneComponent"), {"op": "clone", "object": "Inner wall"}),
        ("bim_edit", "clone nothing", walls, {"op": "clone"}),
        ("bim_edit", "clone moved wrongly", walls, {"op": "clone", "object": "Inner wall", "move": "up"}),
        ("bim_edit", "add", shown, {"op": "add", "object": "Inner wall", "with": ["Box", "Top"]}),
        ("bim_edit", "subtract", shown, {"op": "subtract", "object": "Inner wall", "with": ["Box"]}),
        ("bim_edit", "add to nothing", walls, {"op": "add"}),
        ("bim_edit", "add to what is not a component", walls, {"op": "add", "object": "Box", "with": ["Inner wall"]}),
        ("bim_edit", "add nothing", walls, {"op": "subtract", "object": "Inner wall"}),
        ("bim_edit", "add itself", walls, {"op": "add", "object": "Inner wall", "with": ["Box", "Inner wall"]}),
        ("bim_edit", "add what is built on it", walls, {"op": "add", "object": "Inner wall line", "with": ["Box"]}),
        ("bim_edit", "subtract what stands on it", lambda s: (walls(s), s.doc.getObject("Wall001").__dict__.update(Additions=[])), {"op": "subtract", "object": "Inner wall", "with": ["Box"]}),
        ("bim_edit", "a loop", looped, {"op": "add", "object": "Floor slab", "with": ["Pad"]}),
        ("bim_edit", "cut nothing", walls, {"op": "cut"}),
        ("bim_edit", "cut what has no solid", walls, {"op": "cut", "object": "Hollow"}),
        ("bim_edit", "cut by no direction", walls, {"op": "cut", "object": "Inner wall", "normal": [0, 0, 0]}),
        ("bim_edit", "cut at no point", walls, {"op": "cut", "object": "Inner wall", "at": "top"}),
        ("bim_edit", "cut that misses", then(walls, no_cut=True), {"op": "cut", "object": "Inner wall"}),
        ("bim_edit", "join", three_walls, {"op": "join", "walls": ["A", "B", "C"]}),
        ("bim_edit", "join, the others kept", three_walls, {"op": "join", "walls": ["A", "B"], "delete": False}),
        ("bim_edit", "join one", three_walls, {"op": "join", "walls": ["A"]}),
        ("bim_edit", "join one twice", three_walls, {"op": "join", "walls": ["A", "A"]}),
        ("bim_edit", "join unlike walls", three_walls, {"op": "join", "walls": ["A", "Thick"]}),
        ("bim_edit", "op wrong", walls, {"op": "move", "object": "Inner wall"}),
        ("bim_edit", "no op", walls, {}),
        ("bim_edit", "the object not there", walls, {"op": "move", "object": "Nope"}),

        ("bim_component", "model call 54", bases, {"kind": "component", "from": "Solid", "ifcType": "Furniture", "name": "Sink as component"}),
        ("bim_component", "of nothing", bases, {}),
        ("bim_component", "clone, placed", comps, {"kind": "clone", "from": "Comp", "at": [0, 0, 100], "axis": [0, 0, 1], "angle": 90, "name": "Twin"}),
        ("bim_component", "clone in place", comps, {"kind": "clone", "from": "Comp"}),
        ("bim_component", "unclone", comps, {"kind": "unclone", "from": "Copy"}),
        ("bim_component", "unclone what is no clone", comps, {"kind": "unclone", "from": "Comp"}),
        ("bim_component", "kind wrong", comps, {"kind": "copy", "from": "Comp"}),
        ("bim_component", "from with no shape", bases, {"from": "Sheet"}),
        ("bim_component", "from not there", bases, {"kind": "clone", "from": "Nope"}),
        ("bim_component", "an IFC type FreeCAD has not", bases, {"from": "Solid", "ifcType": "Sofa"}),
        ("bim_component", "clone placed wrongly", comps, {"kind": "clone", "from": "Comp", "at": "there"}),

        ("bim_panel_out", "model call 48", panels, {"kind": "cut", "panels": ["Shelf"]}),
        ("bim_panel_out", "two cut, by default", panels, {"panels": ["Shelf", "Side"]}),
        ("bim_panel_out", "a sheet", panels, {"kind": "sheet", "panels": ["Shelf", "Side"], "width": 2500, "height": 1250, "name": "Stock"}),
        ("bim_panel_out", "a sheet, its own size", panels, {"kind": "sheet", "panels": "Shelf"}),
        ("bim_panel_out", "no panels", panels, {}),
        ("bim_panel_out", "one not a panel", panels, {"panels": ["Shelf", "Box"]}),
        ("bim_panel_out", "two not panels", panels, {"panels": ["Box", "Shelf", "Lid"], "kind": "fold"}),
        ("bim_panel_out", "kind wrong", panels, {"panels": ["Shelf"], "kind": "fold"}),
        ("bim_panel_out", "a panel not there", panels, {"panels": ["Nope"]}),

        ("bim_nest", "nested", flats, {"container": "Sheet", "pieces": ["P1", "P2"]}),
        ("bim_nest", "rotations and a margin", flats, {"container": "Sheet", "pieces": ["P1", "P2"], "rotations": [0, 90], "margin": 5}),
        ("bim_nest", "more than a sheet", then(flats, many_sheets=True), {"container": "Sheet", "pieces": ["P1", "P2"]}),
        ("bim_nest", "no container", flats, {"pieces": ["P1"]}),
        ("bim_nest", "no pieces", flats, {"container": "Sheet"}),
        ("bim_nest", "container a solid", flats, {"container": "Block", "pieces": ["P1"]}),
        ("bim_nest", "container a wire", flats, {"container": "Line", "pieces": ["P1"]}),
        ("bim_nest", "container with no shape", flats, {"container": "Bare", "pieces": ["P1"]}),
        ("bim_nest", "pieces not flat", flats, {"container": "Sheet", "pieces": ["P1", "Block", "Line"]}),
        ("bim_nest", "a piece twice", flats, {"container": "Sheet", "pieces": ["P1", "P1"]}),
        ("bim_nest", "the container among the pieces", flats, {"container": "Sheet", "pieces": ["P1", "Sheet"]}),
        ("bim_nest", "rotations not numbers", flats, {"container": "Sheet", "pieces": ["P1"], "rotations": ["a"]}),
        ("bim_nest", "would not nest", then(flats, no_nest=True), {"container": "Sheet", "pieces": ["P1"], "rotations": [45]}),
        # FreeCAD's nester stopped by the rotations together (tests/test_bim_data.py: the meant differences from the handler)
        ("bim_nest", "stops with the rotations together, laid out with one alone", then(flats, nest_only=90.0), {"container": "Sheet", "pieces": ["P1", "P2"], "rotations": [0, 90]}),
        ("bim_nest", "stops at every rotation and says why", then(flats, nest_only=45.0), {"container": "Sheet", "pieces": ["P1", "P2"], "rotations": [0, 90]}),

        ("bim_ifc_brep", "model call 55", comps, {"objects": ["Comp"], "on": True}),
        ("bim_ifc_brep", "toggled: on, then off", lambda s: (comps(s), s.doc.getObject("Clone").__dict__.update(IfcData={"FlagForceBrep": "True", "x": "1"})), {"objects": ["Comp", "Copy"]}),
        ("bim_ifc_brep", "off", comps, {"objects": "Comp", "on": False}),
        ("bim_ifc_brep", "no objects", comps, {}),
        ("bim_ifc_brep", "not a BIM object", comps, {"objects": ["Comp", "Plain"]}),

        ("bim_views", "model call 42", house, {"levels": ["Ground floor"], "cutHeight": 1200}),
        ("bim_views", "every storey, cut faces", house, {"cutOnly": True}),
        ("bim_views", "an older Draft", then(house, old_views=True), {"levels": "Roof level"}),
        ("bim_views", "no levels", walls, {}),
        ("bim_views", "a level not there", house, {"levels": ["Cellar"]}),

        ("bim_image_plane", "an image", empty, {"path": image}),
        ("bim_image_plane", "sized, placed, named", bases, {"path": image, "width": 4000, "at": [0, 0, -10], "name": "Sketch"}),
        ("bim_image_plane", "by its height", empty, {"path": image, "height": 3000, "width": 0}),
        ("bim_image_plane", "no file", empty, {"path": "/nowhere/plan.png"}),
        ("bim_image_plane", "no path", empty, {}),
        ("bim_image_plane", "placed wrongly", empty, {"path": image, "at": "there"}),

        ("bim_library", "search", empty, {"folder": library, "search": "CHAIR wood"}),
        ("bim_library", "everything", empty, {"folder": library}),
        ("bim_library", "insert by name", empty, {"folder": library, "insert": "chair wood.step"}),
        ("bim_library", "insert a document by path", empty, {"folder": library, "insert": os.path.join(library, "sub", "Table.FCStd")}),
        # (tests/test_bim_data.py: a meant difference from the handler)
        ("bim_library", "insert a document that carries Agent Link's records", then(empty, merge_records=True), {"folder": library, "insert": os.path.join(library, "sub", "Table.FCStd")}),
        ("bim_library", "no library", empty, {"search": "chair"}),
        ("bim_library", "folder not there", empty, {"folder": "/nowhere/lib", "insert": "x"}),
        ("bim_library", "insert what is not there", empty, {"folder": library, "insert": "sofa.step"}),
        ("bim_library", "insert a path not there", empty, {"folder": library, "insert": "/nowhere/sofa.step"}),

        ("bim_reextrude", "from a face", solids, {"face": "Block.Face6"}),
        ("bim_reextrude", "kept, named, in its level", solids, {"face": "Block.Face1", "delete": False, "name": "Turned"}),
        ("bim_reextrude", "a panel", solids, {"face": "Board.Face6"}),
        ("bim_reextrude", "a face with a hole", solids, {"face": "Holed.Face1"}),
        ("bim_reextrude", "no face", solids, {}),
        ("bim_reextrude", "an object", solids, {"face": "Block"}),
        ("bim_reextrude", "an edge", solids, {"face": "Block.Edge2"}),
        ("bim_reextrude", "not there", solids, {"face": "Nope.Face1"}),

        ("bim_rewire", "two runs", loose_lines, {"objects": ["L1", "L2", "L3"]}),
        ("bim_rewire", "a curve", loose_lines, {"objects": ["Arc"]}),
        ("bim_rewire", "no objects", loose_lines, {}),
        ("bim_rewire", "no edges", loose_lines, {"objects": ["Dot"]}),
        ("bim_rewire", "one not there", loose_lines, {"objects": ["L1", "Nope"]}),

        ("bim_glue", "glued", loose_lines, {"objects": ["L1", "L2", "Dot"], "name": "L3"}),
        ("bim_glue", "by default", loose_lines, {"objects": ["L1", "L2"]}),
        ("bim_glue", "one with a shape", loose_lines, {"objects": ["L1", "Blank", "Other"]}),
        ("bim_glue", "no objects", loose_lines, {}),

        ("bim_trash", "model call 56", house, {"action": "put", "objects": ["Inner wall"]}),
        ("bim_trash", "model call 57", binned, {"action": "list"}),
        ("bim_trash", "put, by default, into the trash there", binned, {"objects": ["Outer walls", "Schedule"]}),
        ("bim_trash", "out of a plain group", grouped_box, {"objects": "Box"}),
        ("bim_trash", "a Trash that is no group", lambda s: (walls(s), s.doc.add(Obj("Trash", "Part::Feature"))), {"objects": ["Box"]}),
        ("bim_trash", "list with no trash", house, {"action": "list"}),
        ("bim_trash", "empty", binned, {"action": "empty"}),
        ("bim_trash", "empty with no trash", house, {"action": "empty"}),
        ("bim_trash", "put nothing", house, {"action": "put"}),
        ("bim_trash", "action wrong", house, {"action": "burn"}),

        ("bim_reorder", "model call 58", house, {"group": "Ground floor", "sort": True}),
        ("bim_reorder", "some first", house, {"group": "Ground floor", "order": ["Floor slab", "Inner wall"]}),
        ("bim_reorder", "as it is", house, {"group": "Ground floor"}),
        ("bim_reorder", "no group", house, {}),
        ("bim_reorder", "not a group", house, {"group": "Box"}),
        ("bim_reorder", "not its child", house, {"group": "Ground floor", "order": ["Floor slab", "House"]}),
        ("bim_reorder", "one not there", house, {"group": "Ground floor", "order": ["Nope"]}),
    ]

    def curvy():
        w = outline(SQUARE)
        w.Edges[1] = Shape("edge", [w.pts[1]])
        return w

    fixed = []
    for tool, case, prepare, args in out:
        if tool.startswith("crash: "):
            tool, case = tool[7:], "crash: " + case
        fixed.append((tool, case, prepare, args))
    return fixed

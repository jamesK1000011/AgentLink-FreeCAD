# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datacam_data.py runs through the old handlers and the
# new data entries on the stand-in CAM (tests/_datacam_standin.py): for
# each converted tool its normal paths and each of its refusals. A case is
# (tool, case name, prepare(session), arguments).
import json
import os

FILES = ("cam", "std_more")
WHOLE = ("cam",)  # the files with no tool left in code, but for KEPT; of the others only the tools below were taken

# tool -> its group
CONVERTED = {k: "cam" for k in (
    "cam_job", "cam_op", "cam_list", "cam_tool", "cam_tool_add", "cam_library", "cam_dressup", "cam_setup", "cam_edit", "cam_remove", "cam_sim", "cam_post")}
CONVERTED["points_structure"] = "std_more"

# tool -> why it is still code
KEPT = {}

# Refusals written in an entry that no case reaches, each with its reason.
UNREACHED = []

# What some cases must have answered (so that two empty runs alike do not pass).
EXPECT = {
    ("cam_job", "named, with stock"): {"job": "Walk", "body": "Block", "stock": {"min": [-3.0, -3.0, -1.0], "max": [63.0, 43.0, 22.0], "size": [66.0, 46.0, 23.0]},
                                       "tool": {"name": "TC: Default Tool", "number": 4, "diameter": 5.0, "feed": 120.0, "plunge": 120.0, "rpm": 2000.0}},
    ("cam_job", "no tool"): ["refused", "invalid_input", "tool: { diameter (mm), feed and plunge (mm/min), rpm } — the end mill the person will use; ask if not said."],
    ("cam_op", "profile, named"): {"op": "Outline", "kind": "profile", "job": "Job", "cutMm": 50.7, "tool": "TC: Default Tool"},
    ("cam_op", "drill finds the holes"): {"op": "Drill", "kind": "drill", "cutZ": [0.0, 22.0]},
    ("cam_op", "pocket by a query, a whole-number step over"): {"faces": ["Face6"]},
    ("cam_op", "under the stock"): {"warning": "It cuts down to z -30.0, below the stock's bottom (-1.0): into the fixture — set finalDepth."},
    ("cam_list", "two ops"): {"job": "Job", "minutes": 0.28},
    ("cam_tool", "feed"): {"tool": {"name": "TC: Default Tool", "number": 1, "diameter": 5.0, "feed": 150.0, "plunge": 200.0, "rpm": 12000.0}},
    ("cam_tool_add", "a v-bit, a size it has not"): {"shape": "v-bit", "tools": ["TC: Default Tool", "Vee"], "skipped": ["cornerRadius"]},
    ("cam_library", "import"): {"added": [{"name": "Six", "number": 2, "diameter": 6.0, "feed": 300.0, "plunge": 200.0, "rpm": 12000.0}], "skipped": ["TC: Default Tool"], "notAdded": ["Odd", "None"]},
    ("cam_dressup", "tags"): {"dressup": "TagsDressup", "kind": "tags", "on": "Profile", "tags": 4},
    ("cam_setup", "everything"): {"fixtures": ["G54", "G55"], "coolant": {"mode": "Flood", "ops": 2}, "safeHeightOffset": 5, "clearanceOffset": 10, "order": ["Pocket", "Profile"]},
    ("cam_edit", "an optional stop after an op"): {"op": "Optional stop", "gcode": ["(check the part)", "M1"], "ops": ["Profile", "Optional stop", "Pocket"]},
    ("cam_edit", "off"): {"op": "Pocket", "active": False, "ops": ["Profile", "Pocket (off)"]},
    ("cam_remove", "a stack, by the op under it"): {"removed": ["TagsDressup", "Profile"], "ops": ["Pocket"]},
    ("cam_sim", "plain"): {"job": "Job", "verdict": "fix", "removedMm3": 1497.2},
    ("cam_post", "through the job"): {"post": "grbl", "via": "job", "units": "mm (G21)", "lines": 6, "fixtures": ["G54"], "ops": ["Profile", "Pocket"]},
    ("cam_post", "by the script"): {"via": "script", "fixtures": []},
    ("points_structure", "rows of four"): {"points": "Scan structured", "width": 4, "height": 3},
}


def cases(fc, tmp):
    def P(build=None, missing=(), **flags):
        """prepare: the furniture, then the flags and missing modules of the call."""
        def prepare(s):
            got = build(s) if build else None
            fc.state["flags"].update(flags)
            fc.without(*missing)
            return got

        return prepare

    def B(build, **flags):
        """build under flags of its own (FreeCAD as it was when the job was made)."""
        def run(s):
            fc.state["flags"].update(flags)
            got = build(s)
            fc.state["flags"].clear()
            return got

        return run

    def blk(s):
        s.block()

    def j0(s):
        return s.job()

    def j2(s):
        j = s.job()
        s.op(j, "profile")
        s.op(j, "pocket")
        return j

    def two_jobs(s):
        s.job("A")
        s.job("B", s.block("Other"))

    def with_tool2(s):
        j = j2(s)
        s.tool(j, "Ball 3", "ballend")
        return j

    def dressed(kind="tags", twice=False):
        def build(s):
            j = j2(s)
            dr = s.dressup(j.Operations.Group[0], kind)
            if twice:
                s.dressup(dr, "dogbone")
            return j

        return build

    def off(s):
        j = j2(s)
        for o in j.Operations.Group:
            o.__dict__["Active"] = False

    def one_off(s):
        j = j2(s)
        j.Operations.Group[1].__dict__["Active"] = False
        s.dressup(j.Operations.Group[0], "tags")

    def tool_file(content, name="tools.json"):
        def build(s):
            j2(s)
            with open(os.path.join(s.out_dir, name), "w", encoding="utf-8") as f:
                f.write(content if isinstance(content, str) else json.dumps(content))

        return build

    def shapes(s):
        j2(s)
        d = os.path.join(tmp, "Mod", "CAM", "Tools", "Shape")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "endmill.fcstd"), "w").close()

    def wire(s):
        j2(s)
        w = s.doc.new("Part::Feature", "Wire", Shape=fc.BoxShape((0, 0, 0), (5, 5, 0), faces=0, edges=4))
        w.__dict__["Label"] = "Letters"
        e = s.doc.new("Part::Feature", "Empty", Shape=fc.BoxShape((0, 0, 0), (0, 0, 0), faces=0, edges=0))
        e.__dict__["Label"] = "Nothing"

    def far(s):
        j = s.job(body=s.block(lo=(100, 100, 0), hi=(160, 140, 20)))
        s.op(j, "profile")

    def retooled(s):
        j = with_tool2(s)
        j.Operations.Group[1].__dict__["ToolController"] = j.Tools.Group[1]
        return j

    T = {"diameter": 5}
    out = []

    def add(tool, *rows):
        out.extend((tool, name, prep, args) for name, prep, args in rows)

    add("cam_job",
        ("plain", P(blk), {"tool": T}),
        ("named, with stock", P(blk), {"body": "Block", "name": "Walk", "tool": {"diameter": 5, "feed": 120, "plunge": 120, "rpm": 2000, "number": 4}, "stock": {"margin": 3, "top": 2, "bottom": 1}}),
        ("no tool", P(blk), {"body": "Block"}),
        ("tool is not a record", P(blk), {"tool": 5}),
        ("tool without a diameter", P(blk), {"tool": {"feed": 100}}),
        ("stock is not a record", P(blk), {"tool": T, "stock": 3}),
        ("margin below 0", P(blk), {"tool": T, "stock": {"margin": -1}}),
        ("top below 0", P(blk), {"tool": T, "stock": {"top": -1}}),
        ("bottom below 0", P(blk), {"tool": T, "stock": {"bottom": -1}}),
        ("margin is a word", P(blk), {"tool": T, "stock": {"margin": "wide"}}),
        ("no body", P(), {"tool": T}),
        ("another body's name", P(blk), {"tool": T, "body": "Other"}),
        ("diameter 0", P(blk), {"tool": {"diameter": 0}}),
        ("feed 0", P(blk), {"tool": {"diameter": 5, "feed": 0}}),
        ("plunge 0", P(blk), {"tool": {"diameter": 5, "plunge": 0}}),
        ("rpm below 0", P(blk), {"tool": {"diameter": 5, "rpm": -1}}),
        ("a preferences stock, replaced", P(blk, fixed_stock=True), {"tool": T}),
        ("a preferences stock that stays", P(blk, fixed_stock=True, stock_fails=True), {"tool": T, "stock": {"margin": 5}}),
        ("a job without a first tool", P(blk, no_tc=True), {"tool": T}),
        ("a job without a model", P(blk, no_model=True), {"tool": T}))

    add("cam_list",
        ("two ops", P(j2), {}),
        ("no job", P(blk), {}),
        ("two jobs, none named", P(two_jobs), {}),
        ("two jobs, one named", P(two_jobs), {"job": "B"}),
        ("a job that is not there", P(two_jobs), {"job": "C"}),
        ("an op off, a dressup", P(one_off), {}),
        ("an op without a path", P(B(j2, path="none")), {}),
        ("no ops", P(j0), {}))

    add("cam_tool",
        ("feed", P(j2), {"feed": 150}),
        ("everything", P(j2), {"diameter": 3, "feed": 100, "plunge": 50, "rpm": 0, "number": 7}),
        ("nothing", P(j2), {}),
        ("diameter below 0", P(j2), {"diameter": -1}),
        ("feed is a word", P(j2), {"feed": "fast"}),
        ("no job", P(blk), {"feed": 1}),
        ("crash: a job without tools", P(B(j0, no_tc=True)), {"feed": 150}))

    add("cam_remove",
        ("an op", P(j2), {"op": "Pocket"}),
        ("a stack, by the op under it", P(dressed()), {"op": "Profile"}),
        ("a stack, by its dressup", P(dressed(twice=True)), {"op": "TagsDressup"}),
        ("a boundary dressup with its stock", P(dressed("boundary", twice=True)), {"op": "Profile"}),
        ("not there", P(j2), {"op": "Slot"}),
        ("no op named", P(j2), {}),
        ("no ops", P(j0), {"op": "Profile"}))

    add("cam_setup",
        ("everything", P(j2), {"fixtures": ["g54", "G55"], "coolant": "flood", "safeHeight": 5, "clearance": 10, "order": ["Pocket", "Profile"]}),
        ("nothing", P(j2), {}),
        ("an offset FreeCAD has not", P(j2), {"fixtures": ["G60"]}),
        ("a coolant it has not", P(j2), {"coolant": "oil"}),
        ("coolant under a dressup", P(dressed()), {"coolant": "mist"}),
        ("coolant none", P(j2), {"coolant": "none"}),
        ("safeHeight below 0", P(j2), {"safeHeight": -1}),
        ("clearance below 0", P(j2), {"clearance": -1}),
        ("safeHeight is a word", P(j2), {"safeHeight": "high"}),
        ("clearance only", P(j2), {"clearance": 0}),
        ("a job without a setup sheet", P(B(j2, no_sheet=True)), {"safeHeight": 5}),
        ("a setup sheet without offsets", P(B(j2, bare_sheet=True)), {"safeHeight": 5, "clearance": 5}),
        ("order misses one", P(j2), {"order": ["Pocket"]}),
        ("order names one twice", P(j2), {"order": ["Pocket", "Pocket"]}),
        ("order names a stranger", P(j2), {"order": ["Pocket", "Slot"]}))

    add("cam_edit",
        ("off", P(j2), {"action": "active", "op": "Pocket", "on": False}),
        ("on, by default", P(off), {"action": "active", "op": "Profile"}),
        ("active: not there", P(j2), {"action": "active", "op": "Slot"}),
        ("active: no op named", P(j2), {"action": "active"}),
        ("copy", P(j2), {"action": "copy", "op": "Profile"}),
        ("copy, named, with props", P(j2), {"action": "copy", "op": "Profile", "name": "Second", "props": {"StepDown": 2.0, "Nope": 1}}),
        ("copy, FreeCAD lists it", P(j2, copy_listed=True), {"action": "copy", "op": "Pocket"}),
        ("copy: not there", P(j2), {"action": "copy", "op": "Slot"}),
        ("a comment", P(j2), {"action": "comment", "text": "side (a)"}),
        ("a comment after an op, named", P(j2), {"action": "comment", "text": "then", "after": "Profile", "name": "Say"}),
        ("a comment without text", P(j2), {"action": "comment", "after": "Profile"}),
        ("a comment after a stranger", P(j2), {"action": "comment", "text": "x", "after": "Slot"}),
        ("a stop", P(j2), {"action": "stop"}),
        ("an optional stop after an op", P(j2), {"action": "stop", "text": "check the part", "optional": True, "after": "Profile"}),
        ("a stop with the tool of the op before", P(retooled), {"action": "stop", "text": "turn (it)"}),
        ("a stop in an empty job", P(j0), {"action": "stop", "name": "Hold"}),
        ("a stop FreeCAD does not list", P(j2, unlisted=True), {"action": "stop", "after": "Pocket"}),
        ("a stop named as an op is", P(j2), {"action": "stop", "name": "Pocket"}),
        ("no custom operation here", P(j2, missing=("Path.Op.Custom",)), {"action": "comment", "text": "x"}),
        ("a start point", P(j2), {"action": "start", "op": "Profile", "at": [1, 2, 3]}),
        ("no start point", P(j2), {"action": "start", "op": "Profile"}),
        ("an op that takes no start point", P(j2), {"action": "start", "op": "Pocket", "at": [0, 0, 0]}),
        ("start: not there", P(j2), {"action": "start", "op": "Slot"}),
        ("an action it has not", P(j2), {"action": "move", "op": "Profile"}),
        ("no action", P(j2), {}))

    add("cam_tool_add",
        ("an end mill", P(j2), {"diameter": 6}),
        ("a v-bit, a size it has not", P(j2), {"shape": "v-bit", "diameter": 6, "angle": 60, "cornerRadius": 1, "name": "Vee"}),
        ("a drill, everything", P(j2), {"shape": "drill", "diameter": 5, "angle": 118, "length": 60, "flutes": 2, "feed": 80, "plunge": 60, "rpm": 1500, "number": 9, "name": "Drill 5"}),
        ("flutes on a shape without", P(j2), {"shape": "v-bit", "diameter": 3, "flutes": 1, "tipDiameter": 0.2, "cuttingLength": 4}),
        ("a shape it has not", P(j2), {"shape": "saw", "diameter": 3}),
        ("no diameter", P(j2), {"shape": "drill"}),
        ("diameter 0", P(j2), {"diameter": 0}),
        ("diameter is a word", P(j2), {"diameter": "six"}),
        ("feed 0", P(j2), {"diameter": 6, "feed": 0}),
        ("no job", P(blk), {"diameter": 6}),
        ("a name taken", P(j2), {"diameter": 6, "name": "Pocket"}),
        ("with a window", P(j2, views=True), {"diameter": 6, "shape": "ballend"}),
        ("a FreeCAD whose shapes take no name", P(j2, bit_one=True), {"diameter": 6}),
        ("tool bits that cannot be made", P(j2, bit_fails=True), {"diameter": 6}),
        ("FreeCAD 1.0: from the shape's file", P(shapes, bit10=True, resource=tmp), {"diameter": 6}),
        ("FreeCAD 1.0: no such shape file", P(shapes, bit10=True, resource=tmp), {"diameter": 6, "shape": "drill"}))

    recs = {"tools": [{"name": "TC: Default Tool", "shape": "endmill", "diameter": 5}, {"name": "Six", "shape": "endmill", "diameter": 6, "feed": 300, "angle": None},
                      {"name": "Odd", "shape": "saw", "diameter": 3}, {"shape": None}]}
    add("cam_library",
        ("export", P(with_tool2), {}),
        ("export to a path", P(j2), {"action": "export", "path": "mine.json"}),
        ("import", P(tool_file(recs)), {"action": "import", "path": "tools.json"}),
        ("import again, replacing", P(tool_file(recs)), {"action": "import", "path": "tools.json", "replace": True}),
        ("import a plain list", P(tool_file(recs["tools"][1:2])), {"action": "import", "path": "tools.json"}),
        ("import: a tool that is refused", P(tool_file([{"name": "Zero", "diameter": 0}])), {"action": "import", "path": "tools.json"}),
        ("import: no such file", P(j2), {"action": "import", "path": "none.json"}),
        ("import: not JSON", P(tool_file("{ tools")), {"action": "import", "path": "tools.json"}),
        ("import: no tools", P(tool_file({"tools": []})), {"action": "import", "path": "tools.json"}),
        ("import: tools is a number", P(tool_file({"tools": 5})), {"action": "import", "path": "tools.json"}),
        ("import: a tool that is a number", P(tool_file([3])), {"action": "import", "path": "tools.json"}),
        ("an action it has not", P(j2), {"action": "list"}),
        ("no job", P(blk), {}))

    no_factory = ("Path.Post.Processor",)
    add("cam_post",
        ("through the job", P(j2), {}),
        ("to a path, linuxcnc", P(j2), {"post": "linuxcnc", "path": "walk.nc"}),
        ("a job with a space", P(lambda s: s.op(s.job("My Job"), "profile")), {}),
        ("its arguments and state put back", P(B(j2, post_args="--show-editor --axis-modal", job_state=["Touched"])), {}),
        ("by the script", P(j2, missing=no_factory), {}),
        ("by the script, two tools and a dressup", P(lambda s: s.dressup(retooled(s).Operations.Group[0]), missing=no_factory), {}),
        ("no work offsets: by the script", P(lambda s: j2(s).__dict__.update(Fixtures=[])), {}),
        ("the job's post answers nothing: by the script", P(j2, pp_none=True), {}),
        ("the job's post writes nothing: by the script", P(j2, pp="empty"), {}),
        ("the job's post has no sections", P(j2, pp_nosections=True), {}),
        ("a script without export", P(j2, missing=no_factory), {"post": "linuxcnc"}),
        ("no such script here", P(j2, missing=no_factory), {"post": "marlin"}),
        ("a post it has not", P(j2), {"post": "fanuc"}),
        ("no ops", P(j0), {}),
        ("every op off", P(off), {}),
        ("one op off", P(one_off), {}),
        ("the post stops", P(j2, post="fails"), {}),
        ("the script stops", P(j2, post="fails", missing=no_factory), {}),
        ("nothing written", P(j2, post="empty"), {}),
        ("no text written", P(j2, post="notext", missing=no_factory), {}),
        ("inches", P(j2, inch=True), {}),
        ("cuts under the stock", P(B(j2, path="deep")), {}),
        ("cuts far outside the stock", P(far), {}),
        ("only rapids", P(B(j2, path="rapids")), {}),
        ("no job", P(blk), {}))

    add("cam_dressup",
        ("tags", P(j2), {"op": "Profile", "kind": "tags", "count": 4, "width": 6, "height": 3, "angle": 60}),
        ("tags as FreeCAD spreads them", P(j2), {"op": "Profile", "kind": "tags"}),
        ("tags without positions", P(j2, bare_tags=True), {"op": "Profile", "kind": "tags", "angle": 30, "width": 2}),
        ("no tags", P(j2), {"op": "Profile", "kind": "tags", "count": 0}),
        ("a dogbone, its style", P(j2), {"op": "Pocket", "kind": "dogbone", "style": "T-bone"}),
        ("on a dressup, by the op's name", P(dressed()), {"op": "Profile", "kind": "dogbone"}),
        ("a boundary, the job's stock", P(j2), {"op": "Profile", "kind": "boundary"}),
        ("a boundary with a margin", P(j2), {"op": "Profile", "kind": "boundary", "margin": 4}),
        ("a boundary without a stock", P(j2, no_dress_stock=True), {"op": "Profile", "kind": "boundary", "margin": 4}),
        ("a ramp, made as its command does", P(j2), {"op": "Profile", "kind": "ramp"}),
        ("a ramp whose setup wants more", P(j2, setup_two=True), {"op": "Profile", "kind": "ramp"}),
        ("an array: no way here", P(j2), {"op": "Profile", "kind": "array"}),
        ("lead in/out: not headless", P(j2), {"op": "Profile", "kind": "leadinout"}),
        ("a kind it has not", P(j2), {"op": "Profile", "kind": "chamfer"}),
        ("no kind", P(j2), {"op": "Profile"}),
        ("an op that is not there", P(j2), {"op": "Slot", "kind": "tags"}),
        ("no ops", P(j0), {"op": "Profile", "kind": "tags"}),
        ("FreeCAD refuses it", P(j2, dress_fails=True), {"op": "Profile", "kind": "dogbone"}),
        ("FreeCAD makes none: tags", P(j2, dress_none=True), {"op": "Pocket", "kind": "tags"}),
        ("FreeCAD makes none: dogbone", P(j2, dress_none=True), {"op": "Pocket", "kind": "dogbone"}),
        ("FreeCAD does not list it", P(j2, dress_unlisted=True), {"op": "Profile", "kind": "tags"}),
        ("FreeCAD does not list it, the older call", P(j2, dress_unlisted=True, addop_two=True), {"op": "Profile", "kind": "tags"}),
        ("props", P(j2), {"op": "Profile", "kind": "tags", "props": {"Width": "5 mm"}}),
        ("props: no such property", P(j2), {"op": "Profile", "kind": "tags", "props": {"Depth": 1}}),
        ("props: a value it does not take", P(j2), {"op": "Profile", "kind": "dogbone", "props": {"Style": "Round"}}),
        ("no path comes of it", P(j2, dress_path="empty"), {"op": "Profile", "kind": "tags"}),
        ("no cutting left: a boundary", P(j2, dress_path="rapids"), {"op": "Profile", "kind": "boundary"}),
        ("no cutting left: tags, unlisted", P(j2, dress_path="rapids", dress_unlisted=True), {"op": "Profile", "kind": "tags"}),
        ("an op with only rapids", P(B(j2, path="rapids"), dress_path="rapids"), {"op": "Profile", "kind": "tags"}))

    add("cam_op",
        ("profile, named", P(j0), {"kind": "profile", "side": "outside", "name": "Outline"}),
        ("profile inside, depths", P(j0), {"kind": "Profile", "side": "inside", "stepDown": 2, "finalDepth": 4, "stockToLeave": 0.2, "stepOver": 40}),
        ("pocket by a query, a whole-number step over", P(j0), {"kind": "pocket", "faces": [{"normal": [0, 0, 1]}], "stepOver": 50.0, "props": {"ClearingPattern": "Offset"}, "stockToLeave": 0.5}),
        ("pocket by names", P(j0), {"kind": "pocket", "faces": ["Face3", "Face4"]}),
        ("one query, the nearest", P(j0, faces=["Face6", "Face2"]), {"kind": "pocket", "faces": {"normal": [0, 0, 1], "near": [30, 20, 12]}}),
        ("a query near a point record", P(j0, faces=["Face6", "Face2"]), {"kind": "pocket", "faces": [{"near": {"point": [1, 2, 3]}}, "Face9"]}),
        ("faces of another body", P(lambda s: (s.job(), s.block("Other"))), {"kind": "pocket", "body": "Other", "faces": [{"z": 12}]}),
        ("a body that is not there", P(j0), {"kind": "pocket", "body": "Other"}),
        ("no face matches", P(j0, faces=[]), {"kind": "pocket", "faces": [{"z": 99}]}),
        ("adaptive", P(j0), {"kind": "adaptive", "stepOver": 20}),
        ("adaptive finish, outside", P(j0), {"kind": "adaptive", "side": "outside", "finish": True}),
        ("face", P(j0), {"kind": "face"}),
        ("drill finds the holes", P(j0), {"kind": "drill"}),
        ("drill, no holes", P(j0, no_holes=True), {"kind": "drill"}),
        ("drill the faces given", P(j0), {"kind": "drill", "faces": ["Face7"], "name": "Holes"}),
        ("drill, a FreeCAD that builds it itself", P(j0, old_holes=True), {"kind": "drill"}),
        ("helix, a proxy that knows its model", P(j0, proxy_knows=True), {"kind": "helix"}),
        ("engrave letters", P(wire), {"kind": "engrave", "base": ["Letters"]}),
        ("a slot along a wire", P(wire), {"kind": "slot", "base": "Letters"}),
        ("a profile round a body given as base", P(wire), {"kind": "profile", "base": ["Block"]}),
        ("base without edges", P(wire), {"kind": "engrave", "base": ["Letters", "Nothing"]}),
        ("base that is not there", P(wire), {"kind": "engrave", "base": ["Words"]}),
        ("a probe", P(j0), {"kind": "probe"}),
        ("a probe without touches", P(j0, path="empty"), {"kind": "probe"}),
        ("custom lines", P(j0, path="rapids"), {"kind": "custom"}),
        ("custom without lines", P(j0), {"kind": "custom"}),
        ("no cutting moves", P(j0, path="rapids"), {"kind": "profile"}),
        ("no cutting moves on the faces", P(j0, path="rapids"), {"kind": "pocket", "faces": ["Face1"]}),
        ("no path at all", P(j0, path="none"), {"kind": "face"}),
        ("under the stock", P(j0, path="deep"), {"kind": "profile"}),
        ("a kind it has not", P(j0), {"kind": "lathe"}),
        ("no kind", P(j0), {}),
        ("a side it has not", P(j0), {"kind": "profile", "side": "left"}),
        ("step over 0", P(j0), {"kind": "pocket", "stepOver": 0}),
        ("step over above 100", P(j0), {"kind": "pocket", "stepOver": 101}),
        ("step over is a word", P(j0), {"kind": "pocket", "stepOver": "half"}),
        ("step down 0", P(j0), {"kind": "pocket", "stepDown": 0}),
        ("a job that lost its model", P(B(j0, no_model=True)), {"kind": "profile"}),
        ("a job that lost its tools", P(B(j0, no_tc=True)), {"kind": "profile"}),
        ("surface: not in this FreeCAD", P(j0), {"kind": "surface"}),
        ("deburr: not in this FreeCAD", P(j0), {"kind": "deburr"}),
        ("with another of the job's tools", P(with_tool2), {"kind": "profile", "tool": "Ball 3"}),
        ("a tool by its bit's name", P(with_tool2), {"kind": "pocket", "tool": "Ball 3 bit"}),
        ("a tool the job has not", P(with_tool2), {"kind": "profile", "tool": "Vee"}),
        ("props: no such property", P(j0), {"kind": "profile", "props": {"Depth": 3}}),
        ("props: not one of the choices", P(j0), {"kind": "pocket", "props": {"ClearingPattern": "Spiral"}}),
        ("props: a value it does not take", P(j0, locked=("StartDepth",)), {"kind": "pocket", "props": {"StartDepth": "high"}}),
        ("the build fails: nothing kept", P(j0, create_fails=True), {"kind": "drill"}),
        ("the build fails before it is listed", P(j0, create_fails="early"), {"kind": "pocket"}),
        ("two jobs, none named", P(two_jobs), {"kind": "profile"}),
        ("no job", P(blk), {"kind": "profile"}))

    add("cam_sim",
        ("plain", P(j2), {"inline": False}),
        ("with the picture, coarse", P(j2), {"resolution": 4}),
        ("to a path", P(j2), {"inline": False, "path": os.path.join(tmp, "sim.png"), "resolution": 3}),  # as given: a relative one is not put in the output folder
        ("a ball end and a dressup", P(lambda s: s.dressup(retooled(s).Operations.Group[1])), {"inline": False, "resolution": 2}),
        ("a rapid through the stock", P(B(j2, path="crash")), {"inline": False, "resolution": 2}),
        ("cuts under the stock", P(B(j2, path="deep")), {"inline": False, "resolution": 2}),
        ("only rapids", P(B(j2, path="rapids")), {"inline": False, "resolution": 2}),
        ("resolution 0", P(j2), {"resolution": 0}),
        ("no ops", P(j0), {}),
        ("every op off", P(off), {}),
        ("ops without paths", P(B(j2, path="none")), {}),
        ("no job", P(blk), {}))

    def scan(n):
        return lambda s: s.cloud("Scan", [(i, 0, 0) for i in range(n)])

    add("points_structure",
        ("rows of four", P(scan(12)), {"points": "Scan", "width": 4}),
        ("width and height, named", P(scan(12)), {"points": "Scan", "width": 6, "height": 2, "name": "Grid"}),
        ("a width that does not divide it", P(scan(12)), {"points": "Scan", "width": 5}),
        ("a height that does not fit", P(scan(12)), {"points": "Scan", "width": 4, "height": 4}),
        ("no width", P(scan(12)), {"points": "Scan"}),
        ("one point: no grid", P(scan(1)), {"points": "Scan", "width": 2}),
        ("not a cloud", P(blk), {"points": "Block", "width": 2}),
        ("not there", P(scan(12)), {"points": "Sweep", "width": 2}))
    return out

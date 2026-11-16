# SPDX-License-Identifier: LGPL-2.1-or-later
# The BIM tools moved from handlers to data (agentlink/data/tools.json):
# each one built from its entry is the tool the code made before — name,
# description (byte for byte), inputSchema, changes, reads, group — and, on a
# stand-in FreeCAD, does the same things in the same order and answers or
# refuses in the same words as the handler it replaces.
#
# Plain Python. tests/_bim_before.py is what the code made at
# BASE; where git has that commit the snapshot is checked against its source
# and the old handlers are run beside the new entries (in a child process:
# the stand-in FreeCAD must not be seen by the other tests).
import ast
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)

BASE = "b2d3dbd"  # the commit whose handlers were converted
CONVERTED = {"bim_wall": "bim", "bim_section": "bim", "bim_reference": "bim_gaps"}


def _git(*args):
    try:
        r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _have_base():
    return _git("cat-file", "-e", f"{BASE}^{{commit}}") is not None


def _child(mode):
    r = subprocess.run([sys.executable, os.path.abspath(__file__), mode], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(f"child {mode} failed:\n{r.stderr[-3000:]}")
    return json.loads(r.stdout)


class BimData(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, HERE)
        import _bim_before

        self.before = _bim_before.BEFORE

    def test_the_tool_is_the_one_the_code_made(self):
        from agentlink import runners

        self.assertEqual(sorted(self.before), sorted(CONVERTED))
        for name, group in CONVERTED.items():
            e = runners.entries()[name]
            t = runners.tool(name, e, {})
            b = self.before[name]
            self.assertEqual(t.name, b["name"], name)
            self.assertEqual(t.description.encode("utf-8"), b["description"].encode("utf-8"), name)
            self.assertEqual(t.schema, b["inputSchema"], name)
            self.assertEqual(list(t.schema["properties"]), list(b["inputSchema"]["properties"]), name)  # the order too
            self.assertIs(t.changes, b["changes"], name)
            self.assertEqual(t.reads, b["reads"], name)
            self.assertEqual(t.group, b["group"], name)
            self.assertEqual(t.group, group, name)
            self.assertIsNone(t.activity, name)

    def test_no_handler_is_left_beside_the_entry(self):
        for f in ("bim.py", "bim_more.py", "bim_gaps.py"):
            with open(os.path.join(ROOT, "agentlink", "families", f), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Tool" and node.args and isinstance(node.args[0], ast.Constant):
                    self.assertNotIn(node.args[0].value, CONVERTED, f)
                if isinstance(node, ast.FunctionDef):
                    self.assertNotIn(node.name, CONVERTED, f)

    @unittest.skipUnless(_have_base(), f"git has no {BASE} here")
    def test_the_snapshot_is_the_code_at_base(self):
        self.assertEqual(_child("--before"), self.before)

    @unittest.skipUnless(_have_base(), f"git has no {BASE} here")
    def test_same_steps_and_words_as_the_handlers(self):
        got = _child("--behave")
        self.assertEqual(sorted({c["tool"] for c in got}), sorted(CONVERTED))
        self.assertGreaterEqual(len(got), 40)
        for c in got:
            self.assertEqual(c["new"], c["old"], f"{c['tool']} {c['case']}")
        by = {(c["tool"], c["case"]): c["new"] for c in got}
        # Not two empty runs alike: what some of them must have done.
        w = by[("bim_wall", "model call 1")]
        self.assertEqual(w["result"][0], "ok")
        self.assertEqual({k: w["result"][1][k] for k in ("object", "length", "width", "height", "align", "base", "step")},
                         {"object": "Outer walls", "length": 28000.0, "width": 250.0, "height": 2600.0, "align": "right", "base": "Outer walls line", "step": 1})
        self.assertTrue(any("makeWall" in x and "align='Right'" in x for x in w["trace"]), w["trace"])
        self.assertEqual(by[("bim_wall", "neither")]["result"],
                         ["refused", "invalid_input", "points [[x, y] …] (the wall's line, mm) or base (a sketch or wire's label): one of them."])
        self.assertEqual(by[("bim_wall", "base without edges")]["result"],
                         ["refused", "invalid_input", "base: Empty has no edges to run a wall along; give a sketch or wire, or points [[x, y] …]."])
        self.assertEqual(by[("bim_wall", "base with edges")]["result"][1]["length"], 7000.0)
        sec = by[("bim_section", "model call 41")]
        self.assertEqual(sec["result"][1]["cuts"], ["Plot"])
        self.assertEqual(sec["result"][1]["object"], "Plan cut")
        self.assertEqual(by[("bim_section", "nothing to cut")]["result"][2], "Nothing to cut: no BIM objects here; give objects, or make some first (bim_wall …).")
        self.assertEqual(by[("bim_section", "no maker")]["result"][:2], ["refused", "unavailable"])
        ref = by[("bim_reference", "part and name")]
        self.assertEqual({k: ref["result"][1][k] for k in ("reference", "file", "part")}, {"reference": "Xref", "file": "other.FCStd", "part": "Body"})
        self.assertNotIn("step", ref["result"][1])
        self.assertEqual(by[("bim_reference", "no file")]["result"],
                         ["refused", "not_found", "path '/nowhere/x.FCStd': no such file. Give the full path of an .FCStd (or .ifc, .dxf) to reference."])


# ---- the child: a stand-in FreeCAD, the old handlers and the new entries ----------------------

def _stand_in():
    """FreeCAD, Part and Arch as far as these tools reach, every call and
    every property set written to TRACE."""
    import math
    import types

    trace = []
    state = {"doc": None}

    def show(v):
        if isinstance(v, Obj):
            return f"<{v.Name}>"
        if isinstance(v, (list, tuple)):
            return "[" + ", ".join(show(x) for x in v) + "]"
        if isinstance(v, dict):
            return "{" + ", ".join(f"{k}: {show(x)}" for k, x in v.items()) + "}"
        return repr(v)

    class Fake:
        def __init__(self, name="fake"):
            object.__setattr__(self, "_n", name)

        def __getattr__(self, k):
            if k.startswith("__"):
                raise AttributeError(k)
            return Fake(f"{self._n}.{k}")

        def __call__(self, *a, **k):
            return Fake(self._n + "()")

        def __iter__(self):
            return iter(())

        def __repr__(self):
            return f"Fake({self._n})"

    class Module(types.ModuleType):
        def __getattr__(self, k):
            if k.startswith("__"):
                raise AttributeError(k)
            return Fake(f"{self.__name__}.{k}")

    class Vec:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            if isinstance(x, Vec):
                x, y, z = x.x, x.y, x.z
            self.x, self.y, self.z = float(x), float(y), float(z)

        def __sub__(self, o):
            return Vec(self.x - o.x, self.y - o.y, self.z - o.z)

        def __add__(self, o):
            return Vec(self.x + o.x, self.y + o.y, self.z + o.z)

        @property
        def Length(self):
            return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

        def __repr__(self):
            return f"V({self.x:g}, {self.y:g}, {self.z:g})"

    class Record:
        def __init__(self, *a):
            self.a = a

        def __repr__(self):
            return f"{type(self).__name__}({', '.join(show(x) for x in self.a)})"

    class Placement(Record):
        pass

    class Rotation(Record):
        pass

    class Edge:
        def __init__(self, length):
            self.Length = length

    class Shape:
        def __init__(self, edges=(), null=False):
            self.Edges, self._null = [Edge(x) for x in edges], null

        def isNull(self):
            return self._null

        def __repr__(self):
            return f"Shape({[e.Length for e in self.Edges]})"

    class Obj:
        def __init__(self, name, type_, **kw):
            self.__dict__.update({"Name": name, "TypeId": type_, "Label": name, "InList": [], **kw})

        def __setattr__(self, k, v):
            trace.append(f"{self.Name}.{k} = {show(v)}")
            self.__dict__[k] = v

        def isDerivedFrom(self, t):
            return t == self.TypeId

        def getStatusString(self):
            return "Valid"

    class Doc:
        Label = Name = "Doc"

        def __init__(self):
            self.Objects = []

        def add(self, o):
            self.Objects.append(o)
            return o

        def addObject(self, type_, name):
            n, i = name, 0
            while any(o.Name == n for o in self.Objects):
                i += 1
                n = f"{name}{i:03d}"
            trace.append(f"addObject({type_!r}, {n!r})")
            return self.add(Obj(n, type_))

        def getObject(self, name):
            return next((o for o in self.Objects if o.Name == name), None)

        def getObjectsByLabel(self, label):
            return [o for o in self.Objects if o.Label == label]

        def removeObject(self, name):
            trace.append(f"removeObject({name!r})")
            self.Objects = [o for o in self.Objects if o.Name != name]

        def recompute(self):
            trace.append("recompute()")

    class Session:
        def __init__(self):
            self.doc, self.steps = Doc(), []
            state["doc"] = self.doc

        def unique(self, label, own=None):
            taken = {o.Label for o in self.doc.Objects if o is not own}
            if label not in taken:
                return label
            n = 2
            while f"{label} {n}" in taken:
                n += 1
            return f"{label} {n}"

        def snapshot(self, tool):
            trace.append(f"snapshot({tool!r})")
            self.steps.append({"tool": tool})

    def polygon(points):
        trace.append(f"makePolygon({show(points)})")
        return Shape([(points[i + 1] - points[i]).Length for i in range(len(points) - 1)])

    def maker(name, type_, **attrs):
        def make(*a, **kw):
            trace.append(f"{name}({', '.join([show(x) for x in a] + [f'{k}={show(v)}' for k, v in kw.items()])})")
            o = state["doc"].add(Obj(type_ + str(len(state["doc"].Objects)), type_, **attrs))
            if name == "makeReference":
                o.__dict__["Part"] = a[1] or ""
            return o

        return make

    fc, part, arch = Module("FreeCAD"), Module("Part"), Module("Arch")
    fc.Vector, fc.Placement, fc.Rotation, fc.GuiUp = Vec, Placement, Rotation, False
    part.Shape, part.makePolygon = Shape, polygon
    arch.makeWall = maker("makeWall", "Wall", IfcType="Wall")
    arch.makeSectionPlane = maker("makeSectionPlane", "SectionPlane")
    arch.makeReference = maker("makeReference", "Reference")
    sys.modules.update({"FreeCAD": fc, "Part": part, "Arch": arch})
    return types.SimpleNamespace(trace=trace, Session=Session, Obj=Obj, Shape=Shape, arch=arch)


def _old(name):
    """A family module as it was at BASE, loaded beside today's."""
    import importlib.util
    import tempfile

    src = _git("show", f"{BASE}:agentlink/families/{name}.py")
    d = tempfile.mkdtemp()
    path = os.path.join(d, f"{name}_before.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location(f"agentlink.families.{name}_before", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _tool(mod, session, name, code):
    """The module's tool of that name: the handler's (code) or the entry's."""
    from agentlink import runners

    made = runners.entries()
    hits = [t for t in mod.tools(session) if t.name == name]
    if code:
        # At BASE the name is a Tool(...) in the list after the data tools.
        hits = [t for t in hits if not (name in made and t is hits[0] and len(hits) > 1)]
    if len(hits) != 1:
        raise AssertionError(f"{name}: {len(hits)} tools in {mod.__name__}")
    return hits[0]


def _cases(fc, tmp):
    Obj, Shape = fc.Obj, fc.Shape

    def empty(s):
        pass

    def bases(s):
        s.doc.add(Obj("Sketch", "Sketcher::SketchObject", Shape=Shape([4000, 3000])))
        s.doc.add(Obj("Empty", "Part::Feature", Shape=Shape([])))
        s.doc.add(Obj("Null", "Part::Feature", Shape=Shape([5], null=True)))
        s.doc.add(Obj("Sheet", "Spreadsheet::Sheet"))
        s.doc.add(Obj("Wall", "Part::Feature"))

    def house(s):
        wall = s.doc.add(Obj("Wall001", "Wall", IfcType="Wall", Label="Outer walls"))
        level = s.doc.add(Obj("Level", "Floor", IfcType="Building Storey", Label="Ground floor", Group=[wall]))
        wall.InList.append(level)
        building = s.doc.add(Obj("Building", "Building", IfcType="Building", Label="House", Group=[level]))
        level.InList.append(building)
        site = s.doc.add(Obj("Site", "Site", IfcType="Site", Label="Plot", Group=[building]))
        building.InList.append(site)
        s.doc.add(Obj("Sheet", "Spreadsheet::Sheet", IfcType="x", Label="Schedule"))
        s.doc.add(Obj("Box", "Part::Feature"))

    def no_maker(s):
        house(s)
        fc.arch.makeSectionPlane = None

    file = os.path.join(tmp, "other.FCStd")
    with open(file, "w") as f:
        f.write("x")
    sq = [[0, 0], [8000, 0], [8000, 6000], [0, 6000]]
    return [
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
        ("bim_section", "no maker", no_maker, {"objects": ["Nope"], "normal": [0, 0, 0]}),
        ("bim_reference", "the file", empty, {"path": file}),
        ("bim_reference", "part and name", empty, {"path": file, "part": "Body", "name": "Xref"}),
        ("bim_reference", "label taken", bases, {"path": file, "name": "Sketch"}),
        ("bim_reference", "no file", empty, {"path": "/nowhere/x.FCStd"}),
        ("bim_reference", "a folder", empty, {"path": tmp, "name": "x"}),
        ("bim_reference", "no path", empty, {}),
        ("bim_reference", "an empty path", empty, {"path": "", "part": "Body"}),
    ]


def _main(mode):
    import tempfile

    fc = _stand_in()
    from agentlink.protocol import ToolError

    families = {"bim": "bim", "bim_gaps": "bim_gaps"}
    old = {g: _old(m) for g, m in families.items()}
    if mode == "--before":
        out = {}
        for name, group in CONVERTED.items():
            t = _tool(old[group], fc.Session(), name, True)
            out[name] = {"name": t.name, "description": t.description, "inputSchema": t.schema, "changes": t.changes, "reads": t.reads, "group": old[group].GROUP}
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    import importlib

    new = {g: importlib.import_module(f"agentlink.families.{m}") for g, m in families.items()}
    rows = []
    for tool, case, prepare, args in _cases(fc, tempfile.mkdtemp()):
        row = {"tool": tool, "case": case}
        for which, mods in (("old", old), ("new", new)):
            maker = fc.arch.makeSectionPlane
            del fc.trace[:]
            s = fc.Session()
            prepare(s)
            t = _tool(mods[CONVERTED[tool]], s, tool, which == "old")
            try:
                res = ["ok", t.fn(json.loads(json.dumps(args)))]
            except ToolError as e:
                res = ["refused", e.code, e.message]
            except Exception as e:  # noqa: BLE001 - a crash is compared as one
                res = ["crashed", type(e).__name__, str(e)]
            fc.arch.makeSectionPlane = maker
            row[which] = {"result": res, "trace": list(fc.trace), "objects": [o.Label for o in s.doc.Objects]}
        rows.append(row)
    print(json.dumps(rows, ensure_ascii=False, default=repr))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--before", "--behave"):
        _main(sys.argv[1])
    else:
        unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in FreeCAD of tests/test_datapart2_data.py: tests/_datapart_standin.py
# as it is, and on top of it what the rest of the Part tools reach (model_more.py
# and part_more.py): FreeCAD's parametric wires, compounds, ruled surfaces,
# sections and 2D offsets as objects whose shape a recompute makes, BOPTools'
# split features, attachment, datums, slices, projection, defeaturing and a
# Mesh module. Nothing of the first stand-in is changed for its own test: this
# one is only ever installed in this test's child process.
import math
import types

MODES = ["Deactivated", "Translate", "ObjectXY", "ObjectXZ", "ObjectYZ", "FlatFace", "NormalToEdge", "FrenetNB", "Concentric", "TwoPointLine",
         "AxisOfCurvature", "AxisOfInertia1", "ObjectZ", "Vertex", "CenterOfCurvature", "CenterOfMass"]
WIRES = ("Part::Line", "Part::Circle", "Part::Ellipse", "Part::RegularPolygon", "Part::Helix", "Part::Spiral", "Part::Plane", "Part::Polygon")
DATUMS = ("Part::DatumPoint", "Part::DatumLine", "Part::DatumPlane", "Part::LocalCoordinateSystem", "PartDesign::Point", "PartDesign::Line",
          "PartDesign::Plane", "PartDesign::CoordinateSystem")


def install():
    import sys

    import _datapart_standin

    fc = _datapart_standin.install()
    flag, log, show, trace, Shape, Obj, Vec, part = fc.flag, fc.log, fc.show, fc.trace, fc.Shape, fc.Obj, fc.Vec, fc.part
    Doc = type(fc.Session().doc)
    Placement = fc.fc.Placement

    def fails(what):
        if what in flag("fail", ()):
            raise RuntimeError(f"{what}: BRep_API: command not done")

    # ---- shapes: Part.Shape() is the empty one; slices, sections, projection, defeaturing ----

    first_init = Shape.__init__

    def init(self, *a, **kw):
        if not a and not kw:
            return first_init(self, "empty", "Compound", null=True, solids=0, shells=0)
        return first_init(self, *a, **kw)

    Shape.__init__ = init
    Shape.CenterOfMass = property(lambda self: self.box.Center)

    def reach(self, n):
        b = self.box
        span = [x * n.x + y * n.y + z * n.z for x in (b.XMin, b.XMax) for y in (b.YMin, b.YMax) for z in (b.ZMin, b.ZMax)]
        return min(span), max(span)

    def slice_(self, n, d):
        log("slice", self, n, d)
        lo, hi = reach(self, n)
        if not lo <= d <= hi:
            return []
        return [fc.wire(f"slice of {self.tag} at {d:g} #{i}", [(0, 0, d), (10, 0, d), (10, 10, d), (0, 10, d)], closed=flag("slice_closed", True))
                for i in range(flag("slice_loops", 1))]

    def section(self, other):
        log("section", self, other)
        meet = self.box.gap(other.box) <= 1e-9 and not flag("no_section")
        return Shape(f"section of {self.tag} by {other.tag}", "Compound", self.box.lo, self.box.hi, edges=4 if meet else 0, closed=flag("section_closed", True),
                     solids=0, shells=0, wires=1 if meet else 0)

    def defeaturing(self, subs):
        log("defeaturing", self, [x.tag for x in subs])
        fails("defeaturing")
        how = flag("defeature", "ok")
        if how == "same":
            return self
        if how == "null":
            return Shape()
        return self._like(f"defeatured {self.tag}", faces=self.nfaces - len(subs), volume=self.Volume + 10.0, solids=0 if how == "no solid" else self.nsolids)

    def sew_shape(self, *a):
        log("sewShape", self, *a)
        fails("sewShape")
        if flag("sews"):
            self.nshells, self.closed = 1, True

    def multi_fuse(self, others, tol=0.0):
        log("multiFuse", self, [o.tag for o in others], tol)
        fails("multiFuse")
        return Shape("fused faces", "Compound", self.box.lo, self.box.hi, area=self.Area, faces=1 + len(others), edges=4, closed=False, solids=0, shells=0)

    def landed(self, w, how):
        fails("project")
        if w.tag in flag("misses", ()) or flag("misses") == "all":
            return Shape()
        return Shape(f"{w.tag} {how} {self.tag}", "Compound", self.box.lo, self.box.hi, edges=max(w.nedges, 1), closed=False, solids=0, shells=0)

    def parallel(self, w, d):
        log("makeParallelProjection", self, w, d)
        return landed(self, w, "cast on")

    def project(self, edges):
        log("project", self, [e.tag for e in edges])
        return landed(self, edges[0], "dropped on")

    def from_mesh(self, topology, tol):
        log("makeShapeFromMesh", len(topology[1]), tol)
        fails("makeShapeFromMesh")
        self.tag, self.null, self.nfaces, self.nedges = "faces of the mesh", False, len(topology[1]), 3 * len(topology[1])
        self.nshells, self.closed = flag("mesh_shells", 1), True
        self.box.lo, self.box.hi = (0.0, 0.0, 0.0), (10.0, 10.0, 10.0)

    first_fix = Shape.fix

    def fix(self, *a):
        fails("fix")
        first_fix(self, *a)
        if flag("fix_opens"):  # a fix that leaves shells and no solid
            self.nsolids, self.nshells = 0, flag("fix_opens")
        return True

    Shape.fix = fix
    Shape.slice, Shape.section, Shape.defeaturing, Shape.sewShape, Shape.multiFuse = slice_, section, defeaturing, sew_shape, multi_fuse
    Shape.makeParallelProjection, Shape.project, Shape.makeShapeFromMesh = parallel, project, from_mesh

    def make_plane(length, width, at=None, n=None):
        log("makePlane", length, width, at, n)
        at = at or Vec()
        return Shape("plane", "Face", (at.x, at.y, at.z), (at.x + length, at.y + width, at.z), area=length * width, faces=1, edges=4, wires=1, solids=0, shells=0)

    def make_line(p, q):
        log("makeLine", p, q)
        return fc.wire("line", [p, q], closed=False, kind="Edge")

    def make_shell(faces):
        log("makeShell", [f.tag for f in faces])
        fails("makeShell")
        lo, hi = faces[0].box.lo, faces[0].box.hi
        return Shape(f"shell made of {len(faces)}", "Shell", lo, hi, area=sum(f.Area for f in faces), faces=len(faces), edges=4 * len(faces),
                     closed=flag("shell_closed", True), solids=0)

    class Round(type):
        """Part.Circle: a case says whether an edge's curve is one."""

        def __instancecheck__(cls, x):
            return bool(flag("round_edges"))

    part.makePlane, part.makeLine, part.makeShell, part.Circle = make_plane, make_line, make_shell, Round("Circle", (), {})
    part.BSplineCurve.parameter = lambda self, p: p
    part.BSplineCurve.value = lambda self, p: p + Vec(0, 0, flag("fit_off", 0.001))

    # ---- objects: attachment, and the shapes FreeCAD's own features compute ----

    first_set = Obj.__setattr__

    def set_(self, k, v):
        if k == "MapMode" and v not in flag("takes_modes", MODES):
            raise ValueError(f"'{v}' is not part of the enumeration")
        first_set(self, k, "Deactivated" if k == "MapMode" and flag("detaches") else v)  # detaches: FreeCAD falls back to no attachment

    def extension(self, name):
        trace.append(f"{self.Name}.addExtension({name!r})")
        fails("addExtension")
        self.__dict__.update(attachable())

    Obj.__setattr__ = set_
    Obj.getEnumerationsOfProperty = lambda self, prop: list(flag("map_modes", MODES))
    Obj.addExtension = extension

    def attachable():
        return {"AttachmentOffset": Placement(), "MapMode": "Deactivated", ("Support" if flag("old_support") else "AttachmentSupport"): None}

    def curve_shape(o):
        d, kind = o.__dict__, o.TypeId.split("::")[-1]
        if kind == "Line":
            return fc.wire(f"{o.Name}'s line", [(d["X1"], d["Y1"], d["Z1"]), (d["X2"], d["Y2"], d["Z2"])], closed=False)
        if kind == "Polygon":
            return fc.wire(f"{o.Name}'s polyline", d["Nodes"], closed=bool(d["Close"]))
        if kind == "Plane":
            return fc.face(f"{o.Name}'s plane", [(0, 0, 0), (d["Length"], d["Width"], 0)], area=d["Length"] * d["Width"])
        r = d.get("Radius", d.get("MajorRadius", d.get("Circumradius", 1.0)))
        return fc.wire(f"{o.Name}'s {kind.lower()}", [(-r, -r, 0), (r, r, d.get("Height", 0.0))], closed=kind in ("Ellipse", "RegularPolygon") or kind == "Circle" and "Angle1" not in d)

    def compound_shape(o):
        xs = [x.Shape for x in o.__dict__["Links"]]
        lo = tuple(min(x.box.lo[i] for x in xs) for i in range(3))
        hi = tuple(max(x.box.hi[i] for x in xs) for i in range(3))
        return Shape(f"{o.Name}'s compound", "Compound", lo, hi, volume=sum(x.Volume for x in xs), area=sum(x.Area for x in xs), faces=sum(x.nfaces for x in xs),
                     edges=sum(x.nedges for x in xs), solids=sum(x.nsolids for x in xs), wires=0, shells=0)

    def ruled_shape(o):
        return Shape(f"{o.Name}'s surface", "Face", (0, 0, 0), (10, 10, 5), area=125.0, faces=1, edges=4, solids=0, shells=0, wires=1)

    def section_shape(o):
        b, t = o.__dict__["Base"].Shape, o.__dict__["Tool"].Shape
        meet = b.box.gap(t.box) <= 1e-9 and not flag("no_section")
        return Shape(f"{o.Name}'s curves", "Compound", b.box.lo, b.box.hi, edges=4 if meet else 0, closed=flag("section_closed", True), solids=0, shells=0, wires=1 if meet else 0)

    def offset2d_shape(o):
        src = o.__dict__["Source"].Shape
        if flag("offset2d") == "null":
            return Shape()
        return src._like(f"{o.Name}'s outline", area=src.Area + o.__dict__["Value"])

    def body_shape(o):
        """A PartDesign Body built on a base feature (picks.bake makes one): that feature's shape."""
        base = o.__dict__.get("BaseFeature")
        return base.Shape if base is not None else Shape()

    COMPUTES = {"PartDesign::Body": body_shape, "Part::Compound": compound_shape, "Part::RuledSurface": ruled_shape, "Part::Section": section_shape, "Part::Offset2D": offset2d_shape}
    COMPUTES.update({t: curve_shape for t in WIRES})

    first_add = Doc.addObject

    def add_object(self, type_, name):
        if type_ in flag("no_types", ()):
            raise TypeError(f"No document object type called '{type_}'")
        o = first_add(self, type_, name)
        if type_ in COMPUTES:
            o.__dict__.update(computes=COMPUTES[type_], Shape=Shape())
        if type_ in WIRES or type_ in DATUMS:
            o.__dict__.update(attachable())
        return o

    Doc.addObject = add_object

    # ---- BOPTools' split features ----

    def split_shape(f):
        d = f.__dict__
        if flag("split") == "null":
            return Shape()
        parts = [d["Base"]] if d["splits"] == "slice" else list(d["Objects"])
        n = flag("pieces", 2 if d["splits"] != "fragments" else 3)
        box = parts[0].Shape.box
        for x in parts[1:]:
            box = box.union(x.Shape.box)
        return Shape(f"{d['splits']} of {', '.join(x.Label for x in parts)}", "Compound", box.lo, box.hi, volume=sum(x.Shape.Volume for x in parts), faces=6 * n, edges=12 * n,
                     solids=n, shells=n)

    split = fc.Module("BOPTools.SplitFeatures")

    def proxy(kind, splits):
        def make(f):
            log(f"Feature{kind}", f)
            f.__dict__.update(computes=split_shape, splits=splits, Shape=Shape())
            if fc.fc.GuiUp:
                f.__dict__["ViewObject"] = fc.View(f.Name)
        return make

    for kind, splits in (("Slice", "slice"), ("BooleanFragments", "fragments"), ("XOR", "xor")):
        setattr(split, f"Feature{kind}", proxy(kind, splits))
        setattr(split, f"ViewProvider{kind}", (lambda k: lambda vo: log(f"ViewProvider{k}", vo.owner))(kind))
    fc.mods["BOPTools"].SplitFeatures = split

    # ---- Mesh ----

    mesh = fc.Module("Mesh")

    class MeshData:
        def __init__(self, path=None, facets=None):
            if path is not None:
                log("Mesh", path.replace("\\", "/").rsplit("/", 1)[-1])
                fails("Mesh")
            self.CountFacets = flag("facets", 12) if facets is None else facets
            self.Topology = ([], [(0, 1, 2)] * self.CountFacets)

    mesh.Mesh = MeshData
    sys.modules.update({"BOPTools.SplitFeatures": split, "Mesh": mesh})
    fc.mods.update({"BOPTools.SplitFeatures": split, "Mesh": mesh})

    fc.MeshData, fc.attachable, fc.math = MeshData, attachable, math
    fc.ns = types.SimpleNamespace
    return fc

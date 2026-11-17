# SPDX-License-Identifier: LGPL-2.1-or-later
# A stand-in FreeCAD for tests/test_bim_data.py: FreeCAD, Part, Arch, Draft
# and the IFC modules as far as the BIM tools reach, in plain Python. It is
# not FreeCAD's geometry (a box's faces, a polygon's area and little more):
# it is one fixed world on which the old handlers and the new data entries
# are run side by side, every maker call, object made or removed and
# property set written to TRACE, so the two can be compared step for step.
# Only ever installed in a child process (install() puts it in sys.modules).
import math
import sys
import types


def install():
    trace = []
    state = {"doc": None, "flags": {}}

    def flag(k, default=None):
        return state["flags"].get(k, default)

    def show(v):
        if isinstance(v, Obj):
            return f"<{v.Name}>"
        if isinstance(v, (list, tuple)):
            return "[" + ", ".join(show(x) for x in v) + "]"
        if isinstance(v, dict):
            return "{" + ", ".join(f"{k}: {show(x)}" for k, x in v.items()) + "}"
        if isinstance(v, float):
            return f"{v:.6g}"
        return repr(v)

    def log(name, *a, **kw):
        trace.append(f"{name}({', '.join([show(x) for x in a] + [f'{k}={show(v)}' for k, v in kw.items()])})")

    class Module(types.ModuleType):
        """A module whose names can be taken away for a case (flags["missing"])."""

        def __getattribute__(self, k):
            if not k.startswith("__") and f"{types.ModuleType.__getattribute__(self, '__name__')}.{k}" in state["flags"].get("missing", ()):
                raise AttributeError(k)
            return types.ModuleType.__getattribute__(self, k)

    # ---- vectors and placements ------------------------------------------------------------

    class Vec:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            if isinstance(x, Vec):
                x, y, z = x.x, x.y, x.z
            self.x, self.y, self.z = float(x), float(y), float(z)

        def __sub__(self, o):
            return Vec(self.x - o.x, self.y - o.y, self.z - o.z)

        def __add__(self, o):
            return Vec(self.x + o.x, self.y + o.y, self.z + o.z)

        def __mul__(self, k):
            return Vec(self.x * k, self.y * k, self.z * k)

        __rmul__ = __mul__

        def __neg__(self):
            return self * -1

        def __eq__(self, o):
            return isinstance(o, Vec) and (self.x, self.y, self.z) == (o.x, o.y, o.z)

        def __hash__(self):
            return hash((self.x, self.y, self.z))

        @property
        def Length(self):
            return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

        def cross(self, o):
            return Vec(self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z, self.x * o.y - self.y * o.x)

        def dot(self, o):
            return self.x * o.x + self.y * o.y + self.z * o.z

        def normalize(self):
            n = self.Length
            if n == 0:
                raise RuntimeError("Cannot normalize null vector")
            self.x, self.y, self.z = self.x / n, self.y / n, self.z / n
            return self

        def negative(self):
            return self * -1

        def multiply(self, k):
            self.x, self.y, self.z = self.x * k, self.y * k, self.z * k
            return self

        def getAngle(self, o):
            return math.acos(max(-1.0, min(1.0, self.dot(o) / (self.Length * o.Length))))

        def __repr__(self):
            return f"V({self.x:.6g}, {self.y:.6g}, {self.z:.6g})"

    class Record:
        def __init__(self, *a):
            self.a = a

        def __repr__(self):
            return f"{type(self).__name__}({', '.join(show(x) for x in self.a)})"

    class Rotation(Record):
        def multiply(self, o):
            return Rotation(self, o)

    class Matrix(Record):
        pass

    class Placement:
        def __init__(self, base=None, rot=None):
            if isinstance(base, Placement):
                base, rot = Vec(base.Base), base.Rotation
            self.__dict__.update(Base=Vec() if base is None else base, Rotation=Rotation() if rot is None else rot, owner=None)

        def __setattr__(self, k, v):
            trace.append(f"{self.owner or 'a placement'}.Placement.{k} = {show(v)}")
            self.__dict__[k] = v

        def __repr__(self):
            return f"Placement({show(self.Base)}, {show(self.Rotation)})"

    # ---- shapes ---------------------------------------------------------------------------------

    class Box:
        def __init__(self, pts):
            xs, ys, zs = ([getattr(p, k) for p in pts] or [0.0] for k in "xyz")
            self.XMin, self.XMax, self.YMin, self.YMax, self.ZMin, self.ZMax = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
            self.XLength, self.YLength, self.ZLength = self.XMax - self.XMin, self.YMax - self.YMin, self.ZMax - self.ZMin
            self.DiagonalLength = math.sqrt(self.XLength ** 2 + self.YLength ** 2 + self.ZLength ** 2)

        def isValid(self):
            return True

        def intersect(self, o):
            return not (self.XMax < o.XMin or o.XMax < self.XMin or self.YMax < o.YMin or o.YMax < self.YMin or self.ZMax < o.ZMin or o.ZMax < self.ZMin)

    class Vertex:
        def __init__(self, p):
            self.Point = p

    class Shape:
        """One class for every kind: an edge, a wire, a face, a solid, a compound."""

        def __init__(self, kind="compound", pts=(), edges=(), wires=(), faces=(), solids=(), volume=0.0, area=0.0, null=False, closed=False,
                     normal=None, flat=True):
            self.kind, self.pts, self.Edges, self.Wires, self.Faces, self.Solids = kind, list(pts), list(edges), list(wires), list(faces), list(solids)
            self.Volume, self.Area, self.null, self.closed, self.normal, self.flat = volume, area, null, closed, normal or Vec(0, 0, 1), flat
            self.Placement = None
            self.ParameterRange, self.FirstParameter, self.LastParameter = (0.0, 1.0, 0.0, 1.0), 0.0, 1.0

        @property
        def Vertexes(self):
            return [Vertex(p) for p in self.pts]

        OrderedVertexes = Vertexes

        @property
        def Length(self):
            return (self.pts[-1] - self.pts[0]).Length if self.kind == "edge" else sum(e.Length for e in self.Edges)

        @property
        def BoundBox(self):
            return Box(self.pts)

        @property
        def CenterOfMass(self):
            n = max(len(self.pts), 1)
            return Vec(sum(p.x for p in self.pts) / n, sum(p.y for p in self.pts) / n, sum(p.z for p in self.pts) / n)

        def isNull(self):
            return self.null

        def isValid(self):
            return not flag("invalid_shapes")

        def isClosed(self):
            return self.closed

        def normalAt(self, u, v):
            return Vec(self.normal)

        def tangentAt(self, t):
            return Vec(self.pts[-1] - self.pts[0]).normalize()

        def findPlane(self):
            return object() if self.flat else None

        def getElement(self, sub):
            kind, i = sub.rstrip("0123456789"), int(sub[len(sub.rstrip("0123456789")):])
            return {"Face": self.Faces, "Edge": self.Edges}[kind][i - 1]

        def extrude(self, v):
            log("extrude", self, v)
            moved = [p + v for p in self.pts]
            if self.kind == "face":
                out = Shape("solid", self.pts + moved, volume=self.Area * v.Length, edges=self.Edges)
                out.Faces = [Shape("face", self.pts, area=self.Area, normal=v * -1), Shape("face", moved, area=self.Area, normal=v)]
                out.Solids = [out]
                return out
            faces = [Shape("face", e.pts + [p + v for p in e.pts], area=e.Length * v.Length) for e in (self.Edges or [self])]
            return Shape("face", self.pts + moved, edges=self.Edges, faces=faces, area=sum(f.Area for f in faces))

        def cut(self, o):
            log("cut", self, o)
            out = Shape("solid", self.pts, volume=max(self.Volume - o.Volume, 0.0), faces=self.Faces, edges=self.Edges)
            out.Solids = [out]
            return out

        def common(self, o):
            log("common", self, o)
            vol = min(self.Volume, o.Volume) if self.BoundBox.intersect(o.BoundBox) else 0.0
            out = Shape("solid", self.pts, volume=vol, null=vol == 0.0)
            out.Solids = [out] if vol else []
            return out

        def __repr__(self):
            return f"{self.kind}({len(self.pts)} points, {self.Volume or self.Area or 0:.6g})"

    def edge(p, q):
        return Shape("edge", [p, q])

    def polygon(points):
        log("makePolygon", points)
        pts = [Vec(p) for p in points]
        w = Shape("wire", pts, edges=[edge(pts[i], pts[i + 1]) for i in range(len(pts) - 1)], closed=len(pts) > 2 and pts[0] == pts[-1])
        w.Wires = [w]
        return w

    def face(w):
        log("Face", w)
        if not isinstance(w, Shape) or not w.closed or len({p.z for p in w.pts}) > 1:
            raise RuntimeError("Failed to create face from wire")
        twice = sum(p.x * q.y - q.x * p.y for p, q in zip(w.pts, w.pts[1:]))
        f = Shape("face", w.pts, edges=w.Edges, wires=[w], area=abs(twice) / 2, closed=True, normal=Vec(0, 0, 1 if twice >= 0 else -1))
        f.Faces = [f]
        return f

    def box(length, width, height, at=None, _log=True):
        if _log:
            log("makeBox", length, width, height, at)
        o = at or Vec()
        c = [Vec(o.x + i * length, o.y + j * width, o.z + k * height) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
        b = Shape("solid", c, volume=float(length * width * height))
        side = lambda keep, n, area: Shape("face", [p for p in c if keep(p)], area=area, normal=n, closed=True)  # noqa: E731
        b.Faces = [side(lambda p: p.x == o.x, Vec(-1, 0, 0), width * height), side(lambda p: p.x != o.x, Vec(1, 0, 0), width * height),
                   side(lambda p: p.y == o.y, Vec(0, -1, 0), length * height), side(lambda p: p.y != o.y, Vec(0, 1, 0), length * height),
                   side(lambda p: p.z == o.z, Vec(0, 0, -1), length * width), side(lambda p: p.z != o.z, Vec(0, 0, 1), length * width)]
        for f in b.Faces:
            f.Edges = [edge(f.pts[0], f.pts[1]), edge(f.pts[1], f.pts[3]), edge(f.pts[3], f.pts[2]), edge(f.pts[2], f.pts[0])]
            f.Wires = [Shape("wire", f.pts, edges=f.Edges, closed=True)]
        b.Edges = [e for f in b.Faces for e in f.Edges]
        b.Solids = [b]
        return b

    def compound(shapes):
        log("makeCompound", shapes)
        return Shape("compound", [p for x in shapes for p in x.pts], edges=[e for x in shapes for e in x.Edges], faces=[f for x in shapes for f in x.Faces],
                     solids=[x for x in shapes if x.kind == "solid" and x.Volume], volume=sum(x.Volume for x in shapes))

    def line(p, q):
        log("makeLine", p, q)
        e = edge(p, q)
        e.Edges = [e]
        return e

    def cylinder(r, h, at, d):
        log("makeCylinder", r, h, at, d)
        c = Shape("solid", [at, at + Vec(d).normalize() * h], volume=math.pi * r * r * h)
        c.Solids = [c]
        return c

    # ---- objects and the document ---------------------------------------------------------------

    def proxy(name):
        return type(name, (), {})()

    class Quantity:
        def __init__(self, v):
            self.Value = v

    class Obj:
        def __init__(self, name, type_, **kw):
            self.__dict__.update({"Name": name, "TypeId": type_, "Label": name, "InList": [], "OutList": [], **kw})

        def __setattr__(self, k, v):
            trace.append(f"{self.Name}.{k} = {show(v)}")
            if k == "Placement":
                v = Placement(v)
                v.__dict__["owner"] = self.Name
            if k in self.__dict__.get("refuses", ()):
                raise ValueError(f"{v!r} is not part of the enumeration")
            self.__dict__[k] = v

        def __getattr__(self, k):
            if k == "Placement":
                pl = Placement()
                pl.__dict__["owner"] = self.Name
                self.__dict__[k] = pl
                return pl
            if k == "PropertiesList":
                return [p for p in self.__dict__ if p[:1].isupper() and p not in ("Name", "TypeId", "InList", "OutList")]
            if k == "OutListRecursive":
                out = []
                for c in self.OutList:
                    out += [c] + c.OutListRecursive
                return out
            raise AttributeError(k)

        def isDerivedFrom(self, t):
            return t == self.TypeId or t in self.__dict__.get("kinds", ())

        def getStatusString(self):
            return "Valid"

        def addProperty(self, type_, name, group="", doc=""):
            trace.append(f"{self.Name}.addProperty({type_!r}, {name!r})")
            self.__dict__[name] = [] if "List" in type_ else "" if "String" in type_ else 0.0
            return self

        def getEnumerationsOfProperty(self, p):
            return list(self.__dict__.get("enums", {}).get(p, []))

        def addObject(self, o):
            trace.append(f"{self.Name}.addObject({show(o)})")
            self.__dict__["Group"] = list(self.__dict__.get("Group", [])) + [o]
            o.InList.append(self)

        def removeObject(self, o):
            trace.append(f"{self.Name}.removeObject({show(o)})")
            self.__dict__["Group"] = [x for x in self.Group if x is not o]
            o.InList.remove(self)

        def set(self, cell, v):
            trace.append(f"{self.Name}.set({cell!r}, {v!r})")

        def recompute(self):
            trace.append(f"{self.Name}.recompute()")

    class Doc:
        Label = Name = "Doc"

        def __init__(self):
            self.Objects = []

        def add(self, o):
            self.Objects.append(o)
            return o

        def new(self, type_, _name=None, **kw):
            """An object of the stand-in's own making (a maker's result, a case's furniture)."""
            base = _name or type_.split("::")[-1]
            n, i = base, 0
            while any(o.Name == n for o in self.Objects):
                i += 1
                n = f"{base}{i:03d}"
            return self.add(Obj(n, type_, **kw))

        def addObject(self, type_, name):
            o = self.new(type_, name)
            trace.append(f"addObject({type_!r}, {o.Name!r})")
            if type_ == "Part::Box":
                o.__dict__.update(Length=10.0, Width=10.0, Height=10.0)
            if type_ == "App::DocumentObjectGroup":
                o.__dict__.update(Group=[])
            if type_ == "Image::ImagePlane":
                o.__dict__.update(XSize=100.0, YSize=100.0)
            return o

        def getObject(self, name):
            return next((o for o in self.Objects if o.Name == name), None)

        def getObjectsByLabel(self, label):
            return [o for o in self.Objects if o.Label == label]

        def removeObject(self, name):
            trace.append(f"removeObject({name!r})")
            gone = self.getObject(name)
            self.Objects = [o for o in self.Objects if o.Name != name]
            for o in self.Objects:
                if gone in o.InList:
                    o.InList.remove(gone)

        def recompute(self, objs=None):
            trace.append("recompute()")
            for o in self.Objects:
                if "full" in o.__dict__ and not flag("no_cut"):  # a wall or structure: its solid less what is cut from it
                    sh = o.__dict__["Shape"]
                    sh.Volume = max(o.full - sum(x.Shape.Volume for x in o.Subtractions), 0.0)

        def mergeProject(self, p):
            log("mergeProject", p)
            self.new("Part::Feature", "Merged")
            # A file Agent Link worked on carries its hidden records object (agentlink/store.py);
            # FreeCAD merges it in under the next free name.
            if flag("merge_records"):
                self.new("App::FeaturePython", "AgentLinkRecords001").__dict__["Label"] = "Agent Link records001"

    class Session:
        def __init__(self, out_dir="/tmp"):
            self.doc, self.steps, self.out_dir = Doc(), [], out_dir
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

        def body(self, ref):
            from agentlink.protocol import ToolError

            raise ToolError("invalid_state", "No body here.")

    def doc():
        return state["doc"]

    # ---- Arch ---------------------------------------------------------------------------------

    def component_props():
        return {"Additions": [], "Subtractions": [], "Material": None, "IfcType": "Undefined", "IfcProperties": {}, "IfcData": {},
                "StandardCode": "", "CloneOf": None, "VerticalArea": Quantity(0.0), "HorizontalArea": Quantity(0.0)}

    def prism_of(base, height):
        """A solid standing on base's outline (a face's area × height; a line's box otherwise)."""
        sh = getattr(base, "Shape", None)
        pts = list(sh.pts) if sh is not None else []
        area = sh.Area if sh is not None else 0.0
        out = Shape("solid", pts + [p + Vec(0, 0, height) for p in pts], volume=area * height, edges=sh.Edges if sh is not None else [])
        out.Solids = [out] if out.Volume else []
        out.Faces = [Shape("face", pts, area=area, normal=Vec(0, 0, -1)), Shape("face", [p + Vec(0, 0, height) for p in pts], area=area, normal=Vec(0, 0, 1))]
        return out

    def make_wall(base=None, length=None, width=None, height=None, align="Center", offset=None, face=None, name=None):
        log("makeWall", base, width=width, height=height, align=align)
        run = sum(e.Length for e in base.Shape.Edges) if base is not None and getattr(base, "Shape", None) else 0.0
        pts = list(base.Shape.pts) if base is not None and getattr(base, "Shape", None) else []
        sh = Shape("solid", pts + [p + Vec(0, 0, height or 0) for p in pts], volume=run * (width or 0) * (height or 0))
        sh.Solids = [sh] if sh.Volume else []
        o = doc().new("Part::FeaturePython", "Wall", **component_props(), Base=base, Width=width, Height=height, Align=align, Offset=0.0, Shape=sh,
                      full=sh.Volume, Proxy=proxy("_Wall"), enums={"IfcType": IFC_TYPES})
        o.__dict__["IfcType"] = "Wall"
        if base is not None:
            o.OutList.append(base)
            base.InList.append(o)
        return o

    def make_structure(base=None, length=None, width=None, height=None, name=None):
        log("makeStructure", base, length=length, width=width, height=height)
        if base is not None:
            sh = prism_of(base, height or 0)
        else:
            sh = box(length, width, height, Vec(-length / 2, -width / 2, 0), _log=False)
        o = doc().new("Part::FeaturePython", "Structure", **component_props(), Base=base, Height=height, Normal=Vec(0, 0, 0), Shape=sh, full=sh.Volume,
                      Proxy=proxy("_Structure"), enums={"IfcType": IFC_TYPES})
        if base is not None:
            o.OutList.append(base)
            base.InList.append(o)
        return o

    def make_roof(base, face, angles, runs, idrel, thick, overhang):
        log("makeRoof", base, face, angles, runs, idrel, thick, overhang)
        heights = [r * math.tan(math.radians(a)) if a < 90 else 0.0 for a, r in zip(angles, runs)]
        z = base.Shape.pts[0].z
        # A hipped roof's underside meets lower than the tallest pane's own height (flags["hip"]: by how much).
        top = max(heights) - flag("hip", 0.0)
        under = Shape("face", [p for p in base.Shape.pts] + [Vec(0, 0, z + top)], normal=Vec(0, 0.5, -0.8))
        over = Shape("face", [Vec(0, 0, z + top + thick[0])], normal=Vec(0, 0.5, 0.8))
        sh = Shape("solid", base.Shape.pts + [Vec(0, 0, z + top + thick[0])], volume=1e9, faces=[over, under])
        sh.Solids = [sh]
        o = doc().new("Part::FeaturePython", "Roof", **component_props(), Base=base, Heights=[] if flag("no_heights") else heights, Shape=sh, Proxy=proxy("_Roof"))
        o.__dict__["IfcType"] = "Roof"
        if not flag("no_flip"):
            o.__dict__["Flip"] = False
        return o

    def make_stairs(base=None, length=None, width=None, height=None, steps=None, name=None):
        log("makeStairs", base, length=length, width=width, height=height, steps=steps)
        o = doc().new("Part::FeaturePython", "Stairs", **component_props(), Shape=box(length, width, height, _log=False), Proxy=proxy("_Stairs"))
        o.__dict__["IfcType"] = "Stair"
        return o

    def make_space(objs):
        log("makeSpace", objs)
        sh = objs[0].Shape
        area = sh.Faces[0].Area if sh.Faces else 0.0
        o = doc().new("Part::FeaturePython", "Space", **component_props(), Shape=sh, Area=Quantity(area), SpaceType="Undefined", Proxy=proxy("_Space"),
                      enums={"SpaceType": ["Undefined", "Room", "Office", "Restrooms", "Corridor / Transition", "Dining Area"]})
        o.__dict__["IfcType"] = "Space"
        if flag("no_space_type"):
            del o.__dict__["SpaceType"]
        return o

    def container(maker, type_, ifc, proxy_name):
        def make(objs=None, name=None):
            log(maker, objs)
            o = doc().new(type_, ifc.replace(" ", ""), Group=list(objs or []), IfcType=ifc, Proxy=proxy(proxy_name), Height=0.0)
            for x in objs or []:
                x.InList.append(o)
            return o

        return make

    def simple(maker, **attrs):
        def make(*a, **kw):
            log(maker, *a, **kw)
            if flag("gui") and maker in flag("gui"):
                raise RuntimeError("No module named FreeCADGui: Gui is not up")
            if flag("none") and maker in flag("none"):
                return None
            vals = {k: (v(*a, **kw) if callable(v) else v) for k, v in attrs.items()}
            return doc().new("Part::FeaturePython", maker[4:], **vals)

        return make

    def base_shape(base=None, *a, **kw):
        return getattr(base, "Shape", None) or Shape(null=True)

    def solid_of(base=None, *a, **kw):
        sh = getattr(base, "Shape", None)
        out = Shape("solid", list(sh.pts) if sh is not None else [], volume=5e6, edges=sh.Edges if sh is not None else [])
        out.Solids = [out]
        return out

    def make_panel(base=None, length=None, width=None, thickness=None, name=None):
        log("makePanel", base, length=length, width=width, thickness=thickness)
        sh = prism_of(base, thickness) if base is not None else box(length, width, thickness, Vec(-length / 2, -width / 2, 0), _log=False)
        return doc().new("Part::FeaturePython", "Panel", **component_props(), Base=base, Thickness=thickness, Normal=Vec(0, 0, 0), Shape=sh, Proxy=proxy("_Panel"))

    def make_component(base=None, name=None):
        log("makeComponent", base)
        if flag("gui") and "makeComponent" in flag("gui"):
            raise RuntimeError("Gui is not up")
        o = doc().new("Part::FeaturePython", "Component", **component_props(), Base=base, Shape=base_shape(base), Proxy=proxy("Component"),
                      enums={"IfcType": IFC_TYPES})
        if base is not None:
            o.OutList.append(base)
            base.InList.append(o)
        return o

    def clone_component(src):
        log("cloneComponent", src)
        if flag("none") and "cloneComponent" in flag("none"):
            return None
        o = doc().new("Part::FeaturePython", "Clone", **component_props(), Shape=src.Shape, Proxy=proxy("Component"))
        o.__dict__.update(CloneOf=src, Height=0.0)
        return o

    def join_walls(walls, delete=False):
        log("joinWalls", walls, delete=delete)
        if len({w.Width for w in walls}) > 1:
            return None
        return walls[-1]

    def make_material(name="Material"):
        log("makeMaterial", name)
        return doc().new("App::FeaturePython", "Material", Material={}, Proxy=proxy("_ArchMaterial"))

    def make_multi(name=None):
        log("makeMultiMaterial")
        return doc().new("App::FeaturePython", "MultiMaterial", Materials=[], Names=[], Thicknesses=[], Proxy=proxy("_ArchMultiMaterial"))

    def make_axis(num=1, size=1000, name=None):
        log("makeAxis", num, size)
        return doc().new("App::FeaturePython", "Axis", Distances=[], Angles=[], Length=0.0, Proxy=proxy("_Axis"))

    def make_profile(row):
        log("makeProfile", row)
        if flag("none") and "makeProfile" in flag("none"):
            return None
        f = Shape("face", [Vec(0, 0, 0), Vec(100, 0, 0), Vec(100, 200, 0), Vec(0, 200, 0)], area=7800.0, closed=True)
        return doc().new("Part::Part2DObjectPython", "Profile", Shape=f)

    def make_fence(section, post, path):
        log("makeFence", section, post, path)
        n = int(sum(e.Length for e in path.Shape.Edges) // (section.Length + post.Length))
        return doc().new("Part::FeaturePython", "Fence", **component_props(), Shape=box(1000, 100, 1200, _log=False), NumberOfSections=n, NumberOfPosts=n + 1)

    def make_truss(base):
        log("makeTruss", base)
        attrs = {} if flag("old_truss") else {"RodSections": 3, "RodMode": "/|/|/|", "enums": {"RodMode": flag("rod_modes", ["/|/|/|", "/\\/\\/\\", "/|\\|/|\\"])}}
        return doc().new("Part::FeaturePython", "Truss", **component_props(), Shape=solid_of(base), HeightStart=100.0, HeightEnd=100.0, StrutHeight=10.0,
                         StrutWidth=10.0, RodSize=2.0, **attrs, Proxy=proxy("Truss"))

    def make_covering(base=None, name=None):
        log("makeCovering", base)
        return doc().new("Part::FeaturePython", "Covering", **component_props(), Shape=box(1000, 1000, 10, _log=False), FinishMode="Solid Tiles", TileLength=0.0,
                         TileWidth=0.0, TileThickness=0.0, Proxy=proxy("Covering"))

    IFC_TYPES = ["Undefined", "Wall", "Slab", "Beam", "Column", "Footing", "Covering", "Railing", "Furniture", "Building Element Proxy", "Window", "Door",
                 "Sanitary Terminal", "Pipe Segment", "Reinforcing Bar", "Wall Standard Case"]
    fc, part, arch = Module("FreeCAD"), Module("Part"), Module("Arch")
    fc.Vector, fc.Placement, fc.Rotation, fc.Matrix, fc.GuiUp = Vec, Placement, Rotation, Matrix, False
    fc.getUserAppDataDir = lambda: "/nowhere/FreeCAD/"
    fc.ParamGet = lambda path: types.SimpleNamespace(GetString=lambda k, d="": flag("library", d))
    part.Shape, part.makePolygon, part.Face, part.makeBox, part.makeCompound, part.makeLine, part.makeCylinder = Shape, polygon, face, box, compound, line, cylinder
    part.Vertex = lambda p: Shape("vertex", [p])
    part.__sortEdges__ = lambda edges: list(edges)

    def insert(path, docname):
        log("Part.insert", path, docname)
        doc().new("Part::Feature", "Imported")

    part.insert = insert
    arch.makeWall, arch.makeStructure, arch.makeRoof, arch.makeStairs, arch.makeSpace = make_wall, make_structure, make_roof, make_stairs, make_space
    arch.makeBuilding = container("makeBuilding", "App::FeaturePython", "Building", "_Building")
    arch.makeSite = container("makeSite", "App::FeaturePython", "Site", "_Site")
    arch.makeFloor = container("makeFloor", "App::FeaturePython", "Building Storey", "_Floor")
    arch.makeSectionPlane = simple("makeSectionPlane", Proxy=lambda *a, **k: proxy("_SectionPlane"))
    arch.makeReference = simple("makeReference", Part=lambda f, p=None: p or "")
    arch.makeCurtainWall = simple("makeCurtainWall", **component_props(), Shape=solid_of, VerticalSections=1, HorizontalSections=1, VerticalMullionWidth=0.0,
                                  VerticalMullionHeight=0.0, HorizontalMullionWidth=0.0, HorizontalMullionHeight=0.0)
    arch.makeRebar = simple("makeRebar", **component_props(), Shape=lambda *a, **k: solid_of(a[1]), Direction=None, Proxy=lambda *a, **k: proxy("_Rebar"))
    arch.makeFrame = simple("makeFrame", **component_props(), Shape=solid_of, Rotation=0.0, Align=True)
    arch.makePanelCut = simple("makePanelCut", Shape=lambda p: Shape("wire", p.Shape.pts, edges=p.Shape.Edges))
    arch.makePanelSheet = simple("makePanelSheet", Width=1220.0, Height=2440.0, Group=lambda cuts: list(cuts))
    arch.makePanel, arch.makeComponent, arch.cloneComponent, arch.joinWalls = make_panel, make_component, clone_component, join_walls
    arch.makeMaterial, arch.makeMultiMaterial, arch.makeAxis, arch.makeProfile, arch.makeFence, arch.makeTruss = make_material, make_multi, make_axis, make_profile, make_fence, make_truss
    arch.makeCovering = make_covering

    profile = Module("ArchProfile")
    profile.readPresets = lambda: [[1, "HEB", "HEB200", "H", 200.0, 200.0, 9.0, 15.0], [2, "HEB", "HEB220", "H", 220.0, 220.0, 9.5, 16.0],
                                   [3, "IPE", "IPE100", "H", 55.0, 100.0, 4.1, 5.7], [4, "Timber", "T 50x100", "R", 50.0, 100.0]]

    # ---- Draft -----------------------------------------------------------------------------------

    draft, geomutils = Module("Draft"), Module("DraftGeomUtils")

    def get_type(o):
        return {"_Wall": "Wall", "_Panel": "Panel", "_Structure": "Structure"}.get(type(getattr(o, "Proxy", None)).__name__, o.TypeId)

    def make_wire(points, closed=False):
        log("make_wire", points, closed=closed)
        pts = [Vec(p) for p in points] + ([Vec(points[0])] if closed else [])
        w = Shape("wire", pts, edges=[edge(pts[i], pts[i + 1]) for i in range(len(pts) - 1)], closed=closed)
        return doc().new("Part::Part2DObjectPython", "Wire", Shape=w)

    def make_clone(o):
        log("make_clone", o)
        return doc().new("Part::FeaturePython", "DraftClone", Shape=o.Shape)

    def make_view(o):
        log("make_shape2dview", o)
        attrs = {} if flag("old_views") else {"ProjectionMode": "Solid"}
        return doc().new("Part::Part2DObjectPython", "Shape2DView", **attrs)

    draft.getType, draft.make_wire, draft.make_clone, draft.make_shape2dview = get_type, make_wire, make_clone, make_view

    def find_wires(edges):
        """Runs of edges that share an end, each a wire (in the order given)."""
        wires = []
        for e in edges:
            if wires and wires[-1].pts[-1] == e.pts[0]:
                w = wires[-1]
                w.pts.append(e.pts[1])
                w.Edges.append(e)
                w.closed = w.pts[0] == w.pts[-1]
            else:
                wires.append(Shape("wire", list(e.pts), edges=[e]))
        return wires

    geomutils.findWires = find_wires
    geomutils.hasCurves = lambda w: any(getattr(e, "curved", False) for e in w.Edges)

    # ---- nesting ---------------------------------------------------------------------------------

    nesting = Module("ArchNesting")
    nesting.ROTATIONS = [0, 90, 180, 270]

    class Nester:
        def __init__(self):
            self.container, self.objects, self.results = None, [], []

        def addObjects(self, objs):
            log("Nester.addObjects", objs)
            self.objects = list(objs)

        def run(self):
            log("Nester.run", rotations=list(nesting.ROTATIONS))
            if flag("no_nest"):
                return None
            # FreeCAD's nester gives up on the whole run, with a printed reason, when one of the
            # rotations it tries leaves a piece no place (ArchNesting.py run(): "Could not determine
            # location on sheet. Aborting."): here it lays the pieces out only at the rotation
            # nest_only, tried alone.
            if flag("nest_only") is not None and list(nesting.ROTATIONS) != [flag("nest_only")]:
                print("Placing piece 2 / 2 Area: 18.00 dm^2 : ", ", ".join(str(r) for r in nesting.ROTATIONS), ", ", end="")
                print("Could not determine location on sheet. Aborting.")
                return None
            sheets = [[o] for o in self.objects] if flag("many_sheets") else [list(self.objects)]
            self.results = [sheets]
            return sheets

        def apply(self):
            log("Nester.apply")

    nesting.Nester = Nester

    # ---- IFC -------------------------------------------------------------------------------------

    ifc, ifc_geom, importers, export_ifc, import_ifc = (Module(n) for n in ("ifcopenshell", "ifcopenshell.geom", "importers", "importers.exportIFC", "importers.importIFC"))

    class IfcFile:
        schema = "IFC4"

        def by_type(self, k):
            return [1, 2] if k == "IfcWall" else [1] if k == "IfcSlab" else []

    ifc.open = lambda p: IfcFile()
    ifc.version = "0.8"
    ifc.geom = ifc_geom
    ifc_geom.settings = lambda: types.SimpleNamespace(set=lambda k, v: None)

    def export(objs, p):
        log("exportIFC.export", objs)
        if flag("export_fails"):
            raise ValueError("not enough values to unpack (expected 2, got 1)")
        with open(p, "w") as f:
            f.write("ISO-10303-21;" * 4)

    def insert_ifc(p, docname):
        log("importIFC.insert", docname)
        doc().new("Part::Feature", "Half", IfcType="Wall")
        if flag("import_fails"):
            raise RuntimeError("settings disagree")
        doc().new("Part::Feature", "IfcSlab", IfcType="Slab")
        doc().new("Part::Feature", "IfcWall", IfcType="Wall")

    export_ifc.export, import_ifc.insert = export, insert_ifc
    importers.exportIFC, importers.importIFC = export_ifc, import_ifc

    mods = {"FreeCAD": fc, "Part": part, "Arch": arch, "ArchProfile": profile, "Draft": draft, "DraftGeomUtils": geomutils, "ArchNesting": nesting,
            "ifcopenshell": ifc, "ifcopenshell.geom": ifc_geom, "importers": importers, "importers.exportIFC": export_ifc, "importers.importIFC": import_ifc}

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def importing(name, globals=None, locals=None, fromlist=(), level=0):
        # A module a case takes away (flags["missing"]: "ifcopenshell") is not importable either.
        if level == 0 and name.split(".")[0] in state["flags"].get("missing", ()):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, globals, locals, fromlist, level)

    import builtins

    builtins.__import__ = importing
    sys.modules.update(mods)
    return types.SimpleNamespace(trace=trace, state=state, Session=Session, Obj=Obj, Shape=Shape, Vec=Vec, Quantity=Quantity, arch=arch, part=part, draft=draft,
                                 polygon=polygon, face=face, box=box, edge=edge, proxy=proxy, doc=doc, component_props=component_props)

# SPDX-License-Identifier: LGPL-2.1-or-later
# A stand-in FreeCAD for tests/test_datapart_data.py: FreeCAD and Part as far
# as the Part tools kept as data reach, in plain Python. It is not FreeCAD's
# geometry: a shape here is a kind, a box, a volume, an area and counts of
# faces and edges, and every operation on one answers another by simple
# rules (a fuse adds volumes, a cut takes one away where the boxes meet).
# It is one fixed world on which the old handlers and the new data entries
# are run side by side, every shape operation, object made or removed and
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
        if isinstance(v, bool):
            return repr(v)
        if isinstance(v, float):
            return f"{v:.6g}"
        return repr(v)

    def log(name, *a, **kw):
        trace.append(f"{name}({', '.join([show(x) for x in a] + [f'{k}={show(v)}' for k, v in kw.items()])})")

    def fails(what):
        """A case can make one operation fail (flags["fail"]: its names)."""
        if what in flag("fail", ()):
            raise RuntimeError(f"{what}: BRep_API: command not done")

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

        def distanceToPoint(self, o):
            return (self - o).Length

        def __repr__(self):
            return f"V({self.x:.6g}, {self.y:.6g}, {self.z:.6g})"

    class Rotation:
        def __init__(self, *a):
            self.a = a
            self.Axis, self.Angle = Vec(0, 0, 1), 0.0
            if len(a) == 2 and isinstance(a[0], Vec) and isinstance(a[1], (int, float)):
                self.Axis, self.Angle = Vec(a[0]), math.radians(a[1])

        def multiply(self, o):
            return Rotation(self, o)

        def __repr__(self):
            return f"Rotation({', '.join(show(x) for x in self.a)})"

    class Matrix:
        def __init__(self, *a):
            self.ops = [("of",) + a] if a else []

        def move(self, v):
            self.ops.append(("move", v))

        def scale(self, *f):
            self.ops.append(("scale",) + f)

        def multiply(self, o):
            m = Matrix()
            m.ops = [("mul", list(self.ops), list(o.ops))]
            return m

        def __repr__(self):
            return f"Matrix({show(self.ops)})"

    class Placement:
        def __init__(self, base=None, rot=None, centre=None):
            if isinstance(base, Placement):
                base, rot, centre = Vec(base.Base), base.Rotation, base.centre
            self.__dict__.update(Base=Vec() if base is None else base, Rotation=Rotation() if rot is None else rot, centre=centre, owner=None)

        def __setattr__(self, k, v):
            trace.append(f"{self.owner or 'a placement'}.Placement.{k} = {show(v)}")
            self.__dict__[k] = v

        def multiply(self, o):
            p = Placement(self.Base + o.Base, Rotation(self.Rotation, o.Rotation), self.centre)
            return p

        def __repr__(self):
            return f"Placement({show(self.Base)}, {show(self.Rotation)}{'' if self.centre is None else ', ' + show(self.centre)})"

    # ---- shapes ---------------------------------------------------------------------------------

    class Box:
        def __init__(self, lo=None, hi=None):
            self.lo, self.hi = lo, hi

        def isValid(self):
            return self.lo is not None

        def _g(self, i, which):
            return (self.lo if which == 0 else self.hi)[i] if self.lo is not None else 0.0

        XMin = property(lambda s: s._g(0, 0))
        YMin = property(lambda s: s._g(1, 0))
        ZMin = property(lambda s: s._g(2, 0))
        XMax = property(lambda s: s._g(0, 1))
        YMax = property(lambda s: s._g(1, 1))
        ZMax = property(lambda s: s._g(2, 1))
        XLength = property(lambda s: s.XMax - s.XMin)
        YLength = property(lambda s: s.YMax - s.YMin)
        ZLength = property(lambda s: s.ZMax - s.ZMin)

        @property
        def DiagonalLength(self):
            return math.sqrt(self.XLength ** 2 + self.YLength ** 2 + self.ZLength ** 2)

        @property
        def Center(self):
            return Vec((self.XMin + self.XMax) / 2, (self.YMin + self.YMax) / 2, (self.ZMin + self.ZMax) / 2)

        def gap(self, o):
            """The distance between two boxes (0 when they meet)."""
            if self.lo is None or o.lo is None:
                return 0.0
            d = [max(o.lo[i] - self.hi[i], self.lo[i] - o.hi[i], 0.0) for i in range(3)]
            return math.sqrt(sum(x * x for x in d))

        def union(self, o):
            if self.lo is None:
                return Box(o.lo, o.hi)
            if o.lo is None:
                return Box(self.lo, self.hi)
            return Box(tuple(min(a, b) for a, b in zip(self.lo, o.lo)), tuple(max(a, b) for a, b in zip(self.hi, o.hi)))

        def moved(self, v):
            if self.lo is None:
                return Box()
            d = (v.x, v.y, v.z)
            return Box(tuple(a + b for a, b in zip(self.lo, d)), tuple(a + b for a, b in zip(self.hi, d)))

    class Vertex:
        def __init__(self, p):
            self.Point = p
            self.ShapeType = "Vertex"

        def __repr__(self):
            return f"Vertex({show(self.Point)})"

    class Curve:
        def __init__(self, kind):
            self.kind = kind

    class Shape:
        """One class for every kind: a tag (what made it), its ShapeType,
        a box, a volume, an area, and how many faces and edges it has."""

        def __init__(self, tag="shape", kind="Solid", lo=None, hi=None, volume=0.0, area=0.0, faces=0, edges=0, closed=True, valid=True, null=False,
                     solids=None, wires=None, normal=None, pts=None, flat=True, shells=None):
            self.tag, self.ShapeType, self.box, self.Volume, self.Area = tag, kind, Box(lo, hi), float(volume), float(area)
            self.nfaces, self.nedges, self.closed, self.valid, self.null = faces, edges, closed, valid, null
            self.nsolids = (1 if kind == "Solid" else 0) if solids is None else solids
            self.nwires = (1 if kind == "Wire" else 0) if wires is None else wires
            self.nshells = (1 if kind in ("Solid", "Shell") else 0) if shells is None else shells
            self.normal, self.pts, self.flat = normal or Vec(0, 0, 1), list(pts or []), flat
            self.Placement = Placement()
            self.Placement.__dict__["owner"] = tag
            self._sub = {}

        # what it is made of: each sub-shape made once, so it is the same one each time it is asked for
        def _subs(self, kind, n):
            out = []
            for i in range(1, n + 1):
                key = f"{kind}{i}"
                if key not in self._sub:
                    self._sub[key] = self._make_sub(kind, i)
                out.append(self._sub[key])
            return out

        def _make_sub(self, kind, i):
            t = f"{self.tag}.{kind}{i}"
            if kind == "Face":
                f = Shape(t, "Face", self.box.lo, self.box.hi, area=(self.Area / self.nfaces if self.nfaces else 0.0), faces=1, edges=4, wires=1, closed=True,
                          normal=Vec(0, 0, 1 if i % 2 else -1))
                f.edges_of = self  # a face's edges are its solid's own (the first four, here)
                return f
            if kind == "Edge":
                return Shape(t, "Edge", self.box.lo, self.box.hi, edges=1, closed=False)
            if kind == "Wire":
                return Shape(t, "Wire", self.box.lo, self.box.hi, edges=max(self.nedges, 1), closed=self.closed, pts=self.pts)
            if kind == "Shell":
                return Shape(t, "Shell", self.box.lo, self.box.hi, area=self.Area, faces=self.nfaces, edges=self.nedges, closed=self.closed)
            return Shape(t, "Solid", self.box.lo, self.box.hi, volume=self.Volume / max(self.nsolids, 1), area=self.Area / max(self.nsolids, 1),
                         faces=self.nfaces, edges=self.nedges, valid=self.valid)

        @property
        def Faces(self):
            return [self] if self.ShapeType == "Face" else self._subs("Face", self.nfaces)

        @property
        def Edges(self):
            if getattr(self, "edges_of", None) is not None:
                return self.edges_of.Edges[:4]
            return [self] if self.ShapeType == "Edge" else self._subs("Edge", self.nedges)

        @property
        def Wires(self):
            return [self] if self.ShapeType == "Wire" else self._subs("Wire", self.nwires)

        @property
        def Shells(self):
            return [self] if self.ShapeType == "Shell" else self._subs("Shell", self.nshells)

        @property
        def Solids(self):
            return [self] if self.ShapeType == "Solid" and self.nsolids == 1 else self._subs("Solid", self.nsolids)

        @property
        def Vertexes(self):
            return [Vertex(p) for p in self.pts]

        OrderedVertexes = Vertexes

        @property
        def OuterWire(self):
            return self._subs("Wire", 1)[0]

        @property
        def BoundBox(self):
            return self.box

        @property
        def Length(self):
            return self.box.DiagonalLength

        @property
        def Curve(self):
            return Curve("Line")

        def isNull(self):
            return self.null

        def isValid(self):
            return self.valid

        def isClosed(self):
            return self.closed

        def isSame(self, o):
            return self is o

        def valueAt(self, t):
            """A curve's point at one of its ends (its first parameter 0, its last 1)."""
            return Vec(self.pts[0] if t == self.FirstParameter else self.pts[-1])

        FirstParameter, LastParameter = 0.0, 1.0

        def ancestorsOfType(self, e, kind):
            """The faces an edge bounds: two in a closed shell; in an open one the first two edges have one."""
            return [1, 2] if self.closed or e not in self.Edges[:2] else [1]

        def childShapes(self):
            """A compound's pieces (its solids, here); anything else is its own one piece."""
            return self.Solids if self.ShapeType == "Compound" else [self]

        def getElement(self, sub):
            kind = sub.rstrip("0123456789")
            i = int(sub[len(kind):])
            return {"Face": self.Faces, "Edge": self.Edges, "Vertex": self.Vertexes}[kind][i - 1]

        def findPlane(self):
            return types.SimpleNamespace(Axis=Vec(self.normal)) if self.flat else None

        def normalAt(self, u, v):
            return Vec(self.normal)

        def discretize(self, Number=10):
            return list(self.pts)

        def removeSplitter(self):
            log("removeSplitter", self)
            return self

        def distToShape(self, o):
            return (self.box.gap(o.box), [], [])

        def _like(self, tag, **kw):
            d = dict(kind=self.ShapeType, lo=self.box.lo, hi=self.box.hi, volume=self.Volume, area=self.Area, faces=self.nfaces, edges=self.nedges, closed=self.closed,
                     valid=self.valid, null=self.null, solids=self.nsolids, wires=self.nwires, normal=self.normal, pts=self.pts, flat=self.flat, shells=self.nshells)
            d.update(kw)
            return Shape(tag, **d)

        def copy(self):
            log("copy", self)
            return self._like(f"copy of {self.tag}")

        def reversed(self):
            return self._like(f"reversed {self.tag}")

        def reverse(self):
            log("reverse", self)
            self.Volume = -self.Volume

        def translate(self, v):
            log("translate", self, v)
            self.box = self.box.moved(v)

        def rotate(self, c, axis, angle):
            log("rotate", self, c, axis, angle)
            self.tag += f" turned {angle:g}"

        def scale(self, f, c=None):
            log("scale", self, f, c)
            self.Volume *= f ** 3

        def mirror(self, c, n):
            log("mirror", self, c, n)
            # the far side of the plane through c: a box as far beyond it as this one is before it
            d = Vec(n) * (2 * (Vec(c) - self.box.Center).dot(n))
            return self._like(f"mirror of {self.tag}", lo=self.box.moved(d).lo, hi=self.box.moved(d).hi)

        def transformGeometry(self, m):
            log("transformGeometry", self, m)
            return self._like(f"transformed {self.tag}")

        def fix(self, *a):
            log("fix", self, *a)
            if flag("fix_mends"):
                self.valid, self.closed = True, True
            return True

        def sewShape(self):
            log("sewShape", self)
            if flag("sews"):  # the faces close into one shell
                self.nshells, self.closed = 1, True

        def _bool(self, name, others):
            others = list(others) if isinstance(others, (list, tuple)) else [others]
            log(name, self, others)
            fails(name)
            box = self.box
            meet = [o for o in others if self.box.gap(o.box) <= 1e-9]
            if name == "fuse":
                for o in others:
                    box = box.union(o.box)
                vol = self.Volume + (0.0 if flag("fuse_adds_nothing") else sum(o.Volume for o in others))
                nf = self.nfaces + (0 if flag("fuse_adds_nothing") else sum(o.nfaces for o in others))
                solids = 1 if len(meet) == len(others) else 1 + len(others) - len(meet)
                if flag("fuse_adds_nothing"):
                    box, solids = self.box, 1
                solids = flag("fuse_solids", solids)
            elif name == "cut":
                vol = max(self.Volume - sum(o.Volume for o in meet) * flag("cut_share", 0.5), 0.0)
                nf, solids = self.nfaces + (0 if flag("cut_same_faces") else len(meet)), 1
            else:
                vol = min([self.Volume] + [o.Volume for o in meet]) * flag("common_share", 0.5) if meet else 0.0
                nf, solids = self.nfaces if meet else 0, 1 if meet else 0
            out = Shape(f"{name}({self.tag}; {', '.join(o.tag for o in others)})", "Solid", box.lo, box.hi, volume=vol, area=self.Area, faces=nf, edges=self.nedges,
                        solids=solids, valid=not flag("bool_invalid"))
            return out

        def fuse(self, o):
            return self._bool("fuse", o)

        def cut(self, o):
            return self._bool("cut", o)

        def common(self, o):
            return self._bool("common", o)

        def _round(self, name, size, edges):
            log(name, self, size, [e.tag for e in edges])
            fails(name)
            broken = flag("broken", ())
            return self._like(f"{name}({self.tag})", volume=self.Volume - size * len(edges), faces=self.nfaces + len(edges), valid=name not in broken,
                              solids=0 if name + ":nosolid" in broken else self.nsolids)

        def makeFillet(self, size, edges):
            return self._round("makeFillet", size, edges)

        def makeChamfer(self, size, edges):
            return self._round("makeChamfer", size, edges)

        def makeOffsetShape(self, d, tol, **kw):
            log("makeOffsetShape", self, d, tol, **kw)
            fails("makeOffsetShape")
            mode = flag("offset", "solid")
            return self._like(f"offset({self.tag})", volume=self.Volume + d * self.Area, solids=0 if mode in ("faces", "none") else self.nsolids,
                              faces=0 if mode == "none" else self.nfaces, null=mode == "null")

        def makeThickness(self, faces, t, *rest):
            log("makeThickness", self, [f.tag for f in faces], t, *rest)
            fails("makeThickness")
            mode = flag("shell", "solid")
            return self._like(f"shelled({self.tag})", volume=0.0 if mode == "empty" else self.Volume - abs(t) * self.Area / 4, valid=mode != "invalid",
                              faces=self.nfaces * 2 - len(faces))

        def extrude(self, v):
            log("extrude", self, v)
            fails("extrude")
            lo, hi = self.box.union(self.box.moved(v)).lo, self.box.union(self.box.moved(v)).hi
            if self.ShapeType == "Face" and not flag("extrude_no_solid"):
                return Shape(f"extruded {self.tag}", "Solid", lo, hi, volume=self.Area * v.Length, area=2 * self.Area + 40 * v.Length, faces=6, edges=12)
            return Shape(f"extruded {self.tag}", "Shell", lo, hi, area=40 * v.Length, faces=max(self.nedges, 1), edges=4 * max(self.nedges, 1),
                         closed=False, solids=0)

        def revolve(self, at, axis, angle):
            log("revolve", self, at, axis, angle)
            fails("revolve")
            mode = flag("revolve", "solid")
            if self.ShapeType == "Face" and mode == "solid":
                return Shape(f"revolved {self.tag}", "Solid", self.box.lo, self.box.hi, volume=self.Area * abs(angle) * flag("revolve_sign", 1.0), area=4 * self.Area, faces=4, edges=6)
            return Shape(f"revolved {self.tag}", "Shell", self.box.lo, self.box.hi, area=4 * self.Area, faces=4, edges=6, closed=mode == "shell", solids=0)

        def makePipeShell(self, profiles, solid, frenet, corners):
            log("makePipeShell", self, [p.tag for p in profiles], solid, frenet, corners)
            fails("makePipeShell")
            if solid and not flag("sweep_no_solid"):
                return Shape(f"swept {profiles[0].tag} along {self.tag}", "Solid", self.box.lo, self.box.hi, volume=250.0, area=300.0, faces=3, edges=3)
            return Shape(f"swept {profiles[0].tag} along {self.tag}", "Shell", self.box.lo, self.box.hi, area=300.0, faces=1, edges=4, closed=False, solids=0)

        def getFreeEdges(self):
            return types.SimpleNamespace(Edges=[] if self.closed else [1, 2])

        def __repr__(self):
            return f"{self.ShapeType}<{self.tag}>"

    # ---- makers -----------------------------------------------------------------------------------

    def solid(tag, lo, hi, volume=None, faces=6, edges=12, kind="Solid", **kw):
        size = [b - a for a, b in zip(lo, hi)]
        vol = size[0] * size[1] * size[2] if volume is None else volume
        return Shape(tag, kind, tuple(float(x) for x in lo), tuple(float(x) for x in hi), volume=vol, area=2 * (size[0] * size[1] + size[1] * size[2] + size[0] * size[2]),
                     faces=faces, edges=edges, **kw)

    def wire(tag, pts, closed=True, flat=True, kind="Wire", wires=None):
        pts = [Vec(*p) if not isinstance(p, Vec) else p for p in pts]
        xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
        return Shape(tag, kind, (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)), edges=max(len(pts) - 1, 1), closed=closed, pts=pts, flat=flat, solids=0,
                     shells=0, wires=wires)

    def curves(tag, ends):
        """A wire whose edges run between the points given: [(from, to) …], each its own curve."""
        w = wire(tag, [p for pq in ends for p in pq], closed=False)
        w.nedges = len(ends)
        for i, (p, q) in enumerate(ends, 1):
            w._sub[f"Edge{i}"] = wire(f"{tag}.Edge{i}", [p, q], closed=False, kind="Edge")
        return w

    def face(tag, pts, area=100.0):
        f = wire(tag, pts, kind="Face", wires=1)
        f.Area, f.nfaces = area, 1
        return f

    def make_polygon(points):
        log("makePolygon", points)
        pts = [Vec(p) for p in points]
        return wire(f"polygon of {len(pts)}", pts, closed=len(pts) > 2 and pts[0] == pts[-1])

    def make_circle(r, c=None, n=None):
        log("makeCircle", r, c, n)
        c = c or Vec()
        e = wire(f"circle {r:g}", [c - Vec(r, r, 0), c + Vec(r, r, 0)], kind="Edge")
        return e

    def make_wire(edges):
        log("Wire", [e.tag for e in edges])
        fails("Wire")
        e = list(edges)
        w = wire(f"wire of {', '.join(x.tag for x in e)}", [p for x in e for p in (x.pts or [Vec(*x.box.lo), Vec(*x.box.hi)])],
                 closed=all(x.closed for x in e) if not flag("open_wires") else False)
        return w

    def make_face(wires, maker=None):
        log("makeFace", [w.tag for w in wires], maker)
        fails("makeFace")
        f = wires[0]._like(f"face of {wires[0].tag}", kind="Face", area=flag("face_area", 100.0), faces=1, wires=len(wires), solids=0, shells=0)
        return f

    def face_of(w):
        log("Face", w)
        fails("Face")
        return w._like(f"face of {w.tag}", kind="Face", area=flag("face_area", 100.0), faces=1, wires=1, solids=0, shells=0)

    def make_shell(faces):
        log("Shell", [f.tag for f in faces])
        fails("Shell")
        lo, hi = faces[0].box.lo, faces[0].box.hi
        return Shape(f"shell of {len(faces)}", "Shell", lo, hi, area=sum(f.Area for f in faces), faces=len(faces), edges=4 * len(faces), closed=True, solids=0)

    def make_solid(shell):
        log("Solid", shell)
        fails("Solid")
        return Shape(f"solid of {shell.tag}", "Solid", shell.box.lo, shell.box.hi, volume=flag("solid_volume", 500.0), area=shell.Area, faces=shell.nfaces, edges=shell.nedges)

    def make_compound(shapes):
        log("Compound", [x.tag for x in shapes])
        box = Box()
        for x in shapes:
            box = box.union(x.box)
        return Shape(f"compound of {len(shapes)}", "Compound", box.lo, box.hi, volume=sum(x.Volume for x in shapes), area=sum(x.Area for x in shapes),
                     faces=sum(x.nfaces for x in shapes), edges=sum(x.nedges for x in shapes), solids=sum(x.nsolids for x in shapes),
                     wires=sum(x.nwires for x in shapes), shells=sum(x.nshells for x in shapes))

    def make_cylinder(r, h, at=None, d=None):
        log("makeCylinder", r, h)
        return solid(f"cylinder {r:g}x{h:g}", (-r, -r, 0), (r, r, h), volume=math.pi * r * r * h, faces=3, edges=3)

    def make_loft(ws, solid_, ruled, loop, deg):
        log("makeLoft", [w.tag for w in ws], solid_, ruled, loop, deg)
        plan = flag("loft", {})
        key = f"{'ruled' if ruled else 'smooth'}{deg}"
        which = "rebuilt" if ws[0].tag.startswith("rebuilt") else "given"  # a case may say how each try comes out
        how = plan.get(f"{which} {key}", plan.get(which, plan.get(key, plan.get("ruled" if ruled else "smooth", plan.get("all", "ok")))))
        if how == "raise":
            raise RuntimeError("BRepOffsetAPI_ThruSections: not done")
        box = Box()
        for w in ws:
            box = box.union(w.box)
        tag = f"loft {key} of {len(ws)}" + (f" [{how}]" if how != "ok" else "")
        if not solid_:
            return Shape(tag, "Shell", box.lo, box.hi, area=400.0, faces=len(ws) - 1, edges=4 * len(ws), closed=False, solids=0)
        return Shape(tag, "Solid", box.lo, box.hi, volume=-900.0 if how == "inside out" else 900.0, area=600.0, faces=len(ws) + 1, edges=3 * len(ws))

    class BSplineCurve:
        def interpolate(self, pts, PeriodicFlag=False):
            log("BSplineCurve.interpolate", pts, PeriodicFlag=PeriodicFlag)
            fails("interpolate")
            self.pts, self.closed = list(pts), PeriodicFlag

        def toShape(self):
            return wire(f"bspline of {len(self.pts)}", self.pts, closed=self.closed, kind="Edge")

    # ---- objects and the document ---------------------------------------------------------------

    PRIMS = {"Part::Box": {"Length": 10.0, "Width": 10.0, "Height": 10.0}, "Part::Cylinder": {"Radius": 2.0, "Height": 10.0, "Angle": 360.0},
             "Part::Sphere": {"Radius": 5.0}, "Part::Cone": {"Radius1": 2.0, "Radius2": 4.0, "Height": 10.0},
             "Part::Torus": {"Radius1": 10.0, "Radius2": 2.0},
             "Part::Wedge": {"Xmin": 0.0, "Ymin": 0.0, "Zmin": 0.0, "X2min": 2.0, "Z2min": 2.0, "Xmax": 10.0, "Ymax": 10.0, "Zmax": 10.0, "X2max": 8.0, "Z2max": 8.0},
             "Part::Prism": {"Polygon": 6, "Circumradius": 2.0, "Height": 10.0}, "Part::FeaturePython:Tube": {"OuterRadius": 5.0, "InnerRadius": 2.0, "Height": 10.0}}

    def prim_shape(o):
        """A primitive's solid from its sizes (recompute makes it)."""
        d, t = o.__dict__, o.__dict__.get("prim")
        if flag("empty_primitive"):
            return Shape(f"{o.Name}'s shape", "Compound", null=True, solids=0)
        if t == "Part::Box":
            return solid(f"{o.Name}'s shape", (0, 0, 0), (d["Length"], d["Width"], d["Height"]))
        if t == "Part::Sphere":
            r = d["Radius"]
            return solid(f"{o.Name}'s shape", (-r, -r, -r), (r, r, r), volume=4 / 3 * math.pi * r ** 3, faces=1, edges=3)
        if t == "Part::Torus":
            r, r2 = d["Radius1"], d["Radius2"]
            return solid(f"{o.Name}'s shape", (-r - r2, -r - r2, -r2), (r + r2, r + r2, r2), volume=2 * math.pi ** 2 * r * r2 ** 2, faces=1, edges=3)
        if t == "Part::Wedge":
            return solid(f"{o.Name}'s shape", (d["Xmin"], d["Ymin"], d["Zmin"]), (d["Xmax"], d["Ymax"], d["Zmax"]))
        if t == "Part::Cone":
            r, h = max(d["Radius1"], d["Radius2"]), d["Height"]
            return solid(f"{o.Name}'s shape", (-r, -r, 0), (r, r, h), volume=math.pi * h * (d["Radius1"] ** 2 + d["Radius1"] * d["Radius2"] + d["Radius2"] ** 2) / 3, faces=3, edges=3)
        if t == "Part::Prism":
            r, h = d["Circumradius"], d["Height"]
            return solid(f"{o.Name}'s shape", (-r, -r, 0), (r, r, h), volume=d["Polygon"] * r * r * h / 2, faces=d["Polygon"] + 2, edges=3 * d["Polygon"])
        if t == "Part::FeaturePython:Tube":
            r, h = d["OuterRadius"], d["Height"]
            return solid(f"{o.Name}'s shape", (-r, -r, 0), (r, r, h), volume=math.pi * h * (r ** 2 - d["InnerRadius"] ** 2), faces=4, edges=6)
        r, h = d["Radius"], d["Height"]
        return solid(f"{o.Name}'s shape", (-r, -r, 0), (r, r, h), volume=math.pi * r * r * h, faces=3, edges=3)

    def surface_shape(o):
        """A Surface feature's shape once recomputed: a case says how a sewing or a cut comes out."""
        kind, d = o.TypeId.split("::")[-1], o.__dict__
        if kind in flag("null_types", ()):
            return Shape(f"{o.Name}: nothing", "Compound", null=True, solids=0)
        if kind == "FeatureBlendCurve":
            return wire(f"{o.Name}'s curve", [(0, 0, 0), (3, 4, 0)], closed=False, kind="Edge")
        if kind == "Sewing":
            n = sum(len(subs) for _, subs in d["ShapeList"])
            how = flag("sewn", "open")
            return Shape(f"{o.Name}'s shell", "Shell" if how != "none" else "Compound", (0, 0, 0), (10, 10, 10), area=100.0 * n, faces=n, edges=4 * n,
                         closed=how == "closed", solids=0, shells=0 if how == "none" else 1)
        if kind == "Cut":
            x = d["ShapeList"][0].Shape
            how = flag("cut", "cut")
            return Shape(f"{o.Name}'s cut", "Shell", x.box.lo, x.box.hi, area=x.Area * (0.5 if how == "cut" else 1.0), faces=x.nfaces + (0 if how == "none" else 1),
                         edges=x.nedges, closed=False, solids=0, shells=1)
        return Shape(f"{o.Name}'s surface", "Face", (0, 0, 0), (10, 10, 0), area=100.0, faces=1, edges=4, solids=0, shells=0)

    class Obj:
        def __init__(self, name, type_, **kw):
            self.__dict__.update({"Name": name, "TypeId": type_, "Label": name, "InList": [], "OutList": [], "Visibility": True, **kw})

        def __setattr__(self, k, v):
            trace.append(f"{self.Name}.{k} = {show(v)}")
            if k == "Placement":
                v = Placement(v)
                v.__dict__["owner"] = self.Name
            self.__dict__[k] = v

        def __getattr__(self, k):
            if k == "Placement":
                pl = Placement()
                pl.__dict__["owner"] = self.Name
                self.__dict__[k] = pl
                return pl
            if k == "PropertiesList":
                return [p for p in self.__dict__ if p[:1].isupper() and p not in ("Name", "TypeId", "InList", "OutList")]
            if k == "InListRecursive":
                return list(self.InList)
            raise AttributeError(k)

        def isDerivedFrom(self, t):
            return t == self.TypeId or t in self.__dict__.get("kinds", ())

        def isValid(self):
            return not flag("objects_invalid") and self.TypeId not in flag("invalid_types", ())

        def getStatusString(self):
            if self.TypeId in flag("invalid_types", ()):
                return flag("status", "Curves are disjoint.")
            return "Valid" if not flag("objects_invalid") else "Radius of cylinder too small"

        def addProperty(self, type_, name, group="", doc=""):
            trace.append(f"{self.Name}.addProperty({type_!r}, {name!r})")
            self.__dict__[name] = [] if "List" in type_ else "" if "String" in type_ else 0.0
            return self

        def setEditorMode(self, prop, mode):
            pass

        def addObject(self, o):
            trace.append(f"{self.Name}.addObject({show(o)})")
            self.__dict__["Group"] = list(self.__dict__.get("Group", [])) + [o]
            o.InList.append(self)

        def removeObject(self, o):
            trace.append(f"{self.Name}.removeObject({show(o)})")
            self.__dict__["Group"] = [x for x in self.__dict__.get("Group", []) if x is not o]
            o.InList.remove(self)

        def recompute(self):
            trace.append(f"{self.Name}.recompute()")

    class View:
        """An object's view provider: what is set on it is written down."""

        def __init__(self, owner):
            self.__dict__["owner"] = owner

        def __setattr__(self, k, v):
            trace.append(f"{self.owner}.ViewObject.{k} = {show(v)}")
            self.__dict__[k] = v

    class Doc:
        Label = Name = "Doc"

        def __init__(self):
            self.Objects = []

        def add(self, o):
            self.Objects.append(o)
            return o

        def new(self, type_, _name=None, **kw):
            """An object of the stand-in's own making (a case's furniture)."""
            base = _name or type_.split("::")[-1]
            n, i = base, 0
            while any(o.Name == n for o in self.Objects):
                i += 1
                n = f"{base}{i:03d}"
            return self.add(Obj(n, type_, **kw))

        def addObject(self, type_, name):
            o = self.new(type_, name)
            trace.append(f"addObject({type_!r}, {o.Name!r})")
            if type_ in PRIMS:
                o.__dict__.update(PRIMS[type_], prim=type_)
            if type_ == "App::DocumentObjectGroup":
                o.__dict__.update(Group=[])
            if type_.startswith("Surface::"):
                o.__dict__.update(computes=surface_shape, Shape=Shape(f"{o.Name}, not yet made", "Compound", null=True, solids=0))
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
                if "prim" in o.__dict__:
                    o.__dict__["Shape"] = prim_shape(o)
                if "computes" in o.__dict__:  # a feature: its shape from what it is set to
                    o.__dict__["Shape"] = o.__dict__["computes"](o)

    class Session:
        def __init__(self, out_dir="/tmp"):
            self.doc, self.steps, self.out_dir = Doc(), [], out_dir
            self.last_hidden = []
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

            shown = [o for o in self.doc.Objects if getattr(o, "Shape", None) is not None and o.Shape.Solids and o.Visibility]
            if len(shown) == 1:
                return shown[0]
            raise ToolError("invalid_state" if not shown else "invalid_input", "No body here." if not shown else f"Which body: {', '.join(o.Label for o in shown)}.")

    def doc():
        return state["doc"]

    def body(label, shape, type_="Part::Feature", **kw):
        """A case's furniture: an object with a shape, under a label."""
        o = doc().new(type_, kw.pop("name", "Body"), Shape=shape, **kw)
        o.__dict__["Label"] = label
        return o

    # ---- the modules ------------------------------------------------------------------------------

    fc, part, basic, shapes_mod = Module("FreeCAD"), Module("Part"), Module("BasicShapes"), Module("BasicShapes.Shapes")
    fc.Vector, fc.Rotation, fc.Placement, fc.Matrix, fc.GuiUp = Vec, Rotation, Placement, Matrix, False
    fc.Units = types.SimpleNamespace(Quantity=type("Quantity", (), {}))
    fc.ActiveDocument = None
    fc.Console = types.SimpleNamespace(PrintMessage=lambda *a: None, PrintWarning=lambda *a: None, PrintError=lambda *a: None, PrintLog=lambda *a: None)
    fc.ParamGet = lambda p: types.SimpleNamespace(GetBool=lambda *a: False, GetInt=lambda *a: 0, GetString=lambda *a: "", GetFloat=lambda *a: 0.0)
    fc.Version = lambda: ["1", "1", "3"]
    part.Shape, part.Vertex, part.makePolygon, part.makeCircle, part.Wire, part.makeFace, part.Face = Shape, Vertex, make_polygon, make_circle, make_wire, make_face, face_of
    part.Shell, part.Solid, part.Compound, part.makeCompound, part.makeCylinder, part.makeLoft = make_shell, make_solid, make_compound, make_compound, make_cylinder, make_loft
    part.BSplineCurve, part.Line = BSplineCurve, type("Line", (), {})
    part.__sortEdges__ = lambda edges: list(edges)

    def add_tube(d, name):
        log("addTube", name)
        o = d.new("Part::FeaturePython", name)
        o.__dict__.update(PRIMS["Part::FeaturePython:Tube"], prim="Part::FeaturePython:Tube")
        if flag("tube_fails"):
            raise RuntimeError("no view provider")
        return o

    # ---- CompoundTools, BOPTools, files, Bézier patches ---------------------------------------------

    ctools, explode_mod, filter_mod, bop, joins = (Module(n) for n in ("CompoundTools", "CompoundTools.Explode", "CompoundTools.CompoundFilter", "BOPTools",
                                                                        "BOPTools.JoinFeatures"))

    def explode_compound(o):
        log("explodeCompound", o)
        g = doc().new("App::DocumentObjectGroup", "GroupExplode", Group=[])
        kids = []
        for i, piece in enumerate(o.Shape.childShapes()):
            c = doc().new("Part::FeaturePython", "CompoundFilter", Shape=piece)
            c.__dict__["Label"] = f"{o.Label}.{i}"
            kids.append(c)
        g.__dict__["Group"] = list(kids)
        return g, kids

    def filtered(f):
        if flag("filter_keeps", "some") == "none":
            return Shape("nothing kept", "Compound", null=True, solids=0)
        base = f.Base.Shape
        if f.FilterType == "specific items":
            n = len(f.items.split(";"))
            return base._like(f"{n} of {base.tag}", kind="Compound" if n > 1 else "Solid", solids=n, volume=base.Volume * n / max(base.nsolids, 1))
        return base._like(f"{f.FilterType} of {base.tag}", kind="Compound", solids=max(base.nsolids - 1, 1))

    def make_compound_filter(name, d):
        log("makeCompoundFilter", name)
        return d.new("Part::FeaturePython", name, computes=filtered, State=["Invalid"] if flag("filter_keeps") == "invalid" else [], WindowFrom=80.0, WindowTo=100.0)

    explode_mod.explodeCompound, filter_mod.makeCompoundFilter = explode_compound, make_compound_filter
    ctools.Explode, ctools.CompoundFilter = explode_mod, filter_mod

    def joined(j):
        if flag("join_fails"):
            return Shape("no join", "Compound", null=True, solids=0)
        parts = list(j.__dict__.get("Objects") or [j.__dict__.get("Base"), j.__dict__.get("Tool")])
        box = Box()
        for o in parts:
            box = box.union(o.Shape.box)
        return Shape(f"{j.joins} of {', '.join(o.Label for o in parts)}", "Solid" if not flag("join_open") else "Shell", box.lo, box.hi,
                     volume=0.0 if flag("join_open") else sum(o.Shape.Volume for o in parts), faces=12, edges=24, solids=0 if flag("join_open") else 1)

    def join_proxy(kind):
        def proxy(j):
            log(f"Feature{kind}", j)
            j.__dict__.update(computes=joined, joins=kind.lower(), State=["Invalid"] if flag("join_invalid") else [])
            if fc.GuiUp:
                j.__dict__["ViewObject"] = View(j.Name)
        return proxy

    for kind in ("Connect", "Embed", "Cutout"):
        setattr(joins, f"Feature{kind}", join_proxy(kind))
        setattr(joins, f"ViewProvider{kind}", (lambda k: lambda vo: log(f"ViewProvider{k}", vo.owner))(kind))
    bop.JoinFeatures = joins

    def read(p):
        log("read", p.rsplit("/", 1)[-1])
        fails("read")
        return Shape(f"read {p.rsplit('/', 1)[-1]}", "Compound", (0, 0, 0), (10, 10, 10), edges=flag("file_edges", 5), faces=2, solids=0)

    class BezierSurface:
        def __init__(self):
            self.poles = {}

        def increase(self, u, v):
            log("BezierSurface.increase", u, v)

        def setPole(self, i, j, p):
            log("BezierSurface.setPole", i, j, Vec(round(p.x, 6) + 0.0, round(p.y, 6) + 0.0, round(p.z, 6) + 0.0))
            self.poles[(i, j)] = p

        def toShape(self):
            xs = list(self.poles.values())
            return Shape("bezier patch", "Face", (min(p.x for p in xs), min(p.y for p in xs), min(p.z for p in xs)),
                         (max(p.x for p in xs), max(p.y for p in xs), max(p.z for p in xs)), area=1.0, faces=1, edges=4, solids=0, shells=0)

    part.read, part.BezierSurface, part.makeSolid = read, BezierSurface, make_solid

    shapes_mod.addTube = add_tube
    basic.Shapes = shapes_mod
    mods = {"FreeCAD": fc, "Part": part, "Surface": Module("Surface"), "BasicShapes": basic, "BasicShapes.Shapes": shapes_mod, "CompoundTools": ctools, "CompoundTools.Explode": explode_mod,
            "CompoundTools.CompoundFilter": filter_mod, "BOPTools": bop, "BOPTools.JoinFeatures": joins}

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def importing(name, globals=None, locals=None, fromlist=(), level=0):
        # A module a case takes away (flags["missing"]: "BasicShapes") is not importable either.
        if level == 0 and name.split(".")[0] in state["flags"].get("missing", ()):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, globals, locals, fromlist, level)

    import builtins

    builtins.__import__ = importing
    sys.modules.update(mods)

    # The readings every tool here ends with are agentlink.geometry's (not
    # part of what was converted): the stand-in's shapes answer them simply.
    from agentlink import geometry as geo

    def stats(sh):
        return {"volume": round(sh.Volume, 2), "area": round(sh.Area, 2), "faces": len(sh.Faces), "solids": len(sh.Solids),
                "box": [round(sh.box.XLength, 3), round(sh.box.YLength, 3), round(sh.box.ZLength, 3)]}

    def soundness(sh, solids_intended=False):
        trace.append(f"soundness({show(sh)})")
        problems = []
        if not sh.isValid():
            problems.append("The shape is not valid: a boolean or loft left it broken. Rebuild the last step.")
        if len(sh.Solids) != 1:
            problems.append(f"{len(sh.Solids)} solids where one is meant: pieces that do not touch, or none.")
        return {"ok": not problems, "problems": problems}

    geo.stats, geo.soundness = stats, soundness

    # shape_query's filter is measure's (not converted here): a case says which elements it picks.
    from agentlink.families import measure, picks

    def query(session, a, default_kind="face"):
        log("query", a)
        o = picks.solid_body(session, a.get("body"))
        kind = a.get("kind") or default_kind
        els = o.Shape.Edges if kind == "edge" else o.Shape.Faces
        return o, kind, [(i, els[i - 1], "") for i in flag("query_hits", [1])]

    measure.query = query

    return types.SimpleNamespace(trace=trace, state=state, Session=Session, Obj=Obj, Shape=Shape, Vec=Vec, part=part, fc=fc, doc=doc, body=body, solid=solid,
                                 wire=wire, face=face, log=log, show=show, flag=flag, mods=mods, Module=Module, View=View, ns=types.SimpleNamespace, curves=curves)

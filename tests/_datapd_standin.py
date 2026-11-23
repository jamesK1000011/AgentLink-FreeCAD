# SPDX-License-Identifier: LGPL-2.1-or-later
# A stand-in FreeCAD for tests/test_datapd_data.py: FreeCAD, Part, Sketcher
# and PartDesign as far as the Part Design and Sketcher tools reach, in plain
# Python. It is not FreeCAD: a body's volume is a sum of what each feature
# is said to add or take, a sketch "solves" by counting, a face is found by
# the number its query carries. It is one fixed world on which the old
# handlers and the new data entries are run side by side, every object made
# or removed, property set and geometry call written to TRACE, so the two can
# be compared step for step. Only ever installed in a child process
# (install() puts it in sys.modules).
import math
import sys
import types

LINKS = ("Profile", "Base", "BaseFeature", "Originals", "ReferenceAxis", "UpToFace", "NeutralPlane", "PullDirection", "MirrorPlane", "Direction", "Axis",
         "Sections", "Spine", "AttachmentSupport", "Support", "Transformations")
ADDSUB = ("Pad", "Pocket", "Revolution", "Groove", "Hole", "AdditiveLoft", "SubtractiveLoft", "AdditivePipe", "SubtractivePipe")
DRESS = ("Fillet", "Chamfer", "Draft", "Thickness")
PATTERN = ("Mirrored", "LinearPattern", "PolarPattern", "MultiTransform")
COARSE = ["M1x0.25", "M1.2x0.25", "M1.6x0.35", "M2x0.4", "M2.5x0.45", "M3x0.5", "M4x0.7", "M5x0.8", "M6x1.0", "M8x1.25", "M10x1.5", "M12x1.75", "M16x2.0", "M20x2.5",
          "M24x3.0", "M30x3.5", "M36x4.0"]
FINE = ["M1x0.2", "M1.2x0.2", "M1.6x0.2", "M2x0.25", "M2.5x0.35", "M3x0.35", "M4x0.5", "M5x0.5", "M6x0.75", "M8x0.75", "M8x1.0", "M10x0.75", "M10x1.0", "M10x1.25",
        "M12x1.0", "M12x1.25", "M12x1.5"]


def install():
    trace = []
    state = {"doc": None, "flags": {}}

    def flag(k, default=None):
        return state["flags"].get(k, default)

    def show(v):
        if isinstance(v, Obj):
            return f"<{v.Name}>"
        if isinstance(v, (list, tuple)):
            return ("[" if isinstance(v, list) else "(") + ", ".join(show(x) for x in v) + ("]" if isinstance(v, list) else ")")
        if isinstance(v, dict):
            return "{" + ", ".join(f"{k}: {show(x)}" for k, x in v.items()) + "}"
        if isinstance(v, bool):
            return repr(v)
        if isinstance(v, float):
            return f"{v:.6g}"
        return repr(v)

    def log(name, *a, **kw):
        trace.append(f"{name}({', '.join([show(x) for x in a] + [f'{k}={show(v)}' for k, v in kw.items()])})")

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

        def __iter__(self):
            return iter((self.x, self.y, self.z))

        def __getitem__(self, i):
            return (self.x, self.y, self.z)[i]

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
            self.Axis = a[0] if a and isinstance(a[0], Vec) else Vec(0, 0, 1)
            self.Angle = math.radians(a[1]) if len(a) == 2 and isinstance(a[1], (int, float)) else 0.0

        def multVec(self, v):
            return Vec(v)

        def multiply(self, o):
            return Rotation(self, o)

        def inverted(self):
            return Rotation(self, "inverted")

        def __repr__(self):
            return f"Rotation({', '.join(show(x) for x in self.a)})"

    class Placement:
        def __init__(self, base=None, rot=None, *centre):
            if isinstance(base, Placement):
                base, rot = Vec(base.Base), base.Rotation
            self.Base, self.Rotation = Vec() if base is None else base, Rotation() if rot is None else rot

        def multVec(self, v):
            return Vec(v) + self.Base

        def multiply(self, o):
            return Placement(self.Base + o.Base, self.Rotation.multiply(o.Rotation))

        def inverse(self):
            return Placement(self.Base * -1, self.Rotation.inverted())

        def __repr__(self):
            return f"Placement({show(self.Base)}, {show(self.Rotation)})"

    # ---- shapes ---------------------------------------------------------------------------------

    class Box:
        def __init__(self, pts):
            xs, ys, zs = ([getattr(p, k) for p in pts] or [0.0] for k in "xyz")
            self.XMin, self.XMax, self.YMin, self.YMax, self.ZMin, self.ZMax = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
            self.XLength, self.YLength, self.ZLength = self.XMax - self.XMin, self.YMax - self.YMin, self.ZMax - self.ZMin
            self.DiagonalLength = math.sqrt(self.XLength ** 2 + self.YLength ** 2 + self.ZLength ** 2)
            self.Center = Vec((self.XMin + self.XMax) / 2, (self.YMin + self.YMax) / 2, (self.ZMin + self.ZMax) / 2)

        def isValid(self):
            return True

        def united(self, o):
            return Box([Vec(min(self.XMin, o.XMin), min(self.YMin, o.YMin), min(self.ZMin, o.ZMin)), Vec(max(self.XMax, o.XMax), max(self.YMax, o.YMax), max(self.ZMax, o.ZMax))])

    class Vertex:
        def __init__(self, p, *rest):
            self.Point = Vec(p, *rest) if not isinstance(p, Vec) else p
            self.X, self.Y, self.Z = self.Point.x, self.Point.y, self.Point.z

        def isSame(self, o):
            return (self.Point - o.Point).Length < 1e-9

    class Line:
        """An edge's straight curve (Part.Line)."""

    class Curve:
        def __init__(self, kind, **kw):
            self.kind = kind
            self.__dict__.update(kw)

    class Shape:
        """One class for every kind: an edge, a wire, a face, a solid, a compound."""

        def __init__(self, kind="compound", pts=(), edges=(), wires=(), faces=(), solids=(), volume=0.0, area=0.0, null=False, closed=False, curve="Line", **kw):
            self.kind, self.pts, self.Edges, self.Wires, self.Faces, self.Solids = kind, list(pts), list(edges), list(wires), list(faces), list(solids)
            self.Volume, self.Area, self.null, self.closed = volume, area, null, closed
            self.ShapeType = {"edge": "Edge", "wire": "Wire", "face": "Face", "solid": "Solid", "shell": "Shell"}.get(kind, "Compound")
            self.Curve = (Line() if curve == "Line" else type(curve, (), {})()) if isinstance(curve, str) else curve
            self.__dict__.update(kw)

        @property
        def Vertexes(self):
            return [Vertex(p) for p in self.pts]

        @property
        def Length(self):
            if self.kind == "edge":
                return self.__dict__.get("length", (self.pts[-1] - self.pts[0]).Length if len(self.pts) > 1 else 0.0)
            return sum(e.Length for e in self.Edges)

        @property
        def BoundBox(self):
            return Box(self.pts or [p for e in self.Edges for p in e.pts])

        @property
        def CenterOfMass(self):
            n = max(len(self.pts), 1)
            return Vec(sum(p.x for p in self.pts) / n, sum(p.y for p in self.pts) / n, sum(p.z for p in self.pts) / n)

        def isNull(self):
            return self.null

        def isValid(self):
            return True

        def isClosed(self):
            return self.closed

        def getElement(self, sub):
            head = sub.rstrip("0123456789")
            i = int(sub[len(head):])
            pool = {"Face": self.Faces, "Edge": self.Edges, "Vertex": self.Vertexes}[head]
            if not 1 <= i <= len(pool):
                raise ValueError(f"no {sub}")
            return pool[i - 1]

        def revolve(self, at, axis, angle):
            log("revolve", self, at, axis, angle)
            # Pappus: the area times the path of its middle (points are [x, radius, 0]).
            twice = sum(p.x * q.y - q.x * p.y for p, q in zip(self.pts, self.pts[1:]))
            cy = sum((p.y + q.y) * (p.x * q.y - q.x * p.y) for p, q in zip(self.pts, self.pts[1:])) / (3 * twice) if twice else 0.0
            out = Shape("shell" if flag("revolve_shell") else "solid", self.pts, volume=abs(twice) / 2 * 2 * math.pi * abs(cy) * angle / 360, faces=[self])
            out.Solids = [out]
            return out

        def rotate(self, at, axis, angle):
            log("rotate", self, at, axis, angle)

        def removeSplitter(self):
            log("removeSplitter", self)
            return self

        def copy(self):
            return self

        def distToShape(self, o):
            return (float(self.__dict__.get("far", 0.0)),)

        FirstParameter, LastParameter = 0.0, 1.0

        def valueAt(self, t):
            d = self.pts[-1] - self.pts[0]
            bow = Vec(-d.y, d.x, 0) * (0.5 * math.sin(math.pi * t)) if type(self.Curve).__name__ == "Circle" else Vec()  # an arc is no chord
            return self.pts[0] + d * t + bow

        def toNurbs(self):
            return Shape("edge", self.pts, edges=[Shape("edge", self.pts, curve=BSplineCurve(self.pts))])

        def translated(self, v):
            return Shape("edge", [p + v for p in self.pts], curve=self.Curve)

        def makeOffset2D(self, d, join, fill, open_, inter):
            log("makeOffset2D", self, d, join, fill, open_, inter)
            if flag("no_offset"):
                raise RuntimeError("makeOffset2D: result of offsetting is null!")
            grow = -d if flag("offset_inward") else d
            out = Shape("wire", self.pts, edges=self.Edges, closed=self.closed, area=max(self.Area + 10.0 * grow, 0.0))
            out.Wires = [out]
            return out

        def __repr__(self):
            return f"{self.kind}({len(self.pts)} points, {self.Volume or self.Area or 0:.6g})"


    # ---- sketch geometry (Part's curves) and constraints ------------------------------------------

    class Curve2:
        Construction = False

        def toShape(self):
            pts = self.ends()
            e = Shape("edge", pts, curve=self.curve(), closed=self.closed, area=self.area())
            e.Edges = [e]
            return e

        closed = False

        def curve(self):
            return self

        def area(self):
            return 0.0

        def __repr__(self):
            return f"{type(self).__name__}({', '.join(show(x) for x in self.args())})"

    class LineSegment(Curve2):
        def __init__(self, a, b):
            self.StartPoint, self.EndPoint = Vec(a), Vec(b)

        def ends(self):
            return [self.StartPoint, self.EndPoint]

        def curve(self):
            return Line()

        def args(self):
            return [self.StartPoint, self.EndPoint]

    class Circle(Curve2):
        closed = True

        def __init__(self, c=None, n=None, r=1.0):
            if isinstance(r, Vec):  # three points on it
                (x1, y1), (x2, y2), (x3, y3) = ((p.x, p.y) for p in (c, n, r))
                d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
                if abs(d) < 1e-12:
                    raise RuntimeError("Part.OCCError: three points on one line")
                ux = ((x1 ** 2 + y1 ** 2) * (y2 - y3) + (x2 ** 2 + y2 ** 2) * (y3 - y1) + (x3 ** 2 + y3 ** 2) * (y1 - y2)) / d
                uy = ((x1 ** 2 + y1 ** 2) * (x3 - x2) + (x2 ** 2 + y2 ** 2) * (x1 - x3) + (x3 ** 2 + y3 ** 2) * (x2 - x1)) / d
                c, r = Vec(ux, uy, 0), math.hypot(x1 - ux, y1 - uy)
            self.Center = self.Location = Vec(c) if c is not None else Vec()
            self.Radius = float(r)

        def ends(self):
            return [self.Center + Vec(self.Radius, 0, 0), self.Center - Vec(self.Radius, 0, 0)]

        def area(self):
            return math.pi * self.Radius ** 2

        def args(self):
            return [self.Center, self.Radius]

    class ArcOfCircle(Curve2):
        def __init__(self, c, a0, a1):
            if isinstance(c, Vec):  # three points: start, one on it, end
                c, pts = Circle(c, a0, a1), (c, a1)
                a0, a1 = (math.atan2(p.y - c.Center.y, p.x - c.Center.x) for p in pts)
            self.Center, self.Radius, self.a0, self.a1 = c.Center, c.Radius, a0, a1
            self.StartPoint = self.Center + Vec(math.cos(a0), math.sin(a0), 0) * self.Radius
            self.EndPoint = self.Center + Vec(math.cos(a1), math.sin(a1), 0) * self.Radius

        def ends(self):
            return [self.StartPoint, self.EndPoint]

        def curve(self):
            return Circle(self.Center, None, self.Radius)

        def args(self):
            return [self.Center, self.Radius, self.a0, self.a1]

    class Point(Curve2):
        def __init__(self, p):
            self.X, self.Y, self.Z = p.x, p.y, p.z

        def ends(self):
            return [Vec(self.X, self.Y, self.Z)]

        def args(self):
            return [self.X, self.Y]

    class BSplineCurve(Curve2):
        def __init__(self, pts=()):
            self.how, self.pts = "through", list(pts)

        def interpolate(self, pts, PeriodicFlag=False):
            self.how, self.pts, self.closed = "through", list(pts), bool(PeriodicFlag)

        def buildFromPoles(self, pts, closed, deg):
            self.how, self.pts, self.closed = f"poles, degree {deg}", list(pts), bool(closed)

        def ends(self):
            return [self.pts[0], self.pts[0 if self.closed else -1]]

        def args(self):
            return [self.how, self.pts, self.closed]

    class Conic(Curve2):
        def __init__(self, *a):
            self.a = a
            self.Focal, self.Center = 0.0, Vec()

        def rotate(self, pl):
            self.a += ("rotated", pl)

        def ends(self):
            return [Vec(0, 0, 0), Vec(1, 0, 0)]

        def args(self):
            return list(self.a) + ([self.Focal, self.Center] if type(self).__name__ == "Parabola" else [])

    class Ellipse(Conic):
        closed = True

    Parabola, ArcOfParabola, Hyperbola, ArcOfHyperbola = (type(n, (Conic,), {}) for n in ("Parabola", "ArcOfParabola", "Hyperbola", "ArcOfHyperbola"))

    DIMS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")

    class Constraint:
        def __init__(self, kind, *a):
            self.Type, self.Name, self.Driving, self.Active, self.args = kind, "", True, True, a
            self.Value = 0.0
            ids = list(a)
            if kind in DIMS:
                self.Value = float(ids.pop())
            if kind in ("Group", "Text"):
                ids = list(ids[0])
            if not all(isinstance(x, int) and not isinstance(x, bool) for x in ids):
                raise TypeError(f"Sketcher.Constraint({kind}): integers expected")
            self.ids = ids
            f = [-2000, 0, -2000, 0, -2000, 0]
            if len(ids) == 2 and kind in ("Equal", "Parallel", "Perpendicular", "Tangent", "Angle"):
                f[0], f[2] = ids
            elif len(ids) == 3:
                f[0], f[1], f[2] = ids
            else:
                f[:len(ids)] = ids[:6]
            self.First, self.FirstPos, self.Second, self.SecondPos, self.Third, self.ThirdPos = f

        def geos(self):
            return [g for g in (self.First, self.Second, self.Third) if g != -2000] if self.Type not in ("Group", "Text") else self.ids[::2]

        def key(self):
            return (self.Type, self.First, self.FirstPos, self.Second, self.SecondPos, self.Third, self.ThirdPos)

        def __repr__(self):
            return f"Constraint({self.Type!r}, {', '.join(show(x) for x in self.args)})"

    class Quantity:
        def __init__(self, text):
            self.text = text
            self.Value = float(str(text).split()[0])

        def __repr__(self):
            return f"Quantity({self.text!r})"

    FREE = {"LineSegment": 4, "Circle": 3, "ArcOfCircle": 5, "Point": 2}

    def chain(geos):
        """Runs of curves that meet end to start, each a wire (closed when it comes back to its start)."""
        wires = []
        for g in geos:
            e = g.toShape()
            if isinstance(g, Point):
                continue
            if g.closed:
                wires.append(Shape("wire", [], edges=[e], closed=True, area=e.Area))
                continue
            w = wires[-1] if wires and not wires[-1].closed and (wires[-1].run[-1] - e.pts[0]).Length < 1e-6 else None
            if w is None:
                w = Shape("wire", [e.pts[0]], closed=False, run=[e.pts[0]], area=0.0)
                wires.append(w)
            w.Edges.append(e)
            w.run.append(e.pts[1])
            if (e.pts[1] - w.run[0]).Length < 1e-6:
                w.closed = True
                w.Area = abs(sum(p.x * q.y - q.x * p.y for p, q in zip(w.run, w.run[1:]))) / 2
            else:
                w.pts.append(e.pts[1])
        for w in wires:
            w.Wires = [w]
        return wires

    def sketch_shape(o):
        wires = chain([g for g in o.__dict__["Geometry"] if not g.Construction])
        return Shape("compound", [], wires=wires, edges=[e for w in wires for e in w.Edges], null=not wires)

    def edge(p, q, curve="Line", **kw):
        e = Shape("edge", [p, q], curve=curve, **kw)
        e.Edges = [e]
        return e

    def polygon(points):
        log("makePolygon", points)
        pts = [Vec(p) for p in points]
        w = Shape("wire", pts, edges=[edge(pts[i], pts[i + 1]) for i in range(len(pts) - 1)], closed=len(pts) > 2 and pts[0] == pts[-1])
        w.Wires = [w]
        return w

    def face(w):
        log("Face", w)
        if not isinstance(w, Shape) or not w.closed:
            raise RuntimeError("Failed to create face from wire")
        twice = sum(p.x * q.y - q.x * p.y for p, q in zip(w.pts, w.pts[1:]))
        f = Shape("face", w.pts, edges=w.Edges, wires=[w], area=w.Area or abs(twice) / 2, closed=True)
        f.Faces = [f]
        return f

    def solid_of(volume, faces=6, edges=12):
        """A body's or a feature's shape: its volume and so many faces and edges."""
        s = Shape("solid", [Vec(0, 0, 0), Vec(10, 10, 10)], volume=float(volume), area=6.0 * faces, null=False)
        s.Faces = [Shape("face", [Vec(i, 0, 0), Vec(i + 1, 1, 0)], area=6.0, closed=True) for i in range(faces)]
        s.Edges = [edge(Vec(i, 0, 0), Vec(i + 1, 0, 0), "Circle" if i % 4 == 3 else "Line") for i in range(edges)]
        s.Solids = [s] * (flag("solids", 1) if volume > 1e-9 else 0)
        return s

    NULL = Shape(null=True)

    # ---- objects --------------------------------------------------------------------------------

    def defaults(kind):
        """A new object's properties, as FreeCAD 1.1 gives them (flags["old"]: as 0.21 did)."""
        old = flag("old")
        short = kind.split("::")[-1]
        p = {}
        if short in ("Pad", "Pocket"):
            p = {"Profile": None, "Type": "Length", "Length": 10.0, "Length2": 5.0, "Type2": "Length", "SideType": "One side", "Midplane": False, "Reversed": False,
                 "TaperAngle": 0.0, "UpToFace": None, "Offset": 0.0}
            if old:
                for k in ("SideType", "Type2"):
                    del p[k]
                if flag("no_taper"):
                    del p["TaperAngle"]
        elif short in ("Revolution", "Groove"):
            p = {"Profile": None, "ReferenceAxis": None, "Type": "Angle", "Angle": 360.0, "Angle2": 0.0, "Midplane": False, "Reversed": False}
        elif short == "Hole":
            p = {"Profile": None, "Diameter": 6.0, "Depth": 25.0, "DepthType": "Dimension", "Threaded": False, "ModelThread": False, "ThreadType": "None", "ThreadSize": "",
                 "ThreadFit": "Standard", "HoleCutType": "None", "HoleCutDiameter": 0.0, "HoleCutDepth": 0.0, "HoleCutCountersinkAngle": 90.0, "HoleCutCustomValues": False,
                 "DrillPoint": "Flat", "Reversed": False, "BaseProfileType": 7}
            if old:
                for k in ("ModelThread", "ThreadFit", "HoleCutCustomValues", "BaseProfileType"):
                    del p[k]
        elif short == "Fillet":
            p = {"Base": None, "Radius": 1.0}
        elif short == "Chamfer":
            p = {"Base": None, "Size": 1.0, "Size2": 1.0, "Angle": 45.0, "ChamferType": "Equal distance"}
        elif short == "Draft":
            p = {"Base": None, "Angle": 1.5, "NeutralPlane": None, "PullDirection": None, "Reversed": False}
        elif short == "Thickness":
            p = {"Base": None, "Value": 1.0, "Reversed": False, "Join": "Arc", "Mode": "Skin"}
        elif short in ("Mirrored", "LinearPattern", "PolarPattern"):
            p = {"Originals": [], "TransformMode": "Features"}
            if old or flag("no_transform_mode"):
                del p["TransformMode"]
            if short == "Mirrored":
                p["MirrorPlane"] = None
            elif short == "LinearPattern":
                p.update(Direction=None, Length=100.0, Occurrences=2, Reversed=False, Mode="Extent", Offset=20.0)
            else:
                p.update(Axis=None, Angle=360.0, Occurrences=2, Reversed=False, Mode="Extent", Offset=20.0)
        elif short.endswith("Loft"):
            p = {"Profile": None, "Sections": [], "Ruled": False, "Closed": False}
        elif short.endswith("Pipe"):
            p = {"Profile": None, "Spine": None, "Mode": "Standard", "Transition": "Transformed"}
        elif short == "Plane":
            p = {("Support" if old else "AttachmentSupport"): None, "MapMode": "Deactivated", "AttachmentOffset": Placement()}
        elif short == "Body":
            p = {"Group": [], "Tip": None, "BaseFeature": None}
        elif kind == "Sketcher::SketchObject":
            p = {("Support" if old else "AttachmentSupport"): None, "MapMode": "Deactivated", "MapReversed": False, "AttachmentOffset": Placement(), "Geometry": [],
                 "Constraints": [], "ExpressionEngine": [], "DoF": 0, "ConflictingConstraints": [], "RedundantConstraints": []}
            if old:
                p["ExternalGeometry"] = []
            else:
                p["ExternalGeo"] = ["x axis", "y axis"]
        if kind.startswith("PartDesign::") and short in ADDSUB + DRESS + PATTERN:
            p["Refine"] = False
            if not old:
                p["Suppressed"] = False
        return p

    def enums(o, prop):
        short = o.TypeId.split("::")[-1]
        if prop == "Type" and short == "Pad":
            return ["Length", "UpToLast", "UpToFirst", "UpToFace", "TwoLengths", "UpToShape"] if flag("old") else ["Length", "UpToLast", "UpToFirst", "UpToFace", "?TwoLengths", "UpToShape"]
        if prop == "Type" and short == "Pocket":
            return ["Length", "ThroughAll", "UpToFirst", "UpToFace", "TwoLengths"] if flag("old") else ["Length", "ThroughAll", "UpToFirst", "UpToFace", "?TwoLengths", "UpToShape"]
        if prop == "Type" and short in ("Revolution", "Groove"):
            return ["Angle", "UpToLast", "UpToFirst", "UpToFace", "TwoAngles"]
        if prop == "SideType":
            return ["One side", "Two sides", "Symmetric"]
        if prop == "ThreadType":
            return ["None", "ISOMetricProfile", "ISOMetricFineProfile", "UNC", "UNF"]
        if prop == "ThreadSize":
            return {"ISOMetricProfile": COARSE, "ISOMetricFineProfile": FINE}.get(o.__dict__.get("ThreadType"), [])
        if prop == "ThreadFit":
            return flag("fits", ["Standard", "Close", "Wide"])
        if prop == "HoleCutType":
            return ["None", "Counterbore", "Countersink", "Counterdrill"] + (["ISO 4762", "ISO 10642"] if o.__dict__.get("ThreadSize") else [])
        if prop == "DepthType":
            return ["Dimension", "ThroughAll"]
        if prop == "DrillPoint":
            return ["Flat", "Angled"]
        if prop == "ChamferType":
            return ["Equal distance", "Two distances", "Distance and Angle"]
        if prop == "Join":
            return ["Arc", "Intersection"]
        if prop == "TransformMode":
            return flag("transform_modes", ["Features", "Whole shape"])
        if prop == "MapMode":
            return ["Deactivated", "FlatFace", "ObjectXY", "NormalToEdge"]
        return None

    def effect(o):
        """What a feature adds to (or takes from) its body's volume, mm³."""
        over = flag("effect", {})
        for k in (o.Label, o.Name):
            if k in over:
                return over[k]
        d = o.__dict__
        short = o.TypeId.split("::")[-1]
        if d.get("Suppressed"):
            return 0.0
        if short == "Pad":
            return 100.0 * d["Length"] if d["Type"] in ("Length", "TwoLengths") else 500.0
        if short == "Hole":
            return -10.0 * max(len(getattr(d.get("Profile"), "Geometry", [])), 1)
        if short == "Thickness":
            return -400.0 if d["Reversed"] else 100.0
        if short in ("LinearPattern", "PolarPattern"):
            return 50.0 * (d["Occurrences"] - 1)
        return {"Pocket": -200.0, "Revolution": 300.0, "Groove": -100.0, "Fillet": -5.0, "Chamfer": -5.0, "Draft": -3.0, "Mirrored": 100.0, "AdditiveLoft": 250.0,
                "SubtractiveLoft": -150.0, "AdditivePipe": 120.0, "SubtractivePipe": -80.0, "Feature": 1000.0, "FeatureBase": 1000.0}.get(short, 0.0)

    def refs(v, o):
        if v is o:
            return True
        if isinstance(v, (list, tuple)):
            return any(refs(x, o) for x in v)
        return False

    class Obj:
        def __init__(self, name, type_, **kw):
            self.__dict__.update({"Name": name, "TypeId": type_, "Label": name, **defaults(type_), **kw})

        def __setattr__(self, k, v):
            trace.append(f"{self.Name}.{k} = {show(v)}")
            if k == "Base" and "---- the call" in trace and (self.Name in flag("heals", ()) or self.Label in flag("heals", ())):
                state["flags"].setdefault("_healed", set()).update((self.Name, self.Label))
            if k in flag("refuses", {}).get(self.Name, ()):
                raise ValueError(f"Property '{k}' is read-only" if not isinstance(v, str) else f"'{v}' is not part of the enumeration in {self.Name}.{k}")
            allowed = enums(self, k)
            if allowed is not None and isinstance(v, str) and v not in allowed and k in self.__dict__:
                raise ValueError(f"'{v}' is not part of the enumeration in {self.Name}.{k}")
            if k in self.__dict__ and isinstance(self.__dict__[k], float) and isinstance(v, str):
                raise TypeError("Argument must be float or int")
            self.__dict__[k] = v

        def __getattr__(self, k):
            d = self.__dict__
            if k == "PropertiesList":
                return [p for p in d if p[:1].isupper() and p not in ("Name", "TypeId") and p not in flag("hidden", ())] + ["Shape"] * ("Shape" not in d)
            if k == "InList":
                return [o for o in state["doc"].Objects if o is not self and any(refs(o.__dict__.get(p), self) for p in o.PropertiesList if p != "Shape")]
            if k == "OutListRecursive":
                out = []
                for o in self.OutList:
                    out += [o] + [x for x in o.OutListRecursive if x not in out]
                return out
            if k == "OutList":
                return [o for o in state["doc"].Objects if o is not self and any(refs(d.get(p), o) for p in d if p[:1].isupper())]
            if k == "InListRecursive":
                out = []
                for o in self.InList:
                    out += [o] + [x for x in o.InListRecursive if x not in out]
                return out
            if k == "Shape":
                return sketch_shape(self) if self.TypeId == "Sketcher::SketchObject" else NULL
            if k == "State":
                return [] if self.isValid() else ["Invalid"]
            if k == "Placement":
                return d.setdefault("Placement", Placement())
            if k == "Document":
                return state["doc"]
            if k == "ExpressionEngine":
                return []
            raise AttributeError(k)

        def isDerivedFrom(self, t):
            short = self.TypeId.split("::")[-1]
            pd = self.TypeId.startswith("PartDesign::")
            if t == self.TypeId or t in self.__dict__.get("kinds", ()):
                return True
            if t == "PartDesign::Feature":
                return pd and short in ADDSUB + DRESS + PATTERN + ("FeatureBase", "Boolean")
            if t == "PartDesign::FeatureAddSub":
                return pd and short in ADDSUB
            if t == "PartDesign::DressUp":
                return pd and short in DRESS
            if t == "Part::Feature":
                return pd or self.TypeId.startswith(("Part::", "Sketcher::"))
            if t == "Part::Part2DObject":
                return self.TypeId.startswith("Sketcher::")
            return False

        def _bad(self):
            """What is wrong with it: flags["invalid"] from the start, flags["invalid_after"] once the
            call has recomputed (until its Base is set again, for one of flags["heals"])."""
            bad = dict(flag("invalid", {}))
            if "---- the call" in trace and "recompute()" in trace[trace.index("---- the call"):]:
                bad.update({k: v for k, v in flag("invalid_after", {}).items() if k not in state["flags"].get("_healed", ())})
            return bad.get(self.Name, bad.get(self.Label))

        def isValid(self):
            return self._bad() is None

        def getStatusString(self):
            return self._bad() or "Valid"

        def getEnumerationsOfProperty(self, p):
            if flag("no_enums"):
                raise RuntimeError("no enumerations here")
            return enums(self, p)

        def getTypeIdOfProperty(self, p):
            if p not in self.__dict__:
                raise AttributeError(p)
            return "App::PropertyLinkSub" if p in LINKS else "App::PropertyBool" if isinstance(self.__dict__[p], bool) else "App::PropertyFloat"

        def getParentGeoFeatureGroup(self):
            return next((b for b in state["doc"].Objects if b.TypeId == "PartDesign::Body" and self in b.__dict__["Group"]), None)

        # ---- a body ----
        def hasObject(self, o):
            return o in self.__dict__.get("Group", ()) or o in self.__dict__.get("OriginFeatures", ())

        def newObject(self, kind, name):
            o = state["doc"].new(kind, name)
            trace.append(f"{self.Name}.newObject({kind!r}, {o.Name!r})")
            self._place(o)
            if o.isDerivedFrom("PartDesign::Feature") and not (flag("pattern_keeps_tip") and kind.split("::")[-1] in PATTERN):
                self.__dict__["Tip"] = o
            return o

        def _place(self, o, at=None):
            g = list(self.__dict__["Group"])
            tip = self.__dict__.get("Tip")
            i = at if at is not None else g.index(tip) + 1 if tip in g else len(g)
            g.insert(i, o)
            self.__dict__["Group"] = g

        def addObject(self, o):
            trace.append(f"{self.Name}.addObject({show(o)})")
            self._place(o)
            if o.isDerivedFrom("PartDesign::Feature"):
                self.__dict__["Tip"] = o

        def insertObject(self, o, target, after=False):
            trace.append(f"{self.Name}.insertObject({show(o)}, {show(target)}, {after!r})")
            g = self.__dict__["Group"]
            self._place(o, g.index(target) + (1 if after else 0))

        def removeObject(self, o):
            trace.append(f"{self.Name}.removeObject({show(o)})")
            g = list(self.__dict__["Group"])
            if self.__dict__.get("Tip") is o:
                before = [x for x in g[:g.index(o)] if x.isDerivedFrom("PartDesign::Feature")]
                self.__dict__["Tip"] = before[-1] if before else None
            self.__dict__["Group"] = [x for x in g if x is not o]

        # ---- a sketch ----
        def getConstruction(self, i):
            return bool(getattr(self.__dict__["Geometry"][i], "Construction", False))

        def addGeometry(self, g, construction=False):
            trace.append(f"{self.Name}.addGeometry({show(g)}, {construction!r})")
            g.Construction = bool(construction)
            self.__dict__["Geometry"] = self.__dict__["Geometry"] + [g]
            return len(self.__dict__["Geometry"]) - 1

        def addConstraint(self, c):
            trace.append(f"{self.Name}.addConstraint({show(c)})")
            n, ext = len(self.__dict__["Geometry"]), len(self.__dict__.get("ExternalGeo", ())) + len(self.__dict__.get("ExternalGeometry", ()))
            if c.Type in ("Group", "Text") and not flag("fc12"):
                raise ValueError(f"Unknown constraint type: {c.Type}")
            if any(g >= n or g < -ext - 2 for g in c.geos()) or (c.Type == "Radius" and type(self.__dict__["Geometry"][c.First]).__name__ == "LineSegment"):
                raise ValueError("Invalid constraint")
            self.__dict__["Constraints"] = self.__dict__["Constraints"] + [c]
            return len(self.__dict__["Constraints"]) - 1

        def renameConstraint(self, i, name):
            trace.append(f"{self.Name}.renameConstraint({i}, {name!r})")
            self.__dict__["Constraints"][i].Name = name

        def delConstraint(self, i):
            trace.append(f"{self.Name}.delConstraint({i})")
            cs = list(self.__dict__["Constraints"])
            del cs[i]
            self.__dict__["Constraints"] = cs

        def delGeometries(self, ids):
            trace.append(f"{self.Name}.delGeometries({ids!r})")
            keep = [i for i in range(len(self.__dict__["Geometry"])) if i not in ids]
            new = {old: k for k, old in enumerate(keep)}
            self.__dict__["Geometry"] = [self.__dict__["Geometry"][i] for i in keep]
            self.__dict__["Constraints"] = [c for c in self.__dict__["Constraints"] if not any(g in ids for g in c.geos())]
            for c in self.__dict__["Constraints"]:
                c.First, c.Second, c.Third = (new.get(g, g) for g in (c.First, c.Second, c.Third))

        def solve(self):
            """The solver: the same thing dimensioned twice is redundant (the same value) or conflicting."""
            d = self.__dict__
            seen, conflicting, redundant = {}, [], []
            for i, c in enumerate(d["Constraints"]):
                if not c.Active:
                    continue
                if c.key() in seen:
                    (redundant if abs(seen[c.key()] - c.Value) < 1e-9 else conflicting).append(i + 1)
                else:
                    seen[c.key()] = c.Value
            d["ConflictingConstraints"], d["RedundantConstraints"] = conflicting, redundant
            d["MalformedConstraints"] = [i + 1 for i in flag("malformed", ())]
            d["PartiallyRedundantConstraints"] = [i + 1 for i in flag("partly", ())]
            d["DoF"] = max(sum(FREE.get(type(g).__name__, 6) for g in d["Geometry"]) - len(seen), 0)
            return flag("solve", -3 if conflicting else -2 if redundant else 0)

        def getActive(self, i):
            return self.__dict__["Constraints"][i].Active

        def setActive(self, i, on):
            if flag("no_toggle"):
                raise RuntimeError("cannot toggle")
            self.__dict__["Constraints"][i].Active = on

        def setConstruction(self, i, on):
            trace.append(f"{self.Name}.setConstruction({i}, {on!r})")
            self.__dict__["Geometry"][i].Construction = on

        def getPoint(self, g, p):
            geo_ = self.__dict__["Geometry"][g]
            return {1: getattr(geo_, "StartPoint", None), 2: getattr(geo_, "EndPoint", None), 3: getattr(geo_, "Center", None)}[p]

        def _op(self, name, *a, adds=()):
            trace.append(f"{self.Name}.{name}({', '.join(show(x) for x in a)})")
            if name in flag("raises", {}):
                kind, msg = flag("raises")[name]
                raise {"ValueError": ValueError, "TypeError": TypeError, "RuntimeError": RuntimeError}[kind](msg)
            if name not in flag("nothing", ()):
                self.__dict__["Geometry"] = self.__dict__["Geometry"] + list(adds)

        def moveGeometry(self, g, p, to, relative=False):
            self._op("moveGeometry", g, p, to, relative)

        def setDatum(self, i, q):
            self._op("setDatum", i, q)
            self.__dict__["Constraints"][i].Value = q.Value

        def fillet(self, *a):
            if flag("old") and len(a) > (5 if isinstance(a[1], int) and not isinstance(a[2], Vec) and len(a) < 7 else 7):
                trace.append(f"{self.Name}.fillet: too many arguments")
                raise TypeError("fillet() takes at most 7 arguments")
            chamfer = a[-1] is True and a[-2] is False
            self._op("fillet", *a, adds=[LineSegment(Vec(0, 0, 0), Vec(1, 1, 0)) if chamfer else ArcOfCircle(Circle(Vec(), None, 2.0), 0.0, 1.0)])

        def trim(self, g, at):
            self._op("trim", g, at, adds=[LineSegment(at, at + Vec(1, 0, 0))] if flag("trim_splits") else [])

        def split(self, g, at):
            self._op("split", g, at, adds=[LineSegment(at, at + Vec(1, 0, 0))])

        def addSymmetric(self, geos, ref, pos=None):
            self._op("addSymmetric", geos, ref, pos, adds=[self.__dict__["Geometry"][g] for g in geos])

        def exposeInternalGeometry(self, g):
            if type(self.__dict__["Geometry"][g]).__name__ not in ("Ellipse", "BSplineCurve", "ArcOfParabola", "ArcOfHyperbola"):
                trace.append(f"{self.Name}.exposeInternalGeometry({g}): none")
                raise ValueError("Object does not support internal geometry")
            self._op("exposeInternalGeometry", g, adds=[LineSegment(Vec(), Vec(1, 0, 0)), LineSegment(Vec(), Vec(0, 1, 0))])

        def removeAxesAlignment(self, geos):
            self._op("removeAxesAlignment", geos)

        def setTextAndFont(self, i, words, font, *more):
            self._op("setTextAndFont", i, words, "<font>", *more)

        def addExternal(self, name, sub):
            trace.append(f"{self.Name}.addExternal({name!r}, {sub!r})")
            key = "ExternalGeometry" if "ExternalGeometry" in self.__dict__ else "ExternalGeo"
            taken = self.__dict__[key]
            if (name, sub) in taken or any(isinstance(x, tuple) and x[0] == name and sub in x[1] for x in taken) or sub in flag("no_external", ()):
                raise ValueError("Not able to add external shape element")
            if key == "ExternalGeometry":  # before 1.1: grouped by object
                self.__dict__[key] = [(name, [x for t in taken for x in t[1]] + [sub])]
            else:
                self.__dict__[key] = taken + [(name, sub)]

    class Doc:
        Label = Name = "Doc"

        def __init__(self):
            self.Objects = []

        def new(self, type_, _name=None, **kw):
            """An object of the stand-in's own making (a case's furniture, or what a maker gives)."""
            base = _name or type_.split("::")[-1]
            n, i = base, 0
            while any(o.Name == n for o in self.Objects):
                i += 1
                n = f"{base}{i:03d}"
            o = Obj(n, type_, **kw)
            self.Objects.append(o)
            return o

        def addObject(self, type_, name=None):
            o = self.new(type_, name)
            trace.append(f"addObject({type_!r}, {o.Name!r})")
            if type_ == "PartDesign::Body":
                o.__dict__["Origin"] = origin(self, o)
            return o

        def getObject(self, name):
            return next((o for o in self.Objects if o.Name == name), None)

        def getObjectsByLabel(self, label):
            return [o for o in self.Objects if o.Label == label]

        def removeObject(self, name):
            trace.append(f"removeObject({name!r})")
            self.Objects = [o for o in self.Objects if o.Name != name]

        def recompute(self, objs=None):
            trace.append("recompute()")
            for o in self.Objects:
                if o.TypeId == "Sketcher::SketchObject" and "AttachmentOffset" in o.__dict__:
                    o.__dict__["Placement"] = Placement(o.__dict__["AttachmentOffset"])
            for b in self.Objects:
                if b.TypeId != "PartDesign::Body":
                    continue
                vol = float(flag("base", {}).get(b.Label, 0.0))
                n = 0
                tip = b.__dict__.get("Tip")
                done = tip is None
                shape = NULL
                for o in b.__dict__["Group"]:
                    if not o.isDerivedFrom("PartDesign::Feature"):
                        continue
                    n += 1
                    vol = max(vol + effect(o), 0.0)
                    o.__dict__["Shape"] = solid_of(vol, 6 + 2 * n, 12 + 3 * n) if vol > 1e-9 and o.isValid() else NULL
                    if not done:
                        shape = o.__dict__["Shape"]
                    if o is tip:
                        done = True
                b.__dict__["Shape"] = shape
            return 1

    def origin(doc, body):
        feats = [doc.new("App::Plane" if "Plane" in r else "App::Line", r if body.Name == "Body" else f"{body.Name}_{r}", Role=r)
                 for r in ("X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane")]
        return doc.new("App::Origin", "Origin" if body.Name == "Body" else f"{body.Name}_Origin", OriginFeatures=feats)

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

    # ---- a case's furniture ---------------------------------------------------------------------

    class Geo:
        """A sketch's geometry: a class named as Part names it (Circle, LineSegment …)."""

    def geo(kind, construction=False, **kw):
        g = type(kind, (Geo,), {})()
        if kind == "LineSegment":
            g.__dict__.update(StartPoint=Vec(0, 0, 0), EndPoint=Vec(1, 0, 0))
        g.__dict__.update(Construction=construction, **kw)
        return g

    def body(s, label="Body", base=0.0):
        """A PartDesign body with its origin; base: the volume it starts with (as from a first pad)."""
        b = s.doc.new("PartDesign::Body", None if label == "Body" else label.replace(" ", ""))
        b.__dict__["Label"] = label
        b.__dict__["Origin"] = origin(s.doc, b)
        return b

    def sketch(s, b, label="Sketch", geometry=("Circle",), edges=4, dof=0):
        sk = s.doc.new("Sketcher::SketchObject", label.replace(" ", ""))
        gs = [geo(g) if isinstance(g, str) else g for g in geometry]
        w = Shape("wire", [Vec(0, 0, 0), Vec(10, 0, 0)], edges=[edge(Vec(i, 0, 0), Vec(i + 1, 0, 0)) for i in range(edges)], closed=True)
        sk.__dict__.update(Label=label, Geometry=gs, DoF=dof, Shape=w, Constraints=[], AttachmentSupport=None, MapMode="FlatFace")
        if b is not None:
            b._place(sk)
        return sk

    def drawing(s, b, label="Sketch", geometry=(), constraints=()):
        """A sketch as sketch_new and sketch_add leave it: Part's curves ((curve, construction) for
        a construction one) and Sketcher's constraints ((name, tuple) for a named one)."""
        sk = s.doc.new("Sketcher::SketchObject", label.replace(" ", ""))
        sk.__dict__["Label"] = label
        for g in geometry:
            g, cons = g if isinstance(g, tuple) else (g, False)
            g.Construction = cons
            sk.__dict__["Geometry"].append(g)
        for c in constraints:
            name, c = c if isinstance(c[0], str) and isinstance(c[1], tuple) else ("", c)
            c = Constraint(*c)
            c.Name = name
            sk.__dict__["Constraints"].append(c)
        if b is not None:
            b._place(sk)
        sk.solve()
        return sk

    def feature(s, b, kind, label=None, **props):
        """A feature already in the body (and the tip), as an earlier call left it."""
        f = s.doc.new(f"PartDesign::{kind}", kind)
        f.__dict__.update(Label=label or f.Name, **props)
        b._place(f)
        if f.isDerivedFrom("PartDesign::Feature"):
            b.__dict__["Tip"] = f
        return f

    def settle(s):
        """The case's furniture recomputed, off the record."""
        n = len(trace)
        s.doc.recompute()
        del trace[n:]

    # ---- the modules ----------------------------------------------------------------------------

    fc, part, sketcher, partdesign = (types.ModuleType(n) for n in ("FreeCAD", "Part", "Sketcher", "PartDesign"))
    fc.Vector, fc.Rotation, fc.Placement = Vec, Rotation, Placement
    fc.GuiUp = False
    fc.Version = lambda: ["0", "21", "2"] if flag("old") else ["1", "1", "3"]
    fc.Console = types.SimpleNamespace(PrintMessage=lambda *a: None, PrintWarning=lambda *a: None, PrintError=lambda *a: None, PrintLog=lambda *a: None)
    fc.ActiveDocument = None
    fc.getUserAppDataDir = lambda: "/tmp/"
    fc.ParamGet = lambda p: types.SimpleNamespace(GetString=lambda k, d="": d, GetBool=lambda k, d=False: d, GetInt=lambda k, d=0: d, GetFloat=lambda k, d=0.0: d)
    part.Shape, part.Vertex = Shape, Vertex
    part.makePolygon, part.Face = polygon, face

    def solid(shell):
        log("Solid", shell)
        s = Shape("solid", shell.pts, volume=shell.Volume, faces=shell.Faces)
        s.Solids = [s]
        return s

    def shell(faces):
        log("Shell", faces)
        return Shape("shell", [p for f in faces for p in f.pts], faces=faces, volume=flag("shell_volume", 0.0))

    part.Solid, part.Shell = solid, shell
    part.Line, part.LineSegment, part.Circle, part.ArcOfCircle, part.Point, part.BSplineCurve, part.Ellipse = Line, LineSegment, Circle, ArcOfCircle, Point, BSplineCurve, Ellipse
    part.Parabola, part.ArcOfParabola, part.Hyperbola, part.ArcOfHyperbola = Parabola, ArcOfParabola, Hyperbola, ArcOfHyperbola
    sketcher.Constraint = Constraint
    fc.Units = types.SimpleNamespace(Quantity=Quantity)
    fc.getResourceDir = lambda: "/nonexistent/"

    def sort_edges(edges):
        log("sortEdges", edges)
        if flag("no_join"):
            raise RuntimeError("edges do not join")
        return [w.Edges for w in chain_edges(edges)]

    def chain_edges(edges):
        runs = []
        for e in edges:
            if runs and not e.closed and not runs[-1].Edges[-1].closed and (runs[-1].Edges[-1].pts[-1] - e.pts[0]).Length < 1e-6:
                runs[-1].Edges.append(e)
            else:
                runs.append(Shape("wire", [], edges=[e]))
        return runs

    def wire(edges):
        log("Wire", edges)
        one = len(edges) == 1 and edges[0].closed
        closed = one or (len(edges) > 2 and (edges[-1].pts[-1] - edges[0].pts[0]).Length < 1e-6)
        pts = [e.pts[0] for e in edges] + ([edges[0].pts[0]] if closed and not one else [])
        w = Shape("wire", pts, edges=edges, closed=closed,
                  area=edges[0].Area if one else abs(sum(p.x * q.y - q.x * p.y for p, q in zip(pts, pts[1:]))) / 2 if closed else 0.0)
        w.Wires = [w]
        return w

    def wire_string(words, font, hgt):
        log("makeWireString", words, "<font>", hgt)
        return [[Shape("wire", [], edges=[edge(Vec(i, 0, 0), Vec(i, hgt, 0)), edge(Vec(i, hgt, 0), Vec(i + 1, hgt, 0), curve=BSplineCurve())])] for i, _ in enumerate(words)]

    part.sortEdges, part.Wire, part.makeWireString = sort_edges, wire, wire_string

    # ---- the geometry finders -------------------------------------------------------------------
    # pd_common's faces and edges by where they are (and refs.pick behind them)
    # are FreeCAD's geometry: here a query carries the answer it would get
    # ({"n": 3} the third; "Face3"; {"miss": true} none), and the call is
    # written to the trace. Both the handlers and the entries go through
    # these, so what is compared is what was asked for and in what order.

    def patch():
        from agentlink import geometry as G
        from agentlink.families import pd_common as pc
        from agentlink.protocol import ToolError

        real_edges, real_faces = pc.find_edges, pc.find_faces

        def names(queries, kind):
            out = []
            for q in queries if isinstance(queries, list) else [queries]:
                if isinstance(q, str):
                    out.append(q.split(".")[-1])
                elif isinstance(q, dict) and q.get("miss"):
                    raise ToolError("not_found", f"No {kind.lower()} there.")
                elif isinstance(q, dict) and q.get("all"):
                    out += [f"{kind}{i}" for i in (1, 2, 3)]
                else:
                    out.append(f"{kind}{(q or {}).get('n', 1) if isinstance(q, dict) else 1}")
            return out

        def find_edges(shape, queries, names_=()):
            if not queries:
                return real_edges(shape, queries, names_)
            log("find_edges", shape, queries, list(names_))
            return names(queries, "Edge")

        def find_faces(shape, queries, names_=()):
            if not queries:
                return real_faces(shape, queries, names_)
            log("find_faces", shape, queries, list(names_))
            return names(queries, "Face")

        def find_face(shape, q, tol=0.5, body=None, names=()):  # body, names: face selectors (22 Nov)
            if not isinstance(q, dict) or "at" not in q:
                raise ToolError("invalid_input", "face: { at: [x,y,z] on the face, normal: [x,y,z] outward } — a point on it, not its index (indices change after edits).")
            log("find_face", shape, q)
            if q.get("miss"):
                raise ToolError("not_found", "No face there.")
            i = int(q.get("n", 1)) - 1
            return i, shape.Faces[i]

        pc.find_edges, pc.find_faces, pc.find_face = find_edges, find_faces, find_face

        def face_pick(body, q):
            """The form to copy back (22 Nov face selectors): the query as given, on the stand-in."""
            tip, shape = pc.tip_shape(body)
            find_face(shape, q)
            return dict(q)

        pc.face_pick = face_pick
        from agentlink.families import measure as M

        def query(session, q):
            """shape_query's filter on a body: {"hits": 3} answers Edge1 … Edge3 (the later the farther from near)."""
            log("query", q)
            return None, None, [(None, Shape("edge", far=float(k)), {"ref": f"Edge{k + int(q.get('first', 1))}"}) for k in range(int(q.get("hits", 1)))]

        M.query = query
        G.stats = lambda sh: {"volume": round(sh.Volume, 2), "area": round(sh.Area, 2), "faces": len(sh.Faces), "solids": len(sh.Solids), "box": [10.0, 10.0, 10.0]}

    sys.modules.update({"FreeCAD": fc, "Part": part, "Sketcher": sketcher, "PartDesign": partdesign})
    try:  # std_more's other tools use numpy; these do not, so a Python without it can still run the comparison
        import numpy  # noqa: F401
    except ImportError:
        sys.modules["numpy"] = types.ModuleType("numpy")
    return types.SimpleNamespace(trace=trace, state=state, Session=Session, Obj=Obj, Shape=Shape, Vec=Vec, Placement=Placement, Rotation=Rotation, part=part,
                                 sketcher=sketcher, fc=fc, geo=geo, Geo=Geo, body=body, sketch=sketch, drawing=drawing, feature=feature, settle=settle, patch=patch, edge=edge,
                                 solid_of=solid_of, log=log, show=show, flag=flag, NULL=NULL, Constraint=Constraint)

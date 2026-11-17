# SPDX-License-Identifier: LGPL-2.1-or-later
# A stand-in FreeCAD for tests/test_datamesh_data.py: FreeCAD, Part, Mesh,
# MeshPart and Points as far as the mesh and point-cloud tools reach, in
# plain Python and numpy. It is not FreeCAD's geometry: a mesh is a list of
# points and triangles whose methods are written to TRACE and change it by
# simple fixed rules (a case's flags say which of them fail, open the mesh
# or leave nothing). The old handlers and the new data entries are run on it
# side by side and compared step for step. Only ever installed in a child
# process (install() puts it in sys.modules).
import math
import os
import sys
import types


def install():
    trace = []
    state = {"doc": None, "flags": {}, "n": 0}

    def flag(k, default=None):
        return state["flags"].get(k, default)

    def show(v):
        if isinstance(v, (Obj, FakeMesh, Shape, Cloud)):
            return v.tag()
        if isinstance(v, Vec):
            return f"V({v.x:.6g}, {v.y:.6g}, {v.z:.6g})"
        if isinstance(v, (list, tuple)):
            if len(v) > 12:
                return f"[{len(v)} items: {show(list(v[:3]))[1:-1]}, …]"
            return "[" + ", ".join(show(x) for x in v) + "]"
        if isinstance(v, dict):
            return "{" + ", ".join(f"{k}: {show(x)}" for k, x in v.items()) + "}"
        if isinstance(v, float):
            return f"{v:.6g}"
        if hasattr(v, "shape") and hasattr(v, "tolist"):  # a numpy array
            return f"array{tuple(v.shape)}"
        return repr(v)

    def log(name, *a, **kw):
        trace.append(f"{name}({', '.join([show(x) for x in a] + [f'{k}={show(v)}' for k, v in kw.items()])})")

    def serial(kind):
        state["n"] += 1
        return f"{kind}#{state['n']}"

    # ---- vectors, matrices, placements -----------------------------------------------------

    class Vec:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            if isinstance(x, Vec):
                x, y, z = x.x, x.y, x.z
            elif isinstance(x, (list, tuple)):
                x, y, z = x
            self.x, self.y, self.z = float(x), float(y), float(z)

        def __sub__(self, o):
            return Vec(self.x - o.x, self.y - o.y, self.z - o.z)

        def __add__(self, o):
            return Vec(self.x + o.x, self.y + o.y, self.z + o.z)

        def __mul__(self, k):
            if isinstance(k, Vec):
                return self.dot(k)
            return Vec(self.x * k, self.y * k, self.z * k)

        __rmul__ = __mul__

        def __neg__(self):
            return Vec(-self.x, -self.y, -self.z)

        def __iter__(self):
            return iter((self.x, self.y, self.z))

        def __getitem__(self, i):
            return (self.x, self.y, self.z)[i]

        def __len__(self):
            return 3

        def __eq__(self, o):
            return isinstance(o, Vec) and (self.x, self.y, self.z) == (o.x, o.y, o.z)

        def __hash__(self):
            return hash((self.x, self.y, self.z))

        def __repr__(self):
            return f"Vector ({self.x:.6g}, {self.y:.6g}, {self.z:.6g})"

        @property
        def Length(self):
            return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

        def cross(self, o):
            return Vec(self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z, self.x * o.y - self.y * o.x)

        def dot(self, o):
            return self.x * o.x + self.y * o.y + self.z * o.z

        def normalize(self):
            n = self.Length
            if n:
                self.x, self.y, self.z = self.x / n, self.y / n, self.z / n
            return self

        def distanceToPoint(self, o):
            return (self - o).Length

        def getAngle(self, o):
            n = self.Length * o.Length
            return math.acos(max(-1.0, min(1.0, self.dot(o) / n))) if n else 0.0

    class Matrix:
        """Not a matrix: what was done to it, in order, to be read in the trace."""

        def __init__(self, text="I"):
            self.__dict__["text"] = text

        def scale(self, *a):
            self.__dict__["text"] += f".scale({', '.join(show(x) for x in a)})"

        def move(self, *a):
            self.__dict__["text"] += f".move({', '.join(show(x) for x in a)})"

        def multiply(self, o):
            return Matrix(f"({self.text} * {o.text})")

        def inverse(self):
            return Matrix(f"inv({self.text})")

        def __setattr__(self, k, v):
            self.__dict__["text"] += f".{k}={show(v)}"

        def __repr__(self):
            return f"Matrix[{self.text}]"

    class Rotation:
        def __init__(self, *a):
            self.text = f"Rotation({', '.join(show(x) for x in a)})"
            self.Angle = math.radians(a[1]) if len(a) == 2 and isinstance(a[1], (int, float)) else 0.0
            self.Axis = Vec(a[0]) if a and isinstance(a[0], Vec) else Vec(0, 0, 1)

        def toMatrix(self):
            return Matrix(self.text)

        def multVec(self, v):
            return Vec(v)

        def __repr__(self):
            return self.text

    class Placement:
        def __init__(self, base=None, rot=None, *more):
            if isinstance(base, Placement):
                base, rot = base.Base, base.Rotation
            self.Base = Vec(base) if base is not None else Vec()
            self.Rotation = rot if rot is not None else Rotation()
            self.moved = base is not None and (self.Base.Length > 0 or rot is not None)

        def isIdentity(self):
            return not self.moved

        def toMatrix(self):
            return Matrix(f"P{show(self.Base)}")

        def multVec(self, v):
            return Vec(v) + self.Base

        def inverse(self):
            return Placement(-self.Base)

        def multiply(self, o):
            return Placement(self.Base + o.Base)

        def __repr__(self):
            return f"Placement({show(self.Base)})"

    class Box:
        def __init__(self, pts):
            pts = [Vec(p) for p in pts] or [Vec()]
            self.XMin, self.XMax = min(p.x for p in pts), max(p.x for p in pts)
            self.YMin, self.YMax = min(p.y for p in pts), max(p.y for p in pts)
            self.ZMin, self.ZMax = min(p.z for p in pts), max(p.z for p in pts)
            self.XLength, self.YLength, self.ZLength = self.XMax - self.XMin, self.YMax - self.YMin, self.ZMax - self.ZMin
            self.Center = Vec((self.XMin + self.XMax) / 2, (self.YMin + self.YMax) / 2, (self.ZMin + self.ZMax) / 2)
            self.DiagonalLength = Vec(self.XLength, self.YLength, self.ZLength).Length

        def isValid(self):
            return True

    # ---- meshes --------------------------------------------------------------------------------

    CUBE_P = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0), (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10)]
    CUBE_T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]

    class Facet:
        def __init__(self, m, i):
            self.PointIndices = tuple(m.tris[i])
            p, q, r = (m.pts[k] for k in m.tris[i])
            n = (q - p).cross(r - p)
            self.Area = n.Length / 2
            self.Normal = Vec(n).normalize()

    class FakeMesh:
        """Points and triangles; every method that changes it is written to
        the trace. Flags of the case (state["flags"]) bend what they do."""

        def __init__(self, pts=(), tris=(), solid=None, **kw):
            if len(pts) and not len(tris) and len(pts[0]) == 3 and not isinstance(pts[0][0], (int, float)):
                # Mesh.Mesh([[p, q, r], …]): triangles of points
                log("Mesh.Mesh", f"{len(pts)} triangles")
                tris = [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(pts))]
                pts = [p for t in pts for p in t]
                solid = bool(flag("mesh_closed"))
            self.__dict__.update(pts=[Vec(p) for p in pts], tris=[tuple(t) for t in tris], id=serial("mesh"), problems=set(), parts=None,
                                 volume=None, placement=Placement(), segments=None, forced_solid=solid, comps=None)
            self.__dict__.update(kw)

        def tag(self):
            return f"<{self.id}: {len(self.tris)} facets>"

        def _log(self, name, *a, **kw):
            log(f"{self.id}.{name}", *a, **kw)

        # reading
        @property
        def CountFacets(self):
            return len(self.tris)

        @property
        def CountPoints(self):
            return len(self.pts)

        @property
        def Area(self):
            return sum(Facet(self, i).Area for i in range(len(self.tris)))

        @property
        def Volume(self):
            if self.volume is not None:
                return self.volume
            return sum(self.pts[a].dot(self.pts[b].cross(self.pts[c])) for a, b, c in self.tris) / 6.0

        @property
        def BoundBox(self):
            return Box([self.placement.multVec(p) for p in self.pts])

        @property
        def Topology(self):
            return ([Vec(p) for p in self.pts], [tuple(t) for t in self.tris])

        @property
        def Points(self):
            return [Vec(p) for p in self.pts]

        @property
        def Facets(self):
            return [Facet(self, i) for i in range(len(self.tris))]

        @property
        def Placement(self):
            return self.placement

        @Placement.setter
        def Placement(self, v):
            self._log("Placement =", v)
            self.__dict__["placement"] = v

        def _open_edges(self):
            count = {}
            for t in self.tris:
                for i in range(3):
                    k = tuple(sorted((t[i], t[(i + 1) % 3])))
                    count[k] = count.get(k, 0) + 1
            return sum(1 for v in count.values() if v == 1)

        def isSolid(self):
            if self.forced_solid is not None:
                return self.forced_solid
            return bool(self.tris) and self._open_edges() == 0

        def countComponents(self):
            return self.comps if self.comps is not None else (len(self.parts) if self.parts else 1)

        def copy(self):
            m = FakeMesh(self.pts, self.tris)
            m.__dict__.update({k: v for k, v in self.__dict__.items() if k not in ("id", "pts", "tris")})
            m.__dict__["problems"] = set(self.problems)
            return m

        # evaluation
        def hasNonManifolds(self):
            return "nonManifolds" in self.problems

        def hasSelfIntersections(self):
            return "selfIntersections" in self.problems

        def hasNonUniformOrientedFacets(self):
            return "flippedNormals" in self.problems

        def hasCorruptedFacets(self):
            return "corruptedFacets" in self.problems

        def hasInvalidPoints(self):
            if flag("no_invalid_points_check"):
                raise RuntimeError("not in this build")
            return "invalidPoints" in self.problems

        def hasPointsOnEdge(self):
            return "pointsOnEdges" in self.problems

        def hasFacetsOutOfRange(self):
            return "indicesOutOfRange" in self.problems

        def hasInvalidNeighbourhood(self):
            return "invalidNeighbours" in self.problems

        def countNonUniformOrientedFacets(self):
            return 3 if "flippedNormals" in self.problems else 0

        def getSelfIntersections(self):
            return [(0, 1), (2, 3)] if "selfIntersections" in self.problems else []

        # repairs: each mends its problem; a case can have one fail or tear the mesh
        def _repair(self, name, mends=()):
            self._log(name)
            if name in flag("raises", ()):
                raise RuntimeError(f"{name} gave up")
            if name in flag("tears", ()):
                del self.tris[-1:]
            if name in flag("empties", ()):
                del self.tris[:]
            for p in mends:
                self.problems.discard(p)

        def fixIndices(self):
            self._repair("fixIndices", ["indicesOutOfRange"])

        def rebuildNeighbourHood(self):
            self._repair("rebuildNeighbourHood", ["invalidNeighbours"])

        def removeDuplicatedPoints(self):
            self._repair("removeDuplicatedPoints")

        def removeDuplicatedFacets(self):
            self._repair("removeDuplicatedFacets")

        def fixDegenerations(self, tol):
            self._log("fixDegenerations.args", tol)
            self._repair("fixDegenerations", ["corruptedFacets"])

        def removeNeedles(self, tol):
            self._log("removeNeedles.args", tol)
            self._repair("removeNeedles")

        def removeNonManifolds(self):
            self._repair("removeNonManifolds", ["nonManifolds"])

        def removeNonManifoldPoints(self):
            self._repair("removeNonManifoldPoints")

        def fixSelfIntersections(self):
            self._repair("fixSelfIntersections", ["selfIntersections"])

        def removeFoldsOnSurface(self):
            self._repair("removeFoldsOnSurface")

        def harmonizeNormals(self):
            self._repair("harmonizeNormals", ["flippedNormals"])

        def flipNormals(self):
            self._log("flipNormals")
            self.__dict__["tris"] = [(a, c, b) for a, b, c in self.tris]
            if self.volume is not None:
                self.__dict__["volume"] = -self.volume

        def fillupHoles(self, n):
            self._log("fillupHoles", n)
            if not flag("stays_open"):
                self.__dict__["forced_solid"] = True

        def removeComponents(self, n):
            self._log("removeComponents", n)

        def removePointsOnEdge(self, fill):
            self._log("removePointsOnEdge.args", fill)
            self._repair("removePointsOnEdge", ["pointsOnEdges"])

        # reshaping
        def decimate(self, tol, red):
            self._log("decimate", tol, red)
            keep = max(4, int(round(len(self.tris) * (1 - red))))
            if flag("decimate_stops"):
                keep = max(keep, len(self.tris) - 1)
            del self.tris[keep:]
            self.__dict__["forced_solid"] = self.isSolid() if flag("decimate_opens") else True

        def refine(self):
            self._log("refine")
            self.__dict__["forced_solid"] = self.isSolid()
            self.__dict__["tris"] = self.tris * 3

        def optimizeTopology(self, x):
            self._log("optimizeTopology", x)

        def smooth(self, **kw):
            self._log("smooth", **kw)
            if flag("shrinks"):
                self.__dict__["volume"] = self.Volume * flag("shrinks")

        def offset(self, d):
            self._log("offset", d)

        def trimByPlane(self, p, n):
            self._log("trimByPlane", p, n)
            if flag("trim_leaves_nothing"):
                del self.tris[:]
                return
            side = [[(self.pts[i] - p).dot(n) for i in t] for t in self.tris]
            self.__dict__["tris"] = [t for t, sd in zip(self.tris, side) if not (all(x >= 0 for x in sd) and any(x > 0 for x in sd))]

        def transform(self, mat):
            self._log("transform", mat)

        def translate(self, *a):
            self._log("translate", *a)
            self.__dict__["pts"] = [p + Vec(*a) for p in self.pts]

        def rotate(self, *a):
            self._log("rotate", *a)

        def addMesh(self, o):
            self._log("addMesh", o)
            k = len(self.pts)
            self.pts.extend(o.pts)
            self.tris.extend([tuple(i + k for i in t) for t in o.tris])
            self.__dict__["comps"] = self.countComponents() + o.countComponents()

        def addFacets(self, x):
            if isinstance(x, tuple) and len(x) == 2:
                self._log("addFacets", f"{len(x[0])} points", f"{len(x[1])} facets")
                if flag("no_indexed_facets"):
                    raise TypeError("triangles only")
                self.__dict__["pts"], self.__dict__["tris"] = [Vec(p) for p in x[0]], [tuple(t) for t in x[1]]
            else:
                self._log("addFacets", f"{len(x)} triangles")
                self.__dict__["pts"] = [Vec(p) for t in x for p in t]
                self.__dict__["tris"] = [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(x))]
                self.__dict__["forced_solid"] = not flag("reads_back_open")
            if flag("reads_back_open"):
                self.__dict__["forced_solid"] = False

        def _bool(self, name, o):
            self._log(name, o)
            how = flag("fc_bool")
            if how == "raises":
                raise RuntimeError("boolean failed")
            if how == "empty":
                return FakeMesh()
            r = cube()
            if how == "open":
                r.__dict__["forced_solid"] = False
            if how == "problems":
                r.problems.add("selfIntersections")
            return r

        def unite(self, o):
            return self._bool("unite", o)

        def intersect(self, o):
            return self._bool("intersect", o)

        def difference(self, o):
            return self._bool("difference", o)

        def crossSections(self, planes, tol, joined):
            self._log("crossSections", [(p, n) for p, n in planes], tol, joined)
            if flag("no_sections"):
                return [[] for _ in planes]
            out = []
            for p, n in planes:
                d = p.dot(n)
                loop = [Vec(0, 0, d), Vec(10, 0, d), Vec(10, 10, d), Vec(0, 10, d), Vec(0, 0, d)]
                out.append([loop, list(loop)] if flag("sections_twice") else [loop, [Vec(1, 1, d)]])
            return out

        def getSeparateComponents(self):
            self._log("getSeparateComponents")
            return list(self.parts) if self.parts else [self.copy()]

        def getPlanarSegments(self, dev, least):
            self._log("getPlanarSegments", dev, least)
            return [] if flag("no_segments") else [(0, 1), (2, 3), (4, 5, 6, 7)]

        def getSegmentsByCurvature(self, spec):
            self._log("getSegmentsByCurvature", spec)
            if flag("curvature_fails"):
                raise RuntimeError("no curvature here")
            return [] if flag("no_segments") else [(0, 1), (2, 3)]

        def meshFromSegment(self, idx):
            self._log("meshFromSegment", idx)
            m = FakeMesh(self.pts, [self.tris[i] for i in idx])
            return m

        def getCurvaturePerVertex(self):
            self._log("getCurvaturePerVertex")
            if flag("flat"):
                return [(0.0, 0.0, Vec(), Vec()) for _ in self.pts]
            return [(0.1 * (i % 3), -0.05 * (i % 2), Vec(1, 0, 0), Vec(0, 1, 0)) for i in range(len(self.pts))]

        def write(self, path):
            self._log("write", os.path.basename(path))
            if flag("write_raises"):
                raise RuntimeError("cannot write")
            if not flag("writes_nothing"):
                with open(path, "wb") as f:
                    f.write(b"x" * 84)

    def cube(at=(0, 0, 0), **kw):
        return FakeMesh([(x + at[0], y + at[1], z + at[2]) for x, y, z in CUBE_P], CUBE_T, **kw)

    def open_cube(**kw):
        return FakeMesh(CUBE_P, CUBE_T[2:], **kw)  # no bottom: one loop of four open edges

    def create(name):
        def make(*a):
            log(f"Mesh.{name}", *a)
            if flag("create_raises"):
                raise RuntimeError("cannot build")
            m = cube()
            if name == "createTorus" and flag("torus_on_side"):
                m.__dict__["pts"] = [Vec(p.z, p.y, p.x * 3) for p in m.pts]
            return m

        return make

    mesh_mod = types.ModuleType("Mesh")
    mesh_mod.Mesh = FakeMesh
    for k in ("createBox", "createSphere", "createCylinder", "createCone", "createTorus"):
        setattr(mesh_mod, k, create(k))

    # ---- shapes --------------------------------------------------------------------------------

    class Shape:
        def __init__(self, kind="Shape", pts=(), **kw):
            self.kind, self.pts, self.id = kind, [Vec(p) for p in pts], serial("shape")
            self.Edges, self.Faces, self.Solids, self.Wires, self.Vertexes = [], [], [], [], []
            self.Volume, self.Area, self.null, self.closed = 0.0, 0.0, False, True
            self.__dict__.update(kw)

        def tag(self):
            return f"<{self.id} {self.kind}>"

        @property
        def Length(self):
            return sum((q - p).Length for p, q in zip(self.pts, self.pts[1:]))

        @property
        def BoundBox(self):
            return Box(self.pts)

        def isNull(self):
            return self.null

        def isClosed(self):
            return self.closed

        def isValid(self):
            return True

        def tessellate(self, tol):
            log(f"{self.id}.tessellate", tol)
            if flag("no_triangles"):
                return [], []
            return [Vec(p) for p in CUBE_P], list(CUBE_T)

        def distToShape(self, o):
            return (abs(o.pts[0].z) * 0.01 + 0.001, [], [])

        def makeShapeFromMesh(self, topo, tol):
            log(f"{self.id}.makeShapeFromMesh", f"{len(topo[1])} facets", tol)
            self.Faces = ["face"] * len(topo[1])

        def _bool(self, name, o):
            log(f"{self.id}.{name}", o)
            if flag("solid_bool") == "raises":
                raise RuntimeError("no boolean")
            r = solid_shape()
            if flag("solid_bool") == "empty":
                r.Solids, r.Volume = [], 0.0
            return r

        def fuse(self, o):
            return self._bool("fuse", o)

        def common(self, o):
            return self._bool("common", o)

        def cut(self, o):
            return self._bool("cut", o)

    def solid_shape(**kw):
        s = Shape("Solid", CUBE_P, Volume=1000.0, Area=600.0)
        s.Faces, s.Edges, s.Solids = ["f"] * 6, ["e"] * 12, [s]
        s.__dict__.update(kw)
        return s

    def wire_shape(**kw):
        s = Shape("Wire", [(0, 0, 0), (10, 0, 0), (10, 10, 0)])
        s.Edges = ["e", "e"]
        s.__dict__.update(kw)
        return s

    def make_polygon(pts):
        log("Part.makePolygon", list(pts))
        if flag("polygon_raises"):
            raise RuntimeError("no wire")
        return Shape("Wire", pts)

    def compound(shapes):
        log("Part.Compound", list(shapes))
        return Shape("Compound", [p for s in shapes for p in s.pts])

    def face(w):
        log("Part.Face", w)
        if flag("face_raises"):
            raise RuntimeError("not planar")
        return Shape("Face", w.pts, Area=42.0)

    part = types.ModuleType("Part")
    part.Shape = Shape
    part.makePolygon, part.Compound, part.makeCompound, part.Face = make_polygon, compound, compound, face
    part.makeShell = lambda faces: (log("Part.makeShell", f"{len(faces)} faces"), Shape("Shell"))[1]
    part.makeSolid = lambda sh: (log("Part.makeSolid", sh), solid_shape())[1]
    part.Vertex = lambda p: Shape("Vertex", [p])

    def primitive(name, kind):
        def make(*a):
            log(f"Part.{name}", *a)
            return Shape(kind, CUBE_P, Area=100.0)

        return make

    part.makePlane, part.makeSphere, part.makeCylinder = primitive("makePlane", "Face"), primitive("makeSphere", "Solid"), primitive("makeCylinder", "Solid")

    class BSplineCurve:
        NbPoles, Degree = 7, 3

        def _fit(self, name, **kw):
            log(f"BSplineCurve.{name}", **kw)
            if flag("no_curve"):
                raise RuntimeError("the points fold back")
            self.pts = kw["Points"]

        def interpolate(self, **kw):
            self._fit("interpolate", **kw)

        def approximate(self, **kw):
            self._fit("approximate", **kw)

        def toShape(self):
            return Shape("Edge", self.pts)

    part.BSplineCurve = BSplineCurve

    def mesh_from_shape(**kw):
        log("MeshPart.meshFromShape", **kw)
        how = flag("meshing")
        if how == "raises":
            raise RuntimeError("mesher stopped")
        m = cube()
        if how == "open":
            m.__dict__["forced_solid"] = False
        if how == "nonmanifold":
            m.problems.add("nonManifolds")
        if how == "dense":
            m.__dict__["tris"] = m.tris * 17000
            m.__dict__["forced_solid"] = True
        return m

    def project(shape, m, d):
        log("MeshPart.projectShapeOnMesh", shape, m, d)
        if flag("projection") == "raises":
            raise RuntimeError("no projection")
        if flag("projection") == "none":
            return []
        return [[Vec(0, 0, 10), Vec(5, 0, 10), Vec(5, 0, 10), Vec(10, 0, 10)], [Vec(1, 1, 10)]]

    meshpart = types.ModuleType("MeshPart")
    meshpart.meshFromShape, meshpart.projectShapeOnMesh = mesh_from_shape, project


    # ---- a face to roll out (meshobj_unwrap) --------------------------------------------------

    def faced(kind):
        """A body of one face on a surface of that class."""
        import numpy as np

        srf = type(kind, (), {"Radius": 5.0, "SemiAngle": math.radians(30), "parameter": lambda self, p: (p.x / 5.0, p.y)})()
        ring = types.SimpleNamespace(discretize=lambda Deflection=0.05: (log("wire.discretize", Deflection=Deflection), [Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 4, 0), Vec(0, 4, 0)])[1])

        def tessellate(tol):
            log("face.tessellate", tol)
            return [Vec(*q) for q in ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 3))], [(0, 1, 2), (0, 2, 3)]

        f = Shape("Face", [(0, 0, 0), (10, 0, 0), (10, 10, 0)], Area=62.8, Surface=srf, ParameterRange=(0.0, math.pi, 0.0, 4.0), Wires=[ring], tessellate=tessellate)
        b = solid_shape()
        b.Faces = [f]
        b.getElement = lambda sub: f
        del np
        return b

    # flatmesh runs apart, in a Python of its own: here that run is the
    # stand-in's (it lays the points flat by dropping z, or stops).
    import importlib.machinery
    import importlib.util
    import subprocess

    real_find = importlib.util.find_spec

    def find_spec(name, package=None):
        if name == "flatmesh":
            return None if flag("no_flatmesh") else importlib.machinery.ModuleSpec("flatmesh", None)
        return real_find(name, package)

    importlib.util.find_spec = find_spec
    real_run = subprocess.run

    def run(cmd, *a, **kw):
        if not (isinstance(cmd, list) and len(cmd) == 5 and cmd[1] == "-c" and "flatmesh" in cmd[2]):
            return real_run(cmd, *a, **kw)
        import numpy as np

        z = np.load(cmd[3])
        log("flatmesh", z["P"], z["F"], cmd[2].split("findFlatNodes")[1].split("\n")[0])
        if flag("unwrap") == "stops":
            return types.SimpleNamespace(returncode=1, stderr="Traceback\nRuntimeError: singular matrix\n", stdout="")
        Q = np.array(z["P"], float)
        if flag("unwrap") == "stretched":
            Q[:, 0] *= 1.5
        loop = Q[[0, 1, 2, 3]] if len(Q) >= 4 else Q
        np.savez(cmd[4], Q=Q, n=np.array([len(loop), 2]), B=np.concatenate([loop, Q[:2]]))
        return types.SimpleNamespace(returncode=0, stderr="", stdout="")

    subprocess.run = run

    # ---- point clouds --------------------------------------------------------------------------

    class Cloud:
        """Points.Points: a kernel of points."""

        def __init__(self, pts=()):
            self.pts, self.id = [Vec(p) for p in (pts or [])], serial("cloud")

        def tag(self):
            return f"<{self.id}: {len(self.pts)} points>"

        @property
        def Points(self):
            return [Vec(p) for p in self.pts]

        @property
        def CountPoints(self):
            return len(self.pts)

        @property
        def BoundBox(self):
            return Box(self.pts)

        def addPoints(self, pts):
            log(f"{self.id}.addPoints", f"{len(pts)} points")
            self.pts.extend(Vec(p) for p in pts)

        def copy(self):
            return Cloud(self.pts)

        def read(self, path):
            log(f"{self.id}.read", os.path.basename(path))
            if flag("e57") == "raises":
                raise RuntimeError("no E57 library")
            self.pts = [Vec(i, 0, 0) for i in range(0 if flag("e57") == "empty" else 5)]

        def write(self, path):
            log(f"{self.id}.write", os.path.basename(path))
            with open(path, "wb") as f:
                f.write(b"p" * 10)

    points = types.ModuleType("Points")
    points.Points = Cloud

    def insert(path, docname):
        log("Points.insert", os.path.basename(path), docname)
        if flag("e57") == "raises":
            raise RuntimeError("no E57 library")
        d = state["doc"]
        d.new("App::DocumentObjectGroup", "Scan")
        if flag("e57") != "empty":
            o = d.new("Points::Feature", "Scan_1", Points=Cloud([(0, 0, 0), (1, 0, 0), (0, 1, 0), (float("nan") if flag("e57") == "nan" else 2, 2, 2)]))
            del o

    points.insert = insert

    # Reverse Engineering: a surface through a cloud, and Poisson's mesh.
    def approx_surface(**kw):
        log("ReverseEngineering.approxSurface", **kw)
        if flag("no_surface"):
            raise RuntimeError("the system is singular")
        return types.SimpleNamespace(toShape=lambda: Shape("Face", CUBE_P, Area=123.4567))

    def poisson(*a, **kw):
        log("ReverseEngineering.poissonReconstruction", *a, **kw)
        if kw and flag("poisson") == "old":
            raise TypeError("no keywords here")
        if flag("poisson") == "raises":
            raise RuntimeError("PCL is not here")
        return open_cube() if flag("poisson") == "open" else cube()

    reveng = types.ModuleType("ReverseEngineering")
    reveng.approxSurface, reveng.poissonReconstruction = approx_surface, poisson

    # ---- the document --------------------------------------------------------------------------

    class View:
        def __init__(self, owner):
            self.__dict__["owner"] = owner
            self.__dict__["Visibility"] = True

        def __setattr__(self, k, v):
            trace.append(f"{self.owner}.ViewObject.{k} = {show(v)}")
            self.__dict__[k] = v

    class Obj:
        def __init__(self, name, type_, **kw):
            self.__dict__.update({"Name": name, "TypeId": type_, "Label": name, "InList": [], "OutList": [], **kw})

        def tag(self):
            return f"<{self.Name}>"

        def __setattr__(self, k, v):
            trace.append(f"{self.Name}.{k} = {show(v)}")
            self.__dict__[k] = v

        def __getattr__(self, k):
            if k == "Placement":
                self.__dict__[k] = Placement()
                return self.__dict__[k]
            raise AttributeError(k)

        def isDerivedFrom(self, t):
            return t == self.TypeId or t in self.__dict__.get("kinds", ())

        def getStatusString(self):
            return "Valid"

        def addProperty(self, type_, name, group="", doc=""):
            trace.append(f"{self.Name}.addProperty({type_!r}, {name!r})")
            self.__dict__[name] = [] if "List" in type_ else "" if "String" in type_ else 0.0
            return self

    class Doc:
        Label = Name = "Doc"

        def __init__(self):
            self.Objects, self.Meta, self.records = [], {}, {}

        def new(self, type_, _name=None, **kw):
            """An object of the stand-in's own making (a case's furniture)."""
            base = _name or type_.split("::")[-1]
            n, i = base, 0
            while any(o.Name == n for o in self.Objects):
                i += 1
                n = f"{base}{i:03d}"
            o = Obj(n, type_, **kw)
            self.Objects.append(o)
            return o

        def addObject(self, type_, name):
            o = self.new(type_, name)
            trace.append(f"addObject({type_!r}, {o.Name!r})")
            if type_ == "Mesh::Feature":
                o.__dict__["Mesh"] = FakeMesh()
                if flag("views"):
                    o.__dict__["ViewObject"] = View(o.Name)
            if type_.startswith("Points::"):
                o.__dict__["Points"] = Cloud()
            if type_.startswith("Part::"):
                o.__dict__["Shape"] = Shape(null=True)
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

        def bodies(self):
            return [o for o in self.doc.Objects if o.TypeId.startswith("Part::") and getattr(o, "Shape", None) is not None and o.Shape.Solids]

        def body(self, ref):
            from agentlink.protocol import ToolError

            raise ToolError("invalid_state", "No body here.")

        # furniture for the cases
        def mesh(self, label, m=None, **kw):
            o = self.doc.new("Mesh::Feature", "Mesh", Mesh=m if m is not None else cube(), **kw)
            o.__dict__["Label"] = label
            if flag("views"):
                o.__dict__["ViewObject"] = View(o.Name)
            return o

        def shape(self, label, sh=None, type_="Part::Feature"):
            o = self.doc.new(type_, "Shape", Shape=sh if sh is not None else solid_shape())
            o.__dict__["Label"] = label
            return o

        def cloud(self, label, pts, type_="Points::Feature"):
            o = self.doc.new(type_, "Points", Points=Cloud(pts), kinds=("Points::Feature",))
            o.__dict__["Label"] = label
            return o

    fc = types.ModuleType("FreeCAD")
    fc.Vector, fc.Matrix, fc.Rotation, fc.Placement, fc.BoundBox, fc.GuiUp = Vec, Matrix, Rotation, Placement, Box, False
    fc.ActiveDocument = None
    fc.Console = types.SimpleNamespace(PrintMessage=lambda *a: None, PrintWarning=lambda *a: None, PrintError=lambda *a: None, PrintLog=lambda *a: None)
    fc.Version = lambda: ["1", "1", "3"]
    fc.ParamGet = lambda path: types.SimpleNamespace(GetString=lambda k, d="": d, GetBool=lambda k, d=False: d, GetInt=lambda k, d=0: d,
                                                     GetFloat=lambda k, d=0.0: d, SetString=lambda k, v: None, SetBool=lambda k, v: None)
    fc.getUserAppDataDir = lambda: "/tmp/"
    fc.Units = types.SimpleNamespace(Quantity=lambda *a: types.SimpleNamespace(Value=a[0] if a else 0.0))

    mods = {"FreeCAD": fc, "Part": part, "Mesh": mesh_mod, "MeshPart": meshpart, "Points": points, "ReverseEngineering": reveng}
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def importing(name, globals=None, locals=None, fromlist=(), level=0):
        # A module a case takes away (flags["missing"]) is not importable either.
        if level == 0 and name.split(".")[0] in state["flags"].get("missing", ()):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, globals, locals, fromlist, level)

    import builtins

    builtins.__import__ = importing
    sys.modules.update(mods)

    # The records the tools keep in the document, and Agent Link's own mesh
    # boolean: kept simple and bent by the case's flags.
    from agentlink import meshbool, store

    def read(doc, name, default):
        import json

        return json.loads(doc.records[name]) if name in doc.records else default

    def write(doc, name, value):
        import json

        log("store.write", name, value)
        doc.records[name] = json.dumps(value)

    store.read, store.write = read, write
    real_boolean = meshbool.boolean

    def boolean(*a):
        log("meshbool.boolean", *a)
        how = flag("own_bool")
        if how == "refuses":
            raise meshbool.BooleanError("the meshes touch along a face")
        V, F, x, y = real_boolean(*a)
        if how == "empty":
            F = F[:0]
        return V, F, x, y

    meshbool.boolean = boolean

    return types.SimpleNamespace(trace=trace, state=state, Session=Session, Obj=Obj, Shape=Shape, Vec=Vec, Mesh=FakeMesh, Cloud=Cloud, cube=cube,
                                 open_cube=open_cube, solid_shape=solid_shape, wire_shape=wire_shape, faced=faced, Placement=Placement, mods=mods, log=log)

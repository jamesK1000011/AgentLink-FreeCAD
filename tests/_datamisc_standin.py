# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in FreeCAD of tests/test_datamisc_data.py: tests/_datapart_standin.py
# as it is, and on top of it what the measuring, inspection, notes and robot
# tools reach: faces and edges that say what they are (a surface, a curve, a
# centre), distances with their two points, a cutting plane and its outlines,
# inertia, FreeCAD's Measure objects, the records kept in the document, a Mesh
# and a Points module, the Inspection feature, PartDesign bodies with a history
# the Robot module and an IfcOpenShell whose files are JSON. Nothing of the first stand-in is changed for its own
# test: this one is only ever installed in this test's child process.
import math
import types


def install():
    import importlib
    import sys

    import _datapart_standin

    fc = _datapart_standin.install()
    flag, log, show, trace, Shape, Obj, Vec, part = fc.flag, fc.log, fc.show, fc.trace, fc.Shape, fc.Obj, fc.Vec, fc.part
    Doc = type(fc.Session().doc)
    Vertex = part.Vertex
    Placement, Rotation = fc.fc.Placement, fc.fc.Rotation
    ns = types.SimpleNamespace

    def fails(what):
        if what in flag("fail", ()):
            raise RuntimeError(f"{what}: BRep_API: command not done")

    Doc.Meta = {}  # the records (agentlink/store.py) are kept in an object of the document; Meta is only read

    # ---- elements that say what they are ----------------------------------------------------
    # A case gives a shape's elements their particulars: shape.els = {"Face2": {"surface": "Cylinder",
    # "radius": 4.0, …}, "Edge3": {"curve": "Circle", …}}; an element without any is a flat face or a line.

    first_sub = Shape._make_sub

    def make_sub(self, kind, i):
        x = first_sub(self, kind, i)
        x.__dict__.update(getattr(self, "els", {}).get(f"{kind}{i}", {}))
        return x

    Shape._make_sub = make_sub

    def geometry(name):
        """A surface's or a curve's class by FreeCAD's name for it (the tools read the class's name)."""

        def of(key, default, wrap=lambda v: v):
            return property(lambda self: wrap(self.el.__dict__.get(key, default)))

        vec = lambda v: Vec(*v)  # noqa: E731
        return type(name, (), {
            "__init__": lambda self, el: self.__dict__.update(el=el), "parameter": lambda self, p: (0.0, 0.0) if name in SURFACES else 0.5,
            "value": lambda self, u, w: self.el.CenterOfMass, "kind": name,
            "Radius": of("radius", 5.0), "MajorRadius": of("radius", 5.0), "MinorRadius": of("minor", 1.0), "SemiAngle": of("semi", math.radians(30.0)),
            "Axis": of("axis", (0, 0, 1), vec), "Center": of("center", (0, 0, 0), vec), "Location": of("center", (0, 0, 0), vec), "Apex": of("apex", (0, 0, 10), vec)})

    SURFACES = ("Plane", "Cylinder", "Cone", "Sphere", "Toroid", "BSplineSurface", "Helicoid")
    CURVES = ("Line", "Circle", "Ellipse", "BSplineCurve", "Hyperbola")
    KINDS = {n: geometry(n) for n in SURFACES + CURVES}

    def surface(self):
        if self.__dict__.get("surface") == "broken":
            raise RuntimeError("no surface")
        return KINDS[self.__dict__.get("surface", "Plane")](self)

    def curve(self):
        if self.__dict__.get("curve") == "broken":
            raise RuntimeError("no curve")
        return KINDS[self.__dict__.get("curve", "Line")](self)

    def centre(self):
        c = self.__dict__.get("com")
        return Vec(*c) if c is not None else self.box.Center

    def normal_at(self, u, v):
        if self.__dict__.get("no_normal"):
            raise RuntimeError("normalAt: no normal there")
        return Vec(self.normal)

    def value_at(self, t):
        m = self.__dict__.get("mid")
        return Vec(*m) if m is not None else self.box.Center

    def dist_to_shape(self, o):
        log("distToShape", self, o)
        d = flag("dist")
        return (self.box.gap(o.box) if d is None else d, [(self.box.Center, o.box.Center)], [None])

    def inside(self, q, tol, face):
        return not flag("off_face")

    first_discretize = Shape.discretize

    def discretize(self, Number=None, Deflection=None):
        log("discretize", self, **({"Deflection": Deflection} if Number is None else {"Number": Number}))
        return first_discretize(self, flag("chord_points", 5) if Number is None else Number)

    def inertia(self):
        v = self.Volume
        return ns(A11=2.0 * v, A12=0.0, A13=0.0, A21=0.0, A22=3.0 * v, A23=0.5 * v, A31=0.0, A32=0.5 * v, A33=4.0 * v)

    def principal(self):
        if flag("no_principal"):
            raise RuntimeError("PrincipalProperties: not a solid of one piece")
        return {"Moments": (2.0 * self.Volume, 3.0 * self.Volume, 4.0 * self.Volume), "FirstAxis": Vec(1, 0, 0), "SecondAxis": Vec(0, 1, 0), "ThirdAxis": Vec(0, 0, 1)}

    def tessellate(self, tol):
        log("tessellate", self, tol)
        b = self.box
        z = b.ZMax
        return [Vec(b.XMin, b.YMin, z), Vec(b.XMax, b.YMin, z), Vec(b.XMax, b.YMax, z), Vec(b.XMin, b.YMax, z)], [(0, 1, 2), (0, 2, 3)]

    Shape.Surface, Shape.Curve, Shape.CenterOfMass = property(surface), property(curve), property(centre)
    Shape.MatrixOfInertia, Shape.PrincipalProperties = property(inertia), property(principal)
    Shape.ParameterRange, Shape.Orientation = (0.0, 1.0, 0.0, 1.0), "Forward"
    Shape.normalAt, Shape.valueAt, Shape.distToShape, Shape.isInside, Shape.discretize, Shape.tessellate = normal_at, value_at, dist_to_shape, inside, discretize, tessellate
    Vertex.distToShape, Vertex.isSame, Vertex.tag = dist_to_shape, (lambda self, o: self.Point == o.Point), "a point"

    # ---- a cutting plane ---------------------------------------------------------------------

    def reach(shape, n):
        b = shape.box
        span = [x * n.x + y * n.y + z * n.z for x in (b.XMin, b.XMax) for y in (b.YMin, b.YMax) for z in (b.ZMin, b.ZMax)]
        return min(span), max(span)

    class Plane:
        def __init__(self, p, n):
            log("Plane", p, n)
            self.p, self.n = Vec(p), Vec(n)

        def toShape(self, *limits):
            log("toShape", *limits)
            f = Shape(f"plane through {show(self.p)}", "Face", (-1e6, -1e6, -1e6), (1e6, 1e6, 1e6), faces=1, edges=4, wires=1, solids=0, shells=0)
            f.plane = self
            return f

        def parameter(self, q):
            return (q.x - self.p.x, q.y - self.p.y)

        def value(self, u, v):
            return Vec(self.p.x + u, self.p.y + v, self.p.z)

    first_common = Shape.common

    def common(self, o):
        pl = getattr(o, "plane", None)
        if pl is None:
            return first_common(self, o)
        log("common", self, o)
        fails("common")
        lo, hi = reach(self, pl.n)
        k = flag("regions", 1) if lo - 1e-9 <= pl.p.dot(pl.n) <= hi + 1e-9 else 0
        b = self.box
        out = Shape(f"cut of {self.tag}", "Compound", b.lo, b.hi, area=40.0 * k, faces=k, edges=4 * k, solids=0, shells=0)
        ring = [Vec(b.XMin, b.YMin, 0), Vec(b.XMax, b.YMin, 0), Vec(b.XMax, b.YMax, 0), Vec(b.XMin, b.YMax, 0)]
        out.els = {f"Face{i}": {"nwires": flag("loops", 1), "pts": ring} for i in range(1, k + 1)}
        return out

    Shape.common = common
    part.Plane = Plane

    # ---- the document: types a FreeCAD may lack, Measure objects ------------------------------

    MEASURES = {"Measure::MeasureDistance": "Distance", "Measure::MeasureAngle": "Angle", "Measure::MeasureLength": "Length", "Measure::MeasureArea": "Area",
                "Measure::MeasureRadius": "Radius", "Measure::MeasureDiameter": "Diameter", "Measure::MeasurePosition": "Position"}
    first_add = Doc.addObject

    def add_object(self, type_, name):
        if type_ in flag("no_types", ()):
            raise TypeError(f"No document object type called '{type_}'")
        o = first_add(self, type_, name)
        if type_ in MEASURES:
            v = Vec(1.23456, 2.0, 3.0) if type_.endswith("Position") else flag("measured", 12.345678)
            o.__dict__.update({MEASURES[type_]: ns(Value=v) if flag("quantities") else v, "State": list(flag("state", []))})
        return o

    Doc.addObject = add_object

    first_status = Obj.getStatusString

    def status(self):
        if flag("no_status"):
            raise RuntimeError("getStatusString: no status")
        return first_status(self)

    Obj.getStatusString = status

    # ---- Mesh, Points and the Inspection feature ------------------------------------------------

    import numpy as np

    mesh, points, inspection, robot, kuka = fc.Module("Mesh"), fc.Module("Points"), fc.Module("Inspection"), fc.Module("Robot"), fc.Module("KukaExporter")
    GRID = [(x, y, 10.0) for y in (2.0, 5.0, 8.0) for x in (2.0, 5.0, 8.0)]

    def file_name(path):
        return path.replace("\\", "/").rsplit("/", 1)[-1]

    class MeshData:
        """A mesh: read from a file (a case says which points it holds), or made of triangles."""

        def __init__(self, src=None, pts=None):
            if isinstance(src, str):
                log("Mesh", file_name(src))
                fails("Mesh")
                pts = flag("file_points", GRID)
            elif src is not None:
                log("Mesh", f"{len(src)} triangles")
                pts = list(dict.fromkeys(p for tri in src for p in tri))
            self.Points = [Vec(*p) for p in (pts or [])]
            self.Facets = [ns(PointIndices=(i, i + 1, i + 2)) for i in range(0, max(len(self.Points) - 2, 0))]

        def __repr__(self):
            return f"Mesh<{len(self.Points)} points>"

    class Cloud:
        def __init__(self, src=None, pts=None):
            if isinstance(src, str):
                log("Points", file_name(src))
                pts = flag("file_points", GRID)
            self.Points = [Vec(*p) for p in (pts or [])]

        def __repr__(self):
            return f"Points<{len(self.Points)}>"

    def read_cloud(path):
        log("Points.read", file_name(path))
        return Cloud(pts=flag("file_points", GRID))

    mesh.Mesh, points.Points, points.read = MeshData, Cloud, read_cloud
    sys.modules.update({"Mesh": mesh, "Points": points, "Inspection": inspection, "Robot": robot, "KukaExporter": kuka})
    fc.mods.update({"Mesh": mesh, "Points": points, "Inspection": inspection, "Robot": robot, "KukaExporter": kuka})

    def measured(o):
        """What FreeCAD's Inspection would give: a distance a point of the actual (a case says which, else a ripple)."""
        act = o.__dict__.get("Actual")
        data = getattr(act, "Mesh", None) or getattr(act, "Points", None)
        n = len(data.Points) if data is not None else 0
        d = flag("distances")
        return list(d) if d is not None else [round(0.1 * ((i % 5) - 2), 4) for i in range(n)]

    second_add = Doc.addObject

    def add_inspected(self, type_, name):
        o = second_add(self, type_, name)
        if type_ == "Inspection::Feature":
            o.__dict__.update(SearchRadius=0.05, Thickness=0.0, Distances=[], Nominals=[], Actual=None)
        return o

    first_recompute = Doc.recompute

    def recompute(self, objs=None):
        first_recompute(self, objs)
        for o in self.Objects:
            if o.TypeId == "Inspection::Feature":
                o.__dict__["Distances"] = measured(o)

    Doc.addObject, Doc.recompute = add_inspected, recompute
    Obj.touch = lambda self: trace.append(f"{self.Name}.touch()")

    # The body's tessellation and its splitting are agentlink.render's (not part of what was converted).
    from agentlink import render

    def body_layer(o, i, tol=None, **kw):
        log("body_layer", o, i, tol=tol)
        b = o.Shape.box
        V = np.array([[x, y, b.ZMax] for y in (b.YMin, b.YMax) for x in (b.XMin, b.XMax)], dtype=float)
        return {"name": o.Label, "V": V, "F": np.array([[0, 1, 2], [1, 3, 2]])}

    def subdivide(V, F, spacing, cap=None):
        log("subdivide", len(V), spacing, cap=cap)
        return V, F

    render.body_layer, render.subdivide = body_layer, subdivide

    # ---- notes and steps: picking faces and drawing are not part of what was converted ----------

    from agentlink import facepick
    from agentlink.protocol import ToolError

    def pick(shape, q, what="faces", names=()):
        log("pick", shape, q, what)
        names = [q] if isinstance(q, str) else q if isinstance(q, list) else flag("picks", ["Face1"])
        if not names or any(not isinstance(n, str) or int(n[4:]) > shape.nfaces for n in names):
            raise ToolError("not_found", f"{what}: nothing picked by {q!r}.")
        return [(n, shape.getElement(n)) for n in names]

    def draw(layers, view, width, height, frame=None, bottom=0, **kw):
        log("draw", [(layer["name"], len(layer["V"]), len(layer["F"])) for layer in layers], view, width, height, frame=frame, bottom=bottom)
        return np.zeros((height, width, 3)), None, None

    def text(img, words, x, y, scale=2, **kw):
        log("text", words, x, y, scale=scale)
        img[0, 0, 0] += len(words)

    def png(img):
        log("png", list(img.shape), float(img.sum()))
        return f"PNG {img.shape[1]}x{img.shape[0]} {img.sum():g}".encode()

    facepick.pick, render.draw, render.text, render.png = pick, draw, text, png

    class Clock:
        """datetime, stopped: a note's "made" is the same in every run."""

        class datetime:
            @staticmethod
            def now():
                return ns(isoformat=lambda timespec="auto": "2026-11-16T12:00:00")

    fc.Clock = Clock

    fc.MeshData, fc.Cloud, fc.np = MeshData, Cloud, np

    # ---- Robot ------------------------------------------------------------------------------------
    # A robot here is three sliding axes: its flange stands at 10 mm a degree of axes 1 … 3, and a
    # pose is reached when it is no further than a case's reach from the foot (2000 mm).

    Placement.inverse = lambda self: Placement(self.Base * -1, self.Rotation, self.centre)
    Placement.isIdentity = lambda self: self.Base == Vec() and not self.Rotation.a
    Rotation.toEuler = lambda self: tuple(float(x) for x in self.a) if len(self.a) == 3 and all(isinstance(x, (int, float)) for x in self.a) else (0.0, 0.0, 0.0)

    def flange(o):
        return Placement(Vec(*[10.0 * float(o.__dict__[f"Axis{i}"]) for i in (1, 2, 3)]))

    first_set = Obj.__setattr__

    def set_(self, k, v):
        if k in flag("no_props", ()):
            trace.append(f"{self.Name}.{k}: no such property")
            raise AttributeError(f"'{self.TypeId}' object has no attribute '{k}'")
        first_set(self, k, v)
        if self.TypeId != "Robot::RobotObject":
            return
        if k == "Tcp":
            if v.Base.Length <= flag("reach", 2000.0) and not flag("solver_fails"):
                turns = 360.0 * flag("turns", 0)
                self.__dict__.update(Axis1=v.Base.x / 10.0 + turns, Axis2=v.Base.y / 10.0, Axis3=v.Base.z / 10.0)
            elif flag("says_error"):
                self.__dict__["Error"] = "Pose out of reach"
        elif k.startswith("Axis"):
            self.__dict__["Tcp"] = flange(self)

    Obj.__setattr__ = set_

    class Waypoint:
        def __init__(self, pos, kind="LIN", name="Pt"):
            log("Waypoint", pos, kind, name)
            self.Pos, self.Type, self.Name, self.Velocity, self.Cont = pos, kind, name, 2000.0, False

        def __repr__(self):
            return f"Waypoint({self.Name} {self.Type} {show(self.Pos.Base)} v={self.Velocity:g}{' cont' if self.Cont else ''})"

    class Trajectory:
        def __init__(self, points=()):
            self.Waypoints = list(points)

        def _legs(self):
            w = self.Waypoints
            return [((q.Pos.Base - p.Pos.Base).Length, q.Velocity) for p, q in zip(w, w[1:])]

        Length = property(lambda self: sum(d for d, _v in self._legs()))
        Duration = property(lambda self: sum(d / v for d, v in self._legs()))

        def size(self):
            return len(self.Waypoints)

        def position(self, time):
            """Where the path is at a time: along the straight line from its first point to its last."""
            a, b = self.Waypoints[0].Pos.Base, self.Waypoints[-1].Pos.Base
            return Placement(a + (b - a) * (time / self.Duration))

        def __repr__(self):
            return f"Trajectory<{len(self.Waypoints)} points>"

    class Bare(Trajectory):
        """A trajectory as an older Robot module gives it: no size(), no Length."""

        size = Length = property(lambda self: (_ for _ in ()).throw(AttributeError("size")))

    def along(src):
        o, subs = src
        return Trajectory([point(Vec(10.0 * i, 0, 0), 500.0) for i in range(len(subs) + 1)])

    def point(at, speed):
        w = Waypoint.__new__(Waypoint)
        w.Pos, w.Type, w.Name, w.Velocity, w.Cont = Placement(at), "LIN", "Pt", speed, False
        return w

    def driven(o):
        """The trajectory FreeCAD works out for an object that follows others."""
        d = o.__dict__
        if o.TypeId.startswith("Robot::Edge2Tra"):
            return along(d["Source"]) if "Source" in d else None
        if o.TypeId == "Robot::TrajectoryCompound":
            return Trajectory([w for x in d.get("Source", []) for w in x.Trajectory.Waypoints])
        if o.TypeId.startswith("Robot::TrajectoryDressUp") and "Source" in d:
            pts = [point(w.Pos.multiply(d["PosAdd"]).Base if "PosAdd" in d else w.Pos.Base, d["Speed"] if d.get("UseSpeed") else w.Velocity) for w in d["Source"].Trajectory.Waypoints]
            return (Bare if flag("bare_trajectories") else Trajectory)(pts)
        return None

    third_add = Doc.addObject

    def add_robot(self, type_, name):
        o = third_add(self, type_, name)
        if type_ == "Robot::RobotObject":
            o.__dict__.update({f"Axis{i}": 0.0 for i in range(1, 7)}, Tcp=Placement(), Tool=Placement(), Error="", kinds=("Robot::RobotObject",))
            if flag("home") is not None:
                o.__dict__["Home"] = list(flag("home"))
        return o

    second_recompute = Doc.recompute

    def recompute_robots(self, objs=None):
        second_recompute(self, objs)
        for o in self.Objects:
            if o.TypeId.startswith("Robot::"):
                t = driven(o)
                if t is not None:
                    o.__dict__["Trajectory"] = t

    Doc.addObject, Doc.recompute = add_robot, recompute_robots

    def export(form):
        def write(o, t, path):
            log(form, o, t, file_name(path))
            fails("krl")
            if form == "ExportFullSub" and not flag("full_writes"):
                return
            if flag("writes_nothing"):
                return
            with open(path, "w", encoding="utf-8") as f:
                f.write("DEF " + t.Label.replace(" ", "_") + "()\n")
                for w in t.Trajectory.Waypoints:
                    f.write(f"LIN {{X {w.Pos.Base.x:g},Y {w.Pos.Base.y:g},Z {w.Pos.Base.z:g}}} ; {w.Type} {w.Velocity:g}\n")
                f.write("END\n")
        return write

    kuka.ExportCompactSub, kuka.ExportFullSub = export("ExportCompactSub"), export("ExportFullSub")
    robot.Waypoint, robot.Trajectory = Waypoint, Trajectory
    fc.fc.getResourceDir = lambda: flag("resources", "/no-such-freecad/resources")
    fc.fc.getHomePath = lambda: flag("home_path", "/no-such-freecad")
    fc.point, fc.Trajectory, fc.Placement = point, Trajectory, Placement

    # ---- IfcOpenShell -------------------------------------------------------------------------------
    # An IFC file here is a JSON file a case writes: {"schema", "entities": [{"id", "class", "GlobalId",
    # "Name", …, "storey": id, "material": id, "psets": {name: {prop: value}}, "qtos": {…}}]}.

    import json

    PRODUCTS = ("IfcWall", "IfcSlab", "IfcBeam", "IfcWindow", "IfcDoor", "IfcSpace", "IfcBuildingStorey", "IfcBuilding", "IfcSite")
    CLASSES = PRODUCTS + ("IfcProduct", "IfcProject", "IfcMaterial", "IfcMaterialLayerSet", "IfcMaterialLayerSetUsage", "IfcMaterialConstituentSet", "IfcClassification",
                          "IfcPropertySet", "IfcRelAssociatesClassification")
    ATTRIBUTES = ("Name", "Description", "ObjectType", "Tag")

    class Entity:
        def __init__(self, file, data):
            self.__dict__.update(data, file=file)

        def is_a(self, cls=None):
            mine = self.__dict__["class"]
            return mine if cls is None else cls == mine or (cls == "IfcProduct" and mine in PRODUCTS)

        def step(self):
            return self.__dict__["id"]

        def __getattr__(self, k):
            if k == "HasAssociations":
                return [x for x in self.file.entities if x.is_a("IfcRelAssociatesClassification") and self.step() in x.of]
            if k in ("Name", "Description") and self.__dict__["class"] in PRODUCTS:
                return None
            raise AttributeError(k)

        def __repr__(self):
            return f"#{self.step()}={self.is_a()}({self.__dict__.get('Name')!r})"

    class IfcFile:
        def __init__(self, path):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)  # anything else is not an IFC file
            self.schema = data["schema"]
            self.entities = [Entity(self, dict(e)) for e in data["entities"]]

        def by_type(self, cls):
            if cls not in CLASSES:
                raise RuntimeError(f"Entity with name '{cls}' not found in schema '{self.schema}'")
            return [e for e in self.entities if e.is_a(cls)]

        def by_guid(self, g):
            hit = [e for e in self.entities if e.__dict__.get("GlobalId") == g]
            if not hit:
                raise RuntimeError(f"Instance with GlobalId '{g}' not found")
            return hit[0]

        def by_id(self, i):
            return next(e for e in self.entities if e.step() == i)

        def new(self, cls, **data):
            e = Entity(self, {"id": max([x.step() for x in self.entities] + [0]) + 1, "class": cls, **data})
            self.entities.append(e)
            return e

        def write(self, path):
            log("write", file_name(path))
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"schema": self.schema, "entities": [{k: v for k, v in e.__dict__.items() if k != "file"} for e in self.entities]}, fh, indent=1, default=repr)

    def api_run(usage, f, **kw):
        trace.append(f"{usage}({', '.join(f'{k}={show(v)}' for k, v in kw.items())})")
        fails(usage)
        if flag("one_product") and "products" in kw:
            raise TypeError(f"{usage}() got an unexpected keyword argument 'products'")
        els = kw.get("products") or ([kw["product"]] if "product" in kw else [])
        if usage == "attribute.edit_attributes":
            for k, v in kw["attributes"].items():
                if k not in ATTRIBUTES:
                    raise AttributeError(f"entity instance of type '{f.schema}.{els[0].is_a()}' has no attribute '{k}'")
                els[0].__dict__[k] = v
        elif usage == "pset.add_pset":
            p = f.new("IfcPropertySet", Name=kw["name"], props={})
            els[0].__dict__.setdefault("psets", {})[kw["name"]] = p.step()
            return p
        elif usage == "pset.edit_pset":
            kw["pset"].props.update(kw["properties"])
        elif usage == "material.add_material":
            return f.new("IfcMaterial", Name=kw["name"])
        elif usage == "material.unassign_material":
            for e in els:
                if "material" not in e.__dict__:
                    raise RuntimeError("no material to unassign")
                del e.__dict__["material"]
        elif usage == "material.assign_material":
            for e in els:
                e.__dict__["material"] = kw["material"].step()
        elif usage == "spatial.assign_container":
            for e in els:
                e.__dict__["storey"] = kw["relating_structure"].step()
        elif usage == "classification.add_classification":
            return f.new("IfcClassification", Name=kw["classification"])
        elif usage == "classification.add_reference":
            f.new("IfcRelAssociatesClassification", of=[e.step() for e in els],
                  RelatingClassification=ns(Name=kw["name"], Identification=kw["identification"], ReferencedSource=kw["classification"]))
        elif usage == "root.remove_product":
            f.entities.remove(els[0])
        else:
            raise ValueError(f"{usage}: not a usage this stand-in knows")
        return None

    def get_container(el):
        i = el.__dict__.get("storey")
        return el.file.by_id(i) if i is not None else None

    def sets_of(el, which):
        out = {}
        for name, v in (el.__dict__.get(which) or {}).items():
            p = el.file.by_id(v) if isinstance(v, int) else None
            out[name] = {**(p.props if p is not None else v), "id": p.step() if p is not None else 0}
        return out

    def get_psets(el, **kw):
        if kw and flag("old_psets"):
            raise TypeError("get_psets() got an unexpected keyword argument 'qtos_only'")
        return sets_of(el, "qtos") if kw.get("qtos_only") else {**sets_of(el, "psets"), **({} if kw else sets_of(el, "qtos"))}

    def get_pset(el, name):
        v = (el.__dict__.get("psets") or {}).get(name)
        return {"id": v} if isinstance(v, int) else None

    def get_material(el):
        i = el.__dict__.get("material")
        return el.file.by_id(i) if i is not None else None

    def ifc_open(path):
        log("ifcopenshell.open", file_name(path))
        return IfcFile(path)

    ifc, ifc_api, ifc_util, ifc_el = fc.Module("ifcopenshell"), fc.Module("ifcopenshell.api"), fc.Module("ifcopenshell.util"), fc.Module("ifcopenshell.util.element")
    ifc.open, ifc.api, ifc.util, ifc_api.run, ifc_util.element = ifc_open, ifc_api, ifc_util, api_run, ifc_el
    ifc_el.get_container, ifc_el.get_psets, ifc_el.get_pset, ifc_el.get_material = get_container, get_psets, get_pset, get_material
    sys.modules.update({"ifcopenshell": ifc, "ifcopenshell.api": ifc_api, "ifcopenshell.util": ifc_util, "ifcopenshell.util.element": ifc_el})

    # ---- the tools' own modules, as they are -------------------------------------------------

    # shape_query's filter is measure's own here (the first stand-in put its own in its place).
    from agentlink.families import measure

    importlib.reload(measure)

    from agentlink import hooks
    from agentlink.families import material

    material._library = lambda: flag("library", {})
    fc.hooks, fc.reach, fc.Plane, fc.math = hooks, reach, Plane, math
    fc.ns = ns
    return fc

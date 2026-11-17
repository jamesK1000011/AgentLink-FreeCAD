# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in FreeCAD of tests/test_dataasm_data.py: tests/_datapart_standin.py
# as it is, and on top of it what the Assembly tools reach (families/assembly.py
# and assembly_more.py): an assembly object with its solver's answer, FreeCAD's
# JointObject, UtilsAssembly and CommandCreateView, placements that can be
# multiplied, turned back and compared (about z only), parts whose box follows
# their placement, round faces, a bill of materials that fills on recompute,
# and Agent Link's own records. It is not FreeCAD's solver: a case says what a
# solve answers and where a joint puts a part (flags). Nothing of the first
# stand-in is changed for its own test: this one is only ever installed in
# this test's child process.
import functools
import json
import math
import os

JOINT_TYPES = ["Fixed", "Revolute", "Cylindrical", "Slider", "Ball", "Distance", "Parallel", "Perpendicular", "Angle", "RackPinion", "Screw", "Gears", "Belt"]
GROUPS = ("Assembly::AssemblyObject", "Assembly::JointGroup", "Assembly::BomGroup", "Assembly::ViewGroup", "Assembly::AssemblyLink", "App::Part")


def install():
    import sys

    import _datapart_standin

    fc = _datapart_standin.install()
    flag, log, show, trace, Shape, Obj, Vec, part, state = fc.flag, fc.log, fc.show, fc.trace, fc.Shape, fc.Obj, fc.Vec, fc.part, fc.state
    Doc = type(fc.Session().doc)
    Placement, Rotation = fc.fc.Placement, fc.fc.Rotation
    Box = type(Shape().box)

    def fails(what):
        if what in flag("fail", ()):
            raise RuntimeError(f"{what}: it would not")

    # ---- rotations and placements: about z, enough to multiply, invert and compare ----

    first_rot = Rotation.__init__

    def rot_init(self, *a):
        first_rot(self, *a)
        if len(a) == 4 and all(isinstance(x, (int, float)) for x in a):  # a quaternion
            self.Angle = 2 * math.atan2(a[2], a[3])
        elif len(a) == 2 and isinstance(a[0], Rotation):
            self.Angle = turn(a[0]) + turn(a[1])

    def turn(r):
        """The rotation's angle about +z, radians."""
        return -r.Angle if r.Axis.z < 0 else r.Angle

    def mult_vec(self, v):
        c, s_ = math.cos(turn(self)), math.sin(turn(self))
        return Vec(round(v.x * c - v.y * s_, 9), round(v.x * s_ + v.y * c, 9), v.z)

    Rotation.__init__ = rot_init
    Rotation.multVec = mult_vec
    Rotation.multiply = lambda self, o: Rotation(Vec(0, 0, 1), math.degrees(turn(self) + turn(o)))
    Rotation.inverted = lambda self: Rotation(Vec(0, 0, 1), -math.degrees(turn(self)))
    Rotation.Q = property(lambda self: (0.0, 0.0, round(math.sin(turn(self) / 2), 9), round(math.cos(turn(self) / 2), 9)))

    Placement.multiply = lambda self, o: Placement(self.Base + self.Rotation.multVec(o.Base), self.Rotation.multiply(o.Rotation))
    Placement.inverse = lambda self: Placement(self.Rotation.inverted().multVec(self.Base) * -1, self.Rotation.inverted())
    Placement.copy = lambda self: Placement(Vec(self.Base), Rotation(Vec(0, 0, 1), math.degrees(turn(self.Rotation))))
    Placement.isSame = lambda self, o, tol=1e-7: (self.Base - o.Base).Length <= tol and abs(turn(self.Rotation) - turn(o.Rotation)) <= tol
    Placement.isIdentity = lambda self: self.Base.Length == 0 and turn(self.Rotation) == 0

    def box_add(self, o):
        u = self.union(o)
        self.lo, self.hi = u.lo, u.hi

    Box.add = box_add
    Box.intersect = lambda self, o: self.lo is not None and o.lo is not None and all(self.lo[i] < o.hi[i] and o.lo[i] < self.hi[i] for i in range(3))
    fc.fc.BoundBox = Box

    # ---- shapes: round faces and edges, points of a distance ----

    class Plane:
        pass

    class Sphere:
        pass

    class Cylinder:
        def __init__(self, centre, axis, radius):
            self.Center, self.Axis, self.Radius = centre, axis, radius

    class Circle:
        def __init__(self, centre, axis, radius):
            self.Center, self.Axis, self.Radius = centre, axis, radius

    def surface(self):
        if self.ShapeType != "Face":
            raise AttributeError("Surface")
        return self.__dict__.get("surface") or Plane()

    def curve(self):
        if self.ShapeType == "Face":
            raise AttributeError("Curve")
        return self.__dict__.get("curve") or fc.ns(kind="Line")

    def value_at(self, t, v=None):
        if v is not None:  # a face's point at (u, v)
            return Vec(self.__dict__.get("mid") or self.box.Center)
        return Vec(self.pts[0] if t == self.FirstParameter else self.pts[-1])

    def dist(self, o):
        return (self.box.gap(o.box), [(self.box.Center, o.box.Center)], [])

    Shape.Surface, Shape.Curve, Shape.valueAt, Shape.distToShape = property(surface), property(curve), value_at, dist
    Shape.CenterOfMass = property(lambda self: self.box.Center)
    Shape.ParameterRange = (0.0, 1.0, 0.0, 1.0)
    part.Plane, part.Sphere = Plane, Sphere
    part.getShape = lambda o: o.Shape  # a link's shape as placed: here the object's own

    def round_face(o, i, centre, axis, radius, hole, span=(0.0, 10.0)):
        """Face i of o's shape made a cylinder's: a hole's wall (its normal inward) or a pin's."""
        f = o.Shape.Faces[i - 1]
        c, d = Vec(*centre), Vec(*axis)
        side = Vec(1, 0, 0) if abs(d.x) < 0.9 else Vec(0, 1, 0)
        f.__dict__.update(surface=Cylinder(c, d, float(radius)), mid=c + side * radius, normal=side * (-1 if hole else 1), pts=[c + d * span[0], c + d * span[1]])
        return f

    def round_edge(o, i, centre, axis, radius):
        e = o.Shape.Edges[i - 1]
        e.__dict__["curve"] = Circle(Vec(*centre), Vec(*axis), float(radius))
        return e

    # ---- objects: groups, the assembly's solver, joints' properties, sheets ----

    first_set, first_get = Obj.__setattr__, Obj.__getattr__

    def set_(self, k, v):
        first_set(self, k, v)
        if k == "Placement" and "box0" in self.__dict__:  # a part's box follows its placement
            self.__dict__["Shape"].box = self.__dict__["box0"].moved(self.__dict__["Placement"].Base)

    def new_object(self, type_, name):
        if type_ in flag("no_types", ()):
            raise TypeError(f"No document object type called '{type_}'")
        o = state["doc"].new(type_, name.replace(" ", "_"))
        trace.append(f"{self.Name}.newObject({type_!r}, {o.Name!r})")
        dress(o)
        o.__dict__["within"] = self
        self.__dict__["Group"] = list(self.__dict__.get("Group", [])) + [o]
        o.InList.append(self)
        return o

    def solve(self):
        log("solve", self)
        n = state.setdefault("solves", 0)
        state["solves"] = n + 1
        for name, at in (flag("solve_puts") or {}).items():
            put(name, at)
        code = flag("solve", 0)
        if isinstance(code, list):
            code = code[min(n, len(code) - 1)]
        if code == "raise":
            raise RuntimeError("the solver threw")
        return code

    def export_asmt(self, p):
        log("exportAsASMT", self, os.path.basename(p))
        fails("exportAsASMT")
        if not flag("asmt_writes_nothing"):
            with open(p, "w") as f:
                f.write("OndselSolver\n")

    def cell_set(self, cell, v):
        log(f"{self.Name}.set", cell, v)
        self.__dict__["cells"][cell] = v

    def linked(self, *a):
        return self.__dict__.get("LinkedObject") or self

    is_asm = lambda o: o.TypeId == "Assembly::AssemblyObject"  # noqa: E731
    METHODS = {"newObject": (lambda o: o.TypeId in GROUPS, new_object), "solve": (is_asm, solve), "clearUndo": (is_asm, lambda self: log("clearUndo", self)),
               "isPartConnected": (is_asm, lambda self, o: o.Name not in flag("unconnected", ())), "exportAsASMT": (is_asm, export_asmt),
               "getPropertyByName": (lambda o: True, lambda self, k: getattr(self, k)), "getLinkedObject": (lambda o: o.TypeId.startswith("App::Link"), linked),
               "set": (lambda o: "cells" in o.__dict__, cell_set), "getContents": (lambda o: "cells" in o.__dict__, lambda self, cell: self.__dict__["cells"].get(cell, ""))}

    def get_(self, k):
        if k in METHODS and METHODS[k][0](self) and k not in flag("no_methods", ()):
            return functools.partial(METHODS[k][1], self)
        if k == "Document":
            return state["doc"]
        return first_get(self, k)

    Obj.__setattr__, Obj.__getattr__ = set_, get_

    def dress(o):
        """What an object of its type has from the start."""
        t, d = o.TypeId, o.__dict__
        if t in GROUPS:
            d["Group"] = []
        if t == "Assembly::AssemblyObject":
            d["Type"] = ""
        if t == "Assembly::AssemblyLink":
            d.update(LinkedObject=None, **({} if flag("no_rigid") else {"Rigid": True}))
        if t == "App::Link":
            d.update(LinkedObject=None)
        if t in ("Assembly::BomObject", "Spreadsheet::Sheet"):
            d.update(cells={}, **({"columnsNames": []} if t == "Assembly::BomObject" else {}))

    first_add, first_recompute = Doc.addObject, Doc.recompute

    def add_object(self, type_, name):
        if type_ in flag("no_types", ()):
            raise TypeError(f"No document object type called '{type_}'")
        o = first_add(self, type_, name)
        dress(o)
        return o

    def recompute(self, objs=None):
        first_recompute(self, objs)
        for o in self.Objects:  # FreeCAD's own BOM regenerates: its header, and a row a part
            if o.TypeId == "Assembly::BomObject" and o.columnsNames:
                asm = o.within.within
                cols = list(o.columnsNames)
                cells = {f"{chr(64 + c)}1": "'" + h for c, h in enumerate(cols, 1)}
                names = [x.Label for x in asm.Group if x.TypeId != "Assembly::JointGroup" and "Shape" in x.__dict__] + list(flag("bom_extra", ()))
                for r, nm in enumerate(names, 2):
                    cells.update({f"{chr(64 + cols.index('Index') + 1)}{r}": str(r - 1), f"{chr(64 + cols.index('Name') + 1)}{r}": "'" + nm,
                                  f"{chr(64 + cols.index('Quantity') + 1)}{r}": "1"})
                o.__dict__["cells"] = {**cells, **{k: v for k, v in o.__dict__["cells"].items() if k not in cells}}

    first_remove = Doc.removeObject

    def remove_object(self, name):
        gone = self.getObject(name)
        first_remove(self, name)
        for o in self.Objects:  # out of the groups that held it too
            if gone in o.__dict__.get("Group", ()):
                o.__dict__["Group"] = [x for x in o.__dict__["Group"] if x is not gone]

    Doc.addObject, Doc.recompute, Doc.removeObject = add_object, recompute, remove_object

    def put(name, at):
        """A part moved to at [x, y, z] (and turned to at[3] degrees about z), as a solve or a joint does."""
        o = state["doc"].getObject(name)
        o.Placement = Placement(Vec(*at[:3]), Rotation(Vec(0, 0, 1), at[3] if len(at) > 3 else 0.0))

    # ---- the Assembly workbench's modules ----

    jo, ua, cv = fc.Module("JointObject"), fc.Module("UtilsAssembly"), fc.Module("CommandCreateView")

    class JointProxy:
        def setJointConnectors(self, j, refs):
            log("setJointConnectors", j, refs)
            if refs:
                fails("setJointConnectors")
            j.__dict__.update(Reference1=refs[0] if refs else None, Reference2=refs[1] if len(refs) > 1 else None)
            for name, at in (flag("joint_puts") or {}).items() if refs else ():
                put(name, at)

        def updateJCSPlacements(self, j):
            log("updateJCSPlacements", j)
            fails("updateJCSPlacements")

        def flipOnePart(self, j):
            log("flipOnePart", j)
            for name, at in (flag("flip_puts") or {}).items():
                put(name, at)

    def joint(j, index):
        log("Joint", j, index)
        d = j.__dict__
        d.update(JointType=JOINT_TYPES[index], Reference1=None, Reference2=None, Placement1=Placement(), Placement2=Placement(), Offset1=Placement(), Offset2=Placement(),
                 Distance=0.0, Distance2=0.0, Angle=0.0, Proxy=JointProxy())
        d.update({"Activated": True} if flag("old_suppress") else {"Suppressed": False})
        if not flag("no_limits"):
            d.update(EnableAngleMin=False, EnableAngleMax=False, EnableLengthMin=False, EnableLengthMax=False, AngleMin=0.0, AngleMax=0.0, LengthMin=0.0, LengthMax=0.0)
        j.Proxy.setJointConnectors(j, [])

    def grounded_joint(g, o):
        log("GroundedJoint", g, o)
        g.__dict__["ObjectToGround"] = o

    jo.JointTypes, jo.JointUsingReverse, jo.Joint, jo.GroundedJoint = JOINT_TYPES, ["Fixed", "Revolute", "Cylindrical", "Slider", "Distance", "Parallel"], joint, grounded_joint
    jo.ViewProviderJoint = lambda vo: log("ViewProviderJoint", vo.owner)
    jo.ViewProviderGroundedJoint = lambda vo: log("ViewProviderGroundedJoint", vo.owner)

    def jcs(plc, ref):
        if flag("no_frames"):
            raise RuntimeError("no frames here")
        return ref[0].Placement.multiply(plc)

    def view_group(asm):
        return next((o for o in asm.Group if o.TypeId == "Assembly::ViewGroup"), None) or asm.newObject("Assembly::ViewGroup", "Views")

    ua.getJcsGlobalPlc, ua.getViewGroup = jcs, view_group

    class ViewProxy:
        def saveAssemblyAndExplode(self, view):
            log("saveAssemblyAndExplode", view)
            fails("saveAssemblyAndExplode")
            for st in view.Group:
                o = state["doc"].getObject(st.References[1][0].rstrip("."))
                if o.Name not in flag("explode_stuck", ()):
                    o.Placement = Placement(o.Placement.Base + st.MovementTransform.Base, o.Placement.Rotation)

    def exploded_view(view):
        log("ExplodedView", view)
        fails("ExplodedView")
        view.__dict__.update(Group=[], Proxy=ViewProxy())

    def exploded_step(st, kind):
        log("ExplodedViewStep", st, kind)
        st.__dict__.update(References=None, MovementTransform=Placement())

    cv.ExplodedView, cv.ExplodedViewStep = exploded_view, exploded_step
    cv.ViewProviderExplodedView = lambda vo: log("ViewProviderExplodedView", vo.owner)
    cv.ViewProviderExplodedViewStep = lambda vo: log("ViewProviderExplodedViewStep", vo.owner)
    mods = {"JointObject": jo, "UtilsAssembly": ua, "CommandCreateView": cv}
    sys.modules.update(mods)
    fc.mods.update(mods)

    # ---- Agent Link's own, not part of what was converted: records, noted paths, shape_query ----

    from agentlink import paths, store
    from agentlink.families import measure, picks

    def records():
        return state["doc"].__dict__.setdefault("records", {})

    def write(doc, name, value):
        log("store.write", name, value)
        records()[name] = json.loads(json.dumps(value))

    store.read = lambda doc, name, default: json.loads(json.dumps(records().get(name, default)))
    store.write = write
    store.materials = lambda doc: dict(records().get("materials", {}))

    def made(session, p, kind=None):
        log("made", p.replace(session.out_dir, "<out>"))
        return p

    paths.made = made

    def query(session, a, default_kind="face"):
        log("query", a)
        o = picks.solid_body(session, a.get("body"))
        kind = a.get("kind") or default_kind
        els = o.Shape.Edges if kind == "edge" else o.Shape.Faces
        return o, kind, [(i, els[i - 1], {"ref": f"{'Edge' if kind == 'edge' else 'Face'}{i}"}) for i in flag("query_hits", [1])]

    measure.query = query

    def a_part(label, lo, hi, name="Body", **kw):
        """A case's furniture: a solid body whose box follows its placement."""
        o = fc.body(label, fc.solid(label, lo, hi), name=name, **kw)
        o.__dict__["box0"] = Box(o.Shape.box.lo, o.Shape.box.hi)
        return o

    def an_object(type_, name, label=None, **kw):
        """An object of a type, dressed as the document would."""
        o = state["doc"].new(type_, name, **kw)
        dress(o)
        o.__dict__["Label"] = label or o.Name
        return o

    def into(group, o):
        group.__dict__["Group"] = list(group.__dict__.get("Group", [])) + [o]
        o.InList.append(group)
        o.__dict__["within"] = group
        return o

    fc.a_part, fc.an_object, fc.into, fc.round_face, fc.round_edge, fc.put, fc.joint, fc.records, fc.Placement, fc.Rotation = (
        a_part, an_object, into, round_face, round_edge, put, joint, records, Placement, Rotation)
    fc.Plane, fc.Sphere, fc.Cylinder = Plane, Sphere, Cylinder
    return fc

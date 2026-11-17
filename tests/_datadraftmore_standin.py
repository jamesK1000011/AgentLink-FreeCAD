# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in FreeCAD of tests/test_datadraftmore_data.py: tests/_datapart_standin.py's
# world with a Draft module beside it, as far as draft_more.py's tools reach. It is not
# Draft: a maker here writes down how it was called and answers an object of its kind
# with a simple shape, and a case says (flags) what a maker should do instead: answer
# nothing, fail, or raise the error Draft raises with another tab in front.
# Only ever installed in a child process.
import os
import tempfile
import types

import _datapart_standin


def install():
    fc = _datapart_standin.install()
    F, log, flag, doc, Vec, Shape, Obj, ns = fc.fc, fc.log, fc.flag, fc.doc, fc.Vec, fc.Shape, fc.Obj, types.SimpleNamespace

    # ---- what FreeCAD's own classes need beside the Part tools' stand-in ----
    Vec.isEqual = lambda self, o, tol: (self - o).Length <= tol
    F.Placement.multVec = lambda self, p: self.Base + p
    F.Placement.inverse = lambda self: F.Placement(self.Base * -1, self.Rotation)
    Shape.ParameterRange = property(lambda self: (0.0, 10.0, 0.0, 10.0))
    Shape.CenterOfMass = property(lambda self: self.BoundBox.Center)
    Shape.OrderedVertexes = property(lambda self: [fc.part.Vertex(p) for p in self.pts])
    curve_of = Shape.Curve.fget

    def curve(self):
        c = curve_of(self)
        c.TypeId = "Part::GeomCircle" if self.tag.rsplit("Edge", 1)[-1] in [str(i) for i in flag("round", ())] else "Part::GeomLine"
        return c

    Shape.Curve = property(curve)
    missing = Obj.__getattr__

    def attr(self, k):
        if k == "Document":  # None once the object is out of the document
            return doc() if any(x is self for x in doc().Objects) else None
        return missing(self, k)

    Obj.__getattr__ = attr

    def set_active(name):
        log("setActiveDocument", name)
        F.ActiveDocument = doc()

    F.setActiveDocument = set_active
    res = tempfile.mkdtemp()
    os.makedirs(os.path.join(res, "Mod", "TechDraw", "PAT"))
    with open(os.path.join(res, "Mod", "TechDraw", "PAT", "FCPAT.pat"), "w", encoding="utf-8") as f:
        f.write(";; FreeCAD's patterns\n*Diagonal4, 45 degree lines 4 mm apart\n45,0,0,0,4\n*Square, a grid\n0,0,0,0,5\n90,0,0,0,5\n")
    F.getResourceDir = lambda: res

    # ---- Draft ----
    draft = fc.Module("Draft")

    def new(kind, base, shape=None, **props):
        o = doc().new("Part::Part2DObjectPython", base, Proxy=ns(Type=kind), **props)
        o.__dict__["Shape"] = shape if shape is not None else Shape(f"{o.Name}, no shape", "Compound", null=True, solids=0)
        return o

    def line(tag, pts=((0, 0, 0), (10, 0, 0), (10, 10, 0)), closed=False):
        return fc.wire(tag, [tuple(p) for p in pts], closed=closed)

    def maker(fname, build, show=None):
        def run(*a, **kw):
            fc.trace.append(f"Draft.{fname}({', '.join([fc.show(x) for x in (show(*a) if show else a)] + [f'{k}={fc.show(v)}' for k, v in kw.items()])})")
            if fname in flag("attr_error", ()):
                new("Stray", "Stray")  # Draft had made something before the view failed it
                raise AttributeError(flag("attr_msg", "'NoneType' object has no attribute 'getViewDirection'"))
            if fname in flag("type_error", ()) and "projection" not in kw:
                raise TypeError(f"{fname}() takes 1 positional argument but 2 were given")
            if fname in flag("fail", ()):
                raise RuntimeError(f"{fname}: Draft could not")
            if fname in flag("none", ()):
                return None
            return build(*a, **kw)

        setattr(draft, fname, run)

    def curve_maker(kind):
        return lambda pts, closed=False, face=None: new(kind, kind, line(f"a {kind}", pts, closed), Points=list(pts), Closed=closed)

    maker("make_wire", curve_maker("Wire"))
    maker("make_bspline", curve_maker("BSpline"))
    maker("make_bezcurve", curve_maker("BezCurve"))
    maker("make_rectangle", lambda le, h, placement=None, face=None: new("Rectangle", "Rectangle", fc.face("a rectangle", [(0, 0, 0), (le, 0, 0), (le, h, 0), (0, h, 0)], area=le * h)))
    maker("make_circle", lambda r, placement=None, face=None, startangle=None, endangle=None: new(
        "Circle", "Circle", Shape("a circle", "Wire", closed=startangle is None, solids=0, shells=0) if flag("circle_no_vertex")
        else line("a circle", [(r, 0, 0), (-r, 0, 0)]), Radius=r))
    maker("make_ellipse", lambda major, minor, placement=None, face=None: new("Ellipse", "Ellipse", line("an ellipse", [(major, 0, 0), (0, minor, 0)])))
    maker("make_polygon", lambda sides, r, inscribed=True, placement=None, face=None: new("Polygon", "Polygon", line("a polygon", [(r, 0, 0), (0, r, 0), (-r, 0, 0)], True)))
    maker("make_point", lambda x, y, z: new("Point", "Point"))

    def dim(*a, **kw):
        return new("LinearDimension", "Dimension", Distance=flag("distance", 12.5))

    def angular(center, angles, line_=None, normal=None):
        return new("AngularDimension", "Dimension", **(flag("angular_props") or {"FirstAngle": angles[0], "LastAngle": angles[1]}))

    maker("make_linear_dimension_obj", dim)
    maker("make_linear_dimension", dim)
    maker("make_radial_dimension_obj", dim)
    maker("make_angular_dimension", angular)
    maker("make_label", lambda **kw: new("Label", "dLabel", Text=list(flag("label_reads", kw.get("custom_text") or ["12.00 mm"])), LabelType=kw["label_type"], CustomText=[]))

    def array(base, *a, **kw):
        return new("Array", "Array", fc.solid("copies", (0, 0, 0), (30, 10, 10)), **({} if flag("no_count") else {"Count": flag("count", 4)}))

    for name in ("make_ortho_array", "make_polar_array", "make_circular_array", "make_path_array", "make_point_array"):
        maker(name, array)
    maker("make_clone", lambda o: new("Clone", "Clone", o.Shape, **({} if flag("bim_clone") else {"Scale": Vec(1, 1, 1)})))

    def modify(kind):
        def run(objs, *a, copy=False, **kw):
            if copy or kind == "Mirror":
                return [new(kind, kind, o.Shape) for o in objs]
            return (objs[0] if flag("modify_answers", objs) == "first" else flag("modify_answers", objs))
        return run

    for name in ("move", "rotate", "scale"):
        maker(name, modify("Wire"))
    maker("mirror", modify("Mirror"))
    maker("offset", lambda o, delta, copy=False: new("Wire", "Offset", o.Shape) if copy else o)

    def grade(objs, delete=True):
        how = flag("grade", "made")
        if how == "closes":  # Draft closes an open Draft wire in place
            for o in objs:
                if "Closed" in o.__dict__:
                    o.Closed = True
            return [[], []]
        if how == "nothing":
            return [[], []]
        if how == "odd":
            return None
        made = [new("Wire", "Upgraded", line(f"upgraded {i}", pts, False)) for i, pts in enumerate(flag("grade_makes", [((0, 0, 0), (10, 0, 0))]))]
        if delete:
            for o in objs:
                doc().removeObject(o.Name)
        return [made, list(objs) if delete else []]

    maker("upgrade", grade)
    maker("downgrade", grade)

    def join(objs):
        how = flag("join", "one")
        if how == "none":
            return None
        if how == "same":
            return list(objs)
        for o in objs[1:]:
            doc().removeObject(o.Name)
        return [objs[0]]

    maker("join_wires", join)
    maker("make_fillet", lambda objs, r, chamfer=False, delete=False: new("Fillet", "Fillet", line("a fillet")))

    def layer(name=None, line_width=None):
        o = new("Layer", "Layer", Group=[])
        o.__dict__["Label"] = name
        return o

    maker("make_layer", layer)
    maker("make_hatch", lambda base, pat, name, sc, rot: new("Hatch", "Hatch", None if flag("hatch_empty") else line("hatch lines")),
          show=lambda base, pat, *rest: (base, os.path.basename(pat)) + rest)

    def draftify(objs, makeblock=False, delete=False):
        how = flag("draftify", "list")
        if how == "none":
            return None
        made = [new("Wire", "Wire", line(f"draftified {o.Name}")) for o in objs]
        return made[0] if how == "one" else made + [None]

    maker("draftify", draftify)

    def view2d(base, d=None, projection=None):
        return new("Shape2DView", "Shape2DView", None if flag("view_empty") else line("a projection"), **({} if flag("old_view") else {"HiddenLines": False, "ProjectionMode": "Solid"}))

    maker("make_shape_2d_view", view2d)
    maker("make_shape2dview", view2d)

    def facebinder(sel):
        if flag("binder_wants_tuples") and any(isinstance(sub, list) for _o, sub in sel):
            raise ValueError("make_facebinder: a tuple of names")
        return new("Facebinder", "Facebinder", fc.face("bound faces", [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]), **({} if flag("old_binder") else {"Extrusion": 0.0, "Offset": 0.0}))

    maker("make_facebinder", facebinder)
    maker("make_workingplaneproxy", lambda pl: new("WorkingPlaneProxy", "WPProxy"))
    maker("makeWorkingPlaneProxy", lambda pl: new("WorkingPlaneProxy", "WPProxy"))
    maker("make_sketch", lambda objs, autoconstraints=True, delete=False: new("Sketch", "Sketch", Geometry=[], Constraints=[]))
    import sys

    sys.modules["Draft"] = draft
    fc.mods["Draft"] = draft
    fc.draft, fc.new, fc.line = draft, new, line
    return fc

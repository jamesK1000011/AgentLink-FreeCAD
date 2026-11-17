# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in FreeCAD of tests/test_datask2_data.py: tests/_datapd_standin.py
# as it is, and on top of it what the parameter tools (families/param.py), the
# further Part Design tools (feature_more.py) and the further Sketcher tools
# (sketch_more.py) reach: a spreadsheet with aliases, expressions bound to
# properties, variable sets with typed properties, primitives, helices, gears
# and sprockets, binders and booleans, and the Sketcher's own copy, array,
# extend, join, carbon copy, B-spline and validation calls. Nothing of the
# first stand-in is changed for its own test: this one is only ever installed
# in this test's child process.
import math
import re
import types

QTYPES = {"App::PropertyLength": "mm", "App::PropertyDistance": "mm", "App::PropertyAngle": "deg", "App::PropertyQuantity": ""}
UNITS = ("mm", "cm", "m", "in", "deg", "rad", "N", "kg")
NUMBER = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+))\s*([^\s\d].*)?$")
CELL = re.compile(r"^([A-Z]+)(\d+)$")


def install():
    import sys

    import _datapd_standin

    fc = _datapd_standin.install()
    flag, log, show, trace, Obj, Vec, part, state = fc.flag, fc.log, fc.show, fc.trace, fc.Obj, fc.Vec, fc.part, fc.state
    Doc = type(fc.Session().doc)

    class Q:
        """A quantity: its number and unit, written as FreeCAD writes it."""

        def __init__(self, value, unit=""):
            self.Value, self.Unit = float(value), unit

        def __str__(self):
            return f"{self.Value:g} {self.Unit}".strip()

        def __repr__(self):
            return f"Q({self})"

    # ---- a spreadsheet: cells, aliases, what a cell evaluates to -------------------------------

    def cells(o):
        return o.__dict__.setdefault("cells", {})

    def aliases(o):
        return o.__dict__.setdefault("aliases", {})

    def sheet_set(self, addr, content):
        trace.append(f"{self.Name}.set({addr!r}, {content!r})")
        if content.startswith("=") and ("??" in content or content.count("(") != content.count(")")):
            content = "'" + content  # Cell::setContent keeps what it cannot parse as text
        cells(self)[addr] = content

    def sheet_value(o, content, depth=0):
        if content.startswith("'"):
            return content[1:]
        text = content.lstrip("=").strip()
        m = NUMBER.match(text)
        if m:
            return Q(m.group(1), m.group(2).strip()) if m.group(2) else float(m.group(1))
        if text.startswith("<<"):
            return text.strip("<>")
        if depth > 5:
            raise RuntimeError("Circular reference")
        known = {}
        for addr, al in aliases(o).items():
            try:
                v = sheet_value(o, cells(o).get(addr, ""), depth + 1)
            except Exception:  # noqa: BLE001 - a name that does not evaluate is not a name here
                continue
            known[al] = v.Value if isinstance(v, Q) else v
        try:
            return Q(eval(text, {"__builtins__": {}}, known), "mm")  # noqa: S307 - the stand-in's own arithmetic over a case's cells
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Cannot evaluate {text}: {e}") from None

    def sheet_get(self, name):
        addr = next((a for a, al in aliases(self).items() if al == name), name if name in cells(self) else None)
        if addr is None:
            raise ValueError(f"Invalid cell address or alias: {name}")
        return sheet_value(self, cells(self)[addr])

    def set_alias(self, addr, alias):
        trace.append(f"{self.Name}.setAlias({addr!r}, {alias!r})")
        if alias in flag("bad_alias", ()):
            raise ValueError("Invalid alias")
        if alias:
            aliases(self)[addr] = alias
        else:
            aliases(self).pop(addr, None)

    def remove_rows(self, row, n):
        trace.append(f"{self.Name}.removeRows({row!r}, {n})")
        r = int(row)
        for store in (cells(self), aliases(self)):
            moved = {}
            for addr, v in store.items():
                col, k = CELL.match(addr).groups()
                if int(k) < r:
                    moved[addr] = v
                elif int(k) >= r + n:
                    moved[f"{col}{int(k) - n}"] = v
            store.clear()
            store.update(moved)

    Obj.set, Obj.get, Obj.getContents, Obj.setAlias, Obj.removeRows = sheet_set, sheet_get, lambda self, a: cells(self).get(a, ""), set_alias, remove_rows
    Obj.getAlias = lambda self, a: aliases(self).get(a)
    Obj.getNonEmptyCells = lambda self: list(cells(self))

    def params(s, rows, label="Params"):
        """A Params sheet as param_set leaves it: (name, content, note) rows."""
        ss = s.doc.new("Spreadsheet::Sheet", "Params")
        ss.__dict__["Label"] = label
        cells(ss).update({"A1": "name", "B1": "value", "C1": "note"})
        for i, (name, content, *note) in enumerate(rows, 2):
            cells(ss).update({f"A{i}": "'" + name, f"B{i}": content})
            aliases(ss)[f"B{i}"] = name
            if note:
                cells(ss)[f"C{i}"] = "'" + note[0]
        return ss

    # ---- expressions bound to properties ----------------------------------------------------------

    def set_expression(self, path, expr):
        trace.append(f"{self.Name}.setExpression({path!r}, {expr!r})")
        if expr is not None and flag("no_bind"):
            raise RuntimeError(flag("no_bind"))
        kept = [(p, e) for p, e in self.__dict__.get("ExpressionEngine", []) if p != path]
        self.__dict__["ExpressionEngine"] = kept + ([(path, expr)] if expr is not None else [])

    def eval_expression(self, expr):
        trace.append(f"{self.Name}.evalExpression({expr!r})")
        if "nope" in expr:
            raise RuntimeError("Cannot resolve nope")

    def get_datum(self, name):
        c = next(c for c in self.__dict__["Constraints"] if c.Name == name)
        return Q(c.Value, "mm")

    Obj.setExpression, Obj.evalExpression, Obj.getDatum = set_expression, eval_expression, get_datum

    def bound(o, path, expr):
        """A property bound before the call."""
        o.__dict__["ExpressionEngine"] = list(o.__dict__.get("ExpressionEngine", [])) + [(path, expr)]

    # ---- variable sets: typed properties ------------------------------------------------------------

    def add_property(self, typ, name, group="", doc_=""):
        trace.append(f"{self.Name}.addProperty({typ!r}, {name!r}, {group!r})")
        self.__dict__.setdefault("types", {})[name] = typ
        self.__dict__[name] = Q(0, QTYPES[typ]) if typ in QTYPES else {"App::PropertyBool": False, "App::PropertyInteger": 0, "App::PropertyFloat": 0.0}.get(typ, "")

    first_set = Obj.__setattr__

    def setattr_(self, k, v):
        typ = self.__dict__.get("types", {}).get(k)
        if typ in QTYPES:
            trace.append(f"{self.Name}.{k} = {show(v)}")
            if isinstance(v, str):
                m = NUMBER.match(v)
                if not m or (m.group(2) or "").strip() not in UNITS:
                    raise ValueError(f"Quantity: unit mismatch in {v!r}")
                v = Q(m.group(1), m.group(2).strip())
            elif isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError("Quantity expected")
            else:
                v = Q(v, QTYPES[typ])
            self.__dict__[k] = v
            return
        if typ in ("App::PropertyInteger", "App::PropertyBool") and isinstance(v, str):
            trace.append(f"{self.Name}.{k} = {show(v)}")
            raise TypeError("Argument must be int")
        first_set(self, k, v)

    Obj.__setattr__ = setattr_
    first_get = Obj.__getattr__

    def getattr_(self, k):
        v = first_get(self, k)
        if k == "PropertiesList":
            v = v + [p for p in self.__dict__.get("types", {}) if p not in v]
        return v

    Obj.__getattr__ = getattr_
    first_type = Obj.getTypeIdOfProperty
    Obj.getTypeIdOfProperty = lambda self, p: self.__dict__.get("types", {}).get(p) or first_type(self, p)
    Obj.addProperty = add_property
    Obj.getPropertyStatus = lambda self, p: ["Hidden"] if p in flag("hidden_vars", ()) else []

    def varset(s, label="Dims", **vars_):
        """A variable set as varset_new leaves it: name=(type, value)."""
        o = s.doc.new("App::VarSet", "VarSet")
        o.__dict__["Label"] = label
        o.__dict__["types"] = {}
        for name, (typ, v) in vars_.items():
            o.__dict__["types"][name] = typ
            o.__dict__[name] = Q(*v) if isinstance(v, tuple) else v
        return o

    # ---- documents: what is new here ------------------------------------------------------------------

    first_add, first_new = Doc.addObject, Doc.new

    def add_object(self, type_, name=None):
        if type_ == "App::VarSet" and flag("no_varset"):
            raise RuntimeError("No document object type called App::VarSet")
        return first_add(self, type_, name)

    def new(self, type_, _name=None, **kw):
        o = first_new(self, type_, _name, **kw)
        short = type_.split("::")[-1]
        if short.endswith("Helix"):
            o.__dict__.update(Pitch=10.0, Height=30.0, Turns=3.0, Angle=0.0, LeftHanded=False, Reversed=False, **({} if flag("no_growth") else {"Growth": 0.0}))
        elif short == "SubShapeBinder" and not flag("no_bindmode"):
            o.__dict__["BindMode"] = "Synchronized"
        elif short == "Scaled":
            o.__dict__.update(Factor=2.0, Occurrences=2)
        return o

    Doc.addObject, Doc.new = add_object, new

    first_derived = Obj.isDerivedFrom

    def derived(self, t):
        short = self.TypeId.split("::")[-1]
        if t == "PartDesign::Feature" and self.TypeId.startswith("PartDesign::") and (short.startswith(("Additive", "Subtractive")) or short == "Scaled"):
            return True
        return first_derived(self, t)

    Obj.isDerivedFrom = derived

    def add_objects(self, objs):
        trace.append(f"{self.Name}.addObjects({show(objs)})")
        self.__dict__["Group"] = list(objs)

    Obj.addObjects = add_objects

    # ---- the gear and the sprocket: FreeCAD's own makers ----------------------------------------------

    gear = types.ModuleType("InvoluteGearFeature")

    def involute(prof):
        log("_InvoluteGear", prof)
        prof.__dict__.update(AddendumCoefficient=1.0, **({} if flag("no_shift") else {"ProfileShiftCoefficient": 0.0}))

    gear._InvoluteGear = involute
    pkg, wires, maker = (types.ModuleType(n) for n in ("fcsprocket", "fcsprocket.fcsprocket", "fcsprocket.sprocket"))

    class FCWireBuilder:
        def __init__(self):
            self.wire = []

    def create_sprocket(w, pitch, teeth, roller):
        log("CreateSprocket", pitch, teeth, roller)
        w.wire = [part.Circle(Vec(), None, pitch), part.Circle(Vec(), None, roller)]

    wires.FCWireBuilder, maker.CreateSprocket = FCWireBuilder, create_sprocket
    pkg.fcsprocket, pkg.sprocket = wires, maker
    sys.modules.update({"InvoluteGearFeature": gear, "fcsprocket": pkg, "fcsprocket.fcsprocket": wires, "fcsprocket.sprocket": maker})

    fc.Q, fc.params, fc.varset, fc.bound, fc.cells, fc.aliases = Q, params, varset, bound, cells, aliases
    _sketcher(fc, Q)
    return fc


def _sketcher(fc, Q):
    """What sketch_more.py reaches of the Sketcher: curves copied and moved by
    a matrix, the Sketcher's copy, array, extend, join, carbon copy, B-spline,
    validation and repair calls, and a sketch emptied and filled again."""
    import copy

    flag, log, show, trace, Obj, Vec, part = fc.flag, fc.log, fc.show, fc.trace, fc.Obj, fc.Vec, fc.part

    class Matrix:
        def __init__(self, *ops):
            self.ops, self.A11, self.A22 = list(ops), 1, 1

        def move(self, v):
            self.ops.append(f"move {show(v)}")

        def scale(self, x, y, z):
            self.ops.append(f"scale {x:g} {y:g} {z:g}")

        def multiply(self, o):
            return Matrix(*o.ops, *self.ops)

        def __repr__(self):
            return f"Matrix({', '.join(self.ops)}; {self.A11}, {self.A22})"

    fc.fc.Matrix = Matrix
    first_placement = fc.Placement.__init__

    def placement(self, base=None, rot=None, *centre):
        first_placement(self, base, rot, *centre)
        self.centre = centre

    fc.Placement.__init__ = placement
    fc.Placement.toMatrix = lambda self: Matrix(f"{self!r} about {show(list(self.centre))}")

    Curve2 = part.LineSegment.__mro__[1]

    def transform(self, m):
        self.moved = getattr(self, "moved", ()) + (repr(m),)

    first_repr = Curve2.__repr__
    Curve2.copy = lambda self: copy.copy(self)
    Curve2.transform = transform
    Curve2.__repr__ = lambda self: first_repr(self) + "".join(f" by {m}" for m in getattr(self, "moved", ()))
    fc.Constraint.clone = lambda self: copy.copy(self)
    B = part.BSplineCurve
    B.Degree = 3
    B.NbPoles = property(lambda self: len(self.pts))
    B.getKnots = lambda self: [0.0, 0.33333333, 1.0]
    B.getMultiplicities = lambda self: [self.Degree + 1, 1, self.Degree + 1]

    first_dist = fc.Shape.distToShape

    def dist(self, o):
        """(gap, the nearest points, …): flags gap and meet say what a line going on finds."""
        return (float(flag("gap", first_dist(self, o)[0])), [(Vec(*flag("meet", (45.0, 0.0, 0.0))), Vec())], None)

    fc.Shape.distToShape = dist

    def geo(self):
        return self.__dict__["Geometry"]

    first_geometry, first_constraint, first_external = Obj.addGeometry, Obj.addConstraint, Obj.addExternal

    def add_geometry(self, g, construction=False):
        if not isinstance(g, list):
            return first_geometry(self, g, construction)
        trace.append(f"{self.Name}.addGeometry({show(g)}, {construction!r})")
        for x in g:
            x.Construction = bool(construction)
        self.__dict__["Geometry"] = geo(self) + g
        return list(range(len(geo(self)) - len(g), len(geo(self))))

    def add_constraint(self, c):
        if not isinstance(c, list):
            return first_constraint(self, c)
        trace.append(f"{self.Name}.addConstraint({show(c)})")
        self.__dict__["Constraints"] = self.__dict__["Constraints"] + c

    def add_external(self, name, sub, *defining):
        if defining and flag("no_defining"):
            trace.append(f"{self.Name}.addExternal: too many arguments")
            raise TypeError("addExternal() takes exactly 2 arguments (3 given)")
        if defining:
            trace.append(f"{self.Name}.addExternal: defining")
        return first_external(self, name, sub)

    def copies_of(self, ids):
        return [copy.copy(geo(self)[g]) for g in ids]

    def to_nurbs(self, g):
        old = geo(self)[g]
        if type(old).__name__ == "Point":
            trace.append(f"{self.Name}.convertToNURBS({g}): a point")
            raise ValueError("Point is not a curve")
        self._op("convertToNURBS", g)
        gs = list(geo(self))
        gs[g] = B(old.ends())
        gs[g].Construction = old.Construction
        self.__dict__["Geometry"] = gs

    def degree(self, g, by):
        self._op("changeBSplineDegree", g, by)
        geo(self)[g].Degree = geo(self)[g].Degree + by
        return geo(self)[g].Degree >= 1

    def missing(self, prec, *more):
        if more and flag("old_detect"):
            raise TypeError("detectMissingPointOnPointConstraints() takes 1 argument")
        if flag("no_detect"):
            raise RuntimeError("no detection here")
        self.__dict__["MissingPointOnPointConstraints"] = [0] * flag("missing", 0)
        return None if flag("old_detect") else flag("missing", 0)

    def remove_redundant(self, on):
        self._op("autoRemoveRedundants", on)
        gone = [i - 1 for i in self.__dict__.get("RedundantConstraints", ())]
        self.__dict__["Constraints"] = [c for i, c in enumerate(self.__dict__["Constraints"]) if i not in gone]

    def make_hv(self, on):
        self._op("makeMissingVerticalHorizontal", on)
        self.__dict__["Constraints"] = self.__dict__["Constraints"] + [fc.Constraint("Horizontal", 0)] * flag("auto_adds", 0)

    def clear(self, what):
        trace.append(f"{self.Name}.deleteAll{what}()")
        self.__dict__[what if what == "Constraints" else "Geometry"] = []

    def degenerate(self, prec):
        if flag("no_detect"):
            raise RuntimeError("no detection here")
        return flag("degenerate", 0)

    def evaluate(self):
        if flag("no_detect"):
            raise RuntimeError("no detection here")
        return not flag("invalid_cons")

    first_insert = Obj.insertObject

    def insert_object(self, o, target, after=False):
        if flag("no_insert"):
            trace.append(f"{self.Name}.insertObject: refused")
            raise RuntimeError("Cannot insert here")
        return first_insert(self, o, target, after)

    Obj.addGeometry, Obj.addConstraint, Obj.addExternal, Obj.insertObject = add_geometry, add_constraint, add_external, insert_object
    Obj.addCopy = lambda self, ids, v, clone=False: self._op("addCopy", ids, v, clone, adds=copies_of(self, ids))
    Obj.addMove = lambda self, ids, v: self._op("addMove", ids, v)
    Obj.addRectangularArray = lambda self, ids, v, clone, along, across, constrain, scale: self._op(
        "addRectangularArray", ids, v, clone, along, across, constrain, scale, adds=copies_of(self, ids) * (along * across - 1))
    Obj.extend = lambda self, g, inc, end: self._op("extend", g, inc, end)
    Obj.join = lambda self, g1, p1, g2, p2, cont=0: self._op("join", g1, p1, g2, p2, cont, adds=[B(geo(self)[g1].ends() + geo(self)[g2].ends())])
    Obj.carbonCopy = lambda self, name, construction=False: self._op("carbonCopy", name, construction, adds=copies_of(self.Document.getObject(name), range(len(geo(self.Document.getObject(name))))))
    Obj.convertToNURBS, Obj.increaseBSplineDegree = to_nurbs, degree
    Obj.insertBSplineKnot = lambda self, g, param, mult=1: self._op("insertBSplineKnot", g, param, mult)
    Obj.modifyBSplineKnotMultiplicity = lambda self, g, knot, by=1: self._op("modifyBSplineKnotMultiplicity", g, knot, by)
    Obj.detectDegeneratedGeometries, Obj.detectMissingPointOnPointConstraints, Obj.evaluateConstraints = degenerate, missing, evaluate
    Obj.removeDegeneratedGeometries = lambda self, prec: self._op("removeDegeneratedGeometries", prec)
    Obj.makeMissingPointOnPointCoincident = lambda self, on=False: self._op("makeMissingPointOnPointCoincident", on)
    Obj.validateConstraints = lambda self: self._op("validateConstraints")
    Obj.detectMissingVerticalHorizontalConstraints = lambda self, ang: self._op("detectMissingVerticalHorizontalConstraints", round(ang, 6))
    Obj.autoRemoveRedundants, Obj.makeMissingVerticalHorizontal = remove_redundant, make_hv
    Obj.deleteAllConstraints, Obj.deleteAllGeometry = lambda self: clear(self, "Constraints"), lambda self: clear(self, "Geometry")

    held = Obj.__getattr__

    def getattr_(self, k):
        if k == "decreaseBSplineDegree" and not flag("no_lower"):
            return lambda g, by: False if flag("lower_fails") else degree(self, g, -by)
        return held(self, k)

    Obj.__getattr__ = getattr_

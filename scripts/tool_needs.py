# SPDX-License-Identifier: LGPL-2.1-or-later
"""The readers: which helpers a dry reading may call (tool_groups { needs }).

A dry reading of a data tool (agentlink/needs.py) evaluates the tool's
leading `let` steps to say which of its checks would refuse, without running
the tool. It may only call a helper that reads. This script decides which
helpers those are, from the source alone (ast: no FreeCAD is imported), and
writes them per family to agentlink/data/readers.json:

    python3 scripts/tool_needs.py            # rewrite readers.json
    python3 scripts/tool_needs.py --check    # exit 1 when it is stale
    python3 scripts/tool_needs.py --why body # why a helper is, or is not, a reader

The rule is an allowlist, so what is not understood is not a reader. A helper
is a reader when its code, and the code of everything it calls in this
package, does nothing but:

  - read names, attributes and items; arithmetic; build new values;
  - assign local names (never an attribute: `o.Label = …` is a change; an
    item only of a value made in the function itself);
  - call a builtin that reads (len, sorted, isinstance, getattr …), a
    function of a listed module (math, re, os.path …; FreeCAD's and Part's
    constructors of values), another function of this package that is
    itself a reader, an exception's class, or a method whose name is in
    READ_METHODS below (reads on whatever has them: isDerivedFrom,
    getObject, distToShape …; never a method that changes what it is called
    on — Mesh's and Points' property objects are the document's own);
  - call a method that changes its own object (append, update, normalize …,
    FRESH_METHODS) only on a value the function made itself.

Anything else — a method not listed, setattr, a call of a parameter or of a
value worked out at run time, a class of this package made, a file opened
for writing, global, the session's own state written — and the helper is
left out; `--why name` says which line. What the rule cannot see: a property
whose reading has an effect inside FreeCAD (none is known among those the
readers touch), and an import's own effects (a workbench's Python module
loaded on first use).
"""
import ast
import builtins
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PKG = os.path.join(ROOT, "agentlink")
FAM = os.path.join(PKG, "families")
DATA = os.path.join(PKG, "data")
OUT = os.path.join(DATA, "readers.json")

# Builtins that read or build a value.
BUILTINS = {"abs", "all", "any", "ascii", "bin", "bool", "bytes", "callable", "chr", "complex", "dict", "divmod", "enumerate", "filter", "float",
            "format", "frozenset", "getattr", "hasattr", "hash", "hex", "id", "int", "isinstance", "issubclass", "iter", "len", "list", "map", "max",
            "min", "next", "oct", "ord", "pow", "range", "repr", "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple", "type", "zip"}
EXCEPTIONS = {n for n in dir(builtins) if isinstance(getattr(builtins, n), type) and issubclass(getattr(builtins, n), BaseException)}
# What makes a new value of its own (a "fresh" one, which its maker may change).
MAKERS = {"list", "dict", "set", "sorted", "tuple", "reversed", "bytearray", "V", "Vector", "Placement", "Rotation", "Matrix", "BoundBox"}

# Modules outside this package: the functions a reader may call ("*": all but those listed under "-").
MODULES = {
    "math": "*", "cmath": "*", "re": "*", "difflib": "*", "itertools": "*", "collections": "*", "statistics": "*", "string": "*", "fnmatch": "*",
    "operator": "*", "bisect": {"bisect", "bisect_left", "bisect_right"}, "copy": "*", "struct": {"unpack", "unpack_from", "calcsize", "pack"},
    "base64": "*", "hashlib": "*", "textwrap": "*", "unicodedata": "*", "colorsys": "*", "fractions": "*", "decimal": "*", "datetime": "*",
    "json": {"loads", "dumps"}, "time": {"time", "monotonic", "perf_counter", "strftime", "localtime", "gmtime"},
    "os.path": {"isfile", "isdir", "exists", "basename", "dirname", "join", "isabs", "splitext", "abspath", "normpath", "expanduser", "relpath",
                "getsize", "getmtime", "realpath", "split", "commonpath", "samefile", "normcase"},
    "os": {"getcwd", "listdir", "fspath", "getenv", "sep"}, "shutil": {"which"}, "glob": {"glob"}, "sys": set(), "platform": "*",
    "importlib": {"import_module"}, "importlib.util": {"find_spec"}, "numpy.linalg": "*",
    "numpy": ("*", {"save", "savez", "savez_compressed", "savetxt", "load", "loadtxt", "fromfile", "memmap", "copyto", "put", "place", "putmask",
                    "seterr", "random"}),
    # FreeCAD's own: constructors of values and readings. Nothing that opens, makes, activates or writes.
    "FreeCAD": {"Vector", "Placement", "Rotation", "Matrix", "BoundBox", "Version", "ParamGet", "getHomePath", "getResourceDir", "getUserAppDataDir",
                "getUserMacroDir", "ConfigGet", "listDocuments", "getDocument"},
    "FreeCAD.Units": {"Quantity", "parseQuantity"},
    "Part": {"Shape", "Vertex", "Edge", "Wire", "Face", "Shell", "Solid", "Compound", "CompSolid", "LineSegment", "Line", "Circle", "Ellipse", "Arc",
             "ArcOfCircle", "ArcOfEllipse", "Point", "Plane", "Cylinder", "Cone", "Sphere", "Toroid", "BSplineCurve", "BSplineSurface", "BezierCurve",
             "makeBox", "makeCylinder", "makeCone", "makeSphere", "makeTorus", "makePlane", "makePolygon", "makeLine", "makeCircle", "makeCompound",
             "makeFace", "makeShell", "makeSolid", "makeLoft", "makeHelix", "makeWedge", "makeRuledSurface", "makeFilledFace", "makeSplitShape",
             "sortEdges", "getSortedClusters", "makeLongHelix", "makeThread", "makeRevolution", "makeSweepSurface", "makeTube", "cast_to_shape",
             "makeWireString", "makeShellFromWires", "getShape"},
    "Mesh": {"Mesh"}, "Points": {"Points"},
}
ALIASES_OF = {"np": "numpy", "App": "FreeCAD"}

# Functions of this package taken as readers without their code being read here, each with why.
TRUSTED = {
    # The session's own book of one document's steps and calls (agentlink/docstates.py): looked up, and made
    # empty for a document met for the first time. Neither the document nor the window is touched.
    ("docstates.py", "own"): "the session's own record of a document, made empty when first asked",
    ("docstates.py", "settle"): "the session's own record of a document, made empty when first asked",
    # part_attach's check before anything is set: the references and mode are set on a copy of the object's
    # attacher (o.Attacher is a copy, copied once more), and only its calculateAttachedPlacement is asked.
    ("model_more.py", "attach_check"): "sets a copy of the attacher only, to ask it whether the attachment fits",
    # sketch_of's notes for the call's own answer (decision 4, 23 Nov): the sketch a left-out sketch took (filled)
    # and the sketch the call works on (sketchNote), on the session's per-call lists. Never the document or the
    # window, and nothing while a dry reading runs (needs.dry()).
    ("pd_common.py", "took"): "notes the call's own answer on the session; nothing in a dry reading",
    ("pd_common.py", "note_named"): "notes the call's own answer on the session; nothing in a dry reading",
}


# Methods taken as readings by their name, on whatever has them (a string's, a dict's, numpy's, FreeCAD's own: a
# document's, an object's, a shape's, a mesh's, a sheet's, the window's getters, a parameter group's). A name is
# here only when no class the helpers meet changes itself, the document, the selection or the window by it.
READ_METHODS = (
    "lower", "upper", "strip", "lstrip", "rstrip", "split", "rsplit", "splitlines", "join", "startswith", "endswith", "replace", "format",
    "capitalize", "title", "casefold", "isalnum", "isalpha", "isdigit", "isnumeric", "isspace", "isupper", "islower", "zfill", "ljust", "rjust",
    "center", "find", "rfind", "index", "rindex", "count", "partition", "rpartition", "encode", "decode", "get", "items", "keys", "values", "copy",
    "union", "intersection", "difference", "issubset", "issuperset", "isdisjoint", "fromkeys", "group", "groups", "groupdict", "match", "search", "fullmatch",
    "findall", "finditer", "sub", "is_integer", "tolist", "astype", "reshape", "sum", "mean", "min", "max", "std", "dot", "cross", "any", "all",
    "argmin", "argmax", "argsort", "nonzero", "ravel", "flatten", "isDerivedFrom", "normalize", "getObject", "getObjectsByLabel", "hasObject",
    "getPropertyByName", "getTypeIdOfProperty", "getGroupOfProperty", "getDocumentationOfProperty", "getEnumerationsOfProperty", "getEditorMode",
    "getParentGeoFeatureGroup", "getParentGroup", "hasExtension", "getSubObject", "getLinkedObject", "getGlobalPlacement", "getStatusString",
    "getAngle", "distanceToPoint", "distanceToLine", "distanceToPlane", "distanceToLineSegment", "isEqual", "isOnLineSegment", "negative", "multVec",
    "inverse", "inverted", "isIdentity", "isSame", "toMatrix", "toEuler", "toEulerAngles", "getYawPitchRoll", "isNull", "isValid", "isClosed",
    "isSolid", "isInside", "isPartner", "distToShape", "common", "fuse", "section", "removeSplitter", "slices", "makeOffsetShape", "makeOffset2D",
    "makeThickness", "makeFillet", "makeChamfer", "extrude", "revolve", "transformGeometry", "transformed", "translated", "rotated", "scaled",
    "childShapes", "ancestorsOfType", "findPlane", "getElement", "countElement", "optimalBoundingBox", "valueAt", "tangentAt", "normalAt", "parameterAt", "curvatureAt",
    "derivative1At", "discretize", "toShape", "toNurbs", "value", "normal", "tangent", "parameter", "curvature", "projectPoint", "isPlanar",
    "intersected", "united", "getPoint", "closestPoint", "countComponents", "getSeparateComponents", "hasNonManifolds", "hasSelfIntersections",
    "hasNonUniformOrientedFacets", "countNonUniformOrientedFacets", "getPlanarSegments", "getSegmentsOfType", "getSegmentsByCurvature",
    "crossSections", "nearestFacetOnRay", "getEigenSystem", "getConstruction", "getDatum", "getIndexByName", "getDriving", "getActive",
    "getContents", "getAlias", "getCellFromAlias", "getStyle", "getAlignment", "getForeground", "getBackground", "getDisplayUnit", "getColumnWidth",
    "getRowHeight", "getUsedCells", "getNonEmptyCells", "getUsedRange", "getNonEmptyRange", "isMergedCell", "findParentPage", "getEdgeByIndex", "getVertexByIndex", "windowTitle",
    "objectName", "text", "isVisible", "isEnabled", "isChecked", "actions", "toolTip", "activeWorkbench", "listWorkbenches", "listCommands",
    "getInEdit", "getSelection", "getSelectionEx", "getMainWindow", "name", "GetBool", "GetInt", "GetUnsigned", "GetFloat", "GetString", "GetBools",
    "GetInts", "GetUnsigneds", "GetFloats", "GetStrings", "GetGroup", "GetGroups", "HasGroup", "GetContents", "IsEmpty", "getValueAs",
    "getUserPreferred",
)
# (normalize is a vector's, FreeCAD 1.1's only one: it changes the vector it is called on, which is a value of
# the run — FreeCAD hands a property's vector out as a copy — and never the document. A drawing view's
# getEdgeByIndex and getVertexByIndex build a new shape from the view's geometry: DrawViewPartPyImp.cpp.)
# Methods that change the value they are called on: readings only on a value the function made itself.
FRESH_METHODS = (
    "append", "extend", "insert", "add", "update", "pop", "popitem", "remove", "discard", "clear", "sort", "reverse", "setdefault", "multiply", "scale", "translate", "rotate", "transformShape", "move", "enlarge", "cut", "transpose",
)
READS, FRESH = set(READ_METHODS), set(FRESH_METHODS)
# Of READ_METHODS, Python's own (a string's, a dict's, a set's, a match's, a float's, numpy's): everything up to
# FreeCAD's first, but the few FreeCAD's values have as readings too (a sheet's get, a vector's sub, dot and
# cross, a placement's or a shape's copy). A dry reading takes one of these on a Python value only
# (agentlink/needs.py guards the receiver), so a FreeCAD class that changes itself by such a name is never met.
SHARED = ("get", "copy", "sub", "dot", "cross")
PYTHON_ONLY = tuple(m for m in READ_METHODS[:READ_METHODS.index("isDerivedFrom")] if m not in SHARED)
# Two names FreeCAD has as changes: a sketch's split(geoId, point) and join(geoId1, posId1, geoId2, posId2), found
# by reading every *PyImp.cpp of FreeCAD 1.1 for a method that is not const and bears a READ_METHODS name. They
# are a string's only by their arguments: split with at most one, or a text first; join with exactly one.
BY_SHAPE = ("split", "join")


def string_call(name, args):
    """Whether x.split(…) or x.join(…) is a string's, by its arguments (ast nodes)."""
    if name == "join":
        return len(args) == 1
    return len(args) <= 1 or (isinstance(args[0], ast.Constant) and isinstance(args[0].value, str))
# FreeCAD's own methods that write the document, the selection, the window or a setting: names nothing else has
# (never one a list, a dict or a string has too). A helper that is not a reader because of one of these, or
# because it sets a FreeCAD property (o.Label = …: a capital first letter, as every property has), is a
# "changer": the step that calls it is where a tool's leading part ends.
WRITE_METHODS = (
    "newObject", "addObject", "removeObject", "addObjects", "removeObjects", "removeObjectsFromDocument", "copyObject", "moveObject", "recompute",
    "touch", "purgeTouched", "enforceRecompute", "solve", "setExpression", "clearExpression", "addProperty", "removeProperty", "setEditorMode",
    "setPropertyStatus", "openTransaction", "commitTransaction", "abortTransaction", "saveAs", "saveCopy", "addGeometry", "delGeometry",
    "delGeometries", "addConstraint", "delConstraint", "setDatum", "setDriving", "setConstruction", "toggleConstruction", "addExternal",
    "delExternal", "movePoint", "moveGeometry", "addView", "removeView", "setAlias", "setStyle", "setAlignment", "setForeground", "setBackground",
    "setDisplayUnit", "mergeCells", "splitCell", "setColumnWidth", "setRowHeight", "addSelection", "removeSelection", "clearSelection",
    "runCommand", "activateWorkbench", "setEdit", "resetEdit", "setActiveObject", "setCamera", "SetBool", "SetInt", "SetFloat", "SetString",
    "SetUnsigned", "RemBool", "RemInt", "RemFloat", "RemString", "RemGroup", "explodeCompound", "makeCompoundFilter",
)
# Classes whose making is a write: the mute the hub puts on while it holds a
# command's selection (agentlink/cowork.py hold).
WRITE_CLASSES = ("hooks.selection_muted",)
WRITE_CALLS = ("FreeCAD.newDocument", "FreeCAD.openDocument", "FreeCAD.closeDocument", "FreeCAD.setActiveDocument", "App.newDocument",
               "App.openDocument", "App.closeDocument", "App.setActiveDocument")


def writes(why):
    """Whether a helper's reason for not being a reader is a write to the
    document, the selection, the window or a setting (see WRITE_METHODS)."""
    what = (why or "").split(" ", 1)[-1] if ":" in (why or "").split(" ", 1)[0] else (why or "")
    if what.startswith("sets ."):
        return what[6:7].isupper()
    if what.startswith("calls .") and what.endswith("as a sketch's"):
        return True
    if what.startswith("calls ."):
        return what[7:].rstrip("()") in WRITE_METHODS
    if what.startswith("makes a "):
        return what[8:] in WRITE_CLASSES
    return what.startswith("calls ") and what[6:] in WRITE_CALLS


class Mod:
    """One source file: its functions, classes, imports and plain module-level names."""

    cache = {}

    def __init__(self, path):
        self.path = path
        with open(path, encoding="utf-8") as f:
            self.tree = ast.parse(f.read())
        self.funcs, self.classes, self.imports, self.names = {}, {}, {}, {}
        for n in self.tree.body:
            self._top(n)

    def _top(self, n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.funcs[n.name] = n
        elif isinstance(n, ast.ClassDef):
            self.classes[n.name] = n
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            self.imports.update(imports_of(n, self.path))
        elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            self.names[n.targets[0].id] = n.value
        elif isinstance(n, (ast.If, ast.Try)):
            for sub in ast.iter_child_nodes(n):
                if isinstance(sub, ast.stmt):
                    self._top(sub)
                elif isinstance(sub, ast.ExceptHandler):
                    for x in sub.body:
                        self._top(x)

    @classmethod
    def of(cls, path):
        path = os.path.normpath(path)
        if path not in cls.cache:
            cls.cache[path] = cls(path)
        return cls.cache[path]


def imports_of(n, path):
    """{local name: ("file", path) | ("module", dotted) | ("from", dotted, name) | ("fromfile", path, name)}."""
    out = {}
    here = os.path.dirname(path)
    if isinstance(n, ast.Import):
        for al in n.names:
            dotted = ALIASES_OF.get(al.name, al.name)
            out[al.asname or al.name.split(".")[0]] = ("module", dotted if al.asname else dotted.split(".")[0])
        return out
    base = here
    for _ in range(max(0, n.level - 1)):
        base = os.path.dirname(base)
    for al in n.names:
        name = al.asname or al.name
        if n.level:
            folder = os.path.join(base, *(n.module.split(".") if n.module else []))
            as_module = os.path.join(folder, al.name + ".py")
            as_name = folder + ".py"
            if os.path.isfile(as_module):
                out[name] = ("file", as_module)
            elif os.path.isfile(as_name):
                out[name] = ("fromfile", as_name, al.name)
            elif os.path.isfile(os.path.join(folder, "__init__.py")):
                out[name] = ("fromfile", os.path.join(folder, "__init__.py"), al.name)
            else:
                out[name] = ("unknown", n.module or "", al.name)
        else:
            dotted = ALIASES_OF.get(n.module, n.module)
            out[name] = ("module", dotted + "." + al.name) if (dotted + "." + al.name) in MODULES else ("from", dotted, al.name)
    return out


def module_ok(dotted, fn):
    """Whether dotted.fn is a listed function of a module outside this package."""
    spec = MODULES.get(dotted)
    if spec is None:
        return False
    if spec == "*":
        return True
    if isinstance(spec, tuple):
        return fn not in spec[1]
    return fn in spec


class Scope:
    """Where a name is looked up: the functions round the code being read
    (innermost last), then its module."""

    def __init__(self, mod, chain=(), session=()):
        self.mod, self.chain, self.session = mod, tuple(chain), tuple(session)

    def inside(self, fn):
        return Scope(self.mod, self.chain + (fn,), self.session)

    def local(self, name):
        """A name bound in the functions round here: ("def", node, scope), ("value", expr, scope), ("import", spec),
        ("param",) or None."""
        for depth in range(len(self.chain), 0, -1):
            fn = self.chain[depth - 1]
            scope = Scope(self.mod, self.chain[:depth], self.session)
            got = _bound(fn).get(name)
            if got is not None:
                return (*got, scope) if got[0] in ("def", "value") else got
        return None


_bound_cache = {}


def _own_nodes(fn):
    """fn's own statements and expressions: not those of a function or a class defined inside it."""
    todo = list(fn.body) if isinstance(fn.body, list) else [fn.body]
    while todo:
        n = todo.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                yield c  # the definition itself, not its body
            elif isinstance(c, ast.Lambda):
                yield c
            else:
                todo.append(c)


def _params(fn):
    g = fn.args
    return {x.arg for x in g.posonlyargs + g.args + g.kwonlyargs} | ({g.vararg.arg} if g.vararg else set()) | ({g.kwarg.arg} if g.kwarg else set())


def _bound(fn):
    """{name: ("def", node) | ("value", expr) | ("import", spec) | ("param",) | ("many",)} for fn's own names."""
    key = id(fn)
    if key in _bound_cache:
        return _bound_cache[key]
    out = {}

    def put(name, what):
        out[name] = ("many",) if name in out and out[name] != what else what

    for p in _params(fn):
        out[p] = ("param",)
    for n in _own_nodes(fn):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            put(n.name, ("def", n))
        elif isinstance(n, ast.ClassDef):
            put(n.name, ("many",))
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for k, spec in imports_of(n, _path_of[key] if key in _path_of else "").items():
                put(k, ("import", spec))
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    put(t.id, ("value", n.value))
                else:
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                            put(x.id, ("many",))
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            if isinstance(n.target, ast.Name):
                put(n.target.id, ("many",))
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            for x in ast.walk(n.target):
                if isinstance(x, ast.Name):
                    put(x.id, ("many",))
        elif isinstance(n, (ast.With, ast.AsyncWith)):
            for it in n.items:
                if it.optional_vars is not None:
                    for x in ast.walk(it.optional_vars):
                        if isinstance(x, ast.Name):
                            put(x.id, ("many",))
        elif isinstance(n, ast.ExceptHandler) and n.name:
            put(n.name, ("many",))
        elif isinstance(n, ast.NamedExpr):
            put(n.target.id, ("many",))
    _bound_cache[key] = out
    return out


_path_of = {}


def _fresh_expr(e, fresh):
    """Whether e makes a value of its own: a display, a comprehension, a
    listed maker's call, x.copy(), arithmetic, or a name that is fresh."""
    if isinstance(e, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.SetComp, ast.DictComp, ast.Tuple, ast.JoinedStr, ast.BinOp)):
        return True
    if isinstance(e, ast.Constant):
        return True
    if isinstance(e, ast.Name):
        return e.id in fresh
    if isinstance(e, ast.Call):
        f = e.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        return name in MAKERS or name == "copy" or (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("np", "numpy"))
    return False


def _fresh_names(fn):
    """fn's local names that only ever hold a value made here."""
    params = set()
    values = {}
    for n in ast.walk(fn):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            params |= _params(n)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    values.setdefault(t.id, []).append(n.value)
                elif isinstance(t, ast.Tuple) and isinstance(n.value, ast.Tuple) and len(t.elts) == len(n.value.elts) and all(isinstance(x, ast.Name) for x in t.elts):
                    for x, v in zip(t.elts, n.value.elts):  # out, i = [], 0
                        values.setdefault(x.id, []).append(v)
                else:
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                            values.setdefault(x.id, []).append(None)
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            for x in ast.walk(n.target):
                if isinstance(x, ast.Name):
                    values.setdefault(x.id, []).append(None)
        elif isinstance(n, (ast.With, ast.AsyncWith)):
            for it in n.items:
                for x in ast.walk(it.optional_vars) if it.optional_vars is not None else ():
                    if isinstance(x, ast.Name):
                        values.setdefault(x.id, []).append(None)
        elif isinstance(n, (ast.AnnAssign, ast.NamedExpr)) and isinstance(n.target, ast.Name):
            values.setdefault(n.target.id, []).append(n.value)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            values.setdefault(n.name, []).append(None)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            params |= set(n.names)
    fresh = set()
    changed = True
    while changed:  # a name made from fresh names is fresh
        changed = False
        for k, vs in values.items():
            if k not in fresh and k not in params and all(v is not None and _fresh_expr(v, fresh) for v in vs):
                fresh.add(k)
                changed = True
    return fresh


class Readers:
    def __init__(self):
        self.memo = {}
        self.session_mod = Mod.of(os.path.join(PKG, "tools.py"))
        self.session_cls = self.session_mod.classes["Session"]
        self.session_members = {n.name: n for n in self.session_cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.session_props = {k for k, n in self.session_members.items()
                              if any(isinstance(d, ast.Name) and d.id == "property" for d in n.decorator_list)}
        # Session's properties made by a builder (steps = _own_property("steps")): read through _own().
        self.session_built = {t.id for n in self.session_cls.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                              for t in n.targets if isinstance(t, ast.Name)}

    # ---- a function's body ----------------------------------------------------------------

    def function(self, fn, scope):
        """None when fn only reads, else why not ("file:line what")."""
        key = (scope.mod.path, fn.lineno, fn.col_offset, scope.session)
        if key in self.memo:
            return self.memo[key]
        self.memo[key] = None  # a function that calls itself: decided by the rest of it
        _path_of[id(fn)] = scope.mod.path
        trusted = TRUSTED.get((os.path.basename(scope.mod.path), getattr(fn, "name", "")))
        why = None if trusted else self._body(fn, scope.inside(fn))
        self.memo[key] = why
        return why

    def _body(self, fn, scope):
        fresh = _fresh_names(fn)
        where = f"{os.path.relpath(scope.mod.path, ROOT)}:"
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            session = tuple(p for p in _params(fn) if p in ("s", "session", "self") and (p != "self" or fn in self.session_members.values()))
            scope = Scope(scope.mod, scope.chain, tuple(set(scope.session) | set(session)))
        for n in ast.walk(fn):
            line = f"{where}{getattr(n, 'lineno', fn.lineno)}"
            if isinstance(n, (ast.Global, ast.Nonlocal)):
                return f"{line} {type(n).__name__.lower()} {', '.join(n.names)}"
            if isinstance(n, (ast.Await, ast.Yield, ast.YieldFrom)):
                continue
            if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete, ast.For, ast.AsyncFor, ast.comprehension, ast.With, ast.AsyncWith)):
                targets = (n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [it.optional_vars for it in n.items if it.optional_vars is not None]
                           if isinstance(n, (ast.With, ast.AsyncWith)) else [n.target])
                for t in targets:
                    for x in ast.walk(t):
                        if isinstance(x, ast.Attribute) and isinstance(x.ctx, (ast.Store, ast.Del)):
                            return f"{line} sets .{x.attr}"
                        if isinstance(x, ast.Subscript) and isinstance(x.ctx, (ast.Store, ast.Del)) and not _fresh_expr(x.value, fresh):
                            return f"{line} sets an item of {ast.unparse(x.value)[:40]}"
            if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and isinstance(n.value, ast.Name) and n.value.id in scope.session:
                why = self._session_read(n.attr, line)
                if why:
                    return why
            if isinstance(n, ast.Call):
                why = self.call(n, scope, fresh)
                if why:
                    return why if why[:1].isalpha() and ":" in why.split(" ")[0] else f"{line} {why}"
        return None

    def _session_read(self, attr, line):
        """Reading a property of the session runs its getter."""
        if attr in self.session_props:
            return self.function(self.session_members[attr], Scope(self.session_mod, (), ("self",)))
        if attr in self.session_built:
            return self.function(self.session_members["_own"], Scope(self.session_mod, (), ("self",)))
        return None

    # ---- one call --------------------------------------------------------------------------

    def call(self, n, scope, fresh):
        f = n.func
        if isinstance(f, ast.Name):
            if f.id == "open":
                mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
                if mode is None or (isinstance(mode, ast.Constant) and isinstance(mode.value, str) and mode.value.startswith("r") and "+" not in mode.value):
                    return None
                return "opens a file to write"
            return self.callee(f, scope)
        if isinstance(f, ast.Attribute):
            return self.method(f, scope, fresh, n.args)
        return "calls a value worked out at run time"

    def callee(self, e, scope):
        """Why calling what e names is not a reading, or None. e: a Name or a dotted Attribute."""
        if isinstance(e, ast.Lambda):
            return self.function(e, scope)
        if isinstance(e, ast.Name):
            got = scope.local(e.id)
            if got is not None:
                kind = got[0]
                if kind == "def":
                    return self.function(got[1], got[2])
                if kind == "value":
                    if isinstance(got[1], (ast.Lambda, ast.Name, ast.Attribute)):
                        return self.callee(got[1], got[2])
                    return f"calls {e.id}, a value worked out at run time"
                if kind == "import":
                    return self._imported(got[1], None, e.id)
                return f"calls {e.id}, which is given to it"
            m = scope.mod
            if e.id in m.funcs:
                return self.function(m.funcs[e.id], Scope(m))
            if e.id in m.classes:
                return None if self._is_exception(m.classes[e.id]) else f"makes a {e.id}"
            if e.id in m.imports:
                return self._imported(m.imports[e.id], None, e.id)
            if e.id in m.names:
                v = m.names[e.id]
                if isinstance(v, (ast.Lambda, ast.Name, ast.Attribute)):
                    return self.callee(v, Scope(m))
                return f"calls {e.id}, a value worked out at run time"
            if e.id in BUILTINS or e.id in EXCEPTIONS:
                return None
            return f"calls {e.id}()"
        if isinstance(e, ast.Attribute):
            parts = _dotted(e)
            if parts is None:
                return f"calls .{e.attr}() of a value"
            head, rest = parts[0], parts[1:]
            if head in scope.session and len(rest) == 1:
                return self._session_call(rest[0])
            spec = self._module_of(head, scope)
            if spec is None:
                return f"calls {'.'.join(parts)}"
            return self._imported(spec, rest, ".".join(parts))
        return "calls a value worked out at run time"

    def _module_of(self, head, scope):
        got = scope.local(head)
        if got is not None:
            return got[1] if got[0] == "import" else None
        return scope.mod.imports.get(head)

    def _session_call(self, name):
        if name in ("__dict__",):
            return None
        fn = self.session_members.get(name)
        if fn is None:
            return f"calls the session's {name}"
        return self.function(fn, Scope(self.session_mod, (), ("self",)))

    def _is_exception(self, cls):
        return any((isinstance(b, ast.Name) and (b.id in EXCEPTIONS or b.id == "ToolError")) for b in cls.bases)

    def _imported(self, spec, rest, shown):
        """A call through an import: spec with the attribute names after it (rest; None for the bare name)."""
        rest = list(rest or [])
        kind = spec[0]
        if kind == "file":
            if not rest:
                return f"calls the module {shown}"
            return self._in_file(spec[1], rest, shown)
        if kind == "fromfile":
            return self._in_file(spec[1], [spec[2], *rest], shown)
        if kind == "module":
            dotted = spec[1]
            while len(rest) > 1 and (dotted + "." + rest[0]) in MODULES:
                dotted, rest = dotted + "." + rest[0], rest[1:]
            if len(rest) == 1 and module_ok(dotted, rest[0]):
                return None
            return f"calls {shown}"
        if kind == "from":
            if not rest and module_ok(spec[1], spec[2]):
                return None
            if (spec[1] + "." + spec[2]) in MODULES and len(rest) == 1 and module_ok(spec[1] + "." + spec[2], rest[0]):
                return None
            return f"calls {shown}"
        return f"calls {shown}"

    def _in_file(self, path, names, shown):
        m = Mod.of(path)
        name = names[0]
        if name in m.imports and name not in m.funcs and name not in m.classes:
            return self._imported(m.imports[name], names[1:], shown)
        if len(names) == 1:
            if name in m.funcs:
                return self.function(m.funcs[name], Scope(m))
            if name in m.classes:
                return None if self._is_exception(m.classes[name]) else f"makes a {shown}"
            if name in m.names and isinstance(m.names[name], (ast.Lambda, ast.Name, ast.Attribute)):
                return self.callee(m.names[name], Scope(m))
            return f"calls {shown}"
        if len(names) == 2 and name in m.classes:
            fn = next((x for x in m.classes[name].body if isinstance(x, ast.FunctionDef) and x.name == names[1]), None)
            if fn is not None and any(isinstance(d, ast.Name) and d.id in ("staticmethod", "classmethod") for d in fn.decorator_list):
                return self.function(fn, Scope(m, (), ("cls",) if m is self.session_mod else ()))
        return f"calls {shown}"

    def method(self, f, scope, fresh, call_args=()):
        """x.m(…): a module's function, the session's method, or a method by its name."""
        parts = _dotted(f)
        if parts is not None:
            head = parts[0]
            if head in scope.session and len(parts) == 2:
                return self._session_call(parts[1])
            if head in ("cls", "Session") and len(parts) == 2 and scope.mod is self.session_mod:
                return self._session_call(parts[1])
            got = scope.local(head)
            is_module = (got is not None and got[0] == "import") or (got is None and head in scope.mod.imports)
            if is_module:
                return self.callee(f, scope)
        name = f.attr
        if name in BY_SHAPE and not string_call(name, call_args):
            return f"calls .{name}() as a sketch's"
        if name in READS:
            return None
        if name in FRESH and _fresh_expr(f.value, fresh):
            return None
        return f"calls .{name}()"


def _dotted(e):
    """["os", "path", "isfile"] of os.path.isfile; None when it is not names all the way."""
    parts = []
    while isinstance(e, ast.Attribute):
        parts.append(e.attr)
        e = e.value
    if not isinstance(e, ast.Name):
        return None
    return [e.id, *reversed(parts)]


# ---- the families' helpers ------------------------------------------------------------------

def helper_dicts(mod):
    """{family: {helper name: (expression, the function it is in)}} for one
    family module: the dicts handed to runners.tools(GROUP, s, <dict>,
    family=…), with what was added to them by update()."""
    out = {}
    for fn in [n for n in ast.walk(mod.tree) if isinstance(n, ast.FunctionDef)]:
        dicts = {}
        for n in _own_nodes(fn):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Dict):
                dicts.setdefault(n.targets[0].id, []).append(n.value)
        for n in sorted([x for x in _own_nodes(fn) if isinstance(x, ast.Call)], key=lambda c: (c.lineno, c.col_offset)):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == "update" and isinstance(f.value, ast.Name) and f.value.id in dicts and n.args:
                arg = n.args[0]
                dicts[f.value.id] += [arg] if isinstance(arg, ast.Dict) else dicts.get(arg.id, [None]) if isinstance(arg, ast.Name) else [None]
        for n in _own_nodes(fn):
            f = getattr(n, "func", None)
            if isinstance(n, ast.Call) and isinstance(f, ast.Attribute) and f.attr == "tools" and isinstance(f.value, ast.Name) and f.value.id == "runners":
                family = next((k.value.value for k in n.keywords if k.arg == "family" and isinstance(k.value, ast.Constant)), None)
                name = n.args[2].id if len(n.args) > 2 and isinstance(n.args[2], ast.Name) else None
                helpers = {}
                for d in dicts.get(name, [None]):
                    if d is None:
                        helpers = None  # a dict this cannot read: no reader is claimed for the family
                        break
                    for k, v in zip(d.keys, d.values):
                        if k is None or not isinstance(k, ast.Constant):
                            helpers = None
                            break
                        helpers[k.value] = (v, fn)
                    if helpers is None:
                        break
                out[family] = helpers
    return out


def families():
    """[(family: an entry's "family", else its group; the key of its helpers
    in its module — the family, or None; the module's path)] for every
    family with data tools."""
    with open(os.path.join(DATA, "tools.json"), encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    used = sorted({(e.get("family"), e["group"]) for e in entries.values() if e.get("runner")}, key=str)
    init = Mod.of(os.path.join(FAM, "__init__.py"))
    groups = {}
    for name in ast.literal_eval(init.names["NAMES"]):
        path = os.path.join(FAM, name + ".py")
        g = Mod.of(path).names.get("GROUP")
        if isinstance(g, ast.Constant):
            groups[name] = (g.value, path)
    out = []
    for family, group in used:
        if family is not None:
            out.append((family, family, groups[family][1]))
            continue
        own = [path for g, path in groups.values() if g == group and None in helper_dicts(Mod.of(path))]
        if len(own) != 1:
            raise SystemExit(f"group {group}: {len(own)} modules hand runners.tools() its entries without a family")
        out.append((group, None, own[0]))
    return out


def derive(why=None, changers=None):
    """{family: [reader names]} — and with why (a helper's name), a list of
    (family, name, why not or None) instead. changers: a dict filled with
    {family: [names]} of the helpers that are not readers because they
    write (writes())."""
    r = Readers()
    out, said = {}, []
    for family, key, path in families():
        m = Mod.of(path)
        helpers = helper_dicts(m).get(key)
        if helpers is None:
            out[family] = []
            continue
        good = []
        for name, (e, fn) in helpers.items():
            _path_of[id(fn)] = path
            scope = Scope(m, (fn,), tuple(p for p in ("s", "session") if p in _bound(fn)))
            if isinstance(e, ast.Lambda):
                w = r.function(e, scope)
            elif isinstance(e, (ast.Name, ast.Attribute)):
                w = r.callee(e, scope)
            else:
                w = "a value worked out at run time"
            if w is None:
                good.append(name)
            elif changers is not None and writes(w):
                changers.setdefault(family, []).append(name)
            if why == name:
                said.append((family, name, w))
        out[family] = sorted(good)
        if changers is not None:
            changers[family] = sorted(changers.get(family, []))
    return said if why else out


DATE = "2026-11-16"  # when the lists were last read against the code (put today's when they change)


def document(readers, changers):
    src = "scripts/tool_needs.py; the family's code"
    entries = {fam: {"readers": readers[fam], "changers": changers.get(fam, []), "source": src, "date": DATE} for fam in readers}
    entries["methods"] = {"reading": sorted(READS), "pythonOnly": sorted(PYTHON_ONLY), "byShape": sorted(BY_SHAPE), "writes": sorted(WRITE_METHODS),
                          "source": "scripts/tool_needs.py; FreeCAD 1.1 source (*PyImp.cpp)", "date": DATE}
    return {"$schema": "readers.schema.json", "dataVersion": "1.0.0", "licence": "CC-BY-4.0",
            "about": "Generated by scripts/tool_needs.py from the families' source: what a dry reading of a data tool's leading checks "
                     "(tool_groups { needs }; agentlink/needs.py) may call. Per family (an entry's family, else its group): readers, the "
                     "helpers whose code only reads, and changers, those whose code writes the document, the selection, the window or a "
                     "setting (where a tool's leading part ends). methods: the methods taken as readings by name (reading), those of "
                     "them that are Python's own and taken on a Python value only (pythonOnly), the two told from a sketch's by their "
                     "arguments (byShape), and FreeCAD's own that write (writes). Anything not listed is treated as unsafe: never "
                     "called, and what follows it not told. Do not edit: change the helper, or the script's lists, and run the script.",
            "entries": entries}


def text(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    if "--why" in argv:
        name = argv[argv.index("--why") + 1]
        for family, n, w in derive(why=name):
            print(f"{family}.{n}: {'a reader' if w is None else ('a changer — ' if writes(w) else 'not a reader — ') + w}")
        return 0
    changers = {}
    new = text(document(derive(changers=changers), changers))
    old = ""
    if os.path.isfile(OUT):
        with open(OUT, encoding="utf-8") as f:
            old = f.read()
    if "--check" in argv:
        if new != old:
            print("agentlink/data/readers.json is stale: python3 scripts/tool_needs.py")
            return 1
        return 0
    if new != old:
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(new)
    fams = [v for k, v in json.loads(new)["entries"].items() if k != "methods"]
    print(f"{sum(len(v['readers']) for v in fams)} readers and {sum(len(v['changers']) for v in fams)} changers in {len(fams)} families")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

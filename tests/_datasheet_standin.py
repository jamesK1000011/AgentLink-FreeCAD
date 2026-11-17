# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in FreeCAD of tests/test_datasheet_data.py: tests/_datapart_standin.py
# as it is, and on top of it what the spreadsheet tools (families/sheet.py) and
# the document-level tools of families/std_more.py reach: a spreadsheet that
# keeps its cells, aliases, formats and bindings and works simple formulas
# out, an enumeration property, links, a document's own calls (copy, merge,
# import links, save, revert), units, the window's freeze command, the
# OpenSCAD workbench's tree modules and GraphViz. Nothing of the first
# stand-in is changed for its own test: this one is only ever installed in
# this test's child process.
import os
import re
import types

UNITS = {"": (1.0, ""), "mm": (1.0, "Length"), "cm": (10.0, "Length"), "m": (1000.0, "Length"), "in": (25.4, "Length"), "deg": (1.0, "Angle"),
         "rad": (57.29577951308232, "Angle"), "kg": (1.0, "Mass"), "nil": (0.0, "Length")}
NUM = re.compile(r"^\s*(-?\d+(?:\.\d+)?(?:e-?\d+)?)\s*([A-Za-z]*)\s*$")
CELL = re.compile(r"\b([A-Z]{1,2}[0-9]+)\b")
WORD = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
ROW = re.compile(r"hiddenref\((\w+)\.(\w+)\) \+ (\d+)")
HIDDEN = re.compile(r"^=\s*hiddenref\(\s*(\w+)\.(\w+)\.String\s*\)\s*$")


def install():
    import sys

    import _datapart_standin

    fc = _datapart_standin.install()
    flag, log, show, trace, Obj, Vec = fc.flag, fc.log, fc.show, fc.trace, fc.Obj, fc.Vec
    Doc, Session = type(fc.Session().doc), fc.Session
    from agentlink import cells as C

    class Quantity:
        """A number with a unit: Value in FreeCAD's own unit, Unit its kind."""

        def __init__(self, text):
            m = NUM.match(str(text))
            if not m or m.group(2) not in UNITS:
                raise ValueError("syntax error")
            self.given, self.unit = float(m.group(1)), m.group(2)
            self.Value, self.Unit = self.given * UNITS[self.unit][0], UNITS[self.unit][1]

        def __str__(self):
            return f"{self.Value:g} {self.unit}"

    fc.fc.Units = types.SimpleNamespace(Quantity=Quantity)

    # ---- every object: an enumeration, expressions, a link's and a robot's calls -----------------

    first_set, first_get, first_add, first_status = Obj.__setattr__, Obj.__getattr__, Obj.addProperty, Obj.getStatusString

    def set_(self, k, v):
        enums = self.__dict__.get("enums", {})
        if k in enums:
            trace.append(f"{self.Name}.{k} = {show(v)}")
            if isinstance(v, list):
                enums[k] = list(v)
                self.__dict__[k] = v[0] if v else ""
            elif v not in enums[k] or k in flag("enum_refuses", ()):
                raise ValueError(f"'{v}' is not part of the enumeration in {self.Name}.{k}")
            else:
                self.__dict__[k] = v
            return
        first_set(self, k, v)

    def get_(self, k):
        if k == "Placement" and flag("no_placement") == self.__dict__.get("Label"):
            raise AttributeError(k)
        if k == "Document":
            return fc.state["doc"]
        if k == "OutListRecursive":
            out = []
            for o in self.OutList:
                out += [o] + o.OutListRecursive
            return out
        return first_get(self, k)

    def add_property(self, type_, name, group="", doc=""):
        first_add(self, type_, name, group, doc)
        if type_ == "App::PropertyEnumeration":
            self.__dict__.setdefault("enums", {})[name] = []
            self.__dict__[name] = ""
        return self

    def status(self):
        return "Freezed" if self.__dict__.get("frozen") else first_status(self)

    def set_expression(self, path, expr):
        log(f"{self.Name}.setExpression", path, expr)
        self.__dict__["ExpressionEngine"] = [x for x in self.__dict__.get("ExpressionEngine", []) if x[0] != path] + ([(path, expr)] if expr else [])

    def method(name, does=None):
        def run(self, *a):
            log(f"{self.Name}.{name}", *a)
            return does(self, *a) if does else None
        return run

    Obj.__setattr__, Obj.__getattr__, Obj.addProperty, Obj.getStatusString, Obj.setExpression = set_, get_, add_property, status, set_expression
    Obj.getEnumerationsOfProperty = lambda self, k: list(self.__dict__.get("enums", {}).get(k, []))
    Obj.setPropertyStatus = method("setPropertyStatus", lambda self, *a: fails("setPropertyStatus"))
    Obj.setLink = method("setLink")
    Obj.purgeTouched = method("purgeTouched", lambda self: self.__dict__.update(State=[x for x in self.__dict__.get("State", []) if x != "Touched"]))
    fc.Shape.rotate = lambda self, *a: log("rotate", self, *a)

    def fails(what):
        if what in flag("fail", ()):
            raise RuntimeError(f"{what}: FreeCAD says no")

    # ---- a spreadsheet -------------------------------------------------------------------------

    class Sheet(Obj):
        def _bound(self, a):
            """The cell a bound one shows: the active configuration's, in the same column."""
            for path, expr in self.__dict__.get("ExpressionEngine", []):
                m, row = re.match(r"^\.cells\.Bind\.([A-Z]+[0-9]+)\.([A-Z]+[0-9]+)$", path), ROW.search(expr)
                if m and row and a in C.cells_in(f"{m.group(1)}:{m.group(2)}"):
                    owner = fc.state["doc"].getObject(row.group(1))
                    at = owner.getEnumerationsOfProperty(row.group(2)).index(getattr(owner, row.group(2)))
                    return C.name(int(row.group(3)) + at, C.parse(a)[1])
            return None

        def getContents(self, a):
            return self.cells.get(a, "")

        def get(self, a, depth=0):
            a = self.alias.get(a, a) if a in self.alias else a
            if self._bound(a):
                return self.get(self._bound(a), depth + 1)
            raw = self.cells.get(a, "")
            if not raw or depth > 20:
                raise ValueError(f"Invalid cell address or property: {a}")
            if raw.startswith("'"):
                return raw[1:]
            m = HIDDEN.match(raw)
            if m:
                return str(getattr(fc.state["doc"].getObject(m.group(1)), m.group(2)))
            if raw.startswith("=<<") and raw.endswith(">>"):
                return raw[3:-2]
            body = raw[1:] if raw.startswith("=") else raw
            n = NUM.match(body)
            if n and n.group(2) in UNITS:
                return Quantity(body) if n.group(2) else (float(n.group(1)) if "." in n.group(1) else int(n.group(1)))
            if not raw.startswith("="):
                return raw
            try:
                def at(mm):
                    v = self.get(mm.group(1), depth + 1)
                    return repr(v.Value if isinstance(v, Quantity) else v)

                def far(mm):
                    o = fc.state["doc"].getObject(mm.group(1))
                    return at_of(o, mm.group(2)) if isinstance(o, Sheet) else mm.group(0)

                def at_of(o, name):
                    v = o.get(name, depth + 1)
                    return repr(v.Value if isinstance(v, Quantity) else v)

                body = re.sub(r"\b([A-Za-z]\w*)\.(\w+)\b", far, body)
                text = WORD.sub(lambda mm: at(mm) if mm.group(1) in self.alias or CELL.match(mm.group(1)) else mm.group(1), body)
                return eval(text, {"__builtins__": {}})  # noqa: S307 - the stand-in's own arithmetic
            except Exception as e:  # noqa: BLE001
                return f"ERR: {e}"

        def set(self, a, body):
            log(f"{self.Name}.set", a, body)
            if not C.ADDR.match(a) if hasattr(C, "ADDR") else False:
                raise ValueError("Invalid cell specifier.")
            self.cells[a] = ("'" + body) if body.startswith("=") and "((" in body else body

        def clear(self, a):
            log(f"{self.Name}.clear", a)
            self.cells.pop(a, None)
            for k in [k for k, v in self.alias.items() if v == a]:
                del self.alias[k]
            self.look.pop(a, None)

        def clearAll(self):
            log(f"{self.Name}.clearAll")
            self.cells.clear(), self.alias.clear(), self.look.clear()

        def getNonEmptyCells(self):
            if flag("no_used_cells"):
                raise RuntimeError("not here")
            return list(self.cells)

        def getAlias(self, a):
            return next((k for k, v in self.alias.items() if v == a), None)

        def getCellFromAlias(self, al):
            return self.alias.get(al)

        def setAlias(self, a, al):
            log(f"{self.Name}.setAlias", a, al)
            if al in flag("alias_refused", ()):
                raise ValueError("Invalid alias")
            for k in [k for k, v in self.alias.items() if v == a]:
                del self.alias[k]
            if al:
                self.alias[al] = a

        def _looks(self, a, key, default=None):
            return self.look.get(a, {}).get(key, default)

        def _look(self, a, key, v):
            log(f"{self.Name}.{key}", a, v)
            self.look.setdefault(a, {})[key] = v

        getStyle = lambda self, a: set(filter(None, (self._looks(a, "setStyle") or "").split("|")))  # noqa: E731
        getAlignment = lambda self, a: set(filter(None, (self._looks(a, "setAlignment") or "").split("|")))  # noqa: E731
        getForeground = lambda self, a: self._looks(a, "setForeground")  # noqa: E731
        getBackground = lambda self, a: self._looks(a, "setBackground")  # noqa: E731
        getDisplayUnit = lambda self, a: self._looks(a, "setDisplayUnit") or None  # noqa: E731
        setStyle = lambda self, a, v, how: self._look(a, "setStyle", v)  # noqa: E731
        setAlignment = lambda self, a, v, how: self._look(a, "setAlignment", v)  # noqa: E731
        setForeground = lambda self, a, v: self._look(a, "setForeground", v)  # noqa: E731
        setBackground = lambda self, a, v: self._look(a, "setBackground", v)  # noqa: E731

        def setDisplayUnit(self, a, u):
            if u and u not in UNITS:
                raise ValueError(f"Unknown unit {u}")
            self._look(a, "setDisplayUnit", u)

        def clearBackground(self, a):
            self._look(a, "setBackground", None)

        def __getattr__(self, k):
            if k == "clearForeground" and not flag("old_sheet"):
                return lambda a: self._look(a, "setForeground", None)
            return get_(self, k)

        setColumnWidth = method("setColumnWidth")
        setRowHeight = method("setRowHeight")
        splitCell = method("splitCell")

        def mergeCells(self, rng):
            log(f"{self.Name}.mergeCells", rng)
            for a in C.cells_in(rng)[1:]:
                self.cells.pop(a, None)
                for k in [k for k, v in self.alias.items() if v == a]:
                    del self.alias[k]

        def _shift(self, at_row, at_col, drow, dcol):
            def moved(a):
                r, c = C.parse(a)
                if r < at_row or c < at_col:
                    return a
                if (drow < 0 and r < at_row - drow) or (dcol < 0 and c < at_col - dcol):
                    return None
                return C.name(r + drow, c + dcol)

            self.__dict__["cells"] = {moved(a): v for a, v in self.cells.items() if moved(a)}
            self.__dict__["alias"] = {k: moved(a) for k, a in self.alias.items() if moved(a)}

        def insertRows(self, r, n):
            log(f"{self.Name}.insertRows", r, n)
            self._shift(int(r), 1, n, 0)

        def removeRows(self, r, n):
            log(f"{self.Name}.removeRows", r, n)
            self._shift(int(r), 1, -n, 0)

        def insertColumns(self, c, n):
            log(f"{self.Name}.insertColumns", c, n)
            self._shift(1, C.parse(c + "1")[1], 0, n)

        def removeColumns(self, c, n):
            log(f"{self.Name}.removeColumns", c, n)
            self._shift(1, C.parse(c + "1")[1], 0, -n)

        def importFile(self, p, d, quote, esc):
            log(f"{self.Name}.importFile", os.path.basename(p), d, quote, esc)
            if flag("import_fails"):
                return False
            with open(p, encoding="utf-8") as f:
                for r, line in enumerate(f.read().splitlines(), 1):
                    for c, v in enumerate(line.split(d), 1):
                        if v:
                            self.cells[C.name(r, c)] = v
            return None

        def exportFile(self, p, d, quote, esc):
            log(f"{self.Name}.exportFile", os.path.basename(p), d, quote, esc)
            if flag("export_fails"):
                return False
            if flag("export_writes_nothing"):
                return None
            rows = {}
            for a in self.cells:
                r, c = C.parse(a)
                rows.setdefault(r, {})[c] = str(self.get(a))
            with open(p, "w", encoding="utf-8") as f:
                for r in range(1, max(rows, default=0) + 1):
                    f.write(d.join(rows.get(r, {}).get(c, "") for c in range(1, max(rows.get(r, {0: 0})) + 1)) + "\n")
            return None

    def sheet(label, cells=None, alias=None):
        """A case's furniture: a spreadsheet under a label."""
        ss = fc.state["doc"].new("Spreadsheet::Sheet", "Spreadsheet")
        object.__setattr__(ss, "__class__", Sheet)
        ss.__dict__.update(Label=label, cells=dict(cells or {}), alias=dict(alias or {}), look={})
        return ss

    # ---- the document --------------------------------------------------------------------------

    first_doc_add = Doc.addObject

    def add_object(self, type_, name):
        o = first_doc_add(self, type_, name)
        if type_ == "Spreadsheet::Sheet":
            object.__setattr__(o, "__class__", Sheet)
            o.__dict__.update(cells={}, alias={}, look={})
        if type_ == "App::TextDocument":
            o.__dict__["Text"] = ""
        if type_ == "App::Link":
            o.__dict__.update(ElementList=[], LinkedObject=None)
        return o

    def copy_object(self, o, deps=False):
        log("copyObject", o, deps)
        c = self.new(o.TypeId, o.Name)
        c.__dict__.update({k: v for k, v in o.__dict__.items() if k not in ("Name", "InList")}, InList=[])
        return c

    def import_links(self, links):
        log("importLinks", links)
        return [self.new("Part::Feature", "Imported") for _ in links] if not flag("import_gives_none") else None

    def merge_project(self, p):
        log("mergeProject", os.path.basename(p))
        fails("mergeProject")
        for name in flag("merge_brings", ["Bracket", "AgentLinkRecords001"]):
            self.new("Part::Feature", name)

    def doc_method(name):
        return lambda self, *a: log(name, *a)

    Doc.addObject, Doc.copyObject, Doc.importLinks, Doc.mergeProject = add_object, copy_object, import_links, merge_project
    Doc.abortTransaction, Doc.save = doc_method("abortTransaction"), doc_method("save")
    for k in ("FileName", "CreatedBy", "Company", "Comment", "License", "LicenseURL", "LastModifiedBy", "Id", "Uid", "CreationDate", "LastModifiedDate"):
        setattr(Doc, k, "")
    Doc.Uid, Doc.CreationDate = "uid-1", "2026-11-16T10:00:00Z"
    Session.switch = lambda self, nd: (log("switch", nd.Name), setattr(self, "doc", nd), fc.state.update(doc=nd))[0]

    def open_document(path):
        log("openDocument", os.path.basename(path))
        nd = Doc()
        nd.Name, nd.Label, nd.FileName = "Reopened", "Reopened", path
        nd.new("Part::Feature", "Saved")
        return nd

    fc.fc.closeDocument = lambda name: log("closeDocument", name)
    fc.fc.openDocument = open_document
    fc.fc.listDocuments = lambda: dict(fc.state.get("docs") or {fc.state["doc"].Name: fc.state["doc"]})

    from agentlink.families import doc as doc_family

    doc_family.saved = lambda d: log("saved", d.Name)

    # ---- placements from a matrix; a shape as Part reads it --------------------------------------

    First = fc.fc.Placement

    First.isNull = lambda self: self.Base == Vec() and not self.Rotation.a

    class Placement(First):
        def __init__(self, base=None, rot=None, centre=None):
            if isinstance(base, fc.fc.Matrix):
                m = base.ops[0][1:]
                base, rot = Vec(m[3], m[7], m[11]), fc.fc.Rotation(Vec(0, 0, 1), round(m[0], 6))
            First.__init__(self, base, rot, centre)

    fc.fc.Placement = Placement
    fc.part.getShape = lambda o: (log("getShape", o), o.Shape)[1]

    # ---- the window, the OpenSCAD workbench's modules, GraphViz ------------------------------------

    picked = []

    def run_command(name, n):
        log("runCommand", name, n)
        for o in picked:
            if o.Label not in flag("will_not_freeze", ()):
                o.__dict__["frozen"] = not o.__dict__.get("frozen")

    gui = fc.Module("FreeCADGui")
    gui.Selection = types.SimpleNamespace(clearSelection=lambda: (log("clearSelection"), picked.clear())[0], addSelection=lambda o: (log("addSelection", o), picked.append(o))[0])
    gui.runCommand = run_command

    def module(name, **fns):
        m = fc.Module(name)
        for k, does in fns.items():
            setattr(m, k, (lambda k, does: lambda *a: (log(f"{name}.{k}", *a), does(*a))[1])(k, does))
        return m

    def increase(n, o):
        n.__dict__.update(Vertex=0.0, Edge=0.0, Face=0.0)

    def remove_subtree(objs):
        for o in objs:
            fc.state["doc"].removeObject(o.Name)

    sys.modules.update({"FreeCADGui": gui, "expandplacements": module("expandplacements", expandplacements=lambda o, pl: None),
                        "OpenSCADFeatures": module("OpenSCADFeatures", IncreaseTolerance=increase),
                        "OpenSCADUtils": module("OpenSCADUtils", removesubtree=remove_subtree), "replaceobj": module("replaceobj", replaceobj=lambda p, o, n: None)})

    import shutil
    import subprocess

    real_run = subprocess.run

    def run(cmd, *a, **kw):
        if cmd and cmd[0] == "dot-here":
            log("dot", *[os.path.basename(x) for x in cmd[1:]])
            return types.SimpleNamespace(returncode=flag("dot_returns", 0), stderr=b"Error: syntax error in line 1")
        return real_run(cmd, *a, **kw)

    shutil.which = lambda name: flag("dot")
    subprocess.run = run

    fc.sheet, fc.Sheet, fc.Quantity = sheet, Sheet, Quantity
    return fc

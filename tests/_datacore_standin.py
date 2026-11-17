# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in FreeCAD of tests/test_datacore_data.py: tests/_datapart2_standin.py
# as it is (itself on tests/_datapart_standin.py), and on top of it what the
# hub's own core tools reach (families/view.py, dev.py, unattended.py, doc.py):
# several open documents with a file, a label and a changed mark; a window with
# a 3D view that saves pictures and a dialog or task panel in front; the
# heavy-job queue, the test runner and the crash collector as stubs that write
# down what they were asked; objects with typed properties; and files read and
# written as Part, Mesh and MeshPart would. Nothing of the stand-ins under it
# is changed for their own tests: this one is only ever installed in this
# test's child process.
import os
import struct
import sys
import types


def png(path, w, h):
    """A file with a PNG's header saying w x h."""
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", int(w), int(h)) + b"\x08\x02\x00\x00\x00")


def install():
    import _datapart2_standin

    fc = _datapart2_standin.install()
    flag, log, show, trace, Shape, Obj, state = fc.flag, fc.log, fc.show, fc.trace, fc.Shape, fc.Obj, fc.state
    F = fc.fc
    BaseDoc = type(fc.Session().doc)
    BaseSession = fc.Session

    def fails(what):
        if what in flag("fail", ()):
            raise RuntimeError(f"{what}: it failed here")

    def short(p):
        return str(p).replace("\\", "/").rsplit("/", 1)[-1]

    # ---- documents -------------------------------------------------------------------------------

    class Doc(BaseDoc):
        def __init__(self, name="Model", label=None, file=""):
            BaseDoc.__init__(self)
            self.Name, self.Label, self.FileName = name, label or name, file
            self.changed, self.touched, self.UndoNames, self.RecomputesFrozen = False, [], [], False

        def isTouched(self):
            return bool(self.touched)

        def purgeTouched(self):
            log("purgeTouched", self.Name)

        def save(self):
            log("save", self.Name)
            with open(self.FileName, "w") as f:
                f.write("saved")
            self.changed = False

        def saveAs(self, p):
            log("saveAs", self.Name, short(p))
            with open(p, "w") as f:
                f.write("saved as")
            self.FileName, self.changed = p, False
            if flag("relabel", True):
                self.Label = os.path.splitext(os.path.basename(p))[0]

        def recompute(self, objs=None, force=None):
            if force is not None and flag("old_recompute"):
                raise TypeError("recompute() takes at most 1 argument")
            trace.append(f"{self.Name}.recompute({'' if objs is None and force is None else show(objs) + ('' if force is None else ', ' + show(force))})")
            BaseDoc.recompute(self)
            del trace[-1]  # the first stand-in's own line: this one says which document
            return flag("recomputed", len(self.Objects))

    def docs():
        return state.setdefault("docs", {})

    def new_document(name):
        n, i = name, 0
        while n in docs():
            i += 1
            n = f"{name}{i}"
        log("newDocument", n)
        docs()[n] = Doc(n)
        return docs()[n]

    def open_document(p):
        log("openDocument", short(p))
        fails("openDocument")
        d = new_document(os.path.splitext(os.path.basename(p))[0])
        del trace[-1]
        d.FileName = p
        return d

    def close_document(name):
        log("closeDocument", name)
        docs().pop(name, None)

    def param(path):
        files = flag("recent", [])
        return types.SimpleNamespace(GetBool=lambda *a: False, GetInt=lambda k, d=0: len(files), GetFloat=lambda *a: 0.0,
                                     GetString=lambda k, d="": files[int(k[3:])] if k.startswith("MRU") and int(k[3:]) < len(files) else d)

    F.listDocuments, F.newDocument, F.openDocument, F.closeDocument, F.ParamGet = (lambda: dict(docs())), new_document, open_document, close_document, param
    F.setActiveDocument = lambda name: log("setActiveDocument", name)
    F.getUserAppDataDir = lambda: state["home"]
    F.getHomePath = lambda: state["home"]

    def bound_box(b=None):
        if b is None or not hasattr(b, "lo"):
            raise TypeError("a box")
        nb = type(b)(b.lo, b.hi)
        return nb

    F.BoundBox = bound_box
    F.Placement.isIdentity = lambda self: not flag("moved")

    # ---- the session -----------------------------------------------------------------------------

    class Session(BaseSession):
        CONTAINERS = ("App::Part", "App::DocumentObjectGroup")

        def __init__(self, out_dir="/tmp"):
            BaseSession.__init__(self, out_dir)
            state["docs"] = {}
            state["home"] = out_dir
            self.doc = docs()["Model"] = Doc("Model")
            state["doc"] = self.doc
            self.meta = {}

        def __setattr__(self, k, v):
            if k == "doc":
                state["doc"] = v
            object.__setattr__(self, k, v)

        def bodies(self):
            return [o for o in self.doc.Objects if getattr(o, "Shape", None) is not None and not o.Shape.isNull() and o.Shape.Solids and o.Visibility]

        def hidden_in(self, doc):
            return [o for o in doc.Objects if getattr(o, "Shape", None) is not None and not o.Visibility]

        def helper(self, o):
            return False

        def switch(self, doc):
            log("session.switch", doc.Name)
            self.doc, self.steps, self.meta = doc, [], {}

    # ---- objects with properties -----------------------------------------------------------------

    def type_of(self, p):
        return self.__dict__.get("types", {}).get(p, "App::PropertyString" if isinstance(getattr(self, p), str) else "App::PropertyFloat")

    def set_checked(self, k, v):
        if k in self.__dict__.get("refuses", ()):
            raise ValueError(f"{k}: out of range")
        if k in self.__dict__.get("breaks", ()):  # set, it breaks the object at its next recompute
            self.__dict__["State"] = ["Invalid"]
        if k == "Label" and self.__dict__.get("relabels"):  # FreeCAD keeping labels apart
            v = v + "001"
        first_set(self, k, v)

    first_set = Obj.__setattr__
    Obj.__setattr__ = set_checked
    Obj.getTypeIdOfProperty = type_of
    Obj.getGroupOfProperty = lambda self, p: self.__dict__.get("groups", {}).get(p, "Base")
    Obj.getEditorMode = lambda self, p: list(self.__dict__.get("modes", {}).get(p, []))
    Obj.getPropertyStatus = lambda self, p: list(self.__dict__.get("status", {}).get(p, []))
    Obj.getEnumerationsOfProperty = lambda self, p: list(self.__dict__.get("choices", {}).get(p, []))
    Obj.touch = lambda self: log("touch", self)
    Obj.setLink = lambda self, o: (log("setLink", self, o), self.__dict__.update(LinkedObject=o))[0]
    Obj.getLinkedObject = lambda self, recursive=True: self.__dict__.get("LinkedObject")
    Obj.Document = property(lambda self: state["doc"])

    first_add = Doc.addObject

    def add_object(self, type_, name):
        o = first_add(self, type_, name)
        if type_ in ("App::Part",):
            o.__dict__.update(Group=[])
        if type_ == "Image::ImagePlane" and flag("no_image_planes"):
            raise RuntimeError("No document object type 'Image::ImagePlane'")
        return o

    Doc.addObject = add_object

    # ---- shapes and meshes read and written -------------------------------------------------------

    def shape_read(self, p):
        log("Shape.read", short(p))
        fails("Shape.read")
        n = flag("file_solids", 1)
        self.__dict__.update(Shape(f"read {short(p)}", "Solid" if n == 1 else "Compound", (0, 0, 0), (10, 10, 10), volume=flag("file_volume", 1000.0), area=600.0,
                                   faces=6 * max(n, 1) if flag("file_faces", True) else 0, edges=12, solids=n).__dict__)

    def exporter(kind):
        def export(self, p):
            log(f"export{kind}", self, short(p))
            with open(p, "w") as f:
                f.write(kind)

        return export

    Shape.read, Shape.exportStep, Shape.exportIges, Shape.exportBrep = shape_read, exporter("Step"), exporter("Iges"), exporter("Brep")
    Shape.reverse = lambda self: log("reverse", self)

    def box_size(self):
        return self.box

    Shape.BoundBox = property(box_size)
    first_points = Shape.discretize

    def discretize(self, Number=10, Deflection=None):
        if Deflection is not None and len(self.pts) < 2 and self.box.isValid():  # an edge of a wire: its box's corners
            return [fc.Vec(*self.box.lo), fc.Vec(*self.box.hi)]
        return first_points(self, 3 if Deflection is not None else Number)

    Shape.discretize = discretize

    # TechDraw's projection: ten groups of edges, the hard visible ones and the hard hidden ones filled.
    techdraw = fc.Module("TechDraw")

    def project_ex(sh, d):
        log("projectEx", sh, d)
        none = Shape("no edges", "Compound", null=True, solids=0)
        seen = fc.wire("seen", [(0, 0, 0), (10, 0, 0), (10, 10, 0)], closed=False)
        hid = fc.wire("hidden", [(0, 0, 0), (0, 10, 0), (5, 5, 0)], closed=False)
        return [seen if flag("projected", True) else none, none, none, none, none, hid, none, none, none, none]

    techdraw.projectEx = project_ex
    sys.modules["TechDraw"] = techdraw
    fc.mods["TechDraw"] = techdraw

    MeshData = fc.MeshData
    first_mesh = MeshData.__init__

    def mesh_init(self, path=None, facets=None):
        if isinstance(path, tuple):  # a Topology
            log("Mesh", "from a topology")
            first_mesh(self, None, len(path[1]))
        else:
            first_mesh(self, path, facets if facets is not None or path is not None else 0)
        self.Volume, self.solid = flag("mesh_volume", 1000.0), flag("mesh_closed", True)
        self.Topology = ([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 5.0)], [(0, 1, 2)] * self.CountFacets)

    def mesh_add(self, facets):
        log("addFacets", len(facets))
        self.CountFacets = len(facets)
        self.Topology = ([], [(0, 1, 2)] * self.CountFacets)

    def mesh_merge(self, other):
        log("addMesh", other.CountFacets)
        self.CountFacets += other.CountFacets
        self.Topology = ([], [(0, 1, 2)] * self.CountFacets)

    def mesh_write(self, p):
        log("Mesh.write", short(p), self.CountFacets)
        with open(p, "w") as f:
            f.write("mesh")

    def mesh_copy(self):
        log("Mesh.copy")
        return MeshData(None, self.CountFacets)

    MeshData.__init__, MeshData.addFacets, MeshData.addMesh, MeshData.write, MeshData.copy = mesh_init, mesh_add, mesh_merge, mesh_write, mesh_copy
    MeshData.isSolid = lambda self: self.solid
    MeshData.__repr__ = lambda self: f"<mesh of {self.CountFacets}>"

    meshpart = fc.Module("MeshPart")

    def mesh_from_shape(Shape=None, LinearDeflection=0.0, AngularDeflection=0.0, Relative=False):
        log("meshFromShape", Shape, LinearDeflection, AngularDeflection, Relative)
        m = MeshData(None, 12)
        m.Topology = ([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 5.0)], [(0, 1, 2)] * 12)
        return m

    meshpart.meshFromShape = mesh_from_shape

    def inserter(name):
        m = fc.Module(name)

        def insert(p, docname):
            log(f"{name}.insert", short(p), docname)
            fails(f"{name}.insert")
            for i in range(flag("inserted", 1)):
                o = state["doc"].new("Part::Feature", "Path", Shape=fc.wire(f"{name} {i + 1}", [(0, 0, 0), (10, 0, 0), (10, 10, 0)]))
                o.__dict__["Label"] = f"Path {i + 1}"

        m.insert = insert
        return m

    mods = {"MeshPart": meshpart, "importSVG": inserter("importSVG"), "JtReader": inserter("JtReader"), "Import": inserter("Import")}
    sys.modules.update(mods)
    fc.mods.update(mods)

    # ---- the window ------------------------------------------------------------------------------

    class View3D:
        def __init__(self):
            self.cam = "the person's camera"

        def __getattr__(self, k):
            if k.startswith("view"):
                return lambda: log(k)
            raise AttributeError(k)

        def fitAll(self):
            log("fitAll")

        def getCamera(self):
            if flag("no_camera"):
                raise RuntimeError("no camera")
            return self.cam

        def setCamera(self, cam):
            log("setCamera", cam)

        def saveImage(self, p, w, h, bg):
            log("saveImage", short(p), w, h, bg)
            fails("saveImage")
            sw, sh = flag("saved_size", (w, h))
            png(p, sw, sh)

        def getSize(self):
            return (800, 600)

        def getPointOnViewport(self, v):
            return (400 + 10 * v.x + v.z, 300 + 10 * v.y + v.z)

    class GuiDoc:
        Modified = False

        def activeView(self):
            if flag("no_view"):
                return None
            return object() if flag("odd_view") else View3D()

    gui = fc.Module("FreeCADGui")
    gui.getDocument = lambda name: None if flag("no_gui_doc") else GuiDoc()
    gui.setActiveDocument = lambda name: log("Gui.setActiveDocument", name)

    def main_window():
        raise RuntimeError("no main window here")

    gui.getMainWindow = main_window
    sys.modules["FreeCADGui"] = gui
    fc.mods["FreeCADGui"] = gui

    # ---- Agent Link's own modules the tools lean on, as stubs that write down what they are asked ----

    link = types.ModuleType("agentlink.gui_link")
    link.BACK_OUT = ("cancel", "close", "escape")
    link.modal_info = lambda: (log("modal_info"), flag("dialog"))[1]
    link.task_info = lambda: (log("task_info"), flag("task"))[1]

    def press(d, btn):
        log("press", d["title"], btn)
        return not flag("press_fails")

    def press_task(d, btn):
        log("press_task", d["title"], btn)
        return btn in d["buttons"]

    def fill(d, text=None, item=None):
        log("fill", d["title"], text, item)
        if flag("fill_fails"):
            raise ValueError("item: one of Top, Front — not that.")
        return {k: v for k, v in (("text", text), ("item", item)) if v is not None}

    link.press, link.press_task, link.fill = press, press_task, fill
    link.unstick = lambda all_=False, wait=3.0: (log("unstick", all_), {"closed": flag("closed", []), "open": None})[1]
    sys.modules["agentlink.gui_link"] = link
    import agentlink

    agentlink.gui_link = link

    from agentlink import crash_logs, keep, store, testrun

    crash_logs.collect = lambda: (log("crash_logs.collect"), flag("crash", None))[1]
    keep.log_watchdog = lambda row: log("log_watchdog", row)
    keep.queue_state = lambda: (log("queue_state"), dict(flag("queue", {})))[1]
    keep.save_queue = lambda q: log("save_queue", q)
    keep.preset = lambda: {"heavySlots": 2, "memoryCeilingGB": 12, "fan": "quiet", "other": 1}
    keep.path = lambda *parts: (log("keep.path", *parts), "/".join(("<keep>",) + parts))[1]
    keep.stamp = lambda: "20261116-120000"

    def root_for(addon, mod, own_root, installed):
        from agentlink.protocol import ToolError

        log("root_for", addon, short(mod), sorted(installed) if installed else installed)
        if addon == "Nope":
            raise ToolError("not_found", "addon Nope: not an installed add-on.")
        return f"<mod>/{addon}"

    def find_cmd(exe=None, env=None, home=None, **kw):
        log("find_cmd", "FreeCAD's home" if home == state["home"] else home)
        return (None, None) if flag("no_cmd") else ("<bin>/freecadcmd", "<lib>")

    def start(cmd, addon, root, own_root, roots, lib, log_, pattern="test_*.py", select=None, timeout=None, folder=None):
        log("testrun.start", cmd, addon, root, [short(r) for r in roots], lib, log_, pattern, select, timeout, folder)
        return {"job": "t1", "addon": addon}

    def find(job):
        from agentlink.protocol import ToolError

        if job != "t1":
            raise ToolError("not_found", f"job {job!r}: no such test job.")
        return {"job": "t1", "addon": "Workshop"}

    testrun.root_for, testrun.find_cmd, testrun.start, testrun.find = root_for, find_cmd, start, find
    testrun.wait = lambda j, seconds, pump=None: (log("testrun.wait", j, seconds, pump is not None), {**j, "state": "running"})[1]
    testrun.listing = lambda: (log("testrun.listing"), {"jobs": []})[1]

    store.undo_on = lambda d: log("undo_on", d.Name)
    store.is_changed = lambda d: bool(d.changed)
    store._unchanged = lambda d: log("unchanged", d.Name)
    store.note_saved = lambda d: log("note_saved", d.Name)
    store.touched_since_save = lambda d: list(d.touched)
    store.touched_names = lambda d: list(d.touched)

    from agentlink import geometry as geo

    geo.box_of = lambda sh: {"size": [round(sh.box.XLength, 3), round(sh.box.YLength, 3), round(sh.box.ZLength, 3)]}
    geo.clean = lambda sh: (log("clean", sh), sh)[1]

    fc.Session, fc.Doc, fc.docs, fc.View3D, fc.link, fc.gui, fc.png = Session, Doc, docs, View3D, link, gui, png
    return fc

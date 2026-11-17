# SPDX-License-Identifier: LGPL-2.1-or-later
# A stand-in CAM workbench for tests/test_datacam_data.py, on top of
# tests/_datamesh_standin.py's FreeCAD: jobs with a stock, a model and tool
# controllers, operations with a few moves, dressups, tool bits and
# post-processors, as far as the cam_ tools reach. Not FreeCAD's CAM: an
# operation's path is a fixed handful of moves bent by the case's flags, so
# that the old handlers and the new data entries can be compared step for
# step. Only installed in a child process.
import importlib
import os
import re
import sys
import types


def install():
    import _datamesh_standin

    fc = _datamesh_standin.install()
    trace, state, flag, Obj, Vec, Box, log = fc.trace, fc.state, fc.flag, fc.Obj, fc.Vec, fc.Box, fc.log
    F = fc.fc

    def doc():
        return state["doc"]

    # ---- quantities, shapes ----------------------------------------------------------------------

    class Quantity:
        def __init__(self, v=0.0):
            if isinstance(v, Quantity):
                v = v.Value
            if isinstance(v, str):
                v = re.match(r"\s*(-?\d+(\.\d+)?)", v)[1]
            self.Value = float(v)

        def getValueAs(self, unit):
            return self.Value

    F.Units = types.SimpleNamespace(Quantity=Quantity)
    F.setActiveDocument = lambda name: None
    F.getResourceDir = lambda: flag("resource", os.path.join(os.sep, "nowhere", ""))
    F.getHomePath = lambda: os.path.join(os.sep, "nowhere", "")

    class BoxShape:
        """A box: its corners, twelve triangles, six faces by name."""

        def __init__(self, lo, hi, faces=6, edges=12):
            self.lo, self.hi = tuple(lo), tuple(hi)
            self.Faces, self.Edges, self.Solids = [self] * faces, [self] * edges, [self]

        def __repr__(self):
            return f"<box {self.lo} {self.hi}>"

        tag = __repr__

        @property
        def BoundBox(self):
            return Box([self.lo, self.hi])

        def isNull(self):
            return False

        def tessellate(self, tol):
            (a, b, c), (d, e, f) = self.lo, self.hi
            pts = [Vec(x, y, z) for z in (c, f) for x, y in ((a, b), (d, b), (d, e), (a, e))]
            return pts, [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]

    class Face:
        def __init__(self, far):
            self.far = far

        def distToShape(self, other):
            return (self.far,)

    # ---- document objects ------------------------------------------------------------------------

    class CamObj(Obj):
        """An object whose enumerations and whole-number properties refuse
        what FreeCAD's would."""

        def __repr__(self):
            return f"<{self.Name}>"

        def __setattr__(self, k, v):
            d = self.__dict__
            if k in d.get("enums", {}) and v not in d["enums"][k]:
                raise ValueError(f"'{v}' is not part of the enumeration")
            if k in d.get("ints", ()) and isinstance(v, float):
                raise TypeError("type must be int")
            if k in d.get("locked", ()):
                raise ValueError(f"{k} is read-only")
            Obj.__setattr__(self, k, v)

        def setExpression(self, prop, e):
            trace.append(f"{self.Name}.setExpression({prop!r}, {e!r})")

        def getTypeIdOfProperty(self, prop):
            return "App::PropertyLength"

        def purgeTouched(self):
            trace.append(f"{self.Name}.purgeTouched()")

    class StockObj(CamObj):
        @property
        def Shape(self):
            d = self.__dict__
            if "fixed" in d:
                return BoxShape(*d["fixed"])
            (a, b, c), (x, y, z) = d["around"]
            g = lambda k: float(d.get(k, 0.0))  # noqa: E731
            return BoxShape((a - g("ExtXneg"), b - g("ExtYneg"), c - g("ExtZneg")), (x + g("ExtXpos"), y + g("ExtYpos"), z + g("ExtZpos")))

    state.setdefault("classes", {})["Path::FeaturePython"] = CamObj
    state["classes"]["Part::FeaturePython"] = CamObj
    state["classes"]["Stock"] = StockObj

    def copy_object(self, o, deep=False):
        c = self.new(o.TypeId, o.Name)
        c.__dict__.update({k: v for k, v in o.__dict__.items() if k != "Name"})
        c.__dict__["Label"] = o.Label + "001"
        trace.append(f"copyObject(<{o.Name}>) -> <{c.Name}>")
        job = job_of(o)
        if job is not None and flag("copy_listed"):
            job.Operations.Group.append(c)
        return c

    fc.Doc.copyObject = copy_object

    class Grp:
        def __init__(self, name, group=()):
            self.__dict__.update(name=name, Group=list(group))

        def __repr__(self):
            return f"<{self.name}>"

        def __setattr__(self, k, v):
            trace.append(f"{self.name}.{k} = {fc.show(v)}")
            self.__dict__[k] = list(v)

        def addObject(self, o):
            trace.append(f"{self.name}.addObject(<{o.Name}>)")
            self.Group.append(o)

        def removeObject(self, o):
            trace.append(f"{self.name}.removeObject(<{o.Name}>)")
            self.__dict__["Group"] = [x for x in self.Group if x is not o]

    class Cmd:
        def __init__(self, name, **p):
            self.Name, self.Parameters = name, p

        def toGCode(self):
            return " ".join([self.Name] + [f"{k}{v:g}" for k, v in self.Parameters.items()])

    def path_of(kind):
        how = flag("path")
        if how == "none":
            return None
        z = -30.0 if how == "deep" else 10.0
        cmds = [Cmd("G0", Z=25.0), Cmd("G0", X=0.0, Y=0.0)]
        if how == "empty" or (kind == "custom" and how is None):
            cmds = []
        elif how == "rapids":
            pass
        elif how == "crash":  # a rapid through the stock
            cmds += [Cmd("G0", Z=5.0), Cmd("G0", X=30.0, Y=0.0), Cmd("G1", Z=4.0), Cmd("G1", X=35.0, Y=0.0), Cmd("G0", Z=25.0)]
        elif kind == "probe":
            cmds += [Cmd("G38.2", Z=0.0), Cmd("G0", Z=25.0)]
        elif kind in ("drill", "tapping"):
            cmds += [Cmd("G98"), Cmd("G81", X=7.0, Y=7.0, Z=z - 10.0, R=22.0), Cmd("G80")]
        else:
            cmds += [Cmd("G1", Z=z), Cmd("G1", X=10.0, Y=0.0), Cmd("G2", X=10.0, Y=10.0, I=0.0, J=5.0), Cmd("G1", X=0.0, Y=10.0), Cmd("G0", Z=25.0)]
        return types.SimpleNamespace(Commands=cmds)

    def job_of(o):
        return next((j for j in doc().Objects if hasattr(j, "Operations") and o in j.Operations.Group), None)

    # ---- the job and its tools ---------------------------------------------------------------------

    class JobProxy:
        def __init__(self, job):
            self.job = job

        def __repr__(self):
            return "<job proxy>"

        def addToolController(self, tc):
            trace.append(f"addToolController(<{tc.Name}>)")
            self.job.Tools.Group.append(tc)

        def addOperation(self, op, before=None, *more):
            if more and flag("addop_two"):
                raise TypeError("addOperation() takes from 2 to 3 positional arguments")
            trace.append(f"addOperation(<{op.Name}>{', <' + before.Name + '>' if before is not None else ''}{', True' if more else ''})")
            g = [x for x in self.job.Operations.Group if x is not op]
            i = g.index(before) if before in g else len(g)
            g.insert(i, op)
            if more and more[0] and before in g:
                g.remove(before)
            self.job.Operations.__dict__["Group"] = g

    def new_bit(label, shape="endmill"):
        sizes = {"endmill": ("Length", "CuttingEdgeHeight", "Flutes"), "drill": ("TipAngle", "Length", "Flutes"), "v-bit": ("CuttingEdgeAngle", "TipDiameter", "Length"),
                 "bullnose": ("CornerRadius", "Length", "Flutes"), "ballend": ("Length", "Flutes")}.get(shape, ("Length",))
        b = doc().new("Part::FeaturePython", "Bit", Diameter="5 mm", ShapeID=shape, **{k: (2 if k == "Flutes" else "1 mm") for k in sizes})
        b.__dict__["Label"] = label
        if flag("views"):
            b.__dict__["ViewObject"] = fc.Obj("view", "View", Visibility=True)
        return b

    def tc_create(name=None, tool=None):
        log("ToolController.Create", name, tool)
        tc = doc().new("Path::FeaturePython", "ToolController", HorizFeed="0 mm/min", VertFeed="0 mm/min", SpindleSpeed=0.0, ToolNumber=1)
        label = name or "TC: Default Tool"
        tc.__dict__["Label"] = label + "001" if any(o.Label == label for o in doc().Objects if o is not tc) else label
        tc.__dict__["Tool"] = tool if tool is not None else new_bit("Default Tool")
        return tc

    def job_create(name, models, template=None):
        log("Job.Create", name, models)
        d = doc()
        job = d.new("Path::FeaturePython", name)
        o = models[0]
        clone = d.new("Part::Feature", "Clone", Shape=o.Shape)
        clone.__dict__["Label"] = f"Model-{o.Label}"
        bb = o.Shape.BoundBox
        around = ((bb.XMin, bb.YMin, bb.ZMin), (bb.XMax, bb.YMax, bb.ZMax))
        if flag("fixed_stock"):
            stock = d.new("Stock", "Stock", fixed=((0, 0, 0), (100, 100, 25)))
        else:
            stock = d.new("Stock", "Stock", around=around, **{k: 1.0 for k in ("ExtXneg", "ExtXpos", "ExtYneg", "ExtYpos", "ExtZneg", "ExtZpos")})
        sheet = d.new("App::FeaturePython", "SetupSheet", **({} if flag("bare_sheet") else {"SafeHeightOffset": "3 mm", "ClearanceHeightOffset": "5 mm"}))
        job.__dict__.update(Operations=Grp("Operations"), Tools=Grp("Tools"), Model=Grp("Model", [] if flag("no_model") else [clone]), Stock=stock, around=around,
                            SetupSheet=None if flag("no_sheet") else sheet, Fixtures=["G54"], PostProcessorArgs=flag("post_args", ""), State=list(flag("job_state", [])))
        job.__dict__["Proxy"] = JobProxy(job)
        if not flag("no_tc"):
            job.Tools.Group.append(tc_create())
        return job

    def stock_from_base(job):
        log("Stock.CreateFromBase", job)
        if flag("stock_fails"):
            raise RuntimeError("no base to wrap")
        return doc().new("Stock", "Stock", around=job.around, **{k: 1.0 for k in ("ExtXneg", "ExtXpos", "ExtYneg", "ExtYpos", "ExtZneg", "ExtZpos")})

    def find_tc(*a, **kw):
        trace.append("findToolController()")
        j = next((j for j in doc().Objects if hasattr(j, "Tools") and hasattr(j, "Operations")), None)
        return j.Tools.Group[0] if j is not None and j.Tools.Group else None

    # ---- operations --------------------------------------------------------------------------------

    class OpProxy:
        def __init__(self, kind):
            self.kind = kind

        def __repr__(self):
            return f"<{self.kind} proxy>"

        def findAllHoles(self, op):
            trace.append(f"findAllHoles(<{op.Name}>)")
            op.Base = [] if flag("no_holes") else [(op.__dict__["job"].Model.Group[0], ["Face7"])]

        def generateTags(self, dr, n):
            trace.append(f"generateTags(<{dr.Name}>, {n})")
            dr.__dict__["Positions"] = [Vec(i, 0, 0) for i in range(n)]

        def setup(self, dr, *more):
            if not more and flag("setup_two"):
                raise TypeError("setup() missing 1 required positional argument")
            trace.append(f"setup(<{dr.Name}>{', True' if more else ''})")

    def dress_op(op, kind, name, job):
        """What FreeCAD gives a new operation: its properties, its place in
        the job, the tool controller it asks PathUtils for, a path."""
        if flag("create_fails") == "early":
            raise RuntimeError("the operation would not build")
        tc = sys.modules["PathScripts.PathUtils"].findToolController(op)
        trace.append(f"tool controller: {tc.Label if tc is not None else None}")
        props = {"Active": True, "Base": [], "ToolController": tc, "StartDepth": 20.0, "FinalDepth": 10.0, "CoolantMode": "None", "job": job, "kind": kind, "locked": tuple(flag("locked", ())),
                 "enums": {"CoolantMode": ["None", "Flood", "Mist"], "Side": ["Inside", "Outside"], "ClearingPattern": ["ZigZag", "Offset"], "OperationType": ["Clearing", "Profiling"]}}
        if kind not in ("probe", "custom", "drill"):
            props.update(StepDown=1.0, Side="Outside")
        if kind in ("pocket", "adaptive", "face"):
            props.update(StepOver=50 if kind == "pocket" else 50.0, StockToLeave=0.0, ClearingPattern="ZigZag", ints=("StepOver",) if kind == "pocket" else ())
        if kind == "adaptive":
            props["OperationType"] = "Clearing"
        if kind == "profile":
            props.update(StartPoint=Vec(), UseStartPoint=False)
        if kind == "engrave":
            props["BaseShapes"] = []
        if kind == "custom":
            props["Gcode"] = []
        op.__dict__.update(props)
        op.__dict__["Path"] = path_of(kind)
        if job is not None and not flag("unlisted"):
            job.Operations.Group.append(op)
        if flag("create_fails") == kind or flag("create_fails") is True:
            raise RuntimeError("the operation would not build")
        return op

    def op_module(kind, cls=None):
        m = types.ModuleType(f"Path.Op.{kind}")

        def Create(name, obj=None, parentJob=None):
            log(f"{m.__name__}.Create", name)
            op = doc().new("Path::FeaturePython", name)
            op.__dict__["Proxy"] = OpProxy(kind)
            return dress_op(op, m.kind, name, parentJob if parentJob is not None else next((j for j in doc().Objects if hasattr(j, "Operations")), None))

        m.Create = Create
        if cls:
            def proxy(op, name, job):
                trace.append(f"{cls}(<{op.Name}>, {name!r})")
                p = OpProxy(m.kind)
                dress_op(op, m.kind, name, job)
                if flag("proxy_knows"):
                    p.model = job.Model.Group
                return p

            def late(name):
                if name == cls and not flag("old_holes"):
                    return proxy
                raise AttributeError(name)

            m.__getattr__ = late
        return m

    # ---- dressups ----------------------------------------------------------------------------------

    def dressed(op, kind, listed=True):
        dr = doc().new("Path::FeaturePython", f"{kind.capitalize()}Dressup", Base=op, Active=True)
        how = flag("dress_path")
        cmds = [] if how == "empty" else [c for c in op.Path.Commands if how != "rapids" or c.Name == "G0"]
        dr.__dict__.update(Path=types.SimpleNamespace(Commands=cmds), Proxy=OpProxy(kind), enums={"Style": ["Dogbone", "T-bone"]})
        if kind == "tags":
            dr.__dict__.update(Width="4 mm", Height="2 mm", Angle="45 °", Positions=[Vec(), Vec(1, 0, 0)])
            if flag("bare_tags"):
                del dr.__dict__["Positions"], dr.__dict__["Angle"]
        if kind == "dogbone":
            dr.__dict__["Style"] = "Dogbone"
        if kind == "boundary":
            dr.__dict__["Stock"] = None if flag("no_dress_stock") else doc().new("Stock", "BoundaryStock", around=((0, 0, 0), (60, 40, 20)), ExtXneg=0.0, ExtXpos=0.0, ExtYneg=0.0, ExtYpos=0.0, ExtZneg=0.0, ExtZpos=0.0)
        job = job_of(op)
        if listed and job is not None and not flag("dress_unlisted"):
            g = job.Operations.Group
            g[g.index(op)] = dr
        return dr

    def dress_module(kind):
        m = types.ModuleType(f"Path.Dressup.{kind}")

        def Create(op, *a):
            log(f"{m.__name__}.Create", op)
            if flag("dress_fails"):
                raise RuntimeError("the path has no corners")
            return None if flag("dress_none") else dressed(op, kind)

        m.Create = Create
        return m

    ramp = types.ModuleType("Path.Dressup.Gui.RampEntry")

    def object_dressup(dr):
        trace.append(f"ObjectDressup(<{dr.Name}>)")
        dr.__dict__.update(Path=types.SimpleNamespace(Commands=[]), Active=True)
        return OpProxy("ramp")

    ramp.ObjectDressup = object_dressup

    # ---- tool bits ---------------------------------------------------------------------------------

    class ToolBit:
        def __init__(self, shape, name):
            self.shape, self.name = shape, name

        @staticmethod
        def from_shape_id(shape, *name):
            if name and flag("bit_one"):
                raise TypeError("from_shape_id() takes 1 positional argument")
            log("ToolBit.from_shape_id", shape, *name)
            if flag("bit_fails"):
                raise RuntimeError("no such shape here")
            return ToolBit(shape, name[0] if name else shape)

        def attach_to_doc(self, d):
            return new_bit(self.name, self.shape)

    def factory_create(name, shape_file):
        log("Bit.Factory.Create", name, os.path.basename(shape_file))
        return new_bit(name, os.path.splitext(os.path.basename(shape_file))[0])

    bit10 = types.ModuleType("Path.Tool.Bit")
    bit10.__getattr__ = lambda name: types.SimpleNamespace(Create=factory_create) if name == "Factory" and flag("bit10") else (_ for _ in ()).throw(AttributeError(name))

    # ---- posts -------------------------------------------------------------------------------------

    def gcode(job, labels):
        if flag("post") == "fails":
            raise RuntimeError("an operation has no moves")
        if flag("post") == "empty":
            return ""
        if flag("post") == "notext":
            return None
        return "\n".join(["(posted)", "G20" if flag("inch") else "G21"] + [f"({x})" for x in labels] + ["G1 X1 F100", "M2"]) + "\n"

    class Factory:
        @staticmethod
        def get_post_processor(job, name):
            log("get_post_processor", job, name, job.PostProcessorArgs)
            if flag("pp_none"):
                return None
            text = gcode(job, [o.Label for o in job.Operations.Group if getattr(o, "Active", True)]) if flag("pp") != "empty" else ""
            return types.SimpleNamespace(export=lambda: [("job", text), ("skip", None)] if not flag("pp_nosections") else None)

    def script(name, export=True):
        m = types.ModuleType(f"Path.Post.scripts.{name}_post")
        if export:
            def export_(postables, path, args):
                log(f"{name}_post.export", postables, path, args)
                return gcode(None, [o.Label for o in postables])

            m.export = export_
        return m

    importlib.reload = lambda m: (trace.append(f"reload({m.__name__})"), m)[1]

    # ---- the modules -------------------------------------------------------------------------------

    def ns(name, **kw):
        m = types.ModuleType(name)
        m.__dict__.update(kw)
        return m

    OPS = {"Profile": ("profile", None), "PocketShape": ("pocket", None), "Adaptive": ("adaptive", None), "MillFace": ("face", None), "Drilling": ("drill", "ObjectDrilling"),
           "Engrave": ("engrave", None), "Helix": ("helix", "ObjectHelix"), "Probe": ("probe", None), "Custom": ("custom", None), "Slot": ("slot", None)}
    mods = {"Path": ns("Path", __file__=os.path.join(os.sep, "nowhere", "Mod", "CAM", "Path", "__init__.py")), "Path.Main": ns("Path.Main"), "Path.Main.Job": ns("Path.Main.Job", Create=job_create),
            "Path.Main.Stock": ns("Path.Main.Stock", CreateFromBase=stock_from_base), "Path.Tool": ns("Path.Tool"), "Path.Tool.Controller": ns("Path.Tool.Controller", Create=tc_create),
            "Path.Tool.Bit": bit10, "Path.Tool.toolbit": ns("Path.Tool.toolbit", ToolBit=ToolBit), "Path.Op": ns("Path.Op"), "PathScripts": ns("PathScripts"),
            "PathScripts.PathUtils": ns("PathScripts.PathUtils", findToolController=find_tc), "Path.Dressup": ns("Path.Dressup"), "Path.Dressup.Gui": ns("Path.Dressup.Gui"),
            "Path.Dressup.Tags": dress_module("tags"), "Path.Dressup.DogboneII": dress_module("dogbone"), "Path.Dressup.Boundary": dress_module("boundary"),
            "Path.Dressup.Array": ns("Path.Dressup.Array"), "Path.Dressup.Gui.RampEntry": ramp, "Path.Post": ns("Path.Post"), "Path.Post.Processor": ns("Path.Post.Processor", PostProcessorFactory=Factory),
            "Path.Post.scripts": ns("Path.Post.scripts"), "Path.Post.scripts.grbl_post": script("grbl"), "Path.Post.scripts.linuxcnc_post": script("linuxcnc", export=False)}
    for mod, (kind, cls) in OPS.items():
        m = mods[f"Path.Op.{mod}"] = op_module(kind, cls)
        m.kind = kind

    def restore():
        """Every stand-in module back (a case may have taken some away)."""
        sys.modules.update(mods)
        for name, m in mods.items():
            parent, _, leaf = name.rpartition(".")
            if parent:
                setattr(mods[parent], leaf, m)

    def without(*names):
        """A FreeCAD that has no such module."""
        for name in names:
            sys.modules.pop(name, None)
            parent, _, leaf = name.rpartition(".")
            if parent and leaf in mods[parent].__dict__:
                delattr(mods[parent], leaf)

    restore()

    # shape_query's answer: the faces a case names (flags["faces"]), nearest first by their order
    from agentlink.families import measure

    def query(session, q):
        log("query", q)
        o = next(x for x in doc().Objects if x.Label == q["body"])
        return None, None, [(o, Face(i), {"ref": n}) for i, n in enumerate(flag("faces", ["Face6"]))]

    measure.query = query

    class Session(fc.Session):
        def body(self, ref):
            from agentlink.protocol import ToolError

            pool = [o for o in self.doc.Objects if o.__dict__.get("is_body")]
            hit = next((o for o in pool if ref in (None, o.Label, o.Name)), None)
            if hit is None:
                raise ToolError("not_found", f"body {ref!r}: not here.")
            return hit

        # furniture for the cases
        def block(self, label="Block", lo=(0, 0, 0), hi=(60, 40, 20)):
            o = self.doc.new("Part::Feature", "Body", Shape=BoxShape(lo, hi), is_body=True)
            o.__dict__["Label"] = label
            return o

        def job(self, label="Job", body=None, **tool):
            """A job round a block with its first tool set, made quietly."""
            job = job_create(label, [body or self.block()])
            job.__dict__["Label"] = label
            if job.Tools.Group:
                tc = job.Tools.Group[0]
                tc.__dict__.update(HorizFeed="600 mm/min", VertFeed="200 mm/min", SpindleSpeed=12000.0, **tool)
            return job

        def op(self, job, kind="profile", label=None, **kw):
            mod = next(m for m in mods.values() if getattr(m, "kind", None) == kind)
            op = mod.Create(label or kind.capitalize(), None, job)
            op.__dict__["Label"] = label or kind.capitalize()
            op.__dict__.update(kw)
            return op

        def dressup(self, op, kind="tags", label=None):
            dr = dressed(op, kind)
            dr.__dict__["Label"] = label or dr.Name
            return dr

        def tool(self, job, label, shape="endmill", **kw):
            tc = tc_create(label, new_bit(label + " bit", shape))
            tc.__dict__.update(HorizFeed="300 mm/min", VertFeed="100 mm/min", SpindleSpeed=8000.0, ToolNumber=len(job.Tools.Group) + 1, **kw)
            job.Tools.Group.append(tc)
            return tc

    fc.Session, fc.restore, fc.without, fc.Cmd, fc.BoxShape, fc.CamObj = Session, restore, without, Cmd, BoxShape, CamObj
    return fc

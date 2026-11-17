# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in of tests/test_datatd2_data.py for families/cam_more.py:
# tests/_datacam_standin.py as it is, and on top of it what cam_more's six
# tools reach: CAM's area, shape and compound paths, the window-side proxy
# classes (path from shape, array, stop, fixture), the property bag, a job's
# template, Draft's heal, and an assembly with its joint group. Nothing of
# the first stand-in is changed for its own test: this one is only ever
# installed in this test's child process.
import sys
import types


def install():
    import _datacam_standin

    fc = _datacam_standin.install()
    trace, state, flag, Obj, CamObj, Cmd = fc.trace, fc.state, fc.flag, fc.Obj, fc.CamObj, fc.Cmd
    classes = state["classes"]

    def doc():
        return state["doc"]

    def moves(n=3):
        return types.SimpleNamespace(Commands=[Cmd("G0", Z=25.0), Cmd("G0", X=0.0, Y=0.0), Cmd("G1", Z=-1.0), Cmd("G1", X=10.0, Y=0.0), Cmd("G1", X=10.0, Y=10.0),
                                               Cmd("G1", X=0.0, Y=10.0), Cmd("G0", Z=25.0)][:n])

    # A block's faces by name, and a vector turned round, as cam_more reads them.
    fc.BoxShape.Vertexes = []
    fc.BoxShape.getElement = lambda self, sub: f"<{sub} of {self!r}>"
    if not hasattr(fc.Vec, "negative"):
        fc.Vec.negative = lambda self: -self

    # ---- CAM's own path objects ---------------------------------------------------------------

    class Sections:
        """A Path::FeatureArea's shape: a wire and a face for each source."""

        def __init__(self, n):
            self.Wires = [object()] * n
            self.Faces = [] if flag("area_open") else [types.SimpleNamespace(Area=12.3456)] * n

        def isNull(self):
            return bool(flag("area_null"))

    class Area(CamObj):
        def __init__(self, name, type_, **kw):
            CamObj.__init__(self, name, type_, **{"Sources": [], "Offset": 0.0, "Stepdown": 1.0, "PocketMode": "None", "enums": {"PocketMode": ["None", "ZigZag", "Offset"]}, **kw})

        @property
        def Shape(self):
            return None if flag("area_shapeless") else Sections(len(self.Sources))

    class ShapePath(CamObj):
        @property
        def Path(self):
            return moves(7) if self.__dict__.get("Sources") else None

    class Compound(CamObj):
        @property
        def Path(self):
            return moves(4)

    classes.update({"Path::FeatureArea": Area, "Path::FeatureShape": ShapePath, "Path::FeatureCompound": Compound})

    def proxy(name, **props):
        def make(o, *more):
            trace.append(f"{name}({', '.join(fc.show(x) for x in (o, *more))})")
            o.__dict__.update({k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in props.items()})
            o.__dict__["Path"] = moves(2)

        return make

    FIXTURES = ["G53", "G54", "G55", "G56", "G57", "G58", "G59", "G59.1"]

    def bag_create(name):
        trace.append(f"PropertyBag.Create({name!r})")
        bag = doc().new("App::FeaturePython", name.replace(" ", "_"))
        bag.__dict__["ints"] = set()

        def add(kind, prop, group, info):
            trace.append(f"{bag.Name}.addCustomProperty({kind!r}, {prop!r}, {group!r}, {info!r})")
            bag.__dict__[prop] = 0.0
            if kind == "App::PropertyInteger":
                bag.__dict__["ints"].add(prop)

        bag.__dict__["Proxy"] = types.SimpleNamespace(addCustomProperty=add)
        return bag

    classes["App::FeaturePython"] = CamObj

    def ns(name, **kw):
        m = types.ModuleType(name)
        m.__dict__.update(kw)
        return m

    class Joints(types.ModuleType):
        """Assembly's JointObject: rigid group joints from 1.2 only (a case's flag: rigid)."""

        JointTypes = ["Fixed", "Revolute", "Slider"]

        def __getattr__(self, k):
            if k == "RigidGroupJoint" and flag("rigid"):
                return lambda rg, parts: trace.append(f"RigidGroupJoint({fc.show(rg)}, {fc.show(parts)})")
            raise AttributeError(k)

    def heal(targets):
        trace.append(f"Draft.heal({fc.show(targets) if targets is not None else None})")
        d = doc()
        for label in flag("heals", ()):
            old = next(o for o in d.Objects if o.Label == label)
            d.Objects = [o for o in d.Objects if o is not old]
            d.new(old.TypeId, old.Name + "_healed").__dict__["Label"] = label

    mine = {"Path.Op.Gui": ns("Path.Op.Gui"), "Path.Op.Gui.PathShape": ns("Path.Op.Gui.PathShape", ObjectPathShape=proxy("ObjectPathShape", Base=[])),
            "Path.Op.Gui.Array": ns("Path.Op.Gui.Array", ObjectArray=proxy("ObjectArray", Base=[], ToolController=None, Type="Linear1D", Copies=0, enums={"Type": ["Linear1D", "Linear2D", "Polar"]},
                                                                           ints=("Copies",))),
            "Path.Op.Gui.Stop": ns("Path.Op.Gui.Stop", Stop=proxy("Stop", Stop="Optional", enums={"Stop": ["Optional", "Mandatory"]})),
            "Path.Main.Gui": ns("Path.Main.Gui"), "Path.Main.Gui.Fixture": ns("Path.Main.Gui.Fixture", Fixture=proxy("Fixture", Fixture="G54", Active=False, enums={"Fixture": FIXTURES})),
            "Path.Base": ns("Path.Base"), "Path.Base.PropertyBag": ns("Path.Base.PropertyBag", Create=bag_create),
            "Draft": ns("Draft", heal=heal), "JointObject": Joints("JointObject"), "UtilsAssembly": ns("UtilsAssembly")}
    job_mod, stock_mod = sys.modules["Path.Main.Job"], sys.modules["Path.Main.Stock"]
    job_mod.JobTemplate = types.SimpleNamespace(Description="Desc", ToolController="ToolController", Stock="Stock", SetupSheet="SetupSheet")
    stock_mod.TemplateAttributes = lambda stock: (trace.append(f"Stock.TemplateAttributes({fc.show(stock)})"), {"create": "FromBase", "xneg": 1.0})[1]

    def fresh():
        """The stand-in's counters and every stand-in module as at the start (a case may take some away)."""
        state["n"] = 0
        fc.restore()
        sys.modules.update(mine)
        for name, m in mine.items():
            parent, _, leaf = name.rpartition(".")
            if parent:
                setattr(sys.modules[parent], leaf, m)

    def gone(*names):
        """A FreeCAD that has no such module (one of this stand-in's own)."""
        for name in names:
            sys.modules.pop(name, None)
            parent, _, leaf = name.rpartition(".")
            if parent and leaf in sys.modules[parent].__dict__:
                delattr(sys.modules[parent], leaf)

    fresh()

    # ---- an assembly ------------------------------------------------------------------------------

    class Holder(Obj):
        """An assembly, its joint group or an App::Part: what it holds is in Group."""

        def __init__(self, name, type_, **kw):
            Obj.__init__(self, name, type_, **{"Group": [], **kw})

        def newObject(self, type_, name):
            o = doc().new(type_, name)
            trace.append(f"{self.Name}.newObject({type_!r}, {o.Name!r})")
            self.__dict__["Group"] = self.Group + [o]
            return o

    classes.update({"Assembly::AssemblyObject": Holder, "Assembly::JointGroup": Holder, "App::Part": Holder})

    class Templates:
        """A job's proxy as far as its template goes."""

        def __init__(self, first):
            self.__dict__.update(first.__dict__)
            self.setupSheet = types.SimpleNamespace(
                templateAttributes=lambda *a: (trace.append(f"setupSheet.templateAttributes{a!r}"), {"SafeHeightOffset": "3 mm"})[1],
                encodeTemplateAttributes=lambda attrs: (trace.append(f"setupSheet.encodeTemplateAttributes({sorted(attrs)!r})"), dict(attrs))[1])

        def templateAttrs(self, job):
            trace.append(f"templateAttrs({fc.show(job)})")
            return {"Version": 1, "PostProcessor": "grbl"}

    Base = fc.Session

    class Session(Base):
        # furniture for the cases
        def job(self, label="Job", body=None, **tool):
            job = Base.job(self, label, body, **tool)
            job.__dict__["Proxy"] = Templates(job.Proxy)
            for tc in job.Tools.Group:
                tc.__dict__["Proxy"] = types.SimpleNamespace(templateAttrs=lambda tc: {"label": tc.Label, "nr": tc.ToolNumber})
            return job

        def assembly(self, label="Assembly", parts=("Base", "Arm")):
            asm = self.doc.new("Assembly::AssemblyObject", "Assembly")
            asm.__dict__["Label"] = label
            for i, p in enumerate(parts):
                asm.__dict__["Group"] = asm.Group + [self.block(p, (20 * i, 0, 0), (20 * i + 10, 10, 10))]
            return asm

        def dimension(self, label="Dimension", normal=(0, 0, 1)):
            o = self.doc.new("App::FeaturePython", "Dimension", Normal=fc.Vec(*normal), Dimline=fc.Vec(0, 5, 0))
            o.__dict__["Label"] = label
            return o

        def plain(self, label, **kw):
            o = self.doc.new("Part::Feature", "Wire", **kw)
            o.__dict__["Label"] = label
            return o

    fc.Session, fc.fresh, fc.gone, fc.moves = Session, fresh, gone, moves
    return fc

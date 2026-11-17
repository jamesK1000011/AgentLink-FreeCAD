# SPDX-License-Identifier: LGPL-2.1-or-later
# A stand-in TechDraw for tests/test_datatd_data.py, on top of
# tests/_datamesh_standin.py's FreeCAD: pages, templates, views with a few
# lines and a circle, projection groups, leaders, dimensions and the other
# TechDraw objects as far as the td_ tools reach. Not TechDraw's drawing: a
# view of a body is the body's box seen from the front (x, z) with one hole,
# so that references land on real edges and the old handlers and the new
# data entries can be compared step for step. Only installed in a child process.
import math
import os
import types


def install():
    import _datamesh_standin

    fc = _datamesh_standin.install()
    trace, state, flag, Obj, Vec, Shape = fc.trace, fc.state, fc.flag, fc.Obj, fc.Vec, fc.Shape
    part = fc.part

    def log(text):
        trace.append(text)

    # ---- curves and edges ---------------------------------------------------------------------

    class LineSegment:
        pass

    class Circle:
        def __init__(self, c=None, r=0.0):
            self.Location, self.Radius, self.Center = c or Vec(), r, c or Vec()

    part.LineSegment, part.Line, part.Circle = LineSegment, LineSegment, Circle

    def line(p, q):
        e = Shape("Edge", [p, q], Curve=LineSegment(), FirstParameter=0.0, LastParameter=(Vec(q) - Vec(p)).Length)
        e.Vertexes = [types.SimpleNamespace(Point=Vec(p)), types.SimpleNamespace(Point=Vec(q))]
        e.valueAt = lambda t: Vec(p) + (Vec(q) - Vec(p)) * (t / max(e.LastParameter, 1e-9))
        e.Edges = [e]
        return e

    def circle(c, r):
        c = Vec(c)
        e = Shape("Edge", [c + Vec(-r, -r, 0), c + Vec(r, r, 0)], Curve=Circle(c, r), FirstParameter=0.0, LastParameter=2 * math.pi)
        e.Vertexes = [types.SimpleNamespace(Point=c + Vec(r, 0, 0))]
        e.valueAt = lambda t: c + Vec(r * math.cos(t), r * math.sin(t), 0)
        e.__dict__["length"] = 2 * math.pi * r
        e.Edges = [e]
        return e

    # ---- a body to draw: a 40 × 10 × 20 box --------------------------------------------------------

    BOX = [(x, y, z) for x in (0, 40) for y in (0, 10) for z in (0, 20)]

    def body_shape():
        s = Shape("Solid", BOX, Volume=8000.0, Area=2800.0)
        s.Vertexes = [types.SimpleNamespace(Point=Vec(p)) for p in BOX]
        ring = types.SimpleNamespace(discretize=lambda Deflection=0.02: [Vec(0, 0, 0), Vec(40, 0, 0), Vec(40, 0, 20), Vec(0, 0, 20)])
        flat = types.SimpleNamespace(discretize=lambda Deflection=0.02: [Vec(0, 0, 0), Vec(40, 0, 0), Vec(40, 10, 0), Vec(0, 10, 0)])
        faces = {"Face1": Shape("Face", BOX[:4], Wires=[ring], Area=800.0, CenterOfMass=Vec(20, 0, 10)),
                 "Face2": Shape("Face", BOX[:4], Wires=[flat], Area=400.0, CenterOfMass=Vec(20, 5, 0))}
        s.Faces, s.Solids = list(faces.values()), [s]
        s.Edges = [line((0, 0, 0), (40, 0, 0)), line((40, 0, 0), (40, 0, 20)), line((40, 0, 20), (0, 0, 20)), line((0, 0, 20), (0, 0, 0))]

        def element(name):
            if name not in faces:
                raise ValueError(f"no {name}")
            return faces[name]

        s.getElement = element
        return s

    real_compound = part.makeCompound

    def compound(shapes):
        """A compound of bodies keeps the first one's corners and faces; of edges, their points."""
        shapes = list(shapes)
        c = Shape("Compound", [p for s in shapes for p in s.pts])
        first = shapes[0] if shapes else None
        if first is not None and hasattr(first, "getElement"):
            c.Vertexes, c.getElement, c.Faces, c.Edges = first.Vertexes, first.getElement, first.Faces, first.Edges
        return c

    part.makeCompound = part.Compound = compound
    del real_compound

    # ---- TechDraw's objects ----------------------------------------------------------------------

    class TD(Obj):
        KINDS = ()
        DEFAULTS = {}
        ENUMS = {}

        def __init__(self, name, type_, **kw):
            Obj.__init__(self, name, type_, **{"kinds": self.KINDS, "enums": dict(self.ENUMS), "X": 0.0, "Y": 0.0, **self.DEFAULTS, **kw})

        def call(self, name, *a):
            log(f"{self.Name}.{name}({', '.join(fc.show(x) for x in a)})")

        def findParentPage(self):
            return next((p for p in self.InList if p.TypeId == "TechDraw::DrawPage"), None)

        def recompute(self):
            self.call("recompute")

    class Page(TD):
        DEFAULTS = {"ProjectionType": "Third angle", "Scale": 1.0, "Template": None, "NextBalloonIndex": 1}
        ENUMS = {"ProjectionType": ["First angle", "Third angle"]}

        def __init__(self, name, type_, **kw):
            TD.__init__(self, name, type_, **kw)
            self.__dict__["Views"] = []

        def addView(self, v):
            self.call("addView", v)
            self.__dict__["Views"] = self.Views + [v]
            v.InList.append(self)

        def removeView(self, v):
            self.call("removeView", v)
            self.__dict__["Views"] = [x for x in self.Views if x is not v]

    class Template(TD):
        def __setattr__(self, k, v):
            Obj.__setattr__(self, k, v)
            if k == "Template":
                import re

                base = os.path.basename(v)
                w, h = (420.0, 297.0) if base.startswith("A3") else (279.4, 215.9) if base.startswith(("ANSIA", "USLetter")) else (297.0, 210.0)
                if "Portrait" in base:
                    w, h = h, w
                self.__dict__.update(Width=w, Height=h)
                self.__dict__.pop("EditableTexts", None)
                if "blank" not in base.lower():
                    with open(v, encoding="utf-8") as f:
                        fields = dict(re.findall(r'freecad:editable="([^"]+)"[^>]*>\s*(?:<tspan[^>]*>)?([^<]*)', f.read()))
                    if "FC-SC" in fields:
                        fields["FC-SC"] = "1 : 1"  # what FreeCAD fills in itself
                    self.__dict__["EditableTexts"] = fields

    def view_edges(v):
        """The body's box seen from the front, centred, scaled, y down, with one hole in the middle."""
        if not v.__dict__.get("Source") and not v.__dict__.get("BaseView"):
            return [], []
        if flag("late_edges") and not v.__dict__.get("ready"):
            return [], []
        if flag("no_edges"):
            return [], []
        s = float(v.__dict__.get("Scale", 1.0))
        c = [Vec(-20 * s, 10 * s, 0), Vec(20 * s, 10 * s, 0), Vec(20 * s, -10 * s, 0), Vec(-20 * s, -10 * s, 0)]
        edges = [line(c[i], c[(i + 1) % 4]) for i in range(4)] + [circle((0, 0, 0), 5 * s)]
        return edges, c

    class View(TD):
        KINDS = ("TechDraw::DrawView", "TechDraw::DrawViewPart")
        DEFAULTS = {"Scale": 1.0, "ScaleType": "Page", "Source": [], "XSource": [], "Direction": None, "XDirection": None, "Rotation": 0.0,
                    "CosmeticVertexes": [], "CosmeticEdges": [], "CenterLines": []}
        ENUMS = {"SectionDirection": ["Right", "Left", "Up", "Down"], "ScaleType": ["Page", "Automatic", "Custom"]}

        def __init__(self, name, type_, **kw):
            TD.__init__(self, name, type_, **kw)
            self.__dict__.update(Direction=Vec(0, -1, 0), XDirection=Vec(1, 0, 0))

        def getVisibleEdges(self):
            return view_edges(self)[0]

        def getHiddenEdges(self):
            return []

        def getEdgeByIndex(self, i):
            es = view_edges(self)[0]
            return es[i] if i < len(es) else None

        def getVertexByIndex(self, i):
            vs = view_edges(self)[1]
            return types.SimpleNamespace(Point=vs[i]) if i < len(vs) else None

        def projectPoint(self, p, *more):
            return Vec(p.x, p.z, 0)

        def getScale(self):
            return float(self.Scale)

        def getGeometricCenter(self):
            return Vec(20, 5, 10)

    class Section(View):
        KINDS = View.KINDS + ("TechDraw::DrawViewSection",)
        DEFAULTS = {**View.DEFAULTS, "SectionSymbol": "", "CutSurfaceDisplay": "SvgHatch"}

    class Detail(View):
        KINDS = View.KINDS + ("TechDraw::DrawViewDetail",)
        DEFAULTS = {**View.DEFAULTS, "Reference": ""}

    class Item(View):
        KINDS = View.KINDS + ("TechDraw::DrawProjGroupItem",)

    class Group(TD):
        KINDS = ("TechDraw::DrawView", "TechDraw::DrawViewCollection", "TechDraw::DrawProjGroup")
        DEFAULTS = {"Scale": 1.0, "ScaleType": "Page", "Source": [], "ProjectionType": "Third angle", "AutoDistribute": False}
        ENUMS = {"ProjectionType": ["First angle", "Third angle"]}

        def __init__(self, name, type_, **kw):
            TD.__init__(self, name, type_, **kw)
            self.__dict__["Views"] = []

        def addProjection(self, name):
            self.call("addProjection", name)
            v = state["doc"].new("TechDraw::DrawProjGroupItem", name)
            v.__dict__.update(Label=name, Source=list(self.Source), Type=name, X={"Top": 0.0, "Right": 60.0}.get(name, 0.0), Y={"Top": 40.0}.get(name, 0.0))
            v.InList.append(self)
            self.__dict__["Views"] = self.Views + [v]
            if name == "Front" and not flag("no_anchor"):
                self.__dict__["Anchor"] = v
            return v

    class Arch(TD):
        KINDS = ("TechDraw::DrawView", "TechDraw::DrawViewSymbol")
        DEFAULTS = {"Scale": 1.0, "Source": None, "AllOn": False, "RenderMode": "Wireframe", "ShowFill": False, "ShowHidden": False}

        def __getattr__(self, k):
            if k == "Symbol":
                return "" if flag("arch_draws_nothing") else "<svg>plan</svg>"
            return TD.__getattr__(self, k)

        def __setattr__(self, k, v):
            if k == "RenderMode" and v not in ("Wireframe", "Solid"):
                raise ValueError(f"{v!r} is not part of the enumeration")
            Obj.__setattr__(self, k, v)

    class Leader(TD):
        KINDS = ("TechDraw::DrawView",)
        ENUMS = {"StartSymbol": ["Filled Arrow", "Open Arrow", "None"], "EndSymbol": ["Filled Arrow", "None"]}
        DEFAULTS = {"StartSymbol": "None", "EndSymbol": "None", "LeaderParent": None, "WayPoints": []}


    class Dimension(TD):
        KINDS = ("TechDraw::DrawView",)
        DEFAULTS = {"FormatSpec": "%.2f", "EqualTolerance": True, "TheoreticalExact": False, "Arbitrary": False, "Type": "Distance", "References2D": [],
                    "OverTolerance": types.SimpleNamespace(Value=0.0), "UnderTolerance": types.SimpleNamespace(Value=0.0)}

        def __setattr__(self, k, v):
            Obj.__setattr__(self, k, v)
            if k in ("OverTolerance", "UnderTolerance"):
                self.__dict__[k] = types.SimpleNamespace(Value=float(v))

        def getRawValue(self):
            if flag("cannot_measure"):
                raise RuntimeError("references do not fit the type")
            view = self.References2D[0][0]
            es, vs = view_edges(view)
            names = []
            for _, sub in self.References2D:
                names += list(sub) if isinstance(sub, (list, tuple)) else [sub]
            if self.Type in ("Radius", "Diameter"):
                r = es[int(names[0][4:])].Curve.Radius / float(view.Scale)
                return r * (2 if self.Type == "Diameter" else 1)
            if self.Type == "Angle":
                return 90.0
            if len(names) == 1:
                return es[int(names[0][4:])].Length / float(view.Scale)
            pts = [vs[int(n[6:])] if n.startswith("Vertex") else es[int(n[4:])].pts[0] for n in names]
            d = pts[1] - pts[0]
            k = float(view.Scale)
            return abs(d.x) / k if self.Type == "DistanceX" else abs(d.y) / k if self.Type == "DistanceY" else d.Length / k

        def getText(self):
            if flag("no_text"):
                raise RuntimeError("no text yet")
            return (self.FormatSpec % self.getRawValue()) if "%" in self.FormatSpec else self.FormatSpec

    class Plain(TD):
        KINDS = ("TechDraw::DrawView",)

    class Sheet(Obj):
        def getNonEmptyCells(self):
            return list(self.__dict__.get("cells", {}))

        def getContents(self, a):
            return self.__dict__.get("cells", {}).get(a, "")

    classes = {"TechDraw::DrawPage": Page, "TechDraw::DrawSVGTemplate": Template, "TechDraw::DrawViewPart": View, "TechDraw::DrawViewSection": Section,
               "TechDraw::DrawViewDetail": Detail, "TechDraw::DrawProjGroupItem": Item, "TechDraw::DrawProjGroup": Group, "TechDraw::DrawViewArch": Arch,
               "TechDraw::DrawLeaderLine": Leader, "TechDraw::DrawViewDimension": Dimension, "TechDraw::DrawViewSymbol": Plain, "TechDraw::DrawViewAnnotation": Plain,
               "TechDraw::DrawViewBalloon": Plain, "TechDraw::DrawViewSpreadsheet": Plain, "Spreadsheet::Sheet": Sheet}
    state["classes"] = classes

    # ---- the build's templates, the person's presets -------------------------------------------------

    import tempfile

    res = tempfile.mkdtemp(prefix="td-resource-")
    root = os.path.join(res, "Mod", "TechDraw", "Templates")
    field = '<text freecad:editable="{k}" x="1"><tspan>{v}</tspan></text>'

    def template(rel, fields):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("<svg>" + "".join(field.format(k=k, v=v) for k, v in fields.items()) + "</svg>")

    block = {"AUTHOR_NAME": "Sample Author", "DRAWING_TITLE": "Sample Title", "FC-SC": "1 : 2", "FC-DATE": "2020-01-01", "PM": ""}
    template(os.path.join("ISO", "A4_Landscape_ISO5457_minimal.svg"), block)
    template(os.path.join("ISO", "A4_Portrait_ISO5457_minimal.svg"), block)
    template(os.path.join("ISO", "A3_Landscape_ISO5457_minimal.svg"), block)
    template(os.path.join("ISO", "A4_Landscape_blank.svg"), {})
    template(os.path.join("ASME", "ANSIA_Landscape.svg"), block)
    fc.fc.getResourceDir = lambda: res
    fc.fc.getUserAppDataDir = lambda: state.get("appdata") or tempfile.mkdtemp()
    fc.fc.setActiveDocument = lambda name: log(f"setActiveDocument({name!r})")

    techdraw = types.ModuleType("TechDraw")
    import sys

    sys.modules["TechDraw"] = techdraw

    def make_extent_dim(view, edges, way):
        log(f"TechDraw.makeExtentDim({fc.show(view)}, {edges!r}, {way})")
        if flag("no_extent"):
            return
        d = state["doc"].new("TechDraw::DrawViewDimension", "Extent")
        d.__dict__.update(Type="DistanceX" if way == 0 else "DistanceY", References2D=[(view, "Vertex0"), (view, "Vertex2")], Label="Extent")

    techdraw.makeExtentDim = make_extent_dim

    # TechDraw finishes a view's lines on another thread; here the wait is
    # written down and the views are then ready.
    from agentlink import td_wait

    def wait_views(views, timeout=30.0):
        log(f"wait_views({fc.show(list(views))})")
        for v in views:
            v.__dict__["ready"] = True
        return None

    td_wait.wait_views = wait_views

    Base = fc.Session

    class Session(Base):
        def __init__(self, out_dir="/tmp"):
            Base.__init__(self, out_dir)
            state["appdata"] = os.path.join(out_dir, "appdata")
            os.makedirs(state["appdata"], exist_ok=True)

        def bodies(self):
            return [o for o in self.doc.Objects if o.TypeId == "Part::Feature" and o.__dict__.get("is_body")]

        def body(self, ref):
            from agentlink.protocol import ToolError

            o = next((x for x in self.bodies() if ref in (x.Label, x.Name)), None)
            if o is None:
                raise ToolError("not_found", f"body {ref!r}: not here.")
            return o

        # furniture for the cases
        def box(self, label="Box"):
            o = self.doc.new("Part::Feature", "Box", Shape=body_shape(), is_body=True)
            o.__dict__["Label"] = label
            return o

        def page(self, label="Drawing", template=os.path.join("ISO", "A4_Landscape_ISO5457_minimal.svg")):
            p = self.doc.new("TechDraw::DrawPage", "Page")
            t = self.doc.new("TechDraw::DrawSVGTemplate", "Template")
            n = len(trace)
            t.Template = os.path.join(root, template)
            del trace[n:]
            p.__dict__.update(Label=label, Template=t)
            return p

        def sheet(self, label="Parts", cells=None):
            o = self.doc.new("Spreadsheet::Sheet", "Spreadsheet", cells=dict(cells or {}))
            o.__dict__["Label"] = label
            return o

        def dim(self, view, refs, label="Dimension", type_="Distance"):
            d = self.doc.new("TechDraw::DrawViewDimension", "Dimension")
            d.__dict__.update(Label=label, Type=type_, References2D=[(view, r) for r in refs], X=5.0, Y=-20.0)
            page = view.findParentPage()
            page.__dict__["Views"] = page.Views + [d]
            d.InList.append(page)
            return d

        def view(self, page, label="Front", type_="TechDraw::DrawViewPart", body=None, **kw):
            v = self.doc.new(type_, "View")
            v.__dict__.update({"Label": label, "Source": [body] if body is not None else [], "X": 100.0, "Y": 120.0, **kw})
            page.__dict__["Views"] = page.Views + [v]
            v.InList.append(page)
            return v

    fc.Session, fc.td_root, fc.line, fc.circle, fc.body_shape, fc.TD, fc.classes = Session, root, line, circle, body_shape, TD, classes
    return fc

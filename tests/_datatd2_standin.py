# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in TechDraw of tests/test_datatd2_data.py: tests/_datatd_standin.py
# as it is, and on top of it what TechDraw's last five tools reach (td_list,
# td_export, td_cosmetic, td_view_more, td_lines): a view's own cosmetic edges
# and centerlines by tag, an edge's line format, the window's stacking order,
# broken, Draft, clip, image and symbol views, and TechDraw's DXF writer.
# Nothing of the first stand-in is changed for its own test: this one is only
# ever installed in this test's child process.
import json
import types


def install():
    import _datatd_standin

    fc = _datatd_standin.install()
    flag, trace, state, classes, TD = fc.flag, fc.trace, fc.state, fc.classes, fc.TD
    View, Plain, Page = classes["TechDraw::DrawViewPart"], classes["TechDraw::DrawViewSymbol"], classes["TechDraw::DrawPage"]

    def fresh():
        state["n"] = 0  # the stand-in numbers its shapes: from one in each run

    # ---- a view's own cosmetic edges, centerlines and line formats ---------------------------

    def tags(self):
        return self.__dict__.setdefault("cosmetic", {})

    def make_line(self, p, q):
        if flag("no_cosmetic"):
            raise RuntimeError("no cosmetic edges here")
        t = f"ce{len(tags(self)) + 1}"
        self.call("makeCosmeticLine", p, q)
        tags(self)[t] = types.SimpleNamespace(Format=(1, 0.35, (0, 0, 0, 1), True))
        return t

    def make_circle(self, c, r):
        t = f"ce{len(tags(self)) + 1}"
        self.call("makeCosmeticCircle", c, r)
        tags(self)[t] = types.SimpleNamespace(Format={"style": 1, "weight": 0.35} if flag("format_dict") else (1, 0.35, (0, 0, 0, 1), True))
        return t

    def get_edge(self, t):
        return tags(self)[t]

    def remove_edge(self, t):
        if t not in tags(self):
            raise ValueError(f"no cosmetic edge {t}")
        self.call("removeCosmeticEdge", t)
        tags(self)[t] = None

    def remove_centerline(self, t):
        if t not in self.__dict__.get("centerlines", {}):
            raise ValueError(f"no centerline {t}")
        self.call("removeCenterLine", t)

    def remove_vertex(self, t):
        if not str(t).startswith("cv"):
            raise ValueError(f"no cosmetic vertex {t}")
        self.call("removeCosmeticVertex", t)

    def get_centerline(self, t):
        cl = self.__dict__.get("centerlines", {}).get(t)
        if cl is None:
            raise ValueError("tag not found")
        return cl

    def format_edge(self, i, style, weight, colour, visible):
        self.call("formatGeometricEdge", i, style, weight, list(colour), visible)

    View.makeCosmeticLine, View.makeCosmeticCircle, View.getCosmeticEdge, View.removeCosmeticEdge = make_line, make_circle, get_edge, remove_edge
    View.removeCenterLine, View.removeCosmeticVertex, View.getCenterLine, View.formatGeometricEdge = remove_centerline, remove_vertex, get_centerline, format_edge

    class Centerline:
        """One of FreeCAD's own centerlines: its Extension is written down when set."""

        def __init__(self, tag, ext):
            self.__dict__.update(tag=tag, Extension=ext)

        def __setattr__(self, k, v):
            trace.append(f"centerline {self.tag}.{k} = {v:g}")
            self.__dict__[k] = v

    class Provider:
        """A view's view provider in the window: what keeps its stacking order."""

        def __init__(self, owner, order):
            self.__dict__.update(owner=owner, StackOrder=order)

        def __setattr__(self, k, v):
            trace.append(f"{self.owner}.ViewObject.{k} = {v!r}")
            self.__dict__[k] = v

    # ---- the other kinds of view ----------------------------------------------------------------

    class Broken(View):
        KINDS = View.KINDS + ("TechDraw::DrawBrokenView",)
        DEFAULTS = {**View.DEFAULTS, "Breaks": [], "Gap": 10.0}

    class Clip(TD):
        KINDS = ("TechDraw::DrawView", "TechDraw::DrawViewClip")
        DEFAULTS = {"Width": 0.0, "Height": 0.0, "ShowFrame": False}

        def __init__(self, name, type_, **kw):
            TD.__init__(self, name, type_, **kw)
            self.__dict__["Views"] = []

        addView, removeView = Page.addView, Page.removeView

    classes.update({"TechDraw::DrawBrokenView": Broken, "TechDraw::DrawViewClip": Clip, "TechDraw::DrawViewDraft": Plain, "TechDraw::DrawViewImage": Plain})

    # ---- TechDraw's own DXF writer --------------------------------------------------------------

    import TechDraw

    def write_dxf(page, path):
        trace.append(f"TechDraw.writeDXFPage({fc.show(page)}, {path.rsplit('/', 1)[-1]!r})")
        how = flag("dxf")
        if how == "raises":
            raise RuntimeError("no DXF here")
        if how != "nothing":
            with open(path, "w", encoding="utf-8") as f:
                f.write("0\nSECTION\n" if how != "empty" else "")

    TechDraw.writeDXFPage = write_dxf

    fc.fc.Version = lambda: list(flag("version", ["1", "1", "3"]))

    Base = fc.Session

    class Session(Base):
        # furniture for the cases
        def cosmetic(self, v, prims):
            """td_cosmetic's lines already on a view (its note), each with FreeCAD's own edge where it has tags."""
            for p in prims:
                for t in p.get("tags", []):
                    tags(v)[t] = types.SimpleNamespace(Format=(1, 0.18, (0, 0, 0, 1), True))
            v.__dict__["AgentLinkCosmetic"] = json.dumps(prims)

        def centerline(self, v, tag, ext=3.0):
            v.__dict__.setdefault("centerlines", {})[tag] = Centerline(tag, ext)

        def provider(self, v, order):
            v.__dict__["ViewObject"] = Provider(v.Name, order)

        def symbol(self, page, data, name="Symbol"):
            o = self.doc.new("TechDraw::DrawViewSymbol", name)
            o.__dict__.update(AgentLinkGdt=json.dumps(data), Symbol="<svg/>")
            page.__dict__["Views"] = page.Views + [o]
            o.InList.append(page)
            return o

        def group(self, page, body, label="Views"):
            g = self.doc.new("TechDraw::DrawProjGroup", "ProjGroup")
            g.__dict__.update(Label=label, Source=[body])
            n = len(trace)
            g.addProjection("Front")
            g.addProjection("Top")
            del trace[n:]
            page.__dict__["Views"] = page.Views + [g]
            g.InList.append(page)
            return g

        def clip(self, page, label="Window"):
            c = self.doc.new("TechDraw::DrawViewClip", "Clip")
            c.__dict__["Label"] = label
            page.__dict__["Views"] = page.Views + [c]
            c.InList.append(page)
            return c

    fc.Session, fc.fresh, fc.Centerline = Session, fresh, Centerline
    return fc

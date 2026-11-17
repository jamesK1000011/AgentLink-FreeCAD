# SPDX-License-Identifier: LGPL-2.1-or-later
# The Draft workbench's own parametric objects, beside draft.py's lettering,
# outlines and arrays: 2D shapes (wire, rectangle, circle, arc, ellipse,
# polygon, B-spline, Bezier, point), dimensions and labels, link arrays
# (ortho, polar, circular, along a path, at points), clones, the modify
# tools (move, rotate, scale, mirror, offset, upgrade, downgrade, join,
# 2D fillet), layers, hatches, Draft and Sketch each way, 2D views of a
# body and facebinders. Draft runs headless; its objects open in the GUI.

import json
import os

import FreeCAD
import Draft

from .. import runners
from .. import geometry as geo
from .. import paths
from ..protocol import ToolError, bad
from . import picks

GROUP = "draft"
INFO = ("Draft: lettering, SVG/DXF outlines, arrays, and Draft's own parametric 2D shapes, dimensions, labels, link arrays, clones, "
        "move/rotate/scale/mirror/offset, upgrade/downgrade, layers, hatches, Draft↔Sketch, 2D views, facebinders; surfaces and textures.")

V = FreeCAD.Vector


def v3(a, what, default=None):
    """[x, y, z] (or +x, -z …) as a vector; default when left out."""
    return picks.vec3(a, what, default)


def pl_of(a):
    """Where a Draft shape goes: at, turned so that z is along normal."""
    n = picks.direction(a.get("normal"), "normal", (0, 0, 1))
    return FreeCAD.Placement(v3(a.get("at"), "at", (0, 0, 0)), FreeCAD.Rotation(V(0, 0, 1), n))


def reading(o):
    """What a Draft object is: its label, type, length, area, volume and box."""
    sh = getattr(o, "Shape", None)
    out = {"object": o.Label, "type": (getattr(getattr(o, "Proxy", None), "Type", None) or o.TypeId.split("::")[-1])}
    if sh is not None and not sh.isNull():
        if sh.Edges:
            out["length"] = round(sum(e.Length for e in sh.Edges), 4)
        if sh.Faces:
            out["area"] = round(sh.Area, 4)
        if sh.Solids:
            out["volume"] = round(sh.Volume, 4)
        out["box"] = geo.box_json(sh, 3)["size"]
    return out


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def active():
        """Draft makes objects in the active document: the session's is made that."""
        if FreeCAD.ActiveDocument is not doc():
            FreeCAD.setActiveDocument(doc().Name)

    def named(o, name, default):
        """o under name (or default), unique among the others: Draft has already given it a label of its own."""
        if o is not None:
            want = name or default
            taken = {x.Label for x in doc().Objects if x is not o}
            lab, n = want, 2
            while lab in taken:
                lab = f"{want} {n}"
                n += 1
            o.Label = lab
        return o

    def finish(objs, tool, extra=None):
        """The tail of a tool that made or changed objects: recompute, refuse a broken one with nothing kept, the
        step, and each object's reading (one object: its own fields; several: objects)."""
        objs = [o for o in (objs if isinstance(objs, list) else [objs]) if o is not None]
        if not objs:
            doc().recompute()
            raise ToolError("failed", "Draft made nothing from that.")
        return picks.finish(s, tool, lambda: reading(objs[0]) if len(objs) == 1 else {"objects": [reading(o) for o in objs]},
                            objs=objs, refuse="Draft refused it: {msg} — nothing was kept.", extra=extra)

    def objs_of(refs, what="objects"):
        """The objects a list of names (or one name) means."""
        refs = picks.ref_list(refs, f"{what}: [names].")
        return [picks.find(doc(), r) for r in refs]

    # ---- what the entries (agentlink/data/tools.json) call by name ----

    def done(tool, read, extra=None):
        """The tail of a tool that answers its own fields (a layer): recompute, the step, then read()."""
        return picks.finish(s, tool, read, extra=extra)

    def find(ref, what="object"):
        """An object of the document by name or label."""
        return picks.find(doc(), ref, what)

    def resolve(ref):
        """A reference ("Body", "Body.Face6") as (label, element name or None, shape)."""
        return picks.resolve(s, ref)

    def gui():
        """Whether FreeCAD's window is up."""
        return bool(FreeCAD.GuiUp)

    def kind_of(o):
        """A Draft object's kind as its proxy says it ("Wire", "Circle", "Layer" …), "" for any other object."""
        return getattr(getattr(o, "Proxy", None), "Type", "")

    def is_seq(x):
        """A list or a tuple (Draft answers either)."""
        return isinstance(x, (list, tuple))

    def is_round(e):
        """Whether an edge is a circle or an arc of one."""
        return getattr(getattr(e, "Curve", None), "TypeId", "") == "Part::GeomCircle"

    # ---- labels ----

    def make_label(kw):
        """Draft's label from keywords only (which ones depends on what it shows)."""
        return Draft.make_label(**kw)

    def label_text(show, target, sub):
        """What a label of that kind reads off its target (or one element of it). Draft's label reads these
        itself when it recomputes; this is only for a release that left the text empty."""
        el = target.Shape.getElement(sub) if sub else target.Shape
        return {"area": lambda: f"{el.Area:.2f} mm²", "length": lambda: f"{el.Length:.2f} mm",
                "position": lambda: "{:.2f}, {:.2f}, {:.2f}".format(*el.BoundBox.Center),
                "name": lambda: target.Label}[show]()

    # ---- hatches ----

    def pattern_file(given):
        """The .pat file to hatch from: the one given (a local path), else FreeCAD's own FCPAT.pat."""
        if given:
            return paths.local(s, given)
        return os.path.join(FreeCAD.getResourceDir(), "Mod", "TechDraw", "PAT", "FCPAT.pat")

    def is_pat(path):
        """Whether path is a .pat file that is there."""
        return os.path.isfile(path) and path.lower().endswith(".pat")

    def pattern_names(path):
        """The patterns a .pat file holds, in its order (each starts a line with *name)."""
        with open(path, encoding="utf-8", errors="replace") as f:
            return [ln[1:].split(",")[0].strip() for ln in f if ln.startswith("*")]

    # ---- modify ----

    def new_radius(o, by):
        """Draft offsets a circle to a new radius, not by a vector: the radius of the circle through its first
        vertex moved by `by`."""
        sh = o.Shape
        start = sh.Vertexes[0].Point if sh.Vertexes else o.Placement.multVec(V(float(o.Radius), 0, 0))
        return (start + by - o.Placement.Base).Length

    def pointed(o):
        """A Draft wire's, B-spline's or Bezier curve's points where they are in the model, and its placement."""
        if "Points" not in o.PropertiesList or getattr(getattr(o, "Proxy", None), "Type", "") not in ("Wire", "BSpline", "BezCurve"):
            raise bad(f"{o.Label} is not a Draft wire, B-spline or Bezier curve (they hold points; draft_shape makes them, draft_from_sketch turns a sketch's lines into wires).")
        pl = o.Placement
        return [pl.multVec(p) for p in o.Points], pl

    def set_points(o, pts, pl):
        """Points given in the model, set on the object in its own placement."""
        inv = pl.inverse()
        o.Points = [inv.multVec(p) for p in pts]

    def edit_points(op, objs, a):
        """The point edits Draft does by hand: split, stretch, trim/extend, wire ↔ B-spline."""
        if op == "split":
            if len(objs) != 1:
                raise bad("split: one wire.")
            o = objs[0]
            pts, pl = pointed(o)
            closed = bool(getattr(o, "Closed", False))
            n = len(pts) if closed else len(pts) - 1  # a closed wire's last segment runs back to its first point
            k = a.get("edge", 0)
            if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= n:
                raise bad(f"edge: which segment of {o.Label}, 1 … {n} (segment 1 runs from its first point to its second).")
            if closed:
                # As Draft's Split does on a closed wire: that segment becomes a
                # wire of its own and the rest stays as one open wire (at is not used).
                p, q = pts[k - 1], pts[k % len(pts)]
                set_points(o, pts[k:] + pts[:k] if k < len(pts) else list(pts), pl)
                o.Closed = False
                other = Draft.make_wire([p, q], closed=False)
                other.Label = s.unique(f"{o.Label} split", other)
                return [o, other]
            p, q = pts[k - 1], pts[k]
            if a.get("at") is not None:
                # onto the segment, as Draft projects the picked point
                d = q - p
                t = (v3(a.get("at"), "at") - p).dot(d) / (d.Length ** 2)
                if not 1e-9 < t < 1 - 1e-9:
                    raise bad(f"at: lies beyond segment {k} of {o.Label}, which runs from {[round(c, 3) for c in p]} to {[round(c, 3) for c in q]} — a point between them, or leave at out for its middle.")
                cut = p + d * t
            else:
                cut = (p + q) * 0.5
            first, second = pts[:k] + [cut], [cut] + pts[k:]
            set_points(o, first, pl)
            other = Draft.make_wire(second, closed=False)
            other.Label = s.unique(f"{o.Label} split", other)
            return [o, other]
        if op == "stretch":
            box = a.get("box")
            if not (isinstance(box, list) and len(box) == 2):
                raise bad("box: [[xmin, ymin, zmin], [xmax, ymax, zmax]] — the points inside it move.")
            lo, hi = v3(box[0], "box"), v3(box[1], "box")
            by = v3(a.get("by"), "by")
            moved = 0
            for o in objs:
                pts, pl = pointed(o)
                new = []
                for p in pts:
                    inside = all(min(getattr(lo, c), getattr(hi, c)) - 1e-9 <= getattr(p, c) <= max(getattr(lo, c), getattr(hi, c)) + 1e-9 for c in "xyz")
                    new.append(p + by if inside else p)
                    moved += inside
                set_points(o, new, pl)
            if not moved:
                raise ToolError("failed", "No point lies inside the box: nothing was stretched.")
            return objs
        if op == "extend":
            by = float(a.get("length", 0))
            for o in objs:
                pts, pl = pointed(o)
                if len(pts) < 2:
                    continue
                if a.get("end", "end") == "start":
                    d = pts[0] - pts[1]
                    L = d.Length  # before normalize(), which changes d in place
                    if L + by <= 0:
                        raise bad("length: trims past the whole first segment.")
                    pts[0] = pts[1] + d.normalize() * (L + by)
                else:
                    d = pts[-1] - pts[-2]
                    L = d.Length
                    if L + by <= 0:
                        raise bad("length: trims past the whole last segment.")
                    pts[-1] = pts[-2] + d.normalize() * (L + by)
                set_points(o, pts, pl)
            return objs
        made = []
        for o in objs:
            pts, _pl = pointed(o)
            closed = bool(getattr(o, "Closed", False))
            n = Draft.make_bspline(pts, closed=closed) if op == "to_bspline" else Draft.make_wire(pts, closed=closed)
            label = o.Label
            made.append(n)
            if a.get("delete", True):
                # what used the old one now uses the new one
                picks.repoint(doc(), o, n)
                doc().removeObject(o.Name)
            n.Label = s.unique(label, n)
        return made

    def alive(o):
        """False for an object Draft has removed from the document."""
        try:
            return o.Document is not None and o.Name is not None
        except Exception:
            return False

    def results(op, r, objs, n0):
        """What a modify op made or changed, of what is still in the document: the objects added since n0
        (the point edits and join answer all their results themselves), else what Draft answered (an object,
        a list, or lists of them), else the objects themselves."""
        made = [] if op in ("split", "stretch", "extend", "to_bspline", "to_wire", "join") else [o for o in doc().Objects[n0:]]
        res = made or ([r] if r is not None and not isinstance(r, (list, tuple, bool)) else list(r) if isinstance(r, (list, tuple)) else objs)
        res = [(x[0] if x else None) if isinstance(x, (list, tuple)) else x for x in res if x is not None]
        res = [x for x in res if x is not None]
        return [x for x in res if alive(x) and hasattr(x, "Label")]

    def near_ends(res):
        """The two ends of different open wires among res that lie nearest each other, as (distance, label,
        label), or None. Edges are joined where their ends meet within FreeCAD's 1e-7 mm: ends a hair further
        apart (points typed to six decimals) stay two wires, and nothing else says why."""
        ends = []
        for x in res:
            sh = getattr(x, "Shape", None)
            for w in (getattr(sh, "Wires", None) or []) if sh is not None and not sh.Faces else []:
                if not w.isClosed():
                    vs = w.OrderedVertexes
                    ends += [(x.Label, vs[0].Point), (x.Label, vs[-1].Point)]
        return min(((p.distanceToPoint(q), la, lb) for i, (la, p) in enumerate(ends) for lb, q in ends[i + 1:] if la != lb), default=None)

    # ---- annotation styles ----
    # Draft 1.1 keeps start and end arrows apart and an arrow's type as its
    # index among the arrow names; it reads a style back comparing each value's
    # Python type with its default's (draftutils.utils.repair_annotation_style),
    # and a string where it wants a number is passed to float(). The keys, their
    # kinds and the arrow names are in draft_style's entry.

    def styles_in(meta):
        """The annotation styles in a document's Meta (Draft_Style_<name>: JSON), by name; one that does not
        read is empty."""
        styles = {}
        for k, v in meta.items():
            if k.startswith("Draft_Style_"):
                try:
                    styles[k[len("Draft_Style_"):]] = json.loads(v)
                except ValueError:
                    styles[k[len("Draft_Style_"):]] = {}
        return styles

    def style_users(of):
        """The annotations shown in that style (none without the window: styles live on view objects)."""
        out = []
        if FreeCAD.GuiUp:
            for o in doc().Objects:
                vo = getattr(o, "ViewObject", None)
                try:
                    if vo is not None and "AnnotationStyle" in vo.PropertiesList and vo.AnnotationStyle == of:
                        out.append(o)
                except Exception:
                    pass
        return out

    def offer_styles(vo, names):
        """The style list of an annotation is fixed when it is made: offer today's styles, keeping its own."""
        try:
            cur = vo.AnnotationStyle
        except Exception:
            cur = ""
        vo.AnnotationStyle = [""] + list(names)
        if cur in names:
            vo.AnnotationStyle = cur

    def restyled(users, vals):
        """What already wears a style follows it, as Draft's style editor does: each value set on each view
        object that has it (a colour with full alpha). The labels of those objects."""
        shown = []
        for o in users:
            vo = o.ViewObject
            for k, v in vals.items():
                if k in vo.PropertiesList:
                    try:
                        setattr(vo, k, (v | 0x000000FF) if vo.getTypeIdOfProperty(k) == "App::PropertyColor" else v)
                    except Exception:
                        pass
            shown.append(o.Label)
        return shown

    # Every tool of this file is an entry in agentlink/data/tools.json (those of group draft that name no
    # family); they run on these.
    helpers = {
        # the family's finishing code
        "doc": doc, "active": active, "named": named, "finish": finish, "done": done, "objs_of": objs_of, "find": find, "resolve": resolve,
        "unique": s.unique, "snapshot": s.snapshot, "step": lambda: len(s.steps), "gui": gui,
        # readers of arguments (each refuses a value that is not one, naming the argument)
        "vec": v3, "num": picks.num, "direction": picks.direction, "pl_of": pl_of,
        # FreeCAD's and Python's own, given short names
        "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "basename": os.path.basename, "dumps": json.dumps,
        # Draft and FreeCAD-API logic
        "kind_of": kind_of, "is_seq": is_seq, "is_round": is_round, "alive": alive, "make_label": make_label, "label_text": label_text,
        "pattern_file": pattern_file, "is_pat": is_pat, "pattern_names": pattern_names, "new_radius": new_radius, "edit_points": edit_points,
        "results": results, "near_ends": near_ends, "styles_in": styles_in, "style_users": style_users, "offer_styles": offer_styles,
        "restyled": restyled,
    }
    return runners.tools(GROUP, s, helpers)

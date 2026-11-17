# SPDX-License-Identifier: LGPL-2.1-or-later
# TechDraw, piece by piece: a page on a standard template and its title
# block, views and projection groups, section and detail views, the
# geometry of a view read back so a dimension can be put on a real edge or
# vertex, dimensions with tolerances and ISO 286 fits, geometric tolerance
# frames and datum symbols, notes, balloons and a spreadsheet as a table —
# all TechDraw's own objects, so the person carries on in the GUI — and the
# page written out (DXF by TechDraw; SVG and PDF drawn here from the same
# objects, as a page's own export needs the window).
#
# Page coordinates are TechDraw's: millimetres from the bottom-left corner,
# y up. A view's geometry is read in its own millimetres on the paper.

import glob
import json
import math
import os

import FreeCAD
import TechDraw  # noqa: F401 — the family stands on TechDraw; left out without it

from .. import gdt, iso286, sheets
from .. import paths
from .. import runners
from ..protocol import ToolError, bad
from . import picks

GROUP = "techdraw"
INFO = "TechDraw pages piece by piece: template and title block, views, projection groups, sections, details, dimensions on real edges with tolerances and fits, GD&T frames, datums, notes, balloons, tables, export to SVG, PDF and DXF."

V = FreeCAD.Vector
DIRS = {
    "front": ((0, -1, 0), (1, 0, 0)), "rear": ((0, 1, 0), (-1, 0, 0)), "top": ((0, 0, 1), (1, 0, 0)), "bottom": ((0, 0, -1), (1, 0, 0)),
    "right": ((1, 0, 0), (0, 1, 0)), "left": ((-1, 0, 0), (0, -1, 0)), "iso": ((1, -1, 1), (1, 1, 0)),
}
PROJ_ITEMS = {"front": "Front", "top": "Top", "bottom": "Bottom", "right": "Right", "left": "Left", "rear": "Rear",
              "iso": "FrontTopRight", "isoLeft": "FrontTopLeft", "isoBottomRight": "FrontBottomRight", "isoBottomLeft": "FrontBottomLeft"}
DIM_TYPES = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")
PAPERS = {  # name: (width, height) landscape, mm
    "A0": (1189, 841), "A1": (841, 594), "A2": (594, 420), "A3": (420, 297), "A4": (297, 210),
    "ANSIA": (279.4, 215.9), "Letter": (279.4, 215.9), "ANSIB": (431.8, 279.4), "Tabloid": (431.8, 279.4),
    "ANSIC": (558.8, 431.8), "ANSID": (863.6, 558.8), "ANSIE": (1117.6, 863.6),
}
GDT_PROP = "AgentLinkGdt"


def num(v, nd=4):
    return round(float(v), nd) + 0.0


def vec(v, what):
    if isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return V(*[float(x) for x in v])
    raise bad(f"{what}: [x, y, z] in mm.")


def pt2(v, what):
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return float(v[0]), float(v[1])
    raise bad(f"{what}: [x, y] in mm.")


# ---- templates ----


def template_root():
    return os.path.join(FreeCAD.getResourceDir(), "Mod", "TechDraw", "Templates")


def templates():
    return sorted(glob.glob(os.path.join(template_root(), "**", "*.svg"), recursive=True))


def find_template(paper, portrait=False, blank=False, standard=None):
    """The build's template for a paper: one with a title block unless
    blank. Template names differ from release to release, so they are
    matched by paper and orientation and ranked."""
    paper_key = {"Letter": "USLetter", "Tabloid": "ANSIB"}.get(paper, paper)
    orient = "Portrait" if portrait else "Landscape"
    cands = [p for p in templates() if os.path.basename(p).lower().startswith(paper_key.lower()) and (orient.lower() in os.path.basename(p).lower() or paper_key in ("ANSIB",) and not portrait)]
    if paper_key == "USLetter":
        cands += [p for p in templates() if os.path.basename(p).startswith("ANSIA_" + orient)]
    if standard:
        pref = [p for p in cands if f"{os.sep}{standard.upper()}{os.sep}" in p]
        cands = pref or cands

    def rank(p):
        b = os.path.basename(p).lower()
        if blank:
            return (0 if "blank" in b else 1 if "notitleblock" in b else 2, b)
        return (3 if "blank" in b or "notitleblock" in b else 0 if ("minimal" in b or "_td" in b or "7200" in b) else 1, b)

    cands.sort(key=rank)
    if not cands and paper == "A4" and not portrait and not blank:
        d = os.path.join(template_root(), "Default_Template_A4_Landscape.svg")
        cands = [d] if os.path.isfile(d) else []
    return cands[0] if cands else None


def presets_path():
    d = os.path.join(FreeCAD.getUserAppDataDir(), "AgentLink")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "titleblocks.json")


def load_presets(path=None):
    p = path or presets_path()
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_presets(data, path=None):
    with open(path or presets_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---- finding things ----


def set_enum(o, prop, want):
    """Set an enumeration by its item, matched without case or spaces:
    releases spell them differently ("First angle", "First Angle")."""
    key = want.lower().replace(" ", "").replace("_", "")
    for item in o.getEnumerationsOfProperty(prop) or []:
        if item.lower().replace(" ", "").replace("_", "") == key:
            setattr(o, prop, item)
            return item
    raise bad(f"{prop} {want!r}: this build offers {', '.join(o.getEnumerationsOfProperty(prop) or [])}.")


def ref_names(d):
    """A dimension's references as names: releases give (view, "Edge4") or
    (view, ("Edge4",))."""
    out = []
    for _, sub in d.References2D:
        out += list(sub) if isinstance(sub, (list, tuple)) else [sub]
    return out


def template_defaults(path):
    """The example values a template's editable fields carry in the file."""
    import re

    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}
    out = {}
    for m in re.finditer(r'freecad:editable="([^"]+)"[^>]*>\s*(?:<tspan[^>]*>)?([^<]*)', text):
        out[m.group(1)] = m.group(2).strip()
    return out


def pages(doc):
    return [o for o in doc.Objects if o.TypeId == "TechDraw::DrawPage"]


def page_of(doc, ref):
    all_ = pages(doc)
    if ref is None:
        if len(all_) == 1:
            return all_[0]
        raise (ToolError("not_found", "No TechDraw page: td_page { action: \"new\" } makes one.") if not all_ else bad(f"page: say which — {', '.join(p.Label for p in all_)}."))
    for p in all_:
        if ref in (p.Label, p.Name):
            return p
    raise ToolError("not_found", f"page {ref!r}: not here — the pages: {', '.join(p.Label for p in all_) or 'none'}.")


def obj_of(doc, ref, types=None, what="object"):
    for o in doc.Objects:
        if ref in (o.Label, o.Name) and (types is None or any(o.isDerivedFrom(t) for t in types)):
            return o
    raise ToolError("not_found", f"{what} {ref!r}: not here — td_list names what each page holds.")


def view_of(doc, ref):
    return obj_of(doc, ref, ["TechDraw::DrawViewPart"], "view")


def page_holding(o):
    for p in o.InList:
        if p.TypeId == "TechDraw::DrawPage":
            return p
        if p.isDerivedFrom("TechDraw::DrawProjGroup"):
            return page_holding(p)
    try:
        return o.findParentPage()
    except Exception:
        return None


def paper_size(page):
    t = page.Template
    try:
        return float(t.Width), float(t.Height)
    except Exception:
        return 297.0, 210.0


def wait(views_):
    from ..td_wait import wait_views

    return wait_views([v for v in views_ if v.isDerivedFrom("TechDraw::DrawViewPart")])


def edges_of(v):
    out, i = [], 0
    while i < 20000:
        try:
            e = v.getEdgeByIndex(i)
        except Exception:
            break
        if e is None:
            break
        out.append(e)
        i += 1
    return out


def vertices_of(v):
    out, i = [], 0
    while i < 20000:
        try:
            g = v.getVertexByIndex(i)
        except Exception:
            break
        if g is None:
            break
        out.append(g.Point if hasattr(g, "Point") else g)
        i += 1
    return out


def view_scale(v):
    try:
        return float(v.getScale()) if hasattr(v, "getScale") else float(v.Scale)
    except Exception:
        return float(v.Scale)


def source_shapes(v):
    import Part

    shapes = []
    for o in list(getattr(v, "Source", []) or []) + list(getattr(v, "XSource", []) or []):
        sh = getattr(o, "Shape", None)
        if sh is not None and not sh.isNull():
            shapes.append(sh)
    return Part.makeCompound(shapes) if shapes else None


def frame_of(v, cache):
    """How a 3D point lands in the view's geometry: (scale, sy, tx, ty)
    with view = (s·px + tx, s·sy·py + ty) for px, py = projectPoint(p).
    Releases centre, scale and flip a view's geometry their own ways, so the
    frame is fitted on the source's vertices against the view's."""
    if v.Name in cache:
        return cache[v.Name]
    sh = source_shapes(v)
    verts = vertices_of(v)
    if sh is None or not verts or not box_ok(sh):
        cache[v.Name] = None
        return None
    pts3 = [x.Point for x in sh.Vertexes][:400] or [sh.BoundBox.Center]
    proj = [v.projectPoint(p) for p in pts3]
    try:
        c = v.projectPoint(v.getGeometricCenter() if hasattr(v, "getGeometricCenter") else sh.BoundBox.Center)
    except Exception:
        c = v.projectPoint(sh.BoundBox.Center)
    sc = view_scale(v)
    best = None
    # The indexed geometry (getVertexByIndex, getEdgeByIndex) is the view's
    # own, centred on the source. FreeCAD 1.1.3 gives it unscaled and y up
    # (src/Mod/TechDraw/App/DrawViewPartPyImp.cpp: invertY of the stored
    # y-down geometry, over the scale); other releases scaled, or y down. The
    # fit finds which (sy); to_paper and flip_y turn it to paper y down by it.
    # A symmetric part fits both ways alike: the first is kept, and either
    # way the mark lands where it was asked (the same frame places it).
    for s in (sc, 1.0):
        for sy in (-1, 1):
            for centred in (True, False):
                tx = -s * c.x if centred else 0.0
                ty = -s * sy * c.y if centred else 0.0
                err = 0.0
                for p in proj:
                    X, Y = s * p.x + tx, s * sy * p.y + ty
                    err += min(math.hypot(X - q.x, Y - q.y) for q in verts)
                cand = (err / len(proj), (s, sy, tx, ty))
                if best is None or cand[0] < best[0] - 1e-3 * max(1.0, sc):
                    best = cand
    cache[v.Name] = best[1]
    return best[1]


def gscale(v, cache):
    """Geometry units per mm on the part, as the view's indexed geometry
    holds them: some releases keep it scaled to the paper, some not (the
    visible edges are always on the paper)."""
    fr = frame_of(v, cache)
    return fr[0] if fr else view_scale(v)


def box_ok(sh):
    """Whether a shape has a bounding box with a size (an empty compound's
    is invalid: FreeCAD raises "Cannot determine diagonal length of invalid
    bounding box" when asked its diagonal)."""
    try:
        bb = sh.BoundBox
        return bool(bb.isValid()) and bb.DiagonalLength >= 0
    except Exception:
        return False


def to_paper(v, cache, xy):
    """A point of the view's indexed geometry in paper mm from its centre,
    y down (as the visible edges and the page's svg hold it): the frame says
    which way the indexed geometry's y runs (y up from FreeCAD 1.1)."""
    fr = frame_of(v, cache)
    k = view_scale(v) / (fr[0] if fr else view_scale(v))
    ysign = -fr[1] if fr else 1
    return xy[0] * k, xy[1] * k * ysign + 0.0  # no -0.0


def to_view(fr, v, p3):
    p = v.projectPoint(p3)
    s, sy, tx, ty = fr
    return s * p.x + tx, s * sy * p.y + ty


def edge_info(e, sc):
    cu = getattr(e, "Curve", None)
    name = type(cu).__name__ if cu is not None else "Edge"
    out = {"kind": {"Line": "line", "LineSegment": "line", "Circle": "circle", "ArcOfCircle": "arc", "Ellipse": "ellipse", "BSplineCurve": "spline"}.get(name, name.lower())}
    try:
        a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
        if out["kind"] == "line":
            out["from"], out["to"] = [num(a.x / sc, 3), num(a.y / sc, 3)], [num(b.x / sc, 3), num(b.y / sc, 3)]
            out["length"] = num(e.Length / sc, 3)
    except Exception:
        pass
    if hasattr(cu, "Radius") and hasattr(cu, "Center"):
        out["center"] = [num(cu.Center.x / sc, 3), num(cu.Center.y / sc, 3)]
        out["diameter"] = num(2 * cu.Radius / sc, 3)
        if abs(e.Length - 2 * math.pi * cu.Radius) < 1e-6 * max(1.0, cu.Radius):
            out["kind"] = "circle"
        elif out["kind"] == "circle":
            out["kind"] = "arc"
    return out


def arc_turn(e):
    """How much of a turn a round edge of a view covers: 1.0 a whole
    circle, 0.5 a slot's end. None for an edge that is not round."""
    cu = getattr(e, "Curve", None)
    try:
        r = float(cu.Radius)
        return e.Length / (2 * math.pi * r) if r > 0 else None
    except Exception:
        return None


def whole_circles(es):
    """Indexes of the round edges that are a whole circle, or that with the
    other edges on the same centre and radius make one up (the hidden-line
    pass can hand a hole's circle over in pieces). A slot's two ends lie on
    different centres and stay arcs."""
    groups = {}
    two_pi = 2 * math.pi
    for i, e in enumerate(es):
        t = arc_turn(e)
        if t is None:
            continue
        cu = e.Curve
        ctr = getattr(cu, "Location", None) or cu.Center
        span = None  # a whole circle by itself
        if t < 0.999:
            # where round the centre it runs: about its middle, half its
            # turn either way (two arcs lying on one another — a visible
            # and a hidden rim — cover the same stretch, not a circle)
            try:
                m = e.valueAt((e.FirstParameter + e.LastParameter) / 2)
            except Exception:
                continue
            mid = math.atan2(m.y - ctr.y, m.x - ctr.x) % two_pi
            span = (mid - t * math.pi, mid + t * math.pi)
        groups.setdefault((round(ctr.x, 3), round(ctr.y, 3), round(float(cu.Radius), 3)), []).append((i, span))
    out = set()
    for g in groups.values():
        if not any(sp is None for _, sp in g):
            cuts = []
            for _, (a0, a1) in g:
                if a0 < 0:
                    cuts += [(a0 + two_pi, two_pi), (0.0, a1)]
                elif a1 > two_pi:
                    cuts += [(a0, two_pi), (0.0, a1 - two_pi)]
                else:
                    cuts.append((a0, a1))
            covered, reach = 0.0, 0.0
            for a0, a1 in sorted(cuts):
                if a1 > reach:
                    covered += a1 - max(a0, reach)
                    reach = a1
            if covered < 0.999 * two_pi:
                continue
        out.update(i for i, _ in g)
    return out


def resolve_ref(v, r, cache, want="any"):
    """A view geometry reference: "Edge3" | "Vertex5", or { point: [x,y,z] }
    (the nearest vertex), { circle: { diameter, near } }, { edge: { through:
    [p, q] } } (the edge nearest both points' middle) — returns "EdgeN" /
    "VertexN". want "circle": a { circle } must be a whole circle (a
    diameter callout), so an arc of the same size — a slot's end, a fillet —
    is never taken for a hole."""
    if isinstance(r, str):
        if r.startswith(("Edge", "Vertex")) and r[4 if r.startswith("Edge") else 6:].isdigit():
            n = int(r[4:] if r.startswith("Edge") else r[6:])
            lst = edges_of(v) if r.startswith("Edge") else vertices_of(v)
            if n >= len(lst):
                raise ToolError("not_found", f"{r}: {v.Label} has {len(lst)} {'edges' if r.startswith('Edge') else 'vertices'} (td_geometry lists them).")
            return r
        raise bad(f"reference {r!r}: \"Edge3\", \"Vertex5\", or {{ point }}, {{ circle }}, {{ edge }}.")
    if not isinstance(r, dict):
        raise bad("reference: \"Edge3\" | \"Vertex5\" | { point: [x,y,z] } | { circle: { diameter, near } } | { edge: { through: [p, q] } }.")
    fr = frame_of(v, cache)
    if fr is None:
        raise ToolError("unavailable", f"{v.Label} has no geometry yet: its bodies are empty or hidden, or its lines are still being worked out — td_list shows its edge count; recompute, then again.")
    sc = fr[0]
    if "point" in r:
        q = to_view(fr, v, vec(r["point"], "point"))
        verts = vertices_of(v)
        k = min(range(len(verts)), key=lambda i: math.hypot(verts[i].x - q[0], verts[i].y - q[1]))
        d = math.hypot(verts[k].x - q[0], verts[k].y - q[1]) / sc
        if d > max(0.05, 0.002 * (source_shapes(v).BoundBox.DiagonalLength)):  # frame_of: a valid box
            raise ToolError("not_found", f"No vertex of {v.Label} at {r['point']} (nearest {d:.3g} mm off): a hidden point, or one this view does not draw.")
        return f"Vertex{k}"
    if "center" in r or "centre" in r:
        # a circle's centre: its vertex if the view has one there, else a
        # cosmetic vertex made at it (it follows the part)
        c = r.get("center") or r.get("centre") or {}
        en = resolve_ref(v, {"circle": c}, cache)
        cu = edges_of(v)[int(en[4:])].Curve
        ctr = getattr(cu, "Location", None) or cu.Center
        verts = vertices_of(v)
        for k, q in enumerate(verts):
            if math.hypot(q.x - ctr.x, q.y - ctr.y) < 1e-3 * max(1.0, sc):
                return f"Vertex{k}"
        src = source_shapes(v)
        best = None
        for e in src.Edges:
            ec = getattr(e, "Curve", None)
            if ec is None or type(ec).__name__ != "Circle":
                continue
            loc = getattr(ec, "Location", None) or ec.Center
            gx, gy = to_view(fr, v, loc)
            dd = math.hypot(gx - ctr.x, gy - ctr.y)
            if best is None or dd < best[0]:
                best = (dd, loc)
        if best is None:
            raise ToolError("not_found", "That circle's centre is not found on the part.")
        v.makeCosmeticVertex3d(best[1])
        v.recompute()
        verts = vertices_of(v)
        k = min(range(len(verts)), key=lambda i: math.hypot(verts[i].x - ctr.x, verts[i].y - ctr.y))
        return f"Vertex{k}"
    if "circle" in r:
        c = r["circle"] or {}
        dia = c.get("diameter")
        near = to_view(fr, v, vec(c["near"], "near")) if c.get("near") is not None else None
        hits = []
        es = edges_of(v)
        whole = whole_circles(es) if want == "circle" else None
        arcs = 0
        for i, e in enumerate(es):
            cu = getattr(e, "Curve", None)
            if not (hasattr(cu, "Radius") and (hasattr(cu, "Location") or hasattr(cu, "Center"))):
                continue
            if dia is not None and abs(2 * cu.Radius / sc - float(dia)) > max(0.01, 0.002 * float(dia)):
                continue
            if whole is not None and i not in whole:
                arcs += 1
                continue
            ctr = getattr(cu, "Location", None) or cu.Center
            hits.append((math.hypot(ctr.x - near[0], ctr.y - near[1]) if near else 0.0, i))
        if not hits and arcs:
            raise ToolError("not_found", f"No whole circle{f' of ⌀{dia}' if dia else ''} in {v.Label}: the {arcs} round edge{'s' if arcs != 1 else ''} of that size {'are arcs' if arcs != 1 else 'is an arc'} (a slot's end, a fillet), and a diameter is for a whole circle — "
                            f"type: \"radius\" dimensions an arc; td_geometry {{ kind: \"circles\" }} lists each as circle or arc.")
        if not hits:
            raise ToolError("not_found", f"No circle{f' of ⌀{dia}' if dia else ''} in {v.Label} — td_geometry {{ kind: \"circles\" }} lists them.")
        hits.sort()
        if len(hits) > 1 and near is None and len({h[0] for h in hits}) == 1:
            raise bad(f"{len(hits)} circles match in {v.Label}: add near: [x, y, z] (a point on the part by the one meant) inside circle.")
        return f"Edge{hits[0][1]}"
    if "edge" in r:
        th = (r["edge"] or {}).get("through")
        if not (isinstance(th, list) and len(th) == 2):
            raise bad("edge: { through: [[x,y,z], [x,y,z]] }, two points on it.")
        a, b = to_view(fr, v, vec(th[0], "through")), to_view(fr, v, vec(th[1], "through"))
        best = None
        import Part

        for i, e in enumerate(edges_of(v)):
            d = sum(e.distToShape(Part.Vertex(V(x, y, 0)))[0] for x, y in (a, b))
            if best is None or d < best[0]:
                best = (d, i)
        if best is None or best[0] / sc > 0.1:
            raise ToolError("not_found", f"No edge of {v.Label} through those points.")
        return f"Edge{best[1]}"
    raise bad("reference: one of point, circle, edge.")


# ---- the page as drawn here (export) ----


def page_sheet(doc, page):
    """The page as lines and text for sheets.Sheet: views (visible and
    hidden edges), dimensions, symbols we made, leaders, notes, balloons,
    tables and a frame with the title block's fields."""
    W, H = paper_size(page)
    sh = sheets.Sheet(W, H, page.Label)
    sh.frame(10.0)
    fields = {}
    try:
        fields = dict(page.Template.EditableTexts)
    except Exception:
        pass
    vals = [(k, v) for k, v in fields.items() if str(v).strip()][:10]
    if vals:
        x1, y1 = W - 10, H - 10
        w, ch = 150.0, 7.0
        rows = (len(vals) + 1) // 2
        x0, y0 = x1 - w, y1 - ch * rows
        sh.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "visible", closed=True)
        for r in range(1, rows):
            sh.line([(x0, y0 + r * ch), (x1, y0 + r * ch)], "thin")
        sh.line([(x0 + w / 2, y0), (x0 + w / 2, y1)], "thin")
        for i, (k, v) in enumerate(vals):
            cx, cy = x0 + (i % 2) * w / 2, y0 + (i // 2) * ch
            sh.text(cx + 1.2, cy + 2.2, 1.5, k.upper()[:28])
            sh.text(cx + 1.2, cy + ch - 1.3, 2.4, str(v)[:34])
    skipped = []
    for o in page.Views:
        items = [o] + (list(o.Views) if o.isDerivedFrom("TechDraw::DrawProjGroup") else [])
        for v in items:
            try:
                draw_item(doc, sh, v, H)
            except Exception as e:
                skipped.append(f"{v.Label}: {e}")
    return sh, skipped


def draw_arch(sh, v, H):
    """A BIM section drawn here: what the plane cuts (heavy) and what lies
    beyond it, seen from the plane (thin) — the plane's own frame on the page."""
    import Part

    sec = v.Source
    if sec is None:
        raise ValueError("an Arch view with no section plane")
    pl = sec.Placement
    objs = [o for o in getattr(sec, "Objects", []) if isinstance(getattr(o, "Shape", None), Part.Shape) and not o.Shape.isNull()]
    # every object inside a level or building, not the containers themselves
    seen, flat = set(), []
    while objs:
        o = objs.pop()
        if o.Name in seen:
            continue
        seen.add(o.Name)
        kids = getattr(o, "Group", None)
        if kids:
            objs += [k for k in kids if isinstance(getattr(k, "Shape", None), Part.Shape)]
        elif o.Shape.Solids:
            flat.append(o)
    if not flat:
        raise ValueError("the section cuts no solid BIM objects")
    # the plane's frame: its X and Y on the page, looking against its normal
    inv = pl.inverse()
    shapes = [o.Shape.transformGeometry(inv.toMatrix()) for o in flat]
    lines = []
    big = max([s.BoundBox.DiagonalLength for s in shapes if box_ok(s)] or [0.0]) * 4 + 1
    beyond = Part.makeBox(big, big, big, FreeCAD.Vector(-big / 2, -big / 2, -big))
    belows = []
    for s in shapes:
        for w in s.slice(FreeCAD.Vector(0, 0, 1), 0.0):
            for e in w.Edges:
                lines.append(("cut", [(p.x, p.y) for p in e.discretize(Deflection=0.5)]))
        try:
            below = s.common(beyond)
        except Exception:
            continue
        if not below.isNull() and below.Solids:
            belows += below.Solids
    if belows:
        # all at once, so what is nearer hides what is behind it
        res = TechDraw.projectEx(Part.makeCompound(belows), FreeCAD.Vector(0, 0, 1))
        for i in (0, 1, 3):
            if not res[i].isNull():
                for e in res[i].Edges:
                    lines.append(("thin", [(p.x, p.y) for p in e.discretize(Deflection=0.5)]))
    if not lines:
        raise ValueError("the section plane misses the objects")
    xs = [x for _, pts in lines for x, _ in pts]
    ys = [y for _, pts in lines for _, y in pts]
    X, Y = abs_xy(v)
    sh.place(lines, (min(xs), min(ys), max(xs), max(ys)), (X, H - Y), float(v.Scale))
    sh.text(X, H - Y + (max(ys) - min(ys)) * float(v.Scale) / 2 + 6, 3.0, f"{v.Label.upper()}  SCALE {sheets.scale_text(float(v.Scale))}", "middle")


MARKS_PROP = "AgentLinkCenterMarks"
HATCH_PROP = "AgentLinkHatch"
WELD_PROP = "AgentLinkWeld"
COSMETIC_PROP = "AgentLinkCosmetic"
# FreeCAD's line styles for cosmetic edges: (style, weight mm)
NATIVE_STYLE = {"thin": (1, 0.18), "visible": (1, 0.35), "hidden": (2, 0.18), "center": (4, 0.18)}


SPECIAL_PROP = "AgentLinkSpecial"


def special_length(v, spec, cache):
    """The true length a special dimension shows, read from the view as it
    is now (not when the dimension was made): an arc's length, or the model
    edge an axonometric view edge shows. None where the edge is gone."""
    es = edges_of(v)
    try:
        e = es[int(spec["edge"][4:])]
    except Exception:
        return None
    if spec["kind"] == "arc_length" and spec.get("src"):
        # Anchored to the part's own arc when it was made: read from the
        # model, so neither a new scale nor a release that splits the view's
        # circle differently on the next rebuild (1.0) moves the index.
        L = model_arc_length(v, spec["src"])
        if L is not None:
            return L
    g = gscale(v, cache) or 1.0
    if spec["kind"] == "arc_length":
        if not hasattr(getattr(e, "Curve", None), "Radius"):
            return None
        return e.Length / g
    # axo_length: the source's straight edge whose ends land on this one's
    fr = frame_of(v, cache)
    src = source_shapes(v)
    if fr is None or src is None:
        return None
    a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
    tol = max(1e-3, 1e-3 * e.Length)
    best = None
    for ed in src.Edges:
        if ed.Curve.__class__.__name__ not in ("Line", "LineSegment") or len(ed.Vertexes) < 2:
            continue
        p, q = (to_view(fr, v, x.Point) for x in (ed.Vertexes[0], ed.Vertexes[-1]))
        d1 = math.hypot(p[0] - a.x, p[1] - a.y) + math.hypot(q[0] - b.x, q[1] - b.y)
        d2 = math.hypot(p[0] - b.x, p[1] - b.y) + math.hypot(q[0] - a.x, q[1] - a.y)
        d = min(d1, d2)
        if d < 4 * tol and (best is None or d < best[0]):
            best = (d, ed.Length)
    return best[1] if best else None


def _circular_edges(v):
    src = source_shapes(v)
    if src is None:
        return []
    return [ed for ed in src.Edges if hasattr(getattr(ed, "Curve", None), "Radius") and hasattr(ed.Curve, "Center")]


def model_arc_anchor(v, e, cache):
    """The part's arc a view's arc shows: its centre and radius in 3D and the
    share of its length the view's arc covers. None when no source arc
    lands on it."""
    fr = frame_of(v, cache)
    if fr is None:
        return None
    s = abs(fr[0]) or 1.0
    try:
        c2, r2 = e.Curve.Center, float(e.Curve.Radius)
    except Exception:
        return None
    best = None
    for ed in _circular_edges(v):
        p = to_view(fr, v, ed.Curve.Center)
        d = math.hypot(p[0] - c2.x, p[1] - c2.y) + abs(float(ed.Curve.Radius) * s - r2)
        if best is None or d < best[0]:
            best = (d, ed)
    if best is None or best[0] > max(1e-2, 2e-2 * r2) or best[1].Length <= 0:
        return None
    ed = best[1]
    share = (e.Length / s) / ed.Length
    if not 0 < share <= 1.0 + 1e-3:
        return None
    c = ed.Curve.Center
    return {"center": [c.x, c.y, c.z], "radius": float(ed.Curve.Radius), "share": min(1.0, share)}


def model_arc_length(v, src):
    """The anchored arc's length on the part as the model is now: the arc
    nearest the anchor's centre (a resized hole keeps its centre), times the
    share the view showed."""
    import FreeCAD

    want = FreeCAD.Vector(*src["center"])
    best = None
    for ed in _circular_edges(v):
        d = (ed.Curve.Center - want).Length + 0.1 * abs(float(ed.Curve.Radius) - float(src["radius"]))
        if best is None or d < best[0]:
            best = (d, ed)
    if best is None or best[0] > max(0.5, 0.5 * float(src["radius"])):
        return None
    return best[1].Length * float(src["share"])


def refresh_special(doc, cache=None):
    """Re-read every special dimension's length (arc, axonometric) from the
    view as it is now, so a changed part or scale shows. Returns the
    dimensions whose edge is gone (their text says so)."""
    cache = {} if cache is None else cache
    lost = []
    for d in doc.Objects:
        if SPECIAL_PROP not in getattr(d, "PropertiesList", []) or not getattr(d, SPECIAL_PROP):
            continue
        try:
            spec = json.loads(getattr(d, SPECIAL_PROP))
            v = doc.getObject(spec["view"])
            L = special_length(v, spec, cache) if v is not None else None
        except Exception:
            L = None
        nd = int(spec.get("decimals", 2)) if isinstance(spec, dict) else 2
        pre = "◠ " if isinstance(spec, dict) and spec.get("kind") == "arc_length" else ""
        text = f"{pre}{L:.{nd}f}" if L is not None else f"{pre}? (edge gone: td_dim_special again)"
        if L is None:
            lost.append(d.Label)
        if d.FormatSpec != text:
            d.Arbitrary = True
            d.FormatSpec = text
    return lost


def _canon(v, x, y):
    """A paper point (mm from the view's centre, y down, as the visible
    edges hold it) as FreeCAD keeps cosmetic geometry: unscaled, unrotated,
    y up."""
    sc = view_scale(v) or 1.0
    px, py = x / sc, -y / sc
    rot = math.radians(float(getattr(v, "Rotation", 0) or 0))
    if rot:
        c, s_ = math.cos(-rot), math.sin(-rot)
        px, py = px * c - py * s_, px * s_ + py * c
    return FreeCAD.Vector(px, py, 0)


def native_ok():
    """FreeCAD 1.0 keeps a removed cosmetic edge in the view's geometry and
    aborts on the next edge lookup, so FreeCAD's own cosmetic edges are made
    from 1.1 on only (before it the lines show in td_export only)."""
    try:
        major, minor = (int(x) for x in FreeCAD.Version()[:2])
        return (major, minor) >= (1, 1)
    except Exception:
        return False


def native_cosmetic(v, prim):
    """FreeCAD's own cosmetic edges for one of td_cosmetic's figures, so it
    shows in the window and in TechDraw's own PDF/SVG export too. Returns the
    edges' tags ([] where this FreeCAD cannot make them)."""
    tags = []
    if not native_ok():
        return tags
    style, weight = NATIVE_STYLE.get(prim.get("style", "thin"), (1, 0.18))
    try:
        if prim.get("circle"):
            cx, cy, r = prim["circle"]
            tags.append(v.makeCosmeticCircle(_canon(v, cx, cy), r / (view_scale(v) or 1.0)))
        else:
            pts = list(prim["pts"])
            if prim.get("closed") and len(pts) > 2:
                pts.append(pts[0])
            for p, q in zip(pts, pts[1:]):
                tags.append(v.makeCosmeticLine(_canon(v, *p), _canon(v, *q)))
    except Exception:
        return tags
    for t in tags:
        try:
            ce = v.getCosmeticEdge(t)
            fm = ce.Format
            if isinstance(fm, dict):  # 1.0: {style, weight, color, visible}
                fm = dict(fm, style=style, weight=weight)
            else:
                fm = list(fm)
                fm[0], fm[1] = style, weight
                fm = tuple(fm)
            ce.Format = fm
        except Exception:
            pass
    return tags


def drop_native(v, prim):
    for t in prim.pop("tags", []) or []:
        try:
            v.removeCosmeticEdge(t)
        except Exception:
            pass


def paper_polys(v, faces, X, Y, H):
    """3D faces as polygons on the paper, through the view's own projection."""
    cache = {}
    fr = frame_of(v, cache)
    if fr is None:
        return []
    out = []
    for f in faces:
        for w in f.Wires:
            pts = w.discretize(Deflection=0.02)  # the wire's own order and direction
            poly = []
            for p in pts:
                gx, gy = to_paper(v, cache, to_view(fr, v, p))
                poly.append((X + gx, H - Y + gy))
            if len(poly) >= 3:
                out.append(poly)
    return out


def hatch_regions(v, X, Y, H):
    """What to hatch in a view: a section's cut faces (unless its hatch is off),
    and faces given by td_hatch. [(polygons, spacing, angle)]"""
    import Part

    out = []
    try:
        if v.isDerivedFrom("TechDraw::DrawViewSection") and str(getattr(v, "CutSurfaceDisplay", "SvgHatch")) not in ("None", "Hide"):
            src = source_shapes(v)
            if src is not None:
                o, n = V(v.SectionOrigin), V(v.SectionNormal)
                wires = src.slice(n, n.dot(o))
                if wires:
                    try:
                        faces = Part.makeFace(wires, "Part::FaceMakerBullseye").Faces
                    except Exception:
                        faces = [Part.Face(w) for w in wires if w.isClosed()]
                    polys = paper_polys(v, faces, X, Y, H)
                    if polys:
                        out.append((polys, 2.5, 45.0))
    except Exception:
        pass
    if HATCH_PROP in v.PropertiesList and getattr(v, HATCH_PROP):
        try:
            spec = json.loads(getattr(v, HATCH_PROP))
            src = source_shapes(v)
            faces = [src.getElement(f) for f in spec.get("faces", [])] if src is not None else []
            polys = paper_polys(v, faces, X, Y, H)
            if polys:
                out.append((polys, float(spec.get("spacing", 2.5)), float(spec.get("angle", 45))))
        except Exception as e:
            raise ValueError(f"its hatching could not be drawn ({e})") from None
    return out


def circle_centres(v):
    """The view's whole circles (and arcs past a half turn), on the paper: [((x, y), r)], one per centre and size."""
    import Part

    seen, out = set(), []
    for e in v.getVisibleEdges() or []:
        c = getattr(e, "Curve", None)
        if not isinstance(c, Part.Circle):
            continue
        span = abs(e.LastParameter - e.FirstParameter)
        if span < math.pi * 1.01:
            continue
        key = (round(c.Location.x, 2), round(c.Location.y, 2), round(c.Radius, 2))
        if key in seen:
            continue
        seen.add(key)
        out.append(((c.Location.x, c.Location.y), c.Radius))
    return out


def shifted_svg(fig):
    """A figure drawn about a base point (origin = its top-left from the
    base) as an svg whose own top-left is (0, 0)."""
    ox, oy = fig.origin
    g = gdt.Figure()
    g.lines = [([(x - ox, y - oy) for x, y in pts], c) for pts, c in fig.lines]
    g.circles = [(cx - ox, cy - oy, r) for cx, cy, r in fig.circles]
    g.texts = [(x - ox, y - oy, h, s_, an) for x, y, h, s_, an in fig.texts]
    g.filled = [[(x - ox, y - oy) for x, y in pts] for pts in fig.filled]
    g.w, g.h = fig.w, fig.h
    return g.svg()


ISO_COARSE = {1.6: 0.35, 2: 0.4, 2.5: 0.45, 3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2.0, 16: 2.0, 20: 2.5, 24: 3.0, 30: 3.5, 36: 4.0, 42: 4.5, 48: 5.0}


def coarse_pitch(d):
    k = min(ISO_COARSE, key=lambda x: abs(x - d))
    return ISO_COARSE[k] if abs(k - d) < 0.6 else max(0.25, round(d * 0.125, 2))


def abs_xy(v):
    """A view's centre on the page (mm, y up), through a group it sits in."""
    x, y = float(v.X), float(v.Y)
    for p in v.InList:
        if p.isDerivedFrom("TechDraw::DrawProjGroup"):
            return x + float(p.X), y + float(p.Y)
    return x, y


def edge_key(e):
    """An edge by where it lies (paper mm, rounded): ends, or a circle."""
    cu = getattr(e, "Curve", None)
    if isinstance(cu, __import__("Part").Circle) and len(e.Vertexes) < 2:
        return ("c", round(cu.Center.x, 2), round(cu.Center.y, 2), round(cu.Radius, 2))
    a, b = (e.Vertexes[0].Point, e.Vertexes[-1].Point) if e.Vertexes else (None, None)
    if a is None:
        return None
    k = sorted([(round(a.x, 2), round(a.y, 2)), (round(b.x, 2), round(b.y, 2))])
    return ("l",) + tuple(k)


def cosmetic_keys(v):
    """Where td_cosmetic's native edges lie, to keep them out of the visible
    lines (they are drawn from the JSON, in their own style)."""
    if COSMETIC_PROP not in v.PropertiesList or not getattr(v, COSMETIC_PROP):
        return set()
    keys = set()
    for c in json.loads(getattr(v, COSMETIC_PROP)):
        if not c.get("tags"):
            continue
        if c.get("circle"):
            cx, cy, r = c["circle"]
            keys.add(("c", round(cx, 2), round(cy, 2), round(r, 2)))
            continue
        pts = list(c["pts"]) + ([c["pts"][0]] if c.get("closed") else [])
        for p, q in zip(pts, pts[1:]):
            keys.add(("l",) + tuple(sorted([(round(p[0], 2), round(p[1], 2)), (round(q[0], 2), round(q[1], 2))])))
    return keys


def draw_item(doc, sh, v, H):
    t = v.TypeId
    if v.isDerivedFrom("TechDraw::DrawProjGroup"):
        return
    if v.isDerivedFrom("TechDraw::DrawViewPart"):
        X, Y = abs_xy(v)
        # geometry is Qt-inverted (y down), the page's svg too: y = H - Y + gy
        for kind, getter in (("hidden", "getHiddenEdges"), ("visible", "getVisibleEdges")):
            if kind == "hidden" and not getattr(v, "HardHidden", False) and not getattr(v, "SmoothHidden", False):
                continue
            ours = cosmetic_keys(v) if kind == "visible" else set()
            for e in getattr(v, getter)() or []:
                if ours and edge_key(e) in ours:
                    continue  # one of td_cosmetic's, drawn below in its own style
                pts = [(X + p.x, H - Y + p.y) for p in e.discretize(Deflection=0.05)] if e.Length > 1e-6 else []
                if len(pts) >= 2:
                    sh.line(pts, kind)
        for polys, spacing, angle in hatch_regions(v, X, Y, H):
            for p, q in sheets.hatch(polys, spacing, angle):
                sh.line([p, q], "thin")
            for poly in polys:
                sh.line(poly, "visible", closed=True)
        if COSMETIC_PROP in v.PropertiesList and getattr(v, COSMETIC_PROP):
            for c in json.loads(getattr(v, COSMETIC_PROP)):
                pts = [(X + x, H - Y + y) for x, y in c["pts"]]
                if len(pts) >= 2:
                    sh.line(pts, c.get("style", "thin"), closed=bool(c.get("closed")))
        ext = float(getattr(v, MARKS_PROP, 0) or 0) if MARKS_PROP in v.PropertiesList else 0
        if ext > 0:
            for c, r in circle_centres(v):
                cx, cy = X + c[0], H - Y + c[1]
                sh.line([(cx - r - ext, cy), (cx + r + ext, cy)], "center")
                sh.line([(cx, cy - r - ext), (cx, cy + r + ext)], "center")
        for o in v.InList:
            try:
                if o.isDerivedFrom("TechDraw::DrawViewSection") and o.BaseView == v:
                    cut_line(sh, v, o, X, Y, H)
                elif o.isDerivedFrom("TechDraw::DrawViewDetail") and o.BaseView == v:
                    sc_ = view_scale(v)
                    c = (X + float(o.AnchorPoint.x) * sc_, H - (Y + float(o.AnchorPoint.y) * sc_))
                    r = float(o.Radius) * sc_
                    sh.circle(c[0], c[1], r, "thin", n=48)
                    sh.text(c[0] + r * 0.75 + 1.5, c[1] - r * 0.75 - 1.0, 3.5, str(o.Reference))
            except Exception:
                pass
        cap = getattr(v, "Caption", "") or ""
        label = ""
        if v.isDerivedFrom("TechDraw::DrawViewSection"):
            label = f"SECTION {v.SectionSymbol}-{v.SectionSymbol}"
        elif v.isDerivedFrom("TechDraw::DrawViewDetail"):
            label = f"DETAIL {v.Reference}"
        if label or cap:
            try:
                bb = v.getVisibleEdges() and __import__("Part").makeCompound(v.getVisibleEdges()).BoundBox
                below = (H - Y + bb.YMax + 6) if bb else H - Y + 20
            except Exception:
                below = H - Y + 20
            sc = view_scale(v)
            sh.text(X, below, 3.0, (label + (f"  SCALE {sheets.scale_text(sc)}" if label else "")) or cap, "middle")
        return
    if t == "TechDraw::DrawViewDimension":
        draw_dim(sh, v, H)
        return
    if t == "TechDraw::DrawViewSpreadsheet":
        draw_table(doc, sh, v, H)
        return
    if t == "TechDraw::DrawViewArch":
        draw_arch(sh, v, H)
        return
    if v.isDerivedFrom("TechDraw::DrawViewSymbol"):
        rows = getattr(v, GDT_PROP, "") if GDT_PROP in v.PropertiesList else ""
        if not rows:
            raise ValueError("a symbol not made by these tools is left out of the file")
        data = json.loads(rows)
        if data.get("kind") == "frame":
            fig = gdt.frame(data["rows"], data.get("h", 3.5))
        elif data.get("kind") == "finish":
            fig = gdt.finish(data.get("ra", ""), data.get("removal", "required"), data.get("process", ""), data.get("lay", ""), data.get("allowance", ""), data.get("h", 3.5))
        else:
            fig = gdt.datum(data["letter"], data.get("h", 3.5), data.get("side", "up"))
        X, Y = abs_xy(v)
        org = getattr(fig, "origin", (0.0, 0.0))
        ox, oy = X - fig.w / 2 - org[0], H - Y - fig.h / 2 - org[1]
        for pts, closed, filled in fig.polylines():
            sh.line([(ox + x, oy + y) for x, y in pts], "thin", closed=closed, filled=filled)
        for x, y, h, s, anchor in fig.texts:
            sh.text(ox + x, oy + y, h, s, anchor)
        return
    if t == "TechDraw::DrawLeaderLine":
        par = v.LeaderParent
        PX, PY = abs_xy(par) if par is not None else (0.0, 0.0)
        sc = view_scale(par) if par is not None and hasattr(par, "Scale") else 1.0
        ox, oy = PX + float(v.X) * sc, PY + float(v.Y) * sc
        pts = [(ox + p.x, H - oy + p.y) for p in v.WayPoints]  # WayPoints run y down, as the svg
        if len(pts) >= 2:
            sh.line(pts, "thin")
            if str(getattr(v, "StartSymbol", "")).lower() not in ("none", "no symbol", "-1"):
                sh.arrow(pts[0], pts[1])
            spec = getattr(v, WELD_PROP, "") if WELD_PROP in v.PropertiesList else ""
            if spec:
                w = json.loads(spec)
                fig = gdt.weld(w["kind"], w.get("size", ""), w.get("length", ""), w.get("side", "arrow"), w.get("allAround", False),
                               w.get("field", False), w.get("tail", ""), w.get("h", 3.5))
                jx, jy = pts[-1]
                for poly, closed, filled in fig.polylines():
                    sh.line([(jx + x, jy + y) for x, y in poly], "thin", closed=closed, filled=filled)
                for x, y, hh, s_, anchor in fig.texts:
                    sh.text(jx + x, jy + y, hh, s_, anchor)
        return
    if t == "TechDraw::DrawViewAnnotation":
        X, Y = abs_xy(v)
        size = float(getattr(v, "TextSize", 5.0))
        for i, line in enumerate(list(v.Text)):
            sh.text(X, H - Y + i * size * 1.3, size * 0.75, line, "middle")
        return
    if t == "TechDraw::DrawViewBalloon":
        par = v.SourceView
        PX, PY = abs_xy(par)
        bx, by = PX + float(v.X), H - (PY + float(v.Y))
        tx, ty = PX + float(v.OriginX), H - (PY + float(v.OriginY))
        r = 4.0
        sh.circle(bx, by, r, "thin")
        d = math.hypot(tx - bx, ty - by) or 1
        sh.line([(bx + (tx - bx) / d * r, by + (ty - by) / d * r), (tx, ty)], "thin")
        sh.circle(tx, ty, 0.5, "thin")
        sh.text(bx, by + 1.2, 3.5, str(v.Text), "middle")
        return
    if t == "TechDraw::DrawViewSpreadsheet":
        draw_table(doc, sh, v, H)
        return
    raise ValueError(f"{t} is left out of the file")


def cut_line(sh, base, sv, X, Y, H):
    """A section's cutting line across its base view: chain-dotted, thick
    ends, arrows the way the section is looked at, the letter at each end."""
    import Part

    fr = frame_of(base, {})
    if fr is None:
        return
    o = V(sv.SectionOrigin)
    n = V(sv.SectionNormal)
    k = view_scale(base) / fr[0]
    a0 = [c * k for c in to_view(fr, base, o)]
    a1 = [c * k for c in to_view(fr, base, o + n * 10)]
    a0[1], a1[1] = -fr[1] * a0[1] + 0.0, -fr[1] * a1[1] + 0.0  # y down, as the page's svg
    nx, ny = a1[0] - a0[0], a1[1] - a0[1]
    ln = math.hypot(nx, ny)
    if ln < 1e-9:
        return
    nx, ny = nx / ln, ny / ln
    dx, dy = -ny, nx  # along the cut, in the view's plane
    bb = Part.makeCompound(base.getVisibleEdges()).BoundBox
    half = 0.5 * math.hypot(bb.XLength, bb.YLength) + 4

    def P(x, y):
        return (X + x, H - Y + y)

    p, q = (a0[0] - dx * half, a0[1] - dy * half), (a0[0] + dx * half, a0[1] + dy * half)
    sh.line([P(*p), P(*q)], "trail")
    for e, sgn in ((p, 1), (q, -1)):
        inner = (e[0] + dx * sgn * 5, e[1] + dy * sgn * 5)
        sh.line([P(*e), P(*inner)], "visible")
        tail = (e[0] + dx * sgn * 2.5, e[1] + dy * sgn * 2.5)
        tip = (tail[0] - nx * 7, tail[1] - ny * 7)
        sh.line([P(*tail), P(*tip)], "thin")
        sh.arrow(P(*tip), P(*tail))
        sh.text(*P(tip[0] - nx * 3, tip[1] - ny * 3 + 1.2), 4.0, str(sv.SectionSymbol), "middle")


def draw_dim(sh, d, H):
    refs = d.References2D
    if not refs:
        raise ValueError("no references")
    v = refs[0][0]
    X, Y = abs_xy(v)

    def P(p):  # view geometry (y down) → svg page
        return (X + p.x, H - Y + p.y)

    text = d.getText() if hasattr(d, "getText") else f"{d.getRawValue():.2f}"
    tol = ""
    if not getattr(d, "Arbitrary", False):
        try:
            over, under = float(d.OverTolerance.Value), float(d.UnderTolerance.Value)
            if d.TheoreticalExact:
                pass
            elif d.EqualTolerance and abs(over) > 0:
                tol = f" ±{iso286._num(over)}"
            elif not d.EqualTolerance and (abs(over) > 0 or abs(under) > 0):
                tol = f" {iso286._dev(over)}/{iso286._dev(under)}"
        except Exception:
            pass
    label = text if (not tol or "±" in text or tol.strip() in text) else text + tol
    # the label's place: the dimension's X, Y (paper mm, y up) from the view's centre
    L = (X + float(d.X), H - (Y + float(d.Y)))
    typ = d.Type
    sc = view_scale(v)
    k = sc / gscale(v, {})
    if typ in ("Distance", "DistanceX", "DistanceY"):
        lp = d.getLinearPoints()[:2]
        # on the paper, or the part's mm in some releases: told by length
        dx_, dy_ = abs(lp[1].x - lp[0].x), abs(lp[1].y - lp[0].y)
        span = dx_ if typ == "DistanceX" else dy_ if typ == "DistanceY" else math.hypot(dx_, dy_)
        raw = float(d.getRawValue())
        f = sc if (abs(span - raw) < 1e-3 * max(1, raw) and abs(sc - 1) > 1e-9) else 1.0
        a, b = [P(V(p.x * f, p.y * f, 0)) for p in lp]
        if typ == "DistanceX":
            a2, b2 = (a[0], L[1]), (b[0], L[1])
        elif typ == "DistanceY":
            a2, b2 = (L[0], a[1]), (L[0], b[1])
        else:
            dx, dy = b[0] - a[0], b[1] - a[1]
            n = math.hypot(dx, dy) or 1
            nx, ny = -dy / n, dx / n
            off = (L[0] - a[0]) * nx + (L[1] - a[1]) * ny
            a2, b2 = (a[0] + nx * off, a[1] + ny * off), (b[0] + nx * off, b[1] + ny * off)
        sh.line([a, a2], "dim")
        sh.line([b, b2], "dim")
        sh.line([a2, b2], "dim")
        sh.arrow(a2, b2)
        sh.arrow(b2, a2)
        vertical = abs(a2[0] - b2[0]) < abs(a2[1] - b2[1])
        sh.text(L[0], L[1] - 1.0, 3.5, label, "vertical" if vertical else "middle")
        if getattr(d, "TheoreticalExact", False):
            # a basic size is boxed
            hw, hh = len(label) * 3.5 * 0.31 + 1.0, 2.6
            cx, cy = L[0], L[1] - 2.2
            if vertical:
                hw, hh, cx, cy = hh, hw, L[0] - 2.2 + 1.0, L[1]
            sh.line([(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)], "thin", closed=True)
    elif typ in ("Radius", "Diameter"):
        e = v.getEdgeBySelection(ref_names(d)[0]) if hasattr(v, "getEdgeBySelection") else None
        cu = getattr(e, "Curve", None)
        if cu is not None and hasattr(cu, "Center"):
            c = P(V(cu.Center.x * k, cu.Center.y * k, 0))
            r = cu.Radius * k
            dx, dy = L[0] - c[0], L[1] - c[1]
            n = math.hypot(dx, dy) or 1
            ux, uy = dx / n, dy / n
            tip = (c[0] + ux * r, c[1] + uy * r)
            start = (c[0] - ux * r, c[1] - uy * r) if typ == "Diameter" else c
            sh.line([start, L], "dim")
            sh.arrow(tip, L if n > r else c)
            if typ == "Diameter":
                sh.arrow(start, c)
        sh.text(L[0], L[1] - 1.0, 3.5, label, "middle")
    else:
        sh.text(L[0], L[1] - 1.0, 3.5, label, "middle")


def draw_table(doc, sh, v, H):
    from .. import cells as C

    src = v.Source
    if src is None:
        raise ValueError("no sheet")
    (r0, c0), (r1, c1) = C.parse_range(f"{v.CellStart}:{v.CellEnd}")
    X, Y = abs_xy(v)
    size = float(getattr(v, "TextSize", 3.5))
    rh = size * 1.8
    cols = []
    for c in range(c0, c1 + 1):
        w = 0.0
        for r in range(r0, r1 + 1):
            try:
                val = src.get(C.name(r, c))
            except Exception:
                val = ""
            w = max(w, len(str(val)) * size * 0.55)
        cols.append(max(w + size, size * 3))
    tw, th = sum(cols), rh * (r1 - r0 + 1)
    x0, y0 = X - tw / 2, H - Y - th / 2
    for i in range(r1 - r0 + 2):
        sh.line([(x0, y0 + i * rh), (x0 + tw, y0 + i * rh)], "thin")
    x = x0
    for w in cols + [0]:
        sh.line([(x, y0), (x, y0 + th)], "thin")
        x += w
    for i, r in enumerate(range(r0, r1 + 1)):
        x = x0
        for j, c in enumerate(range(c0, c1 + 1)):
            try:
                val = src.get(C.name(r, c))
            except Exception:
                val = ""
            if hasattr(val, "Value"):
                val = str(val)
            elif isinstance(val, float):
                val = f"{val:g}"
            sh.text(x + size * 0.4, y0 + i * rh + rh * 0.7, size * 0.8, str(val))
            x += cols[j]


# ---- what the tools kept as data call by name (agentlink/data/tools.json; docs/data-tools.md) ----


def proxy_name(o):
    """The class name of an object's Python proxy ("_SectionPlane"), "NoneType" for none."""
    return type(getattr(o, "Proxy", None)).__name__


def try_set(o, prop, value):
    """A property set where this release's object has it; a value it will not take is passed by."""
    if hasattr(o, prop):
        try:
            setattr(o, prop, value)
        except Exception:
            pass


def setprop(o, prop, value):
    """A property set by its name (Agent Link's own notes on a view are named by constants)."""
    setattr(o, prop, value)


def edge_on(v, src, faces):
    """Those of the part's faces a view sees edge-on: their outline on the paper has no area (under 0.01 mm²)."""
    X, Y = abs_xy(v)
    H = paper_size(page_holding(v))[1] if page_holding(v) is not None else 210.0
    flat = []
    for f in faces:
        ps = paper_polys(v, [src.getElement(f)], X, Y, H)
        area = sum(abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(p, p[1:] + p[:1]))) / 2 for p in ps)
        if area < 0.01:
            flat.append(f)
    return flat


def leader_points(dx, dy, shoulder=5.0):
    """A leader's WayPoints for an end dx, dy page mm (y up) from its start:
    a slanted run, then a horizontal shoulder this long into the end, as
    drawn by hand (TechDraw would flatten a two-point leader whole) —
    [(x, y)] page mm from the first point, y DOWN, as FreeCAD keeps them:
    DrawLeaderLine::makeLeader stores invertY of the page deltas and
    QGILeaderLine::getWayPointsFromFeature draws them as they are. A y-up
    delta drew the leader mirrored, its end away from the note set at the
    end (td 046-048: text above the plate, symbol off its leader, the
    weld's tiles under the part)."""
    ex, ey = float(dx), -float(dy) + 0.0
    sh = abs(float(shoulder)) if ex >= 0 else -abs(float(shoulder))
    if abs(ex) > abs(sh) + 1:
        return [(0.0, 0.0), (ex - sh, ey), (ex, ey)]
    return [(0.0, 0.0), (ex, ey)]


def _cross(p, q, r, t):
    """Whether segment p-q crosses segment r-t (touching at an end does not
    count: a leader starts on the part, where other lines end too)."""
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2, d3, d4 = side(r, t, p), side(r, t, q), side(p, q, r), side(p, q, t)
    return ((d1 > 1e-9 and d2 < -1e-9) or (d1 < -1e-9 and d2 > 1e-9)) and ((d3 > 1e-9 and d4 < -1e-9) or (d3 < -1e-9 and d4 > 1e-9))


def seg_in_box(p, q, box, pad=0.0):
    """Whether segment p-q runs through box (cx, cy, w, h), grown by pad."""
    cx, cy, w, h = box
    x0, x1, y0, y1 = cx - w / 2 - pad, cx + w / 2 + pad, cy - h / 2 - pad, cy + h / 2 + pad
    if any(x0 < x < x1 and y0 < y < y1 for x, y in (p, q)):
        return True
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return any(_cross(p, q, a, b) for a, b in zip(corners, corners[1:] + corners[:1]))


def free_spot(busy, paper, want, w, h, dx=0.0, dy=0.0, side_of=None, away=None, lines=(), src=None):
    """A page point near want (page mm, y up) where a box w x h — its centre
    dx, dy from the point, dx turned to the point's side of side_of when
    given (a note right of its leader's end when the end is right of the
    feature) — lies on the paper (5 mm in) and clear of every busy box
    (cx, cy, w, h) by 1 mm, and of every busy line [(p, q)] (dimension
    lines and leaders: the "4.71" text sat on the 30/30 chain's line, the
    area's leader crossed the frame's, td 048, 061). src: where the new
    leader starts; its run from there to the point may cross no busy line
    either. Rings of 4 mm out to 60 mm, 16 ways each, first the way from
    away to want. want itself when nothing is free."""
    W, H = paper

    def free(x, y):
        cx = x + (dx if side_of is None else (abs(dx) if x >= side_of else -abs(dx)))
        cy = y + dy
        if cx - w / 2 < 5 or cx + w / 2 > W - 5 or cy - h / 2 < 5 or cy + h / 2 > H - 5:
            return False
        if not all(not (abs(cx - bx) < (w + bw) / 2 + 1 and abs(cy - by) < (h + bh) / 2 + 1) for bx, by, bw, bh in busy):
            return False
        me = (cx, cy, w, h)
        if any(seg_in_box(p, q, me, 0.5) for p, q in lines):
            return False
        if src is not None and any(_cross(tuple(src), (x, y), p, q) for p, q in lines):
            return False
        return True

    x0, y0 = float(want[0]), float(want[1])
    if free(x0, y0):
        return x0, y0
    a0 = math.atan2(y0 - away[1], x0 - away[0]) if away is not None and (x0, y0) != tuple(away) else 0.0
    for r in range(4, 64, 4):
        for k in sorted(range(16), key=lambda k: min(k, 16 - k)):
            a = a0 + k * math.pi / 8
            x, y = x0 + r * math.cos(a), y0 + r * math.sin(a)
            if free(x, y):
                return round(x, 2), round(y, 2)
    return x0, y0


def moved_text(old_anchor, new_anchor, text):
    """Where a dimension's text goes when its reference moves (td_dim_repair:
    the R3 text stayed at the slot's right end while its leader came from
    the left end, across the slot, td 070): the same offset from the new
    anchor, turned to the outside along each axis the anchor moved across
    (an offset pointing back toward where the anchor came from). Page mm
    or paper mm alike, y up."""
    ox, oy = text[0] - old_anchor[0], text[1] - old_anchor[1]
    mx, my = new_anchor[0] - old_anchor[0], new_anchor[1] - old_anchor[1]
    if mx * ox < 0:
        ox = -ox
    if my * oy < 0:
        oy = -oy
    return new_anchor[0] + ox, new_anchor[1] + oy


def poly_area_centre(pts):
    """(area, (cx, cy)) of a closed polygon [(x, y)] (shoelace; the area
    is positive whichever way it runs)."""
    pts = [tuple(p[:2]) for p in pts]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    if abs(a) < 1e-12:
        n = max(len(pts), 1)
        return 0.0, (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)
    return abs(a) / 2, (cx / (3 * a), cy / (3 * a))


def pick_view_face(faces, area, centre, tol=0.05):
    """The index of the view face [(area, (cx, cy))] that shows a part's
    face of this area and centre (the same paper frame; the centre's y
    taken either way up, as releases keep it), or None when none is within
    tol of the area."""
    best, k = None, None
    for i, (a, c) in enumerate(faces):
        if area <= 0 or abs(a - area) / area > tol:
            continue
        d = min(math.hypot(c[0] - centre[0], c[1] - centre[1]), math.hypot(c[0] - centre[0], c[1] + centre[1]))
        score = abs(a - area) / area + d / max(math.sqrt(area), 1e-6)
        if best is None or score < best:
            best, k = score, i
    return k


def flip_y(v, cache, pts):
    """Points worked out on the view's indexed geometry, multiplied to paper
    mm (k), as paper mm y down: the indexed geometry runs y up from FreeCAD
    1.1 (frame_of says which), the paper as the page's svg, y down."""
    fr = frame_of(v, cache)
    ys = -fr[1] if fr else 1
    return [(x, y * ys + 0.0) for x, y in pts]


def native_marks(v, on):
    """FreeCAD's own centre marks of a view switched on or off in the window
    (ViewProviderViewPart.ArcCenterMarks: a small cross at each circle's
    centre, as the Decorations/ShowCenterMarks preference sets it for new views).
    Switched on, the crosses are made at least 1.5 times the vertex size
    (CenterScale; FreeCAD's default 0.5 gives arms of about 1 mm at a 0.5 mm
    line, hidden under a diameter dimension's lines at the holes, td 038).
    False where there is no window."""
    vo = getattr(v, "ViewObject", None) if getattr(FreeCAD, "GuiUp", False) else None
    if vo is None or not hasattr(vo, "ArcCenterMarks"):
        return False
    try:
        vo.ArcCenterMarks = bool(on)
    except Exception:
        return False
    if on and hasattr(vo, "CenterScale"):
        try:
            if float(vo.CenterScale) < 1.5:
                vo.CenterScale = 1.5
        except Exception:
            pass
    return True


HATCH_OWN = "AgentLinkHatchOf"


def view_faces(v):
    """The view's faces as FreeCAD numbers them (FaceN of a hatch's Source:
    DrawViewPart::findFacesNew walks the visible edges with TechDraw's
    EdgeWalker, keeps the closed wires with an area, biggest first):
    [(area, (cx, cy))] in the visible edges' frame (paper mm). Worked out
    again here with TechDraw.edgeWalker on the same edges: FreeCAD has no
    Python call that hands a view's faces over."""
    out = []
    es = list(v.getVisibleEdges() or [])
    if not es:
        return out
    wires = TechDraw.edgeWalker(es, True) or []
    for w in wires:
        try:
            if not w.isClosed():
                continue
            a, c = poly_area_centre([(p.x, p.y) for p in w.discretize(Deflection=0.02)])
        except Exception:
            continue
        if a > 1e-6:
            out.append((a, c))
    return out


def native_hatch(doc, v, src, faces):
    """FreeCAD's own hatch (TechDraw::DrawHatch, as TechDraw_Hatch makes it:
    Source the view and its FaceN, the default SVG pattern) on the view
    faces that show the part's faces, so the hatch shows in the window
    (td 059: td_hatch only noted the faces for td_export, and the picture
    showed no hatch). Earlier hatches of Agent Link's on the view are
    replaced; none given takes them off. What was done, for the answer: a
    headless fact for a picture with no hatch (viewFaces 0: FreeCAD found
    no faces in the view, its HandleFaces preference off or the edges not
    closed; missing: a part face no view face matched)."""
    out = {}
    for o in list(getattr(v, "InList", []) or []):
        try:
            if o.TypeId == "TechDraw::DrawHatch" and HATCH_OWN in o.PropertiesList:
                doc.removeObject(o.Name)
        except Exception:
            continue
    if not faces:
        return out
    cache = {}
    fr = frame_of(v, cache)
    if fr is None:
        out["why"] = "the view's projection could not be read"
        return out
    try:
        vf = view_faces(v)
    except Exception as e:
        out["why"] = f"the view's faces could not be read ({e})"
        return out
    out["viewFaces"] = len(vf)
    subs, missing = [], []
    for f in faces:
        try:
            wire = src.getElement(f).OuterWire
            a, c = poly_area_centre([to_paper(v, cache, to_view(fr, v, p)) for p in wire.discretize(Deflection=0.02)])
        except Exception:
            missing.append(f)
            continue
        k = pick_view_face(vf, a, c)
        if k is None:
            missing.append(f)
        elif f"Face{k}" not in subs:
            subs.append(f"Face{k}")
    if missing:
        out["missing"] = missing
    if not subs:
        return out
    try:
        h = doc.addObject("TechDraw::DrawHatch", "Hatch")
        h.addProperty("App::PropertyString", HATCH_OWN, "AgentLink", "The part's faces this hatch shows (JSON)")
        setattr(h, HATCH_OWN, json.dumps(list(faces)))
        h.Source = (v, subs)
    except Exception as e:
        out["why"] = f"FreeCAD made no hatch ({e})"
        return out
    try:
        v.touch()  # as TechDraw_Hatch does: the view draws its hatches again
        doc.recompute()
        v.requestPaint()
    except Exception:
        pass
    out["object"] = h.Name
    out["viewFace"] = subs
    try:
        out["pattern"] = os.path.basename(str(h.HatchPattern))
        out["state"] = list(h.State)
    except Exception:
        pass
    return out


def mark_facts(v):
    """Where FreeCAD itself has a centre for its crosses (a headless fact
    for a picture with no cross at a hole): FreeCAD keeps a centre vertex
    for each Circle edge of the view (App/GeometryObject.cpp 566-571,
    QGIViewPart::drawAllVertexes draws it as a cross) unless an end point
    already sits there. centres: the circles' and arcs' centres in the
    view's indexed geometry; marked: how many of them have that vertex;
    scale: the view's CenterScale where there is a window."""
    out = {}
    try:
        cs, seen = [], set()
        for e in edges_of(v):
            c = getattr(e, "Curve", None)
            if c is None or not hasattr(c, "Radius") or not hasattr(c, "Center"):
                continue
            k = (round(c.Center.x, 2), round(c.Center.y, 2))
            if k not in seen:
                seen.add(k)
                cs.append(c.Center)
        vs = vertices_of(v)
        out["centres"] = len(cs)
        out["marked"] = sum(1 for c in cs if any(abs(p.x - c.x) < 0.01 and abs(p.y - c.y) < 0.01 for p in vs))
    except Exception:
        pass
    vo = getattr(v, "ViewObject", None) if getattr(FreeCAD, "GuiUp", False) else None
    try:
        if vo is not None and hasattr(vo, "CenterScale"):
            out["scale"] = round(float(vo.CenterScale), 2)
    except Exception:
        pass
    return out


def broken_3d(d):
    """A dimension's 3D references (References3D) that name an element its
    object's shape does not have — what FreeCAD's "Shape index N out of
    bound M" (Part/App/TopoShapeExpansion.cpp getSubTopoShape, from
    TechDraw's ReferenceEntry::hasGeometry) reports in the Report view when
    the dimension recomputes. [] when all resolve or there are none."""
    out = []
    try:
        refs = list(getattr(d, "References3D", []) or [])
    except Exception:
        return out
    for item in refs:
        try:
            o, subs = item
        except Exception:
            continue
        for sub in (subs if isinstance(subs, (list, tuple)) else [subs]):
            sub = str(sub or "")
            kind = next((k for k in ("Edge", "Vertex", "Face") if sub.startswith(k) and sub[len(k):].isdigit()), None)
            if o is None or kind is None:
                continue
            try:
                sh = o.Shape
                have = len(getattr(sh, kind + ("es" if kind == "Vertex" else "s")))
            except Exception:
                have = 0
            if int(sub[len(kind):]) > have:
                out.append(f"{o.Label}.{sub}: {o.Label} has {have} {kind.lower()}{'s' if have != 1 else ''}")
    return out


# A weld kind's symbol in FreeCAD's own AWS set (Mod/TechDraw/Symbols/Welding/AWS):
# the file's stem, with Up / Down where it has both.
WELD_SVG = {"fillet": "fillet", "square": "Square", "v": "V", "plug": "plug", "surfacing": "bead"}


def weld_svg(kind, above):
    """The path of FreeCAD's own AWS weld symbol for a kind, drawn above the
    line (above) or below it; None where FreeCAD has none for it."""
    stem = WELD_SVG.get(kind)
    if stem is None:
        return None
    d = os.path.join(FreeCAD.getResourceDir(), "Mod", "TechDraw", "Symbols", "Welding", "AWS")
    for name in ((stem + ("Up" if above else "Down")) + ".svg", stem + ".svg"):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def weld_tiles(doc, w):
    """A weld symbol's two tiles (TechDraw::DrawTileWeld, made by FreeCAD as
    the symbol joins the document, DrawWeldSymbol::onSettingDocument): those
    whose TileParent is the symbol — the symbol's InList may not hold them
    yet right after addObject."""
    out = []
    inlist = list(getattr(w, "InList", []) or [])
    for o in inlist + list(getattr(doc, "Objects", []) or []):
        try:
            if any(o is x for x in out) or not o.isDerivedFrom("TechDraw::DrawTileWeld"):
                continue
            par = getattr(o, "TileParent", None)
            if any(o is x for x in inlist) or par is w or getattr(par, "Name", None) == w.Name:
                out.append(o)
        except Exception:
            continue
    return out


def tile_reading(tiles, vo=None):
    """What a weld symbol's tiles hold, as FreeCAD will draw them (a headless
    fact for a picture that shows no size): row (0 arrow side, -1 other
    side), the symbol file's name, the texts left (size) and right (length),
    and the view provider's tile text size in mm where there is a window."""
    rows = []
    for t in tiles:
        try:
            rows.append({"row": int(getattr(t, "TileRow", 0)), "symbol": os.path.basename(str(getattr(t, "SymbolFile", "") or "")) or None,
                         "left": str(getattr(t, "LeftText", "") or ""), "right": str(getattr(t, "RightText", "") or "")})
        except Exception:
            continue
    rows.sort(key=lambda r: -r["row"])
    out = {"tiles": rows}
    try:
        if vo is not None and hasattr(vo, "TileFontSize"):
            out["tileTextMm"] = round(float(getattr(vo.TileFontSize, "Value", vo.TileFontSize)), 2)
    except Exception:
        pass
    return out


def native_weld(doc, page, ln, spec):
    """FreeCAD's own weld symbol (TechDraw::DrawWeldSymbol, its two tiles
    made by FreeCAD as it joins the document) on a leader, as the
    TechDraw_WeldSymbol command makes it (src/Mod/TechDraw/Gui/
    TaskWeldingSymbol.cpp createWeldingSymbol, updateTiles): AllAround,
    FieldWeld, TailText, and the arrow-side tile (row 0) and other-side tile
    (row -1) with the kind's symbol and size / length. The tiles' text size
    (ViewProviderWeld.TileFontSize, by default the label size x 0.75) is
    raised to the asked text size: the size "3" was not seen in the window
    (td 048). Returns (the symbol or None, whether FreeCAD has the kind's
    symbol, what the tiles hold)."""
    try:
        w = doc.addObject("TechDraw::DrawWeldSymbol", "WeldSymbol")
    except Exception:
        return None, False, {}
    try:
        w.Leader = ln
        w.AllAround = bool(spec.get("allAround"))
        w.FieldWeld = bool(spec.get("field"))
        w.TailText = str(spec.get("tail") or "")
        page.addView(w)
    except Exception:
        try:
            doc.removeObject(w.Name)
        except Exception:
            pass
        return None, False, {}
    side = spec.get("side", "arrow")
    found = True
    tiles = weld_tiles(doc, w)
    for tile in tiles:
        row = int(getattr(tile, "TileRow", 0))
        if (row == 0 and side not in ("arrow", "both")) or (row != 0 and side not in ("other", "both")):
            continue
        svg = weld_svg(spec.get("kind", "fillet"), row == 0)  # QGITile draws row 0 above the line, row -1 below
        try:
            if svg:
                tile.SymbolFile = svg
            else:
                found = False
            tile.LeftText = str(spec.get("size") or "")
            tile.RightText = str(spec.get("length") or "")
        except Exception:
            found = False
    vo = getattr(w, "ViewObject", None) if getattr(FreeCAD, "GuiUp", False) else None
    if vo is not None and hasattr(vo, "TileFontSize"):
        try:
            want = float(spec.get("h") or 3.5)
            have = float(getattr(vo.TileFontSize, "Value", vo.TileFontSize))
            if have < want:
                vo.TileFontSize = want
        except Exception:
            pass
    return w, found, tile_reading(tiles, vo)


def weld_wrong(spec):
    """What is wrong with a weld symbol's words (gdt.weld draws it for td_export), or None."""
    try:
        gdt.weld(spec["kind"], spec["size"], spec["length"], spec["side"], spec["allAround"], spec["field"], spec["tail"], spec["h"])
    except gdt.GdtError as e:
        return str(e)
    return None


def face_front(g, z, x):
    """A projection group's front turned to face z with x to the right,
    before the others are added: TechDraw works each secondary view's
    direction out from the front's as it is when the view is added
    (DrawProjGroup::addProjection), not afterwards."""
    try:
        anchor = g.Anchor
        anchor.Direction = z
        anchor.XDirection = x
    except Exception:
        pass


def axis_vector(name):
    """ "x", "-y" … as a vector along that axis."""
    sgn = -1.0 if name.startswith("-") else 1.0
    return V(*[sgn if c == name[-1] else 0.0 for c in "xyz"])


def section_frame(base, normal):
    """(x, side) for a section cut with normal from a base view: the
    section's x direction (the base's, laid into the cut plane), and the
    side of the base it is seen from — Right, Left, Up, Down, or None when
    the cut runs askew to the base's paper."""
    bx = V(base.XDirection)
    x = bx - normal * bx.dot(normal)
    if x.Length < 1e-6:
        x = V(base.Direction).cross(normal)
    x.normalize()
    by = V(base.Direction).cross(bx)
    side = "Right" if normal.dot(bx) > 0.7 else "Left" if normal.dot(bx) < -0.7 else "Up" if normal.dot(by) > 0.7 else "Down" if normal.dot(by) < -0.7 else None
    return x, side


def hide_cut(sv):
    """A section's cut face left unhatched: TechDraw's own word is Hide (Hide | Color | SvgHatch | PatHatch), None on older releases."""
    for word in ("Hide", "None"):
        try:
            sv.CutSurfaceDisplay = word
            break
        except Exception:
            continue


def curve_name(e):
    """The class name of an edge's curve ("LineSegment", "Circle"); "NoneType" for none."""
    return type(getattr(e, "Curve", None)).__name__


def figure(kind, *args):
    """A GD&T figure drawn by agentlink/gdt.py (kind: frame, datum …):
    (figure, None), or (None, what is wrong with its words)."""
    try:
        return getattr(gdt, kind)(*args), None
    except gdt.GdtError as e:
        return None, str(e)


def next_balloon(page):
    """The page's next balloon number, taken ("1" where the page keeps none)."""
    try:
        text = str(page.NextBalloonIndex)
        page.NextBalloonIndex = page.NextBalloonIndex + 1
    except Exception:
        text = "1"
    return text


def area_text(form, val, decimals, unit):
    """An area as the caller's text: form with {value} (to decimals places) and {unit} (mm², cm², m²) filled."""
    return form.format(value=f"{val:.{int(decimals)}f}", unit={"mm2": "mm²", "cm2": "cm²", "m2": "m²"}.get(unit, unit))


def without_prefix(f):
    """A dimension's format without what stands before its number."""
    i = f.find("%")
    return f[i:] if i > 0 else f


def with_decimals(f, n):
    """A dimension's format showing n decimals (its first number's; one is put in where it names none)."""
    import re

    return re.sub(r"%\.(\d)([fwgG])", lambda m: f"%.{n}{m.group(2)}", f, count=1) if re.search(r"%\.\d", f) else f.replace("%", f"%.{n}", 1)


def more_decimals(f, k):
    """A dimension's format with k more decimals (fewer for a negative k), kept within 0 to 9."""
    import re

    return re.sub(r"%\.(\d)", lambda m: f"%.{max(0, min(9, int(m.group(1)) + k))}", f, count=1)


def prefixed(f, pre, count):
    """A dimension's format with a prefix before its number: "diameter" ⌀,
    "square" □, the text itself, or "count" (count×, before any symbol)."""
    import re

    if pre == "count":
        # Before everything, the ⌀ FreeCAD's diameter format starts with
        # too: "2× ⌀6", not "⌀2× 6" (td 066 read "⌀1× 6").
        return f"{int(count)}× " + re.sub(r"^\d+× ", "", f)
    tok = {"diameter": "⌀", "square": "□"}.get(pre)
    if tok is None:
        tok = str(pre)
    i = f.find("%")
    return f[:i] + tok + f[i:] if i >= 0 else tok + f


def chamfer_angle(v, names, kind):
    """A chamfer's angle in whole degrees (90 at most) between two of the
    view's vertices, from the horizontal for chamfer_h, the vertical for chamfer_v."""
    vs = vertices_of(v)
    p, q = (vs[int(n[6:])] for n in names)
    ang = round(math.degrees(abs(math.atan2(q.y - p.y, q.x - p.x))) if kind == "chamfer_h" else math.degrees(abs(math.atan2(q.x - p.x, q.y - p.y))))
    return ang if ang <= 90 else 180 - ang


def nearest_vertices(v, e):
    """The view's vertices nearest an edge's two ends, by name ("Vertex3"): what a dimension along the edge stands on."""
    vs = vertices_of(v)
    ends = []
    for pt in (e.Vertexes[0].Point, e.Vertexes[-1].Point):
        k = min(range(len(vs)), key=lambda i: (vs[i] - pt).Length)
        ends.append(f"Vertex{k}")
    return ends


def axo_angles(e, x):
    """(line angle, extension angle) in degrees for a length along one of
    the part's axes in an axonometric view, read true (not foreshortened):
    e the measured edge, x the one the extension lines run along."""
    dl = e.Vertexes[-1].Point - e.Vertexes[0].Point
    el = x.Vertexes[-1].Point - x.Vertexes[0].Point
    X = FreeCAD.Vector(1, 0, 0)
    la, ea = math.degrees(dl.getAngle(X)), math.degrees(el.getAngle(X))
    if dl.y < 0:
        la = 180 - la
    if el.y < 0:
        ea = 180 - ea
    return la, ea


LINE_STYLES = {"solid": 1, "dashed": 2, "dotted": 3, "dashdot": 4, "dashdotdot": 5, "none": 0}  # TechDraw's line numbers, by td_lines' names


def mark_not_ready(rows, still):
    """td_list's rows of the views still without lines (and a group's items):
    no edge or vertex count — never zeros as if counted — and notReady."""
    for row in rows:
        if row.get("name") in still:
            row.pop("edges", None)
            row.pop("vertices", None)
            row["notReady"] = True
        mark_not_ready(row.get("items") or [], still)


def turn_to_align(p, q, upright):
    """The turn in degrees, within a quarter either way, that lays the line
    from p to q level (or upright) on the page."""
    ang = math.degrees(math.atan2(q.y - p.y, q.x - p.x))
    turn = 90 - ang if upright else -ang
    while turn > 90:
        turn -= 180
    while turn < -90:
        turn += 180
    return turn


def stretched(pts, by):
    """A two-point line made longer by `by` mm at each end (shorter when
    negative): its length as it was, and its two new points."""
    (x0, y0), (x1, y1) = pts
    L = math.hypot(x1 - x0, y1 - y0) or 1
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    return L, [[x0 - ux * by, y0 - uy * by], [x1 + ux * by, y1 + uy * by]]


def erase_tag(v, tag):
    """FreeCAD's own cosmetic edge, centerline or cosmetic vertex of that tag
    removed from a view, whichever it is (one that is none of them is passed by)."""
    for fn in ("removeCosmeticEdge", "removeCenterLine", "removeCosmeticVertex"):
        try:
            getattr(v, fn)(tag)
            break
        except Exception:
            continue


def circle_points(c, r):
    """A circle on the paper as 48 points about c."""
    return [(c[0] + r * math.cos(2 * math.pi * i / 48), c[1] + r * math.sin(2 * math.pi * i / 48)) for i in range(48)]


def mid_line(e1, e2, k, ext):
    """The line midway between two of a view's edges (a shaft's or a hole's
    sides; k: the view's lines to paper mm), run on by ext mm past each end:
    its two points, and its length before the run-on."""
    a1, b1 = [(p.x * k, p.y * k) for p in (e1.Vertexes[0].Point, e1.Vertexes[-1].Point)]
    a2, b2 = [(p.x * k, p.y * k) for p in (e2.Vertexes[0].Point, e2.Vertexes[-1].Point)]
    if (a1[0] - b1[0]) * (a2[0] - b2[0]) + (a1[1] - b1[1]) * (a2[1] - b2[1]) < 0:
        a2, b2 = b2, a2
    m0 = ((a1[0] + a2[0]) / 2, (a1[1] + a2[1]) / 2)
    m1 = ((b1[0] + b2[0]) / 2, (b1[1] + b2[1]) / 2)
    d = math.hypot(m1[0] - m0[0], m1[1] - m0[1]) or 1
    ux, uy = (m1[0] - m0[0]) / d, (m1[1] - m0[1]) / d
    return [(m0[0] - ux * ext, m0[1] - uy * ext), (m1[0] + ux * ext, m1[1] + uy * ext)], d


def thread_arc(cu, k, r):
    """A thread seen end-on, as drawings show it: three quarters of a circle
    of radius r (paper mm) about a round edge's centre, begun 10 degrees round."""
    loc = getattr(cu, "Location", None) or cu.Center
    c = (float(loc.x) * k, float(loc.y) * k)
    a0 = math.radians(10)
    return [(c[0] + r * math.cos(a0 + 1.5 * math.pi * i / 36), c[1] + r * math.sin(a0 + 1.5 * math.pi * i / 36)) for i in range(37)]


def side_outline(e1, e2, k):
    """A thread's two outline lines in a side view, on the paper: the
    first's ends, the second's, the unit direction along the first, its
    length, and the signed gap across to the second (paper mm)."""
    A = [(p.x * k, p.y * k) for p in (e1.Vertexes[0].Point, e1.Vertexes[-1].Point)]
    B = [(p.x * k, p.y * k) for p in (e2.Vertexes[0].Point, e2.Vertexes[-1].Point)]
    ux, uy = A[1][0] - A[0][0], A[1][1] - A[0][1]
    L = math.hypot(ux, uy) or 1
    ux, uy = ux / L, uy / L
    gap = (B[0][0] - A[0][0]) * (-uy) + (B[0][1] - A[0][1]) * ux
    return {"A": A, "B": B, "u": (ux, uy), "L": L, "gap": gap}


def root_lines(o, off, length):
    """The two thin lines of a thread in a side view: each outline line of
    side_outline's moved off mm toward the other (negative: away), both begun
    at the end the first starts from and run for length."""
    A, B, (ux, uy) = o["A"], o["B"], o["u"]
    nx, ny = -uy, ux
    sgn = 1 if o["gap"] > 0 else -1
    b0 = min(B, key=lambda q: (q[0] - A[0][0]) * ux + (q[1] - A[0][1]) * uy)
    out = []
    for start, toward in ((A[0], sgn), (b0, -sgn)):
        p0 = (start[0] + nx * off * toward, start[1] + ny * off * toward)
        out.append([p0, (p0[0] + ux * length, p0[1] + uy * length)])
    return out


def stack_of(x):
    """What keeps a view's stacking order: its view provider (TechDraw's
    Gui side), not the view itself; None headless or where this FreeCAD has none."""
    g = getattr(x, "ViewObject", None)
    return g if g is not None and hasattr(g, "StackOrder") else None


def read_text(p):
    """A text file's content (an SVG for a symbol view), bytes that are not UTF-8 replaced."""
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def drawn(sheet, kind):
    """The page drawn here (page_sheet's) in one format: its SVG or DXF text, or its PDF's bytes."""
    return {"svg": sheet.svg, "pdf": sheet.pdf, "dxf": sheet.dxf}[kind]()


def write_out(p, data):
    """A drawn page written to its file: bytes (a PDF) as they are, text as UTF-8."""
    with open(p, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as f:
        f.write(data)



def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731
    frames = {}

    def recompute(objs=()):
        doc().recompute()
        frames.clear()
        if objs:
            wait(objs)
            doc().recompute()
            settle()
        try:
            if refresh_special(doc(), frames):
                pass
        except Exception:
            pass

    def settle(seconds=0.15):
        # TechDraw finishes a view's lines (and a section's faces) on worker
        # threads; let them land before the next change touches the views.
        try:
            from PySide import QtCore
        except ImportError:
            try:
                from PySide2 import QtCore
            except ImportError:
                return
        import time

        app = QtCore.QCoreApplication.instance()
        if app is None:
            return
        t0 = time.time()
        from ..td_wait import pump

        while time.time() - t0 < seconds:
            pump(app)
            time.sleep(0.01)

    def _own_data(o, prop):
        # Agent Link's own notes on a view (what td_export draws): writing
        # them is no change FreeCAD has to recompute, so it must not leave
        # the view marked touched (td_hatch left eight objects "not
        # recomputed yet").
        try:
            o.setPropertyStatus(prop, "NoRecompute")
        except Exception:
            pass

    def done(tool, out):
        return picks.finish(s, tool, out, recompute=False)

    def place_xy(page, at, default):
        if at is None:
            return default
        x, y = pt2(at, "at")
        W, H = paper_size(page)
        if not (0 <= x <= W and 0 <= y <= H):
            raise bad(f"at: on the paper, 0..{W:g} by 0..{H:g} mm from its bottom-left corner.")
        return x, y

    def view_reading(v):
        out = {"view": v.Label, "name": v.Name, "type": v.TypeId.split("::")[-1], "at": [num(v.X, 2), num(v.Y, 2)]}
        if v.isDerivedFrom("TechDraw::DrawViewPart"):
            out["scale"] = num(view_scale(v), 4)
            try:
                es = v.getVisibleEdges() or []
                if es:
                    import Part

                    bb = Part.makeCompound(es).BoundBox
                    out["size"] = [num(bb.XLength, 2), num(bb.YLength, 2)]
                out["edges"], out["vertices"] = len(edges_of(v)), len(vertices_of(v))
            except Exception:
                pass
        return out

    def bodies_for(refs):
        objs = [s.body(r) for r in refs] if refs else s.bodies()
        if not objs:
            raise ToolError("not_found", "No body in the document to draw: bodies names them (session_state lists what there is); part_primitive or pd_body_new makes one.")
        return objs

    def direction(d, what="direction"):
        if isinstance(d, str):
            if d not in DIRS:
                raise bad(f"{what}: one of {', '.join(DIRS)}, or [x, y, z] (from the part toward the viewer).")
            z, x = DIRS[d]
            return V(*z), V(*x)
        z = vec(d, what)
        if z.Length < 1e-9:
            raise bad(f"{what}: not zero.")
        z.normalize()
        x = V(1, 0, 0) if abs(z.x) < 0.9 else V(0, 1, 0)
        x = x - z * x.dot(z)
        x.normalize()
        return z, x

    # ---- pages and title blocks ----


    def page_reading(p, full=False):
        W, H = paper_size(p)
        out = {"page": p.Label, "name": p.Name, "paper": [num(W, 1), num(H, 1)], "template": os.path.basename(getattr(p.Template, "Template", "") or ""),
               "projection": getattr(p, "ProjectionType", ""), "views": []}
        for v in p.Views:
            out["views"].append(view_reading(v))
            if v.isDerivedFrom("TechDraw::DrawProjGroup"):
                out["views"][-1]["items"] = [view_reading(x) for x in v.Views]
        if full:
            try:
                out["titleBlock"] = dict(p.Template.EditableTexts)
            except Exception:
                out["titleBlock"] = {}
        return out


    # ---- views ----


    def next_letter(d, kind):
        used = set()
        for o in d.Objects:
            if o.isDerivedFrom("TechDraw::DrawViewSection"):
                used.add(o.SectionSymbol)
            elif o.isDerivedFrom("TechDraw::DrawViewDetail"):
                used.add(o.Reference)
        for ch in "ABCDEFGHJKLMNPRSTUVWXYZ":
            if ch not in used:
                return ch
        return "Z"


    # ---- dimensions and tolerances ----


    def apply_tol(d, a, raw):
        if a.get("format"):
            d.FormatSpec = str(a["format"])
        if a.get("label") is not None:
            d.Arbitrary = bool(a["label"])
            if a["label"]:
                d.FormatSpec = str(a["label"])
        if a.get("basic") is not None:
            d.TheoreticalExact = bool(a["basic"])
        src = None
        if a.get("fit"):
            try:
                up, lo, src = iso286.limits_from(raw, a["fit"])
            except ValueError as e:
                raise bad(f"fit: {e}")
            d.EqualTolerance = False
            d.OverTolerance = up
            d.UnderTolerance = lo
            spec = d.FormatSpec
            if a["fit"] not in spec:
                d.FormatSpec = f"{spec} {a['fit']}"
        elif a.get("plus") is not None or a.get("minus") is not None:
            p = float(a.get("plus") or 0)
            m = a.get("minus")
            m = -abs(float(m)) if m is not None else -p
            if abs(p + m) < 1e-12:
                d.EqualTolerance = True
                d.OverTolerance = p
            else:
                d.EqualTolerance = False
                d.OverTolerance = p
                d.UnderTolerance = m
        return src

    def dim_reading(d):
        out = {"dimension": d.Name, "label": d.Label, "type": d.Type, "refs": ref_names(d), "view": d.References2D[0][0].Label if d.References2D else None}
        try:
            out["measured"] = num(d.getRawValue(), 4)
        except Exception as e:
            out["error"] = str(e)
        try:
            out["text"] = d.getText()
        except Exception:
            pass
        if d.TheoreticalExact:
            out["basic"] = True
        broken = broken_3d(d)
        if broken:
            out["broken3d"] = broken
            out["why"] = ("Its 3D references name elements the model no longer has: FreeCAD's own "
                          "\"Shape index N out of bound M\" in the Report view comes from this dimension when it recomputes.")
        try:
            over, under = float(d.OverTolerance.Value), float(d.UnderTolerance.Value)
            if d.EqualTolerance and over:
                out["tolerance"] = f"±{iso286._num(over)}"
            elif not d.EqualTolerance and (over or under):
                out["tolerance"] = f"{iso286._dev(over)}/{iso286._dev(under)}"
        except Exception:
            pass
        return out


    # ---- GD&T, notes, balloons, tables ----

    def leader(view, p_from, to_page, shoulder=5.0):
        """A leader from a point on the view (view mm, y as geometry) to a
        page point: TechDraw's own leader line, owned by the view, ending in
        a horizontal shoulder this long (mm). A weld symbol's reference line
        is the leader's last segment (src/Mod/TechDraw/Gui/QGIWeldSymbol.cpp
        getKinkPoint, getTailPoint): td_weld asks for 20 mm — on the 5 mm
        shoulder no reference line could be seen and the tiles' size text sat
        on the slanted run (td 048)."""
        page = page_holding(view)
        ln = doc().addObject("TechDraw::DrawLeaderLine", "Leader")
        page.addView(ln)
        ln.LeaderParent = view
        sc = view_scale(view)
        vx, vy = abs_xy(view)
        # anchored at the feature: X, Y in the view's unscaled frame, y up
        ln.X, ln.Y = p_from[0] / sc, -p_from[1] / sc
        pts = leader_points(to_page[0] - (vx + p_from[0]), to_page[1] - (vy - p_from[1]), shoulder)
        ln.WayPoints = [V(x, y, 0) for x, y in pts]
        try:
            ln.AutoHorizontal = False
        except Exception:
            pass
        for prop, want in (("StartSymbol", ("Filled Arrow", "FILLED_ARROW")), ("EndSymbol", ("None", "No Symbol", "NONE"))):
            for w in want:
                try:
                    set_enum(ln, prop, w)
                    break
                except Exception:
                    continue
        return ln

    def paper_half(v):
        """A part view's half width and half height on the paper (mm): its
        indexed geometry is in part mm (unscaled from FreeCAD 1.1), the
        page and a dimension's X, Y in paper mm — td_dimset's lanes took
        the part's half size as paper mm and sat inside the part at scale 2,
        on a radius dimension's text (td 036: "30" over "R3")."""
        es = edges_of(v)
        if not es:
            return None
        bb = __import__("Part").makeCompound(es).BoundBox
        xs, ys = [], []
        for x in (bb.XMin, bb.XMax):
            for y in (bb.YMin, bb.YMax):
                px, py = to_paper(v, frames, (x, y))
                xs.append(px)
                ys.append(py)
        return (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2

    def busy_boxes(page, skip=()):
        """What already takes room on a page, as boxes (cx, cy, w, h) in
        page mm, y up: part views (their lines), dimension texts, notes,
        symbols, balloons and detail circles. Sizes of texts are guessed
        from their characters (0.6 of the height each)."""
        skip = {getattr(o, "Name", o) for o in skip}
        out = []

        def add(cx, cy, w, h):
            out.append((float(cx), float(cy), max(float(w), 1.0), max(float(h), 1.0)))

        items = []
        for o in list(getattr(page, "Views", []) or []):
            items.append(o)
            if o.isDerivedFrom("TechDraw::DrawProjGroup"):
                items += list(getattr(o, "Views", []) or [])
        for o in items:
            if getattr(o, "Name", None) in skip:
                continue
            try:
                if o.isDerivedFrom("TechDraw::DrawViewPart"):
                    half = paper_half(o)
                    if half:
                        X, Y = abs_xy(o)
                        add(X, Y, 2 * half[0], 2 * half[1])
                    if o.isDerivedFrom("TechDraw::DrawViewDetail") and getattr(o, "BaseView", None) is not None:
                        b = o.BaseView
                        bs = view_scale(b)
                        bx, by = abs_xy(b)
                        A = o.AnchorPoint
                        r = float(getattr(o.Radius, "Value", o.Radius)) * bs
                        add(bx + A.x * bs, by + A.y * bs, 2 * r, 2 * r)
                elif o.TypeId == "TechDraw::DrawViewDimension":
                    par = o.References2D[0][0] if o.References2D else None
                    X, Y = abs_xy(par) if par is not None else (0.0, 0.0)
                    try:
                        t = str(o.getText() or "")
                    except Exception:
                        t = "00.00"
                    add(X + float(o.X), Y + float(o.Y), len(t) * 3.5 * 0.6 + 2, 5.5)
                elif o.isDerivedFrom("TechDraw::DrawViewAnnotation"):
                    lines = [str(x) for x in (o.Text or [""])]
                    h = float(getattr(o, "TextSize", 3.5) or 3.5)
                    add(o.X, o.Y, max(len(x) for x in lines) * h * 0.6 + 2, len(lines) * h * 1.3 + 1)
                elif o.isDerivedFrom("TechDraw::DrawViewBalloon"):
                    par = getattr(o, "SourceView", None)
                    X, Y = abs_xy(par) if par is not None else (0.0, 0.0)
                    sc = view_scale(par) if par is not None else 1.0
                    add(X + float(o.X) * sc, Y + float(o.Y) * sc, 10, 10)
                elif o.isDerivedFrom("TechDraw::DrawViewSymbol") and not o.isDerivedFrom("TechDraw::DrawSVGTemplate"):
                    add(o.X, o.Y, 18, 10)
            except Exception:
                continue
        return out

    def clear_xy(page, want, w, h, dx=0.0, dy=0.0, side_of=None, skip=(), away=None, src=None):
        """A page point near want where a box w x h lies on nothing the page
        holds (busy_boxes, busy_lines; free_spot says how), and the leader
        from src (page mm) to it crosses no line already there. Labels
        placed by fixed offsets lay on each other and on the part (td 036,
        037, 043, 046, 047); boxes alone let a label sit on a dimension's
        line and a leader cross another (td 048, 061)."""
        return free_spot(busy_boxes(page, skip), paper_size(page), want, w, h, dx, dy, side_of, away,
                         busy_lines(page, skip), src)

    def ref_xy(v, n):
        """A view reference's points on the paper from the view's centre, y
        up: a vertex's point, a round edge's centre, a straight edge's two
        ends. [] where it cannot be read."""
        try:
            if n.startswith("Vertex"):
                p = vertices_of(v)[int(n[6:])]
                x, y = to_paper(v, frames, (p.x, p.y))
                return [(x, -y)]
            e = edges_of(v)[int(n[4:])]
            c = getattr(e, "Curve", None)
            if hasattr(c, "Radius") and hasattr(c, "Center"):
                x, y = to_paper(v, frames, (c.Center.x, c.Center.y))
                return [(x, -y)]
            out = []
            for q in (e.Vertexes[0].Point, e.Vertexes[-1].Point):
                x, y = to_paper(v, frames, (q.x, q.y))
                out.append((x, -y))
            return out
        except Exception:
            return []

    def dim_refs(d):
        """(the view, its sub-element names) a dimension measures."""
        out, v = [], None
        for item in list(getattr(d, "References2D", []) or []):
            try:
                o, subs = item
            except Exception:
                continue
            v = v or o
            out += [subs] if isinstance(subs, str) else list(subs)
        return v, [x for x in out if x]

    def dim_anchor(d):
        """Where a dimension's references are, on the paper from its view's
        centre, y up: their points' middle (a radius' or diameter's centre).
        None where any of them cannot be read."""
        v, names = dim_refs(d)
        got = [ref_xy(v, n) for n in names] if v is not None else []
        if not got or not all(got):
            return None  # one not read: no middle rather than a wrong one
        pts = [p for g in got for p in g]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

    def busy_lines(page, skip=()):
        """The lines already on a page that a new label may not sit on and a
        new leader may not cross, [(p, q)] page mm y up: Agent Link's
        leaders (their start on the view and their way points), a
        horizontal or vertical dimension's line and extension lines, a
        radius' or diameter's line from its text to the centre."""
        skip = {getattr(o, "Name", o) for o in skip}
        out = []
        for o in list(getattr(page, "Views", []) or []):
            if getattr(o, "Name", None) in skip:
                continue
            try:
                if o.isDerivedFrom("TechDraw::DrawLeaderLine"):
                    par = getattr(o, "LeaderParent", None)
                    if par is None:
                        continue
                    sc = view_scale(par)
                    X, Y = abs_xy(par)
                    sx, sy = X + float(o.X) * sc, Y + float(o.Y) * sc
                    pts = [(sx + float(p.x), sy - float(p.y)) for p in o.WayPoints]
                    out += list(zip(pts, pts[1:]))
                elif o.TypeId == "TechDraw::DrawViewDimension":
                    v, names = dim_refs(o)
                    if v is None:
                        continue
                    X, Y = abs_xy(v)
                    tx, ty = X + float(o.X), Y + float(o.Y)
                    pts = [(X + x, Y + y) for n in names for x, y in ref_xy(v, n)]
                    if o.Type == "DistanceX" and len(pts) >= 2:
                        out.append(((min(p[0] for p in pts), ty), (max(p[0] for p in pts), ty)))
                        out += [((p[0], p[1]), (p[0], ty)) for p in pts]
                    elif o.Type == "DistanceY" and len(pts) >= 2:
                        out.append(((tx, min(p[1] for p in pts)), (tx, max(p[1] for p in pts))))
                        out += [((p[0], p[1]), (tx, p[1])) for p in pts]
                    elif o.Type in ("Radius", "Diameter") and pts:
                        out.append(((tx, ty), pts[0]))
            except Exception:
                continue
        return [(p, q) for p, q in out if math.hypot(q[0] - p[0], q[1] - p[1]) > 0.05]

    def text_box(d):
        """A dimension's text as a box on the page (cx, cy, w, h), its text's
        length guessed at 0.6 of 3.5 mm a character."""
        v, _ = dim_refs(d)
        X, Y = abs_xy(v) if v is not None else (0.0, 0.0)
        try:
            t = str(d.getText() or "")
        except Exception:
            t = "00.00"
        return X + float(d.X), Y + float(d.Y), len(t) * 3.5 * 0.6 + 2, 5.5

    def nudge_out(d, most=30.0):
        """A radius' or diameter's text that now lies on something (its text
        grew: "1× ⌀6.0" ran into the detail circle's B, td 066) moved out
        along its own line from the centre, 2 mm at a time, until it lies
        clear; its line keeps its direction. The new [X, Y], or None when it
        lay clear already, is no radius or diameter, or nothing is clear."""
        if d.Type not in ("Radius", "Diameter"):
            return None
        page = page_holding(dim_refs(d)[0]) if dim_refs(d)[0] is not None else None
        c = dim_anchor(d)
        if page is None or c is None:
            return None
        busy = busy_boxes(page, [d])
        lines = busy_lines(page, [d])
        cx, cy, w, h = text_box(d)

        def clear(x, y):
            if any(abs(x - bx) < (w + bw) / 2 + 1 and abs(y - by) < (h + bh) / 2 + 1 for bx, by, bw, bh in busy):
                return False
            return not any(seg_in_box(p, q, (x, y, w, h), 0.5) for p, q in lines)

        if clear(cx, cy):
            return None
        ox, oy = float(d.X) - c[0], float(d.Y) - c[1]
        L = math.hypot(ox, oy)
        if L < 1e-6:
            return None
        ux, uy = ox / L, oy / L
        k = 2.0
        while k <= most:
            if clear(cx + ux * k, cy + uy * k):
                d.X, d.Y = float(d.X) + ux * k, float(d.Y) + uy * k
                return [num(d.X, 2), num(d.Y, 2)]
            k += 2.0
        return None

    def ref_point(v, r):
        """A view-geometry point for a reference: a vertex, an edge's middle,
        a circle's rim nearest the part's outside."""
        n = resolve_ref(v, r, frames)
        if n.startswith("Vertex"):
            p = vertices_of(v)[int(n[6:])]
            return n, to_paper(v, frames, (p.x, p.y))
        e = edges_of(v)[int(n[4:])]
        m = e.valueAt((e.FirstParameter + e.LastParameter) / 2)
        return n, to_paper(v, frames, (m.x, m.y))

    def symbol(page, fig, data, at, label):
        sym = doc().addObject("TechDraw::DrawViewSymbol", "Symbol")
        page.addView(sym)
        sym.Label = s.unique(label)
        sym.Symbol = fig.svg() if not hasattr(fig, "origin") else shifted_svg(fig)
        sym.addProperty("App::PropertyString", GDT_PROP, "AgentLink", "What this symbol is, for export and editing")
        _own_data(sym, GDT_PROP)
        setattr(sym, GDT_PROP, json.dumps(data))
        sym.X, sym.Y = at
        try:
            sym.Scale = 1.0
            sym.ScaleType = "Custom"
        except Exception:
            pass
        return sym


    # ---- reading and writing out ----

    def lines_of(v):
        try:
            return bool(v.getVisibleEdges())
        except Exception:
            return False

    def warm(page):
        """The page's part views that have no lines yet — a document just
        opened: FreeCAD saves a view's settings, not its lines, and works
        them out at the view's first recompute (DrawViewPart::execute; on a
        worker thread in the window) — recomputed here and waited for, and
        the dimensions on them recomputed after (a dimension keeps the
        points it measures between from its own recompute). (how many were
        cold, seconds waited, the names of those still without lines)."""
        parts = []
        for v in page.Views:
            if v.isDerivedFrom("TechDraw::DrawProjGroup"):
                parts += [x for x in v.Views if x.isDerivedFrom("TechDraw::DrawViewPart")]
            elif v.isDerivedFrom("TechDraw::DrawViewPart"):
                parts.append(v)
        cold = [v for v in parts if not lines_of(v)]
        if not cold:
            return 0, None, set()
        import time

        t0 = time.time()
        for v in cold:
            try:
                v.recompute()
            except Exception:
                pass
        try:
            from ..td_wait import wait_views

            wait_views(cold, timeout=20.0)
        except Exception:
            pass
        still = {v.Name for v in cold if not lines_of(v)}
        warmed = {v.Name for v in cold} - still
        frames.clear()
        for d in page.Views:
            try:
                if d.TypeId == "TechDraw::DrawViewDimension" and d.References2D and d.References2D[0][0].Name in warmed:
                    d.recompute()
            except Exception:
                pass
        return len(cold), round(time.time() - t0, 2), still

    # ---- cosmetic geometry, leaders, finishes, areas ----

    def paper_of3d(v, p3):
        fr = frame_of(v, frames)
        if fr is None:
            raise ToolError("invalid_state", f"{v.Label} has no geometry yet to place against.")
        return to_paper(v, frames, to_view(fr, v, vec(p3, "point")))

    # ---- the rest of TechDraw's commands, headless ----------------------------------------

    def dims_of(refs):
        refs = picks.ref_list(refs, "dims: one or more dimensions by label.")
        return [obj_of(doc(), r, ["TechDraw::DrawViewDimension"], "dimension") for r in refs]


    def colour(c):
        """A colour as the document family reads it ("#rrggbb" or [r, g, b]): (r, g, b, a) in 0…1."""
        from .doc import colour as read

        return read(c)

    def own_prop(o, prop, kind, about):
        """One of Agent Link's own notes on a view (what td_export draws),
        added where the object has none yet; no change FreeCAD has to recompute."""
        if prop not in o.PropertiesList:
            o.addProperty(kind, prop, "AgentLink", about)
            _own_data(o, prop)

    def template_path(tpl):
        """Where a template the caller names is: as given when absolute, in
        the build's template folder when it is there, else in the session's folder."""
        p = os.path.expanduser(tpl)
        if not os.path.isabs(p):
            p = os.path.join(template_root(), p) if os.path.isfile(os.path.join(template_root(), p)) else os.path.join(s.out_dir, p)
        return p

    def clear_samples(t, path):
        """The template's own example values (names, numbers) cleared: they
        are not this drawing's. What FreeCAD fills in itself (today's date,
        the scale) differs from them and stays. Answers the fields cleared."""
        try:
            texts = dict(t.EditableTexts)
            samples = template_defaults(path)
            cleared = [k for k, v in texts.items() if v and samples.get(k) == v and "scale" not in k.lower()]
            if cleared:
                t.EditableTexts = {k: ("" if k in cleared else v) for k, v in texts.items()}
                recompute()
        except Exception:
            cleared = []
        return cleared

    def anchor_at(base, p3):
        """A detail's AnchorPoint for a point on the part: in the base
        view's own frame, unscaled, y up (the view's lines are waited for
        when they are not there yet)."""
        fr = frame_of(base, frames)
        if fr is None:
            recompute([base])
            fr = frame_of(base, frames)
        q = to_view(fr, base, p3)
        sc = fr[0]
        return V(q[0] / sc, -q[1] / sc if fr[1] < 0 else q[1] / sc, 0)

    def extent_dim(v, edges, way):
        """TechDraw's extent dimension over edges of a view (none: the whole
        view), way 0 across, 1 up: the dimension it made, or None."""
        import TechDraw

        before = {o.Name for o in doc().Objects}
        TechDraw.makeExtentDim(v, edges, way)
        recompute()
        return next((o for o in doc().Objects if o.Name not in before and o.isDerivedFrom("TechDraw::DrawViewDimension")), None)

    def one_dim(args):
        """td_dim itself (its entry, run with these arguments): td_dimset makes each of its dimensions with it."""
        return runners.run_steps("td_dim", runners.entries()["td_dim"], args, helpers)

    def sheet_find(ref):
        from . import sheet as SH

        return SH.find(doc(), ref)

    def filled_bounds(ss):
        """The range that holds every filled cell of a sheet ("A1:C4"), or nothing for an empty one."""
        from . import sheet as SH
        from .. import cells as C

        return C.bounds(SH.filled(ss))

    def range_corners(rng):
        """A range's two corners ((row, column), (row, column)) and None; or None and what is wrong with it."""
        from .. import cells as C

        try:
            return C.parse_range(rng), None
        except C.AddressError as e:
            return None, str(e)

    def cell_name(rc):
        from .. import cells as C

        return C.name(*rc)

    def range_text(a_, b_):
        from .. import cells as C

        return C.range_text(a_, b_)

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"extent_dim": extent_dim, "chamfer_angle": chamfer_angle, "nearest_vertices": nearest_vertices, "axo_angles": axo_angles,
               "model_arc_anchor": lambda v, e: model_arc_anchor(v, e, frames), "special_length": lambda v, spec: special_length(v, spec, frames),
               "refresh_special": lambda: refresh_special(doc(), frames), "SPECIAL_PROP": SPECIAL_PROP,
               "paper_of3d": paper_of3d, "dims_of": dims_of, "resolve": lambda ref: picks.resolve(s, ref), "area_text": area_text,
               "without_prefix": without_prefix, "with_decimals": with_decimals, "more_decimals": more_decimals, "prefixed": prefixed,
               "anchor_at": anchor_at, "one_dim": one_dim, "sheet_find": sheet_find, "filled_bounds": filled_bounds, "range_corners": range_corners,
               "cell_name": cell_name, "range_text": range_text, "apply_tol": apply_tol, "dim_reading": dim_reading, "symbol": symbol,
               "next_letter": lambda kind: next_letter(doc(), kind), "resolve_ref": lambda v, r, kind="any": resolve_ref(v, r, frames, kind),
               "gscale": lambda v: gscale(v, frames), "V": V, "vec": vec, "num": num, "view_scale": view_scale, "vertices_of": vertices_of,
               "edge_info": edge_info, "arc_turn": arc_turn, "whole_circles": whole_circles, "describe": gdt.describe, "DIM_TYPES": DIM_TYPES,
               "axis_vector": axis_vector, "section_frame": section_frame, "hide_cut": hide_cut, "curve_name": curve_name, "figure": figure,
               "next_balloon": next_balloon, "make_compound": lambda shapes: __import__("Part").makeCompound(shapes),
               "doc": doc, "recompute": recompute, "done": done, "place_xy": place_xy, "view_reading": view_reading, "page_reading": page_reading,
               "bodies_for": bodies_for, "direction": direction, "leader": leader, "ref_point": ref_point,
               "clear_xy": clear_xy, "paper_half": paper_half, "dim_anchor": dim_anchor, "moved_text": moved_text,
               "nudge_out": nudge_out, "native_hatch": lambda v, src, faces: native_hatch(doc(), v, src, faces),
               "unique": lambda label, *own: s.unique(label, *own), "local": lambda p: paths.local(s, p),
               "pages": lambda: pages(doc()), "page_of": lambda ref: page_of(doc(), ref), "view_of": lambda ref: view_of(doc(), ref),
               "obj_of": lambda ref, types=None, what="object": obj_of(doc(), ref, types, what), "ref_list": picks.ref_list,
               "isfile": os.path.isfile, "relpath": os.path.relpath, "basename": os.path.basename, "sep": os.sep, "dumps": json.dumps,
               # the family's
               "flip_y": lambda v, pts: flip_y(v, frames, pts), "native_marks": native_marks, "native_weld": lambda page, ln, spec: native_weld(doc(), page, ln, spec),
               "tile_reading": tile_reading, "mark_facts": mark_facts, "broken_3d": broken_3d,
               "PAPERS": PAPERS, "PROJ_ITEMS": PROJ_ITEMS, "MARKS_PROP": MARKS_PROP, "HATCH_PROP": HATCH_PROP, "WELD_PROP": WELD_PROP,
               "template_root": template_root, "templates": templates, "find_template": find_template, "template_path": template_path,
               "clear_samples": clear_samples, "load_presets": load_presets, "save_presets": save_presets, "set_enum": set_enum,
               "paper_size": paper_size, "page_holding": page_holding, "edges_of": edges_of, "source_shapes": source_shapes, "abs_xy": abs_xy,
               "pt2": pt2, "circle_centres": circle_centres, "proxy_name": proxy_name, "try_set": try_set, "setprop": setprop, "own_prop": own_prop,
               "edge_on": edge_on, "weld_wrong": weld_wrong, "face_front": face_front,
               # td_list, td_export, td_cosmetic, td_view_more, td_lines
               "warm": warm, "mark_not_ready": mark_not_ready, "GDT_PROP": GDT_PROP, "COSMETIC_PROP": COSMETIC_PROP, "loads": json.loads,
               "page_sheet": lambda page: page_sheet(doc(), page), "made": lambda p: paths.made(s, p), "out_dir": lambda: s.out_dir,
               "join": os.path.join, "getsize": os.path.getsize, "expanduser": os.path.expanduser, "write_out": write_out, "drawn": drawn, "read_text": read_text,
               "write_dxf_page": lambda page, p: TechDraw.writeDXFPage(page, p), "hypot": math.hypot, "vector_of": lambda xyz: V(*xyz),
               "circle_points": circle_points, "mid_line": mid_line, "thread_arc": thread_arc, "side_outline": side_outline, "root_lines": root_lines,
               "coarse_pitch": coarse_pitch, "native_ok": native_ok, "native_cosmetic": native_cosmetic, "drop_native": drop_native,
               "find": lambda ref, what: picks.find(doc(), ref, what), "stack_of": stack_of, "LINE_STYLES": LINE_STYLES,
               "colour": colour, "turn_to_align": turn_to_align,
               "stretched": stretched, "erase_tag": erase_tag}
    return runners.tools(GROUP, s, helpers)

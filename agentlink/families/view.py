# SPDX-License-Identifier: LGPL-2.1-or-later
# Pictures to check the work by. view_render draws the parts without a
# screen (headless too): shaded, from any standard view or several at once,
# cut open, zoomed to a spot, painted with a map — the wall, the stress of a
# solve, or what another add-on registers (a scan's deviation). The picture
# comes back to the agent as an image as well as a file. view_snapshot
# saves the FreeCAD window's own 3D view, when there is one.

import os

import numpy as np

from .. import render
from .. import paths
from .. import geometry as _geo
from .. import runners
from ..protocol import Tool, ToolError
from ..tools import obj
from . import picks

GROUP = "view"
INFO = "Pictures: the parts drawn from any view, cut open, zoomed, with maps (wall, stress, a scan's deviation) — headless; the FreeCAD window's own view."

ALIASES = {"back": "rear", "isometric": "iso"}
GRID = ["iso", "top", "front", "right"]


def snap_grid(n):
    """(columns, rows) for n pictures side by side: 2 across up to 4, then 3."""
    cols = 1 if n <= 1 else 2 if n <= 4 else 3
    return cols, -(-n // cols)


def png_size(path):
    """(width, height) of a PNG file from its header, or None."""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def snap_size(w, h, n, cell=False):
    """(columns, rows, cell width, cell height) for n views: width and
    height are the whole picture (the grid), or each view's with cell."""
    cols, rows = snap_grid(n)
    if cell:
        return cols, rows, w, h
    return cols, rows, max(16, w // cols), max(16, h // rows)


def fit_png(path, w, h):
    """The PNG at path made exactly w x h when it is not (a window on a
    HiDPI screen saves at its pixel ratio): True when it is now. Qt, which
    the window has."""
    got = png_size(path)
    if got == (w, h):
        return True
    try:
        from PySide import QtCore, QtGui
    except ImportError:
        try:
            from PySide6 import QtCore, QtGui
        except ImportError:
            return False
    try:
        img = QtGui.QImage(path)
        if img.isNull():
            return False
        img = img.scaled(w, h, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
        try:
            img.setDevicePixelRatio(1.0)
        except Exception:  # noqa: BLE001
            pass
        return bool(img.save(path, "PNG")) and png_size(path) == (w, h)
    except Exception:  # noqa: BLE001
        return False


class still:
    """While it holds, the view moves at once, not in steps over time:
    FreeCAD turns a view (viewIsometric …) as an animation that goes on
    after the call returns, and its fitAll steps the zoom inside an event
    loop of its own — so a picture taken right after was of a view still
    on its way, and a fit worked out for it was undone as the turn went
    on. The person's setting is put back. A view without the switch is
    left as it is."""

    def __init__(self, view):
        self.view, self.was = view, False

    def __enter__(self):
        try:
            self.was = bool(self.view.isAnimationEnabled())
            if self.was:
                self.view.setAnimationEnabled(False)
        except Exception:  # noqa: BLE001 - no such switch on this view
            self.was = False
        return self

    def __exit__(self, *exc):
        if self.was:
            try:
                self.view.setAnimationEnabled(True)
            except Exception:  # noqa: BLE001
                pass
        return False


FAR = 1e9  # mm: a box reaching past this is not a part's (a datum plane or line has no end: 1e100)


def snap_fit(view, w, h, box=None):
    """Fit the parts to a picture w x h, not to the window: fitAll fits the
    window's shape, so a picture of another shape (a grid's cell, a tall
    one from a wide window) came out with the part a third of the frame.
    Coin's viewAll on the camera for that viewport, the window's fitAll
    when Coin cannot be reached.

    box: the shown parts' own box (shown_box). The camera is framed on a
    cube of that size in its place, as FreeCAD's own viewAll(factor) does
    (View3DInventorViewer.cpp), not on the whole scene graph: FreeCAD's fit
    leaves out what is marked to be skipped (a sketch's grid, a sketch's
    edit layer: SoSkipBoundingGroup), which a plain viewAll of the scene
    graph takes in, with anything else an add-on hangs in the scene. A fit
    of the scene then left the parts a speck (seen live: view_snapshot
    { view: iso, fit: true } answered "a speck" on a 40 mm bracket), and
    the check that follows reads this same box. No box: the scene graph."""
    with still(view):
        view.fitAll()
    try:
        from pivy import coin

        cam = view.getCameraNode()
        region = coin.SbViewportRegion(int(w), int(h))
        size = None
        if box is not None:
            size = [max(float(v), 1e-6) for v in (box.XLength, box.YLength, box.ZLength)]
        if size is not None and 1e-6 < max(size) < 2 * FAR:
            graph = coin.SoSeparator()
            graph.ref()
            try:
                at, cube = coin.SoTranslation(), coin.SoCube()
                c = box.Center
                at.translation.setValue(float(c.x), float(c.y), float(c.z))
                cube.width, cube.height, cube.depth = size
                graph.addChild(at)
                graph.addChild(cube)
                cam.viewAll(graph, region)
            finally:
                graph.unref()
        else:
            cam.viewAll(view.getSceneGraph(), region)
        return True
    except Exception:  # noqa: BLE001 - the window's own fit stands
        return False


def snap_combine(files, names, cols, rows, cw, ch, out):
    """The views' PNGs in one grid PNG at out (Qt, which the window has),
    each labelled; False when it could not be made."""
    try:
        from PySide import QtCore, QtGui
    except ImportError:
        try:
            from PySide6 import QtCore, QtGui
        except ImportError:
            return False
    try:
        img = QtGui.QImage(cw * cols, ch * rows, QtGui.QImage.Format_RGB32)
        try:
            img.setDevicePixelRatio(1.0)
        except Exception:  # noqa: BLE001
            pass
        img.fill(QtGui.QColor(255, 255, 255))
        p = QtGui.QPainter(img)
        try:
            for i, (f, n) in enumerate(zip(files, names)):
                x, y = (i % cols) * cw, (i // cols) * ch
                p.drawImage(QtCore.QRect(x, y, cw, ch), QtGui.QImage(f))
                p.setPen(QtGui.QColor(0, 0, 0))
                p.drawText(x + 8, y + 18, n)
                p.drawRect(x, y, cw - 1, ch - 1)
        finally:
            p.end()
        return bool(img.save(out, "PNG"))
    except Exception:  # noqa: BLE001 - the single files are still there
        return False


def _views(a):
    v = a.get("views", a.get("view", "iso"))
    if v == "all":
        v = GRID
    names = [v] if isinstance(v, str) else list(v or [])
    out = []
    for n in names:
        n = ALIASES.get(str(n).lower(), str(n).lower())
        if n not in render.VIEWS:
            raise ToolError("invalid_input", f"view: one of {', '.join(render.VIEWS)}, a list of up to 6, or \"all\" (iso, top, front, right).")
        out.append(n)
    if not 1 <= len(out) <= 6:
        raise ToolError("invalid_input", "views: 1 to 6.")
    return out


def _vec(v, what):
    if not (isinstance(v, (list, tuple)) and len(v) == 3):
        raise ToolError("invalid_input", f"{what}: [x, y, z] in mm.")
    return [float(x) for x in v]


# Render timings are kept under their own key, by triangles x views: the
# old view_render timings were logged against the document's faces.
RENDER_KEY = "view_render:work"


def render_work(layers, views, w, h):
    """A render's work: the triangles drawn times the views, plus the
    pixels filled (a big picture of a small part still takes its time)."""
    tris = sum(int(len(l["F"])) for l in layers)
    return max(1, tris * max(1, len(views)) + (int(w) * int(h) * max(1, len(views))) // 50)


# A render is sized before it draws (a map of an inspection on a fine
# body's mesh, 230,896 points against a 140k-triangle scan in four views at
# 1400 x 800, froze the window past the watchdog's 120 s): its work
# (render_work) and, from past renders here, its time. Over RENDER_TARGET
# seconds the layers are drawn thinned (render.thin) to fit, the count
# said; a map's own sample (detail) is capped the same way.
RENDER_TARGET = 40.0
# Seconds per unit of work when no render has been timed here yet: on the
# slow side (a 1400 x 800 four-view render of about 75k triangles in 40 s).
RENDER_PRIOR_RATE = 1e-4
# Seconds a render may draw, counted from its call's start (a batch's
# start inside a batch): past it, the views not yet drawn are left and
# said. Under the watchdog's 120 s for a call, with room for the PNG.
RENDER_STOP = 90.0


def _queue():
    try:
        from .. import keep

        return keep.queue_state() or {}
    except Exception:
        return {}


def render_rate(q, work):
    """Seconds per unit of render work here: the typical of past renders
    (view_render:work), else RENDER_PRIOR_RATE. (rate, from history)"""
    from .. import keep

    try:
        r = keep.estimate_range(q, RENDER_KEY, max(1, work))
    except Exception:
        r = None
    if r and r[1] > 0:
        return r[1] / float(max(1, work)), True
    return RENDER_PRIOR_RATE, False


def _said(r):
    from .. import keep

    return keep.said_range(r) + " from past renders here"


def _bodies(s, a, shapeless=None):
    """The parts to draw. shapeless (a list): gets the label of each object
    named that is in the document but has no solid shape, which is then
    left out instead of refused as not there."""
    refs = a.get("objects")
    if refs is None:
        return s.bodies() if s.doc else []
    refs = picks.ref_list(refs)
    out = []
    for r in refs:
        try:
            out.append(s.body(r))
        except ToolError:
            o = None
            try:
                o = next((x for x in s.doc.Objects if x.Label == r or x.Name == r), None)
            except Exception:
                o = None
            if o is None or shapeless is None:
                raise
            shapeless.append(o.Label)
    return out


def _nothing(s, a, shapeless):
    """Why view_render has nothing to draw (emptywhy.nothing_to_draw), from
    the document."""
    from .. import emptywhy

    named = a.get("objects") is not None
    hidden, n, bare = [], 0, list(shapeless)
    try:
        objs = list(s.doc.Objects)
        n = len(objs)
        hidden = [o.Label for o in s.hidden_in(s.doc)]
        if not named:
            bare = [o.Label for o in objs if not s._solid(o) and getattr(o, "TypeId", "") not in s.CONTAINERS and not s.helper(o)]
    except Exception:
        pass
    return emptywhy.nothing_to_draw(hidden=[] if named else hidden, shapeless=bare, objects=n, named=named, layers=list(render.LAYERS))


def _box(layers):
    """{ min, max } of the layers' points, or None."""
    try:
        pts = [np.asarray(l["V"], dtype=float) for l in layers if len(l["V"])]
        if not pts:
            return None
        allp = np.concatenate(pts)
        return {"min": [float(c) for c in allp.min(axis=0)], "max": [float(c) for c in allp.max(axis=0)]}
    except Exception:
        return None


def _snap_shown(s):
    """Whether anything with a shape is visible in the window (True when
    it cannot be read)."""
    try:
        for o in s.doc.Objects:
            try:
                vo = o.ViewObject
                if vo is None or not vo.Visibility:
                    continue
                sh = getattr(o, "Shape", None)
                if (sh is not None and not sh.isNull()) or getattr(o, "Mesh", None) is not None or getattr(o, "Points", None) is not None:
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return True


def _seen(o):
    """Whether nothing that holds o is hidden: a feature keeps its own
    Visibility when its Body or its App::Part is hidden, and is not drawn."""
    for _ in range(32):
        p = None
        for get in ("getParentGeoFeatureGroup", "getParentGroup"):
            try:
                p = getattr(o, get)()
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                break
        if p is None:
            return True
        try:
            if p.ViewObject is not None and not p.ViewObject.Visibility:
                return False
        except Exception:  # noqa: BLE001
            return True
        o = p
    return True


def _placed(o, bb):
    """bb (o's box, in the frame of what holds o) in the document's frame:
    a body in a moved App::Part is drawn where the Part puts it."""
    try:
        move = o.getGlobalPlacement().multiply(o.Placement.inverse())
        if move.isIdentity():
            return bb
        return bb.transformed(move.toMatrix())
    except Exception:  # noqa: BLE001 - as it reads
        return bb


def shown_box(s):
    """(how many objects with a shape, a mesh or points are shown in the
    window, their box together or None). Reads only. What is held by a
    hidden Body or Part is not shown. A shape without an end (a datum
    plane, a datum line: its box reaches 1e100 mm) counts as shown but is
    left out of the box: seen live, such a box could not be fitted (it
    does not go in Coin's numbers) and every corner of it landed on one
    pixel, so a fitted view was called a speck."""
    import FreeCAD

    shown, box = 0, None
    for o in s.doc.Objects:
        try:
            vo = o.ViewObject
            if vo is None or not vo.Visibility:
                continue
            bb = None
            sh = getattr(o, "Shape", None)
            if sh is not None and not sh.isNull():
                bb = sh.BoundBox
            elif _geo.mesh_of(o) is not None and o.Mesh.CountFacets:
                bb = o.Mesh.BoundBox
            elif getattr(o, "Points", None) is not None and o.Points.CountPoints:
                bb = o.Points.BoundBox
            if bb is None or not bb.isValid() or not _seen(o):
                continue
            shown += 1
            if max(abs(float(v)) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)) > FAR:
                continue
            bb = _placed(o, bb)
            if box is None:
                box = FreeCAD.BoundBox(bb)
            else:
                box.add(bb)
        except Exception:
            continue
    return shown, box


def _fit_box(s):
    """The box a fit frames (shown_box's), or None when it cannot be read."""
    try:
        return shown_box(s)[1]
    except Exception:  # noqa: BLE001 - the scene graph is fitted instead
        return None


def _snap_empty(s, view, w=None, h=None, fitted=False):
    """Why the window's view shows nothing or almost nothing of the model
    (emptywhy.off_screen), or None: what is shown, and where the shown
    objects' box lands in the picture w x h as the camera stands (worked
    out from the camera itself: emptywhy.in_picture) — in the window's own
    pixels when the camera cannot be read. fitted: the call fitted the
    view first. Reads only."""
    from .. import emptywhy

    try:
        import FreeCAD

        shown, box = shown_box(s)
        hidden = []
        try:
            hidden = [o.Label for o in s.hidden_in(s.doc)]
        except Exception:
            pass
        pts, size, span = [], tuple(view.getSize()), None
        if box is not None:
            span = {"min": [box.XMin, box.YMin, box.ZMin], "max": [box.XMax, box.YMax, box.ZMax]}
            corners = [(x, y, z) for x in (box.XMin, box.XMax) for y in (box.YMin, box.YMax) for z in (box.ZMin, box.ZMax)]
            cam, own = None, None
            if w and h:
                try:
                    cam = emptywhy.camera_of(view.getCamera())
                except Exception:  # noqa: BLE001
                    cam = None
                own = emptywhy.in_picture(cam, corners, w, h) if cam else None
            if own is not None:
                pts, size = own, (w, h)
            else:
                pts = [tuple(view.getPointOnViewport(FreeCAD.Vector(*c))) for c in corners]
                if size[0] < 16 or size[1] < 16:
                    pts = []  # a view with no size yet (never in front): its pixels say nothing
        return emptywhy.off_screen(pts, size, shown=shown, hidden=hidden, fitted=fitted, box=span)
    except Exception:
        return None


def _same_box(p, q, tol=0.01):
    """Whether two { min, max } boxes are the same within tol of the larger
    one's diagonal (a mesh an add-on already draws as its own layer)."""
    if not p or not q:
        return False
    a0, a1, b0, b1 = (np.asarray(x, dtype=float) for x in (p["min"], p["max"], q["min"], q["max"]))
    d = max(float(np.linalg.norm(a1 - a0)), float(np.linalg.norm(b1 - b0)), 1e-9)
    return float(np.abs(a0 - b0).max()) <= tol * d and float(np.abs(a1 - b1).max()) <= tol * d


def _meshes(s, a, shapeless):
    """The mesh objects to draw. Named: the named ones that have no solid
    shape and are meshes (taken out of shapeless). Else every shown mesh
    that nothing else is built from (a container holding it aside)."""
    if s.doc is None:
        return []
    if a.get("objects") is not None:
        out = []
        for lab in list(shapeless):
            o = next((x for x in s.doc.Objects if x.Label == lab or x.Name == lab), None)
            if o is not None and render.is_mesh(o):
                out.append(o)
                shapeless.remove(lab)
        return out
    out = []
    for o in s.doc.Objects:
        try:
            if not render.is_mesh(o) or not getattr(o, "Visibility", True) or s.helper(o):
                continue
            if any(getattr(p, "TypeId", "") not in s.CONTAINERS for p in (o.InList or [])):
                continue
        except Exception:  # noqa: BLE001
            continue
        out.append(o)
    return out


# ---- the maps Agent Link has ---------------------------------------------------------

def _stress(s, a):
    from . import strength

    r = strength._results(s)  # this study's solve only (round 7: an older study's was drawn)
    if not r or "field" not in r:
        raise ToolError("not_found", "No stress to show: fea_solve first (a solve in this session).")
    o = s.body(r["body"])
    from .. import geometry as geo

    stale = geo.stats(o.Shape) != r["stats"]
    f = r["field"]
    P, vm = np.asarray(f["points"], dtype=float), np.asarray(f["vonMises"], dtype=float)
    L = render.body_layer(o, 0, tol=float(a.get("tolerance", 0.05)))
    cap = int(a.get("detail", 30000))
    V, F = render.subdivide(L["V"], L["F"], render.even_length(L["V"], L["F"], cap), cap=cap)
    # Blended from the nodes on the mesh's outside (fault 17 Nov: each
    # point took its nearest node's value, and the map read in patches; an
    # inner node, lower in bending, coloured the surface near it).
    SP, SV = P, vm
    surf = render.surface_nodes(f.get("elements") or ())
    if len(surf) >= 3 and max(surf) < len(P):
        SP, SV = P[surf], vm[surf]
    # Blended within the time the render leaves it (render.map_budget): a
    # fine FEM mesh's surface nodes against detail 30000 took 330 s before.
    V, F, vals, fit = render.blend_fit(V, F, SP, SV, budget=render.map_budget(s))
    warp = None
    if a.get("deform") not in (None, False, 0):
        # The deformed shape (FEM's warp filter, headless): each spot moved by
        # its nearest node's displacement times deform ("auto": the largest
        # move shown as a twentieth of the part's size).
        U = np.asarray(f.get("displacement") or [], dtype=float)
        if len(U) == len(P):
            mags = np.linalg.norm(U, axis=1)
            k = a["deform"]
            if k in (True, "auto"):
                size = float(np.linalg.norm(np.ptp(np.asarray(V, float), axis=0))) or 1.0
                k = 0.05 * size / float(mags.max()) if mags.max() > 0 else 1.0
            k = float(k)
            idx = np.empty(len(V), dtype=int)
            Vf = np.asarray(V, float)
            for i in range(0, len(Vf), 2048):
                d = ((Vf[i:i + 2048, None, :] - P[None, :, :]) ** 2).sum(-1)
                idx[i:i + 2048] = d.argmin(1)
            V = Vf + k * U[idx]
            warp = round(k, 3)
    y = (r["result"].get("material") or {}).get("yield")
    out = {"layers": [{"name": o.Label, "V": V, "F": F, "values": vals, "creases": True}], "unit": "MPa", "cmap": "jet", "worst": "max", "label": "VON MISES",
           "note": "Von Mises stress from the last solve, blended smoothly from the nearest surface nodes." + (f" Yield {y:g} MPa." if y else "")}
    if warp is not None:
        out["note"] += f" Drawn deformed: displacements × {warp:g}."
        out["deform"] = warp
    if stale:
        out["note"] += " The body changed since the solve: stale — fea_solve again."
        out["stale"] = True
    if fit:
        out["blendThinned"] = dict(fit, nodes=int(len(SP)))
    return out


def _heat(s, a):
    r = getattr(s, "_agentlink_heat", None)
    if not r:
        raise ToolError("not_found", "No temperatures to show: fea_heat first (a solve in this session).")
    o = s.body(r["body"])
    from .. import geometry as geo

    f = r["field"]
    P, T = np.asarray(f["points"], dtype=float), np.asarray(f["celsius"], dtype=float)
    L = render.body_layer(o, 0, tol=float(a.get("tolerance", 0.05)))
    cap = int(a.get("detail", 30000))
    V, F = render.subdivide(L["V"], L["F"], render.even_length(L["V"], L["F"], cap), cap=cap)
    V, F, vals, fit = render.blend_fit(V, F, P, T, budget=render.map_budget(s))
    out = {"layers": [{"name": o.Label, "V": V, "F": F, "values": vals, "creases": True}], "unit": "C", "cmap": "jet", "worst": "max", "label": "TEMPERATURE",
           "note": "Steady temperature from the last fea_heat, blended smoothly from the nearest mesh nodes."}
    if fit:
        out["blendThinned"] = dict(fit, nodes=int(len(P)))
    if geo.stats(o.Shape) != r["stats"]:
        out["note"] += " The body changed since: stale — fea_heat again."
        out["stale"] = True
    return out


render.register_map("stress", _stress, "Von Mises stress of the last fea_solve.")
render.register_map("heat", _heat, "Temperature of the last fea_heat (red hot).")


def tools(session):
    s = session

    def view_render(a):
        import time as _time

        t0 = _time.time()
        views = _views(a)
        w, h = int(a.get("width", 900 if len(views) > 1 else 800)), int(a.get("height", 700 if len(views) > 1 else 600))
        if not (64 <= w <= 3000 and 64 <= h <= 3000):
            raise ToolError("invalid_input", "width and height: 64 to 3000 px.")
        section = a.get("section")
        if section is not None:
            if not isinstance(section, dict):
                raise ToolError("invalid_input", "section: { axis: x|y|z or [x, y, z], offset (mm, along it; the middle when left out), flip }.")
            ax = section.get("axis", "x")
            if not (ax in ("x", "y", "z") or (isinstance(ax, list) and len(ax) == 3 and any(float(c) for c in ax))):
                raise ToolError("invalid_input", "section axis: x, y, z or [x, y, z].")
        frame = None
        if a.get("zoom") is not None:
            z = a["zoom"]
            if not isinstance(z, dict) or "at" not in z:
                raise ToolError("invalid_input", "zoom: { at: [x, y, z], size: mm across (20) } — e.g. a finding's at.")
            frame = {"at": _vec(z["at"], "zoom at"), "size": float(z.get("size", 20))}
            if frame["size"] <= 0:
                raise ToolError("invalid_input", "zoom size: mm across, over 0.")

        layers, shown = [], []
        shapeless = []
        capped_detail = None
        map_took, blend_cut, meshes, n_bodies = 0.0, None, [], 0
        mapname = a.get("map")
        mapinfo = None
        if mapname:
            if mapname not in render.MAPS:
                raise ToolError("invalid_input", f"map: one of {', '.join(render.MAPS) or 'none here'}.")
            # The map's own sample (detail) capped to what this render can
            # draw in time; the drawing is thinned below as well.
            q0 = _queue()
            rate, _hist = render_rate(q0, 1)
            cap0 = render.triangle_cap(views, w, h, rate, RENDER_TARGET)
            ma = a
            if isinstance(a.get("detail"), (int, float)) and not isinstance(a.get("detail"), bool) and a["detail"] > cap0:
                ma = dict(a, detail=int(cap0))
                capped_detail = (int(a["detail"]), int(cap0))
            from .. import emptywhy

            # The map's own reading (a blend from a solve's nodes, rays for a
            # wall) has until RENDER_TARGET from the call's start
            # (render.map_budget), so the drawing still has its time before
            # the RENDER_STOP cut (test drive of 20 Nov, finding 4).
            bn0 = getattr(s, "batch_now", None)
            s.render_deadline = ((bn0.get("t0") if isinstance(bn0, dict) else None) or t0) + RENDER_TARGET
            tm = _time.time()
            try:
                m = render.MAPS[mapname][0](s, ma)
            except ToolError as e:
                if e.code != "not_found":
                    raise
                # No data to colour by (no solve yet, no scan loaded): said,
                # with no picture.
                return {"empty": emptywhy.no_map(mapname, e.message), "map": mapname}
            finally:
                s.render_deadline = None
            map_took = _time.time() - tm
            blend_cut = m.get("blendThinned")
            vals = np.concatenate([np.asarray(l["values"], dtype=float) for l in m["layers"]]) if m["layers"] else np.zeros(0)
            fin = vals[np.isfinite(vals)]
            if not len(fin):
                return {"empty": emptywhy.no_map(mapname, "it read no value on any point here" + (f" ({m['note']})" if m.get("note") else "")
                                                 + " — for wall: the body must be a closed solid (body_check), and reach (mm) at least its thickest wall."), "map": mapname}
            rng = a.get("range") or m.get("range")
            if rng:
                lo, hi = float(rng[0]), float(rng[1])
            elif m.get("symmetric"):
                hi = float(np.percentile(np.abs(fin), 99)) or 1e-6
                lo = -hi
            else:
                lo, hi = float(np.percentile(fin, 1)), float(np.percentile(fin, 99))
                if m.get("worst") == "min":
                    lo = min(0.0, float(fin.min()))
            if hi <= lo:
                hi = lo + 1e-6
            for l in m["layers"]:
                l["colors"] = render.colours_for(l["values"], lo, hi, m.get("cmap", "jet"))
                layers.append(l)
                shown.append({"layer": l["name"], "triangles": int(len(l["F"])), "map": mapname})
            # The worst spot: where to look (zoom: { at } it).
            allV = np.concatenate([np.asarray(l["V"], dtype=float) for l in m["layers"]])
            key = {"min": vals, "max": -vals, "abs": -np.abs(vals)}.get(m.get("worst", "max"), -vals)
            key = np.where(np.isfinite(vals), key, np.inf)
            k = int(np.argmin(key))
            mapinfo = {"range": [lo, hi], "unit": m.get("unit", ""), "cmap": m.get("cmap", "jet"), "label": m.get("label", mapname.upper())}
            summary = {"name": mapname, "unit": m.get("unit", ""), "range": [round(lo, 4), round(hi, 4)], "min": round(float(fin.min()), 4), "max": round(float(fin.max()), 4),
                       "worst": {"value": round(float(vals[k]), 4), "at": [round(float(c), 2) for c in allV[k]]}, "note": m.get("note", "")}
            unread = float((~np.isfinite(vals)).mean())
            if unread > 0:
                summary["unread"] = f"{unread:.0%} (grey)"
            for kk in ("stale", "warning"):
                if kk in m:
                    summary[kk] = m[kk]
        else:
            summary = None
            for i, o in enumerate(_bodies(s, a, shapeless)):
                l = render.body_layer(o, i, tol=float(a.get("tolerance", 0.05)))
                layers.append(l)
                shown.append({"layer": o.Label, "triangles": int(len(l["F"]))})
            meshes = _meshes(s, a, shapeless)
        n_bodies = len(layers)
        want = a.get("layers")
        for name, (fn, _) in render.LAYERS.items():
            if want is not None and name not in want:
                continue
            if mapname and any(sh["layer"] == name for sh in shown):
                continue
            for l in fn(s, a) or []:
                if mapname and l.get("mapped"):
                    continue
                layers.append(l)
                shown.append({"layer": l["name"], "triangles": int(len(l["F"]))})
        # Meshes (a Textured result, an imported STL) after the add-ons'
        # layers: one an add-on already draws as its own layer (a scan) is
        # not drawn twice (test drive of 20 Nov, finding 6: a mesh was "no solid
        # shape" and not drawn at all).
        drawn_counts = {(int(len(l["V"])), int(len(l["F"]))) for l in layers}
        addon_boxes = [b for b in (_box([l]) for l in layers[n_bodies:]) if b] if meshes else []
        for o in meshes:
            try:
                l = render.mesh_layer(o, len(layers))
            except Exception:  # noqa: BLE001 - an empty or broken mesh: said, not drawn
                shapeless.append(o.Label)
                continue
            if not len(l["F"]):
                shapeless.append(o.Label)
                continue
            if a.get("objects") is None and ((int(len(l["V"])), int(len(l["F"]))) in drawn_counts or any(_same_box(_box([l]), b) for b in addon_boxes)):
                continue
            layers.append(l)
            shown.append({"layer": o.Label, "triangles": int(len(l["F"])), "mesh": True})
        if want is not None:
            unknown = [x for x in want if x not in render.LAYERS]
            if unknown:
                raise ToolError("invalid_input", f"layers: {', '.join(render.LAYERS) or 'none here'} (the parts are always drawn; objects picks which).")
        if not layers:
            # No picture, and why: a blank image would say nothing.
            return {"empty": _nothing(s, a, shapeless)}
        render.distinct_colours(layers)
        # Sized before it draws: the triangles of every layer (the map's,
        # a scan's) times the views, and the time that takes here. Over
        # RENDER_TARGET the big layers are thinned to fit (the count said);
        # a map's colours are worked out on the thinned layer, its numbers
        # (min, max, worst) on the full one above.
        q = _queue()
        work0 = render_work(layers, views, w, h)
        rate, hist = render_rate(q, work0)
        thinned = []
        if work0 * rate > RENDER_TARGET:
            layers, thinned = render.fit_layers(layers, render.triangle_cap(views, w, h, rate, RENDER_TARGET))
        if mapinfo:
            for l in layers:
                if l.get("values") is not None and (l.get("colors") is None or l.get("thinnedFrom")):
                    l["colors"] = render.colours_for(l["values"], mapinfo["range"][0], mapinfo["range"][1], mapinfo.get("cmap", "jet"))
        # The work: triangles drawn times views — what a render's time
        # follows. Logged against it (heavy.WORK), and the time it should
        # take said from past renders here at that work.
        work = render_work(layers, views, w, h)
        try:
            from .. import keep
        except Exception:
            keep = None
        expected = None
        try:
            expected = keep.estimate_range(q, RENDER_KEY, work) if keep else None
        except Exception:
            pass
        if expected and map_took:
            # The map's own reading is already spent: the time said is it
            # plus the drawing's (it was the drawing's alone: "expected 3 s"
            # for a 330 s stress map).
            expected = tuple(x + map_took for x in expected)
        # Logged in the drawing's units, the map's seconds in them too, so
        # the time per unit stays the drawing's.
        s.heavy_work = (RENDER_KEY, work + int(map_took / max(rate, 1e-12)))
        # The watchdog times the call from its start (a batch's start inside
        # a batch: the batch is one call to it). A render that may run long
        # marks itself heavy so the watchdog waits for it, and stops drawing
        # at RENDER_STOP from that start whatever its estimate said.
        bn = getattr(s, "batch_now", None)
        started = (bn.get("t0") if isinstance(bn, dict) else None) or t0
        est = work * rate
        stop_at = started + RENDER_STOP
        marked = False
        if keep is not None and est > 10.0:
            try:
                keep.mark_heavy_call("view_render", max(est, (_time.time() - started + RENDER_STOP + 30.0) / 3.0), work)
                marked = True
            except Exception:
                pass
        cut = []
        cover = {}
        try:
            img, across, drawn = render.compose(layers, views, w, h, frame=frame, section=section, mapinfo=mapinfo, stop_at=stop_at, cut=cut, cover=cover)
        finally:
            if marked:
                keep.clear_heavy_call()
        data = render.png(img)
        p = paths.out_file(s, "view_render", a.get("path") or f"render_{'_'.join(views)}{'_' + mapname if mapname else ''}.png", ".png")
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        out = {"path": p, "views": views, "mmAcross": across, "layers": shown, "width": w, "height": h, "bytes": len(data),
               "time": {"took": round(_time.time() - t0, 1), "triangles": int(sum(len(l["F"]) for l in layers)),
                        **({"map": round(map_took, 1)} if mapname else {}),
                        **({"expected": _said(expected)} if expected else {})}}
        if thinned:
            out["thinned"] = {"layers": thinned, "why": f"drawn on fewer triangles to finish in about {RENDER_TARGET:g} s here (" + ("from past renders" if hist else "a first render here: a cautious guess") + f", {int(work0):,} units of work as asked); the map's numbers are read on every point. A zoom or fewer views draws finer."}
        if capped_detail:
            out["detailCapped"] = {"asked": capped_detail[0], "used": capped_detail[1], "why": "the map's sample capped to what this render draws in time"}
        if blend_cut:
            asked = capped_detail[0] if capped_detail else a.get("detail", "default")
            out["detailCapped"] = {"asked": asked, "used": blend_cut["to"],
                                   "why": f"the map's blend from {blend_cut.get('nodes', 0):,} nodes would take about {blend_cut['estimate']:g} s, over the {blend_cut['budget']:g} s it has "
                                          f"in this render: the map was thinned from {blend_cut['from']:,} to {blend_cut['to']:,} triangles before blending, so its min, max "
                                          "and worst are read on the thinned map. A smaller detail or a zoom draws finer in time."}
        if cut:
            out["cut"] = {"views": cut, "why": f"stopped drawing at {RENDER_STOP:g} s into the call so the watchdog does not take FreeCAD for hung; fewer views, a zoom, or a smaller picture draws them"}
        if summary:
            out["map"] = summary
        if section:
            out["section"] = section
        if frame:
            out["zoom"] = frame
        if a.get("objects") is None and s.doc is not None:
            # Never silent about what is left out: a hidden part is not drawn
            # (a boolean's kept inputs drew nothing and nothing said so).
            try:
                hid = [o.Label for o in s.hidden_in(s.doc)]
            except Exception:
                hid = []
            if hid:
                out["hidden"] = "hidden, not drawn: " + ", ".join(hid) + " — objects: [names] draws them too."
        if shapeless:
            out["notDrawn"] = f"no solid shape, so not drawn: {', '.join(shapeless)}"
        from .. import emptywhy

        why = emptywhy.off_frame(cover, frame, section, _box(layers)) if not cut else None
        if why is None and not drawn:
            why = "Nothing landed in the picture: the zoom or the cut leaves the parts out of view."
        if why:
            # The file is written; the blank picture is not sent to be looked at.
            out["empty"] = why
        elif a.get("inline", True):
            out["_png"] = data
        if frame:
            out["fitted"] = False  # framed on the zoom, not fitted to the parts
        return out

    SNAP_TURN = {"iso": "viewIsometric", "front": "viewFront", "rear": "viewRear", "top": "viewTop", "bottom": "viewBottom", "left": "viewLeft", "right": "viewRight"}

    # ---- view_maps and view_snapshot are data (agentlink/data/tools.json): what their entries call ----

    def gui_up():
        """Whether this FreeCAD has a window."""
        import FreeCAD

        return bool(FreeCAD.GuiUp)

    def active_view():
        """The window's 3D view of the session's document, or None when the
        document has none open."""
        import FreeCADGui

        gd = FreeCADGui.getDocument(s.doc.Name)
        view = gd.activeView() if gd else None
        if view is not None and not hasattr(view, "saveImage"):
            # A drawing page or a spreadsheet is the document's front tab: its 3D view behind it.
            try:
                more = gd.mdiViewsOfType("Gui::View3DInventor")
                view = more[0] if more else view
            except Exception:  # noqa: BLE001 - as it was
                pass
        return view

    def turn(view, name):
        """The view turned to a standard view (SNAP_TURN: FreeCAD's own
        viewFront, viewIsometric …)."""
        with still(view):
            getattr(view, SNAP_TURN[name])()

    def nothing_shown():
        """Why a grid of views would show nothing (emptywhy.off_screen), or
        None: nothing with a shape is visible in the window."""
        from .. import emptywhy

        return emptywhy.off_screen([], None, shown=0, hidden=[o.Label for o in s.hidden_in(s.doc)]) if not _snap_shown(s) else None

    def shots(view, views, cw, ch, bg, fit):
        """Each view saved on its own (turned, fitted when asked, cw x ch),
        the person's camera put back afterwards whatever happens. The files."""
        try:
            cam = view.getCamera()
        except Exception:
            cam = None
        each = []
        try:
            for n in views:
                turn(view, n)
                if fit:
                    snap_fit(view, cw, ch, _fit_box(s))
                q = paths.out_file(s, "view_snapshot", f"snapshot_{n}.png", ".png")
                view.saveImage(q, cw, ch, bg)
                fit_png(q, cw, ch)
                each.append(q)
        finally:
            if cam is not None:
                try:
                    view.setCamera(cam)
                except Exception:
                    pass
        return each

    def read_bytes(p):
        """A file's bytes (the picture sent back with the answer)."""
        with open(p, "rb") as f:
            return f.read()

    helpers = {
        "maps": lambda: render.MAPS, "layers": lambda: render.LAYERS, "views": lambda: list(render.VIEWS),
        "SNAP_TURN": SNAP_TURN, "GRID": GRID, "alias": lambda n: ALIASES.get(str(n).lower(), str(n).lower()),
        "gui_up": gui_up, "active_view": active_view, "turn": turn,
        "snap_fit": lambda view, w, h: snap_fit(view, w, h, _fit_box(s)), "snap_empty": lambda view, w=None, h=None, fitted=False: _snap_empty(s, view, w, h, fitted), "nothing_shown": nothing_shown,
        "snap_size": snap_size, "shots": shots, "snap_combine": snap_combine, "fit_png": fit_png, "png_size": png_size,
        "out_file": lambda name: paths.out_file(s, "view_snapshot", name, ".png"),
        "filesize": os.path.getsize, "read_bytes": read_bytes,
    }

    vschema = {"description": "A view (iso, top, bottom, front, rear, left, right, iso-front-left, iso-rear-left, iso-rear-right), a list of up to 6 drawn side by side, or \"all\"."}
    return [
        Tool(
            "view_render",
            "Draw the parts as a picture and look at it; works headless. It draws the shown parts, without the containers that hold them (an assembly, an "
            "App::Part, a group). Shown meshes are drawn too, for example an imported STL or a texture result, but not with a map. Hidden parts are not drawn, and the answer names them (hidden). objects: [names] draws those named. views: one or several (\"all\": "
            "iso, top, front, right, each fitted). "
            "front looks from -Y toward +Y (it shows the -Y side), with Z up. top looks down -Z, with +Y up the screen. right looks from +X, rear from +Y, left from -X. "
            "iso looks from the front, the right and above. map: wall (thickness, red thin), stress (the last fea_solve), heat (the last fea_heat), or an add-on's map "
            "(view_maps lists them). A map has a legend and the worst spot's at. range: [lo, hi] fixes the colours. section { axis x|y|z, offset mm, flip }: cuts "
            "it open (cut faces hatched). zoom { at, size mm }: frames a spot, for example a finding's at. layers: which add-on layers (a scan …). The PNG comes "
            "back as an image (inline false: the file only) and is written to path. Limits: the size is calculated before it draws: every layer's triangles times "
            "the views, timed from past renders here. time gives took and expected. After about 40 s, the big layers are drawn thinned (thinned: from and to). A "
            "map's min, max and worst still use every point. A larger detail is limited (detailCapped). The map's own reading has until 40 s into the call. A blend that "
            "would take longer is thinned before it starts, and detailCapped says so. time.map gives its seconds, and expected includes them. At 90 s into the call (in a batch, from its start), it "
            "stops and names the views left (cut). Fewer views, a zoom or a smaller picture draws them. An empty picture is answered in words, with no image. empty "
            "tells why and what to do. Reasons: no shown body (the document is empty, every part is hidden, or nothing has a solid shape). The objects named have "
            "no solid shape (notDrawn names them when others were drawn). The zoom or section puts the parts out of frame, or below 0.2% of the picture (with the "
            "parts' box). The map has no data (no solve in this session, no wall read). fitted: false marks a picture framed by zoom, not fitted to the parts.",
            obj({
                "view": vschema, "views": vschema,
                "map": {"type": "string"}, "range": {"type": "array", "items": {"type": "number"}},
                "section": {"type": "object"}, "zoom": {"type": "object"},
                "objects": {}, "layers": {"type": "array", "items": {"type": "string"}},
                "reach": {"type": "number"}, "tolerance": {"type": "number"}, "deform": {"description": "map stress: draw the deformed shape, displacements times this (\"auto\" scales the largest to a twentieth of the part)."}, "detail": {"type": "integer", "description": "How many small triangles a map is read on (wall 16000, stress 30000): more is finer and slower; capped to what the render can draw in time (detailCapped says so)."},
                "width": {"type": "integer"}, "height": {"type": "integer"}, "inline": {"type": "boolean"}, "path": {"type": "string"},
            }),
            view_render,
        ),
    ] + runners.tools(GROUP, s, helpers)

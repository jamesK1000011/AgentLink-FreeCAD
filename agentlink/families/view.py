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


def snap_fit(view, w, h):
    """Fit the parts to a picture w x h, not to the window: fitAll fits the
    window's shape, so a picture of another shape (a grid's cell, a tall
    one from a wide window) came out with the part a third of the frame.
    Coin's viewAll on the camera for that viewport, the window's fitAll
    when Coin cannot be reached."""
    view.fitAll()
    try:
        from pivy import coin

        cam = view.getCameraNode()
        cam.viewAll(view.getSceneGraph(), coin.SbViewportRegion(int(w), int(h)))
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


def _snap_empty(s, view):
    """Why the window's view shows nothing or almost nothing of the model
    (emptywhy.off_screen), or None: what is shown, and where the shown
    objects' box lands in the view's pixels. Reads only."""
    from .. import emptywhy

    try:
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
                elif getattr(o, "Mesh", None) is not None and o.Mesh.CountFacets:
                    bb = o.Mesh.BoundBox
                elif getattr(o, "Points", None) is not None and o.Points.CountPoints:
                    bb = o.Points.BoundBox
                if bb is None or not bb.isValid():
                    continue
                shown += 1
                if box is None:
                    box = FreeCAD.BoundBox(bb)
                else:
                    box.add(bb)
            except Exception:
                continue
        hidden = []
        try:
            hidden = [o.Label for o in s.hidden_in(s.doc)]
        except Exception:
            pass
        pts = []
        if box is not None:
            for x in (box.XMin, box.XMax):
                for y in (box.YMin, box.YMax):
                    for z in (box.ZMin, box.ZMax):
                        pts.append(tuple(view.getPointOnViewport(FreeCAD.Vector(x, y, z))))
        return emptywhy.off_screen(pts, tuple(view.getSize()), shown=shown, hidden=hidden)
    except Exception:
        return None


# ---- the maps Agent Link has ---------------------------------------------------------

def _stress(s, a):
    r = getattr(s, "_agentlink_fea", None)
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
    vals = render.nearest_values(V, P, vm)
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
           "note": "Von Mises stress from the last solve, at the nearest mesh node." + (f" Yield {y:g} MPa." if y else "")}
    if warp is not None:
        out["note"] += f" Drawn deformed: displacements × {warp:g}."
        out["deform"] = warp
    if stale:
        out["note"] += " The body changed since the solve: stale — fea_solve again."
        out["stale"] = True
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
    out = {"layers": [{"name": o.Label, "V": V, "F": F, "values": render.nearest_values(V, P, T), "creases": True}], "unit": "C", "cmap": "jet", "worst": "max", "label": "TEMPERATURE",
           "note": "Steady temperature from the last fea_heat, at the nearest mesh node."}
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

            try:
                m = render.MAPS[mapname][0](s, ma)
            except ToolError as e:
                if e.code != "not_found":
                    raise
                # No data to colour by (no solve yet, no scan loaded): said,
                # with no picture.
                return {"empty": emptywhy.no_map(mapname, e.message), "map": mapname}
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
        s.heavy_work = (RENDER_KEY, work)
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
                        **({"expected": _said(expected)} if expected else {})}}
        if thinned:
            out["thinned"] = {"layers": thinned, "why": f"drawn on fewer triangles to finish in about {RENDER_TARGET:g} s here (" + ("from past renders" if hist else "a first render here: a cautious guess") + f", {int(work0):,} units of work as asked); the map's numbers are read on every point. A zoom or fewer views draws finer."}
        if capped_detail:
            out["detailCapped"] = {"asked": capped_detail[0], "used": capped_detail[1], "why": "the map's sample capped to what this render draws in time"}
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

    def view_maps(a):
        return {"maps": [{"name": n, "about": about} for n, (_, about) in render.MAPS.items()],
                "layers": [{"name": n, "about": about} for n, (_, about) in render.LAYERS.items()],
                "views": list(render.VIEWS)}

    SNAP_TURN = {"iso": "viewIsometric", "front": "viewFront", "rear": "viewRear", "top": "viewTop", "bottom": "viewBottom", "left": "viewLeft", "right": "viewRight"}

    def snap_views(a):
        """The views asked for: view (one) or views (a list, up to 6, or
        "all"); [] keeps the person's view."""
        v = a.get("views")
        if v is None:
            v = a.get("view")
            v = [v] if v else []
        elif v == "all":
            v = list(GRID)
        elif isinstance(v, str):
            v = [v]
        if not isinstance(v, list):
            raise ToolError("invalid_input", f"views: a list of {', '.join(SNAP_TURN)} (up to 6), or \"all\".")
        out = []
        for n in v:
            n = ALIASES.get(str(n).lower(), str(n).lower())
            if n not in SNAP_TURN:
                raise ToolError("invalid_input", f"view: one of {', '.join(SNAP_TURN)}, or left out to keep the person's view.")
            out.append(n)
        if len(out) > 6:
            raise ToolError("invalid_input", "views: 1 to 6.")
        return out

    def view_snapshot(a):
        import FreeCAD

        views = snap_views(a)
        w, h = int(a.get("width", 800)), int(a.get("height", 600))
        if not (16 <= w <= 4096 and 16 <= h <= 4096):
            raise ToolError("invalid_input", "width and height: 16 to 4096 px.")
        if not FreeCAD.GuiUp:
            raise ToolError("unavailable", "view_snapshot is the FreeCAD window's own view: there is no window (headless). view_render draws the parts without one.")
        import FreeCADGui

        gd = FreeCADGui.getDocument(s.doc.Name)
        view = gd.activeView() if gd else None
        if view is None or not hasattr(view, "saveImage"):
            raise ToolError("unavailable", "No 3D view open for this document: open one in FreeCAD, then again — or view_render.")
        bg = a.get("background", "Current")
        if len(views) <= 1:
            which = views[0] if views else None
            fitted = False
            if which:
                getattr(view, SNAP_TURN[which])()
                if a.get("fit", True):
                    snap_fit(view, w, h)
                    fitted = True
            # Nothing (or a speck) of the model in the view: said, with no
            # picture taken to look at.
            why = _snap_empty(s, view)
            if why:
                return {"empty": why, "view": which or "as the person left it", "fitted": fitted}
            p = paths.out_file(s, "view_snapshot", a.get("path") or f"snapshot_{which or 'current'}.png", ".png")
            view.saveImage(p, w, h, bg)
            fit_png(p, w, h)
            got = png_size(p) or (w, h)
            out = {"path": p, "view": which or "as the person left it", "width": got[0], "height": got[1], "bytes": os.path.getsize(p)}
            if not fitted:
                out["fitted"] = False
                out["fitNote"] = ("Not re-fitted: the view is as the person left it (its zoom and pan), so parts may be cut off or out of frame."
                                  if not which else "Turned but not re-fitted (fit: false): the zoom is the person's, so parts may be cut off.")
            if got != (w, h):
                out["warning"] = f"Asked {w} x {h}; FreeCAD saved {got[0]} x {got[1]} and it could not be resized here."
            if a.get("inline", True):
                with open(p, "rb") as f:
                    out["_png"] = f.read()
            return out
        # Several views: each saved on its own, then one grid picture of them
        # (2 across up to 4, 3 across for 5 or 6). The person's camera is put
        # back afterwards.
        # width and height are the whole picture; cell: true makes them each
        # view's (the grid then cols x that).
        cols, rows, cw, ch = snap_size(w, h, len(views), bool(a.get("cell")))
        if cw * cols > 8192 or ch * rows > 8192:
            raise ToolError("invalid_input", f"cell {cw} x {ch} in a {cols} x {rows} grid is {cw * cols} x {ch * rows} px: 8192 at most each way.")
        from .. import emptywhy

        why = emptywhy.off_screen([], None, shown=0, hidden=[o.Label for o in s.hidden_in(s.doc)]) if not _snap_shown(s) else None
        if why:
            return {"empty": why, "views": views}
        try:
            cam = view.getCamera()
        except Exception:
            cam = None
        each = []
        try:
            for n in views:
                getattr(view, SNAP_TURN[n])()
                if a.get("fit", True):
                    snap_fit(view, cw, ch)
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
        p = paths.out_file(s, "view_snapshot", a.get("path") or f"snapshot_{'_'.join(views)}.png", ".png")
        combined = snap_combine(each, views, cols, rows, cw, ch, p)
        out = {"views": views, "paths": each, "width": cw * cols, "height": ch * rows, "grid": [cols, rows], "cell": [cw, ch],
               **({} if a.get("fit", True) else {"fitted": False, "fitNote": "Turned but not re-fitted (fit: false): each view keeps the person's zoom, so parts may be cut off or out of frame."}),
               "sizeIs": "each view's (cell: true)" if a.get("cell") else "the whole grid (cell: true makes it each view's)",
               "note": "The person's own view is put back."}
        if combined:
            got = png_size(p)
            if got and got != (cw * cols, ch * rows):
                fit_png(p, cw * cols, ch * rows)
                got = png_size(p) or got
            if got:
                out["width"], out["height"] = got
            out["path"] = p
            out["bytes"] = os.path.getsize(p)
            if a.get("inline", True):
                with open(p, "rb") as f:
                    out["_png"] = f.read()
        else:
            out["warning"] = "The views could not be put in one picture here: each view's own file is in paths."
        return out

    vschema = {"description": "A view (iso, top, bottom, front, rear, left, right, iso-front-left, iso-rear-left, iso-rear-right), a list of up to 6 drawn side by side, or \"all\"."}
    return [
        Tool(
            "view_render",
            "Draw the parts as a picture and look at it — works headless. The parts shown, without the containers that hold them (an assembly, an App::Part, a group); hidden parts are not drawn and the answer names them (hidden); objects: [names] draws those named. views: one or several (\"all\": iso, top, front, right, each fitted). "
            "map: wall (thickness, red thin), stress (the last fea_solve), heat (the last fea_heat), or an add-on's (view_maps lists them) — with a legend and the worst spot's at; range [lo, hi] fixes the colours. "
            "section { axis x|y|z, offset mm, flip } cuts it open (cut faces hatched). zoom { at, size mm } frames a spot — a finding's at. layers: which add-on layers (a scan …). The PNG comes back as an image (inline false: the file only) and is written to path. "
            "Limits: sized before it draws (every layer's triangles times the views, timed from past renders here: time gives took and expected). Past about 40 s the big layers are drawn thinned (thinned: from and to; a map's min, max and worst are still read on every point) and a larger detail is capped (detailCapped). "
            "At 90 s into the call (a batch's start, in a batch) it stops drawing and names the views left (cut): fewer views, a zoom or a smaller picture draws them. "
            "An empty picture is answered in words, with no image sent: empty says why and what to do — no shown body (the document is empty, every part is hidden, or nothing has a solid shape), the objects named have no solid shape (notDrawn names them when others were drawn), the zoom or section leaves the parts out of frame or under 0.2% of the picture (with the parts' box), or the map has no data (no solve in this session, no wall read). fitted: false marks a picture framed by zoom rather than fitted to the parts.",
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
        Tool("view_maps", "The maps and layers view_render can draw here (add-ons add theirs), and the views.", obj({}), view_maps),
        Tool("view_snapshot", "Save the FreeCAD window's own 3D view as the person sees it (view: turn it to a standard view first, fit true) and look at it. views [..] (up to 6, or \"all\") gives one grid picture of them, each view's file in paths, and puts the person's view back. width and height (800 x 600) are the whole picture — the grid with several views, split among them; cell: true makes them each view's size instead. The answer gives the sizes as saved. When nothing with a shape is shown (an empty document, everything hidden), or the model lies outside the frame or is under 6 pixels across as the view stands, the answer is empty with the reason and what to do, and no picture is taken. fitted: false with fitNote says the view was not re-fitted (no view given: as the person left it; or fit: false), so parts may be cut off. Needs the window; view_render draws without one.", obj({"cell": {"type": "boolean", "description": "width and height are each view's in the grid, not the whole grid's."}, "view": {"type": "string"}, "views": {"description": "A list of views (iso, top, bottom, front, rear, left, right), up to 6, or \"all\" (iso, top, front, right): one grid picture."}, "fit": {"type": "boolean"}, "width": {"type": "integer"}, "height": {"type": "integer"}, "background": {"type": "string"}, "inline": {"type": "boolean"}, "path": {"type": "string"}}), view_snapshot),
    ]

# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's own reader for the geometry of an ASCII DXF: LINE, ARC,
# CIRCLE, ELLIPSE, POINT, LWPOLYLINE, POLYLINE (2D and 3D, with its bulges
# and its closed flag) and SPLINE (control points with knots and weights, or
# fit points). FreeCAD's importer (Import.readDXF) dropped the closing edge
# of a closed 3D POLYLINE (flag 70 = 9: 39 of 40 edges) and refused a SPLINE
# by fit points ("PropertyLinkList does not support external object"), so
# import_file reads these here and leaves the rest of a drawing (blocks,
# text, dimensions, hatches) to FreeCAD's importer. parse() is pure Python;
# shapes() builds Part edges and wires and needs FreeCAD.

import math

SUPPORTED = ("LINE", "ARC", "CIRCLE", "ELLIPSE", "POINT", "LWPOLYLINE", "POLYLINE", "SPLINE")
# Entities that are bookkeeping, not drawing.
QUIET = ("VERTEX", "SEQEND", "VIEWPORT", "ENDBLK", "BLOCK")


def _pairs(text):
    lines = text.splitlines()
    for i in range(0, len(lines) - 1, 2):
        code = lines[i].strip()
        try:
            yield int(code), lines[i + 1].strip()
        except ValueError:
            continue


def _num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def read(path):
    """parse() of a DXF file; None for a binary DXF (FreeCAD's reader)."""
    with open(path, "rb") as f:
        head = f.read(22)
    if head.startswith(b"AutoCAD Binary DXF"):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return parse(f.read())


def parse(text):
    """{"entities": [{type, layer, …}], "other": {type: count} (entities
    this reader leaves to FreeCAD's), "units": $INSUNITS or None}."""
    pairs = list(_pairs(text))
    units = None
    for k, (c, v) in enumerate(pairs):
        if c == 9 and v == "$INSUNITS" and k + 1 < len(pairs):
            units = int(_num(pairs[k + 1][1]))
            break
    # The ENTITIES section only (blocks hold geometry INSERT places).
    start = end = None
    for k in range(len(pairs) - 1):
        if pairs[k] == (0, "SECTION") and pairs[k + 1] == (2, "ENTITIES"):
            start = k + 2
        elif start is not None and k >= start and pairs[k] == (0, "ENDSEC"):
            end = k
            break
    if start is None:
        return {"entities": [], "other": {}, "units": units}
    body = pairs[start:end]
    # Split into entities: each starts at a 0 group.
    raw = []
    for c, v in body:
        if c == 0:
            raw.append([v, []])
        elif raw:
            raw[-1][1].append((c, v))
    out, other = [], {}
    k = 0
    while k < len(raw):
        kind, g = raw[k]
        k += 1
        if kind == "POLYLINE":
            verts = []
            while k < len(raw) and raw[k][0] == "VERTEX":
                verts.append(raw[k][1])
                k += 1
            if k < len(raw) and raw[k][0] == "SEQEND":
                k += 1
            e = _polyline(g, verts)
        elif kind in SUPPORTED:
            e = {"LINE": _line, "ARC": _arc, "CIRCLE": _circle, "ELLIPSE": _ellipse, "POINT": _point,
                 "LWPOLYLINE": _lwpolyline, "SPLINE": _spline}[kind](g)
        else:
            if kind not in QUIET:
                other[kind] = other.get(kind, 0) + 1
            continue
        if e is None:
            other[kind] = other.get(kind, 0) + 1
            continue
        e.setdefault("layer", _first(g, 8, "0"))
        e["type"] = kind
        out.append(e)
    return {"entities": out, "other": other, "units": units}


def _first(g, code, d=None):
    for c, v in g:
        if c == code:
            return v
    return d


def _xyz(g, cx=10):
    return [_num(_first(g, cx)), _num(_first(g, cx + 10)), _num(_first(g, cx + 20))]


def _ocs(g):
    return [_num(_first(g, 210), 0.0), _num(_first(g, 220), 0.0), _num(_first(g, 230), 1.0)]


def _line(g):
    return {"points": [_xyz(g, 10), _xyz(g, 11)]}


def _point(g):
    return {"points": [_xyz(g, 10)]}


def _arc(g):
    return {"center": _xyz(g), "radius": _num(_first(g, 40)), "start": _num(_first(g, 50)), "end": _num(_first(g, 51), 360.0), "ocs": _ocs(g)}


def _circle(g):
    return {"center": _xyz(g), "radius": _num(_first(g, 40)), "ocs": _ocs(g)}


def _ellipse(g):
    return {"center": _xyz(g, 10), "major": _xyz(g, 11), "ratio": _num(_first(g, 40), 1.0),
            "start": _num(_first(g, 41), 0.0), "end": _num(_first(g, 42), 2 * math.pi), "ocs": _ocs(g)}


def _lwpolyline(g):
    pts, bulges = [], []
    elev = _num(_first(g, 38), 0.0)
    for c, v in g:
        if c == 10:
            pts.append([_num(v), 0.0, elev])
            bulges.append(0.0)
        elif c == 20 and pts:
            pts[-1][1] = _num(v)
        elif c == 42 and bulges:
            bulges[-1] = _num(v)
    flags = int(_num(_first(g, 70), 0))
    return {"points": pts, "bulges": bulges, "closed": bool(flags & 1), "ocs": _ocs(g)}


def _polyline(g, verts):
    flags = int(_num(_first(g, 70), 0))
    if flags & (16 | 64):
        return None  # a polygon mesh or a polyface: FreeCAD's reader
    pts, bulges = [], []
    for v in verts:
        vf = int(_num(_first(v, 70), 0))
        if vf & 16:
            continue  # a spline's frame point, not on the curve
        pts.append(_xyz(v))
        bulges.append(_num(_first(v, 42), 0.0))
    three_d = bool(flags & 8)
    e = {"points": pts, "bulges": [0.0] * len(pts) if three_d else bulges, "closed": bool(flags & 1), "is3d": three_d,
         "layer": _first(g, 8, "0")}
    if not three_d:
        e["ocs"] = _ocs(g)
    return e


def _spline(g):
    flags = int(_num(_first(g, 70), 0))
    degree = int(_num(_first(g, 71), 3))
    knots, weights, ctrl, fit = [], [], [], []
    for c, v in g:
        if c == 40:
            knots.append(_num(v))
        elif c == 41:
            weights.append(_num(v))
        elif c == 10:
            ctrl.append([_num(v), 0.0, 0.0])
        elif c == 20 and ctrl:
            ctrl[-1][1] = _num(v)
        elif c == 30 and ctrl:
            ctrl[-1][2] = _num(v)
        elif c == 11:
            fit.append([_num(v), 0.0, 0.0])
        elif c == 21 and fit:
            fit[-1][1] = _num(v)
        elif c == 31 and fit:
            fit[-1][2] = _num(v)
    t0 = [_num(_first(g, 12)), _num(_first(g, 22)), _num(_first(g, 32))] if _first(g, 12) is not None else None
    t1 = [_num(_first(g, 13)), _num(_first(g, 23)), _num(_first(g, 33))] if _first(g, 13) is not None else None
    return {"degree": degree, "closed": bool(flags & 1), "periodic": bool(flags & 2), "rational": bool(flags & 4),
            "knots": knots, "weights": weights, "control": ctrl, "fit": fit, "startTangent": t0, "endTangent": t1}


# ---- the arbitrary axis algorithm (OCS to world), pure ------------------------------------

def ocs_axes(n):
    """The OCS x, y, z axes for extrusion direction n (DXF's arbitrary axis
    algorithm)."""
    L = math.sqrt(sum(c * c for c in n)) or 1.0
    nz = [c / L for c in n]
    if abs(nz[0]) < 1.0 / 64 and abs(nz[1]) < 1.0 / 64:
        ax = _cross([0.0, 1.0, 0.0], nz)
    else:
        ax = _cross([0.0, 0.0, 1.0], nz)
    la = math.sqrt(sum(c * c for c in ax)) or 1.0
    ax = [c / la for c in ax]
    ay = _cross(nz, ax)
    return ax, ay, nz


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def to_world(p, n):
    if n is None or (abs(n[0]) < 1e-12 and abs(n[1]) < 1e-12 and n[2] > 0):
        return list(p)
    ax, ay, az = ocs_axes(n)
    return [p[0] * ax[i] + p[1] * ay[i] + p[2] * az[i] for i in range(3)]


def bulge_mid(a, b, bulge):
    """The middle point of a bulged segment from a to b (2D, z of a): the
    bulge is tan(angle / 4), positive counter-clockwise."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return None
    sagitta = bulge * chord / 2
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    # The arc bulges to the right of a->b for a negative bulge, left for positive.
    nx, ny = -dy / chord, dx / chord
    return [mx - nx * sagitta, my - ny * sagitta, a[2]]


def segments(e):
    """A polyline's pieces as ("line", a, b) / ("arc", a, mid, b), the
    closing one included when the polyline is closed; OCS points."""
    pts, bul = e["points"], e.get("bulges") or [0.0] * len(e["points"])
    n = len(pts)
    pairs = [(i, i + 1) for i in range(n - 1)]
    if e.get("closed") and n > 2 and any(abs(pts[0][k] - pts[-1][k]) > 1e-9 for k in range(3)):
        pairs.append((n - 1, 0))
    out = []
    for i, j in pairs:
        a, b = pts[i], pts[j]
        if all(abs(a[k] - b[k]) < 1e-12 for k in range(3)):
            continue
        if abs(bul[i]) > 1e-12:
            m = bulge_mid(a, b, bul[i])
            if m is not None:
                out.append(("arc", a, m, b))
                continue
        out.append(("line", a, b))
    return out


# ---- FreeCAD shapes ---------------------------------------------------------------------

def shape(e):
    """A Part shape for one entity; raises with the reason when it cannot."""
    import FreeCAD
    import Part

    V = FreeCAD.Vector
    t = e["type"]
    if t == "LINE":
        return Part.makeLine(V(*e["points"][0]), V(*e["points"][1]))
    if t == "POINT":
        return Part.Vertex(V(*e["points"][0]))
    if t in ("CIRCLE", "ARC"):
        ax, ay, az = ocs_axes(e["ocs"])
        c = V(*to_world(e["center"], e["ocs"]))
        circ = Part.Circle(c, V(*az), e["radius"])
        circ.XAxis = V(*ax)
        if t == "CIRCLE":
            return circ.toShape()
        a0, a1 = math.radians(e["start"]), math.radians(e["end"])
        if a1 <= a0:
            a1 += 2 * math.pi
        return Part.ArcOfCircle(circ, a0, a1).toShape()
    if t == "ELLIPSE":
        c = V(*e["center"])
        major = V(*e["major"])
        n = V(*e["ocs"])
        R = major.Length
        el = Part.Ellipse(c + major, c + n.cross(major).normalize() * (R * e["ratio"]), c)
        a0, a1 = e["start"], e["end"]
        if abs((a1 - a0) - 2 * math.pi) < 1e-9 or abs(a1 - a0) < 1e-12:
            return el.toShape()
        if a1 <= a0:
            a1 += 2 * math.pi
        return Part.ArcOfEllipse(el, a0, a1).toShape()
    if t in ("LWPOLYLINE", "POLYLINE"):
        n = e.get("ocs")
        edges = []
        for seg in segments(e):
            pts = [V(*to_world(p, n)) for p in seg[1:]]
            if seg[0] == "line":
                edges.append(Part.makeLine(pts[0], pts[1]))
            else:
                edges.append(Part.Arc(pts[0], pts[1], pts[2]).toShape())
        if not edges:
            raise ValueError("no segments")
        w = Part.Wire(edges)
        return w
    if t == "SPLINE":
        bs = Part.BSplineCurve()
        if e["control"] and e["knots"]:
            poles = [V(*p) for p in e["control"]]
            knots, mults = [], []
            for k in e["knots"]:
                if knots and abs(k - knots[-1]) < 1e-10:
                    mults[-1] += 1
                else:
                    knots.append(k)
                    mults.append(1)
            weights = e["weights"] if len(e["weights"]) == len(poles) else None
            if sum(mults) != len(poles) + e["degree"] + 1:
                raise ValueError(f"{len(e['knots'])} knots for {len(poles)} control points of degree {e['degree']} (needs {len(poles) + e['degree'] + 1})")
            bs.buildFromPolesMultsKnots(poles, mults, knots, False, e["degree"], weights)
        elif len(e["fit"]) >= 2:
            pts = [V(*p) for p in e["fit"]]
            closed = e["closed"] and (pts[0] - pts[-1]).Length > 1e-9
            if e["closed"] and not closed:
                pts = pts[:-1]
                closed = True
            if e.get("startTangent") and e.get("endTangent") and not closed:
                bs.interpolate(pts, InitialTangent=V(*e["startTangent"]), FinalTangent=V(*e["endTangent"]))
            else:
                bs.interpolate(pts, PeriodicFlag=closed)
        else:
            raise ValueError("neither control points with knots nor two fit points")
        return bs.toShape()
    raise ValueError(f"{t} is not read here")

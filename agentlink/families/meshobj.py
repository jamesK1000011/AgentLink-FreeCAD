# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD's Mesh and MeshPart workbenches on the document's mesh objects
# (an add-on's scan tools work on the scan in its own session instead):
# a body meshed three ways, a mesh evaluated and repaired as the Mesh
# workbench's Evaluate & Repair does, decimated, refined, smoothed, offset,
# trimmed by a plane, transformed, joined by booleans, cut into
# cross-sections, split into its pieces and into planar or curved segments,
# its curvature measured (and drawn), and a shape projected onto it.

import math
import os

import FreeCAD
import Mesh  # noqa: F401 — the family stands on the Mesh module; left out without it
import Part

import numpy as np

from .. import geometry as geo
from .. import meshbool
from .. import meshdist
from .. import render
from .. import store
from .. import runners
from .. import paths
from ..protocol import ToolError, bad
from . import picks

GROUP = "mesh"
INFO = ("FreeCAD's Mesh workbench on document meshes: mesh a body, evaluate and repair, decimate, refine, smooth, offset, trim, transform, "
        "booleans, cross-sections, split, planar and curvature segments, curvature, projection onto a mesh.")

V = FreeCAD.Vector


def meshes(doc):
    return [o for o in doc.Objects if o.isDerivedFrom("Mesh::Feature")]


def reading(m):
    out = {"points": m.CountPoints, "facets": m.CountFacets, "solid": bool(m.isSolid()), "components": int(m.countComponents()),
           "area": round(m.Area, 3), "box": geo.box_json(m, 3)["size"]}
    if out["solid"]:
        out["volume"] = round(m.Volume, 3)
    return out


def arrays(m):
    """A Mesh's points (where they stand, its Placement applied) and facets."""
    pts, tris = m.Topology
    V = np.array([[p.x, p.y, p.z] for p in pts], dtype=float).reshape(-1, 3)
    return V, np.array(tris, dtype=np.int64).reshape(-1, 3)


def from_arrays(V, F):
    """A Mesh of points V and facets F as they are: given as (points,
    facets), so no point is merged with a near one; as triangles of points
    where this FreeCAD does not take that form."""
    F = np.asarray(F, dtype=np.int64).reshape(-1, 3)
    try:
        m = Mesh.Mesh()
        m.addFacets(([FreeCAD.Vector(*p) for p in np.asarray(V, dtype=float).tolist()], [tuple(t) for t in F.tolist()]))
        if m.CountFacets == len(F):
            return m
    except Exception:
        pass
    m = Mesh.Mesh()
    m.addFacets([[tuple(V[i]) for i in t] for t in F.tolist()])
    return m


def in_place(m):
    """A copy of a Mesh with its points where they stand and no placement
    of its own (addMesh and transform work on the stored points and pass a
    placement by)."""
    g = m.copy()
    pl = g.Placement
    if not pl.isIdentity():
        g.Placement = FreeCAD.Placement()
        g.transform(pl.toMatrix())
    return g


def vec(v, name, default=None):
    """[x, y, z] numbers as a Vector, refused by name."""
    if v is None and default is not None:
        v = list(default)
    if not (isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)):
        raise bad(f"{name}: [x, y, z] numbers.")
    return V(*[float(x) for x in v])


def edges_state(m):
    """open: edges one facet has; bad: edges more than two share."""
    F = np.array(m.Topology[1], dtype=np.int64).reshape(-1, 3)
    if len(F) == 0:
        return {"open": 0, "bad": 0, "facets": 0}
    a, b = F.reshape(-1), F[:, [1, 2, 0]].reshape(-1)
    n = int(F.max()) + 1
    _, c = np.unique(np.minimum(a, b) * n + np.maximum(a, b), return_counts=True)
    return {"open": int((c == 1).sum()), "bad": int((c > 2).sum()), "facets": int(len(F))}


def worse(after, before):
    """Whether a repair step left the mesh worse than it found it: more open
    or overloaded edges, or nothing left."""
    return after["facets"] == 0 or after["open"] > before["open"] or after["bad"] > before["bad"]


def evaluation(m):
    """The Mesh workbench's Evaluate & Repair checks, read."""
    e = {}
    checks = (("nonManifolds", "hasNonManifolds"), ("selfIntersections", "hasSelfIntersections"), ("flippedNormals", "hasNonUniformOrientedFacets"),
              ("corruptedFacets", "hasCorruptedFacets"), ("invalidPoints", "hasInvalidPoints"), ("pointsOnEdges", "hasPointsOnEdge"),
              ("indicesOutOfRange", "hasFacetsOutOfRange"), ("invalidNeighbours", "hasInvalidNeighbourhood"))
    for k, f in checks:
        try:
            e[k] = bool(getattr(m, f)())
        except Exception:
            pass
    try:
        e["flippedCount"] = int(m.countNonUniformOrientedFacets())
    except Exception:
        pass
    try:
        # the pairs are found a second time to be listed: only when there are any
        e["selfIntersectionPairs"] = len(m.getSelfIntersections()) if e.get("selfIntersections") else 0
    except Exception:
        pass
    e["open"] = not m.isSolid()
    problems = [k for k, v in e.items() if v is True and k != "open"] + (["open (holes)"] if e["open"] else [])
    return e, problems


def _curv_map(s, a):
    ref = a.get("mesh") or (a.get("objects") or [None])[0]
    ms = meshes(s.doc)
    o = next((x for x in ms if ref in (x.Label, x.Name)), None) if ref else (ms[-1] if ms else None)
    if o is None:
        raise ToolError("not_found", "No mesh to show: meshobj_from_shape or import_file one.")
    m = o.Mesh
    V_ = np.array([[p.x, p.y, p.z] for p in m.Points], dtype=float)
    F_ = np.array([list(f.PointIndices) for f in m.Facets], dtype=int)
    c = np.array([(k[0], k[1]) for k in m.getCurvaturePerVertex()], dtype=float)  # k1, k2 (and their directions) per point
    kind = a.get("curvature", "mean")
    vals = {"mean": (c[:, 0] + c[:, 1]) / 2, "gauss": c[:, 0] * c[:, 1], "max": np.max(np.abs(c), axis=1)}.get(kind, (c[:, 0] + c[:, 1]) / 2)
    lo5, hi95 = float(np.percentile(vals, 5)), float(np.percentile(vals, 95))
    if lo5 < 0 < hi95:  # concave and convex: zero in the middle
        m_ = max(-lo5, hi95) or 1.0
        rng = [-m_, m_]
    else:  # all one way: the colours spent on its own spread
        rng = [lo5, hi95] if hi95 > lo5 else [lo5 - 1e-6, hi95 + 1e-6]
    return {"layers": [{"name": o.Label, "V": V_, "F": F_, "values": vals, "creases": True}], "unit": "1/mm", "cmap": "jet", "range": rng,
            "worst": "abs", "label": f"CURVATURE ({kind.upper()})", "note": f"{o.Label}: {kind} curvature at each point (1 / radius); 5% beyond the colours' ends."}


render.register_map("curvature", _curv_map, "A document mesh's curvature (mesh names which; curvature mean | gauss | max).")


# The tools themselves are data (agentlink/data/tools.json; run by
# agentlink/runners.py's steps runner). What follows is what their entries
# call by name (docs/data-tools.md): each is one thing FreeCAD's Mesh API or
# the geometry needs known, said in its docstring.

def show(o, visible):
    """An object shown or hidden in the window, where it has a view (none headless)."""
    if o is not None and getattr(o, "ViewObject", None) is not None:
        o.ViewObject.Visibility = visible


def mesh_shape(kw):
    """MeshPart.meshFromShape with the settings of one of its meshers (kw's
    names choose it: LinearDeflection, MaxLength or Fineness)."""
    import MeshPart

    return MeshPart.meshFromShape(**kw)


def outward(m):
    """A closed mesh whose normals point in (negative volume) turned inside out."""
    if m.isSolid() and m.Volume < 0:
        m.flipNormals()


def repair_step(m, w, a):
    """One of Evaluate & Repair's fixes by its name here, as the FreeCAD
    calls it takes (tolerance, maxHoleEdges and minFacets from the call)."""
    if w == "indices":
        m.fixIndices()
        m.rebuildNeighbourHood()
    elif w == "duplicates":
        m.removeDuplicatedPoints()
        m.removeDuplicatedFacets()
    elif w == "degenerate":
        m.fixDegenerations(float(a.get("tolerance", 1e-6)))
        m.removeNeedles(float(a.get("tolerance", 1e-6)) * 1000)
    elif w == "nonmanifolds":
        m.removeNonManifolds()
        m.removeNonManifoldPoints()
    elif w == "selfintersections":
        m.fixSelfIntersections()
    elif w == "folds":
        m.removeFoldsOnSurface()
    elif w == "normals":
        m.harmonizeNormals()
        outward(m)
    elif w == "holes":
        m.fillupHoles(int(a.get("maxHoleEdges", 50)))
    elif w == "islands":
        m.removeComponents(int(a.get("minFacets", 10)))
    elif w == "pointsonedges":
        m.removePointsOnEdge(False)


def plane_sides(m, p, n):
    """(gone, crossed): the triangles wholly on the side of the plane
    (through p) that n points to, and those the plane crosses. Each cut one
    comes back from trimByPlane as one or two, so the count after is no
    measure of what went (a cube cut in half has 14 triangles where it had 12)."""
    P0, F0 = arrays(m)
    side = ((P0 - np.array([p.x, p.y, p.z])) @ np.array([n.x, n.y, n.z]) / n.Length)[F0] if len(F0) else np.zeros((0, 3))
    gone = int(np.sum((side >= -1e-7).all(axis=1) & (side > 1e-7).any(axis=1)))
    crossed = int(np.sum((side > 1e-7).any(axis=1) & (side < -1e-7).any(axis=1)))
    return gone, crossed


def merge_cut(m):
    """After trimByPlane: it adds the split triangles with points of their
    own, so the strip along the cut came back as a second component, its
    seam as two extra open loops, and closing then capped all three.
    Merging the points first leaves the one cut loop."""
    m.removeDuplicatedPoints()
    m.removeDuplicatedFacets()
    m.fixIndices()


def cap(m, edges):
    """A cut's open loops (up to edges long) filled flat, the triangles facing out."""
    m.fillupHoles(edges)
    m.harmonizeNormals()
    outward(m)


def shift(v):
    """A matrix that moves by v."""
    t = FreeCAD.Matrix()
    t.move(v)
    return t


def mirror_matrix(axis):
    """A matrix that flips the sign of "x", "y" or "z" (x mirrors across the YZ plane through the origin)."""
    mm = FreeCAD.Matrix()
    setattr(mm, {"x": "A11", "y": "A22", "z": "A33"}[axis], -1.0)
    return mm


def through_placement(m, mat):
    """mat as Mesh.transform needs it: transform moves the stored points,
    before the mesh's own placement is applied, so the change is carried
    through it and a mesh that has been placed turns and moves in the
    document's axes like any other."""
    pl = m.Placement
    if pl.isIdentity():
        return mat
    pm = pl.toMatrix()
    return pm.inverse().multiply(mat).multiply(pm)


def own_boolean(x, y, op):
    """Agent Link's own boolean of two meshes (numpy, any density: only the
    triangles the other mesh crosses are cut, the rest kept as they are):
    (mesh, None, False); (None, why, False) when it refuses or its result
    does not read back closed; (None, None, True) when nothing is left."""
    try:
        V_, F, _, _ = meshbool.boolean(*arrays(x), *arrays(y), {"union": "add", "intersection": "intersect", "difference": "subtract"}[op])
        if len(F) == 0:
            return None, None, True
        res = from_arrays(V_, F)
        if not res.isSolid():
            return None, "its result did not read back closed", False
        return res, None, False
    except meshbool.BooleanError as e:
        return None, str(e), False


def freecad_boolean(x, y, op):
    """FreeCAD's Mesh boolean (it comes back open on dense meshes); None when it throws."""
    mx = x.copy()
    try:
        return {"union": mx.unite, "intersection": mx.intersect, "difference": mx.difference}[op](y)
    except Exception:
        return None


def solid_boolean(x, y, op):
    """The boolean through solids: each mesh sewn into a solid (0.01 mm), then Part's fuse, common or cut."""
    def solid(m):
        sh = Part.Shape()
        sh.makeShapeFromMesh(m.Topology, 0.01)
        return Part.makeSolid(Part.makeShell(sh.Faces))

    sa, sb = solid(x), solid(y)
    return {"union": sa.fuse, "intersection": sa.common, "difference": sa.cut}[op](sb)


def reach(bb, n):
    """(lo, hi): a box's reach along the unit vector n — each axis gives its low or its high end, by n's sign there."""
    ends = [(bb.XMin * n.x, bb.XMax * n.x), (bb.YMin * n.y, bb.YMax * n.y), (bb.ZMin * n.z, bb.ZMax * n.z)]
    return sum(min(e) for e in ends), sum(max(e) for e in ends)


def loops(sec):
    """One cross-section's polylines as wires. A plane through a row of the
    mesh's own edges is answered twice over: each loop once; a polyline of
    one point, or one that makes no wire, is left out."""
    ws = []
    sec, _twice = meshdist.once_each([[(q.x, q.y, q.z) for q in map(V, pl)] for pl in sec])
    for pl in sec:
        pts = [V(*p) for p in pl]
        if len(pts) >= 2:
            try:
                ws.append(Part.makePolygon(pts))
            except Exception:
                pass
    return ws


def mean_normal(sub):
    """A mesh patch's normal: its facets' normals weighted by their areas, of length 1 (zero for none)."""
    nrm = V()
    for f in sub.Facets:
        nrm += V(f.Normal) * f.Area
    if nrm.Length > 1e-12:
        nrm.normalize()
    return nrm


def curvature_stats(m, flat):
    """A mesh's curvature per point (FreeCAD's two principal curvatures)
    in a few numbers: how many points are flat (both under flat, 1/mm), the
    tightest and the median radius, the mean curvature's range."""
    c = np.array([(k[0], k[1]) for k in m.getCurvaturePerVertex()], dtype=float).reshape(-1, 2)
    k1, k2 = c[:, 0], c[:, 1]
    mean = (k1 + k2) / 2
    kmax = np.max(np.abs(c), axis=1)
    share = float(np.mean(kmax < float(flat)) * 100)
    r = 1 / np.maximum(kmax, 1e-12)
    return {"points": int(len(c)), "flatPercent": round(share, 2),
            "tightestRadius": round(float(np.min(r)), 4), "medianRadius": round(float(np.median(r[kmax > 1e-6])) if (kmax > 1e-6).any() else math.inf, 3),
            "meanCurvature": {"min": round(float(mean.min()), 5), "max": round(float(mean.max()), 5)}}


def polylines(polys):
    """A projection's polylines as wires: FreeCAD's polyline repeats the
    points where its stretches join, and runs out and back along a
    triangle's chord where a sample lands on a mesh edge — both taken out."""
    clean = [meshdist.no_spurs([(q.x, q.y, q.z) for q in map(V, pl)]) for pl in polys]
    return [Part.makePolygon([V(*q) for q in pl]) for pl in clean if len(pl) >= 2]


def project_on(shape, m, d):
    """MeshPart's projection of a shape's edges onto a mesh along d: polylines."""
    import MeshPart

    return MeshPart.projectShapeOnMesh(shape, m, d)


def file_ext(path):
    """A path's extension, lower case, without its dot ("" for none)."""
    return os.path.splitext(str(path))[1].lower().lstrip(".")


def open_edges(m):
    """The edges one triangle has, as pairs of point numbers, counted in
    numpy (a dict of every edge took seconds on a dense scan); None for a
    mesh without triangles."""
    F = np.array(m.Topology[1], dtype=np.int64).reshape(-1, 3)
    if len(F) == 0:
        return None
    e0, e1 = F.reshape(-1), F[:, [1, 2, 0]].reshape(-1)
    lo_, hi_ = np.minimum(e0, e1), np.maximum(e0, e1)
    nn = int(F.max()) + 1
    keys, cnt = np.unique(lo_ * nn + hi_, return_counts=True)
    return [(int(k // nn), int(k % nn)) for k in keys[cnt == 1]]


def edge_loops(edges):
    """Open edges chained end to end into loops of point numbers (a closed one ends where it starts)."""
    nbr = {}
    for p0, p1 in edges:
        nbr.setdefault(p0, []).append(p1)
        nbr.setdefault(p1, []).append(p0)
    seen = set()
    found = []
    for p0, p1 in edges:
        if (p0, p1) in seen:
            continue
        chain = [p0, p1]
        seen.add((p0, p1))
        while True:
            last, prev = chain[-1], chain[-2]
            nxt = next((q for q in nbr[last] if q != prev and (min(last, q), max(last, q)) not in seen), None)
            if nxt is None:
                break
            seen.add((min(last, nxt), max(last, nxt)))
            chain.append(nxt)
            if nxt == chain[0]:
                break
        found.append(chain)
    return found


def has_module(name):
    """Whether this FreeCAD's Python has a module (flatmesh is left out of some builds)."""
    import importlib.util

    return importlib.util.find_spec(name) is not None


def surface_kind(face):
    """A face's surface by its class name: Plane, Cylinder, Cone, BSplineSurface …"""
    return type(face.Surface).__name__


def flat_pattern(face, tolerance):
    """A plane's, cylinder's or cone's face rolled out exactly, without
    stretch: (the outlines as flat2d items, what a cone adds to the answer).
    A cylinder's side is its turn's length by its height; a cone's (a
    frustum) two arcs between two straight edges; a plane its own wires
    (tolerance: how finely they are walked)."""
    srf = face.Surface
    kind = type(srf).__name__

    def flat(p):
        u, v = srf.parameter(p)
        if kind == "Cylinder":
            return (srf.Radius * u, v)
        if kind == "Cone":
            sa = math.sin(srf.SemiAngle)
            rho = (srf.Radius + v * sa) / abs(sa)
            th = u * abs(sa)
            return (rho * math.cos(th), rho * math.sin(th))
        return (u, v)

    u0, u1, v0, v1 = face.ParameterRange
    if kind == "Plane":
        return [{"kind": "line", "points": [list(flat(p)) for p in w.discretize(Deflection=float(tolerance))], "closed": True, "layer": "cut"}
                for w in face.Wires], {}
    if kind == "Cylinder":
        w_, h_ = srf.Radius * (u1 - u0), v1 - v0
        return [{"kind": "line", "points": [[0, 0], [w_, 0], [w_, h_], [0, h_]], "closed": True, "layer": "cut"}], {}
    sa = math.sin(srf.SemiAngle)
    r0, r1 = sorted([(srf.Radius + v0 * sa) / abs(sa), (srf.Radius + v1 * sa) / abs(sa)])
    span = (u1 - u0) * abs(sa)
    n = max(16, int(math.degrees(span) / 3))
    outer = [(r1 * math.cos(span * i / n), r1 * math.sin(span * i / n)) for i in range(n + 1)]
    inner = [(r0 * math.cos(span * (n - i) / n), r0 * math.sin(span * (n - i) / n)) for i in range(n + 1)]
    return ([{"kind": "line", "points": [list(q) for q in outer + inner], "closed": True, "layer": "cut"}],
            {"radii": [round(r0, 3), round(r1, 3)], "angle": round(math.degrees(span), 3)})


def outline_area(poly):
    """The area inside a flat outline [[x, y], …] (the shoelace sum)."""
    return abs(sum(x0_ * y1_ - x1_ * y0_ for (x0_, y0_), (x1_, y1_) in zip(poly, poly[1:] + poly[:1]))) / 2


def face_arrays(face, tolerance):
    """A face tessellated to tolerance mm: its points and triangles as arrays."""
    vs, ts = face.tessellate(tolerance)
    return np.array([(v.x, v.y, v.z) for v in vs], float), np.array(ts, int)


UNWRAP_MARK = "agentlink-unwrap: "


def unwrap_stop(stderr, returncode):
    """How the unwrapping's own Python ended, from its error stream and its
    exit code: ("load", why) when it had begun loading FreeCAD's modules and
    never finished (a crash or an error at import), else ("stopped", why).
    why: its last own word (not one of the marks), or the code it ended with."""
    lines = (stderr or "").strip().splitlines()
    marks = [x[len(UNWRAP_MARK):].strip() for x in lines if x.startswith(UNWRAP_MARK)]
    said = [x for x in lines if not x.startswith(UNWRAP_MARK)]
    why = said[-1] if said else f"it stopped (code {returncode})"
    return ("load" if "loading" in marks and "loaded" not in marks else "stopped"), why


def flatten_apart(P, F, iters, weight):
    """FreeCAD's flatmesh on a surface (points P, triangles F), run in a
    Python of its own: flatmesh can bring FreeCAD down on a surface it
    cannot handle, and a crash there is then only a refusal. Answers
    (flat points, boundary loops, None, None), or (None, None, stop, why):
    stop "python" (no Python to run it in apart from FreeCAD), "time" (over
    5 minutes), "load" (it ended while FreeCAD's own modules were being
    loaded there, before any unwrapping: the surface is not at fault) or
    "stopped" (why: its last word). It marks where it is on its error
    stream (UNWRAP_MARK), so that a crash with no word of its own (seen
    live: code -11 on a sphere's cap of 1,651 triangles) says which:
    "loading" … "loaded" for FreeCAD's modules, "unwrapping" … "unwrapped"
    for flatmesh's own work. The outlines are found here (flat_loops), not
    by flatmesh."""
    import subprocess
    import sys
    import tempfile

    d = tempfile.mkdtemp(prefix="agentlink-unwrap-")
    src, dst = os.path.join(d, "in.npz"), os.path.join(d, "out.npz")
    np.savez(src, P=P, F=F)
    code = (
        "import sys, numpy as np\n"
        f"def at(where):\n    sys.stderr.write({UNWRAP_MARK!r} + where + chr(10))\n    sys.stderr.flush()\n"
        "at('loading')\n"
        "import FreeCAD, Part, Mesh  # flatmesh stands on them: loaded first\n"
        "import flatmesh\n"
        "at('loaded')\n"
        "z = np.load(sys.argv[1])\n"
        "at('unwrapping')\n"
        "fl = flatmesh.FaceUnwrapper(np.ascontiguousarray(z['P'], dtype=np.float64), np.ascontiguousarray(z['F'], dtype=np.int64))\n"
        f"fl.findFlatNodes({iters}, {weight})\n"
        "at('unwrapped')\n"
        "np.savez(sys.argv[2], Q=np.asarray(fl.ze_nodes, float))\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([x for x in sys.path if x])
    exe = sys.executable if sys.executable and "python" in os.path.basename(sys.executable).lower() else None
    if exe is None:
        # FreeCAD's window is its own program, not a Python: the one shipped
        # with it (beside it, or in the Mac bundle's Resources/bin) runs it.
        from .. import testrun
        from .app import _bundle_python

        exe = testrun.real_python(sys.executable) or _bundle_python()
    if exe is None:
        return None, None, "python", None
    try:
        r = subprocess.run([exe, "-c", code, src, dst], env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None, None, "time", None
    if r.returncode != 0 or not os.path.isfile(dst):
        stop, why = unwrap_stop(r.stderr, r.returncode)
        return None, None, stop, why
    z = np.load(dst)
    Q = np.asarray(z["Q"], float)[:, :2]
    return Q, flat_loops(Q, F), None, None


def flat_loops(Q, F):
    """The flat pattern's outlines: the surface's open edges (one triangle
    each) chained into loops, as arrays of flat points. Worked out here,
    not by flatmesh's getFlatBoundaryNodes: that walk reads past the end of
    its own table where two outlines meet at one point (a point on four
    open edges) and brings its Python down (FreeCAD's MeshFlattening.cpp,
    getBoundaries)."""
    F = np.asarray(F, dtype=np.int64).reshape(-1, 3)
    if len(F) == 0:
        return []
    e0, e1 = F.reshape(-1), F[:, [1, 2, 0]].reshape(-1)
    lo_, hi_ = np.minimum(e0, e1), np.maximum(e0, e1)
    nn = int(F.max()) + 1
    keys, cnt = np.unique(lo_ * nn + hi_, return_counts=True)
    edges = [(int(k // nn), int(k % nn)) for k in keys[cnt == 1]]
    return [np.asarray(Q, float)[chain, :2] for chain in edge_loops(edges) if len(chain) >= 3]


def stretch(P, Q, F):
    """How a surface (points P, triangles F) was stretched to lie flat as
    Q: its area before and after, and each triangle's change of area as a
    share — the mean and the most, in percent."""
    def area(X, T):
        A, B, C = X[T[:, 0]], X[T[:, 1]], X[T[:, 2]]
        if X.shape[1] == 2:
            return 0.5 * np.abs((B[:, 0] - A[:, 0]) * (C[:, 1] - A[:, 1]) - (B[:, 1] - A[:, 1]) * (C[:, 0] - A[:, 0]))
        return 0.5 * np.linalg.norm(np.cross(B - A, C - A), axis=1)

    a3, a2 = area(P, F), area(Q, F)
    s = np.where(a3 > 1e-12, a2 / np.maximum(a3, 1e-12) - 1, 0.0)
    return {"area3d": round(float(a3.sum()), 3), "areaFlat": round(float(a2.sum()), 3),
            "mean": round(float(np.abs(s).mean()) * 100, 3), "max": round(float(np.abs(s).max()) * 100, 3)}


def closed_polygon(points):
    """A flat outline [[x, y], …] as a closed wire on the XY plane."""
    return Part.makePolygon([FreeCAD.Vector(x, y, 0) for x, y in points] + [FreeCAD.Vector(*points[0], 0)])


# Distinct colours for kept segments (RGB 0..1), in turn.
SEGMENT_COLOURS = [(0.90, 0.30, 0.25), (0.25, 0.60, 0.90), (0.35, 0.75, 0.35), (0.95, 0.70, 0.20), (0.65, 0.40, 0.85),
                   (0.20, 0.75, 0.75), (0.90, 0.45, 0.70), (0.60, 0.60, 0.30), (0.45, 0.45, 0.90), (0.85, 0.55, 0.35),
                   (0.40, 0.80, 0.60), (0.75, 0.75, 0.75)]

def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    EDIT = "meshEdit"

    def editing():
        """{original label: its edit copy's label} for meshes being edited."""
        return store.read(doc(), EDIT, {})

    def mesh_of(ref):
        ms = meshes(doc())
        ed = editing()
        if ref is not None and ref in ed:
            # Being edited: the tools work on its copy (meshobj_edit).
            cp = next((x for x in ms if x.Label == ed[ref]), None)
            if cp is not None:
                return cp
        if ref is None:
            ms = [x for x in ms if x.Label not in ed]  # an original being edited is not a choice

            if len(ms) == 1:
                return ms[0]
            raise (ToolError("not_found", "No mesh in the document: meshobj_from_shape makes one, import_file reads one.") if not ms else bad(f"mesh: say which — {', '.join(o.Label for o in ms)}."))
        o = next((x for x in ms if ref in (x.Label, x.Name)), None)
        if o is None:
            raise ToolError("not_found", f"mesh {ref!r}: the meshes are {', '.join(x.Label for x in ms) or 'none'}.")
        return o

    def keep(o, m, tool, a, extra=None, before=None):
        """The changed mesh: into the object, or a new one with copy: true."""
        if a.get("copy"):
            n = doc().addObject("Mesh::Feature", "Mesh")
            n.Label = s.unique(a.get("name") or f"{o.Label} ({tool.split('_', 1)[1]})")
            n.Mesh = m
            target = n
        else:
            o.Mesh = m
            target = o
        doc().recompute()
        s.snapshot(tool)
        out = {"mesh": target.Label, **reading(target.Mesh), **(extra or {}), "step": len(s.steps)}
        if before is not None:
            out["before"] = before
        return out

    def tinted(o, i):
        """A kept segment given a colour of its own in the window, as FreeCAD's
        Mesh_Segmentation colours each segment it finds; o unchanged where
        there is no window."""
        vo = getattr(o, "ViewObject", None) if getattr(FreeCAD, "GuiUp", False) else None
        if vo is not None:
            c = SEGMENT_COLOURS[(int(i) - 1) % len(SEGMENT_COLOURS)]
            try:
                vo.ShapeColor = c
            except Exception:
                pass
        return o

    def new_mesh(m, label):
        n = doc().addObject("Mesh::Feature", "Mesh")
        n.Label = s.unique(label)
        n.Mesh = m
        return n

    def write_pattern(items, path):
        """A flat pattern's outlines written to path (the session's folder
        when relative): .dxf through flat2d's writer, anything else as SVG.
        Answers (the path, the DXF writer's name or None)."""
        from .. import flat2d

        pth = paths.made(s, path if os.path.isabs(path) else os.path.join(s.out_dir, path))
        os.makedirs(os.path.dirname(pth), exist_ok=True)
        if pth.lower().endswith(".dxf"):
            return pth, flat2d.write_dxf(items, pth)[1]
        with open(pth, "w", encoding="utf-8") as f:
            f.write(flat2d.svg(items))
        return pth, None

    def bounds(items):
        from .. import flat2d

        return flat2d.bounds(items)

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "mesh_of": mesh_of, "keep": keep, "new_mesh": new_mesh, "tinted": tinted, "editing": editing,
               "edit_store": lambda ed: store.write(doc(), EDIT, ed), "meshes": lambda: meshes(doc()), "bodies": lambda: s.bodies(),
               "finish": lambda tool, read: picks.finish(s, tool, read), "snapshot": lambda tool: s.snapshot(tool), "steps_n": lambda: len(s.steps),
               "unique": lambda label: s.unique(label), "num": picks.num, "vec": vec, "xyz": geo.vec, "reading": reading, "evaluation": evaluation,
               "resolve": lambda ref: picks.resolve(s, ref), "out_file": lambda tool, want: paths.out_file(s, tool, want),
               "isfile": os.path.isfile, "filesize": os.path.getsize,
               # FreeCAD's own
               "V": V, "matrix": FreeCAD.Matrix, "rotation": FreeCAD.Rotation, "polygon": Part.makePolygon, "compound": Part.Compound,
               "make_compound": Part.makeCompound, "face": Part.Face, "mesh_shape": mesh_shape, "project_on": project_on,
               "mesh_box": Mesh.createBox, "mesh_sphere": Mesh.createSphere, "mesh_cylinder": Mesh.createCylinder, "mesh_cone": Mesh.createCone,
               "mesh_torus": Mesh.createTorus,
               # the family's
               "show": show, "outward": outward, "repair_step": repair_step, "edges_state": edges_state, "worse": worse,
               "plane_sides": plane_sides, "merge_cut": merge_cut, "cap": cap, "shift": shift, "mirror_matrix": mirror_matrix,
               "through_placement": through_placement, "arrays": arrays, "in_place": in_place, "own_boolean": own_boolean,
               "freecad_boolean": freecad_boolean, "solid_boolean": solid_boolean, "reach": reach, "loops": loops, "mean_normal": mean_normal,
               "curvature_stats": curvature_stats, "polylines": polylines, "file_ext": file_ext, "open_edges": open_edges,
               "edge_loops": edge_loops, "has_module": has_module, "surface_kind": surface_kind, "flat_pattern": flat_pattern,
               "outline_area": outline_area, "face_arrays": face_arrays, "flatten_apart": flatten_apart, "stretch": stretch,
               "closed_polygon": closed_polygon, "write_pattern": write_pattern, "bounds": bounds}
    return runners.tools(GROUP, s, helpers)

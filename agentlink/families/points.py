# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD's Points and Reverse Engineering workbenches: point clouds read
# (ASC/XYZ, PCD, PLY, E57, CSV) and written, sampled from a body or mesh,
# cropped and thinned, and shapes fitted through them — a plane, a sphere,
# a cylinder (fitting.py, least squares) or a free B-spline surface
# (Reverse Engineering's approximation) — made as bodies when asked.

import os

import FreeCAD
import Part
import Points  # noqa: F401 — the family stands on the Points module; left out without it

import numpy as np

from .. import fitting
from .. import paths
from .. import runners
from ..protocol import bad
from . import picks

GROUP = "points"
INFO = "Point clouds (Points, Reverse Engineering): read and write ASC/XYZ, PCD, PLY, E57, CSV; sample a body or mesh; crop and thin; fit a plane, sphere, cylinder or B-spline surface, and make it a body."

READS = ("asc", "xyz", "txt", "csv", "pcd", "ply", "e57")
WRITES = ("asc", "xyz", "pcd", "ply", "csv")


def array_of(o):
    """A Points object's points as an n × 3 array, where they stand in the document.
    The kernel already carries the object's Placement (Points::Feature::onChanged sets
    it as the kernel's transform, and the kernel's iterator applies it), so the points
    are read as they come: applying the Placement here as well moved a placed cloud twice."""
    pts = o.Points.Points
    return np.array([(p.x, p.y, p.z) for p in pts], float).reshape(-1, 3)


def reading(o, P=None):
    P = array_of(o) if P is None else P
    out = {"object": o.Label, "points": int(len(P))}
    if len(P):
        lo, hi = P.min(axis=0), P.max(axis=0)
        out["min"] = [round(float(x), 3) for x in lo]
        out["max"] = [round(float(x), 3) for x in hi]
        out["box"] = [round(float(x), 3) for x in hi - lo]
    return out


def read_text(path):
    """x y z per line (commas, spaces or tabs); a header line and extra columns skipped."""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.replace(",", " ").replace(";", " ").split()
            if len(parts) < 3:
                continue
            try:
                rows.append([float(x) for x in parts[:3]])
            except ValueError:
                continue
    return np.array(rows, float).reshape(-1, 3)


PLY_TYPES = {"char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1", "short": "i2", "int16": "i2", "ushort": "u2", "uint16": "u2",
             "int": "i4", "int32": "i4", "uint": "u4", "uint32": "u4", "float": "f4", "float32": "f4", "double": "f8", "float64": "f8"}


def read_ply(path):
    """A PLY's vertices (ascii or binary), x y z of whatever other properties it has."""
    with open(path, "rb") as f:
        data = f.read()
    end = data.find(b"end_header")
    if not data.startswith(b"ply") or end < 0:
        raise ValueError("not a PLY file")
    head = data[:end].decode("ascii", "replace").splitlines()
    body = data[data.index(b"\n", end) + 1:]
    fmt, n, props, cur = "ascii", 0, [], None
    for line in head:
        w = line.split()
        if not w:
            continue
        if w[0] == "format":
            fmt = w[1]
        elif w[0] == "element":
            cur = w[1]
            if cur == "vertex":
                n = int(w[2])
        elif w[0] == "property" and cur == "vertex":
            if w[1] == "list":
                raise ValueError("a vertex with list properties")
            props.append((w[2], PLY_TYPES[w[1]]))
    names = [p[0] for p in props]
    if not all(k in names for k in "xyz"):
        raise ValueError("vertices without x, y, z")
    if fmt == "ascii":
        rows = body.decode("ascii", "replace").split()
        A = np.array(rows[: n * len(props)], float).reshape(n, len(props))
        return A[:, [names.index(k) for k in "xyz"]]
    order = "<" if fmt == "binary_little_endian" else ">"
    dt = np.dtype([(k, order + v) for k, v in props])
    A = np.frombuffer(body[: n * dt.itemsize], dtype=dt, count=n)
    return np.column_stack([A["x"], A["y"], A["z"]]).astype(float)


def read_pcd(path):
    """A PCD's points (ascii or binary), x y z."""
    with open(path, "rb") as f:
        data = f.read()
    meta, off = {}, 0
    while off < len(data):
        nl = data.index(b"\n", off)
        line = data[off:nl].decode("ascii", "replace").strip()
        off = nl + 1
        if not line or line.startswith("#"):
            continue
        k, _, v = line.partition(" ")
        meta[k.upper()] = v.split()
        if k.upper() == "DATA":
            break
    fields, sizes, types = meta["FIELDS"], [int(x) for x in meta["SIZE"]], meta["TYPE"]
    counts = [int(x) for x in meta.get("COUNT", ["1"] * len(fields))]
    n = int(meta["POINTS"][0])
    if meta["DATA"][0] == "ascii":
        cols = sum(counts)
        A = np.array(data[off:].decode("ascii", "replace").split(), float)[: n * cols].reshape(-1, cols)
    elif meta["DATA"][0] == "binary":
        dt = np.dtype([(f"{fl}{i}" if c > 1 else fl, {"F": "f", "I": "i", "U": "u"}[ty] + str(sz)) for fl, sz, ty, c in zip(fields, sizes, types, counts) for i in range(c)])
        A = np.frombuffer(data[off: off + n * dt.itemsize], dtype=dt, count=n)
        return np.column_stack([A["x"], A["y"], A["z"]]).astype(float)
    else:
        raise ValueError("compressed PCD: save it as ascii or binary")
    idx, col = {}, 0
    for fl, c in zip(fields, counts):
        idx[fl] = col
        col += c
    return A[:, [idx["x"], idx["y"], idx["z"]]]


def read_file(path):
    """A cloud file's points by its ending, as points_import and points_export's read-back take them."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "ply":
        return read_ply(path)
    if ext == "pcd":
        return read_pcd(path)
    return read_text(path)


def write_points(path, P):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext in ("asc", "xyz"):
        np.savetxt(path, P, fmt="%.6f")
    elif ext == "csv":
        np.savetxt(path, P, fmt="%.6f", delimiter=",", header="x,y,z", comments="")
    elif ext == "pcd":
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# .PCD v0.7\nVERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\nWIDTH {len(P)}\nHEIGHT 1\n"
                    f"VIEWPOINT 0 0 0 1 0 0 0\nPOINTS {len(P)}\nDATA ascii\n")
            np.savetxt(f, P, fmt="%.6f")
    elif ext == "ply":
        with open(path, "wb") as f:
            f.write(f"ply\nformat binary_little_endian 1.0\nelement vertex {len(P)}\nproperty float x\nproperty float y\nproperty float z\nend_header\n".encode("ascii"))
            f.write(P.astype("<f4").tobytes())
    else:
        raise bad(f"path: .{ext or '(no ending)'} is not a format written here; end it .ply, .pcd, .asc, .xyz or .csv.")


def sample_triangles(V, T, n, seed=1):
    """n points spread evenly by area over triangles (the same points each time)."""
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(B - A, C - A), axis=1)
    if area.sum() <= 0:
        raise bad("The surface has no area to sample.")
    rng = np.random.default_rng(seed)
    k = rng.choice(len(T), size=n, p=area / area.sum())
    r1, r2 = rng.random(n), rng.random(n)
    s = np.sqrt(r1)
    return (1 - s)[:, None] * A[k] + (s * (1 - r2))[:, None] * B[k] + (s * r2)[:, None] * C[k]


def vec(x):
    return FreeCAD.Vector(*[float(c) for c in x])


def xyz(v, name):
    """[x, y, z] as an array; a refusal naming the input otherwise."""
    q = picks.vec3(v, name)
    return np.array([q.x, q.y, q.z], float)


def spacing(P):
    """The typical distance between neighbouring points (a surface's: a
    sample's nearest gaps scaled back to the whole count)."""
    k = min(len(P), 2000)
    Q = P[np.random.default_rng(0).choice(len(P), k, replace=False)]
    d = np.sqrt(((Q[:, None, :] - Q[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    nn = d.min(axis=1) * np.sqrt(k / len(P)) if len(P) > k else d.min(axis=1)
    return float(np.median(nn))


def ring_order(P, gap_deg=45.0):
    """The points in order round their centre when they make a loop (no
    gap wider than gap_deg seen from the centre, all well away from it):
    else None."""
    if len(P) < 8:
        return None
    c = P.mean(axis=0)
    _, _, vt = np.linalg.svd(P - c, full_matrices=False)
    u, v = (P - c) @ vt[0], (P - c) @ vt[1]
    r = np.hypot(u, v)
    if r.min() < 0.2 * np.median(r):
        return None
    ang = np.arctan2(v, u)
    order = np.argsort(ang)
    s_ = np.sort(ang)
    gaps = np.diff(np.concatenate([s_, [s_[0] + 2 * np.pi]]))
    return order if np.degrees(gaps.max()) < gap_deg else None


def chain_order(P):
    """An order along a line of points: start at one end (farthest from the
    centre along the main axis) and walk to the nearest unvisited point."""
    n = len(P)
    if n < 3:
        return np.arange(n)
    c = P.mean(axis=0)
    _, _, vt = np.linalg.svd(P - c, full_matrices=False)
    t = (P - c) @ vt[0]
    if n > 3000:
        return np.argsort(t)
    left = np.ones(n, dtype=bool)
    i = int(np.argmin(t))
    out = [i]
    left[i] = False
    for _ in range(n - 1):
        d = ((P - P[i]) ** 2).sum(axis=1)
        d[~left] = np.inf
        i = int(np.argmin(d))
        out.append(i)
        left[i] = False
    return np.array(out)


def grid_mesh(P, cell):
    """A height field's triangles: the points binned on the plane of their
    two widest axes, one vertex (the mean) per occupied cell, two triangles
    per square of four occupied cells."""
    c = P.mean(axis=0)
    _, _, vt = np.linalg.svd(P - c, full_matrices=False)
    u, v = (P - c) @ vt[0], (P - c) @ vt[1]
    if not cell:
        # about six points to a cell, so nearly every cell has one
        cell = 2.5 * float(np.sqrt(max(np.ptp(u) * np.ptp(v), 1e-12) / len(P)))
    iu = np.floor((u - u.min()) / cell).astype(int)
    iv = np.floor((v - v.min()) / cell).astype(int)
    key = iu * (iv.max() + 1) + iv
    order = np.argsort(key)
    uniq, start = np.unique(key[order], return_index=True)
    ends = list(start[1:]) + [len(order)]
    V = np.array([P[order[s:e]].mean(axis=0) for s, e in zip(start, ends)])
    index = {int(k): j for j, k in enumerate(uniq)}
    W = iv.max() + 1
    T = []
    for k, j in index.items():
        a, b = divmod(k, W)
        r = index.get((a + 1) * W + b)
        up = index.get(a * W + b + 1) if b + 1 < W else None  # never wrap to the next row
        d = index.get((a + 1) * W + b + 1) if b + 1 < W else None
        if r is not None and d is not None and up is not None:
            T += [(j, r, d), (j, d, up)]
        elif r is not None and d is not None:
            T.append((j, r, d))
        elif d is not None and up is not None:
            T.append((j, d, up))
        elif r is not None and up is not None:
            T.append((j, r, up))
    return V, T, cell


# The tools themselves are data (agentlink/data/tools.json; run by
# agentlink/runners.py's steps runner). What follows is what their entries
# call by name (docs/data-tools.md): the numpy over the points, and the
# FreeCAD calls a cloud, a fit or a mesh takes.

def file_ext(path):
    """A path's extension, lower case, without its dot ("" for none)."""
    return os.path.splitext(path)[1].lower().lstrip(".")


def stem(path):
    """A file's name without its folder and ending."""
    return os.path.splitext(os.path.basename(path))[0]


def finite(P):
    """The points without those that hold a NaN or an infinity."""
    if np.isfinite(P).all():
        return P
    return P[np.isfinite(P).all(axis=1)]


def kernel(P):
    """A Points kernel (Points.Points) holding the array's points."""
    pk = Points.Points()
    pk.addPoints([tuple(p) for p in P.tolist()])
    return pk


def sampled(pts, tri, n, seed, noise):
    """n points spread evenly by area over a tessellation's triangles (the
    same each time for a seed); noise mm scatters them (one standard
    deviation), from the next seed on."""
    V = np.array([(p.x, p.y, p.z) for p in pts], float)
    T = np.array(tri, int).reshape(-1, 3)
    P = sample_triangles(V, T, n, seed)
    if noise > 0:
        P = P + np.random.default_rng(seed + 1).normal(0, noise, P.shape)
    return P


def everything(P):
    """A mask that keeps every point."""
    return np.ones(len(P), bool)


def both(keep, mask):
    """The points two masks both keep."""
    return keep & mask


def inverse(keep):
    """The points a mask leaves out."""
    return ~keep


def in_box(P, b):
    """The points inside the box between two corners (in any order), its sides included."""
    lo, hi = np.minimum(b[0], b[1]), np.maximum(b[0], b[1])
    return np.all((P >= lo) & (P <= hi), axis=1)


def within(P, c, r):
    """The points no farther than r from c."""
    return np.linalg.norm(P - c, axis=1) <= r


def in_front(P, at, n):
    """The points on the side of the plane through at that its normal n points to (the plane included)."""
    return (P - at) @ n >= 0


def without_specks(Q, radius, least):
    """(the points with least neighbours or more within radius, how many
    were dropped, None); (Q, 0, why) when the count cannot be made."""
    try:
        k2 = fitting.radius_outliers(Q, radius, least)
    except fitting.FitError as e:
        return Q, 0, str(e)
    return Q[k2], int((~k2).sum()), None


def thinned(Q, cell):
    """One point kept per cell mm (the first met in each), in their order."""
    _, first = np.unique(np.floor(Q / cell).astype(np.int64), axis=0, return_index=True)
    return Q[np.sort(first)]


def fitted(kind, P, hint):
    """The least-squares plane, sphere or cylinder (hint: its axis) through
    the points: (fit, None), or (None, why) when there is none. A surface
    or a curve is not fitted here: (None, None)."""
    try:
        if kind == "plane":
            return fitting.plane(P), None
        if kind == "sphere":
            return fitting.sphere(P), None
        if kind == "cylinder":
            return fitting.cylinder(P, hint), None
    except fitting.FitError as e:
        return None, str(e)
    return None, None


def reverse_engineering():
    """FreeCAD's ReverseEngineering module, or None where this build has none."""
    try:
        import ReverseEngineering as RE
    except ImportError:
        return None
    return RE


def distances(shape, P):
    """How far up to 400 of the points (the same each time) lie from a fitted shape, mm."""
    return np.array([shape.distToShape(Part.Vertex(vec(p)))[0] for p in P[np.random.default_rng(0).choice(len(P), min(len(P), 400), replace=False)]])


def rms(d):
    """The root mean square of distances, to 4 places."""
    return round(float(np.sqrt(np.mean(d * d))), 4)


def along(P, order):
    """The points in an order along their line, thinned to about 400."""
    Q = P[order]
    return Q[::max(1, len(Q) // 400)]


def curve_through(Q, loop, degree, tol):
    """A B-spline along ordered points. A loop: through the mean of each of
    up to 48 slices round it (noise averaged out), periodic; an open one
    approximated to tol mm up to degree."""
    c = Part.BSplineCurve()
    if loop:
        k = max(8, min(48, len(Q) // 3))
        bins = np.array_split(Q, k)
        M = [b.mean(axis=0) for b in bins if len(b)]
        c.interpolate(Points=[vec(q) for q in M], PeriodicFlag=True)
    else:
        c.approximate(Points=[vec(q) for q in Q], DegMax=int(degree), Tolerance=tol)
    return c


def plane_patch(P, f):
    """A fitted plane as a face: the rectangle on it that spans the points along the fit's own two axes."""
    u, v = f["axes"]
    Q = P - f["centre"]
    uu, vv = Q @ u, Q @ v
    c = f["centre"] + u * (uu.max() + uu.min()) / 2 + v * (vv.max() + vv.min()) / 2
    w, h = uu.max() - uu.min(), vv.max() - vv.min()
    return Part.makePlane(w, h, vec(c - u * w / 2 - v * h / 2), vec(f["normal"]), vec(u))


def triangles_mesh(V, T):
    """A Mesh of triangles T over points V."""
    import Mesh

    return Mesh.Mesh([[tuple(V[i]) for i in tri] for tri in T])


def hull(P):
    """The convex hull's points and triangles (agentlink/hull3d.py)."""
    from .. import hull3d

    return hull3d.hull(P)


def poisson(P, depth):
    """Reverse Engineering's Poisson reconstruction of a cloud (only in a
    FreeCAD built with PCL): with the octree depth where this build takes it."""
    import ReverseEngineering as RE

    pk = kernel(P)
    try:
        return RE.poissonReconstruction(Points=pk, OctreeDepth=int(depth))
    except TypeError:
        return RE.poissonReconstruction(pk)


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def clouds():
        return [o for o in doc().Objects if o.isDerivedFrom("Points::Feature")]

    def cloud(ref):
        if not ref:
            cs = clouds()
            if len(cs) == 1:
                return cs[0]
            raise bad("points: which point cloud — " + (", ".join(o.Label for o in cs) or "there are none (points_import or points_sample makes one)") + ".")
        o = picks.find(doc(), ref, "points")
        if not o.isDerivedFrom("Points::Feature"):
            cs = clouds()
            raise bad(f"points: {o.Label} is not a point cloud" + (f" — the clouds are {', '.join(c.Label for c in cs)}." if cs else "; points_sample { object } makes one from a body or mesh."))
        return o

    def make(P, label):
        pk = kernel(P)
        o = doc().addObject("Points::Feature", "Points")
        o.Label = s.unique(label)
        o.Points = pk
        doc().recompute()
        return o

    def read_e57(p):
        """An E57 file's points: FreeCAD's own reader makes the cloud an
        object (or several); their points are taken and the objects removed."""
        before = {o.Name for o in doc().Objects}
        Points.insert(p, doc().Name)
        new = [o for o in doc().Objects if o.Name not in before]
        P = np.concatenate([array_of(o) for o in new if o.isDerivedFrom("Points::Feature")] or [np.zeros((0, 3))])
        for o in new:
            doc().removeObject(o.Name)
        return P

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "cloud": cloud, "make": make, "find": lambda ref, what: picks.find(doc(), ref, what),
               "finish": lambda tool, read: picks.finish(s, tool, read), "finish_as_is": lambda tool, read: picks.finish(s, tool, read, recompute=False),
               "snapshot": lambda tool: s.snapshot(tool), "steps_n": lambda: len(s.steps), "unique": lambda label: s.unique(label),
               "local": lambda p: paths.local(s, p, expand=False), "num": picks.num, "xyz": xyz, "vec": vec, "reading": reading, "array_of": array_of,
               "isfile": os.path.isfile, "basename": os.path.basename, "dirname": os.path.dirname, "filesize": os.path.getsize,
               "makedirs": lambda d: os.makedirs(d, exist_ok=True),
               # FreeCAD's own
               "placement": FreeCAD.Placement, "sphere": Part.makeSphere, "cylinder": Part.makeCylinder, "is_shape": lambda x: isinstance(x, Part.Shape),
               # the family's
               "file_ext": file_ext, "stem": stem, "read_file": read_file, "read_e57": read_e57, "write_points": write_points, "finite": finite,
               "kernel": kernel, "sampled": sampled, "spacing": spacing, "everything": everything, "both": both, "inverse": inverse, "in_box": in_box,
               "within": within, "in_front": in_front, "unit": fitting.unit, "without_specks": without_specks, "thinned": thinned, "fitted": fitted,
               "norm": np.linalg.norm, "reverse_engineering": reverse_engineering, "distances": distances, "rms": rms, "ring_order": ring_order, "chain_order": chain_order,
               "along": along, "curve_through": curve_through, "plane_patch": plane_patch, "stacked": lambda srcs: np.vstack([array_of(c) for c in srcs]),
               "grid_mesh": grid_mesh, "triangles_mesh": triangles_mesh, "hull": hull, "poisson": poisson}
    return runners.tools(GROUP, s, helpers)

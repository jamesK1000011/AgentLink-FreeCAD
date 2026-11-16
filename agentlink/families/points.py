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
from ..protocol import Tool, ToolError, bad
from ..tools import obj
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
        pk = Points.Points()
        pk.addPoints([tuple(p) for p in P.tolist()])
        o = doc().addObject("Points::Feature", "Points")
        o.Label = s.unique(label)
        o.Points = pk
        doc().recompute()
        return o

    def where(p):
        if not p:
            raise bad("path: a file (in the session's output folder when relative).")
        return paths.local(s, p, expand=False)

    def points_import(a):
        p = where(a.get("path"))
        if not os.path.isfile(p):
            raise ToolError("not_found", f"path {a.get('path')!r}: no such file (a relative path is looked for in the session's output folder; give the full path of a file elsewhere).")
        ext = os.path.splitext(p)[1].lower().lstrip(".")
        if ext not in READS:
            raise bad(f"path: .{ext or '(no ending)'} is not read here — one of {', '.join(READS)}. A mesh (.stl, .obj) is opened with import_file and sampled with points_sample.")
        k = int(a.get("every", 1))
        if k < 1:
            raise bad("every: keep every n-th point, 1 or more.")
        scale = picks.number(a, "scale", 1.0, gt=0, msg="scale: what one file unit is in mm, above 0 (1000 for metres, 25.4 for inches).")
        try:
            if ext != "e57":
                P = read_file(p)
            else:
                # E57: FreeCAD's own reader makes the cloud an object; its points are taken.
                before = {o.Name for o in doc().Objects}
                Points.insert(p, doc().Name)
                new = [o for o in doc().Objects if o.Name not in before]
                P = np.concatenate([array_of(o) for o in new if o.isDerivedFrom("Points::Feature")] or [np.zeros((0, 3))])
                for o in new:
                    doc().removeObject(o.Name)
        except Exception as e:
            raise ToolError("failed", f"{os.path.basename(p)} could not be read: {e}" + (" (E57 needs a FreeCAD built with the E57 library; save the scan as .ply or .pcd instead)." if ext == "e57" else ". A text file needs x y z on each line; a .ply its vertices' x, y, z; a compressed .pcd saved as ascii or binary.")) from None
        if not len(P):
            raise ToolError("failed", f"{os.path.basename(p)}: no points read (no line had three numbers).")
        if not np.isfinite(P).all():
            keep = np.isfinite(P).all(axis=1)
            P = P[keep]
            if not len(P):
                raise ToolError("failed", f"{os.path.basename(p)}: every point is NaN or infinite.")
        total = len(P)
        P = P[::k] * scale
        o = make(P, a.get("name") or os.path.splitext(os.path.basename(p))[0])
        return picks.finish(s, "points_import", lambda: {**reading(o, P), "read": total}, recompute=False)

    def points_sample(a):
        o = picks.find(doc(), a.get("object"), "object")
        n = int(a.get("count", 5000))
        if not 3 <= n <= 2_000_000:
            raise bad("count: 3 … 2000000 points.")
        if float(a.get("noise", 0)) < 0:
            raise bad("noise: mm of scatter (one standard deviation), 0 or more.")
        if o.isDerivedFrom("Mesh::Feature"):
            pts, tri = o.Mesh.Topology
        else:
            sh = getattr(o, "Shape", None)
            if not isinstance(sh, Part.Shape) or sh.isNull() or not sh.Faces:
                raise bad(f"object: {o.Label} has no faces to sample; give a body, a surface or a mesh.")
            tol = picks.number(a, "tolerance", 0.01, gt=0, msg="tolerance: mm the sampled facets may stray from curved faces, above 0 (0.01).")
            pts, tri = sh.tessellate(tol)
        if not len(tri):
            raise bad(f"object: {o.Label} gave no triangles to sample.")
        V = np.array([(p.x, p.y, p.z) for p in pts], float)
        T = np.array(tri, int).reshape(-1, 3)
        P = sample_triangles(V, T, n, int(a.get("seed", 1)))
        noise = float(a.get("noise", 0))
        if noise > 0:
            P = P + np.random.default_rng(int(a.get("seed", 1)) + 1).normal(0, noise, P.shape)
        c = make(P, a.get("name") or f"{o.Label} points")
        return picks.finish(s, "points_sample", lambda: {**reading(c, P), "from": o.Label, **({"noise": noise} if noise else {})}, recompute=False)

    def points_info(a):
        o = cloud(a.get("points"))
        P = array_of(o)
        out = reading(o, P)
        if len(P) >= 2:
            out["spacing"] = round(spacing(P), 4)
            out["centre"] = [round(float(x), 3) for x in P.mean(axis=0)]
        return out

    def points_crop(a):
        o = cloud(a.get("points"))
        P = array_of(o)
        keep = np.ones(len(P), bool)
        if a.get("box") is not None:
            b = a["box"]
            if not (isinstance(b, list) and len(b) == 2 and all(isinstance(x, list) and len(x) == 3 for x in b)):
                raise bad("box: [[xmin, ymin, zmin], [xmax, ymax, zmax]] in mm, document coordinates (points_info gives the cloud's min and max).")
            lo, hi = np.minimum(b[0], b[1]), np.maximum(b[0], b[1])
            keep &= np.all((P >= lo) & (P <= hi), axis=1)
        if a.get("near") is not None:
            if a.get("radius") is None:
                raise bad("radius: mm round near to keep (near and radius go together).")
            r = picks.number(a, "radius", gt=0, msg="radius: mm, above 0.")
            keep &= np.linalg.norm(P - xyz(a["near"], "near"), axis=1) <= r
        if a.get("plane") is not None:
            pl = a["plane"]
            if not isinstance(pl, dict):
                raise bad("plane: { at [x, y, z], normal [x, y, z] }: the side the normal points to is kept.")
            try:
                n = fitting.unit(pl.get("normal", [0, 0, 1]))
            except (fitting.FitError, TypeError, ValueError):
                raise bad("plane.normal: a direction [x, y, z], not zero.") from None
            keep &= (P - xyz(pl.get("at", [0, 0, 0]), "plane.at")) @ n >= 0
        if not any(a.get(k) is not None for k in ("box", "near", "plane")) and not a.get("thin") and not a.get("specks"):
            raise bad("Nothing to do: give box, near + radius, plane, thin or specks.")
        if a.get("outside") and not any(a.get(k) is not None for k in ("box", "near", "plane")):
            raise bad("outside: true needs a box, near + radius or plane to be outside of.")
        if a.get("outside"):
            keep = ~keep
        voxel = a.get("thin")
        Q = P[keep]
        dropped = 0
        if a.get("specks"):
            sp = a["specks"]
            rr, least = float(sp.get("radius", 1.0)), int(sp.get("least", 4))
            try:
                k2 = fitting.radius_outliers(Q, rr, least)
            except fitting.FitError as e:
                raise bad(f"specks: {e}") from None
            dropped = int((~k2).sum())
            Q = Q[k2]
        if voxel:
            vx = picks.num(voxel, "thin")
            if vx <= 0:
                raise bad("thin: the cell size in mm, above 0 — one point kept per cell.")
            _, first = np.unique(np.floor(Q / vx).astype(np.int64), axis=0, return_index=True)
            Q = Q[np.sort(first)]
        if not len(Q):
            lo, hi = P.min(axis=0), P.max(axis=0)
            raise ToolError("failed", f"Nothing left after the crop: no point was kept, and the cloud is unchanged. It spans {[round(float(x), 2) for x in lo]} … {[round(float(x), 2) for x in hi]}; check the box or plane against that.")
        if a.get("replace", True):
            pk = Points.Points()
            pk.addPoints([tuple(p) for p in Q.tolist()])
            o.Placement = FreeCAD.Placement()
            o.Points = pk
            doc().recompute()
            c = o
        else:
            c = make(Q, a.get("name") or f"{o.Label} cropped")
        return picks.finish(s, "points_crop", lambda: {**reading(c, Q), "from": int(len(P)), "kept": int(len(Q)), **({"specksDropped": dropped} if a.get("specks") else {})}, recompute=False)

    def points_fit(a):
        o = cloud(a.get("points"))
        P = array_of(o)
        kind = a.get("shape", "plane")
        if kind not in ("plane", "sphere", "cylinder", "surface", "curve"):
            raise bad("shape: plane | sphere | cylinder | surface (a free B-spline) | curve (a B-spline through a line of points).")
        if a.get("tolerance") is not None and float(a["tolerance"]) <= 0:
            raise bad("tolerance: mm, above 0.")
        hint = None
        if kind == "cylinder" and a.get("axis") is not None:
            hint = xyz(a["axis"], "axis")
            if not np.linalg.norm(hint):
                raise bad("axis: a direction [x, y, z], not zero (leave it out to let the fit find it).")
        try:
            if kind == "plane":
                f = fitting.plane(P)
            elif kind == "sphere":
                f = fitting.sphere(P)
            elif kind == "cylinder":
                f = fitting.cylinder(P, hint)
            elif kind in ("surface", "curve"):
                f = None
            else:
                raise bad("shape: plane | sphere | cylinder | surface (a free B-spline) | curve (a B-spline through a line of points).")
        except fitting.FitError as e:
            raise ToolError("failed", f"{e} points_info counts the cloud; points_crop narrows it to the one feature.") from None
        r3 = lambda v: [round(float(x), 4) for x in v]  # noqa: E731
        out = {"points": o.Label, "shape": kind}
        body = None
        if kind == "surface":
            try:
                import ReverseEngineering as RE
            except ImportError:
                raise ToolError("unavailable", "Reverse Engineering is not in this FreeCAD build: fit a plane, sphere or cylinder, or points_mesh for a mesh.") from None
            ud, vd = int(a.get("degree", 3)), int(a.get("degree", 3))
            nu = nv = int(a.get("poles", 6))
            if ud < 1 or nu <= ud:
                raise bad("degree 1 or more, and poles more than the degree (6 poles for degree 3).")
            if len(P) < nu * nv:
                raise bad(f"The cloud has {len(P)} points; a surface of {nu} × {nv} poles needs {nu * nv} or more. Fewer poles, or more points.")
            if len(P) > 200000:
                raise bad(f"{len(P)} points is more than a surface fit takes in one call (200000): points_crop {{ thin }} first; the fit gains nothing from more.")
            pk = Points.Points()
            pk.addPoints([tuple(p) for p in P.tolist()])
            try:
                srf = RE.approxSurface(Points=pk, UDegree=ud, VDegree=vd, NbUPoles=nu, NbVPoles=nv, Smooth=bool(a.get("smooth", True)),
                                       Weight=float(a.get("weight", 0.1)), Iterations=int(a.get("iterations", 5)))
            except Exception as e:
                raise ToolError("failed", f"The surface could not be fitted: {e}. It fits one sheet seen from one side (like a height field over the points' own plane): crop to such a patch, or use fewer poles.") from None
            face = srf.toShape()
            d = np.array([face.distToShape(Part.Vertex(vec(p)))[0] for p in P[np.random.default_rng(0).choice(len(P), min(len(P), 400), replace=False)]])
            out.update({"degree": ud, "poles": [nu, nv], "rms": round(float(np.sqrt(np.mean(d * d))), 4), "max": round(float(d.max()), 4),
                        "sampled": int(len(d)), "area": round(face.Area, 3)})
            body = face
        elif kind == "curve":
            tol = float(a.get("tolerance", 0.1))
            ring = ring_order(P)
            loop = a.get("closed", ring is not None)
            if loop and ring is None:
                raise bad("closed: these points do not go round a centre (a gap wider than 45° seen from it, or points near the middle); leave closed out for an open curve.")
            Q = P[ring] if loop else P[chain_order(P)]
            step = max(1, len(Q) // 400)
            Q = Q[::step]
            if len(Q) < 4:
                raise bad(f"curve: four or more points along a line, not {len(Q)}.")
            c = Part.BSplineCurve()
            try:
                if loop:
                    # the mean of each of up to 48 slices round the loop: noise averaged out
                    k = max(8, min(48, len(Q) // 3))
                    bins = np.array_split(Q, k)
                    M = [b.mean(axis=0) for b in bins if len(b)]
                    c.interpolate(Points=[vec(q) for q in M], PeriodicFlag=True)
                else:
                    c.approximate(Points=[vec(q) for q in Q], DegMax=int(a.get("degree", 3)), Tolerance=tol)
            except Exception as e:
                raise ToolError("failed", f"No curve through these points: {e}. A larger tolerance, or crop to the one line of points.") from None
            edge = c.toShape()
            d = np.array([edge.distToShape(Part.Vertex(vec(p)))[0] for p in P[np.random.default_rng(0).choice(len(P), min(len(P), 400), replace=False)]])
            out.update({"length": round(edge.Length, 3), "poles": c.NbPoles, "degree": c.Degree, "closed": bool(loop),
                        "rms": round(float(np.sqrt(np.mean(d * d))), 4), "max": round(float(d.max()), 4)})
            body = edge
            a = dict(a, make=True)
        elif kind == "plane":
            out.update({"centre": r3(f["centre"]), "normal": r3(f["normal"])})
            if a.get("make"):
                u, v = f["axes"]
                Q = P - f["centre"]
                uu, vv = Q @ u, Q @ v
                c = f["centre"] + u * (uu.max() + uu.min()) / 2 + v * (vv.max() + vv.min()) / 2
                w, h = uu.max() - uu.min(), vv.max() - vv.min()
                body = Part.makePlane(w, h, vec(c - u * w / 2 - v * h / 2), vec(f["normal"]), vec(u))
        elif kind == "sphere":
            out.update({"centre": r3(f["centre"]), "radius": round(f["radius"], 4), "diameter": round(2 * f["radius"], 4)})
            if a.get("make"):
                body = Part.makeSphere(f["radius"], vec(f["centre"]))
        else:
            out.update({"base": r3(f["base"]), "axis": r3(f["axis"]), "radius": round(f["radius"], 4), "diameter": round(2 * f["radius"], 4),
                        "length": round(f["length"], 4)})
            if a.get("make"):
                body = Part.makeCylinder(f["radius"], max(f["length"], 1e-3), vec(f["base"]), vec(f["axis"]))
        if f is not None:
            out.update({"rms": round(f["rms"], 4), "max": round(f["max"], 4)})
        tol = a.get("tolerance")
        if tol is not None:
            out["verdict"] = "fits" if out["max"] <= float(tol) else "does not fit"
            out["tolerance"] = float(tol)
        if body is not None and (a.get("make") or kind in ("surface", "curve")):
            b = doc().addObject("Part::Feature", "Fit")
            b.Label = s.unique(a.get("name") or f"{o.Label} {kind}")
            b.Shape = body
            out["body"] = b.Label
            picks.finish(s, "points_fit", out)
        return out

    def points_export(a):
        o = cloud(a.get("points"))
        P = array_of(o)
        p = where(a.get("path") or (o.Label.replace(" ", "_") + ".ply"))
        ext = os.path.splitext(p)[1].lower().lstrip(".")
        if ext not in WRITES:
            raise bad(f"path: .{ext or '(no ending)'} is not a format written here; end it .ply, .pcd, .asc, .xyz or .csv.")
        if not len(P):
            raise ToolError("invalid_state", f"{o.Label} has no points to write.")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        write_points(p, P)
        out = {"points": o.Label, "path": p, "bytes": os.path.getsize(p), "count": int(len(P))}
        try:
            back = read_file(p)
            out["readBack"] = int(len(back))
            if len(back) == len(P):
                out["maxError"] = round(float(np.abs(back - P).max()), 6)
            else:
                out["warning"] = f"The file reads back as {len(back)} points, not {len(P)}."
        except Exception as e:
            out["warning"] = f"The file could not be read back: {e}"
        return out

    def points_merge(a):
        refs = a.get("points")
        if not isinstance(refs, list) or len(refs) < 2:
            raise bad("points: two or more clouds to join, a list of labels.")
        srcs = [cloud(r) for r in refs]
        if len({c.Name for c in srcs}) < len(srcs):
            raise bad("points: each cloud once.")
        P = np.vstack([array_of(c) for c in srcs])
        o = make(P, a.get("name") or "Merged points")
        if a.get("remove"):
            for c in srcs:
                doc().removeObject(c.Name)
        return picks.finish(s, "points_merge", lambda: {"points": o.Label, "count": int(len(P)), **{k: v for k, v in reading(o, P).items() if k in ("min", "max", "box")}, "from": list(refs), "removed": bool(a.get("remove"))}, recompute=False)

    def points_mesh(a):
        o = cloud(a.get("points"))
        P = array_of(o)
        method = a.get("method", "height")
        if method not in ("height", "hull", "poisson"):
            raise bad("method: height (one side, gridded) | hull (convex) | poisson (needs FreeCAD built with PCL).")
        if len(P) < 4:
            raise bad(f"{o.Label} has {len(P)} points: a mesh needs four or more.")
        import Mesh
        if method == "height":
            if a.get("cell") is not None and float(a["cell"]) <= 0:
                raise bad("cell: mm, above 0 (left out: about six points to a cell).")
            V, T, cell = grid_mesh(P, float(a["cell"]) if a.get("cell") else None)
            if not T:
                raise ToolError("failed", f"No triangles at a {cell:g} mm cell: a larger cell (points_info gives the spacing; two or three times it), or the points are not a surface seen from one side.")
            if len(T) > 2_000_000:
                raise bad(f"A {cell:g} mm cell makes {len(T)} triangles: a larger cell (2000000 at most).")
            m = Mesh.Mesh([[tuple(V[i]) for i in tri] for tri in T])
            note = f"A height field on the points' own plane, one vertex per {cell:g} mm cell: for a scan of one side (terrain, a panel, a face)."
        elif method == "hull":
            from .. import hull3d
            Vh, Th = hull3d.hull(P)
            m = Mesh.Mesh([[tuple(Vh[i]) for i in tri] for tri in Th])
            note = "The convex hull: the shrink-wrap round every point."
        elif method == "poisson":
            try:
                import ReverseEngineering as RE
                pk = Points.Points()
                pk.addPoints([tuple(p) for p in P.tolist()])
                try:
                    m = RE.poissonReconstruction(Points=pk, OctreeDepth=int(a.get("depth", 8)))
                except TypeError:
                    m = RE.poissonReconstruction(pk)
            except Exception as e:
                raise ToolError("unavailable", f"Poisson reconstruction is not in this FreeCAD build ({e}): it needs a FreeCAD compiled with the Point Cloud Library. method height or hull instead.") from None
            note = "Poisson reconstruction: a closed surface through the cloud."
        else:
            raise bad("method: height (one side, gridded) | hull (convex) | poisson (needs FreeCAD built with PCL).")
        mo = doc().addObject("Mesh::Feature", "Mesh")
        mo.Mesh = m
        mo.Label = s.unique(a.get("name") or f"{o.Label} mesh")
        doc().recompute()
        s.snapshot("points_mesh")
        return {"mesh": mo.Label, "method": method, "facets": int(m.CountFacets), "points": int(m.CountPoints),
                "area": round(m.Area, 3), "closed": bool(m.isSolid()), "note": note, "step": len(s.steps)}

    pts = {"type": "string", "description": "The point cloud's label (the only one when left out)."}
    return [
        Tool("points_import", "Read a point cloud file: path .asc / .xyz / .txt / .csv (x y z a line), .pcd, .ply, .e57 (where FreeCAD has the E57 library). every: keep every n-th point; scale: mm per file unit (1000 for metres). Positions only. The whole file is read into memory: thin a huge one with every. Answers object, points (kept), read, min, max, box.",
             obj({"path": {"type": "string"}, "every": {"type": "integer"}, "scale": {"type": "number"}, "name": {"type": "string"}}, ["path"]), points_import, changes=True),
        Tool("points_sample", "A point cloud spread evenly over a body's, surface's or mesh's faces (object): count (5000; up to 2000000), noise mm (to try a fit as a scan would see it), seed, tolerance mm (faceting of curved faces, 0.01). Answers object, points, min, max, box.",
             obj({"object": {"type": "string"}, "count": {"type": "integer"}, "noise": {"type": "number"}, "seed": {"type": "integer"}, "tolerance": {"type": "number"}, "name": {"type": "string"}}, ["object"]), points_sample, changes=True),
        Tool("points_info", "A point cloud's points (count), min, max, box (mm, where it stands in the document), centre and spacing (typical gap between neighbours). Changes nothing.", obj({"points": pts}), points_info),
        Tool("points_crop", "Keep part of a cloud, filters combined: box [[min], [max]], near [x, y, z] with radius, plane { at, normal } (the side the normal points to); outside: true keeps the rest. specks { radius, least } drops points with fewer than least neighbours; thin mm keeps one point per cell. The cloud itself is cut down unless replace: false. Answers from, kept, min, max, box; refused, nothing changed, when no point is left.",
             obj({"points": pts, "box": {"type": "array", "items": {}}, "near": {"type": "array", "items": {}}, "radius": {"type": "number"}, "plane": {"type": "object"}, "outside": {"type": "boolean"},
                  "thin": {"type": "number"}, "specks": {"type": "object"}, "replace": {"type": "boolean"}, "name": {"type": "string"}}), points_crop, changes=True),
        Tool("points_fit", "Fit a shape through all of a cloud's points (crop to the one feature first): shape plane (centre, normal) | sphere (centre, diameter) | cylinder (base, axis, diameter, length; axis is a hint) | surface (a B-spline sheet over the points' own plane, one side only: degree 3, poles 6, smooth; 200000 points at most) | curve (a B-spline along a line of points; a loop closes itself: degree, tolerance). Answers rms and max (the points' distance from it, mm; a large max means the crop holds more than the feature); tolerance adds verdict fits | does not fit. make: true keeps the shape as an object (a surface or curve always is).",
             obj({"points": pts, "shape": {"type": "string", "enum": ["plane", "sphere", "cylinder", "surface", "curve"]}, "axis": {"type": "array", "items": {}}, "tolerance": {"type": "number"},
                  "make": {"type": "boolean"}, "degree": {"type": "integer"}, "poles": {"type": "integer"}, "smooth": {"type": "boolean"}, "weight": {"type": "number"},
                  "iterations": {"type": "integer"}, "name": {"type": "string"}}), points_fit, changes=True),
        Tool("points_merge", "Join two or more point clouds into a new one: points [labels]; remove: true deletes the originals. Answers points (its label), count, box.",
             obj({"points": {"type": "array", "items": {"type": "string"}}, "remove": {"type": "boolean"}, "name": {"type": "string"}}, ["points"]), points_merge, changes=True),
        Tool("points_mesh", "A mesh through a point cloud: method height (one side of a surface: a height field on the points' own plane, one vertex per cell mm, about six points a cell by default) | hull (convex) | poisson (closed; only in a FreeCAD built with PCL; depth). Answers mesh, facets, area, closed. Then meshobj_repair / part_from_mesh.",
             obj({"points": pts, "method": {"type": "string", "enum": ["height", "hull", "poisson"]}, "cell": {"type": "number"}, "depth": {"type": "integer"}, "name": {"type": "string"}}), points_mesh, changes=True),
        Tool("points_export", "Write a point cloud (mm, where it stands) to path: .ply (binary, 32-bit floats), .pcd, .asc / .xyz, .csv; <label>.ply in the output folder by default. Read back: answers count, readBack (should match), maxError. Changes nothing.", obj({"points": pts, "path": {"type": "string"}}), points_export),
    ]

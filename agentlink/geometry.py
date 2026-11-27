# SPDX-License-Identifier: LGPL-2.1-or-later
# This add-on's own copy; it was AddonKit's addonkit.geo, retired 14 Nov 2026.
# Shape building and reading on FreeCAD's Part module: rounded-rectangle
# prisms and ruled lofts (what the generators are made of), and the readings
# the checks give — sound or not, sliver faces, the least wall by rays.
# Everything in millimetres, the document's own unit.

import math

import FreeCAD
import Part


def clean(shape):
    """One solid, coplanar faces merged: a boolean leaves faces split where
    its pieces met, which reads as clutter and as short edges."""
    try:
        shape = shape.removeSplitter()
    except Exception:  # removeSplitter refuses some compounds; the shape stands
        pass
    if shape.ShapeType == "Compound" and len(shape.Solids) == 1:
        shape = shape.Solids[0]
    return shape


# ---- readings -----------------------------------------------------------------------------

def r3(v):
    return round(float(v), 3) + 0.0


def vec(v):
    return [r3(v.x), r3(v.y), r3(v.z)]


# Faces up to which a shape's box is asked from its geometry (bound_box).
BOX_EXACT_FACES = 600


def bound_box(shape):
    """A shape's bounding box from its geometry. OCC's quick box (BoundBox)
    of a curved shape that has been tessellated for the 3D view is the box
    of its triangles, a little inside the surface: in the window a 55 mm
    cylinder read 54.814 × 54.907 and a 28 mm ring 27.95, while headless
    (no tessellation) the same shapes read exact. optimalBoundingBox
    without the triangulation is the true box; it is slower, so shapes over
    BOX_EXACT_FACES faces keep the quick one (box_note says so)."""
    return bound_box_said(shape)[0]


def bound_box_said(shape):
    """(the box, whether it is the exact one). Not exact: the shape has
    more than BOX_EXACT_FACES faces, or this FreeCAD gave no exact box."""
    try:
        if shape.countElement("Face") <= BOX_EXACT_FACES:
            b = shape.optimalBoundingBox(False, False)
            if b.isValid():
                return b, True
    except Exception:
        pass
    return shape.BoundBox, False


def box_note(shape):
    """The words an answer gives with a box that is not the exact one; ""
    for an exact box. A fact about how the box was read, said each time it
    applies (27 Nov: a limit that is used is said)."""
    try:
        if bound_box_said(shape)[1]:
            return ""
        n = shape.countElement("Face")
    except Exception:
        return ""
    if n > BOX_EXACT_FACES:
        return (f"The box is not exact: the shape has {n} faces, and the exact box is worked out for {BOX_EXACT_FACES} at most. "
                "This box is FreeCAD's quick BoundBox, which can be the box of the display mesh.")
    return "The box is not exact: this FreeCAD gave no exact box. This box is FreeCAD's quick BoundBox, which can be the box of the display mesh."


def placement_fact(o):
    """An object's Placement as { at, axis, angle } (mm, deg) when it is not
    the identity; None when it is the identity or cannot be read. A body's
    sketch planes and axes are its own: with a Placement that is not the
    identity they are not the world's."""
    import math

    try:
        p = o.Placement
        if p.isIdentity():
            return None
        return {"at": vec(p.Base), "axis": vec(p.Rotation.Axis), "angle": round(math.degrees(p.Rotation.Angle), 4)}
    except Exception:
        return None


def shape_key(shape):
    """A cheap key that changes when the shape does: its hash (the OCC shape
    and placement), kind, element counts and quick box. The hash alone is
    not enough: a recomputed shape can be given the address the old one had
    (a box made taller hashed the same on FreeCAD 1.1.3 on the Mac, and a
    step's snapshot then kept its old volume)."""
    b = shape.BoundBox
    return (shape.hashCode(), shape.ShapeType, shape.countElement("Face"), shape.countElement("Edge"), shape.countElement("Vertex"),
            round(b.XMin, 6), round(b.YMin, 6), round(b.ZMin, 6), round(b.XMax, 6), round(b.YMax, 6), round(b.ZMax, 6))


def box_of(shape):
    b, exact = bound_box_said(shape)
    return {"min": [r3(b.XMin), r3(b.YMin), r3(b.ZMin)], "max": [r3(b.XMax), r3(b.YMax), r3(b.ZMax)], "size": [r3(b.XLength), r3(b.YLength), r3(b.ZLength)],
            **({} if exact else {"exact": False})}


def box_json(b, nd=1):
    """A bounding box (or a shape's) as lists rounded to nd places: min,
    max and size (the lengths along x, y, z)."""
    b = bound_box(b) if hasattr(b, "BoundBox") else b
    return {"min": [round(b.XMin, nd), round(b.YMin, nd), round(b.ZMin, nd)], "max": [round(b.XMax, nd), round(b.YMax, nd), round(b.ZMax, nd)],
            "size": [round(b.XLength, nd), round(b.YLength, nd), round(b.ZLength, nd)]}


def stats(shape):
    """What a body is, in a few numbers: what a diff compares."""
    return {
        "volume": round(shape.Volume, 2),
        "area": round(shape.Area, 2),
        "faces": len(shape.Faces),
        "solids": len(shape.Solids),
        "box": box_of(shape)["size"],
    }


def narrow_faces(shape, width_mm=0.01):
    """Faces under width_mm wide, by 2 x area / perimeter — the width of a
    strip — a sliver two faces a hair apart leave, which a round beside it
    stumbles on."""
    out = []
    for i, f in enumerate(shape.Faces):
        p = sum(e.Length for e in f.Edges)
        if p <= 0:
            continue
        w = 2.0 * f.Area / p
        if w < width_mm:
            out.append({"index": i, "width": round(w, 5), "area": round(f.Area, 4), "centroid": vec(f.CenterOfMass)})
    return sorted(out, key=lambda x: x["width"])


def short_edges(shape, length_mm=0.02):
    out = []
    for i, e in enumerate(shape.Edges):
        if e.Length < length_mm:
            out.append({"index": i, "length": round(e.Length, 5), "at": vec(e.CenterOfMass)})
    return out


def core_check(shape):
    """FreeCAD's own geometry check (Part Check Geometry's, shape.check with
    its BOP checks): (ok, the problems it names). None, [] where this
    FreeCAD's shape has no check."""
    fn = getattr(shape, "check", None)
    if fn is None:
        return None, []
    try:
        fn(True)
        return True, []
    except Exception as e:  # Part.OCCError / ValueError: one line a problem
        lines = [ln.strip() for ln in str(e).splitlines() if ln.strip()]
        return False, lines[:10] or [type(e).__name__]


# BOP check findings that are tolerance matters on a shape BRepCheck
# calls valid: a 3D curve that strays from its face's surface more than its
# tolerance (where a counterbore breaks a chamfer). Kept strict: a
# self-intersection or a bad face stays a problem.
SOFT_BOP = ("BOPAlgo_InvalidCurveOnSurface",)


def soft_bop(lines):
    """Every line of a failed check names only soft BOP findings (or is a
    heading with no finding of its own)."""
    import re

    found = False
    for ln in lines or ():
        kinds = re.findall(r"BOPAlgo_\w+|BRepCheck_\w+", ln)
        if not kinds:
            continue
        if any(k not in SOFT_BOP for k in kinds):
            return False
        found = True
    return found


def bop_where(shape, lines, n=3):
    """Where a soft BOP finding is: the elements the check's lines name
    (Edge12, Face3) with their centres; else the edges whose tolerance OCC
    widened most (where a curve and its surface disagree)."""
    import re

    out = []
    for ln in lines or ():
        for kind, i in re.findall(r"\b(Edge|Face|Vertex)(\d+)\b", ln):
            try:
                el = shape.getElement(f"{kind}{i}")
                out.append({"element": f"{kind}{i}", "at": vec(el.CenterOfMass if kind != "Vertex" else el.Point)})
            except Exception:
                pass
    if out:
        return out[:n]
    try:
        tol = sorted(((float(getattr(e, "Tolerance", 0.0)), i, e) for i, e in enumerate(shape.Edges)), key=lambda t: -t[0])
        return [{"element": f"Edge{i + 1}", "at": vec(e.CenterOfMass), "tolerance": round(t, 5)} for t, i, e in tol[:n] if t > 1e-6]
    except Exception:
        return []


def shape_facts(shape):
    """What FreeCAD says of a shape, with no grade: valid (Shape.isValid),
    closed (every shell is closed; false with no shell), solids (the
    count) and volume (mm³)."""
    shells = shape.Shells
    try:
        volume = shape.Volume
    except Exception:
        volume = 0.0
    return {"valid": bool(shape.isValid()), "closed": bool(shells) and all(s.isClosed() for s in shells), "solids": len(shape.Solids), "volume": round(volume, 3)}


def each_solid(shape):
    """Each solid of a compound, as shape_facts reads one: valid, closed,
    volume, and the centre of its box."""
    out = []
    for i, so in enumerate(shape.Solids):
        r = shape_facts(so)
        out.append({"solid": i + 1, "valid": r["valid"], "closed": r["closed"], "volume": r["volume"], "at": vec(bound_box(so).Center)})
    return out


def soundness(shape, solids_intended=False):
    """Valid, closed, one solid, a volume above 0, no slivers: as a body
    check reads it, and what "sound" means wherever a tool reports it.
    solids_intended: several solids are meant (a Body with AllowCompound),
    so their count is no problem."""
    shells = shape.Shells
    closed = bool(shells) and all(s.isClosed() for s in shells)
    narrow = narrow_faces(shape)
    short = short_edges(shape)
    problems = []
    valid = shape.isValid()  # once: on thousands of faces it is the slow part
    if not valid:
        problems.append("The shape is not valid: a boolean or loft left it broken. Rebuild the last step.")
    if not closed:
        problems.append("The shape is not closed: it has open edges, so it has no inside to print or weigh.")
    if len(shape.Solids) != 1 and not (solids_intended and shape.Solids):
        problems.append(f"{len(shape.Solids)} solids where one is meant: pieces that do not touch, or none.")
    try:
        volume = shape.Volume
    except Exception:
        volume = 0.0
    if shape.Solids and volume <= 1e-9:
        problems.append(f"The volume is {volume:.3g} mm³, not above 0: the solid is inside out or broken (a loft that twisted, a boolean that failed). Rebuild the last step.")
    if narrow:
        problems.append(
            f"{len(narrow)} face{'s' if len(narrow) != 1 else ''} under 0.01 mm wide — a sliver two faces a hair apart leave: "
            + ", ".join(f"{n['index']} ({n['width']} mm at {n['centroid']})" for n in narrow[:5])
            + ". Overlap the pieces clearly, or carry a cutter on along its slope."
        )
    return {
        "valid": valid,
        "closed": closed,
        "solids": len(shape.Solids),
        "volume": round(volume, 3),
        "narrow": narrow[:10],
        "shortEdges": short[:10],
        "problems": problems,
        "ok": not problems,
    }




def _closed_solids(shape):
    """How many of shape's solids are closed (every shell of each)."""
    n = 0
    for so in shape.Solids:
        try:
            shells = so.Shells
            if shells and all(x.isClosed() for x in shells):
                n += 1
        except Exception:
            pass
    return n


def refine_harm(before, after, rel=1e-4, absolute=1e-3):
    """Why a refine (or its fix step) made a shape worse, or None: a valid
    shape became invalid, it has fewer closed solids, or its volume moved
    by more than rel of it (absolute mm³ at the least). A shape that was
    not valid, or had no solid, is not judged on that count: fix may repair
    it. Plain shape reads only."""
    why = []
    try:
        was_valid = before.isValid()
    except Exception:
        was_valid = False
    try:
        now_valid = after.isValid()
    except Exception:
        now_valid = False
    if was_valid and not now_valid:
        why.append("the shape was valid and the result is not (isValid false)")
    c0, c1 = _closed_solids(before), _closed_solids(after)
    if c1 < c0:
        why.append(f"closed solids went from {c0} to {c1}")
    try:
        v0 = abs(before.Volume) if before.Solids else None
        v1 = abs(after.Volume) if after.Solids else 0.0
    except Exception:
        v0 = v1 = None
    if v0 and v1 is not None and abs(v1 - v0) > max(absolute, rel * v0):
        why.append(f"the volume went from {v0:.3f} to {v1:.3f} mm³ ({(v1 - v0) / v0 * 100:+.2f} %)")
    return "; ".join(why) or None


# ---- mesh objects ----------------------------------------------------------------------------

def mesh_of(o):
    """o's mesh (a Mesh kernel: CountFacets, isSolid) when o is a mesh object
    (Mesh::Feature and kin), else None. A FEM result or mesh object
    (FeaturePython) also has a property named Mesh, but it links another
    object (live 77: object_list failed "'FeaturePython' object has no
    attribute 'CountFacets'" in a FEM document)."""
    m = getattr(o, "Mesh", None)
    if m is None or not hasattr(m, "CountFacets") or not hasattr(m, "isSolid"):
        return None
    try:
        if hasattr(o, "isDerivedFrom") and str(getattr(o, "TypeId", "")).startswith("Fem::") and not o.isDerivedFrom("Mesh::Feature"):
            return None
    except Exception:  # noqa: BLE001
        pass
    return m


def mesh_row(o):
    """A mesh object in a listing: {triangles, closed}; None for any other object."""
    m = mesh_of(o)
    if m is None:
        return None
    return {"triangles": int(m.CountFacets), "closed": bool(m.isSolid())}


# ---- meshes written for export --------------------------------------------------------------

# The angle (radians) MeshPart may turn between two triangles of an exported
# mesh, beside its chord error (LinearDeflection). 0.5 is about FreeCAD's own
# default for a mesh export (28.5 degrees). At 0.0873 (5 degrees) one smooth
# loft face of 87 profiles made 3.77 M triangles and 188 MB at a chord error
# of 0.05 mm (live 65): the chord error alone keeps the surface accurate.
EXPORT_ANGULAR = 0.5


def weld_arrays(V, F, eps):
    """Points closer than about eps merged into one (a grid of eps), the
    triangles that then have a repeated corner dropped. V: (n, 3) floats;
    F: (m, 3) ints. Returns (V, F, merged count). No FreeCAD needed."""
    import numpy as np

    V = np.asarray(V, float).reshape(-1, 3)
    F = np.asarray(F, int).reshape(-1, 3)
    if not len(V):
        return V, F, 0
    key = np.round(V / eps).astype(np.int64)
    _u, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = np.asarray(inv).reshape(-1)
    V2 = V[first]
    F2 = inv[F]
    keep = (F2[:, 0] != F2[:, 1]) & (F2[:, 1] != F2[:, 2]) & (F2[:, 0] != F2[:, 2])
    return V2, F2[keep], int(len(V) - len(V2))


def welded_mesh(m, shape=None):
    """A mesh made from a shape, with its coincident points merged when it
    is not closed: the seam of a periodic face (a loft, a revolve) is
    meshed on both of its sides with points that differ in the last digits,
    so the mesh had open edges along it and an export of a valid closed
    solid read back closed: false (live 65). m when it is closed already,
    or when the merge does not help."""
    try:
        if m.isSolid():
            return m
        import Mesh

        pts, fs = m.Topology
        if not fs:
            return m
        diag = shape.BoundBox.DiagonalLength if shape is not None else 0.0
        eps = max(1e-9, 1e-7 * max(1.0, float(diag)))
        V, F, merged = weld_arrays([tuple(p) for p in pts], fs, eps)
        if not merged:
            return m
        out = Mesh.Mesh(([FreeCAD.Vector(*map(float, v)) for v in V], [tuple(int(i) for i in f) for f in F]))
        return out if out.CountFacets else m
    except Exception:  # noqa: BLE001 - the mesh as MeshPart made it
        return m


def mesh_closed(back):
    """{closed} of a mesh read back from its file. When it is open, its
    duplicate points are removed and it is checked once more: closed then,
    closedAfterMerge says so."""
    closed = bool(back.isSolid())
    out = {"closed": closed}
    if closed:
        return out
    try:
        back.removeDuplicatedPoints()
        if back.isSolid():
            out = {"closed": True, "closedAfterMerge": True}
    except Exception:  # noqa: BLE001
        pass
    return out

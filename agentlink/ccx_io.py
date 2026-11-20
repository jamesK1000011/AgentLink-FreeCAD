# SPDX-License-Identifier: LGPL-2.1-or-later
# This add-on's own copy; it was AddonKit's addonkit.ccx, retired 14 Nov 2026.
# CalculiX's files, as much as a linear static solve needs: the mesh part
# of an Abaqus/CalculiX input deck (as FreeCAD's FemMesh.writeABAQUS writes
# it), the loads and supports added to it, and the nodal results read back
# from the .frd. Plain Python, no FreeCAD, so it is tested anywhere.
# Units: mm, N, MPa, tonne/mm³ (CalculiX takes any consistent set).

import math

# The corner and mid-side nodes of each face of a C3D10 tetrahedron, in
# CalculiX's numbering (0-based): face n is the n-th entry (faces 1 to 4).
TET10_FACES = [
    ((0, 1, 2), (4, 5, 6)),
    ((0, 3, 1), (7, 8, 4)),
    ((1, 3, 2), (8, 9, 5)),
    ((2, 3, 0), (9, 7, 6)),
]


def read_mesh(text):
    """Nodes {id: (x, y, z)} and C3D10 elements {id: (n1 … n10)} of a deck."""
    nodes, elems = {}, {}
    mode = None
    pending = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("**"):
            continue
        if line.startswith("*"):
            mode = None
            pending = []
            kw = line.upper().replace(" ", "")
            if kw.startswith("*NODE,") or kw == "*NODE":
                mode = "node"
            elif kw.startswith("*ELEMENT,") and "TYPE=C3D10" in kw:
                mode = "tet10"
            continue
        if mode == "node":
            p = [x for x in line.split(",") if x.strip()]
            nodes[int(p[0])] = (float(p[1]), float(p[2]), float(p[3]))
        elif mode == "tet10":
            pending += [int(x) for x in line.split(",") if x.strip()]
            if len(pending) >= 11:
                elems[pending[0]] = tuple(pending[1:11])
                pending = []
    return nodes, elems


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)


def face_nodes(elem, face_no):
    corners, mids = TET10_FACES[face_no - 1]
    return [elem[i] for i in corners], [elem[i] for i in mids]


def area_of(nodes, corners):
    a, b, c = (nodes[n] for n in corners)
    return 0.5 * _norm(_cross(_sub(b, a), _sub(c, a)))


def nodal_loads(nodes, elems, faces, force):
    """A total force [Fx, Fy, Fz] (N) spread evenly over the area of the
    element faces [(element, face 1-4)]: for a six-node triangle under an
    even traction the corners carry nothing and each mid-side node a third
    of the triangle's share (the consistent nodal loads). {node: [fx,fy,fz]}."""
    tris = []
    for eid, fno in faces:
        corners, mids = face_nodes(elems[eid], fno)
        tris.append((area_of(nodes, corners), mids))
    total = sum(a for a, _ in tris)
    if total <= 0:
        return {}, 0.0
    out = {}
    for a, mids in tris:
        share = a / total / 3.0
        for n in mids:
            f = out.setdefault(n, [0.0, 0.0, 0.0])
            for k in range(3):
                f[k] += force[k] * share
    return out, total


def _rows(ids, per=12):
    ids = list(ids)
    return "\n".join(", ".join(str(i) for i in ids[j:j + per]) for j in range(0, len(ids), per))


def deck(mesh_text, material, fixed, cloads, dloads, gravity, buckle=None, thermal=None, bounds=None, centrif=None):
    """The whole input deck: the mesh as written, one material on every
    volume element (Evolumes), the fixed nodes, nodal loads {node: [f]},
    face pressures [(element, face, MPa)], gravity [gx, gy, gz] mm/s² or
    None; nodal displacements and stresses to the .frd."""
    out = [mesh_text.rstrip(), "",
           "** Agent Link: material, supports, loads",
           "*MATERIAL, NAME=PART",
           "*ELASTIC",
           f"{material['E']:.6g}, {material['nu']:.6g}",
           "*DENSITY",
           f"{material['rho'] * 1e-9:.6g}"] + (
           # a uniform temperature change: the material's expansion, every node from 0 to delta
           ["*EXPANSION, ZERO=0", f"{thermal['alpha']:.6g}"] if thermal else []) + [
           "*SOLID SECTION, ELSET=Evolumes, MATERIAL=PART",
           ] + (["*NSET, NSET=AGFIX", _rows(sorted(fixed))] if fixed else []) + (
           ["*NSET, NSET=AGALL", _rows(sorted(thermal["nodes"])), "*INITIAL CONDITIONS, TYPE=TEMPERATURE", "AGALL, 0.0"] if thermal else []) + [
           "*STEP"] + (["*BUCKLE", f"{int(buckle)}"] if buckle else ["*STATIC"]) + [
           "*BOUNDARY"] + (["AGFIX, 1, 3, 0.0"] if fixed else [])
    # partial holds: (node, dof 1..3, value mm) — a slide, a pin, a set move
    for n, k, v in sorted(bounds or []):
        out.append(f"{n}, {k}, {k}, {v:.9g}")
    cl = []
    for n in sorted(cloads):
        for k in range(3):
            v = cloads[n][k]
            if abs(v) > 1e-12:
                cl.append(f"{n}, {k + 1}, {v:.9g}")
    if cl:
        out += ["*CLOAD"] + cl
    dl = [f"{e}, P{f}, {p:.9g}" for e, f, p in dloads]
    if gravity is not None:
        g = _norm(gravity)
        if g > 0:
            dl.append(f"Evolumes, GRAV, {g:.9g}, {gravity[0] / g:.9g}, {gravity[1] / g:.9g}, {gravity[2] / g:.9g}")
    for c in centrif or []:
        # spinning: omega² (rad/s)², a point on the axis, the axis
        w2 = (c["rpm"] * 2 * 3.141592653589793 / 60.0) ** 2
        p, ax = c["at"], c["axis"]
        dl.append(f"Evolumes, CENTRIF, {w2:.9g}, {p[0]:.9g}, {p[1]:.9g}, {p[2]:.9g}, {ax[0]:.9g}, {ax[1]:.9g}, {ax[2]:.9g}")
    if dl:
        out += ["*DLOAD"] + dl
    if thermal:
        out += ["*TEMPERATURE", f"AGALL, {thermal['delta']:.6g}"]
    out += ["*NODE FILE", "U"] + ([] if buckle else ["*EL FILE", "S"]) + ["*END STEP", ""]
    return "\n".join(out)


def read_buckling(dat):
    """[(mode, factor)] from the .dat's buckling factor table: the loads
    times the factor is where that mode buckles."""
    out, on = [], False
    for line in dat.splitlines():
        u = line.upper().replace(" ", "")
        if "BUCKLINGFACTOROUTPUT" in u:
            on = True
            continue
        if not on:
            continue
        p = line.split()
        if len(p) >= 2:
            try:
                out.append((int(p[0]), float(p[1])))
                continue
            except ValueError:
                if out:
                    break
                continue
        if out and not line.strip():
            break
    return out


def vtu(points, cells, point_data):
    """An unstructured grid as VTK XML (ASCII): points [(x,y,z)], cells
    [10 point indices] (quadratic tetrahedra — CalculiX's C3D10 order is
    VTK's), point_data {name: [value or (x,y,z)]}."""
    out = ['<?xml version="1.0"?>', '<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">', "<UnstructuredGrid>",
           f'<Piece NumberOfPoints="{len(points)}" NumberOfCells="{len(cells)}">', "<PointData>"]
    for name, vals in point_data.items():
        comp = len(vals[0]) if vals and isinstance(vals[0], (list, tuple)) else 1
        flat = " ".join(f"{x:.6g}" for v in vals for x in (v if comp > 1 else (v,)))
        out.append(f'<DataArray type="Float64" Name="{name}" NumberOfComponents="{comp}" format="ascii">{flat}</DataArray>')
    out += ["</PointData>", "<Points>", '<DataArray type="Float64" NumberOfComponents="3" format="ascii">' + " ".join(f"{c:.6g}" for p in points for c in p) + "</DataArray>", "</Points>", "<Cells>"]
    out.append('<DataArray type="Int64" Name="connectivity" format="ascii">' + " ".join(str(i) for c in cells for i in c) + "</DataArray>")
    out.append('<DataArray type="Int64" Name="offsets" format="ascii">' + " ".join(str(10 * (k + 1)) for k in range(len(cells))) + "</DataArray>")
    out.append('<DataArray type="UInt8" Name="types" format="ascii">' + " ".join("24" for _ in cells) + "</DataArray>")
    out += ["</Cells>", "</Piece>", "</UnstructuredGrid>", "</VTKFile>", ""]
    return "\n".join(out)


def read_frd(text):
    """The last step's nodal DISP {node: (ux,uy,uz)} and STRESS
    {node: (sxx,syy,szz,sxy,syz,szx)} from an ASCII .frd."""
    disp, stress = {}, {}
    block = None
    for line in text.splitlines():
        if line.startswith(" -4"):
            name = line[5:13].strip()
            block = {"DISP": disp, "STRESS": stress}.get(name)
            if block is not None:
                block.clear()
            continue
        if line.startswith(" -3"):
            block = None
            continue
        if block is not None and line[1:3] == "-1":
            nid = int(line[3:13])
            s = line.rstrip("\r\n")
            block[nid] = tuple(float(s[p:p + 12]) for p in range(13, len(s), 12) if s[p:p + 12].strip())
    return disp, stress


def von_mises(s):
    sxx, syy, szz, sxy, syz, szx = s[:6]
    return math.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3.0 * (sxy ** 2 + syz ** 2 + szx ** 2))


def normal_stress(s, n):
    """The normal stress along the unit direction n."""
    sxx, syy, szz, sxy, syz, szx = s[:6]
    x, y, z = n
    return sxx * x * x + syy * y * y + szz * z * z + 2 * (sxy * x * y + syz * y * z + szx * z * x)


# ---- natural frequencies ---------------------------------------------------------------

def deck_modes(mesh_text, material, fixed, count, bounds=None):
    """A frequency step: the lowest `count` modes, held at the fixed nodes
    (none: free, the first six near zero being the rigid motions)."""
    out = [mesh_text.rstrip(), "",
           "** Agent Link: material, supports, natural frequencies",
           "*MATERIAL, NAME=PART",
           "*ELASTIC",
           f"{material['E']:.6g}, {material['nu']:.6g}",
           "*DENSITY",
           f"{material['rho'] * 1e-9:.6g}",
           "*SOLID SECTION, ELSET=Evolumes, MATERIAL=PART"]
    if fixed:
        out += ["*NSET, NSET=AGFIX", _rows(sorted(fixed))]
    out += ["*STEP", "*FREQUENCY", f"{int(count)}"]
    if fixed or bounds:
        out += ["*BOUNDARY"] + (["AGFIX, 1, 3, 0.0"] if fixed else [])
        # partial holds in a frequency step are held at zero
        out += [f"{n}, {k}, {k}, 0.0" for n, k, _ in sorted(bounds or [])]
    out += ["*NODE FILE", "U", "*END STEP", ""]
    return "\n".join(out)


def read_frequencies(dat):
    """[(mode, Hz)] from the .dat's eigenvalue table (units mm, N, tonne:
    CalculiX's CYCLES/TIME column is in Hz)."""
    out, on = [], False
    for line in dat.splitlines():
        u = line.upper()
        if "E I G E N V A L U E   O U T P U T" in u:
            on = True
            continue
        if not on:
            continue
        p = line.split()
        if len(p) >= 4:
            try:
                out.append((int(p[0]), float(p[3])))
                continue
            except ValueError:
                if out:
                    break
                continue
        if out and not line.strip():
            break
    return out


def read_frd_blocks(text, name):
    """Every block of one result in an .frd, in order: [{node: values}] —
    one DISP block per mode of a frequency step."""
    blocks, block = [], None
    for line in text.splitlines():
        if line.startswith(" -4"):
            block = {} if line[5:13].strip() == name else None
            if block is not None:
                blocks.append(block)
            continue
        if line.startswith(" -3"):
            block = None
            continue
        if block is not None and line[1:3] == "-1":
            nid = int(line[3:13])
            s = line.rstrip("\r\n")
            block[nid] = tuple(float(s[p:p + 12]) for p in range(13, len(s), 12) if s[p:p + 12].strip())
    return blocks


# ---- steady heat -----------------------------------------------------------------------

HEAT_ELEMENTS = ("DC3D10", "C3D10")


def deck_heat(mesh_text, k, temps, fluxes, films, start=20.0, element="DC3D10", elastic=None):
    """A steady heat-transfer step on the same mesh. element: DC3D10 (a
    heat-transfer tetrahedron) or C3D10 (the mesh as written, as FreeCAD's
    own CalculiX writer runs a *HEAT TRANSFER step:
    femsolver/calculix/write_step_equation.py); elastic (E, nu) is written
    for C3D10, whose material CalculiX may check for it (unused by the step).
    Units mm, tonne, s: k in W/(m·K) is the same number in mW/(mm·K);
    temps {node: °C}, fluxes [(element, face, mW/mm²)] into the part, films
    [(element, face, h mW/(mm²·K), air °C)]."""
    if element == "DC3D10":
        mesh = mesh_text.replace("TYPE=C3D10", "TYPE=DC3D10").replace("type=C3D10", "type=DC3D10")
    else:
        mesh = mesh_text
    nodes, _ = read_mesh(mesh_text)
    mat = ["*MATERIAL, NAME=PART"]
    if element != "DC3D10":
        e, nu = elastic or (1000.0, 0.3)
        mat += ["*ELASTIC", f"{float(e):.6g}, {float(nu):.6g}"]
    out = [mesh.rstrip(), "",
           "** Agent Link: steady heat",
           "*NSET, NSET=AGALL", _rows(sorted(nodes))] + mat + [
           "*CONDUCTIVITY",
           f"{k:.6g}",
           "*SOLID SECTION, ELSET=Evolumes, MATERIAL=PART",
           "*INITIAL CONDITIONS, TYPE=TEMPERATURE",
           f"AGALL, {start:.6g}",
           "*STEP",
           "*HEAT TRANSFER, STEADY STATE",
           "1., 1."]
    if temps:
        out += ["*BOUNDARY"] + [f"{n}, 11, 11, {t:.6g}" for n, t in sorted(temps.items())]
    if fluxes:
        out += ["*DFLUX"] + [f"{e}, S{f}, {q:.9g}" for e, f, q in fluxes]
    if films:
        out += ["*FILM"] + [f"{e}, F{f}, {t:.6g}, {h:.9g}" for e, f, h, t in films]
    out += ["*NODE FILE", "NT", "*END STEP", ""]
    return "\n".join(out)


def read_temperatures(frd):
    """{node: °C} from the last NDTEMP block of an .frd."""
    blocks = read_frd_blocks(frd, "NDTEMP")
    return {n: v[0] for n, v in blocks[-1].items()} if blocks else {}


def frd_times(frd, name="NDTEMP"):
    """The step time of each block of one result in an .frd, in order (the
    " 100C" line before it; None where it cannot be read): a heat step that
    stopped short shows a last time under 1."""
    times, t = [], None
    for line in (frd or "").splitlines():
        if line.startswith("  100C"):
            parts = line.split()
            try:
                t = float(parts[2])
            except (IndexError, ValueError):
                t = None
            continue
        if line.startswith(" -4"):
            if line[5:13].strip() == name:
                times.append(t)
            t = None
    return times


def held_check(temps, T, tol=None):
    """Whether the solved temperatures T {node: °C} hold the temperatures
    given (temps {node: °C}), per value given: [{celsius, nodes, read [min,
    max], missing}], and ok. tol: 0.1 % of the span given, at least 0.01 °C.
    Plain Python."""
    groups = {}
    for n, c in (temps or {}).items():
        groups.setdefault(float(c), []).append(n)
    if tol is None:
        vals = list(groups) or [0.0]
        tol = max(0.01, 1e-3 * (max(vals) - min(vals)))
    rows, ok = [], True
    for c in sorted(groups, reverse=True):
        got = [T[n] for n in groups[c] if n in T]
        row = {"celsius": c, "nodes": len(groups[c])}
        if got:
            row["read"] = [round(min(got), 4), round(max(got), 4)]
        missing = len(groups[c]) - len(got)
        if missing:
            row["missing"] = missing
        if not got or missing or max(abs(x - c) for x in got) > tol:
            ok = False
        rows.append(row)
    return rows, ok


# ---- several parts: each its own material, tied or in contact -------------------------

def parts_deck(text, parts, ties=(), contacts=(), contact_slope=None, friction=0.0, contact_type="NODE TO SURFACE"):
    """A one-material deck (deck()) made a several-part one: parts
    [(elset, element ids, {E, nu, rho, alpha?})] each with its own
    material and section; ties and contacts [(name, slave [(e, f)], master
    [(e, f)])] as element-face surfaces, bonded (*TIE) or touching
    (*CONTACT PAIR, linear pressure-overclosure, optional friction). A
    contact makes the step nonlinear: it runs in increments."""
    head, sep, rest = text.partition("** Agent Link: material, supports, loads")
    lines = rest.split("\n")
    # the one material's own block and section go; each part gets its own
    keep, skip = [], False
    for ln in lines:
        u = ln.strip().upper()
        if u.startswith("*MATERIAL, NAME=PART"):
            skip = True
            continue
        if skip and u.startswith("*SOLID SECTION"):
            skip = False
            continue
        if skip and u.startswith("*") and not u.startswith(("*ELASTIC", "*DENSITY", "*EXPANSION")):
            skip = False
        if not skip:
            keep.append(ln)
    defs = []
    for name, ids, m in parts:
        defs += [f"*ELSET, ELSET={name}", _rows(sorted(ids)), f"*MATERIAL, NAME=M{name}", "*ELASTIC", f"{m['E']:.6g}, {m['nu']:.6g}",
                 "*DENSITY", f"{m['rho'] * 1e-9:.6g}"]
        if m.get("alpha"):
            defs += ["*EXPANSION, ZERO=0", f"{m['alpha']:.6g}"]
        defs += [f"*SOLID SECTION, ELSET={name}, MATERIAL=M{name}"]
    for kind, items in (("tie", ties), ("contact", contacts)):
        for name, slave, master in items:
            for side, faces in (("S", slave), ("M", master)):
                defs += [f"*SURFACE, NAME={name}{side}, TYPE=ELEMENT"] + [f"{e}, S{f}" for e, f in faces]
            if kind == "tie":
                defs += [f"*TIE, NAME={name}, ADJUST=NO", f"{name}S, {name}M"]
            else:
                defs += [f"*CONTACT PAIR, INTERACTION=AGSI, TYPE={contact_type}", f"{name}S, {name}M"]
    if contacts:
        defs += ["*SURFACE INTERACTION, NAME=AGSI", "*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR", f"{float(contact_slope or 1e4):.6g}"]
        if friction:
            defs += ["*FRICTION", f"{float(friction):.6g}, {float(contact_slope or 1e4) / 20:.6g}"]
    body = "\n".join(keep)
    i = body.find("*STEP")
    body = body[:i] + "\n".join(defs) + "\n" + body[i:]
    if contacts:
        body = body.replace("*STEP\n*STATIC", "*STEP, INC=200\n*STATIC\n0.1, 1.0, 1e-5, 1.0", 1)
    return head + sep + body


def find_binary(name, pref_group, pref_key, env):
    """A solver's command line: the environment variable env, else FreeCAD's
    FEM preference (Mod/Fem/<pref_group> <pref_key>), else name on the PATH;
    None when none is found."""
    import os
    import shutil

    p = os.environ.get(env)
    if p and shutil.which(p):
        return shutil.which(p)
    try:
        import FreeCAD

        q = FreeCAD.ParamGet(f"User parameter:BaseApp/Preferences/Mod/Fem/{pref_group}").GetString(pref_key, "")
        if q and shutil.which(q):
            return shutil.which(q)
    except Exception:  # noqa: BLE001 — no FreeCAD here, or no such preference
        pass
    return shutil.which(name)


# ---- the solvers' own error lines, and where they are ----------------------------------------
# Gmsh ends a failed run with a summary block ("Mesh generation error
# summary", "2 errors", "Check the full log for details") that says nothing
# of what or where. The words that do are its "Error" lines before that
# block: the entity they name (surface 12, curve 7, volume 1), a point
# ("at point (x, y, z)", "(x,y,z)"), facets that intersect. CalculiX writes
# "*ERROR in <routine>: <what>" and often the next line or two say which
# element or node. These read the lines out, with the numbers, and keep
# the whole log in a file so the answer can name it.

import re as _re

_GMSH_SUMMARY = _re.compile(r"^(-+|mesh generation error summary|\d+\s+(warning|error)s?|check the full log( for details)?\.?|there (was|were) \d+ (warning|error)s?.*)$", _re.I)
_GMSH_ENTITY = _re.compile(r"\b(surface|curve|volume|point|face|edge|line)s?\s+(\d+(?:\s*(?:,|and)\s*\d+)*)", _re.I)
_POINT = _re.compile(r"\(\s*(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*,\s*(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*,\s*(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*\)", _re.I)
_POINT_WORDS = _re.compile(r"\bpoint\s+(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)", _re.I)
_KIND = {"surface": "surface", "face": "surface", "curve": "curve", "edge": "curve", "line": "curve", "volume": "volume", "point": "point"}
_SHAPE_WORD = {"surface": "Face", "curve": "Edge", "volume": "Solid", "point": "Vertex"}


def _tag_after(line):
    """The text of a log line after its "Error   :" or "Warning :" head."""
    return _re.sub(r"^\s*(error|warning|info)\s*:\s*", "", line, flags=_re.I).strip()


def gmsh_report(text, limit=8):
    """Gmsh's own error and warning lines (its summary block left out), and
    where they are: entities [{kind, tag, shape}] (shape: the FreeCAD
    sub-shape name of the same number, e.g. surface 12 is Face12 — Gmsh
    keeps the order of a merged BREP's faces) and points [[x, y, z]].
    Plain text in, plain dict out."""
    errors, warnings, entities, points = [], [], [], []
    seen = set()
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        is_err = low.startswith("error") or "plc error" in low
        is_warn = low.startswith("warning")
        if not (is_err or is_warn):
            continue
        body = _tag_after(line).rstrip(".").strip()
        if not body or _GMSH_SUMMARY.match(body):
            continue
        if body in seen:
            continue
        seen.add(body)
        (errors if is_err else warnings).append(body)
        for m in _GMSH_ENTITY.finditer(body):
            kind = _KIND[m.group(1).lower()]
            for t in _re.findall(r"\d+", m.group(2)):
                row = {"kind": kind, "tag": int(t), "shape": f"{_SHAPE_WORD[kind]}{int(t)}"}
                if row not in entities:
                    entities.append(row)
        for m in list(_POINT.finditer(body)) + list(_POINT_WORDS.finditer(body)):
            p = [round(float(m.group(i)), 3) for i in (1, 2, 3)]
            if p not in points:
                points.append(p)
    # A point named as an entity ("point 3") is a vertex tag; a point with
    # three numbers is a place: the place is kept, not a tag of 3 numbers.
    entities = [e for e in entities if not (e["kind"] == "point" and points and any(float(e["tag"]) in p for p in points))]
    return {"errors": errors[:limit], "warnings": warnings[:max(2, limit // 2)], "entities": entities[:12], "points": points[:6],
            "more": max(0, len(errors) - limit)}


def ccx_report(text, limit=6):
    """CalculiX's own *ERROR lines, each with the line after it when that
    one says more (CalculiX often writes the element or node there), and
    the elements and nodes they name."""
    lines = [ln.rstrip() for ln in str(text or "").splitlines()]
    errors, elements, nodes = [], [], []
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if "*ERROR" in ln.upper() or ln.upper().startswith("ERROR"):
            said = ln
            j = i + 1
            while j < len(lines) and j <= i + 2:
                nxt = lines[j].strip()
                if not nxt or nxt.startswith("*") or "ERROR" in nxt.upper():
                    break
                said += " " + nxt
                j += 1
            if said not in errors:
                errors.append(said)
            i = j
            continue
        i += 1
    for e in errors:
        for m in _re.finditer(r"\belements?\s+(\d+)", e, _re.I):
            if int(m.group(1)) not in elements:
                elements.append(int(m.group(1)))
        for m in _re.finditer(r"\bnodes?\s+(\d+)", e, _re.I):
            if int(m.group(1)) not in nodes:
                nodes.append(int(m.group(1)))
    return {"errors": errors[:limit], "elements": elements[:12], "nodes": nodes[:12], "more": max(0, len(errors) - limit)}


def keep_log(folder, name, text):
    """The whole log written as <folder>/<name>; its path, or None when it
    could not be written."""
    import os

    try:
        os.makedirs(folder, exist_ok=True)
        p = os.path.join(folder, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(str(text or ""))
        return p
    except OSError:
        return None


def gmsh_words(rep, log=None, fallback=""):
    """One sentence for a refusal from gmsh_report: Gmsh's own lines, then
    where (the entities and points it named), then the log's path."""
    said = " | ".join(rep["errors"] or rep["warnings"]) or fallback or "no error line (see the log)"
    if rep.get("more"):
        said += f" | and {rep['more']} more"
    where = []
    if rep["entities"]:
        where.append(", ".join(f"Gmsh {e['kind']} {e['tag']} ({e['shape']})" for e in rep["entities"]))
    if rep["points"]:
        where.append("at " + ", ".join("(" + ", ".join(f"{v:g}" for v in p) + ")" for p in rep["points"]) + " mm")
    out = "Gmsh said: " + said
    if where:
        out += ". Where: " + "; ".join(where)
    if log:
        out += f". Full Gmsh log: {log}"
    return out


def ccx_words(rep, log=None, at=None, fallback=""):
    """One sentence for a refusal from ccx_report: CalculiX's own lines,
    the elements and nodes they name (at: {element: [x, y, z]} where
    known), then the log's path."""
    said = " | ".join(rep["errors"]) or fallback or "no *ERROR line (see the log)"
    if rep.get("more"):
        said += f" | and {rep['more']} more"
    where = []
    if rep["elements"]:
        where.append("element " + ", ".join(str(e) + (f" at ({', '.join(f'{v:g}' for v in at[e])}) mm" if at and e in at else "") for e in rep["elements"]))
    if rep["nodes"]:
        where.append("node " + ", ".join(str(n) for n in rep["nodes"]))
    out = "CalculiX said: " + said
    if where:
        out += ". Where: " + "; ".join(where)
    if log:
        out += f". Full CalculiX log: {log}"
    return out

# SPDX-License-Identifier: LGPL-2.1-or-later
# Strength by finite elements. fea_solve builds the study as FreeCAD's own
# FEM analysis (CalculiX solver, Gmsh mesh, material, fixed / force /
# pressure / self-weight constraints) and solves it with FemToolsCcx, its
# results loaded into the analysis, where the study is one body, fixed
# holds, those loads, linear (fem_route_why). The rest — several parts tied
# or in contact, nonlinear, refined regions, pinned holds, heat and spin, and
# fea_modes / fea_buckle / fea_heat / fea_shell — still run Agent Link's own
# deck: Gmsh into ten-node tetrahedra, read into FreeCAD's FemMesh, solved by
# CalculiX (ccx), read back from the .frd. The verdicts are Agent Link's
# either way.
# Headless: no FEM workbench GUI, no Qt. The study (body, material, holds,
# loads) is kept with the document; the last results with the session.

import math
import os
import subprocess
import time

import FreeCAD
import Part

from .. import ccx_io
from .. import paths
from .. import runners
from .. import facepick
from .. import geometry as geo
from .. import store
from ..protocol import ToolError
from . import material as matfam
from . import picks

GROUP = "strength"
INFO = "Strength by finite elements (Gmsh and CalculiX): set up a body, hold faces, load them, solve for stress, displacement and safety factor."

V = FreeCAD.Vector
KEY = "fea"
G = 9810.0  # mm/s²


def _study(doc):
    """The strength study kept with the document, or None."""
    return store.read(doc, KEY, None)


def _save(doc, st):
    """The study written to the document."""
    store.write(doc, KEY, st)


def _results(session):
    """The last solve kept with the session, or None."""
    return getattr(session, "_agentlink_fea", None)


ELMER_EQUATIONS = {"elasticity": "makeEquationElasticity", "deformation": "makeEquationDeformation", "heat": "makeEquationHeat",
                   "flow": "makeEquationFlow", "electrostatic": "makeEquationElectrostatic", "electricforce": "makeEquationElectricforce",
                   "flux": "makeEquationFlux", "staticcurrent": "makeEquationStaticCurrent", "magnetodynamic": "makeEquationMagnetodynamic",
                   "magnetodynamic2d": "makeEquationMagnetodynamic2D"}


FLUIDS = {"air": {"Name": "Air", "Density": "1.204 kg/m^3", "DynamicViscosity": "1.81e-5 Pa*s", "KinematicViscosity": "1.5e-5 m^2/s",
                  "ThermalConductivity": "0.0257 W/m/K", "SpecificHeat": "1005 J/kg/K", "SpecificHeatRatio": "1.4"},
          "water": {"Name": "Water", "Density": "998 kg/m^3", "DynamicViscosity": "1.0e-3 Pa*s", "KinematicViscosity": "1.0e-6 m^2/s",
                    "ThermalConductivity": "0.6 W/m/K", "SpecificHeat": "4182 J/kg/K"}}


def _setq(o, prop, text, number):
    """A quantity set as text with its unit, or as a plain SI number where
    this FreeCAD's property is a float."""
    try:
        setattr(o, prop, text)
    except Exception:
        setattr(o, prop, number)


def ObjectsFem_():
    """FreeCAD's ObjectsFem, the makers of every FEM object."""
    import ObjectsFem

    return ObjectsFem


def objects_fem():
    """FreeCAD's ObjectsFem, or None where the FEM module is not in this build."""
    try:
        return ObjectsFem_()
    except ImportError:
        return None


def _binary(name, pref_group, pref_key, env):
    """A program's path: FreeCAD's FEM preference, the environment variable, the PATH; None when it is not found."""
    return ccx_io.find_binary(name, pref_group, pref_key, env)


def _nonlinear(text, cards, a):
    """A deck made nonlinear: large deflections (NLGEOM) in increments, and
    each material elastic-plastic from its yield to its tensile strength
    (or a little past yield) at elongation (5 % unless the card says)."""
    import re

    text = text.replace("*STEP\n*STATIC", "*STEP, NLGEOM, INC=300\n*STATIC\n0.05, 1.0, 1e-6, 0.25", 1)
    text = text.replace("*STEP, INC=200\n*STATIC\n0.1, 1.0, 1e-5, 1.0", "*STEP, NLGEOM, INC=300\n*STATIC\n0.05, 1.0, 1e-6, 0.25", 1)
    if not a.get("elasticOnly"):
        for name, c in cards.items():
            y = c.get("yield")
            if not y:
                continue
            uts = float(c.get("uts") or float(y) * 1.1)
            elong = float(c.get("elongation") or 5) / 100.0
            plastic = f"*PLASTIC\n{float(y):.6g}, 0\n{max(uts, float(y) * 1.001):.6g}, {elong:.6g}"
            text = re.sub(rf"(\*MATERIAL, NAME={name}\n\*ELASTIC\n[^\n]*\n)", lambda m: m.group(1) + plastic + "\n", text, count=1)
    text = text.replace("*EL FILE\nS\n", "*EL FILE\nS, PEEQ\n", 1)
    return text


def failed_at(e, own=__file__):
    """Where in this file an exception of FreeCAD's came up, as " (strength.py:820)":
    which of the FEM route's steps it was (an error such as "Cannot add static
    property" names no object), or "" when no frame of the traceback is here."""
    import traceback

    here = [f for f in traceback.extract_tb(e.__traceback__) if os.path.basename(f.filename) == os.path.basename(own)]
    return f" ({os.path.basename(own)}:{here[-1].lineno})" if here else ""


def mark_helper(o):
    """An object Agent Link keeps for a study (a compound of parts, one
    solid studied alone): hidden, and not a part of its own to
    session_state, view_render or the hidden lists (AgentLinkHelper)."""
    try:
        if "AgentLinkHelper" not in o.PropertiesList:
            o.addProperty("App::PropertyBool", "AgentLinkHelper", "Agent Link", "Kept by Agent Link for a study: not a part")
            o.AgentLinkHelper = True
            try:
                o.setEditorMode("AgentLinkHelper", 2)
            except Exception:
                pass
    except Exception:
        pass
    try:
        o.Visibility = False
    except Exception:
        pass


def solid_holder(session, src, n):
    """One solid of a multi-solid body, for a study of it alone: a hidden
    helper object "<body> solid <n> (study)", its shape the body's solid n
    as the body is now (made or refreshed)."""
    sols = list(src.Shape.Solids)
    if not 1 <= n <= len(sols):
        raise ToolError("invalid_input" if len(sols) > 1 else "invalid_state",
                        f"solid: 1 to {len(sols)} — {src.Label} has {len(sols)} solid{'s' if len(sols) != 1 else ''}" + ("" if len(sols) > 1 else ": study the body itself (leave solid out)") + ".")
    label = f"{src.Label} solid {n} (study)"
    doc = session.doc
    h = next((x for x in doc.Objects if x.Label == label), None)
    if h is None:
        h = doc.addObject("Part::Feature", "StudySolid")
        h.Label = label
    sh = sols[n - 1].copy()
    try:
        same = not h.Shape.isNull() and geo.stats(h.Shape) == geo.stats(sh)
    except Exception:
        same = False
    if not same:
        h.Shape = sh
    mark_helper(h)
    return h


def last_lines(text, n=6):
    """CalculiX's last lines that say something (its errors first), joined."""
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    errs = [ln for ln in lines if "ERROR" in ln.upper() or "WARNING" in ln.upper()]
    pick = (errs[:3] + [ln for ln in lines[-n:] if ln not in errs[:3]])[:n] if errs else lines[-n:]
    return " | ".join(pick)[:900]


def ccx_hint(log):
    """What to do about CalculiX's own error lines, where they say it: a
    part free to move, a badly shaped element. "" when they name neither."""
    low = str(log or "").lower()
    out = ""
    if "singular" in low or "zero pivot" in low:
        out += " The part may be free to move: hold more faces (fea_hold)."
    if "nonpositive jacobian" in low:
        out += (" Nonpositive jacobian: an element of the mesh is folded over, usually a coarse second-order tetrahedron on a small"
                " round or a thin wall — fea_setup { mesh: a smaller size, about half } (holds and loads are kept), or fea_refine at the small feature, then fea_solve again.")
    if "no material was assigned" in low:
        out += " An element has no material: the mesh holds elements outside the part's solid — body_check the body (one closed solid), then fea_solve again."
    if "too many cutbacks" in low or "increment size smaller" in low:
        out += (" It stopped finding equilibrium as the load rose (a nonlinear run): less load, a stronger material or a larger section;"
                " or contact that never closes, or a part held too little.")
    return out


def self_weight(g, gravity):
    """A self-weight constraint set to gravity [gx, gy, gz] in g. FreeCAD 1.1
    keeps GravityAcceleration (a quantity) and GravityDirection (a unit
    vector); before it, Gravity_x / _y / _z as multiples of g."""
    gv = V(*[float(x) for x in gravity])
    if "GravityAcceleration" in g.PropertiesList:
        g.GravityAcceleration = g.GravityAcceleration * gv.Length  # its own 1 g, as FreeCAD's migration does
        d = V(gv)
        d.normalize()
        g.GravityDirection = d
    else:
        g.Gravity_x, g.Gravity_y, g.Gravity_z = gv.x, gv.y, gv.z


def gmsh_run(tool, timeout, name="Gmsh", slow="a coarser mesh (fea_setup { mesh }) or a longer timeout (fea_solve { timeout })"):
    """One of FreeCAD's meshers (GmshTools, NetgenTools) run to the end,
    bounded: its error lines, or "". FreeCAD 1.1 runs a mesher as a
    QProcess (prepare, compute, then the mesh is read into the mesh object
    when it finishes) and GmshTools.create_mesh() answers nothing; before
    1.1 create_mesh() answered Gmsh's stderr."""
    proc = getattr(tool, "process", None)
    if proc is None or not hasattr(tool, "prepare") or not hasattr(tool, "compute"):
        return str(tool.create_mesh() or "") if hasattr(tool, "create_mesh") else str(tool.run() or "")
    tool.prepare()
    tool.compute()
    if not proc.waitForFinished(int(max(1.0, float(timeout)) * 1000)):
        running = True
        try:
            running = proc.state() != proc.ProcessState.NotRunning
        except Exception:
            pass
        if running:
            try:
                proc.kill()
                proc.waitForFinished(3000)
            except Exception:
                pass
            raise ToolError("failed", f"{name} took over {float(timeout):g} s: {slow}.")
        why = ""
        try:
            why = str(proc.errorString())
        except Exception:
            pass
        raise RuntimeError(f"{name} did not run ({why or 'no reason given'})")
    try:
        return bytes(proc.readAllStandardError().data()).decode("utf-8", "replace").strip()
    except Exception:
        return ""


def ccx_said(fea, ccx, timeout):
    """What CalculiX printed on a run that wrote no results: FemToolsCcx's
    kept stdout and stderr, else ccx run again in its folder on the same
    deck, its output read."""
    text = ""
    for k in ("ccx_stdout", "ccx_stderr"):
        v = getattr(fea, k, None)
        if isinstance(v, bytes):
            v = v.decode("utf-8", "replace")
        if v:
            text += str(v) + "\n"
    if text.strip():
        return last_lines(text)
    try:
        inp = fea.inp_file_name
        r = subprocess.run([ccx, "-i", os.path.splitext(os.path.basename(inp))[0]], cwd=os.path.dirname(inp), capture_output=True, text=True, timeout=min(float(timeout), 120.0))
        return last_lines((r.stdout or "") + (r.stderr or ""))
    except Exception:  # noqa: BLE001 - no words to add
        return ""


def unheld_words(label, count, free):
    """The refusal for solids no hold reaches: "solid 2 (at …) touches" for
    one, "solids 2 and 3 (…) touch" for several."""
    where = [f"solid {i} (at {geo.vec(p)})" for i, p in free]
    if len(where) == 1:
        said, verb = where[0], "touches"
    else:
        said, verb = ", ".join(where[:-1]) + " and " + where[-1], "touch"
    return (f"{label} is {count} separate solids and {said} {verb} no held face: a part held by nothing has no static answer, and solids that only touch are not joined in the study. "
            "Hold each solid too (fea_hold its faces), study one alone (fea_setup { solid: n }), or fuse them for a check of the whole.")


def _pick_report(shape, q, what):
    """The faces a query picks, and each described (name, area, centre) for the answer."""
    picked = facepick.pick(shape, q, what)
    return picked, [facepick.describe(n, f) for n, f in picked]


def fem_route_why(st, a):
    """Why this study does not go through FreeCAD's FEM objects here, or
    None when it does: one body, fixed holds, force / pressure / gravity,
    linear, no refined regions."""
    if st.get("parts"):
        return "several parts tied or in contact (fea_parts) are solved by its own deck"
    if a.get("nonlinear"):
        return "nonlinear (large deflection, elastic-plastic) is solved by its own deck"
    if st.get("refine"):
        return "refined mesh regions (fea_refine) are meshed by its own Gmsh script"
    if any(h.get("kind", "fixed") != "fixed" for h in st["holds"]):
        return "a pinned or sliding hold is solved by its own deck"
    odd = sorted({ld["kind"] for ld in st["loads"] if ld["kind"] not in ("force", "pressure", "gravity")})
    if odd:
        return f"{' and '.join(odd)} loads are solved by its own deck"
    try:
        import ObjectsFem  # noqa: F401
        from femtools import ccxtools  # noqa: F401
        from femmesh import gmshtools  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return f"FreeCAD's FEM tools are not here ({type(e).__name__}: {e})"
    return None


def _query_words(q):
    """A face query in words: "at z = 20 facing +Z", "Face6", "near [1, 2, 3]"."""
    if not isinstance(q, dict):
        return str(q)
    bits = []
    if "faces" in q:
        bits.append(", ".join(q["faces"]) if isinstance(q["faces"], list) else str(q["faces"]))
    for ax in "xyz":
        if ax in q:
            bits.append(f"at {ax} = {q[ax]:g}" if isinstance(q[ax], (int, float)) else f"at {ax} = {q[ax]}")
    if "normal" in q:
        n = q["normal"]
        axes = {(1, 0, 0): "+X", (-1, 0, 0): "-X", (0, 1, 0): "+Y", (0, -1, 0): "-Y", (0, 0, 1): "+Z", (0, 0, -1): "-Z"}
        try:
            key = tuple(int(round(float(c))) for c in n)
            name = axes.get(key) if all(abs(float(c) - k) < 1e-9 for c, k in zip(n, key)) else None
        except (TypeError, ValueError):
            name = None
        bits.append(f"facing {name or list(n)}")
    if "near" in q:
        bits.append(f"near {list(q['near'])}")
    if q.get("cylinder"):
        bits.append("cylindrical")
    return " ".join(bits) or "the query"


def unmatched(st, shape, pick):
    """The study's holds and loads whose face query picks nothing on the
    shape as it is now: ["Load 1: no face at z = 20 facing +Z now; the part changed?"]."""
    out = []
    for what, items in (("Hold", st.get("holds") or []), ("Load", st.get("loads") or [])):
        for i, it in enumerate(items, 1):
            q = it.get("faces")
            if q is None:
                continue  # gravity, temperature, spin: the whole part
            try:
                got = pick(shape, q, "faces")
            except Exception:  # noqa: BLE001 - the refusal is the answer here
                got = []
            if not got:
                out.append(f"{what} {i}: no face {_query_words(q)} now; the part changed? fea_{what.lower()} it again (replace: true), or clear: true.")
    return out


def _same_in(item, items):
    """Whether an identical hold or load is already in the list."""
    import json

    key = json.dumps(item, sort_keys=True, default=str)
    return any(json.dumps(x, sort_keys=True, default=str) == key for x in items or [])


def _setup_said(old, keep, reset):
    """What fea_setup did with the study before: its holds and loads kept
    (the same body, no reset) or dropped (another body, or reset: true),
    said either way so a second setup never doubles them silently."""
    holds, loads = len(old.get("holds") or []), len(old.get("loads") or [])
    if not (holds or loads):
        return {}
    if keep:
        return {"kept": {"holds": holds, "loads": loads,
                         "note": "The study's holds and loads from before are kept: fea_hold / fea_load add to them (an identical one is refused); reset: true starts the study fresh."}}
    return {"dropped": {"holds": old.get("holds") or [], "loads": old.get("loads") or [],
                        "why": "reset: true" if reset else f"the study was on {old.get('body')}"}}



def _unheld_solids(st, shape):
    """The solids of a multi-solid shape that touch none of the held faces:
    [(number from 1, centre)]. One solid: none."""
    sols = list(getattr(shape, "Solids", []) or [])
    if len(sols) < 2:
        return []
    held = []
    for h in st.get("holds", []):
        try:
            held += [f for _name, f in facepick.pick(shape, h["faces"], "faces")]
        except Exception:
            continue
    if not held:
        return []
    out = []
    for i, so in enumerate(sols, 1):
        try:
            if not any(so.distToShape(f)[0] < 1e-4 for f in held):
                out.append((i, so.BoundBox.Center))
        except Exception:
            continue
    return out

# The study's tools that set up or read and never run CalculiX: every other
# fea_ tool's answer carries its lines.
NOT_SOLVERS = ("fea_setup", "fea_hold", "fea_load", "fea_clear", "fea_results", "fea_probe", "fea_chart", "fea_export", "fea_refine")


def _health(session, tool, changed):
    """CalculiX's own warning lines after a solve that went through (the
    shared health check, agentlink/health.py). A refused solve carries its
    error lines in the refusal."""
    tail = getattr(session, "_ccx_tail", None)
    session._ccx_tail = None  # read once: a later call is not told an earlier solve's lines
    name = str(getattr(tool, "name", ""))
    if not tail or not name.startswith("fea_") or name in NOT_SOLVERS:
        return None
    warn = [x for x in str(tail).split(" | ") if "WARNING" in x.upper() or "ERROR" in x.upper()]
    if not warn:
        return [{"line": "CalculiX ran clean"}]
    return [{"line": "CalculiX: " + " | ".join(warn[:3]), "red": any("ERROR" in x.upper() for x in warn),
             "todo": "read the lines: a part free to move wants more held faces (fea_hold); a bad element a coarser or finer mesh"}]


def faces_normal(picked):
    """The picked faces' outward normals summed by area: the one way they
    face (near nothing when they face no one way)."""
    n = V(0, 0, 0)
    for _, f in picked:
        n += facepick.outward_normal(f) * f.Area
    return n


def write_vtu(path, f):
    """A solve's kept field written as a VTU (ParaView, FreeCAD's FEM post-processing)."""
    with open(path, "w") as fh:
        fh.write(ccx_io.vtu(f["points"], f["elements"], {"von_Mises_MPa": f["vonMises"], "displacement_mm": f["displacement"]}))


def write_csv(path, f):
    """A solve's kept field written as a CSV: every node's position, von Mises stress and displacement."""
    with open(path, "w") as fh:
        fh.write("x,y,z,von_mises_MPa,ux,uy,uz\n")
        for p, vm, u in zip(f["points"], f["vonMises"], f["displacement"]):
            fh.write(f"{p[0]:.5f},{p[1]:.5f},{p[2]:.5f},{vm:.5f},{u[0]:.6g},{u[1]:.6g},{u[2]:.6g}\n")


class Probe:
    """The last solve's kept field read where asked: at a point (from the four
    nearest nodes, by inverse distance), along a line, over faces. msize is
    the solve's element size: the study's mesh (the session keeps body,
    study, result, field)."""

    def __init__(self, r):
        import numpy as np

        f = r["field"]
        self.np = np
        self.P = np.asarray(f["points"], float)
        self.VM = np.asarray(f["vonMises"], float)
        self.um = np.linalg.norm(np.asarray(f["displacement"], float), axis=1)
        m_ = (r.get("study") or {}).get("mesh") or ((r.get("result") or {}).get("mesh") or {}).get("size")
        self.msize = float(m_ or 1.0)

    def at(self, q):
        """von Mises and displacement at q, and how near the nearest node is."""
        np = self.np
        d = np.linalg.norm(self.P - np.asarray(q, float), axis=1)
        k = np.argsort(d)[:4]
        w = 1.0 / np.maximum(d[k], 1e-9)
        if d[k[0]] < 1e-6:
            w = (d[k] < 1e-6).astype(float)
        w = w / w.sum()
        return {"at": [round(float(c), 3) for c in q], "vonMisesMPa": round(float(self.VM[k] @ w), 3),
                "displacementMm": round(float(self.um[k] @ w), 5), "nearestNodeMm": round(float(d[k[0]]), 3)}

    def ends(self, ln):
        """A line's two ends as arrays."""
        return self.np.asarray(ln.get("from"), float), self.np.asarray(ln.get("to"), float)

    def along(self, p0, p1, n):
        """n samples from p0 to p1."""
        return [self.at(p0 + (p1 - p0) * i / (n - 1)) for i in range(n)]

    def on_faces(self, faces):
        """The nodes lying on the faces: how many, the largest and mean von
        Mises and displacement, and where the largest stress is; None when no
        node lies on them."""
        np, P, VM, um = self.np, self.P, self.VM, self.um
        tol = max(0.05, 0.02 * self.msize)
        on = np.zeros(len(P), bool)
        for fc in faces:
            bb = fc.BoundBox
            cand = np.where((P[:, 0] >= bb.XMin - tol) & (P[:, 0] <= bb.XMax + tol) & (P[:, 1] >= bb.YMin - tol) & (P[:, 1] <= bb.YMax + tol)
                            & (P[:, 2] >= bb.ZMin - tol) & (P[:, 2] <= bb.ZMax + tol))[0]
            for i in cand:
                if not on[i] and fc.distToShape(Part.Vertex(FreeCAD.Vector(*P[i])))[0] <= tol:
                    on[i] = True
        if not on.any():
            return None
        i_max = int(np.argmax(np.where(on, VM, -1)))
        return {"nodes": int(on.sum()), "vm_max": float(VM[on].max()), "vm_mean": float(VM[on].mean()), "max_at": [float(c) for c in P[i_max]],
                "u_max": float(um[on].max()), "u_mean": float(um[on].mean())}


def field_values(r, field):
    """The kept field's values over every node: von Mises, or the size of the displacement."""
    import numpy as np

    f = r["field"]
    return np.asarray(f["vonMises"], float) if field == "vonMises" else np.linalg.norm(np.asarray(f["displacement"], float), axis=1)


def histogram(vals, bins):
    """Values counted into bins: counts, the bins' edges, and the least,
    median, 95th and 99th percentile and largest."""
    import numpy as np

    counts, edges = np.histogram(vals, bins=bins)
    pct = np.percentile(vals, [50, 95, 99]) if len(vals) else [0, 0, 0]
    return {"counts": [int(c) for c in counts], "edges": [float(e) for e in edges], "min": float(vals.min()), "max": float(vals.max()),
            "median": float(pct[0]), "p95": float(pct[1]), "p99": float(pct[2])}


def distance(p, q):
    """How far two points are apart."""
    import numpy as np

    return float(np.linalg.norm(np.asarray(p, float) - np.asarray(q, float)))


def write_text(path, text):
    """A text file written (UTF-8)."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def tools(session):
    """The strength tools are data (agentlink/data/tools.json, group "strength"): the
    solver runs, the result reading and the FreeCAD FEM objects their entries call
    by name are here (docs/data-tools.md). FEA here is a feasibility check, never a sign-off."""
    s = session
    try:
        from .. import health

        health.register("strength", _health)
    except Exception:
        pass

    TYPICAL_ALPHA = {"pla": 68e-6, "petg": 60e-6, "abs": 90e-6, "asa": 95e-6, "nylon": 110e-6, "pa": 110e-6, "tpu": 150e-6, "pc": 68e-6,
                     "steel": 12e-6, "stainless": 16e-6, "aluminium": 23e-6, "aluminum": 23e-6, "brass": 19e-6, "copper": 17e-6, "titanium": 8.6e-6}

    def _alpha(st, ld):
        """A temperature load's expansion coefficient, 1/K: the load's own,
        the material card's, else a typical one by the material's name; None
        when there is none."""
        if ld.get("alpha") is not None:
            return float(ld["alpha"])
        c = matfam.card(s.doc, st["material"]) or {}
        for k in ("alpha", "cte", "ThermalExpansionCoefficient", "expansion"):
            v = c.get(k)
            if v:
                try:
                    v = float(str(v).split()[0])
                    return v * 1e-6 if v > 1e-3 else v  # µm/m·K given as a whole number
                except ValueError:
                    pass
        key = str(st["material"]).lower()
        return next((v for k, v in TYPICAL_ALPHA.items() if k in key), None)

    def _thermal(st, nodes):
        """The study's temperature loads as the deck takes them (alpha, the
        summed change, every node), or None."""
        lds = [ld for ld in st["loads"] if ld["kind"] == "temperature"]
        if not lds:
            return None
        return {"alpha": _alpha(st, lds[-1]), "delta": sum(ld["delta"] for ld in lds), "nodes": list(nodes.keys()) if isinstance(nodes, dict) else list(range(1, len(nodes) + 1))}

    def _meshed(o, st, timeout, tag="fea"):
        """(ccx binary, work folder, femmesh, mesh deck text, nodes, elements)
        for a body: Gmsh's second-order tetrahedra read into FemMesh."""
        ccx = _binary("ccx", "Ccx", "ccxBinaryPath", "AGENTLINK_CCX")
        gmsh = _binary("gmsh", "Gmsh", "gmshBinaryPath", "AGENTLINK_GMSH")
        missing = [n for n, b in (("CalculiX (ccx)", ccx), ("Gmsh", gmsh)) if not b]
        if missing:
            raise ToolError("unavailable", f"{' and '.join(missing)} not found: install them (conda install -c conda-forge calculix gmsh; or your system's packages), or set the paths in FreeCAD's FEM preferences or AGENTLINK_CCX / AGENTLINK_GMSH.")
        try:
            import Fem
        except ImportError:
            raise ToolError("unavailable", "FreeCAD's FEM module is not in this build: a FreeCAD with FEM is needed for the solve.")
        shape = o.Shape
        wd = paths.made(s, os.path.join(s.out_dir, tag + "_" + "".join(ch if ch.isalnum() else "_" for ch in o.Label)), "run")
        os.makedirs(wd, exist_ok=True)
        for n in os.listdir(wd):
            if n.startswith("job.") or n.startswith("part."):
                os.remove(os.path.join(wd, n))

        # The mesh: Gmsh on the body as BREP, second order, nodes on the geometry.
        brep = os.path.join(wd, "part.brep")
        shape.exportBrep(brep)
        mesh = float(st["mesh"])
        # Finer near the faces fea_refine named: a distance field from them,
        # the size growing back to the study's over three element lengths.
        fields = []
        for k, rg in enumerate(st.get("refine") or []):
            ids = [int(n[4:]) for n, _ in facepick.pick(shape, rg["faces"], "faces")]
            d, th = 2 * k + 1, 2 * k + 2
            fields += [f"Field[{d}] = Distance;", f"Field[{d}].SurfacesList = {{{', '.join(map(str, ids))}}};", f"Field[{d}].Sampling = 40;",
                       f"Field[{th}] = Threshold;", f"Field[{th}].InField = {d};", f"Field[{th}].SizeMin = {float(rg['size'])};",
                       f"Field[{th}].SizeMax = {mesh};", f"Field[{th}].DistMin = 0;", f"Field[{th}].DistMax = {3 * mesh};"]
        if fields:
            n = len(st["refine"])
            fields += [f"Field[{2 * n + 1}] = Min;", f"Field[{2 * n + 1}].FieldsList = {{{', '.join(str(2 * k + 2) for k in range(n))}}};", f"Background Field = {2 * n + 1};",
                       "Mesh.MeshSizeExtendFromBoundary = 0;"]
        geo_txt = "\n".join([
            'Merge "part.brep";'] + fields + [
            f"Mesh.MeshSizeMax = {mesh};",
            "Mesh.MeshSizeMin = 0;",
            "Mesh.MeshSizeFromCurvature = 12;",
            "Mesh.MeshSizeFromPoints = 0;",
            "Mesh.ElementOrder = 2;",
            "Mesh.SecondOrderLinear = 0;",
            "Mesh.Algorithm = 2;",
            "Mesh.Algorithm3D = 1;",
            "Mesh.Optimize = 1;",
            "Mesh.HighOrderOptimize = 0;",
            "Mesh 3;",
            "Mesh.SaveAll = 1;",
            'Save "part.unv";',
            "",
        ])
        with open(os.path.join(wd, "part.geo"), "w") as f:
            f.write(geo_txt)
        try:
            r = subprocess.run([gmsh, "-", "part.geo"], cwd=wd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ToolError("failed", f"Gmsh took over {timeout:g} s: a coarser mesh (fea_setup {{ mesh }}) or a longer timeout.")
        unv = os.path.join(wd, "part.unv")
        if r.returncode != 0 or not os.path.isfile(unv):
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
            raise ToolError("failed", f"Gmsh could not mesh {o.Label}: {' | '.join(tail)} — body_check it, or try another mesh size.")
        femmesh = Fem.read(unv)
        if femmesh.VolumeCount == 0:
            raise ToolError("failed", "Gmsh made no volume elements: the body may not be a closed solid — body_check it.")
        mesh_inp = os.path.join(wd, "part.inp")
        femmesh.writeABAQUS(mesh_inp, 1, False)
        with open(mesh_inp) as f:
            mesh_text = f.read()
        nodes, elems = ccx_io.read_mesh(mesh_text)
        if not elems:
            raise ToolError("failed", "The mesh has no ten-node tetrahedra: this solve needs them.")
        return ccx, wd, femmesh, mesh_text, nodes, elems

    def _assemble(st, shape, femmesh, nodes, elems):
        """The study's holds and loads on the mesh: (fixed nodes, held face
        names, nodal loads, face pressures, gravity, what was applied)."""
        def resolve(q):
            """The faces a query picks on the shape."""
            return facepick.pick(shape, q, "faces")

        fixed = set()
        held_faces = set()
        bounds = {}
        for h in st["holds"]:
            for name, f in resolve(h["faces"]):
                held_faces.add(name)
                ns = femmesh.getNodesByFace(f)
                if h.get("kind", "fixed") == "fixed":
                    fixed.update(ns)
                else:
                    for d, v in zip(h["dofs"], h["values"]):
                        for n in ns:
                            bounds[(n, d)] = v
        bounds = [(n, d, v) for (n, d), v in bounds.items() if n not in fixed]
        if len(fixed) + len({n for n, _, _ in bounds}) < 3:
            raise ToolError("failed", "The held faces hold fewer than 3 mesh nodes: pick bigger faces or a finer mesh.")
        st["_bounds"] = bounds
        cloads, dloads, gravity = {}, [], None
        st["_centrif"] = []
        applied = []
        for ld in st["loads"]:
            if ld["kind"] == "temperature":
                applied.append({"temperature": ld["delta"]})
                continue
            if ld["kind"] == "spin":
                st["_centrif"].append(ld["spin"])
                applied.append({"spin": ld["spin"]})
                continue
            if ld["kind"] == "gravity":
                g = ld["gravity"]
                gravity = [x * G for x in g] if gravity is None else [gravity[i] + g[i] * G for i in range(3)]
                applied.append({"gravity": g})
                continue
            picked = resolve(ld["faces"])
            vf = []
            for _, f in picked:
                vf += [tuple(x) for x in femmesh.getccxVolumesByFace(f)]
            if not vf:
                raise ToolError("failed", f"No element faces found on {[n for n, _ in picked]}: try another mesh size.")
            if ld["kind"] == "pressure":
                dloads += [(e, fn, ld["pressure"]) for e, fn in vf]
                applied.append({"pressure": ld["pressure"], "faces": [n for n, _ in picked]})
            else:
                nl, area = ccx_io.nodal_loads(nodes, elems, vf, ld["force"])
                for n, fv in nl.items():
                    acc = cloads.setdefault(n, [0.0, 0.0, 0.0])
                    for k in range(3):
                        acc[k] += fv[k]
                applied.append({"force": ld["force"], "faces": [n for n, _ in picked], "area": round(area, 2)})
        return fixed, held_faces, cloads, dloads, gravity, applied

    def _parts_split(st, shape, femmesh, nodes, elems):
        """Elements per part (by their centre inside its solid) and the
        element faces where two parts touch."""
        sol = shape.Solids
        groups = [[] for _ in sol]
        for e, ns in elems.items():
            c = [sum(nodes[n][k] for n in ns[:4]) / 4.0 for k in range(3)]
            p = V(*c)
            hit = None
            for i, so in enumerate(sol):
                if so.BoundBox.isInside(p) and so.isInside(p, 1e-6, True):
                    hit = i
                    break
            if hit is None:
                hit = min(range(len(sol)), key=lambda i: sol[i].distToShape(Part.Vertex(p))[0])
            groups[hit].append(e)
        member = {}
        for i, g in enumerate(groups):
            for e in g:
                member[e] = i
        tol = float(st.get("tolerance", 0.05))
        pairs = []
        for i in range(len(sol)):
            for j in range(i + 1, len(sol)):
                if not sol[i].BoundBox.intersect(sol[j].BoundBox) and sol[i].distToShape(sol[j])[0] > tol:
                    continue
                sa, sb = [], []
                for fa in sol[i].Faces:
                    for fb in sol[j].Faces:
                        if not fa.BoundBox.intersect(fb.BoundBox) and fa.distToShape(fb)[0] > tol:
                            continue
                        try:
                            if fa.common(fb).Area <= 1e-3:
                                continue
                        except Exception:
                            continue
                        sa += [(e, f) for e, f in femmesh.getccxVolumesByFace(fa) if member.get(e) == i]
                        sb += [(e, f) for e, f in femmesh.getccxVolumesByFace(fb) if member.get(e) == j]
                if sa and sb:
                    pairs.append((i, j, sorted(set(sb)), sorted(set(sa))))  # slave on the second part
        return groups, pairs

    def _solve_fem(st, o, c, timeout):
        """_fem_build_and_run, and on its own failure what it made taken out
        again (the own deck then solves, and the document holds no
        half-built analysis)."""
        doc = s.doc
        before = {x.Name for x in doc.Objects}
        try:
            return _fem_build_and_run(st, o, c, timeout)
        except ToolError:
            raise
        except Exception:
            for x in [x for x in doc.Objects if x.Name not in before]:
                try:
                    doc.removeObject(x.Name)
                except Exception:
                    pass
            raise

    def _fem_build_and_run(st, o, c, timeout):
        """The study as FreeCAD's FEM analysis (replacing the one the last
        solve made), meshed by its Gmsh tools and solved by FemToolsCcx:
        (work folder, FemMesh, nodes, elements, displacements, stresses,
        the analysis's label)."""
        import ObjectsFem
        from femmesh import gmshtools
        from femtools import ccxtools

        ccx = _binary("ccx", "Ccx", "ccxBinaryPath", "AGENTLINK_CCX")
        if not ccx:
            raise ToolError("unavailable", "CalculiX (ccx) not found: install it (conda install -c conda-forge calculix; or your system's packages), or set its path in FreeCAD's FEM preferences or AGENTLINK_CCX.")
        doc = s.doc
        label = f"{o.Label} strength (fea_solve)"
        for old in [x for x in doc.Objects if x.Label == label and x.TypeId == "Fem::FemAnalysis"]:
            members = list(getattr(old, "Group", []) or [])
            # A result object's mesh (CCX_Results_Mesh) is linked from it, not
            # a member of the analysis: taken away with it, or one is left per solve.
            members += [m.Mesh for m in members if m.isDerivedFrom("Fem::FemResultObject") and getattr(m, "Mesh", None) is not None]
            # and a mesh's refinements (fem_add puts them on the mesh, not in the analysis)
            members += [r for m in members for k in ("MeshRegionList", "MeshGroupList", "MeshBoundaryLayerList") for r in (getattr(m, k, None) or [])]
            for m in members:
                try:
                    doc.removeObject(m.Name)
                except Exception:
                    pass
            doc.removeObject(old.Name)
        for old in [x for x in doc.Objects if x.Label.startswith(f"{o.Label} force direction")]:
            doc.removeObject(old.Name)
        an = ObjectsFem.makeAnalysis(doc, "Analysis")
        an.Label = label
        names = ("makeSolverCalculiXCcxTools", "makeSolverCalculixCcxTools", "makeSolverCcxTools", "makeSolverCalculiX", "makeSolverCalculix")
        mk = next((getattr(ObjectsFem, n) for n in names if hasattr(ObjectsFem, n)), None)
        if mk is None:
            raise RuntimeError("no CalculiX solver object in this FEM")
        solver = mk(doc)
        # Said outright, as FreeCAD's own examples do: a linear static step
        # whatever this FreeCAD's defaults or preferences are.
        for prop, val in (("AnalysisType", "static"), ("GeometricalNonlinearity", "linear")):
            if prop in solver.PropertiesList:
                setattr(solver, prop, val)
        an.addObject(solver)
        mo = ObjectsFem.makeMaterialSolid(doc, "Material")
        props = {"Name": c.get("name", st["material"]), "YoungsModulus": f"{float(c['E'])} MPa", "PoissonRatio": str(float(c.get("nu") or 0.35)),
                 "Density": f"{float(c['density']) * 1000} kg/m^3"}
        mo.Material = props
        # No References: the one material is every element's. With a
        # reference FreeCAD's prerequisite check prints an error line ("Only
        # one material object, but this one has a reference shape") at each solve.
        an.addObject(mo)
        mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
        if "Shape" in mesh.PropertiesList:
            mesh.Shape = o
        else:
            mesh.Part = o  # before FreeCAD 1.1
        mesh.CharacteristicLengthMax = f"{float(st['mesh'])} mm"
        mesh.ElementOrder = "2nd"
        an.addObject(mesh)
        shape = o.Shape
        for h in st["holds"]:
            fx = ObjectsFem.makeConstraintFixed(doc, "Fixed")
            fx.References = [(o, tuple(n for n, _ in facepick.pick(shape, h["faces"], "faces")))]
            an.addObject(fx)
        for ld in st["loads"]:
            if ld["kind"] == "pressure":
                pr = ObjectsFem.makeConstraintPressure(doc, "Pressure")
                pr.References = [(o, tuple(n for n, _ in facepick.pick(shape, ld["faces"], "faces")))]
                pr.Pressure = f"{float(ld['pressure'])} MPa"
                an.addObject(pr)
            elif ld["kind"] == "gravity":
                g = ObjectsFem.makeConstraintSelfWeight(doc, "SelfWeight")
                self_weight(g, ld["gravity"])
                an.addObject(g)
            else:
                fv = V(*ld["force"])
                ln = doc.addObject("Part::Line", "ForceDirection")
                ln.Label = f"{o.Label} force direction"
                d = V(fv)
                d.normalize()
                ln.X2, ln.Y2, ln.Z2 = d.x, d.y, d.z
                ln.Visibility = False
                fo = ObjectsFem.makeConstraintForce(doc, "Force")
                fo.References = [(o, tuple(n for n, _ in facepick.pick(shape, ld["faces"], "faces")))]
                fo.Force = f"{fv.Length} N"
                fo.Direction = (ln, ["Edge1"])
                an.addObject(fo)
        doc.recompute()
        err = gmsh_run(gmshtools.GmshTools(mesh), timeout)
        femmesh = mesh.FemMesh
        if not femmesh.VolumeCount:
            said = " | ".join([ln.strip() for ln in err.splitlines() if ln.strip()][-3:])[:600]
            raise ToolError("failed", f"Gmsh did not mesh {o.Label}: {said or 'no volume elements'} — body_check it (one closed solid), or another mesh size (fea_setup {{ mesh }}).")
        wd = paths.made(s, os.path.join(s.out_dir, "fea_" + "".join(ch if ch.isalnum() else "_" for ch in o.Label)), "run")
        os.makedirs(wd, exist_ok=True)
        fea = ccxtools.FemToolsCcx(an, solver)
        fea.update_objects()
        fea.setup_working_dir(wd)
        fea.setup_ccx(ccx)
        # ccx_run() calls setup_ccx() again with no argument, which looks in
        # FreeCAD's preference and the PATH only: the binary found here
        # (AGENTLINK_CCX too) is the one it runs.
        _setup = fea.setup_ccx
        fea.setup_ccx = lambda ccx_binary=None, ccx_binary_sig="CalculiX": _setup(ccx_binary or ccx, ccx_binary_sig)
        msg = fea.check_prerequisites()
        if msg:
            raise RuntimeError(f"its prerequisites: {msg.strip()}")
        fea.write_inp_file()
        rc = fea.ccx_run()
        # CalculiX's own lines for the shared health check, as the own deck keeps them.
        said = [getattr(fea, k, "") or "" for k in ("ccx_stdout", "ccx_stderr")]
        s._ccx_tail = last_lines("\n".join(v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v) for v in said)) or None
        frd = os.path.splitext(fea.inp_file_name)[0] + ".frd"
        disp = stress = None
        if os.path.isfile(frd):
            with open(frd) as f:
                disp, stress = ccx_io.read_frd(f.read())
        if not disp or not stress:
            # CalculiX's own words (FemToolsCcx keeps its output; else it is
            # run again here to read them), then Agent Link's own deck tries.
            tail = ccx_said(fea, ccx, timeout)
            s._ccx_fem_tail = tail
            raise RuntimeError(f"CalculiX (run by FreeCAD's FEM, exit {rc}) wrote no displacements or stresses" + (f" — it said: {tail}" if tail else "") + f" (files in {wd})")
        try:
            fea.load_results()
        except Exception:
            pass
        nodes = {int(n): (float(p.x), float(p.y), float(p.z)) for n, p in femmesh.Nodes.items()}
        # A ten-node tetrahedron's nodes in CalculiX's order, as FreeCAD's deck
        # writer puts them (FemMesh.cpp: 1, 0, 2, 3, 4, 6, 5, 8, 7, 9 of its own):
        # the face numbers of getccxVolumesByFace, the loaded area and the VTU
        # written from these all count in that order (in FreeCAD's own, a 1e6 mm²
        # face read 1045519 mm²).
        ccx_order = (1, 0, 2, 3, 4, 6, 5, 8, 7, 9)
        elems = {}
        for e in femmesh.Volumes:
            ns = tuple(femmesh.getElementNodes(e))
            elems[int(e)] = tuple(ns[i] for i in ccx_order) if len(ns) == 10 else ns
        # The verdict reads job.frd beside the deck, as the own route writes it.
        try:
            import shutil

            if os.path.abspath(frd) != os.path.join(os.path.abspath(wd), "job.frd"):
                shutil.copyfile(frd, os.path.join(wd, "job.frd"))
        except OSError:
            pass
        return wd, femmesh, nodes, elems, disp, stress, an.Label

    def _solve_own(st, o, c, a, timeout):
        """Agent Link's own deck and run (the cases FreeCAD's FEM route does
        not take here)."""
        shape = o.Shape
        ccx, wd, femmesh, mesh_text, nodes, elems = _meshed(o, st, timeout)
        fixed, held_faces, cloads, dloads, gravity, applied = _assemble(st, shape, femmesh, nodes, elems)
        mat = {"E": float(c["E"]), "nu": float(c.get("nu") or 0.35), "rho": float(c["density"])}
        text = ccx_io.deck(mesh_text, mat, fixed, cloads, dloads, gravity, thermal=_thermal(st, nodes), bounds=st.pop("_bounds", None), centrif=st.pop("_centrif", None))
        groups = pairs = None
        part_cards = []
        if st.get("parts"):
            groups, pairs = _parts_split(st, shape, femmesh, nodes, elems)
            defs = []
            for k, pinfo in enumerate(st["parts"]):
                pc = matfam.card(s.doc, pinfo["material"]) or c
                part_cards.append(pc)
                defs.append((f"P{k + 1}", groups[k], {"E": float(pc["E"]), "nu": float(pc.get("nu") or 0.35), "rho": float(pc.get("density") or c["density"]),
                                                     **({"alpha": _thermal(st, nodes)["alpha"]} if _thermal(st, nodes) else {})}))
            empty = [st["parts"][k]["body"] for k, g in enumerate(groups) if not g]
            if empty:
                raise ToolError("failed", f"No elements landed in {', '.join(empty)}: a finer mesh (fea_setup is not used here — fea_parts {{ mesh }}).")
            join = [(f"J{n + 1}", sl, ma) for n, (i, j, sl, ma) in enumerate(pairs)]
            Emin = min(float(pc["E"]) for pc in part_cards)
            text = ccx_io.parts_deck(text, defs, ties=join if st.get("join") == "tie" else (), contacts=join if st.get("join") == "contact" else (),
                                     contact_slope=Emin * 50, friction=st.get("friction", 0))
        nonlin = bool(a.get("nonlinear"))
        if nonlin:
            text = _nonlinear(text, {"PART": c} if not st.get("parts") else {f"MP{k + 1}": pc for k, pc in enumerate(part_cards)}, a)
        with open(os.path.join(wd, "job.inp"), "w") as f:
            f.write(text)
        env = dict(os.environ)
        env.setdefault("OMP_NUM_THREADS", str(max(1, min(4, os.cpu_count() or 1))))
        try:
            r = subprocess.run([ccx, "-i", "job"], cwd=wd, capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            raise ToolError("failed", f"CalculiX took over {timeout:g} s: a coarser mesh or a longer timeout.")
        frd = os.path.join(wd, "job.frd")
        log = (r.stdout or "") + (r.stderr or "")
        s._ccx_tail = last_lines(log)
        if "*ERROR" in log or not os.path.isfile(frd):
            err = [l.strip() for l in log.splitlines() if "ERROR" in l][:2] or log.strip().splitlines()[-2:]
            hint = ccx_hint(log)
            if nonlin and any("increment size smaller" in l.lower() for l in log.splitlines()):
                hint += (" It stopped finding equilibrium as the load rose: past its strength the part gives way (it would collapse or break) — "
                         "less load, a stronger material or a larger section; or contact that never closes.")
            raise ToolError("failed", f"CalculiX refused the job: {' | '.join(err)}.{hint}")
        with open(frd) as f:
            disp, stress = ccx_io.read_frd(f.read())
        return wd, femmesh, nodes, elems, disp, stress, fixed, held_faces, applied, groups, pairs, part_cards, frd


    def _where(nodes, shape, n):
        """Where a node is: its place, and the face of the shape nearest to it."""
        p = nodes.get(n, (0, 0, 0))
        vx = Part.Vertex(V(*p))
        best = min(((vx.distToShape(f)[0], i) for i, f in enumerate(shape.Faces)), default=(0, 0))
        return {"at": [round(p[0], 2), round(p[1], 2), round(p[2], 2)], "face": f"Face{best[1] + 1}"}

    def _run(ccx, wd, timeout, what):
        """CalculiX run on job.inp in a folder, bounded: (job.frd, job.dat) as
        text. A run over the time or one CalculiX refuses is refused here,
        with its own error lines."""
        env = dict(os.environ)
        env.setdefault("OMP_NUM_THREADS", str(max(1, min(4, os.cpu_count() or 1))))
        try:
            r = subprocess.run([ccx, "-i", "job"], cwd=wd, capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            raise ToolError("failed", f"CalculiX took over {timeout:g} s: a coarser mesh or a longer timeout.")
        log = (r.stdout or "") + (r.stderr or "")
        if "*ERROR" in log or not os.path.isfile(os.path.join(wd, "job.frd")):
            err = [l.strip() for l in log.splitlines() if "ERROR" in l][:2] or log.strip().splitlines()[-2:]
            raise ToolError("failed", f"CalculiX refused the {what}: {' | '.join(err)}.{ccx_hint(log)}")
        with open(os.path.join(wd, "job.frd")) as f:
            frd = f.read()
        dat = ""
        if os.path.isfile(os.path.join(wd, "job.dat")):
            with open(os.path.join(wd, "job.dat")) as f:
                dat = f.read()
        return frd, dat

    # ---- FreeCAD's own FEM objects (fea_native) ----

    def _analysis(doc, a, o):
        """A new FEM analysis, under the name given or "<body> analysis" (a label no other has)."""
        an = ObjectsFem_().makeAnalysis(doc, "Analysis")
        an.Label = s.unique(a.get("name") or f"{o.Label} analysis")
        return an

    def _elmer_conditions(doc, an, o, shape, a, eqs):
        """Elmer's own boundary conditions: temperatures and heat for heat,
        potentials for electrostatics (the study's holds and loads serve
        elasticity as they are)."""
        made = []

        def refs(q, where):
            """A face query as a FEM object's References."""
            return [(o, tuple(n for n, _ in facepick.pick(shape, q, where)))]

        for i, tq in enumerate(a.get("temperatures") or []):
            if "heat" not in eqs:
                raise ToolError("invalid_input", "temperatures need the heat equation: equations [..., heat].")
            tc = ObjectsFem_().makeConstraintTemperature(doc, "Temperature")
            tc.References = refs(tq.get("faces"), f"temperatures.{i}.faces")
            _setq(tc, "Temperature", f"{273.15 + float(tq['celsius'])} K", 273.15 + float(tq["celsius"]))
            an.addObject(tc)
            made.append(tc.Label)
        for i, hq in enumerate(a.get("heat") or []):
            if "heat" not in eqs:
                raise ToolError("invalid_input", "heat needs the heat equation: equations [..., heat].")
            picked = facepick.pick(shape, hq.get("faces"), f"heat.{i}.faces")
            area = sum(f.Area for _, f in picked) * 1e-6
            hf = ObjectsFem_().makeConstraintHeatflux(doc, "Heatflux")
            hf.References = [(o, tuple(n for n, _ in picked))]
            # "DFlux" in FreeCAD 1.0, "Flux" later
            kinds = hf.getEnumerationsOfProperty("ConstraintType") or []
            hf.ConstraintType = next((k for k in ("DFlux", "Flux") if k in kinds), "DFlux")
            flux = "DFlux" if "DFlux" in hf.PropertiesList else "DistributedHeatFlux"
            _setq(hf, flux, f"{float(hq['watts']) / area} W/m^2", float(hq["watts"]) / area)
            an.addObject(hf)
            made.append(hf.Label)
        for i, pq in enumerate(a.get("potentials") or []):
            if "electrostatic" not in eqs:
                raise ToolError("invalid_input", "potentials need the electrostatic equation: equations [..., electrostatic].")
            ep = ObjectsFem_().makeConstraintElectrostaticPotential(doc, "Potential")
            ep.References = refs(pq.get("faces"), f"potentials.{i}.faces")
            _setq(ep, "Potential", f"{float(pq['volts'])} V", float(pq["volts"]))
            for flag in ("PotentialEnabled", "EnablePotential"):
                if hasattr(ep, flag):
                    setattr(ep, flag, True)
            an.addObject(ep)
            made.append(ep.Label)
        return made

    def _elmer_write(o, mesh, solver, run, timeout):
        """Mesh by Gmsh, write Elmer's case (case.sif, mesh.unv) into a folder;
        ElmerGrid turns the mesh into Elmer's, and ElmerSolver solves — each
        only when installed."""
        if not _binary("gmsh", "Gmsh", "gmshBinaryPath", "AGENTLINK_GMSH"):
            raise ToolError("unavailable", "Gmsh not found: the case needs a mesh (conda install -c conda-forge gmsh, or FreeCAD's FEM preferences).")
        from femmesh import gmshtools
        wd = paths.made(s, os.path.join(s.out_dir, "elmer_" + "".join(ch if ch.isalnum() else "_" for ch in o.Label)), "run")
        os.makedirs(wd, exist_ok=True)
        err = gmshtools.GmshTools(mesh).create_mesh()
        if err or not mesh.FemMesh.NodeCount:
            raise ToolError("failed", f"Gmsh did not mesh it: {err or 'no nodes'}")
        from femsolver.elmer import writer as ew
        if hasattr(solver, "WorkingDirectory"):
            solver.WorkingDirectory = wd
        try:
            w = ew.Writer(solver, wd, testmode=True)
            (getattr(w, "write_solver_input", None) or getattr(w, "write"))()
        except Exception as e:
            raise ToolError("invalid_state", f"Elmer's writer refused the case: {e}")
        unv = os.path.join(wd, "mesh.unv")
        mesh.FemMesh.write(unv)
        out = {"files": wd, "mesh": {"nodes": mesh.FemMesh.NodeCount, "volumes": mesh.FemMesh.VolumeCount}, "solved": False}
        grid = _binary("ElmerGrid", "Elmer", "gridBinaryPath", "AGENTLINK_ELMERGRID")
        elmer = _binary("ElmerSolver", "Elmer", "elmerBinaryPath", "AGENTLINK_ELMER")
        if not grid:
            out["note"] = "ElmerGrid not found: the case is written (case.sif, mesh.unv); turn the mesh into Elmer's with ElmerGrid 8 2 mesh.unv -out . where Elmer is installed."
            return out
        r = subprocess.run([grid, "8", "2", unv, "-out", wd, "-autoclean"], cwd=wd, capture_output=True, text=True, timeout=timeout)
        if r.returncode:
            raise ToolError("failed", "ElmerGrid refused the mesh: " + (r.stderr or r.stdout)[-400:])
        if not run:
            return out
        if not elmer:
            out["note"] = "ElmerSolver not found: the case is ready to solve where Elmer is installed (ElmerSolver in the folder)."
            return out
        r = subprocess.run([elmer, "case.sif"], cwd=wd, capture_output=True, text=True, timeout=timeout)
        log = (r.stdout or "") + (r.stderr or "")
        with open(os.path.join(wd, "elmer.log"), "w") as f:
            f.write(log)
        bad = [l.strip() for l in log.splitlines() if "ERROR" in l and "::" in l]
        if r.returncode or bad:
            raise ToolError("failed", "ElmerSolver stopped: " + (" | ".join(bad[-3:]) or log[-400:]) + f" (log: {wd}/elmer.log)")
        out["solved"] = True
        out["results"] = sorted(os.path.relpath(os.path.join(dp, n), wd) for dp, _, ns in os.walk(wd) for n in ns if n.endswith((".vtu", ".pvtu", ".pvd", ".dat")))
        out["note"] = "Solved: open the .vtu in ParaView, or in the FEM workbench (the Elmer solver's results)."
        return out

    # ---- what the tools' entries (agentlink/data/tools.json, group "strength") call by name ----

    def study_body(st):
        """The study's body as it is now. One solid of a body studied alone
        is read again from that body (its hidden helper made or refreshed)."""
        of = st.get("of")
        if of:
            return solid_holder(s, s.body(of["body"]), int(of["solid"]))
        return s.body(st["body"])

    def forget():
        """The study dropped from the document, its results from the session."""
        store.remove(s.doc, KEY)
        s._agentlink_fea = None
        from .. import hooks

        hooks.remember(s, "fea", None)

    def meshed(o, st, timeout, tag="fea"):
        """A body meshed for Agent Link's own deck (_meshed), by name: ccx,
        wd, femmesh, mesh_text, nodes, elems."""
        return dict(zip(("ccx", "wd", "femmesh", "mesh_text", "nodes", "elems"), _meshed(o, st, timeout, tag)))

    def modes_run(o, st, c, count, timeout):
        """The frequency step run: the body meshed, held by the study's holds
        (none: free, six more modes asked for its rigid motions), CalculiX
        run, its frequencies and mode shapes read."""
        shape = o.Shape
        ccx, wd, femmesh, mesh_text, nodes, elems = _meshed(o, st, timeout, "modes")
        fixed = set()
        mbounds = set()
        for h in st["holds"]:
            for _, f in facepick.pick(shape, h["faces"], "faces"):
                if h.get("kind", "fixed") == "fixed":
                    fixed.update(femmesh.getNodesByFace(f))
                else:
                    mbounds.update((n, d, 0.0) for n in femmesh.getNodesByFace(f) for d in h["dofs"])
        mbounds = [b for b in mbounds if b[0] not in fixed]
        free = not fixed and not mbounds
        # A free part's first six modes are its rigid motions, near 0 Hz.
        ask = count + (6 if free else 0)
        mat = {"E": float(c["E"]), "nu": float(c.get("nu") or 0.35), "rho": float(c["density"])}
        with open(os.path.join(wd, "job.inp"), "w") as f:
            f.write(ccx_io.deck_modes(mesh_text, mat, fixed, ask, bounds=mbounds))
        frd, dat = _run(ccx, wd, timeout, "frequency step")
        return {"wd": wd, "nodes": nodes, "elems": elems, "free": free, "freqs": ccx_io.read_frequencies(dat), "shapes": ccx_io.read_frd_blocks(frd, "DISP")}

    def mode_rows(run, shape, count):
        """Each mode's Hz, where it swings most and which way (a unit
        direction); a free part's six rigid motions left out."""
        nodes, shapes = run["nodes"], run["shapes"]
        modes = []
        for k, (no, hz) in enumerate(run["freqs"]):
            if run["free"] and k < 6:
                continue
            m = {"mode": len(modes) + 1, "hz": round(hz, 2)}
            if k < len(shapes) and shapes[k]:
                mag = {n: math.sqrt(sum(x * x for x in u[:3])) for n, u in shapes[k].items() if n in nodes}
                if mag:
                    n_max = max(mag, key=mag.get)
                    m["moves"] = _where(nodes, shape, n_max)
                    u = shapes[k][n_max][:3]
                    L = math.sqrt(sum(x * x for x in u)) or 1.0
                    m["moves"]["along"] = [round(x / L, 3) for x in u]
            modes.append(m)
            if len(modes) >= count:
                break
        return modes

    def buckle_run(o, st, c, count, timeout):
        """The buckling step run: the body meshed, the study's holds and loads
        put on the mesh, CalculiX run, its buckling factors read."""
        shape = o.Shape
        ccx, wd, femmesh, mesh_text, nodes, elems = _meshed(o, st, timeout, "buckle")
        fixed, held_faces, cloads, dloads, gravity, applied = _assemble(st, shape, femmesh, nodes, elems)
        mat = {"E": float(c["E"]), "nu": float(c.get("nu") or 0.35), "rho": float(c["density"])}
        with open(os.path.join(wd, "job.inp"), "w") as f:
            f.write(ccx_io.deck(mesh_text, mat, fixed, cloads, dloads, gravity, buckle=count, thermal=_thermal(st, nodes), bounds=st.pop("_bounds", None), centrif=st.pop("_centrif", None)))
        frd, dat = _run(ccx, wd, timeout, "buckling step")
        return {"wd": wd, "nodes": nodes, "applied": applied, "frd": frd, "factors": ccx_io.read_buckling(dat)}

    def bulge_rows(run, shape):
        """Each buckling mode's factor and where it bulges most."""
        nodes = run["nodes"]
        shapes = ccx_io.read_frd_blocks(run["frd"], "DISP")
        modes = []
        for k, (no, fac) in enumerate(run["factors"]):
            m = {"mode": no, "factor": round(fac, 4)}
            if k < len(shapes) and shapes[k]:
                mag = {n: math.sqrt(sum(x * x for x in u[:3])) for n, u in shapes[k].items() if n in nodes}
                if mag:
                    m["bulges"] = _where(nodes, shape, max(mag, key=mag.get))
            modes.append(m)
        return modes

    def hold_temperature(m, picked, celsius, used, temps):
        """Faces held at a temperature: their nodes into temps, their names into used."""
        for name, f in picked:
            used.add(name)
            for n in m["femmesh"].getNodesByFace(f):
                temps[n] = celsius

    def heated(m, picked, used):
        """Faces heat goes in through: (their element faces, their area); their names into used."""
        vf = []
        for name, f in picked:
            used.add(name)
            vf += [tuple(x) for x in m["femmesh"].getccxVolumesByFace(f)]
        return vf, sum(f.Area for _, f in picked)

    def rest_faces(shape, used):
        """The faces no temperature or heat was given on: where still air takes heat away."""
        return [(n, f) for n, f in ((f"Face{i + 1}", f) for i, f in enumerate(shape.Faces)) if n not in used]

    def film_faces(m, on, hc, ta):
        """The element faces of faces air cools, each with the film coefficient and the air's temperature."""
        films = []
        for _, f in on:
            films += [(e, fn, hc, ta) for e, fn in (tuple(x) for x in m["femmesh"].getccxVolumesByFace(f))]
        return films

    def heat_solve(m, k, temps, fluxes, films, start, timeout):
        """The heat step run on the mesh: the deck written, CalculiX run, each node's temperature read."""
        with open(os.path.join(m["wd"], "job.inp"), "w") as f:
            f.write(ccx_io.deck_heat(m["mesh_text"], k, temps, fluxes, films, start=start))
        frd, _ = _run(m["ccx"], m["wd"], timeout, "heat step")
        return {n: t for n, t in ccx_io.read_temperatures(frd).items() if n in m["nodes"]}

    def keep_heat(o, shape, T, nodes):
        """The temperatures kept with the session, the field for view_render map heat."""
        ids = list(T)
        s._agentlink_heat = {"body": o.Label, "stats": geo.stats(shape), "field": {"points": [nodes[n] for n in ids], "celsius": [T[n] for n in ids]}}

    def solved_body(r):
        """The body the last solve was of, as it is in the document now, or None."""
        o = s.doc.getObject(r.get("bodyName", "")) if r.get("bodyName") else None
        if o is None:
            o = next((x for x in s.doc.Objects if x.Label == r["body"]), None)
        return o

    def chart_svg(series, **kw):
        """An SVG chart (agentlink/charts.py)."""
        from .. import charts

        return charts.svg(series, **kw)

    # ---- fea_shell ----

    def shell_of(faces):
        """The faces as one shell (a single face as itself): the plate's mid-surface."""
        return Part.makeShell(faces) if len(faces) > 1 else faces[0]

    def shell_meshed(o, shell, mesh, gmsh, timeout):
        """The shell meshed by Gmsh into second-order triangles, in its own
        run folder: wd, ok (Gmsh ended well and wrote the mesh), said (its
        last two lines)."""
        wd = paths.made(s, os.path.join(s.out_dir, "shell_" + "".join(ch if ch.isalnum() else "_" for ch in o.Label)), "run")
        os.makedirs(wd, exist_ok=True)
        for n in os.listdir(wd):
            if n.startswith(("job.", "shell.")):
                os.remove(os.path.join(wd, n))
        shell.exportBrep(os.path.join(wd, "shell.brep"))
        with open(os.path.join(wd, "shell.geo"), "w") as f:
            f.write("\n".join(['Merge "shell.brep";', f"Mesh.MeshSizeMax = {mesh};", "Mesh.MeshSizeMin = 0;", "Mesh.ElementOrder = 2;", "Mesh.SecondOrderLinear = 0;",
                               "Mesh.Algorithm = 6;", "Mesh 2;", "Mesh.SaveAll = 1;", 'Save "shell.unv";', ""]))
        r = subprocess.run([gmsh, "-", "shell.geo"], cwd=wd, capture_output=True, text=True, timeout=timeout)
        return {"wd": wd, "ok": r.returncode == 0 and os.path.isfile(os.path.join(wd, "shell.unv")), "said": " | ".join((r.stderr or r.stdout or "").strip().splitlines()[-2:])}

    def shell_elements(m):
        """Gmsh's mesh read into a FemMesh and written as a deck's mesh, into
        m: fm, mesh_text, and the element type and set it holds (etype None
        when the deck names none)."""
        import re

        import Fem

        fm = Fem.read(os.path.join(m["wd"], "shell.unv"))
        inp = os.path.join(m["wd"], "shell.inp")
        fm.writeABAQUS(inp, 1, False)
        with open(inp) as f:
            mesh_text = f.read()
        hit = re.search(r"\*Element, TYPE=(\w+), ELSET=(\w+)", mesh_text, re.I)
        m.update(fm=fm, mesh_text=mesh_text, etype=hit.group(1).upper() if hit else None, eset=hit.group(2) if hit else None)
        return m

    def boundary_edges(shell):
        """The shell's free edges: an edge on one face only is on the boundary."""
        return [e for e in shell.Edges if sum(1 for f in shell.Faces for fe in f.Edges if fe.isSame(e)) <= 1]

    def nearest_edges(shell, queries):
        """The shell's edge nearest each { near: [x, y, z] }."""
        es = []
        for q in queries:
            p = V(*[float(x) for x in q["near"]])
            es.append(min(shell.Edges, key=lambda e: e.distToShape(Part.Vertex(p))[0]))
        return es

    def edge_nodes(m, edges):
        """The mesh nodes on the edges, in order."""
        ns = set()
        for e in edges:
            ns.update(m["fm"].getNodesByEdge(e))
        return sorted(ns)

    def shell_deck(m, c, th, bl, pressure, gravity):
        """The shell's deck written (job.inp): the mesh, the material, the
        section of that thickness, the held nodes, pressure and its own weight."""
        nu = float(c.get("nu") or 0.3)
        eset = m["eset"]
        lines = [m["mesh_text"].rstrip(), "*MATERIAL, NAME=SM", "*ELASTIC", f"{float(c['E']):.6g}, {nu:.6g}", "*DENSITY", f"{float(c.get('density') or 1) * 1e-9:.6g}",
                 f"*SHELL SECTION, ELSET={eset}, MATERIAL=SM", f"{th:.6g}", "*STEP", "*STATIC", "*BOUNDARY"] + bl
        dl = []
        if pressure:
            dl.append(f"{eset}, P, {float(pressure):.9g}")
        if gravity:
            dl.append(f"{eset}, GRAV, {G:.6g}, 0, 0, -1")
        lines += ["*DLOAD"] + dl + ["*NODE FILE", "U", "*EL FILE", "S", "*END STEP", ""]
        with open(os.path.join(m["wd"], "job.inp"), "w") as f:
            f.write("\n".join(lines))

    def shell_solve(m, ccx, timeout):
        """CalculiX run on the shell's deck: its displacements and stresses."""
        frd, _ = _run(ccx, m["wd"], timeout, "shell")
        disp, stress = ccx_io.read_frd(frd)
        return {"disp": disp, "stress": stress}

    def shell_peaks(res):
        """(the largest deflection, the largest von Mises stress) of a shell's results."""
        dmax = max(math.sqrt(sum(x * x for x in u[:3])) for u in res["disp"].values())
        return dmax, max((ccx_io.von_mises(sv) for sv in res["stress"].values()), default=0.0)

    # ---- fea_parts ----

    def parts_holder(objs, name):
        """The parts' solids kept apart in one compound, on the hidden object
        of that name (found, or made under a label no other has): (holder, compound)."""
        comp = Part.makeCompound([o.Shape.Solids[0].copy() for o in objs])
        holder = next((x for x in s.doc.Objects if x.Label == name), None)
        if holder is None:
            holder = s.doc.addObject("Part::Feature", "FeaParts")
            holder.Label = s.unique(name, holder)
        holder.Shape = comp
        mark_helper(holder)
        s.doc.recompute()
        return holder, comp

    def touching(comp, tol):
        """Where the parts touch: faces of two parts that lie on each other
        within tol, as [{a, b (their numbers from 0), area}]."""
        found = []
        sol = comp.Solids
        for i in range(len(sol)):
            for j in range(i + 1, len(sol)):
                if sol[i].BoundBox.intersect(sol[j].BoundBox) or sol[i].distToShape(sol[j])[0] <= tol:
                    for fa in sol[i].Faces:
                        for fb in sol[j].Faces:
                            if not fa.BoundBox.intersect(fb.BoundBox) and fa.distToShape(fb)[0] > tol:
                                continue
                            try:
                                ar = fa.common(fb).Area
                            except Exception:
                                ar = 0.0
                            if ar > 1e-3:
                                found.append({"a": i, "b": j, "area": round(ar, 2)})
        return found

    def overlapping(comp):
        """The pairs of parts (their numbers from 0) whose volumes cross."""
        sol = comp.Solids
        return [(i, j) for i in range(len(sol)) for j in range(i + 1, len(sol)) if sol[i].common(sol[j]).Volume > 1e-3]

    # ---- fea_native ----

    def native_material(F, an, st, c, fluid):
        """The analysis's material object: a fluid's (air, water) where flow
        is asked, else the study's card as FreeCAD's solid material (cards
        keep g/cm³: FreeCAD's material wants kg/m³). No References: one
        material is every element's, for CalculiX and Elmer alike (a
        reference makes FreeCAD's check print an error line)."""
        doc = s.doc
        if fluid:
            mo = F.makeMaterialFluid(doc, "Fluid")
            mo.Material = dict(FLUIDS[fluid])
            an.addObject(mo)
            return mo.Label
        mo = F.makeMaterialSolid(doc, "Material")
        props = {"Name": c.get("name", st["material"])}
        if c.get("E"):
            props["YoungsModulus"] = f"{float(c['E'])} MPa"
        if c.get("nu"):
            props["PoissonRatio"] = str(float(c["nu"]))
        if c.get("density"):
            props["Density"] = f"{float(c['density']) * 1000} kg/m^3"
        if c.get("k"):
            props["ThermalConductivity"] = f"{float(c['k'])} W/m/K"
        props["SpecificHeat"] = f"{float(c.get('cp', 1500))} J/kg/K"
        if c.get("alpha"):
            props["ThermalExpansionCoefficient"] = f"{float(c['alpha'])} 1/K"
        props["RelativePermittivity"] = str(float(c.get("permittivity", 1)))
        mo.Material = props
        an.addObject(mo)
        return mo.Label

    def native_mesh(F, an, o, st):
        """The analysis's Gmsh mesh object of the body, at the study's size, second order."""
        mesh = F.makeMeshGmsh(s.doc, "Mesh")
        if "Shape" in mesh.PropertiesList:
            mesh.Shape = o
        else:
            mesh.Part = o  # before FreeCAD 1.1
        mesh.CharacteristicLengthMax = f"{float(st['mesh'])} mm"
        try:
            mesh.ElementOrder = "2nd"
        except Exception:
            pass
        an.addObject(mesh)
        return mesh

    def face_refs(o, q):
        """A face query as a FEM object's References."""
        return [(o, tuple(n for n, _ in facepick.pick(o.Shape, q, "faces")))]

    def fixed_on(F, an, o, q):
        """A fixed constraint on the faces: its label."""
        fx = F.makeConstraintFixed(s.doc, "Fixed")
        fx.References = face_refs(o, q)
        an.addObject(fx)
        return fx.Label

    def pressure_on(F, an, o, ld):
        """A pressure constraint for a pressure load: its label."""
        pr = F.makeConstraintPressure(s.doc, "Pressure")
        pr.References = face_refs(o, ld["faces"])
        pr.Pressure = f"{float(ld['pressure'])} MPa"
        an.addObject(pr)
        return pr.Label

    def temperature_on(F, an, o, delta):
        """A temperature change as an initial temperature and a temperature on
        every face: their labels, or None where this FEM does not take them."""
        try:
            it = F.makeConstraintInitialTemperature(s.doc, "InitialTemperature")
            it.initialTemperature = "293.15 K"
            an.addObject(it)
            tc = F.makeConstraintTemperature(s.doc, "Temperature")
            tc.References = [(o, tuple(f"Face{i + 1}" for i in range(len(o.Shape.Faces))))]
            tc.Temperature = f"{293.15 + float(delta)} K"
            an.addObject(tc)
            return [it.Label, tc.Label]
        except Exception:
            return None

    def gravity_on(F, an, gravity):
        """A self-weight constraint for a gravity load: its label."""
        g = F.makeConstraintSelfWeight(s.doc, "SelfWeight")
        self_weight(g, gravity)
        an.addObject(g)
        return g.Label

    def force_on(F, an, o, ld):
        """A force constraint for a force load: (its label, whether its
        direction was set). A force's direction is a line in the model: one
        drawn for it, hidden."""
        doc = s.doc
        fv = V(*ld["force"])
        ln = doc.addObject("Part::Line", "ForceDirection")
        ln.X2, ln.Y2, ln.Z2 = fv.normalize().x, fv.y, fv.z
        ln.Visibility = False
        fo = F.makeConstraintForce(doc, "Force")
        fo.References = face_refs(o, ld["faces"])
        fo.Force = f"{V(*ld['force']).Length} N"
        ok = True
        try:
            fo.Direction = (ln, ["Edge1"])
        except Exception:
            ok = False
        an.addObject(fo)
        return fo.Label, ok

    # ---- fea_solve ----

    def reset_tails():
        """CalculiX's lines kept from the solve before, forgotten."""
        s._ccx_tail = s._ccx_fem_tail = None

    def solve_run(st, o, c, a, timeout):
        """The study solved. FreeCAD's own FEM first: an analysis with its
        CalculiX solver, Gmsh mesh, material and constraints, solved by
        FemToolsCcx and its results loaded into the analysis. Agent Link's
        own deck only for what that route does not take here
        (fem_route_why), or where it fails. By name: fem (which route),
        an_label, route_why, wd, nodes, elems, disp, stress, fixed,
        held_faces, applied, groups, pairs, part_cards, frd, said
        (CalculiX's last lines)."""
        shape = o.Shape
        groups = pairs = None
        part_cards = []
        an_label = None
        route_why = fem_route_why(st, a)
        fem = None
        if route_why is None:
            try:
                fem = _solve_fem(st, o, c, timeout)
            except ToolError:
                raise
            except Exception as e:  # noqa: BLE001 - its own failure: the deck below runs, and the answer says why
                route_why = f"FreeCAD's FEM route failed here: {type(e).__name__}: {e}{failed_at(e)}"
        if fem is not None:
            wd, femmesh, nodes, elems, disp, stress, an_label = fem
            fixed, held_faces, _cl, _dl, _gr, applied = _assemble(st, shape, femmesh, nodes, elems)
            st.pop("_bounds", None)
            st.pop("_centrif", None)
            frd = os.path.join(wd, "job.frd")
        else:
            wd, femmesh, nodes, elems, disp, stress, fixed, held_faces, applied, groups, pairs, part_cards, frd = _solve_own(st, o, c, a, timeout)
        said = getattr(s, "_ccx_tail", None) if fem is None else getattr(s, "_ccx_fem_tail", None)
        return {"fem": fem is not None, "an_label": an_label, "route_why": route_why, "wd": wd, "nodes": nodes, "elems": elems, "disp": disp, "stress": stress, "fixed": fixed,
                "held_faces": held_faces, "applied": applied, "groups": groups, "pairs": pairs, "part_cards": part_cards, "frd": frd, "said": said}

    def peaks(run, shape):
        """The results read: each node's von Mises stress and displacement
        (kept in run as vm, dmag), the largest of each, the node it is at
        and where that is."""
        nodes = run["nodes"]
        vm = {n: ccx_io.von_mises(sv) for n, sv in run["stress"].items()}
        n_max = max(vm, key=vm.get)
        dmag = {n: math.sqrt(sum(x * x for x in u[:3])) for n, u in run["disp"].items()}
        n_dmax = max(dmag, key=dmag.get)
        run.update(vm=vm, dmag=dmag)
        return {"smax": vm[n_max], "n_max": n_max, "dmax": dmag[n_dmax], "at_max": _where(nodes, shape, n_max), "at_dmax": _where(nodes, shape, n_dmax)}

    def plastic_strain(frd):
        """The largest equivalent plastic strain of a nonlinear run's last
        increment (0.0 with none written), or None when it cannot be read."""
        try:
            pe = ccx_io.read_frd_blocks(open(frd).read(), "PE")
            return max((v[0] for v in pe[-1].values()), default=0.0) if pe else 0.0
        except Exception:
            return None

    def part_rows(run, st, shape):
        """Each part's own peak (several parts solved together): its body,
        material, largest von Mises stress, where, and its safety factor."""
        vm, elems, groups, part_cards = run["vm"], run["elems"], run["groups"], run["part_cards"]
        rows = []
        for k, pinfo in enumerate(st["parts"]):
            ns = {n for e in groups[k] for n in elems[e]}
            pv = {n: vm[n] for n in ns if n in vm}
            if not pv:
                continue
            nm = max(pv, key=pv.get)
            yk = part_cards[k].get("yield")
            rows.append({"body": pinfo["body"], "material": part_cards[k]["name"], "vonMisesMaxMPa": round(pv[nm], 3), **_where(run["nodes"], shape, nm),
                         **({"safety": round(yk / pv[nm], 2)} if yk and pv[nm] > 0 else {})})
        return rows

    def keep_solve(o, shape, st, out, run):
        """Every node's stress and displacement, for a map of the part
        (view_render map stress): kept with the session, not the file."""
        nodes, vm, disp, stress, elems = run["nodes"], run["vm"], run["disp"], run["stress"], run["elems"]
        ids = [n for n in vm if n in nodes]
        field = {"points": [nodes[n] for n in ids], "vonMises": [vm[n] for n in ids], "displacement": [list(disp.get(n, (0, 0, 0))[:3]) for n in ids],
                 "stress": [list(stress.get(n, (0.0,) * 6)) for n in ids]}
        at = {n: i for i, n in enumerate(ids)}
        field["elements"] = [[at[n] for n in e] for e in elems.values() if all(n in at for n in e)]
        s._agentlink_fea = {"body": o.Label, "stats": geo.stats(shape), "study": st, "result": out, "field": field}
        from .. import hooks

        hooks.remember(s, "fea", s._agentlink_fea)

    # FreeCAD's own and the other modules' are reached when called, not here.
    helpers = {"binaries": lambda: (_binary("ccx", "Ccx", "ccxBinaryPath", "AGENTLINK_CCX"), _binary("gmsh", "Gmsh", "gmshBinaryPath", "AGENTLINK_GMSH")),
               "fem_module": lambda: __import__("Fem"), "shaped": lambda ref, what="body": picks.shaped(s.doc, ref, what), "element": picks.element,
               "shell_of": shell_of, "shell_meshed": shell_meshed, "shell_elements": shell_elements, "boundary_edges": boundary_edges, "nearest_edges": nearest_edges,
               "edge_nodes": edge_nodes, "shell_deck": shell_deck, "shell_solve": shell_solve, "shell_peaks": shell_peaks,
               "parts_holder": parts_holder, "touching": touching, "overlapping": overlapping,
               "doc": lambda: s.doc, "objects_fem": objects_fem, "ELMER_EQUATIONS": ELMER_EQUATIONS, "FLUIDS": FLUIDS, "new_analysis": lambda a, o: _analysis(s.doc, a, o),
               "solver_makers": lambda F: [n for n in dir(F) if n.startswith("makeSolver")], "native_material": native_material, "native_mesh": native_mesh, "fixed_on": fixed_on,
               "pressure_on": pressure_on, "temperature_on": temperature_on, "gravity_on": gravity_on, "force_on": force_on,
               "elmer_conditions": lambda an, o, a, eqs: _elmer_conditions(s.doc, an, o, o.Shape, a, eqs), "elmer_write": _elmer_write,
               "reset_tails": reset_tails, "unheld_solids": _unheld_solids, "unheld_words": unheld_words, "ccx_hint": ccx_hint, "solve_run": solve_run, "peaks": peaks,
               "plastic_strain": plastic_strain, "part_rows": part_rows, "keep_solve": keep_solve,
               "now": lambda: time.time(), "merged": lambda *ds: {k: v for d in ds for k, v in d.items()}, "where": _where,
               "meshed": meshed, "modes_run": modes_run, "mode_rows": mode_rows, "buckle_run": buckle_run, "bulge_rows": bulge_rows,
               "hold_temperature": hold_temperature, "heated": heated, "rest_faces": rest_faces, "film_faces": film_faces, "heat_solve": heat_solve, "keep_heat": keep_heat,
               "probe": Probe, "solved_body": solved_body, "field_values": field_values, "histogram": histogram, "distance": distance, "chart_svg": chart_svg,
               "safe_name": lambda text: "".join(ch if ch.isalnum() else "_" for ch in text), "ensure_out": lambda: os.makedirs(s.out_dir, exist_ok=True),
               "csv_text": lambda rows: "\n".join(",".join(str(c) for c in row) for row in rows) + "\n", "write_text": write_text,
               "study": lambda: _study(s.doc), "save": lambda st: _save(s.doc, st), "study_body": study_body, "results": lambda: _results(s), "forget": forget,
               "snapshot": lambda tool: s.snapshot(tool), "body": lambda ref: s.body(ref), "stats": lambda shape: geo.stats(shape),
               "solid_holder": lambda src, n: solid_holder(s, src, n), "card": lambda mid: matfam.card(s.doc, mid), "of_body": lambda label: matfam.of_body(s.doc, label),
               "setup_said": _setup_said, "unmatched": lambda st, shape: unmatched(st, shape, facepick.pick),
               "pick": lambda shape, q, what="faces": facepick.pick(shape, q, what), "pick_both": lambda shape, q: _pick_report(shape, q, "faces"),
               "faces_normal": faces_normal, "same_in": _same_in, "alpha_of": _alpha, "vector": lambda xs: V(*[float(c) for c in xs]),
               "out_path": lambda name: os.path.join(s.out_dir, name), "made": lambda path, kind=None: paths.made(s, path, kind), "write_vtu": write_vtu, "write_csv": write_csv}
    return runners.tools(GROUP, s, helpers)

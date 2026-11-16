# SPDX-License-Identifier: LGPL-2.1-or-later
# More of FreeCAD's BIM workbench headless: frames (a library section along
# a path), trusses, fences, coverings (tiles, finishes), layered walls and
# slabs (multi-materials), IFC property sets and classification, quantity
# take-off by IFC type and material, an IFC preflight of the model, and
# component edits (additions, subtractions, plane cuts, joined walls, clones).

import FreeCAD
import Part

import Arch  # the family is left out without BIM

from .. import geometry as geo
from .. import runners
from . import picks
from .bim import contained, headless_call, ifc_set, ifc_type, is_bim, proxy_name, settype, shape, vec

# The tools themselves are data (agentlink/data/tools.json, "family":
# "bim_more"; run by agentlink/runners.py's steps runner). What is here is
# what their entries call by name (docs/data-tools.md).

GROUP = "bim"
INFO = "BIM extras: frames, trusses, fences, coverings, layered walls (multi-materials), IFC properties and classification, quantity take-off, IFC preflight, additions/subtractions/cuts/joins."

V = FreeCAD.Vector


def setsome(o, vals):
    done, skipped = {}, []
    for k, v in vals.items():
        if v is None:
            continue
        if hasattr(o, k):
            try:
                setattr(o, k, v)
                done[k] = v
            except Exception as e:
                skipped.append(f"{k}: {e}")
        else:
            skipped.append(f"{k}: not on this FreeCAD's {proxy_name(o)}")
    return done, skipped


def qty(v):
    return float(getattr(v, "Value", v) or 0)


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def finish(o, tool, extra=None):
        return picks.finish(s, tool, lambda: reading(o), extra=extra)

    def reading(o):
        sh = getattr(o, "Shape", None)
        out = {"object": o.Label, "ifc": ifc_type(o)}
        if isinstance(sh, Part.Shape) and not sh.isNull():
            out["box"] = geo.box_json(sh)["size"]
            if sh.Solids:
                out["volume_m3"] = round(sh.Volume / 1e9, 4)
                out["solids"] = len(sh.Solids)
        else:
            out["warning"] = "no shape came out — check its base and sizes."
        st = o.getStatusString() if hasattr(o, "getStatusString") else ""
        if st and st not in ("Valid", "Touched"):
            out["status"] = st
        return out

    def arch_material(name, density=None):
        m = next((o for o in doc().Objects if o.Label == name and proxy_name(o) == "_ArchMaterial"), None)
        if m is None:
            m = headless_call(Arch.makeMaterial, name)
            m.Label = s.unique(name, m)
        if density is not None:
            d = dict(getattr(m, "Material", {}) or {})
            d["Density"] = f"{density} kg/m^3"
            m.Material = d
        return m

    def density_of(o):
        m = getattr(o, "Material", None)
        if m is None:
            return None
        mats = getattr(m, "Materials", None)
        if mats:  # a multi-material: thickness-weighted
            th = [qty(t) for t in getattr(m, "Thicknesses", [])]
            ds = [density_of_mat(x) for x in mats]
            if th and all(d is not None for d in ds) and sum(th) > 0:
                return sum(d * t for d, t in zip(ds, th)) / sum(th)
            return None
        return density_of_mat(m)

    def density_of_mat(m):
        d = (getattr(m, "Material", {}) or {}).get("Density")
        if not d:
            return None
        try:
            return float(str(d).split()[0])
        except ValueError:
            return None

    # ---- quantities -----------------------------------------------------------

    SPATIAL = ("_Building", "_Floor", "_Site", "BuildingPart")

    def counted():
        """The BIM objects a take-off counts: those with a shape, less the
        containers. A level, building or site carries its members' solids as
        its own shape in FreeCAD 1.1: counted, every member would be counted
        again. Nothing without volume but a space."""
        out = []
        for o in doc().Objects:
            if not is_bim(o) or not isinstance(getattr(o, "Shape", None), Part.Shape) or o.Shape.isNull():
                continue
            if getattr(o, "Group", None) and not o.Shape.Solids:
                continue  # a container
            if proxy_name(o) in SPATIAL or ifc_type(o) in ("Building", "Building Storey", "Site", "Project"):
                continue
            if (o.Shape.Volume / 1e9 if o.Shape.Solids else 0.0) <= 0 and ifc_type(o) not in ("Space",):
                continue
            out.append(o)
        return out

    def takeoff(o):
        """One object's take-off: its row (as answered), and its volume (m³) and density unrounded for the sums."""
        sh = o.Shape
        vol = sh.Volume / 1e9 if sh.Solids else 0.0
        mat = getattr(o, "Material", None)
        dens = density_of(o)
        row = {"object": o.Label, "ifc": ifc_type(o), "material": mat.Label if mat is not None else None, "volume_m3": round(vol, 4)}
        for k, key in (("VerticalArea", "verticalArea_m2"), ("HorizontalArea", "horizontalArea_m2"), ("PerimeterLength", "perimeter_m")):
            if hasattr(o, k):
                v = qty(getattr(o, k))
                if v:
                    row[key] = round(v / (1e6 if "Area" in k else 1e3), 3)
        if dens:
            row["mass_kg"] = round(vol * dens, 1)
        return {"row": row, "volume": vol, "density": dens}

    def grouped(items, by):
        """The take-offs added up by IFC type, by material or by both: count,
        volume, and mass (None where a member has no density)."""
        groups = {}
        for it in items:
            row, vol, dens = it["row"], it["volume"], it["density"]
            key = row["ifc"] if by == "type" else (row["material"] or "(no material)") if by == "material" else f"{row['ifc']} / {row['material'] or '-'}"
            g = groups.setdefault(key, {"count": 0, "volume_m3": 0.0, "mass_kg": 0.0, "massKnown": True})
            g["count"] += 1
            g["volume_m3"] += vol
            if dens:
                g["mass_kg"] += vol * dens
            else:
                g["massKnown"] = False
        for g in groups.values():
            g["volume_m3"] = round(g["volume_m3"], 4)
            g["mass_kg"] = round(g["mass_kg"], 1) if g["massKnown"] else None
            del g["massKnown"]
        return groups

    # ---- tiles (FreeCAD 1.0 and 1.1 have no covering object) ---------------------

    def tile_grid(face, n, tl, tw, j):
        """How tiles tl × tw with joint j lie on a flat face with normal n:
        their two directions (u along the face's first edge, v across), the
        face's centre c, and how many are tried each way from it (k, m)."""
        u = face.Edges[0].tangentAt(face.Edges[0].FirstParameter) if face.Edges else V(1, 0, 0)
        u = (u - n * u.dot(n))
        u.normalize()
        span = face.BoundBox.DiagonalLength
        return {"u": u, "v": n.cross(u), "c": face.CenterOfMass, "k": int(span / (tl + j)) + 2, "m": int(span / (tw + j)) + 2}

    def lay_tiles(slab, grid, n, tl, tw, th, j):
        """The tiles of the grid that land on the slab of finish, each cut to
        it (a boolean each): the pieces, and how many are whole and cut."""
        u, v, c = grid["u"], grid["v"], grid["c"]
        tiles = []
        full = tl * tw * th
        whole = cut = 0
        sb = slab.BoundBox
        for i in range(-grid["k"], grid["k"]):
            for jj in range(-grid["m"], grid["m"]):
                o0 = c + u * (i * (tl + j)) + v * (jj * (tw + j))
                b = Part.makeBox(tl, tw, th)
                b.Placement = FreeCAD.Placement(o0, FreeCAD.Rotation(u, v, n, "ZXY"))
                if not b.BoundBox.intersect(sb):
                    continue  # clear of the face: no boolean needed
                piece = b.common(slab)
                if piece.isNull() or piece.Volume < 1e-6:
                    continue
                tiles.append(piece)
                if piece.Volume > full * 0.999:
                    whole += 1
                else:
                    cut += 1
        return {"tiles": tiles, "whole": whole, "cut": cut}

    # What the tools' entries (agentlink/data/tools.json, "family": "bim_more") call by name.
    helpers = {"doc": doc, "finish": finish, "headless_call": headless_call, "snapshot": lambda tool: s.snapshot(tool), "step_count": lambda: len(s.steps),
               "find": lambda ref, *what: picks.find(doc(), ref, *what), "finds": lambda refs, *what: [picks.find(doc(), r, *what) for r in (refs or [])],
               "resolve": lambda ref: picks.resolve(s, ref), "num": picks.num, "vec": vec, "vec3": picks.vec3, "direction": picks.direction,
               "unique": lambda label, *own: s.unique(label, *own),
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "polygon": Part.makePolygon, "segment": Part.makeLine,
               "box": Part.makeBox, "compound": Part.makeCompound, "is_shape": lambda x: isinstance(x, Part.Shape),
               # the family's
               "shape": shape, "is_bim": is_bim, "ifc_type": ifc_type, "ifc_set": ifc_set, "contained": contained, "proxy_name": proxy_name,
               "settype": settype, "setsome": setsome, "arch_material": arch_material, "counted": counted, "takeoff": takeoff, "grouped": grouped,
               "tile_grid": tile_grid, "lay_tiles": lay_tiles}
    return runners.tools(GROUP, s, helpers, family="bim_more")

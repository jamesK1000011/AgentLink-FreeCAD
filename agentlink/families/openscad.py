# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD's OpenSCAD workbench headless: CSG files in (and .scad through the
# OpenSCAD program), OpenSCAD code run straight into the document, objects
# written out as CSG for OpenSCAD, and hull / Minkowski sums through OpenSCAD
# — the convex hull computed here when OpenSCAD is not installed.

import contextlib
import os

import FreeCAD
import Part

from .. import paths
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks

GROUP = "openscad"
INFO = "OpenSCAD: CSG and SCAD files in, OpenSCAD code run into the document, CSG out, hull and Minkowski sums."


@contextlib.contextmanager
def console_mode():
    """The workbench's importers reach for view objects when FreeCAD says a
    window is up (Agent Link's headless renderer loads FreeCADGui)."""
    up = FreeCAD.GuiUp
    FreeCAD.GuiUp = False
    # A CSG file can call OpenSCAD (hull, minkowski, import): FreeCAD then
    # searches for it through Finder on a Mac — kept to the plain search here.
    try:
        import OpenSCADUtils as U

        search, U.searchforopenscadexe = U.searchforopenscadexe, (lambda: exe())
    except ImportError:
        U = None
    try:
        yield
    finally:
        FreeCAD.GuiUp = up
        if U is not None:
            U.searchforopenscadexe = search


PREF = "User parameter:BaseApp/Preferences/Mod/OpenSCAD"


def exe():
    """The OpenSCAD program: FreeCAD's preference, the PATH, or the usual app
    folders. Never FreeCAD's own search, which on a Mac asks Finder through
    AppleScript and waits on a permission prompt."""
    import shutil

    cands = [FreeCAD.ParamGet(PREF).GetString("openscadexecutable"), shutil.which("openscad"),
             "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD", os.path.expanduser("~/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"),
             "/opt/homebrew/bin/openscad", "/usr/local/bin/openscad", "/usr/bin/openscad"]
    for p in cands:
        if p and os.path.isfile(p):
            # FreeCAD's own calls then find it without searching.
            FreeCAD.ParamGet(PREF).SetString("openscadexecutable", p)
            return p
    return None


def need_exe(what):
    p = exe()
    if not p:
        raise ToolError("unavailable", f"{what} needs the OpenSCAD program, not found on this computer: the person installs it (openscad.org) "
                        "or sets its path in FreeCAD's OpenSCAD preferences.")
    return p


def hull_here(shapes, tol=0.05):
    """The convex hull of shapes' points (tessellated) as a solid."""
    import numpy as np

    from .. import hull3d

    diag = max(s_.BoundBox.DiagonalLength for s_ in shapes)
    tol = max(tol, diag * 0.002)  # a chord error to the shapes' size: a few thousand points, not tens
    pts, corners = [], []
    for sh in shapes:
        v, _f = sh.tessellate(tol)
        pts += [(p.x, p.y, p.z) for p in v]
        corners += [(p.Point.x, p.Point.y, p.Point.z) for p in sh.Vertexes]
    P = np.unique(np.round(np.array(pts, float), 9), axis=0)
    if len(P) > 6000:
        P = P[np.random.default_rng(0).choice(len(P), 6000, replace=False)]
    if corners:
        P = np.vstack([P, np.array(corners, float)])
    try:
        V, T = hull3d.hull(P)
    except hull3d.HullError as e:
        raise bad(f"objects: {e}.") from None
    # built through a mesh (FreeCAD's own code, quick for thousands of
    # triangles); flat sides are merged only when there are few faces
    sh = Part.Shape()
    sh.makeShapeFromMesh(([FreeCAD.Vector(*v) for v in V], [tuple(int(i) for i in tr) for tr in T]), 1e-6)
    sol = Part.makeSolid(Part.Shell(sh.Faces))
    if len(T) <= 400:
        try:
            sol = sol.removeSplitter()
        except Exception:
            pass
    return sol


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def where(p):
        if not isinstance(p, str) or not p.strip():
            raise bad("path: a file's path (a relative one is in the session's folder).")
        return paths.local(s, p, expand=False)

    def made_since(before):
        out = []
        for o in doc().Objects:
            if o.Name in before:
                continue
            e = {"object": o.Label, "type": o.TypeId}
            sh = getattr(o, "Shape", None)
            if isinstance(sh, Part.Shape) and not sh.isNull():
                e["solids"] = len(sh.Solids)
                if sh.Solids:
                    e["volume"] = round(sh.Volume, 3)
            out.append(e)
        # the top of what came in: objects nothing else made uses
        tops = [o.Label for o in doc().Objects if o.Name not in before and not any(p.Name not in before for p in o.InList)]
        return out, tops

    def scad_import(a):
        p = where(a.get("path"))
        if not os.path.isfile(p):
            raise ToolError("not_found", f"{p}: no such file — a relative path is looked for in the session's folder.")
        ext = os.path.splitext(p)[1].lower()
        if ext not in (".csg", ".scad"):
            raise bad(f"path: {ext or 'no extension'} is not OpenSCAD's — a .csg or .scad file (import_file reads STL, STEP and the rest).")
        if ext == ".scad":
            need_exe("A .scad file")
        before = {o.Name for o in doc().Objects}
        try:
            import importCSG

            with console_mode():
                importCSG.insert(p, doc().Name)
        except ImportError as e:
            raise ToolError("unavailable", f"FreeCAD's CSG importer is not loadable here ({e}).") from None
        except Exception as e:
            raise ToolError("failed", f"{os.path.basename(p)} could not be read: {e or type(e).__name__} — nothing was kept. scad_status says whether the CSG parser and OpenSCAD are here; a .scad that uses fonts or imports other files needs them beside it.") from None
        doc().recompute()
        objs, tops = made_since(before)
        if not objs:
            raise ToolError("failed", f"{os.path.basename(p)}: nothing came in — the file has no geometry at its top level (modules only defined, never called?).")
        return picks.finish(s, "scad_import", lambda: {"path": p, "objects": len(objs), "top": tops, "made": objs[:40]}, recompute=False)

    def scad_code(a):
        code = a.get("code")
        if not isinstance(code, str) or not code.strip():
            raise bad("code: OpenSCAD source, e.g. \"difference() { cube(20, center=true); sphere(13); }\".")
        need_exe("OpenSCAD code")
        import OpenSCADUtils as U

        try:
            with console_mode():
                out = U.callopenscadstring(code, "csg")
        except Exception as e:
            raise ToolError("failed", f"OpenSCAD refused the code: {e} — fix the line it names; nothing was made.") from None
        if not out or not os.path.isfile(out):
            raise ToolError("failed", "OpenSCAD made nothing from the code (an error in it, or no geometry at the top level).")
        before = {o.Name for o in doc().Objects}
        try:
            import importCSG

            with console_mode():
                importCSG.insert(out, doc().Name)
        except Exception as e:  # noqa: BLE001 - OpenSCAD ran, FreeCAD's CSG reader did not take its answer
            raise ToolError("failed", f"OpenSCAD ran the code, but FreeCAD's CSG importer could not read the result: {e or type(e).__name__} — nothing was kept. Simpler code (no text(), surface() or import()) usually reads.") from None
        finally:
            try:
                os.unlink(out)
            except OSError:
                pass
        doc().recompute()
        objs, tops = made_since(before)
        if not objs:
            raise ToolError("failed", "The code made no geometry (modules only defined, or everything commented out).")
        if a.get("name") and len(tops) == 1:
            top = next(o for o in doc().Objects if o.Label == tops[0])
            top.Label = s.unique(a["name"], top)
            tops = [top.Label]
        return picks.finish(s, "scad_code", lambda: {"top": tops, "objects": len(objs), "made": objs[:40]}, recompute=False)

    def scad_export(a):
        names = a.get("objects") or []
        objs = [picks.find(doc(), n, "objects") for n in picks.ref_list(names)] if names else [s.body(None)]
        for o in objs:
            if not isinstance(getattr(o, "Shape", None), Part.Shape) or o.Shape.isNull():
                raise bad(f"objects: {o.Label} ({o.TypeId}) has no shape to write as CSG.")
        p = where(a.get("path") or (objs[0].Label.replace(" ", "_") + ".csg"))
        if not p.lower().endswith((".csg", ".scad")):
            p += ".csg"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        try:
            import exportCSG

            with console_mode():
                exportCSG.export(objs, p)
        except Exception as e:
            raise ToolError("failed", f"CSG export failed: {e or type(e).__name__} — FreeCAD's exporter writes Part primitives, booleans, extrusions and placements itself and meshes the rest; export {{ format: \"stl\" }} gives OpenSCAD a mesh to import() instead.") from None
        with open(p, encoding="utf-8", errors="replace") as f:
            text = f.read()
        poly = text.count("polyhedron(")
        out = {"objects": [o.Label for o in objs], "path": p, "bytes": os.path.getsize(p), "lines": text.count("\n")}
        if poly:
            out["note"] = f"{poly} object(s) went out as polyhedra (triangles): OpenSCAD has no equivalent for those features."
        return out

    def scad_op(a):
        op = picks.choice(a, "op", ("hull", "minkowski"), "op: hull | minkowski.", "hull")
        objs = [picks.shaped(doc(), n, "objects") for n in (picks.ref_list(a.get("objects")) or [])]
        if len(objs) < (1 if op == "hull" else 2):
            raise bad("objects: " + ("one or more bodies" if op == "hull" else "two bodies (the shape, then what sweeps round it)") + " by name or label.")
        how = "OpenSCAD"
        if exe():
            import OpenSCADUtils as U

            try:
                with console_mode():
                    res = U.process_ObjectsViaOpenSCAD(doc(), objs, op)
            except Exception as e:
                raise ToolError("failed", f"OpenSCAD's {op} failed: {e or type(e).__name__} — nothing was made.") from None
            if res is None:
                raise ToolError("failed", f"OpenSCAD's {op} made nothing: the objects must be all solids or all flat (2D and 3D do not mix), or OpenSCAD gave an error of its own (report_read shows it).")
        elif op == "hull":
            res = doc().addObject("Part::Feature", "Hull")
            res.Shape = hull_here([o.Shape for o in objs])
            how = "here (OpenSCAD not installed): the hull of the bodies' points"
        else:
            need_exe("A Minkowski sum")
        res.Label = s.unique(a.get("name") or op.capitalize(), res)
        doc().recompute()
        s.snapshot("scad_op")
        sh = res.Shape
        return {"object": res.Label, "op": op, "of": [o.Label for o in objs], "made": how, "volume": round(sh.Volume, 3) if sh.Solids else None,
                "faces": len(sh.Faces), "step": len(s.steps)}

    def scad_status(a):
        p = exe()
        out = {"openscad": p}
        if p:
            try:
                import OpenSCADUtils as U

                out["version"] = U.getopenscadversion(p)  # given the path: no search
            except Exception as e:
                out["version"] = f"unknown ({e})"
        else:
            out["note"] = "OpenSCAD is not installed: .csg import, CSG export and hull work; .scad files, scad_code and Minkowski need it."
        try:
            import ply  # noqa: F401

            out["csgParser"] = True
        except ImportError:
            out["csgParser"] = False
            out["warning"] = "The CSG parser (ply) is missing from FreeCAD's Python: CSG import will not run."
        return out

    return [
        Tool("scad_status", "Whether the OpenSCAD program is on this computer (openscad: its path or null; version), and whether FreeCAD's CSG parser (ply) loads. Without OpenSCAD: .csg import, CSG export and hull work; .scad files, scad_code and minkowski do not. Changes nothing.", obj({}), scad_status),
        Tool("scad_import", "Read an OpenSCAD file into the document (path; relative: the session's folder): .csg needs only FreeCAD; .scad is run through the OpenSCAD program first (scad_status). Primitives, booleans, transforms and extrusions come in as FreeCAD's own parametric objects (Part::Box, Cut, Fuse …; one object per CSG node, so a small file makes many), hull and minkowski as meshes turned to shapes. Reply: objects (how many), top (the results nothing else uses — the bodies to work with), made [{ object, type, solids, volume }], health.",
             obj({"path": {"type": "string"}}, ["path"]), scad_import, changes=True),
        Tool("scad_code", "Run OpenSCAD code into the document: code (e.g. \"difference() { cube(20, center=true); sphere(13); }\") goes through the OpenSCAD program to CSG and comes in as scad_import does. Needs OpenSCAD installed (scad_status); a syntax error is refused with OpenSCAD's message. name: the label of the result when there is one top object. Reply: top, objects, made.",
             obj({"code": {"type": "string"}, "name": {"type": "string"}}, ["code"]), scad_code, changes=True),
        Tool("scad_export", "Write objects (the one body when left out) as OpenSCAD CSG (path: .csg or .scad, .csg added; relative: the session's folder): Part primitives, booleans, extrusions and placements as OpenSCAD's own, anything else (PartDesign bodies, fillets, imports) as polyhedra of triangles — the note counts them. Reply: path, bytes, lines. The document is not changed.",
             obj({"objects": {"type": "array", "items": {"type": "string"}}, "path": {"type": "string"}}), scad_export),
        Tool("scad_op", "OpenSCAD's hull (the convex shape stretched round the objects, like shrink-wrap) or minkowski (the first shape swept round by the second: rounded edges all over; slow, minutes on curved shapes) of objects [names]. Hull works without OpenSCAD (computed here from the shapes' points, faceted on curves: made says which); minkowski needs OpenSCAD. The inputs are kept. name: the result's label. Reply: object, made, volume, faces, health.",
             obj({"op": {"type": "string", "enum": ["hull", "minkowski"]}, "objects": {"type": "array", "items": {"type": "string"}}, "name": {"type": "string"}}, ["objects"]), scad_op, changes=True),
    ]

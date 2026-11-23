# SPDX-License-Identifier: LGPL-2.1-or-later
# The document-level commands still left to the window, done headless: links
# (make, group, to an element, replace, unlink, import), App::Part
# containers, duplicates, merging another file in, the document's
# information, revert and save all, appearance (colour, transparency, a
# colour per face, random colours) and text documents; Part's compound
# tools, join features and curve-network import; PartDesign's clone, moving
# features between bodies and in the tree, the tip, and a stepped shaft.

import math
import os
import random

import FreeCAD
import Part

from .. import runners
from .. import paths
from ..protocol import ToolError
from . import pd_common as pdc
from . import picks
from .doc import colour

GROUP = "std_more"
INFO = "Links, App::Part, the dependency graph, freeze, units, point-pair alignment, duplicates, merge files, document info, revert, save all, appearance and face colours, text documents; compounds, join features; PartDesign clone, move feature, reorder, tip."

V = FreeCAD.Vector
# Kept on the object itself, so a colour set headless survives the save and
# shows when the file opens in the window (and export colours can read it).
COLOR_PROP = "AgentLinkColor"
FACE_PROP = "AgentLinkFaceColors"


def solid_feature(o):
    """What a body's tip may be: a feature with a solid of its own — not
    a sketch, a datum or a binder (Body::execute refuses those: "Linked
    object is not a PartDesign feature"), nor a MultiTransform's step."""
    if not o.isDerivedFrom("PartDesign::Feature"):
        return False
    return not any(x.TypeId == "PartDesign::MultiTransform" and o in x.Transformations for x in o.InList)


def after_tip(b):
    """The solid features past the tip: kept, but not in the body's shape
    ({ afterTip: [labels] }, or nothing)."""
    g = list(b.Group)
    if b.Tip is None or b.Tip not in g:
        return {}
    left = [o.Label for o in g[g.index(b.Tip) + 1:] if solid_feature(o)]
    return {"afterTip": left} if left else {}


def profile_sketch(f):
    """The sketch a feature is built on: its Profile, which FreeCAD keeps as
    the sketch or as (sketch, [sub-elements]). None when it has none."""
    prof = getattr(f, "Profile", None)
    return prof[0] if isinstance(prof, tuple) else prof


def reattach(o, src, to):
    """A sketch moved from body src to body to, put on the same origin plane
    of its new body: origin planes are per body. Anything else (a sketch on
    a face, a feature) is left as it is."""
    sp = pdc.support_prop(o)
    sup = getattr(o, sp, None)
    if o.TypeId == "Sketcher::SketchObject" and src is not None and sup:
        ref = sup[0][0] if isinstance(sup, list) else None
        if ref is not None and src.Origin.hasObject(ref):
            role = ref.Role if hasattr(ref, "Role") else ref.Label
            new = next((x for x in to.Origin.OriginFeatures if getattr(x, "Role", x.Label) == role), None)
            if new is not None:
                setattr(o, sp, [(new, "")])


def shaft_solid(pts, axis="x"):
    """A stepped shaft's solid from its half outline (points [x, radius, 0]
    along x, the first and last on the axis): the outline closed, points
    that repeat dropped, turned once about x, and laid along y or z when
    asked."""
    clean = [pts[0]]
    for p in pts[1:]:
        if (p - clean[-1]).Length > 1e-9:
            clean.append(p)
    clean.append(pts[0])
    face = Part.Face(Part.makePolygon(clean))
    solid = face.revolve(V(0, 0, 0), V(1, 0, 0), 360)
    solid = Part.Solid(Part.Shell(solid.Faces)) if solid.ShapeType != "Solid" else solid
    if axis != "x":
        solid.rotate(V(0, 0, 0), V(0, 1, 0), -90) if axis == "z" else solid.rotate(V(0, 0, 0), V(0, 0, 1), 90)
    return solid


def open_far(s, p):
    """The document of the .FCStd at p: the open one, else opened in the
    background (hidden where FreeCAD allows it). The agent's own document
    stays the active one."""
    here = s.doc
    ap = os.path.abspath(p)
    for x in FreeCAD.listDocuments().values():
        if os.path.abspath(x.FileName or "") == ap:
            return x
    try:
        fd = FreeCAD.openDocument(p, hidden=True)
    except TypeError:  # an older FreeCAD without hidden
        fd = FreeCAD.openDocument(p)
    try:
        fd.recompute()
        from ..store import _unchanged

        _unchanged(fd)
    except Exception:  # noqa: BLE001
        pass
    try:
        if here is not None:
            FreeCAD.setActiveDocument(here.Name)
    except Exception:  # noqa: BLE001
        pass
    return fd


def far_doc(s, to, file):
    """(the other document, the object reference in it) for link_make's to
    "Doc#Object" or file + to; (None, to) for an object of this document.
    Refused when that document has no file: a link cannot keep its path."""
    here = s.doc
    if file is not None:
        if not isinstance(file, str) or not file.strip():
            raise ToolError("invalid_input", "file: the path of a .FCStd (relative: in the session's folder).")
        p = paths.in_file(s, "link_make", file, key="file")
        if not p.lower().endswith(".fcstd"):
            raise ToolError("invalid_input", f"file: {os.path.basename(p)} is not a FreeCAD document (.FCStd).")
        if not os.path.isfile(p):
            raise ToolError("not_found", f"file {p}: no such file. A relative path is in the session's folder.")
        ref = to.split("#", 1)[1] if isinstance(to, str) and "#" in to else to
        fd = open_far(s, p)
    elif isinstance(to, str) and "#" in to:
        name, ref = to.split("#", 1)
        docs = FreeCAD.listDocuments()
        fd = docs.get(name) or next((x for x in docs.values() if x.Name == name or x.Label == name), None) \
            or next((x for x in docs.values() if name.lower() in (x.Name.lower(), x.Label.lower())), None)
        if fd is None:
            names = ", ".join(x.Label for x in docs.values()) or "none"
            raise ToolError("not_found", f"to {to!r}: no open document {name!r}. Open ones: {names}. Give file: the .FCStd path to open it.")
    else:
        return None, to
    if not ref:
        raise ToolError("invalid_input", "to: the object in the other file, by name or label.")
    if here is not None and fd.Name == here.Name:
        return None, ref
    if not fd.FileName:
        raise ToolError("invalid_state", f"{fd.Label} is not saved yet, so a link cannot keep its path: doc_save it first.")
    return fd, ref


def same_tree(s, fd):
    """Whether the other file is in the folder tree of this document's file
    (or the session's folder before a save), or this one in its: FreeCAD
    keeps such a path relative, and the folder can move as one."""
    here = s.doc
    a = os.path.dirname(os.path.abspath(here.FileName)) if here is not None and here.FileName else os.path.abspath(s.out_dir)
    b = os.path.dirname(os.path.abspath(fd.FileName))
    try:
        c = os.path.commonpath([a, b])
    except ValueError:
        return False
    return c in (a, b)


def tools(s):
    def d():
        if s.doc is None:
            raise ToolError("invalid_state", "No document open: doc_new first.")
        return s.doc

    def objs(refs, what="objects"):
        refs = picks.ref_list(refs, f"{what}: one or more objects by label.")
        return [picks.find(d(), r, what) for r in refs]

    def done(tool, out):
        return picks.finish(s, tool, out, doc=d(), step=False)

    # ---- what the document-level entries call by name --------------------------------------
    # (their tools are data too: links, duplicates, merge, information, revert, save all,
    # appearance, text documents, the OpenSCAD tree tools, freeze, units, alignment)

    def link_target(o):
        """What a link points at: its LinkedObject, which FreeCAD keeps as the
        object or as (object, [sub-elements])."""
        t = getattr(o, "LinkedObject", None)
        return t[0] if isinstance(t, tuple) else t

    def is_records(o):
        """Whether o is a file's own hidden records object (its steps,
        materials and setups): not part of the model, so a merge leaves it out."""
        from ..store import HOLDER

        return o.Name.startswith(HOLDER)

    def doc_errors():
        """The document's failing objects, as doc_open answers them."""
        from .doc import errors

        return errors(d())

    def as_its_file(nd):
        """A document just read is as its file, though FreeCAD 1.1 marks it
        touched on opening (doc_close then asked to discard): recomputed and
        marked unchanged, as doc_open does."""
        try:
            from ..store import _unchanged

            nd.recompute()
            _unchanged(nd)
        except Exception:  # noqa: BLE001
            pass

    def mark_saved(dd):
        """A document just written to its file: the window's mark and the saved state, as doc_save keeps them."""
        from .doc import saved

        saved(dd)

    def keep_colour(o, prop, kind, value):
        """A colour kept on the object itself (the property added when it has
        none), so it survives the save where there is no window."""
        if prop not in o.PropertiesList:
            o.addProperty(kind, prop, "Agent Link", "Colour set by Agent Link")
        setattr(o, prop, value)

    def keep_untouched(o, rgb):
        """keep_colour for OpenSCAD's Color Shapes, which in FreeCAD sets the
        view's colour only and so touches nothing: the property write marks
        the object touched though its shape does not depend on it, so an
        object that was clean before is marked clean again; one already
        waiting for a recompute keeps waiting."""
        try:
            was_touched = "Touched" in o.State
        except Exception:  # noqa: BLE001
            was_touched = True
        keep_colour(o, COLOR_PROP, "App::PropertyColor", rgb)
        if not was_touched:
            try:
                o.purgeTouched()
            except Exception:  # noqa: BLE001 - left touched: recompute clears it
                pass

    def shape_kind(sh):
        """What OpenSCAD's Color Shapes colours a shape by: empty, invalid, or the highest kind it holds."""
        if sh.isNull():
            return "empty"
        if not sh.isValid():
            return "invalid"
        return next((k for k, lst in (("Solid", sh.Solids), ("Shell", sh.Shells), ("Face", sh.Faces), ("Wire", sh.Wires), ("Edge", sh.Edges), ("Vertex", sh.Vertexes)) if lst), "empty")

    def tidy_range(text):
        """(a cell or range in FreeCAD's capitals, None), or (None, what is wrong with the address)."""
        from .. import cells as C

        try:
            return C.range_text(*C.parse_range(text)), None
        except C.AddressError as e:
            return None, str(e)

    def dot_path(p):
        """Where the graph's GraphViz file goes: in the session's folder, .dot, its folder made."""
        p = paths.local(s, p)
        if not p.lower().endswith(".dot"):
            p += ".dot"
            paths.made(s, p)
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        return p

    def dot_text(nodes, edges):
        """The dependency graph as GraphViz text: a box per object, an arrow to each input."""
        def q(t):
            return '"' + str(t).replace("\\", "\\\\").replace('"', '\\"') + '"'
        dot = ["digraph G {", "  rankdir=BT;", "  node [shape=box, fontsize=10];"]
        dot += [f"  {q(o.Name)} [label={q(o.Label)}];" for o in nodes]
        dot += [f"  {q(x.Name)} -> {q(u.Name)};" for x, u in edges]
        dot.append("}")
        return "\n".join(dot) + "\n"

    def write_text(p, text):
        """text written to the file p."""
        with open(p, "w") as f:
            f.write(text)

    def which(name):
        """A program's path on this computer, or None."""
        import shutil

        return shutil.which(name)

    def dot_draw(exe, p):
        """GraphViz's dot run on a .dot file: (the SVG's path, None), or (None, the end of what it said)."""
        import subprocess

        svg = p[:-4] + ".svg"
        r = subprocess.run([exe, "-Tsvg", p, "-o", svg], capture_output=True, timeout=60)
        return (svg, None) if r.returncode == 0 else (None, r.stderr.decode(errors="replace")[-200:])

    def frozen(o):
        """Whether an object is frozen (FreeCAD says so only in its status string)."""
        try:
            return o.getStatusString() == "Freezed"
        except Exception:
            return False

    def toggle_freeze(objects):
        """The window's Std_ToggleFreeze on these objects: FreeCAD has no
        Python door to freezing, only the command, on the selection."""
        import FreeCADGui

        from .. import cowork

        # The person's selection is put back after the command (cowork.held).
        with cowork.held(list(objects)):
            FreeCADGui.runCommand("Std_ToggleFreeze", 0)

    def pair_points(pairs):
        """pairs [[from, to] …] as two n × 3 arrays, or None when they are not numbers."""
        import numpy as np

        try:
            return (np.array([[float(c) for c in p[0]] for p in pairs]), np.array([[float(c) for c in p[1]] for p in pairs]))
        except Exception:
            return None

    def rigid_fit(P, Q):
        """The rigid move that best lays points P on Q (least squares, no
        scaling; fewer than three pairs: a move only): (its 4 × 4 matrix as
        16 numbers by rows, the rms miss, the largest miss), or None when
        three or more from-points lie on one line."""
        import numpy as np

        cp, cq = P.mean(0), Q.mean(0)
        if len(P) >= 3:
            H = (P - cp).T @ (Q - cq)
            U, S, Vt = np.linalg.svd(H)
            if S[1] < 1e-9 * max(1.0, S[0]):
                return None
            dsign = np.sign(np.linalg.det(Vt.T @ U.T)) or 1.0
            R = Vt.T @ np.diag([1, 1, dsign]) @ U.T
        else:
            R = np.eye(3)
        t = cq - R @ cp
        miss = np.linalg.norm((R @ P.T).T + t - Q, axis=1)
        return ([float(x) for x in (*R[0], t[0], *R[1], t[1], *R[2], t[2], 0, 0, 0, 1)], round(float(np.sqrt((miss ** 2).mean())), 4), round(float(miss.max()), 4))

    INFO_PROPS = {"author": "CreatedBy", "company": "Company", "comment": "Comment", "license": "License", "licenseUrl": "LicenseURL", "lastModifiedBy": "LastModifiedBy", "id": "Id", "uid": "Uid", "label": "Label"}
    # OpenSCAD's Color Shapes: by validity and what the shape most is.
    SCAD_COLOURS = {"invalid": "#ff0000", "Solid": "#cccccc", "Shell": "#ffaa00", "Face": "#ffff00", "Wire": "#00ccff", "Edge": "#0066ff", "Vertex": "#aa00ff", "empty": "#555555"}
    doc_helpers = {"link_target": link_target, "split_ref": picks.split_ref, "element": picks.element, "placement_json": picks.placement_json,
                   "repoint": lambda old, new: picks.repoint(d(), old, new), "get_shape": lambda o: Part.getShape(o),
                   "local": lambda p: paths.local(s, p), "is_records": is_records, "errors": doc_errors, "INFO_PROPS": INFO_PROPS, "set_prop": setattr, "getsize": os.path.getsize,
                   "close_document": lambda name: FreeCAD.closeDocument(name), "open_document": lambda path: FreeCAD.openDocument(path), "as_its_file": as_its_file,
                   "switch": lambda nd: s.switch(nd), "documents": lambda: FreeCAD.listDocuments(), "mark_saved": mark_saved,
                   "colour": colour, "random_colour": lambda: (random.random() * 0.8 + 0.1, random.random() * 0.8 + 0.1, random.random() * 0.8 + 0.1, 1.0),
                   "hex_of": lambda c: "#" + "".join(f"{int(round(x * 255)):02x}" for x in c[:3]), "keep_colour": keep_colour, "keep_untouched": keep_untouched,
                   "shape_kind": shape_kind, "SCAD_COLOURS": SCAD_COLOURS, "no_placement": lambda: FreeCAD.Placement(), "tidy_range": tidy_range,
                   "dot_path": dot_path, "dot_text": dot_text, "dot_draw": dot_draw, "which": which, "write_text": write_text,
                   "gui_up": lambda: bool(getattr(FreeCAD, "GuiUp", False)), "frozen": frozen, "toggle_freeze": toggle_freeze,
                   "quantity": lambda text: FreeCAD.Units.Quantity(text), "pair_points": pair_points, "rigid_fit": rigid_fit,
                   "moved_by": lambda m, pl: FreeCAD.Placement(FreeCAD.Matrix(*m)).multiply(pl), "degrees": math.degrees,
                   "far_doc": lambda to, file: far_doc(s, to, file), "same_tree": lambda fd: same_tree(s, fd),
                   "find_in": lambda fd, ref, what="object": picks.find(fd if fd is not None else d(), ref, what)}

    # ---- what the Part, compound and Surface entries call by name ---------------------------
    # (their tools are data: agentlink/data/tools.json, docs/data-tools.md)

    def join_feature(proxy, view, default, name):
        """A BOPTools join feature (Connect, Embed, Cutout) made in the
        session's document: BOPTools' own make* add to FreeCAD.ActiveDocument,
        which is not always this one. Its view provider only in the window."""
        j = d().addObject("Part::FeaturePython", default)
        proxy(j)
        if FreeCAD.GuiUp and getattr(j, "ViewObject", None) is not None:
            view(j.ViewObject)
        j.Label = s.unique(name or default, j)
        return j

    def cloud_points(o):
        """A mesh's or a point cloud's points as an n × 3 array; None for any other object."""
        import numpy as np

        m = getattr(o, "Mesh", None)
        # A FEM result's Mesh links its FEM mesh object, which has no Points (live 77).
        if m is not None and hasattr(m, "Points"):
            return np.array([[p.x, p.y, p.z] for p in m.Points])
        if o.isDerivedFrom("Points::Feature"):
            return np.array([[p.x, p.y, p.z] for p in o.Points.Points])
        return None

    def quadric_patch(P):
        """A quadric fitted to points by least squares, as Reen's Polynomial
        Surface: z(u, v) over the points' best plane, made a 3 × 3 Bézier
        patch over their box. One algorithm: (the patch's shape, the rms and
        the largest miss of the points along the plane's normal)."""
        import numpy as np

        c = P.mean(0)
        _, _, vt = np.linalg.svd(P - c)
        ex, ey, ez = vt[0], vt[1], vt[2]
        L = (P - c) @ np.array([ex, ey, ez]).T
        u, v, z = L[:, 0], L[:, 1], L[:, 2]
        A = np.c_[np.ones_like(u), u, v, u * u, u * v, v * v]
        k, *_ = np.linalg.lstsq(A, z, rcond=None)
        u0, u1, v0, v1 = u.min(), u.max(), v.min(), v.max()
        f = lambda x, y: k[0] + k[1] * x + k[2] * y + k[3] * x * x + k[4] * x * y + k[5] * y * y  # noqa: E731
        # A quadric over a box is a degree-2 Bézier patch: its 9 poles by least squares on a grid.
        B = lambda t: np.array([(1 - t) ** 2, 2 * t * (1 - t), t * t])  # noqa: E731
        ts = np.linspace(0, 1, 7)
        rows, rhs = [], []
        for tu in ts:
            for tv in ts:
                bu, bv = B(tu), B(tv)
                rows.append(np.outer(bu, bv).ravel())
                rhs.append(f(u0 + (u1 - u0) * tu, v0 + (v1 - v0) * tv))
        zp, *_ = np.linalg.lstsq(np.array(rows), np.array(rhs), rcond=None)
        poles = []
        for i in range(3):
            row = []
            for j in range(3):
                uu = u0 + (u1 - u0) * i / 2
                vv = v0 + (v1 - v0) * j / 2
                w = c + ex * uu + ey * vv + ez * zp[i * 3 + j]
                row.append(V(*w))
            poles.append(row)
        bz = Part.BezierSurface()
        bz.increase(2, 2)
        for i in range(3):
            for j in range(3):
                bz.setPole(i + 1, j + 1, poles[i][j])
        res = z - f(u, v)
        return bz.toShape(), round(float(np.sqrt((res ** 2).mean())), 4), round(float(np.abs(res).max()), 4)

    def filter_keeps(o, kind, invert, stencil, frm=None, to=None):
        """How many of o's pieces FreeCAD's CompoundFilter (kind, invert)
        would keep: its own tests (Part/CompoundTools/CompoundFilter.py,
        execute), worked out before the filter is made. A filter that keeps
        nothing raises "Nothing passes through the filter" at its recompute,
        a red traceback in the Report view; it is refused before instead.
        None when not known (the filter's recompute still decides)."""
        try:
            shps = o.Shape.childShapes()
            st = stencil.Shape if stencil is not None else None
            if kind == "collision-pass":
                if st is None:
                    return None
                conf = 1e-7  # Part.Precision.confusion(): OCC's Precision::Confusion
                return sum(1 for x in shps if bool(x.distToShape(st)[0] < conf) ^ bool(invert))
            if kind not in ("window-volume", "window-area", "window-length", "window-distance") or not shps:
                return None
            if kind == "window-distance":
                if st is None:
                    return None
                vals = [x.distToShape(st)[0] for x in shps]
            else:
                attr = {"window-volume": "Volume", "window-area": "Area", "window-length": "Length"}[kind]
                vals = [getattr(x, attr) for x in shps]
            top = max(vals)
            if st is not None and kind != "window-distance":
                top = getattr(st, {"window-volume": "Volume", "window-area": "Area", "window-length": "Length"}[kind])
            lo = (80.0 if frm is None else float(frm)) / 100.0 * top
            hi = (100.0 if to is None else float(to)) / 100.0 * top
            return sum(1 for v in vals if bool(lo <= v <= hi) ^ bool(invert))
        except Exception:  # noqa: BLE001 — not known here: the recompute's check stays
            return None

    def tool_module(name):
        """One of FreeCAD's Python modules by name (CompoundTools.Explode), loaded when the tool runs."""
        import importlib

        return importlib.import_module(name)

    # FreeCAD's CompoundFilter FilterType for each way of keeping, and
    # whether it is inverted: collision-fail is collision-pass with Invert;
    # window-distribution was compound_filter's old word for window-distance.
    FILTER_KINDS = {"collision-pass": ("collision-pass", False), "collision-fail": ("collision-pass", True), "window-volume": ("window-volume", False),
                    "window-area": ("window-area", False), "window-length": ("window-length", False), "window-distance": ("window-distance", False),
                    "window-distribution": ("window-distance", False)}
    part_helpers = {"objs": objs, "find": lambda ref, what="object": picks.find(d(), ref, what), "ref_list": picks.ref_list, "snapshot": lambda tool: s.snapshot(tool),
                    "tool_module": tool_module, "FILTER_KINDS": FILTER_KINDS, "filter_keeps": filter_keeps, "join_feature": join_feature,
                    "in_file": lambda tool, path: paths.in_file(s, tool, path), "isfile": os.path.isfile, "basename": os.path.basename,
                    "stem": lambda p: os.path.splitext(os.path.basename(p))[0], "read_shape": lambda *a, **k: Part.read(*a, **k), "compound": lambda *a, **k: Part.Compound(*a, **k),
                    "cloud_points": cloud_points, "quadric_patch": quadric_patch}

    # The wrappers kept as data (agentlink/data/tools.json) run on these.
    helpers = {"carry_material": lambda src, copies: picks.carry_material(s, src, copies), "doc": d, "done": done, "unique": s.unique, "placed": picks.placed, "placement": picks.placement,
               "shaped": lambda ref, what: picks.shaped(d(), ref, what),
               "find": lambda ref, what="object": picks.find(d(), ref, what), "snapshot": lambda tool: s.snapshot(tool), "V": V,
               # PartDesign: bodies, their features and their tip
               "pd_body": lambda ref: pdc.pd_body(d(), ref), "body_of": pdc.body_of, "in_body": pdc.in_body, "broken": lambda: pdc.newly_broken(d()),
               # every failing object after the call, old ones too (compound_explode: which one a red
               # "Nothing passes through the filter" came from)
               "all_broken": lambda: pdc.broken(d()),
               "solid_feature": solid_feature, "after_tip": after_tip, "profile_sketch": profile_sketch, "reattach": reattach, "shaft_solid": shaft_solid}

    helpers.update(part_helpers)
    helpers.update(doc_helpers)
    return runners.tools(GROUP, s, helpers)

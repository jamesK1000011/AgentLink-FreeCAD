# SPDX-License-Identifier: LGPL-2.1-or-later
# BIM's remaining commands, headless: generic components, clones and
# unclones, external references, structural systems, pipe connectors, panel
# cut sheets and nesting, the IFC B-rep flag, 2D views of the levels, image
# planes, the objects library, re-extrusion from a face, rewiring, glue,
# trash and reordering a group's children.

import glob
import os

import FreeCAD
import Part

import Arch  # noqa: F401 - the family is left out without BIM

from .. import runners
from .. import geometry as geo
from ..protocol import ToolError
from . import picks
from .bim import headless_call, ifc_set, shape

# The tools themselves are data (agentlink/data/tools.json; run by
# agentlink/runners.py's steps runner). What is here is what their entries
# call by name (docs/data-tools.md).

GROUP = "bim_gaps"
INFO = "BIM components, clones, references, structural systems, pipe connectors, panel cuts and sheets, nesting, IFC B-rep flag, 2D level views, image planes, library, re-extrude, rewire, glue, trash, reorder."

V = FreeCAD.Vector


def file(path):
    """The file at path (~ opened out), or None when there is none."""
    p = os.path.expanduser(path or "")
    return p if os.path.isfile(p) else None


def stem(path):
    """A file's name without its folder and ending."""
    return os.path.splitext(os.path.basename(path))[0]


def image_ratio(path):
    """An image's height / width, read from the file where Pillow is there; None otherwise."""
    try:
        from PIL import Image  # noqa: F401

        with Image.open(path) as im:
            return im.height / im.width
    except Exception:
        return None


def unclone(o, src):
    """A clone cut loose from its original src: it keeps its place and takes src's own properties."""
    pl = FreeCAD.Placement(o.Placement)
    o.CloneOf = None
    skip = {"Objects", "CloneOf", "ExpressionEngine", "HorizontalArea", "Area", "VerticalArea", "PerimeterLength", "Placement", "Proxy", "Shape", "Label", "Label2"}
    for p in src.PropertiesList:
        if p not in skip and p in o.PropertiesList:
            try:
                setattr(o, p, getattr(src, p))
            except Exception:
                pass
    o.Placement = pl


def depth_along(o, norm):
    """The length of o's first edge that runs along norm (either way): how deep it was extruded. None when it has none."""
    for e in o.Shape.Edges:
        if abs(e.tangentAt(0).getAngle(norm)) < 1e-4 or abs(e.tangentAt(0).getAngle(norm) - 3.141592653589793) < 1e-4:
            return e.Length
    return None


def copy_props(src, dst, names):
    """Those of the named properties that both have, copied from src to dst."""
    for p in names:
        if hasattr(src, p) and hasattr(dst, p):
            setattr(dst, p, getattr(src, p))


def library_roots(folder):
    """Where the objects library may be: the folder given, the parts_library
    add-on's own setting, its place in FreeCAD's Mod folder — those that exist."""
    roots = [folder] if folder else []
    try:
        pref = FreeCAD.ParamGet("User parameter:Plugins/parts_library").GetString("destination", "")
        if pref:
            roots.append(pref)
    except Exception:
        pass
    roots.append(os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "parts_library"))
    return [os.path.expanduser(r) for r in roots if r and os.path.isdir(os.path.expanduser(r))]


def library_files(roots, q):
    """The model files under roots whose path holds every word of q (200 a root at most)."""
    hits = []
    for r in roots:
        for f in glob.glob(os.path.join(r, "**", "*"), recursive=True):
            if f.lower().endswith((".fcstd", ".step", ".stp", ".iges", ".igs", ".stl", ".brep")) and all(w in f.lower() for w in q.split()):
                hits.append(f)
                if len(hits) >= 200:
                    break
    return hits


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

    def named(o, name):
        if name:
            o.Label = s.unique(name, o)
        return o

    def reading(o):
        d().recompute()
        sh = getattr(o, "Shape", None)
        if sh is None or sh.isNull():
            return {}
        return {"volume": round(sh.Volume, 3) if sh.Solids else None, "box": geo.box_json(sh, 3)["size"]}

    def nester(sheet, pieces):
        """FreeCAD's nester (ArchNesting.Nester) with its sheet (one flat face) and its pieces."""
        import ArchNesting

        n = ArchNesting.Nester()
        n.container = sheet
        n.addObjects(pieces)
        return n

    def nest_rotations():
        import ArchNesting

        return list(ArchNesting.ROTATIONS)

    def nest_run(n, rotations):
        """The nester run. It has no settings of its own: the rotations it
        tries are the module's ROTATIONS (0, 90, 180, 270), set for this run
        and put back after it; it has no margin in 1.1."""
        import ArchNesting

        was = list(ArchNesting.ROTATIONS)
        try:
            if rotations:
                ArchNesting.ROTATIONS = rotations
            return n.run()
        finally:
            ArchNesting.ROTATIONS = was

    def emptied(trash):
        """The trash's own children deleted, each with the children nothing else uses: their labels."""
        gone = []

        def kids(o):
            out = []
            for c in o.OutList:
                if len(c.InList) == 1 and c.InList[0] is o:
                    out += [c] + kids(c)
            return out

        for o in list(trash.Group):
            if len(o.InList) == 1 and o.InList[0] is trash:
                for x in [o] + kids(o):
                    gone.append(x.Label)
                    d().removeObject(x.Name)
        return gone

    def draft(name):
        """A function of FreeCAD's Draft or DraftGeomUtils by name (loaded when first called)."""
        def call(*a, **kw):
            import Draft
            import DraftGeomUtils

            return (getattr(Draft, name, None) or getattr(DraftGeomUtils, name))(*a, **kw)

        return call

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": d, "objs": objs, "done": done, "named": named, "reading": reading, "headless_call": headless_call,
               "file": file, "basename": os.path.basename, "snapshot": lambda tool: s.snapshot(tool),
               "find": lambda ref, *what: picks.find(d(), ref, *what), "shaped": lambda ref, *what: picks.shaped(d(), ref, *what),
               "resolve": lambda ref: picks.resolve(s, ref), "placed": picks.placed, "placement_of": picks.placement,
               "unique": lambda label, *own: s.unique(label, *own), "ifc_set": ifc_set, "shape": shape,
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "compound": Part.makeCompound,
               "part_insert": lambda path, name: Part.insert(path, name), "draft_type": draft("getType"), "find_wires": draft("findWires"),
               "has_curves": draft("hasCurves"), "expanduser": os.path.expanduser, "isfile": os.path.isfile, "isabs": os.path.isabs,
               # the family's
               "stem": stem, "image_ratio": image_ratio, "unclone": unclone, "depth_along": depth_along, "copy_props": copy_props,
               "library_roots": library_roots, "library_files": library_files, "nester": nester, "nest_rotations": nest_rotations,
               "nest_run": nest_run, "emptied": emptied}
    return runners.tools(GROUP, s, helpers)

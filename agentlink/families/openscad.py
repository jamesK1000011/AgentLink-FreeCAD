# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD's OpenSCAD workbench headless: CSG files in (and .scad through the
# OpenSCAD program), OpenSCAD code run straight into the document, objects
# written out as CSG for OpenSCAD, and hull / Minkowski sums through OpenSCAD
# — the convex hull computed here when OpenSCAD is not installed.

import contextlib
import os
import re

import FreeCAD
import Part

from .. import paths
from .. import runners
from ..protocol import bad
from . import picks

GROUP = "openscad"
INFO = "OpenSCAD: CSG and SCAD files in, OpenSCAD code run into the document, CSG out, hull and Minkowski sums."


def _search():
    return exe()


def plain_search():
    """FreeCAD's own search for the OpenSCAD program replaced, for good, by
    exe(): on a Mac FreeCAD's asks Finder through AppleScript and waits, with
    no time limit, on a permission prompt nobody sees. It is reached from
    places no tool here calls: the OpenSCAD workbench as it first comes up
    (InitGui.py, when the preference is empty — so every scad_ call shown in
    the window met it), and a hull or Minkowski feature at any later
    recompute, which loads the module a second time as
    OpenSCAD.OpenSCADUtils. This loads the first copy and sets it; the guard
    below sets either copy as it loads, whoever loads it."""
    try:
        import OpenSCADUtils  # noqa: F401 - loaded with FreeCAD.GuiUp as it truly is
    except Exception:  # noqa: BLE001 - no workbench in this build: nothing to guard
        return False
    guard_search()
    return True


SEARCHERS = ("OpenSCADUtils", "OpenSCAD.OpenSCADUtils")


class _Loaded:
    """A module's own loader, with the plain search set once it has run."""

    def __init__(self, inner):
        self.inner = inner

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        self.inner.exec_module(module)
        try:
            module.searchforopenscadexe = _search
        except Exception:  # noqa: BLE001
            pass

    def __getattr__(self, name):
        return getattr(self.inner, name)


class _SearchGuard:
    """On sys.meta_path: whoever loads FreeCAD's OpenSCADUtils, under either
    name (the workbench the person clicks, a saved hull feature recomputing,
    a tool here), gets it with the plain search already in place. Finds
    nothing itself: the other finders do, and only these two names are
    touched."""

    def find_spec(self, name, path=None, target=None):
        if name not in SEARCHERS:
            return None
        import sys

        for f in list(sys.meta_path):
            find = getattr(f, "find_spec", None)
            if f is self or find is None:
                continue
            try:
                spec = find(name, path, target)
            except Exception:  # noqa: BLE001
                spec = None
            if spec is not None:
                if getattr(spec, "loader", None) is not None and hasattr(spec.loader, "exec_module"):
                    spec.loader = _Loaded(spec.loader)
                return spec
        return None


def guard_search():
    """The guard put on (once), and any copy of the module already loaded
    set: no import is made here, so it costs nothing until FreeCAD's
    OpenSCAD code is wanted."""
    import sys

    if not any(isinstance(f, _SearchGuard) for f in sys.meta_path):
        sys.meta_path.insert(0, _SearchGuard())
    for name in SEARCHERS:
        m = sys.modules.get(name)
        if m is not None and getattr(m, "searchforopenscadexe", None) is not _search:
            m.searchforopenscadexe = _search


guard_search()


# The importers' own switches, read once as each module loads: gui asks for
# view objects, the front document and message boxes ("Unsupported Function",
# the DXF library download question); printverbose prints every node.
SWITCHES = {"importCSG": ("gui", "printverbose"), "exportCSG": ("gui",), "importDXF": ("gui",)}


@contextlib.contextmanager
def console_mode():
    """FreeCAD's OpenSCAD code run as it runs without a window, whatever is
    up: no dialog, no view object, no search through Finder. The modules are
    loaded BEFORE FreeCAD.GuiUp is set False (a module loaded while it is
    False keeps its window parts switched off for the rest of the session),
    and their own gui switches are set False too: those were read when each
    module loaded, so GuiUp alone does not reach them."""
    import sys

    plain_search()  # loads OpenSCADUtils, and with it exportCSG and importDXF
    kept = []
    for name, flags in SWITCHES.items():
        for full in (name, "OpenSCAD." + name):
            m = sys.modules.get(full)
            for flag in flags if m is not None else ():
                if hasattr(m, flag):
                    kept.append((m, flag, getattr(m, flag)))
                    setattr(m, flag, False)
    up = FreeCAD.GuiUp
    FreeCAD.GuiUp = False
    try:
        yield
    finally:
        FreeCAD.GuiUp = up
        for m, flag, was in kept:
            setattr(m, flag, was)


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


# What FreeCAD's CSG reader hands to the OpenSCAD program: hull and minkowski
# (OpenSCADFeatures.CGALFeature, at recompute) and text (importCSG.processTextCmd).
NEEDS_PROGRAM = re.compile(r"\b(hull|minkowski|text)\s*\(")
NOT_CODE = re.compile(r'"[^"]*"|//[^\n]*')


def csg_needs(text):
    """The CSG words in text that only the OpenSCAD program can work out
    (strings and comments left out), in the file's order."""
    out = []
    for w in NEEDS_PROGRAM.findall(NOT_CODE.sub(" ", text)):
        if w not in out:
            out.append(w)
    return out


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


def version_of(p):
    """What the OpenSCAD program at p says to -v, asked here with a time
    limit (FreeCAD's getopenscadversion waits without one): ("ok", its
    words or None), ("timeout", None) after 20 s, or ("error", why)."""
    import subprocess

    try:
        r = subprocess.run([p, "-v"], capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
        return "ok", (r.stdout.strip() or r.stderr.strip()) or None
    except subprocess.TimeoutExpired:
        return "timeout", None
    except Exception as e:
        return "error", str(e)


def has_ply():
    """Whether FreeCAD's Python has ply, the parser FreeCAD's CSG reader stands on."""
    try:
        import ply  # noqa: F401

        return True
    except ImportError:
        return False


def has_shape(o):
    """Whether an object has a shape to write (a Part shape that is not empty)."""
    return isinstance(getattr(o, "Shape", None), Part.Shape) and not o.Shape.isNull()


def said(e):
    """An error for a message: itself, or its class's name where it would read as nothing."""
    return e or type(e).__name__


def read_text(p):
    """A text file's content, bytes that are not UTF-8 replaced."""
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def drop_file(p):
    """A file removed (OpenSCAD's own output, once read); one already gone is passed by."""
    try:
        os.unlink(p)
    except OSError:
        pass


def make_folder(p):
    """The folder a file is to be written in, made where it is not there."""
    os.makedirs(os.path.dirname(p), exist_ok=True)


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

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

    def read_in(p):
        """FreeCAD's CSG reader on p, into the session's document: window
        parts off (console_mode), the session's document the active one
        while it runs (the reader makes circles, polygons and mesh imports in
        the ACTIVE document), then put back."""
        import importCSG  # needs ply: an ImportError is the caller's to word

        front = FreeCAD.ActiveDocument
        mine = doc().Name
        moved = front is None or front.Name != mine
        if moved:
            FreeCAD.setActiveDocument(mine)
        try:
            with console_mode():
                importCSG.insert(p, mine)
        finally:
            del importCSG.original_root_objects[:]  # the reader's list of what was here: never emptied by it
            if moved and front is not None:
                try:
                    FreeCAD.setActiveDocument(front.Name)
                except Exception:  # noqa: BLE001 - closed meanwhile
                    pass

    def tidy_view(before):
        """In the window, what the reader itself does there (fixVisibility):
        the tops shown, what they are built from hidden."""
        if not FreeCAD.GuiUp:
            return
        for o in doc().Objects:
            if o.Name in before:
                continue
            try:
                vo = getattr(o, "ViewObject", None)
                if vo is not None:
                    vo.Visibility = not any(p.Name not in before for p in o.InList)
            except Exception:  # noqa: BLE001 - how it looks never fails the import
                pass

    def scad_utils():
        """FreeCAD's OpenSCADUtils (an ImportError where this build has no OpenSCAD workbench)."""
        import OpenSCADUtils

        return OpenSCADUtils

    def run_code(utils, code):
        """The OpenSCAD program run on code, window parts off: the CSG file it wrote (FreeCAD's own call; an error of OpenSCAD's is raised)."""
        with console_mode():
            return utils.callopenscadstring(code, "csg")

    def via_openscad(utils, objs, op):
        """A hull or Minkowski sum of objects worked out by the OpenSCAD program (FreeCAD's own call, window parts off): the object made, or None."""
        with console_mode():
            return utils.process_ObjectsViaOpenSCAD(doc(), objs, op)

    def export_csg(objs, p):
        """FreeCAD's CSG exporter on objects, into p, window parts off."""
        import exportCSG

        with console_mode():
            exportCSG.export(objs, p)

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "exe": lambda: exe(), "csg_needs": csg_needs, "hull_here": hull_here, "made_since": made_since, "read_in": read_in, "tidy_view": tidy_view,
               "scad_utils": scad_utils, "run_code": run_code, "via_openscad": via_openscad, "export_csg": export_csg, "version_of": version_of, "has_ply": has_ply,
               "has_shape": has_shape, "said": said, "read_text": read_text, "drop_file": drop_file, "make_folder": make_folder,
               "local": lambda p: paths.local(s, p, expand=False), "find": lambda ref, what: picks.find(doc(), ref, what), "shaped": lambda ref, what: picks.shaped(doc(), ref, what),
               "ref_list": picks.ref_list, "body": lambda: s.body(None), "unique": lambda label, *own: s.unique(label, *own), "snapshot": s.snapshot, "step": lambda: len(s.steps),
               "finish": lambda tool, read: picks.finish(s, tool, read, recompute=False),
               "isfile": os.path.isfile, "basename": os.path.basename, "splitext": os.path.splitext, "getsize": os.path.getsize}
    return runners.tools(GROUP, s, helpers)

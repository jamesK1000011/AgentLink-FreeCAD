# SPDX-License-Identifier: LGPL-2.1-or-later
# The shared health check: what FreeCAD itself says went red or yellow after
# a changing call, read from its own state (no screenshot) and returned with
# the answer as "health": a verdict in words, and short lists of what to fix.
#
#   - object State flags and recompute errors (the tree's red and yellow
#     badges): which objects failed and FreeCAD's reason, which still need a
#     recompute;
#   - sketches the call recomputed: degrees of freedom left and on which
#     geometry, conflicting / redundant / malformed constraints (the solver's
#     own lists), open profiles — news only: a sketch that reads as it did
#     before the call (a spreadsheet edit recomputes the sketches that use
#     the sheet), a CAM tool bit's own sketch, and "fully constrained" after
#     a call that is not a sketch tool's are passed over;
#   - shapes the call recomputed: valid, closed, solid count, self-
#     intersection (small shapes only), overlap with the other parts, with
#     the overlap's size;
#   - what a family adds for its own objects (register: the assembly
#     solver's status, CalculiX's lines);
#   - the window: an open dialog, the task panel's warning labels, the status
#     bar's text. New Report view lines come back as "report" beside it
#     (report_watch), and are counted in the verdict;
#   - "next": one short line of what the window is in the middle of (a sketch
#     open in edit and its freedom, a task panel and its buttons, the
#     workbench, tools whose FreeCAD commands are active), said when it is
#     not what was last said (agentlink/nexthint.py).
#
# One place runs it (protocol.Server._call, round every changing tool), so a
# tool gets it without doing anything. It only reads; it has a time budget
# and size limits and says what it left unchecked instead of going over
# them; and nothing it does can fail the call it follows.

import os
import re
import time

from .once import HEALTH_TODOS  # the advice said once a conversation (agentlink/once.py)

BUDGET_S = 1.5        # the whole check, after which the rest is named as unchecked
MAX_OBJECTS = 4000    # State flags are read on at most this many objects
MAX_LIST = 6          # entries per list in the answer
FACES_VALID = 3000    # isValid on shapes up to this many faces
FACES_SELF = 200      # the self-intersection check (BOP) up to this many faces
FACES_OVERLAP = 300   # a pair's common volume when both have at most this many
OVERLAP_S = 0.6       # seconds the overlap pass may start pairs for
MAX_PAIRS = 24        # pairs tried for overlap
MAX_SKETCHES = 60     # read from attributes: cheap
SKETCHES_BEFORE = 300 # sketches whose reading is kept from before the call
MAX_SHAPES = 12       # and the time budget ends it sooner
MAX_AMBER = 3         # yellow lines in the verdict; the rest are counted
SKETCH_GEO = 400      # a sketch's per-geometry freedom is read up to this many
FREEFORM_MAX = 120    # control points of free-form faces up to which a shape's geometry check or an overlap runs here
SLOW_S = 2.0          # one check on one shape past this is remembered, and not run on that shape again here
MS_BY = 500           # a check this long says where its time went (msBy)

SOLVE = {0: "solved", -1: "the solver failed", -2: "redundant constraints", -3: "conflicting constraints",
         -4: "over-constrained", -5: "malformed constraints"}
POS = {0: "", 1: "the start of ", 2: "the end of ", 3: "the centre of "}
CONTAINERS = ("Assembly::AssemblyObject", "App::Part", "App::DocumentObjectGroup", "App::LinkGroup")
TASK_WORDS = re.compile(r"(error|warning|invalid|failed|cannot|could not|conflict|redundant|malformed|over-?constrained|"
                        r"under-?constrained|degrees? of freedom|not (?:valid|closed|supported|possible)|no (?:solution|valid))", re.I)

# What the observer saw, in order, while any mark is open: a batch's mark and
# its calls' marks nest, each reading the log from where it started.
SOLVER_LABEL = re.compile(r"(under-?constrained|over-?constrained|fully constrained|degrees? of freedom|redundant|conflicting|malformed|empty sketch)", re.I)
_seen = {"log": [], "depth": 0}
_marks = []  # the marks open now, innermost last
_extra = []  # [(owner, fn)] — families' own readings


def enabled():
    return os.environ.get("AGENTLINK_HEALTH", "1") not in ("0", "false", "off")


# ---- which objects a call recomputed: FreeCAD's own document observer ------------------

def _observer_note(obj):
    try:
        if _seen["depth"] > 0 and len(_seen["log"]) < 200000:
            _seen["log"].append((obj.Document.Name, obj.Name))
    except Exception:
        pass


class _Observer:
    """FreeCAD calls these as objects are made, recomputed and removed: the
    exact set a call touched, at no cost to the call."""

    def slotCreatedObject(self, obj):
        _observer_note(obj)

    def slotRecomputedObject(self, obj):
        _observer_note(obj)


_observer = None


def _watch():
    global _observer
    if _observer is None:
        try:
            import FreeCAD

            _observer = _Observer()
            FreeCAD.addDocumentObserver(_observer)
        except Exception:
            _observer = False
    return bool(_observer)


def register(owner, fn):
    """A family's own reading, run after the shared ones: fn(session, tool,
    changed) -> a list of { line, red (bool), todo } (or None). changed: the
    objects the call made or recomputed. Called on the thread the tool ran
    on; anything it raises is dropped."""
    _extra[:] = [(o, f) for o, f in _extra if o != owner]
    _extra.append((owner, fn))


def unregister(owner):
    _extra[:] = [(o, f) for o, f in _extra if o != owner]


# ---- before the call --------------------------------------------------------------------

def _failing(o):
    """FreeCAD's reason when o failed its recompute (the red badge), else
    None."""
    try:
        if o.isValid():
            return None
    except Exception:
        try:
            if "Invalid" not in o.State:
                return None
        except Exception:
            return None
    try:
        return str(o.getStatusString()) or "invalid"
    except Exception:
        return "invalid"


# Objects that are what was put into them and compute nothing: touched after
# a write, they are not out of date (a study's helper solid, the session's
# own records object, a mesh, a group).
HOLDERS = ("Part::Feature", "Mesh::Feature", "Points::Feature", "App::TextDocument", "App::DocumentObjectGroup",
           "App::FeaturePython", "App::Annotation", "App::AnnotationLabel")


def _holds_only(o):
    try:
        return o.TypeId in HOLDERS and not o.OutList
    except Exception:
        return False


def mark(session):
    """Before a changing call: the objects already failing (so the answer
    says which are new), and the observer armed."""
    if not enabled():
        return None
    doc = getattr(session, "doc", None)
    m = {"doc": None, "bad": {}, "t": time.time(), "watched": _watch(), "since": len(_seen["log"]), "open": True}
    _seen["depth"] += 1
    # Every change and recompute in order, for the objects the call leaves
    # waiting for a recompute (agentlink/changes.py).
    try:
        from . import changes

        m["watch"] = changes.open()
    except Exception:
        m["watch"] = None
    try:
        m["doc"] = doc.Name
        objs = doc.Objects
        if len(objs) <= MAX_OBJECTS:
            for o in objs:
                why = _failing(o)
                if why:
                    m["bad"][o.Name] = why
        m["names"] = {o.Name for o in objs}
    except Exception:
        pass
    m["shapes"] = _part_hashes(doc)
    m["sketches"] = _sketch_sigs(doc)
    _marks.append(m)
    return m


def failing_before(doc):
    """The names of doc's objects that were already failing when the call
    in hand began (the innermost open mark on doc): what a guard that
    refuses a change for breaking something must not count — they are the
    verdict's "still failing from before this call". Empty when no call is
    marked on doc (the check off, or a document past MAX_OBJECTS): a guard
    then counts every failing object, as it always did."""
    try:
        name = doc.Name
    except Exception:
        return set()
    for m in reversed(_marks):
        if m.get("open") and m.get("doc") == name:
            return set(m.get("bad") or ())
    return set()


def _key(o):
    """What tells a part's shape before a call from the one after it: kind,
    element counts, box and (small shapes) volume. Not its hash: a recompute
    that changes nothing still makes a new OCC shape (a sketch added to a
    body had the body read again)."""
    from . import geometry as geo

    sh = o.Shape
    k = geo.shape_key(sh)[1:]
    try:
        vol = round(float(sh.Volume), 4) if k[1] <= 500 else None
    except Exception:
        vol = None
    return k + (vol,)


# _key by (document, object), kept while the object's shape is the very
# one it was read from (geometry.shape_key: the OCC shape's hash, its
# counts and box). Before every changing call each part's key was worked
# out afresh, volume and all: in a document of heavy shapes that was most
# of a second a call, whatever the call did. A part a call recomputed is
# read afresh after it (_key_fresh), so the kept value is never older than
# the part's last recompute through a call.
_keys = {}


def _key_kept(doc_name, o):
    from . import geometry as geo

    try:
        full = geo.shape_key(o.Shape)
    except Exception:
        return _key(o)
    hit = _keys.get((doc_name, o.Name))
    if hit is not None and hit[0] == full:
        return hit[1]
    k = _key(o)
    _keys[(doc_name, o.Name)] = (full, k)
    if len(_keys) > 2000:
        for old in list(_keys)[:500]:
            _keys.pop(old, None)
    return k


def _key_fresh(doc_name, o):
    """_key read from the shape now, and kept for the next call's mark."""
    k = _key(o)
    try:
        from . import geometry as geo

        _keys[(doc_name, o.Name)] = (geo.shape_key(o.Shape), k)
    except Exception:
        _keys.pop((doc_name, o.Name), None)
    return k


def _part_hashes(doc):
    """{part name: its shape's key} — a part a call recomputed without
    changing (a Body whose new sketch left its tip alone) is told from one
    it changed."""
    out = {}
    try:
        from .tools import Session

        name = doc.Name
        for o in Session.bodies_in(doc):
            try:
                out[o.Name] = _key_kept(name, o)
            except Exception:
                continue
    except Exception:
        pass
    return out


# ---- checks that can run long ------------------------------------------------------------
# One OCC call cannot be stopped once it runs, so the time budget can only
# decide what is started. Two things keep a single check from taking the
# call with it (a swept helical spring of 3 faces held one answer for 44 s,
# (FREEFORM_MAX was 300: a helical spring swept live came in under it, one
# B-spline face, and its check still took 45.8 s; 120 since.)
# live): a shape with large free-form faces is not given FreeCAD's geometry
# check (shape.check with its BOP self-intersection pass) or an overlap
# boolean here at all, and a check that did run long on a shape is not run
# on that shape again. Each is named as unchecked, with the tool that runs
# it in full; nothing is passed over in silence.

ANALYTIC = ("Plane", "Cylinder", "Cone", "Sphere", "Toroid")
_slow = {}  # (document, object, check) -> (the shape's key then, seconds)


def freeform(sh, stop=None):
    """How much free-form surface a shape carries: the control points of
    its B-spline and Bézier faces, a swept or revolved face by its profile
    curve's, any other non-analytic face as 100. Planes, cylinders, cones,
    spheres and tori count nothing. stop: a total past which counting ends
    (the answer is then only "more than stop")."""
    total = 0
    try:
        faces = sh.Faces
    except Exception:
        return 0
    for f in faces:
        try:
            su = f.Surface
            kind = type(su).__name__
            if kind in ANALYTIC:
                continue
            if kind in ("BSplineSurface", "BezierSurface"):
                total += int(su.NbUPoles) * int(su.NbVPoles)
            elif kind in ("SurfaceOfExtrusion", "SurfaceOfRevolution"):
                c = su.BasisCurve
                total += int(getattr(c, "NbPoles", 0) or 0) if type(c).__name__ in ("BSplineCurve", "BezierCurve") else (0 if type(c).__name__ in ("Line", "Circle", "LineSegment", "ArcOfCircle") else 100)
            else:
                total += 100
        except Exception:
            total += 100
        if stop is not None and total > stop:
            break
    return total


def _slow_key(o):
    try:
        return _key(o)[:-1]  # kind, counts and box: not the volume (it may be what is slow)
    except Exception:
        return None


def was_slow(doc_name, o, check):
    """Seconds check took on o's shape as it is now, when that was long;
    else None."""
    hit = _slow.get((doc_name, o.Name, check))
    if hit is None:
        return None
    if hit[0] != _slow_key(o):
        _slow.pop((doc_name, o.Name, check), None)
        return None
    return hit[1]


def timed(doc_name, o, check, fn):
    """fn() run and timed; one that took long is remembered for o's shape."""
    t = time.time()
    try:
        return fn()
    finally:
        took = time.time() - t
        if took >= SLOW_S:
            _slow[(doc_name, o.Name, check)] = (_slow_key(o), round(took, 1))
            if len(_slow) > 500:
                for old in list(_slow)[:100]:
                    _slow.pop(old, None)


# ---- the readings -----------------------------------------------------------------------

def _label(o):
    try:
        return o.Label
    except Exception:
        return str(getattr(o, "Name", "?"))


def _short(o):
    try:
        return o.TypeId.split("::")[-1]
    except Exception:
        return "object"


def _geo_kind(g):
    n = type(g).__name__
    return {"LineSegment": "line", "ArcOfCircle": "arc", "Circle": "circle", "Point": "point", "Ellipse": "ellipse",
            "ArcOfEllipse": "elliptical arc", "BSplineCurve": "spline", "ArcOfHyperbola": "hyperbola arc",
            "ArcOfParabola": "parabola arc"}.get(n, n.lower())


def free_geometry(sk, cap=MAX_LIST):
    """(the geometry the solver can still move, in words; how many in all):
    FreeCAD's getGeometryWithDependentParameters, the list its own "select
    unconstrained DoF" command uses. A whole edge named once, else its
    points."""
    try:
        pairs = list(sk.getGeometryWithDependentParameters())
    except Exception:
        return [], 0
    try:
        geos = sk.Geometry
    except Exception:
        geos = []
    by = {}
    for g, p in pairs:
        by.setdefault(int(g), set()).add(int(p))
    # Grouped by what is free and of which kind, so a rectangle's four
    # corners read "the start of lines 0, 1, 2, 3", not four phrases.
    groups, order = {}, []
    for g in sorted(by):
        kind = _geo_kind(geos[g]) if 0 <= g < len(geos) else "geometry"
        ps = by[g]
        # A circle or a point has no ends: whichever of its parameters the
        # solver names, it is the thing itself that is free.
        whole = 0 in ps or len(ps) > 1 or kind in ("circle", "point", "ellipse")
        where = "" if whole else POS.get(next(iter(ps)), "")
        key = (where, kind)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(g)
    out = []
    for where, kind in order:
        ids = groups[(where, kind)]
        shown = ", ".join(str(i) for i in ids[:8]) + (" …" if len(ids) > 8 else "")
        out.append(f"{where}{kind}{'s' if len(ids) > 1 else ''} {shown}")
    return out[:cap], len(out)


def _open_profiles(sk):
    """How many of a sketch's wires are open; None when it cannot be read."""
    try:
        sh = sk.Shape
        return 0 if sh.isNull() else sum(1 for w in sh.Wires if not w.isClosed())
    except Exception:
        return None


def sketch_sig(sk):
    """A sketch's reading as one value to compare: degrees of freedom, the
    solver's four lists, whether it is empty, open profiles. Two equal ones
    make the same line in the verdict (bar which geometry is free)."""
    def ids(prop):
        try:
            return tuple(int(i) for i in (getattr(sk, prop, None) or ()))
        except Exception:
            return ()

    try:
        dof = int(sk.DoF)
    except Exception:
        dof = None
    try:
        empty = int(sk.GeometryCount) == 0
    except Exception:
        empty = None
    return (dof, ids("ConflictingConstraints"), ids("RedundantConstraints"), ids("PartiallyRedundantConstraints"),
            ids("MalformedConstraints"), empty, _open_profiles(sk))


def _sketch_sigs(doc):
    """{sketch name: sketch_sig} before the call, for up to SKETCHES_BEFORE
    sketches (attributes and a wire count each: cheap). A sketch past that
    has no reading from before and is read as a new one."""
    out = {}
    try:
        for o in doc.Objects:
            if getattr(o, "TypeId", "") != "Sketcher::SketchObject":
                continue
            if len(out) >= SKETCHES_BEFORE:
                break
            try:
                out[o.Name] = sketch_sig(o)
            except Exception:
                continue
    except Exception:
        pass
    return out


def tool_bit_sketch(sk):
    """Whether a sketch is part of a CAM tool bit's own model: FreeCAD's
    tool bit (Path.Tool.toolbit) keeps the bit's parametric body in its
    BitBody link, copied in from the bit's shape file, sketches and all.
    Nobody designs in it, so its solver state is no news."""
    try:
        holders = []
        try:
            g = sk.getParentGeoFeatureGroup()
        except Exception:
            g = None
        if g is not None:
            holders.append(g)
        for p in getattr(sk, "InList", None) or []:
            if getattr(p, "TypeId", "") == "PartDesign::Body" and p not in holders:
                holders.append(p)
        for body in holders:
            for user in getattr(body, "InList", None) or []:
                try:
                    if "BitBody" in user.PropertiesList and user.BitBody is body:
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def sketch_tool(tool):
    """Whether a call is a sketch tool's own (its group or its name says
    so): after one, the sketches it recomputed are read out as they stand,
    "fully constrained" included; after any other, only what changed."""
    try:
        return str(getattr(tool, "group", "") or "") == "sketch" or str(getattr(tool, "name", "") or "").startswith("sketch_")
    except Exception:
        return False


def sketch_reading(sk):
    """One sketch after its recompute, from the solver's own results (no new
    solve): { sketch, dof, free, conflicting, redundant, partiallyRedundant,
    malformed, open, line, red }."""
    r = {"sketch": _label(sk)}
    lists = {}
    for key, prop in (("conflicting", "ConflictingConstraints"), ("redundant", "RedundantConstraints"),
                      ("partiallyRedundant", "PartiallyRedundantConstraints"), ("malformed", "MalformedConstraints")):
        try:
            v = [int(i) - 1 for i in (getattr(sk, prop, None) or [])]  # FreeCAD counts them from 1
        except Exception:
            v = []
        if v:
            lists[key] = v
    try:
        dof = int(sk.DoF)
    except Exception:
        dof = None
    try:
        n_geo = int(sk.GeometryCount)
    except Exception:
        n_geo = 0
    red = bool(lists.get("conflicting") or lists.get("redundant") or lists.get("malformed"))
    words = []
    if red:
        for key in ("conflicting", "redundant", "malformed"):
            if key in lists:
                ids = ", ".join(f"#{i}" for i in lists[key][:MAX_LIST]) + (" …" if len(lists[key]) > MAX_LIST else "")
                words.append(f"{key} constraints {ids}")
        r["todo"] = "sketch_state names each constraint; sketch_edit { deleteConstraints } removes one"
    elif n_geo == 0:
        words.append("empty")
    elif dof == 0:
        words.append("fully constrained")
    elif dof is not None:
        free, n = (free_geometry(sk) if n_geo <= SKETCH_GEO else ([], 0))
        r["dof"] = dof
        if free:
            r["free"] = free
            words.append(f"{dof} DoF left on {', '.join(free)}{' …' if n > len(free) else ''}")
        else:
            words.append(f"{dof} DoF left")
    r.update(lists)
    try:
        sh = sk.Shape
        wires = [] if sh.isNull() else sh.Wires
        n_open = sum(1 for w in wires if not w.isClosed())
        if n_open:
            r["open"] = n_open
            words.append(f"{n_open} open profile{'s' if n_open != 1 else ''}")
    except Exception:
        pass
    r["red"] = red
    r["amber"] = not red and (bool(r.get("dof")) or bool(r.get("open")))
    r["state"] = "empty" if words == ["empty"] else ("fully constrained" if words == ["fully constrained"] else None)
    r["line"] = f"{r['sketch']}: " + "; ".join(words) if words else None
    return r


def _faces(sh):
    try:
        return sh.countElement("Face")
    except Exception:
        try:
            return len(sh.Faces)
        except Exception:
            return 0


def _in_full(o):
    return f'body_check {{ body: "{_label(o)}" }} runs it in full (as a job: background: true)'


def shape_reading(o, deadline, doc_name=""):
    """One part's shape after its recompute: valid, closed, solids, and
    self-intersection when it is small enough to check in time. What is
    not checked is named (unchecked), never passed over."""
    r = {"object": _label(o), "red": False}
    try:
        sh = o.Shape
    except Exception:
        return None
    if sh is None or sh.isNull():
        r.update(red=True, line=f"{r['object']}: empty shape", todo="the step made nothing: check its inputs, or history_undo")
        return r
    n = _faces(sh)
    words, skipped = [], []
    try:
        solids = sh.Solids
    except Exception:
        solids = []
    slow_valid = was_slow(doc_name, o, "valid")
    if n > FACES_VALID:
        skipped.append(f"validity ({n} faces, over {FACES_VALID}): body_check as a job")
    elif slow_valid is not None:
        skipped.append(f"validity (it took {slow_valid:g} s on this shape before): {_in_full(o)}")
    else:
        valid = bool(timed(doc_name, o, "valid", sh.isValid))
        words.append("valid" if valid else "NOT valid")
        if not valid:
            r["red"] = True
            r["todo"] = "the last step left a broken shape: history_undo and rebuild it another way; body_check says where"
    if solids:
        try:
            closed = all(s.isClosed() for s in sh.Shells)
        except Exception:
            closed = None
        if closed is not None:
            words.append("closed" if closed else "NOT closed")
            if not closed:
                r["red"] = True
                r.setdefault("todo", "open edges: the solid has no inside — body_check names them")
        if len(solids) != 1:
            # FreeCAD 1.1 allows a Body of several solids (AllowCompound, on
            # by default), so it cannot say whether they are meant: yellow,
            # never passed over.
            allowed = False
            try:
                allowed = bool(getattr(o, "AllowCompound", False)) and o.TypeId == "PartDesign::Body"
            except Exception:
                pass
            words.append(f"{len(solids)} solids" + (" (AllowCompound)" if allowed else ""))
            r["solids"] = len(solids)
            r["amber"] = True
        else:
            words.append("1 solid")
        try:
            vol = float(sh.Volume)
        except Exception:
            vol = None
        if vol is not None and vol <= 1e-9:
            words.append(f"volume {vol:.4g} mm³: inside out")
            r["red"] = True
            r.setdefault("todo", "a solid with no positive volume is turned inside out or broken: part_fix { op: \"reverse\" } turns it, or history_undo")
    else:
        try:
            kind = sh.ShapeType.lower()
        except Exception:
            kind = "shape"
        words.append(f"no solid ({kind})")
        r["amber"] = True
    slow_self = was_slow(doc_name, o, "check") if n <= FACES_SELF and not r["red"] else None
    if n <= FACES_SELF and not r["red"] and time.time() >= deadline:
        skipped.append(f"FreeCAD's geometry check (out of time): {_in_full(o)}")
    elif n <= FACES_SELF and not r["red"] and slow_self is not None:
        skipped.append(f"FreeCAD's geometry check (it took {slow_self:g} s on this shape before): {_in_full(o)}")
    elif n <= FACES_SELF and not r["red"] and freeform(sh, FREEFORM_MAX) > FREEFORM_MAX:
        skipped.append(f"FreeCAD's geometry check (large free-form faces, a sweep or a loft: its self-intersection pass can take minutes): {_in_full(o)}")
    elif n <= FACES_SELF and not r["red"]:
        try:
            from . import geometry as geo

            # Several solids are checked one by one: together, solids that
            # touch read as one shape cutting itself.
            ok, said = True, []

            def run_check():
                good, words = True, []
                for piece in (solids if len(solids) > 1 else [sh]):
                    k, lines_ = geo.core_check(piece)
                    if k is False:
                        good, words = False, words + lines_
                return good, words

            ok, said = timed(doc_name, o, "check", run_check)
            said = [ln for ln in said if "found the following errors" not in ln]
            if ok is False and geo.soft_bop(said):
                # A tolerance finding on a shape BRepCheck calls valid (a
                # curve off its surface where two features meet): body_check
                # words it as a warning, and so it is no red here.
                r["amber"] = True
                words.append("a tolerance finding in FreeCAD's geometry check (body_check says where)")
            elif ok is False:
                words.append(f"FreeCAD's geometry check: {(said[0] if said else 'failed')[:120]}")
                r["red"] = True
                r["todo"] = "body_check names the faces; change the step that made them (a smaller fillet, a profile that does not cross itself)"
        except Exception:
            pass
    elif n > FACES_SELF and n <= FACES_VALID:
        skipped.append(f"FreeCAD's geometry check ({n} faces, over {FACES_SELF})")
    if skipped:
        r["unchecked"] = skipped
    r["line"] = f"{r['object']}: " + ", ".join(words)
    return r


def _boxes_meet(a, b):
    try:
        return a.isValid() and b.isValid() and a.intersect(b)
    except Exception:
        return False


def _in_container(o, kinds=("Assembly::AssemblyObject",)):
    try:
        return any(p.TypeId in kinds for p in o.InListRecursive)
    except Exception:
        return False


def _visible(o):
    try:
        v = o.ViewObject
        return True if v is None else bool(v.Visibility)
    except Exception:
        return True


def _holds_others(o):
    """A container whose shape is its members' (a BIM level or building, a
    group with a shape), or reinforcement, which lies inside its concrete on
    purpose: no overlap of theirs is a finding (a storey "interfered" with
    the roof it holds, the slab's bars with the house)."""
    try:
        if getattr(o, "Group", None):
            return True
        return str(getattr(o, "IfcType", "")) in ("Reinforcing Bar", "Reinforcing Mesh", "Building Storey", "Building", "Site")
    except Exception:
        return False


def overlaps(changed, parts, deadline):
    """Changed parts against the other visible parts: [{ a, b, volume, box
    [x, y, z] mm, line }], and what was left unchecked. Parts inside an
    assembly are left to asm_check, which knows a screw's thread from an
    overlap."""
    out, skipped, tried = [], [], 0
    done = set()
    weights = {}

    def weight(o, sh):
        if o.Name not in weights:
            weights[o.Name] = freeform(sh, FREEFORM_MAX)
        return weights[o.Name]

    for a in changed:
        try:
            sa = a.Shape
            if sa.isNull() or not sa.Solids or _in_container(a) or _holds_others(a):
                continue
            ba, na = sa.BoundBox, _faces(sa)
        except Exception:
            continue
        for b in parts:
            if b is a or (b.Name, a.Name) in done:
                continue
            done.add((a.Name, b.Name))
            try:
                sb = b.Shape
                if sb.isNull() or not sb.Solids or not _visible(b) or _in_container(b) or _holds_others(b):
                    continue
                # Made from one another (a copy, a filter's pieces, a mesh
                # made solid): they lie where their source does.
                if b in a.OutListRecursive or b in a.InListRecursive:
                    continue
                if not _boxes_meet(ba, sb.BoundBox):
                    continue
                if na > FACES_OVERLAP or _faces(sb) > FACES_OVERLAP:
                    skipped.append(f"{_label(a)} × {_label(b)} (over {FACES_OVERLAP} faces)")
                    continue
                if tried >= MAX_PAIRS or time.time() > deadline:
                    skipped.append(f"{_label(a)} × {_label(b)} (out of time)")
                    continue
                # A boolean on large free-form faces (a swept spring) can
                # take many seconds and cannot be stopped: left to clearance.
                if weight(a, sa) + weight(b, sb) > FREEFORM_MAX:
                    skipped.append(f"{_label(a)} × {_label(b)} (large free-form faces)")
                    continue
                tried += 1
                c = sa.common(sb)
                vol = 0.0 if c.isNull() else float(c.Volume)
                if vol > 1e-3:
                    bb = c.BoundBox
                    box = [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)]
                    out.append({"a": _label(a), "b": _label(b), "volume": round(vol, 2), "box": box,
                                "line": f"{_label(a)} interferes with {_label(b)}: {round(vol, 2):g} mm³ in a box {box[0]:g} × {box[1]:g} × {box[2]:g} mm"})
            except Exception:
                continue
    return out, skipped


def window():
    """The window's own warnings (GUI only, read on its thread): { dialog,
    task: [labels that warn], status }. {} headless or when nothing can be
    read."""
    out = {}
    try:
        import FreeCAD

        if not FreeCAD.GuiUp:
            return out
        import FreeCADGui
        from PySide import QtWidgets

        mw = FreeCADGui.getMainWindow()
        if mw is None:
            return out
        try:
            modal = QtWidgets.QApplication.activeModalWidget()
            if modal is not None and modal.isVisible():
                out["dialog"] = (modal.windowTitle() or modal.metaObject().className())[:80]
        except Exception:
            pass
        try:
            if FreeCADGui.Control.activeDialog():
                warn = []
                for w in mw.findChildren(QtWidgets.QWidget):
                    if w.metaObject().className() == "Gui::TaskView::TaskView" and w.isVisible():
                        for lab in w.findChildren(QtWidgets.QLabel):
                            if not lab.isVisible():
                                continue
                            t = re.sub(r"<[^>]+>", " ", lab.text() or "")
                            t = re.sub(r"\s+", " ", t).strip()
                            if t and len(t) < 200 and TASK_WORDS.search(t) and t not in warn:
                                warn.append(t)
                        break
                if warn:
                    out["task"] = warn[:4]
        except Exception:
            pass
        try:
            msg = (mw.statusBar().currentMessage() or "").strip()
            # Agent Link's own echo lines are not FreeCAD's news.
            if msg and not msg.startswith("Agent") and TASK_WORDS.search(msg):
                out["status"] = msg[:160]
        except Exception:
            pass
    except Exception:
        pass
    return out


# ---- after the call ---------------------------------------------------------------------

def _close(m):
    """m's mark closed: (document, object) names seen since it opened."""
    if not m or not m.get("open"):
        return set()
    m["open"] = False
    _marks[:] = [x for x in _marks if x is not m]
    try:
        from . import changes

        m["events"], m["whole"] = changes.close(m.get("watch"))
    except Exception:
        m["events"], m["whole"] = [], False
    seen = set(_seen["log"][m.get("since", 0):])
    _seen["depth"] = max(0, _seen["depth"] - 1)
    if _seen["depth"] == 0:
        del _seen["log"][:]
    return seen


def _input(o, prop):
    """Whether a change of o's property prop marks o for a recompute:
    FreeCAD touches an object on a change of any property that is not an
    Output one (FreeCAD 1.1 source: src/App/DocumentObject.cpp, onChanged).
    True when it cannot be read."""
    try:
        if "Output" in (o.getPropertyStatus(prop) or []) or "Output" in (o.getTypeOfProperty(prop) or []):
            return False
    except Exception:
        pass
    return True


def waiting(m, doc_name):
    """The names of doc_name's objects the call itself left waiting for a
    recompute: made and never recomputed, or changed (an input property)
    after their last recompute in the call. None when the call was not
    seen whole — then an object the call recomputed is taken as up to date,
    as before.

    Why the order matters: a document's recompute signals each object and
    then clears its mark (Document::recompute: signalRecomputedObject,
    purgeTouched), so a mark still there afterwards was set later; one
    object's own recompute (Document::recomputeFeature) signals and leaves
    the mark, and that object is up to date."""
    if not m.get("whole"):
        return None
    try:
        from . import changes

        since, recomputed = changes.after_recompute(m.get("events") or [], doc_name)
    except Exception:
        return None
    return {"since": since, "recomputed": recomputed}


def _waits(o, w):
    """Whether o, which the call made or recomputed and which is still
    marked touched, waits for a recompute (w: waiting()'s)."""
    if w is None or o.Name not in w["since"]:
        return False
    if o.Name not in w["recomputed"]:
        return True  # made by the call and never recomputed
    if _in_container(o):
        return False  # a part an assembly's solver placed: the assembly's own way
    return any(_input(o, p) for p in w["since"][o.Name])


def check(session, tool, m):
    """The health of the document after a changing call, or None when the
    call recomputed nothing and nothing is red (attach() then says "nothing
    red", so every changing call's answer carries a health). m: mark()'s."""
    if m is None:
        return None
    seen_now = _close(m)
    t0 = time.time()
    deadline = t0 + BUDGET_S
    doc = getattr(session, "doc", None)
    if doc is None:
        return None
    try:
        doc_name = doc.Name
        objs = list(doc.Objects)
    except Exception:
        return None
    by_name = {o.Name: o for o in objs}
    same_doc = doc_name == m.get("doc")
    before_bad = m.get("bad", {}) if same_doc else {}
    names0 = m.get("names") if same_doc else None

    touched_names = {n for d, n in seen_now if d == doc_name}
    if names0 is not None:
        touched_names |= {n for n in by_name if n not in names0}
    changed = [o for o in objs if o.Name in touched_names]  # in the document's order
    left_waiting = waiting(m, doc_name)

    h, lines, todos, unchecked = {}, [], [], []
    red = False
    by, lap = {}, [time.time()]

    def took(name):
        now = time.time()
        by[name] = by.get(name, 0) + int((now - lap[0]) * 1000)
        lap[0] = now

    # 1. State flags and recompute errors.
    errors, pending = [], []
    if len(objs) <= MAX_OBJECTS:
        for o in objs:
            why = _failing(o)
            if why:
                errors.append({"object": _label(o), "type": _short(o), "error": why[:200], **({} if o.Name in before_bad else {"new": True})})
            else:
                try:
                    # Still touched after the call recomputed it is that
                    # object's own way (some Python features, links moved by
                    # an assembly's solver): another recompute changes
                    # nothing, so it is not asked for. One the call changed
                    # after its last recompute, or made and never
                    # recomputed, does wait — said now, not by the next
                    # call's reading (a drawing's template and dimensions
                    # showed one call late).
                    if "Touched" in o.State and not _holds_only(o) and (o.Name not in touched_names or _waits(o, left_waiting)):
                        pending.append(_label(o))
                except Exception:
                    pass
    else:
        unchecked.append(f"State flags ({len(objs)} objects, over {MAX_OBJECTS}): recompute lists the failing ones")
    if errors:
        red = True
        new = [e for e in errors if e.get("new")]
        old = len(errors) - len(new)
        show = (new or errors)[:MAX_LIST]
        if new:
            h["errors"] = show  # failures that were there before are named, not listed again each call
            lines.append(f"{len(new)} object{'s' if len(new) != 1 else ''} failed to recompute: "
                         + "; ".join(f"{e['object']} ({e['error'][:80]})" for e in show[:3]) + (" …" if len(new) > 3 else "")
                         + (f" — {old} more were failing before this call" if old else ""))
            todos.append("fix the input of the first failed object (those after it fail because of it), or history_undo")
        else:
            lines.append(f"{old} object{'s' if old != 1 else ''} still failing from before this call: " + ", ".join(e["object"] for e in show[:3]) + (" …" if old > 3 else ""))
            todos.append(HEALTH_TODOS["failing"])
    if pending:
        h["needRecompute"] = pending[:MAX_LIST] + ([f"… {len(pending) - MAX_LIST} more"] if len(pending) > MAX_LIST else [])
        lines.append(f"{len(pending)} object{'s' if len(pending) != 1 else ''} not recomputed yet")
        todos.append("recompute brings them up to date")

    failing_now = {e["object"] for e in errors}
    took("state")

    # 2. Sketches the call recomputed. Red ones are all named, yellow ones up
    # to MAX_AMBER, and the clean ones named when few and counted when many.
    amber, fine = [], []
    sketches = [o for o in changed if getattr(o, "TypeId", "") == "Sketcher::SketchObject" and _label(o) not in failing_now]
    # News only (live: every sheet_format repeated "NutSketch: 1 DoF left…",
    # and cam_tool_add said "Sketch001: fully constrained" of the bit's own
    # sketch). A red reading is always said.
    sigs0 = (m.get("sketches") or {}) if same_doc else {}
    own_call = sketch_tool(tool)
    for sk in sketches[:MAX_SKETCHES]:
        try:
            if tool_bit_sketch(sk):
                continue  # a CAM tool bit's own model
            r = sketch_reading(sk)
            was = sigs0.get(sk.Name)
            same = was is not None and was == sketch_sig(sk)
        except Exception:
            continue
        if not r["red"] and not own_call:
            if same:
                continue  # recomputed, and reads as it did before the call
            if not r.get("amber") and was is None:
                continue  # made by the call, with nothing to do on it
        if r["red"]:
            red = True
            lines.append(r["line"])
            todos.append(r.get("todo"))
            h.setdefault("sketches", []).append({k: r[k] for k in ("sketch", "conflicting", "redundant", "partiallyRedundant", "malformed") if k in r})
        elif r.get("amber"):
            amber.append(r["line"])
        elif r.get("line"):
            fine.append(("sketch", r["state"] or "ok", r["line"]))
    if len(sketches) > MAX_SKETCHES:
        unchecked.append(f"{len(sketches) - MAX_SKETCHES} more sketches: sketch_state")

    took("sketches")

    # 3. Shapes the call recomputed: the parts they belong to.
    try:
        from .tools import Session

        parts = list(Session.bodies_in(doc))
    except Exception:
        parts = []
    part_names = {p.Name for p in parts}
    # A part is read when it was itself recomputed (a Body is, when its tip
    # changes): a sketch added to a body leaves the body's solid as it was,
    # and its reading is not repeated.
    shapes0 = m.get("shapes") or {} if same_doc else {}
    todo_parts = []
    for o in changed:
        try:
            if o.Name not in part_names or o.TypeId in CONTAINERS or _label(o) in failing_now:
                continue
            if o.Name in shapes0 and shapes0[o.Name] == _key_fresh(doc_name, o):
                continue  # recomputed, and the same shape as before the call
        except Exception:
            continue
        todo_parts.append(o)
    late = 0
    for p in todo_parts[:MAX_SHAPES]:
        if time.time() > deadline:
            late += 1
            continue
        try:
            r = shape_reading(p, deadline, doc_name)
        except Exception:
            r = None
        if not r:
            continue
        if r["red"]:
            red = True
            lines.append(r["line"])
            todos.append(r.get("todo"))
        elif r.get("amber"):
            amber.append(r["line"])
        else:
            fine.append(("part", r["line"].split(": ", 1)[1], r["line"]))
        unchecked += [f"{r['object']}: {u}" for u in r.get("unchecked", [])]
    late += max(0, len(todo_parts) - MAX_SHAPES)
    if late:
        unchecked.append(f"{late} more part{'s' if late != 1 else ''}' shapes (out of time): body_check")

    took("shapes")
    lines += amber[:MAX_AMBER]
    if len(amber) > MAX_AMBER:
        lines.append(f"{len(amber) - MAX_AMBER} more with freedom left or several solids (sketch_state, body_check)")
    if len(fine) <= 2:
        lines += [x[2] for x in fine]
    else:
        tally = {}
        for kind, state, _line in fine:
            tally[(kind, state)] = tally.get((kind, state), 0) + 1
        plural = {"sketch": "sketches", "part": "parts"}
        lines += [f"{n} {plural[kind] if n != 1 else kind} {state}" for (kind, state), n in tally.items() if state != "empty"]

    # 4. Interference between the changed parts and the others.
    # Yellow, not red: in Part work a body laid over another is the next
    # boolean's tool, and only the person or agent knows which it is. An
    # assembly's overlaps are asm_check's, which knows a thread from a clash.
    if todo_parts and len(parts) > 1:
        try:
            hits, skipped = overlaps(todo_parts[:MAX_SHAPES], parts, min(deadline, time.time() + OVERLAP_S))
        except Exception:
            hits, skipped = [], []
        if hits:
            lines += [x["line"] for x in hits[:2]]
            if len(hits) > 2:
                lines.append(f"{len(hits) - 2} more overlaps")
            todos.append(HEALTH_TODOS["overlap"])
        if skipped:
            unchecked.append("interference of " + "; ".join(skipped[:3]) + (" …" if len(skipped) > 3 else "") + ": clearance")

    took("overlap")

    # 5. The families' own readings (assembly solver, CalculiX …).
    for _owner, fn in list(_extra):
        try:
            for x in fn(session, tool, changed) or []:
                if x.get("line"):
                    lines.append(str(x["line"])[:240])
                if x.get("red"):
                    red = True
                    if x.get("todo"):
                        todos.append(x["todo"])
        except Exception:
            continue

    took("families")

    # 6. The window.
    w = window()
    if w.get("dialog"):
        red = True
        lines.append(f"a dialog is open in the window: {w['dialog']}")
        todos.append("dialog_answer reads it and presses a button")
    # The Sketcher panel's solver message is the open sketch's standing
    # state, read above when the call recomputed it and no news when it did not.
    task = [t for t in (w.get("task") or []) if not SOLVER_LABEL.search(t)]
    if task:
        h["taskPanel"] = task
        lines.append("the task panel says: " + " | ".join(task[:2]))
    if w.get("status"):
        h["statusBar"] = w["status"]

    # 7. What the window is in the middle of, when that is news (a sketch
    # now open in edit, a task panel, another workbench): one short line,
    # nothing without a window (tools.next_hint).
    nxt = None
    try:
        import FreeCAD

        if FreeCAD.GuiUp:
            from .tools import next_hint

            nxt = next_hint(session, news_only=True)
    except Exception:
        nxt = None

    took("window")
    if not lines and not unchecked and not nxt:
        return None
    out = {"ok": not red, "verdict": "; ".join(lines) if lines else "nothing red"}
    if unchecked:
        # Said in the verdict too: a reading that left a check out is not
        # the same as one that ran it.
        out["verdict"] += f"; {len(unchecked)} check{'s' if len(unchecked) != 1 else ''} not run here (unchecked names {'them' if len(unchecked) != 1 else 'it'} and the tool that does)"
    if nxt:
        out["next"] = nxt
    todos = [t for i, t in enumerate(todos) if t and t not in todos[:i]]
    if todos:
        out["todo"] = "; ".join(todos[:3])
    out.update(h)
    if unchecked:
        out["unchecked"] = unchecked[:MAX_LIST]
    ms = int((time.time() - t0) * 1000)
    if ms >= 200:
        out["ms"] = ms
    if ms >= MS_BY:
        # Where a long check's time went: state (the objects' flags),
        # sketches, shapes (validity and FreeCAD's geometry check),
        # overlap, families (the add-ons' own readings), window (the
        # window's warnings and the next hint).
        out["msBy"] = {k: v for k, v in by.items() if v >= 20}
    return out


def attach(session, tool, m, out):
    """check() put onto a tool's answer as "health" (a dict answer only; an
    answer that already carries one keeps it): always there after a
    changing call while the check is on — "nothing red" when there is
    nothing to say, and the reason when the check itself failed. Never
    raises."""
    try:
        if m is None or not isinstance(out, dict) or "health" in out:
            _close(m)
            return out
        h = check(session, tool, m)
        # Nothing recomputed and nothing red is said too: an answer of a
        # changing call with no health at all read as a check that did not
        # run (a drawing with a section, live).
        out["health"] = h if h is not None else {"ok": True, "verdict": "nothing red"}
    except Exception as e:
        _close(m)
        try:
            out["health"] = {"ok": None, "verdict": f"the health check did not run ({type(e).__name__}: {str(e)[:120]}): recompute lists what is failing; body_check and sketch_state read the result"}
        except Exception:
            pass
    return out


def drop(m):
    """A mark whose call was refused: closed without a reading."""
    try:
        _close(m)
    except Exception:
        pass


def note_report(body, lines):
    """New Report view problem lines counted in the verdict of an answer in
    hand (they come back whole as "report")."""
    try:
        n = len(lines or [])
        h = body.get("health")
        if n and isinstance(h, dict):
            h["verdict"] = f"{h.get('verdict', '')}; {n} new Report view line{'s' if n != 1 else ''} (see report)".lstrip("; ")
    except Exception:
        pass

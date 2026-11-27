# SPDX-License-Identifier: LGPL-2.1-or-later
# The shared health check: what FreeCAD itself reports after a changing
# call, read from its own state (no screenshot) and returned with the answer
# as "health". Facts only (27 Nov): health.facts is one text of facts, each
# with its source first (recompute, state, solver, shape, Check Geometry,
# measured, window, or a family's name). There is no ok, no verdict, no
# todo and no advice: nothing in it grades the result.
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
#     not what was last said (agentlink/nexthint.py);
#
# One place runs it (protocol.Server._call, round every changing tool), so a
# tool gets it without doing anything. It only reads; it has a time budget
# and size limits and says what it left unchecked instead of going over
# them; and nothing it does can fail the call it follows.

import os
import re
import time

# What health.facts says when no fact is news: the state pass ran on every
# object and FreeCAD reports no recompute error.
NOTHING = "recompute: FreeCAD reports no recompute error"
# What health.facts says when the check did not read the document: never
# NOTHING for a pass that did not run (27 Nov review, A2).
NOT_READ = "health: not read"
# Whether the last check read a fault that FreeCAD reports (a recompute
# error, a shape that is not valid or not closed, conflicting, redundant or
# malformed constraints, an open dialog): a repeated reading with one is
# never left out as "nothing new" (agentlink/once.py).
_last = {"fault": False}


def last_fault():
    return bool(_last.get("fault"))


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
                more = len(lists[key]) - MAX_LIST
                ids = ", ".join(f"#{i}" for i in lists[key][:MAX_LIST]) + (f" and {more} more ({len(lists[key])} in all)" if more > 0 else "")
                words.append(f"{key} constraints {ids}")
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
        elif n_geo > SKETCH_GEO:
            # a limit that is used is said: the free geometry is not read
            words.append(f"{dof} DoF left (the free geometry is not named: {n_geo} geometries, over {SKETCH_GEO})")
        else:
            words.append(f"{dof} DoF left")
    r.update(lists)
    try:
        sh = sk.Shape
        wires = [] if sh.isNull() else sh.Wires
        n_open = sum(1 for w in wires if not w.isClosed())
        if n_open:
            r["open"] = n_open
            words.append(f"{n_open} open wire{'s' if n_open != 1 else ''}")
    except Exception:
        pass
    r["red"] = red
    r["amber"] = not red and (bool(r.get("dof")) or bool(r.get("open")))
    r["state"] = "empty" if words == ["empty"] else ("fully constrained" if words == ["fully constrained"] else None)
    r["line"] = f"{r['sketch']}: " + "; ".join(words) if words else None
    if r.get("free") and words:
        # The same line without which geometry is free (sketch_state names it).
        r["short"] = f"{r['sketch']}: " + "; ".join(f"{dof} DoF left" if w.startswith(f"{dof} DoF left on ") else w for w in words)
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
    return f'body_check {{ body: "{_label(o)}" }} runs it in full'


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
        r.update(red=True, line=f"{r['object']}: empty shape")
        return r
    n = _faces(sh)
    words, skipped = [], []
    try:
        solids = sh.Solids
    except Exception:
        solids = []
    slow_valid = was_slow(doc_name, o, "valid")
    if n > FACES_VALID:
        skipped.append(f"validity ({n} faces, over {FACES_VALID})")
    elif slow_valid is not None:
        skipped.append(f"validity (it took {slow_valid:g} s on this shape before): {_in_full(o)}")
    else:
        valid = bool(timed(doc_name, o, "valid", sh.isValid))
        words.append("valid" if valid else "NOT valid")
        if not valid:
            r["red"] = True
    if solids:
        try:
            closed = all(s.isClosed() for s in sh.Shells)
        except Exception:
            closed = None
        if closed is not None:
            words.append("closed" if closed else "NOT closed")
            if not closed:
                r["red"] = True
        if len(solids) != 1:
            # FreeCAD 1.1 allows a Body of several solids (AllowCompound, on
            # by default): the count is said, with the property.
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
        if vol is not None and vol <= 0:
            words.append(f"volume {vol:.4g} mm³")  # the measured number: not above 0
            r["red"] = True
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
        skipped.append(f"FreeCAD's geometry check (free-form faces with more than {FREEFORM_MAX} control points): {_in_full(o)}")
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
            if ok is False:
                # FreeCAD's own words, whatever the finding (body_check gives
                # them all, with where).
                r["amber"] = True
                r["red"] = r["red"] or not geo.soft_bop(said)
                words.append(f"Check Geometry reports {(said[0] if said else 'an error')[:120]}" + (f" and {len(said) - 1} more" if len(said) > 1 else ""))
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
    """Shown in the window, or, headless (no view), not hidden by its own
    Visibility property: a fuse's hidden base was counted as a body there
    (live 18 Nov, 90: "CubeOverhang interferes with Cube")."""
    try:
        v = o.ViewObject
        if v is not None:
            return bool(v.Visibility)
    except Exception:
        pass
    try:
        return bool(getattr(o, "Visibility", True))
    except Exception:
        return True


def _holds_others(o):
    """A container whose shape is its members' (a BIM level or building, a
    group with a shape), or reinforcement, which lies inside its concrete on
    purpose: no overlap of theirs is a finding (a storey "interfered" with
    the roof it holds, the slab's bars with the house)."""
    try:
        # A PartDesign Body has a Group too (its features), but its shape is
        # its tip's solid: a part like any other (a box laid in it was not
        # found).
        if getattr(o, "Group", None) and getattr(o, "TypeId", "") != "PartDesign::Body":
            return True
        return str(getattr(o, "IfcType", "")) in ("Reinforcing Bar", "Reinforcing Mesh", "Building Storey", "Building", "Site")
    except Exception:
        return False


# Bicycle runs (21 Nov), finding 8: on 22 parts (two spoke bodies of 32
# solids) each asm_joint took 15-35 s and each pd_primitive 8-15 s in this
# pass. A pair is cut only when the changed part's box, MARGIN mm larger,
# meets the other's; a part of many solids is cut solid by solid, only the
# solids whose boxes meet; the other parts' shapes are kept between calls
# while their key (mark()'s) stays the same.
MARGIN = 0.01
_still = {}  # (document, part name) -> (key, { shape, box, faces, ok })


def _near(ba, bb, gap=MARGIN):
    try:
        return (ba.isValid() and bb.isValid() and ba.XMin - gap <= bb.XMax and bb.XMin - gap <= ba.XMax and ba.YMin - gap <= bb.YMax
                and bb.YMin - gap <= ba.YMax and ba.ZMin - gap <= bb.ZMax and bb.ZMin - gap <= ba.ZMax)
    except Exception:
        return _boxes_meet(ba, bb)


def _entry(o, doc_name=None, key=None, other=True):
    """A part's shape and what the pass needs of it, kept for the next call
    while key (its shape key, as mark() read it) is the same."""
    k = (doc_name, o.Name)
    if key is not None:
        hit = _still.get(k)
        if hit is not None and hit[0] == key:
            return hit[1]
    sh = o.Shape
    ok = not sh.isNull() and bool(sh.Solids) and not _in_container(o) and not _holds_others(o) and (_visible(o) if other else True)
    e = {"shape": sh, "box": sh.BoundBox if ok else None, "faces": _faces(sh) if ok else 0, "ok": ok}
    if key is not None:
        _still[k] = (key, e)
        if len(_still) > 500:
            for old in list(_still)[:100]:
                _still.pop(old, None)
    return e


def _common(sa, sb):
    """(volume, box of the common or None): a part of many solids is cut
    solid by solid, only where their boxes meet."""
    try:
        la, lb = list(sa.Solids), list(sb.Solids)
    except Exception:
        la, lb = [], []
    if len(la) <= 1 and len(lb) <= 1:
        c = sa.common(sb)
        return (0.0, None) if c.isNull() else (float(c.Volume), c.BoundBox)
    vol, box = 0.0, None
    for x in la:
        bx = x.BoundBox
        for y in lb:
            if not _near(bx, y.BoundBox):
                continue
            c = x.common(y)
            if c.isNull():
                continue
            v = float(c.Volume)
            if v > 1e-9:
                vol += v
                if box is None:
                    box = c.BoundBox
                else:
                    box.add(c.BoundBox)
    return vol, box


def overlaps(changed, parts, deadline, doc_name=None, keys=None, counts=None):
    """Changed parts against the other visible parts: [{ a, b, volume, box
    [x, y, z] mm, line }], and what was left unchecked. Parts inside an
    assembly are left to asm_check, which knows a screw's thread from an
    overlap. keys: { part name: its shape key } of the parts the call left
    as they were (their shapes are kept between calls, _still). counts: a
    dict that gets { checked, skipped }: pairs cut, pairs left out."""
    out, skipped, tried = [], [], 0
    done = set()
    weights = {}
    counts = {} if counts is None else counts
    counts.setdefault("checked", 0)
    counts.setdefault("skipped", 0)
    names = {o.Name for o in changed}

    def weight(o, sh):
        if o.Name not in weights:
            weights[o.Name] = freeform(sh, FREEFORM_MAX)
        return weights[o.Name]

    for a in changed:
        try:
            ea = _entry(a, other=False)
            if not ea["ok"]:
                counts["skipped"] += len(parts) - 1
                continue
            sa, ba, na = ea["shape"], ea["box"], ea["faces"]
        except Exception:
            continue
        for b in parts:
            if b is a or (b.Name, a.Name) in done:
                continue
            done.add((a.Name, b.Name))
            try:
                eb = _entry(b, doc_name, None if b.Name in names or keys is None else keys.get(b.Name))
                # Made from one another (a copy, a filter's pieces, a mesh
                # made solid): they lie where their source does.
                if not eb["ok"] or not _near(ba, eb["box"]) or b in a.OutListRecursive or b in a.InListRecursive:
                    counts["skipped"] += 1
                    continue
                sb = eb["shape"]
                if na > FACES_OVERLAP or eb["faces"] > FACES_OVERLAP:
                    skipped.append(f"{_label(a)} × {_label(b)} (over {FACES_OVERLAP} faces)")
                    counts["skipped"] += 1
                    continue
                if tried >= MAX_PAIRS:
                    skipped.append(f"{_label(a)} × {_label(b)} (the pass tests {MAX_PAIRS} pairs at most)")
                    counts["skipped"] += 1
                    continue
                if time.time() > deadline:
                    skipped.append(f"{_label(a)} × {_label(b)} (out of time: the pass has {OVERLAP_S:g} s)")
                    counts["skipped"] += 1
                    continue
                # A boolean on large free-form faces (a swept spring) can
                # take many seconds and cannot be stopped: left to clearance.
                if weight(a, sa) + weight(b, sb) > FREEFORM_MAX:
                    skipped.append(f"{_label(a)} × {_label(b)} (free-form faces with more than {FREEFORM_MAX} control points)")
                    counts["skipped"] += 1
                    continue
                tried += 1
                counts["checked"] += 1
                vol, bb = _common(sa, sb)
                if vol > 1e-3:
                    box = [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)] if bb is not None else [0, 0, 0]
                    out.append({"a": _label(a), "b": _label(b), "volume": round(vol, 2), "box": box,
                                "line": f"{_label(a)} and {_label(b)} share {round(vol, 2):g} mm³ in a box {box[0]:g} × {box[1]:g} × {box[2]:g} mm"})
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


def _targets(args):
    """The sketches a call names (its sketch or sketches argument), as
    given: labels or names. Empty when it names none."""
    out = set()
    try:
        for key in ("sketch", "sketches"):
            v = (args or {}).get(key)
            for x in (v if isinstance(v, (list, tuple)) else [v]):
                if isinstance(x, str) and x:
                    out.add(x)
    except Exception:
        pass
    return out


def check(session, tool, m, args=None):
    """The health of the document after a changing call, or None when the
    call has no fact that is news (attach() then gives NOTHING, so every
    changing call's answer carries a health). m: mark()'s.
    args: the call's arguments, when known: a sketch tool's call that names
    its sketch reads out that sketch, and the others only when they changed."""
    if m is None:
        return None
    seen_now = _close(m)
    t0 = time.time()
    deadline = t0 + BUDGET_S
    doc = getattr(session, "doc", None)
    if doc is None:
        _last["fault"] = False
        return {"facts": f"{NOT_READ} (no document)"}
    try:
        doc_name = doc.Name
        objs = list(doc.Objects)
    except Exception as e:
        _last["fault"] = False
        return {"facts": f"{NOT_READ} (the document's objects were not read: {type(e).__name__})"}
    by_name = {o.Name: o for o in objs}
    same_doc = doc_name == m.get("doc")
    before_bad = m.get("bad", {}) if same_doc else {}
    names0 = m.get("names") if same_doc else None

    touched_names = {n for d, n in seen_now if d == doc_name}
    if names0 is not None:
        touched_names |= {n for n in by_name if n not in names0}
    changed = [o for o in objs if o.Name in touched_names]  # in the document's order
    left_waiting = waiting(m, doc_name)

    h, lines, unchecked = {}, [], []
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
                # FreeCAD's own reason, word for word.
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
        unchecked.append(f"State flags ({len(objs)} objects, over {MAX_OBJECTS})")
        lines.append(f"recompute: not read ({len(objs)} objects, and the State flags are read for {MAX_OBJECTS} at most)")
    if errors:
        red = True
        new = [e for e in errors if e.get("new")]
        old = len(errors) - len(new)
        show = (new or errors)[:MAX_LIST]
        if new:
            h["errors"] = list(show)  # failures that were there before are named, not listed again each call
            lines.append(f"recompute: {len(new)} object{'s' if len(new) != 1 else ''} failed to recompute: "
                         + "; ".join(f"{e['object']} ({e['error'][:80]})" for e in show[:3]) + (f" and {len(new) - 3} more" if len(new) > 3 else "")
                         + (f" — {old} more were failing before this call" if old else ""))
        else:
            lines.append(f"recompute: {old} object{'s' if old != 1 else ''} still failing from before this call: " + ", ".join(e["object"] for e in show[:3]) + (f" and {old - 3} more" if old > 3 else ""))
    if pending:
        h["needRecompute"] = pending[:MAX_LIST] + ([f"… {len(pending) - MAX_LIST} more"] if len(pending) > MAX_LIST else [])
        lines.append(f"state: {len(pending)} object{'s' if len(pending) != 1 else ''} not recomputed yet (State Touched)")

    failing_now = {e["object"] for e in errors}
    took("state")

    # 2. Sketches the call recomputed. Red ones are all named, yellow ones up
    # to MAX_AMBER, and the clean ones named when few and counted when many.
    amber, fine = [], []
    amber_sketches = 0
    sketches = [o for o in changed if getattr(o, "TypeId", "") == "Sketcher::SketchObject" and _label(o) not in failing_now]
    # News only (live: every sheet_format repeated "NutSketch: 1 DoF left…",
    # and cam_tool_add said "Sketch001: fully constrained" of the bit's own
    # sketch). A red reading is always said.
    sigs0 = (m.get("sketches") or {}) if same_doc else {}
    own_call = sketch_tool(tool)
    # A sketch tool's call reads out the sketch it names as it stands; the
    # other sketches it recomputed only when they changed (24 Nov blind QA:
    # every sketch's freedom piled up in each verdict).
    named = _targets(args) if own_call else set()
    for sk in sketches[:MAX_SKETCHES]:
        try:
            if tool_bit_sketch(sk):
                continue  # a CAM tool bit's own model
            r = sketch_reading(sk)
            was = sigs0.get(sk.Name)
            same = was is not None and was == sketch_sig(sk)
        except Exception:
            continue
        mine = own_call and (not named or sk.Name in named or _label(sk) in named)
        if not r["red"] and not mine:
            if same:
                continue  # recomputed, and reads as it did before the call
            if not r.get("amber") and was is None:
                continue  # made by the call, with nothing to do on it
        if r["red"]:
            red = True
            lines.append("solver: " + r["line"])
            h.setdefault("sketches", []).append({k: r[k] for k in ("sketch", "conflicting", "redundant", "partiallyRedundant", "malformed") if k in r})
        elif r.get("amber"):
            # Which geometry is free, for the first sketch only: the others
            # say their count (sketch_state names it for each).
            amber.append("solver: " + (r["line"] if not amber_sketches else (r.get("short") or r["line"])))
            amber_sketches += 1
        elif r.get("line"):
            fine.append(("sketch", r["state"] or "read", "solver: " + r["line"]))
    if len(sketches) > MAX_SKETCHES:
        unchecked.append(f"{len(sketches) - MAX_SKETCHES} more sketches (the check reads {MAX_SKETCHES} at most)")

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
            lines.append("shape: " + r["line"])
        elif r.get("amber"):
            amber.append("shape: " + r["line"])
        else:
            fine.append(("part", r["line"].split(": ", 1)[1], "shape: " + r["line"]))
        unchecked += [f"{r['object']}: {u}" for u in r.get("unchecked", [])]
    over = max(0, len(todo_parts) - MAX_SHAPES)
    if late:
        unchecked.append(f"{late} more part{'s' if late != 1 else ''}' shapes (out of time: the check has {BUDGET_S:g} s)")
    if over:
        unchecked.append(f"{over} more part{'s' if over != 1 else ''}' shapes (the check reads {MAX_SHAPES} at most)")

    took("shapes")
    lines += amber[:MAX_AMBER]
    if len(amber) > MAX_AMBER:
        lines.append(f"{len(amber) - MAX_AMBER} more sketch or shape readings are not shown (this text shows {MAX_AMBER}; sketch_state and body_check read each)")
    if len(fine) <= 2:
        lines += [x[2] for x in fine]
    else:
        tally = {}
        for kind, state, _line in fine:
            tally[(kind, state)] = tally.get((kind, state), 0) + 1
        plural = {"sketch": "sketches", "part": "parts"}
        source = {"sketch": "solver", "part": "shape"}
        lines += [f"{source[kind]}: {n} {plural[kind] if n != 1 else kind} {state}" for (kind, state), n in tally.items() if state != "empty"]

    # 4. The volume the changed parts share with the others: a measured
    # fact, with no word on whether it is meant. An assembly's overlaps are
    # asm_check's.
    pair_counts = {}
    if todo_parts and len(parts) > 1:
        try:
            hits, skipped = overlaps(todo_parts[:MAX_SHAPES], parts, min(deadline, time.time() + OVERLAP_S), doc_name,
                                    {n: k for n, k in shapes0.items() if n not in touched_names}, pair_counts)
        except Exception:
            hits, skipped = [], []
        if hits:
            lines += ["measured: " + x["line"] for x in hits[:2]]
            if len(hits) > 2:
                lines.append(f"measured: {len(hits) - 2} more pairs of parts share volume (this text shows 2)")
        if skipped:
            unchecked.append("shared volume of " + "; ".join(skipped[:3]) + (f" and {len(skipped) - 3} more pairs" if len(skipped) > 3 else ""))

    took("overlap")

    # 5. The families' own readings (assembly solver, CalculiX …).
    for _owner, fn in list(_extra):
        try:
            for x in fn(session, tool, changed) or []:
                if x.get("line"):
                    lines.append(f"{_owner}: " + str(x["line"])[:240])
                if x.get("red"):
                    red = True
        except Exception:
            continue

    took("families")

    # 6. The window.
    w = window()
    if w.get("dialog"):
        red = True
        lines.append(f"window: a dialog is open: {w['dialog']}")
    # The Sketcher panel's solver message is the open sketch's standing
    # state, read above when the call recomputed it and no news when it did not.
    task = [t for t in (w.get("task") or []) if not SOLVER_LABEL.search(t)]
    if task:
        h["taskPanel"] = task
        lines.append("window: the task panel says: " + " | ".join(task[:2]) + (f" and {len(task) - 2} more (taskPanel)" if len(task) > 2 else ""))
    if w.get("status"):
        h["statusBar"] = w["status"]

    # 7. What the window is in the middle of, when that is news (a sketch
    # now open in edit, a task panel, another workbench): one short line,
    # nothing without a window (tools.next_hint).
    nxt = None
    try:
        import FreeCAD

        from . import nexthint

        if FreeCAD.GuiUp and nexthint.on():  # the NextHints switch
            from .tools import next_hint

            nxt = next_hint(session, news_only=True)
    except Exception:
        nxt = None

    took("window")

    _last["fault"] = bool(red)
    if not lines and not unchecked and not nxt:
        return None
    out = {"facts": "; ".join(lines) if lines else NOTHING}
    if nxt:
        out["next"] = nxt
    out.update(h)
    if unchecked:
        # Each check that a limit left out, with the limit: a reading that
        # left a check out is not the same as one that ran it.
        out["unchecked"] = unchecked[:MAX_LIST] + ([f"and {len(unchecked) - MAX_LIST} more checks not run"] if len(unchecked) > MAX_LIST else [])
    ms = int((time.time() - t0) * 1000)
    if ms >= 200:
        out["ms"] = ms
        if pair_counts.get("checked") or pair_counts.get("skipped"):
            # the interference pass: pairs cut, pairs left out (finding 8)
            out["overlapPairs"] = {"checked": pair_counts["checked"], "skipped": pair_counts["skipped"]}
    if ms >= MS_BY:
        # Where a long check's time went: state (the objects' flags),
        # sketches, shapes (validity and FreeCAD's geometry check),
        # overlap, families (the add-ons' own readings), window (the
        # window's warnings and the next hint).
        out["msBy"] = {k: v for k, v in by.items() if v >= 20}
    return out


def attach(session, tool, m, out, args=None):
    """check() put onto a tool's answer as "health" (a dict answer only; an
    answer that already carries one keeps it): always there after a
    changing call while the check is on — NOTHING when no fact is news, and
    the reason when the check itself failed. Never raises."""
    try:
        if m is None or not isinstance(out, dict) or "health" in out:
            _close(m)
            if m is not None and isinstance(out, dict):
                _timed(session, out.get("health"))  # a batch's own health
            return out
        h = check(session, tool, m, args)
        # No news is said too: an answer of a changing call with no health
        # at all read as a check that did not run (a drawing with a
        # section, live).
        if h is None:
            _last["fault"] = False
        out["health"] = _timed(session, h if h is not None else {"facts": NOTHING})
    except Exception as e:
        _close(m)
        try:
            _last["fault"] = True
            out["health"] = {"facts": f"the health check did not run ({type(e).__name__}: {str(e)[:120]})"}
        except Exception:
            pass
    return out


def _timed(session, h):
    """The run's time line at the end of health.facts when a time limit is
    set (agentlink/timelimit.py, AGENTLINK_TIME_LIMIT_MIN); a call inside a
    batch leaves it to the batch's own answer. Never raises."""
    try:
        if getattr(session, "batch_now", None) is None:
            from . import timelimit

            timelimit.mark_health(h)
    except Exception:
        pass
    return h


def time_on_batch(session, out):
    """The time line on the last health of a batch's answer (its calls'
    healths leave it out: _timed). Never raises."""
    try:
        rows = out.get("results") if isinstance(out, dict) else None
        if isinstance(out, dict) and isinstance(out.get("health"), dict):
            _timed(session, out["health"])
            return out
        for r in reversed(rows or []):
            h = (r.get("result") or {}).get("health") if isinstance(r, dict) and isinstance(r.get("result"), dict) else None
            if isinstance(h, dict):
                _timed(session, h)
                break
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
    """New Report view problem lines counted in health.facts of an answer in
    hand (they come back whole as "report")."""
    try:
        n = len(lines or [])
        h = body.get("health")
        if n and isinstance(h, dict):
            h["facts"] = f"{h.get('facts', '')}; report view: {n} new line{'s' if n != 1 else ''} (see report)".lstrip("; ")
    except Exception:
        pass

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
#     own lists), open profiles;
#   - shapes the call recomputed: valid, closed, solid count, self-
#     intersection (small shapes only), overlap with the other parts, with
#     the overlap's size;
#   - what a family adds for its own objects (register: the assembly
#     solver's status, CalculiX's lines);
#   - the window: an open dialog, the task panel's warning labels, the status
#     bar's text. New Report view lines come back as "report" beside it
#     (report_watch), and are counted in the verdict.
#
# One place runs it (protocol.Server._call, round every changing tool), so a
# tool gets it without doing anything. It only reads; it has a time budget
# and size limits and says what it left unchecked instead of going over
# them; and nothing it does can fail the call it follows.

import os
import re
import time

BUDGET_S = 1.5        # the whole check, after which the rest is named as unchecked
MAX_OBJECTS = 4000    # State flags are read on at most this many objects
MAX_LIST = 6          # entries per list in the answer
FACES_VALID = 3000    # isValid on shapes up to this many faces
FACES_SELF = 200      # the self-intersection check (BOP) up to this many faces
FACES_OVERLAP = 600   # a pair's common volume when both have at most this many
MAX_PAIRS = 24        # pairs tried for overlap
MAX_SKETCHES = 6
MAX_SHAPES = 4
SKETCH_GEO = 400      # a sketch's per-geometry freedom is read up to this many

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


def mark(session):
    """Before a changing call: the objects already failing (so the answer
    says which are new), and the observer armed."""
    if not enabled():
        return None
    doc = getattr(session, "doc", None)
    m = {"doc": None, "bad": {}, "t": time.time(), "watched": _watch(), "since": len(_seen["log"]), "open": True}
    _seen["depth"] += 1
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
    return m


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
        where = "" if (0 in ps or len(ps) > 1) else POS.get(next(iter(ps)), "")
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


def shape_reading(o, deadline):
    """One part's shape after its recompute: valid, closed, solids, and
    self-intersection when it is small enough to check in time."""
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
    if n > FACES_VALID:
        skipped.append(f"validity ({n} faces, over {FACES_VALID}): body_check as a job")
    else:
        valid = bool(sh.isValid())
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
            meant = False
            try:
                meant = bool(getattr(o, "AllowCompound", False)) and o.TypeId == "PartDesign::Body"
            except Exception:
                pass
            words.append(f"{len(solids)} solids" + (" (AllowCompound)" if meant else ""))
            r["solids"] = len(solids)
        else:
            words.append("1 solid")
    else:
        try:
            kind = sh.ShapeType.lower()
        except Exception:
            kind = "shape"
        words.append(f"no solid ({kind})")
    if n <= FACES_SELF and not r["red"] and time.time() < deadline:
        try:
            sh.check(True)  # the BOP check: raises with what it found
        except Exception as e:
            first = str(e).strip().splitlines()[0][:120] if str(e).strip() else "self-intersecting"
            words.append(f"geometry check: {first}")
            r["red"] = True
            r["todo"] = "the shape cuts or touches itself: change the step that made it (a smaller fillet, a profile that does not cross itself)"
    elif n > FACES_SELF and n <= FACES_VALID:
        skipped.append(f"self-intersection ({n} faces, over {FACES_SELF})")
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


def overlaps(changed, parts, deadline):
    """Changed parts against the other visible parts: [{ a, b, volume, box
    [x, y, z] mm, line }], and what was left unchecked. Parts inside an
    assembly are left to asm_check, which knows a screw's thread from an
    overlap."""
    out, skipped, tried = [], [], 0
    done = set()
    for a in changed:
        try:
            sa = a.Shape
            if sa.isNull() or not sa.Solids or _in_container(a):
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
                if sb.isNull() or not sb.Solids or not _visible(b) or _in_container(b):
                    continue
                if not _boxes_meet(ba, sb.BoundBox):
                    continue
                if na > FACES_OVERLAP or _faces(sb) > FACES_OVERLAP:
                    skipped.append(f"{_label(a)} × {_label(b)} (over {FACES_OVERLAP} faces)")
                    continue
                if tried >= MAX_PAIRS or time.time() > deadline:
                    skipped.append(f"{_label(a)} × {_label(b)} (out of time)")
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


def _body_of(o):
    """The PartDesign Body (or other part) an object belongs to, else the
    object."""
    try:
        for p in o.InList:
            if p.TypeId == "PartDesign::Body" and o in getattr(p, "Group", []):
                return p
    except Exception:
        pass
    return o


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
    seen = set(_seen["log"][m.get("since", 0):])
    _seen["depth"] = max(0, _seen["depth"] - 1)
    if _seen["depth"] == 0:
        del _seen["log"][:]
    return seen


def check(session, tool, m):
    """The health of the document after a changing call, or None when the
    call recomputed nothing and nothing is red. m: mark()'s."""
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
    changed = [by_name[n] for n in touched_names if n in by_name]

    h, lines, todos, unchecked = {}, [], [], []
    red = False

    # 1. State flags and recompute errors.
    errors, pending = [], []
    if len(objs) <= MAX_OBJECTS:
        for o in objs:
            why = _failing(o)
            if why:
                errors.append({"object": _label(o), "type": _short(o), "error": why[:200], **({} if o.Name in before_bad else {"new": True})})
            else:
                try:
                    if "Touched" in o.State:
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
        h["errors"] = show
        if new:
            lines.append(f"{len(new)} object{'s' if len(new) != 1 else ''} failed to recompute: "
                         + "; ".join(f"{e['object']} ({e['error'][:80]})" for e in show[:3]) + (" …" if len(new) > 3 else "")
                         + (f" — {old} more were failing before this call" if old else ""))
            todos.append("fix the input of the first failed object (those after it fail because of it), or history_undo")
        else:
            lines.append(f"{old} object{'s' if old != 1 else ''} still failing from before this call: " + ", ".join(e["object"] for e in show[:3]) + (" …" if old > 3 else ""))
            todos.append("recompute lists them with FreeCAD's reasons")
    if pending:
        h["needRecompute"] = pending[:MAX_LIST] + ([f"… {len(pending) - MAX_LIST} more"] if len(pending) > MAX_LIST else [])
        lines.append(f"{len(pending)} object{'s' if len(pending) != 1 else ''} not recomputed yet")
        todos.append("recompute brings them up to date")

    failing_now = {e["object"] for e in errors}

    # 2. Sketches the call recomputed.
    sketches = [o for o in changed if getattr(o, "TypeId", "") == "Sketcher::SketchObject" and _label(o) not in failing_now]
    read_sketch = False
    for sk in sketches[:MAX_SKETCHES]:
        try:
            r = sketch_reading(sk)
        except Exception:
            continue
        if r.get("line"):
            lines.append(r["line"])
        if r["red"]:
            red = True
            todos.append(r.get("todo"))
        # The lists only when something is red: the verdict's words carry
        # the freedom, and the sketch tools' own "state" the rest.
        if r["red"]:
            h.setdefault("sketches", []).append({k: r[k] for k in ("sketch", "conflicting", "redundant", "partiallyRedundant", "malformed") if k in r})
        read_sketch = True
    if len(sketches) > MAX_SKETCHES:
        unchecked.append(f"{len(sketches) - MAX_SKETCHES} more sketches: sketch_state")

    # 3. Shapes the call recomputed: the parts they belong to.
    try:
        from .tools import Session

        parts = list(Session.bodies_in(doc))
    except Exception:
        parts = []
    part_names = {p.Name for p in parts}
    todo_parts, seen = [], set()
    for o in changed:
        p = _body_of(o)
        try:
            if p.Name in seen or p.Name not in part_names or p.TypeId in CONTAINERS or _label(p) in failing_now:
                continue
        except Exception:
            continue
        seen.add(p.Name)
        todo_parts.append(p)
    for p in todo_parts[:MAX_SHAPES]:
        if time.time() > deadline:
            unchecked.append(f"{_label(p)}'s shape (out of time): body_check")
            continue
        try:
            r = shape_reading(p, deadline)
        except Exception:
            r = None
        if not r:
            continue
        lines.append(r["line"])
        if r["red"]:
            red = True
            todos.append(r.get("todo"))
        unchecked += [f"{r['object']}: {u}" for u in r.get("unchecked", [])]
    if len(todo_parts) > MAX_SHAPES:
        unchecked.append(f"{len(todo_parts) - MAX_SHAPES} more parts' shapes: body_check")

    # 4. Interference between the changed parts and the others.
    if todo_parts and len(parts) > 1:
        try:
            hits, skipped = overlaps(todo_parts[:MAX_SHAPES], parts, deadline)
        except Exception:
            hits, skipped = [], []
        if hits:
            red = True
            h["interference"] = [{k: x[k] for k in ("a", "b", "volume", "box")} for x in hits[:MAX_LIST]]
            lines += [x["line"] for x in hits[:3]]
            todos.append("move one part, or cut the overlap away (part_boolean cut) if it is not meant; clearance reads the gap")
        if skipped:
            unchecked.append("interference of " + "; ".join(skipped[:3]) + (" …" if len(skipped) > 3 else "") + ": clearance")

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

    # 6. The window.
    w = window()
    if w.get("dialog"):
        red = True
        lines.append(f"a dialog is open in the window: {w['dialog']}")
        todos.append("dialog_answer reads it and presses a button")
    task = w.get("task") or []
    if read_sketch:
        # The Sketcher panel's solver message says what the sketch reading
        # above already did.
        task = [t for t in task if not SOLVER_LABEL.search(t)]
    if task:
        h["taskPanel"] = task
        lines.append("the task panel says: " + " | ".join(task[:2]))
    if w.get("status"):
        h["statusBar"] = w["status"]

    if not lines and not unchecked:
        return None
    out = {"ok": not red, "verdict": "; ".join(lines) if lines else "nothing red"}
    todos = [t for i, t in enumerate(todos) if t and t not in todos[:i]]
    if todos:
        out["todo"] = "; ".join(todos[:3])
    out.update(h)
    if unchecked:
        out["unchecked"] = unchecked[:MAX_LIST]
    ms = int((time.time() - t0) * 1000)
    if ms >= 200:
        out["ms"] = ms
    return out


def attach(session, tool, m, out):
    """check() put onto a tool's answer as "health" (a dict answer only; an
    answer that already carries one keeps it). Never raises."""
    try:
        if m is None or not isinstance(out, dict) or "health" in out:
            _close(m)
            return out
        h = check(session, tool, m)
        if h is not None:
            out["health"] = h
    except Exception:
        _close(m)
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

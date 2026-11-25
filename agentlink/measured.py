# SPDX-License-Identifier: LGPL-2.1-or-later
"""Measure before claim (owner, 22 Nov 2026): an agent's own document is
saved only after its geometry was read since its last change.

Why: in "Done Is Not Correct" (build123d, 13 tasks), agents said done 98%
of the time and were silently wrong 14.1% of the time. A contract that the
final geometry is measured by the kernel before "done" cut that to 3.2%; the
contract, not the feedback, made the difference. One of our own runs said
pass at 25.7 mm³ off.

What the session keeps, per document (its own record, agentlink/docstates.py,
key "measured"):
  changed   the order number of the last change made in it
  step      the history step after that change (what the refusal names)
  measured  the order number of its last measure (or save)
  sigs      each body's numbers at that measure or save: { label: [volume,
            area, faces, solids, size, at] }; before the first change, the
            numbers as they were before it.

doc_save refuses (gate_words) when the document is the agent's, it has
bodies, a change came after the last measure, and some body's numbers differ
from the ones read then. A change that did not touch geometry (a label, a
colour, a setting) does not hold the save.

A measure: body_check, measure or measure_mass of a body (or a PartDesign
feature) alone, object_get of a body's Shape (or all its properties),
session_state, get of a body's volume, area, size, mass … or Shape, a
fast block's own end reading, and a feature's own answer (its body's
volume, box and solids after the recompute: answered). Other reads (a sketch, an edge, a distance
between two things, a property) are not.

AGENTLINK_MEASURE_GATE=0 (or off, false, no) turns the gate off.

Plain Python: the session gives the bodies' numbers (Session.measure_sigs).
"""
import os

KEY = "measured"
OFF = ("0", "off", "false", "no")

# Reads whose answer is a body's measured geometry, whatever they name.
ALWAYS = ("body_check", "session_state")
# Reads that measure when what they name alone is a body or a feature.
OF_ONE = ("measure", "measure_mass")
# get { what: "<Body>.<this>" } values that are the body's geometry.
GET_KEYS = {"volume", "area", "size", "min", "max", "mass", "centerofmass", "inertia", "shape", "box", "boundbox"}
# object_get filter words that reach the Shape (its stats: volume, area, box).
SHAPE_WORDS = ("shape", "volume", "area", "box")


def enabled():
    return os.environ.get("AGENTLINK_MEASURE_GATE", "1").strip().lower() not in OFF


def _seq(session):
    n = session.__dict__.get("_measure_seq", 0) + 1
    session.__dict__["_measure_seq"] = n
    return n


def record(session):
    """The session's measure record of the document it is in now (a dict;
    kept with the document's own record where the session has one)."""
    try:
        rec = session.measured
    except Exception:  # noqa: BLE001 - a stand-in without the property
        rec = None
    if not isinstance(rec, dict):
        rec = session.__dict__.setdefault("_measured_plain", {})
    return rec


# ---- what counts as a measure -------------------------------------------------------------------

def _named(v, labels):
    low = {str(x).lower() for x in labels}
    return isinstance(v, str) and v.lower() in low


def is_measure(tool, args, labels, is_body_or_feature=None):
    """Whether a read that went through is a measure of the document's
    geometry. labels: the bodies' labels (and names); is_body_or_feature(ref):
    whether a reference names a body or a PartDesign feature (None: by
    labels only)."""
    args = args or {}
    if not labels:
        return False
    if tool in ALWAYS:
        return True

    def counts(ref):
        if not isinstance(ref, str) or not ref.strip():
            return False
        if "." in ref:  # Body.Face3, Body.Edge7: an element, not the body
            return False
        if _named(ref, labels):
            return True
        try:
            return bool(is_body_or_feature(ref)) if is_body_or_feature is not None else False
        except Exception:  # noqa: BLE001
            return False

    if tool in OF_ONE:
        a = args.get("a", args.get("body", args.get("object")))
        if args.get("b") is not None:
            return False
        if a is None:
            return len(labels) == 1  # left out: the one body
        return counts(a)
    if tool == "object_get":
        if not counts(args.get("object")):
            return False
        flt = args.get("filter")
        if flt in (None, "", []):
            return True
        if isinstance(flt, str):
            words = [w.strip().lower() for w in flt.split("|") if w.strip()]
            return any(w in SHAPE_WORDS or (len(w) >= 3 and w in "shape") for w in words)
        if isinstance(flt, (list, tuple)):
            return any(str(x) == "Shape" for x in flt)
        return False
    if tool == "get":
        what = args.get("what")
        whats = [what] if isinstance(what, str) else (what if isinstance(what, (list, tuple)) else [])
        return any(is_get_measure(w, labels, is_body_or_feature) for w in whats)
    return False


def is_get_measure(what, labels, is_body_or_feature=None):
    """get's what as a measure: "<Body>.volume", "body.area", "Body.Shape"."""
    if not isinstance(what, str) or "." not in what:
        return False
    head, key = what.strip().rsplit(".", 1)
    if key.lower() not in GET_KEYS:
        return False
    if head == "body":
        return bool(labels)
    if _named(head, labels):
        return True
    try:
        return bool(is_body_or_feature(head)) if is_body_or_feature is not None and "." not in head else False
    except Exception:  # noqa: BLE001
        return False


# ---- what the session keeps ---------------------------------------------------------------------

def before_change(rec, sigs_now):
    """Before a change: the numbers it is compared with, when nothing was read
    yet in this document (opened, made, or last saved before the session
    kept any)."""
    if "sigs" not in rec:
        try:
            rec["sigs"] = dict(sigs_now())
        except Exception:  # noqa: BLE001
            rec["sigs"] = None


def changed(session, rec, step):
    rec["changed"] = _seq(session)
    rec["step"] = step


def measured(session, rec, sigs):
    """A measure (or a save): the numbers now become the ones compared with."""
    rec["measured"] = _seq(session)
    rec["sigs"] = dict(sigs or {})


def answered(session, rec, sigs_now, labels):
    """A changing call whose own answer read these bodies (a feature's
    answer: volume, box, solids, from the recomputed body; 26 Nov QA: a
    save right after a fillet's answer was refused). Their numbers now
    become the ones compared with. The document counts as measured only
    when no other body moved since its last measure: a body this answer did
    not read still holds the save."""
    if rec.get("sigs") is None:
        return
    sigs = dict(rec["sigs"])
    now = dict(sigs_now or {})
    for label in labels:
        if label in now:
            sigs[label] = now[label]
    rec["sigs"] = sigs
    if not differs(sigs, now):
        rec["measured"] = _seq(session)


def differs(before, now):
    """The body labels whose numbers are not as they were: changed, made or
    removed. before None (not read): every body now."""
    now = now or {}
    if before is None:
        return sorted(now)
    out = [k for k in now if before.get(k) != now[k]]
    out += [k for k in before if k not in now]
    return sorted(out)


def gate_words(rec, label, now, mine):
    """The refusal words for doc_save, or None. rec: the document's record;
    label: the document's label; now: its bodies' numbers now; mine: whether
    the agent made or changed it (Session.agent_docs)."""
    if not enabled() or not mine or not isinstance(rec, dict):
        return None
    if rec.get("changed", 0) <= rec.get("measured", 0):
        return None
    if not now:
        return None  # no body: nothing to measure
    bodies = differs(rec.get("sigs"), now)
    if not bodies:
        return None  # the change did not touch geometry
    shown = [b for b in bodies if b in now] or list(now)
    first = shown[0]
    names = ", ".join(bodies[:8]) + (f" and {len(bodies) - 8} more" if len(bodies) > 8 else "")
    return (f"{label} changed after it was last measured (step {rec.get('step', '?')}): read its geometry first, then save. "
            f"Changed: {names}. "
            f"body_check {{ body: \"{first}\" }} measures it: its answer gives volume, box and solids. "
            f"get {{ what: \"{first}.volume\" }} (or .size, .area) measures it too. "
            "Nothing was saved.")

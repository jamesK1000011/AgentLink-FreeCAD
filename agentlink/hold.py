# SPDX-License-Identifier: LGPL-2.1-or-later
"""One recompute for a run of changes (plain Python; used by tools.py's batch).

batch { build: "end" } holds the document's recompute while a run of calls
changes one document, and builds once: at the batch's end, before the first
call that is not in the run (a read that needs geometry, a tool that builds
for itself), or when a call moves to another document.

How: FreeCAD's own Document.RecomputesFrozen (the tree's "Skip recomputes";
FreeCAD 1.1 source: src/App/DocumentPyImp.cpp setRecomputesFrozen sets the
document's SkipRecompute status, and src/App/Document.cpp Document::recompute
returns 0 at once while it is set, unless forced). The tools are not changed:
their own doc.recompute() does nothing while the run is held.

Only tools declared here are held. A tool is safe to hold when, read from its
code, (1) what it changes is written at once and does not need a recompute
for the next call to find it, (2) it does not refuse by reading the rebuilt
model, or what it would refuse is caught by the build's health instead, and
(3) the parts of its answer that are read from the rebuilt shape are listed
here, and are left out of a held answer — a held answer never carries a
volume, a wire count or a body reading from before the build as if it were
new. Every other tool builds first and runs as it always did.
"""
import time

# tool -> the parts of its answer that are read from the rebuilt shape
# (dotted keys), left out while the build is held.
_SKETCH_STATE = ("state.wires", "state.closedWires", "state.openVertices", "state.openVerticesCount", "state.wiresMeet", "state.selfCrossing", "state.todo")
HELD_OK = {
    # The sketch's geometry and constraints are written at once, and the
    # solver's reading (solver, dof, conflicting, redundant) is a fresh
    # solve; the wires are read from the sketch's shape, which is the build's.
    "sketch_add": _SKETCH_STATE,
    "sketch_constrain": _SKETCH_STATE,
    "sketch_offset": _SKETCH_STATE,
    # Also reads the body built from the sketch, and refuses an edit that
    # breaks a later feature: both are the build's while it is held.
    "sketch_edit": _SKETCH_STATE + ("bodyAfter",),
    # Sets properties; its refusal of a value that breaks the object is the
    # build's while it is held.
    "object_set": ("note",),
}
# Reads that need no geometry: they run in a held run without a build.
NO_BUILD = {"guide_read", "tool_groups", "usage_report", "job_status"}

HELD = "held"


def declare(tool, stale=()):
    """An add-on's tool declared safe to hold (see this module's words for
    what that takes); stale: the parts of its answer read from the rebuilt
    shape."""
    HELD_OK[str(tool)] = tuple(stale)


def mode(build):
    """batch's build argument: "each" (the default: every call builds as it
    always did) or "end". The refusal's words for anything else."""
    if build in (None, "each"):
        return "each", None
    if build == "end":
        return "end", None
    return None, f"build: \"end\" (one recompute for a run of changes, at the end) or \"each\" (the default), not {build!r}. Nothing was run."


def _drop(body, path):
    cur = body
    parts = path.split(".")
    for p in parts[:-1]:
        cur = cur.get(p) if isinstance(cur, dict) else None
        if cur is None:
            return False
    if isinstance(cur, dict) and parts[-1] in cur:
        del cur[parts[-1]]
        return True
    return False


def held_answer(tool, body):
    """A held call's answer made honest: the parts read from the shape left
    out, and its health saying plainly that the reading is held."""
    if not isinstance(body, dict):
        return body
    left = [p for p in HELD_OK.get(tool, ()) if _drop(body, p)]
    body["build"] = HELD
    h = {"build": HELD, "facts": "build: held — the document is not rebuilt yet, so this call has no reading of its own: "
                                 "the batch's builds[] carries the health of everything held, after the one recompute"}
    if left:
        h["leftOut"] = left
        h["facts"] += f"; left out of this answer until then: {', '.join(left)}"
    body["health"] = h
    return body


class Hold:
    """A held run on one document. mark(doc) arms the health check and
    answers its mark; check(mark, tools) reads the health after the build
    (None: nothing to say; tools None: only close the mark); snapshot(doc)
    records the step after it."""

    def __init__(self, mark, check, snapshot=None, clock=time.time):
        self._mark, self._check, self._snapshot, self._clock = mark, check, snapshot, clock
        self.doc = None
        self.was = False
        self.m = None
        self.calls = []
        self.tools = []
        self.builds = []
        self.off = None  # why nothing is held, once known

    @property
    def active(self):
        return self.doc is not None

    def plan(self, tool, changing):
        """What a call is to a held run: "hold" (it joins the run), "pass"
        (it runs without a build) or "build" (the run is built first)."""
        if self.off:
            return "pass"
        if changing and tool in HELD_OK:
            return "hold"
        if not changing and tool in NO_BUILD:
            return "pass"
        return "build"

    def begin(self, doc):
        """Hold doc's recomputes. False (and off says why) when they cannot
        be held: the person has them switched off already, or this FreeCAD
        has no such switch."""
        try:
            was = bool(doc.RecomputesFrozen)
        except Exception:
            self.off = "this FreeCAD's documents have no RecomputesFrozen switch: every call built as usual"
            return False
        if was:
            self.off = ("the document's recomputes are already switched off (Skip recomputes, in the document's menu): nothing is built until the person "
                        "switches them on again, so nothing was held or built by this batch")
            return False
        m = self._mark(doc)
        try:
            doc.RecomputesFrozen = True
        except Exception as e:
            self._check(m, None)
            self.off = f"the document's recomputes could not be held ({e}): every call built as usual"
            return False
        self.doc, self.was, self.m, self.calls, self.tools = doc, was, m, [], []
        return True

    def note(self, i, tool):
        self.calls.append(i)
        self.tools.append(tool)

    def release(self):
        """The hold let go with no build (before a rollback, which undoes
        and recomputes itself). The mark is closed."""
        if not self.active:
            return
        doc, m = self.doc, self.m
        self.doc = self.m = None
        try:
            doc.RecomputesFrozen = self.was
        except Exception:
            pass
        try:
            self._check(m, None)
        except Exception:
            pass

    def build(self, when):
        """The one recompute of the held run, and its health: an entry for
        the batch's builds[] (None when nothing is held)."""
        if not self.active:
            return None
        doc, m, calls, tools = self.doc, self.m, self.calls, self.tools
        self.doc = self.m = None
        t0 = self._clock()
        entry = {"when": when, "held": len(calls)}
        if calls:
            entry["calls"] = [calls[0], calls[-1]]
        try:
            doc.RecomputesFrozen = self.was
            entry["recomputed"] = doc.recompute()
        except Exception as e:
            entry["error"] = f"the recompute failed: {e}"
        try:
            h = self._check(m, tools)
        except Exception as e:
            h = {"facts": f"the health check did not run ({e})"}
        if h is None:
            from . import health as _health

            h = {"facts": _health.NOTHING}
        if "error" in entry:
            h = {**h, "facts": f"{entry['error']}; {h.get('facts', '')}".rstrip("; ")}
        entry["health"] = h
        entry["ms"] = int((self._clock() - t0) * 1000)
        if calls and self._snapshot is not None:
            try:
                self._snapshot(doc)
            except Exception:
                pass
        self.builds.append(entry)
        return entry


def build_failed(entry):
    """Whether a build left something failing that was not failing before
    the run (the health's errors marked new), or did not run at all."""
    if not entry:
        return False
    if "error" in entry:
        return True
    h = entry.get("health") or {}
    return any(isinstance(e, dict) and e.get("new") for e in h.get("errors") or [])

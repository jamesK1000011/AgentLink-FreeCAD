# SPDX-License-Identifier: LGPL-2.1-or-later
# What a call did to the open documents, as FreeCAD's own observers saw it,
# and what that means for the undo step the call runs as.
#
# FreeCAD 1.1 makes an undo step lazily (FreeCAD 1.1 source:
# src/App/Document.cpp, src/App/AutoTransaction.cpp, src/App/Transactions.cpp):
#   - Document.openTransaction(name) only names the application's "active
#     transaction". A step exists once something is recorded under it: an
#     object made or removed, a property about to change (an object's or its
#     view provider's), a dynamic property added or removed.
#   - Document.commitTransaction() commits the step when there is one and
#     otherwise does nothing — it does not even take the name back, so the
#     next change anyone makes (a read's leftover, the person) becomes a step
#     under the old call's name.
#   - A step whose every record cancelled out (objects made and removed again
#     inside it: Transaction::addObjectNew erases what addObjectDel wrote) is
#     empty, and FreeCAD pushes it on the undo stack all the same
#     (_commitTransaction does not ask Transaction::isEmpty).
#   - Python is told none of this but Document.HasPendingTransaction;
#     Transaction::isEmpty has no binding, UndoRedoMemSize is a limit, not a
#     size.
# So the session asks HasPendingTransaction before it commits, and for the
# made-and-removed case goes by what the observers saw: finish() below.
#
# The observers are FreeCAD's document observers (App and, with a window,
# Gui), connected only while a call is watched: FreeCAD connects just the
# slots an observer has, so nothing of this runs between calls.
#
# Plain Python but for the two lazy imports; tests drive note() directly.

MAX_EVENTS = 200000   # past this a watch says it is not complete, and nothing is judged from it

NEW, GONE, CHANGED, RECOMPUTED, VIEW = "new", "gone", "changed", "recomputed", "view"

_state = {"log": [], "depth": 0, "full": False, "app": None, "gui": None, "whole": False}


def note(kind, doc, name, prop=None):
    """One event, while any watch is open: kind (NEW, GONE, CHANGED,
    RECOMPUTED, VIEW), the document's and the object's names, the property
    (CHANGED and VIEW)."""
    if _state["depth"] <= 0:
        return
    log = _state["log"]
    if len(log) >= MAX_EVENTS:
        _state["full"] = True
        return
    log.append((kind, doc, name, prop))


def _of(obj):
    return obj.Document.Name, obj.Name


def _holder(obj):
    for get in (lambda: _of(obj), lambda: _of(obj.Object)):
        try:
            return get()
        except Exception:
            continue
    return "?", "?"


class _App:
    """FreeCAD.addDocumentObserver: every record a transaction takes has one
    of these signals beside it (Document::addObject, removeObject,
    onChangedProperty, addDynamicProperty, removeDynamicProperty)."""

    def slotCreatedObject(self, obj):
        try:
            note(NEW, *_of(obj))
        except Exception:
            pass

    def slotDeletedObject(self, obj):
        try:
            note(GONE, *_of(obj))
        except Exception:
            pass

    def slotChangedObject(self, obj, prop):
        try:
            note(CHANGED, *_of(obj), str(prop))
        except Exception:
            pass

    def slotRecomputedObject(self, obj):
        try:
            note(RECOMPUTED, *_of(obj))
        except Exception:
            pass

    # A dynamic property's container is an object or a view provider; one
    # that cannot be placed still counts as a change that stays.
    def slotAppendDynamicProperty(self, obj, prop):
        note(CHANGED, *_holder(obj), str(prop))

    def slotRemoveDynamicProperty(self, obj, prop):
        note(CHANGED, *_holder(obj), str(prop))


class _Gui:
    """FreeCADGui.addDocumentObserver: a view provider's property change is
    recorded in its object's document's transaction
    (ViewProviderDocumentObject::onBeforeChange), and the App observer never
    hears of it. One that belongs to no object (or to one already gone) is
    recorded nowhere, and is passed over."""

    def slotChangedObject(self, vp, prop):
        try:
            # A view provider still being built (its first properties are
            # set before it is given its object) has no object: reading
            # .Object then crashes FreeCAD (a null pointer in its getter),
            # while .Document raises "View provider detached", so that is
            # asked first.
            if getattr(vp, "Document", None) is None:
                return
            o = vp.Object
            if o is None or o.Document is None:
                return
            note(VIEW, o.Document.Name, o.Name, str(prop))
        except Exception:
            pass


def _arm():
    """The observers connected: True when what a transaction records can all
    be seen (the App observer, and the Gui one where there is a window)."""
    try:
        import FreeCAD
    except ImportError:
        return False
    try:
        if _state["app"] is None:
            a = _App()
            FreeCAD.addDocumentObserver(a)
            _state["app"] = a
    except Exception:
        return False
    if not getattr(FreeCAD, "GuiUp", False):
        return True
    try:
        if _state["gui"] is None:
            import FreeCADGui

            g = _Gui()
            FreeCADGui.addDocumentObserver(g)
            _state["gui"] = g
        return True
    except Exception:
        return False


def _disarm():
    for key, mod in (("app", "FreeCAD"), ("gui", "FreeCADGui")):
        o, _state[key] = _state[key], None
        if o is None:
            continue
        try:
            __import__(mod).removeDocumentObserver(o)
        except Exception:
            pass


def open(arm=True):  # noqa: A001 - a watch is opened and closed
    """A watch: everything the observers see from now until close(). Watches
    nest (a batch's and its calls', the session's and the health check's).
    arm: False for tests, which call note() themselves."""
    w = {"since": len(_state["log"]), "open": True, "seen": False}
    if arm and _state["depth"] == 0:
        w["seen"] = _state["whole"] = _arm()
    elif arm:
        w["seen"] = bool(_state.get("whole"))
    else:
        w["seen"] = True
    _state["depth"] += 1
    return w


def events(w):
    """The events since w opened (it may still be open)."""
    return _state["log"][w.get("since", 0):] if w else []


def complete(w):
    """Whether w saw everything: the observers were connected and the log
    did not fill."""
    return bool(w) and bool(w.get("seen")) and not _state["full"]


def close(w):
    """w closed: (its events, whether they are complete)."""
    if not w or not w.get("open"):
        return [], False
    w["open"] = False
    ev, ok = list(events(w)), complete(w)
    _state["depth"] = max(0, _state["depth"] - 1)
    if _state["depth"] == 0:
        del _state["log"][:]
        _state["full"] = False
        _disarm()
    return ev, ok


# ---- a refused call's outcome ----

def mark_outcome(exc, ev, removed, doc, names0):
    """Put on exc what a refused changing call left (read by
    protocol.refusal; Session.execute calls it after the take-back): "not_started" (no change was made), "rolled_back"
    (all of it was taken back) or "cleanup_incomplete" with the objects that
    stay. Never raises."""
    try:
        if getattr(exc, "outcome", None):
            return
        left = []
        if doc is not None and names0 is not None:
            try:
                left = [o.Label for o in doc.Objects if o.Name not in names0]
            except Exception:
                left = []
        touched = bool(removed) or any(e and e[0] not in (RECOMPUTED, VIEW) for e in (ev or []))
        exc.outcome = "cleanup_incomplete" if left else ("rolled_back" if touched else "not_started")
        if left:
            exc.outcome_left = left[:8]
    except Exception:
        pass


# ---- readings ---------------------------------------------------------------------------

def stays(ev):
    """The (document, object) pairs a run of events left something of: every
    object with an event, less those made and removed again within it. An
    empty set with events at all means the run made only things it took
    away again."""
    made, temp, kept = set(), set(), set()
    for kind, doc, name, _prop in ev:
        key = (doc, name)
        if kind == RECOMPUTED:
            continue  # a recompute records nothing itself: what it changed is a CHANGED event
        if kind == NEW:
            made.add(key)
            temp.discard(key)  # the name used again: this one is here
        elif kind == GONE:
            if key in made:
                made.discard(key)
                temp.add(key)
                kept.discard(key)
            else:
                kept.add(key)  # an object from before the run was removed
        else:
            if key in temp:
                continue  # a late word about an object already gone
            kept.add(key)
    # What was made and is still here stays; so does anything changed that
    # was not made and removed.
    return kept | made


def only_passing(ev):
    """True when a run of events made objects and removed them all again and
    touched nothing else — in any document. Such a transaction is empty
    (see the top of this file)."""
    return any(k in (NEW, GONE) for k, _d, _n, _p in ev) and not stays(ev)


def after_recompute(ev, doc):
    """For the objects of document doc with events in ev: {name: the
    properties changed since its last recompute in ev — all of them when it
    was never recomputed in ev}, and the set of names recomputed at all.
    An object with an empty list was recomputed last: a Touched flag it
    still carries is from before that recompute (a single object's
    recompute executes and does not purge: Document::recomputeFeature),
    not a change waiting for one."""
    since, recomputed = {}, set()
    for kind, d, name, prop in ev:
        if d != doc:
            continue
        if kind == RECOMPUTED:
            recomputed.add(name)
            since[name] = []
        elif kind == CHANGED:
            since.setdefault(name, []).append(prop)
        elif kind == NEW:
            since.setdefault(name, [])
            recomputed.discard(name)
        elif kind == GONE:
            since.pop(name, None)
            recomputed.discard(name)
    return since, recomputed


# ---- the undo step ----------------------------------------------------------------------

def undo_names(doc):
    try:
        return list(doc.UndoNames)
    except Exception:
        return None


def close_active(abort=False):
    """The application's active transaction closed, so no later change is
    recorded under this call's name (commitTransaction and abortTransaction
    leave the name standing when the document has no step pending)."""
    try:
        import FreeCAD

        fn = getattr(FreeCAD, "closeActiveTransaction", None)
        if fn is not None:
            fn(bool(abort))
    except Exception:
        pass


def finish(doc, start, ev, ok, u0, names0, closer=close_active):
    """End a changing call's transaction on doc (the session's document now;
    start: the one the call began in). Returns (made, why): whether the
    call left an undo step in doc, and when not, why in a few words.

    - A document that cannot say whether a step is pending (a stand-in, an
      old FreeCAD) is committed and counted, as before.
    - No step pending and the undo stack as it was: FreeCAD made none; none
      is counted.
    - A step pending, and all the call did — in any document, seen whole —
      was make objects and remove them again: the step is empty, and it is
      aborted (which rolls back nothing and deletes it) instead of pushed
      on the stack for history_undo to spend.
    - Anything else is committed and counted."""
    try:
        pending = getattr(doc, "HasPendingTransaction", None)
    except Exception:
        pending = None
    if pending is None:
        doc.commitTransaction()
        return True, None
    if pending and doc is start and ok and only_passing(ev):
        doc.abortTransaction()
        closer(True)
        return False, "it made only objects it removed again"
    doc.commitTransaction()
    closer(False)
    if pending:
        return True, None
    # Nothing pending at the end: a step only where the call committed one
    # of its own inside (the stack grew, or its names moved at the limit).
    try:
        if u0 is not None and doc.UndoCount > u0:
            return True, None
    except Exception:
        return True, None
    now = undo_names(doc)
    if doc is start and names0 is not None and now is not None and now != names0:
        return True, None
    if doc is not start:
        return True, None  # another document: counted as before
    return False, "it changed nothing FreeCAD keeps an undo step for"

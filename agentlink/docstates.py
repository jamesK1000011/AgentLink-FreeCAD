# SPDX-License-Identifier: LGPL-2.1-or-later
# Each family's state belongs to the document it was made in.
#
# A session works in one document at a time and may move to another by any
# route (doc_new, doc_open, doc_close, doc_switch, doc_revert, the window
# link when the person closed the agent's document, an add-on setting
# session.doc itself). session.family_state — a dict of each family's own
# state under its group's name — is therefore one dict per document:
#
#   on leaving a document   its dict is set aside under that document, for
#                           as long as the document stays open;
#   on arriving in one      the dict set aside for it comes back, else an
#                           empty one (the family reads what it keeps in the
#                           document itself, as after any restart).
#
# A document is told by identity, not by name: FreeCAD keeps one Python
# object per open document (FreeCAD 1.1 source: src/App/Document.cpp, the
# document's DocumentPythonObject), so a document closed and another made
# or opened under the same name is another document and starts empty.
#
# Two events say when (agentlink.hooks.on):
#   document_state_leaving(session, doc, state)
#       the session has moved away from doc, which is still open; state is
#       doc's dict, about to be set aside: write into doc now what must not
#       be lost with the session.
#   document_state_entered(session, doc, state, restored)
#       state is the session's dict for doc from now on; restored is True
#       when it is the one set aside earlier, False when it starts empty.
# Both run on the thread that moved the session, before any state is handed
# out for the new document.
#
# An add-on that settles its own state per document (it keeps its own book
# of which document its state belongs to, and writes and parks it itself)
# says so, and its key is then carried along untouched for it to settle:
#   agentlink.hooks.own_document_state("mykey")
# or, with no call at all, by keeping that book on the session under the
# attribute "_<key>_documents" — a key whose session has that attribute is
# carried along too.
#
# The session's own record of a document goes the same way, by the same
# book: its steps (what history_diff compares), meta, tx (undo steps made in
# it), calls (the changing calls, for a macro), checks (what history_diff
# says to run again) and measured (when its geometry last changed and was
# last measured: agentlink/measured.py). They are the document's, not the session's: carried
# into the next document they gave a history_diff across two documents, a
# macro of calls made in two, and an undo count that was another stack's.
# session.steps, .meta, .tx, .calls and .checks are properties over own().
#
# Plain Python: the session calls settle() from its doc and family_state
# properties, and own() from those five (agentlink/tools.py).

OWN = set()  # keys their add-on settles itself (hooks.own_document_state)

_ATTR = "_agentlink_document_states"


def open_documents():
    """{name: document} of the open documents, or None where FreeCAD cannot
    say (a test's stand-in): every document then counts as open."""
    try:
        import FreeCAD

        return dict(FreeCAD.listDocuments())
    except Exception:
        return None


def is_open(doc, name=None):
    """True while doc is an open document (the very object, not one of the
    same name)."""
    if doc is None:
        return False
    docs = open_documents()
    if docs is None:
        return True
    try:
        return docs.get(name if name is not None else doc.Name) is doc
    except Exception:
        return False


def name_of(doc):
    try:
        return doc.Name
    except Exception:  # a document already closed
        return None


def settles_itself(session, key):
    """Whether key's add-on settles its own state per document."""
    try:
        return key in OWN or getattr(session, f"_{key}_documents", None) is not None
    except Exception:
        return False


OWN_KEYS = ("steps", "meta", "tx", "calls", "checks", "measured")


def fresh():
    """The session's own record of a document it has done nothing in yet."""
    return {"steps": [], "meta": {}, "tx": 0, "calls": [], "checks": {}, "measured": {}}


def _book(session):
    b = session.__dict__.get(_ATTR)
    if b is None:
        b = session.__dict__[_ATTR] = {"owner": None, "name": None, "state": {}, "parked": {}, "own": fresh(), "own_parked": {}}
    return b


def _emit(event, *args):
    try:
        from . import hooks

        hooks.emit(event, *args)
    except Exception:
        pass


def settle(session, doc):
    """The session's family state made the state of doc, the document the
    session is in now; returns that dict. Cheap when nothing moved."""
    b = _book(session)
    if doc is None or b["owner"] is doc:
        return b["state"]
    old, was, state = b["owner"], b["name"], b["state"]
    if old is None:
        # The first document: what the session holds is this document's.
        b["owner"], b["name"] = doc, name_of(doc)
        return state
    carried = {k: state.pop(k) for k in [k for k in state if settles_itself(session, k)]}
    parked, own_parked = b["parked"], b["own_parked"]
    if is_open(old, was):
        if state:
            _emit("document_state_leaving", session, old, state)
        parked[was] = (old, state)
        own_parked[was] = (old, b["own"])
    for n in [n for n, (d, _st) in parked.items() if not is_open(d, n)]:
        del parked[n]  # closed: what its families kept in the file is there
    for n in [n for n, (d, _rec) in own_parked.items() if not is_open(d, n)]:
        del own_parked[n]  # closed: its undo stack and steps went with it
    name = name_of(doc)
    rec = parked.pop(name, None)
    restored = rec is not None and rec[0] is doc
    new = rec[1] if restored else {}
    new.update(carried)
    mine = own_parked.pop(name, None)
    b["own"] = mine[1] if mine is not None and mine[0] is doc else fresh()
    b["owner"], b["name"], b["state"] = doc, name, new
    _emit("document_state_entered", session, doc, new, restored)
    return new


def put(session, doc, state):
    """state made the session's dict for the document it is in (an add-on
    that reopened a document from a copy puts the state it kept back)."""
    b = _book(session)
    settle(session, doc)
    b["state"] = state if isinstance(state, dict) else {}
    return b["state"]


def own(session, doc):
    """The session's own record of doc, the document it is in now: { steps,
    meta, tx, calls, checks }."""
    settle(session, doc)
    return _book(session)["own"]


def own_of(session, doc):
    """The session's own record of an open document, the one it is in or
    one it left (set aside): for a batch that takes back its steps in the
    document it started in after a call moved the session on. None for a
    document the session never worked in, or one closed since."""
    b = _book(session)
    if doc is None:
        return None
    if b["owner"] is doc:
        return b["own"]
    for n, (d, rec) in b["own_parked"].items():
        if d is doc and is_open(d, n):
            return rec
    return None


def set_aside(session):
    """For session_state and tests: the names of the open documents a
    state is set aside for."""
    b = _book(session)
    return sorted(n for n, (d, _st) in b["parked"].items() if is_open(d, n))


def front_document():
    """The document in front: the window's active document (its 3D view's
    tab) when there is a window, else FreeCAD's ActiveDocument; None when
    none. Tools that act on "the active document" (FreeCAD's own commands,
    FEM's and Draft's makers) act on this one, not on the session's."""
    try:
        import FreeCAD
    except Exception:
        return None
    if getattr(FreeCAD, "GuiUp", False):
        try:
            import FreeCADGui

            gd = FreeCADGui.ActiveDocument
            if gd is not None and getattr(gd, "Document", None) is not None:
                return gd.Document
        except Exception:
            pass
    try:
        return FreeCAD.ActiveDocument
    except Exception:
        return None


def mismatch(session_doc):
    """{agentDocument, frontDocument, mismatch} when the document in front
    is another one than the session's (by name, or another object of the
    same name: a document closed and opened again); {} when they agree or
    no document is in front."""
    front = front_document()
    if front is None or session_doc is None:
        return {}
    try:
        same = front is session_doc or (front.Name == session_doc.Name and is_open(session_doc))
        if same:
            return {}
        mine, theirs = session_doc.Label, front.Label
    except Exception:
        return {}
    return {"agentDocument": mine, "frontDocument": theirs,
            "mismatch": f"The agent works in {mine}, but {theirs} is in front. Tools that act on the front document act on {theirs}. "
                        f"doc_switch {{ document: \"{mine}\" }} binds both to {mine} again."}

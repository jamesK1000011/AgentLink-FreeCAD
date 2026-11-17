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
# Plain Python: the session calls settle() from its doc and family_state
# properties (agentlink/tools.py).

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


def _book(session):
    b = session.__dict__.get(_ATTR)
    if b is None:
        b = session.__dict__[_ATTR] = {"owner": None, "name": None, "state": {}, "parked": {}}
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
    parked = b["parked"]
    if is_open(old, was):
        if state:
            _emit("document_state_leaving", session, old, state)
        parked[was] = (old, state)
    for n in [n for n, (d, _st) in parked.items() if not is_open(d, n)]:
        del parked[n]  # closed: what its families kept in the file is there
    name = name_of(doc)
    rec = parked.pop(name, None)
    restored = rec is not None and rec[0] is doc
    new = rec[1] if restored else {}
    new.update(carried)
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


def set_aside(session):
    """For session_state and tests: the names of the open documents a
    state is set aside for."""
    b = _book(session)
    return sorted(n for n, (d, _st) in b["parked"].items() if is_open(d, n))

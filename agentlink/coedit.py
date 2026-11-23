# SPDX-License-Identifier: LGPL-2.1-or-later
# Co-work (design E5 #8): the agent does not change what the person is
# editing. While the person has a body (or an object in it) open for
# editing, or a task panel is open that does not let the document change
# (Gui.Control.activeDialog() and not isAllowedAlterDocument()), a changing
# call on that body, or on that document when its target is not known,
# is held: refused before it starts (code held_person_editing, outcome
# not_started), with what is open and what to do. Reads, other bodies and
# other documents go on. An edit the agent's echo opened itself
# (echo._agent_edits) is not the person's. Without the window (headless,
# no FreeCADGui) nothing is held.

CODE = "held_person_editing"

# Calls that drive the window as a person does (a command, a menu entry, a
# click, a dialog): how a task panel is answered or closed, so never held.
# app_: a restart is the way out of a FreeCAD that hangs.
FLOWS = ("cmd_", "menu_", "gui_", "dialog_")
FREE_PREFIXES = FLOWS + ("app_",)
# Calls that do not change the document they start in.
FREE = frozenset({"batch", "fast", "doc_new", "doc_open", "doc_switch"})

BODY = "PartDesign::Body"


def _gui():
    """FreeCADGui when the window is up, else None (headless)."""
    try:
        import FreeCAD

        if not getattr(FreeCAD, "GuiUp", False):
            return None
        import FreeCADGui

        return FreeCADGui
    except Exception:  # noqa: BLE001
        return None


# Edits that began during an agent call (a sketch a cmd_run or gui_input
# opened, a feature's task panel a call left open): the agent's, not the
# person's. Kept to the edit still open (settle).
_opened = set()


def _agent_edits():
    try:
        from . import echo

        return set(echo._agent_edits) | _opened
    except Exception:  # noqa: BLE001
        return set(_opened)


def edit_key(gui=None):
    """(document, object) names of what is open for editing now, or None."""
    gui = _gui() if gui is None else gui
    if gui is None:
        return None
    try:
        fn = getattr(gui, "editDocument", None)
        ed = fn() if callable(fn) else getattr(gui, "ActiveDocument", None)
        vp = ed.getInEdit() if ed is not None else None
        if vp is None:
            return None
        return (ed.Document.Name, getattr(getattr(vp, "Object", None), "Name", None))
    except Exception:  # noqa: BLE001
        return None


def settle(before, gui=None):
    """After an agent call: an edit open now that was not before the call
    is the agent's. before: edit_key() from before the call. Never raises."""
    try:
        now = edit_key(gui)
        for k in list(_opened):
            if k != now:
                _opened.discard(k)
        if now is not None and now != before:
            _opened.add(now)
    except Exception:  # noqa: BLE001
        pass


def _alters_ok(ctl):
    """Whether the open task panel lets the document change. A panel that
    cannot say is taken as one that does not (FreeCAD's TaskDialog default)."""
    for get in (lambda: ctl.isAllowedAlterDocument(), lambda: ctl.activeTaskDialog().isAllowedAlterDocument()):
        try:
            got = get()
        except Exception:  # noqa: BLE001
            continue
        if isinstance(got, bool):
            return got
    return False


def person_edit(gui, mine=None):
    """What the person has open in the window, or None:
    {"doc": document name, "object": the object in edit or None (a task
    panel with no edit behind it)}. An edit in mine ((doc, object) names:
    the agent's own) is not the person's, nor is its task panel."""
    if gui is None:
        return None
    mine = _agent_edits() if mine is None else mine
    ed = None
    try:
        fn = getattr(gui, "editDocument", None)
        ed = fn() if callable(fn) else None
    except Exception:  # noqa: BLE001
        ed = None
    if ed is None:
        ed = getattr(gui, "ActiveDocument", None)
    vp = None
    try:
        vp = ed.getInEdit() if ed is not None else None
    except Exception:  # noqa: BLE001
        vp = None
    if vp is not None:
        obj = getattr(vp, "Object", None)
        doc = getattr(getattr(ed, "Document", None), "Name", None)
        if (doc, getattr(obj, "Name", None)) in mine:
            return None
        return {"doc": doc, "object": obj}
    ctl = getattr(gui, "Control", None)
    try:
        open_ = bool(ctl.activeDialog()) if ctl is not None else False
    except Exception:  # noqa: BLE001
        open_ = False
    if not open_ or _alters_ok(ctl):
        return None
    ad = getattr(gui, "ActiveDocument", None)
    return {"doc": getattr(getattr(ad, "Document", None), "Name", None), "object": None}


def _strings(v, depth=0):
    if depth > 4:
        return
    if isinstance(v, str):
        yield v
        # "Pad.Face3" and "Pad:Face3" name Pad.
        for sep in (".", ":"):
            if sep in v:
                yield v.split(sep, 1)[0]
    elif isinstance(v, (list, tuple)):
        for x in v[:200]:
            yield from _strings(x, depth + 1)
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x, depth + 1)


def targets(doc, args):
    """The objects of doc that the call's arguments name (by Name or Label)."""
    out = []
    if doc is None or not isinstance(args, dict):
        return out
    try:
        objs = list(doc.Objects)
    except Exception:  # noqa: BLE001
        objs = []
    seen = set()
    for n in _strings(args):
        if not n or n in seen:
            continue
        seen.add(n)
        o = None
        try:
            o = doc.getObject(n)
        except Exception:  # noqa: BLE001
            o = None
        if o is None:
            o = next((x for x in objs if getattr(x, "Label", None) == n), None)
        if o is not None and all(o is not x for x in out):
            out.append(o)
    return out


def body_of(o):
    """The Part Design Body that o is (or is in), or None."""
    for _ in range(20):
        if o is None:
            return None
        if getattr(o, "TypeId", "") == BODY:
            return o
        try:
            o = o.getParentGeoFeatureGroup()
        except Exception:  # noqa: BLE001
            return None
    return None


def _deps(o):
    try:
        return list(o.OutListRecursive)
    except Exception:  # noqa: BLE001
        return []


def related(t, e):
    """Whether a change to t disturbs e, in edit: the same object, the same
    body, or one built from the other (a recompute of one reaches the other)."""
    if t is e:
        return True
    b = body_of(e)
    if b is not None and body_of(t) is b:
        return True
    return any(x is e for x in _deps(t)) or any(x is t for x in _deps(e))


def refusal(tool, args, session, gui=None, mine=None):
    """The words of a hold for this call, or None when it goes on."""
    name = getattr(tool, "name", "")
    if not isinstance(name, str) or name in FREE or name.startswith(FREE_PREFIXES):
        return None
    try:
        changes = tool.changes_for(args or {})
    except Exception:  # noqa: BLE001
        changes = bool(getattr(tool, "changes", False))
    if not changes:
        return None
    gui = _gui() if gui is None else gui
    if gui is None:
        return None
    pe = person_edit(gui, mine)
    if pe is None:
        return None
    doc = getattr(session, "doc", None)
    if doc is None or getattr(doc, "Name", None) != pe["doc"]:
        return None  # another document: not held
    e = pe["object"]
    after = ("Nothing changed. Wait until the person closes the task panel, then call again. Or ask the person to close it. "
             "Reads, other bodies and other documents are not held.")
    if e is None:
        return (f"Held: a task panel is open in {pe['doc']}, and it does not let the document change. "
                f"{name} would change this document, so it did not start. " + after)
    found = targets(doc, args)
    if found and not any(related(t, e) for t in found):
        return None
    b = body_of(e)
    where = getattr(e, "Label", None) or getattr(e, "Name", "?")
    if b is not None and b is not e:
        where += f" in {getattr(b, 'Label', None) or b.Name}"
    what = ", ".join(getattr(t, "Label", None) or t.Name for t in found[:3]) if found else "this document"
    return f"Held: the person is editing {where} in {pe['doc']}. {name} would change {what}, so it did not start. " + after


def check(tool, args, session):
    """Raises the hold (ToolError held_person_editing) when refusal has
    words. Else the edit open now (edit_key), for settle after the call."""
    said = refusal(tool, args, session)
    if said:
        from .protocol import ToolError

        raise ToolError(CODE, said)
    return edit_key()

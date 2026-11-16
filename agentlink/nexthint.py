# SPDX-License-Identifier: LGPL-2.1-or-later
"""The "next" hint of session_state and the health check: one short line of
what FreeCAD's window is in the middle of, so the agent's next call fits it
— a dialog in front and its buttons, a sketch open in edit with its degrees
of freedom, an open task panel and its buttons, the active workbench, the
status bar's text, and up to five tools whose FreeCAD commands report
themselves active now (agentlink/toolindex.py's entries, tools.now_state()).

Plain Python: the state is read by tools.next_state(); here it is put into
words and kept under MAX characters.
"""
from . import toolindex

MAX = 400
MAX_TOOLS = 5
MAX_CANDIDATES = 60


def _cut(text, n):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:max(1, n - 1)].rstrip() + "…"


def _buttons(names, n=5):
    names = [_cut(b, 18) for b in (names or []) if str(b or "").strip()]
    return ", ".join(names[:n]) + (" …" if len(names) > n else "")


def candidates(names, workbench, editing=None, entry=toolindex.entry, cap=MAX_CANDIDATES):
    """The tools worth asking FreeCAD about: those of the active workbench
    (a sketch in edit: Sketcher's) that name a FreeCAD command, at most cap.
    [(tool, entry)] — asking every command of every tool would cost more
    than the hint is worth."""
    want = {w for w in (workbench, "SketcherWorkbench" if editing == "sketch" else None) if w}
    out = []
    if not want:
        return out
    for n in names:
        try:
            e = entry(n)
        except Exception:  # noqa: BLE001
            continue
        if e.get("commands") and e.get("workbench") in want:
            out.append((n, e))
            if len(out) >= cap:
                break
    return out


def active_tools(rows, state, n=MAX_TOOLS):
    """The tools among rows [(tool, entry)] whose FreeCAD command reports
    itself active in state (now_state's), best fit first, at most n."""
    hits = []
    for name, e in rows:
        try:
            score, why = toolindex.fits(e, state)
        except Exception:  # noqa: BLE001
            continue
        if "command active" in why:
            hits.append((-score, name))
    hits.sort()
    return [name for _s, name in hits[:n]]


def key(state):
    """What makes a hint news: the dialog, the sketch in edit and its
    freedom, the task panel, the workbench. Not the status bar's text or the
    tools, which move with the mouse and the selection."""
    d, sk, p = state.get("dialog") or {}, state.get("sketch") or {}, state.get("panel") or {}
    return (state.get("workbench"), state.get("editing"), sk.get("name"), sk.get("dof"), bool(p), tuple(p.get("buttons") or ()),
            d.get("title"), tuple(d.get("buttons") or ()))


def compose(state, tools=(), limit=MAX):
    """The hint, or None when there is nothing to say (no window).
    state: { window, workbench, editing, sketch { name, dof }, panel
    { buttons }, dialog { title, buttons }, status }; tools: names from
    active_tools. What matters most comes first, and the line is cut to
    limit."""
    if not state or not state.get("window"):
        return None
    parts = []
    d = state.get("dialog")
    if d:
        b = _buttons(d.get("buttons"))
        parts.append(f"a dialog is in front: {_cut(d.get('title') or 'untitled', 50)}" + (f" [{b}]" if b else "") + " — dialog_answer presses a button")
    sk = state.get("sketch")
    if sk:
        dof = sk.get("dof")
        parts.append(f"sketch {_cut(sk.get('name'), 40)} is open in edit"
                     + ("" if dof is None else (", fully constrained" if dof == 0 else f", {dof} DoF left")))
    elif state.get("editing"):
        parts.append(f"{_cut(state['editing'], 40)} is open in edit")
    p = state.get("panel")
    if p:
        b = _buttons(p.get("buttons"))
        parts.append("a task panel is open" + (f" [{b}]" if b else ""))
    if state.get("workbench"):
        parts.append(f"workbench {state['workbench']}")
    if state.get("status"):
        parts.append(f"status bar: {_cut(state['status'], 80)}")
    if tools:
        parts.append("active now: " + ", ".join(list(tools)[:MAX_TOOLS]))
    if not parts:
        return None
    return _cut("; ".join(parts), limit)

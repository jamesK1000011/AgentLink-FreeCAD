# SPDX-License-Identifier: LGPL-2.1-or-later
"""The context-controlled tool list (arm B of the 17 Nov exploration).

Two modes, chosen with no new install:

    classic  (default)  the lean list: the core and view groups and the
                        groups an add-on asks for; tool_groups turns more on.
    context             a small fixed base (BASE) is always listed; after
                        each changing call the client is shown the tools that
                        fit the state of the document and the window, and is
                        told so with notifications/tools/list_changed.

Switch: the environment variable AGENTLINK_TOOLLIST=classic|context, else
the preference ToolListMode (text, Mod/AgentLink). The mode is read again
after each changing call, so a preference set while FreeCAD runs takes
effect on the next change.

What is shown in context mode (compute()):

1. Always BASE: session_state, batch, guide_read, tool_groups, tool_find.
2. No document, or an empty one: START (open or make a document) and the
   likely next tools (session_state's next).
3. A document with objects: the likely next tools; the tools the tool index
   puts in the active workbench, a sketch in edit, the linked workbenches,
   the workbenches of the selection and of the document's objects
   (appliesnow.chosen()); each read with its own leading checks
   (appliesnow.take()). A tool whose check refuses now ("not") is not
   shown. The rest are shown, those that apply first. COMPANIONS (undo, a
   picture) are shown too.
4. Thin context (the owner's rule): when half or more of the tools read could
   not be told (notChecked, or the budget ran out), or no tool was chosen,
   the list gets LARGER: the classic lean list is added.
5. A token cap (ToolListCap, tokens; CAP_TOKENS) on the extra workbench
   tools only: the base, the likely next tools, those that apply, the
   companions and (thin context) the classic list are always shown.

Nothing is unreachable: tool_find returns any tool, tool_groups { tool }
gives its whole definition, and every tool is callable by name (directly,
or in a batch where the client sends only listed tools). A group turned on
with tool_groups { enable } stays listed in both modes.

The list changes only when the context changes (CONTEXT key: the document,
its object types, the workbench, a sketch or task dialog in edit, the
selection's kind), never inside a batch (the batch's end counts once).

Counters for the A/B test (stats()): list changes, tokens of each list
sent, calls to a tool that was not listed, tool_find calls.
"""
import json
import os
import time

from . import appliesnow

PREFS = appliesnow.PREFS
BASE = ("session_state", "batch", "guide_read", "tool_groups", "tool_find")
START = ("doc_new", "doc_open", "doc_switch", "doc_close", "doc_save")
COMPANIONS = ("history_undo", "view_snapshot", "view_render")
CAP_TOKENS = 12000
CHARS_PER_TOKEN = 3.5


def mode():
    """'context' or 'classic'."""
    env = os.environ.get("AGENTLINK_TOOLLIST", "").strip().lower()
    if env in ("context", "classic"):
        return env
    try:
        import FreeCAD

        v = FreeCAD.ParamGet(PREFS).GetString("ToolListMode", "classic").strip().lower()
        return "context" if v == "context" else "classic"
    except Exception:  # noqa: BLE001 - no FreeCAD here
        return "classic"


def cap_tokens():
    try:
        import FreeCAD

        v = int(FreeCAD.ParamGet(PREFS).GetInt("ToolListCap", CAP_TOKENS))
        return max(1500, min(60000, v))
    except Exception:  # noqa: BLE001
        return CAP_TOKENS


def tokens_of(tools):
    """Tokens of these tools' listings (3.5 characters a token)."""
    n = 0
    for t in tools:
        try:
            n += len(json.dumps(t.listing(), ensure_ascii=False, separators=(",", ":")))
        except Exception:  # noqa: BLE001
            pass
    return int(round(n / CHARS_PER_TOKEN))


def _lean(server):
    groups = getattr(server, "lean_groups", None) or set()
    return [t.name for t in server.tools.values() if t.group in groups and not getattr(t, "alias_of", None)]


def context_key(state, doc):
    """What decides the list: when it is the same, the list is not computed again."""
    try:
        types = tuple(sorted({o.TypeId for o in doc.Objects})) if doc is not None else None
        name = doc.Name if doc is not None else None
    except Exception:  # noqa: BLE001
        types, name = None, None
    return (name, types, state.get("workbench"), state.get("editing"), state.get("task"),
            tuple(sorted(state.get("selSubs") or ())), tuple(sorted(state.get("selBenches") or ())), bool(state.get("selected")))


def _task_open():
    try:
        import FreeCADGui

        return bool(FreeCADGui.Control.activeDialog())
    except Exception:  # noqa: BLE001
        return False


def _state(session):
    """tools.now_state() of the session's document; a bare state where it cannot be read."""
    try:
        from .tools import now_state

        return now_state(getattr(session, "doc", None), ())
    except Exception:  # noqa: BLE001 - no FreeCAD here
        return {"window": False, "workbench": None, "editing": None, "selected": 0, "selBenches": set(), "selSubs": set(), "docBenches": None, "active": {}}


def _next(session, state):
    """The likely next tools (session_state's next)."""
    try:
        from .tools import next_picks

        gui = None
        if state.get("window"):
            import FreeCADGui as gui  # noqa: N813
        return [p["tool"] for p in next_picks(session, state, gui)[1]]
    except Exception:  # noqa: BLE001
        return []


def compute(session, state=None):
    """(names in order, how): the context list, BASE not included. Never raises."""
    server = getattr(session, "server", None)
    how = {}
    if server is None:
        return [], how
    doc = getattr(session, "doc", None)
    if state is None:
        state = _state(session)
    nexts = _next(session, state)
    try:
        objects = len(doc.Objects) if doc is not None else 0
    except Exception:  # noqa: BLE001
        objects = 0
    must = list(nexts)   # always shown, whatever the cap
    rest = []            # shown while the cap lets them in, in this order
    if objects == 0:
        how["start"] = True
        must += list(START)
    else:
        cand, how = appliesnow.chosen(server, state)
        how = dict(how)
        try:
            by_bench, _links = appliesnow._index(server)
            for w in sorted(state.get("selBenches") or ()):
                for n in sorted(by_bench.get(w, ())):
                    if n not in cand:
                        cand.append(n)
        except Exception:  # noqa: BLE001
            pass
        r = appliesnow.take(session, state=state, names=cand)
        by = r.get("by") or {}
        unread = sum(1 for n in cand if by.get(n) in (None, "notChecked", "notEvaluated"))
        nots = [n for n in cand if by.get(n) == "not"]
        applies = [n for n in cand if by.get(n) == "applies"]
        rest = [n for n in cand if by.get(n) != "applies" and n not in nots]
        must += applies + list(COMPANIONS)
        how["read"] = {"chosen": len(cand), "applies": len(applies), "not": len(nots), "unknown": unread}
        if not cand or unread * 2 >= len(cand):
            # Thin context: the list gets larger, never smaller than the classic one.
            how["fallback"] = "lean"
            must += _lean(server)
    # Order kept, duplicates and BASE out, only tools that exist here.
    seen = set(BASE)

    def keep(names):
        out = []
        for n in names:
            if n not in seen and n in server.tools and not getattr(server.tools[n], "alias_of", None):
                seen.add(n)
                out.append(n)
        return out

    kept = keep(must)
    rest = keep(rest)
    cap = cap_tokens() - tokens_of(server.tools[n] for n in BASE if n in server.tools)
    total = tokens_of(server.tools[n] for n in kept)
    for i, n in enumerate(rest):
        k = tokens_of([server.tools[n]])
        if total + k > cap:
            how["capped"] = len(rest) - i
            break
        total += k
        kept.append(n)
    return kept, how


def stats(session):
    return session.__dict__.setdefault("_ctx_stats", {"changes": 0, "sent": [], "hiddenCalls": 0, "hiddenNames": [], "finds": 0, "computeMs": 0})


def apply(server, session, notify=True, force=False):
    """Bring server.shown in line with the mode and the context. Returns True
    when the list changed (and, with notify, list_changed was queued)."""
    try:
        m = mode()
        if m != "context":
            if getattr(server, "shown", None) is not None:
                server.shown = None
                session._ctx_key = None
                if notify:
                    server.outbox.append({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
                return True
            return False
        t0 = time.time()
        state = _state(session)
        state["task"] = _task_open() if state.get("window") else False
        key = context_key(state, getattr(session, "doc", None))
        if not force and getattr(server, "shown", None) is not None and key == getattr(session, "_ctx_key", None):
            return False
        names, how = compute(session, state)
        session._ctx_key = key
        session._ctx_how = how
        st = stats(session)
        st["computeMs"] += int((time.time() - t0) * 1000)
        new = set(names)
        if new == getattr(server, "shown", None):
            return False
        server.shown = new
        server.shown_order = list(names)
        st["changes"] += 1
        if notify:
            server.outbox.append({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
        return True
    except Exception:  # noqa: BLE001 - the list never fails the call it follows
        return False


def after_call(session, tool_name):
    """After a changing call (or a batch that changed): the list again, unless inside a batch."""
    if getattr(session, "batch_now", None) is not None:
        return False
    server = getattr(session, "server", None)
    if server is None:
        return False
    return apply(server, session)


def note_call(server, session, name):
    """Before a call: count a call to a tool the client was not shown."""
    try:
        if getattr(server, "shown", None) is None:
            return
        st = stats(session)
        if name == "tool_find":
            st["finds"] += 1
        if not server.is_listed(name):
            st["hiddenCalls"] += 1
            if len(st["hiddenNames"]) < 40:
                st["hiddenNames"].append(name)
    except Exception:  # noqa: BLE001
        pass


def note_listed(server, session, tools):
    try:
        if getattr(server, "shown", None) is not None:
            st = stats(session)
            st["sent"].append({"t": round(time.time(), 1), "tools": len(tools), "tokens": tokens_of(server.tools[t["name"]] for t in tools if t["name"] in server.tools)})
            del st["sent"][:-50]
    except Exception:  # noqa: BLE001
        pass


def describe(server, session):
    """For tool_groups { listing: true }: the mode, what is listed and why, the counters."""
    listed = server.listed()
    out = {"mode": mode(), "count": len(listed), "tokens": tokens_of(listed), "names": [t.name for t in listed]}
    if getattr(server, "shown", None) is not None:
        out["how"] = getattr(session, "_ctx_how", {})
        out["stats"] = {k: v for k, v in stats(session).items() if k != "sent"}
        out["stats"]["sent"] = stats(session)["sent"][-10:]
    return out

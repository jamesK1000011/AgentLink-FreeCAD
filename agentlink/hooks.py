# SPDX-License-Identifier: LGPL-2.1-or-later
"""How other add-ons plug into Agent Link without Agent Link knowing them.

Agent Link API 1. An add-on's agentlink_families module (found on the path,
never named here) may say which API it needs:

    AGENTLINK_API = ">=1,<2"

and is left out, with the reason in the log, when this Agent Link does not
meet it. Everything below is optional; an add-on uses what it needs. Every
hook swallows and logs an add-on's exception rather than let it stop
FreeCAD or another add-on. docs/hooks.md is the reference for developers.

Families (the tools)          FAMILIES = [module, ...] in agentlink_families;
                              each module has GROUP, INFO, tools(session),
                              and may set LEAN = True to be in the default list,
                              and HEAVY, WRITERS, GEOMETRIC (sets of its tool
                              names: queued heavy jobs; a path written, not
                              read; a path that is a curve, not a file).
Readers                       register_reader(kind, fn); readers(kind)
Services                      provide(name, obj); service(name); core's own
                              for add-ons: "overlay" (agentlink/overlay.py:
                              rings, badges, a callout over the window),
                              "annotations" (agentlink/annotate.py: faces,
                              edges, vertices lit in the 3D view),
                              "panel_layout", "panel_caller"
Finding controls              agentlink.targets: command_for, actions,
                              buttons, group_buttons (a command inside a
                              toolbar dropdown), menus_of, menu_path,
                              native_menubar
Echo                          a family's NO_ECHO (names or prefixes): its
                              tools are never shown as they run
Events                        on(event, fn); off(event, fn); emit(event, *args);
                              call_done(session, tool, ok, changed) after
                              every call through the server;
                              document_closing(session, name) before
                              doc_close closes a document: an add-on
                              that holds it (rings, timers, a task
                              panel) lets go of it first
Rider line                    register_rider(owner, fn): fn(tool) -> a short
                              line while the add-on has something in hand,
                              else None; every active line joins each
                              answer as "rider" (rider_line below)
Who is acting                 agent_acting(): True while one of the agent's
                              calls runs (not a panel click), so an
                              add-on's observers keep the person's events
                              apart from the agent's; not inside gui_input
                              with as: "person" (person_input, dev only)
Socket-thread tools           register_thread_tool(name): the window link
                              answers it on its socket thread (a long poll
                              that never holds the GUI thread); the tool
                              reads only what it keeps under its own lock
Window events                 watch_window(owner) / unwatch_window(owner):
                              while any owner watches, workbench_activated
                              (name, by) and command_used(name, by) are
                              emitted (agentlink/gui_events.py)
Test flag                     AGENTLINK_AS_USER=1 (as_user()): the agent's
                              calls run as the person's (session.by);
                              for tests only, off by default
Tool extensions               extend_tool(name, properties, before, after, describe)
Panel                         register_tab(title, factory, order, workbench,
                              own_credit)
                              (the widget's fill(), if any, runs as its tab
                              comes up; the tab shows only while workbench
                              is active); tab_in(title, *workbenches);
                              register_reviewer(fn); the service
                              "panel_layout" (agentlink/layout.py) places
                              an add-on's own panel beside Agent Link's
Protected settings            guard_setting(path, name)
Last results                  remember(session, kind, value); analysis(session, kind)
State per document            session.family_state is one dict per document
                              (agentlink/docstates.py): set aside when the
                              session leaves it, back when it returns; the
                              events document_state_leaving and
                              document_state_entered; own_document_state(key)
                              for an add-on that settles its own
Tools as data                 tools_from_data(folder, group, handlers):
                              the add-on's tools.json (agentlink/tooldata.py
                              is the format) bound to its handlers
Guides                        tools.register_guides(folder)
Render layers and maps        render.register_layer / render.register_map
Tools from Python             agentlink.run(tool, args); agentlink.serving(server)
"""

import sys

API = 1


def _parse(v):
    return tuple(int(x) for x in str(v).split("."))


def api_ok(spec, api=API):
    """True when this API meets spec (">=1,<2"); None or "" accepts any."""
    if not spec:
        return True
    have = _parse(api)
    for clause in (c.strip() for c in str(spec).split(",") if c.strip()):
        for op in (">=", "<=", "==", ">", "<"):
            if clause.startswith(op):
                want = _parse(clause[len(op):].strip())
                n = max(len(have), len(want))
                a, b = have + (0,) * (n - len(have)), want + (0,) * (n - len(want))
                if not {">=": a >= b, "<=": a <= b, "==": a == b, ">": a > b, "<": a < b}[op]:
                    return False
                break
        else:
            return False
    return True


def tools_from_data(folder, group, handlers, who="this add-on"):
    """An add-on's tools for one group from its folder/tools.json (the format
    is agentlink/tooldata.py), each bound to its handler by name."""
    from . import tooldata

    return tooldata.build(folder, group, handlers, who)


def _log(what, e):
    sys.stderr.write(f"Agent Link: {what} ({type(e).__name__}: {e})\n")


# ---- readers: answers to a question by kind ("wall": the thinnest wall of
# a shape; "thread_scan": a thread read from a scan). Each fn returns its
# answer or None to pass; the first answer wins. The lists are live, so an
# add-on written for the old attributes (printability.WALL_READERS) still
# lands here.
_READERS = {}


def readers(kind):
    return _READERS.setdefault(kind, [])


def register_reader(kind, fn):
    lst = readers(kind)
    if fn not in lst:
        lst.append(fn)
    return fn


def read(kind, *args, **kw):
    for fn in list(readers(kind)):
        try:
            got = fn(*args, **kw)
        except Exception as e:  # noqa: BLE001
            _log(f"a {kind} reader failed", e)
            continue
        if got is not None:
            return got
    return None


# ---- services: one named object an add-on offers (process_of, checkpoints,
# reopen, material_cards, frame_solver, encased …); absent gives None, and
# whoever asks says what is missing.
#   checkpoints   take(session, name=None, auto=False, doc=None) -> (entry, dropped);
#                 find(session, ref) -> entry or None; index(doc_name) -> [entry];
#                 restore(session, ref) -> answer. An entry: { id, name, file,
#                 step, tx, session, … }. Used by history_diff { since: "cp3" },
#                 before heavy jobs and before app_restart saves.
#   reopen        keep([doc]) -> [{ name, label, file, copy, t }]: before
#                 app_restart, copies of the changed documents it does not
#                 save, reopened beside their files once FreeCAD is back.
#   notice        fn() -> a short line or None, asked after every tool call;
#                 a line rides once on that answer as "notice" (notice() below).
_SERVICES = {}


def provide(name, obj):
    _SERVICES[name] = obj
    return obj


def service(name):
    return _SERVICES.get(name)


# The notice provider is asked with a short wait: a slow one never holds an
# answer up, and the line it gives late rides on the next answer instead.
NOTICE_WAIT = 0.2
_notice = {"late": [], "busy": False}


def notice():
    """The line the notice service has for the agent now, or None. A provider
    that raises is logged and skipped."""
    fn = _SERVICES.get("notice")
    if fn is None:
        return None
    if _notice["late"]:
        return _notice["late"].pop(0)
    if _notice["busy"]:
        return None
    import threading

    box, lock, done = {}, threading.Lock(), threading.Event()

    def ask():
        try:
            line = fn()
            line = str(line) if line else None
        except Exception as e:  # noqa: BLE001
            _log("the notice service failed", e)
            line = None
        with lock:
            box["line"] = line
            if box.get("late") and line:
                _notice["late"].append(line)
            _notice["busy"] = False
            done.set()

    _notice["busy"] = True
    threading.Thread(target=ask, name="agentlink-notice", daemon=True).start()
    done.wait(NOTICE_WAIT)
    with lock:
        if done.is_set():
            return box["line"]
        box["late"] = True
    return None


# ---- the rider line: short lines from any number of add-ons that join each
# answer while they have something in hand ("lesson: step 3/7 passed"), as
# "rider". Unlike the one notice service, every provider is asked, each
# line is cut to RIDER_EACH characters and the whole to RIDER_MAX; a
# provider with nothing in hand answers None and adds nothing. Providers
# are asked on the thread that answers, so they read what they keep in
# memory and return at once.
RIDER_EACH = 80
RIDER_MAX = 200
_RIDERS = []


def register_rider(owner, fn):
    """fn(tool) -> a short line or None, asked after each call to tool.
    Registering again under the same owner replaces the provider."""
    _RIDERS[:] = [r for r in _RIDERS if r[0] != owner]
    _RIDERS.append((owner, fn))
    return fn


def unregister_rider(owner):
    _RIDERS[:] = [r for r in _RIDERS if r[0] != owner]


def _cut(text, n):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def rider_line(tool=None):
    """Every active provider's line for an answer to tool, joined with
    " · " and capped; None when none is active. A provider that raises is
    logged and skipped."""
    lines = []
    for owner, fn in list(_RIDERS):
        try:
            got = fn(tool)
        except Exception as e:  # noqa: BLE001
            _log(f"the {owner} rider failed", e)
            continue
        if got:
            lines.append(_cut(got, RIDER_EACH))
    if not lines:
        return None
    return _cut(" · ".join(lines), RIDER_MAX)


# ---- who is acting: the agent's own calls (protocol.Server.call, which
# every call goes through, the window link's and the echo's alike) set it
# while they run; a panel click (session.by "person") does not. Read on
# the GUI thread by an add-on's observers.
_ACTING = [0]


class acting:
    def __enter__(self):
        _ACTING[0] += 1
        return self

    def __exit__(self, *exc):
        _ACTING[0] = max(0, _ACTING[0] - 1)
        return False


def agent_acting():
    n = _ACTING[0]
    return n > 0 and not (_PERSON_AT and _PERSON_AT[-1] == n)


# ---- the person's hands, for one call: gui_input's dev-only as: "person"
# (a student agent standing in for the person, beside a teaching agent on the
# same link). While its steps run, agent_acting() is False at the depth of
# the call that opened it, so the window events its input makes are the
# person's; an agent's call that runs inside it (a call taken while a
# step's menu or dialog loop holds the window) is one level deeper and
# stays the agent's. Attribution follows the call: no global toggle, so a
# teaching agent's calls on the same link before, after or inside it are
# untouched. close() is idempotent; the with block closes it on any exit.
_PERSON_AT = []


class person_input:
    def __init__(self):
        self.level = None

    def __enter__(self):
        self.level = _ACTING[0]
        _PERSON_AT.append(self.level)
        return self

    def close(self):
        if self.level is None:
            return
        for i in range(len(_PERSON_AT) - 1, -1, -1):
            if _PERSON_AT[i] == self.level:
                del _PERSON_AT[i]
                break
        self.level = None

    def __exit__(self, *exc):
        self.close()
        return False


# ---- socket-thread tools: answered by the window link on its socket
# thread, never queued for the GUI thread and never holding in_call (a long
# poll such as a watch). Such a tool reads only data it keeps behind its own
# lock and touches no FreeCAD or Qt object; it gets no undo step, echo,
# call_done, notice or rider.
THREAD_TOOLS = set()


def register_thread_tool(name):
    THREAD_TOOLS.add(str(name))
    return name


# ---- window events for add-ons, only while some owner watches
# (agentlink/gui_events.py): workbench_activated(name, by) and
# command_used(name, by), by "agent" or "person" (agent_acting()).
_WATCHERS = set()


def watch_window(owner):
    """Start the window events for owner; True when they could start."""
    _WATCHERS.add(owner)
    try:
        from . import gui_events

        return gui_events.attach()
    except Exception as e:  # noqa: BLE001
        _log("window events could not start", e)
        return False


def unwatch_window(owner):
    _WATCHERS.discard(owner)
    if not _WATCHERS:
        try:
            from . import gui_events

            gui_events.detach()
        except Exception as e:  # noqa: BLE001
            _log("window events could not stop", e)


# ---- the test flag: AGENTLINK_AS_USER=1 runs the agent's calls as the
# person's (session.by "person"), so an add-on that tells the two apart
# (a lesson the person works through) can be tested end to end by an agent.
# For tests only; off by default, and logged once when on.
AS_USER_ENV = "AGENTLINK_AS_USER"
_as_user_said = []


def as_user():
    import os

    on = os.environ.get(AS_USER_ENV, "") == "1"
    if on and not _as_user_said:
        _as_user_said.append(True)
        sys.stderr.write(f"Agent Link: {AS_USER_ENV}=1, the agent's calls count as the person's (a test flag)\n")
    return on


# ---- events: after_change(session, tool_name); setting_changing(tool, path)
# before a settings change and setting_changed(path, name, old, new, tool=,
# restart=, applies=) after each value (pref_set, pref_reset, pref_pack,
# pref_import); reply_written(session) after each reply of the stdio server;
# workbench_activated(name, by) and command_used(name, by) while an add-on
# watches the window (watch_window);
# docs_changed(session); call_done(session, tool_name, ok, changed) after
# every call through the server (protocol.Server.call), refusals too:
# changed is True when the call went through and changed the document (an
# undo step taken or given back, or a changing tool's call), so an add-on
# re-reads what it follows after the agent's own calls and the person's
# panel clicks alike (session.by says whose).
_EVENTS = {}


def on(event, fn):
    lst = _EVENTS.setdefault(event, [])
    if fn not in lst:
        lst.append(fn)
    return fn


def off(event, fn):
    """fn no longer told of event."""
    lst = _EVENTS.get(event) or []
    if fn in lst:
        lst.remove(fn)


def emit(event, *args, **kw):
    for fn in list(_EVENTS.get(event, ())):
        try:
            fn(*args, **kw)
        except Exception as e:  # noqa: BLE001
            _log(f"{event} handler failed", e)


# ---- tool extensions: arguments and answers added to a tool another family
# owns, without renaming it. before(args, session) may change the arguments
# (returns them, or None to keep them); after(args, answer, session) may add
# to the answer (returns it, or None to keep it).
_EXTENSIONS = {}


# Tools no add-on extends (red team, 2026-11-18): a before hook could put
# its own words in their arguments, so the person's OK and the settings
# that guard code stay Agent Link's own.
# An add-on keeps one of its own tools out of reach with keep_unextended().
NOT_EXTENDED = {"cookbook_approve", "cookbook_unapprove", "cookbook_import", "cookbook_run", "app_extensions", "addon",
                "pref_set", "pref_reset", "pref_import", "pref_pack", "agentlink_update", "batch",
                "gui_input", "dialog_answer", "cmd_run", "menu_run", "app_restart"}


def keep_unextended(name):
    """No add-on extends this tool (an add-on's own OK, such as approving
    a macro). Checked when the extensions are put on, so the order in
    which add-ons load does not matter."""
    NOT_EXTENDED.add(str(name))


def extendable(name):
    return name not in NOT_EXTENDED and "approve" not in str(name)
DESCRIBE_MAX = 300


def extend_tool(name, properties=None, before=None, after=None, describe=None):
    """describe: a sentence added to the tool's description, saying what the
    extension's arguments and answers are (one line, DESCRIBE_MAX characters
    or fewer). A tool in NOT_EXTENDED, or with "approve" in its name, is
    not extended: apply_extensions logs it and leaves it out."""
    if describe is not None:
        # One line with no control, invisible or direction characters (red
        # team 4, R4-8): an add-on's words go into a tool's description.
        from . import approvals

        describe = approvals.clean(describe, DESCRIBE_MAX).rstrip("…")[:DESCRIBE_MAX]
    props = {k: v for k, v in dict(properties or {}).items() if isinstance(k, str) and k.isidentifier() and not k.startswith("_")}
    _EXTENSIONS.setdefault(name, []).append({"properties": props, "before": before, "after": after, "describe": describe})
    return extendable(name)


def person_ok(kind, name, title, lines, sha=None, on_ok=None, shown=None):
    """The person's approval for an add-on's own approvals (a macro, a
    recovered copy): agentlink/approvals.py ask(). Answers {"ok": True}, or
    {"pending": True, "approve": {"tool", "arguments"}, "next"}: the agent
    calls approve_file or approve_code with those arguments, which the
    person sets in the client's tool permissions. kind "dialog", "recover"
    or "save-all" is approve_file's; every other kind is approve_code's.
    shown: the facts the client shows the person (source, version, author;
    document, file, button). A typed confirm is never an approval."""
    from . import approvals

    return approvals.ask(kind, name, title, lines, sha, on_ok, shown=shown)


approval = person_ok


def approval_in_window(answer, then=None):
    """For a person's own action in an add-on's panel (a button): show
    Agent Link's Approve dialog in the FreeCAD window for a pending answer
    of person_ok. Only a system press by the person there counts
    (agentlink/person_ok.py); then() runs after it, on the window's thread.
    False when there is no window or nothing waits."""
    from . import approvals, person_ok as _p

    args = ((answer or {}).get("approve") or {}).get("arguments") or {}
    k = approvals.key(args.get("kind"), args.get("id"), args.get("fingerprint"))
    with approvals._lock:
        req = approvals._OPEN.get(k)
    if req is None:
        return False
    req["then"] = then
    return _p.offer(req, force=True)


def apply_extensions(tools, session):
    """Called once the server's tools are built."""
    by = {t.name: t for t in tools}
    for name, exts in _EXTENSIONS.items():
        t = by.get(name)
        if t is None:
            continue
        if not extendable(name):
            _log(f"extend_tool({name!r}) ignored", ValueError("this tool holds the person's OK or guards code; no add-on extends it"))
            continue
        # A copy: a data tool's schema is its entry's own dict, shared by
        # every server built in this process (and the entry stays as the
        # data says).
        import copy

        t.schema = copy.deepcopy(t.schema or {"type": "object"})
        props = t.schema.setdefault("properties", {})
        for x in exts:
            for k, v in x["properties"].items():
                props.setdefault(k, v)
            if x.get("describe") and x["describe"] not in t.description:
                t.description = t.description.rstrip() + " " + x["describe"]
        fn = t.fn

        def wrapped(a, _fn=fn, _exts=list(exts)):
            for x in _exts:
                if x["before"]:
                    try:
                        got = x["before"](a, session)
                    except Exception as e:  # noqa: BLE001 — an extension's refusal is the tool's
                        if type(e).__name__ == "ToolError":
                            raise
                        _log(f"an extension of {name} failed before it", e)
                        got = None
                    if got is not None:
                        a = got
            mine = {k: a[k] for x in _exts for k in x["properties"] if k in a}
            rest = {k: v for k, v in a.items() if k not in mine}
            out = _fn(rest)
            for x in _exts:
                if x["after"]:
                    try:
                        got = x["after"]({**rest, **mine}, out, session)
                    except Exception as e:  # noqa: BLE001
                        if type(e).__name__ == "ToolError":
                            raise
                        _log(f"an extension of {name} failed after it", e)
                        got = None
                    if got is not None:
                        out = got
            return out

        t.fn = wrapped


# ---- the panel: tabs from add-ons, and who reviews a part for the Review tab.
TABS = []
REVIEWERS = []
# Tab title -> the workbenches (their names, as FreeCADGui.activeWorkbench()
# .name() gives them) in which the tab shows. A tab named nowhere here
# shows in every workbench (an add-on written before tab_in).
TAB_WORKBENCHES = {}


def register_tab(title, factory, order=50, workbench=None, own_credit=False):
    """factory(panel) -> a QWidget, built when the panel is. workbench: a
    workbench name, or several, in which the tab shows (tab_in).
    own_credit: the tab's page carries its own credit line for the work it
    builds on, so Agent Link's is hidden while it is in front (one credit,
    not two)."""
    TABS.append({"title": title, "factory": factory, "order": order, **({"own_credit": True} if own_credit else {})})
    TABS.sort(key=lambda x: x["order"])
    if workbench:
        tab_in(title, *((workbench,) if isinstance(workbench, str) else workbench))


def tab_in(title, *workbenches):
    """Show the tab title (an add-on's, or Agent Link's Review) while one
    of workbenches is active."""
    TAB_WORKBENCHES.setdefault(title, set()).update(w for w in workbenches if w)


def register_reviewer(fn):
    """fn(session, body) -> {"verdict", "findings", ...} for the Review tab."""
    if fn not in REVIEWERS:
        REVIEWERS.append(fn)
    return fn


def review(session, body):
    """The Review tab's verdict on body: each reviewer in the order they
    registered, the first answer that is not None. None when no reviewer
    is installed or none answered; a reviewer that fails is logged and
    the next asked."""
    for fn in list(REVIEWERS):
        try:
            got = fn(session, body)
        except Exception as e:  # noqa: BLE001
            _log("a reviewer failed", e)
            continue
        if got is not None:
            return got
    return None


# ---- protected settings: pref_set refuses to change these (an add-on's
# own switches only the person changes, in its own panel).
GUARDED = set()


def guard_setting(path, name):
    GUARDED.add((path, name))


# ---- family state per document (agentlink/docstates.py) ----
def own_document_state(key):
    """An add-on that settles its own state per document says so: its key
    in session.family_state is then carried along with the session from
    document to document untouched, for the add-on to write, set aside and
    restore itself. Every other key is set aside with the document the
    session leaves and comes back when the session returns to it (the
    events document_state_leaving and document_state_entered say when)."""
    from . import docstates

    docstates.OWN.add(str(key))


def remember(session, kind, value):
    d = getattr(session, "_agentlink_results", None)
    if d is None:
        d = session._agentlink_results = {}
    d[kind] = value


def analysis(session, kind):
    return (getattr(session, "_agentlink_results", None) or {}).get(kind)


def saved():
    """For tests: every registration as it stands, for restore()."""
    return ({k: list(v) for k, v in _READERS.items()}, dict(_SERVICES), {k: list(v) for k, v in _EVENTS.items()},
            {k: list(v) for k, v in _EXTENSIONS.items()}, list(TABS), list(REVIEWERS), set(GUARDED),
            {k: set(v) for k, v in TAB_WORKBENCHES.items()}, list(_RIDERS))


def restore(state):
    readers_, services, events, exts, tabs, reviewers, guarded = state[:7]
    reset()
    TAB_WORKBENCHES.update(state[7] if len(state) > 7 else {})
    _RIDERS[:] = state[8] if len(state) > 8 else []
    for k, v in readers_.items():
        readers(k)[:] = v
    _SERVICES.update(services)
    _EVENTS.update(events)
    _EXTENSIONS.update(exts)
    TABS[:] = tabs
    REVIEWERS[:] = reviewers
    GUARDED.update(guarded)


def reset():
    """For tests: every registration forgotten."""
    del _PERSON_AT[:]
    for lst in _READERS.values():
        del lst[:]
    _SERVICES.clear()
    del _notice["late"][:]
    _EVENTS.clear()
    _EXTENSIONS.clear()
    del TABS[:]
    del REVIEWERS[:]
    TAB_WORKBENCHES.clear()
    GUARDED.clear()
    del _RIDERS[:]
    try:
        from . import docstates

        docstates.OWN.clear()
    except Exception:
        pass


# ---- who a call is for ----------------------------------------------------------------------

PERSON, AGENT = "person", "agent"


class as_person:
    """A call the person made by a click in a panel (Agent Link's own, or an
    add-on dock it hosts): session.by is "person" while it runs, then back
    to what it was ("agent" for the agent's session). Add-ons read
    session.by (a checkpoint labelled "My checkpoint" by it, say)."""

    def __init__(self, session):
        self.s = session
        self.was = None

    def __enter__(self):
        self.was = getattr(self.s, "by", AGENT)
        try:
            self.s.by = PERSON
        except Exception:
            pass
        return self.s

    def __exit__(self, *exc):
        try:
            self.s.by = self.was
        except Exception:
            pass
        return False

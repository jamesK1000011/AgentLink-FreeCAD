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
Services                      provide(name, obj); service(name)
Events                        on(event, fn); emit(event, *args)
Tool extensions               extend_tool(name, properties, before, after, describe)
Panel                         register_tab(title, factory, order);
                              register_reviewer(fn)
Protected settings            guard_setting(path, name)
Last results                  remember(session, kind, value); analysis(session, kind)
Tools as data                 tools_from_data(folder, group, handlers):
                              the add-on's tools.json (agentlink/tooldata.py
                              is the format) bound to its handlers
Guides                        tools.register_guides(folder)
Render layers and maps        render.register_layer / render.register_map
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
# material_cards, frame_solver, encased …); absent gives None, and whoever
# asks says what is missing.
_SERVICES = {}


def provide(name, obj):
    _SERVICES[name] = obj
    return obj


def service(name):
    return _SERVICES.get(name)


# ---- events: after_change(session, tool_name), setting_changed(path, name,
# old, new), docs_changed(session), call_done(session, tool_name, ok).
_EVENTS = {}


def on(event, fn):
    lst = _EVENTS.setdefault(event, [])
    if fn not in lst:
        lst.append(fn)
    return fn


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


def extend_tool(name, properties=None, before=None, after=None, describe=None):
    """describe: a sentence added to the tool's description, saying what the
    extension's arguments and answers are."""
    _EXTENSIONS.setdefault(name, []).append({"properties": dict(properties or {}), "before": before, "after": after, "describe": describe})


def apply_extensions(tools, session):
    """Called once the server's tools are built."""
    by = {t.name: t for t in tools}
    for name, exts in _EXTENSIONS.items():
        t = by.get(name)
        if t is None:
            continue
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


def register_tab(title, factory, order=50):
    """factory(panel) -> a QWidget, built when the panel is."""
    TABS.append({"title": title, "factory": factory, "order": order})
    TABS.sort(key=lambda x: x["order"])


def register_reviewer(fn):
    """fn(session, body) -> {"verdict", "findings", ...} for the Review tab."""
    if fn not in REVIEWERS:
        REVIEWERS.append(fn)
    return fn


# ---- protected settings: pref_set refuses to change these (an add-on's
# own switches only the person changes, in its own panel).
GUARDED = set()


def guard_setting(path, name):
    GUARDED.add((path, name))


# ---- last results by kind ("fea": the last solve), read-only to others.
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
            {k: list(v) for k, v in _EXTENSIONS.items()}, list(TABS), list(REVIEWERS), set(GUARDED))


def restore(state):
    readers_, services, events, exts, tabs, reviewers, guarded = state
    reset()
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
    for lst in _READERS.values():
        del lst[:]
    _SERVICES.clear()
    _EVENTS.clear()
    _EXTENSIONS.clear()
    del TABS[:]
    del REVIEWERS[:]
    GUARDED.clear()

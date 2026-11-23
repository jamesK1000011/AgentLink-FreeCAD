# SPDX-License-Identifier: LGPL-2.1-or-later
"""The static minimal tool list: the default since 17 Nov 2026 (arm C of
the A/B/C test won; classic stays one switch away).

ToolListMode (preference, Mod/AgentLink, text) or AGENTLINK_TOOLLIST:
    classic            the lean list, as before.
    static (default)   only BASE is listed: session_state, batch, guide_read,
                       tool_find, approve_file and approve_code (the person sets
                       the two approval tools in the client's permissions, so
                       the client must list them). Every other tool is found with
                       tool_find and called by name (in a batch where the
                       client sends only listed tools). The list never
                       changes by itself: no tools/list_changed, so every
                       client sees the same list. A group turned on with
                       tool_groups { enable } is listed too.
ToolDescStyle (preference, text) or AGENTLINK_DESC:
    full               the tools' own descriptions.
    ste (default)      the BASE tools' descriptions in ASD-STE100 from
                       data/ste.json; batch's full text is the batch guide
                       (guide_read { topic: "batch" }), and a refused batch
                       names it.
Both are read again at each tools/list, so a preference set while FreeCAD
runs takes effect when the client next lists the tools.
"""
import json
import os

BASE = ("session_state", "batch", "guide_read", "tool_find", "approve_file", "approve_code")
# With the fast path on (fastpath.enabled), its two tools are listed too:
# a client that sends only listed tools (OpenCode) can then call them
# directly, not only inside batch. Eight tools on, six off: the A/B test
# decides whether eight becomes the default for every client (owner, 22 Nov).
FAST = ("fast", "get")
PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
_STE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ste.json")
_cache = {}


def _pref(name, env, default, allowed):
    v = os.environ.get(env, "").strip().lower()
    if v in allowed:
        return v
    try:
        import FreeCAD

        v = FreeCAD.ParamGet(PREFS).GetString(name, default).strip().lower()
    except Exception:  # noqa: BLE001 - no FreeCAD here
        v = default
    return v if v in allowed else default


def mode():
    return _pref("ToolListMode", "AGENTLINK_TOOLLIST", "static", ("classic", "static"))


def style():
    return _pref("ToolDescStyle", "AGENTLINK_DESC", "ste", ("full", "ste"))


def ste_descriptions():
    if "ste" not in _cache:
        try:
            with open(_STE, encoding="utf-8") as f:
                _cache["ste"] = json.load(f)["entries"]
        except Exception:  # noqa: BLE001
            _cache["ste"] = {}
    return _cache["ste"]


def apply(server):
    """Set server.static_base from the mode now (None in classic)."""
    # A server without tool_find (a test server, a small add-on server on
    # this protocol) keeps its own list: the base is no use without a find.
    tools = getattr(server, "tools", None) or {}
    has_find = "tool_find" in tools
    server.static_base = base(tools) if mode() == "static" and has_find else None
    return server.static_base


def base(tools=None):
    """BASE, plus the fast path's two tools when it is on and they are here."""
    try:
        from . import fastpath

        on = fastpath.enabled()
    except Exception:  # noqa: BLE001 - a server without the fast path
        on = False
    if on and all(t in (tools or {}) for t in FAST):
        return BASE + FAST
    return BASE


def listing(server, tools):
    """The tools/list entries, with the STE descriptions when asked for."""
    out = [t.listing() for t in tools]
    if style() == "ste":
        ste = ste_descriptions()
        for e in out:
            if e.get("name") in ste:
                e["description"] = ste[e["name"]]
    return out


GUIDE_HINT = ' guide_read { topic: "batch" } has the rules (chaining with $from, to, lines, from/next).'


NOTHING_RAN = "Nothing was run."
BASIC_FORM = " The basic form: batch { calls: [{ tool, arguments }] }."


def batch_hint(message):
    """A batch refused whole (its own form: a refused call is a row of its
    answer, not this): the words say that nothing ran and give the basic
    form (local-model runs, 23 Nov: models put every field in a first
    batch); they name its guide when the short descriptions are listed."""
    m = message.rstrip()
    if "nothing was run" not in m.lower() and "nothing ran" not in m.lower():
        m += " " + NOTHING_RAN
    if BASIC_FORM.strip() not in m:
        m += BASIC_FORM
    if style() == "ste" and GUIDE_HINT.strip() not in m:
        m += GUIDE_HINT
    return m

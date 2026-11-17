# SPDX-License-Identifier: LGPL-2.1-or-later
"""The static minimal tool list (arms B and C of the 17 Nov A/B/C test).

ToolListMode (preference, Mod/AgentLink, text) or AGENTLINK_TOOLLIST:
    classic (default)  the lean list, as before.
    static             only BASE is listed: session_state, batch, guide_read
                       and tool_find. Every other tool is found with
                       tool_find and called by name (in a batch where the
                       client sends only listed tools). The list never
                       changes by itself: no tools/list_changed, so every
                       client sees the same list. A group turned on with
                       tool_groups { enable } is listed too.
ToolDescStyle (preference, text) or AGENTLINK_DESC:
    full (default)     the tools' own descriptions.
    ste                the BASE tools' descriptions in ASD-STE100 from
                       data/ste.json; batch's full text is the batch guide
                       (guide_read { topic: "batch" }), and a refused batch
                       names it.
Both are read again at each tools/list, so a preference set while FreeCAD
runs takes effect when the client next lists the tools.
"""
import json
import os

BASE = ("session_state", "batch", "guide_read", "tool_find")
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
    return _pref("ToolListMode", "AGENTLINK_TOOLLIST", "classic", ("classic", "static"))


def style():
    return _pref("ToolDescStyle", "AGENTLINK_DESC", "full", ("full", "ste"))


def ste_descriptions():
    if "ste" not in _cache:
        try:
            with open(_STE, encoding="utf-8") as f:
                _cache["ste"] = json.load(f)["descriptions"]
        except Exception:  # noqa: BLE001
            _cache["ste"] = {}
    return _cache["ste"]


def apply(server):
    """Set server.static_base from the mode now (None in classic)."""
    server.static_base = BASE if mode() == "static" else None
    return server.static_base


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


def batch_hint(message):
    """A refused batch names its guide when the short descriptions are listed."""
    if style() == "ste" and GUIDE_HINT.strip() not in message:
        return message.rstrip() + GUIDE_HINT
    return message

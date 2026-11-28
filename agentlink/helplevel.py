# SPDX-License-Identifier: LGPL-2.1-or-later
"""The help level: how much a tool's card gives besides its facts.

Level 0 (the default): the facts only (does, inputs, rules, returns).
Level 1: also hint, where a card has one. Level 2: also guards (none yet).
The facts are the same at every level; a level never changes what a tool
does or its defaults (owner, 27 Nov, decision 6).

The level is set outside the model (owner, 27 Nov, decision 12): the
person's preference HelpLevel (Mod/AgentLink), or AGENTLINK_HELP_LEVEL,
which a test runner sets per model. A call can still ask for a field by
name with what: [..] (tool_find { card, what: ["hint"] })."""
import os

PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
PREF = "HelpLevel"
ENV = "AGENTLINK_HELP_LEVEL"
LEVELS = (0, 1, 2)
# The card fields each level adds to the facts.
ADDS = {1: ("hint",), 2: ("hint", "guards")}


def level():
    """The help level now: AGENTLINK_HELP_LEVEL, else the preference, else 0."""
    v = os.environ.get(ENV)
    if v is not None and v.strip() != "":
        try:
            n = int(v.strip())
            return n if n in LEVELS else 0
        except ValueError:
            return 0
    try:
        import FreeCAD

        n = int(FreeCAD.ParamGet(PREFS).GetInt(PREF, 0))
        return n if n in LEVELS else 0
    except Exception:  # noqa: BLE001 - no FreeCAD here: the default
        return 0


def shown(field):
    """Whether a card field that is not a fact is shown at this level."""
    n = level()
    return any(field in ADDS.get(k, ()) for k in range(1, n + 1))

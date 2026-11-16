# SPDX-License-Identifier: LGPL-2.1-or-later
"""Which installed add-ons loaded their tools, and which were left out and
why: kept in memory for the tools (session_state, tool_groups) and on disk
(~/AgentLink/extensions.json) for what runs outside this FreeCAD — the
launcher's update, its smoke test, the supervisor.

An add-on whose agentlink_families module fails at import (a SyntaxError
after an update) used to be said in the Report view only: the update
answered success and its tools were gone without a word. Everything left
out is noted here, with its error, where the families load
(agentlink/families/__init__.py load(), agentlink/tools.py build_server).

Plain Python, no FreeCAD: the rules are tested without it.
"""
import os
import time

from . import keep

FILE = "extensions.json"
# Set by the smoke test (agentlink/smoke.py): the server it builds is a
# trial of add-ons not yet in use, and must not replace the record of what
# runs.
NO_RECORD = "AGENTLINK_NO_EXTENSION_RECORD"
# Given to the smoke test by the launcher: the extension modules that
# loaded before the update, comma-separated.
BEFORE = "AGENTLINK_LOADED_BEFORE"

# This process's own reading, set anew each time the families load.
_left = []    # [{ extension, error, stage }]
_loaded = {}  # extension -> { groups: [..], tools: n }


def reset():
    del _left[:]
    _loaded.clear()


def _cut(text, n=400):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def error_words(e):
    """An exception as one line: its kind, its message, and for a
    SyntaxError the file's name and line (never a folder)."""
    if isinstance(e, str):
        return _cut(e)
    words = f"{type(e).__name__}: {e}"
    if isinstance(e, SyntaxError) and e.filename:
        base = os.path.basename(str(e.filename))
        if base not in words:
            words += f" ({base}, line {e.lineno})"
        else:
            # Python's own message carries the whole path: only the name stays.
            words = words.replace(str(e.filename), base)
    return _cut(words)


def left_out(extension, error, stage="import"):
    """Note an add-on (its agentlink_families module's name) left out.
    stage: import (the module raised), api (it needs another Agent Link
    API), tools (its tools() raised), names (every tool's name was taken)."""
    row = {"extension": str(extension), "error": error_words(error), "stage": stage}
    for old in _left:
        if old["extension"] == row["extension"] and old["stage"] == stage:
            old.update(row)
            return row
    _left.append(row)
    return row


def loaded(extension, group=None, tools=0):
    """Note an add-on found, and the tools one of its groups brought."""
    row = _loaded.setdefault(str(extension), {"groups": [], "tools": 0})
    if group and group not in row["groups"]:
        row["groups"].append(group)
    row["tools"] += int(tools or 0)
    return row


def state():
    """{ loaded: [{ extension, groups, tools }], leftOut: [{ extension,
    error }], noTools: [{ extension, error }] }: noTools is every installed
    add-on that brought no tool at all — those left out, and those that
    loaded and gave none."""
    left = [{"extension": r["extension"], "error": r["error"]} for r in _left]
    whole = {r["extension"] for r in _left if r["stage"] in ("import", "api")}
    rows = [{"extension": k, "groups": list(v["groups"]), "tools": v["tools"]} for k, v in _loaded.items() if k not in whole]
    no_tools = [r for r in left if _loaded.get(r["extension"], {}).get("tools", 0) == 0]
    said = {r["extension"] for r in no_tools}
    no_tools += [{"extension": r["extension"], "error": "it loaded, and its families gave no tools"} for r in rows if r["tools"] == 0 and r["extension"] not in said]
    return {"loaded": [r for r in rows if r["tools"] > 0], "leftOut": left, "noTools": no_tools}


def short_name(extension):
    """somepackage.agentlink_families → somepackage."""
    return str(extension).rsplit(".agentlink_families", 1)[0]


def warning(left, lost_groups=()):
    """The plain warning for an answer, or None when nothing is left out."""
    left = [r for r in (left or []) if isinstance(r, dict) and r.get("extension")]
    if not left:
        return None
    names = ", ".join(dict.fromkeys(short_name(r["extension"]) for r in left))
    one = len(set(r["extension"] for r in left)) == 1
    words = (f"An installed add-on did not load, so its tools are not here: {names}." if one
             else f"Installed add-ons did not load, so their tools are not here: {names}.")
    lost = [g for g in (lost_groups or ()) if g]
    if lost:
        words += f" Tool groups gone: {', '.join(lost)}."
    words += (" leftOut gives each one's error. It is a fault in the add-on's own code or a version that does not fit this Agent Link:"
              " fix or update the add-on, then agentlink_update (or app_restart for the window); report_read shows the log.")
    return words


def lost_groups(before, after):
    """The tool groups in before ({ group: count }) that after lacks."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []
    return sorted(g for g, n in before.items() if n and not after.get(g))


def groups_of(tools):
    """{ group: count } of a server's tools."""
    out = {}
    for t in tools:
        g = getattr(t, "group", None)
        if g:
            out[g] = out.get(g, 0) + 1
    return out


# ---- on disk ------------------------------------------------------------------------------

def record_path():
    return keep.path(FILE)


def write(groups=None, window=False, version=None):
    """This process's reading to ~/AgentLink/extensions.json, under
    "window" or "hidden" (the two FreeCADs load the same add-ons but not
    always the same families). Not under the smoke test. Never raises."""
    if os.environ.get(NO_RECORD):
        return None
    try:
        p = record_path()
        whole = keep._load(p, {})
        if not isinstance(whole, dict):
            whole = {}
        st = state()
        whole["window" if window else "hidden"] = {
            "t": time.time(), "pid": os.getpid(), "version": version,
            "loaded": st["loaded"], "leftOut": st["leftOut"], "noTools": st["noTools"], "groups": dict(groups or {}),
        }
        keep._save(p, whole)
        return p
    except Exception:  # noqa: BLE001 - a record, never in the way of the server
        return None


def read(window=False):
    """What write() kept for the window or the hidden FreeCAD, or {}."""
    whole = keep._load(record_path(), {})
    got = whole.get("window" if window else "hidden") if isinstance(whole, dict) else None
    return got if isinstance(got, dict) else {}


# ---- the smoke test's rule ----------------------------------------------------------------

def before_list(text):
    """The extension modules named in AGENTLINK_LOADED_BEFORE."""
    return [x.strip() for x in str(text or "").split(",") if x.strip()]


def smoke_failures(left, before):
    """The smoke test's failures for add-ons left out: one per add-on that
    loaded before the update (before: module names) and no longer does. One
    that never loaded here is a warning in the answer, not a failed update."""
    was = set(before or ())
    out = []
    for r in left or []:
        if r.get("extension") in was:
            out.append(f"the add-on {short_name(r['extension'])} loaded before and no longer does ({r.get('error')}): its tools would be gone")
    return out

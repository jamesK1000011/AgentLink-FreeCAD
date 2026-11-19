# SPDX-License-Identifier: LGPL-2.1-or-later
# The tool families beyond the first ones: each a module here with GROUP (its
# group's name), INFO (one line on what the group holds) and tools(session)
# giving its Tool list. A family whose FreeCAD module is missing in this
# build (FEM, TechDraw …) is left out, and says why in the server's log.

import importlib
import os
import sys

# One line each, in the order they are listed.
NAMES = [
    "doc",
    "model",
    "model_more",
    "part_more",
    "measure",
    "sketch",
    "sketch_more",
    "feature",
    "feature_more",
    "param",
    "sheet",
    "material",
    "strength",
    "techdraw",
    "inspection",
    "view",
    "notes",
    "app",
    "meshobj",
    "assembly",
    "assembly_more",
    "cam",
    "draft",
    "draft_more",
    "surface",
    "points",
    "bim",
    "bim_more",
    "ifc",
    "openscad",
    "robot",
    "std_more",
    "cam_more",
    "bim_gaps",
    "fem_more",
    "unattended",
    "dev",
    "porting",
]


# Families from other add-ons, found at run time and never named here: any
# package on the path holding an agentlink_families module (FreeCAD puts
# each Mod folder on the path), and modules named in AGENTLINK_EXTENSIONS
# (comma-separated). Its FAMILIES keep the same contract. Each keeps its
# own licence; nothing of theirs is part of this add-on, and this add-on
# imports none of them by name.


def _discovered():
    found = []
    for d in list(sys.path):
        if not d or not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for pkg in names:
            if pkg.startswith((".", "_")) or not pkg.isidentifier():
                continue
            if os.path.isfile(os.path.join(d, pkg, "agentlink_families.py")) and os.path.isfile(os.path.join(d, pkg, "__init__.py")):
                n = f"{pkg}.agentlink_families"
                if n not in found:
                    found.append(n)
    return found


# The extensions loaded, each with its own credit and licence (their
# agentlink_families module's CREDIT and LICENSE): shown where they load.
EXTENSIONS = []
# Extensions left out because they need another Agent Link API, and why.
SKIPPED = []
# Tools an add-on declares free of the window's pinned document (its
# family's PINNED_FREE): answered even after the person closed the document
# the agent was working in, as doc_open and session_state are.
PINNED_FREE = set()


def load():
    # Add-ons installed beside Agent Link by app_extensions go on the path
    # first, so their agentlink_families are found below.
    try:
        from .. import ext

        ext._paths()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Agent Link: extension folders not put on the path — {e}\n")
    from .. import extstate

    out = []
    del EXTENSIONS[:]
    del SKIPPED[:]
    # Which add-ons load and which are left out, with why: read by
    # session_state, tool_groups and the update (agentlink/extstate.py).
    extstate.reset()
    for n in NAMES:
        try:
            out.append(importlib.import_module(f"{__name__}.{n}"))
        except ImportError as e:
            sys.stderr.write(f"Agent Link: the {n} tools are left out — {e}\n")
    extra = [x.strip() for x in os.environ.get("AGENTLINK_EXTENSIONS", "").split(",") if x.strip()]
    seen = set()
    for n in _discovered() + extra:
        if n in seen:
            continue
        seen.add(n)
        # An add-on that fails to load (an older or newer Agent Link than it
        # expects) is left out and said, not allowed to stop this one.
        try:
            mod = importlib.import_module(n)
            fams = list(getattr(mod, "FAMILIES", []))
        except Exception as e:
            sys.stderr.write(f"Agent Link: extension {n} left out — {type(e).__name__}: {e}\n")
            extstate.left_out(n, e, "import")
            continue
        from .. import hooks

        need = getattr(mod, "AGENTLINK_API", None)
        if not hooks.api_ok(need):
            sys.stderr.write(f"Agent Link: extension {n} left out — it needs Agent Link API {need}, this is API {hooks.API}; update one or the other\n")
            SKIPPED.append({"module": n, "needs": need, "api": hooks.API})
            extstate.left_out(n, f"it needs Agent Link API {need}, this is API {hooks.API}: update one or the other", "api")
            continue
        _register_guides(mod)
        credit, lic = getattr(mod, "CREDIT", None), getattr(mod, "LICENSE", None)
        extstate.loaded(n)
        for f in fams:
            f.EXTERNAL = True
            f.EXTENSION = n
            f.CREDIT = credit
            f.LICENSE = lic
        if fams:
            EXTENSIONS.append({"credit": credit, "license": lic, "groups": [getattr(f, "GROUP", "?") for f in fams]})
        out.extend(fams)
    declared(out)
    return out


def _register_guides(mod):
    """An add-on's guides/ (or freecad_guides/) folder beside its
    agentlink_families module, registered for guide_read: no code needed in
    the add-on."""
    try:
        from .. import tools

        here = os.path.dirname(os.path.abspath(mod.__file__))
        # freecad_guides/ is the add-on's guides for FreeCAD when its plain
        # guides/ serve its own server elsewhere: then only it is read.
        mine = os.path.join(here, "freecad_guides")
        tools.register_guides(mine if os.path.isdir(mine) else os.path.join(here, "guides"))
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Agent Link: {getattr(mod, '__name__', '?')}'s guides not registered — {e}\n")


def declared(fams):
    """What each family says of its own tools, so no list here names them:
    HEAVY (queued, timed, given a deadline), WRITERS (their path is written,
    not read), GEOMETRIC (their path is a curve, not a file), NOT_IN_MACROS
    (changing calls a saved macro does not replay), PINNED_FREE (answered
    after the window's pinned document was closed), NEXT (rules for the
    "next" hint, agentlink/nexthint.py), and for the live echo in the
    window SHOWN, AREAS, WORKBENCHES, COMMANDS and PAGES
    (agentlink/echo.py declare())."""
    from .. import echo, keep, paths

    try:
        from .. import tools
    except ImportError:  # no FreeCAD (tests)
        tools = None
    for f in fams:
        paths.WRITERS.update(getattr(f, "WRITERS", ()) or ())
        if getattr(f, "EXTERNAL", False):
            refuse_hiding(f)
            # An add-on's GEOMETRIC (no path check), PINNED_FREE, HEAVY and
            # NOT_IN_MACROS count only for its own tools: owned() adds them
            # once its tools are made (red team, 2026-11-18: an add-on that
            # said "export" was GEOMETRIC turned off the path check of the
            # hub's export; red team 2, R2-4: HEAVY made approve_code a job).
            continue
        keep.declare_heavy(getattr(f, "HEAVY", ()) or ())
        if tools is not None:
            tools.NOT_IN_MACROS.update(x for x in (getattr(f, "NOT_IN_MACROS", ()) or ()) if isinstance(x, str))
        paths.GEOMETRIC.update(getattr(f, "GEOMETRIC", ()) or ())
        PINNED_FREE.update(x for x in (getattr(f, "PINNED_FREE", ()) or ()) if isinstance(x, str) and x)
        echo.declare(f)
        # NEXT: an add-on's own rules for the "next" hint ({ id: entry },
        # the shape of data/nexthint.json's entries): its tools named as the
        # likely next step in the states it says.
        nxt = getattr(f, "NEXT", None)
        if nxt:
            from .. import nexthint

            for words in nexthint.declare(nxt, str(getattr(f, "GROUP", None) or "an add-on")):
                sys.stderr.write(f"Agent Link: {words} — left out\n")


def owned(fam, names):
    """An add-on family's GEOMETRIC, PINNED_FREE, HEAVY, NOT_IN_MACROS,
    PATH_KEYS and WRITE_KEYS, for the tools it made and that loaded (names); a name of another's tool
    is left out, said."""
    from .. import keep, paths

    try:
        from .. import tools
        macros = tools.NOT_IN_MACROS
    except ImportError:  # no FreeCAD (tests)
        macros = set()
    names = set(names)
    heavy = set()
    for attr, into in (("GEOMETRIC", paths.GEOMETRIC), ("PINNED_FREE", PINNED_FREE), ("HEAVY", heavy), ("NOT_IN_MACROS", macros)):
        for x in getattr(fam, attr, ()) or ():
            if not isinstance(x, str) or not x:
                continue
            if x in names:
                into.add(x)
            else:
                sys.stderr.write(f"Agent Link: {getattr(fam, 'EXTENSION', '?')} declares {x} in {attr}, but {x} is not its tool — left out\n")
    if heavy:
        keep.declare_heavy(heavy)
    # PATH_KEYS and WRITE_KEYS: {tool: ["texture.file", "profiles.*", ...]},
    # its other fields that hold a file it reads or writes (red team 3, R3-10).
    for attr, kind in (("PATH_KEYS", "read"), ("WRITE_KEYS", "write")):
        v = getattr(fam, attr, None) or {}
        if not isinstance(v, dict):
            sys.stderr.write(f"Agent Link: {getattr(fam, 'EXTENSION', '?')} declares {attr} as {type(v).__name__}, not {{tool: [fields]}} — left out\n")
            continue
        for tool, keys in v.items():
            if tool not in names:
                sys.stderr.write(f"Agent Link: {getattr(fam, 'EXTENSION', '?')} declares {tool} in {attr}, but {tool} is not its tool — left out\n")
                continue
            if isinstance(keys, str):
                keys = [keys]
            bad = paths.declare_keys(tool, **{kind: list(keys or ())})
            if bad:
                sys.stderr.write(f"Agent Link: {getattr(fam, 'EXTENSION', '?')} declares {bad} in {attr} for {tool}: not field names — left out\n")


# What an add-on may never say of the hub's tools and groups (the owner, 18 Nov
# 2026): it never hides or replaces a hub tool or group. Its tools sit
# beside the hub's. (REPLACES once left a hub group out of the listing.)
HIDING = ("REPLACES", "HIDES", "HIDE", "REPLACE")


def refuse_hiding(fam):
    """An add-on family that says REPLACES or HIDES: refused at load, said
    in the log, and the attribute taken off. Its own tools still load.
    The attributes refused."""
    out = []
    for attr in HIDING:
        v = getattr(fam, attr, None)
        if not v:
            continue
        out.append(attr)
        sys.stderr.write(f"Agent Link: {getattr(fam, 'EXTENSION', None) or getattr(fam, 'GROUP', '?')} declares {attr} {sorted(map(str, v)) if not isinstance(v, str) else v!r} — "
                         f"refused: an add-on never hides or replaces a hub tool or group; its tools sit beside them\n")
        try:
            setattr(fam, attr, ())
        except Exception:  # noqa: BLE001
            pass
    return out

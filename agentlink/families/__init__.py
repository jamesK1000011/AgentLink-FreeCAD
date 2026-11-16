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
        keep.declare_heavy(getattr(f, "HEAVY", ()) or ())
        if tools is not None:
            tools.NOT_IN_MACROS.update(x for x in (getattr(f, "NOT_IN_MACROS", ()) or ()) if isinstance(x, str))
        paths.WRITERS.update(getattr(f, "WRITERS", ()) or ())
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

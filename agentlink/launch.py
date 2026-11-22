# SPDX-License-Identifier: LGPL-2.1-or-later
"""`agentlink-freecad`: the MCP server started from a package (uvx, pip)
rather than from the add-on's folder. The Python that runs this is uv's or
any other; it finds FreeCAD (agentlink/setup_check.py) and runs
agentlink_headless.py in FreeCAD's own Python, which serves.

    agentlink-freecad [--out DIR]       headless; a call goes to the FreeCAD window instead while its link is on
    agentlink-freecad --own [--out DIR] headless only: its own hidden FreeCAD, never the window (or AGENTLINK_OWN=1)
    agentlink-freecad --connect [PORT]  relay to the FreeCAD window's Start link (needs no FreeCAD here)
    agentlink-freecad --check [--json]  what is missing and how to get it
    agentlink-freecad --version         the version (needs no FreeCAD)
"""

import importlib.util
import os
import subprocess
import sys


def _headless():
    spec = importlib.util.find_spec("agentlink_headless")
    if spec and spec.origin:
        return spec.origin
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agentlink_headless.py")


def version():
    """The server's VERSION, read from server.py without importing it."""
    import re

    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py"), encoding="utf-8") as f:
            m = re.search(r'(?m)^VERSION = "([^"]+)"', f.read())
        return m.group(1) if m else "unknown"
    except OSError:
        return "unknown"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--version" in argv or "-V" in argv:
        sys.stdout.write(f"agentlink-freecad {version()}\n")
        return 0
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(__doc__.split("\n\n", 1)[1].strip("\n") + "\n")
        return 0
    from . import setup_check

    if "--check" in argv:
        return setup_check.main([a for a in argv if a != "--check"])
    script = _headless()
    # The relay is plain Python: it runs here.
    if "--connect" in argv:
        return subprocess.call([sys.executable, script] + argv)
    fcs = setup_check.freecad_candidates()
    if not fcs:
        sys.stderr.write("Agent Link: FreeCAD was not found. " + setup_check.GET_FREECAD[setup_check.OS]
                         + " Run `agentlink-freecad --check` for the rest.\n")
        return 2
    fc = fcs[0]
    env = dict(os.environ)
    # Files go to ~/AgentLink unless told otherwise (an MCP client's working
    # folder is often / or the app's own).
    if "--out" not in argv and not env.get("AGENTLINK_OUT"):
        env["AGENTLINK_OUT"] = os.path.join(os.path.expanduser("~"), "AgentLink")
        os.makedirs(env["AGENTLINK_OUT"], exist_ok=True)
    # FreeCAD's own bin first: gmsh, ccx and its Python live there.
    env["PATH"] = os.pathsep.join([fc["bin"], env.get("PATH", "")])
    if fc.get("python"):
        if fc.get("lib"):
            env["FREECAD_LIB"] = fc["lib"]
        return subprocess.call([fc["python"], script] + argv, env=env)
    # FreeCADCmd takes the arguments after a script for files: flags by env.
    if "--own" in argv:
        env["AGENTLINK_OWN"] = "1"
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 < len(argv):
            env["AGENTLINK_OUT"] = os.path.abspath(os.path.expanduser(argv[i + 1]))
    return subprocess.call([fc["cmd"], script], env=env)


if __name__ == "__main__":
    sys.exit(main())

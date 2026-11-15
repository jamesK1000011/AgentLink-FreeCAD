# SPDX-License-Identifier: LGPL-2.1-or-later
"""`agentlink-freecad`: the MCP server started from a package (uvx, pip)
rather than from the add-on's folder. The Python that runs this is uv's or
any other; it finds FreeCAD (agentlink/setup_check.py) and runs
agentlink_headless.py in FreeCAD's own Python, which serves.

    agentlink-freecad [--out DIR]       headless
    agentlink-freecad --connect [PORT]  relay to the FreeCAD window's Start link (needs no FreeCAD here)
    agentlink-freecad --check [--json]  what is missing and how to get it
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
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
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 < len(argv):
            env["AGENTLINK_OUT"] = os.path.abspath(os.path.expanduser(argv[i + 1]))
    return subprocess.call([fc["cmd"], script], env=env)


if __name__ == "__main__":
    sys.exit(main())

# SPDX-License-Identifier: LGPL-2.1-or-later
"""What Agent Link needs on this computer, what is here, and how to get what
is missing. Plain Python 3.8+, no FreeCAD needed, changes nothing:

    python3 agentlink_headless.py --check          # from this folder
    uvx --from git+https://github.com/jamesK1000011/AgentLink-FreeCAD agentlink-freecad --check
    ... --check --json                             # the same, for an agent

The exit code is 1 when something required is missing, 0 otherwise."""

import glob
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
OS = {"Darwin": "mac", "Windows": "windows"}.get(platform.system(), "linux")
MIN_FREECAD = (1, 1)
DOWNLOAD = "https://www.freecad.org/downloads.php"

GET_FREECAD = {
    "mac": f"Download FreeCAD 1.1 or later from {DOWNLOAD} and drag it into /Applications (or set FREECAD_APP to its path).",
    "linux": f"Install FreeCAD 1.1 or later: the AppImage from {DOWNLOAD}, your distribution's package, or conda-forge's `freecad`; or set FREECAD_LIB to its lib folder.",
    "windows": f"Run the FreeCAD 1.1 (or later) installer from {DOWNLOAD}, or set FREECAD_APP to the folder it went in.",
}
GET_UV = {
    "mac": "curl -LsSf https://astral.sh/uv/install.sh | sh   (or: brew install uv)",
    "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh",
    "windows": 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
}
GET_NODE = "Node 18 or later from https://nodejs.org (only if you do not use uv)."

# Programs some tool groups drive, each found on PATH, in FreeCAD's own bin
# folder, or where its installer puts it. None is needed to start.
OPTIONAL = [
    # (label, executables, mac app bundles, what it is for, where to get it)
    ("OrcaSlicer", ["orca-slicer", "OrcaSlicer"], ["OrcaSlicer.app"], "slicing to a printer-ready 3MF", "https://github.com/OrcaSlicer/OrcaSlicer/releases"),
    ("PrusaSlicer", ["prusa-slicer", "PrusaSlicer"], ["PrusaSlicer.app", "Original Prusa Drivers/PrusaSlicer.app"], "slicing with PrusaSlicer", "https://www.prusa3d.com/page/prusaslicer_424/"),
    ("KiCad", ["kicad-cli"], ["KiCad/KiCad.app", "KiCad.app"], "circuit boards and their enclosures", "https://www.kicad.org/download/"),
    ("Gmsh", ["gmsh"], [], "FEM meshes (most FreeCAD builds bring it)", "https://gmsh.info"),
    ("CalculiX", ["ccx"], [], "FEM strength checks (most FreeCAD builds bring it)", "https://www.calculix.de"),
]


def _mac_apps(pattern):
    out = []
    for root in ("/Applications", os.path.join(HOME, "Applications")):
        out += sorted(glob.glob(os.path.join(root, pattern)))
    return out


def _mac_version(app):
    try:
        with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
            return plistlib.load(f).get("CFBundleShortVersionString")
    except Exception:
        return None


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


def freecad_candidates():
    """Each FreeCAD found: {where, python, cmd, lib, bin}, the one named by
    FREECAD_APP or FREECAD_LIB first."""
    out = []

    def add(where, bindir, lib=None):
        names = {"python": ["python3", "python", "python.exe"], "cmd": ["freecadcmd", "FreeCADCmd", "FreeCADCmd.exe", "freecadcmd.exe"]}
        found = {k: next((os.path.join(bindir, n) for n in ns if os.path.isfile(os.path.join(bindir, n))), None) for k, ns in names.items()}
        if found["python"] or found["cmd"]:
            out.append({"where": where, "bin": bindir, "lib": lib or os.path.join(os.path.dirname(bindir), "lib"), **found})

    given = os.environ.get("FREECAD_APP")
    if given:
        given = os.path.expanduser(given)
        add(given, os.path.join(given, "Contents", "Resources", "bin") if given.endswith(".app") else os.path.join(given, "bin"))
    lib = os.environ.get("FREECAD_LIB")
    if lib:
        add(lib, os.path.join(os.path.dirname(os.path.expanduser(lib)), "bin"), os.path.expanduser(lib))
    import importlib.util

    if importlib.util.find_spec("FreeCAD"):  # a Python with FreeCAD on it (conda-forge's freecad)
        out.append({"where": sys.executable, "bin": os.path.dirname(sys.executable), "lib": "", "python": sys.executable, "cmd": None})
    if OS == "mac":
        apps = _mac_apps("FreeCAD*.app")
        apps.sort(key=lambda a: (_vtuple(_mac_version(a)), os.path.basename(a) == "FreeCAD.app"), reverse=True)
        for app in apps:
            add(app, os.path.join(app, "Contents", "Resources", "bin"), os.path.join(app, "Contents", "Resources", "lib"))
    elif OS == "windows":
        for root in filter(None, {os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA") and os.path.join(os.environ["LOCALAPPDATA"], "Programs")}):
            for d in sorted(glob.glob(os.path.join(root, "FreeCAD*")), reverse=True):
                add(d, os.path.join(d, "bin"))
    else:
        for n in ("freecadcmd", "FreeCADCmd"):
            p = shutil.which(n)
            if p:
                add(p, os.path.dirname(os.path.realpath(p)))
        for d in ("/usr/lib/freecad", "/usr/lib/freecad-python3", "/usr/local/lib/freecad"):
            add(d, os.path.join(d, "bin"), os.path.join(d, "lib"))
    seen, uniq = set(), []
    for c in out:
        if c["bin"] not in seen:
            seen.add(c["bin"])
            uniq.append(c)
    return uniq


ASK = "import FreeCAD,sys;sys.stdout.write('@@%s|%s@@' % ('.'.join(FreeCAD.Version()[:3]), FreeCAD.getUserAppDataDir()))"


def ask_freecad(fc, timeout=90):
    """(version, user folder) from FreeCAD itself, or (None, None)."""
    tries = []
    if fc.get("python"):
        tries.append([fc["python"], "-c", f"import sys;sys.path.append({fc['lib']!r});{ASK}"])
    if fc.get("cmd"):
        tries.append([fc["cmd"], "-c", ASK])
    for argv in tries:
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except Exception:
            continue
        m = re.search(r"@@(.*?)\|(.*?)@@", (r.stdout or "") + (r.stderr or ""))
        if m:
            return m.group(1), m.group(2)
    return None, None


def find_app(label, exes, bundles, fc_bin=None):
    for n in exes:
        if fc_bin and os.path.isfile(os.path.join(fc_bin, n)):
            return os.path.join(fc_bin, n)
        p = shutil.which(n)
        if p:
            return p
    if OS == "mac":
        for b in bundles:
            hits = _mac_apps(b)
            if hits:
                return hits[0]
    if OS == "windows":
        hits = glob.glob(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), label + "*"))
        if hits:
            return hits[0]
    return None


LOGS = {
    "mac": [os.path.join(HOME, "Library", "Logs", "FreeCAD Agent Link", "launcher.log"), os.path.join(HOME, "Library", "Logs", "Claude", "mcp-server-*.log")],
    "linux": [],
    "windows": [os.path.join(os.environ.get("APPDATA", HOME), "Claude", "logs", "mcp-server-*.log")],
}


def check(ask=True):
    """The report: a list of {item, state (ok | missing | optional | note), what, fix}."""
    rows = []

    def row(item, state, what, fix=None):
        rows.append({"item": item, "state": state, "what": what, **({"fix": fix} if fix else {})})

    row("Python", "ok", f"{platform.python_version()} at {sys.executable} (runs this check; the server runs in FreeCAD's own Python)")
    fcs = freecad_candidates()
    fc, version, user = (fcs[0] if fcs else None), None, None
    if not fc:
        row("FreeCAD", "missing", "not found", GET_FREECAD[OS])
    else:
        version, user = ask_freecad(fc) if ask else (None, None)
        if not version and OS == "mac" and fc["where"].endswith(".app"):
            version = _mac_version(fc["where"])
        if version and _vtuple(version)[:2] < MIN_FREECAD:
            row("FreeCAD", "missing", f"{version} at {fc['where']}: 1.1 or later is needed", GET_FREECAD[OS])
        else:
            row("FreeCAD", "ok", f"{version or 'version unknown'} at {fc['where']}")
    if fc and ask:
        if not user:
            row("FreeCAD user folder", "note", "FreeCAD did not say where its user folder is",
                "Open FreeCAD once and close it: that makes its user folder and Mod folder.")
        else:
            mod = os.path.join(user, "Mod")
            here = [d for d in sorted(glob.glob(os.path.join(mod, "*"))) if os.path.isfile(os.path.join(d, "agentlink_headless.py"))]
            if here:
                row("Agent Link add-on", "ok", f"in {here[0]}")
            elif not os.path.isdir(user):
                row("Agent Link add-on", "optional", f"{user} does not exist yet",
                    "Open FreeCAD once and close it, then install the add-on (README: Install).")
            else:
                row("Agent Link add-on", "optional", f"not in {mod} (needed only to watch the agent in the FreeCAD window)",
                    "Install it: the Claude Desktop extension (Mac), Addon Manager > custom repository, or by hand (README: Install).")
    uv, node = shutil.which("uv"), shutil.which("node")
    if uv:
        row("uv", "ok", uv)
    else:
        row("uv", "optional" if node else "missing", "not found (preferred: it brings its own Python and runs `uvx agentlink-freecad`)", GET_UV[OS])
    if node:
        row("Node", "ok", node)
    elif not uv:
        row("Node", "missing", "not found (the backup to uv)", GET_NODE)
    if OS == "mac":
        try:
            from agentlink import launcher_check
        except ImportError:
            launcher_check = None
        if launcher_check:
            r = launcher_check.report()
            if r.get("fetched"):
                row("Claude extension launcher", "ok" if not launcher_check.can_mend(r) else "missing", launcher_check.summary(r).splitlines()[0],
                    None if not launcher_check.can_mend(r) else "Run this check from FreeCAD (Agent Link > Setup check) and press Mend.")
            else:
                row("Claude extension launcher", "note", "not fetched (fine unless you use the Claude Desktop extension: open Claude Desktop once with it installed)")
    for label, exes, bundles, why, url in OPTIONAL:
        p = find_app(label, exes, bundles, fc and fc["bin"])
        row(label, "ok" if p else "optional", p or f"not found; only for {why}", None if p else url)
    for pat in LOGS[OS]:
        hits = glob.glob(pat)
        row("Log", "note", (hits[0] if len(hits) == 1 else pat) + ("" if hits else " (none yet)"))
    return rows


def text(rows):
    mark = {"ok": "ok      ", "missing": "MISSING ", "optional": "optional", "note": "note    "}
    lines = [f"Agent Link setup check ({ {'mac': 'macOS', 'linux': 'Linux', 'windows': 'Windows'}[OS] })"]
    for r in rows:
        lines.append(f"  {mark[r['state']]}  {r['item']}: {r['what']}")
        if r.get("fix"):
            lines.append(f"            get it: {r['fix']}")
    missing = [r["item"] for r in rows if r["state"] == "missing"]
    lines.append("Missing: " + ", ".join(missing) if missing else "Everything required is here.")
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    rows = check(ask="--no-ask" not in argv)
    sys.stdout.write((json.dumps({"os": OS, "items": rows}, indent=1) if "--json" in argv else text(rows)) + "\n")
    return 1 if any(r["state"] == "missing" for r in rows) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())

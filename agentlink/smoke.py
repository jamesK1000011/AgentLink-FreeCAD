# SPDX-License-Identifier: LGPL-2.1-or-later
# The smoke test an update must pass before the window moves onto it
# (unattended use, G): a FreeCAD and the add-ons as they would run together,
# started headless. Every tool family loads (or says which FreeCAD module it
# lacks), and a few core tools run on a fresh document: session_state, a
# primitive, body_check, an export read back. Run as a script with the new
# FreeCAD's Python (or FreeCADCmd) and the new add-ons on the path; the last
# line out is JSON: { ok, freecad, failures, families, extensions { loaded,
# leftOut [{ extension, error }] }, groups { group: count }, tools, ms }.
# An installed add-on that loaded before the update (AGENTLINK_LOADED_BEFORE,
# given by the launcher) and no longer loads is a failure.

import json
import os
import sys
import tempfile
import time


def _trial_first(sys, os):
    """The add-ons on trial (PYTHONPATH, as the launcher gives it) before
    the installed ones: FreeCAD's start-up puts its own Mod folders on the
    path and may import the installed agentlink first, and the trial then
    tested the add-ons in use, not the new ones (seen when a new module of
    the trial was "not in" the installed package)."""
    roots = [os.path.realpath(p) for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p and os.path.isdir(p)]
    if not roots:
        return
    for r in reversed(roots):
        sys.path[:] = [p for p in sys.path if os.path.realpath(p or ".") != r]
        sys.path.insert(0, r)
    tops = set()
    for r in roots:
        try:
            for n in os.listdir(r):
                if os.path.isfile(os.path.join(r, n, "__init__.py")):
                    tops.add(n)
                elif n.endswith(".py"):
                    tops.add(n[:-3])
        except OSError:
            pass
    for name, mod in list(sys.modules.items()):
        top = name.split(".", 1)[0]
        f = getattr(mod, "__file__", None)
        if top in tops and f and not any(os.path.realpath(f).startswith(r + os.sep) for r in roots):
            sys.modules.pop(name, None)


def run():
    # Imported here: FreeCAD's start-up, run from a script as __main__, can
    # take module names out of its globals (seen on 26.x).
    import json
    import os
    import sys
    import tempfile
    import time

    t0 = time.time()
    fails = []
    out = {"ok": False, "failures": fails}
    try:
        if os.environ.get("FREECAD_LIB") and os.environ["FREECAD_LIB"] not in sys.path:
            sys.path.append(os.environ["FREECAD_LIB"])
        import FreeCAD

        out["freecad"] = ".".join(FreeCAD.Version()[:3])
        _trial_first(sys, os)
    except Exception as e:
        fails.append(f"FreeCAD does not import: {e}")
        return out
    try:
        from agentlink import families
        from agentlink.tools import Session, build_server
    except Exception as e:
        fails.append(f"Agent Link does not import: {e}")
        return out
    loaded, left = [], {}
    for name in families.NAMES:
        try:
            __import__(f"agentlink.families.{name}")
            loaded.append(name)
        except ImportError as e:
            # A FreeCAD module this build lacks (FEM, TechDraw …) is fine.
            left[name] = str(e)
        except Exception as e:
            fails.append(f"family {name} fails to load: {type(e).__name__}: {e}")
    out["families"] = {"loaded": len(loaded), "leftOut": left}
    d = tempfile.mkdtemp(prefix="agentlink-smoke-")
    try:
        # A trial of add-ons not yet in use: the record of what runs
        # (~/AgentLink/extensions.json) is not replaced by it.
        from agentlink import extstate

        os.environ[extstate.NO_RECORD] = "1"
        s = Session(out_dir=d)
        srv = build_server(s, lean=False)
        # The installed add-ons' own families load too: one left out (its
        # module raised, its tools() raised) is named with its error, and
        # fails the test when it loaded before this update — its tools
        # would be gone without a word otherwise.
        ext = extstate.state()
        out["extensions"] = {"loaded": [r["extension"] for r in ext["loaded"]], "leftOut": ext["leftOut"]}
        out["groups"] = extstate.groups_of(srv.tools.values())
        fails.extend(extstate.smoke_failures(ext["leftOut"], extstate.before_list(os.environ.get(extstate.BEFORE))))

        def call(name, args):
            reply = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})
            if not isinstance(reply, dict) or "result" not in reply:
                # A protocol error: the raw fault, as the server gave it.
                fails.append(f"{name}: no result: {json.dumps(reply)[:400]}")
                return None
            r = reply["result"]
            body = json.loads(r["content"][0]["text"])
            if r.get("isError"):
                fails.append(f"{name}: {body.get('error', {}).get('message', body)}"[:300])
                return None
            return body

        call("session_state", {})
        if call("part_primitive", {"kind": "box", "size": [20, 10, 5], "name": "Smoke"}):
            b = call("body_check", {"body": "Smoke"})
            if b is not None and (b.get("valid") is False or b.get("solids") != 1):
                fails.append(f"body_check: the test box reads unsound ({b.get('valid')}, {b.get('solids')} solids)")
            e = call("export_file", {"body": "Smoke", "path": os.path.join(d, "smoke.step")})
            if e is not None and abs((e.get("verify") or {}).get("volume", 0) - 1000.0) > 1.0:
                fails.append(f"export_file: read back {e.get('verify')}")
        out["tools"] = len(srv.tools)
        try:
            FreeCAD.closeDocument(s.doc.Name)
        except Exception:
            pass
    except Exception as e:
        import traceback

        tb = traceback.format_exc().strip().splitlines()
        fails.append(f"the server did not start: {type(e).__name__}: {e} | " + " | ".join(x.strip() for x in tb[-6:])[:900])
    out["ok"] = not fails
    out["ms"] = int((time.time() - t0) * 1000)
    return out


def app_python(app):
    """A FreeCAD.app's own Python and library folder: (python, lib, cmd)."""
    b = os.path.join(app, "Contents", "Resources", "bin")
    lib = os.path.join(app, "Contents", "Resources", "lib")
    py = next((os.path.join(b, n) for n in ("python3", "python") if os.path.exists(os.path.join(b, n))), None)
    cmd = next((os.path.join(b, n) for n in ("freecadcmd", "FreeCADCmd") if os.path.exists(os.path.join(b, n))), None)
    return py, lib, cmd


def against(app=None, addon_dirs=(), python=None, lib=None, timeout=600):
    """Run this smoke test in another process: a FreeCAD.app (its own Python)
    or a Python with FreeCAD's lib, with addon_dirs (folders holding
    AgentLink and the add-ons to try with it) first on the path. The parsed result."""
    import subprocess

    cmd = None
    if app:
        python, lib, cmd = app_python(app)
    exe = python or cmd
    if not exe:
        return {"ok": False, "failures": [f"no Python or FreeCADCmd in {app}"]}
    here = os.path.dirname(os.path.abspath(__file__))
    # Each folder is the add-on itself (it holds the agentlink package, as a
    # checkout of AgentLink-FreeCAD does under any name) or holds it as
    # AgentLink (a Mod folder); its neighbours come from beside it.
    dirs = [d if os.path.isdir(os.path.join(d, "agentlink")) else os.path.join(d, "AgentLink") if os.path.isdir(os.path.join(d, "AgentLink")) else d for d in addon_dirs] or [os.path.dirname(here)]
    # Its neighbours: every other add-on in the same Mod folder (the library
    # it needs, and whatever plugs into it), none of them named here; then
    # the path this process was given.
    extra = []
    for d in dirs:
        parent = os.path.dirname(d)
        try:
            names = sorted(os.listdir(parent))
        except OSError:
            names = []
        for n in names:
            p = os.path.join(parent, n)
            if p not in dirs and p not in extra and (os.path.isfile(os.path.join(p, "package.xml")) or os.path.isfile(os.path.join(p, "Init.py"))):
                extra.append(p)
    inherited = [x for x in os.environ.get("PYTHONPATH", "").split(os.pathsep) if x and x not in dirs + extra]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(dirs + extra + inherited + ([lib] if lib else [])), **({"FREECAD_LIB": lib} if lib else {})}
    env.pop("AGENTLINK_SUPERVISED", None)
    # The add-ons that load in this FreeCAD: one of them no longer loading
    # with what is tried fails the test (run() above).
    try:
        from . import extstate

        if extstate.BEFORE not in env:
            env[extstate.BEFORE] = ",".join(r["extension"] for r in extstate.state()["loaded"])
    except Exception:  # noqa: BLE001 - run as a script, or an older layout
        pass
    script = os.path.join(dirs[0], "agentlink", "smoke.py")
    if not os.path.isfile(script):
        script = os.path.abspath(__file__)
    try:
        r = subprocess.run([exe, script], capture_output=True, timeout=timeout, env=env, text=True)
    except subprocess.TimeoutExpired:
        return {"ok": False, "failures": [f"the smoke test ran past {timeout} s"]}
    except OSError as e:
        return {"ok": False, "failures": [f"could not start {exe}: {e}"]}
    for line in reversed((r.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                break
    return {"ok": False, "failures": [f"no answer (exit {r.returncode}): " + ((r.stderr or "")[-400:] or "nothing on stderr")]}


if __name__ == "__main__":
    res = run()
    import json as _json
    import os as _os
    import sys as _sys

    _sys.stdout.write("\n" + _json.dumps(res) + "\n")
    _sys.stdout.flush()
    _os._exit(0 if res["ok"] else 1)

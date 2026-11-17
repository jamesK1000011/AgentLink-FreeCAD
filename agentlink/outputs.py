# SPDX-License-Identifier: LGPL-2.1-or-later
# The output folder (~/AgentLink, the session's out_dir) kept tidy: every
# file or folder a tool makes there is written down in outputs.jsonl (path,
# kind, tool, time, size), and only those are ever cleared. The person's own
# files, and anything moved in or renamed, stay where they are.
#
# A tool's path goes through paths.local (or paths.made where a tool builds
# it by hand), which notes it here if nothing was there yet; after the call
# the ones that now exist are recorded. Kinds and how long they stay
# (Mod/AgentLink/Outputs):
#   shot    pictures (gui_input shots, window and view snapshots, renders):
#           the last ShotKeep (50), and any from the last ShotDays (3)
#   run     solver and job folders (fea_, elmer_, buckle_, shell_, slicer and
#           CAM jobs): RunDays (14)
#   export  what the person asked for (STL, STEP, 3MF, G-code, drawings):
#           never cleared on its own, only listed
#   fcbak   FreeCAD's backups of a document saved here, beyond its own count
#           (Document CountBackupFiles): FCBakDays (7)
# Cleared at Agent Link's start and then at most once a day, quietly, when
# the heavy-job queue is free; outputs_clean shows (or does) it on asking.
# Never: a path a document links to, a file open in FreeCAD, anything under
# install, settings, crash, checkpoints or autosave. Cleared means the Trash
# where there is one.
#
# No FreeCAD needed for the rules: tests run them on a folder of their own.

import json
import os
import re
import shutil
import sys
import time

MANIFEST = "outputs.jsonl"
STAMP = ".outputs-clean.json"
PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink/Outputs"
KINDS = ("shot", "run", "export", "fcbak")
NEVER = {"install", "settings", "crash", "checkpoints", "autosave"}
DEFAULTS = {"ShotKeep": 50, "ShotDays": 3.0, "RunDays": 14.0, "FCBakDays": 7.0, "Auto": True}
DAY = 86400.0

SHOT_TOOLS = {"gui_input", "window_snapshot", "view_snapshot", "view_render", "view_maps", "cam_sim"}
RUN_PREFIXES = ("fea_", "elmer_", "buckle_", "shell_", "slice", "job_", "cam_", "orca_")
RUN_TOOL_PREFIXES = ("fea_", "elmer_", "buckle", "shell_", "slice", "orca_", "cam_")


# ---- settings -----------------------------------------------------------------------------

def settings():
    """The retention settings: Mod/AgentLink/Outputs over the defaults."""
    out = dict(DEFAULTS)
    try:
        import FreeCAD

        g = FreeCAD.ParamGet(PREFS)
        out["ShotKeep"] = g.GetInt("ShotKeep", DEFAULTS["ShotKeep"])
        for k in ("ShotDays", "RunDays", "FCBakDays"):
            out[k] = g.GetFloat(k, DEFAULTS[k])
        out["Auto"] = g.GetBool("Auto", True)
    except Exception:
        pass
    return out


def backup_count():
    """How many backups FreeCAD itself keeps of a document (Document
    CountBackupFiles, 1 by default)."""
    try:
        import FreeCAD

        return max(0, FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document").GetInt("CountBackupFiles", 1))
    except Exception:
        return 1


# ---- recording ----------------------------------------------------------------------------

def _real(p):
    return os.path.realpath(os.path.expanduser(p))


def _inside(p, root):
    return p != root and p.startswith(root.rstrip("/") + "/")


def _top(p, root):
    """The first part of p under root ('' when not under it)."""
    return os.path.relpath(p, root).split(os.sep)[0] if _inside(p, root) else ""


def manifest_path(out_dir):
    return os.path.join(out_dir, MANIFEST)


def read(out_dir):
    """The manifest: the newest record of each path, in order written."""
    rows = {}
    try:
        with open(manifest_path(out_dir), encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and isinstance(r.get("path"), str):
                    rows.pop(r["path"], None)
                    rows[r["path"]] = r
    except OSError:
        pass
    return rows


def _write_all(out_dir, rows):
    p = manifest_path(out_dir)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    os.replace(tmp, p)


def size_of(p):
    try:
        if os.path.isdir(p) and not os.path.islink(p):
            n = 0
            for d, _dirs, files in os.walk(p):
                for x in files:
                    try:
                        n += os.lstat(os.path.join(d, x)).st_size
                    except OSError:
                        pass
            return n
        return os.lstat(p).st_size
    except OSError:
        return 0


def kind_for(path, tool, isdir):
    """A record's kind when the tool did not say."""
    base = os.path.basename(path)
    if base.lower().endswith(".fcbak"):
        return "fcbak"
    if (tool or "") in SHOT_TOOLS:
        return "shot"
    if isdir and (base.lower().startswith(RUN_PREFIXES) or (tool or "").startswith(RUN_TOOL_PREFIXES)):
        return "run"
    return "export"


def record(out_dir, path, kind=None, tool=None, now=None, extra=None):
    """Write a record for a path that is there now; answers the record."""
    out_real = _real(out_dir)
    p = _real(path)
    if not _inside(p, out_real) or not os.path.lexists(p):
        return None
    try:
        st = os.lstat(p)
    except OSError:
        return None
    isdir = os.path.isdir(p)
    r = {"path": p, "kind": kind if kind in KINDS else kind_for(p, tool, isdir), "tool": tool or "", "time": round(now or time.time(), 3),
         "size": size_of(p), "dir": isdir, "ino": st.st_ino, **(extra or {})}
    if getattr(st, "st_birthtime", None):
        r["born"] = round(st.st_birthtime, 3)
    os.makedirs(out_real, exist_ok=True)
    with open(manifest_path(out_real), "a", encoding="utf-8") as f:
        f.write(json.dumps(r, sort_keys=True) + "\n")
    return r


def _state(session):
    st = getattr(session, "_outputs", None)
    if st is None:
        st = {"pending": {}, "tools": [], "known": None, "last_auto": None}
        try:
            session._outputs = st
        except Exception:
            return None
    return st


def _backups(p):
    """FreeCAD's backup files beside a document file (Name.FCBak, Name1.FCBak,
    Name.<time>.FCBak)."""
    d, stem = os.path.dirname(p), os.path.splitext(os.path.basename(p))[0]
    try:
        names = os.listdir(d)
    except OSError:
        return set()
    return {os.path.join(d, n) for n in names if n.lower().endswith(".fcbak") and n.startswith(stem)}


def expect(session, path, kind=None, tool=None):
    """A path a tool may write: noted when it is in the output folder and
    nothing is there yet (or what is there is one of ours), recorded after
    the call if it then exists. Answers path."""
    try:
        out_dir = getattr(session, "out_dir", None)
        st = _state(session) if out_dir else None
        if st is None or not isinstance(path, str):
            return path
        out_real = _real(out_dir)
        p = _real(path)
        if not _inside(p, out_real) or _top(p, out_real) in NEVER or p == manifest_path(out_real):
            return path
        if p not in st["pending"]:
            tool = tool or (st["tools"][-1] if st["tools"] else None)
            ours = os.path.lexists(p) and p in _known(st, out_real)
            if not os.path.lexists(p) or ours:
                st["pending"][p] = {"kind": kind, "tool": tool}
            if p.lower().endswith(".fcstd"):
                st["pending"].setdefault(("fcbak", p), {"before": _backups(p), "tool": tool})
        elif kind and not st["pending"][p].get("kind"):
            st["pending"][p]["kind"] = kind
    except Exception:
        pass
    return path


def _known(st, out_real):
    if st["known"] is None:
        st["known"] = set(read(out_real))
    return st["known"]


def flush(session):
    """Record the noted paths that exist now; forget the rest."""
    st = getattr(session, "_outputs", None)
    if not st or not st["pending"]:
        return []
    pending, st["pending"] = st["pending"], {}
    out_dir = getattr(session, "out_dir", None)
    if not out_dir:
        return []
    out_real = _real(out_dir)
    made = []
    for p, info in pending.items():
        try:
            if isinstance(p, tuple):  # backups FreeCAD wrote beside a saved document
                for b in sorted(_backups(p[1]) - info["before"]):
                    r = record(out_real, b, "fcbak", info.get("tool"), extra={"doc": _real(p[1])})
                    if r:
                        made.append(r)
                continue
            if os.path.lexists(p):
                r = record(out_real, p, info.get("kind"), info.get("tool"))
                if r:
                    made.append(r)
        except Exception:
            pass
    if st["known"] is not None:
        st["known"].update(r["path"] for r in made)
    return made


def track(session, tool, fn):
    """Run a call with its outputs noted and, at the outermost call,
    recorded; then the daily clear when it is due."""
    st = _state(session)
    if st is None:
        return fn()
    st["tools"].append(getattr(tool, "name", str(tool)))
    try:
        return fn()
    finally:
        st["tools"].pop()
        if not st["tools"]:
            import time as _time

            t_out = _time.time()
            try:
                flush(session)
            except Exception:
                pass
            try:
                maybe_auto(session)
            except Exception:
                pass
            try:
                from . import around

                around.add("outputs", _time.time() - t_out)
            except Exception:
                pass


# ---- what may go ----------------------------------------------------------------------------

def linked_paths(out_dir):
    """Paths under the output folder that an open document holds: its own
    file, file and path properties (a solver's working folder, an included
    file, an image)."""
    out = set()
    try:
        import FreeCAD
    except ImportError:
        return out
    root = _real(out_dir)
    keep_types = ("App::PropertyFile", "App::PropertyFileIncluded", "App::PropertyPath", "App::PropertyString", "App::PropertyStringList")

    def note(v):
        if isinstance(v, str) and v:
            r = _real(v)
            if _inside(r, root):
                out.add(r)
        elif isinstance(v, (list, tuple)):
            for x in v:
                note(x)

    try:
        docs = list(FreeCAD.listDocuments().values())
    except Exception:
        return out
    for d in docs:
        try:
            note(d.FileName)
        except Exception:
            pass
        for o in getattr(d, "Objects", []) or []:
            try:
                props = o.PropertiesList
            except Exception:
                continue
            for pr in props:
                try:
                    if o.getTypeIdOfProperty(pr) in keep_types:
                        note(getattr(o, pr))
                except Exception:
                    pass
    return out


def open_files(paths_):
    """Of these paths, those a process has open (lsof; a folder counts when a
    file inside it is open). Nothing found where lsof is missing."""
    if not paths_ or not shutil.which("lsof"):
        return set()
    import subprocess

    argv = ["lsof", "-n", "-Fn"]
    for p in paths_:
        argv += (["+D", p] if os.path.isdir(p) else [p])
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return set()
    names = {_real(ln[1:]) for ln in r.stdout.splitlines() if ln.startswith("n/")}
    hit = set()
    for p in paths_:
        if p in names or any(_inside(n, p) for n in names):
            hit.add(p)
    return hit


def _held_by(p, held):
    return p in held or any(_inside(h, p) for h in held)


def plan(out_dir, now=None, kinds=None, older_than_days=None, prefs=None, linked=(), open_=None):
    """What would go: {"go": [record], "keep": [record], "exports": [record],
    "skipped": {why: n}, "gone": [path]}. kinds: those considered (all but
    export by default); older_than_days: the age, in place of each kind's."""
    now = now or time.time()
    prefs = dict(DEFAULTS, **(prefs or {}))
    root = _real(out_dir)
    rows = read(root)
    chosen = set(kinds or ("shot", "run", "fcbak"))
    held = {_real(x) for x in linked}
    out = {"go": [], "keep": [], "exports": [], "skipped": {}, "gone": []}

    def skip(why):
        out["skipped"][why] = out["skipped"].get(why, 0) + 1

    live = []
    for p, r in rows.items():
        if not os.path.lexists(p):
            out["gone"].append(p)
            continue
        if not _inside(p, root) or _top(p, root) in NEVER or p == manifest_path(root):
            skip("protected")
            continue
        try:
            st = os.lstat(p)
        except OSError:
            out["gone"].append(p)
            continue
        # Something else under our name (the person's file moved in, or ours
        # replaced): not ours any more.
        born = getattr(st, "st_birthtime", None)
        if ((r.get("ino") is not None and st.st_ino != r["ino"]) or bool(r.get("dir")) != os.path.isdir(p)
                or (born and r.get("born") and abs(born - r["born"]) > 1.0)
                or (not r.get("dir") and st.st_size != r.get("size") and st.st_mtime > float(r.get("time") or 0) + 1.0)):
            skip("replaced")
            continue
        r = dict(r, age=(now - max(float(r.get("time") or 0), st.st_mtime)) / DAY, size=size_of(p))
        if r["kind"] == "export":
            out["exports"].append(r)
        live.append(r)
    # Shots: the newest ShotKeep stay whatever their age.
    shots = sorted((r for r in live if r["kind"] == "shot"), key=lambda r: r["age"])
    newest = {r["path"] for r in shots[: int(prefs["ShotKeep"])]} if older_than_days is None else set()
    # Backups: FreeCAD's own count of each document's newest stays.
    count = prefs.get("CountBackupFiles", 1)
    by_doc = {}
    for r in live:
        if r["kind"] == "fcbak":
            stem = r.get("doc") or os.path.join(os.path.dirname(r["path"]), re.sub(r"(\.\d{8,}.*|\d+)?\.fcbak$", "", os.path.basename(r["path"]).lower()))
            by_doc.setdefault(stem, []).append(r)
    own = set()
    for group in by_doc.values():
        own |= {r["path"] for r in sorted(group, key=lambda r: r["age"])[:count]}
    days = {"shot": prefs["ShotDays"], "run": prefs["RunDays"], "fcbak": prefs["FCBakDays"], "export": None}
    candidates = []
    for r in live:
        k = r["kind"]
        limit = older_than_days if older_than_days is not None else days.get(k)
        if k not in chosen or limit is None:
            out["keep"].append(r)
            continue
        # Exports go only on an explicit age (outputs_clean, kinds with export).
        if k == "export" and older_than_days is None:
            out["keep"].append(r)
            continue
        if r["age"] < float(limit) or r["path"] in newest or r["path"] in own:
            out["keep"].append(r)
            continue
        if _held_by(r["path"], held):
            skip("linked")
            out["keep"].append(r)
            continue
        candidates.append(r)
    busy = (open_ or open_files)([r["path"] for r in candidates]) if candidates else set()
    for r in candidates:
        if r["path"] in busy:
            skip("open")
            out["keep"].append(r)
        else:
            out["go"].append(r)
    return out


# ---- clearing -----------------------------------------------------------------------------

def trash(p):
    """To the Trash where there is one; answers how. send2trash when it is
    there; on a Mac, ~/.Trash; elsewhere removed."""
    try:
        from send2trash import send2trash

        send2trash(p)
        return "trash"
    except ImportError:
        pass
    if sys.platform == "darwin":
        bin_ = os.path.expanduser("~/.Trash")
        if os.path.isdir(bin_):
            name = os.path.basename(p)
            dest = os.path.join(bin_, name)
            if os.path.lexists(dest):
                stem, ext = os.path.splitext(name)
                dest = os.path.join(bin_, f"{stem} {time.strftime('%H-%M-%S')}{ext}")
                n = 2
                while os.path.lexists(dest):
                    dest = os.path.join(bin_, f"{stem} {time.strftime('%H-%M-%S')} {n}{ext}")
                    n += 1
            shutil.move(p, dest)
            return "trash"
    if os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p)
    else:
        os.unlink(p)
    return "removed"


def _sum(rows, names=3):
    return {"count": len(rows), "mb": round(sum(r.get("size") or 0 for r in rows) / 1048576.0, 2),
            "names": [os.path.basename(r["path"]) for r in rows[:names]]}


def clean(out_dir, dry_run=True, kinds=None, older_than_days=None, prefs=None, linked=(), open_=None, now=None, remove=None, limit=2000):
    """Clear what the rules say may go (dry_run: only say so). The answer:
    by kind, counts, MB and a few names; the exports listed."""
    pr = dict(DEFAULTS, **(prefs or {}))
    pr.setdefault("CountBackupFiles", backup_count())
    pl = plan(out_dir, now=now, kinds=kinds, older_than_days=older_than_days, prefs=pr, linked=linked, open_=open_)
    go = pl["go"][:limit]
    done, how, failed = [], set(), []
    if not dry_run:
        for r in go:
            try:
                how.add((remove or trash)(r["path"]))
                done.append(r)
            except OSError as e:
                failed.append(f"{os.path.basename(r['path'])}: {e.strerror or e}")
        # The manifest keeps what is still there.
        gone = {r["path"] for r in done} | set(pl["gone"])
        try:
            rows = [r for p, r in read(out_dir).items() if p not in gone]
            _write_all(_real(out_dir), rows)
        except OSError:
            pass
    sel = go if dry_run else done
    by = {}
    for k in KINDS:
        rows = [r for r in sel if r["kind"] == k]
        if rows:
            by[k] = _sum(rows)
    out = {"dryRun": bool(dry_run), ("wouldGo" if dry_run else "went"): by,
           "total": {"count": len(sel), "mb": round(sum(r.get("size") or 0 for r in sel) / 1048576.0, 2)},
           "kept": len(pl["keep"]), "exports": _sum(sorted(pl["exports"], key=lambda r: r["age"]))}
    if pl["skipped"]:
        out["skipped"] = pl["skipped"]
    if how:
        out["to"] = "the Trash" if how == {"trash"} else ("removed" if how == {"removed"} else "the Trash, or removed")
    if failed:
        out["failed"] = failed[:5]
    if len(pl["go"]) > limit:
        out["more"] = len(pl["go"]) - limit
    return out


# ---- when it runs on its own --------------------------------------------------------------

def _live():
    try:
        import FreeCAD

        gui = bool(getattr(FreeCAD, "GuiUp", False))
    except Exception:
        gui = False
    return gui or bool(os.environ.get("AGENTLINK_SUPERVISED")) or bool(os.environ.get("AGENTLINK_OUTPUTS_AUTO"))


def _last_run(out_dir):
    try:
        with open(os.path.join(out_dir, STAMP), encoding="utf-8") as f:
            return float(json.load(f).get("t") or 0)
    except (OSError, ValueError, TypeError, AttributeError):
        return 0.0


def queue_free():
    """The heavy-job queue lets a quiet job run: not held for the person,
    nothing heavy running, no heat throttling or memory pressure."""
    try:
        from . import keep

        q = keep.queue_state()
        if q.get("held") or q.get("running"):
            return False
        return not keep.mac_thermal() and keep.mac_pressure() not in ("warn", "critical")
    except Exception:
        return True


def auto(session, now=None):
    """The quiet clear, when it is on and due (a day since the last) and the
    queue is free; answers its result, or None when it did not run."""
    out_dir = getattr(session, "out_dir", None)
    if not out_dir or not os.path.isdir(out_dir):
        return None
    pr = settings()
    if not pr.get("Auto", True):
        return None
    now = now or time.time()
    st = _state(session)
    if st is not None:
        st["last_auto"] = now
    if now - _last_run(out_dir) < DAY or not queue_free():
        return None
    res = clean(out_dir, dry_run=False, prefs=pr, linked=linked_paths(out_dir), now=now)
    try:
        with open(os.path.join(out_dir, STAMP), "w", encoding="utf-8") as f:
            json.dump({"t": now, "went": res.get("went"), "total": res.get("total")}, f)
    except OSError:
        pass
    return res


def maybe_auto(session):
    """After a call: the quiet clear at most once a day (checked in memory
    first, so a call costs nothing)."""
    if not _live():
        return None
    st = _state(session)
    if st is not None and st["last_auto"] and time.time() - st["last_auto"] < 3600.0:
        return None
    return auto(session)


def at_start(session, delay_ms=30000):
    """At Agent Link's start: the quiet clear, after the window settles (in
    the window), or now (the hidden FreeCAD)."""
    if not _live():
        return
    try:
        import FreeCAD

        if getattr(FreeCAD, "GuiUp", False):
            from PySide import QtCore

            QtCore.QTimer.singleShot(delay_ms, lambda: _quiet(auto, session))
            return
    except Exception:
        pass
    _quiet(auto, session)


def _quiet(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None

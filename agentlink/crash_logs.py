# SPDX-License-Identifier: LGPL-2.1-or-later
# Crash evidence kept before it is cleaned away: FreeCAD's document-recovery
# folders (its transient folders holding fc_recovery_file*), its own crash
# log, and the system's crash reports for FreeCAD, copied into
# ~/AgentLink/crash/<time>/. Run before Document Recovery's Cleanup and by
# crash_collect, so a crash can be looked into after the window is clean.
import glob
import os
import shutil
import sys
import time

RECOVERY_MARK = "fc_recovery_file"
# Crash reports this old are left where they are (already seen).
REPORT_DAYS = 14


def _temp_dir():
    try:
        import FreeCAD

        return FreeCAD.getTempPath()
    except Exception:
        import tempfile

        return tempfile.gettempdir()


def _user_dir():
    try:
        import FreeCAD

        return FreeCAD.getUserAppDataDir()
    except Exception:
        return ""


def _cache_dir():
    try:
        import FreeCAD

        return FreeCAD.getUserCachePath()
    except Exception:
        return ""


def recovery_dirs(temp=None, skip_pid=None):
    """FreeCAD's transient document folders that hold a recovery file,
    except this process's own (its open documents are not crashed). FreeCAD
    1.x keeps them in its cache folder (~/Library/Caches/FreeCAD/… on a Mac),
    older releases in the temporary folder: both are looked in."""
    roots = [temp] if temp else [r for r in (_cache_dir(), _temp_dir()) if r]
    found = []
    for root in roots:
        found += glob.glob(os.path.join(root, "*_Doc_*")) + glob.glob(os.path.join(root, "*", "*_Doc_*"))
    out = []
    for d in sorted(set(found)):
        if not os.path.isdir(d):
            continue
        if skip_pid is not None and d.rstrip(os.sep).endswith("_" + str(skip_pid)):
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        if any(n.startswith(RECOVERY_MARK) for n in names):
            out.append(d)
    return out


def crash_reports(now=None, home=None):
    """The system's crash reports for FreeCAD from the last REPORT_DAYS
    (macOS DiagnosticReports), and FreeCAD's own crash.log."""
    now = now or time.time()
    home = home or os.path.expanduser("~")
    found = []
    if sys.platform == "darwin":
        for pat in ("FreeCAD*.ips", "FreeCAD*.crash", "freecad*.ips"):
            found += glob.glob(os.path.join(home, "Library", "Logs", "DiagnosticReports", pat))
    found = [f for f in found if now - os.path.getmtime(f) < REPORT_DAYS * 86400]
    ud = _user_dir()
    if ud and os.path.isfile(os.path.join(ud, "crash.log")):
        found.append(os.path.join(ud, "crash.log"))
    return sorted(set(found))


def collect(out_root=None, temp=None, home=None, skip_pid=None):
    """Copy the evidence into out_root/<time>/ (recovery/<folder>, reports/).
    Copies only: nothing is removed. Returns what was copied, or {} when
    there was nothing."""
    out_root = out_root or os.path.join(os.path.expanduser("~"), "AgentLink", "crash")
    skip_pid = os.getpid() if skip_pid is None else skip_pid
    dirs = recovery_dirs(temp, skip_pid)
    seen_file = os.path.join(out_root, "seen.txt")
    try:
        seen = set(open(seen_file, encoding="utf-8").read().splitlines())
    except OSError:
        seen = set()
    # A report is copied once, not again at every collect.
    reports = [f for f in crash_reports(home=home) if f"{f}|{int(os.path.getmtime(f))}" not in seen]
    if not dirs and not reports:
        return {}
    dest = os.path.join(out_root, time.strftime("%Y%m%d-%H%M%S"))
    copied = {"folder": dest, "recovery": [], "reports": []}
    for d in dirs:
        to = os.path.join(dest, "recovery", os.path.basename(d.rstrip(os.sep)))
        try:
            shutil.copytree(d, to)
            copied["recovery"].append(to)
        except OSError:
            pass
    for f in reports:
        os.makedirs(os.path.join(dest, "reports"), exist_ok=True)
        to = os.path.join(dest, "reports", os.path.basename(f))
        if os.path.exists(to):
            continue
        try:
            shutil.copy2(f, to)
            copied["reports"].append(to)
        except OSError:
            pass
    if reports:
        os.makedirs(out_root, exist_ok=True)
        with open(seen_file, "a", encoding="utf-8") as fh:
            for f in reports:
                fh.write(f"{f}|{int(os.path.getmtime(f))}\n")
    return copied

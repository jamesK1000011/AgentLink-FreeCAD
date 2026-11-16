# SPDX-License-Identifier: LGPL-2.1-or-later
"""addon_test's two halves, with no FreeCAD in them.

The tool's side (root_for, find_cmd, child_env, start, wait, listing):
which add-on may be tested, the FreeCAD command-line binary beside the
running FreeCAD, the environment, the job running in the background, the
compact answer and the full log, whose last line says how the run ended. Running an add-on's
tests is running its code: only Agent Link and the add-ons the launcher
installed are allowed.

The child's side (main): run in that separate FreeCAD process, never in
the window or the hidden FreeCAD, so documents and the GUI are untouched.
It runs the add-on's tests with pytest when FreeCAD's Python has it, and
otherwise with the small runner here: unittest TestCase classes, plain
test_* functions and Test* classes, and the pytest pieces add-on suites
use (skip, skipif, parametrize, raises, approx, importorskip, simple
fixtures, tmp_path, monkeypatch). A test needing more of pytest is
reported as skipped with the reason, never as a crash. Each result is one
JSON line in the file AGENTLINK_TEST_RESULT names.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from .protocol import ToolError, bad

OWN = "AgentLink"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}")
PATTERN = re.compile(r"[A-Za-z0-9_*?.\-\[\]]{1,80}\.py")
SELECT = re.compile(r"[A-Za-z0-9_]{1,120}")
# A subfolder of tests/: names joined by "/", none starting with "." (so no "..").
FOLDER = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,40}(/[A-Za-z0-9_][A-Za-z0-9_-]{0,40}){0,3}")
CMD_NAMES = ("freecadcmd", "FreeCADCmd", "freecadcmd.exe", "FreeCADCmd.exe")
CAP = 4000  # bytes of answer
TRACE_LINES = 15
TIMEOUT, TIMEOUT_MAX = 600.0, 1800.0


# ---- the tool's side -----------------------------------------------------------------------

def root_for(addon, mod, own_root, installed):
    """The folder of the add-on to test: Agent Link itself, or one the
    launcher installed in mod (installed: its folder names, or None)."""
    if not isinstance(addon, str) or not addon:
        raise bad("addon: an add-on's folder name in FreeCAD's Mod folder, or AgentLink.")
    if any(c in addon for c in ("/", "\\", os.sep)) or (os.altsep and os.altsep in addon) or ".." in addon:
        raise bad("addon: a folder name in the Mod folder, not a path.")
    if addon == OWN:
        return own_root
    allowed = sorted(set(installed or ()) - {OWN, "AddonManager"})
    if not NAME.fullmatch(addon) or addon not in allowed:
        raise bad(f"{addon}: not an add-on the launcher installed. A test suite is code, so only those run here: "
                  + ", ".join([OWN] + allowed) + ".")
    root = os.path.join(mod, addon)
    if not os.path.isdir(root):
        raise ToolError("not_found", f"{addon} is on the launcher's list but not in {mod}.")
    return root


def _cmd_in(d):
    return next((os.path.join(d, n) for n in CMD_NAMES if os.path.isfile(os.path.join(d, n))), None)


def _lib(bindir):
    lib = os.path.join(os.path.dirname(bindir), "lib")
    return lib if os.path.isdir(lib) else None


def find_cmd(exe=None, env=None, home=None, which=shutil.which, apps=("/Applications/FreeCAD.app",)):
    """FreeCAD's command-line binary beside the running FreeCAD, and its lib
    folder: (cmd, lib), or (None, None). The running bundle's first (macOS:
    <FreeCAD.app>/Contents/Resources/bin), then FREECAD_APP, FreeCAD's home,
    the folder of this Python, the PATH and /Applications/FreeCAD.app."""
    exe = exe or sys.executable or ""
    env = os.environ if env is None else env
    dirs = []
    if ".app/" in exe:
        dirs.append(os.path.join(exe.split(".app/")[0] + ".app", "Contents", "Resources", "bin"))
    if env.get("FREECAD_APP"):
        a = os.path.expanduser(env["FREECAD_APP"]).rstrip("/")
        dirs.append(os.path.join(a, "Contents", "Resources", "bin") if a.endswith(".app") else os.path.join(a, "bin"))
    if home:
        dirs.append(os.path.join(home, "bin"))
    if exe:
        dirs.append(os.path.dirname(exe))
    for d in dirs:
        c = _cmd_in(d)
        if c:
            return c, _lib(d)
    for n in CMD_NAMES[:2]:
        p = which(n)
        if p:
            return p, _lib(os.path.dirname(os.path.realpath(p)))
    for app in apps:
        d = os.path.join(app, "Contents", "Resources", "bin")
        c = _cmd_in(d)
        if c:
            return c, _lib(d)
    return None, None


def child_env(own_root, roots, lib, tmp, base=None):
    """The test process's environment: every add-on root and Agent Link's on
    PYTHONPATH, a fresh AGENTLINK_HOME and FreeCAD user folder, so nothing
    is written into the person's ~/AgentLink or FreeCAD settings."""
    env = dict(os.environ if base is None else base)
    for k in ("AGENTLINK_SUPERVISED", "AGENTLINK_GATE"):
        env.pop(k, None)
    paths = [own_root] + [r for r in roots if r != own_root]
    inherited = [x for x in env.get("PYTHONPATH", "").split(os.pathsep) if x and x not in paths]
    env.update(PYTHONPATH=os.pathsep.join(paths + inherited + ([lib] if lib else [])),
               AGENTLINK_HOME=os.path.join(tmp, "home"), AGENTLINK_OUT=os.path.join(tmp, "out"),
               AGENTLINK_SRC=own_root, AGENTLINK_USAGE="off", FREECAD_USER_HOME=os.path.join(tmp, "freecad"),
               PYTHONDONTWRITEBYTECODE="1")
    if lib:
        env["FREECAD_LIB"] = lib
    for d in ("home", "out", "freecad"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    return env


def _tail(text, n=TRACE_LINES, chars=1500):
    t = "\n".join((text or "").rstrip().splitlines()[-n:])
    return t if len(t) <= chars else "…" + t[-chars:]


def summarize(rows, addon, runner, seconds, log, timed_out=None):
    """The compact answer: counts, time, each failure's last traceback
    lines, within CAP bytes."""
    n = {k: sum(1 for r in rows if r.get("outcome") == k) for k in ("passed", "failed", "error", "skipped")}
    out = {"addon": addon, "runner": runner, "passed": n["passed"], "failed": n["failed"], "errors": n["error"],
           "skipped": n["skipped"], "seconds": round(seconds, 1), "log": log}
    if timed_out:
        out["timedOut"] = f"stopped after {timed_out:g} s: the counts are those finished by then"
    bad_rows = [r for r in rows if r.get("outcome") in ("failed", "error")]
    out["failures"] = []
    for i, r in enumerate(bad_rows):
        e = {"id": r.get("id"), "outcome": r["outcome"], "trace": _tail(r.get("trace"))}
        if len(json.dumps(out)) + len(json.dumps(e)) > CAP:
            out["more"] = f"{len(bad_rows) - i} more failures in the log"
            break
        out["failures"].append(e)
    why = {}
    for r in rows:
        if r.get("outcome") == "skipped":
            k = str(r.get("reason") or "")[:120]
            why[k] = why.get(k, 0) + 1
    if why:
        top = dict(sorted(why.items(), key=lambda kv: -kv[1])[:5])
        if len(json.dumps(out)) + len(json.dumps(top)) < CAP:
            out["skippedWhy"] = top
    return out


# Jobs: the run goes on in its own process after the call that started it
# returns (a remote client drops a call after about 80 s); addon_test
# { job } reads how far it is. Kept in this FreeCAD only: a job's process
# is killed when FreeCAD quits.
JOBS = {}
_LOCK = threading.Lock()
START_WAIT, STATUS_WAIT = 20.0, 30.0
KEEP_JOBS = 20


class Job:
    def __init__(self, job, addon, cmd, root, log, pattern, select, timeout):
        self.job, self.addon, self.cmd, self.root, self.log = job, addon, cmd, root, log
        self.pattern, self.select, self.timeout = pattern, select, timeout
        self.tmp = tempfile.mkdtemp(prefix="agentlink-test-")
        self.result = os.path.join(self.tmp, "results.jsonl")
        self.t0 = time.time()
        self.ended = threading.Event()
        self.how = None  # done | timed out | killed (…)
        self.seconds = None
        self.rows, self.runner = [], None
        self.p = None
        self._lock = threading.Lock()

    def read(self):
        """The rows written so far, and the runner."""
        rows, runner, end = [], None, False
        try:
            with open(self.result, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if "outcome" in r:
                        rows.append(r)
                    elif "runner" in r:
                        runner = r["runner"]
                    elif r.get("end"):
                        end = True
        except OSError:
            pass
        return rows, runner, end

    def _watch(self):
        try:
            self.p.wait(self.timeout)
        except subprocess.TimeoutExpired:
            self.finish(f"timed out after {self.timeout:g} s")
            return
        self.finish(None)

    def finish(self, how):
        """Stop the process group if it runs, write how it ended as the log's
        last line, and keep the rows; once only."""
        with self._lock:
            if self.ended.is_set():
                return
            if how is not None:
                _stop(self.p)
            rows, runner, end = self.read()
            code = self.p.poll()
            self.how = how or ("done" if end else f"killed (exit {code} before the tests finished)")
            self.rows, self.runner, self.seconds = rows, runner, time.time() - self.t0
            try:
                with open(self.log, "a", encoding="utf-8", errors="replace") as lf:
                    lf.write(f"\n== exit {code}, {self.seconds:.1f} s ==\n")
                    for r in rows:
                        if r["outcome"] in ("failed", "error"):
                            lf.write(f"\n== {r['outcome']}: {r.get('id')}\n{r.get('trace', '')}\n")
                    n = summarize(rows, self.addon, runner, self.seconds, self.log)
                    lf.write(f"\naddon_test: {self.how} — {n['passed']} passed, {n['failed']} failed, {n['errors']} errors, {n['skipped']} skipped\n")
            except OSError:
                pass
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.ended.set()

    def state(self):
        return "running" if not self.ended.is_set() else ("done" if self.how == "done" else self.how)

    def answer(self):
        if not self.ended.is_set():
            rows, runner, _ = self.read()
            n = {k: sum(1 for r in rows if r.get("outcome") == k) for k in ("passed", "failed", "error", "skipped")}
            return {"job": self.job, "addon": self.addon, "state": "running", "seconds": round(time.time() - self.t0, 1),
                    "passed": n["passed"], "failed": n["failed"], "errors": n["error"], "skipped": n["skipped"], "log": self.log,
                    "note": f"Still running (stopped at {self.timeout:g} s): addon_test {{ job: \"{self.job}\" }} again for the result."}
        if not self.rows and self.runner is None:
            with open(self.log, encoding="utf-8", errors="replace") as lf:
                tail = _tail(lf.read(), chars=1200)
            raise ToolError("failed", f"The tests of {self.addon} did not start ({self.how}): {tail}\nFull log: {self.log}")
        out = {"job": self.job, "state": self.state(), **summarize(self.rows, self.addon, self.runner, self.seconds, self.log,
                                                                   self.timeout if self.how.startswith("timed out") else None)}
        if not self.rows:
            out["note"] = f"No tests matched (pattern {self.pattern}" + (f", select {self.select}" if self.select else "") + ")."
        return out


def tests_dir(addon, root, folder=None):
    """root's tests/ folder, or the subfolder of it folder names (a
    relative path such as "make" or "make/slice": no "..", no absolute path,
    and still inside tests/ once links are followed)."""
    tests = os.path.join(root, "tests")
    if not os.path.isdir(tests):
        raise ToolError("not_found", f"{addon} has no tests/ folder at {root}.")
    if folder is None:
        return tests
    if not isinstance(folder, str) or not FOLDER.fullmatch(folder):
        raise bad('folder: a subfolder of tests/, such as "make" (names joined by /; no "..", no absolute path).')
    sub = os.path.join(tests, *folder.split("/"))
    real, top = os.path.realpath(sub), os.path.realpath(tests)
    if os.path.commonpath([real, top]) != top:
        raise bad("folder: must stay inside the add-on's tests/ folder.")
    if not os.path.isdir(sub):
        have = sorted(n for n in os.listdir(tests) if os.path.isdir(os.path.join(tests, n)) and not n.startswith((".", "__")))
        raise ToolError("not_found", f"{addon} has no tests/{folder} folder" + (f"; its subfolders: {', '.join(have)}." if have else "."))
    return sub


def start(cmd, addon, root, own_root, roots, lib, log, pattern="test_*.py", select=None, timeout=TIMEOUT, folder=None):
    """Start root's tests (tests/, or its subfolder folder) in a separate
    process (cmd: freecadcmd, or any Python for the tests here) in its own
    process group, and a thread that stops it at timeout and writes how it
    ended. The Job; one at a time per add-on."""
    tests = tests_dir(addon, root, folder)
    with _LOCK:
        busy = next((j for j in JOBS.values() if j.addon == addon and not j.ended.is_set()), None)
        if busy:
            return busy
        jid = os.path.splitext(os.path.basename(log))[0]
        while jid in JOBS:
            jid += "x"
        j = Job(jid, addon, cmd, root, log, pattern, select, timeout)
        env = child_env(own_root, roots, lib, j.tmp)
        env.update(AGENTLINK_TEST_ROOT=root, AGENTLINK_TEST_DIR=tests, AGENTLINK_TEST_PATTERN=pattern,
                   AGENTLINK_TEST_SELECT=select or "", AGENTLINK_TEST_RESULT=j.result)
        boot = os.path.join(j.tmp, "agentlink_test_boot.py")
        with open(boot, "w", encoding="utf-8") as f:
            f.write(f"import sys\nsys.path.insert(0, {own_root!r})\nfrom agentlink import testrun\ntestrun.main()\n")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w", encoding="utf-8", errors="replace") as lf:
            lf.write(f"addon_test {addon} (job {jid}): {root}\ncommand: {cmd} {boot}\nfolder: tests/{folder or ''}  pattern: {pattern}  select: {select or '-'}  timeout: {timeout:g} s\n"
                     f"PYTHONPATH: {env['PYTHONPATH']}\n\n")
            lf.flush()
            j.p = subprocess.Popen([cmd, boot], stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, cwd=j.tmp,
                                   start_new_session=(os.name != "nt"))
        JOBS[jid] = j
        for old in [k for k, v in JOBS.items() if v.ended.is_set()][:-KEEP_JOBS]:
            JOBS.pop(old, None)
        _quit_hook()
    threading.Thread(target=j._watch, name=f"addon_test {jid}", daemon=True).start()
    return j


def wait(j, seconds, pump=None):
    """Wait up to seconds for the job to end (the window painting meanwhile
    through pump), then its answer."""
    end = time.time() + seconds
    while not j.ended.is_set() and time.time() < end:
        if pump:
            pump()
        else:
            j.ended.wait(min(0.2, max(0.0, end - time.time())))
    return j.answer()


def find(job):
    j = JOBS.get(job) if isinstance(job, str) else None
    if j is None:
        raise ToolError("not_found", f"{job}: no such test job in this FreeCAD — " + (", ".join(JOBS) or "none have run since it started") + ".")
    return j


def listing():
    rows = []
    for j in reversed(list(JOBS.values())):
        r = {"job": j.job, "addon": j.addon, "state": j.state(), "seconds": round((j.seconds if j.seconds is not None else time.time() - j.t0), 1)}
        if j.ended.is_set():
            r.update({k: sum(1 for x in j.rows if x.get("outcome") == o) for k, o in (("passed", "passed"), ("failed", "failed"), ("errors", "error"))})
        rows.append(r)
    return {"jobs": rows, "note": "addon_test { addon } starts one; addon_test { job } answers how it stands." if rows else "No test jobs since this FreeCAD started: addon_test { addon } starts one."}


_HOOKED = []


def _quit_hook():
    if not _HOOKED:
        import atexit

        atexit.register(stop_all)
        _HOOKED.append(True)


def stop_all(why="killed (FreeCAD quit)"):
    """Every running job's process group stopped (FreeCAD quitting)."""
    for j in list(JOBS.values()):
        if not j.ended.is_set():
            j.finish(why)


def _stop(p):
    import signal

    if p is None or p.poll() is not None:
        return
    try:
        if os.name != "nt":
            os.killpg(p.pid, signal.SIGKILL)
        else:
            p.kill()
    except OSError:
        pass
    try:
        p.wait(10)
    except Exception:  # noqa: BLE001
        pass


# ---- the child's side: run in the test process ---------------------------------------------

class Unsupported(Exception):
    """A pytest feature the small runner lacks: the test is skipped with it."""


def real_python(exe, version=None):
    """The Python interpreter shipped beside exe (FreeCAD's bin folder), when
    exe is not itself one; else None."""
    import os
    import sys

    name = os.path.basename(exe or "").lower()
    if not exe or name.startswith("python"):
        return None
    v = version or sys.version_info
    d = os.path.dirname(exe)
    for cand in (f"python{v[0]}.{v[1]}", f"python{v[0]}", "python"):
        p = os.path.join(d, cand)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def main():
    # Imported here: FreeCAD's start-up can take module names out of a
    # script's globals.
    import json
    import os
    import sys
    import time

    out = os.environ["AGENTLINK_TEST_RESULT"]
    root, tests = os.environ["AGENTLINK_TEST_ROOT"], os.environ["AGENTLINK_TEST_DIR"]
    pattern = os.environ.get("AGENTLINK_TEST_PATTERN") or "test_*.py"
    select = os.environ.get("AGENTLINK_TEST_SELECT") or None
    for p in reversed([x for x in os.environ.get("PYTHONPATH", "").split(os.pathsep) if x]):
        if p not in sys.path:
            sys.path.insert(0, p)
    # Tests that start a fresh interpreter run sys.executable: in freecadcmd
    # that is freecadcmd itself, which takes neither -I nor Python's -c.
    py = real_python(sys.executable)
    if py:
        sys.executable = py

    def emit(row):
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    _orphan_guard()
    t0 = time.time()
    runner = "agentlink"
    if os.environ.get("AGENTLINK_TEST_RUNNER") != "agentlink":  # set: the small runner even with pytest there
        try:
            import pytest  # noqa: F401

            runner = "pytest"
        except ImportError:
            pass
    emit({"runner": runner})
    try:
        if runner == "pytest":
            _with_pytest(root, tests, pattern, select, emit)
        else:
            Mini(root, tests, pattern, select, emit).run()
    except BaseException as e:  # noqa: BLE001
        import traceback

        emit({"id": "(runner)", "outcome": "error", "trace": "".join(traceback.format_exception(type(e), e, e.__traceback__))})
    emit({"end": True})
    sys.stdout.write(f"\naddon_test: the tests finished in {time.time() - t0:.1f} s\n")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def _orphan_guard():
    """FreeCAD gone (this process handed to another parent): say so in the
    log and stop this process group, tests' own children with it."""
    import os
    import threading
    import time

    if os.name == "nt":
        return
    parent = os.getppid()

    def watch():
        while True:
            time.sleep(2)
            if os.getppid() != parent:
                import signal
                import sys

                sys.stdout.write("\naddon_test: killed (FreeCAD quit)\n")
                sys.stdout.flush()
                os.killpg(os.getpgrp(), signal.SIGKILL)

    threading.Thread(target=watch, daemon=True).start()


def _with_pytest(root, tests, pattern, select, emit):
    """pytest, each result written as it comes."""
    import pytest

    class Rows:
        def pytest_collectreport(self, report):
            if report.failed:
                emit({"id": report.nodeid or "(collection)", "outcome": "error", "trace": str(report.longrepr)})

        def pytest_runtest_logreport(self, report):
            if hasattr(report, "wasxfail"):
                if report.when == "call" or report.skipped:
                    emit({"id": report.nodeid, "outcome": "skipped" if report.skipped else "passed", "reason": "xfail"})
            elif report.failed:
                emit({"id": report.nodeid, "outcome": "failed" if report.when == "call" else "error", "trace": str(report.longrepr)})
            elif report.skipped:
                lr = report.longrepr
                emit({"id": report.nodeid, "outcome": "skipped", "reason": str(lr[2] if isinstance(lr, tuple) and len(lr) == 3 else lr)})
            elif report.when == "call":
                emit({"id": report.nodeid, "outcome": "passed"})

    args = [tests, "-q", "-p", "no:cacheprovider", "--rootdir", root, "--continue-on-collection-errors", "-o", f"python_files={pattern}"]
    if select:
        args += ["-k", select]
    pytest.main(args, plugins=[Rows()])


class Mini:
    """The runner used when FreeCAD's Python has no pytest."""

    def __init__(self, root, tests, pattern, select, emit):
        self.root, self.tests, self.pattern, self.select, self.emit = root, tests, pattern, select, emit
        self.fixtures = {}

    def run(self):
        import fnmatch

        sys.modules.setdefault("pytest", _shim())
        files = []
        for d, dirs, names in os.walk(self.tests):
            dirs[:] = sorted(x for x in dirs if not x.startswith((".", "__pycache__")))
            if "conftest.py" in names:
                self._conftest(os.path.join(d, "conftest.py"))
            files += [os.path.join(d, n) for n in sorted(names) if fnmatch.fnmatch(n, self.pattern)]
        for path in files:
            self._file(path)

    # -- collection

    def _rel(self, path):
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def _import(self, path):
        import importlib
        import importlib.util

        d = os.path.dirname(path)
        stem = os.path.splitext(os.path.basename(path))[0]
        if os.path.isfile(os.path.join(d, "__init__.py")):
            parts, top = [stem], d
            while os.path.isfile(os.path.join(top, "__init__.py")):
                parts.insert(0, os.path.basename(top))
                top = os.path.dirname(top)
            if top not in sys.path:
                sys.path.insert(0, top)
            return importlib.import_module(".".join(parts))
        if d not in sys.path:
            sys.path.insert(0, d)
        spec = importlib.util.spec_from_file_location(stem, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[stem] = mod
        spec.loader.exec_module(mod)
        return mod

    def _fixtures_of(self, mod):
        return {f._al_fixture.get("name") or n: f for n, f in vars(mod).items() if _is_fixture(f)}

    def _conftest(self, path):
        try:
            self.fixtures.update(self._fixtures_of(self._import(path)))
        except BaseException as e:  # noqa: BLE001
            self._record(self._rel(path), e, "error")

    def _file(self, path):
        import inspect
        import unittest

        rel = self._rel(path)
        try:
            mod = self._import(path)
        except BaseException as e:  # noqa: BLE001
            if self.select is None or self.select in rel:
                self._record(rel, e, "error")
            return
        fixtures = {**self.fixtures, **self._fixtures_of(mod)}
        module_marks = _marks_of(mod)
        for name, obj in list(vars(mod).items()):
            if getattr(obj, "__module__", None) != mod.__name__:
                continue
            if inspect.isclass(obj) and issubclass(obj, unittest.TestCase):
                self._unittest(rel, obj, module_marks)
            elif inspect.isclass(obj) and name.startswith("Test") and "__init__" not in vars(obj):
                for m in sorted(n for n in dir(obj) if n.startswith("test") and callable(getattr(obj, n))):
                    self._case(f"{rel}::{name}::{m}", obj, m, fixtures, module_marks + _marks_of(obj))
            elif inspect.isfunction(obj) and name.startswith("test") and not _is_fixture(obj):
                self._case(f"{rel}::{name}", None, name, fixtures, module_marks, fn=obj)

    # -- unittest classes

    def _unittest(self, rel, cls, marks):
        import unittest

        names = [n for n in unittest.TestLoader().getTestCaseNames(cls) if not self.select or self.select in f"{rel}::{cls.__name__}::{n}"]
        if not names:
            return
        why = _skip_reason(marks + _marks_of(cls))
        if why is not None:
            for n in names:
                self.emit({"id": f"{rel}::{cls.__name__}::{n}", "outcome": "skipped", "reason": why})
            return
        unittest.TestSuite([cls(n) for n in names]).run(_Result(self, rel))

    # -- pytest-style functions and classes

    def _case(self, tid, cls, name, fixtures, marks, fn=None):
        import itertools

        if self.select and self.select not in tid:
            return
        target = fn or getattr(cls, name)
        marks = marks + _marks_of(target)
        why = _skip_reason(marks)
        if why is not None:
            self.emit({"id": tid, "outcome": "skipped", "reason": why})
            return
        grids = []
        for m in marks:
            if m.name == "parametrize":
                names, values = m.args[0], m.args[1]
                names = [x.strip() for x in names.split(",")] if isinstance(names, str) else list(names)
                grids.append([dict(zip(names, v if len(names) > 1 else (v,))) for v in values])
        combos = [dict(kv for d in c for kv in d.items()) for c in itertools.product(*grids)] if grids else [{}]
        uses = [f for m in marks if m.name == "usefixtures" for f in m.args]
        xfail = any(m.name == "xfail" for m in marks)
        for i, params in enumerate(combos):
            self._one(f"{tid}[{i}]" if grids else tid, cls, name, fixtures, params, fn, uses, xfail)

    def _one(self, tid, cls, name, fixtures, params, fn, uses=(), xfail=False):
        import inspect

        stack, cache = [], {}
        stage = "setup"
        try:
            inst = cls() if cls is not None else None
            call = fn if inst is None else getattr(inst, name)
            for f in fixtures.values():
                if f._al_fixture.get("autouse"):
                    self._fixture(f, fixtures, cache, stack)
            for u in uses:
                self._value(u, fixtures, cache, stack)
            if inst is not None and hasattr(inst, "setup_method"):
                inst.setup_method(call)
                if hasattr(inst, "teardown_method"):
                    stack.append(lambda: inst.teardown_method(call))
            kwargs = {}
            for p in inspect.signature(call).parameters.values():
                if p.name in params:
                    kwargs[p.name] = params[p.name]
                elif p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY):
                    kwargs[p.name] = self._value(p.name, fixtures, cache, stack)
            stage = "call"
            call(**kwargs)
            outcome = None
        except BaseException as e:  # noqa: BLE001
            outcome = e
        for undo in reversed(stack):
            try:
                undo()
            except BaseException as e:  # noqa: BLE001
                outcome = outcome or e
        if outcome is None:
            self.emit({"id": tid, "outcome": "passed"})
        elif xfail and stage == "call" and not isinstance(outcome, (Skipped, Unsupported, _unittest.SkipTest)):
            self.emit({"id": tid, "outcome": "skipped", "reason": "xfail: failed as expected"})
        else:
            self._record(tid, outcome, "failed" if stage == "call" else "error")

    def _value(self, name, fixtures, cache, stack):
        import pathlib
        import tempfile

        if name in cache:
            return cache[name]
        if name in fixtures:
            v = self._fixture(fixtures[name], fixtures, cache, stack)
        elif name == "tmp_path":
            v = pathlib.Path(tempfile.mkdtemp(prefix="pytest-"))
        elif name == "monkeypatch":
            v = MonkeyPatch()
            stack.append(v.undo)
        else:
            raise Unsupported(f"fixture {name}")
        cache[name] = v
        return v

    def _fixture(self, f, fixtures, cache, stack):
        import inspect

        spec = f._al_fixture
        key = spec.get("name") or f.__name__
        if key in cache:
            return cache[key]
        if spec.get("params"):
            raise Unsupported("fixture params")
        kwargs = {p: self._value(p, fixtures, cache, stack) for p, d in inspect.signature(f).parameters.items() if d.default is inspect.Parameter.empty}
        if inspect.isgeneratorfunction(f):
            g = f(**kwargs)
            v = next(g)
            stack.append(lambda: next(g, None))
        else:
            v = f(**kwargs)
        cache[key] = v
        return v

    def _record(self, tid, e, outcome):
        import traceback
        import unittest

        if isinstance(e, (Skipped, unittest.SkipTest)):
            self.emit({"id": tid, "outcome": "skipped", "reason": str(e)})
        elif isinstance(e, Unsupported):
            self.emit({"id": tid, "outcome": "skipped", "reason": f"needs {e}, which this runner lacks (no pytest in FreeCAD's Python)"})
        else:
            self.emit({"id": tid, "outcome": outcome, "trace": "".join(traceback.format_exception(type(e), e, e.__traceback__))})


import unittest as _unittest  # noqa: E402


def _is_fixture(f):
    return callable(f) and "_al_fixture" in getattr(f, "__dict__", {})


class _Result(_unittest.TestResult):
    def __init__(self, mini, rel):
        super().__init__()
        self.mini, self.rel = mini, rel

    def _id(self, test):
        m = getattr(test, "_testMethodName", None)
        return f"{self.rel}::{type(test).__name__}::{m}" if m else f"{self.rel}::{test}"

    def addSuccess(self, test):
        self.mini.emit({"id": self._id(test), "outcome": "passed"})

    def addFailure(self, test, err):
        self.mini.emit({"id": self._id(test), "outcome": "failed", "trace": self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        if isinstance(err[1], Unsupported):
            return self.addSkip(test, f"needs {err[1]}, which this runner lacks (no pytest in FreeCAD's Python)")
        self.mini.emit({"id": self._id(test), "outcome": "error", "trace": self._exc_info_to_string(err, test)})

    def addSkip(self, test, reason):
        self.mini.emit({"id": self._id(test), "outcome": "skipped", "reason": reason})

    def addSubTest(self, test, subtest, err):
        if err is not None:
            ok = issubclass(err[0], test.failureException)
            self.mini.emit({"id": f"{self._id(test)} {subtest._subDescription()}", "outcome": "failed" if ok else "error", "trace": self._exc_info_to_string(err, test)})

    def addExpectedFailure(self, test, err):
        self.addSuccess(test)

    def addUnexpectedSuccess(self, test):
        self.mini.emit({"id": self._id(test), "outcome": "failed", "trace": "unexpected success (marked expectedFailure)"})


# ---- the pytest stand-in --------------------------------------------------------------------

class Skipped(Exception):
    pass


class _Mark:
    def __init__(self, name, args=(), kwargs=None, given=False):
        self.name, self.args, self.kwargs, self.given = name, args, kwargs or {}, given

    def __call__(self, *a, **k):
        if self.given or (len(a) == 1 and not k and callable(a[0])):  # used as a decorator
            return _mark(a[0], self)
        return _Mark(self.name, a, k, True)


def _mark(obj, m):
    obj._al_marks = list(vars(obj).get("_al_marks", [])) + [m]
    return obj


def _marks_of(obj):
    own = list(vars(obj).get("_al_marks", [])) if hasattr(obj, "__dict__") else []
    pm = vars(obj).get("pytestmark") if hasattr(obj, "__dict__") else None
    if pm is not None:
        own += [m for m in (pm if isinstance(pm, (list, tuple)) else [pm]) if isinstance(m, _Mark)]
    return own


def _skip_reason(marks):
    for m in marks:
        if m.name == "skip":
            return m.kwargs.get("reason") or (m.args[0] if m.args else "skipped")
        if m.name == "skipif" and m.args and m.args[0]:
            return m.kwargs.get("reason") or "skipif"
    return None


class _Marks:
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Mark(name)  # unknown marks (slow, integration …) are labels only


class _Missing:
    def __init__(self, what):
        self.what = what

    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return _Missing(f"{self.what}.{n}")

    def __call__(self, *a, **k):
        raise Unsupported(self.what)


class _Raises:
    def __init__(self, exc, match=None):
        self.exc, self.match, self.value = exc, match, None

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        if t is None:
            raise AssertionError(f"DID NOT RAISE {self.exc}")
        if not issubclass(t, self.exc):
            return False
        if self.match and not re.search(self.match, str(v)):
            raise AssertionError(f"{self.match!r} does not match {str(v)!r}")
        self.value = v
        return True


class _Approx:
    def __init__(self, expected, rel=None, abs=None):
        self.e, self.rel, self.abs = expected, rel, abs

    def _close(self, a, b):
        rel = 1e-6 if self.rel is None else self.rel
        return abs(a - b) <= max(rel * abs(b), 1e-12 if self.abs is None else self.abs)

    def __eq__(self, other):
        if isinstance(self.e, (list, tuple)):
            return len(other) == len(self.e) and all(self._close(a, b) for a, b in zip(other, self.e))
        if isinstance(self.e, dict):
            return other.keys() == self.e.keys() and all(self._close(other[k], v) for k, v in self.e.items())
        return self._close(other, self.e)

    def __repr__(self):
        return f"approx({self.e!r})"


class MonkeyPatch:
    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value=None, raising=True):
        if isinstance(target, str):
            import importlib

            mod, _, attr = target.rpartition(".")
            target, name, value = importlib.import_module(mod), attr, name
        old = getattr(target, name, _NOTSET)
        if old is _NOTSET and raising:
            raise AttributeError(f"{target!r} has no attribute {name!r}")
        setattr(target, name, value)
        self._undo.append(lambda: delattr(target, name) if old is _NOTSET else setattr(target, name, old))

    def delattr(self, target, name, raising=True):
        if not hasattr(target, name):
            if raising:
                raise AttributeError(name)
            return
        old = getattr(target, name)
        delattr(target, name)
        self._undo.append(lambda: setattr(target, name, old))

    def setitem(self, d, k, v):
        old = d.get(k, _NOTSET)
        d[k] = v
        self._undo.append(lambda: d.pop(k, None) if old is _NOTSET else d.__setitem__(k, old))

    def delitem(self, d, k, raising=True):
        if k not in d:
            if raising:
                raise KeyError(k)
            return
        old = d.pop(k)
        self._undo.append(lambda: d.__setitem__(k, old))

    def setenv(self, k, v, prepend=None):
        v = str(v)
        if prepend and os.environ.get(k):
            v = v + prepend + os.environ[k]
        self.setitem(os.environ, k, v)

    def delenv(self, k, raising=True):
        self.delitem(os.environ, k, raising)

    def syspath_prepend(self, p):
        sys.path.insert(0, str(p))
        self._undo.append(lambda: sys.path.remove(str(p)) if str(p) in sys.path else None)

    def chdir(self, p):
        old = os.getcwd()
        os.chdir(p)
        self._undo.append(lambda: os.chdir(old))

    def undo(self):
        for u in reversed(self._undo):
            u()
        self._undo = []


_NOTSET = object()


def _shim():
    import types

    m = types.ModuleType("pytest")
    m.__getattr__ = lambda name: _Missing(f"pytest.{name}")  # anything else: skipped where used
    m.__agentlink_shim__ = True
    m.mark = _Marks()

    def skip(reason="", allow_module_level=False, **_):
        raise Skipped(reason)

    def fail(reason="", **_):
        raise AssertionError(reason)

    def importorskip(name, minversion=None, reason=None):
        import importlib

        try:
            return importlib.import_module(name)
        except ImportError:
            raise Skipped(reason or f"could not import {name!r}")

    def raises(exc, *a, match=None, **k):
        r = _Raises(exc, match)
        if a:
            with r:
                a[0](*a[1:], **k)
            return r
        return r

    def fixture(*a, **k):
        def deco(f):
            f._al_fixture = k
            return f

        return deco(a[0]) if a and callable(a[0]) and not k else deco

    m.skip, m.fail, m.importorskip, m.raises, m.fixture, m.approx = skip, fail, importorskip, raises, fixture, _Approx
    return m

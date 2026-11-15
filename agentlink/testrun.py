# SPDX-License-Identifier: LGPL-2.1-or-later
"""addon_test's two halves, with no FreeCAD in them.

The tool's side (root_for, find_cmd, child_env, run): which add-on may be
tested, the FreeCAD command-line binary beside the running FreeCAD, the
environment, the compact answer and the full log. Running an add-on's
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
import time

from .protocol import ToolError, bad

OWN = "AgentLink"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}")
PATTERN = re.compile(r"[A-Za-z0-9_*?.\-\[\]]{1,80}\.py")
SELECT = re.compile(r"[A-Za-z0-9_]{1,120}")
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


def run(cmd, addon, root, own_root, roots, lib, log, pattern="test_*.py", select=None, timeout=TIMEOUT, pump=None):
    """Run root's tests in a separate process (cmd: freecadcmd, or any
    Python for the tests here) and answer as summarize() does; the full
    output and every traceback go to log."""
    tests = os.path.join(root, "tests")
    if not os.path.isdir(tests):
        raise ToolError("not_found", f"{addon} has no tests/ folder at {root}.")
    tmp = tempfile.mkdtemp(prefix="agentlink-test-")
    try:
        env = child_env(own_root, roots, lib, tmp)
        result = os.path.join(tmp, "results.jsonl")
        env.update(AGENTLINK_TEST_ROOT=root, AGENTLINK_TEST_DIR=tests, AGENTLINK_TEST_PATTERN=pattern,
                   AGENTLINK_TEST_SELECT=select or "", AGENTLINK_TEST_RESULT=result)
        boot = os.path.join(tmp, "agentlink_test_boot.py")
        with open(boot, "w", encoding="utf-8") as f:
            f.write(f"import sys\nsys.path.insert(0, {own_root!r})\nfrom agentlink import testrun\ntestrun.main()\n")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        t0 = time.time()
        timed_out = None
        with open(log, "w", encoding="utf-8", errors="replace") as lf:
            lf.write(f"addon_test {addon}: {root}\ncommand: {cmd} {boot}\npattern: {pattern}  select: {select or '-'}\n"
                     f"PYTHONPATH: {env['PYTHONPATH']}\n\n")
            lf.flush()
            p = subprocess.Popen([cmd, boot], stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, cwd=tmp,
                                 start_new_session=(os.name != "nt"))
            while p.poll() is None:
                if time.time() - t0 > timeout:
                    timed_out = timeout
                    _stop(p)
                    break
                (pump or (lambda: time.sleep(0.2)))()
        secs = time.time() - t0
        rows, runner = [], None
        try:
            with open(result, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if "runner" in r and "outcome" not in r:
                        runner = r["runner"]
                    elif "outcome" in r:
                        rows.append(r)
        except OSError:
            pass
        with open(log, "a", encoding="utf-8", errors="replace") as lf:
            lf.write(f"\n== exit {p.returncode}, {secs:.1f} s ==\n")
            for r in rows:
                if r["outcome"] in ("failed", "error"):
                    lf.write(f"\n== {r['outcome']}: {r.get('id')}\n{r.get('trace', '')}\n")
        if not rows and runner is None:
            with open(log, encoding="utf-8", errors="replace") as lf:
                tail = _tail(lf.read(), chars=1200)
            how = f"stopped after {timeout:g} s" if timed_out else f"exit {p.returncode}"
            raise ToolError("failed", f"The tests did not start ({how}): {tail}\nFull log: {log}")
        out = summarize(rows, addon, runner, secs, log, timed_out)
        if not rows:
            out["note"] = f"No tests matched (pattern {pattern}" + (f", select {select}" if select else "") + ")."
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _stop(p):
    import signal

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

    def emit(row):
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

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
    sys.stdout.write(f"\naddon_test: done in {time.time() - t0:.1f} s\n")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def _with_pytest(root, tests, pattern, select, emit):
    import os
    import xml.etree.ElementTree as ET

    import pytest

    xml = os.path.join(os.path.dirname(os.environ["AGENTLINK_TEST_RESULT"]), "junit.xml")
    args = [tests, "-q", "-p", "no:cacheprovider", "--rootdir", root, "--continue-on-collection-errors", "-o", f"python_files={pattern}", f"--junitxml={xml}"]
    if select:
        args += ["-k", select]
    pytest.main(args)
    try:
        cases = ET.parse(xml).getroot().iter("testcase")
    except (OSError, ET.ParseError):
        return
    for tc in cases:
        tid = f"{tc.get('classname', '')}::{tc.get('name', '')}"
        kids = {k.tag: k for k in tc}
        if "failure" in kids or "error" in kids:
            k = kids.get("failure", kids.get("error"))
            emit({"id": tid, "outcome": "failed" if k.tag == "failure" else "error", "trace": (k.text or k.get("message") or "")})
        elif "skipped" in kids:
            emit({"id": tid, "outcome": "skipped", "reason": kids["skipped"].get("message") or ""})
        else:
            emit({"id": tid, "outcome": "passed"})


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

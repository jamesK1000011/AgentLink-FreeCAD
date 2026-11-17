# SPDX-License-Identifier: LGPL-2.1-or-later
"""What a data tool needs, read from the tool itself: a dry reading of its
leading checks against the document as it is now, without running the tool.

A steps entry (agentlink/data/tools.json; agentlink/runners.py) begins with
`let` and `refuse` steps: the tool's own checks, in its own words, before
its first step that changes the document. reading() runs THOSE SAME steps,
through the runners' own evaluator, and stops at the first step that is not
provably a reading. There is no second description of what a tool needs:
no table of words or states. What a reading says:

    { tool, applies: true | false | null, wouldRefuse: [{ code, words }],
      notChecked: [reason] }

  false   one of the leading checks refuses now: wouldRefuse has its code
          and its words, as the call would give them
  true    every leading check was read, there was at least one, and all
          pass (notChecked then says how many of the tool's checks come
          after its first change: those only the call tells)
  null    not checked: a leading step needs the call's arguments, calls a
          helper that is not a known reader, or raised; or there is no
          leading check to read; or the tool is not a steps entry — never
          a guess either way

It is advice. It hides nothing, blocks nothing and is never the authority:
the tool's own refusal is.

Never guess, never change:
  - a step is evaluated only when every helper it calls is in the family's
    list of pure readers (data/readers.json, derived from the helpers' code
    by scripts/tool_needs.py and pinned by tests/test_needs.py), every
    method it calls is in that file's "methods", and every function is one
    of the expressions' own. Anything else is treated as unsafe. The
    helpers handed to the evaluator are the readers only, so an unsafe one
    cannot be reached even by a mistake here;
  - make, add and set steps, a `do` that is not a reading, a refusal with
    `first` (something to undo: a change came before it) and an answer end
    the leading part;
  - without the call's arguments ("a"), a step that reads them, or a value
    made from them, is not evaluated: it is counted as needing arguments.
    With arguments given, those steps are evaluated too;
  - a step that raises anything but a refusal ends the reading as not
    checked.

Plain Python: FreeCAD is reached only through the tool's own helpers.
"""
import ast
import json
import os
import sys
import time

from . import expr, runners
from .protocol import ToolError

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "readers.json")
STEP_S = 1.0          # one reading asked for by name (tool_groups { needs }) stops after this
MAX_WORDS = 300       # a refusal's words in a reading

_cache = {}


def _file():
    if "file" not in _cache:
        try:
            with open(DATA, encoding="utf-8") as f:
                _cache["file"] = json.load(f)
        except (OSError, ValueError):
            _cache["file"] = {}
    return _cache["file"]


def readers(family):
    """The family's helpers a dry reading may call (none when the file is
    missing or does not have the family: everything is then unsafe)."""
    return _names(family, "readers")


def _names(entry, key):
    k = (entry, key)
    if k not in _cache:
        e = (_file().get("entries") or {}).get(entry)
        _cache[k] = frozenset((e.get(key) if isinstance(e, dict) else None) or ())
    return _cache[k]


def changers(family):
    """The family's helpers whose code writes (the document, the selection,
    the window, a setting): where a tool's leading part ends."""
    return _names(family, "changers")


def methods():
    """The methods taken as readings by name."""
    return _names("methods", "reading")


def python_only():
    """The reading methods that are Python's own: taken on a Python value only."""
    return _names("methods", "pythonOnly")


def string_call(name, args):
    """Whether x.split(…) or x.join(…) is a string's, by its arguments
    (scripts/tool_needs.py has why: a sketch's split and join change it)."""
    if name == "join":
        return len(args) == 1
    return len(args) <= 1 or (isinstance(args[0], ast.Constant) and isinstance(args[0].value, str))


PYTHON = (str, bytes, dict, list, tuple, set, frozenset, int, float, complex, type(None))


def _guard(x, name):
    """Before a method of a value is called in a dry reading: one of
    Python's own names is taken on a Python value (numpy's and re's
    included) and on nothing else."""
    if name in python_only() and not isinstance(x, PYTHON) and type(x).__module__.split(".")[0] not in ("numpy", "re", "builtins", "collections"):
        raise _Stop("blocked", f".{name}() of a {type(x).__name__} is not a known reading")


def writes():
    """FreeCAD's own methods that write, by name."""
    return _names("methods", "writes")


def family_of(entry):
    """The key of an entry's helpers in readers.json: its family, else its group."""
    return entry.get("family") or entry.get("group")


def _dry_maker(dotted):
    """runners' maker for a dry reading: a module's function only when the
    module is loaded already (a reading imports nothing)."""
    mod, _, fn = str(dotted).rpartition(".")
    if mod not in sys.modules:
        raise _Stop("blocked", f"the module {mod} is not loaded yet")
    return getattr(sys.modules[mod], fn, None)


# The expressions' own functions: all of them only read or build a value,
# but maker, which imports (a dry one stands in for it).
FUNCTIONS = {**{k: v for k, v in expr.FUNCTIONS.items() if k != "maker"}, "maker": _dry_maker}


# ---- what a value calls and reads (static) ----------------------------------------------------

class _Use:
    """What one value of an entry uses: the names it reads, and why it is
    not a reading (None when it is one)."""

    __slots__ = ("names", "why", "helpers", "unknown", "changes")

    def __init__(self):
        self.names, self.why, self.helpers, self.unknown, self.changes = set(), None, set(), False, False

    def bad(self, why, change=False):
        """Not a reading: change, when what it calls is known to write
        (a changer, a writing method); else unknown."""
        if self.why is None or (self.changes and not change and not self.unknown):
            self.why = why
        if change:
            self.changes = True
        else:
            self.unknown = True

    @property
    def stop(self):
        """None for a reading; "change" when all that is not a reading is
        known to write; "blocked" when any of it is unknown."""
        return None if self.why is None else "blocked" if self.unknown else "change"


def _use_expr(text, family, use):
    try:
        tree = expr.parse(text)
    except expr.ExprError as e:
        use.bad(str(e))
        return
    ok, chg, meth, wr = readers(family), changers(family), methods(), writes()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            use.names.add(n.id)
            if n.id in chg:  # called here, or handed on by name to what calls it
                use.bad(f"{n.id}() writes", True)
            elif n.id in ok:
                use.helpers.add(n.id)
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name):
            if f.id not in ok and f.id not in chg and f.id not in FUNCTIONS:
                use.bad(f"{f.id}() is not a known reader")
        elif f.attr in wr or (f.attr in ("split", "join") and not string_call(f.attr, n.args)):
            use.bad(f".{f.attr}() writes", True)
        elif f.attr not in meth:
            use.bad(f".{f.attr}() is not a known reading")


def _use_fmt(template, family, use):
    try:
        parts = expr._split(template)
    except expr.ExprError as e:
        use.bad(str(e))
        return
    for _text, field, _spec, _conv in parts:
        if field is None:
            continue
        if expr._PLAIN.match(field):
            use.names.add(field.split(".")[0])
        else:
            _use_expr(field, family, use)


def _use(x, family, use=None):
    """What a value of an entry (an expression, a "$path", a message, a
    list or an object of them) uses."""
    use = _Use() if use is None else use
    if isinstance(x, str):
        if x.startswith("="):
            _use_expr(x[1:], family, use)
        elif x.startswith("$"):
            use.names.add(x[1:].split(".")[0].replace("[]", ""))
    elif isinstance(x, list):
        for v in x:
            _use(v, family, use)
    elif isinstance(x, dict):
        if len(x) == 1:
            (op, arg), = x.items()
            if op == "fmt" and isinstance(arg, str):
                _use_fmt(arg, family, use)
                return use
            if op in ("set", "do"):
                use.bad(f"{{{op}}} changes what it is given", op == "set")
                return use
        if "call" in x and set(x) <= {"call", "with"}:
            if x["call"] in readers(family):
                use.helpers.add(x["call"])
            elif x["call"] in changers(family):
                use.bad(f"{x['call']}() writes", True)
            else:
                use.bad(f"{x['call']}() is not a known reader")
            return _use(x.get("with", []), family, use)
        for v in x.values():
            _use(v, family, use)
    return use


_used = {}


def use_of(x, family):
    """_use(), kept by the value's identity (an entry's values are read once)."""
    key = (id(x), family)
    got = _used.get(key)
    if got is None or got[0] is not x:
        got = _used[key] = (x, _use(x, family))
    return got[1]


# ---- the steps, statically ------------------------------------------------------------------

NESTED = ("then", "else", "steps", "try", "except")


def _children(st):
    for k in NESTED:
        if isinstance(st.get(k), list):
            yield from st[k]
    if isinstance(st.get("of"), dict):
        for v in st["of"].values():
            yield from v


def _binds(st):
    """The names a step (and the steps in it) may set."""
    out = set()
    for k in (st.get("let") or {}) if isinstance(st.get("let"), dict) else ():
        out.update(x.strip() for x in k.split(","))
    for k in ("as", "index"):
        if isinstance(st.get(k), str):
            out.add(st[k])
    if "make" in st or "add" in st:
        out.add(st.get("as", "o"))
    if isinstance(st.get("each"), str):
        out.update(x.strip() for x in st["each"].split(","))
    if "put" in st:
        out.add(st.get("into", "out"))
    if isinstance(st.get("push"), dict):
        out.update(st["push"])
    if "try" in st:
        out.add("error")
    for c in _children(st):
        out |= _binds(c)
    return out


def _lists(st):
    """A step's own lists of steps, each a way a run may go."""
    for k in NESTED:
        if isinstance(st.get(k), list):
            yield k, st[k]
    if isinstance(st.get("of"), dict):
        for v in st["of"].values():
            yield "of", v


_kinds = {}


def kind(st, family):
    """What a step is to a dry reading: "pure" (it and all in it only read,
    by the lists), "change" (it ends the leading part: make, add, set, a do
    that is not a reading, a refusal that undoes first, an answer, or a
    step holding one of those), "blocked" (a value in it calls what is not
    a known reader, so what follows cannot be told)."""
    got = _kinds.get(id(st))
    if got is None or got[0] is not st:
        got = _kinds[id(st)] = (st, _kind(st, family))
    return got[1]


def _kind(st, family):
    stops = {use_of(st[k], family).stop for k in ("when", "let", "put", "push", "in", "choose") if k in st}
    if "blocked" in stops:
        return "blocked"
    if "change" in stops or "make" in st or "add" in st or "set" in st or "answer" in st:
        return "change"
    if "refuse" in st:
        return "change" if st.get("first") else "pure"  # its words are not needed to know that it refuses
    if "do" in st:
        return "change" if use_of(st["do"], family).why else "pure"  # done for its effect: what is not a reading is the change
    kinds = [kind(c, family) for c in _children(st)]
    return "change" if "change" in kinds else "blocked" if "blocked" in kinds else "pure"


def _lead_walk(steps, family, seen):
    """seen(step) for every step of steps a run can reach before a change;
    False when the list holds a change (what follows the list then comes
    after one)."""
    for st in steps:
        k = kind(st, family)
        inner = list(_lists(st))
        if k == "change" and not inner:
            return False  # the changing step itself: a refusal from inside it is not a leading check's
        seen(st)
        clean = True
        for name, lst in inner:
            if name == "except" and not clean:
                continue  # after a try that may have changed something
            clean = _lead_walk(lst, family, seen) and clean
        if not clean:
            return False
    return True


def leading(entry):
    """The ids of an entry's leading steps: every step a run can reach
    before any step that changes (in a branch: while nothing before it in
    its own list, or before the branch, changes). What a refusal is told
    from: a call refused at one of these was refused by a leading check
    (runners puts the step on the refusal)."""
    key = ("lead", id(entry))
    got = _cache.get(key)
    if got is None or got[0] is not entry:
        out = set()
        _lead_walk(entry.get("steps") or [], family_of(entry), lambda st: out.add(id(st)))
        got = _cache[key] = (entry, out)
    return got[1]


def later_refusals(entry):
    """How many of an entry's refuse steps are not leading ones (they come
    after a step that changes, or undo something first)."""
    key = ("later", id(entry))
    got = _cache.get(key)
    if got is None or got[0] is not entry:
        every = []

        def walk(x):
            if isinstance(x, dict):
                if "refuse" in x:
                    every.append(x)
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)

        walk(entry.get("steps") or [])
        walk(entry.get("answer") or {})
        lead = leading(entry)
        got = _cache[key] = (entry, sum(1 for st in every if id(st) not in lead))
    return got[1]


def leading_refusals(steps, family):
    """The refuse steps among steps' leading steps."""
    out = []
    _lead_walk(steps, family, lambda st: out.append(st) if "refuse" in st else None)
    return out


# ---- the dry reading ------------------------------------------------------------------------

class _Stop(BaseException):
    """The reading ends here (BaseException: no try step catches it)."""

    def __init__(self, how, why=None):
        self.how, self.why = how, why


def _never(name):
    """What stands in for a helper that is not a known reader: reaching it ends the reading."""
    def stop(*_a, **_k):
        raise _Stop("blocked", f"{name}() is not a known reader")

    return stop


class _Run:
    def __init__(self, entry, helpers, args, deadline):
        self.family = family_of(entry)
        ok = readers(self.family)
        # The readers as they are; every other helper as a stop, so that none can be reached (a helper wins over
        # an expressions' function of its name, as in a run); the dry maker.
        self.helpers = {k: (v if k in ok or not callable(v) else _never(k)) for k, v in (helpers or {}).items()}  # a table is read as it is
        self.helpers.setdefault("maker", _dry_maker)
        self.given = args is not None
        self.tainted = set() if self.given else {"a"}
        self.deadline = deadline
        self.evaluated = 0     # checks evaluated: refuse steps read, and steps that called a helper
        self.args_steps = []   # what was left for the call's arguments
        self.at = None

    # -- one value --

    def use(self, x):
        return use_of(x, self.family)

    def needs_args(self, x):
        return bool(self.use(x).names & self.tainted)

    def value(self, x, env):
        return runners.value(x, env, self.helpers)

    def left(self, st, what):
        self.args_steps.append(what)

    def calls_helper(self, st):
        for k in ("when", "let", "do", "put", "push", "in", "choose"):
            if k in st and self.use(st[k]).helpers:
                return True
        return any(self.calls_helper(c) for c in _children(st))

    # -- the steps --

    def steps(self, steps, env):
        for st in steps:
            if self.deadline is not None and time.time() > self.deadline:
                raise _Stop("blocked", "the reading ran out of time")
            self.at = st
            self.step(st, env)

    def skip(self, st):
        """A step that cannot be read without the arguments: passed over
        when all of it only reads (what it would set is unknown from here
        on), the end of the leading part when it holds a change."""
        k = kind(st, self.family)
        if k == "blocked":
            raise _Stop("blocked", self.why_blocked(st))
        n = len(leading_refusals([st], self.family))
        if n or self.calls_helper(st):
            self.left(st, n)
        if k == "change":
            raise _Stop("change")
        self.tainted |= _binds(st)

    def end(self, u):
        """The reading ends at a value that is not one: a known write is
        the end of the leading part, anything else leaves the rest untold."""
        raise _Stop("change") if u.stop == "change" else _Stop("blocked", u.why)

    def why_blocked(self, st):
        for k in ("when", "let", "put", "push", "in", "choose"):
            if k in st and self.use(st[k]).stop == "blocked":
                return self.use(st[k]).why
        for c in _children(st):
            if kind(c, self.family) == "blocked":
                return self.why_blocked(c)
        return "a step is not a known reading"

    def step(self, st, env):
        if "when" in st:
            u = self.use(st["when"])
            if u.why:
                self.end(u)
            if self.needs_args(st["when"]):
                return self.skip(st)
            if not self.value(st["when"], env):
                if "then" in st:
                    self.steps(st.get("else", []), env)
                elif "refuse" in st:
                    self.evaluated += 1
                return None
        if "let" in st:
            for k, x in st["let"].items():
                u = self.use(x)
                if u.why:
                    self.end(u)
                names = [n.strip() for n in k.split(",")]
                if self.needs_args(x):
                    self.tainted.update(names)
                    if u.helpers:
                        self.left(st, 0)
                    continue
                v = self.value(x, env)
                if u.helpers:
                    self.evaluated += 1
                runners._assign(k, v, env)
                self.tainted.difference_update(names)
        elif "refuse" in st:
            if st.get("first"):
                raise _Stop("change")
            u = self.use(st["refuse"])
            if u.why or self.needs_args(st["refuse"]):
                # The check itself was read (its condition held): its words need what is not known here.
                words = st["refuse"]["fmt"] if isinstance(st["refuse"], dict) else st["refuse"]
            else:
                words = self.value(st["refuse"], env)
            self.evaluated += 1
            raise ToolError(st.get("code", "invalid_input"), words)
        elif "make" in st or "add" in st or "set" in st:
            raise _Stop("change")
        elif "answer" in st:
            raise _Stop("answer")
        elif "do" in st:
            u = self.use(st["do"])
            if u.why:
                raise _Stop("change")
            if self.needs_args(st["do"]):
                if u.helpers:
                    self.left(st, 0)
                return None
            self.value(st["do"], env)
            if u.helpers:
                self.evaluated += 1
        elif "put" in st or "push" in st:
            act = "put" if "put" in st else "push"
            u = self.use(st[act])
            if u.why:
                self.end(u)
            into = [st.get("into", "out")] if act == "put" else list(st[act])
            if self.needs_args(st[act]) or set(into) & self.tainted:
                self.tainted.update(into)
                return None
            if any(type(env.get(k)) not in (dict, list) for k in into):
                raise _Stop("blocked", f"{act} into a value the reading did not make")
            for k, x in st[act].items():
                if act == "put":
                    env[into[0]][k] = self.value(x, env)
                else:
                    env[k].append(self.value(x, env))
        elif "each" in st:
            u = self.use(st["in"])
            if u.why:
                self.end(u)
            if self.needs_args(st["in"]):
                return self.skip(st)
            for i, x in enumerate(list(self.value(st["in"], env))):
                runners._assign(st["each"], x, env)
                if "index" in st:
                    env[st["index"]] = i
                self.steps(st["steps"], env)
        elif "choose" in st:
            u = self.use(st["choose"])
            if u.why:
                self.end(u)
            if self.needs_args(st["choose"]):
                return self.skip(st)
            v = self.value(st["choose"], env)
            self.steps(st["of"][v] if isinstance(v, str) and v in st["of"] else st.get("else", []), env)
        elif "try" in st:
            try:
                self.steps(st["try"], env)
            except runners._caught(st.get("on", "error")) as e:
                if st.get("on") == "failure" and isinstance(e, ToolError):
                    raise
                env["error"] = e
                self.tainted.discard("error")
                self.steps(st.get("except", []), env)
                if st.get("reraise"):
                    raise
        elif "then" in st:
            self.steps(st["then"], env)
        else:
            raise _Stop("blocked", "a step the reading does not know")
        return None


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _result(name, applies, refused=(), not_checked=()):
    return {"tool": name, "applies": applies, "wouldRefuse": list(refused), "notChecked": list(not_checked)}


def reading(name, entry, helpers, args=None, budget=STEP_S):
    """The dry reading of one tool (the module's docstring has the shape).
    entry: its tools.json entry (None: not a data tool); helpers: its
    family's; args: the call's arguments, or None for what can be told
    without them. Never raises, and changes nothing."""
    if not isinstance(entry, dict) or not entry.get("runner"):
        return _result(name, None, not_checked=["not a data tool: its checks are in its code"])
    if entry["runner"] != "steps":
        return _result(name, None, not_checked=[f"a {entry['runner']} wrapper: its rules are checked by the call"])
    if args is not None and not isinstance(args, dict):
        return _result(name, None, not_checked=["arguments: an object"])
    run = _Run(entry, helpers, args, None if budget is None else time.time() + budget)
    env = {"a": dict(args) if args is not None else {}, "tool": name, expr.GUARD: _guard}
    stop = None
    try:
        run.steps(entry.get("steps") or [], env)
    except _Stop as s:
        stop = s
    except ToolError as e:
        return _result(name, False, [{"code": e.code, "words": str(e.message)[:MAX_WORDS], "step": id(getattr(e, "step", None) or run.at)}])
    except Exception as e:  # noqa: BLE001 - a step that raises is not a refusal, and not a reading
        return _result(name, None, not_checked=[f"a leading step raised {type(e).__name__}: {str(e)[:80]}"])
    notes = []
    if run.args_steps:
        n = sum(run.args_steps)
        notes.append(f"{_plural(len(run.args_steps), 'leading step')} ({_plural(n, 'refusal')} written in them) need the call's arguments"
                     + (f"; what needs none passes ({run.evaluated} read)" if run.evaluated else "")
                     + f": tool_groups {{ needs: \"{name}\", arguments: {{…}} }} reads them too")
    if stop is not None and stop.how == "blocked":
        return _result(name, None, not_checked=[f"stopped before the end of the leading checks: {stop.why}", *notes])
    if notes:
        return _result(name, None, not_checked=notes)
    later = later_refusals(entry)
    if not run.evaluated:
        # Nothing was read: "applies" would say more than is known.
        return _result(name, None, not_checked=["no leading check to read: this tool's checks are inside its helpers"
                                                + (f", or come after its first change ({later} of them)" if later else "")])
    # Its leading checks all pass. Checks written after its first change are not leading ones: only the call tells.
    return _result(name, True, not_checked=[f"{later} of this tool's checks come after its first change: only the call tells"] if later else [])


def of_tool(tool, args=None, budget=STEP_S):
    """reading() of a server's tool: its entry and helpers are on the tool
    when the runners built it (runners.tool)."""
    return reading(tool.name, getattr(tool, "entry", None), getattr(tool, "helpers", None), args, budget)


def public(r):
    """A reading as an answer gives it (no step ids)."""
    return {**r, "wouldRefuse": [{"code": x["code"], "words": x["words"]} for x in r["wouldRefuse"]]}


CLASSES = ("applies", "not", "notChecked")


def klass(r):
    return "applies" if r["applies"] is True else "not" if r["applies"] is False else "notChecked"


def census(entries=None):
    """Per family, how the entries stand before any document is looked at
    (from tools.json and readers.json alone): tools; steps entries;
    leadingRefusals (refuse steps a run can reach before a change);
    noArgument (those of them that read no argument, nor a value made from
    one); and each steps entry in one of four: blocked (its leading part
    meets a step that calls what is not a known reader), needsArguments
    (not blocked; some leading step reads the arguments), complete (not
    blocked, no leading step reads them: the reading is whole without
    arguments), of which noCheck have no leading refusal at all."""
    entries = runners.entries() if entries is None else entries
    out = {}
    for name, e in entries.items():
        fam = family_of(e)
        row = out.setdefault(fam, {"tools": 0, "steps": 0, "leadingRefusals": 0, "noArgument": 0, "blocked": 0, "needsArguments": 0, "complete": 0, "noCheck": 0})
        row["tools"] += 1
        if e.get("runner") != "steps":
            continue
        row["steps"] += 1
        lead = leading_refusals(e.get("steps") or [], fam)
        row["leadingRefusals"] += len(lead)
        st = _static(e.get("steps") or [], fam)
        row["noArgument"] += st["free"]
        which = "blocked" if st["blocked"] else "needsArguments" if st["args"] else "complete"
        row[which] += 1
        if which == "complete" and not lead:
            row["noCheck"] += 1
    return out


def _static(steps, family, tainted=None, out=None):
    """The reading's walk without a document: every branch taken."""
    tainted = {"a"} if tainted is None else tainted
    out = {"free": 0, "args": 0, "blocked": False, "ended": False} if out is None else out
    for st in steps:
        k = kind(st, family)
        heads = [st[key] for key in ("when", "in", "choose") if key in st]
        own = [st[key] for key in ("refuse", "let", "do", "put", "push") if key in st]
        if any(use_of(x, family).stop == "blocked" for x in heads) or (k == "blocked" and not list(_lists(st))):
            out["blocked"] = out["ended"] = True
            return out
        if any(use_of(x, family).stop == "change" for x in heads):
            out["ended"] = True
            return out
        needs = any(use_of(x, family).names & tainted for x in heads)
        if needs:
            if k == "blocked":
                out["blocked"] = out["ended"] = True
                return out
            if leading_refusals([st], family) or any(use_of(x, family).helpers for x in heads + own):
                out["args"] += 1
            tainted |= _binds(st)
        elif "refuse" in st and not st.get("first"):
            out["free"] += 1
        elif "let" in st:
            for key, x in st["let"].items():
                u = use_of(x, family)
                if u.names & tainted:
                    tainted.update(n.strip() for n in key.split(","))
                    out["args"] += 1 if u.helpers else 0
        elif own and not list(_lists(st)):
            if any(use_of(x, family).names & tainted for x in own):
                out["args"] += 1 if any(use_of(x, family).helpers for x in own) else 0
                tainted |= _binds(st)
        else:
            for _name, lst in _lists(st):
                _static(lst, family, tainted, out)
                if out["blocked"]:
                    return out
            out["ended"] = False
        if k == "change":
            out["ended"] = True
            return out
    return out

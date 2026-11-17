# SPDX-License-Identifier: LGPL-2.1-or-later
# What a data tool needs, read from its own leading checks (agentlink/needs.py),
# the live filter and its meter (agentlink/appliesnow.py):
#
#   - the list of pure readers (agentlink/data/readers.json) is the one the
#     helpers' code gives (scripts/tool_needs.py) and is pinned here: a helper
#     that is not in it is never called by a reading;
#   - each step kind, read dry, on entries made for the purpose;
#   - on the stand-in FreeCADs of the data tools' own tests, every case of
#     five suites: the reading with the case's arguments, then the tool itself
#     — a reading of "false" is the call's refusal word for word, a reading of
#     "true" is never refused before the tool's first change, and no reading
#     changes anything (in a child process: a stand-in must not be seen by the
#     other tests);
#   - the filter's set, line and full reading on three stand-in states, the
#     meter's counts, and what each costs in tokens (pinned upper bounds).
#
# Plain Python. With FreeCAD importable, tool_groups { needs }, { now } and
# { find } are run through the real server too (skipped otherwise).
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import appliesnow, needs, runners  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402

# The readers' pin: sha256 of readers.json's entries (each family's readers and changers, and the methods), as
# scripts/tool_needs.py writes them. A helper or a method that joins or leaves a list changes it: read why
# (`python3 scripts/tool_needs.py --why name`), then put the new value here.
PIN = "1c477476094a00b58f93a80b4e300ca7bd238c09521bcd07ba39daf2a69bcaef"
COUNTS = {"readers": 892, "changers": 141, "families": 36}

# The stand-in suites whose cases are run: name -> (stand-in, cases, family files).
SUITES = {
    "pd": ("_datapd_standin", "_datapd_cases", ("feature", "std_more", "sketch")),
    "mesh": ("_datamesh_standin", "_datamesh_cases", None),
    "td": ("_datatd_standin", "_datatd_cases", None),
    "cam": ("_datacam_standin", "_datacam_cases", None),
    "bim": ("_bim_standin", "_bim_cases", ("bim", "bim_more", "bim_gaps")),
}
# What the cases must at least show (so that an agreement of nothing with nothing does not pass): per suite,
# readings of false and of true with the arguments given.
AT_LEAST = {"pd": (212, 307), "mesh": (133, 48), "td": (61, 73), "cam": (6, 2), "bim": (144, 155)}

NUMPY = ("mesh", "td", "cam")
CHARS_PER_TOKEN = 3.5


def tokens(x):
    text = x if isinstance(x, str) else json.dumps(x, separators=(",", ":"), ensure_ascii=False)
    return int(round(len(text) / CHARS_PER_TOKEN))


def _numpy():
    try:
        import numpy  # noqa: F401
    except ImportError:
        return False
    return True


_ran = {}


def _child(*mode):
    if mode not in _ran:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), *mode], capture_output=True, text=True, timeout=280)
        if r.returncode != 0:
            raise AssertionError(f"child {mode} failed:\n{r.stderr[-3000:]}")
        # (the last line: a stand-in may print on the way, as FreeCAD's nester does)
        _ran[mode] = json.loads([ln for ln in r.stdout.splitlines() if ln.startswith(("{", "["))][-1])
    return _ran[mode]


def _readers_file():
    with open(needs.DATA, encoding="utf-8") as f:
        return json.load(f)


class Readers(unittest.TestCase):
    """The allowlist: derived from the code, pinned, and closed."""

    def test_the_file_is_what_the_helpers_code_gives(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "tool_needs.py"), "--check"], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_lists_are_pinned(self):
        d = _readers_file()["entries"]
        lists = {k: {x: v[x] for x in v if x not in ("source", "date")} for k, v in d.items()}
        got = hashlib.sha256(json.dumps(lists, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(got, PIN, "readers.json's lists changed: read why (scripts/tool_needs.py --why <helper>), then pin the new value")
        fams = [v for k, v in d.items() if k != "methods"]
        self.assertEqual({"readers": sum(len(v["readers"]) for v in fams), "changers": sum(len(v["changers"]) for v in fams), "families": len(fams)}, COUNTS)

    def test_no_helper_is_both_and_every_family_of_a_data_tool_is_there(self):
        d = _readers_file()["entries"]
        m = d["methods"]
        for fam, e in d.items():
            if fam != "methods":
                self.assertEqual(set(e["readers"]) & set(e["changers"]), set(), fam)
        self.assertEqual({needs.family_of(e) for e in runners.entries().values()}, set(d) - {"methods"})
        self.assertEqual(set(m["reading"]) & set(m["writes"]), set())
        self.assertLessEqual(set(m["pythonOnly"]) | set(m["byShape"]), set(m["reading"]))
        self.assertEqual(needs.readers("no_such_family"), frozenset())  # a family the file has not heard of has no reader

    def test_helpers_known_to_change_are_not_readers(self):
        """Read in the code: each of these writes (a solve, a new object, a
        property, a setting), or keeps the session's own books."""
        d = _readers_file()["entries"]
        for fam, name in (("sketch", "state_of"), ("feature", "new"), ("assembly", "typed"), ("assembly", "grounded"), ("assembly", "joints"),
                          ("sheet", "params_sheet"), ("techdraw", "warm"), ("feature", "finish"), ("openscad", "exe"), ("cam", "job_of"),
                          ("bim", "baseline"), ("model", "profile"), ("sketch", "build")):
            self.assertNotIn(name, d[fam]["readers"], f"{fam}.{name}")
        for fam, name in (("feature", "new"), ("assembly", "typed"), ("assembly", "joints"), ("openscad", "exe"), ("cam", "job_of")):
            self.assertIn(name, d[fam]["changers"], f"{fam}.{name}")
        for fam, name in (("feature", "body"), ("feature", "sketch_of"), ("feature", "volume"), ("techdraw", "page_of"), ("sheet", "bindings")):
            self.assertIn(name, d[fam]["readers"], f"{fam}.{name}")
        # FreeCAD's own names that change what they are called on are no reading.
        for m in ("recompute", "solve", "addObject", "newObject", "removeObject", "addGeometry", "delConstraint", "setDatum", "openTransaction",
                  "addSelection", "clearSelection", "runCommand", "SetBool", "append", "update", "clear", "touch"):
            self.assertNotIn(m, d["methods"]["reading"], m)

    def test_a_sketchs_split_and_join_are_told_from_a_strings(self):
        import ast

        def args(text):
            return ast.parse(text, mode="eval").body.args

        self.assertTrue(needs.string_call("split", args("f()")))
        self.assertTrue(needs.string_call("split", args("f(sep)")))
        self.assertTrue(needs.string_call("split", args("f(',', 1)")))
        self.assertFalse(needs.string_call("split", args("f(4, V(0, 10, 0))")))
        self.assertTrue(needs.string_call("join", args("f(names)")))
        self.assertFalse(needs.string_call("join", args("f(1, 2, 3, 1)")))
        self.assertEqual(needs.use_of("=sk.split(g, p)", "sketch").stop, "change")
        self.assertIsNone(needs.use_of("=name.split('.')", "sketch").stop)


def _entry(steps, family="t", **more):
    return {"group": family, "runner": "steps", "steps": steps, **more}


class _Files:
    """readers.json swapped for a small one of the test's own."""

    def __init__(self, readers=(), changers=()):
        self.doc = {"entries": {"t": {"readers": list(readers), "changers": list(changers)},
                                "methods": {"reading": ["get", "lower", "startswith", "copy", "split", "join", "isNull"], "pythonOnly": ["lower", "startswith", "split", "join"],
                                            "byShape": ["split", "join"], "writes": ["recompute", "addObject"]}}}

    def __enter__(self):
        self.kept = dict(needs._cache)
        needs._cache.clear()
        needs._cache["file"] = self.doc
        needs._used.clear()
        needs._kinds.clear()

    def __exit__(self, *exc):
        needs._cache.clear()
        needs._cache.update(self.kept)
        needs._used.clear()
        needs._kinds.clear()


class Reading(unittest.TestCase):
    """Each step kind, dry."""

    def setUp(self):
        self.called = []

        def count():
            self.called.append("count")
            return self.n

        def find(ref):
            self.called.append(f"find {ref}")
            if ref not in self.have:
                raise ToolError("not_found", f"{ref}: not here.")
            return ref

        def make(*_a):
            self.called.append("make")
            raise AssertionError("a reading called a changer")

        def unknown(*_a):
            self.called.append("unknown")
            raise AssertionError("a reading called a helper that is not a known reader")

        self.n, self.have = 0, {"A"}
        self.helpers = {"count": count, "find": find, "make": make, "unknown": unknown, "KINDS": ("a", "b")}
        self.files = _Files(readers=("count", "find"), changers=("make",))

    def read(self, steps, args=None, **more):
        with self.files:
            return needs.public(needs.reading("t_tool", _entry(steps, **more), self.helpers, args))

    def test_a_check_that_refuses_now_is_false_with_its_code_and_words(self):
        steps = [{"let": {"n": "=count()"}}, {"refuse": {"fmt": "Nothing here ({n}): t_new first."}, "code": "invalid_state", "when": "=n == 0"}, {"add": "X::Y"}]
        self.assertEqual(self.read(steps), {"tool": "t_tool", "applies": False, "wouldRefuse": [{"code": "invalid_state", "words": "Nothing here (0): t_new first."}],
                                            "notChecked": []})
        self.n = 2
        self.assertEqual(self.read(steps), {"tool": "t_tool", "applies": True, "wouldRefuse": [], "notChecked": []})

    def test_a_step_that_reads_the_arguments_waits_for_them(self):
        steps = [{"let": {"o": "=find(a.object)", "n": "=count()"}}, {"refuse": "Nothing here.", "code": "invalid_state", "when": "=n == 0"},
                 {"refuse": {"fmt": "{o} is not it."}, "when": "=o != 'A'"}, {"set": {"o.Label": "x"}}]
        got = self.read(steps)  # the state check needs no argument and refuses
        self.assertIs(got["applies"], False)
        self.assertEqual(self.called, ["count"])  # find(a.object) was not called without the arguments
        self.n = 1
        got = self.read(steps)
        self.assertIsNone(got["applies"])
        self.assertEqual(len(got["notChecked"]), 1)
        self.assertIn("2 leading steps (1 refusal written in them) need the call's arguments; what needs none passes (2 read)", got["notChecked"][0])
        # With the arguments: all of it.
        self.assertIs(self.read(steps, {"object": "A"})["applies"], True)
        self.assertEqual(self.read(steps, {"object": "B"})["wouldRefuse"], [{"code": "not_found", "words": "B: not here."}])  # the finder's own refusal
        self.assertEqual(self.read(steps, {})["wouldRefuse"], [{"code": "not_found", "words": "None: not here."}])  # the call with nothing given

    def test_a_helper_that_is_not_a_known_reader_is_never_called(self):
        steps = [{"let": {"x": "=unknown()"}}, {"refuse": "no", "when": "=x"}, {"add": "X::Y"}]
        got = self.read(steps, {})
        self.assertIsNone(got["applies"])
        self.assertEqual(got["notChecked"], ["stopped before the end of the leading checks: unknown() is not a known reader"])
        self.assertEqual(self.called, [])
        # A helper that is in no list at all (the file has not heard of it), by name in a call object, or handed on by name.
        for steps in ([{"let": {"x": {"call": "unknown", "with": []}}}], [{"let": {"x": "=sorted([1], key=unknown)"}}],
                      [{"when": "=unknown()", "then": [{"refuse": "no"}]}], [{"each": "x", "in": "=unknown()", "steps": []}],
                      [{"choose": "=unknown()", "of": {}}], [{"put": {"k": "=unknown()"}, "into": "d"}]):
            self.assertIsNone(self.read(steps, {})["applies"], steps)
        self.assertEqual(self.called, [])
        # With the file gone nothing is a reader.
        self.files = _Files()
        self.assertIsNone(self.read([{"let": {"n": "=count()"}}, {"add": "X::Y"}], {})["applies"])
        self.assertEqual(self.called, [])

    def test_the_reading_ends_at_the_first_change_and_never_makes_it(self):
        made = []

        class Doc:
            def addObject(self, *a):
                made.append(a)

        self.helpers["doc"] = lambda: Doc()
        self.files = _Files(readers=("count", "find", "doc"), changers=("make",))
        late = {"refuse": "too late", "first": [{"do": "=make()"}], "when": "=True"}
        for change in ({"make": "Mod.fn"}, {"add": "X::Y"}, {"set": {"o.Label": "x"}}, {"do": "=make()"}, {"do": "=doc().recompute()"}, {"let": {"o": "=make()"}},
                       {"let": {"o": "=doc().addObject('X::Y', 'N')"}}, {"do": "=unknown()"}, {"answer": {"via": "make"}}, late,
                       {"when": "=True", "then": [{"add": "X::Y"}]}, {"try": [{"add": "X::Y"}], "except": []}):
            got = self.read([{"let": {"n": "=count()", "o": "=find('A')"}}, {"refuse": "none", "when": "=n < 0"}, change, {"refuse": "after it", "when": "=True"}], {})
            self.assertIs(got["applies"], True, change)
            self.assertEqual(got["wouldRefuse"], [])
            self.assertIn("after its first change", got["notChecked"][0])
        self.assertEqual(made, [])
        self.assertEqual(set(self.called), {"count", "find A"})

    def test_branches_loops_and_a_try(self):
        steps = [{"let": {"kind": "=a.kind", "out": "=[]", "d": "={}"}},
                 {"choose": "=kind", "of": {"a": [{"refuse": "kind a is refused."}], "b": [{"push": {"out": "=1"}}]}, "else": [{"refuse": "kind: a or b.", "when": "=kind not in KINDS"}]},
                 {"each": "x", "in": "=[1, 2, 3]", "index": "i", "steps": [{"refuse": {"fmt": "item {i} is {x}."}, "when": "=x == a.bad"}]},
                 {"try": [{"let": {"o": "=find(a.object)"}}], "on": "refusal", "except": [{"refuse": {"fmt": "object: {error.message} Say which."}, "code": "not_found"}]},
                 {"put": {"n": "=len(out)"}, "into": "d"}, {"when": "=d['n'] == 1", "then": [{"refuse": "one was pushed."}], "else": [{"refuse": "none was pushed."}]}]
        self.assertEqual(self.read(steps, {"kind": "a"})["wouldRefuse"][0]["words"], "kind a is refused.")
        self.assertEqual(self.read(steps, {"kind": "c"})["wouldRefuse"][0]["words"], "kind: a or b.")
        self.assertEqual(self.read(steps, {"kind": "b", "bad": 2})["wouldRefuse"][0]["words"], "item 1 is 2.")
        self.assertEqual(self.read(steps, {"kind": "b", "object": "Z"})["wouldRefuse"], [{"code": "not_found", "words": "object: Z: not here. Say which."}])
        self.assertEqual(self.read(steps, {"kind": "b", "object": "A"})["wouldRefuse"][0]["words"], "one was pushed.")
        # Without the arguments none of it can be told, and nothing is called with a guess.
        del self.called[:]
        got = self.read(steps)
        self.assertIsNone(got["applies"])
        self.assertEqual(self.called, [])

    def test_a_step_that_raises_is_not_a_refusal(self):
        got = self.read([{"let": {"x": "=[][3]"}}, {"add": "X::Y"}], {})
        self.assertIsNone(got["applies"])
        self.assertIn("a leading step raised IndexError", got["notChecked"][0])

    def test_methods_are_taken_by_the_list_and_on_python_values_only(self):
        class Sketch:
            def __init__(self):
                self.did = []

            def split(self, *a):
                self.did.append(a)

            def lower(self):
                self.did.append("lower")

            def isNull(self):
                return False

        sk = Sketch()
        self.helpers["sk"] = lambda: sk
        self.files = _Files(readers=("sk",))
        self.assertIs(self.read([{"refuse": "no", "when": "='A.b'.lower().split('.')[0] != 'a'"}, {"refuse": "null", "when": "=sk().isNull()"}], {})["applies"], True)
        got = self.read([{"let": {"x": "=sk().split(4, 5)"}}, {"refuse": "after"}], {})  # a sketch's split: the change, and nothing before it to read
        self.assertEqual(got["notChecked"], ["no leading check to read: this tool's checks are inside its helpers, or come after its first change (1 of them)"])
        self.assertIs(self.read([{"refuse": "no", "when": "=False"}, {"let": {"x": "=sk().split(4, 5)"}}, {"refuse": "after"}], {})["applies"], True)
        got = self.read([{"let": {"x": "=sk().lower()"}}], {})  # a string's method on what is not one
        self.assertEqual(got["notChecked"], ["stopped before the end of the leading checks: .lower() of a Sketch is not a known reading"])
        got = self.read([{"let": {"x": "=sk().split('x')"}}], {})
        self.assertIsNone(got["applies"])
        self.assertIsNone(self.read([{"let": {"x": "=sk().explode()"}}, {"refuse": "after"}], {})["applies"])  # a method in no list
        self.assertEqual(sk.did, [])

    def test_maker_imports_nothing(self):
        steps = [{"refuse": "No such maker here.", "code": "unavailable", "when": "=maker('no_such_module_zz.make') is None"}, {"add": "X::Y"}]
        got = self.read(steps, {})
        self.assertEqual(got["notChecked"], ["stopped before the end of the leading checks: the module no_such_module_zz is not loaded yet"])
        self.assertNotIn("no_such_module_zz", sys.modules)
        self.assertEqual(self.read([{"refuse": "No dumps.", "when": "=maker('json.dumps') is None"}, {"refuse": "No such.", "when": "=maker('json.nope') is None"}], {})
                         ["wouldRefuse"][0]["words"], "No such.")

    def test_what_is_not_a_steps_entry_is_not_checked(self):
        self.assertEqual(needs.reading("x", None, None)["notChecked"], ["not a data tool: its checks are in its code"])
        self.assertIsNone(needs.reading("x", {"runner": "make", "group": "t"}, {})["applies"])
        self.assertIsNone(needs.reading("x", _entry([]), {}, ["not", "an", "object"])["applies"])

    def test_a_reading_stops_when_its_time_is_up(self):
        with self.files:
            got = needs.reading("t_tool", _entry([{"each": "x", "in": "=range(100000)", "steps": [{"refuse": "no", "when": "=x < 0"}]}]), self.helpers, {}, budget=0.02)
        self.assertEqual(got["notChecked"], ["stopped before the end of the leading checks: the reading ran out of time"])

    def test_the_runner_puts_the_step_on_a_refusal(self):
        e = _entry([{"let": {"n": "=count()"}}, {"when": "=True", "then": [{"refuse": "inner", "when": "=n == 0"}]}], description="d" * 30, inputSchema={}, changes=True)
        t = runners.tool("t_tool", e, self.helpers)
        self.assertIs(t.entry, e)
        self.assertIs(t.helpers, self.helpers)
        with self.assertRaises(ToolError) as c:
            t.fn({})
        self.assertIs(c.exception.step, e["steps"][1]["then"][0])  # the innermost
        self.assertEqual(runners.REFUSED[0], ("t_tool", e["steps"][1]["then"][0]))


class Census(unittest.TestCase):
    """How the entries stand, from tools.json and readers.json alone: the
    numbers docs/data-tools.md gives."""

    def test_totals(self):
        c = needs.census()
        total = {}
        for row in c.values():
            for k, v in row.items():
                total[k] = total.get(k, 0) + v
        self.assertEqual(total, TOTAL)
        self.assertEqual(total["blocked"] + total["needsArguments"] + total["complete"], total["steps"])

    def test_every_leading_step_is_found_once(self):
        for name, e in runners.entries().items():
            if e.get("runner") != "steps":
                continue
            lead = needs.leading(e)
            first = e["steps"][0] if e["steps"] else None
            if first is not None and needs.kind(first, needs.family_of(e)) != "change":
                self.assertIn(id(first), lead, name)
            self.assertGreaterEqual(needs.later_refusals(e), 0, name)


TOTAL = {"tools": 383, "steps": 370, "leadingRefusals": 772, "noArgument": 38, "blocked": 112, "needsArguments": 194, "complete": 64, "noCheck": 55}


class Agreement(unittest.TestCase):
    """Every case of the stand-in suites: the reading, then the tool."""

    def test_false_is_the_calls_own_refusal_and_true_is_never_refused_before_a_change(self):
        for suite in SUITES:
            if suite in NUMPY and not _numpy():
                continue  # these stand-ins are built on the mesh one, which stands on numpy (as their own tests do)
            got = _child("--agree", suite)
            self.assertEqual(got["wrong"], [], suite)
            self.assertEqual(got["changedByReading"], [], suite)
            # How many cases could be told with their arguments: a change to the readers that tells fewer shows here.
            self.assertGreaterEqual(got["withArguments"].get("false", 0), AT_LEAST[suite][0], suite)
            self.assertGreaterEqual(got["withArguments"].get("true", 0), AT_LEAST[suite][1], suite)
            # Without the arguments a reading of "not" is still the call's refusal: never a tool that then answered.
            self.assertEqual(got["notThenAnswered"], [], suite)


class Filter(unittest.TestCase):
    """The set, the line, the full reading, the meter: on three states of
    the Part Design stand-in."""

    def test_links_from_the_index(self):
        entries = {"sketch_new": {"workbench": "SketcherWorkbench", "commands": ["Sketcher_NewSketch"]},
                   "sketch_add": {"workbench": "SketcherWorkbench", "commands": ["Sketcher_CreateLine", "Std_New"]},
                   "pd_pad": {"workbench": "PartDesignWorkbench", "commands": ["PartDesign_Pad"]},
                   "pd_sketch": {"workbench": "PartDesignWorkbench", "commands": ["Sketcher_NewSketch", "PartDesign_NewSketch"]},
                   "mesh_x": {"workbench": "MeshWorkbench", "commands": ["Mesh_X"]}, "doc_new": {"workbench": None, "commands": ["Std_New"]}}
        self.assertEqual(appliesnow.links(entries), {"PartDesignWorkbench": ["SketcherWorkbench"], "SketcherWorkbench": ["PartDesignWorkbench"]})
        from agentlink import toolindex

        real = appliesnow.links({k: toolindex.clean(v) or {} for k, v in toolindex.load().items()})
        self.assertIn("PartDesignWorkbench", real["SketcherWorkbench"])
        self.assertLessEqual(max(len(v) for v in real.values()), 4)  # the set stays small

    def test_three_states(self):
        got = _child("--states")
        for name in ("empty", "sketch", "pad"):
            st = got[name]
            self.assertEqual(st["changedByReading"], False, name)
            self.assertLessEqual(st["lineTokens"], BOUNDS["line"], name)
            self.assertLessEqual(st["fullTokens"], BOUNDS["full"], name)
            self.assertEqual(set(st["line"] or {"groups", "not", "notChecked", "ms"}) - {"partial"}, {"groups", "not", "notChecked", "ms"}, name)
        self.assertIsNone(got["empty"]["line"])  # no workbench, no object: no tool is chosen, nothing is said
        self.assertEqual(got["sketch"]["how"], {"workbench": "SketcherWorkbench", "linked": ["PartDesignWorkbench"]})
        self.assertEqual(got["pad"]["how"], {"document": ["PartDesignWorkbench", "SketcherWorkbench"]})
        self.assertEqual(got["classes"], CLASSES)

    def test_a_state_the_filter_tells(self):
        """The strength tools on the FEM stand-in: before fea_setup most of
        them refuse by their first check, and the reading says so in the
        entry's own words; after it that check passes."""
        got = _child("--fem")
        self.assertEqual(got["before"]["line"], {"groups": {"strength": 1}, "not": 11, "notChecked": 7})
        self.assertEqual(got["before"]["hold"], {"tool": "fea_hold", "applies": False, "notChecked": [],
                                                 "wouldRefuse": [{"code": "invalid_state", "words": "No strength study: fea_setup { body } first."}]})
        self.assertEqual(got["before"]["call"], ["invalid_state", "No strength study: fea_setup { body } first."])  # the call's own refusal, word for word
        self.assertEqual(got["before"]["full"]["more"], {"not": 11 - appliesnow.NOT_CAP})
        self.assertLessEqual(tokens(got["before"]["full"]), BOUNDS["full"])
        self.assertLess(got["after"]["line"]["not"], 11)
        self.assertGreater(got["after"]["line"]["groups"]["strength"], 1)
        self.assertIs(got["after"]["hold"]["applies"], True)
        self.assertEqual(got["changedByReading"], False)

    def test_the_line_is_pushed_once_and_measured(self):
        got = _child("--states")["server"]
        self.assertEqual(got["first"]["health"]["appliesNow"].keys() - {"ms"}, {"groups", "not", "notChecked"})
        self.assertNotIn("appliesNow", got["second"].get("health", {}))  # not said again while it is as it was
        self.assertNotIn("appliesNow", json.dumps(got["off"]))  # the switch
        self.assertEqual(got["refusedOutcome"], "refusedLeading")
        self.assertEqual(got["laterOutcome"], "refusedLater")
        m = got["meter"]
        self.assertEqual(m["notThenAnswered"], {})
        self.assertEqual(m["calls"], got["calls"])
        self.assertTrue(got["file"]["sessions"])
        self.assertEqual(list(got["file"]["sessions"].values())[0]["calls"], got["calls"])
        self.assertEqual(got["parts"], ["appliesMeter", "appliesNow"])

    def test_through_the_hubs_own_server(self):
        """tool_groups, batch and usage_report as build_server makes them,
        on three tools made for the purpose (FreeCAD's modules are stand-in
        objects: only the hub's own code is run)."""
        got = _child("--hub")
        self.assertEqual(got["needs"], {"tool": "fea_hold", "applies": False, "notChecked": [], "ms": got["needs"]["ms"],
                                        "wouldRefuse": [{"code": "invalid_state", "words": "No strength study: fea_setup { body } first."}],
                                        "note": "Read from the tool's own leading checks, not run: advice — the call itself is the authority."})
        self.assertLessEqual(tokens(got["needs"]), BOUNDS["needsReply"])
        self.assertIsNone(got["needsBare"]["applies"])  # fea_setup finds what its argument names
        self.assertEqual(got["needsArgs"]["wouldRefuse"], [{"code": "not_found", "words": "B: not here."}])
        self.assertIs(got["needsOk"]["applies"], True)
        self.assertEqual(got["needsBad"]["wouldRefuse"][0]["code"], "invalid_input")  # the tool's own schema
        self.assertEqual(got["needsMissing"]["error"]["code"], "not_found")
        self.assertEqual(got["argsAlone"]["error"]["code"], "invalid_input")
        self.assertFalse(got["study"])  # no reading made the study
        # find: nothing dropped; those that would be refused now after the rest, and marked.
        self.assertEqual([(t["tool"], t.get("applies")) for t in got["find"]["tools"] if t["tool"].startswith("fea_")],
                         [("fea_setup", None), ("fea_hold", False), ("fea_solve", False)])
        self.assertEqual(got["find"]["count"], len(got["find"]["tools"]))
        last = [t.get("applies") is False for t in got["find"]["tools"]]
        self.assertEqual(last, sorted(last))
        now = got["now"]["appliesNow"]
        self.assertEqual(now["chosen"], {"workbench": "FemWorkbench"})
        self.assertEqual([x["tool"] for x in now["not"]], ["fea_hold", "fea_solve"])
        self.assertEqual(now["notChecked"], {"count": 1, "tools": ["fea_setup"]})
        self.assertLessEqual(tokens(got["now"]), BOUNDS["nowReply"])
        # The call itself: refused in the reading's words; then a batch, whose answer carries the one line.
        self.assertEqual(got["refused"]["error"], {"code": "invalid_state", "message": "No strength study: fea_setup { body } first."})
        b = got["batch"]
        self.assertEqual(b["appliesNow"].keys() - {"ms"}, {"groups", "not", "notChecked"})
        self.assertEqual(b["appliesNow"]["groups"], {"strength": 1})
        self.assertNotIn("appliesNow", json.dumps(b["results"]))
        self.assertNotIn("appliesNow", json.dumps(got["again"]))  # as it was: not said again
        m = got["usage"]["appliesNow"]
        self.assertEqual(m["notThenAnswered"], {"count": 0, "tools": []})
        self.assertEqual(m["stale"], 1)  # fea_solve inside the batch: read as "not" before fea_setup ran, and not held against the filter
        self.assertEqual(m["byReading"]["not"], {"answered": 1, "refusedLeading": 1})
        self.assertEqual(got["file"]["notRefusedByTheSameCheck"], 1)
        self.assertLessEqual(tokens(m), BOUNDS["report"])
        self.assertEqual(got["listed"], got["listedBefore"])  # tools/list is as it was

    def test_the_meter_counts(self):
        class S:
            pass

        s = S()
        s.server = None
        m = appliesnow.Meter("one")
        s._applies_seq = 3
        s._applies = {"seq": 3, "by": {"a": "applies", "n": "not", "u": "notChecked"}, "steps": {}}
        for name, refused in (("a", False), ("n", True), ("u", False), ("zz", False), ("n", False)):
            m.note(s, name, refused, appliesnow.before_call(s))
        s._applies_seq = 4  # a change the reading has not seen: what it said is stale, and not held against it
        m.note(s, "n", False, appliesnow.before_call(s))
        t = m.totals()
        self.assertEqual(t["calls"], 6)
        self.assertEqual(t["notThenAnswered"], {"n": 1})
        self.assertEqual(t["stale"], 1)
        self.assertEqual(t["coverage"], round(4 / 6, 3))
        self.assertEqual(t["byReading"]["notEvaluated"], {"answered": 1})
        r = m.report()
        self.assertEqual(r["notThenAnswered"], {"count": 1, "tools": ["n"]})
        self.assertLessEqual(tokens(r), BOUNDS["report"])
        d = tempfile.mkdtemp()
        other = appliesnow.Meter("two")
        other.note(s, "a", False)
        self.assertTrue(other.write(d))
        self.assertTrue(m.write(d))
        with open(os.path.join(d, appliesnow.FILE), encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(sorted(doc["sessions"]), ["one", "two"])  # another session's counts are kept
        self.assertEqual(doc["sessions"]["one"]["notThenAnswered"], {"n": 1})
        self.assertEqual([n for n in os.listdir(d) if n.endswith(".tmp")], [])


# Upper bounds, in tokens at 3.5 characters each: a later change cannot bloat these without saying so here.
# explore/full-ste: every description in ASD-STE100 measures 92 801 for everything (data and coded tools),
# over main's 90 000; the bound is raised to 93 000 on this branch only. The others still hold unchanged.
BOUNDS = {"line": 45, "full": 800, "report": 260, "needsReply": 260, "nowReply": 1500, "oneCard": 900, "leanListing": 7450, "everything": 93000, "toolGroupsCard": 740}
# The three states, without arguments: every Part Design and Sketcher tool begins by finding the body or the sketch its
# arguments name, so none of the 32 can be told before a call (they are told with arguments: Agreement). The filter
# has something to say where a tool's first check is of the document alone: test_a_state_the_filter_tells.
CLASSES = {"empty": {"chosen": 0}, "sketch": {"chosen": 32, "notChecked": 32}, "pad": {"chosen": 32, "notChecked": 32}}


class Tokens(unittest.TestCase):
    """What the pieces cost, at 3.5 characters a token (docs/data-tools.md
    has the table). The data tools' definitions are counted exactly from
    tools.json; a tool written in code is counted from its source (the
    text of its description and of its schema as written), which is a
    close estimate of what tools/list sends."""

    def setUp(self):
        with open(os.path.join(runners.DATA, "tools.json"), encoding="utf-8") as f:
            self.entries = json.load(f)["entries"]

    def card(self, name):
        e = self.entries[name]
        return {"name": name, "description": e["description"], "inputSchema": e["inputSchema"]}

    def coded(self):
        """{name: characters} of the tools written in code (Tool("name", description, schema, …))."""
        import ast

        out = {}
        pkg = os.path.join(ROOT, "agentlink")
        for path in [os.path.join(pkg, "tools.py")] + sorted(os.path.join(pkg, "families", n) for n in os.listdir(os.path.join(pkg, "families")) if n.endswith(".py")):
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for n in ast.walk(tree):
                f = getattr(n, "func", None)
                if isinstance(n, ast.Call) and (getattr(f, "id", None) == "Tool" or getattr(f, "attr", None) == "Tool") and len(n.args) >= 3 \
                        and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                    words = "".join(c.value for c in ast.walk(n.args[1]) if isinstance(c, ast.Constant) and isinstance(c.value, str))
                    out[n.args[0].value] = len(n.args[0].value) + len(words) + len(ast.unparse(n.args[2])) + 40
        return out

    def test_the_costs(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import tool_summary

        coded = self.coded()
        data = {n: tokens(self.card(n)) for n in self.entries}
        lean = [n for g in tool_summary.groups().values() if g["lean"] for n in g["tools"]]
        self.assertEqual([n for n in lean if n not in data and n not in coded], [])
        cards = sorted(data.values())
        got = {"dataTools": len(data), "dataToolsTokens": sum(data.values()), "codedTools": len(coded), "codedToolsTokens": int(round(sum(coded.values()) / CHARS_PER_TOKEN)),
               "leanTools": len(lean), "leanListingTokens": sum(data[n] if n in data else int(round(coded[n] / CHARS_PER_TOKEN)) for n in lean),
               "oneCardMedian": cards[len(cards) // 2], "oneCardLargest": cards[-1], "toolGroupsCard": int(round(coded["tool_groups"] / CHARS_PER_TOKEN)),
               "usageReportCard": int(round(coded["usage_report"] / CHARS_PER_TOKEN))}
        self.assertEqual(got, COSTS)
        self.assertLessEqual(got["dataToolsTokens"] + got["codedToolsTokens"], BOUNDS["everything"])
        self.assertLessEqual(got["leanListingTokens"], BOUNDS["leanListing"])
        self.assertLessEqual(got["oneCardLargest"], BOUNDS["oneCard"])
        self.assertLessEqual(got["toolGroupsCard"], BOUNDS["toolGroupsCard"])

    def test_the_pushed_line_and_the_replies_at_their_largest(self):
        # The pushed line: six groups applying (the pushed set holds no more), three digits each, cut short.
        line = {"groups": {g: 100 for g in ("feature", "sketch", "model", "techdraw", "assembly", "sheet")}, "not": 100, "notChecked": 100, "ms": 150, "partial": 100}
        self.assertLessEqual(tokens({"appliesNow": line}), BOUNDS["line"])
        # One reading as tool_groups { needs } answers it, at the longest words a reading gives.
        reply = {"tool": "x" * 24, "applies": False, "wouldRefuse": [{"code": "invalid_state", "words": "w" * needs.MAX_WORDS}], "notChecked": [],
                 "note": "Read from the tool's own leading checks, not run: advice — the call itself is the authority."}
        self.assertLessEqual(tokens(reply), BOUNDS["needsReply"])
        # The full reading with every class at its cap and every name long.
        class T:
            def __init__(self, group):
                self.group = group

        class Srv:
            tools = {f"{k}_tool_with_a_long_name_{i:03d}": T(f"group{i % 6}") for k in ("a", "n", "u") for i in range(appliesnow.MAX_SET // 3)}

        by = {n: {"a": "applies", "n": "not", "u": "notChecked"}[n[0]] for n in Srv.tools}
        r = {"by": by, "why": {n: {"code": "invalid_state", "words": "w" * needs.MAX_WORDS} for n in by if n[0] == "n"}, "ms": 600, "left": 99,
             "how": {"workbench": "PartDesignWorkbench", "editing": "sketch", "linked": ["SketcherWorkbench", "PartWorkbench"], "document": ["TechDrawWorkbench", "MeshWorkbench"], "cut": 99}}
        full = appliesnow.full_of(r, Srv)
        self.assertEqual(sum(len(v) for v in full["applies"].values()), appliesnow.CAP)
        self.assertEqual(len(full["not"]), appliesnow.NOT_CAP)
        self.assertEqual(full["more"], {"applies": 50 - appliesnow.CAP, "not": 50 - appliesnow.NOT_CAP, "notChecked": 50 - appliesnow.CAP})  # nothing is dropped unsaid
        self.assertLessEqual(tokens(full), BOUNDS["full"])
        self.assertLessEqual(tokens({"appliesNow": appliesnow.line(r, Srv)}), BOUNDS["line"])


def _walk(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from _walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from _walk(v)


# Measured (tokens): the 383 data tools' definitions; the 21 Tool(…) written in code; the lean listing (core and
# view: what a session loads at its start); one data tool's card; tool_groups' and usage_report's own cards (586 and
# 150 before needs, arguments and the meter's clause were added: the lean listing grew by 154; report_read's clause on known faults added 16).
# The token pass (docs/hardening/tokens-findings.md) added 216 to the lean listing: batch's read/at, lines "full" and the
# file batch's record reply (+168), tool_groups' said (+22), guide_read's index wording (+26).
# explore/full-ste (every description in ASD-STE100): data 79008 -> 83635, coded 9037 -> 9166, lean listing 7406 -> 7409,
# one card's median 178 -> 190 and largest 824 -> 878, tool_groups' card 734 -> 729, usage_report's 178 -> 194.
COSTS = {"dataTools": 383, "dataToolsTokens": 83685, "codedTools": 22, "codedToolsTokens": 9166, "leanTools": 20, "leanListingTokens": 7409,
         "oneCardMedian": 190, "oneCardLargest": 878, "toolGroupsCard": 729, "usageReportCard": 194}


try:
    import FreeCAD  # noqa: F401

    HAVE = True
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class Live(unittest.TestCase):
    """tool_groups { needs }, { now } and { find } through the real server."""

    def setUp(self):
        from _fc import caller, server

        self.session, self.srv = server()
        self.call = caller(self.srv)
        self.call("doc_new", {"name": "Needs"})

    def ok(self, n, a=None):
        err, out = self.call(n, a)
        self.assertFalse(err, f"{n}: {out}")
        return out

    def test_needs(self):
        before = len(self.session.doc.Objects)
        got = self.ok("tool_groups", {"needs": "fea_hold"})
        self.assertIs(got["applies"], False)
        self.assertEqual(got["wouldRefuse"][0]["code"], "invalid_state")
        self.assertIn("fea_setup", got["wouldRefuse"][0]["words"])
        got = self.ok("tool_groups", {"needs": "pd_pad"})
        self.assertIsNone(got["applies"])
        got = self.ok("tool_groups", {"needs": "pd_pad", "arguments": {"length": 5}})
        self.assertIs(got["applies"], False)  # no body: the call's own words
        err, real = self.call("pd_pad", {"length": 5})
        self.assertTrue(err)
        self.assertEqual(got["wouldRefuse"][0], {"code": real["error"]["code"], "words": real["error"]["message"][:needs.MAX_WORDS]})
        self.assertIs(self.ok("tool_groups", {"needs": "pd_pad", "arguments": {"nope": 1}})["applies"], False)
        self.assertEqual(len(self.session.doc.Objects), before)
        self.assertLessEqual(tokens(got), BOUNDS["needsReply"])
        err, out = self.call("tool_groups", {"needs": "pd_padd"})
        self.assertTrue(err)
        self.assertEqual(out["error"]["code"], "not_found")

    def test_now_and_find(self):
        self.ok("pd_body_new", {"name": "Bracket"})
        out = self.ok("sketch_new", {"plane": "XY", "name": "Base"})
        self.assertIn("health", out)
        got = self.ok("tool_groups", {"now": True})
        self.assertIn("appliesNow", got)
        self.assertLessEqual(tokens(got["appliesNow"]), BOUNDS["full"])
        self.assertEqual(set(got["appliesNow"]) - {"more", "partial"}, {"chosen", "tools", "applies", "not", "notChecked", "ms", "note"})
        self.assertLessEqual(tokens(got), BOUNDS["nowReply"])
        hits = self.ok("tool_groups", {"find": "strength hold load", "limit": 10})["tools"]
        flags = [t.get("applies") for t in hits]
        self.assertEqual(flags, sorted(flags, key=lambda f: f is False))  # those that would be refused now come last
        self.assertIn("appliesNow", self.ok("usage_report", {"session": True}))
        self.assertEqual(self.ok("usage_report", {"session": True})["appliesNow"]["notThenAnswered"]["count"], 0)


# ---- the child: a stand-in FreeCAD ---------------------------------------------------------------

def _snap(v, depth=0):
    """A value as far as a change would show (an object's own attributes, lists, numbers and text)."""
    if isinstance(v, (str, int, float, bool, type(None))):
        return v
    if isinstance(v, (list, tuple)):
        return [_snap(x, depth + 1) for x in v[:200]] if depth < 4 else len(v)
    if isinstance(v, dict):
        return {str(k): _snap(x, depth + 1) for k, x in list(v.items())[:200]} if depth < 4 else len(v)
    name = getattr(v, "Name", None)
    if isinstance(name, str) and depth:
        return f"<{name}>"
    d = getattr(v, "__dict__", None)
    if isinstance(d, dict) and depth < 3:
        return {k: _snap(x, depth + 1) for k, x in d.items() if not callable(x)}
    return type(v).__name__


def _doc_snap(session):
    for o in session.doc.Objects:
        getattr(o, "Placement", None)  # a stand-in makes an object's placement when it is first read: read before, not a change
    return json.dumps([_snap(o) for o in session.doc.Objects], sort_keys=True, default=repr)


def _agree(suite):
    import importlib

    standin, casesmod, files = SUITES[suite]
    fc = importlib.import_module(standin).install()
    if hasattr(fc, "patch"):
        fc.patch()
    cm = importlib.import_module(casesmod)
    files = files or cm.FILES
    mods = {m: importlib.import_module(f"agentlink.families.{m}") for m in files}
    # The tool's own run, watched: whether a step that changes had begun before it refused.
    flag = {"changed": False, "family": None}
    real = runners._step

    def watched(st, env, helpers):
        if needs.kind(st, flag["family"]) == "change" and not list(needs._lists(st)) and not ("when" in st and not runners.value(st["when"], env, helpers)):
            flag["changed"] = True
        return real(st, env, helpers)

    runners._step = watched
    out = {"wrong": [], "changedByReading": [], "notThenAnswered": [], "withArguments": {}, "withoutArguments": {}, "cases": 0}
    for tool, case, prepare, args in cm.cases(fc, tempfile.mkdtemp()):
        fc.state["flags"] = {}
        s = fc.Session(tempfile.mkdtemp())
        prepare(s)
        t = next((x for m in mods.values() for x in m.tools(s) if x.name == tool and getattr(x, "entry", None) is not None), None)
        if t is None or t.entry.get("runner") != "steps":
            continue
        out["cases"] += 1
        before = _doc_snap(s)
        bare = needs.of_tool(t, None)
        full = needs.of_tool(t, json.loads(json.dumps(args)))
        if _doc_snap(s) != before:
            out["changedByReading"].append(f"{tool} {case}")
        flag["changed"], flag["family"] = False, needs.family_of(t.entry)
        try:
            t.fn(json.loads(json.dumps(args)))
            res = ("ok",)
        except ToolError as e:
            res = ("refused", e.code, str(e.message)[:needs.MAX_WORDS], flag["changed"], getattr(e, "step", None) is not None)
        except Exception as e:  # noqa: BLE001 - a case that crashes on purpose
            res = ("crashed", type(e).__name__)
        for key, r in (("withArguments", full), ("withoutArguments", bare)):
            k = {True: "true", False: "false", None: "null"}[r["applies"]]
            out[key][k] = out[key].get(k, 0) + 1
        if full["applies"] is False and (res[0] != "refused" or [res[1], res[2]] != [full["wouldRefuse"][0]["code"], full["wouldRefuse"][0]["words"]]):
            out["wrong"].append(f"{tool} {case}: read {full['wouldRefuse']}, the call {res}")
        if full["applies"] is True and res[0] == "refused" and not res[3] and res[4]:
            out["wrong"].append(f"{tool} {case}: read as applying, refused before any change: {res}")
        if bare["applies"] is False and res[0] != "refused":
            out["notThenAnswered"].append(f"{tool} {case}")
    print(json.dumps(out))


def _states():
    import importlib

    import _datapd_standin

    fc = _datapd_standin.install()
    fc.patch()
    from agentlink import around, protocol

    def server(s):
        tools = [t for m in ("feature", "sketch", "std_more") for t in importlib.import_module(f"agentlink.families.{m}").tools(s)]
        srv = protocol.Server("standin", "0", tools, "")
        srv.session, s.server = s, srv
        return srv

    def empty(s):
        return {"window": False, "docBenches": set()}

    def sketch(s):
        b = fc.body(s)
        fc.sketch(s, b, "Sketch", dof=2)
        return {"window": True, "workbench": "SketcherWorkbench", "editing": "sketch", "docBenches": {"PartDesignWorkbench", "SketcherWorkbench"}}

    def pad(s):
        b = fc.body(s)
        sk = fc.sketch(s, b)
        fc.feature(s, b, "Pad", Profile=sk)
        fc.settle(s)
        return {"window": False, "docBenches": {"PartDesignWorkbench", "SketcherWorkbench"}}

    out, classes = {}, {}
    for name, prepare in (("empty", empty), ("sketch", sketch), ("pad", pad)):
        s = fc.Session(tempfile.mkdtemp())
        state = prepare(s)
        srv = server(s)
        before = _doc_snap(s)
        r = appliesnow.take(s, state=state)
        line = appliesnow.line(r, srv)
        full = appliesnow.full(s, state)
        count = {}
        for k in r["by"].values():
            count[k] = count.get(k, 0) + 1
        classes[name] = {"chosen": len(r["by"]), **count}
        out[name] = {"line": line, "how": r["how"], "lineTokens": tokens({"appliesNow": line}) if line else 0, "fullTokens": tokens(full), "full": full,
                     "changedByReading": _doc_snap(s) != before}
    out["classes"] = classes

    # The line pushed after a changing call, and the meter, through the server's own call.
    from agentlink import usage

    s = fc.Session(tempfile.mkdtemp())
    s.by, s.tx = "agent", 0
    b = fc.body(s)
    fc.sketch(s, b, "Sketch")
    fc.settle(s)
    srv = server(s)
    srv.meter = usage.Meter(where=tempfile.mkdtemp(), write=False)
    state = {"window": False, "docBenches": {"PartDesignWorkbench", "SketcherWorkbench"}}
    real_take = appliesnow.take
    appliesnow.take = lambda session, budget=None, state_=None, names=None: real_take(session, budget, state, names)

    def call(name, args):
        around.start()
        r = srv.call({"name": name, "arguments": args})
        parts = around.take()
        return json.loads(r["content"][0]["text"]), bool(r.get("isError")), parts

    calls, parts = 0, set()
    first, _e, p = call("pd_pad", {"sketch": "Sketch", "length": 5})
    parts |= {k for k in p if k.startswith("applies")}
    second, _e, _p = call("pd_pad", {"sketch": "Sketch", "length": 6})
    calls += 2
    m = appliesnow.meter_of(s)
    refused, err, _p = call("pd_pad", {"sketch": "Sketch", "length": 5, "type": "through_all"})
    calls += 1
    lead = {o: n for o, n in m.counts["notChecked"].items() if n}
    refused_outcome = "refusedLeading" if err and m.counts["notChecked"]["refusedLeading"] == 1 else f"{refused} {lead}"
    fc.state["flags"] = {"effect": {"Pad": 0.0}}  # the pad adds nothing: refused after it was made
    later, err, _p = call("pd_pad", {"sketch": "Sketch", "length": 5})
    fc.state["flags"] = {}
    calls += 1
    later_outcome = "refusedLater" if err and m.counts["notChecked"]["refusedLater"] == 1 else f"{later} { {o: n for o, n in m.counts['notChecked'].items() if n} }"
    os.environ["AGENTLINK_APPLIES"] = "off"
    s._applies_said = None
    off, _e, _p = call("pd_pad", {"sketch": "Sketch", "length": 7})
    calls += 1
    del os.environ["AGENTLINK_APPLIES"]
    with open(os.path.join(s.out_dir, appliesnow.FILE), encoding="utf-8") as f:
        file = json.load(f)
    out["server"] = {"first": first, "second": second, "off": off, "refusedOutcome": refused_outcome, "laterOutcome": later_outcome, "meter": m.totals(), "calls": calls,
                     "file": file, "parts": sorted(parts)}
    print(json.dumps(out, default=repr))


def _fem():
    import importlib

    import _datafem_standin

    fc = _datafem_standin.install()
    from agentlink import protocol

    fc.fc.GuiUp = False
    s = fc.Session(tempfile.mkdtemp())
    fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10)), ShapeMaterial=None)
    tools = [t for m in ("material", "fem_more", "strength") for t in importlib.import_module(f"agentlink.families.{m}").tools(s)]
    srv = protocol.Server("standin", "0", tools, "")
    srv.session, s.server = s, srv
    state = {"window": True, "workbench": "FemWorkbench", "docBenches": set()}

    def look():
        r = appliesnow.take(s, state=state)
        line = appliesnow.line(r, srv)
        line.pop("ms")
        return {"line": line, "hold": needs.public(needs.of_tool(srv.tools["fea_hold"])), "full": appliesnow.full_of(r, srv)}

    snap = _doc_snap(s)
    before = look()
    changed = _doc_snap(s) != snap
    try:
        srv.tools["fea_hold"].fn({"faces": [{"normal": [0, 0, -1]}]})
    except ToolError as e:
        before["call"] = [e.code, e.message]
    srv.tools["fea_setup"].fn({})
    print(json.dumps({"before": before, "after": look(), "changedByReading": changed}, default=repr))


def _hub():
    import types
    from unittest import mock

    fc = mock.MagicMock()
    fc.GuiUp = False
    grp = mock.MagicMock()
    for k in ("GetInt", "GetBool", "GetFloat", "GetString", "GetUnsigned"):
        getattr(grp, k).side_effect = lambda name, default=None: default
    fc.ParamGet.return_value = grp
    sys.modules["FreeCAD"] = fc
    for m in ("Part", "FreeCADGui", "Mesh"):
        sys.modules[m] = mock.MagicMock()
    os.environ["HOME"] = tempfile.mkdtemp()  # the usage meter's own folder
    from agentlink import families, toolindex, tools

    state = {"study": False}

    def find(ref):
        if ref != "A":
            raise ToolError("not_found", f"{ref}: not here.")
        return ref

    def make(o):
        state["study"] = True
        return o

    helpers = {"study": lambda: state["study"], "find": find, "make": make}

    def entry(what, steps):
        return {"group": "strength", "runner": "steps", "description": f"A tool made for the hub's own test: it {what} the strength study.", "changes": True, "source": "test",
                "date": "2026-11-16", "inputSchema": {"type": "object", "properties": {"object": {"type": "string"}}, "additionalProperties": False}, "steps": steps,
                "answer": {"fields": {"ok": True}}}

    no_study = {"refuse": "No strength study: fea_setup { body } first.", "code": "invalid_state", "when": "=not study()"}
    data = {"fea_setup": entry("sets up", [{"let": {"o": "=find(a.object)"}}, {"do": "=make(o)"}]),
            "fea_hold": entry("holds a face of", [no_study, {"let": {"o": "=find(a.object)"}}, {"do": "=make(o)"}]),
            "fea_solve": entry("solves", [no_study, {"do": "=make(1)"}])}
    fam = types.SimpleNamespace(GROUP="strength", INFO="Strength.", EXTERNAL=False, __name__="strength", tools=lambda s: runners.tools("strength", s, helpers, data=data))
    families.load = lambda: [fam]
    needs._cache["file"] = {"entries": {"strength": {"readers": ["study", "find"], "changers": ["make"]}, "methods": {}}}
    for n in data:
        toolindex.declare(n, {"workbench": "FemWorkbench", "commands": ["FEM_Analysis"]})
    tools.now_state = lambda doc, commands=(): {"window": True, "workbench": "FemWorkbench", "editing": None, "selected": 0, "selBenches": set(), "selSubs": set(),
                                                 "docBenches": set(), "active": {}}
    doc = mock.MagicMock()
    doc.Objects, doc.Name, doc.UndoCount = [], "Doc", 0

    class Session(tools.Session):
        def execute(self, tool, fn):
            return fn()

    s = Session(doc=doc, out_dir=tempfile.mkdtemp())
    srv = tools.build_server(s, lean=True)

    def call(name, args=None):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})["result"]
        return json.loads(r["content"][0]["text"])

    def listed():
        return sorted(t["name"] for t in srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"])

    out = {"listedBefore": listed()}
    out["needs"] = call("tool_groups", {"needs": "fea_hold"})
    out["needsBare"] = call("tool_groups", {"needs": "fea_setup"})
    out["needsArgs"] = call("tool_groups", {"needs": "fea_setup", "arguments": {"object": "B"}})
    out["needsOk"] = call("tool_groups", {"needs": "fea_setup", "arguments": {"object": "A"}})
    out["needsBad"] = call("tool_groups", {"needs": "fea_setup", "arguments": {"nope": 1}})
    out["needsMissing"] = call("tool_groups", {"needs": "fea_holdd"})
    out["argsAlone"] = call("tool_groups", {"arguments": {}})
    out["find"] = call("tool_groups", {"find": "strength study", "limit": 40})
    out["now"] = call("tool_groups", {"now": True})
    out["study"] = state["study"]
    out["refused"] = call("fea_hold", {"object": "A"})
    out["batch"] = call("batch", {"calls": [{"tool": "fea_setup", "arguments": {"object": "A"}}, {"tool": "fea_solve", "arguments": {}}], "rollback": False})
    out["again"] = call("fea_hold", {"object": "A"})
    out["usage"] = call("usage_report", {"session": True})
    with open(os.path.join(s.out_dir, appliesnow.FILE), encoding="utf-8") as f:
        out["file"] = list(json.load(f)["sessions"].values())[0]
    out["listed"] = listed()
    print(json.dumps(out, default=repr))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--hub":
        _hub()
    elif len(sys.argv) > 1 and sys.argv[1] == "--fem":
        _fem()
    elif len(sys.argv) > 2 and sys.argv[1] == "--agree":
        _agree(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == "--states":
        _states()
    else:
        unittest.main()

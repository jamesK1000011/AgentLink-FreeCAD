# SPDX-License-Identifier: LGPL-2.1-or-later
# hubfix5b:
#   - meshobj_unwrap: the helper marks each import step before it takes it,
#     a crash while loading names the step, and the next program
#     (freecadcmd) is tried; the entry in the data stand-in.
#   - batch: no call starts once the time left is under that tool's
#     typical time (jobs.note_slow).
import json
import os
import subprocess
import sys
import textwrap
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(HERE, "tests")

try:
    import numpy  # noqa: F401
except ImportError:
    numpy = None


def child(code, timeout=120):
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=HERE, capture_output=True, text=True, timeout=timeout,
                       env=dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, TESTS])))
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


FAKES = r'''
import json, os, stat, sys, tempfile
fake = tempfile.mkdtemp()
def mod(name, body=""):
    with open(os.path.join(fake, name + ".py"), "w") as f:
        f.write(body)
mod("FreeCAD")
mod("Mesh")
mod("Part", "import os, signal\nif os.environ.get('CRASH_PART') and not os.environ.get('FAKE_CMD'):\n    os.kill(os.getpid(), signal.SIGSEGV)\n")
mod("flatmesh", "import numpy as np\nclass FaceUnwrapper:\n    def __init__(self, P, F):\n        self.P = P\n    def findFlatNodes(self, i, w):\n        self.ze_nodes = self.P[:, :2] * 2\n")
sys.path.insert(0, fake)
cmd = os.path.join(fake, "freecadcmd")
with open(cmd, "w") as f:
    f.write("#!/bin/sh\nFAKE_CMD=1 exec " + sys.executable + " \"$@\"\n")
os.chmod(cmd, 0o755)
import numpy as np
P = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
F = np.array([[0, 1, 2], [0, 2, 3]], int)
sys.modules.setdefault("FreeCAD", type(sys)("FreeCAD"))
'''


@unittest.skipIf(numpy is None, "no numpy")
class UnwrapHelper(unittest.TestCase):
    def run_it(self, crash, runners):
        return child(FAKES + f'''
import importlib.util
if {crash!r}:
    os.environ["CRASH_PART"] = "1"
# meshobj itself needs FreeCAD, Part and Mesh at import: the stand-in's
# (without its fake subprocess.run: the helper runs for real here).
import subprocess
real = subprocess.run
import _datamesh_standin
_datamesh_standin.install()
subprocess.run = real
from agentlink.families import meshobj
rs = [(n, sys.executable if n == "python" else cmd) for n in {runners!r}]
Q, loops, stop, why = meshobj.flatten_apart(P, F, 5, 0.95, runners_=rs)
print(json.dumps({{"Q": None if Q is None else Q.tolist(), "stop": stop, "why": why}}))
''')

    def test_it_runs_and_answers_the_flat_points(self):
        got = self.run_it(False, ["python"])
        self.assertEqual(got["Q"], [[0, 0], [2, 0], [2, 2], [0, 2]])
        self.assertIsNone(got["stop"])
        self.assertIsNone(got["why"])

    def test_a_crash_while_loading_names_the_step(self):
        got = self.run_it(True, ["python"])
        self.assertEqual((got["stop"], got["why"]), ("load", "it stopped (code -11) at import Part"))

    def test_the_console_program_is_tried_next_and_named(self):
        got = self.run_it(True, ["python", "freecadcmd"])
        self.assertEqual(got["Q"], [[0, 0], [2, 0], [2, 2], [0, 2]])
        self.assertEqual(got["why"], "ran in freecadcmd: python: it stopped (code -11) at import Part")

    def test_both_failing_name_each(self):
        got = child(FAKES + '''
import subprocess
real = subprocess.run
import _datamesh_standin
_datamesh_standin.install()
subprocess.run = real
from agentlink.families import meshobj
os.environ["CRASH_PART"] = "1"
with open(cmd, "w") as f:
    f.write("#!/bin/sh\\nexec " + sys.executable + " \\"$@\\"\\n")
Q, loops, stop, why = meshobj.flatten_apart(P, F, 5, 0.95, runners_=[("python", sys.executable), ("freecadcmd", cmd)])
print(json.dumps([stop, why]))
''')
        self.assertEqual(got, ["load", "python: it stopped (code -11) at import Part; freecadcmd: it stopped (code -11) at import Part"])

    def test_nothing_to_run_it_in(self):
        got = self.run_it(False, [])
        self.assertEqual(got["stop"], "python")

    def test_the_settings_folder_is_its_own(self):
        with open(os.path.join(HERE, "agentlink", "families", "meshobj.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('base["FREECAD_USER_HOME"] = os.path.join(d, "freecad")', src)

    def test_the_entry_answers_which_program_ran_it(self):
        with open(os.path.join(HERE, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]["meshobj_unwrap"]
        self.assertIn('{"put": {"helper": "=why"}, "into": "out", "when": "=why"}', json.dumps(e["steps"]))


@unittest.skipIf(numpy is None, "no numpy")
class UnwrapEntry(unittest.TestCase):
    """The entry through the data stand-in (new side only: the comparison
    with the old handler needs a commit this checkout may lack)."""

    def test_cases(self):
        got = child(r'''
import json, sys, tempfile
import _datamesh_standin
fc = _datamesh_standin.install()
from agentlink.families import meshobj
from agentlink.protocol import ToolError
from _datamesh_cases import cases
# The stand-in's Python is the only program here (no freecadcmd).
meshobj.unwrap_runners = lambda: [("python", sys.executable)]
out = {}
for tool, case, prepare, args in cases(fc, tempfile.mkdtemp()):
    if tool != "meshobj_unwrap":
        continue
    fc.state["flags"] = {}
    fc.state["n"] = 0
    s = fc.Session(tempfile.mkdtemp())
    prepare(s)
    t = [t for t in meshobj.tools(s) if t.name == tool][0]
    try:
        r = ["ok", t.fn(json.loads(json.dumps(args)))]
    except ToolError as e:
        r = ["refused", e.code, e.message]
    out[case] = json.loads(json.dumps(r, default=repr))
print(json.dumps(out))
''')
        self.assertEqual(got["its Python dies loading FreeCAD's modules"],
                         ["refused", "unavailable", "The unwrapping runs in a Python apart from FreeCAD, and FreeCAD's own modules would not load there "
                          "(it stopped (code -11)): nothing was unwrapped, and this surface is not the cause — unwrap a cylinder, cone or flat face "
                          "(\"Body.Face3\") instead: those are laid flat exactly, without it."])
        self.assertEqual(got["flatmesh stops"][:2], ["refused", "failed"])
        self.assertIn("RuntimeError: singular matrix", got["flatmesh stops"][2])
        ok = got["a mesh"]
        self.assertEqual(ok[0], "ok", ok)
        self.assertNotIn("helper", ok[1])
        self.assertIn("area3d", ok[1])


HELPERS = r'''
import json, sys, tempfile
import _datapart2_standin
fc = _datapart2_standin.install()
from agentlink import runners
seen = {}
real = runners.tools
def spy(group, session, helpers, data=None, family=None):
    seen[(group, family)] = helpers
    return real(group, session, helpers, data, family)
runners.tools = spy
from agentlink.families import model_more, std_more
model_more.tools(fc.Session(tempfile.mkdtemp()))
std_more.tools(fc.Session(tempfile.mkdtemp()))
H = {}
for v in seen.values():
    H.update(v)
'''


class PartQuiet(unittest.TestCase):
    """part 0030 / 0080 (window rounds 3-6): red lines in the Report view."""

    def test_attach_check_asks_a_copy_of_the_attacher(self):
        got = child(HELPERS + r'''
class Eng:
    made = []
    def __init__(self, fail=None):
        self.fail, self.References, self.Mode = fail, None, None
        Eng.made.append(self)
    def copy(self):
        return Eng(self.fail)
    def calculateAttachedPlacement(self, pl):
        if self.fail:
            raise ValueError(self.fail)
        return pl
class O:
    Placement = None
    def __init__(self, eng):
        self.Attacher = eng
first = Eng()
ok = H["attach_check"](O(first), "T", "Vertex1", "Translate")
bad = H["attach_check"](O(Eng("No planar face in AttachEngine3D::calculateAttachedPlacement()!")), "T", "Vertex1", "FlatFace")
off = H["attach_check"](O(Eng("x")), "T", "", "Deactivated")
none = H["attach_check"](O(None), "T", "", "ObjectXY")
print(json.dumps([ok, bad, off, none, first.References, first.Mode, Eng.made[1].References, Eng.made[1].Mode]))
''')
        self.assertEqual(got[:4], [None, "No planar face in AttachEngine3D::calculateAttachedPlacement()!", None, None])
        # the object's own attacher untouched; the copy asked
        self.assertEqual(got[4:], [None, None, [["T", "Vertex1"]], "Translate"])

    def test_part_attach_detaches_before_the_support_is_set(self):
        with open(os.path.join(HERE, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            steps = json.load(f)["entries"]["part_attach"]["steps"]
        said = [json.dumps(x, ensure_ascii=False) for x in steps]
        i = next(n for n, x in enumerate(said) if "attach_check(o, tgt, sub, mode)" in x)
        j = next(n for n, x in enumerate(said) if '"o.MapMode": "Deactivated"' in x)
        k = next(n for n, x in enumerate(said) if "'AttachmentSupport' if" in x)
        self.assertLess(i, j)
        self.assertLess(j, k)
        self.assertIn("{why_not}", said[i + 1])

    def test_filter_keeps_follows_freecads_compound_filter(self):
        got = child(HELPERS + r'''
class Box:
    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi
class S:
    def __init__(self, lo, hi, vol, kids=()):
        self.lo, self.hi, self.Volume, self.Area, self.Length, self.kids = lo, hi, vol, vol, vol, list(kids)
    def childShapes(self):
        return self.kids
    def distToShape(self, o):
        gap = max(0.0, max(o.lo - self.hi, self.lo - o.hi))
        return (gap, [], [])
class Obj:
    def __init__(self, sh):
        self.Shape = sh
k = H["filter_keeps"]
a, b, c = S(0, 1, 10), S(2, 3, 5), S(4, 5, 1)
comp = Obj(S(0, 5, 16, [a, b, c]))
touch = Obj(S(0.5, 2.5, 1))
far = Obj(S(10, 11, 1))
print(json.dumps([
    k(comp, "collision-pass", False, touch), k(comp, "collision-pass", True, touch),
    k(comp, "collision-pass", True, far), k(comp, "collision-pass", False, None),
    k(comp, "window-volume", False, None), k(comp, "window-volume", False, None, 10, 20),
    k(comp, "window-volume", False, None, 40, 100), k(comp, "window-volume", True, None, 40, 100),
    k(comp, "window-distance", False, far, 0, 100), k(Obj(None), "window-volume", False, None)]))
''')
        # touch reaches a and b; window: of the largest (10): 80-100% only a; 10-20% only c; 40-100% a and b
        self.assertEqual(got, [2, 1, 3, None, 1, 1, 2, 1, 3, None])

    def test_the_filter_that_keeps_nothing_is_refused_before_it_is_made(self):
        got = child(r'''
import json, sys, tempfile
import _datapart_standin
fc = _datapart_standin.install()
from _datapart_cases import cases
import importlib
from _datapart_cases import CONVERTED
from agentlink.families import std_more
from agentlink.protocol import ToolError
mods = {m: importlib.import_module(f"agentlink.families.{m}") for m in set(CONVERTED.values())}
out = {}
for tool, case, prepare, args in cases(fc, tempfile.mkdtemp(), mods, mods):
    if tool != "compound_filter" or case not in ("every piece touches", "none in the window", "not touching a stencil"):
        continue
    del fc.trace[:]; fc.state["flags"] = {}
    s = fc.Session(tempfile.mkdtemp()); prepare(s)
    t = [t for t in std_more.tools(s) if t.name == tool and t.fn.__module__ == "agentlink.runners"][0]
    try:
        r = ["ok", t.fn(json.loads(json.dumps(args)))]
    except ToolError as e:
        r = ["refused", e.code, e.message]
    out[case] = [r, any("makeCompoundFilter" in x for x in fc.trace)]
print(json.dumps(out))
''')
        self.assertEqual(got["every piece touches"], [["refused", "failed", "The filter keeps nothing of Parts (collision-fail): every piece touches the stencil — nothing was made."], False])
        self.assertEqual(got["none in the window"][0][2], "The filter keeps nothing of Parts (window-area): no piece lies within 10 … 20% of the largest (or of the stencil's) — nothing was made.")
        self.assertFalse(got["none in the window"][1])
        self.assertEqual(got["not touching a stencil"][0][0], "ok")
        self.assertTrue(got["not touching a stencil"][1])

    def test_compound_explode_names_what_fails_after_it(self):
        with open(os.path.join(HERE, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]["compound_explode"]
        self.assertEqual(e["answer"]["fields"]["failing"], {"when": "=all_broken()", "value": "=all_broken()"})


class BatchTypical(unittest.TestCase):
    """jobs.typical stays as logged data; a batch no longer holds a call back
    on it (no prejudging, 18 Nov: a loft put at 766 s took 7 s)."""

    def test_typical_is_the_middle_of_the_last_times(self):
        sys.path.insert(0, HERE)
        from agentlink import jobs

        jobs._RECENT.pop("t_tool", None)
        self.assertIsNone(jobs.typical("t_tool"))
        for x in (1, 30, 2, 50, 40, 3):  # the last five kept
            jobs.note_time("t_tool", x)
        self.assertEqual(jobs._RECENT["t_tool"], [30, 2, 50, 40, 3])
        self.assertEqual(jobs.typical("t_tool"), 30)
        # A wild size-scaled estimate from the slow-read log is not trusted (live: part_loft "7813307 s").
        jobs._RECENT.pop("t_tool", None)
        real = jobs.keep.queue_state, jobs.keep.estimate_range
        try:
            jobs.keep.queue_state = lambda: {"timings": {"t_tool": [1]}}
            jobs.keep.estimate_range = lambda q, n, size: (1.0, 7813307.0, 9e9)
            self.assertIsNone(jobs.typical("t_tool"))
            jobs.keep.estimate_range = lambda q, n, size: (1.0, 12.0, 30.0)
            self.assertEqual(jobs.typical("t_tool"), 12.0)
        finally:
            jobs.keep.queue_state, jobs.keep.estimate_range = real
        for x in (30, 2, 50, 40, 3):
            jobs.note_time("t_tool", x)
        jobs.note_time("t_tool", "x")
        jobs.note_time("t_tool", -1)
        self.assertEqual(len(jobs._RECENT["t_tool"]), 5)
        jobs._RECENT.pop("t_tool", None)

    def test_a_call_typically_long_is_still_started(self):
        sys.path.insert(0, TESTS)
        from test_hubfix2 import in_a_process
        from test_hubfix4 import SETUP

        out = __import__("tempfile").mkdtemp(prefix="agentlink-hubfix5b-")
        got = in_a_process(SETUP + '''
    from agentlink import jobs, tools
    s = tools.Session(out_dir=%r)
    srv = tools.build_server(s, lean=False)
    def call(name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
        return [r.get("isError", False), json.loads(r["content"][0]["text"])]
    calls = [{"tool": "tool_groups", "arguments": {}}, {"tool": "session_state", "arguments": {}}, {"tool": "tool_groups", "arguments": {}}]
    plain = call("batch", {"calls": calls, "rollback": False})
    jobs._RECENT["session_state"] = [70.0, 80.0, 90.0]
    slow = call("batch", {"calls": calls, "rollback": False})
    first = call("batch", {"calls": calls[1:], "rollback": False})
    roomy = call("batch", {"calls": calls, "rollback": False, "budget": 100})
    print(json.dumps({"plain": plain, "slow": slow, "first": first, "roomy": roomy}))
''' % out)
        err, plain = got["plain"]
        self.assertFalse(err, plain)
        # notRun is also given at a refusal now (23 Nov): the budget's stop says "Stopped after".
        self.assertNotIn("Stopped after", plain.get("note", ""))
        err, slow = got["slow"]
        self.assertFalse(err, slow)
        self.assertNotIn("Stopped after", slow.get("note", ""))
        self.assertNotIn("typically takes", json.dumps(slow))
        self.assertEqual(slow["results"][1]["tool"], "session_state")  # it was started
        # the first call of a batch always runs
        self.assertNotIn("Stopped after", got["first"][1].get("note", ""))
        # its time recorded by the call itself (the stand-in's is short): the middle stays 80 s, under a 100 s budget
        self.assertNotIn("Stopped after", got["roomy"][1].get("note", ""))


if __name__ == "__main__":
    unittest.main()

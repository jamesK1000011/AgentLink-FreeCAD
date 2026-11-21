# SPDX-License-Identifier: LGPL-2.1-or-later
# Findings of the three bicycle design runs (FreeCAD 1.1.3, 21 Nov 2026), on
# the data tests' stand-in FreeCAD in a child process (test_bicycle_1120.child):
#   1  asm_sweep of 25 parts: only pairs with motion between them, boxes
#      first, static shapes read once; parts and skip; pairsChecked/Skipped.
import json
import os
import sys
import time
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS)

from test_bicycle_1120 import child  # noqa: E402


class SweepCheap(unittest.TestCase):
    """Finding 1."""

    BUILD = '''
        # a wheel (Lid turns on Base) with a spoke set carried on it, and 22 still parts in a row far off
        fc.a_part("Spokes", (1, 1, 9), (9, 9, 11), name="Spokes")  # into the base: a contact the motion keeps
        far = []
        for i in range(22):
            n = f"Still{i}"
            fc.a_part(n, (100 + 20 * i, 0, 0), (110 + 20 * i, 10, 10), name=n)
            far.append(n)
        asm, jg = assembly("Base", "Lid", "Spokes", *far)
        joint(jg, "Revolute", "Base.Face1", "Lid.Face1", "Hub")
        joint(jg, "Fixed", "Lid.Face1", "Spokes.Face1", "Carry")
        reads = {}
        first_shape = A._shape
        def counted(o):
            reads[o.Name] = reads.get(o.Name, 0) + 1
            return first_shape(o)
        A._shape = counted
    '''

    def test_only_pairs_with_motion_and_counts(self):
        got = child(self.BUILD, '''
            full = run("asm_sweep", {"joint": "Hub", "steps": 4})
            r1 = dict(reads)
            reads.clear()
            only = run("asm_sweep", {"joint": "Hub", "steps": 4, "parts": ["Spokes", "Base"]})
            skip = run("asm_sweep", {"joint": "Hub", "steps": 4, "skip": ["Still0", "Still1"]})
            bad = run("asm_sweep", {"joint": "Hub", "parts": ["Nope"]})
            print(json.dumps([full, r1, only, skip, bad], default=str))
        ''')
        full, reads, only, skip, bad = got
        self.assertEqual(full[0], "ok", full)
        f = full[1]
        self.assertEqual(f["moves"], ["Lid", "Spokes"])
        # 25 parts: 300 pairs a step. Moving (Lid, Spokes) x the 23 still: 46 pairs with motion; Lid/Spokes and the
        # 253 still/still pairs are left out. Boxes: only Spokes can meet Base (Lid only touches it): at most 1 pair is cut a step
        # (the stand-in's box follows the turn's shift only, so some steps cut none).
        n = f["pairsChecked"]
        self.assertTrue(1 <= n <= 5, n)
        self.assertEqual(n + f["pairsSkipped"], 300 * 5)
        self.assertEqual(len(f["steps"]), 5)
        # a part that stays put is read once for the whole sweep; a moving part once a step
        self.assertEqual(reads["Still5"], 1)
        self.assertEqual(reads["Base"], 1)
        self.assertEqual(reads["Lid"], 5)
        self.assertEqual(only[1]["pairsChecked"], n)
        self.assertEqual(only[1]["pairsSkipped"], 300 * 5 - n)
        self.assertEqual(skip[1]["pairsChecked"], n)
        self.assertEqual(skip[1]["pairsSkipped"], 300 * 5 - n)
        self.assertEqual(bad[:2], ["refused", "invalid_input"])
        self.assertIn("'Nope' is not a part of Assembly", bad[2])

    def test_a_still_overlap_is_not_a_collision_of_the_motion(self):
        # Base and a pin pressed into it: neither moves, so the pair is never cut
        got = child('''
            fc.a_part("Pin", (2, 2, 2), (4, 4, 8), name="Pin")
            asm, jg = assembly("Base", "Lid", "Pin")
            joint(jg, "Revolute", "Base.Face1", "Lid.Face1", "Hub")
            print(json.dumps(run("asm_sweep", {"joint": "Hub", "steps": 2})))
        ''')
        self.assertEqual(got[0], "ok", got)
        for row in got[1]["steps"]:
            for h in row.get("overlaps", ()):
                self.assertNotEqual(sorted(h["parts"]), ["Base", "Pin"])

    def test_the_card_says_it(self):
        with open(os.path.join(os.path.dirname(TESTS), "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]["asm_sweep"]
        for k in ("parts", "skip"):
            self.assertIn(k, e["inputSchema"]["properties"])
        for words in ("Only pairs with motion between them are checked.", "pairsChecked, pairsSkipped"):
            self.assertIn(words, e["description"])


class SideCheck(unittest.TestCase):
    """Finding 3."""

    def run_case(self, puts, args=None):
        return child(f'''
            asm, jg = assembly("Base", "Lid")
            fc.state["flags"].update(joint_puts={{"Lid": {puts!r}}})
            print(json.dumps(run("asm_joint", {{**{{"kind": "fixed", "a": {{"part": "Base", "element": "Face1"}}, "b": {{"part": "Lid", "element": "Face2"}}}}, **{args or {}!r}}})))
        ''')

    def test_a_part_put_across_the_plane_is_said(self):
        r = self.run_case([0, 0, -30])
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["sideCheck"], [{"part": "Lid", "before": 11.0, "after": -19.0, "crossed": True}])
        w = r[1]["sideWarning"]
        self.assertIn("Lid on the other side of the joint's plane", w)
        self.assertIn("reverse: true", w)

    def test_the_same_side_gives_no_warning(self):
        r = self.run_case([0, 0, 2])
        self.assertEqual(r[1]["sideCheck"][0]["crossed"], False)
        self.assertNotIn("sideWarning", r[1])

    def test_with_reverse_the_warning_names_reverse_false(self):
        r = self.run_case([0, 0, -30], {"reverse": True})
        if "sideWarning" in r[1]:
            self.assertIn("reverse: false", r[1]["sideWarning"])

    def test_no_side_check_with_auto_flip(self):
        r = self.run_case([0, 0, -30], {"autoFlip": True})
        self.assertNotIn("sideCheck", r[1])


# Finding 5: in a Python of its own with stand-in FreeCAD modules (as tests/test_fem_route.py).
FEA = r'''
import json, os, subprocess, sys, tempfile, time, types
sys.path.insert(0, ROOT)
fc = types.ModuleType("FreeCAD")
fc.Vector = lambda *a: a
fc.GuiUp = False
fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d)
sys.modules["FreeCAD"] = fc
sys.modules["Part"] = types.ModuleType("Part")
from agentlink.families import strength as S
from agentlink.protocol import ToolError
out = {}
# a fork blade, 30 x 2 mm tube 400 mm long: V = pi (15² - 13²) 400, A = 2 pi (15 + 13) 400
import math
V, A = math.pi * (15 ** 2 - 13 ** 2) * 400, 2 * math.pi * (15 + 13) * 400
out["default"] = S.mesh_estimate(V, A, 10.0)
out["rule"] = S.mesh_estimate(V / 4, A / 4, 1.0)  # a 100 mm stub of it
out["fine"] = S.mesh_estimate(V, A, 0.25)
out["refusal"] = S.mesh_refusal("Blade", 0.25, out["fine"])
out["cube"] = S.mesh_estimate(1000.0, 600.0, 3.0)
big = S.mesh_estimate(8e6, 2.4e5, 1.0)
out["big"] = big
out["bigRefusal"] = S.mesh_refusal("Block", 1.0, big)
# one budget: what is left, refused when it is used
t0 = time.monotonic() - 299.5
try:
    S.left_of(t0, 300, "CalculiX ran")
    out["left"] = "no refusal"
except ToolError as e:
    out["left"] = [e.code, e.message]
out["leftSome"] = round(S.left_of(time.monotonic() - 100, 300, "x"))
# CalculiX on the FEM route is bounded: a ccx that hangs is stopped at the time left
d = tempfile.mkdtemp()
ccx = os.path.join(d, "ccx")
with open(ccx, "w") as f:
    f.write("#!/bin/sh\nexec sleep 30\n")
os.chmod(ccx, 0o755)
fea = types.SimpleNamespace(inp_file_name=os.path.join(d, "FEMMeshGmsh.inp"))
t1 = time.monotonic()
try:
    S.ccx_bounded(fea, ccx, 1.5)
    out["hang"] = "no refusal"
except ToolError as e:
    out["hang"] = [e.code, e.message, round(time.monotonic() - t1, 1)]
with open(ccx, "w") as f:
    f.write("#!/bin/sh\necho Job finished\nexit 0\n")
out["ran"] = [S.ccx_bounded(fea, ccx, 5), fea.ccx_stdout.strip()]
print(json.dumps(out))
'''


class FeaSolveBounded(unittest.TestCase):
    """Finding 5."""

    @classmethod
    def setUpClass(cls):
        import subprocess as sp

        root = os.path.dirname(TESTS)
        r = sp.run([sys.executable, "-c", f"ROOT = {root!r}\n" + FEA], capture_output=True, text=True, timeout=120, cwd=root)
        if r.returncode:
            raise AssertionError(r.stderr[-3000:])
        cls.got = json.loads(r.stdout.strip().splitlines()[-1])

    def test_the_estimate(self):
        g = self.got
        self.assertAlmostEqual(g["default"]["wall"], 2.0, places=2)  # 2 V / A is the wall of a tube
        self.assertFalse(g["default"]["over"])
        self.assertLess(g["default"]["through"], 1)
        self.assertEqual(g["default"]["rule"], 1.0)
        self.assertTrue(g["rule"]["ruleFits"])
        self.assertTrue(g["fine"]["over"])
        self.assertGreater(g["fine"]["elements"], 400000)
        self.assertGreater(g["cube"]["wall"], 3)

    def test_the_refusal_names_a_size_that_fits_and_the_rule(self):
        g = self.got
        w = g["refusal"]
        self.assertTrue(w.startswith("Not meshed: Blade at 0.25 mm makes about "), w)
        self.assertIn(f"A mesh of {g['fine']['fits']:g} mm fits", w)
        self.assertIn("2 elements through the wall", w)
        self.assertIn("1 mm or less", w)
        # 400 mm of tube at 1 mm is over the limit as well: beam elements or shells
        self.assertFalse(g["fine"]["ruleFits"])
        self.assertIn("over the limit too", w)
        self.assertIn("beam elements", w)
        self.assertIn("fea_shell", w)
        # a solid block: the rule fits, no word of fea_frame
        b = g["bigRefusal"]
        self.assertTrue(g["big"]["ruleFits"], g["big"])
        self.assertNotIn("beam elements", b)

    def test_one_budget_for_gmsh_and_calculix(self):
        g = self.got
        self.assertEqual(g["left"][0], "failed")
        self.assertIn("used its timeout (300 s) before CalculiX ran", g["left"][1])
        self.assertEqual(g["leftSome"], 200)

    def test_calculix_on_the_fem_route_is_stopped_in_time(self):
        g = self.got
        self.assertEqual(g["hang"][0], "failed", g["hang"])
        self.assertIn("CalculiX took over 1.5 s", g["hang"][1])
        self.assertLess(g["hang"][2], 10)
        self.assertEqual(g["ran"], [0, "Job finished"])

    def test_the_card_and_the_steps(self):
        with open(os.path.join(os.path.dirname(TESTS), "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]["fea_solve"]
        self.assertIn("one limit for Gmsh and CalculiX together", e["description"])
        self.assertIn("refuses before meshing", e["description"])
        self.assertIn("2 elements through the wall", e["description"])
        self.assertIn("elements through the wall", json.dumps(e["steps"]))
        with open(os.path.join(os.path.dirname(TESTS), "agentlink", "families", "strength.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("fea.ccx_run()", src)


class ClosedTube(unittest.TestCase):
    """Finding 6: a tube on a closed path is refused (FreeCAD's Pipe made a solid ring)."""

    def test_a_ring_path_with_a_wall_is_refused_with_the_way(self):
        import test_pipe_1120 as P

        got = P.child("_datapd_standin", "feature", P.PD_SETUP, '''
            sq = [fc.edge(V(0, 0, 0), V(50, 0, 0)), fc.edge(V(50, 0, 0), V(50, 50, 0)), fc.edge(V(50, 50, 0), V(0, 50, 0)), fc.edge(V(0, 50, 0), V(0, 0, 0))]
            ring = s.doc.new("PartDesign::SubShapeBinder", "RimPath")
            ring.__dict__["Shape"] = fc.Shape("compound", [], edges=sq + [fc.edge(V(0, 0, 0), V(0, 0, 0))])
            b._place(ring)
            n0 = len(s.doc.Objects)
            out = {"square": run("pd_pipe", {"path": "RimPath", "edges": ["Edge1", "Edge2", "Edge3", "Edge4"], "profile": {"circle": {"d": 30, "wall": 2}}}),
                   "circle": run("pd_pipe", {"path": "RimPath", "edges": ["Edge5"], "profile": {"circle": {"d": "Geo.od", "wall": 2}}}),
                   "made": len(s.doc.Objects) - n0,
                   "rod": run("pd_pipe", {"path": "RimPath", "edges": ["Edge1", "Edge2", "Edge3", "Edge4"], "profile": {"circle": {"d": 30}}})[0],
                   "open": run("pd_pipe", {"path": "FrameSkel", "edges": ["Edge1", "Edge2"], "profile": {"circle": {"d": 30, "wall": 2}}})[0]}
            print(json.dumps(out))
        ''')
        sq = got["square"]
        self.assertEqual(sq[:2], ["refused", "invalid_input"])
        self.assertIn("a tube (circle with wall) on a closed path (RimPath: Edge1, Edge2, Edge3, Edge4)", sq[2])
        self.assertIn("pd_pipe { profile: { circle: { d: 30 } } }", sq[2])
        self.assertIn("pd_pipe { profile: { circle: { d: 26 } }, subtractive: true }", sq[2])
        self.assertIn("Nothing was made", sq[2])
        self.assertIn('d: "(Geo.od) - 2 * (2 mm)"', got["circle"][2])
        self.assertEqual(got["made"], 0)
        self.assertEqual(got["rod"], "ok")  # a rod on a ring path is FreeCAD's solid ring, as meant
        self.assertEqual(got["open"], "ok")


# Finding 7: the real batch tool on a stand-in FreeCAD (every module a mock), as tests/test_batch_nested_81b.py.
BATCH = r'''
import io, json, os, sys, tempfile, types
from unittest import mock
ROOT=sys.argv[1]; sys.path.insert(0, ROOT)
class Auto(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"): raise AttributeError(k)
        m = mock.MagicMock(name=f"{self.__name__}.{k}"); setattr(self, k, m); return m
for n in ("FreeCAD", "FreeCADGui", "Part", "Mesh", "MeshPart", "Sketcher", "Import", "TechDraw", "Draft", "Spreadsheet", "PySide", "PySide.QtCore", "PySide.QtGui"):
    sys.modules[n] = Auto(n)
fc = sys.modules["FreeCAD"]; fc.GuiUp = False
fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d)
os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp()
from agentlink.protocol import Tool
from agentlink.tools import Session, build_server
s = Session(out_dir=tempfile.mkdtemp())
class Doc:
    Name = Label = "D"; UndoCount = 0; FileName = ""; Objects = []
    def undo(self): pass
    def recompute(self): pass
    def openTransaction(self, n=""): pass
    def commitTransaction(self): pass
    def abortTransaction(self): pass
    def isTouched(self): return False
s.doc = Doc()
srv = build_server(s, lean=False); s.server = srv
srv.tools["probe_state"] = Tool("probe_state", "probe", {"type": "object", "properties": {"n": {}}}, lambda a: {"n": a.get("n"), "big": "x" * 50})
args = json.loads(sys.argv[2])
if "file" in args:
    with open(os.path.join(s.out_dir, "calls.json"), "w") as fh:
        json.dump(json.loads(sys.argv[3]), fh)
r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "batch", "arguments": args}})
txt = r["result"]["content"][0]["text"]
p = os.path.join(s.out_dir, "out.json")
print(json.dumps({"reply": json.loads(txt) if txt.startswith("{") else txt, "file": os.path.isfile(p), "out_dir": s.out_dir}))
'''


class BatchFileTo(unittest.TestCase):
    """Finding 7: a batch file's own to and lines: "full" are kept."""

    def run_batch(self, args, data):
        import subprocess as sp

        root = os.path.dirname(TESTS)
        r = sp.run([sys.executable, "-c", BATCH, root, json.dumps(args), json.dumps(data)], capture_output=True, text=True, timeout=120, cwd=root)
        if r.returncode:
            raise AssertionError(r.stderr[-3000:])
        return json.loads(r.stdout.strip().splitlines()[-1])

    CALLS = [{"tool": "probe_state", "arguments": {"n": 1}}]

    def test_to_and_full_in_the_file(self):
        got = self.run_batch({"file": "calls.json"}, {"calls": self.CALLS, "to": "out.json", "lines": "full"})
        self.assertTrue(got["file"], got)
        self.assertEqual(got["reply"]["written"]["path"], os.path.join(got["out_dir"], "out.json"))
        self.assertEqual(got["reply"]["results"][0]["result"]["n"], 1)  # full: the whole answer here too

    def test_full_in_the_call_and_to_in_the_file(self):
        got = self.run_batch({"file": "calls.json", "lines": "full"}, {"calls": self.CALLS, "to": "out.json"})
        self.assertTrue(got["file"], got)
        self.assertIn("result", got["reply"]["results"][0])

    def test_calls_with_to_and_full(self):
        got = self.run_batch({"calls": self.CALLS, "to": "out.json", "lines": "full"}, None)
        self.assertTrue(got["file"], got)
        self.assertIn("written", got["reply"])
        self.assertIn("result", got["reply"]["results"][0])


class _Box:
    def __init__(self, lo, hi):
        self.XMin, self.YMin, self.ZMin = lo
        self.XMax, self.YMax, self.ZMax = hi

    def isValid(self):
        return True

    def intersect(self, o):
        return all(getattr(self, a + "Min") < getattr(o, a + "Max") and getattr(o, a + "Min") < getattr(self, a + "Max") for a in "XYZ")

    def add(self, o):
        for a in "XYZ":
            setattr(self, a + "Min", min(getattr(self, a + "Min"), getattr(o, a + "Min")))
            setattr(self, a + "Max", max(getattr(self, a + "Max"), getattr(o, a + "Max")))

    XLength = property(lambda s: s.XMax - s.XMin)
    YLength = property(lambda s: s.YMax - s.YMin)
    ZLength = property(lambda s: s.ZMax - s.ZMin)


class _Shape:
    """A box-like solid, or a compound of them, that counts its booleans and reads."""
    cuts = [0]

    def __init__(self, boxes):
        self.boxes = boxes
        lo = tuple(min(b[0][i] for b in boxes) for i in range(3))
        hi = tuple(max(b[1][i] for b in boxes) for i in range(3))
        self.BoundBox = _Box(lo, hi)
        self.Faces = []
        self.Solids = [self] if len(boxes) == 1 else [_Shape([b]) for b in boxes]

    def isNull(self):
        return False

    def countElement(self, k):
        return 6 * len(self.boxes)

    @property
    def Volume(self):
        return sum((b[1][0] - b[0][0]) * (b[1][1] - b[0][1]) * (b[1][2] - b[0][2]) for b in self.boxes)

    def common(self, o):
        _Shape.cuts[0] += 1
        a, b = self.boxes[0], o.boxes[0]
        lo = tuple(max(a[0][i], b[0][i]) for i in range(3))
        hi = tuple(min(a[1][i], b[1][i]) for i in range(3))
        if any(hi[i] <= lo[i] for i in range(3)):
            return _Shape([((0, 0, 0), (0, 0, 0))])
        return _Shape([(lo, hi)])


class _Part:
    reads = {}

    def __init__(self, name, boxes):
        self.Name = self.Label = name
        self._shape = _Shape(boxes)
        self.InListRecursive, self.OutListRecursive, self.Visibility, self.TypeId = [], [], True, "PartDesign::Body"

    @property
    def Shape(self):
        _Part.reads[self.Name] = _Part.reads.get(self.Name, 0) + 1
        return self._shape


class HealthPairs(unittest.TestCase):
    """Finding 8: the health check's interference pass."""

    def setUp(self):
        from agentlink import health

        self.H = health
        health._still.clear()
        _Shape.cuts[0] = 0
        _Part.reads.clear()
        # 22 parts: a hub, two spoke bodies of 32 solids round it, 19 parts far off
        hub = _Part("Hub", [((-10, -10, -10), (10, 10, 10))])
        spokes = [_Part(f"Spokes{k}", [((-300 + 18 * i, -1 + 3 * k, -1), (-290 + 18 * i, 1 + 3 * k, 1)) for i in range(32)]) for k in (0, 1)]
        far = [_Part(f"Far{i}", [((1000 + 50 * i, 0, 0), (1010 + 50 * i, 10, 10))]) for i in range(19)]
        self.parts = [hub] + spokes + far
        self.keys = {p.Name: ("key", p.Name) for p in self.parts}

    def run_pass(self, changed):
        counts = {}
        hits, _skipped = self.H.overlaps(changed, self.parts, time.time() + 30, "Doc", {n: k for n, k in self.keys.items() if n not in {c.Name for c in changed}}, counts)
        return hits, counts

    def test_a_changed_hub_checks_only_what_its_box_meets(self):
        hub = self.parts[0]
        hits, counts = self.run_pass([hub])
        # the hub against 21 others: only the two spoke bodies' boxes meet it
        self.assertEqual(counts, {"checked": 2, "skipped": 19})
        # each spoke body cut solid by solid, only the solids whose boxes meet the hub's: 2 of its 32
        self.assertEqual(_Shape.cuts[0], 4)
        self.assertEqual(sorted(h["b"] for h in hits), ["Spokes0", "Spokes1"])

    def test_still_parts_are_read_once_across_calls(self):
        hub = self.parts[0]
        self.run_pass([hub])
        self.run_pass([hub])
        self.assertEqual(_Part.reads["Far3"], 1)
        self.assertEqual(_Part.reads["Spokes0"], 1)
        self.assertEqual(_Part.reads["Hub"], 2)  # the changed part is read afresh each call
        # a still part whose key changed is read again
        self.keys["Far3"] = ("key", "new")
        self.run_pass([hub])
        self.assertEqual(_Part.reads["Far3"], 2)

    def test_a_far_part_moved_cuts_nothing(self):
        _hits, counts = self.run_pass([self.parts[-1]])
        self.assertEqual(counts, {"checked": 0, "skipped": 21})
        self.assertEqual(_Shape.cuts[0], 0)


if __name__ == "__main__":
    unittest.main()


# Finding 2: real rotations (the stand-in turns about z only), FreeCAD's rule
# for a fixed joint: the moving part goes where both ends' frames meet, each
# frame part · (part⁻¹ · object) · PlacementN, PlacementN = found · OffsetN.
QMATH = r'''
import math, types
class QV:
    def __init__(s, x=0.0, y=0.0, z=0.0):
        if isinstance(x, (QV, tuple, list)):
            x, y, z = x[0], x[1], x[2]
        s.x, s.y, s.z = float(x), float(y), float(z)
    def __getitem__(s, i): return (s.x, s.y, s.z)[i]
    def __iter__(s): return iter((s.x, s.y, s.z))
    def __add__(s, o): return QV(s.x + o.x, s.y + o.y, s.z + o.z)
    def __sub__(s, o): return QV(s.x - o.x, s.y - o.y, s.z - o.z)
    def __mul__(s, k): return QV(s.x * k, s.y * k, s.z * k)
    @property
    def Length(s): return math.sqrt(s.x ** 2 + s.y ** 2 + s.z ** 2)
class QR:
    def __init__(s, axis=None, deg=0.0, q=None):
        if q is not None:
            s.q = q
            return
        if axis is None:
            s.q = (0.0, 0.0, 0.0, 1.0)
            return
        a = QV(axis); n = a.Length; h = math.radians(deg) / 2
        s.q = (a.x / n * math.sin(h), a.y / n * math.sin(h), a.z / n * math.sin(h), math.cos(h))
    def multiply(s, o):
        x1, y1, z1, w1 = s.q; x2, y2, z2, w2 = o.q
        return QR(q=(w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2))
    def inverted(s):
        x, y, z, w = s.q
        return QR(q=(-x, -y, -z, w))
    def multVec(s, v):
        p = s.multiply(QR(q=(v.x, v.y, v.z, 0.0))).multiply(s.inverted()).q
        return QV(p[0], p[1], p[2])
    @property
    def Angle(s): return 2 * math.acos(max(-1.0, min(1.0, abs(s.q[3]))))
    @property
    def Axis(s):
        x, y, z, w = s.q; n = math.sqrt(x * x + y * y + z * z)
        return QV(0, 0, 1) if n < 1e-12 else QV(x / n, y / n, z / n)
class QP:
    def __init__(s, base=None, rot=None):
        s.Base, s.Rotation = QV(base or (0, 0, 0)), rot or QR()
    def multiply(s, o): return QP(s.Base + s.Rotation.multVec(o.Base), s.Rotation.multiply(o.Rotation))
    def inverse(s):
        r = s.Rotation.inverted()
        return QP(r.multVec(s.Base) * -1, r)
    def copy(s): return QP(QV(s.Base), QR(q=s.Rotation.q))
    def isSame(s, o, tol=1e-7):
        d = s.Rotation.inverted().multiply(o.Rotation)
        return (s.Base - o.Base).Length <= tol and d.Angle <= tol
FC = types.SimpleNamespace(Placement=QP, Vector=QV, Rotation=QR)
'''


class KeepOnARotatedLcs(unittest.TestCase):
    """Finding 2."""

    def run_keep(self, frame_fix=True):
        return child(QMATH, f'''
            A.FreeCAD = FC
            class Obj:
                def __init__(s, name, plc):
                    s.Name = s.Label = name
                    s.Placement = plc
            frame = Obj("Frame", QP((0, 0, 0)))
            # the crank's origin is far from its joint; its LCS is turned 90° about x and set off the origin
            crank = Obj("Crank", QP((120, -40, 30), QR(QV(0, 0, 1), 25)))
            lcs_f = QP((50, 10, 0), QR(QV(1, 0, 0), 90))  # the frame's LCS in the frame
            lcs_c = QP((-35, 22, 8), QR(QV(1, 0, 0), 90))  # the crank's LCS in the crank
            class Joint:
                Reference1 = [frame, ["LCS.", "LCS."]]
                Reference2 = [crank, ["LCS.", "LCS."]]
                def __init__(s):
                    s.__dict__["Placement1"] = QP(); s.__dict__["Placement2"] = QP()
                    s.__dict__["Offset1"] = QP(); s.__dict__["Offset2"] = QP()
                def __setattr__(s, k, v):
                    s.__dict__[k] = v
                    if k in ("Offset1", "Offset2"):  # PlacementN = found (identity on an LCS) · OffsetN
                        s.__dict__["Placement" + k[-1]] = v.copy()
            j = Joint()
            ua = sys.modules["UtilsAssembly"]
            def glob(ref, target=None):
                part = ref[0]
                if target is not None:
                    return target.Placement
                return part.Placement.multiply(lcs_f if part is frame else lcs_c)
            if {frame_fix!r}:
                ua.getGlobalPlacement = glob
            elif hasattr(ua, "getGlobalPlacement"):
                del ua.getGlobalPlacement
            def solve():
                g1 = frame.Placement.multiply(lcs_f).multiply(j.Placement1)
                crank.Placement = g1.multiply(lcs_c.multiply(j.Placement2).inverse())
            class Doc:
                def recompute(s):
                    solve()
            before = {{"Frame": frame.Placement.copy(), "Crank": crank.Placement.copy()}}
            A._parts = lambda asm: [frame, crank]
            A._status = lambda asm: (0, "solved")
            solve()  # the joint as made, without keep: the crank jumps
            jumped = (crank.Placement.Base - before["Crank"].Base).Length
            code, said, kept = A.keep_offset(Doc(), None, j, [(frame, "LCS."), (crank, "LCS.")], before)
            print(json.dumps([jumped, kept, list(crank.Placement.Base), crank.Placement.isSame(before["Crank"], 1e-6)]))
        ''')

    def test_keep_moves_nothing_on_a_rotated_lcs(self):
        jumped, kept, at, same = self.run_keep()
        self.assertGreater(jumped, 10)
        self.assertEqual(kept["moved"], {"mm": 0.0, "degrees": 0.0}, kept)
        self.assertTrue(same, at)
        for c, want in zip(at, (120, -40, 30)):
            self.assertAlmostEqual(c, want, places=6)

    def test_the_old_frame_moved_the_part(self):
        # without the object's own placement (the old math) the offset found does not hold the crank
        _jumped, kept, _at, same = self.run_keep(frame_fix=False)
        self.assertFalse(same)
        self.assertGreater(kept["moved"]["mm"] + kept["moved"]["degrees"], 1)

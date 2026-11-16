# SPDX-License-Identifier: LGPL-2.1-or-later
# fea_solve goes through FreeCAD's own FEM objects (analysis, CalculiX
# solver, Gmsh mesh, constraints, FemToolsCcx) for the studies that route
# takes, and says why when its own deck solves instead. In a separate Python
# with stand-in FreeCAD modules.
import os
import subprocess
import sys
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = textwrap.dedent("""
    import sys, types
    sys.path.insert(0, ROOT)
    fc = types.ModuleType("FreeCAD")
    fc.Vector = lambda *a: a
    fc.GuiUp = False
    fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d)
    sys.modules["FreeCAD"] = fc
    sys.modules["Part"] = types.ModuleType("Part")
    from agentlink.families import strength as S

    plain = {"holds": [{"faces": "bottom", "kind": "fixed"}], "loads": [{"kind": "force", "faces": "top", "force": [0, 0, -100]}, {"kind": "gravity", "gravity": [0, 0, -1]}]}
    why = S.fem_route_why(plain, {})
    assert why is not None and "not here" in why, why  # no FEM tools in this Python

    for k in ("ObjectsFem", "femtools", "femtools.ccxtools", "femmesh", "femmesh.gmshtools"):
        sys.modules[k] = types.ModuleType(k)
    assert S.fem_route_why(plain, {}) is None
    assert "nonlinear" in S.fem_route_why(plain, {"nonlinear": True})
    assert "fea_parts" in S.fem_route_why(dict(plain, parts=[{}]), {})
    assert "fea_refine" in S.fem_route_why(dict(plain, refine=[{}]), {})
    assert "pinned" in S.fem_route_why(dict(plain, holds=[{"faces": "x", "kind": "pinned"}]), {})
    assert "spin" in S.fem_route_why(dict(plain, loads=[{"kind": "spin", "spin": 100}]), {})
    # A second setup says what it kept or dropped; an identical hold or load is spotted.
    h = {"faces": "bottom", "kind": "fixed"}
    ld = {"kind": "force", "faces": "top", "force": [0, 0, -100]}
    assert S._same_in(dict(ld), [ld]) and not S._same_in(dict(ld, force=[0, 0, -50]), [ld])
    assert S._same_in({"kind": "fixed", "faces": "bottom"}, [h])
    old = {"body": "Pad", "holds": [h], "loads": [ld]}
    kept = S._setup_said(old, True, False)["kept"]
    assert (kept["holds"], kept["loads"]) == (1, 1), kept
    dropped = S._setup_said(old, False, True)["dropped"]
    assert dropped["loads"] == [ld] and dropped["why"] == "reset: true", dropped
    assert S._setup_said(old, False, False)["dropped"]["why"] == "the study was on Pad"
    assert S._setup_said({}, True, False) == {}
    # Holds and loads whose face query matches nothing now are named.
    def pick(shape, q, what):
        if q.get("z") == 20:
            raise ValueError("no flat face")
        return [("Face5", None)]
    st = {"holds": [{"faces": {"normal": [0, 0, -1], "z": 0}, "kind": "fixed"}],
          "loads": [{"kind": "force", "faces": {"normal": [0, 0, 1], "z": 20}, "force": [0, 0, -100]}, {"kind": "gravity", "gravity": [0, 0, -1]}]}
    lost = S.unmatched(st, None, pick)
    assert lost == ["Load 1: no face at z = 20 facing +Z now; the part changed? fea_load it again (replace: true), or clear: true."], lost
    assert S.unmatched(dict(st, loads=st["loads"][1:]), None, pick) == []
    assert S._query_words({"faces": ["Face6"]}) == "Face6"
    assert S._query_words({"near": [1, 2, 3], "normal": [0.3, 0, 1]}) == "facing [0.3, 0, 1] near [1, 2, 3]"
    # CalculiX's own lines, each with what to do next.
    assert "body_check" in S.ccx_hint("*ERROR in calinput: no material was assigned to element 12")
    assert "equilibrium" in S.ccx_hint("*ERROR: too many cutbacks\\n best solution and residuals are in the frd file")
    assert S.ccx_hint("Job finished") == ""
    # Self weight: FreeCAD 1.1's GravityAcceleration and GravityDirection, Gravity_x/_y/_z before it.
    class Vec:
        def __init__(self, *a):
            a = a[0] if len(a) == 1 else a
            self.x, self.y, self.z = (a.x, a.y, a.z) if hasattr(a, "x") else a
        @property
        def Length(self):
            return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5
        def normalize(self):
            n = self.Length
            self.x, self.y, self.z = self.x / n, self.y / n, self.z / n
            return self
    class Qty:
        def __init__(self, v):
            self.v = v
        def __mul__(self, k):
            return Qty(self.v * k)
    S.V = Vec
    new = types.SimpleNamespace(PropertiesList=["GravityAcceleration", "GravityDirection"], GravityAcceleration=Qty(9806.65), GravityDirection=None)
    S.self_weight(new, [0, 3, -4])
    assert abs(new.GravityAcceleration.v - 9806.65 * 5) < 1e-6, new.GravityAcceleration.v
    assert (new.GravityDirection.x, round(new.GravityDirection.y, 6), round(new.GravityDirection.z, 6)) == (0, 0.6, -0.8)
    assert not hasattr(new, "Gravity_x")
    before = types.SimpleNamespace(PropertiesList=["Gravity_x", "Gravity_y", "Gravity_z"])
    S.self_weight(before, [0, 0, -2])
    assert (before.Gravity_x, before.Gravity_y, before.Gravity_z) == (0, 0, -2)
    # A mesher run bounded: FreeCAD 1.1's QProcess tools, and create_mesh() before it.
    class Proc:
        ProcessState = types.SimpleNamespace(NotRunning=0)
        def __init__(self, done, state=0):
            self.done, self._state, self.killed = done, state, False
        def waitForFinished(self, ms):
            self.ms = ms
            return self.done
        def state(self):
            return self._state
        def kill(self):
            self.killed = True
        def errorString(self):
            return "no such file"
        def readAllStandardError(self):
            return types.SimpleNamespace(data=lambda: b"Warning : thin\\n")
    class Mesher:
        def __init__(self, proc):
            self.process, self.steps = proc, []
        def prepare(self):
            self.steps.append("prepare")
        def compute(self):
            self.steps.append("compute")
    t = Mesher(Proc(True))
    assert S.gmsh_run(t, 7) == "Warning : thin" and t.steps == ["prepare", "compute"] and t.process.ms == 7000
    t = Mesher(Proc(False, state=2))
    try:
        S.gmsh_run(t, 1)
        raise SystemExit("a mesher still running at the timeout was not refused")
    except S.ToolError as e:
        assert "took over 1 s" in e.message and "fea_setup { mesh }" in e.message and t.process.killed, e.message
    try:
        S.gmsh_run(Mesher(Proc(False, state=0)), 1, "Netgen")
        raise SystemExit("a mesher that never started was not reported")
    except RuntimeError as e:
        assert "Netgen did not run (no such file)" in str(e), e
    assert S.gmsh_run(types.SimpleNamespace(create_mesh=lambda: "Error : bad"), 5) == "Error : bad"
    print("OK")
""")


class FemRoute(unittest.TestCase):
    def test_which_route(self):
        r = subprocess.run([sys.executable, "-c", f"ROOT = {ROOT!r}\n" + SCRIPT], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["OK"], r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

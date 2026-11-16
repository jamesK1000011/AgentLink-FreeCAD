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
    print("OK")
""")


class FemRoute(unittest.TestCase):
    def test_which_route(self):
        r = subprocess.run([sys.executable, "-c", f"ROOT = {ROOT!r}\n" + SCRIPT], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["OK"], r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

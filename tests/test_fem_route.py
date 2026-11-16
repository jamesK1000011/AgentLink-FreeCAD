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
    print("OK")
""")


class FemRoute(unittest.TestCase):
    def test_which_route(self):
        r = subprocess.run([sys.executable, "-c", f"ROOT = {ROOT!r}\n" + SCRIPT], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["OK"], r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

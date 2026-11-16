# SPDX-License-Identifier: LGPL-2.1-or-later
# glTF, Collada and 3DS come in through FreeCAD's own importers first; Agent
# Link's readers (meshformats) only where those are not here or read
# nothing, saying why. In a separate Python with stand-in FreeCAD modules.
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
    from agentlink.families import doc as D

    class Doc:
        Name = "Scene"
        def __init__(self):
            self.Objects = []
    d = Doc()

    imp = types.ModuleType("Import")
    def insert(p, name):
        d.Objects.append(types.SimpleNamespace(Name="Gear"))
    imp.insert = insert
    sys.modules["Import"] = imp
    made, why = D.core_scene(d, "gear.glb", "gltf", set())
    assert [o.Name for o in made] == ["Gear"] and why is None, (made, why)

    pkg = types.ModuleType("importers")
    dae = types.ModuleType("importers.importDAE")
    def no_collada(p, name):
        raise ImportError("pycollada is not installed")
    dae.insert = no_collada
    sys.modules["importers"] = pkg
    sys.modules["importers.importDAE"] = dae
    made, why = D.core_scene(d, "part.dae", "dae", {"Gear"})
    assert made == [] and "pycollada" in why, why

    made, why = D.core_scene(d, "part.3ds", "3ds", {"Gear"})
    assert made == [] and "not in this FreeCAD" in why, why
    print("OK")
""")

# FreeCAD's OpenSCAD code in the window: its search for the OpenSCAD program
# (Finder through AppleScript on a Mac, no time limit) never runs, under
# either name the module loads by; its modules load with FreeCAD.GuiUp as it
# truly is and run with their own gui switches off; a CSG file's words that
# need the program are found before anything is read.
SCAD = textwrap.dedent("""
    import os, sys, tempfile, types
    sys.path.insert(0, ROOT)
    mod = tempfile.mkdtemp()
    os.makedirs(os.path.join(mod, "OpenSCAD"))
    with open(os.path.join(mod, "OpenSCAD", "OpenSCADUtils.py"), "w") as f:
        f.write("import FreeCAD\\nLOADED_UP = FreeCAD.GuiUp\\n"
                "def searchforopenscadexe():\\n    raise RuntimeError('asked Finder')\\n"
                "def getopenscadexe():\\n    return searchforopenscadexe()\\n")
    with open(os.path.join(mod, "OpenSCAD", "importCSG.py"), "w") as f:
        f.write("import FreeCAD\\nfrom OpenSCADUtils import *\\ngui = bool(FreeCAD.GuiUp)\\nprintverbose = True\\n"
                "original_root_objects = []\\nSEEN = []\\n"
                "def insert(p, name):\\n    original_root_objects.append(name)\\n    SEEN.append((gui, printverbose, FreeCAD.GuiUp))\\n")
    # as FreeCAD does: the Mod folder and each workbench's own folder
    sys.path[:0] = [mod, os.path.join(mod, "OpenSCAD")]

    fc = types.ModuleType("FreeCAD")
    fc.Vector = lambda *a: a
    fc.GuiUp = True
    fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d, SetString=lambda k, v: None)
    fc.Console = types.SimpleNamespace(PrintLog=lambda *a: None)
    sys.modules["FreeCAD"] = fc
    sys.modules["Part"] = types.ModuleType("Part")
    from agentlink.families import openscad as S

    S.exe = lambda: None  # no OpenSCAD on this computer
    assert "OpenSCADUtils" not in sys.modules, "the guard must not load FreeCAD's module by itself"

    # whoever loads it, under either name, gets the plain search
    import OpenSCADUtils
    assert OpenSCADUtils.getopenscadexe() is None
    import OpenSCAD.OpenSCADUtils as twin
    assert twin is not OpenSCADUtils and twin.getopenscadexe() is None
    assert OpenSCADUtils.__file__.endswith("OpenSCADUtils.py")

    # a copy loaded before the guard was there is set too
    twin.searchforopenscadexe = lambda: 1 / 0
    S.guard_search()
    assert twin.getopenscadexe() is None
    assert sum(isinstance(f, S._SearchGuard) for f in sys.meta_path) == 1

    # the workbench brought up from here: the search is plain first
    from agentlink import echo
    del sys.modules["OpenSCADUtils"]
    echo.bench_ready("PartWorkbench")
    assert "OpenSCADUtils" not in sys.modules
    echo.bench_ready("OpenSCADWorkbench")
    assert sys.modules["OpenSCADUtils"].LOADED_UP is True
    assert sys.modules["OpenSCADUtils"].searchforopenscadexe() is None

    # the reader: loaded as the window has it, run with its switches off, then as it was
    import importCSG
    assert importCSG.gui is True
    with S.console_mode():
        importCSG.insert("x.csg", "Doc")
    assert importCSG.SEEN == [(False, False, False)], importCSG.SEEN
    assert importCSG.gui is True and importCSG.printverbose is True and fc.GuiUp is True
    try:
        with S.console_mode():
            raise KeyError("x")
    except KeyError:
        pass
    assert importCSG.gui is True and fc.GuiUp is True

    # what only the program can work out, strings and comments apart
    assert S.csg_needs('group() { cube(size = [1, 2, 3], center = false); }') == []
    assert S.csg_needs('// hull() of old\\nimport(file = "text (1).stl", layer = "hull(");') == []
    assert S.csg_needs('minkowski() { hull () { sphere(r = 1); } }\\ntext(text = "a");hull(){}') == ["minkowski", "hull", "text"]
    assert S.csg_needs('multmatrix([[1, 0, 0, 0]]) { context(); }') == []
    print("OK")
""")


class CoreReaders(unittest.TestCase):
    def test_scad_never_asks_finder(self):
        r = subprocess.run([sys.executable, "-c", f"ROOT = {ROOT!r}\n" + SCAD], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["OK"], r.stderr[-2000:])

    def test_core_first_then_why_not(self):
        r = subprocess.run([sys.executable, "-c", f"ROOT = {ROOT!r}\n" + SCRIPT], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["OK"], r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

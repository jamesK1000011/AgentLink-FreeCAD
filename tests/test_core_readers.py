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


class CoreReaders(unittest.TestCase):
    def test_core_first_then_why_not(self):
        r = subprocess.run([sys.executable, "-c", f"ROOT = {ROOT!r}\n" + SCRIPT], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["OK"], r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
# Mass and materials belong to the add-on that owns them when it is
# installed: measure_mass asks its "mass_properties" service, material_set
# and material_clear its "material_set" service; without one (or for a
# material it does not keep) Agent Link answers itself. Run in a separate
# Python with stand-in FreeCAD and Part modules, so no other test sees them.
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
    from agentlink import hooks
    from agentlink.families import measure, material
    from agentlink.protocol import ToolError

    s = types.SimpleNamespace()
    assert measure._deferred(s, "mass_properties", {"body": "Lid"}) is None
    assert material._owner("doc", ["Lid"], "petg") is None

    seen = []
    hooks.provide("mass_properties", lambda sess, a: (seen.append(a), {"bodies": [{"body": a["body"], "mass": 12.5}]})[1])
    got = measure._deferred(s, "mass_properties", {"body": "Lid"})
    assert got["bodies"][0]["mass"] == 12.5 and "add-on" in got["from"] and seen == [{"body": "Lid"}], got

    class Refused(Exception):
        code, message = "not_found", "No body named Lid."
    def refuse(sess, a):
        raise Refused()
    hooks.provide("mass_properties", refuse)
    try:
        measure._deferred(s, "mass_properties", {"body": "Lid"})
        raise SystemExit("a refusal should come through")
    except ToolError as e:
        assert e.code == "not_found"
    hooks.provide("mass_properties", lambda sess, a: 1 / 0)
    assert measure._deferred(s, "mass_properties", {}) is None  # its own failure: answered here

    hooks.provide("material_set", lambda doc, bodies, m: {"materials": {b: m for b in bodies}, "freecadMaterial": {}})
    got = material._owner("doc", ["Lid"], "petg")
    assert got["materials"] == {"Lid": "petg"} and "material_set" in got["from"], got
    def unknown(doc, bodies, m):
        raise ValueError("material: one of pla, petg")
    hooks.provide("material_set", unknown)
    assert material._owner("doc", ["Lid"], "custom:oak") is None
    print("OK")
""")


class OwnerServices(unittest.TestCase):
    def test_defer_and_fall_back(self):
        r = subprocess.run([sys.executable, "-c", f"ROOT = {ROOT!r}\n" + SCRIPT], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip().splitlines()[-1:] , ["OK"], r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

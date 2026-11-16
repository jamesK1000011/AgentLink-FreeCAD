# SPDX-License-Identifier: LGPL-2.1-or-later
# body_check reads FreeCAD's own Check Geometry (shape.check with its BOP
# checks) first and keeps only its extras on top. With stand-in FreeCAD and
# Part modules where FreeCAD is not importable.
import importlib
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _geometry():
    """agentlink.geometry for these tests: the one already loaded when there
    is one (a run with FreeCAD, where the tools hold it), else a copy loaded
    over stand-ins and put away again. Loading a second copy beside a loaded
    one left it as the package's attribute while agentlink.tools kept the
    first: a later test that patched "agentlink.geometry" patched a module
    no tool used (test_live_findings' stats count read 0 in a run of every
    file in one FreeCAD)."""
    if "agentlink.geometry" in sys.modules:
        return sys.modules["agentlink.geometry"]
    had = {k: sys.modules.get(k) for k in ("FreeCAD", "Part")}
    try:
        import FreeCAD  # noqa: F401

        return importlib.import_module("agentlink.geometry")  # the real one: it stays
    except ImportError:
        sys.modules["FreeCAD"] = types.SimpleNamespace(Vector=lambda *a: a)
        sys.modules["Part"] = types.SimpleNamespace()
    try:
        return importlib.import_module("agentlink.geometry")
    finally:
        # the copy made over stand-ins is nobody else's: out of sys.modules
        # and off the package, so the next import loads a real one
        sys.modules.pop("agentlink.geometry", None)
        pkg = sys.modules.get("agentlink")
        if pkg is not None and "geometry" in vars(pkg):
            delattr(pkg, "geometry")
        for k, v in had.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


geo = _geometry()


class Shape:
    def __init__(self, err=None):
        self.err = err

    def check(self, bop):
        assert bop is True
        if self.err:
            raise ValueError(self.err)


class CoreCheck(unittest.TestCase):
    def test_sound(self):
        self.assertEqual(geo.core_check(Shape()), (True, []))

    def test_problems_named(self):
        ok, said = geo.core_check(Shape("BOPAlgo SelfIntersect\nFace3: BRepCheck_NotClosed"))
        self.assertFalse(ok)
        self.assertEqual(said, ["BOPAlgo SelfIntersect", "Face3: BRepCheck_NotClosed"])

    def test_no_check(self):
        self.assertEqual(geo.core_check(object()), (None, []))


if __name__ == "__main__":
    unittest.main()

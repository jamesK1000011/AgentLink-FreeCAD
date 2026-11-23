# SPDX-License-Identifier: LGPL-2.1-or-later
"""Open fault 3 (tool-research 2.3, T3): sketch_edit fillet deleted the
corner's constraints, bound ones too, with no word. The fillet now keeps
the corner (createCorner), and its answer names any named constraint that
is gone. No FreeCAD: the helpers are read from the source."""
import ast
import os
import unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "agentlink", "families", "sketch.py")
NAMES = ("_FILLET_BEFORE", "_named", "fillet", "fillet_made")


def helpers():
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    body = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in NAMES)
            or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) in NAMES)]
    ns = {}
    exec(compile(ast.Module(body, []), "sketch.py", "exec"), ns)
    return ns


class C:
    def __init__(self, name=""):
        self.Name = name


class G:
    def __init__(self, t):
        self.TypeId = t


class Sk:
    def __init__(self, lose=()):
        self.Constraints = [C("r_width"), C("r_height"), C("")]
        self.Geometry = [G("Part::GeomLineSegment")] * 4
        self.lose, self.calls = set(lose), []

    def fillet(self, *a):
        self.calls.append(a)
        self.Geometry = self.Geometry + [G("Part::GeomArcOfCircle"), G("Part::GeomPoint")]
        self.Constraints = [c for c in self.Constraints if c.Name not in self.lose]


class Fillet(unittest.TestCase):
    def test_the_corner_is_kept(self):
        ns, sk = helpers(), Sk()
        ns["fillet"](sk, False, 0, 2, 3.0)
        self.assertEqual(sk.calls, [(0, 2, 3.0, True, True)])  # trim, createCorner
        ns["fillet"](sk, True, 0, 1, (0, 0), (1, 1), 2.0)
        self.assertEqual(sk.calls[-1], (0, 1, (0, 0), (1, 1), 2.0, True, True, True))

    def test_answer_names_the_arc_and_the_kept_point(self):
        ns, sk = helpers(), Sk()
        ns["fillet"](sk, False, 0, 2, 3.0)
        self.assertEqual(ns["fillet_made"](sk, 4), "arc 4; corner kept as point 5")

    def test_answer_names_lost_constraints(self):
        ns, sk = helpers(), Sk(lose={"r_width"})
        ns["fillet"](sk, False, 0, 2, 3.0)
        said = ns["fillet_made"](sk, 4)
        self.assertIn("named constraints gone: r_width", said)
        self.assertNotIn("r_height", said)


if __name__ == "__main__":
    unittest.main()

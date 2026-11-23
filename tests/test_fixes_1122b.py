"""22 Nov fixes (owner's items 2 and 3): doc_new first when the document in
front is the person's; a pocket that cut nothing names the side."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import options  # noqa: E402


class TheirsFirst(unittest.TestCase):
    def sess(self, mine):
        doc = types.SimpleNamespace(Name="Doc", Label="Bracket")
        server = types.SimpleNamespace(tools={"doc_new": None})
        return types.SimpleNamespace(doc=doc, agent_docs={"Doc"} if mine else set()), server

    def test_person_doc_gets_doc_new_first(self):
        s, server = self.sess(False)
        o = options.theirs_first(s, server)
        self.assertEqual((o["n"], o["tool"], o["ask"]), (1, "doc_new", [{"arg": "name"}]))
        self.assertIn("Bracket", o["why"])

    def test_agent_doc_gets_none(self):
        s, server = self.sess(True)
        self.assertIsNone(options.theirs_first(s, server))

    def test_no_doc_new_tool(self):
        s, _ = self.sess(False)
        self.assertIsNone(options.theirs_first(s, types.SimpleNamespace(tools={})))


class V:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def __sub__(self, o):
        return V(self.x - o.x, self.y - o.y, self.z - o.z)

    def dot(self, o):
        return self.x * o.x + self.y * o.y + self.z * o.z


class CutSide(unittest.TestCase):
    def setUp(self):
        fc = types.ModuleType("FreeCAD")
        fc.Vector = V
        names = ("FreeCAD", "Part", "agentlink.geometry", "agentlink.families.picks", "agentlink.families.pd_common")
        self._old = {n: sys.modules.get(n) for n in names}
        sys.modules["FreeCAD"] = fc
        sys.modules["Part"] = types.ModuleType("Part")
        self.addCleanup(self.restore)
        try:
            from agentlink.families import pd_common
        except ImportError as e:  # another FreeCAD-only import
            self.skipTest(f"needs FreeCAD: {e}")
        self.pd = pd_common

    def restore(self):
        # Do not leave the stand-ins for the other tests.
        for n, m in self._old.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m

    def words(self, body_z, reversed_):
        rot = types.SimpleNamespace(multVec=lambda v: V(0, 0, 1))
        sk = types.SimpleNamespace(Label="Sketch001", Placement=types.SimpleNamespace(Rotation=rot, Base=V(0, 0, 0)))
        feat = types.SimpleNamespace(Profile=[sk, ["Face1"]], Reversed=reversed_)
        bb = types.SimpleNamespace(XMin=-5, XMax=5, YMin=-5, YMax=5, ZMin=body_z - 2, ZMax=body_z + 2)
        body = types.SimpleNamespace(Shape=types.SimpleNamespace(BoundBox=bb))
        return self.pd.cut_side_words(feat, body)

    def test_body_on_normal_side_says_reversed_true(self):
        w = self.words(10, False)
        self.assertIn("+z", w)
        self.assertIn("reversed: true", w)

    def test_already_reversed_says_false(self):
        self.assertIn("reversed: false", self.words(-10, True))

    def test_cut_toward_body_says_overlap(self):
        self.assertIn("overlaps", self.words(-10, False))


if __name__ == "__main__":
    unittest.main()

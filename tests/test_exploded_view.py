# SPDX-License-Identifier: LGPL-2.1-or-later
# asm_explode makes FreeCAD's own Exploded View (a Normal move step a part,
# applied by it) and moves placements itself only where that cannot be
# made, leaving nothing half-made behind. In a separate Python with
# stand-in FreeCAD modules.
import os
import subprocess
import sys
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = textwrap.dedent("""
    import sys, types

    sys.path.insert(0, ROOT)

    class Vec:
        def __init__(self, x=0, y=0, z=0):
            if isinstance(x, Vec):
                x, y, z = x.x, x.y, x.z
            self.x, self.y, self.z = float(x), float(y), float(z)
        def __add__(self, o):
            return Vec(self.x + o.x, self.y + o.y, self.z + o.z)
        def __sub__(self, o):
            return Vec(self.x - o.x, self.y - o.y, self.z - o.z)
        @property
        def Length(self):
            return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5

    class Plc:
        def __init__(self, base=None, rot=None):
            self.Base, self.Rotation = Vec(base or Vec()), rot

    fc = types.ModuleType("FreeCAD")
    fc.Vector, fc.Placement, fc.Rotation = Vec, Plc, (lambda *a: "rot")
    fc.GuiUp = False
    fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d)
    sys.modules["FreeCAD"] = fc
    sys.modules["Part"] = types.ModuleType("Part")
    sys.modules["JointObject"] = types.SimpleNamespace(JointTypes=["Fixed", "Revolute"])
    UA = sys.modules["UtilsAssembly"] = types.ModuleType("UtilsAssembly")
    from agentlink.families import assembly_more as AM

    class Doc:
        def __init__(self):
            self.objs = {}
        def removeObject(self, n):
            self.objs.pop(n)

    D = Doc()

    class Obj:
        n = 0
        def __init__(self, name):
            Obj.n += 1
            self.Name, self.Label, self.Document = f"{name}{Obj.n}", name, D
            self.Placement = Plc(Vec())
            D.objs[self.Name] = self
        def newObject(self, t, name):
            return Obj(name)

    asm = Obj("Assembly")
    lid, base = Obj("Lid"), Obj("Base")
    moves = {lid.Name: Vec(0, 0, 10), base.Name: Vec(0, 0, -5)}

    # Not here: placements are left to asm_explode, nothing made.
    n0 = len(D.objs)
    view, why = AM._exploded_view(asm, [lid, base], moves)
    assert view is None and "not here" in why and len(D.objs) == n0, why

    CV = types.ModuleType("CommandCreateView")
    class ExplodedView:
        def __init__(self, o):
            o.Proxy = self
        def saveAssemblyAndExplode(self, v):
            for st in v.Group:
                part = D.objs[st.References[1][0].rstrip(".")]
                part.Placement = Plc(part.Placement.Base + st.MovementTransform.Base)
    class ExplodedViewStep:
        def __init__(self, o, kind=0):
            o.Proxy, o.MoveType = self, ("Normal", "Radial")[kind]
    CV.ExplodedView, CV.ExplodedViewStep = ExplodedView, ExplodedViewStep
    UA.getViewGroup = lambda a: Obj("Views")
    sys.modules["CommandCreateView"] = CV

    view, why = AM._exploded_view(asm, [lid, base], moves)
    assert why is None and view.Label == "Exploded View", why
    assert [st.MoveType for st in view.Group] == ["Normal", "Normal"]
    assert (lid.Placement.Base.z, base.Placement.Base.z) == (10.0, -5.0)

    # In the window: each object gets its view provider before its references
    # are set, and applying a step draws through it (the live failure was a
    # ViewObject with no proxy: 'NoneType' object has no attribute 'redrawLines').
    order = []
    class VO:
        def __init__(self, owner):
            self.owner, self.Proxy = owner, None
    class VPView:
        def __init__(self, vo):
            vo.Proxy = self
            order.append(("vp", vo.owner.Label))
    class VPStep:
        def __init__(self, vo):
            vo.Proxy = self
            order.append(("vp", vo.owner.Label))
        def redrawLines(self, move, positions):
            order.append(("lines", move.Label))
    CV.ViewProviderExplodedView, CV.ViewProviderExplodedViewStep = VPView, VPStep
    real_new = Obj.newObject
    def windowed(self, t, name):
        o = real_new(self, t, name)
        o.ViewObject = VO(o)
        return o
    Obj.newObject = windowed
    real_apply = ExplodedView.saveAssemblyAndExplode
    def apply_drawing(self, v):
        for st in v.Group:
            assert st.References, "references set after the view provider"
            st.ViewObject.Proxy.redrawLines(st, [])
        real_apply(self, v)
    ExplodedView.saveAssemblyAndExplode = apply_drawing
    real_setattr = Obj.__setattr__
    def watch(self, k, v):
        if k == "References":
            assert self.ViewObject.Proxy is not None, "References set before the view provider"
        real_setattr(self, k, v)
    Obj.__setattr__ = watch
    lid.Placement, base.Placement = Plc(Vec()), Plc(Vec())
    view, why = AM._exploded_view(asm, [lid, base], moves)
    assert why is None, why
    assert order[0] == ("vp", "Exploded View") and order.count(("lines", "Move")) == 2, order
    Obj.__setattr__ = real_setattr
    Obj.newObject = real_new
    ExplodedView.saveAssemblyAndExplode = real_apply

    # A step it would not take: put back, and what it made removed.
    ExplodedView.saveAssemblyAndExplode = lambda self, v: None
    n0 = len(D.objs)
    view, why = AM._exploded_view(asm, [lid], {lid.Name: Vec(0, 0, 10)})
    assert view is None and "did not move" in why and len(D.objs) == n0 + 1, (why, len(D.objs), n0)  # the view group stays
    assert lid.Placement.Base.z == 10.0
    print("OK")
""")


class ExplodedViewTest(unittest.TestCase):
    def test_freecads_view_first(self):
        r = subprocess.run([sys.executable, "-c", f"ROOT = {ROOT!r}\n" + SCRIPT], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["OK"], r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

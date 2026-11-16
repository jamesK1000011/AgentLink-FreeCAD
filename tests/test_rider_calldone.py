# SPDX-License-Identifier: LGPL-2.1-or-later
# Hooks for add-ons that follow a job with the person: the rider line (any
# number of providers, each line capped, only while active), call_done with
# whether the call changed the document, and the AGENTLINK_AS_USER test flag.
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import annotate, hooks  # noqa: E402
from agentlink.protocol import Server, Tool, ToolError  # noqa: E402


class Sess:
    def __init__(self):
        self.tx = 0
        self.doc = object()
        self.by = hooks.AGENT


def server(session=None):
    def refuse(a):
        raise ToolError("not_found", "nothing here")

    def change(a):
        session.tx += 1
        return {"made": "Pad"}

    def seen(a):
        return {"by": session.by if session is not None else None}

    tools = [Tool("look", "Look.", {"type": "object", "properties": {}}, lambda a: {"said": "hi"}),
             Tool("make", "Make.", {"type": "object", "properties": {}}, change, changes=True),
             Tool("who", "Who.", {"type": "object", "properties": {}}, seen),
             Tool("refuse", "Refuse.", {"type": "object", "properties": {}}, refuse)]
    s = Server("t", "0", tools, "hi")
    s.session = session
    return s


def answer(s, name="look"):
    r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {}}})
    return json.loads(r["result"]["content"][0]["text"])


class Base(unittest.TestCase):
    def setUp(self):
        self.state = hooks.saved()
        hooks.reset()
        self.env = os.environ.pop(hooks.AS_USER_ENV, None)

    def tearDown(self):
        hooks.restore(self.state)
        os.environ.pop(hooks.AS_USER_ENV, None)
        if self.env is not None:
            os.environ[hooks.AS_USER_ENV] = self.env


class Rider(Base):
    def test_no_provider_no_rider(self):
        self.assertNotIn("rider", answer(server()))

    def test_several_providers_join_while_active(self):
        state = {"on": True}
        hooks.register_rider("a", lambda tool: "lesson: step 3/7 passed" if state["on"] else None)
        hooks.register_rider("b", lambda tool: f"watch: {tool}")
        got = answer(server())
        self.assertEqual(got["rider"], "lesson: step 3/7 passed · watch: look")
        self.assertEqual(got["said"], "hi")
        state["on"] = False
        self.assertEqual(answer(server())["rider"], "watch: look")
        hooks.unregister_rider("b")
        self.assertNotIn("rider", answer(server()))

    def test_rider_is_not_the_notice(self):
        hooks.provide("notice", lambda: "A screenshot.")
        hooks.register_rider("a", lambda tool: "lesson: step 1/5 pending")
        got = answer(server())
        self.assertEqual((got["notice"], got["rider"]), ("A screenshot.", "lesson: step 1/5 pending"))

    def test_capped_each_and_whole(self):
        for k in "abcd":
            hooks.register_rider(k, lambda tool, k=k: k * 300)
        line = answer(server())["rider"]
        self.assertLessEqual(len(line), hooks.RIDER_MAX)
        self.assertTrue(line.startswith("a" * (hooks.RIDER_EACH - 1) + "…"))

    def test_same_owner_replaces_and_raising_skipped(self):
        hooks.register_rider("a", lambda tool: "one")
        hooks.register_rider("a", lambda tool: "two")

        def boom(tool):
            raise RuntimeError("boom")

        hooks.register_rider("b", boom)
        got = answer(server(), "refuse")
        self.assertEqual(got["rider"], "two")
        self.assertIn("error", got)

    def test_saved_and_restored(self):
        hooks.register_rider("a", lambda tool: "x")
        st = hooks.saved()
        hooks.reset()
        self.assertIsNone(hooks.rider_line())
        hooks.restore(st)
        self.assertEqual(hooks.rider_line(), "x")


class CallDone(Base):
    def setUp(self):
        super().setUp()
        self.seen = []
        hooks.on("call_done", lambda s, tool, ok, changed: self.seen.append((tool, ok, changed, s.by)))

    def test_each_call_with_changed(self):
        sess = Sess()
        s = server(sess)
        answer(s, "look")
        answer(s, "make")
        answer(s, "refuse")
        answer(s, "nope")  # no such tool: nothing to tell
        self.assertEqual(self.seen, [("look", True, False, "agent"), ("make", True, True, "agent"), ("refuse", False, False, "agent")])

    def test_a_new_document_counts_as_changed(self):
        sess = Sess()
        s = server(sess)
        s.tools["look"].fn = lambda a: setattr(sess, "doc", object()) or {}
        answer(s, "look")
        self.assertEqual(self.seen[-1][2], True)

    def test_without_a_session_nothing(self):
        answer(server(None), "look")
        self.assertEqual(self.seen, [])

    def test_the_persons_panel_click(self):
        sess = Sess()
        s = server(sess)
        with hooks.as_person(sess):
            answer(s, "make")
        self.assertEqual(self.seen, [("make", True, True, "person")])

    def test_before_the_rider_is_asked(self):
        sess = Sess()
        order = []
        hooks.on("call_done", lambda *a: order.append("done"))
        hooks.register_rider("a", lambda tool: order.append("rider"))
        answer(server(sess), "look")
        self.assertEqual(order, ["done", "rider"])


class AsUser(Base):
    def test_off_by_default(self):
        sess = Sess()
        self.assertFalse(hooks.as_user())
        self.assertEqual(answer(server(sess), "who")["by"], "agent")

    def test_on_the_agents_calls_are_the_persons(self):
        os.environ[hooks.AS_USER_ENV] = "1"
        sess = Sess()
        seen = []
        hooks.on("call_done", lambda s, *a: seen.append(s.by))
        self.assertEqual(answer(server(sess), "who")["by"], "person")
        self.assertEqual(seen, ["person"])
        self.assertEqual(sess.by, "agent")  # back after the call

    def test_other_values_are_off(self):
        os.environ[hooks.AS_USER_ENV] = "yes"
        self.assertEqual(answer(server(Sess()), "who")["by"], "agent")

    def test_documented_as_test_only(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "docs", "hooks.md"), encoding="utf-8") as f:
            doc = f.read()
        self.assertIn("AGENTLINK_AS_USER", doc)
        self.assertIn("tests only", doc)


# ---- the 3D badge: big enough to read, where the person can see it ----------------

class V:
    def __init__(self, *p):
        self.x, self.y, self.z = p


class Square:
    """A 10 × 10 face at z = 0 in two-by-two-mm cells (two triangles each)."""
    CenterOfMass = V(5, 5, 0)

    def tessellate(self, tol):
        pts, tris = [], []
        for j in range(6):
            for i in range(6):
                pts.append(V(2 * i, 2 * j, 0))
        for j in range(5):
            for i in range(5):
                a = j * 6 + i
                tris += [(a, a + 1, a + 6), (a + 1, a + 7, a + 6)]
        return pts, tris


class View:
    """Screen = mm × 10; a screw (another object) covers x, y in 3..7 mm."""

    def __init__(self, cover=(3, 7)):
        self.cover = cover
        self.asked = 0

    def getSize(self):
        return (100, 100)

    def getPointOnScreen(self, p):
        x, y = (p.x, p.y) if hasattr(p, "x") else (p[0], p[1])
        return (x * 10, y * 10)

    def getObjectInfo(self, xy):
        self.asked += 1
        x, y = xy[0] / 10.0, xy[1] / 10.0
        lo, hi = self.cover
        if lo <= x <= hi and lo <= y <= hi:
            return {"Object": "Screw", "Component": "Face1"}
        if 0 <= x <= 10 and 0 <= y <= 10:
            return {"Object": "Pad", "Component": "Face6"}
        return None


class Badge(unittest.TestCase):
    def test_face_candidates_are_on_the_face_nearest_first(self):
        pts = annotate.candidates(Square(), "face")
        self.assertLessEqual(len(pts), annotate.BADGE_SAMPLES)
        d = [(p[0] - 5) ** 2 + (p[1] - 5) ** 2 for p in pts[:10]]
        self.assertEqual(d, sorted(d))
        self.assertTrue(all(0 <= p[0] <= 10 and 0 <= p[1] <= 10 for p in pts))

    def test_badge_not_under_the_screw(self):
        obj = types.SimpleNamespace(Name="Pad", InList=[])
        p = annotate.visible_point(View(), obj, "Face6", annotate.candidates(Square(), "face"))
        self.assertIsNotNone(p)
        self.assertFalse(3 <= p[0] <= 7 and 3 <= p[1] <= 7, p)
        # with room around it: the pixels BADGE_CLEAR away show the face too
        v = View()
        x, y = p[0] * 10, p[1] * 10
        for dx, dy in ((14, 0), (-14, 0), (0, 14), (0, -14)):
            self.assertEqual(v.getObjectInfo((x + dx, y + dy))["Component"], "Face6")

    def test_body_and_tip_names_count(self):
        pad = types.SimpleNamespace(Name="Pad")
        body = types.SimpleNamespace(Name="Body", Tip=pad, InList=[])
        obj = types.SimpleNamespace(Name="Pocket", InList=[body])
        self.assertEqual(annotate._names(obj), {"Pocket", "Body", "Pad"})

    def test_nothing_visible_none_and_picks_capped(self):
        obj = types.SimpleNamespace(Name="Pad", InList=[])
        v = View(cover=(-1, 11))
        self.assertIsNone(annotate.visible_point(v, obj, "Face6", annotate.candidates(Square(), "face")))
        self.assertLessEqual(v.asked, annotate.PICKS_MAX)
        self.assertIsNone(annotate.visible_point(None, obj, "Face6", [(1, 1, 0)]))

    def test_badge_drawn_at_visible_point_and_scaled(self):
        from test_overlay import FakeCoin, Node

        scene = Node("root")
        ann = annotate.Annotations(coin=FakeCoin(), scene=lambda: scene, view=View, ratio=lambda: 2.0)
        shape = types.SimpleNamespace(getElement=lambda n: Square())
        got = ann.light(types.SimpleNamespace(Name="Pad", Label="Pad", InList=[]), ["Face6"], owner="t", shape=shape, badge=3)
        self.assertEqual(got["lit"], ["Face6"])
        badge = scene.children[0].children[1]
        at = badge.children[1].translation
        self.assertFalse(3 <= at[0] <= 7 and 3 <= at[1] <= 7, at)
        font = badge.children[4]
        self.assertEqual(font.size, round(annotate.BADGE_FONT * 2))
        self.assertIn("Bold", font.name)
        self.assertEqual(badge.children[5].string, "  3")

    def test_without_a_view_the_nearest_point_on_the_face(self):
        from test_overlay import FakeCoin, Node

        scene = Node("root")
        ann = annotate.Annotations(coin=FakeCoin(), scene=lambda: scene)
        shape = types.SimpleNamespace(getElement=lambda n: Square())
        ann.light(types.SimpleNamespace(Name="Pad", Label="Pad"), ["Face6"], shape=shape, badge=1)
        at = scene.children[0].children[1].children[1].translation
        self.assertLess((at[0] - 5) ** 2 + (at[1] - 5) ** 2, 2.0)
        self.assertEqual(scene.children[0].children[1].children[4].size, annotate.BADGE_FONT)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
# The live echo's benches and buttons for add-ons' tools (longest match,
# COMMANDS, a bench not loaded), and the Review tab asking the reviewers
# add-ons registered — all without FreeCAD.
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import echo, hooks  # noqa: E402


class EchoDeclared(unittest.TestCase):
    def setUp(self):
        self.saved = (echo.SHOWN, dict(echo.PREFIX_NAME), list(echo.WORKBENCH), list(echo.PAGES),
                      dict(echo.COMMANDS), list(echo.COMMAND_FNS), set(echo.UNKNOWN_BENCHES), set(echo.NO_BUTTON))

    def tearDown(self):
        echo.SHOWN, names, wb, pages, cmds, fns, unknown, quiet = self.saved
        echo.NO_BUTTON.clear()
        echo.NO_BUTTON.update(quiet)
        echo.PREFIX_NAME.clear()
        echo.PREFIX_NAME.update(names)
        echo.WORKBENCH[:] = wb
        echo.PAGES[:] = pages
        echo.COMMANDS.clear()
        echo.COMMANDS.update(cmds)
        echo.COMMAND_FNS[:] = fns
        echo.UNKNOWN_BENCHES.clear()
        echo.UNKNOWN_BENCHES.update(unknown)

    def test_no_button_wins(self):
        echo.declare(types.SimpleNamespace(COMMANDS={"mine_": "Mine_Any", "mine_do": "Mine_Do"}, NO_BUTTON={"mine_do_quiet", "mine_peek_"},
                                           command_for=lambda n, a: "Mine_Fn"))
        self.assertIsNone(echo.command_for("mine_do_quiet", {}))  # exact name, though mine_do matches
        self.assertIsNone(echo.command_for("mine_peek_at", {}))   # prefix, though mine_ matches and command_for answers
        self.assertEqual(echo.command_for("mine_do", {}), "Mine_Fn")
        echo.declare(types.SimpleNamespace(NO_BUTTON=None))  # nothing declared: nothing changes
        self.assertEqual(echo.NO_BUTTON & {"mine_do_quiet", "mine_peek_"}, {"mine_do_quiet", "mine_peek_"})

    def test_longest_prefix_and_exact_names(self):
        echo.declare(types.SimpleNamespace(WORKBENCHES={"part_check": "MineWorkbench", "mine_": "MineWorkbench"}))
        self.assertEqual(echo._workbench_for("part_check"), "MineWorkbench")  # beats core's part_
        self.assertEqual(echo._workbench_for("part_boolean"), "PartWorkbench")
        self.assertEqual(echo._workbench_for("mine_do"), "MineWorkbench")
        self.assertIsNone(echo._workbench_for("session_state"))

    def test_core_prefix_kept(self):
        echo.declare(types.SimpleNamespace(WORKBENCHES={"part_": "MineWorkbench"}))
        self.assertEqual(echo._workbench_for("part_boolean"), "PartWorkbench")

    def test_bench_not_loaded(self):
        echo.declare(types.SimpleNamespace(WORKBENCHES={"mine_": "MineWorkbench"}))
        loaded = {"PartWorkbench": None, "PartDesignWorkbench": None}
        self.assertIsNone(echo.bench_to_switch("mine_do", loaded, "PartWorkbench"))
        self.assertIsNone(echo.bench_to_switch("mine_other", loaded, "PartWorkbench"))
        self.assertEqual(echo.UNKNOWN_BENCHES & {"MineWorkbench"}, {"MineWorkbench"})
        self.assertEqual(echo.bench_to_switch("pd_pad", loaded, "PartWorkbench"), "PartDesignWorkbench")
        self.assertIsNone(echo.bench_to_switch("pd_pad", loaded, "PartDesignWorkbench"))
        loaded["MineWorkbench"] = None
        self.assertEqual(echo.bench_to_switch("mine_do", loaded, "PartWorkbench"), "MineWorkbench")

    def test_commands(self):
        def by_kind(name, args):
            return {"bin": "Mine_Bin"}.get(args.get("kind")) if name == "mine_make" else None

        echo.declare(types.SimpleNamespace(COMMANDS={"mine_": "Mine_Any", "mine_do": "Mine_Do", "bim_wall": "Mine_Wall"}, command_for=by_kind))
        self.assertEqual(echo.command_for("mine_do", {}), "Mine_Do")
        self.assertEqual(echo.command_for("mine_do_more", {}), "Mine_Do")
        self.assertEqual(echo.command_for("mine_x", {}), "Mine_Any")
        self.assertEqual(echo.command_for("mine_make", {"kind": "bin"}), "Mine_Bin")
        self.assertEqual(echo.command_for("mine_make", {}), "Mine_Any")
        self.assertEqual(echo.command_for("bim_wall", {}), "BIM_Wall")  # core's own stays
        self.assertIsNone(echo.command_for("session_state", {}))
        echo.declare(types.SimpleNamespace(COMMANDS={"mine_do": "Other"}))
        self.assertEqual(echo.command_for("mine_do", {}), "Mine_Do")  # first declared stays

    def test_argument_button_wins(self):
        """A family with both: its command_for(name, args) answers first, even
        over an exact COMMANDS entry; None falls back to COMMANDS."""
        def by_args(name, args):
            if name == "fit" and args.get("calibrate"):
                return "Make_FitCalibrate"
            if name == "setup" and args.get("op") in ("set", "remove"):
                return "Make_Setup" + args["op"].title()
            if name == "gen_part":
                return {"bin": "Parts_Bin"}.get(args.get("generator"))
            return None

        echo.declare(types.SimpleNamespace(COMMANDS={"fit": "Make_Fit", "setup": "Make_Setups", "gen_": "Parts_Any"}, command_for=by_args))
        self.assertEqual(echo.command_for("fit", {"calibrate": True}), "Make_FitCalibrate")
        self.assertEqual(echo.command_for("fit", {}), "Make_Fit")
        self.assertEqual(echo.command_for("setup", {"op": "remove"}), "Make_SetupRemove")
        self.assertEqual(echo.command_for("setup", {"op": "list"}), "Make_Setups")
        self.assertEqual(echo.command_for("gen_part", {"generator": "bin"}), "Parts_Bin")
        self.assertEqual(echo.command_for("gen_part", {"generator": "?"}), "Parts_Any")

    def test_core_maps_unchanged(self):
        self.assertEqual(echo.command_for("asm_joint", {"kind": "revolute"}), "Assembly_CreateJointRevolute")
        self.assertEqual(echo.command_for("cam_op", {"kind": "pocket"}), "CAM_Pocket_Shape")
        self.assertEqual(echo._workbench_for("asm_joint"), "AssemblyWorkbench")


class ReviewDispatch(unittest.TestCase):
    def setUp(self):
        self.state = hooks.saved()
        hooks.reset()

    def tearDown(self):
        hooks.restore(self.state)

    def test_none_installed(self):
        self.assertIsNone(hooks.review(object(), "Body"))

    def test_first_answer_wins(self):
        seen = []

        def passes(s, b):
            seen.append("passes")
            return None

        def broken(s, b):
            seen.append("broken")
            raise RuntimeError("boom")

        def answers(s, b):
            seen.append("answers")
            return {"verdict": "pass", "findings": [], "body": b}

        def later(s, b):
            seen.append("later")
            return {"verdict": "fail"}

        for fn in (passes, broken, answers, later):
            hooks.register_reviewer(fn)
        hooks.register_reviewer(answers)  # once only
        out = hooks.review("session", "Box")
        self.assertEqual(out, {"verdict": "pass", "findings": [], "body": "Box"})
        self.assertEqual(seen, ["passes", "broken", "answers"])

    def test_none_answers(self):
        hooks.register_reviewer(lambda s, b: None)
        self.assertIsNone(hooks.review(None, "Box"))


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: LGPL-2.1-or-later
"""The context-controlled tool list (agentlink/contextlist.py), with a
stand-in server and session: no FreeCAD needed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import appliesnow, contextlist  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402


def _tool(name, group, desc="does a thing"):
    return Tool(name, desc, {"type": "object", "properties": {}, "required": [], "additionalProperties": False}, lambda a: {"ok": True}, group=group)


class _Doc:
    def __init__(self, n):
        self.Name = "D"
        self.Objects = [type("O", (), {"TypeId": f"T::{i % 2}"})() for i in range(n)]


class _Session:
    def __init__(self, n=0):
        self.doc = _Doc(n)
        self.batch_now = None


class ContextList(unittest.TestCase):
    def setUp(self):
        names = [("session_state", "core"), ("batch", "core"), ("guide_read", "core"), ("tool_groups", "core"), ("history_undo", "core"),
                 ("view_snapshot", "view"), ("tool_find", "find"), ("doc_new", "doc"), ("doc_open", "doc"),
                 ("pd_pad", "feature"), ("pd_pocket", "feature"), ("pd_fillet", "feature"), ("fea_solve", "strength"), ("fea_hold", "strength")]
        self.server = Server("t", "0", [_tool(n, g) for n, g in names], groups={"core", "view"})
        self.server.lean_groups = {"core", "view"}
        self.s = _Session(0)
        self.s.server = self.server
        self.server.session = self.s
        os.environ["AGENTLINK_TOOLLIST"] = "context"
        self._chosen, self._take, self._state = appliesnow.chosen, appliesnow.take, contextlist._state
        contextlist._state = lambda session: {"window": True, "workbench": "PartDesignWorkbench", "selSubs": set(), "selBenches": set()}

    def tearDown(self):
        os.environ.pop("AGENTLINK_TOOLLIST", None)
        appliesnow.chosen, appliesnow.take, contextlist._state = self._chosen, self._take, self._state

    def names(self):
        return [t.name for t in self.server.listed()]

    def test_classic_is_the_lean_list(self):
        os.environ["AGENTLINK_TOOLLIST"] = "classic"
        self.assertFalse(contextlist.apply(self.server, self.s))
        self.assertEqual(sorted(self.names()), sorted(["session_state", "batch", "guide_read", "tool_groups", "history_undo", "view_snapshot"]))
        self.assertNotIn("tool_find", self.names())

    def test_start_is_base_and_start(self):
        self.assertTrue(contextlist.apply(self.server, self.s))
        got = self.names()
        self.assertEqual(got[:5], list(contextlist.BASE))
        self.assertIn("doc_new", got)
        self.assertNotIn("pd_pad", got)
        self.assertEqual(self.server.outbox[-1]["method"], "notifications/tools/list_changed")

    def test_not_hidden_and_applies_first(self):
        self.s.doc = _Doc(3)
        appliesnow.chosen = lambda server, state: (["pd_fillet", "pd_pad", "pd_pocket"], {"workbench": "PartDesignWorkbench"})
        appliesnow.take = lambda session, state=None, names=None, budget=None: {"by": {"pd_pad": "applies", "pd_pocket": "not", "pd_fillet": "applies"}}
        contextlist.apply(self.server, self.s)
        got = self.names()
        self.assertIn("pd_pad", got)
        self.assertNotIn("pd_pocket", got)
        self.assertNotIn("fea_solve", got)
        self.assertNotIn("fallback", self.s._ctx_how)
        self.assertTrue(self.server.is_listed("history_undo"))

    def test_thin_context_gets_larger(self):
        self.s.doc = _Doc(3)
        appliesnow.chosen = lambda server, state: (["pd_fillet", "pd_pad", "pd_pocket"], {})
        appliesnow.take = lambda session, state=None, names=None, budget=None: {"by": {"pd_pad": "notChecked", "pd_pocket": "notChecked", "pd_fillet": "applies"}}
        contextlist.apply(self.server, self.s)
        got = self.names()
        self.assertEqual(self.s._ctx_how.get("fallback"), "lean")
        for n in ("pd_pad", "pd_pocket", "pd_fillet", "view_snapshot", "history_undo"):
            self.assertIn(n, got)

    def test_same_context_no_change(self):
        contextlist.apply(self.server, self.s)
        n = len(self.server.outbox)
        self.assertFalse(contextlist.apply(self.server, self.s))
        self.assertEqual(len(self.server.outbox), n)

    def test_hidden_tool_still_callable_and_counted(self):
        contextlist.apply(self.server, self.s)
        self.assertFalse(self.server.is_listed("fea_solve"))
        r = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "fea_solve", "arguments": {}}})
        self.assertFalse(r["result"].get("isError"))
        self.assertEqual(contextlist.stats(self.s)["hiddenCalls"], 1)

    def test_enabled_group_stays_listed(self):
        contextlist.apply(self.server, self.s)
        self.server.groups = {"core", "view", "strength"}
        self.assertIn("fea_hold", self.names())

    def test_back_to_classic(self):
        contextlist.apply(self.server, self.s)
        os.environ["AGENTLINK_TOOLLIST"] = "classic"
        self.assertTrue(contextlist.apply(self.server, self.s))
        self.assertIsNone(self.server.shown)
        self.assertIn("history_undo", self.names())

    def test_token_cap(self):
        self.s.doc = _Doc(3)
        big = [f"t{i}" for i in range(40)]
        for n in big:
            self.server.add(_tool(n, "feature", "x" * 3500))
        appliesnow.chosen = lambda server, state: (list(big), {})
        appliesnow.take = lambda session, state=None, names=None, budget=None: {"by": {n: "applies" for n in big}}
        contextlist.apply(self.server, self.s)
        self.assertIn("capped", self.s._ctx_how)
        self.assertLessEqual(contextlist.tokens_of(self.server.listed()), contextlist.CAP_TOKENS + 200)


if __name__ == "__main__":
    unittest.main()

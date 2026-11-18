# SPDX-License-Identifier: LGPL-2.1-or-later
"""The static minimal list and the STE descriptions (agentlink/staticbase.py), with a stand-in server."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import staticbase  # noqa: E402
from agentlink.protocol import Server, Tool, ToolError  # noqa: E402


def _tool(name, group, fn=None):
    return Tool(name, f"{name}: the full text", {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                fn or (lambda a: {"ok": True}), group=group)


def _boom(a):
    raise ToolError("invalid_input", "calls.1: a batch does not run another batch.")


class Static(unittest.TestCase):
    def setUp(self):
        names = [("session_state", "core"), ("guide_read", "core"), ("tool_groups", "core"), ("history_undo", "core"),
                 ("view_snapshot", "view"), ("tool_find", "find"), ("pd_pad", "feature"), ("approve_file", "core"), ("approve_code", "core")]
        self.server = Server("t", "0", [_tool(n, g) for n, g in names] + [_tool("batch", "core", _boom)], groups={"core", "view"})
        self.server.lean_groups = {"core", "view"}

    def tearDown(self):
        os.environ.pop("AGENTLINK_TOOLLIST", None)
        os.environ.pop("AGENTLINK_DESC", None)

    def names(self):
        r = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        return [t["name"] for t in r["result"]["tools"]], r["result"]["tools"]

    def test_default_is_static(self):
        got, _ = self.names()
        # The two approval tools are always listed: the person sets them in the client's tool permissions.
        self.assertEqual(sorted(got), sorted(["session_state", "batch", "guide_read", "tool_find", "approve_file", "approve_code"]))

    def test_classic_unchanged(self):
        os.environ["AGENTLINK_TOOLLIST"] = "classic"
        got, _ = self.names()
        self.assertIn("history_undo", got)
        self.assertNotIn("tool_find", got)

    def test_static_lists_the_base_only(self):
        os.environ["AGENTLINK_TOOLLIST"] = "static"
        got, _ = self.names()
        self.assertEqual(got, list(staticbase.BASE))
        self.assertFalse(self.server.is_listed("pd_pad"))
        r = self.server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "pd_pad", "arguments": {}}})
        self.assertFalse(r["result"].get("isError"))  # callable by name

    def test_enabled_group_listed_in_static(self):
        os.environ["AGENTLINK_TOOLLIST"] = "static"
        self.server.groups = {"core", "view", "feature"}
        got, _ = self.names()
        self.assertIn("pd_pad", got)

    def test_ste_descriptions_and_batch_hint(self):
        os.environ["AGENTLINK_TOOLLIST"] = "static"
        os.environ["AGENTLINK_DESC"] = "ste"
        _, tools = self.names()
        d = {t["name"]: t["description"] for t in tools}
        self.assertIn("$from", d["batch"])
        self.assertIn('guide_read { topic: "batch" }', d["batch"])
        self.assertNotIn("the full text", d["session_state"])
        r = self.server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "batch", "arguments": {}}})
        self.assertIn('guide_read { topic: "batch" }', json.loads(r["result"]["content"][0]["text"])["error"]["message"])
        os.environ["AGENTLINK_DESC"] = "full"
        r = self.server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "batch", "arguments": {}}})
        self.assertNotIn("guide_read", r["result"]["content"][0]["text"])

    def test_batch_guide_keeps_the_whole_text(self):
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink", "guides", "batch.md")
        with open(here, encoding="utf-8") as f:
            g = f.read()
        for words in ("$from", "$file", 'build: "end"', "lines:", "EchoBatchDelay", "budget", "record", "read:"):
            self.assertIn(words, g)


if __name__ == "__main__":
    unittest.main()

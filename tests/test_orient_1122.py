# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the agent is, without a turn (owner, 22 Nov): a short read in the
words sent at initialize, and once on the first answer of a conversation."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from agentlink import protocol  # noqa: E402
from agentlink.protocol import ORIENT_HEAD, Server, Tool  # noqa: E402

OBJ = {"type": "object", "properties": {}, "additionalProperties": False}
WHERE = {"at": "13:50", "where": "hidden", "documents": [{"name": "Unnamed", "label": "Unnamed", "unsaved": False, "byAgent": False, "agent": True}],
         "agentDocument": "Unnamed", "bodies": []}


def server():
    srv = Server("t", "0", [Tool("session_state", "state", OBJ, lambda a: {"document": "Unnamed"}),
                            Tool("tool_find", "find", OBJ, lambda a: {"tools": []})], instructions="Base words.")
    srv.orient = lambda: dict(WHERE)
    return srv


def call(srv, name, mid=1):
    r = srv.handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call", "params": {"name": name, "arguments": {}}})["result"]
    return json.loads(r["content"][0]["text"])


def init(srv):
    return srv.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"clientInfo": {"name": "test"}}})["result"]


class AtConnect(unittest.TestCase):
    def test_words_carry_the_read(self):
        text = init(server())["instructions"]
        self.assertTrue(text.startswith("Base words."))
        got = json.loads(text.split(ORIENT_HEAD, 1)[1])
        self.assertEqual(got["agentDocument"], "Unnamed")

    def test_none_without_orient(self):
        srv = server()
        srv.orient = None
        self.assertEqual(init(srv)["instructions"], "Base words.")

    def test_a_failing_read_leaves_the_words(self):
        srv = server()
        srv.orient = lambda: 1 / 0
        self.assertEqual(init(srv)["instructions"], "Base words.")


class FirstAnswer(unittest.TestCase):
    def test_once(self):
        srv = server()
        init(srv)
        self.assertIn("whereYouAre", call(srv, "tool_find", 1))
        self.assertNotIn("whereYouAre", call(srv, "tool_find", 2))

    def test_session_state_first_is_the_read(self):
        srv = server()
        init(srv)
        self.assertNotIn("whereYouAre", call(srv, "session_state", 1))
        self.assertNotIn("whereYouAre", call(srv, "tool_find", 2))

    def test_a_new_conversation_orients_again(self):
        srv = server()
        init(srv)
        call(srv, "tool_find", 1)
        init(srv)
        self.assertIn("whereYouAre", call(srv, "tool_find", 2))
        srv.handle({"jsonrpc": "2.0", "id": 3, "method": protocol.CLIENT_METHOD, "params": {"clientInfo": {"name": "next"}}})
        self.assertIn("whereYouAre", call(srv, "tool_find", 4))


class Supervisor(unittest.TestCase):
    def test_same_head(self):
        src = open(os.path.join(os.path.dirname(HERE), "agentlink", "supervise.py"), encoding="utf-8").read()
        self.assertIn("ORIENT_HEAD = " + json.dumps(ORIENT_HEAD), src)


if __name__ == "__main__":
    unittest.main()

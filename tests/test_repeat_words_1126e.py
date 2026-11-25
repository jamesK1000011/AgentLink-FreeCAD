"""A new error at the same place is not "the same refusal as before"
(live check 25 Nov: sketch_constrain's second refusal was a different
error, and the note said it was the same)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class NewErrorSamePlace(unittest.TestCase):
    def server(self, messages):
        from agentlink.protocol import Server, Tool, ToolError

        it = iter(messages)

        def bad(a):
            raise ToolError("invalid_input", next(it))

        obj = {"type": "object", "properties": {"n": {"type": "integer"}}}
        return Server("t", "0", [Tool("sketch_constrain", "c.", obj, bad, changes=True)])

    def call(self, srv, n):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": "sketch_constrain", "arguments": {"n": n}}})["result"]
        return json.loads(r["content"][0]["text"])["error"]

    def test_new_words_same_place(self):
        srv = self.server(["constraints[0]: Line1 has no point 3.",
                           "constraints[0]: the solver found a conflict with constraint 4."])
        self.call(srv, 1)
        two = self.call(srv, 2)
        self.assertNotIn("repeat", two)
        self.assertNotIn("same refusal as before", two["message"])

    def test_new_words_same_lead(self):
        srv = self.server(["kind: not a known constraint.", "kind: needs two edges, got 1."])
        self.call(srv, 1)
        self.assertNotIn("same refusal as before", self.call(srv, 2)["message"])

    def test_same_words_other_numbers(self):
        srv = self.server(["constraints[0]: Line1 has no point 3.", "constraints[2]: Line4 has no point 5."])
        self.call(srv, 1)
        two = self.call(srv, 2)
        self.assertEqual(two["repeat"], 2)
        self.assertIn("same refusal as before", two["message"])


if __name__ == "__main__":
    unittest.main()

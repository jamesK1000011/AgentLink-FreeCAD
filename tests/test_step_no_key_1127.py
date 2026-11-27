"""The step schema declares no key (27 Nov).

llama.cpp b12800 makes, for an object with a declared key and open other keys,
a grammar rule that also refuses each key that is the start of the declared
key. With "tool" declared, "to" could not be written (replay of s1127a).
"""
import unittest

from agentlink import staticbase
from agentlink.families import fast as fast_family


def _objects(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _objects(v)


class StepDeclaresNoKey(unittest.TestCase):
    def steps(self):
        for name in ("run", "batch", "fast"):
            yield name, staticbase.LISTED_SCHEMAS[name]["properties"]["calls"]["items"]
        yield "fast family", fast_family.STEP_SCHEMA

    def test_step_has_no_declared_key(self):
        for name, step in self.steps():
            self.assertNotIn("properties", step, name)
            self.assertNotIn("required", step, name)
            self.assertIs(step.get("additionalProperties"), True, name)
            self.assertIn('"tool" is necessary', step.get("description", ""), name)

    def test_no_open_object_declares_a_key(self):
        # The rule for every listed schema: an object that lets other keys in
        # declares none, so no key name can be the start of a declared key.
        for name, schema in staticbase.LISTED_SCHEMAS.items():
            for obj in _objects(schema):
                if obj.get("additionalProperties") is True:
                    self.assertFalse(obj.get("properties"), name)


if __name__ == "__main__":
    unittest.main()

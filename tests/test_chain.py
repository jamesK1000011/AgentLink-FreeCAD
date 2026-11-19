# SPDX-License-Identifier: LGPL-2.1-or-later
# Answer chaining for batch (agentlink/chain.py): { $file, $at } and
# { $from, $at } inside a call's arguments, and a call's answer written to a
# file. Plain Python: no FreeCAD.
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import chain as C  # noqa: E402

ANSWER = {"bodies": [{"name": "Lid", "volume": 12.5}, {"name": "Box"}], "loops": [{"points": [[0, 0], [10, 0], [10, 5]]}], "n": 2}


class At(unittest.TestCase):
    def test_keys_and_indices(self):
        self.assertEqual(C.at(ANSWER, "bodies.0.name", "x"), "Lid")
        self.assertEqual(C.at(ANSWER, "loops.0.points.-1", "x"), [10, 5])
        self.assertEqual(C.at(ANSWER, "loops.0.points.1.0", "x"), 10)
        self.assertIs(C.at(ANSWER, None, "x"), ANSWER)
        self.assertIs(C.at(ANSWER, "", "x"), ANSWER)
        self.assertEqual(C.at([5, 6], 1, "x"), 6)

    def test_a_missing_key_names_the_keys_there(self):
        with self.assertRaises(C.Miss) as e:
            C.at(ANSWER, "bodies.0.label", "call 0's answer")
        self.assertEqual(e.exception.code, "not_found")
        self.assertIn("'label'", e.exception.message)
        self.assertIn("bodies.0 of call 0's answer", e.exception.message)
        self.assertIn("name, volume", e.exception.message)

    def test_a_missing_index_names_the_length(self):
        with self.assertRaises(C.Miss) as e:
            C.at(ANSWER, "bodies.2.name", "f.json")
        self.assertIn("a list of 2 (indices 0 to 1)", e.exception.message)
        with self.assertRaises(C.Miss) as e:
            C.at(ANSWER, "bodies.first", "f.json")
        self.assertIn("not a list index", e.exception.message)

    def test_past_a_value_says_what_it_is(self):
        with self.assertRaises(C.Miss) as e:
            C.at(ANSWER, "n.x", "f.json")
        self.assertIn("a number", e.exception.message)
        with self.assertRaises(C.Miss) as e:
            C.at(ANSWER, "nope", "f.json")
        self.assertIn("its top", e.exception.message)
        self.assertIn("bodies, loops, n", e.exception.message)

    def test_a_path_that_is_no_path(self):
        with self.assertRaises(C.Miss) as e:
            C.at(ANSWER, ["a"], "f.json")
        self.assertEqual(e.exception.code, "invalid_input")


class Resolve(unittest.TestCase):
    def setUp(self):
        self.answers = {0: {"ok": True, "tool": "mk", "answer": ANSWER, "size": 100}, 1: {"ok": False, "tool": "pad", "error": "no sketch"}}
        self.files = {"a.json": ANSWER}

    def read(self, name):
        if name not in self.files:
            raise C.Miss("not_found", f"$file: {name} — no such file")
        return self.files[name]

    def r(self, v, index=2, first=0):
        return C.resolve(v, self.read, self.answers, index, first)

    def test_anywhere_inside(self):
        args = {"name": {"$from": 0, "$at": "bodies.0.name"}, "items": [{"points": {"$file": "a.json", "$at": "loops.0.points"}}, 3], "whole": {"$file": "a.json"}, "plain": {"a": 1}}
        got = self.r(args)
        self.assertEqual(got["name"], "Lid")
        self.assertEqual(got["items"][0]["points"], [[0, 0], [10, 0], [10, 5]])
        self.assertEqual(got["whole"], ANSWER)
        self.assertEqual(got["plain"], {"a": 1})
        # The arguments given are left as they were (a batch run again reads again).
        self.assertEqual(args["name"], {"$from": 0, "$at": "bodies.0.name"})
        self.assertTrue(C.has_refs(args))
        self.assertFalse(C.has_refs({"a": [1, {"b": "$file"}]}))

    def test_only_an_earlier_call(self):
        for n in (2, 5):
            with self.assertRaises(C.Miss) as e:
                self.r({"$from": n}, index=2)
            self.assertIn("not before this call", e.exception.message)
        for n in (-1, "0", True, 1.5):
            with self.assertRaises(C.Miss) as e:
                self.r({"$from": n})
            self.assertEqual(e.exception.code, "invalid_input")

    def test_a_refused_call_has_no_answer(self):
        with self.assertRaises(C.Miss) as e:
            self.r({"$from": 1})
        self.assertIn("was refused", e.exception.message)
        self.assertIn("no sketch", e.exception.message)

    def test_a_call_of_an_earlier_part(self):
        with self.assertRaises(C.Miss) as e:
            C.resolve({"$from": 3}, self.read, {}, 12, 10)
        self.assertIn("earlier part", e.exception.message)
        self.assertIn("$file", e.exception.message)

    def test_a_reference_stands_alone(self):
        for ref in ({"$file": "a.json", "other": 1}, {"$from": 0, "path": "x"}, {"$file": "a.json", "$from": 0}):
            with self.assertRaises(C.Miss) as e:
                self.r(ref)
            self.assertEqual(e.exception.code, "invalid_input", ref)
        with self.assertRaises(C.Miss):
            self.r({"$file": ""})

    def test_too_large_an_answer(self):
        self.answers[0]["size"] = C.MAX_BYTES + 1
        with self.assertRaises(C.Miss) as e:
            self.r({"$from": 0})
        self.assertIn("20 MB", e.exception.message)

    def test_a_missing_file_refuses(self):
        with self.assertRaises(C.Miss) as e:
            self.r({"x": [{"$file": "b.json"}]})
        self.assertEqual(e.exception.code, "not_found")


class Files(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_write_then_read(self):
        p = os.path.join(self.d, "sub", "a.json")
        w = C.write_answer(p, ANSWER)
        self.assertEqual(w, {"path": p, "bytes": os.path.getsize(p)})
        self.assertFalse(os.path.exists(p + ".part"))
        cache = {}
        self.assertEqual(C.read_json(p, "sub/a.json", cache), ANSWER)
        self.assertIs(C.read_json(p, "sub/a.json", cache), cache[p][1])
        # Written again: read again, not from the copy kept.
        C.write_answer(p, {"other": [1, 2, 3, 4, 5, 6, 7, 8, 9]})
        self.assertEqual(C.read_json(p, "sub/a.json", cache), {"other": [1, 2, 3, 4, 5, 6, 7, 8, 9]})

    def test_no_such_file_names_the_files_there(self):
        C.write_answer(os.path.join(self.d, "have.json"), {})
        with self.assertRaises(C.Miss) as e:
            C.read_json(os.path.join(self.d, "want.json"), "want.json", may_list=lambda f: True)
        self.assertEqual(e.exception.code, "not_found")
        self.assertIn("have.json", e.exception.message)
        with self.assertRaises(C.Miss) as e:
            C.read_json(os.path.join(self.d, "nofolder", "want.json"), "nofolder/want.json", may_list=lambda f: True)
        self.assertIn("no such folder", e.exception.message)

    def test_not_json_and_a_folder(self):
        p = os.path.join(self.d, "bad.json")
        with open(p, "w") as f:
            f.write("{nope")
        with self.assertRaises(C.Miss) as e:
            C.read_json(p, "bad.json")
        self.assertIn("not JSON", e.exception.message)
        with self.assertRaises(C.Miss) as e:
            C.read_json(self.d, "d")
        self.assertIn("folder", e.exception.message)

    def test_over_the_cap(self):
        p = os.path.join(self.d, "big.json")
        with open(p, "w") as f:
            json.dump(list(range(50)), f)
        old = C.MAX_BYTES
        C.MAX_BYTES = 10
        try:
            with self.assertRaises(C.Miss) as e:
                C.read_json(p, "big.json")
        finally:
            C.MAX_BYTES = old
        self.assertEqual(e.exception.code, "invalid_input")
        self.assertIn("over the", e.exception.message)

    def test_a_calls_to_is_a_json_name(self):
        self.assertIsNone(C.to_name("a.json", 0))
        self.assertIsNone(C.to_name("sub/A.JSON", 0))
        for bad in ("a.txt", "", 3, None, "a.py"):
            self.assertIn("calls.4.to", C.to_name(bad, 4))

    def test_the_row_left_in_the_reply(self):
        w = {"path": "p", "bytes": 3}
        row = C.written_row("mk", {**ANSWER, "health": {"ok": False, "verdict": "1 object failed", "todo": "fix", "errors": [1]}}, w)
        self.assertEqual(row["written"], w)
        self.assertEqual(row["keys"], ["bodies", "loops", "n", "health"])
        self.assertEqual(row["health"], {"ok": False, "verdict": "1 object failed", "todo": "fix"})
        self.assertNotIn("result", row)
        self.assertEqual(C.written_row("mk", [1, 2, 3], w)["length"], 3)
        self.assertNotIn("health", C.written_row("mk", ANSWER, w))
        many = C.summary({str(i): i for i in range(60)})
        self.assertEqual(len(many["keys"]), C.KEYS_SHOWN)
        self.assertEqual(many["keysInAll"], 60)


if __name__ == "__main__":
    unittest.main()

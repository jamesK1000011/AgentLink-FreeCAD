# SPDX-License-Identifier: LGPL-2.1-or-later
# guide_read's index and reading (agentlink/guideidx.py): what each section
# costs, Start here first, the sections for a later moment, and several
# guides in one call. Plain Python, and the guides here themselves.
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import guideidx as G  # noqa: E402

GUIDES = os.path.join(os.path.dirname(__file__), "..", "agentlink", "guides")
TEXT = """# A guide
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

Opening words.

## workflow
1. First.

## Start here
- Read workflow.

## Heavy steps
<!-- later: before a big boolean -->
- Slow.

## traps
- One.
"""


def guides():
    out = {}
    for n in sorted(os.listdir(GUIDES)):
        if n.endswith(".md"):
            with open(os.path.join(GUIDES, n), encoding="utf-8") as f:
                out[n[:-3]] = f.read()
    return out


class Index(unittest.TestCase):
    def test_entry(self):
        e = G.entry("g", TEXT)
        self.assertEqual(e["title"], "A guide")
        self.assertEqual(e["sections"], ["Start here", "workflow", "Heavy steps", "traps"])
        self.assertEqual(e["start"], "Start here")
        self.assertEqual(e["chars"], len(TEXT))
        self.assertEqual(e["tokens"], G.tokens(TEXT))
        self.assertEqual(list(e["sectionTokens"]), e["sections"])
        self.assertEqual(e["sectionTokens"]["workflow"], G.tokens("## workflow\n1. First.\n\n"))
        self.assertEqual(e["later"], [{"section": "Heavy steps", "when": "before a big boolean", "tokens": e["sectionTokens"]["Heavy steps"]}])
        self.assertEqual(e["firstReadTokens"], e["tokens"] - e["later"][0]["tokens"])

    def test_a_guide_without_the_conventions_reads_as_before(self):
        text = "# T\n\n## a\nx\n\n## b\ny\n"
        e = G.entry("t", text)
        self.assertEqual(e["sections"], ["a", "b"])
        self.assertNotIn("start", e)
        self.assertNotIn("later", e)
        self.assertEqual(G.clean(text), text)

    def test_tokens_are_characters_over_four(self):
        self.assertEqual(G.tokens(""), 0)
        self.assertEqual(G.tokens("abcd"), 1)
        self.assertEqual(G.tokens("abcde"), 2)


class Read(unittest.TestCase):
    def test_the_later_comment_is_not_in_the_text(self):
        whole = G.clean(TEXT)
        self.assertNotIn("later:", whole)
        self.assertIn("## Heavy steps\n- Slow.", whole)
        self.assertIn("SPDX", whole)  # other comments stay

    def test_sections_by_the_start_of_their_names(self):
        text, missing, names = G.pick(TEXT, "traps")
        self.assertEqual((text, missing), ("## traps\n- One.\n", []))
        self.assertEqual(names, ["workflow", "Start here", "Heavy steps", "traps"])
        text, missing, _ = G.pick(TEXT, ["start", "HEAVY", "nope"])
        self.assertTrue(text.startswith("## Start here\n"))
        self.assertIn("## Heavy steps\n- Slow.", text)
        self.assertNotIn("workflow\n1.", text)
        self.assertEqual(missing, ["nope"])

    def test_several_guides_up_to_the_cap(self):
        texts = {"a": "# A\n\n## s\n" + "x" * 300, "b": "# B\n\n## s\n" + "y" * 300, "c": "# C\n\n## s\n" + "z" * 300}
        out = G.read_many(texts, ["a", "b", "c"], cap=700)
        self.assertEqual([r["topic"] for r in out["read"]], ["a", "b"])
        self.assertEqual(out["next"], ["c"])
        self.assertIn("next", out["note"])
        self.assertLessEqual(len(json.dumps(out["read"])), 760)
        # The first is read whatever it costs; all fit: no next.
        self.assertEqual([r["topic"] for r in G.read_many(texts, ["a", "b"], cap=10)["read"]], ["a"])
        self.assertNotIn("next", G.read_many(texts, ["a", "b", "c"]))

    def test_one_section_of_each(self):
        texts = {"g": TEXT, "t": "# T\n\n## a\nx\n"}
        out = G.read_many(texts, ["t", "g"], "Start here")
        self.assertEqual([r["topic"] for r in out["read"]], ["g"])
        self.assertEqual(out["missing"], ["t"])


class TheGuidesHere(unittest.TestCase):
    def test_the_three_longest_have_a_map(self):
        gs = guides()
        longest = sorted((t for t in gs if t != "start"), key=lambda t: -len(gs[t]))[:3]
        for t in longest:
            e = G.entry(t, gs[t])
            self.assertEqual(e.get("start"), "Start here", t)
            self.assertEqual(e["sections"][0], "Start here", t)
            self.assertTrue(e.get("later"), t)
            # The map names sections that are there, and every later one.
            text, _, names = G.pick(gs[t], "Start here")
            first = [n for n in names if n != "Start here" and n not in {x["section"] for x in e["later"]}]
            self.assertGreaterEqual(sum(1 for n in first if f"`{n}`" in text), 2, t)
            for x in e["later"]:
                self.assertIn(f"`{x['section']}`", text, t)
            self.assertLess(e["firstReadTokens"], e["tokens"])

    def test_every_later_mark_says_when(self):
        for t, text in guides().items():
            for x in G.entry(t, text).get("later", []):
                self.assertGreater(len(x["when"]), 8, (t, x))
            # A later comment anywhere but under a heading would show as text.
            self.assertNotIn("later:", G.clean(text), t)

    def test_all_guides_in_two_or_three_reads(self):
        gs = guides()
        left, reads = list(gs), 0
        while left and reads < 9:
            out = G.read_many(gs, left)
            self.assertLessEqual(len(json.dumps(out, ensure_ascii=False)), 60_000)
            left = out.get("next", [])
            reads += 1
        self.assertEqual(left, [])
        self.assertLessEqual(reads, 4)


if __name__ == "__main__":
    unittest.main()

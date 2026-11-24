# SPDX-License-Identifier: LGPL-2.1-or-later
# The connect text of design 1h (24 Nov): (1) the guide list is made from
# the guide files when the words are made, with one line of common words
# from data/guide_words.json; (2) decision 6: guide_read with an unknown
# topic matches it as tool_find matches a tool name and answers the
# matches and the index; (3) the softer guide-first words; (4) the ask
# line; (5) pick shown as a batch call when pick is not listed.
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import guideidx, options  # noqa: E402
from agentlink.protocol import close_in  # noqa: E402
from test_local_fixes_1123 import run  # noqa: E402

GUIDES = sorted(n[:-3] for n in os.listdir(os.path.join(ROOT, "agentlink", "guides")) if n.endswith(".md"))
CARD = ("A tool's card (tool_find { tool: name }) gives its inputs and an example: read it before the first call of that tool. "
        "A guide gives the workflow and traps: read the section you need when a card is not enough.")
ASK = ("What only the person knows (how a part is made, what it is made of, what it must carry): ask, when someone answers. "
       "When nobody answers (a run with no person), take the plain choice, and say it in your last answer. "
       "Never start, pause or stop a print without the person's typed say-so.")
WORDS = "PartDesign work (bodies, pads, pockets, holes, fillets) is in feature and sketch."


class ConnectWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts = run('''
    print(json.dumps([tools.instructions(True, False, static=True), tools.instructions(True, True, static=False),
                      tools.instructions(False, False, static=False)]))
''')

    def test_the_guide_list_is_the_guide_files(self):
        for text in self.texts:
            self.assertIn("The guides here: " + ", ".join(GUIDES) + ".", text)
            self.assertNotIn("(start, model, sketch,", text)

    def test_one_line_of_common_words(self):
        for text in self.texts:
            self.assertEqual(text.count(WORDS), 1, text)

    def test_card_first_then_guide_section(self):
        for text in self.texts:
            self.assertIn(CARD, text)
            self.assertNotIn("Before a task's first step read its guide", text)

    def test_the_ask_line(self):
        for text in self.texts:
            self.assertIn(ASK, text)
            self.assertNotIn("Ask the person what only they know", text)

    def test_no_placeholder_is_left(self):
        for text in self.texts:
            self.assertNotIn("{guides}", text)
            self.assertNotIn("{words}", text)


class AddOnGuides(unittest.TestCase):
    def test_a_registered_guide_and_its_words_show_at_the_next_connect(self):
        d = tempfile.mkdtemp(prefix="agentlink-guides-")
        with open(os.path.join(d, "zzwidget.md"), "w", encoding="utf-8") as f:
            f.write("# Widgets\n\n## workflow\nMake one.\n")
        with open(os.path.join(d, "guide_words.json"), "w", encoding="utf-8") as f:
            json.dump({"entries": {"w": {"work": "Widget work (gears and cogs)", "guides": ["zzwidget"], "words": ["cogs"],
                                         "source": "test", "date": "2026-11-24"}}}, f)
        got = run('''
    before = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})["result"]["instructions"]
    tools.register_guides(%r)
    after = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}})["result"]["instructions"]
    print(json.dumps({"before": before, "after": after, "read": call("guide_read", {"topic": "cogs"})}))
''' % d)
        self.assertNotIn("zzwidget", got["before"])
        self.assertIn(", zzwidget.", got["after"])
        self.assertIn("Widget work (gears and cogs) is in zzwidget.", got["after"])
        err, body, _ = got["read"]
        self.assertFalse(err)
        self.assertEqual(body["notFound"], [{"topic": "cogs", "matches": ["zzwidget"]}])


class GuideFuzzy(unittest.TestCase):
    """Decision 6: an unknown guide topic is matched, never refused bare."""

    def test_partdesign_finds_feature_and_sketch(self):
        got = run('''
    print(json.dumps({"pd": call("guide_read", {"topic": "partdesign"}), "two": call("guide_read", {"topic": ["model", "sketches"]}),
                      "none": call("guide_read", {"topic": "qqqq"}), "ok": call("guide_read", {"topic": "sketch", "section": "traps"})}))
''')
        err, body, _ = got["pd"]
        self.assertFalse(err)
        self.assertEqual(body["notFound"][0]["topic"], "partdesign")
        self.assertEqual(body["notFound"][0]["matches"][:2], ["feature", "sketch"])
        self.assertEqual(sorted(g["topic"] for g in body["guides"]), GUIDES)
        self.assertNotIn("text", body)
        self.assertIn('guide_read { topic: "feature" } reads one', body["note"])
        self.assertIn("Nothing was read.", body["note"])
        err, body, _ = got["two"]
        self.assertFalse(err)
        self.assertEqual(body["notFound"], [{"topic": "sketches", "matches": ["sketch"]}])
        err, body, _ = got["none"]
        self.assertFalse(err)
        self.assertEqual(body["notFound"], [{"topic": "qqqq", "matches": []}])
        self.assertIn("no name is close", body["note"])
        err, body, _ = got["ok"]
        self.assertFalse(err)
        self.assertTrue(body["text"].startswith("## traps"))

    def test_the_match_words(self):
        words = guideidx.load_words()
        for asked, first in (("PartDesign", ["feature", "sketch"]), ("Part Design workbench", ["feature", "sketch"]), ("pads", ["feature", "sketch"]),
                             ("techdrawing", ["techdraw"]), ("assembly4", ["assembly"])):
            self.assertEqual(guideidx.fuzzy(asked, GUIDES, words)[:len(first)], first, asked)
        self.assertEqual(guideidx.fuzzy("", GUIDES, words), [])
        self.assertEqual(guideidx.fuzzy(None, GUIDES, words), [])

    def test_the_line_names_only_guides_that_are_here(self):
        words = guideidx.load_words()
        self.assertEqual(guideidx.words_lines(words, GUIDES), [WORDS])
        self.assertEqual(guideidx.words_lines(words, ["feature"]), ["PartDesign work (bodies, pads, pockets, holes, fillets) is in feature."])
        self.assertEqual(guideidx.words_lines(words, ["model"]), [])

    def test_tool_finds_helper_is_shared(self):
        # The same helper as tool_find's near names (protocol.close_names).
        self.assertEqual(close_in("pd_pad_create", ["pd_pad", "pd_pocket", "view_render"]), ["pd_pad", "pd_pocket"])

    def test_the_data_has_its_schema_shape(self):
        with open(os.path.join(ROOT, "agentlink", "data", "guide_words.json"), encoding="utf-8") as f:
            data = json.load(f)
        with open(os.path.join(ROOT, "agentlink", "data", "guide_words.schema.json"), encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(data["$schema"], "guide_words.schema.json")
        for e in data["entries"].values():
            self.assertEqual(set(e) - set(schema["properties"]), set())
            for k in schema["required"]:
                self.assertIn(k, e)
            for g in e["guides"]:
                self.assertIn(g, GUIDES)


class PickAsBatch(unittest.TestCase):
    """Item 5: with the static list, pick is not listed: the example is a batch call."""

    DOC_NEW = {"step": 0, "list": [{"n": 1, "tool": "doc_new", "arguments": {}, "ask": [{"arg": "name"}]}]}

    def test_static_shows_a_batch_call(self):
        self.assertEqual(options.pick_how(self.DOC_NEW, static=True),
                         'batch { calls: [{ tool: "pick", arguments: { option: 1, fill: { name: "Part" } } }] } runs option 1; option: "1, Part" also works')
        self.assertEqual(options.pick_how({"step": 1, "list": [{"n": 2, "tool": "body_check", "arguments": {}}]}, static=True),
                         'batch { calls: [{ tool: "pick", arguments: { option: 2 } }] } runs option 2')
        self.assertTrue(options.pick_how(None, static=True).startswith('batch { calls: [{ tool: "pick", arguments: { option: 1, fill: { length: 4 } } }] }'))

    def test_classic_keeps_the_short_form(self):
        self.assertEqual(options.pick_how(self.DOC_NEW, static=False), 'pick { option: 1, fill: { name: "Part" } } runs option 1; the text "1, Part" also works')
        self.assertEqual(options.pick_how(None, static=False), options.PICK_HOW)

    def test_the_mode_decides(self):
        with mock.patch.dict(os.environ, {"AGENTLINK_TOOLLIST": "static"}):
            self.assertTrue(options.public(self.DOC_NEW)["pick"].startswith("batch {"))
        with mock.patch.dict(os.environ, {"AGENTLINK_TOOLLIST": "classic"}):
            self.assertTrue(options.public(self.DOC_NEW)["pick"].startswith("pick {"))


if __name__ == "__main__":
    unittest.main()

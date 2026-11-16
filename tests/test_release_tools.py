# SPDX-License-Identifier: LGPL-2.1-or-later
# scripts/release.py: the version written everywhere agrees, the Claude
# extension's manifest is sound, its download links name the file the build
# makes, and the changelog fold keeps every entry. No FreeCAD needed.
import copy
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import release  # noqa: E402

REPO = "https://github.com/jamesK1000011/AgentLink-FreeCAD"


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


class Versions(unittest.TestCase):
    def test_every_place_agrees(self):
        vs = release.versions()
        want = vs["package.xml"]
        self.assertRegex(want, r"^0\.\d+\.\d+$")
        self.assertEqual({k: v for k, v in vs.items() if v != want}, {})

    def test_check_passes(self):
        self.assertEqual(release.problems(), [])

    def test_tag(self):
        v = release.versions()["package.xml"]
        self.assertTrue(any("does not name" in p for p in release.problems("v" + v)))
        self.assertTrue(any("does not name" in p for p in release.problems("agentlink-v9.9.9")))
        self.assertFalse(any("does not name" in p for p in release.problems("agentlink-v" + v)))

    def test_release_workflow_checks_the_tag(self):
        wf = _read(".github", "workflows", "mcpb-release.yml")
        self.assertIn("tags: ['%s*']" % release.TAG_PREFIX, wf)
        self.assertIn("python3 scripts/release.py check --tag", wf)


class Manifest(unittest.TestCase):
    def setUp(self):
        self.m = json.loads(_read("packaging", "mcpb", "manifest.json"))

    def test_sound(self):
        self.assertEqual(release.manifest_problems(self.m), [])

    def test_tools_are_the_lean_list_and_the_update(self):
        names = [t["name"] for t in self.m["tools"]]
        self.assertIn("session_state", names)
        self.assertIn("tool_groups", names)
        self.assertEqual(names[-1], "agentlink_update")
        self.assertTrue(self.m["tools_generated"])

    def test_catches_what_is_wrong(self):
        for change, word in (
            (lambda m: m.pop("icon"), "icon missing"),
            (lambda m: m.__setitem__("icon", "nope.png"), "not in packaging/mcpb"),
            (lambda m: m.__setitem__("version", "1.0"), "not X.Y.Z"),
            (lambda m: m["tools"].pop(0), "lean list"),
            (lambda m: m["user_config"]["out_dir"].__setitem__("required", True), "required"),
            (lambda m: m["user_config"]["auto_update"].__setitem__("default", "yes"), "default"),
            (lambda m: m["server"]["mcp_config"]["env"].__setitem__("X", "${user_config.nothing}"), "not declared"),
            (lambda m: m["server"].__setitem__("entry_point", "server/gone.js"), "entry_point"),
        ):
            m = copy.deepcopy(self.m)
            change(m)
            self.assertTrue(any(word in p for p in release.manifest_problems(m)), word)

    def test_build_and_release_name_one_file(self):
        name = release.build_asset_name()
        self.assertEqual(name, "freecad-agentlink.mcpb")
        for wf in ("mcpb-release.yml", "bakeoff.yml"):
            self.assertIn("dist/" + name, _read(".github", "workflows", wf))
        self.assertIn('cp "$HERE/icon.png"', _read("packaging", "mcpb", "build.sh"))


class DownloadLinks(unittest.TestCase):
    def test_links_name_this_repository_and_the_built_file(self):
        url = "%s/releases/latest/download/%s" % (REPO, release.build_asset_name())
        for p in (("README.md",), ("SETUP.md",), ("docs", "clients", "claude-desktop.md")):
            text = _read(*p)
            self.assertIn(url, text, os.path.join(*p))
            # The old channel only as a note that it retires, never a link.
            self.assertEqual(re.findall(r"https?://\S*(?:scanruler|ScanRuler)/(?:releases|tree/freecad-spike)\S*", text), [], p)
            if "freecad-spike" in text:
                self.assertRegex(text, r"retire", os.path.join(*p))


class Fold(unittest.TestCase):
    TEXT = ("# Changelog\n\nIntro.\n\n## [Unreleased]\n\nBeing prepared.\n\n### Added\n\n- a\n\n### Fixed\n\n- b\n\n"
            "### Removed\n\n- c\n\n### Fixed\n\n- d\n\n## [0.2.0] - 2026-01-01\n\n### Added\n\n- old\n")

    def test_fold_merges_and_keeps_everything(self):
        out = release.fold_text(self.TEXT, "0.3.0", "2026-11-16")
        self.assertIn("## [Unreleased]\n\n## [0.3.0] - 2026-11-16\n\n### Added\n\n- a\n\n### Fixed\n\n- b\n- d\n\n### Removed\n\n- c\n\n## [0.2.0]", out)
        self.assertEqual(release.released(out), ("0.3.0", "2026-11-16"))
        self.assertTrue(out.startswith("# Changelog\n\nIntro.\n\n"))

    def test_fold_again_adds_later_entries(self):
        once = release.fold_text(self.TEXT, "0.3.0", "2026-11-16")
        later = once.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Fixed\n\n- e\n\n### Changed\n\n- f\n", 1)
        out = release.fold_text(later, "0.3.0", "2026-11-17")
        self.assertIn("## [Unreleased]\n\n## [0.3.0] - 2026-11-17\n\n### Fixed\n\n- e\n- b\n- d\n\n### Changed\n\n- f\n\n### Added\n\n- a\n", out)
        self.assertEqual(out.count("## [0.3.0]"), 1)
        self.assertIn("## [0.2.0] - 2026-01-01\n\n### Added\n\n- old\n", out)

    def test_unreleased_empty_after_fold(self):
        secs = release.changelog_sections(_read("CHANGELOG.md"))
        self.assertRegex(secs[0][0], r"^\[?Unreleased\]?$")
        self.assertEqual(release.released(), (release.versions()["package.xml"], re.search(r"<date>([^<]+)</date>", _read("package.xml")).group(1)))


if __name__ == "__main__":
    unittest.main()

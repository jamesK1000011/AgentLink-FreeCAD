# SPDX-License-Identifier: LGPL-2.1-or-later
# Release readiness without FreeCAD: the README's tool table is current, the
# licence of every tracked file is stated (a REUSE-style check, for when the
# `reuse` tool is not installed) and its text is in LICENSES/, package.xml
# is what the Addon Manager needs, the versions agree, the client configs
# parse and their install links carry the same command, the setup check
# runs, and the changelog has an Unreleased section.
import base64
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import unittest
import urllib.parse
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MAIN = "LGPL-2.1-or-later"
SOURCE = (".py", ".js", ".mjs", ".sh")
NS = {"p": "https://wiki.freecad.org/Package_Metadata"}
COMMAND = {"command": "uvx", "args": ["--from", "git+https://github.com/jamesK1000011/AgentLink-FreeCAD", "agentlink-freecad"]}


def tracked():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [f for f in out.splitlines() if os.path.exists(os.path.join(ROOT, f))]


def reuse_annotations():
    """(globs, licence) pairs from REUSE.toml, read without tomllib."""
    out, globs = [], None
    with open(os.path.join(ROOT, "REUSE.toml"), encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*path\s*=\s*(.+)", line)
            if m:
                globs = re.findall(r'"([^"]+)"', m.group(1))
            m = re.match(r'\s*SPDX-License-Identifier\s*=\s*"([^"]+)"', line)
            if m and globs is not None:
                out.append((globs, m.group(1)))
                globs = None
    return out


def _match(path, glob):
    rx = re.escape(glob).replace(r"\*\*", "\0").replace(r"\*", "[^/]*").replace("\0", ".*")
    return re.fullmatch(rx, path) is not None


def _licence_file(f):
    return re.fullmatch(r"LICEN[CS]E([-.].*)?", f) is not None or f.startswith("LICENSES/")


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


class Readme(unittest.TestCase):
    def test_tool_table_is_current(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        try:
            import tool_summary
        finally:
            sys.path.pop(0)
        text = _read("README.md")
        self.assertEqual(tool_summary.render(text), text, "run python3 scripts/tool_summary.py")
        gs = tool_summary.groups()
        self.assertIn("core", gs)
        self.assertTrue(gs["core"]["lean"])
        self.assertIn("session_state", gs["core"]["tools"])

    def test_sections(self):
        text = _read("README.md")
        for h in ("What you need", "Install", "Connect your agent", "Where everything lives", "What the agent can do",
                  "Platforms", "Token usage", "Troubleshooting", "Uninstall", "Credits and licence"):
            self.assertRegex(text, r"(?m)^## " + re.escape(h), h)
        self.assertIn("--check", text)
        self.assertIn("Stefan Hermann (CNC Kitchen)", text)
        self.assertIn("SETUP.md", text)


class Licences(unittest.TestCase):
    def test_every_file_has_a_licence(self):
        files = tracked()
        if files is None:
            self.skipTest("not a git checkout")
        notes = reuse_annotations()
        missing, wrong = [], []
        for f in files:
            if _licence_file(f):
                continue
            with open(os.path.join(ROOT, f), "rb") as fh:
                head = fh.read(600).decode("utf-8", "replace")
            m = re.search(r"SPDX-License-Identifier:\s*([^\s*>-][^\s>]*)", head)
            if m:
                ids = [m.group(1)]
            else:
                ids = [lic for globs, lic in notes if any(_match(f, g) for g in globs)]
                if f.endswith(SOURCE) or not ids:
                    missing.append(f)
                    continue
            for i in ids:
                for part in re.split(r"\s+(?:AND|OR|WITH)\s+", i):
                    if not os.path.exists(os.path.join(ROOT, "LICENSES", part + ".txt")):
                        wrong.append(f"{f}: {part}")
        self.assertEqual(missing, [], "no SPDX header or REUSE.toml entry")
        self.assertEqual(wrong, [], "licence text not in LICENSES/")

    def test_licence_texts(self):
        self.assertIn("LESSER GENERAL PUBLIC LICENSE", _read("LICENSE")[:400])
        self.assertEqual(_read("LICENSE"), _read("LICENSES", MAIN + ".txt"))
        self.assertIn("Attribution 4.0 International", _read("LICENSES", "CC-BY-4.0.txt"))
        self.assertIn("CC BY 4.0", _read("LICENSE-DATA"))
        for lic in ("MIT", "Apache-2.0"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "LICENSES", lic + ".txt")), lic)

    def test_data_is_cc_by(self):
        notes = reuse_annotations()
        for f in os.listdir(os.path.join(ROOT, "agentlink", "data")):
            ids = [lic for globs, lic in notes if any(_match("agentlink/data/" + f, g) for g in globs)]
            self.assertEqual(ids, ["CC-BY-4.0"], f)

    def test_no_bytecode_tracked(self):
        files = tracked()
        if files is None:
            self.skipTest("not a git checkout")
        self.assertEqual([f for f in files if "__pycache__" in f or f.endswith(".pyc")], [])


class Changelog(unittest.TestCase):
    def test_unreleased_section(self):
        self.assertRegex(_read("CHANGELOG.md"), r"(?m)^## \[?Unreleased\]?")


class PackageXml(unittest.TestCase):
    """package.xml as FreeCAD's Addon Manager reads it."""

    @classmethod
    def setUpClass(cls):
        import xml.etree.ElementTree as ET

        cls.root = ET.parse(os.path.join(ROOT, "package.xml")).getroot()

    def one(self, tag, under=None):
        el = (under if under is not None else self.root).find("p:" + tag, NS)
        self.assertIsNotNone(el, tag)
        self.assertTrue((el.text or "").strip(), tag)
        return el

    def test_format_and_required(self):
        self.assertEqual(self.root.tag, "{%s}package" % NS["p"])
        self.assertEqual(self.root.get("format"), "1")
        for tag in ("name", "description", "version", "date", "maintainer", "license", "freecadmin", "icon"):
            self.one(tag)
        self.assertRegex(self.one("version").text, r"^\d+\.\d+\.\d+$")
        self.assertRegex(self.one("date").text, r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(self.one("freecadmin").text.strip(), "1.0.0")

    def test_versions_agree(self):
        v = self.one("version").text.strip()
        self.assertRegex(_read("agentlink", "server.py"), r'(?m)^VERSION = "%s"' % re.escape(v))
        self.assertRegex(_read("pyproject.toml"), r'(?m)^version = "%s"' % re.escape(v))

    def test_licences(self):
        lics = self.root.findall("p:license", NS)
        self.assertEqual(lics[0].text.strip(), MAIN)
        self.assertIn("CC-BY-4.0", [lic.text.strip() for lic in lics])
        for lic in lics:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, lic.get("file"))), lic.get("file"))

    def test_urls(self):
        urls = {u.get("type"): (u.text or "").strip() for u in self.root.findall("p:url", NS)}
        for kind in ("repository", "bugtracker", "readme"):
            self.assertTrue(urls.get(kind, "").startswith("https://github.com/jamesK1000011/AgentLink-FreeCAD"), kind)
        self.assertTrue(urls["readme"].endswith("/README.md"))

    def test_icons_and_workbench(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, self.one("icon").text.strip())))
        wbs = self.root.findall("p:content/p:workbench", NS)
        self.assertEqual(len(wbs), 1)
        # InitGui.py only calls workbench.add(); the class lives in the module
        # (FreeCAD's exec() hides InitGui's own names from a class body).
        initgui = _read("InitGui.py")
        built = _read(os.path.join("agentlink", "workbench.py"))
        wb = wbs[0]
        cls = self.one("classname", wb).text.strip()
        self.assertRegex(built, r"(?m)^    class %s\(Gui\.Workbench\)" % re.escape(cls))
        self.assertRegex(initgui, r"(?m)^_agentlink_workbench\.add\(FreeCADGui\)")
        self.assertTrue(os.path.isfile(os.path.join(ROOT, self.one("subdirectory", wb).text.strip(), "InitGui.py")))
        self.assertTrue(os.path.isfile(os.path.join(ROOT, self.one("icon", wb).text.strip())))
        self.one("name", wb)
        for pp in self.root.findall("p:content/p:preferencepack", NS):
            name = self.one("name", pp).text.strip()
            self.assertTrue(os.path.isfile(os.path.join(ROOT, name, name + ".cfg")), name)

    def test_tags(self):
        self.assertGreaterEqual(len(self.root.findall("p:tag", NS)), 3)


class Pyproject(unittest.TestCase):
    def test_package(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest("tomllib is Python 3.11+")
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
            p = tomllib.load(f)
        self.assertEqual(p["project"]["scripts"]["agentlink-freecad"], "agentlink.launch:main")
        st = p["tool"]["setuptools"]
        pkgs = sorted(os.path.relpath(d, ROOT).replace(os.sep, ".") for d, _, fs in os.walk(os.path.join(ROOT, "agentlink"))
                      if "__init__.py" in fs and "__pycache__" not in d)
        self.assertEqual(sorted(st["packages"]), pkgs)
        for m in st["py-modules"]:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, m + ".py")), m)
        # Every non-Python file the server reads is in the package.
        self.assertEqual(sorted(st["package-data"]["agentlink"]), ["data/*.json", "guides/*.md"])
        self.assertEqual(p["project"]["dependencies"], [])


class Clients(unittest.TestCase):
    DIR = os.path.join(ROOT, "docs", "clients")

    def test_json_blocks_parse_and_carry_the_command(self):
        for n in sorted(os.listdir(self.DIR)):
            text = _read("docs", "clients", n)
            for block in re.findall(r"```json\n(.*?)```", text, re.S):
                cfg = json.loads(block)
                entry = (cfg.get("mcpServers") or cfg.get("servers") or cfg.get("mcp"))["agentlink-freecad"]
                if isinstance(entry.get("command"), list):
                    self.assertEqual(entry["command"], [COMMAND["command"]] + COMMAND["args"], n)
                else:
                    self.assertEqual({k: entry[k] for k in COMMAND}, COMMAND, n)

    def test_install_links(self):
        cursor = _read("docs", "clients", "cursor.md")
        for b64 in re.findall(r"install\?name=agentlink-freecad&config=([A-Za-z0-9+/=]+)", cursor):
            self.assertEqual(json.loads(base64.b64decode(b64)), COMMAND)
        vs = _read("docs", "clients", "vscode.md")
        found = re.findall(r"redirect/mcp/install\?name=agentlink-freecad&config=([^)\s]+)\)", vs)
        self.assertEqual(len(found), 2)
        for q in found:
            self.assertEqual(json.loads(urllib.parse.unquote(q)), COMMAND)
        deep = re.search(r"vscode:mcp/install\?([^`\s]+)", vs).group(1)
        self.assertEqual(json.loads(urllib.parse.unquote(deep)), {"name": "agentlink-freecad", **COMMAND})

    def test_chatgpt_and_small_models(self):
        text = _read("docs", "clients", "README.md")
        self.assertRegex(text, r"(?m)^## ChatGPT")
        self.assertRegex(text, r"(?m)^## Small local models")


class SetupCheck(unittest.TestCase):
    def test_report_without_freecad(self):
        from agentlink import setup_check

        with mock.patch.object(setup_check, "freecad_candidates", return_value=[]):
            rows = setup_check.check(ask=False)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = setup_check.main(["--json", "--no-ask"])
        fc = [r for r in rows if r["item"] == "FreeCAD"][0]
        self.assertEqual(fc["state"], "missing")
        self.assertIn("freecad.org", fc["fix"])
        self.assertEqual(code, 1)
        report = json.loads(out.getvalue())
        self.assertEqual(report["os"], setup_check.OS)
        for r in report["items"]:
            self.assertIn(r["state"], ("ok", "missing", "optional", "note"))
            if r["state"] == "missing":
                self.assertTrue(r.get("fix"), r["item"])

    def test_old_freecad_is_missing(self):
        from agentlink import setup_check

        fc = {"where": "/x", "bin": "/x/bin", "lib": "/x/lib", "python": "/x/bin/python", "cmd": None}
        with mock.patch.object(setup_check, "freecad_candidates", return_value=[fc]), \
                mock.patch.object(setup_check, "ask_freecad", return_value=("0.22.0", "/nowhere")):
            rows = setup_check.check()
        self.assertEqual([r["state"] for r in rows if r["item"] == "FreeCAD"], ["missing"])

    def test_headless_flag(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "agentlink_headless.py"), "--check", "--json", "--no-ask"],
                           capture_output=True, text=True, timeout=60)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        self.assertIn("items", json.loads(r.stdout))

    def test_launcher_without_freecad(self):
        from agentlink import launch, setup_check

        err = io.StringIO()
        with mock.patch.object(setup_check, "freecad_candidates", return_value=[]), contextlib.redirect_stderr(err):
            self.assertEqual(launch.main([]), 2)
        self.assertIn("--check", err.getvalue())


if __name__ == "__main__":
    unittest.main()

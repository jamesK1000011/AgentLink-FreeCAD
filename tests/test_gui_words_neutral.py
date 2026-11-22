# SPDX-License-Identifier: LGPL-2.1-or-later
# The words the person sees in FreeCAD (panel, menus, tooltips, dialogs,
# Setup check, captions) are neutral: Agent Link works with any MCP client.
# "Claude" may appear only where the help is about Claude Desktop itself
# (its extension, its log folder). No FreeCAD needed: string literals are
# read from the source.
import ast
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
GUI = ["InitGui.py", "agentlink/panel.py", "agentlink/panel_tabs.py", "agentlink/commands.py", "agentlink/setup_check.py",
       "agentlink/launcher_check.py", "agentlink/echo.py", "agentlink/quit_guard.py", "agentlink/gui_events.py",
       "agentlink/gui_input.py", "agentlink/overlay.py", "agentlink/usage.py"]
# Allowed: help about Claude Desktop itself, and its log folder's name.
ALLOWED = re.compile(r"Claude Desktop|^Claude$")


def strings(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                docs.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            yield node.lineno, node.value


def offending():
    bad = []
    for rel in GUI:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        for line, s in strings(p):
            if "Claude" in s and not ALLOWED.search(s):
                bad.append(f"{rel}:{line}: {s[:90]!r}")
    return bad


class NeutralWords(unittest.TestCase):
    def test_no_client_name_in_gui_words(self):
        bad = offending()
        self.assertEqual(bad, [], "GUI words name Claude for a general function; say 'the agent' or 'your AI assistant', "
                                  "or name Claude Desktop only where the help is about it:\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()

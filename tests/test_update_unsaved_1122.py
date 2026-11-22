# SPDX-License-Identifier: LGPL-2.1-or-later
"""agentlink_update with documents changed since their save: it refuses
first and names them (live, 22 Nov: restarts brought a person's assembly
back only as recovered copies). Also: a recovered copy kept beside its
original is still known as a copy here."""
import json
import os
import re
import shutil
import subprocess
import unittest

from agentlink import store, supervise

SRC = os.path.join(os.path.dirname(__file__), "..", "packaging", "mcpb", "server", "index.js")


class UnsavedGate(unittest.TestCase):
    def setUp(self):
        self.js = open(SRC, encoding="utf-8").read()

    def test_the_gate_is_before_the_update(self):
        i = self.js.index("const held = unsavedDocs(readHeartbeat())")
        self.assertLess(i, self.js.index("selfUpdate(msg.id)", i))
        self.assertIn("args.unsaved !== 'recover'", self.js)
        self.assertIn("enum: ['recover']", self.js)

    @unittest.skipUnless(shutil.which("node"), "node is not here")
    def test_unsaved_docs(self):
        fn = re.search(r"function unsavedDocs\(hb\) \{.*?\n\}", self.js, re.S).group(0)
        hb = {"docs": [{"name": "Bicycle", "label": "Bicycle", "modified": True}, {"name": "Bar", "label": "Bar"}, {"name": "X", "modified": True}]}
        out = subprocess.run(["node", "-e", fn + f"\nconsole.log(JSON.stringify([unsavedDocs({json.dumps(hb)}), unsavedDocs(null)]))"],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), [["Bicycle", "X"], []])


class CopyBeside(unittest.TestCase):
    def test_a_copy_beside_its_original_is_a_copy(self):
        f = "/work/BikeParts/Bicycle.agentlink-recovered-20261122-091600.FCStd"
        self.assertTrue(supervise.temp_copy(f))
        self.assertTrue(store.copy_file(f))
        self.assertFalse(supervise.temp_copy("/work/BikeParts/Bicycle.FCStd"))


if __name__ == "__main__":
    unittest.main()

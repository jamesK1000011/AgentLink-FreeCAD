# SPDX-License-Identifier: LGPL-2.1-or-later
# A copy opened from a temporary folder during a call (a recovered copy) is
# marked unchanged: renaming and recomputing it as it opened set the
# window's modified mark, so the heartbeat read it as changed for ever and
# every restart recovered it again (a copy of a copy). With a stand-in
# FreeCAD.
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class Doc:
    def __init__(self, name, file):
        self.Name, self.FileName, self.purged = name, file, False

    def purgeTouched(self):
        self.purged = True


class SettleCopies(unittest.TestCase):
    def setUp(self):
        self.docs = {"Mine": Doc("Mine", "/srv/parts/Mine.FCStd")}
        fc = types.ModuleType("FreeCAD")
        fc.GuiUp = False
        fc.listDocuments = lambda: dict(self.docs)
        fc.getDocument = lambda n: self.docs.get(n)
        self.patch = mock.patch.dict(sys.modules, {"FreeCAD": fc})
        self.patch.start()
        from agentlink import protocol, store

        self.store, self.protocol = store, protocol

    def tearDown(self):
        self.patch.stop()

    def test_copies_opened_in_the_call_are_settled(self):
        tmp = tempfile.gettempdir()

        def call():
            self.docs["Grip_recovered"] = Doc("Grip_recovered", os.path.join(tmp, "agentlink-recovered-x", "Grip_recovered.FCStd"))
            self.docs["Plate"] = Doc("Plate", "/srv/parts/Plate.FCStd")
            self.docs["Ck"] = Doc("Ck", "/srv/x/agentlink-restore-1/Ck.FCStd")
            return {"ok": True}

        self.assertEqual(self.protocol._settled(call), {"ok": True})
        self.assertTrue(self.docs["Grip_recovered"].purged)
        self.assertTrue(self.docs["Ck"].purged)
        self.assertFalse(self.docs["Plate"].purged)  # the person's file: as the call left it
        self.assertFalse(self.docs["Mine"].purged)  # open before the call

    def test_copy_file(self):
        self.assertTrue(self.store.copy_file("/var/x/agentlink-recovered-ab/A_recovered.FCStd"))
        self.assertTrue(self.store.copy_file(os.path.join(tempfile.gettempdir(), "a", "b.FCStd")))
        self.assertFalse(self.store.copy_file("/srv/parts/A.FCStd"))
        self.assertFalse(self.store.copy_file(""))


if __name__ == "__main__":
    unittest.main()

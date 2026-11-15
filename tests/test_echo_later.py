# SPDX-License-Identifier: LGPL-2.1-or-later
# echo puts a lit button or menu item back after a moment, unless a workbench
# switch deleted it meanwhile (PySide raises RuntimeError on a deleted C++
# object; it showed in the Report view in the GUI pass).
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentlink import echo  # noqa: E402


class Gone:
    def setFont(self, _f):
        raise RuntimeError("Internal C++ object (PySide6.QtGui.QAction) already deleted.")


class Here:
    font = None

    def setFont(self, f):
        self.font = f


class Later(unittest.TestCase):
    def test_deleted_is_skipped(self):
        echo._later(Gone(), "setFont", "old")

    def test_live_is_restored(self):
        h = Here()
        echo._later(h, "setFont", "old")
        self.assertEqual(h.font, "old")


class GoneLabel:
    def isVisible(self):
        raise RuntimeError("Internal C++ object (PySide6.QtWidgets.QLabel) already deleted.")


class Label:
    def __init__(self, text):
        self.t, self.shown = text, True

    def isVisible(self):
        return self.shown

    def text(self):
        return self.t

    def hide(self):
        self.shown = False


class CaptionLater(unittest.TestCase):
    def test_deleted_label_is_skipped(self):
        echo._hide_later(GoneLabel(), "done")

    def test_label_hidden(self):
        lbl = Label("✦ Agent: done")
        echo._hide_later(lbl, "done")
        self.assertFalse(lbl.shown)

    def test_newer_words_stay(self):
        lbl = Label("✦ Agent: next")
        echo._hide_later(lbl, "done")
        self.assertTrue(lbl.shown)


if __name__ == "__main__":
    unittest.main()

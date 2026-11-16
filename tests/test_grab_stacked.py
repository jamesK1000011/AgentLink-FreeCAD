# SPDX-License-Identifier: LGPL-2.1-or-later
# A window shot puts back what is stacked over the 3D view inside its
# window (the agent's caption, an add-on's callout on the view), not the
# main window's own children (the overlay, docks): grab.stacked_over.
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
_stubbed = [n for n in ("FreeCAD", "FreeCADGui") if n not in sys.modules]
for name in _stubbed:  # grab.py imports FreeCAD; stand-ins only while it loads
    sys.modules[name] = types.ModuleType(name)
try:
    from agentlink import grab  # noqa: E402
finally:
    for name in _stubbed:
        sys.modules.pop(name, None)


class W:
    def __init__(self, name, parent=None, visible=True, window=False):
        self.name, self.parent, self.visible, self.window = name, parent, visible, window
        self.kids = []
        if parent is not None:
            parent.kids.append(self)

    def parentWidget(self):
        return self.parent

    def children(self):
        return list(self.kids)

    def isWidgetType(self):
        return True

    def isVisible(self):
        return self.visible

    def isWindow(self):
        return self.window

    def raise_(self):
        self.parent.kids.remove(self)
        self.parent.kids.append(self)

    def __repr__(self):
        return self.name


class StackedOver(unittest.TestCase):
    def setUp(self):
        self.mw = W("mainwindow")
        self.dock = W("dock", self.mw)
        self.mdi = W("mdi", self.mw)
        self.overlay = W("overlay", self.mw)  # the main window's own: left out
        self.view = W("View3DInventor", self.mdi)
        self.gl = W("viewport", self.view)

    def test_callout_and_caption_on_the_view_come_back(self):
        callout = W("AddonCallout", self.view)
        arrow = W("AddonCalloutArrow", self.view)
        caption = W("caption", self.view)
        W("hidden", self.view, visible=False)
        W("dialog", self.view, window=True)
        self.assertEqual(grab.stacked_over(self.gl, self.mw), [callout, arrow, caption])

    def test_what_is_below_the_view_is_left_out(self):
        under = W("under", self.view)
        under.raise_()
        self.gl.raise_()  # the view's surface above it
        self.assertEqual(grab.stacked_over(self.gl, self.mw), [])

    def test_no_view(self):
        self.assertEqual(grab.stacked_over(None, self.mw), [])


if __name__ == "__main__":
    unittest.main()

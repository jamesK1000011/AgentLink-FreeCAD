# SPDX-License-Identifier: LGPL-2.1-or-later
# A picture of the FreeCAD window (or a part of it) as the person sees it:
# Qt draws the widgets, and the 3D view, which OpenGL draws and a widget
# grab leaves blank, is rendered by FreeCAD and painted into its place.
# No screen-recording permission: FreeCAD draws it all itself.

import os

import FreeCAD
import FreeCADGui


def stacked_over(gl, target):
    """The visible widgets stacked above gl inside its 3D view's window: at
    each level from gl's parent up to (not including) target, the siblings
    after the branch that holds gl (Qt paints later children on top; raise_
    moves a child last). The main window's own children (Agent Link's
    overlay, docks) are left out: the GL surface paints over those."""
    out = []
    branch, parent = gl, gl.parentWidget() if gl is not None else None
    while parent is not None and branch is not target and parent is not target:
        kids = [k for k in parent.children() if hasattr(k, "isWidgetType") and k.isWidgetType()]
        if branch in kids:
            out += [k for k in kids[kids.index(branch) + 1:] if k.isVisible() and not k.isWindow()]
        branch, parent = parent, parent.parentWidget()
    return out


def grab_window(target=None):
    gui = FreeCADGui
    target = target or gui.getMainWindow()
    gui.updateGui()
    pix = target.grab()
    # The 3D view is drawn by OpenGL, which a widget grab leaves blank:
    # render it the way view_snapshot does and paint it in its place.
    try:
        import tempfile

        from PySide import QtCore, QtGui

        QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
        gd = gui.ActiveDocument
        view = gd.activeView() if gd else None
        gl = None
        try:  # FreeCAD 1.x: the view's own QGraphicsView and its viewport
            gv = view.graphicsView() if view is not None else None
            gl = gv.viewport() if gv is not None and gv.viewport() is not None else gv
        except Exception:
            gl = None
        if gl is None or not gl.isVisible() or not (gl is target or target.isAncestorOf(gl)):
            gl = next((w for w in target.findChildren(QtW.QWidget) if w.isVisible() and (type(w).__name__ in ("QuarterWidget", "QOpenGLWidget", "QGLWidget") or any(n in w.metaObject().className() for n in ("Quarter", "View3DInventor")))), None)
        if view is not None and gl is not None and hasattr(view, "saveImage"):
            tmp = os.path.join(tempfile.gettempdir(), "agentlink_view.png")
            ratio = getattr(pix, "devicePixelRatio", lambda: 1.0)()
            view.saveImage(tmp, int(gl.width() * ratio), int(gl.height() * ratio), "Current")
            img = QtGui.QImage(tmp)
            painter = QtGui.QPainter(pix)
            painter.drawImage(QtCore.QRect(gl.mapTo(target, QtCore.QPoint(0, 0)), gl.size()), img)
            # What floats over the view goes back on top: the agent's caption,
            # widgets an add-on put on the view (a number field on a grip, a
            # callout) and anything else stacked above it.
            over = [lbl for lbl in target.findChildren(QtW.QLabel) if lbl.isVisible() and lbl.text().startswith("✦")]
            over += [w for w in gl.findChildren(QtW.QWidget) if w.isVisible() and w.parentWidget() is gl and w not in over]
            glr = QtCore.QRect(gl.mapTo(target, QtCore.QPoint(0, 0)), gl.size())
            for w in stacked_over(gl, target):
                if w not in over and QtCore.QRect(w.mapTo(target, QtCore.QPoint(0, 0)), w.size()).intersects(glr):
                    over.append(w)
            for w in over:
                painter.drawPixmap(w.mapTo(target, QtCore.QPoint(0, 0)), w.grab())
            painter.end()
    except Exception as e:
        FreeCAD.Console.PrintLog(f"Agent Link window_snapshot: 3D view not painted in ({e})\n")
    return pix

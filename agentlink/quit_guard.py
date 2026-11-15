# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD 1.1 on macOS crashes as it quits: Qt quits through
# -[NSApplication terminate:], which calls exit() from inside the main
# window's closeEvent, and PySide 6.8's teardown of its Python-held Qt
# objects (Shiboken::BindingManager's destructor) then segfaults. Every
# quit, and every app_restart, crashed this way, so FreeCAD found recovery
# files at its next start and showed Document Recovery each time.
#
# Once the window is closing, a C-level exit handler is registered. exit()
# runs handlers in the reverse order they were registered, so this one runs
# before PySide's teardown: it writes FreeCAD's settings (the step the crash
# skipped) and ends the process at once with status 0. Only on macOS, only
# with the GUI up, only once the window has accepted closing, so Python is
# still running when the handler is called.
import os
import sys

_state = {"handler": None, "filter": None}


def _bye():
    try:
        import FreeCAD

        FreeCAD.saveParameter()
    except Exception:
        pass
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(0)


def arm():
    """Register the exit handler (once)."""
    if _state["handler"] is not None:
        return False
    import ctypes

    # __cxa_atexit is exported by libSystem and glibc alike (glibc keeps
    # atexit itself out of its shared library).
    handler = ctypes.CFUNCTYPE(None, ctypes.c_void_p)(lambda _arg: _bye())
    try:
        if ctypes.CDLL(None).__cxa_atexit(handler, None, None) != 0:
            return False
    except AttributeError:
        return False
    _state["handler"] = handler
    return True


def install(mw=None):
    """Watch the main window: when its close is accepted, arm the handler."""
    if sys.platform != "darwin" or _state["filter"] is not None:
        return False
    try:
        import FreeCAD

        if not FreeCAD.GuiUp:
            return False
        from PySide import QtCore

        if mw is None:
            import FreeCADGui

            mw = FreeCADGui.getMainWindow()
    except Exception:
        return False

    class _Watch(QtCore.QObject):
        def eventFilter(self, obj, ev):
            if ev.type() == QtCore.QEvent.Type.Close:
                # FreeCAD's own closeEvent runs after this filter and may ask
                # about unsaved documents; arming early is harmless, as the
                # handler only runs if the process really exits.
                arm()
            return False

    _state["filter"] = _Watch(mw)
    mw.installEventFilter(_state["filter"])
    return True

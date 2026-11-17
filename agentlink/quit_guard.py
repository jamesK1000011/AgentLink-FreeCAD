# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD 1.1 on macOS crashes as it quits: Qt quits through
# -[NSApplication terminate:], which calls exit() from inside the main
# window's closeEvent, and PySide 6.8's teardown of its Python-held Qt
# objects (Shiboken::BindingManager's destructor) then segfaults. Every
# quit, and every app_restart, crashed this way, so FreeCAD found recovery
# files at its next start and showed Document Recovery each time.
#
# Once the window is closing, C-level exit handlers are registered. exit()
# runs handlers in the reverse order they were registered, so these run
# before PySide's teardown: libc's fflush(NULL) writes out C stdio buffers,
# then libc's _exit(NULL), i.e. _exit(0), ends the process at once with
# status 0. Both are plain C functions taken from libc: no Python callback
# is registered, because a quit can also go the normal way (Python is
# finalized first, then exit() runs the handlers), and a ctypes callback
# entered then segfaults in PyGILState_Ensure (seen on the Mac, 17 Nov).
# FreeCAD's settings (the step the crash skipped) are written while Python
# still runs: when the handlers are armed, and again when the main window
# hides after its close was accepted (MainWindow::closeEvent has then saved
# the window's geometry). Only on macOS, only with the GUI up.
import os
import sys

_state = {"armed": False, "filter": None, "lib": None}


def save_settings():
    """Write FreeCAD's parameters and flush Python's streams (Python alive)."""
    ok = True
    try:
        import FreeCAD

        FreeCAD.saveParameter()
    except Exception:
        ok = False
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    return ok


def _libc():
    import ctypes

    return _state["lib"] or ctypes.CDLL(None)


def arm(save=True):
    """Register the C exit handlers (once). No Python code runs at exit."""
    if _state["armed"]:
        return False
    import ctypes

    if save:
        save_settings()
    try:
        lib = _libc()
        reg = lib.__cxa_atexit
        # __cxa_atexit is exported by libSystem and glibc alike (glibc keeps
        # atexit itself out of its shared library). Plain C addresses only.
        quit_now = ctypes.cast(lib._exit, ctypes.c_void_p).value
        flush = ctypes.cast(lib.fflush, ctypes.c_void_p).value
    except (AttributeError, OSError, TypeError):
        return False
    if not quit_now:
        return False
    reg.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    reg.restype = ctypes.c_int
    # Reverse order at exit: fflush(NULL) first, then _exit(0).
    if reg(quit_now, None, None) != 0:
        return False
    _state["armed"] = True
    if flush:
        reg(flush, None, None)
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
            try:
                t = ev.type()
                if t == QtCore.QEvent.Type.Close:
                    # FreeCAD's own closeEvent runs after this filter and may
                    # ask about unsaved documents; arming early is harmless,
                    # as the handlers only run if the process really exits.
                    arm()
                elif t == QtCore.QEvent.Type.Hide and _state["armed"]:
                    # The close was accepted: the window's settings are now
                    # in the parameters; write them while Python runs.
                    save_settings()
            except Exception:
                pass
            return False

    _state["filter"] = _Watch(mw)
    mw.installEventFilter(_state["filter"])
    return True

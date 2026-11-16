# SPDX-License-Identifier: LGPL-2.1-or-later
# This add-on's own copy; it was AddonKit's addonkit.techdraw, retired 14 Nov 2026.
"""TechDraw helpers FreeCAD add-ons share (moved from Agent Link for FreeCAD
on 14 Nov 2026). Needs FreeCAD's TechDraw; Qt only when there is no window."""


def wait_views(views_, timeout=30.0):
    """TechDraw works out a view's lines on another thread and takes them up
    when Qt's event loop says it is done; with no window nothing runs that
    loop, so it is run here until every view has its lines. Seconds waited,
    or None when they were there at once."""
    import time

    def ready():
        try:
            return all(v.getVisibleEdges() for v in views_)
        except Exception:
            return False

    if ready():
        return None
    try:
        from PySide import QtCore
    except ImportError:
        try:
            from PySide2 import QtCore
        except ImportError:
            return None
    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    t0 = time.time()
    while time.time() - t0 < timeout:
        pump(app)
        if ready():
            break
        time.sleep(0.02)
    for v in views_:
        try:
            v.recompute()
        except Exception:
            pass
    return round(time.time() - t0, 2)


# Errors raised by someone else's timer or slot while the loop was pumped
# here (PySide2 hands them to the caller of processEvents): logged and kept,
# never the TechDraw call's own failure.
PUMP_ERRORS = []


def pump(app):
    """app.processEvents(), an error from what it ran logged, not raised."""
    try:
        app.processEvents()
    except Exception:  # noqa: BLE001
        import sys
        import traceback

        tb = traceback.format_exc()
        PUMP_ERRORS.append(tb[-2000:])
        del PUMP_ERRORS[:-5]
        sys.stderr.write("Agent Link: an error raised while TechDraw's lines were awaited (not TechDraw's):\n" + tb)

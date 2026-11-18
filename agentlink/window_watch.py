# SPDX-License-Identifier: LGPL-2.1-or-later
# The FreeCAD window going down and coming back, as the supervisor sees it
# (finding 52). No mark file and no fixed wait: the supervisor is told that
# a restart comes (app_restart answered "restarting", or the launcher's
# AGENTLINK_WINDOW_RESTART after agentlink_update), and the window is back
# at the first heartbeat (~/AgentLink/heartbeat.json) of a NEW pid that
# pairs. macOS's launch and quit notifications (NSWorkspace, through
# pyobjc) say sooner that FreeCAD quit or started; without pyobjc the pid of
# the heartbeat is polled. Between the quit and the pairing, calls wait
# with a time limit. After the limit they fail with clear words. They never
# go to the hidden FreeCAD without a word. No FreeCAD here: plain Python,
# and every outside source is a stand-in in the tests.

import json
import os
import threading
import time

# A call waits this long for the window that starts again: under the
# supervisor's 60 s move to the background (supervise.DETACH_AFTER), so the
# call's own clear answer goes first.
WAIT = float(os.environ.get("AGENTLINK_RESTART_WAIT", "45"))
# A restart that never paired is given up after this: the next call is
# told that the window did not come back, and the hidden FreeCAD takes the
# calls after it.
GIVE_UP = float(os.environ.get("AGENTLINK_RESTART_GIVE_UP", "600"))
# A heartbeat older than this is not the window's word now.
FRESH = 10.0
FREECAD_IDS = ("org.freecad.freecad", "org.freecadweb.freecad")


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def restart_from_env(value=None):
    """The launcher's word that it restarted the window (agentlink_update):
    { pid, t, pinned } or None."""
    raw = os.environ.get("AGENTLINK_WINDOW_RESTART") if value is None else value
    if not raw:
        return None
    try:
        got = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(got, dict) or not got.get("pid"):
        return None
    return got


def is_freecad(app):
    """An NSRunningApplication-like row (bundle id or name) that is FreeCAD."""
    bid = str((app or {}).get("bundle") or "").lower()
    name = str((app or {}).get("name") or "").lower()
    return bid in FREECAD_IDS or bid.startswith("org.freecad") or name == "freecad"


class Watch:
    """What the window is doing now: None (no restart in hand), or a
    restart { old, t, pinned, quit, launched } that waits for the first
    heartbeat of a new pid with pairing.

    heartbeat(): the heartbeat file as a dict (or None). alive(pid): the
    process is there. clock and sleep: time.time and time.sleep."""

    def __init__(self, heartbeat, alive=_pid_alive, clock=time.time, sleep=time.sleep):
        self.heartbeat = heartbeat
        self.alive = alive
        self.clock = clock
        self.sleep = sleep
        self.restart = None
        self.lost = None  # a restart given up: said once at the next call
        self.lock = threading.Lock()

    # ---- what the supervisor is told ----------------------------------------------------

    def expect(self, old_pid, pinned=None, t=None, why="app_restart"):
        """A restart comes: old_pid quits, a new FreeCAD starts."""
        with self.lock:
            self.restart = {"old": old_pid, "t": self.clock() if t is None else float(t), "pinned": pinned, "why": why,
                            "quit": not self.alive(old_pid) if old_pid else True, "launched": None}
            self.lost = None

    def launched(self, pid):
        """macOS says FreeCAD started (pid). With no restart in hand, a
        FreeCAD started by the person is waited for as well: its link comes
        up within seconds."""
        with self.lock:
            if self.restart is None:
                hb = self.heartbeat() or {}
                if hb.get("pid") == pid and self._paired(hb, None, 0):
                    return
                self.restart = {"old": hb.get("pid") if hb.get("pid") != pid else None, "t": self.clock(), "pinned": None,
                                "why": "FreeCAD started", "quit": True, "launched": pid}
                return
            self.restart["launched"] = pid

    def terminated(self, pid):
        """macOS says FreeCAD quit (pid)."""
        with self.lock:
            if self.restart is not None and self.restart.get("old") == pid:
                self.restart["quit"] = True

    # ---- reading ------------------------------------------------------------------------

    def _paired(self, hb, old, since):
        if not isinstance(hb, dict) or not hb.get("pairing") or not hb.get("pid"):
            return False
        if old is not None and hb.get("pid") == old:
            return False
        try:
            t = float(hb.get("t") or 0)
        except (TypeError, ValueError):
            return False
        return t >= since - 1.0 and self.clock() - t < FRESH

    def back(self):
        """The new window's heartbeat (a new pid, pairing, fresh) when a
        restart is in hand and it is there, else None."""
        r = self.restart
        if r is None:
            return None
        hb = self.heartbeat()
        return hb if self._paired(hb, r.get("old"), r["t"]) else None

    def pending(self):
        """A restart in hand that has not paired yet (False once given up)."""
        r = self.restart
        if r is None:
            return False
        if r.get("old") and not r.get("quit") and not self.alive(r["old"]):
            r["quit"] = True
        if self.clock() - r["t"] > GIVE_UP:
            with self.lock:
                self.lost = self.restart
                self.restart = None
            return False
        return True

    def done(self):
        """The new window paired: the restart is over. Its record (for the
        pinned document) or None."""
        with self.lock:
            r, self.restart = self.restart, None
        return r

    def take_lost(self):
        with self.lock:
            r, self.lost = self.lost, None
        return r

    def wait(self, ready, limit=None, step=0.5):
        """While a restart is in hand: ready() tried every step seconds, up
        to limit. True once it answers (the restart is over), else the
        words for the call's clear refusal. With no restart in hand: None."""
        if not self.pending():
            return None
        limit = WAIT if limit is None else limit
        t0 = self.clock()
        while True:
            if self.back() is not None and ready():
                return True
            if not self.pending():
                return None if self.lost is None else self.lost_words(self.take_lost())
            waited = self.clock() - t0
            if waited >= limit:
                return self.waiting_words(waited)
            self.sleep(step)

    def waiting_words(self, waited):
        r = self.restart or {}
        if r.get("old") and not r.get("quit"):
            stage = "the old FreeCAD has not quit yet"
        elif r.get("launched"):
            stage = "FreeCAD has started, but its link has not paired yet"
        else:
            stage = "FreeCAD has quit and has not started again yet"
        return (f"FreeCAD is starting again ({r.get('why') or 'a restart'}); no window yet after {int(waited)} s ({stage}). "
                "This call was not run. Call it again in a moment: calls wait for the window and never go to the hidden FreeCAD meanwhile. "
                "app_force_restart if the window does not come back.")

    @staticmethod
    def lost_words(r):
        mins = int(GIVE_UP // 60)
        return (f"The FreeCAD window did not come back within {mins} min after {(r or {}).get('why') or 'its restart'}. This call was not run. "
                "The next calls run in the hidden FreeCAD, which has an empty document of its own. Ask the person to open FreeCAD again, or app_force_restart.")


# ---- macOS: launch and quit notifications (optional) ---------------------------------------

def mac_events(watch):
    """NSWorkspace's didLaunch and didTerminate notifications for FreeCAD,
    handed to watch on a thread of their own. False when pyobjc is not
    there (the Python FreeCAD ships has none): the heartbeat's pid is
    polled instead, which gives the same states a little later."""
    try:
        from AppKit import NSWorkspace  # noqa: F401
        from Foundation import NSDate, NSOperationQueue, NSRunLoop  # noqa: F401
    except Exception:  # noqa: BLE001 — no pyobjc
        return False

    def run():
        try:
            from AppKit import NSWorkspace
            from Foundation import NSDate, NSOperationQueue, NSRunLoop

            nc = NSWorkspace.sharedWorkspace().notificationCenter()
            q = NSOperationQueue.alloc().init()

            def row(note):
                app = note.userInfo().get("NSWorkspaceApplicationKey") if note.userInfo() else None
                if app is None:
                    return None
                return {"bundle": str(app.bundleIdentifier() or ""), "name": str(app.localizedName() or ""), "pid": int(app.processIdentifier())}

            def on_launch(note):
                r = row(note)
                if r and is_freecad(r):
                    watch.launched(r["pid"])

            def on_quit(note):
                r = row(note)
                if r and is_freecad(r):
                    watch.terminated(r["pid"])

            nc.addObserverForName_object_queue_usingBlock_("NSWorkspaceDidLaunchApplicationNotification", None, q, on_launch)
            nc.addObserverForName_object_queue_usingBlock_("NSWorkspaceDidTerminateApplicationNotification", None, q, on_quit)
            loop = NSRunLoop.currentRunLoop()
            while True:
                loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(1.0))
        except Exception:  # noqa: BLE001 — the polling still covers it
            return

    threading.Thread(target=run, name="agentlink-mac-events", daemon=True).start()
    return True


# ---- the agent's pinned document after a restart (finding 40) ------------------------------

def pinned_of(hb):
    """The agent's pinned document in a heartbeat: { name, label, file } or None."""
    if not isinstance(hb, dict) or not hb.get("pinned"):
        return None
    name = hb["pinned"]
    for d in hb.get("docs") or []:
        if isinstance(d, dict) and d.get("name") == name:
            return {"name": name, "label": d.get("label"), "file": d.get("file") or ""}
    return {"name": name, "label": None, "file": ""}


def pin_target(pinned, docs):
    """The document of the new window that is the pinned one of before:
    by its file, else by its label, else a "(recovered …)" copy of its
    label. Its name, or None."""
    if not pinned:
        return None
    rows = [d for d in docs or [] if isinstance(d, dict) and d.get("name")]
    f = pinned.get("file") or ""
    if f:
        for d in rows:
            if d.get("file") and os.path.abspath(d["file"]) == os.path.abspath(f):
                return d["name"]
    lab = pinned.get("label")
    if lab:
        for d in rows:
            if d.get("label") == lab:
                return d["name"]
        for d in rows:
            if str(d.get("label") or "").startswith(lab + " (recovered"):
                return d["name"]
    for d in rows:
        if d.get("name") == pinned.get("name") and not f:
            return d["name"]
    return None

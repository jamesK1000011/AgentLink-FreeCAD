<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Jobs and restart (18 Nov 2026)

Findings 40, 41, 45, 52, 62 and 66, and the goal "no prejudging".
The owner decided the approach on 18 Nov. This note records it.

## 1. The window restart (finding 52)

Fault: after `agentlink_update`, calls went to the hidden FreeCAD without a word.
The new supervisor did not know that the window was restarting.

Rules:

- Do not use a mark file to decide the wait. Do not use a fixed wait.
- The supervisor learns that a restart comes from one of these:
  - the window answers `app_restart` with `restarting: true`;
  - the launcher sets `AGENTLINK_WINDOW_RESTART` (`{ pid, t, pinned }`) for the
    supervisor that it starts after `agentlink_update`;
  - macOS says that FreeCAD started (NSWorkspace didLaunch).
- The window is back at the first heartbeat (`~/AgentLink/heartbeat.json`)
  with a NEW pid and `pairing`.
- macOS didLaunch and didTerminate (pyobjc) are optional. Without pyobjc, the
  supervisor polls the pid of the old heartbeat.
- Between the quit and the pairing, each call waits up to 45 s
  (`AGENTLINK_RESTART_WAIT`). Then it fails with clear words:
  "FreeCAD is starting again; no window yet after N s".
- A call never goes to the hidden FreeCAD without a word.
- After 10 min with no window (`AGENTLINK_RESTART_GIVE_UP`), the next call
  says that the window did not come back. The calls after it go to the hidden FreeCAD.

Code: `agentlink/window_watch.py` (plain Python, stand-ins in the tests),
`supervise.Window._ready`, `packaging/mcpb/server/index.js` (`restartWord`).
The window keeps `restart_mark.py` for its own work only: the documents
to open again and the dialogs at start. The supervisor does not read it.

## 2. The pinned document after a restart (finding 40)

Fault: after a restart, a call went to another document.

Rule: the supervisor reads the pinned document from the old heartbeat
(`pinned`, with its label and file). When the new window pairs, the supervisor
finds that document (by file, then label, then a "(recovered …)" copy) and
sends `doc_switch` to it. This occurs after `app_restart`, after
`agentlink_update`, and after a crash or a forced restart.

## 3. Jobs: no prejudging (findings 41, 45)

Live data (18 Nov): an export estimated at 2 min took 0.48 s. A loft
estimated at 3 min took 6.4 s. A batch guess of 766 s took 7 s.

Rules:

- Every call starts normally. No estimate refuses, holds or delays a call.
- The supervisor times each call from when it comes in. If a call has no
  answer after 60 s (`AGENTLINK_DETACH_AFTER`), the supervisor answers it with a
  job id (`call-N`). The call goes on where it runs. The supervisor keeps
  its real answer.
- A client drops a call after about 80 s. The job answer comes at 60 s, so the
  client always gets an answer.
- `job_status` is answered by the supervisor at once. It never waits behind a
  call in FreeCAD:
  - `call-N`: from the supervisor's table;
  - `job-…` (a heavy read on a worker thread): asked of the window on a
    connection of its own, or of the hidden FreeCAD on a thread of its own
    (`protocol.serve_lines`), with a time limit and a clear "busy" answer.
- `job_start { tool, arguments, wait }` becomes the call itself in the
  supervisor. It runs where calls run: on the window's thread for the document
  work. `wait: false` gives the id at once. This fixes finding 45: no export runs
  on a worker thread that holds FreeCAD's Python while the heartbeat goes stale.
- Estimates stay as logged data only (`queue.json` timings).
  `heavy.Gate` does not refuse. `jobs.wanted` decides by the kind of tool only.
  A batch does not skip a call on a guess.

What may run off the Qt main thread: an OCC tessellation and a file write
on a copied shape. A document change may not. FreeCAD's Python wrappers keep
the GIL during most OCC calls. Thus a worker thread does not keep the window
free during a long C++ call. That is why the supervisor, a separate process,
keeps the answers.

## 4. The watchdog: only true hangs

Rule: the watchdog stops FreeCAD only when all of these are true:

- the call is past its limit (120 s, or its own `timeout` + 60 s);
- there is no heartbeat for 60 s;
- FreeCAD and its child processes did no CPU work for 60 s (`ps`, `AGENTLINK_STALL`).

A long OCC call keeps the CPU busy, so the watchdog does not stop it.
With no heartbeat for 2 h (`AGENTLINK_HANG_CEILING`), the watchdog stops FreeCAD
even when the CPU is busy. The person can use `app_force_restart` sooner.
The rule for a nested event loop is the same as before, but with no estimate.

## 5. doc_close with discard (finding 62)

Fault: `doc_close { discard: true }` on a modified document that was never saved
showed FreeCAD's "Save all changes to document … before closing?" dialog.
"Don't Save" from `dialog_answer` then crashed FreeCAD.

Probable cause (not proved live): FreeCAD's `Gui::Document::canClose` asks when the window's document is
marked modified and a view closes before the document starts to close.
The echo does not run `Std_CloseActiveWindow`: it only lights the button.

Live clue (18 Nov): the same discard worked after the Tutor's lesson was
stopped. In the failing case, the lesson (done at 21/21) still held its
document: its rings, its timers and its watchers.

Rules:

- `close_doc` first sends the hook event `document_closing(session, name)`.
  An add-on that holds the document lets go of it first. The Tutor must
  stop its lesson on it there (in the Tutor repository: not done here).
- `close_doc` removes the window's "modified" mark (`Gui Document.Modified = False`)
  before it leaves the edit, and again after. Then `canClose` has nothing to
  ask. The steps of `doc_close` close a changed document only with `discard: true`.
- `dialog_answer` refuses Save and Don't Save on that dialog ("Unsaved
  Document", `confirmSave`) while another call closes the document. It tells
  you to press Cancel, then to use `doc_close { discard: true }`. Cancel is always
  pressed. With no call in hand, the press is the person's own and is done.

## 6. part_boolean fuzzy retry (finding 66)

Fault: a fuse of two valid smooth lofts that overlap by about 2 mm failed with
"OCC made an invalid result".

Rule: before the refusal, the tool tries again once with a fuzzy value
of 1e-4 and then 1e-3 of the base's box diagonal. The answer gives `fuzzy` and
`fuzzyNote` when a fuzzy value was used. The refusal gives the values that it tried.

## Status

Fixed on main, not yet seen live. The main session runs the live checks.

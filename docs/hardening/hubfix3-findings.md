# hubfix3: findings (16 Nov 2026)

Checkout: d17 at a399f58. Patch: `hubfix3.patch` (`git add -A -N; git diff a399f58`, FILES excluded).
Nothing here was run in FreeCAD. "Source" is FreeCAD 1.1's source as checked out (the Mac runs 1.1.3);
"tested" means plain-Python tests on stand-ins (`tests/test_hubfix3.py`, 23 run, 1 skipped: it needs FreeCAD
and was written unrun). Full suite here: 1021 passed, 348 skipped. `tool_index.py --check` and
`tool_summary.py --check` pass. Changed files compile under python3.11.

## Before this is pinned

1. **Regenerate FILES.** New: `tests/test_hubfix3.py`. `tests/test_files.py` fails until then (expected).
2. Files touched: `agentlink/docstates.py`, `jobs.py`, `protocol.py`, `tools.py`, `gui_link.py` (one line),
   `docs/hooks.md`. No family file, no `data/tools.json`, no `families/app.py`. No description was changed.
3. Two refusals gained words (both still say what to do next): background's refusal for a read that runs in
   place, and job_start's.

---

## 1. steps, tx, calls (and meta, checks) crossed documents — fixed, per document

- **Cause.** They were plain attributes of `Session`; only `Session.switch` (doc_switch, doc_revert) emptied
  them, and `families/doc.py`'s `switch()` (doc_new, doc_open, doc_close) and the window link set
  `session.doc` and left them. So history_diff compared a step of one document with a step of another,
  `session.calls` (what SafetyNet's macro_save reads, with `c["tx"] <= s.tx`) held two documents' calls
  filtered by a count that was a third stack's, and a checkpoint's "can undo reach it" was wrong after doc_new.
- **Fix.** The same book as `family_state` (`docstates.py`): beside each document's family dict it keeps the
  session's own record `{ steps, meta, tx, calls, checks }` (`docstates.own`, `fresh`, `own_of`). On
  `Session` the five names are properties over the record of the document the session is in
  (`tools.py`, `_own_property`), so every route is covered and no family or add-on needed a change.
  A document left open keeps its record and gets it back; a closed one is let go; one reopened or reverted is
  another document and starts at nothing (told by identity, as before).
  - `Session.switch` no longer empties anything: the record follows the document. doc_switch back to a
    document therefore finds its steps, calls and undo count again (before: emptied).
  - A batch's rollback takes the undone steps off the record of the document it started in, also when a
    call moved the session on (`own_of`; before: only when the session was still there).
  - `gui_link.py`: the line that emptied `steps` and `meta` when the person closed the agent's document is
    gone (it would now empty the record of the document arrived in).
- **The Undecided worry, answered.** "calls deliberately spans documents (a saved macro replays doc_new)":
  doc_new's own call is recorded after the session has moved, so it is the first call of the new document's
  record. A macro saved in a document is now what made that document, starting with its doc_new or
  doc_open. A macro spanning two documents is no longer possible; I think that is right, but it is a change.
- **SafetyNet.** `reopen_copy` (keeps steps, meta, calls; `switch`; puts them back; `tx = 0`) works through
  the setters. Its 118 plain tests pass against this checkout. Its auto-save book (`tx` per document name)
  and checkpoints (`tx` at the time) now compare like with like.
- **Tests.** `OwnRecordPerDocument` (4), `TheSessionsRecord` (2: the real `Session` on a stand-in FreeCAD —
  every route, history_diff's steps per document, an add-on putting a record back, a name reused).
- **Unproven.** Any add-on that kept its own reference to `session.steps` across a document change and
  relied on doc_switch emptying it. I found none in Workshop or ScanRuler's checkout here.
- **Live.** In A: two part_primitive, `history_checkpoint`. `doc_new`. `session_state` → step 0.
  One part_primitive there; `history_diff { since: 0 }` → steps `["part_primitive"]` (one, not three).
  `doc_switch` to A → `session_state` step 2; `history_diff { since: 0 }` → A's two; `history_restore` of the
  checkpoint → taken back by undo (not "from its saved copy"). `macro_save` in A → A's calls only; in the new
  document → doc_new first.

## 2. A skipped geometry check as a background job — not done; it would not be in the background

- **Why not (source).** `TopoShapePy::check` (`src/Mod/Part/App/TopoShapePyImp.cpp:698`) calls
  `TopoShape::analyze` holding Python's lock for the whole check; nothing in that file releases it (no
  `Py_BEGIN_ALLOW_THREADS`), and `isValid` and the booleans are the same. A job's thread inside one such call
  therefore holds the lock until it returns. Agent Link's server is Python on the GUI thread: the next call,
  the wait for the job (`Event.wait` needs the lock to come back) and job_status all stand still for exactly
  as long as the check would have held the call in place. The window would also stop at the first paint that
  needs Python, and the watchdog would see no heartbeat on an ordinary call's deadline.
  Copying the shape first (`shape.copy()`, on the GUI thread) makes the read safe; it does not make it
  concurrent. So: safe to build on `jobs.py`, and pointless.
- **What this says about what exists.** `body_check { background: true }` (which health's `unchecked` line
  recommends) has the same limit for one long check: it does not free the window. It still does one thing
  right — the answer is kept under a job id, so a call the client dropped at 80 s is not lost — so the
  advice stands. Jobs do run beside the window for reads made of many short FreeCAD calls (a thickness map).
  This follows from the source; it was not timed.
- **Recommendation (its own piece of work).** Run the long check in a process of its own: write the shape
  with `exportBrep` (GUI thread, quick), start `freecadcmd` on it as addon_test starts its runs
  (`testrun.py` has the start, the log and the wait), `health.unchecked` names the job, job_status reads the
  verdict from the child's output. It can be given a deadline and stopped, which a thread cannot.
- **Test.** None: nothing changed.

## 3. Reads that drive the document or the window on the way — audited, 32 kept from jobs (2 were), pinned by a scan

`jobs.MOVES_PARTS` is now `jobs.IN_PLACE`, a dict name → what the read does on the way (the old name still
answers). `jobs.IN_PLACE_WHEN` holds reads that run in place only as the document stands.
`jobs.in_place(name, why)` is for an add-on's own (docs/hooks.md, "Reads that must run in place").
`eligible(tool, args, session=None)`; the batch's heavy-read test, `wanted`, `note_slow` and the refusals
pass the session. Background's refusal now says what the read does: "asm_list cannot run as a job — it
changes nothing, but it solves the assembly on the way, which places its parts, which only the window's own
thread may do. Leave background out: it runs as a plain call."

**How a read reached a worker thread before:** `background: true` or job_start on any of them; on its own
when heavy (`keep.HEAVY`: addon_test) or once a run took over 20 s (any of them, e.g. asm_check on a large
assembly, td_export, session_state).

**Unsafe, added** (data entries of `agentlink/data/tools.json`, changes false; the helper is where it happens):

| Tool | What it does on the way | Where |
|---|---|---|
| asm_sweep, asm_motion | already there | `families/assembly.py` sweep_run 558–580 |
| asm_list, asm_check | `asm.solve()`: `AssemblyObject::solve` runs setNewPlacements and redrawJointPlacements | `assembly.py:283` (`status`); `src/Mod/Assembly/App/AssemblyObject.cpp:139–183` |
| asm_export | writes no property, but `exportAsASMT` rebuilds the object's own solver model (mbdAssembly, objectPartMap) that a solve or a drag uses | entry step `asm.exportAsASMT(p)`; `AssemblyObject.cpp:464` |
| sketch_state | `sk.solve()`: `SketchObject::solve` moves the solved geometry in and signals the sketch's view | `families/sketch.py:176`; `src/Mod/Sketcher/App/SketchObject.cpp:535` |
| td_list | views with no lines recomputed, then waited for | `families/techdraw.py:1823, 1838` (`warm`) |
| td_geometry, td_export | `doc().recompute()` twice and a Qt event pump | `techdraw.py:1541–1572` (`recompute`, `settle`) |
| cam_list, cam_library (its export call) | `FreeCAD.setActiveDocument`, which signals the window (it activates an MDI window when the document is not the active one) | `families/cam.py:149`; `src/App/Application.cpp:1033`, `src/Gui/Application.cpp:1265` |
| cam_post | the same, and sets `job.PostProcessorArgs`, puts it back, `purgeTouched` | `cam.py:381–388` |
| robot_run | sets Tcp and the axes at each sample, then the axes back and `doc().recompute()` | `families/robot.py:112, 136–137`; entry steps 8–9 |
| scad_export | `FreeCAD.GuiUp = False` for the whole process while it writes | `families/openscad.py:138–142` |
| scad_status | writes the program it found into FreeCAD's settings (observers run on the writing thread) | `openscad.py:162` |
| bim_export | FreeCAD's exporter works on `FreeCAD.ActiveDocument` and recomputes it | `src/Mod/BIM/importers/exportIFC.py:1637` |
| note_list | follows the notes' faces and writes them back into the document | `families/notes.py:262, 34`; `store.py:91` |
| addon_test | its wait pumps Qt's events "so the window keeps painting": on a worker thread that pumps nothing, and the GUI thread stood waiting for the job. Not a crash; it never did what it was written to do as a job, and it was one on every call (heavy) | `families/dev.py:26–34, 53–64` |

**Unsafe, added** (the hub's own `Tool(…)` reads):

| Tool | What | Where |
|---|---|---|
| history_undo, history_redo | `d.undo()` / `d.redo()`, recompute, snapshot — and both were open to `background: true` | `tools.py:2238` |
| history_diff | a checkpoint older than the session: a document opened, recomputed and closed | `tools.py:752` |
| session_state, tool_groups (now: true) | read the window: workbench, selection, what is open | `tools.py:1189`; `nexthint.py:105` |
| report_read | reads the Report view's widget | `tools.py:967`; `report_watch.py` |
| selection, workbench, cmd_list, menu_list, pref_import, pref_reset | `families/app.py` (read, not edited): the selection, workbench activation, QActions and menus, settings written | their handlers |
| live_run, addon | run other tools, changes among them; drive the Addon Manager | `families/dev.py:143`; `families/unattended.py:285` |

**In place only as the document stands** (`IN_PLACE_WHEN`): fea_heat, fea_buckle, fea_modes when the study
is of one solid of a body of several — `study_body` → `solid_holder` then makes or refreshes a hidden helper
(`doc.addObject`, `h.Shape = …`, `families/strength.py:150–158`). Any other study only reads and stays a job
(fea_heat and fea_buckle are heavy: the solve is minutes). In that one case the solve now holds the window;
see Undecided 2.

**Flagged by the scan, read, safe** (`LOOKED_AT` in the test, each with why): bim_profiles (its "make" step
is `ArchProfile.readPresets`, a CSV read), param_list (`sheet()` without make), and the read calls of three
changing tools: bim_schedule without sheet, bim_library without insert, bim_trash list.

**Already kept by name** (prefix or picture tool; scan agrees): doc_*, view_*, gui_*, dialog_*, queue_*,
app_*, window_*, job_*, cam_sim, gui_input, batch.

**Read and clean** (the scan flags nothing; I spot-read the ones in bold): **asm_fits**, **export**,
**section**, **measure_mass**, **steps_render** (tessellates and draws in numpy), **sheet_read**,
**sheet_chart**, **cam_template_export**, **fea_shell**, bim_list, bim_quantities, bim_preflight,
meshobj_info/curvature/export, points_info/export, feature_list, draft_fonts, material_list/get,
fea_results/probe/chart/export, shape_query, measure, clearance, insp_*, steps_list, robot_export, ifc_*
(an IFC file in memory, not the document), sheet_list/export, units_convert, object_list/get,
crash_collect, body_check, usage_report, guide_read, outputs_clean, pref_get, snapshot_latest/list.

- **Test** (`ReadsThatRunInPlace`, 7). The scan reads source only: every read — a hub `Tool(…)` without
  changes, a data entry with changes false or with `reads` — and the code it runs (its handler; the family
  helpers its entry's expressions name; what those call inside the hub, six calls deep) for a recompute, a
  solve, an object made or removed, a capitalised property set, a transaction, undo, the selection, the view,
  Qt, a document opened or made active, a setting written; plus an entry's own make / add / set steps. A read
  it flags must be in `IN_PLACE` / `IN_PLACE_WHEN`, kept by name, or in `LOOKED_AT` with a reason, else the
  test fails naming the signs. A `LOOKED_AT` name the scan no longer flags fails too.
- **What the scan cannot see** (honest limits): FreeCAD's own modules (asm_export and bim_export are listed
  from reading FreeCAD's source, not from the scan); an add-on's tools (Workshop, ScanRuler: not audited
  here — they say `jobs.in_place`); a method reached through a value the scan cannot name; reads of
  `ViewObject` properties, which it does not count. A read of a changing tool is scanned whole, not by branch.
- **robot_run, by the way:** its helper's docstring says the axes are "left where the last point put them";
  the entry does put them back and recomputes. It is a read that moves the robot; left as it is.
- **Live.** `asm_list { background: true }` → refused with the words above. `job_start { tool:
  "history_undo" }` → refused, "call history_undo itself". A batch holding asm_check or td_export: runs in
  its place, no job id. `measure { background: true }` and `body_check { background: true }` still answer as
  jobs. `addon_test { addon }`: the window keeps painting while it waits (it did not before).

## 4. The hang trace — reworked; covers a job's thread and a batch's wait

- **Why no file was written.** The batch's own call was excluded, the batch started the job with
  `jobs.start` directly (outside `Server.call`), and no call was in hand while the GUI thread waited: nothing
  was armed. Two more faults in the code as it was: faulthandler has one timer for the process, so an inner
  call's exit cancelled the outer call's watch for good (the comment said it was armed again; it was not),
  and `_stack` was unused.
- **Fix** (`protocol.py`, `_hang_trace`, `hang_trace(session or folder, name, kind, after)`): every open
  watch is in one list under a lock; the one timer is always set for the watch due first and set again as
  each ends. One file is open at a time (the one the timer writes to); it is closed whenever the timer moves
  on, removed if nothing was written, and none is open when the last watch ends.
  - `jobs.start`'s worker runs inside a watch: `<outDir>/crash/hang-job-<tool>.txt`.
  - The batch's wait for a heavy read is inside one: `hang-batch-wait-<tool>.txt`.
  - A call's stays `hang-<tool>.txt`; a batch's own call is still not watched.
  - The file starts with a line saying what ran, on which thread, since when. One that ran long and then
    ended gets a last line "… ended after N s: long, not hung", so a slow job's file is not read as a hang.
- **Cost.** About 0.1 ms a call here (a file made and removed; measured on this machine's disk, not the Mac's).
- **Limits.**
  - With the default budget (55 s) the batch's wait ends before its 60 s; the job's own watch, armed at the
    same moment, is the one that writes — with every thread's stack, the waiting GUI thread included. The
    wait's own file appears only with a budget over 60.
  - After a watch has written, the next one due is timed only when some watch starts or ends (the timer is
    set from Python). In a true hang nothing starts or ends; the one file written has every thread.
  - A legitimately long job (a 5-minute solve) writes its file at 60 s each time, and marks it "long, not
    hung" when it ends. One file per tool, overwritten.
  - faulthandler shows Python frames only: a thread stuck inside OCC or Qt shows the Python line that
    called in, not the C++ below it.
- **Tests.** `HangTrace` (7): ends in time → nothing, handle closed; a batch and no folder → no watch; a job
  thread running late with a wait and an inner call round it → the job's file with both threads' stacks, the
  others leave nothing; the one due first is timed and the next after it; one overdue while the timer was
  another's; `jobs.start`'s worker in a process of its own; that the batch's wait is inside the watch (by
  source — the batch itself needs FreeCAD). `BatchWaitWithFreeCAD` (1, skipped here, written unrun).
- **Live.** A heavy read known to run past a minute in a batch (a wall-thickness map of the dense scan):
  after 60 s `crash/hang-job-<tool>.txt` exists; its first line names the job; it holds a thread inside the
  tool and the main thread in `wait_for`; when the job ends the last line says so. An ordinary session
  leaves no `hang-*.txt` and `lsof` shows none open.

## 5. The batch's compact lines — measured; nothing safe to cut

No recorded live replies were here to measure, so these are `batchrec.to_reply` on built rows, using the
1552 calls of the 20 model files in the patches folder for the tool names (mean 11.7 characters) and
health's own wording for the verdicts. Bytes are of the compact JSON, per line:

| Line | Bytes | Of which |
|---|---|---|
| a read (index, tool, ok) | 39 | the whole line |
| a change, "nothing red" | 62 | 23 the verdict |
| a change, "Bracket: valid, closed, 1 solid" | 82 | 43 the verdict |
| a sketch verdict | 94 | |
| a refusal of 85 characters | 125 | whole, as asked |
| five identical refusals | 123 each, 891 the reply | left whole |

A mix as the models run (45 % reads, 20 % nothing red, 25 % a part's verdict, 5 % a sketch's, 5 % refusals):
60 bytes a line, 12.5 kB for 200 lines, about 3 600 tokens. Outside the lines: 270 bytes once (the file,
the note; 280 more for healthNote when a standing part was left out).

- **What repeats on every line:** `"ok":true` (10 bytes, 17 % of the mix) and, on a fifth of the lines,
  `"health":"nothing red"` (23). The second is a verdict and stays. The first could be left off lines that
  are ok, but the compare scripts and the models read `ok` on every row; changing a line's shape is not a
  safe saving. Left.
- **One thing to know:** `protocol.trim` never shortens a batch's `results`, so a compact reply is not
  capped at 60 000 characters: about 1 000 lines reach it. The 55 s budget keeps real replies far below
  (a line is a call that ran).
- **Tests.** `CompactLineSizes` (2): identical refusals each whole; a line is index, tool and ok and only
  then what it has to say, within a byte bound, and the reply's fixed part under 500 bytes.

## Also fixed on the way

- **The queue file was written from two threads without a turn.** A job's thread as it ends and the call's
  thread logging a slow read both read, change and write `queue.json`; the later write put back what the
  other had just changed. It showed as `test_stem_findings_more.Jobs.test_slow_read_is_logged` failing once
  in a full run here (it passes alone). `jobs.py` now takes `_queue_lock` round its three read-change-writes.
  `keep.py` and `heavy.py` write the same file from the GUI thread without it: narrowed, not closed.
  Test: `QueueFile`.

---

## Undecided, with a recommendation

1. **session_state in place.** It reads the window for `next`, so it is in `IN_PLACE`; the price is that a
   session_state slow enough to have gone to a job on its own (over 20 s, a very large document) now holds
   the call. Recommend keeping it in place and, if that is ever seen live, giving it a `next: false` that
   skips the window so that form can be a job.
2. **fea_heat / fea_buckle / fea_modes on a study of one solid.** In place there, so a solve of minutes
   holds the window and the client drops the call at 80 s (whether fea_results can still read the result then
   I did not check). Recommend moving the helper's refresh out of the read: make and refresh it in a changing
   call (fea_setup, or a step of its own), and let `study_body` only find it. A change in
   `families/strength.py`, not made here.
3. **Reads of add-ons.** Workshop's and ScanRuler's reads were not audited. Recommend running the same scan
   over each add-on's handlers (the scan's functions are in `tests/test_hubfix3.py`; they read this repo's folders and would need pointing at the add-on's) and
   declaring with `jobs.in_place`.
4. **robot_run and note_list are reads that write.** robot_run moves and restores; note_list writes the
   followed notes back with no undo step. Recommend note_list's follow becomes a changing call's work
   (note_follow, or done by health after a change), decided with the notes family's owner.
5. **A geometry check in a process of its own** (item 2's recommendation).
6. **`"ok":true` on every compact line** (item 5): 17 % of a typical reply; needs the readers changed with it.
7. **The rest of the queue file's writers** (`keep.py`, `heavy.py`) under one lock in `keep`.
8. hubfix2's Undecided 2–8 stand as they were; its 1 is this file's item 1.

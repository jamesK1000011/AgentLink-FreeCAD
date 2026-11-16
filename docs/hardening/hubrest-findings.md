# Hub (AgentLink-FreeCAD), rest: dev, unattended, notes, app; the "more" files; core and view — 16 Nov 2026

Nothing here ran on FreeCAD. Plain-Python suite after the changes: 712 passed, 313 skipped (4 min 56 s).
Files edited: agentlink/families/dev.py and app.py only (two descriptions). tools.py, health.py, protocol.py, view.py,
render.py, echo.py and every other family file are untouched.

## What was left to do, and what I found already done

docs/hardening/coredoc-findings.md (the earlier pass) has a row for every tool of app (17), dev (4), unattended (3) and
notes (7): checked against FreeCAD 1.1 source where FreeCAD is involved (selection, cmd_run, workbench), "own code"
otherwise, refusals fixed, descriptions rewritten. The one thing it marked not done was **app_restart's description**.
agentlink/data/tool_index.json already carries workbench / commands / words for every tool of these groups.

bim_gaps.py (16 tools), cam_more.py (3), fem_more.py (3) and std_more.py (22): **every one of the 44 has a row** in an
earlier findings file (bimcam, sheetfem, part, partdesign, coredoc). None was left unchecked, so I changed nothing in
those four files.

| Tool | Done here | Still doubtful |
|---|---|---|
| app_restart | Description rewritten from the code (app.py app_restart, restart_plan): the three save rules, that a changed document that is not saved needs the checkpoint add-on to keep a copy (else refused, nothing changed), the smoke test before another .app, every reply field, when not to use it | "A task panel or sketch left open is not carried over" is from reading (documents are reopened by path), not from a run |
| live_run | The description now **begins** with the rule: reset the test document first, every time (live_run { script: "reset" }), what reset does and what goes wrong without it. The earlier text had it in the second sentence after a semicolon | none |
| addon_test, gui_input, gui_unstick | Read again against dev.py: nothing to add to the earlier pass | none |
| addon, doc_switch, queue_go | Read again: nothing to add. queue_go is the person's go only; it is kept out of the test model | none |
| note_*, steps_* | Read again (notes.py): nothing to add | none |
| the other 16 app tools | Not re-read line by line: the earlier rows stand | as the earlier findings say |

Counts for this part: 31 tools of the four groups read against the earlier rows, 2 descriptions rewritten, 0 code bugs
fixed.

## core and view: proposed text (not edited — tools.py and view.py are another agent's)

Checked against FreeCAD 1.1 source: src/App/Document.pyi (UndoMode, UndoCount, RedoCount, UndoNames, RedoNames, undo,
redo) and src/App/Document.cpp (Document::undo).

### Proven bug: history_undo / history_redo with steps of 0 or less (tools.py, history())

`n = int(a.get("steps", 1))`; `names = list(d.UndoNames)[:n]`; `for _ in range(n)`. With steps -1 the loop does nothing
but the slice `[:-1]` answers every undo name but the last, so the reply lists steps as undone that were not. With
steps 0 nothing is undone, yet the document is recomputed and a snapshot step "history_undo" is recorded. Proposed:
refuse `steps < 1` ("steps: a whole number from 1; undoCount in the last answer says how many there are"), and answer
`steps: names[:done]` with `done` the number of loops that ran, so a request for more steps than there are does not
overstate either. Also: these two change the document but are not `changes=True`, so no health reading rides on their
reply (by design: an undo must not be wrapped in a transaction). Say so in the description.

### Proposed descriptions

- **history_undo**: "Undo the last changes of this document, as FreeCAD's Edit > Undo does. steps: how many (1 when left
  out; a whole number from 1). One step is one changing tool call (each runs as one FreeCAD transaction), or one thing
  the person did in the window; FreeCAD keeps the last 20 by default, and a batch that rolled back, a document reopened
  or a restart leaves none. It recomputes afterwards. Reply: done, steps (the names of what was undone, newest first),
  undoCount and redoCount (what is left each way), bodies (the bodies there now). No health reading comes with it: call
  session_state or body_check to see where the model stands. Face and edge numbers may differ from before the undone
  step: query again. history_redo puts it back; history_diff says what changed."
- **history_redo**: "Redo what history_undo (or Edit > Undo) undid. steps: how many (1 when left out). Redo is only
  there until the next change: any changing call empties it (redoCount 0 means nothing to redo, and the call then does
  nothing). Reply as history_undo."
- **history_diff**: add the inputs' ranges and the reply: "since: a step number of this session from 0 to one less than
  the step now (session_state gives it; left out: the step before the last), or a checkpoint (cp3 or its name; needs
  the add-on that keeps checkpoints). Reply: since, to, changed (true | false), bodies { label: { volume, area, faces,
  solids, size: from and to } } for the bodies that changed only, steps (the tools run between). Refused: a step out of
  range (with the range), an unknown checkpoint. Reads only."
- **guide_read**: "The written guides: the workflow and the traps that the tools' own descriptions do not carry, one per
  workbench or task. No topic: the index (every topic with a line). topic: that guide whole; section: one of its ##
  sections by its heading, to keep the answer short. Add-ons add their own topics (texture, orca …). Read the guide of
  a workbench before the first changing call there. Reply: topic, text (or the index). Reads only."
- **app_force_restart**: add what the agent sees: "…It is answered by Agent Link's supervisor, outside FreeCAD, so it
  works when no other call does. If FreeCAD itself answers the call it is refused (invalid_state): the window is not
  stuck, use app_restart, or gui_unstick / dialog_answer for a dialog that holds it. Unsaved work since the newest saved
  copy is lost: try gui_unstick first."
- **report_read**: "FreeCAD's Report view in the window. last: how many lines from the end (40; 1 to 200). problems:
  true gives only the warnings and errors (told by FreeCAD's own colours for them, so a red line counts whatever its
  words). Reply: found (false with a note when the Report view cannot be found), count (lines there), problems (how many
  are warnings or errors), lines. New problem lines also ride on each answer as report, so call this only to look
  further back. Window only (refused headless)."
- **session_state**, **body_check**, **job_start**, **job_status**, **batch**, **tool_groups**, **usage_report**,
  **outputs_clean**: read against tools.py; they name inputs, limits and reply. No change proposed, except
  outputs_clean: say the reply's fields (it does not), and session_state: name the reply's top-level fields (document,
  bodies, step, jobs, out, where) in one line, since nearly every model's first call reads them.
- **dialog_answer** and **crash_collect** are group core but live in families/unattended.py. Left alone as core. Their
  descriptions name inputs and effect; dialog_answer does not name its reply's fields (dialog { title, text, buttons } or
  task { … }, pressed): one sentence would do.
- **export**: covered by the coredoc pass (doc.py). **app_extensions** (ext.py), **collab**, **history_checkpoint**,
  **history_restore** (add-ons): not in tools.py and not in my files; not looked at. The index (tool_index.json) has no
  words for history_redo and no entries for collab, history_checkpoint, history_restore.

- **view_maps**: "What view_render can draw here. Reply: maps [{ name, about }] (wall, stress, heat, and any an add-on
  adds), layers [{ name, about }] (an add-on's extra things to draw, such as a scan), views (the view names view_render
  and view_snapshot take: iso, top, front, right …). Call it once before the first view_render with map or layers.
  Reads only; headless too."
- **view_snapshot**: names inputs and reply; add one line: "Needs the window and turns the person's 3D view for the
  moment of the picture (their view is put back). It shows what is on screen, so a hidden object is not in it; it says
  how the model looks, never whether a step worked: read that from the tools' answers."
- **view_render**: already states limits (40 s thinning, 90 s cut). Add the reply's fields in one place: "Reply: path,
  views, hidden, time { took, expected }, legend / min / max / worst { at } with a map, thinned, detailCapped, cut."
  The work order's leftover 4 (its time estimate is too high) is in render.py's timing, not in the description; not
  looked into (not my file).

## Test model

hubrest-model.json: 46 calls in the window, starting with live_run reset; one placeholder (<NOTE_ID>). The WindowTest
body's numbers are the reset script's own and are read from call 2, not stated by me. None of it has run.

# diff pass: smarter, cheaper tool calling — findings

Checkout: the hub at main 5cfd320. Nothing committed or pushed. Patch: diff.patch (new files included, FILES excluded).
Tests here: 739 passed, 322 skipped (every FreeCAD test skips: FreeCAD is not installed here). The new FreeCAD tests have
never run. FILES is stale by six files (agentlink/batchrec.py, diffing.py, emptywhy.py, nexthint.py,
tests/test_history_diff_fc.py, tests/test_smart_calls.py): tests/test_files.py fails until the main session regenerates it.

All eight items are built. Files outside the list I was given, each touched because its item names it:
agentlink/report_watch.py (item 8), agentlink/supervise.py (item 5, one sentence in the refusal),
families/model.py and families/techdraw.py (item 7), families/view.py and render.py (item 2).

Coordinator's mid-task ruling applied: tools.now_state() asks isActive() only of commands on the active workbench's own
toolbars (gui.activeWorkbench().getToolbarItems()), records state["asked"]; the next hint asks nothing outside that set
and is kept off the health path unless the window's state moved.

## 6. Health check noise (agentlink/health.py)
Built: mark() keeps each sketch's reading (DoF, the solver's four lists, empty, open profiles; up to 300 sketches). After
the call a recomputed sketch is passed over when (a) its reading is unchanged and the call is not a sketch tool's;
(b) its Body is a CAM tool bit's BitBody (any tool); (c) it is "fully constrained" or "empty", made by a call that is not
a sketch tool's. A red reading (conflicting / redundant / malformed) is always said. A sketch tool (group "sketch" or name
sketch_*) reads its sketches out as before.
Proven here: tests/test_health.py, 7 new plain tests on stand-ins. BitBody is App::PropertyLink on the tool bit
(FreeCAD 1.1 source: src/Mod/CAM/Path/Tool/toolbit/models/base.py).
Needs the Mac: that the bit's sketch reaches its BitBody through getParentGeoFeatureGroup() or InList in a live job.
Judgement call to check: after a sketch tool, an unchanged dependent sketch is still read out (I could not tell the
sketch the call addressed from one it merely recomputed without a per-property observer, which I did not add for cost).
Live: sheet_format on a sheet a free sketch uses (no "NutSketch: 1 DoF left"); cam_tool_add (no "Sketch001: fully
constrained"); sketch_constrain on a sketch (still reads it); a sheet value that changes a sketch's DoF (said once).

## 1. history_diff (agentlink/tools.py, new agentlink/diffing.py)
Built: each step now also keeps every body's box lowest corner and a record of every PartDesign feature, sketch and Part
parametric object (values of its properties, expressions, a sketch's constraints and geometry count/length/size).
Reply adds, only when there is something: moved { body: { by, distance } }; features { added, removed, edited { name:
{ property: { from, to } }, constraintValues by index and name, constraints count, geometry } }; recheck [ … ].
recheck is NOT a fixed list of check names. It names (1) each check this session actually ran on a changed body before
the change (tool, body, ranAt) — a read whose name has check / review / fit / clearance / results / probe / wall /
thickness / mass / dfm / strength / qa — (2) asm_check when the body is in an assembly, (3) fea_solve when the last
solve's body is not as it was, (4) td_list per drawing page with a view of it. So add-on checks appear without the hub
naming them, but only once they have been run; a check never run in this session is not listed.
Limits said in the reply: over 600 features, or a step's reading over 0.25 s, gives features.unchecked for the session.
Features are not compared from before the session's first step (since: 0).
Proven here: tests/test_smart_calls.py (9 plain tests). Needs the Mac: tests/test_history_diff_fc.py (4 tests) and the
cost of the reading per step on a large document (not measured).
Not verified: steps only exist for tools that call session.snapshot; a changing tool that does not is invisible to the
diff, as before.
Live: part_primitive box; body_check; object_set Length; history_diff → features.edited, recheck body_check. Then
part_transform move; history_diff → moved only. Then a sketch dimension edit; history_diff → constraintValues.
An add-on check (the review / DFM one) run, body changed, history_diff → it is in recheck.

## 3. next hint (new agentlink/nexthint.py; tools.next_state, next_hint; health.py)
Built: session_state.next in the window: dialog in front and buttons, sketch in edit with DoF, task panel and buttons,
workbench, status-bar text, up to 5 tools whose commands are active. Under 400 characters, never raises; no window costs
one GuiUp read. health carries the same line only when workbench, object in edit and its DoF, selection count, task
panel or dialog differ from the last hint (five attribute reads decide; no command is asked on that path otherwise).
This can add a health block ("nothing red" + next) to a call that had none, once per change of state.
Proven here: wording, order, length, candidate filter (4 plain tests). Needs the Mac: everything that reads Qt and
FreeCADGui — untested code. Specifically unverified: that the task panel's QDialogButtonBox has an ancestor whose class
name contains "TaskView"; Control.activeDialog() in 1.1.3; getToolbarItems() names matching the index's command names.
Live: session_state in PartDesign; open a sketch (sketch_edit / as the tools do) then session_state; a changing call
after opening a sketch (health.next once, not on the next call); watch FreeCAD stays up across 20 session_state calls
on several workbenches (the crash the coordinator reported).

## 2. Empty pictures (families/view.py, render.py, new agentlink/emptywhy.py)
Built: view_render answers { empty: why } with no image when there is nothing to draw (empty document / all hidden,
named / named objects have no solid / nothing solid), when the map has no data, and when the drawn picture covers
under 0.2% of its pixels (zoom or section misses; says the parts' box). notDrawn names shapeless objects when others were
drawn. view_snapshot answers empty before taking a picture when nothing with a shape is visible, or the shown objects'
box projects wholly outside the view or under 6 px; fitted: false + fitNote when not re-fitted.
BEHAVIOUR CHANGE: three former refusals are now ordinary answers with empty (nothing to draw; map with no solve; map
read nothing). A batch no longer stops on them. tests/test_view.py's stress-map assertion was changed to match.
Found on the way: a zoom far from the part still lit one stray pixel, so the old "Nothing landed" warning did not fire.
Proven here: 4 plain tests incl. render cover. Needs the Mac: view_snapshot's path entirely
(View3DInventor.getPointOnViewport and getSize exist in FreeCAD 1.1 source: src/Gui/View3DPy.cpp; behaviour for points
behind a perspective camera not verified — could misjudge "misses the model"). The 0.2% threshold is my choice: a very
thin part seen edge-on in a single view could be called empty.
Live: view_render on a new empty document; with every body hidden; objects: [a sketch]; zoom at [900,900,900];
map stress before any solve; view_snapshot with all hidden; view_snapshot after zooming far out in the window;
view_snapshot with no view (fitted: false).

## 7. Two tool faults
(a) families/model.py: a new result with solid: false and no solid answers body, surface: true, faces, area, box, valid,
openEdges, closed, note — no sound / problems / volume. One place (finish) covers part_sweep, part_loft, part_extrude,
part_revolve. openEdges is Part.Shell(faces).getFreeEdges() (FreeCAD 1.1 source: TopoShapeShellPyImp.cpp,
ShapeAnalysis_Shell). Not verified: that a seam is not counted free; with op/into the old path still runs.
(b) families/techdraw.py td_list: part views without lines are recomputed and waited for (td_wait.wait_views, 20 s),
then their dimensions recomputed; a view still without lines gets notReady and no edge count, its dimensions notReady and
no measured / text. Reason from source: DrawViewPart::execute builds the lines, on a worker thread when the GUI is up
(src/Mod/TechDraw/App/DrawViewPart.cpp); nothing restores them from the file. td_list is a read that now recomputes
view objects (no model change, but the document may show as modified — not checked). Other td_ reads (td_geometry,
td_dim) were not changed and may have the same cold start.
Proven here: nothing (both FreeCAD only). Tests written: test_model.py (surface), test_techdraw.py test_9.
Live: part_sweep { solid: false } of a circle along a line; part_extrude of an open 2-point profile solid: false;
save a document with a page, doc_close, doc_open, td_list (computed present, measured non-zero), td_list again.

## 8. Font-alias line (agentlink/report_watch.py)
Built: lines matching "Populating font family aliases took" / "Replace uses of missing font family" are left out of
take() and problems(); read() (report_read) still returns them. Test changed (2 → 1) and one added.
Proven here: plain tests. Live: app_restart, first answer has no such report line; report_read { problems: true } shows it.

## 4. Stale tool list (agentlink/protocol.py, tools.py)
Built: Server remembers what tools/list last sent (names, a hash of description + inputs, all tool names).
session_state.toolsChanged: first time added / removed / updated / callable (new, unlisted) / gone by name, then counts
until tools/list is read again. Nothing before the client's first listing.
Proven here: 1 plain test. Not verified: that the Claude extension's launcher forwards tools/list to this server each
time rather than answering from a cache (packaging/mcpb/server/index.js tracks listing ids; I did not trace it). If it
caches, the flag would stay up.
Live: tool_groups { enable: ["model"] } then session_state twice (names, then counts); after the client relists, gone.
Install or update an add-on, session_state.

## 5. Batch records (new agentlink/batchrec.py, tools.py, supervise.py)
Built: every batch writes batches/<date>-<time>.json under outDir, rewritten after each call (running: true, ran, results),
final answer at the end; newest 20 kept; reply carries record (with to: as well). Recorded as a "run" output, so
outputs_clean also clears it after 14 days. The "window went away / held / stopped responding" refusal for a batch now
points at it; the batch description says so.
Cost: the whole record is rewritten per call; once a write takes over 50 ms it goes to every fifth call and the end, so
after a kill up to four finished calls can be missing from a large record.
Proven here: 2 plain tests. Needs the Mac: FreeCAD test in test_history_diff_fc.py; the forced-restart case itself.
Live: a 3-call batch (reply.record, file contents); a batch whose second call hangs past the watchdog, then read the
newest record.

## Worth saving (learned here, not from memory)
- Asking Command.isActive() of commands outside the active workbench's toolbars crashed FreeCAD 1.1.3 (coordinator's
  live finding, this run).
- A render zoomed off the part can still light one pixel: "anything drawn" is not a test for an empty picture.

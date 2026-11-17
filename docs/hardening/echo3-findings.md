<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Echo, third window pass: what was changed and why

Source: `window-pd3-skasm2-findings.md` (pictures after round 2), `echo2-findings.md`, and the first reviews of
the other families on the old echo (`window-td-cam-findings.md`, `window-bim-findings.md`,
`window-draft-surf-fem-mesh-findings.md`). FreeCAD 1.1.3 source, read only.
Base: `origin/main` 35df6eb. Files: `agentlink/echo.py`, `agentlink/overlay.py` (one change: the painter is
not painted again when nothing it draws changed), `agentlink/data/activity.json`, new
`tests/test_echo_hold.py` (18 tests), `tests/test_echo_window.py` (two tests changed to the new rules).
No FreeCAD ran here. "Test" means a test with stand-ins, not a live check. "Old" line numbers are
`agentlink/echo.py` at 35df6eb.

## Rules kept

- The echo never raises into a call (`_step`, `wrap`); it is off with no window (`_on`); it changes no saved
  content. New view state: `ViewObject.Transparency` of covers (item 4), put back at the next changing call;
  mesh segment colours (scene only, no property).
- The trace (`session.echo_trace`, the batch row's `echo`) now holds names only. Round 2 put FreeCAD objects
  in it (`named`, `inEdit`), which a JSON answer cannot carry. Test: `AfterAChange`.

## 1. No ring anywhere (and two captions missing)

- Causes (two, both certain from the code):
  - Old 1403: `before` called `rings_off()` at the start of every call that was not skipped.
    `window_snapshot` was not skipped, so the snapshot put out the last change's ring before it took the
    picture. That is why 0 of 76 pictures had a ring.
  - The marks timed out. The ring lasted 1.3 s (old 673). The caption lasted 2.6 s (old 601, 644). The status
    bar lasted 4 s. The result's selection was cleared after 1.8 s (old 1257, 1690). A picture taken later than
    that showed nothing. This explains pd 051 (caption gone, status words still there) and asm 061 (both
    gone). It also explains several "not selected" pictures: pd 051 binder, asm 035 joint, asm 061 washer.
  - The ring was not skipped at the short pace. A hidden toolbar can still stop it (item 2).
  - The overlay is painted when the window is grabbed: earlier runs had 17 rings in their pictures.
- Changes:
  - New `WATCH` and `watching()`. Pictures, Report view reads, session reads and job status are in it.
    These calls get no echo at all: no ring put out, no words, no selection, no pause, and the trace is not
    reset. `SKIP` calls (`session_state`) no longer reset the trace either; before, `session_state` always
    read None. Add-ons can declare their own `WATCH`.
  - `rings_off()`, `restore_covers()` and the foreign-sketch check now run only for a changing call. A read
    keeps the last change's ring. It says its own words in their place, as round 2 wanted.
  - New `HOLD_MS` = 30 s for the ring, the caption and the status bar. The next changing call replaces them.
  - The selection timer is gone. The selection stays until the next changing call. When a changing call
    selects nothing, the last call's selection is cleared, so it is never left standing.
  - Only one caption is ever shown. Words left on a page or on another 3D view are hidden.
- How sure: certain for the cause. Tested by `Replay.test_change_then_snapshot_keeps_the_ring_and_the_words`
  (change, snapshot, change against stand-ins) and `HeldOnTheOverlay` (the real `Board` with a clock 10 s on).
- Live check: a file batch with `lines: "counts"`: `pd_pad`, `window_snapshot`, `pd_pocket`,
  `window_snapshot`, `session_state`. Both pictures must show the Pad / Pocket button ringed and the caption.
  `session_state` must show the `pd_pocket` trace.

## 2. Sketch in another document; Sketcher edit toolbars

- Cause of the grey buttons: a sketch in edit keeps FreeCAD's task dialog open for the whole application.
  Part and Assembly commands are inactive while a task dialog is open. Round 2 never left such a sketch.
- Choice made: the echo leaves the sketch, with `resetEdit` on its document, only when all of these hold:
  - the echo itself opened that edit in this FreeCAD session (`enter_edit` records it in `_agent_edits`);
  - the call is a changing call in another document;
  - the call does not name the sketch;
  - the call is not a `cmd_`, `menu_`, `gui_` or `dialog_` call;
  - no modal dialog is open.

  A sketch the person opened is never left. An entry is dropped once its sketch is no longer the one in
  edit. Inside one document the round 2 rule (`closes_edit`) still decides. The functions are
  `edit_to_leave` (the rule, plain Python) and `leave_agent_edit`; the trace key is `leftEdit`.
- Toolbars, probable cause (from the FreeCAD source; not proven live):
  - `src/Mod/Sketcher/Gui/Workbench.cpp` 205-251 saves the edit toolbars' shown/hidden state to the
    user parameter `BaseApp/MainWindow/Toolbars` when a sketch is left in the Sketcher bench (`SaveState` reads
    `isVisible()`).
  - `Workbench::activated` (174-203) makes them available only when the *active* document has a sketch in
    edit. The echo brought up the Sketcher bench while the sketch was open in another document. If that sketch
    was then left, the toolbars were saved as hidden, and from then on no sketch shows them.
- Change: new `sketch_bars_shown()`, run before and after every `sketch_` call that has a sketch in edit.
  When none of the 7 edit toolbars is shown, all of them are shown with the toolbar's own `show()`.
  If the person has hidden only one or two, nothing is changed. On the next `leaveEditMode`, FreeCAD itself
  then saves them as shown again.
- How sure: rule tested (`LeaveTheAgentsSketch`, `SketchBars`). The toolbar cause is a guess from the source.
- Live check: in document A run `sketch_new` and `sketch_add`, then in document B run `part_primitive`. The
  row's `echo.leftEdit` must say `A.<sketch>`, the Part buttons must be enabled, and `sketch_add` in A must
  show the Sketcher toolbars. If `echo.sketchBars` names toolbars, they had been saved as hidden.

## 3. Fit

- New-sketch over-zoom (pd 004; sk 003, 004, 013):
  - Cause, from the code and the FreeCAD source: `View3DInventorViewer::viewSelection` (src/Gui
    3648-3681) frames the view providers' box. A sketch in edit draws its lines apart from its shape, so the
    box is not valid and the camera does not move. Old `_fit_selection` (816) returned True anyway. The view
    stayed where `sketch_new`'s whole-document fit had left it (about 5 mm on the origin).
  - Change: new `sketch_box()`, which is the box of the sketch's own geometry in global coordinates. An empty
    sketch gets 100 mm of its plane. New `frame_box()` frames that box with Coin's `viewBoundingBox` and keeps
    the view direction.
  - The open sketch is now framed whole after *every* changing `sketch_` call. Before, this happened only when
    the answer named new ids (old 1685).
  - `_fit_selection` now says False when the camera did not move.
- sketch_attach edge-on (sk 053):
  - Cause: the sketch was opened, and the camera turned to it, *before* the call moved it to the new plane.
  - Change: after `sketch_attach` the sketch is opened again, so the camera faces its new plane
    (`_reopen_sketch`). Its words now give the offset ("Put TourBoth on XY, 3 mm off").
- asm_add shows nothing (asm 061): the words and the selection were lost to the timers (item 1).
- Results that were not selected:
  - `sketch_project` answers outside-geometry ids (-3 down), like `sketch_external`, but they were read as
    `EdgeN`. They are now read as `ExternalEdgeN`.
  - `asm_new` now selects its assembly (`OUT_MORE`).
  - Mesh, Surface, Draft layer, projection, sections, pieces, views and "made" keys were added to `OUT_KEYS`.
  - When the answer names nothing, the objects new in the document are taken (`_new_objects`). If there are
    none, what the call worked on is taken (`madeFrom` in the trace).
- How sure: tested (`SketchFrame`, `Names`, `AfterAChange`). The camera call is not seen live.
- Live check: PD model calls 3-4 (`sketch_new`, `sketch_add` rectangle) and Sketcher model calls 3, 4 and 53:
  the whole sketch must be on screen, face on. The Assembly model: call 31 must have CrankSlider selected and
  call 61 must have the washer selected, with words.

## 4. Families (judged on the round-2 code; the earlier reviews were of the old echo)

- Still held, and fixed:
  - The page stays in front for `part_` / `sheet_` / `shape_query` calls (td 020, 026, 049, 058). Cause: old
    1474 read `activeSubWindow()`, which is None while FreeCAD is not the application in front.
    New `front_3d()` reads `currentSubWindow()` too and brings up the 3D view of the agent's own document
    (by its title).
  - Spreadsheet results are shown: `sheet_`, `asm_bom` and `bim_schedule` open the sheet's view
    (`show_view_of`). Any page a call makes comes to the front. A TechDraw read brings its page up.
  - Results hidden inside or under other things (BIM space, tiles and rebar under the roof; Surface results
    inside solids; mesh copies on their source): new `uncover()`. For `bim_`, `surface_`, `meshobj_`,
    `draft_`, `part_`, `fea_`, `import_`, `points_`, `insp_` and `material_` calls, a shown object whose box
    holds the middle of the result and is at least 0.9 of its size gets Transparency 80. The result, its
    sources and its containers are never touched. The old value is put back at the next changing call.
    Boxes are kept per shape hash, so they are not measured again on each call.
  - Flat plans (`draft_2d_view`, `bim_views`, `bim_panel_out`): the camera turns to the top.
  - `meshobj_segments` shows each segment in its own colour (`highlightSegments`, scene only).
  - The empty Mesh Info panel: this is FreeCAD's own task watcher (src/Mod/Mesh/Gui/Workbench.cpp 61-150).
    It fills from the selected meshes, and meshes were never selected. They are selected now.
  - Stale selection (Draft, BIM "House"): it is now always replaced or cleared.
  - Reads now select the object they read. This leaves out Part Design bodies and sketches, so the last
    feature stays selected.
- Not done:
  - The FEM result colour map and deformed shape. Agent Link's `fea_solve` makes no FEM result objects (its
    answer is its own), so there is nothing to show. That is a tool question.
  - CAM toolpaths not drawn.
  - The TechDraw anchor and Y-flip faults (tool faults).
  - IFC file tools: words only.
  - `shape_query` faces not lit.
- How sure: rules tested (`Uncover`, `Names.test_view_titles`). The rest is from code reading.
- Live check:
  - TechDraw model call 20 (`part_primitive` after the page): the 3D view is in front with Plate selected.
    Call 58 (`sheet_new`): the sheet's tab is in front.
  - BIM call 18 (`bim_space`): the roof and walls are see-through and the room is selected. Call 32
    (`bim_schedule`): the sheet is open.
  - Surface call 17 (`surface_cut`): Block is see-through.
  - Mesh call 1 (`meshobj_smooth`): "Globe smooth" is selected, Globe is see-through and Mesh Info is filled.

## 5. Speed

- What round 2 added, from the code (no live timing here):
  - Every call, reads and pictures included, put out the overlay. On the next paint this hid a translucent
    layer the size of the window.
  - Each change was selected 3 times after the call (`_select_made`, `fit_on`, and again at old 1725), plus a
    clear 1.8 s later. Each selection runs the tree's and the 3D view's selection updates.
  - Reads that "show" (`view_`, `body_check`, `measure`, `note_`) painted and paused 350 ms before they ran.
    `view_snapshot` was one of them.
  - Each change ended with a paint (old 1696), even at the short pace.
  - The overlay repainted the whole window 4 times a second for as long as a ring was lit (`overlay.py`
    822-829 `sync()` called `update()` on every 250 ms tick). A repaint of that layer repaints what is under
    it, the 3D view included.
  - Each lit button walked all of the window's QActions (`targets.actions`).
- Changes:
  - `WATCH` calls do nothing.
  - Reads put nothing out and do not pause.
  - A change is selected once.
  - There is no final paint at the short pace. The next call's pause, or the picture's own `updateGui`,
    paints it.
  - The overlay is painted again only when what it draws changes (`overlay.paint_key`). It is raised only
    when it is not already on top.
  - Buttons are found with `Gui.Command.get(cmd).getAction()` first.
- Added cost:
  - The document's object names are listed twice per changing call (in documents of up to 5000 objects).
  - `uncover()` measures boxes, only for the families listed in item 4, and keeps them per shape.
- How sure: the causes are from code reading. The 40 % figure was not reproduced here.
- Live check: the TechDraw model batch and the BIM batch with `profile: true`. Compare the calls per 55 s
  with the figures above. Read `around.outside.echoBefore` / `echoAfter` on the rows.

## Words

- `pd_linear_pattern`, `pd_polar_pattern` and `pd_mirrored` now name their features.
- `asm_list` reads "Read CrankSlider: solver says solved".
- `sketch_attach` gives its offset.

## Risks

- A ring, words and the selection now stay up to 30 s after the last call. A person sees the last result
  selected until the next change, as after their own work.
- Transparency set on covers is view state. If the document is saved before the next changing call, it is
  saved with that transparency. The same is true for round 2's hidden datums.
- If the person closes and opens again the same sketch between two agent calls, it still counts as the
  agent's. It can then be left for a call in another document.
- Showing the Sketcher's edit toolbars makes FreeCAD save them as shown on the next leave. This puts back the
  default it had before.
- The new-object fallback can select helpers that a tool made and left shown.

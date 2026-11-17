# Part Design in the window: what a person sees (34 pictures)

Source: `<work>/win/pd/pictures.json` and the 34 pictures (all 34 looked at, half size; three full-size crops of the toolbars and the status bar).
Model: `docs/hardening/models/partdesign-model.json`. Echo code read: `agentlink/echo.py` at bc76fbb, `agentlink/grab.py`.
Nothing was changed. No network.

Limits of this evidence
- A picture is one frame, taken after the call. It cannot show the animation, the pace, or a thing that was on screen for a moment and then went away.
- `grab.py` paints the 3D view with `saveImage`. The navigation cube and the axis cross are in none of the pictures; that is probably the capture, not the window.
- I do not know which Agent Link build the Mac ran. Commit bc76fbb (isometric turn, Model tab back) is dated 23:36; the pictures are dated 23:44 to 23:45.
- Picture times are 1 to 2 s apart, so most calls and their snapshot took less than about 1 s.

## Short answer

- Workbench box: correct in 34 of 34 (Sketcher for the two sketch tools, Part Design for the rest).
- Sketch tools: the sketch opens, the geometry shows, the Tasks panel is the sketch's. These two are good.
- Every solid is shown from straight above (top view). No picture shows a part in 3D. Pads, pockets, drafts, grooves, clones, a helix and a pipe look flat, or cannot be seen.
- No picture has the callout label. No picture has status bar words. No picture has a lit button.
- The left panel is the Tasks tab ("Helper Tools / New Sketch / Boolean Operation") in all 32 non-sketch pictures. The Model tree with the new object is never in front.
- A body is missing from the view in 4 pictures (Plate in 037 and 038, Hist in 108 and 111).
- The Report View has the same red BIM tracebacks (23:42:55, before this run) in all 34. None belongs to a Part Design step. No dialog was left open. The correct document tab (PDTutorial) is in front in all 34.

Counts: GOOD 2, MINOR 20, BAD 12.

How I graded: the faults that are in every picture (no callout, no status words, no lit button, old red text in the Report View) are recorded once, as G1 and G2 below, and are not counted again per picture. If I counted them, no picture would be GOOD.

## Table

| call | tool | verdict | why |
|---|---|---|---|
| 2 | pd_body_new | MINOR | Empty 3D view (correct for an empty body), but nothing on screen says a body exists: tree hidden behind Tasks. |
| 3 | sketch_new | GOOD | Sketcher bench, empty sketch open on its axes, Sketch Edit panel. |
| 4 | sketch_add | GOOD | Rectangle drawn and framed, constraints and 4 lines listed in the panel. |
| 7 | pd_pad | BAD | Top view: the 53 mm pad is a flat green rectangle. A person cannot see that a solid was made. |
| 10 | pd_pocket | MINOR | One corner outline appears. No depth visible. Whole body green, not the pocket. |
| 11 | pd_mirrored | MINOR | Second corner outline appears. Same limits. |
| 19 | feature_edit | BAD | Refine changes nothing a person can see, and no label, status or tree says what was done. |
| 20 | feature_list | MINOR | A read: nothing shown, by design. The green selection of call 19 is still there. |
| 21 | body_check | MINOR | Part goes grey (not selected); panel changes to "Start Part / New Body"; no words give the result. |
| 24 | pd_hole | MINOR | One faint 2 mm circle on a green part. Easy to miss. |
| 25 | pd_linear_pattern | MINOR | Three small circles visible. Flat. |
| 26 | pd_chamfer | MINOR | One more thin line near the top edge. Hard to see as a chamfer. |
| 27 | pd_fillet | MINOR | Bottom right corner goes round. Small but visible. |
| 28 | pd_datum_plane | MINOR | Plane shown, green, view reframed. From above, the 30 mm offset cannot be seen; the plane covers the part. |
| 29 | feature_suppress | MINOR | The corner goes square again. Very small change, no words. |
| 32 | pd_tip | MINOR | A read: nothing shown, by design. Green selection stays. |
| 34 | pd_primitive | MINOR | New box green at the right, fully in frame. Flat. Best framed of the solids. |
| 35 | pd_draft | BAD | Same picture as 034. A 5 degree draft on a side face cannot be seen from above. |
| 37 | pd_multitransform | BAD | The Plate is not in the picture. The view is on the Tut body. Nothing is green. |
| 38 | pd_datum | BAD | The Plate is still not shown (the frame reaches x = 97 mm; the Plate is at 60 to 100). No datum line visible. |
| 49 | pd_thickness | MINOR | Tray green with a faint inner wall line. Small. |
| 51 | pd_binder | BAD | Nothing new visible (the bound face is under the Tray) and nothing is green. |
| 56 | pd_polar_pattern | MINOR | Disc green with six holes. Clear; top view suits it. |
| 59 | pd_clone | BAD | The clone is 40 mm straight above the Disc. From above it is the same shape in the same place. |
| 63 | pd_revolution | MINOR | Ring green, visible, small. |
| 68 | pd_groove | BAD | The groove is on the outer wall: not visible from above. Ring grey, nothing selected, panel "Start Part". |
| 74 | pd_helix | BAD | The coil is seen end-on: a thin green circle. A person cannot tell it is a spring. |
| 82 | pd_loft | MINOR | Frustum green, two nested squares. Its datum plane "Up" is a large green sheet over the Disc and Tut. |
| 88 | pd_pipe | BAD | The tube is seen end-on: a green dot of about 8 pixels. |
| 90 | pd_gear | MINOR | Small green gear, teeth visible. |
| 95 | pd_boolean | MINOR | Sheet green with the round cut. Clear. |
| 102 | pd_reorder | BAD | An order change shows only in the tree, which is hidden. No words. Hist is a small green block. |
| 108 | pd_move_feature | BAD | A 5 mm green square only. The Hist body is gone from the view. |
| 111 | pd_shaft | MINOR | Shaft visible with its steps and taper, but grey (not selected) and drawn across the Tut body and two planes. |

## Recurring problems, worst first

### P1. The camera stays in top view for the whole run
Pictures: all 32 non-sketch pictures. It makes these BAD: 007, 035, 059, 068, 074, 088. It makes the rest look flat.
Where: `Echo.after`, lines 914 to 920. The view turns to isometric only when `_left_sketch` is set (`_mode`, line 853), and only once.
In 007 this case applied (the Profile sketch was open before pd_pad) and the view still is top view. Two possible causes, which the pictures cannot tell apart: the Mac ran a build older than bc76fbb, or `viewIsometric()` did not take effect. Check the build first.
Even when that code works, it does nothing for bodies made without a sketch (primitive, clone, gear, shaft, datum) or after the first turn if the camera returns to an axis view when the next sketch opens.
Smallest change: in `after`, lines 914 to 920, drop the `_left_sketch` condition for the turn: when the result has a solid and the camera looks straight along X, Y or Z, call `viewIsometric()` before the fit.

### P2. No callout label and no status bar words in any picture
Pictures: all 34.
Where: `caption()` lines 422 to 443, host from `_view_widget()` lines 396 to 403; status bar at line 698.
`grab.py` paints a visible "✦" label back onto the picture (lines 60 to 68), so a label that was up would be in the frame. The label lasts 2600 ms and the status words 4000 ms from `before`; the snapshots came about 1 s later. Timing alone does not explain 34 misses.
Likely cause for the label (not confirmed): `_view_widget` uses `QMdiArea.activeSubWindow()` (line 402). Qt returns nothing there when FreeCAD is not the active application, which is how this project runs it (background only). `caption` then returns at line 427 with no label and no log line.
Smallest change: line 402, `area.currentSubWindow() or area.activeSubWindow()`. The same call is at line 748.
Status bar: cause not found from this evidence. A check: read `statusBar().currentMessage()` right after a call.
This problem is the reason that 019 and 102 are BAD: for a change with nothing to see, words are the only signal.

### P3. The Tasks tab is in front, not the Model tree
Pictures: all 32 non-sketch pictures.
Where: `_model_tab_back`, lines 930 to 950. It looks for a `QTabWidget` with "Model" and "Tasks" tabs (lines 943 to 947). The pictures show three tabbed dock panels (Model, Tasks, Agent Link) with a dock title bar "Tasks" below the tabs. Tabbed docks have a `QTabBar` of the main window, not a `QTabWidget`, so the function finds nothing and returns False. (Or the Mac ran an older build; the dock point is true in both cases.)
Smallest change: in `_model_tab_back`, when no `QTabWidget` matches, find the `QDockWidget` whose window title is "Model" among `mw.tabifiedDockWidgets(tasks_dock)` and call `raise_()` on it.
Note: the panel is not empty (it has FreeCAD's "Helper Tools"), but it is not about the step.

### P4. A body goes missing from the view
Pictures: 037, 038 (Plate), 108, 111 (Hist). The Plate is back in 049.
Where: not in `echo.py`. I did not trace it. `feature.py`, `feature_more.py` and `pd_common.py` have no `Visibility` handling (grep). The Plate was last seen in 035, before the subtractive Bore (call 36) and BoreGrid (call 37). Hist was last seen in 102, before pd_tip (103), Pad 3 (106) and the move (108).
Smallest change in the echo: none that is honest; it would hide a tool fault. Find which call leaves the body with no visible feature (read `ViewObject.Visibility` of the body and its tip after calls 36, 37, 103, 106, 108).

### P5. The view fits the whole document, so each new part is small
Pictures: 049 to 111 (15 pictures). 088 and 108 are the worst (about 8 pixels).
Where: `fit()`, line 534 (`v.fitAll()`), called at line 924.
Smallest change: when `made` is not empty, frame the selection (`FreeCADGui.SendMsgToActiveView("ViewSelection")` after `_select(made)`) in place of `fitAll()`.

### P6. The whole body goes green, not what changed; some results get no highlight
Pictures: whole body green in 007 to 029, 034, 035, 049, 056, 059, 063, 074, 082, 090, 095, 102. Nothing green in 021, 037, 038, 051, 068, 111.
Where: `after`, line 885: `made` comes from `OUT_KEYS` (line 159), which has "body", so the body is selected with the feature. `_select`, lines 577 to 588. The 1800 ms clear is at line 898.
For 051, 068, 111 the reply probably names the result under a key that is not in `OUT_KEYS` (binder, shaft), or the selection was already cleared; I did not read the replies.
Smallest change: line 885, select the feature when the reply has one and leave the body out; add the missing reply keys to `OUT_KEYS` after a look at the replies of pd_binder, pd_shaft and pd_groove. A selected tip feature is still the whole solid, so this helps the tree more than the 3D view.

### P7. No lit button in any picture
Pictures: all 34 (full-size toolbar crops of 007, 024, 034 checked).
Where: `flash_command`, lines 458 to 492, called at line 705; lit for 1300 ms from `before`.
A single frame after the call cannot prove this either way. In addition, these tools have no entry in `COMMAND` (lines 37 to 64), so nothing can light for them: pd_datum, pd_clone, pd_gear, pd_shaft, pd_tip, pd_reorder, pd_move_feature, feature_edit, feature_suppress, sketch_add.
Smallest change: add the entries (names to confirm with cmd_list: PartDesign_Clone, PartDesign_Line, PartDesign_InvoluteGear, PartDesign_MoveTip, PartDesign_MoveFeatureInTree, PartDesign_MoveFeature). To prove the ring, take a snapshot inside the 1300 ms, or make the test keep the ring until the snapshot.

### P8. Datum planes stay on and cover other parts
Pictures: 034 to 111 (yellow sheet over Tut), 082 to 111 (large sheet over Disc and Tut).
Where: not in `echo.py` (the datum tools leave the plane visible; FreeCAD sizes it).
Smallest change in the echo: none. Tool side: hide a datum plane when the next feature that uses it is made.

### G2. Old red errors in the Report View
Pictures: all 34. BIM `ArchWall.py` tracebacks at 23:42:55 and a nesting "Aborting" line at 23:43:03, from an earlier run. Not from Part Design, not from the echo. A person who watches sees red text the whole time. For a clean test, clear the Report View before the run.

Not found in any picture: a leftover dialog, a wrong document tab in front, overlapping labels. One cut-off text: "Under-constrain…" in the Sketch Edit panel of 004 (FreeCAD's own layout at this panel width).

## Proven live in the window, on this evidence

Proven (bench, result visible, panel fits the step):
- sketch_new, sketch_add.

Partly proven (bench correct, the result is on screen and green, but flat, with the wrong panel and no words):
- pd_pocket, pd_mirrored, pd_hole, pd_linear_pattern, pd_chamfer, pd_fillet, pd_datum_plane, feature_suppress, pd_primitive, pd_thickness, pd_polar_pattern, pd_revolution, pd_loft, pd_gear, pd_boolean.
- pd_shaft (visible, not highlighted), pd_body_new (bench only; nothing to see).

Not proven:
- pd_pad, pd_draft, pd_multitransform, pd_datum, pd_binder, pd_clone, pd_groove, pd_helix, pd_pipe, pd_reorder, pd_move_feature, feature_edit.
- body_check (no result shown), feature_list and pd_tip as a read (the echo shows nothing for a read, by design).

Not proven for any tool: "buttons light", the callout label, the status bar words.

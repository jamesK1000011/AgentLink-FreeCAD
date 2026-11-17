<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Echo, second window pass: what was changed and why

Source: `window-pd-findings.md`, `window-pd2-findings.md`, `window-skasm-findings.md`; the earlier agent's WIP
(branch `wip/echo2`, untested); FreeCAD 1.1.3 source (read only).
Base: `origin/main` aab454d. Files: `agentlink/echo.py`, `agentlink/activity.py`, `agentlink/data/activity.json`,
`agentlink/data/tool_index.json` (made again by `scripts/tool_index.py`), `scripts/tool_index_more.py`,
new `tests/test_echo_window.py` (31 tests).
No FreeCAD ran here. "Test" below means a test with stand-in objects, not a live check.

Line numbers: "old" is `agentlink/echo.py` at aab454d; "new" is this branch.

## Rules kept

- The echo never raises into a tool call. Each step after a call runs on its own (`Echo._step`): a failure is
  written to the call's trace (`session.echo_trace`, shown as `echo` on a batch row with `profile: true`) and to
  the log, and the next step runs. `wrap()` also catches anything from `before` and `after`.
- No window, no echo: `_on()` is false when FreeCAD has no GUI or is not loaded. Test: `After.test_off_without_a_window`.
- No saved content changes. What the echo sets: selection, camera, active body/assembly (as before), the
  `ViewObject.Visibility` of features and datums (new, see P4 and P8), and the exploded-view lines in the scene (A9).
- Visibility, what I chose: I set `ViewObject.Visibility`, as the space bar does. In FreeCAD 1.1.3
  (`src/Gui/ViewProviderDocumentObject.cpp` 185-217, `src/App/DocumentObject.cpp` 74-81) this goes to the
  object's `Visibility` property with the NoModify status on, and that property has the Output status (no
  touch, no recompute). So no object is marked touched and the document is not marked modified. The value
  is still written to the file on the next save, as a person's own hide would be. Tests check that the echo
  sets no property on the document object itself (`ViewStateOnly`).
- A sketch is never closed under a call that works in it (A1/S9). See that item.

## P3. Tasks tab stays in front of the Model tab

- Cause: old 999-1018, `_model_tab_back` looked only for a `QTabWidget` with "Model" and "Tasks". FreeCAD 1.1
  docks Model, Tasks and Agent Link as tabbed `QDockWidget`s; their tabs are a `QTabBar` of the main window.
  It found nothing. It also ran only when Follow was on.
- Change: new `model_tab_index` and `_model_tab_back` (new 1770-1835). It looks at every `QTabBar`. When the
  current tab is "Tasks" and a "Model" tab is there, it calls `FreeCADGui.Control.showModelView()` (FreeCAD's
  own, `src/Gui/Control.cpp` 128-144) and sets the tab. It does nothing when a task dialog is open, when
  anything is in edit in any document (`edit_document()`), or when another tab (Agent Link) is in front.
  It runs after every changing call.
- How sure: test (rule and a stand-in tab bar). Not seen live.
- Check live: `pd_body_new {name: "T"}`, `sketch_new {body: "T", plane: "XY"}`, `sketch_add` a rectangle,
  `pd_pad {sketch, length: 5}`, then `window_snapshot`: the Model tab must be in front.

## P4. Body hidden after pd_multitransform / pd_datum / pd_move_feature

- Cause: in the tool, not the echo. `pd_multitransform` (tools.json, runner steps) makes the MultiTransform,
  then makes its steps with `b.newObject(...)`. The steps come after it, have no shape, and are visible; the
  MultiTransform (the tip) is left hidden. The body then shows nothing. `pd_datum` only showed the same body
  one call later. `pd_move_feature` takes the visible tip out of the body; the old body's new tip stays hidden.
  This is from code reading, not proven live.
- Change: new `tip_shown` and `bodies_of` (WIP code, checked and kept; new 895-960), called in `_after` for
  `pd_`, `feature_` and `sketch_attach` calls. For each body the call worked in (its `body`, `to`, `from`, and
  the bodies of what it made): when the body is shown and its tip has a shape, the tip is shown and the other
  solid features are hidden. Sketches, datums and binders are not touched. A hidden body is left hidden.
- How sure: test (stand-in Plate). The root fault stays in the tool; the echo only puts the view right.
- Check live: the Part Design model, calls 37-38 (`pd_primitive` Bore, `pd_multitransform` BoreGrid on Plate),
  then `window_snapshot`: Plate is shown. Calls 107-109 (`pd_pad` Pad 3, `pd_body_new` Hist2,
  `pd_move_feature {feature: "Pad 3", to: "Hist2"}`): Hist and Hist2 both shown. The batch row's
  `echo.tipShown` names the bodies put right.

## P5. Fit frames the whole document

- Cause: old 537, `fit()` always did `v.fitAll()`.
- Change: new `fit_on` (805) and `Echo._frame` (1707). After a change the view is framed on what the call
  made (`framed()`: shown, with a shape that has a size; a link is read with `Part.getShape`), by FreeCAD's
  "ViewSelection", then one zoom step out. When the call drew in a sketch that is open, the whole sketch is
  framed. Only when nothing can be framed (a new empty body, a joint) is the whole document framed, as before.
  The trace says which: `fit: "made" | "sketch" | "all"`.
- How sure: test (stand-ins). Framing a single feature: a PartDesign feature's shape is the body's solid up to
  it, so a pocket frames the body, not the pocket alone. That is intended.
- Check live: after the Part Design model's call 50 (`pd_thickness` on Tray) and 89 (`pd_pipe`), the new
  part fills most of the 3D view.

## P6. The whole body is green

- Cause: old 908, `made` took every key of `OUT_KEYS` (old 159), "body" too, so the body was selected with
  the feature. Old 589 selected by object name only, without the parent path.
- Change: `out_names` (WIP, kept) adds per-tool keys (`OUT_MORE`: datum, plane, binder, shaft, moved, tip,
  added, as, inAssembly, part, sheet, view). `result_of` drops the body when anything else was named.
  New `sel_path` and `_add_sel` (1052-1100) select an object by its top-level parent path, as the tree does
  (`Body` + `Pad.`; `Assembly` + `Joints.Joint.`), from FreeCAD's `Parents`; a non-link parent is preferred.
- How sure: test for the choice of objects and the path. Not seen live whether the 3D highlight is now on the
  feature (FreeCAD draws a tip feature as the whole solid, so the 3D view may look much the same; the tree row
  is now the feature).
- Check live: `pd_pocket` in the Part Design model (call 11), `window_snapshot`: the Model tree has the Pocket
  row selected, not the Body row.

## P7. Lit button missing or wrong

- Causes:
  - No ring was ever put out. A ring lasts 1.3 s; the next call came sooner. A call with no button of its own
    showed the last call's ring (multitransform and thickness: the primitive; binder and move_feature: New Body).
  - Wrong or missing names (old 38-67): `pd_binder` was `PartDesign_ShapeBinder` (the tool makes a
    SubShapeBinder); `pd_clone`, `pd_gear`, `pd_shaft`, `pd_move_feature`, `pd_reorder`, `pd_tip` and every
    Sketcher tool but `sketch_new` had none; `pd_datum_plane` was `PartDesign_Plane`, which is on no toolbar in
    FreeCAD 1.1.3 (`src/Mod/PartDesign/Gui/Workbench.cpp` setupToolBars; the datum buttons on screen are Part's
    `Part_Datums` dropdown, `src/Mod/Part/Gui/WorkbenchManipulator.cpp` 58-71); `sketch_new` was
    `PartDesign_NewSketch` but the echo brings up the Sketcher, whose button is `Sketcher_NewSketch`;
    `asm_motion` lit the revolute joint button.
  - linear_pattern, chamfer, draft, polar_pattern and groove have plain toolbar buttons in 1.1.3. The narrow
    window in the pictures cut the toolbars ("»"). A hidden button cannot be ringed.
- Changes:
  - `before` calls `rings_off()` first on every call (reads too): the echo's rings are put out.
  - Command table: `pd_binder` → `PartDesign_SubShapeBinder`; `pd_clone`, `pd_gear` (`PartDesign_InvoluteGear`),
    `pd_shaft` (`PartDesign_WizardShaft`), `pd_move_feature`, `pd_reorder` (`PartDesign_MoveFeatureInTree`),
    `pd_tip` (`PartDesign_MoveTip`, set only; a read lights nothing), `feature_edit` (`Std_Edit`); datums →
    `Part_DatumPlane`, `Part_DatumLine`, `Part_DatumPoint`, `Part_CoordinateSystem`; subtractive primitive,
    loft, pipe and helix light their subtractive button. Sketcher: every changing sketch tool has a button
    (`Sketcher_Offset`, `Sketcher_CarbonCopy`, `Sketcher_Projection`, `Sketcher_Extend`, `Sketcher_JoinCurves`,
    `Sketcher_MirrorSketch`, `Sketcher_MergeSketches`, `Sketcher_ValidateSketch`, `Sketcher_MapSketch`,
    `Sketcher_BSplineConvertToNURBS`; `sketch_add`, `sketch_constrain`, `sketch_edit`, `sketch_copy`,
    `sketch_array` and `sketch_bspline` by what was asked). `sketch_array` lights `Sketcher_Translate` (or
    `Sketcher_Rotate` for polar): `Sketcher_RectangularArray` is on no toolbar in 1.1.3. `asm_motion` lights
    nothing. All names are in `docs/hardening/freecad-1.1.0-commands.txt` (test).
  - New `overflow_flash` (727): when the button exists but is hidden in its toolbar's "»" list, the "»" button
    lights. Never another command's button. The trace says how: `button: [cmd, "button" | "group" | "behind »"
    | "button not on screen" | "menu only" | "no button"]`.
  - `tool_index.json` made again (its first command per tool comes from the echo). The commands that dropped
    out of it (`PartDesign_NewSketch`, `PartDesign_ShapeBinder`, `PartDesign_Plane`) were added back as extra
    commands in `scripts/tool_index_more.py`, with the Part datum names for `pd_datum`.
- How sure: test for the names and for the "»" rule; FreeCAD source for which buttons are on toolbars. Sketcher
  edit-mode toolbars: the "Sketcher" toolbar (New, Map, Validate, Merge, Mirror) may be hidden while a sketch
  is in edit; the trace then says "button not on screen". Not seen live.
- Check live: a batch with `profile: true` on each call: `pd_primitive` then `pd_multitransform` (no primitive
  ring), `pd_linear_pattern` in a narrow window (the "»" lights), `sketch_offset`. Read `echo.button` on the rows.

## P8. Datum planes left visible

- Cause: not in the echo before; the datum tools leave the plane shown and FreeCAD sizes it.
- Change: new `datums_after` (966). A datum (PartDesign or Part datum, by type) made by a call is noted. When
  a later call in the same document makes a solid, the noted datums that are still shown are hidden, each once.
  A datum the person made is never touched; one the person shows again stays shown.
- How sure: test. A choice to check: a datum is hidden at the first solid after it, even when a later
  sketch will use it (it still works hidden).
- Check live: Part Design model calls 29 (`pd_datum_plane` Above) and 30 (`feature_suppress`): the yellow plane goes
  at call 30. Calls 66 (`pd_datum` RingAxis) and 69 (`pd_groove`): the axis goes at 69.

## pd_groove: echo did not run (no words)

- Cause: not found. In the old `after` (old 902-996) every step was in one `try`; one failing step dropped
  the selection, the fit and the words that come last. The pictures fit this, but cannot say which step failed.
  A refused call also said nothing (old 902 returned at once).
- Change: `_after` runs each step on its own (`_step`), the words last and always; the failing step is named
  in the trace (`<step>Error`). A refused call now says so: "Grooved with GrooveProfile: refused (…)".
- How sure: guess for the cause; test that a failing step no longer stops the words.
- Check live: Part Design model call 69 with `profile: true`; read `echo` on its row. If a `…Error` is there,
  that is the cause.

## Words

- Causes:
  - Reads, checks and exports: old 678 (`if not shown: return`) and old 902 (`tool.changes` only) — a read wrote
    no words, so the last change's words stayed (asm_sweep, asm_list, shape_query, asm_check, asm_fits,
    asm_export, sketch_state, sketch_validate, feature_list).
  - asm_ground: activity.json used `{object}`; the argument is `part`, and `grounded: false` had no words.
  - pd_tip: one phrase, "Set the body's tip", for a read too.
  - Tool names: many PD, Sketcher and Assembly tools had no phrase (the fallback is the tool's name), and
    others named a field the tool does not have (`{object}` for part_ tools that take `body`).
  - The words before and after the call ignored the tool's own `activity` template, and the words after did
    not use the answer.
- Changes:
  - `after` says words for every non-skipped call: a read gets "what it did: what came of it"
    (`read_words`: "Checked CrankSlider for overlaps: clear", "Exported CrankSlider for the solver: wrote
    crank_slider.asmt", "Read StarSketch: fully constrained"); a change gets its words with the answer's names;
    a refusal says "refused". `say()` puts them on the caption and the status bar (each guarded).
  - activity.json: phrases for every pd_, sketch_, asm_ and feature_ tool (test), results for the checks
    (body_check Sound / Has problems, asm_check, asm_sweep, asm_fits, asm_export, asm_list, sketch_state,
    shape_query, feature_list, pd_tip). asm_ground: "Let Base move again" for `grounded: false`, "Fixed Base in
    place" else. pd_tip: "Read Hist's tip" / "Set Hist's tip to H1". part_ tools: `{body}` first.
  - activity.py: `feature_edit` says what it set ("Set Pocket 2 Refine to on"); `sketch_edit` with `set` says
    the dimension and value ("Set plate_width to 70 in PlateSketch"; its `set` is a list of { constraint, value }).
- How sure: test. The same words show in the Activity tab.
- Check live: Assembly model call 33 `asm_ground {part: "Base", grounded: false}`, `pd_tip {body: "Hist"}`, `asm_check`, `asm_export`;
  read the caption and the status bar with `window_snapshot`.

## A1/S9. A sketch left in edit in another document

- Left as it is, as asked. The echo never closes a sketch in another document, and never closes the sketch a
  call works in.
- Change: new `closes_edit` (1299) and `KEEP_EDIT` (1285). The echo closes the open sketch before a call only
  when the call builds on it (`pd_`, `part_`, `feature_`, `body_`) or names other objects. It never closes it
  for `sketch_`, `view_`, `note_`, `measure`, `cmd_`, `menu_`, `gui_`, `dialog_`, `window_`, `selection`,
  `steps_`, `history_`, `workbench`, `doc_save`, `snapshot_`, or for a call that names the sketch in its
  arguments (`object_set` on it, a lesson's own call). The WIP's `leave_edit` (it closed an edit and
  recomputed) was removed.
- How sure: test (`cmd_run Sketcher_LeaveSketch` keeps the sketch open; `pd_pad` closes it).
- Check live: `sketch_add` in a sketch, then `cmd_run {name: "Sketcher_LeaveSketch"}`: it must not be refused.

## S1. Camera does not face the sketch plane once a solid exists

- Cause: old 850, `gd.setEdit(target.Name)`. FreeCAD turns the camera to the sketch itself, animated
  (`ViewProviderSketch.cpp` 3857-3881); the echo's fit right after cut the turn off at its first frame.
- Change: new `enter_edit` (1168, WIP code kept): the sketch opens with the view's animation off for that one
  step, so FreeCAD's turn is made at once; if the camera still does not face the sketch, it is set to the
  sketch's own orientation. Used in `_mode` and for new sketches. The fit after a sketch call frames the sketch
  and does not turn the camera.
- How sure: test with a stand-in view; FreeCAD source for the turn. Not seen live.
- Check live: Sketcher model call 20 (`sketch_edit` on PlateSketch after the pad), `window_snapshot`: the
  sketch is seen face on. Row `echo.edit` says "opened, camera turned to it" when the echo had to turn it.

## S4/A7. New geometry, joint, part not selected

- Change: `sub_names` (293) also takes a join's new B-spline id and the ids that extend, to_bspline and
  bspline change in place. The new geometry and constraints are selected by the path Sketcher uses
  (`Body` + `Sketch.Edge3`, from `ViewProviderSketch.cpp` 4305-4325). Joints, added parts and new parts are
  selected by their path in the assembly (P6).
- How sure: test for the names and the path. Not seen live.
- Check live: Sketcher model `sketch_add`, `sketch_offset`, `sketch_join`; Assembly model `asm_joint`, `asm_add`.

## S5. Mirror and merge do not show the new sketch

- Cause: old 915, only `sketch_new` opened its sketch.
- Change: `NEW_SKETCH` = sketch_new, sketch_mirror, sketch_merge; `_open_new_sketch` opens the sketch the
  answer names (with `enter_edit`).
- How sure: code reading. Check live: Sketcher model calls 51 and 52: the panel shows TourMirror, then TourBoth.

## A9. Exploded-view lines stay after collapse

- Cause: Assembly's step view providers draw the dashed lines (`CommandCreateView.py` 474-530,
  `redrawLines`), and only its task panel clears them. `asm_explode {collapse: true}` moves the parts back
  and leaves the lines.
- Change: new `explode_lines_off` (1000): after `asm_explode` with `collapse: true`, every view provider with
  `redrawLines` is given no lines. Scene only; no property is set.
- How sure: test with a stand-in; FreeCAD source. Not seen live.
- Check live: Assembly model calls 57 (`asm_explode`) and 59 (`asm_explode {collapse: true}`), then `window_snapshot`: no red dashed lines.

## Not done

- N5 (the Ring turns into a half ring): planned. Part Design model call 71 is `feature_edit {Angle: 180}`.
- A6 (a pose read from a fixed camera), A5 (no motion is shown for a sweep), S6 (other sketches crowd the open
  one), S7 (labels on top of each other), A11 (new parts land far away): not in this task.
- The pd_groove cause: not found (see above).

## Risks

- Hiding features (P4) and datums (P8) is view state only, but it is saved with the file on the next save.
- The Model tab is raised after every changing call when Tasks is in front and empty; a person who keeps the
  Tasks tab up on purpose will see it change.
- `ViewSelection` frames a tip feature as the whole body solid; a very small feature far from the body's
  centre is still framed with the body.

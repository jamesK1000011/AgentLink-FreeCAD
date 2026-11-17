# Window review after echo2: Part Design (third pass), Sketcher and Assembly (second pass)

Pictures: `pics2/pd` (34), `pics2/sk` (21), `pics2/asm` (21), with `pictures.json`.
All 76 pictures were looked at at full size (1400 x 852). Enlarged crops were made of every toolbar
(rows 1 to 4), of the caption in pd 007, of the tree in pd 019 and 111, and of pd 019, 051, 108.
Compared with: `docs/hardening/window-pd2-findings.md`, `window-skasm-findings.md`, and the claims in
`echo2-findings.md`. No code was read, no file other than this one was changed, no Mac tools.

Limits of this evidence
- One frame per call. No motion. No Report View in any picture, so red error text cannot be judged.
- The window is now 1400 x 852 with the Model/Agent Link tabs on the left and the Tasks panel as a
  separate dock on the right. The earlier pictures had another layout. Some changes below (Model tab, no
  "»" overflow) may come from this layout and not from the echo code. I say so where it matters.
- `pictures.json` lists only the pictured calls.

## Short answers to the two extra questions

- Caption ("✦ Agent: …", bottom right of the 3D view): YES, visible in 74 of 76 pictures (crop of pd 007
  shows the ✦ and the words). Missing in pd 051 (status bar words only) and asm 061 (no caption and no
  status bar words).
- Ringed toolbar button: NO. No ring in any of the 76 pictures. I checked all four toolbar rows in every
  picture with enlarged crops. In the earlier PD pass, 17 pictures had a ring (12 matching).

## Ratings

How graded: as before. Faults present in (almost) every picture are recorded once and not counted per
picture: no ring (P7, all 76) and the wrong Sketch Edit panel in Assembly (A1, all 21). If "no ring" were
counted against GOOD, no picture would be GOOD. The 3D view of a Part Design feature shows the whole tip
solid green; that is FreeCAD's own drawing (echo2 says so) and is not counted when the tree row is the
feature.

### Part Design (34)

| call | tool | before | now | why |
|---|---|---|---|---|
| 2 | pd_body_new | MINOR | MINOR | Empty view (correct). Tut row selected in tree. Words "Made a new body Tut". No ring. |
| 3 | sketch_new | GOOD | GOOD | Sketcher, empty sketch face on, Master selected, words correct. |
| 4 | sketch_add | GOOD | BAD | View is 5.55 x 5.06 mm on the origin. The 53 x 26 mm rectangle is not on screen; only the Elements list shows 4 lines selected. |
| 7 | pd_pad | GOOD | GOOD | Model tree, Pad row selected, solid green and well framed, words "Padded Profile by 53 mm". |
| 10 | pd_pocket | GOOD | GOOD | Pocket row selected, cut clear, words "Pocketed Corner". |
| 11 | pd_mirrored | GOOD | GOOD | Mirrored row selected, second cut clear. |
| 19 | feature_edit | MINOR | GOOD | Words now "Set Pocket 2 Refine to on". Pocket 2 row selected. |
| 20 | feature_list | MINOR | GOOD | Own words with result: "Listed the features of Tut: tip Pocket 2". |
| 21 | body_check | MINOR | GOOD | "Checked Tut: sound". Tut row selected. |
| 24 | pd_hole | MINOR | MINOR | Hole row selected, words correct. The 2 mm hole is hard to find (frame is the body). |
| 25 | pd_linear_pattern | MINOR | MINOR | Three small holes visible. Words "Repeated a feature in a row" do not name Hole. |
| 26 | pd_chamfer | MINOR | MINOR | Words "Chamfered edges by 1 mm". Change too small to see. |
| 27 | pd_fillet | GOOD | GOOD | Round corner visible, Fillet row selected, words correct. |
| 28 | pd_datum_plane | MINOR | GOOD | Only the plane is green, body grey, offset clear, words "Made a datum plane Above". |
| 29 | feature_suppress | MINOR | MINOR | Words correct, Fillet row selected. Plane Above is now hidden (P8). Square corner is a small change. |
| 32 | pd_tip | MINOR | MINOR | Words now "Read Tut's tip" (correct kind) but do not say the tip (Fillet). |
| 34 | pd_primitive | GOOD | GOOD | View framed on the new box only. PlateBase row selected. No yellow plane. |
| 35 | pd_draft | MINOR | MINOR | Draft row selected, words "Tapered faces by 5°". Taper only a slight lean on the right face. |
| 37 | pd_multitransform | BAD | GOOD | Plate shown with 4 bores, BoreGrid row selected, words "Repeated Bore in Plate". |
| 38 | pd_datum | BAD | GOOD | Datum line green through a bore of the shown Plate, words "Made a datum line BoreAxis". |
| 49 | pd_thickness | MINOR | GOOD | Tray hollow, green, fills the view. Words "Hollowed Tray to 2 mm walls". |
| 51 | pd_binder | MINOR | MINOR | No caption (status words only: "Copied Tray into Cap"). Binder row not selected. Only a thin yellow edge at the Tray base. Tasks shows "Start Part / New Body". |
| 56 | pd_polar_pattern | MINOR | GOOD | Disc with 6 holes, green, fills view. No datum plane over it. |
| 59 | pd_clone | MINOR | GOOD | Clone green above the grey Disc, words "Cloned Disc". |
| 63 | pd_revolution | MINOR | GOOD | Ring green and large, words "Revolved RingProfile". |
| 68 | pd_groove | BAD | GOOD | Echo now runs: caption, status, Groove row selected, two grooves visible, RingAxis hidden. |
| 74 | pd_helix | MINOR | GOOD | Coil large and green, words "Made a helix from Wire". (Ring is a C shape; planned, call 71.) |
| 82 | pd_loft | MINOR | GOOD | Frustum large and green. Plane "Up" hidden. |
| 88 | pd_pipe | MINOR | GOOD | Pipe large and green, words "Swept a sketch along a path". |
| 90 | pd_gear | MINOR | GOOD | Gear large, teeth clear, words "Made a gear Spur". |
| 95 | pd_boolean | MINOR | GOOD | Sheet with cut, SheetCut row selected, words "Combined bodies into Sheet". |
| 102 | pd_reorder | MINOR | MINOR | Words "Moved H2 before H1", H2 row selected. A large grey post of another body stands in front of the block. |
| 108 | pd_move_feature | BAD | MINOR | Words "Moved Pad 3 to Hist2", Pad 3 row selected and green. Frame is 11 mm; other bodies fill and cut into the view. Tasks shows "Modeling Tools" with Hole, Revolve, Additive Helix in bold (unclear why). |
| 111 | pd_shaft | MINOR | MINOR | Shaft green and clear, words "Made a shaft Shaft". Property view shows H1 while the Shaft row is selected; H1 (red, tip mark) now sits in Hist2. |

### Sketcher (21)

| call | tool | before | now | why |
|---|---|---|---|---|
| 1 | pd_body_new | MINOR | GOOD | Model tree, Star row selected, words correct. |
| 2 | sketch_new | GOOD | GOOD | Face on, empty sketch, words correct. |
| 3 | sketch_add | GOOD | MINOR | Five lines selected (green, and in Elements). View is 5.55 mm wide; the 30 mm lines run off the screen. |
| 4 | sketch_constrain | GOOD | MINOR | Five constraints selected in the list. Same 6.8 mm over-zoom. Words do not say which constraints. |
| 13 | sketch_state | MINOR | MINOR | Words now "Read StarSketch: fully constrained" (fixed). View 27 mm; the star arcs are out of frame. |
| 14 | pd_pad | GOOD | GOOD | Star solid green, Pad row selected, words correct. |
| 20 | sketch_edit | MINOR | GOOD | Face on. "70 mm" readable. Words "Set plate_width to 70 in PlateSketch". |
| 24 | sketch_external | MINOR | GOOD | Face on, external circle and line selected, words good. |
| 29 | sketch_offset | MINOR | MINOR | Face on, words "Offset geometry in TopSketch by 1 mm". The new curve is hard to tell from the old; 2-Circle selected. |
| 31 | sketch_carbon | MINOR | GOOD | Copied geometry selected, face on, words "Copied PlateSketch into PlateCopy". |
| 33 | sketch_project | BAD | MINOR | Words now "Projected edges of PlateSketch into PlateCopy". New lines 6, 7 in the list but not selected or seen. |
| 37 | sketch_validate | MINOR | MINOR | Face on (XZ). Words "Validated TourSketch": no result. |
| 39 | sketch_array | MINOR | GOOD | Six circles, new ones selected, words "Made a 2 by 3 array in TourSketch". |
| 40 | sketch_copy | MINOR | GOOD | New circle selected green, words "Copied geometry in TourSketch". |
| 42 | sketch_extend | MINOR | GOOD | Longer arc selected green, words with 15.708 mm. |
| 48 | sketch_to_bspline | MINOR | MINOR | B-spline selected, words correct. Weight labels lie on top of each other. |
| 49 | sketch_bspline | BAD | MINOR | Words "Raised a B-spline's degree". Change hard to see; labels overlap. |
| 51 | sketch_mirror | MINOR | MINOR | TourMirror now open (S5 fixed), words good. Labels overlap; TourSketch geometry also shown. |
| 52 | sketch_merge | BAD | MINOR | TourBoth open (116 DoF), words "Merged TourSketch and TourMirror into TourBoth". Crowded, labels overlap. |
| 53 | sketch_attach | MINOR | BAD | Camera not turned to the new XY plane: TourBoth is seen edge-on as a line. Words "Put TourBoth on XY" (no 3 mm). |
| 60 | sketch_join | MINOR | MINOR | Face on, words "Joined two curves in Cuts", B-spline selected. Small, labels overlap, crowded. |

### Assembly (21)

| call | tool | before | now | why |
|---|---|---|---|---|
| 1 | part_primitive | GOOD | GOOD | Box green, words "Made a box Base". |
| 5 | part_boolean | GOOD | GOOD | Fused shape green, words correct. |
| 13 | part_transform | MINOR | GOOD | Rod green, words "Moved SliderRod". |
| 31 | asm_new | GOOD | MINOR | Words good. Tree row ConnectingRod selected (not the assembly); nothing green in 3D. |
| 32 | asm_ground | BAD | GOOD | Words "Let Base move again"; lock gone. |
| 35 | asm_joint | GOOD | GOOD | Crank on pin, marker visible, words "Joined parts with a revolute joint". SliderRod and ConnectingRod drawn see-through (unclear why). |
| 36 | asm_limits | MINOR | GOOD | Words "Limited CrankPivot to -90 ... 90"; property view shows the joint. |
| 38 | asm_pose | MINOR | MINOR | Words "Moved CrankPivot to 45". Crank still reads as an upright post (A6, not in scope). |
| 41 | asm_sweep | BAD | MINOR | Words "Swept CrankPivot from -90 to 90: clear". Picture is the start pose (expected). |
| 44 | asm_motion | MINOR | MINOR | Words "Saved the motion swing". Nothing to see (correct). |
| 49 | asm_list | MINOR | MINOR | Own words now, but "Read CrankSlider: solve: solved" reads badly. Base and SliderRod see-through. |
| 50 | shape_query | MINOR | MINOR | Words "Found faces of ConnectingRod: 2 found". Faces not highlighted. |
| 53 | asm_check | MINOR | GOOD | "Checked CrankSlider for overlaps: clear". |
| 54 | asm_fits | MINOR | GOOD | "Checked the H7/g6 fits of CrankSlider: needs a fix". |
| 55 | asm_bom | MINOR | MINOR | Words "Made a parts list". Bills_of_Materials now visible in tree but not selected; table not shown. |
| 56 | asm_explode | GOOD | GOOD | Parts lifted, dotted lines, words correct. |
| 59 | asm_export | BAD | GOOD | "Exported the assembly for the solver: wrote crank_slider.asmt". No dotted lines left. |
| 61 | asm_add | MINOR | BAD | No caption and no status bar words at all. Washer fills the view but is not selected. |
| 64 | asm_joint_remove | MINOR | GOOD | "Removed the joint WasherGap". No red lines. |
| 66 | asm_new_part | MINOR | GOOD | "Made a new part Guard"; Guard and Guard 2 rows selected (empty part, nothing to see). |
| 71 | asm_sub | MINOR | GOOD | Stand green, framed, words "Put Stand into CrankSlider". |

## Counts

| family | earlier GOOD/MINOR/BAD | now GOOD/MINOR/BAD |
|---|---|---|
| Part Design (34) | 7 / 23 / 4 | 22 / 11 / 1 |
| Sketcher (21) | 4 / 14 / 3 | 9 / 11 / 1 |
| Assembly (21) | 5 / 13 / 3 | 13 / 7 / 1 |

Got worse: pd 004 (GOOD to BAD), sk 003, sk 004 (GOOD to MINOR), sk 053 (MINOR to BAD), asm 031 (GOOD to
MINOR), asm 061 (MINOR to BAD).

## Earlier problems: fixed or not

| item | status | proof |
|---|---|---|
| P3 Model tab in front | FIXED | Model tab in front in all 76; tree visible (pd 007, sk 014, asm 031). Caveat: the Tasks panel is now a separate right-hand dock, so the new layout may be the reason, not the tab-raise code. |
| P4 hidden body | FIXED | pd 037 and 038 show Plate; pd 108 shows Hist2 with Pad 3; Hist row still shown in 111. |
| P5 fit | PARTLY | 3D: FIXED, new part fills the view (pd 034, 049, 074, 088, 090, asm 061, 071). Sketch: WORSE on new sketches, view 5 to 7 mm on the origin (pd 004, sk 003, sk 004), 27 mm cutting the star (sk 013). pd 108 framed at 11 mm with neighbours cut in. |
| P6 selection | PARTLY | Tree row is the feature now (pd 007, 010, 019, 037, 095); datum alone green (pd 028, 038). Not selected: pd 051 binder, asm 061 washer; asm 031 selects ConnectingRod row with no 3D highlight. |
| P7 lit button | WORSE | No ring in any of 76 (was 17 in PD). In sketch mode the Sketcher toolbars are not on screen at all (only the "What's this" row: sk 002 to 060, pd 003, 004). In all 21 Assembly pictures every Part and Assembly button is greyed out (disabled). No "»" overflow at this width, so not the cause. |
| P8 datum planes | FIXED | Above hidden at 029; RingAxis hidden at 068; Up hidden at 082; no yellow plane in 034 to 111. |
| Words / captions | PARTLY (mostly fixed) | Reads and checks now say a result (pd 020, 021; sk 013; asm 041, 049, 050, 053, 054, 059). Tool-name words gone (sk 031 to 060, asm 036, 038, 044, 071). Remaining: no caption pd 051; no words at all asm 061; no result sk 037, pd 032; no offset in sk 053; "solve: solved" in asm 049. |
| S1 camera faces sketch | PARTLY | Face on after solids exist: sk 020, 024, 029, 031, 033, 037 to 052, 060. Not after sketch_attach to a new plane: sk 053 edge-on. |
| S4 sketch selection | FIXED (one gap) | New geometry selected: sk 003, 024, 031, 039, 040, 042, 048, 049, 060; constraints in sk 004. Not in sk 033 (projected lines). |
| A7 assembly selection | PARTLY | Green: asm 013, 071; rows: asm 066. Not: asm 031 (3D), 035 joint, 050 faces, 055 BOM row, 061 washer. |
| S5 new sketch shown | FIXED | sk 051 opens TourMirror; sk 052 opens TourBoth (116 DoF). |
| A9 explode lines | FIXED | No dotted lines in asm 059, 061, 064, 066, 071. |
| A1 / S9 sketch left open | NOT FIXED (left as is, as echo2 says) | Tasks dock shows "Sketch Edit, 21 Degrees of Freedom" (sketch Cuts) in all 21 Assembly pictures. New side effect seen: Part and Assembly toolbars greyed in all 21. |
| A2 asm_ground words | FIXED | asm 032. |
| N3 pd_groove no echo | FIXED | pd 068. |

## New problems

1. No ring at all (76 of 76). Rings were visible before. Either the ring is put out before the picture
   is taken (echo2 now calls `rings_off()` at the start of every call; the ring lasts 1.3 s) or it is not
   drawn. Pictures of earlier runs showed rings, so this is a regression in what a person sees. Check the
   `echo.button` trace on a batch row with `profile: true`.
2. Sketch fit over-zooms on a new or small sketch: pd 004 (rectangle not on screen), sk 003, sk 004, sk 013.
   The "fit: sketch" step seems to frame something near the origin (5.55 mm) instead of the whole sketch.
3. Words missing on two calls: pd 051 pd_binder (no caption, status only); asm 061 asm_add (no caption and
   no status). Same symptom as the old pd_groove. Read the `…Error` step in the trace for those calls.
4. Sketcher edit toolbars absent in every sketch-mode picture, so no sketch button can be ringed even if
   the ring works.
5. Every button greyed in the Part and Assembly benches (all 21 asm pictures), very likely because the
   sketch Cuts is still in edit in another document (A1/S9). A person cannot use those buttons either.
6. sketch_attach does not turn the camera to the new plane (sk 053).
7. asm_new selects the last part row (ConnectingRod), not the new assembly (asm 031).
8. A white sketch outline (Tut's visible sketch Master/Corner) stays on Tut from pd 010 to 111.
9. Parts drawn see-through in asm 035 to 041 and 049 (SliderRod, ConnectingRod, Base); cause unknown.
10. pd 111: property view shows H1 while the Shaft row is selected; H1 with the tip mark is now in Hist2.
11. Part Design Tasks panel shows some entries in bold (pd 028 Datum Plane, 038 Datum Line, 108 Hole,
    Revolve, Additive Helix). It may be the echo marking a task item; it does not match pd 108's step.

## Tools proven live in the window (GOOD or MINOR here)

Part Design: pd_body_new, sketch_new, pd_pad, pd_pocket, pd_mirrored, feature_edit, feature_list,
body_check, pd_hole, pd_linear_pattern, pd_chamfer, pd_fillet, pd_datum_plane, feature_suppress, pd_tip,
pd_primitive, pd_draft, pd_multitransform, pd_datum, pd_thickness, pd_binder, pd_polar_pattern, pd_clone,
pd_revolution, pd_groove, pd_helix, pd_loft, pd_pipe, pd_gear, pd_boolean, pd_reorder, pd_move_feature,
pd_shaft. (sketch_add is BAD in the PD run, MINOR in the Sketcher run.)

Sketcher: sketch_add, sketch_constrain, sketch_state, sketch_edit, sketch_external, sketch_offset,
sketch_carbon, sketch_project, sketch_validate, sketch_array, sketch_copy, sketch_extend,
sketch_to_bspline, sketch_bspline, sketch_mirror, sketch_merge, sketch_join.

Assembly: part_primitive, part_boolean, part_transform, asm_new, asm_ground, asm_joint, asm_limits,
asm_pose, asm_sweep, asm_motion, asm_list, shape_query, asm_check, asm_fits, asm_bom, asm_explode,
asm_export, asm_joint_remove, asm_new_part, asm_sub.

Not proven here: sketch_attach (sk 053), asm_add (asm 061). No tool is proven for the lit-button part of
the echo.

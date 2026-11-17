# Window review, round 3 (after echo round 3): Part Design, Sketcher, Assembly

Pictures: `pics3/pd` (34), `pics3/sk` (21), `pics3/asm` (21). Only the pictures in `pictures.json` count.
I looked at all 76 pictures at full size (1400 x 852). I also made enlarged crops of the toolbar rows
(pd 003, 019, 020, 021, 029, 032, 090, 102, 108, 111; sk 029, 039, 040; asm 001, 005), the tree of
pd 007 and sk 029, and the ringed button of pd 034.
Compared with: `docs/hardening/window-pd3-skasm2-findings.md` (round 2) and the claims in
`docs/hardening/echo3-findings.md`. No code was read. No other file was changed. No Mac tools.

Limits: one frame per call, no motion, no Report view in any picture (red error text cannot be judged).

## Short answers to the round-3 questions

| family | pictures | ring visible | caption visible | result selected (changing calls) | Sketcher edit toolbars in sketch-edit pictures |
|---|---|---|---|---|---|
| Part Design | 34 | 24 | 34 | 31 of 31 | yes (pd 003, 004) |
| Sketcher | 21 | 15 | 21 | 18 of 19 (not sk 020) | yes, in all 19 sketch-edit pictures |
| Assembly | 21 | 15 | 21 | 9 of 17 (see below) | no sketch in edit (correct) |

- Ring: back. Round 2 had 0 of 76; now 54 of 76. The ringed button matches the tool in every case I
  checked. Two are near misses: asm 001 rings Part "Primitives..." and not the Box button; asm 005 rings
  the general Boolean button and not Fuse. Pictures with no ring are calls that have no toolbar button
  (feature_edit, feature_suppress, pd_tip, pd_gear, pd_reorder, pd_move_feature, pd_shaft, sketch_edit,
  sketch_validate, sketch_mirror, sketch_merge, sketch_attach, asm_limits, asm_pose, asm_sweep,
  asm_motion, asm_joint_remove) or sketch_new (no New Sketch button in sketch edit).
- Reads keep the last change's ring and selection (pd 020; sk 013; asm 049, 050). This works as claimed.
- Caption: in all 76, with the "Agent:" words and the same words in the status bar.
- Assembly selection: selected in asm 001, 005, 013, 031 (part), 036, 056, 061, 066, 071. Not selected:
  asm 032 (Base), 035 (joint CrankPivot), 038 (joint), 055 (Bills_of_Materials). Nothing to select:
  041, 044, 059, 064.

## Ratings

The property view is often stale (it shows the object of an earlier call). I record that once (N2) and
do not count it per picture.

### Part Design (34)

| call | tool | round 2 | round 3 | why |
|---|---|---|---|---|
| 2 | pd_body_new | MINOR | GOOD | Empty view (correct), Tut selected, body button ringed, words "Made a new body Tut". |
| 3 | sketch_new | GOOD | GOOD | Sketcher, face on, Master selected, edit toolbars shown, words correct. No button to ring. |
| 4 | sketch_add | BAD | GOOD | Whole 53 x 26 rectangle framed face on, 4 lines selected, Rectangle ringed. |
| 7 | pd_pad | GOOD | GOOD | Pad row selected, solid framed, Pad ringed, words "Padded Profile by 53 mm". |
| 10 | pd_pocket | GOOD | GOOD | Pocket row selected, cut clear, Pocket ringed. |
| 11 | pd_mirrored | GOOD | GOOD | Words now "Mirrored Pocket in Tut", second cut clear, Mirrored ringed. |
| 19 | feature_edit | GOOD | GOOD | Pocket 2 selected, words "Set Pocket 2 Refine to on". Property view shows only "Label Tut". |
| 20 | feature_list | GOOD | GOOD | Read; keeps Pocket 2 selected; words give the tip. |
| 21 | body_check | GOOD | GOOD | "Checked Tut: sound", Tut selected. |
| 24 | pd_hole | MINOR | MINOR | Hole row selected, Hole ringed, words good. The 2 mm hole is still hard to find. |
| 25 | pd_linear_pattern | MINOR | GOOD | Words now "Repeated Hole in a row", 3 holes visible, button ringed. |
| 26 | pd_chamfer | MINOR | MINOR | Chamfer ringed and selected, words good. The 1 mm change is too small to see. |
| 27 | pd_fillet | GOOD | GOOD | Round corner visible, Fillet ringed and selected. |
| 28 | pd_datum_plane | GOOD | GOOD | Plane alone green, datum button ringed, words good. Tasks shows "Datum Plane" in bold. |
| 29 | feature_suppress | MINOR | GOOD | Fillet selected, "Suppressed Yes", corner square again, plane Above hidden. |
| 32 | pd_tip | MINOR | MINOR | Words "Read Tut's tip" still do not give the tip (Fillet). |
| 34 | pd_primitive | GOOD | GOOD | New box fills the view, PlateBase selected, additive primitive ringed. |
| 35 | pd_draft | MINOR | MINOR | Draft ringed and selected, words good. Taper only a slight lean. |
| 37 | pd_multitransform | GOOD | GOOD | 4 bores, BoreGrid ringed and selected. |
| 38 | pd_datum | GOOD | GOOD | Datum line green through a bore, datum button ringed. Tasks shows "Datum Line" in bold. |
| 49 | pd_thickness | GOOD | GOOD | Hollow tray fills the view, Thickness ringed and selected. |
| 51 | pd_binder | MINOR | MINOR | Fixed: caption, binder row selected, binder button ringed. The binder is only a thin green edge at the base. |
| 56 | pd_polar_pattern | GOOD | GOOD | Words now "Repeated Pin in a circle", 6 holes, ringed. |
| 59 | pd_clone | GOOD | GOOD | Clone green above Disc, Clone ringed, DiscClone selected. |
| 63 | pd_revolution | GOOD | GOOD | Ring solid green and large, Revolution ringed. |
| 68 | pd_groove | GOOD | GOOD | Two grooves, Groove ringed and selected, RingAxis hidden. |
| 74 | pd_helix | GOOD | GOOD | Coil large and green, Helix ringed. |
| 82 | pd_loft | GOOD | GOOD | Frustum large and green, Loft ringed, plane Up hidden. |
| 88 | pd_pipe | GOOD | GOOD | Pipe green, Pipe ringed. A neighbour sits under the caption. |
| 90 | pd_gear | GOOD | GOOD | Gear large, teeth clear, "Spur bore" row selected. No button. |
| 95 | pd_boolean | GOOD | GOOD | Sheet with cut, Boolean ringed, SheetCut selected. |
| 102 | pd_reorder | MINOR | MINOR | Words good, H2 selected. Grey post of another body still stands in front of the block. |
| 108 | pd_move_feature | MINOR | MINOR | Pad 3 selected, words good. Frame 11 mm, other bodies fill the view. Tasks shows Hole, Revolve, Additive Helix in bold. |
| 111 | pd_shaft | MINOR | MINOR | Shaft green and clear. Property view shows H1; H1 has a red icon in Hist2. |

### Sketcher (21)

| call | tool | round 2 | round 3 | why |
|---|---|---|---|---|
| 1 | pd_body_new | GOOD | GOOD | Star selected, body ringed, words correct. |
| 2 | sketch_new | GOOD | GOOD | Face on, empty sketch, edit toolbars shown. |
| 3 | sketch_add | MINOR | GOOD | All five 30 mm lines framed and selected, Line ringed. |
| 4 | sketch_constrain | MINOR | GOOD | Whole sketch framed, 5 constraints selected, Coincident ringed. |
| 13 | sketch_state | MINOR | GOOD | Whole star framed, words "Read StarSketch: fully constrained". Last ring kept. |
| 14 | pd_pad | GOOD | GOOD | Star solid green, Pad ringed and selected. |
| 20 | sketch_edit | GOOD | GOOD | Face on, "70 mm" readable, words good. The changed constraint is not selected. |
| 24 | sketch_external | GOOD | GOOD | External circle and line selected, external button ringed. Tree row shows Pad 2, not TopSketch. |
| 29 | sketch_offset | MINOR | MINOR | Offset ringed, new circle selected. View 15.5 mm on one hole; upper halves of the circles hidden behind the plate face. |
| 31 | sketch_carbon | GOOD | GOOD | Copied geometry selected, Carbon copy ringed. |
| 33 | sketch_project | MINOR | GOOD | Projected lines 6 and 7 selected and drawn dashed, button ringed. |
| 37 | sketch_validate | MINOR | MINOR | Face on. Words "Validated TourSketch" still give no result. Plate seen edge-on covers part of the sketch. |
| 39 | sketch_array | GOOD | GOOD | New circles selected, Translate ringed. Plate edge-on overlaps one circle. |
| 40 | sketch_copy | GOOD | GOOD | New circle 10 selected, Translate (copy) ringed. |
| 42 | sketch_extend | GOOD | GOOD | Longer arc selected, Trim/Extend ringed, words with 15.708 mm. |
| 48 | sketch_to_bspline | MINOR | GOOD | B-spline selected, button ringed, weight labels now readable. |
| 49 | sketch_bspline | MINOR | GOOD | Degree 3 and new weights shown, Increase degree ringed. |
| 51 | sketch_mirror | MINOR | MINOR | TourMirror open, words good. Nothing selected; TourSketch drawn on top; crowded. |
| 52 | sketch_merge | MINOR | MINOR | TourBoth open (116 DoF), words good. Crowded; nothing selected. |
| 53 | sketch_attach | BAD | MINOR | Fixed: face on to XY, words "Put TourBoth on XY, 3 mm off". The Plate and Star bodies cover most of the sketch. |
| 60 | sketch_join | MINOR | MINOR | Join ringed, B-spline selected. Plate edge-on covers the sketch; the joint is small. |

### Assembly (21)

| call | tool | round 2 | round 3 | why |
|---|---|---|---|---|
| 1 | part_primitive | GOOD | GOOD | Box green, words good. Ring on Primitives dialog, not the Box button. |
| 5 | part_boolean | GOOD | GOOD | Fused shape green, words good. Ring on general Boolean, not Fuse. Tree row not lit; property view empty. |
| 13 | part_transform | GOOD | GOOD | Rod green and framed, SliderRod selected. |
| 31 | asm_new | MINOR | MINOR | Assembly ringed, all parts green, words good. Tree row selected is still ConnectingRod, not CrankSlider. |
| 32 | asm_ground | GOOD | MINOR | Words good, Ground ringed. Base not selected. |
| 35 | asm_joint | GOOD | MINOR | Revolute ringed, words good. Joint not selected; SliderRod and ConnectingRod see-through. |
| 36 | asm_limits | GOOD | GOOD | Words good; property view shows CrankPivot. |
| 38 | asm_pose | MINOR | MINOR | Words good. Crank reads as an upright post; joint not selected. |
| 41 | asm_sweep | MINOR | MINOR | Words "...: clear". Picture is the start pose (expected). |
| 44 | asm_motion | MINOR | MINOR | Words good. Nothing to see (correct). |
| 49 | asm_list | MINOR | MINOR | Words now "solver says solved". The whole assembly is drawn see-through. |
| 50 | shape_query | MINOR | MINOR | ConnectingRod whole green; the 2 faces not lit. |
| 53 | asm_check | GOOD | MINOR | Words good, check button ringed. ConnectingRod from call 50 still selected (left over). |
| 54 | asm_fits | GOOD | MINOR | Words good. Same left-over ConnectingRod selection. |
| 55 | asm_bom | MINOR | BAD | Words "Made a parts list", BOM ringed. Table not shown (claim said the sheet opens). Bills_of_Materials not selected; ConnectingRod row still selected. |
| 56 | asm_explode | GOOD | GOOD | Parts lifted, dotted lines, explode ringed. |
| 59 | asm_export | GOOD | GOOD | Words with file name, no dotted lines left. |
| 61 | asm_add | BAD | GOOD | Fixed: caption, washer green and framed, Insert ringed. |
| 64 | asm_joint_remove | GOOD | GOOD | Words good, no red lines. |
| 66 | asm_new_part | GOOD | GOOD | Guard and Guard 2 rows selected, button ringed. |
| 71 | asm_sub | GOOD | GOOD | Stand green and framed, rows selected. |

## Counts

| family | round 2 GOOD/MINOR/BAD | round 3 GOOD/MINOR/BAD |
|---|---|---|
| Part Design (34) | 22 / 11 / 1 | 26 / 8 / 0 |
| Sketcher (21) | 9 / 11 / 1 | 15 / 6 / 0 |
| Assembly (21) | 13 / 7 / 1 | 10 / 10 / 1 |

Assembly is lower mainly because the result is often not selected, or an earlier read's selection is
left standing (asm 032, 035, 053, 054, 055). Rings and words in Assembly are better than in round 2.

## Round-2 problems: status

| round-2 problem | status | pictures |
|---|---|---|
| 1. No ring at all (0 of 76) | FIXED | 54 of 76 ringed: pd 004, 007, 025, 051; sk 003, 029, 060; asm 031, 055, 061. Reads keep the ring: sk 013, asm 049. |
| 2. Sketch fit over-zooms on new or small sketch | FIXED (one left) | pd 004, sk 003, 004, 013 now whole. sk 029 still 15.5 mm on one hole. |
| 3. Words missing (pd 051, asm 061) | FIXED | pd 051, asm 061. |
| 4. Sketcher edit toolbars absent | FIXED | Shown in pd 003, 004 and all 19 sketch-edit sk pictures. |
| 5. All buttons greyed in Part/Assembly (sketch left in edit) | FIXED | No Sketch Edit dock and enabled buttons in all 21 asm pictures. |
| 6. sketch_attach not turned to new plane | FIXED | sk 053 face on, offset in words (but covered, new problem N1). |
| 7. asm_new selects ConnectingRod | NOT FIXED | asm 031 (3D shows all parts green, tree row is ConnectingRod). |
| 8. White sketch outline stays on Tut | NOT FIXED | Master stays shown with a red/yellow mark from pd 007 to 032; outline in 010 to 111. |
| 9. Parts drawn see-through in Assembly | NOT FIXED / WORSE | asm 035, 036, 038, 041; asm 049 whole assembly see-through. |
| 10. pd 111 property view shows H1 | NOT FIXED, and wider | pd 111; see N2. |
| 11. Bold entries in Part Design Tasks | NOT FIXED | pd 028, 038, 108. |
| P6 selection gaps | PARTLY | Fixed: pd 051, asm 061, sk 033. Still: asm 031, 032, 035, 038, 055, sk 020. |
| Words: no result | PARTLY | Fixed: pd 025, 056 name the feature; asm 049 reads well; sk 053 gives offset. Still: pd 032, sk 037. |
| pd 108 frame 11 mm with neighbours; pd 102 post in front | NOT FIXED | pd 102, 108. |
| asm_bom table not shown | NOT FIXED (claimed fixed) | asm 055. |
| shape_query faces not lit | NOT FIXED (claim says not done) | asm 050. |
| P3 Model tab in front | FIXED (still) | all 76. |
| P8 datum planes left shown | FIXED (still) | pd 029, 068, 082. |

## Problems particular to these families (what the echo should do)

N1. Sketch in edit drawn behind other bodies (sk 029, 037, 039, 053, 060). The "covering objects
    see-through" rule (`uncover()`) does not run for `sketch_` calls. In sk 053 the Plate and Star hide
    most of TourBoth. The echo should make other shown bodies see-through (or hide them) while an agent
    sketch is in edit, and put them back after.
N2. Property view stale. It shows an object from an earlier call while the tree row of the new result is
    selected: pd 026 (LinearPattern), 034 to 038 (Tut), 049, 051 (PlateHoles), 059 (Fillet 2),
    088 to 102 (TubePath), 111 (H1); sk 001 (Shaft); asm 031, 032 (ConnectingRod). The selection is set
    but the property view does not follow. The echo should let the property view update after it selects
    (for example clear, then add the selection, then process events), or set it to the result.
N3. Read selection left standing (asm 050 -> 053, 054, 055). shape_query selects ConnectingRod; the next
    calls (asm_check, asm_fits, asm_bom) do not replace it. asm_check and asm_fits ring a button, so
    they count as changing calls; they should clear the old selection or select CrankSlider.
N4. asm_bom does not show the table (asm 055). The claim says `show_view_of` opens the sheet; the 3D view
    is in front. Check that the BOM object (Bills_of_Materials) is a spreadsheet the code can find, and
    select it.
N5. asm_new selects the last part, not the assembly (asm 031). `OUT_MORE` for asm_new does not reach the
    tree; select CrankSlider after the parts are added.
N6. Assembly joints are not selected (asm 035, 038). The Joints folder stays closed. Select the joint and
    expand the folder.
N7. Assembly see-through parts (asm 035 to 041, 049). Cause unknown; if `uncover()` or the Assembly
    "Activate" ghost does this, put the parts back for Assembly calls.
N8. sk 029 frames only one hole at 15.5 mm; the offset curve's sketch is framed, but the result reads
    badly with the plate face over it. Add a margin and see N1.
N9. Ring on a near button: asm 001 (Primitives dialog for a box), asm 005 (general Boolean for fuse).
    Map part_primitive kind=box to Part_Box and part_boolean op=fuse to Part_Fuse.
N10. sk 051, 052: the new sketch is open but nothing in it is selected, and the source sketch is drawn
    over it. Hide the source sketches while the new one is in edit.

## Tools proven live in the window (GOOD or MINOR here)

Part Design (all 34): pd_body_new, sketch_new, sketch_add, pd_pad, pd_pocket, pd_mirrored, feature_edit,
feature_list, body_check, pd_hole, pd_linear_pattern, pd_chamfer, pd_fillet, pd_datum_plane,
feature_suppress, pd_tip, pd_primitive, pd_draft, pd_multitransform, pd_datum, pd_thickness, pd_binder,
pd_polar_pattern, pd_clone, pd_revolution, pd_groove, pd_helix, pd_loft, pd_pipe, pd_gear, pd_boolean,
pd_reorder, pd_move_feature, pd_shaft.

Sketcher (all 21): pd_body_new, sketch_new, sketch_add, sketch_constrain, sketch_state, pd_pad,
sketch_edit, sketch_external, sketch_offset, sketch_carbon, sketch_project, sketch_validate,
sketch_array, sketch_copy, sketch_extend, sketch_to_bspline, sketch_bspline, sketch_mirror,
sketch_merge, sketch_attach, sketch_join.

Assembly (20 of 21): part_primitive, part_boolean, part_transform, asm_new, asm_ground, asm_joint,
asm_limits, asm_pose, asm_sweep, asm_motion, asm_list, shape_query, asm_check, asm_fits, asm_explode,
asm_export, asm_add, asm_joint_remove, asm_new_part, asm_sub.

Not proven here: asm_bom (asm 055, table not shown).

Lit-button part of the echo: now proven for 54 pictures across the three families.

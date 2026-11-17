# Window review, round 4: Part Design, Sketcher, Assembly, Part, Points, Spreadsheet

Pictures: `pics4/pd` (34), `sk` (21), `asm` (21), `part` (37), `pts` (10), `sheet` (23). I looked at all 146 pictures that `pictures.json` lists.
Compared with the round-3 reviews `window-r3-pd-sk-asm-findings.md`, `window-r3-part-core-pts-sheet-findings.md` and the claims in `round4-findings.md`.
No code was read and no Mac tools were used. One frame per call.

## General (counted once, not marked again in each row)

- G1 (NEW, all families from asm 055 on): the Assembly **Bill of Materials task dialog** (Cancel / OK, Columns, Export) opens at asm_bom and **stays open** in every later asm picture, in all 37 Part and 10 Points pictures, and in sheet 0001-0004 (in other documents too). It goes away at sheet 0005 (pd_pad). It takes 370 px of the window and leaves a modal-like task open.
- G2: the Report view stays open with old red errors (DiffuseColor traceback, CompoundFilter, AttachEngine, OpenSCAD, Spreadsheet parse). This is the same as round 3.
- G3: the active-container highlight (green row) is on the body or assembly in all pd, sk and asm pictures. This is FreeCAD's normal look.
- G4 (FIXED): the property view now follows the new result in nearly all pictures (pd 034-111, sk 001, asm 031, 032, pts 0011). The tree often does not scroll down to the new row (pd 025+, part 0024+, pts 0008+), but the property view names the result.

## Counts

| family | round 3 G/M/B | round 4 G/M/B | ring on real button | caption | result selected |
|---|---|---|---|---|---|
| Part Design (34) | 26 / 8 / 0 | **28 / 6 / 0** | 24 | 34 | 33 (not 108) |
| Sketcher (21) | 15 / 6 / 0 | **13 / 8 / 0** | 15 | 21 | 18 (not 020, 051, 052) |
| Assembly (21) | 10 / 10 / 1 | **11 / 9 / 1** | 14 | 21 | 15 of 17 changing |
| Part (37) | 8 / 27 / 2 | **14 / 21 / 2** | 22 (was 12) | 37 | 34 |
| Points (10) | 1 / 8 / 1 | **2 / 8 / 0** | 8 (was 1) | 10 | 9 |
| Sheet (23) | 10 / 12 / 1 | **13 / 10 / 0** | 14 real + 6 on Alias (was 4) | 23 | 18 |

The Sketcher drop is my stricter rating of sk 024 and 040, where bodies cover the sketch. It is not a regression in the echo. Sketcher edit toolbars show in all sketch-edit pictures (pd 003, 004; sk 002-053, 060; sheet 0002-0004).

## 1. Part Design (34)

| pic | tool | rating | reason |
|---|---|---|---|
| 002 | pd_body_new | GOOD | Body ringed, Tut selected |
| 003 | sketch_new | GOOD | Face on, edit toolbars, Master selected |
| 004 | sketch_add | GOOD | Rectangle framed, 4 lines selected, ringed |
| 007 | pd_pad | GOOD | Pad ringed, row and properties Pad |
| 010 | pd_pocket | GOOD | Cut clear, Pocket ringed |
| 011 | pd_mirrored | GOOD | Second cut, Mirrored ringed |
| 019 | feature_edit | GOOD | Pocket 2 properties, Refine on in words |
| 020 | feature_list | GOOD | Read keeps Pocket 2, words give tip |
| 021 | body_check | GOOD | "Checked Tut: sound" |
| 024 | pd_hole | MINOR | Hole ringed, 2 mm hole still hard to see |
| 025 | pd_linear_pattern | GOOD | Holes in a row, ringed |
| 026 | pd_chamfer | MINOR | Ringed; 1 mm chamfer not visible |
| 027 | pd_fillet | GOOD | Round corner, ringed |
| 028 | pd_datum_plane | GOOD | Plane green, datum ringed |
| 029 | feature_suppress | GOOD | "Suppressed: Yes", corner square |
| 032 | pd_tip | MINOR | Words "Read Tut's tip: 18440 mm³" still give no tip name |
| 034 | pd_primitive | GOOD | Box ringed, properties PlateBase (fixed) |
| 035 | pd_draft | MINOR | Ringed; taper only a slight lean |
| 037 | pd_multitransform | GOOD | 4 bores, ringed |
| 038 | pd_datum | GOOD | Datum line green, ringed |
| 049 | pd_thickness | GOOD | Hollow tray, ringed |
| 051 | pd_binder | GOOD | Tray see-through, binder face clear (fixed) |
| 056 | pd_polar_pattern | GOOD | 6 holes, ringed |
| 059 | pd_clone | GOOD | Clone green, ringed |
| 063 | pd_revolution | GOOD | Ring green, ringed |
| 068 | pd_groove | GOOD | Grooves, ringed |
| 074 | pd_helix | GOOD | Coil green, ringed |
| 082 | pd_loft | GOOD | Frustum, ringed |
| 088 | pd_pipe | GOOD | Pipe green, ringed |
| 090 | pd_gear | GOOD | Gear green, properties Spur bore |
| 095 | pd_boolean | GOOD | Sheet with cut, ringed |
| 102 | pd_reorder | MINOR | Grey post of another body still in front |
| 108 | pd_move_feature | MINOR | Properties show "Island"; tight frame, bold Tasks entries |
| 111 | pd_shaft | GOOD | Shaft green, properties Shaft (fixed H1) |

Round-3 problems:
- N2 stale property view: **FIXED** (pd 034, 035, 037, 049, 059, 111).
- Master outline on Tut: **FIXED** in the 3D view (no white outline). The Master row still shows its eye and a red/yellow mark (pd 007-032).
- pd 102 post in front: **NOT FIXED**.
- pd 108 frame: **NOT FIXED**. The property view shows "Island", not Pad 3.
- Bold entries in Tasks: **NOT FIXED** (028, 038, 108).
- pd_tip words: **NOT FIXED** (032).
- pd 051 binder thin: **FIXED** (Tray is now see-through).

Part Design particular: pd_reorder and pd_move_feature should uncover the other bodies and frame the moved feature, and select it.

## 2. Sketcher (21)

| pic | tool | rating | reason |
|---|---|---|---|
| 001 | pd_body_new | GOOD | Star selected, ringed |
| 002 | sketch_new | GOOD | Face on, edit toolbars |
| 003 | sketch_add | GOOD | Five lines framed and selected, Line ringed |
| 004 | sketch_constrain | GOOD | 5 constraints selected, ringed |
| 013 | sketch_state | GOOD | "fully constrained", whole star |
| 014 | pd_pad | GOOD | Star solid, Pad ringed |
| 020 | sketch_edit | GOOD | 70 mm shown, Star see-through; constraint not selected |
| 024 | sketch_external | MINOR | Row TopSketch now; opaque Star covers external circle |
| 029 | sketch_offset | MINOR | Ringed; still framed on one hole |
| 031 | sketch_carbon | GOOD | Copy selected, ringed, Star see-through |
| 033 | sketch_project | GOOD | Projected lines selected, ringed |
| 037 | sketch_validate | MINOR | Edge-on plate covers sketch; words give no result |
| 039 | sketch_array | MINOR | Array selected, ringed; edge-on plate overlaps circles |
| 040 | sketch_copy | MINOR | Copy selected, ringed; edge-on plate overlaps |
| 042 | sketch_extend | GOOD | Arc selected, length in words |
| 048 | sketch_to_bspline | GOOD | B-spline selected, weights shown |
| 049 | sketch_bspline | GOOD | Degree raised, ringed |
| 051 | sketch_mirror | MINOR | Source TourSketch drawn on top; nothing selected |
| 052 | sketch_merge | MINOR | Sources shown, red-marked rows; nothing selected |
| 053 | sketch_attach | GOOD | Plate and Star see-through, sketch clear (fixed) |
| 060 | sketch_join | MINOR | Edge-on plate over the joint; source rows red-marked |

Round-3 problems:
- N1 bodies over the sketch: **PARTLY**. Fixed when the bodies face the camera (sk 020, 031, 033, 053). NOT FIXED when a body is seen edge-on or beside the sketch (sk 024, 037, 039, 040, 060). The new line-of-sight test seems to miss bodies whose box is crossed only at the side.
- N8 sk 029 one-hole frame: **NOT FIXED**.
- N10 sk 051 and 052 sources over the new sketch, nothing selected: **NOT FIXED**.
- sk 020 changed constraint not selected: **NOT FIXED**.
- sk 037 words: **NOT FIXED**.
- NEW: TourSketch, TourMirror and TourBoth have red marks in the tree (sk 052, 060). They may be sketch errors. Check them with body_check.

## 3. Assembly (21)

| pic | tool | rating | reason |
|---|---|---|---|
| 001 | part_primitive | GOOD | Box button ringed (fixed N9) |
| 005 | part_boolean | GOOD | Fuse ringed (fixed N9) |
| 013 | part_transform | GOOD | SliderRod green, selected |
| 031 | asm_new | GOOD | CrankSlider row selected (fixed N5) |
| 032 | asm_ground | GOOD | Base selected (fixed) |
| 035 | asm_joint | MINOR | Parts opaque now; joint row not selected, Joints closed |
| 036 | asm_limits | GOOD | Words good, CrankPivot properties |
| 038 | asm_pose | MINOR | Crank reads as a post; joint row not selected |
| 041 | asm_sweep | GOOD | Opaque, words with range |
| 044 | asm_motion | GOOD | Ringed, words good |
| 049 | asm_list | GOOD | Whole assembly opaque now (fixed) |
| 050 | shape_query | MINOR | ConnectingRod row selected; the 2 faces not lit |
| 053 | asm_check | GOOD | Old ConnectingRod selection gone (fixed N3) |
| 054 | asm_fits | GOOD | Words "needs a fix" |
| 055 | asm_bom | BAD | BOM task dialog opens and stays; table not shown |
| 056 | asm_explode | MINOR | Explode good; BOM dialog left open |
| 059 | asm_export | MINOR | File in words; BOM dialog left open |
| 061 | asm_add | MINOR | Washer green, ringed; BOM dialog left open |
| 064 | asm_joint_remove | MINOR | Words good; BOM dialog left open |
| 066 | asm_new_part | MINOR | Guard 2 properties, ringed; BOM dialog left open |
| 071 | asm_sub | MINOR | Stand green; BOM dialog left open |

Round-3 problems: N3 **FIXED**. N5 **FIXED**. N7 see-through **FIXED** (035-054 opaque). N9 **FIXED**. asm_ground selection **FIXED**. N6 joint not selected **NOT FIXED** (035, 038; the property view shows the joint but the tree row is not selected). shape_query faces **NOT FIXED** (asm 050, part 0033). N4 asm_bom table **WORSE**: in place of the sheet, the echo opened the BOM object's own task dialog. This is likely `show_view_of` calling `doubleClicked()` on the `Assembly::BomObject`, which opens its edit task. The dialog is never closed (G1).

What the echo should do for asm_bom: never call doubleClicked on a BomObject. Open its sheet view with the Spreadsheet view, not an edit. If a task dialog was opened, close it (`Gui.Control.closeDialog()`) before the call returns.

## 4. Part (37)

| pic | tool | rating | reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Box ringed (near miss fixed), volume in words |
| 0003 | object_set | GOOD | Cube see-through, Inner green (fixed) |
| 0004 | body_check | GOOD | Same view, "Checked Inner: sound" |
| 0008 | part_boolean | MINOR | Fuse ringed; opaque Cube hides box part; properties Inner |
| 0011 | part_transform | MINOR | Rotated box framed; words "Moved" for a rotate |
| 0021 | part_wire | MINOR | Plane selected and ringed now; words are the tool name |
| 0022 | part_section | GOOD | Outline green, Section ringed |
| 0024 | part_slices | MINOR | Slices selected and ringed now; words tool name |
| 0025 | part_split | MINOR | Hidden Halves selected; all grey; no ring |
| 0026 | part_compound | MINOR | Green result; no ring; words tool name |
| 0027 | compound_filter | MINOR | One half green; no ring; words tool name |
| 0030 | compound_explode | BAD | New red traceback "Nothing passes through the filter" |
| 0031 | part_fillet | GOOD | Fillet ringed, ball green |
| 0033 | shape_query | MINOR | Found face not lit; Block not selected |
| 0034 | part_extrude | GOOD | Extrude ringed, face named |
| 0037 | part_chamfer | GOOD | Chamfer ringed |
| 0038 | part_refine | MINOR | Words good; no ring (claimed mapped) |
| 0040 | part_thickness | GOOD | Thickness ringed, Cup green |
| 0044 | part_offset | MINOR | Pad green; no ring; new object unclear |
| 0049 | part_revolve | GOOD | Revolve ringed |
| 0052 | part_sweep | GOOD | Sweep ringed |
| 0053 | part_loft | GOOD | Loft ringed |
| 0055 | part_face | MINOR | Make face ringed now; words tool name |
| 0056 | part_offset2d | MINOR | Band green; no ring; words tool name |
| 0059 | part_ruled | MINOR | Ruled ringed now; words tool name |
| 0062 | part_project | MINOR | Projection ringed; Screen fills view; words tool name |
| 0063 | part_extract | MINOR | Top face green, ringed; words tool name |
| 0065 | part_fix | GOOD | Words "Turned Screen again inside out" (fixed) |
| 0068 | part_datum | MINOR | Whole-document fit; faint datum square |
| 0073 | part_attach | MINOR | Peg framed; no ring; words tool name |
| 0080 | part_defeature | MINOR | Defeaturing ringed; removed face not visible |
| 0081 | meshobj_from_shape | BAD | Still whole-document fit (1 m); mesh tiny |
| 0082 | part_from_mesh | GOOD | Words name Taper mesh (fixed) |
| 0086 | part_join | MINOR | Tee green; opaque box behind; no ring |
| 0087 | part_container | MINOR | Std Part ringed, Tee part selected; words tool name |
| 0096 | export | GOOD | File in words, ring kept |
| 0097 | part_import_curves | MINOR | Crate see-through now; awkward words |

Round-3 problems:
1. Covers not see-through: **PARTLY** (fixed 0003, 0004, 0097; not 0008, 0086).
2. Missing rings: **PARTLY** (now 0021, 0024, 0055, 0059, 0062, 0063, 0080, 0081, 0087). Still none on split, compound, compound_filter, compound_explode, refine, offset, offset2d, attach, join.
3. Wrong tree selection: **PARTLY** (0021, 0024, 0087 fixed; 0025 still the hidden parent).
4. Traceback at 0030: **NOT FIXED**.
5. meshobj_from_shape fit: **NOT FIXED** (the Mesh Info box is gone).
6. Captions: **PARTLY** (0065, 0082 fixed). "Part xxx on Name" is still in 0021, 0024, 0026, 0027, 0055, 0056, 0059, 0062, 0063, 0068, 0073, 0080, 0086, 0087, 0097. `activity.json` lacks phrases for these tools.
7. z-fighting: **PARTLY** (0031 better; 0030 still).

## 5. Points (10)

| pic | tool | rating | reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Cylinder ringed |
| 0002 | points_sample | MINOR | Cloud visible, Shaft see-through, ringed (fixed); words tool name |
| 0003 | points_info | GOOD | "Read Shaft cloud: 6000 points" |
| 0004 | points_export | MINOR | Words "Exported Points on shaft.ply: 6000 found" |
| 0008 | points_import | MINOR | Import ringed; tree not scrolled to Shaft back |
| 0010 | points_crop | MINOR | Polygon cut ringed; 2x cloud behind; words tool name |
| 0011 | points_fit | MINOR | Shaft fit selected (fixed); no ring |
| 0021 | points_mesh | MINOR | Mesh selected; no ring; whole-document fit |
| 0027 | points_merge | MINOR | Merge ringed; whole-document fit |
| 0028 | points_structure | MINOR | Structure ringed; grid not shown on its own |

Round-3 problems:
1. Cloud under the solid: **FIXED** (0002-0008).
2. Selection lag: **FIXED** (0008, 0010, 0011 in the property view).
3. No Points rings: **FIXED** (8 of 10; none on points_fit and points_mesh).
4. 2x cloud: not a fault (scale 2).
5. Mesh and structure fit the whole document: **NOT FIXED** (0021, 0027, 0028).
- NEW: Points words use "Points xxx on Name" (0002, 0010, 0011, 0021, 0028).

## 6. Spreadsheet / VarSet (23)

| pic | tool | rating | reason |
|---|---|---|---|
| 0001 | pd_body_new | GOOD | Body ringed |
| 0002 | sketch_new | GOOD | Edit toolbars, face on |
| 0003 | sketch_add | GOOD | Polygon ringed, "2 added" |
| 0004 | sketch_constrain | GOOD | Ringed, 1 DoF |
| 0005 | pd_pad | GOOD | Pad ringed, nut green |
| 0006 | sheet_new | GOOD | Create-sheet ringed, sheet open |
| 0007 | sheet_set | MINOR | Cells filled; ring on Alias button, not right |
| 0013 | param_bind | MINOR | Spreadsheet bench; nothing selected; words lack names |
| 0018 | sheet_read | MINOR | Sheet shown; words "Read Dimensions" no values |
| 0020 | sheet_list | GOOD | Sheet shown, words good |
| 0021 | sheet_format | MINOR | Bold ringed, words good; white text on light grey |
| 0023 | sheet_rows | MINOR | Row inserted; ring on Alias; B2 shows 0.84 cm |
| 0026 | sheet_cells | MINOR | Merge ringed, words good; merge not visible |
| 0030 | sheet_export | MINOR | Words fixed; ring on Alias, not export |
| 0031 | sheet_import | GOOD | New sheet opened, import ringed |
| 0033 | varset_new | GOOD | VarSet ringed, NutVars properties (fixed) |
| 0035 | varset_set | GOOD | 10.80 mm shown |
| 0037 | param_set | GOOD | Params sheet opened (fixed), value in words |
| 0041 | param_list | MINOR | Params shown; no count; new red Params.B3 error |
| 0043 | sheet_table | GOOD | NutTable shown, row selected, words good |
| 0047 | param_remove | GOOD | Params shown, row removed (fixed) |
| 0054 | sheet_chart | MINOR | NutTable shown (fixed); no chart; words "Spreadsheet chart on bar" |
| 0055 | sheet_clear | MINOR | Empty sheet; words "Cleared Spreadsheet", no range |

Round-3 problems:
1. Sheet not shown: **FIXED** (0037, 0041, 0047, 0054).
2. No Spreadsheet rings: **PARTLY**. Real buttons ring in 0006, 0021, 0026, 0031, 0033, 0043. The Alias button ("Set alias") is ringed for sheet_set, sheet_rows, sheet_export, param_set, param_remove and sheet_clear. That is a wrong mapping.
3. White-on-light format: **NOT FIXED** (0021-0030).
4. Cell selection not moved to the changed range: **NOT FIXED** (0021, 0026, 0055).
5. Tool-name captions: **PARTLY** (format, rows, cells, table fixed; chart and clear still poor).
6. param_bind bench and selection: **NOT FIXED** (0013).
7. B2 unit to cm after insert row: still there (0023-0030).

## Top problems left (what the echo should do)

1. Close the BOM task dialog. asm_bom opens the BomObject edit dialog, and it stays across documents (G1). Show the sheet without setEdit, and close any task the echo opened.
2. Bodies edge-on or beside a sketch still cover it (sk 024, 037, 039, 040, 060). Also part 0008 and 0086. Widen the cover test, or hide other bodies while an agent sketch is in edit.
3. Tool-name words ("Part xxx on", "Points xxx on", "Spreadsheet chart on") are still in about 20 pictures. Add phrases for part_wire, part_slices, part_compound, compound_filter, part_face, part_offset2d, part_ruled, part_project, part_extract, part_datum, part_attach, part_defeature, part_join, part_container, the points_ tools, sheet_chart and sheet_clear.
4. Whole-document fit is left for meshobj_from_shape (part 0081), part_datum (0068), points_mesh, points_merge and points_structure. Fit the new object.
5. Sheet rings default to the Alias button. Map sheet_set, sheet_rows (insert rows), sheet_export, sheet_clear and param_set/remove to their real buttons, or to none.
6. Faces found by shape_query are still not lit (asm 050, part 0033). Joints are not selected in the tree (asm 035, 038).
7. compound_explode prints a red traceback (part 0030). sk 051 and 052 draw the source sketches over the new one, with nothing selected.

## Proven live

PROVEN_LIVE pd: pd_body_new, sketch_new, sketch_add, pd_pad, pd_pocket, pd_mirrored, feature_edit, feature_list, body_check, pd_hole, pd_linear_pattern, pd_chamfer, pd_fillet, pd_datum_plane, feature_suppress, pd_tip, pd_primitive, pd_draft, pd_multitransform, pd_datum, pd_thickness, pd_binder, pd_polar_pattern, pd_clone, pd_revolution, pd_groove, pd_helix, pd_loft, pd_pipe, pd_gear, pd_boolean, pd_reorder, pd_move_feature, pd_shaft
NOT_PROVEN pd: none
PROVEN_LIVE sk: pd_body_new, sketch_new, sketch_add, sketch_constrain, sketch_state, pd_pad, sketch_edit, sketch_external, sketch_offset, sketch_carbon, sketch_project, sketch_validate, sketch_array, sketch_copy, sketch_extend, sketch_to_bspline, sketch_bspline, sketch_mirror, sketch_merge, sketch_attach, sketch_join
NOT_PROVEN sk: none
PROVEN_LIVE asm: part_primitive, part_boolean, part_transform, asm_new, asm_ground, asm_joint, asm_limits, asm_pose, asm_sweep, asm_motion, asm_list, asm_check, asm_fits, asm_explode, asm_export, asm_add, asm_joint_remove, asm_new_part, asm_sub
NOT_PROVEN asm: asm_bom (task dialog in place of the table, left open), shape_query (faces not lit)
PROVEN_LIVE part: part_primitive, object_set, body_check, part_boolean, part_transform, part_wire, part_section, part_slices, part_compound, compound_filter, part_fillet, part_extrude, part_chamfer, part_refine, part_thickness, part_revolve, part_sweep, part_loft, part_face, part_offset2d, part_ruled, part_project, part_extract, part_fix, part_datum, part_attach, part_from_mesh, part_join, part_container, export, part_import_curves
NOT_PROVEN part: part_split (hidden parent, result not shown), part_offset (new object unclear), part_defeature (removed face not visible), shape_query (face not lit), compound_explode (traceback), meshobj_from_shape (whole-document fit)
PROVEN_LIVE pts: part_primitive, points_sample, points_info, points_export, points_import, points_crop, points_fit, points_mesh, points_merge
NOT_PROVEN pts: points_structure (grid not shown on its own)
PROVEN_LIVE sheet: pd_body_new, sketch_new, sketch_add, sketch_constrain, pd_pad, sheet_new, sheet_set, param_bind, sheet_read, sheet_list, sheet_format, sheet_rows, sheet_export, sheet_import, varset_new, varset_set, param_set, param_list, sheet_table, param_remove, sheet_clear
NOT_PROVEN sheet: sheet_cells (merge not visible), sheet_chart (no chart shown)

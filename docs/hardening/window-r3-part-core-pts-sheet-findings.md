# Window review, round 3 (first review of these families): Part, Core, Points, Spreadsheet/VarSet

I looked at all 119 pictures listed in pictures.json (Part 37, Core 49, Points 10, Sheet 23).

General notes that apply to all four families (counted here, not repeated in every row):
- The Report view stays open at the bottom for the whole run after Part call 30. Its old red errors (CompoundFilter "Nothing passes through the filter", AttachEngine3D "No planar face", OpenSCAD "executable not found", Spreadsheet parse errors) stay on screen in every later picture, also in other documents.
- The property view often shows the object of an EARLIER call (it lags by one or more calls). Examples: Part 0024-0037 show "Big ones" or "Ball slices"; Points 0021 shows "Plate cloud".
- When the tree is longer than the panel, it does not scroll to the new object. The new object is selected but you cannot see it in the tree (Part 0049 on, Core 0074/0097, Points 0021 on, Sheet 0037 on).
- From Core 0082 on, the right-hand Tasks panel is wider and the 3D view is narrower (about 630 px wide in place of 810 px). It does not go back. The document tabs are cut off.

---

## 1. Part (37 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Cube made, framed, selected, ring on Primitives, caption good |
| 0003 | object_set | MINOR | Inner is selected but hidden inside Cube; Cube is not see-through |
| 0004 | body_check | MINOR | Same as 0003: Inner is hidden inside Cube; caption "sound" is good |
| 0008 | part_boolean | MINOR | Ring on Union; only the cylinder caps show green, the box part is hidden inside Cube; property view is empty |
| 0011 | part_transform | MINOR | Rotated box is selected and framed; no ring |
| 0021 | part_wire | MINOR | Plane shows green in the view, but the tree selects Cube; caption "Part wire on Mid plane" is tool-like |
| 0022 | part_section | GOOD | Section outline shown and selected, ring on Section, caption good |
| 0024 | part_slices | MINOR | Nothing is selected in the tree; no ring; recompute button shows the document needs recompute |
| 0025 | part_split | MINOR | The selected item "Halves" is hidden; Halves 1 and 2 are not selected; no ring |
| 0026 | part_compound | MINOR | Result selected and framed; no ring; property view is stale |
| 0027 | compound_filter | MINOR | One half selected and framed; no ring; property view lags (shows Halves again) |
| 0030 | compound_explode | BAD | Report view opens with a red Python traceback (CompoundFilter "Nothing passes"); striped z-fighting on the ball; no ring |
| 0031 | part_fillet | GOOD | Whiffle ball selected, ring on Fillet, caption good (some z-fighting from overlapping bodies) |
| 0033 | shape_query | MINOR | Whole Block selected, not the found top face; old ring from Primitives stays (correct for round 3) |
| 0034 | part_extrude | GOOD | Block selected, ring on Extrude, caption names the face |
| 0037 | part_chamfer | GOOD | Block selected, ring on Chamfer, caption good |
| 0038 | part_refine | MINOR | Selected and framed; no ring |
| 0040 | part_thickness | MINOR | Cup selected, ring on Thickness; property view is stale; a part of the neighbour shows in the corner |
| 0044 | part_offset | MINOR | Pad selected; I cannot tell if the offset is a new object or Pad itself; no ring |
| 0049 | part_revolve | GOOD | Ring selected, ring on Revolve, caption good (tree not scrolled to it) |
| 0052 | part_sweep | GOOD | Coil selected, ring on Sweep, caption good |
| 0053 | part_loft | GOOD | Cone selected, ring on Loft, caption good |
| 0055 | part_face | MINOR | Hex face selected; no ring (Make face button exists); caption "Part face on Hex face" is tool-like |
| 0056 | part_offset2d | MINOR | Band selected (area in status bar); no ring; caption is tool-like |
| 0059 | part_ruled | MINOR | Ramp selected; no ring on Ruled surface button; caption is tool-like |
| 0062 | part_project | MINOR | Projected hex shown green, but the Screen block fills and spills over the view; stray ramp edges; no ring |
| 0063 | part_extract | MINOR | Top face shown green on a see-through Screen; no ring; caption is tool-like |
| 0065 | part_fix | MINOR | Screen again selected; caption "Fixed Part on Screen again" is unclear (does not say "reversed") |
| 0068 | part_datum | MINOR | Fit frames the whole document; the datum plane is a tiny faint square |
| 0073 | part_attach | MINOR | Peg selected and close-framed, attachment shown in properties; no ring; caption is tool-like |
| 0080 | part_defeature | MINOR | Plate selected, but I cannot see a removed face; new red AttachEngine errors in Report view |
| 0081 | meshobj_from_shape | BAD | Fit frames the whole document; the new mesh is a tiny cone; a datum plane and axis show; Mesh Info task box opens on the right; no ring |
| 0082 | part_from_mesh | MINOR | Solid shown and selected; caption is wrong: "Turned Taper solid into a solid" (should name the mesh) |
| 0086 | part_join | MINOR | Tee selected; a grey box covers the back and is not see-through; no ring |
| 0087 | part_container | MINOR | The Tee is selected, not the new "Tee part" container; no ring on Std Part |
| 0096 | export | GOOD-ish, rated MINOR | Crate selected, caption gives the file; only the old Report errors |
| 0097 | part_import_curves | MINOR | Imported curves lie on top of Crate, which is not see-through, so they show only as broken green lines |

Counts: GOOD 8, MINOR 27, BAD 2.

Round-3 counts: visible ring 12 of 37 (0001, 0008, 0022, 0031, 0033 kept, 0034, 0037, 0040, 0049, 0052, 0053, 0096 kept). Caption present 37 of 37 (none stale). Result selected 34 of 37 (not 0021, 0024, 0033 face).

### Part problems particular to this family
1. Covering objects are not see-through (0003, 0004, 0008, 0086, 0097). The new or changed object is inside or under another body. The echo should make the covering bodies see-through (or hide them for the picture), as round 3 promised.
2. Rings missing on Part buttons that exist: Make face (0055), Ruled surface (0059), Projection on surface (0062), Section/Cross-sections (0024), Offset/2D offset (0044, 0056), Split (0025), Compound tools (0026, 0027, 0030), Refine (0038), Std Part (0087), Mesh from shape (0081). Add these to the tool-to-button table.
3. Tree selection is not the new object (0021 selects Cube; 0024 selects nothing; 0025 selects a hidden parent; 0087 selects the child). The echo should select the object the tool made (for explode/split: the pieces).
4. 0030: after an earlier failing compound_filter, the Report view pops up with a red traceback and stays for the rest of the run. The echo should not leave the Report view open, or the failing call should be caught so FreeCAD does not print a traceback.
5. 0081: meshobj_from_shape fits the whole document. Fit the new mesh, hide or make see-through the source solid, and do not open the Mesh Info task box.
6. Caption wording bugs: 0082 "Turned Taper solid into a solid"; 0065 "Fixed Part on ..."; 0021/0055/0056/0059/0063/0073/0086/0087 "Part xxx on Name" is the tool name, not what was done.
7. Overlapping copies flicker (z-fighting) in 0030 and 0031. Hide the input when the result sits on top of it.

### Part tools proven live in the window (GOOD or MINOR, result visible)
part_primitive, part_boolean, part_transform, part_wire, part_section, part_slices, part_split, part_compound, compound_filter, part_fillet, shape_query (body only), part_extrude, part_chamfer, part_refine, part_thickness, part_revolve, part_sweep, part_loft, part_face, part_offset2d, part_ruled, part_project, part_extract, part_fix, part_datum, part_attach, part_from_mesh, part_join, part_container, export, part_import_curves.
Not proven: object_set and body_check (result hidden inside Cube), part_offset (unclear result), part_defeature (removed face not visible), compound_explode and meshobj_from_shape (BAD).

---

## 2. Core: document, view, material, robot, OpenSCAD, inspection (49 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Block made, framed, selected, ring, caption good |
| 0003 | object_list | GOOD | Caption "2 found"; last change (Rod) stays selected with its ring |
| 0005 | object_get | MINOR | Block is highlighted in the view but the tree and properties still show Rod; Block not framed |
| 0007 | object_set | GOOD | Block selected, caption "Set Block Length to 2 in" |
| 0011 | units_convert | MINOR | Caption "Converted units" does not give the answer (50.8 mm) |
| 0014 | object_rename | MINOR | Pin is not selected; nothing is highlighted |
| 0016 | object_group | MINOR | Parts folder not selected or opened; no ring on Group button |
| 0021 | link_make | MINOR | A box shows green but no tree item is selected; property view is empty; caption has no name |
| 0023 | link_edit | BAD | Ghost is selected but hidden (eye off), so the edited link cannot be seen; caption "Edited Link" |
| 0025 | object_duplicate | MINOR | Tree selects "Pin copy", not the new "Block moved"; the copy sits exactly on Block |
| 0026 | object_align | MINOR | Block moved selected; flickers against Block (z-fighting); caption good |
| 0028 | text_document | BAD | Build notes is not selected or opened; the text cannot be seen; caption has no name |
| 0030 | doc_info | MINOR | The tool SET comment and company, but the caption says "Read the document's details" |
| 0031 | doc_graph | BAD | Picture is the same as 0030; caption is stale (doc_info); no graph shown |
| 0032 | object_appearance | BAD | Block stays grey; the two Block links turn blue instead; Face6 colour not seen; caption has no name |
| 0034 | object_freeze | MINOR | Caption "Froze an object" has no name; nothing shows what was frozen |
| 0035 | recompute | GOOD | Ring on Recompute, caption good |
| 0038 | shape_query | MINOR | Two edges of Block light up, not the found top face |
| 0041 | measure | BAD | Pin is selected (wrong object); caption is an explanation with no numbers; nothing measured is shown |
| 0044 | measure_keep | MINOR | 20.00 mm label shows on Block; measurement not selected; caption has no value |
| 0048 | section | BAD | No section is shown and no new object; old measurement stays selected |
| 0050 | clearance | MINOR | Caption "Measured the gap between parts" has no value; nothing shown |
| 0052 | measure_mass | MINOR | Caption "Weighed Block" has no mass |
| 0053 | material_list | MINOR | Caption has no count |
| 0054 | material_get | MINOR | Caption is a warning text, cut off, no material values |
| 0055 | material_set | MINOR | Material workbench, but Block not selected; no ring on the material button; caption has no names |
| 0060 | material_clear | MINOR | Block links show as hidden in the tree while they still show in the view; nothing selected |
| 0062 | insp_run | GOOD | Inspection workbench, colour map and legend shown, Shift check selected |
| 0063 | insp_read | MINOR | Colour map shown; caption "Read Inspection" has no worst values |
| 0064 | insp_list | MINOR | Caption "Listed Inspection" has no count |
| 0065 | insp_faces | MINOR | Caption is an explanation, not the face results |
| 0066 | insp_update | MINOR | Shift check is no longer selected; legend still -1..+1 after the tolerance change |
| 0069 | insp_export | MINOR | Caption has no file name |
| 0070 | scad_status | MINOR | Caption is a long warning text, cut off |
| 0071 | scad_export | MINOR | Workbench stays Inspection (should be OpenSCAD); Block not selected |
| 0072 | scad_import | BAD | Imported "cube" sits under the Inspection colour map of Block moved and cannot be seen; colour legend still on screen |
| 0074 | scad_op | MINOR | Hull shown; tree item hidden by scroll; property view shows "cube"; colour legend still on screen |
| 0077 | scad_tidy | MINOR | Caption "OpenSCAD tidy" is only the tool name; colour code not visible; Block links greyed in tree |
| 0081 | robot_new | BAD | Robot "Arm" is not visible at all (no VRML model); task panel opens on the right; colour legend still on screen |
| 0082 | robot_move | BAD | Robot still not visible; caption "Robot move" is only the tool name; 3D view becomes narrower |
| 0087 | robot_path | MINOR | Fit is 10 m wide; path is a small orange line; Trajectory Tools task box open |
| 0088 | robot_run | MINOR | Caption is an explanation ("out of reach..."), cut off |
| 0092 | robot_tool | BAD | Caption "Robot tool" only; robot and tool not shown; view still 10 m wide |
| 0096 | export | MINOR | Robot workbench stays; Block not framed or selected (view 10 m wide); caption good |
| 0097 | import_file | BAD | Robot workbench; imported shape is hidden under the colour map of Block moved; tree not scrolled to it |
| 0103 | doc_save_all | GOOD | Caption good; last change (Ball) stays selected with ring |
| 0105 | doc_merge | MINOR | Ball001 sits exactly on Ball; it merged into MergeSrc itself |
| 0108 | object_delete | GOOD | Ball gone, Ball001 left, caption good |
| 0110 | doc_open | MINOR | CoreDoc was already open, so a second "CoreDoc" (CoreDoc1) opens; camera is top view, not iso; nothing selected |

Counts: GOOD 7, MINOR 31, BAD 11.

Round-3 counts: visible ring 7 of 49 (0001, 0003, 0005, 0035, 0038, 0041, 0103; five of them are rings kept from an earlier call, as expected). Caption present 49 of 49 (1 stale: 0031). Result selected 14 of 49.

### Core problems particular to this family
1. Robot tools show nothing (0081, 0082, 0092): the Arm has no visible model, and the camera goes to a 10 m wide fit. The echo should fit the robot, and robot_new should load the robot model so it shows. Close the robot task panel after the call, and put the 3D view width back.
2. The Inspection colour map and legend stay on screen after the inspection calls (0071-0097). Later results (scad_import 0072, import_file 0097) sit under it and cannot be seen. When the next changing call is not an inspection call, hide the inspected copy and the legend.
3. The workbench does not follow the tool: scad_export stays in Inspection (0071); export and import_file stay in Robot (0096, 0097).
4. object_appearance (0032) colours the two Block links, not Block itself. Block keeps its grey colour, but its property view shows the new Agent Link colour properties. Check the tool, not only the echo.
5. Read-only and measure tools give no value in the caption: units_convert, clearance, measure_mass, material_list, insp_read, insp_list, measure_keep. Some captions are long explanations cut off with "..." (measure 0041, material_get 0054, insp_faces 0065, scad_status 0070, robot_run 0088). The caption should give the short answer (number + unit, or count).
6. Results not shown: text_document does not open the text (0028); doc_graph shows nothing and keeps the old caption (0031); section shows no cut (0048); measure selects Pin (0041).
7. Selection goes to the wrong object: object_duplicate selects "Pin copy" (0025); object_get highlights Block in the view but the tree keeps Rod (0005); link_edit selects a hidden link (0023).
8. doc_info caption says "Read" for a call that writes (0030).
9. doc_open on a document that is already open makes a second copy (0110).

### Core tools proven live in the window (GOOD or MINOR, result visible)
part_primitive, object_list, object_get (partly), object_set, object_rename, object_group, link_make, object_duplicate, object_align, doc_info, recompute, measure_keep, material_get, material_list, material_set (workbench only), insp_run, insp_read, insp_list, insp_faces, insp_update, insp_export, scad_status, scad_export, scad_op, robot_path, robot_run, export, doc_save_all, doc_merge, object_delete, doc_open.
Not proven: units_convert, clearance, measure_mass, object_freeze, material_clear, shape_query and scad_tidy (no visible effect or answer); link_edit, text_document, doc_graph, object_appearance, measure, section, scad_import, robot_new, robot_move, robot_tool, import_file (BAD).

---

## 3. Points (10 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Shaft made, framed, selected, ring, caption good |
| 0002 | points_sample | BAD | The cloud cannot be seen: the solid Shaft covers it; tree selects Shaft, not Shaft cloud; no ring |
| 0003 | points_info | MINOR | Shaft cloud selected (bounding box); caption has no point count; cloud still hidden by the solid |
| 0004 | points_export | MINOR | Caption gives file and "6000 found"; cloud still hidden by the solid |
| 0008 | points_import | MINOR | Shaft back made but Shaft cloud stays selected; the new cloud is not shown on its own |
| 0010 | points_crop | MINOR | Tree selects Shaft half, but caption says Shaft wall; one cloud is about twice the size of the shaft |
| 0011 | points_fit | MINOR | Fitted cylinder shows green, but the tree selects the input (Shaft wall), not Shaft fit |
| 0021 | points_mesh | MINOR | Fit frames the whole document; the plate mesh is not selected; property view shows Plate cloud |
| 0027 | points_merge | MINOR | Shaft parts selected (bounding box); fit frames the whole document; tree not scrolled |
| 0028 | points_structure | MINOR | Same picture as 0027 except the caption; Shaft grid not selected or shown |

Counts: GOOD 1, MINOR 8, BAD 1.

Round-3 counts: visible ring 1 of 10 (0001 only; I enlarged the Points toolbar and no Points button has a ring). Caption present 10 of 10. Result selected 4 of 10 (0001, 0003, 0004, 0027).

### Points problems particular to this family
1. Point clouds are invisible under their source solid (0002-0008). The echo should make the solid see-through or hide it, and show the points large enough to see (bigger point size or a colour).
2. Tree selection lags one call behind the view (0008, 0010, 0011). Select the object the tool made.
3. No ring on any Points button (sample = convert from shape, import, export, structure, merge, polygon cut).
4. 0010: a cloud about twice the shaft's size appears after import/crop. Check that the PLY import (Shaft back) keeps mm units.
5. Mesh and structure results (0021, 0028) are not selected and the fit covers the whole document.

### Points tools proven live in the window (GOOD or MINOR, result visible)
part_primitive, points_info, points_export, points_import (partly), points_crop, points_fit, points_mesh, points_merge.
Not proven: points_sample (BAD, cloud hidden), points_structure (no change visible).

---

## 4. Spreadsheet / VarSet (23 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001 | pd_body_new | GOOD | Part Design, ring on Body, Nut selected, caption good |
| 0002 | sketch_new | GOOD | Sketch edit open, Sketcher toolbars shown, caption good (no ring) |
| 0003 | sketch_add | GOOD | Ring on Polygon, elements selected, sketch framed by its lines (one diameter label cut off at right) |
| 0004 | sketch_constrain | GOOD | Ring on Coincident, 1 degree of freedom left, caption good |
| 0005 | pd_pad | GOOD | Ring on Pad, Pad selected and framed (an extra leftover toolbar row appears) |
| 0006 | sheet_new | GOOD | Spreadsheet workbench, empty sheet opened, Dimensions selected |
| 0007 | sheet_set | GOOD | Cells filled, B1:B3 selected, caption good |
| 0013 | param_bind | MINOR | Shows the 3D nut but workbench stays Spreadsheet; Pad not selected; caption "Linked a parameter" has no names; new red Spreadsheet parse errors in Report view |
| 0018 | sheet_read | MINOR | Sheet shown; caption "Read Dimensions" has no values; old cell selection stays |
| 0020 | sheet_list | GOOD | Sheet shown, caption good |
| 0021 | sheet_format | MINOR | A1:A3 get a light grey fill but the text stays white, so it cannot be read; caption is only the tool name; selection stays on B |
| 0023 | sheet_rows | MINOR | Row inserted; caption is only the tool name; B2 now shows "0.84 cm" in place of 8.40 mm |
| 0026 | sheet_cells | MINOR | Merge of D5:E5 cannot be seen; caption is only the tool name |
| 0030 | sheet_export | MINOR | Caption is a long explanation, cut off |
| 0031 | sheet_import | GOOD | New sheet nut-dimensions opened with the values, caption good |
| 0033 | varset_new | MINOR | NutVars not selected (nut-dimensions stays selected); its properties are not shown |
| 0035 | varset_set | GOOD | NutVars selected, Thickness 10.80 mm shown in properties |
| 0037 | param_set | MINOR | The Params sheet is not opened or selected; NutVars stays selected |
| 0041 | param_list | MINOR | New red error "Params.B3: Failed to parse expression '(clearance /'"; caption has no count |
| 0043 | sheet_table | MINOR | NutTable opened and row selected; rows 2 and 3 are the same M10 row; caption is tool-like |
| 0047 | param_remove | MINOR | Shows the 3D nut; Params sheet not shown |
| 0054 | sheet_chart | BAD | The chart is not shown and NutTable is not shown; only the 3D nut |
| 0055 | sheet_clear | MINOR | Dimensions shown with A1:B3 empty; caption has no range |

Counts: GOOD 10, MINOR 12, BAD 1.

Round-3 counts: visible ring 4 of 23 (0001, 0003, 0004, 0005; no Spreadsheet button gets a ring). Caption present 23 of 23. Result selected 8 of 23. Sketcher edit toolbars: YES, they show in all three sketch-edit pictures (0002, 0003, 0004), and the sketch is framed by its own lines in 0003 and 0004.

### Spreadsheet / VarSet problems particular to this family
1. Some sheet tools do not show their sheet: param_set, param_list, param_remove (Params sheet) and sheet_chart (NutTable and the chart) show the 3D view. Round 3 says sheet tools show their spreadsheet. For sheet_chart, also open the SVG chart or show it next to the sheet.
2. No ring on any Spreadsheet button (format bold/align, merge cells, insert rows, import/export, create sheet).
3. sheet_format: a light background with white text in the dark theme makes the labels unreadable (0021). When it sets a light background, also set a dark text colour (or warn).
4. Cell selection is not moved to the range the tool changed (0021 A1:A3, 0026 D5:E5, 0055 A1:B3).
5. Captions are only the tool name: "Spreadsheet format", "Spreadsheet rows", "Spreadsheet cells", "Spreadsheet table on NutTable".
6. param_bind (0013) and the varset tools leave the workbench on Spreadsheet while showing the 3D model. Use Part Design for param_bind.
7. Possible tool problems (not echo): sheet_table writes the M10 row twice (0043); sheet_rows changes the B2 display unit to cm (0023).

### Spreadsheet / VarSet tools proven live in the window (GOOD or MINOR, result visible)
pd_body_new, sketch_new, sketch_add, sketch_constrain, pd_pad, sheet_new, sheet_set, param_bind, sheet_read, sheet_list, sheet_format, sheet_rows, sheet_export, sheet_import, varset_new, varset_set, param_list, sheet_table, sheet_clear.
Not proven: sheet_cells (merge not visible), param_set and param_remove (Params sheet not shown), sheet_chart (BAD).

---

## Totals

| Family | Pictures | GOOD | MINOR | BAD | Ring | Caption | Result selected |
|---|---|---|---|---|---|---|---|
| Part | 37 | 8 | 27 | 2 | 12 | 37 | 34 |
| Core | 49 | 7 | 31 | 11 | 7 | 49 (1 stale) | 14 |
| Points | 10 | 1 | 8 | 1 | 1 | 10 | 4 |
| Sheet/VarSet | 23 | 10 | 12 | 1 | 4 | 23 | 8 |

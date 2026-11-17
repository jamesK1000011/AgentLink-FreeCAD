# Window review, round 6: Assembly, Part, Points, Core

Pictures: `pics6/asm` (21), `part` (37), `pts` (10), `core` (49). I looked at all 117 pictures listed in `pictures.json`.
Compared with `window-r4-pd-sk-asm-part-pts-sheet-findings.md`, `window-r4-core-bim-mesh-findings.md` and the claims in `round6-findings.md`.

Rating: GOOD = result shown correctly, only known general problems. MINOR = result shown, small problem. BAD = result not seen, or an error the user would see.

## General (counted once)

- G1 Bill of Materials task dialog: **FIXED**. asm 055 shows the BOM sheet ("CrankSlider BOM" tab, 4 rows with volumes) and no task dialog. No BOM dialog in any later picture (asm 056-071, all of part, pts and core). Only the normal "Activate Assembly" task watcher is in Tasks.
- Model tab is in front in all 117 pictures.
- The Report view keeps red text from earlier runs in every asm/part/pts picture ("Refine failed", "TopoShapeExpansion ... Shape index 29 out of bound 0", 05:22:09). From part 0030 the CompoundFilter traceback is added, and from part 0080 two new "AttachEngine3D ... no subobjects specified" lines (05:25:04-05, made by a call between part 0073 and 0080).
- Core: the kept "20.00 mm" measurement label still shows in every 3D picture from 0044 on, in the robot views too and in the second copy CoreDoc1 (0110).

## Counts

| Family | Round 4 G / M / B | **Round 6 G / M / B** |
|---|---|---|
| Assembly (21) | 11 / 9 / 1 | **17 / 4 / 0** |
| Part (37) | 14 / 21 / 2 | **14 / 22 / 1** |
| Points (10) | 2 / 8 / 0 | **3 / 7 / 0** |
| Core (49) | 18 / 27 / 4 | **16 / 31 / 2** |

## 1. Assembly (21)

| pic | tool | rating | reason |
|---|---|---|---|
| 001 | part_primitive | GOOD | Base framed, Box ringed, volume in words |
| 005 | part_boolean | GOOD | Fuse ringed, Base selected, volume |
| 013 | part_transform | GOOD | SliderRod selected; Base cut at right edge |
| 031 | asm_new | GOOD | CrankSlider selected, ringed, "4 parts" |
| 032 | asm_ground | GOOD | Base selected, words "Let Base move again" |
| 035 | asm_joint | MINOR | Joint in property view; tree row not selected |
| 036 | asm_limits | GOOD | Words give "-90 ... 90: solved" |
| 038 | asm_pose | MINOR | Crank reads as a post; joint row not selected |
| 041 | asm_sweep | GOOD | Words give range and "clear" |
| 044 | asm_motion | GOOD | Ringed, words name the motion |
| 049 | asm_list | GOOD | "solver says solved", last change kept |
| 050 | shape_query | MINOR | Bore faces not lit; whole rod selected |
| 053 | asm_check | GOOD | "overlaps: clear" |
| 054 | asm_fits | GOOD | "H7/g6 ... needs a fix" |
| 055 | asm_bom | GOOD | BOM sheet in front, no task dialog (fixed) |
| 056 | asm_explode | GOOD | Exploded view, ringed, no dialog |
| 059 | asm_export | GOOD | File named in words |
| 061 | asm_add | GOOD | Washer framed, selected, ringed |
| 064 | asm_joint_remove | GOOD | Words name WasherGap, "solved" |
| 066 | asm_new_part | MINOR | Empty Guard; property view only, nothing to see |
| 071 | asm_sub | GOOD | Stand framed, selected, "solved" |

Round-4 problems:
- asm_bom table and task dialog (N4, G1): **FIXED** (055 sheet shown; 056-071 no dialog).
- N6 joint row not selected in the tree: **NOT FIXED** (035, 038).
- shape_query faces not lit: **NOT FIXED** (050; the faces are bore faces inside the holes and the whole ConnectingRod row is selected).
- 038 Crank seen end-on as a post: **NOT FIXED** (property view also says Angle 0.00° after a pose to 45).

## 2. Part (37)

| pic | tool | rating | reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Box ringed, volume |
| 0003 | object_set | GOOD | Cube see-through, Inner green |
| 0004 | body_check | GOOD | "Checked Inner: sound" |
| 0008 | part_boolean | GOOD | Cube see-through now (fixed), Fuse ringed |
| 0011 | part_transform | MINOR | Words "Moved" for a rotate; no ring |
| 0021 | part_wire | MINOR | Ringed; words "Part wire on ..." (value added) |
| 0022 | part_section | GOOD | Outline green, Section ringed, length |
| 0024 | part_slices | MINOR | Ringed; words "Part slices on ..." |
| 0025 | part_split | MINOR | Old "Ball slices" stays selected; no ring, no count |
| 0026 | part_compound | MINOR | No ring; "Part compound on ..." |
| 0027 | compound_filter | MINOR | No ring; tool-name words, no value |
| 0030 | compound_explode | BAD | Red CompoundFilter traceback; z-fighting |
| 0031 | part_fillet | MINOR | Ringed; z-fighting patches on the ball |
| 0033 | shape_query | MINOR | Found face not lit |
| 0034 | part_extrude | GOOD | Extrude ringed, face named |
| 0037 | part_chamfer | GOOD | Chamfer ringed, volume |
| 0038 | part_refine | MINOR | No ring; no figure |
| 0040 | part_thickness | GOOD | Thickness ringed, Cup green |
| 0044 | part_offset | MINOR | No ring; result now clear (Pad 1728 mm³) |
| 0049 | part_revolve | GOOD | Revolve ringed |
| 0052 | part_sweep | GOOD | Sweep ringed |
| 0053 | part_loft | GOOD | Loft ringed |
| 0055 | part_face | MINOR | Ringed; "Part face on ..." |
| 0056 | part_offset2d | MINOR | No ring; "Part offset2d on ..." |
| 0059 | part_ruled | MINOR | Ringed; "Part ruled on ..." |
| 0062 | part_project | MINOR | Screen fills view; tool-name words |
| 0063 | part_extract | MINOR | Tool-name words; "160 mm" for a face |
| 0065 | part_fix | GOOD | "Turned Screen again inside out" |
| 0068 | part_datum | MINOR | Whole-document fit; datum a faint square |
| 0073 | part_attach | MINOR | No ring; "Part attach on Peg" |
| 0080 | part_defeature | MINOR | Removed face not seen; new red AttachEngine3D lines |
| 0081 | meshobj_from_shape | GOOD | Mesh framed, Mesh bench, ringed (fixed) |
| 0082 | part_from_mesh | MINOR | No caption and no status words (new) |
| 0086 | part_join | MINOR | No ring; tool-name words |
| 0087 | part_container | MINOR | Covers see-through; tool-name words |
| 0096 | export | GOOD | File in words, Crate selected |
| 0097 | part_import_curves | MINOR | Curves faint; "Imported Part curves on ..." |

Round-4 problems:
1. Covers not see-through: **FIXED** (0008 Cube see-through; 0087 Tee part see-through; 0086 box is behind, not over).
2. Missing rings: **NOT FIXED** (no ring on transform 0011, split 0025, compound 0026, compound_filter 0027, compound_explode 0030, refine 0038, offset 0044, offset2d 0056, attach 0073, join 0086).
3. Wrong selection at part_split: **PARTLY** (0025: the hidden "Halves" is no longer selected, but the old "Ball slices" stays selected; Halves 1 and 2 are not selected).
4. Traceback at compound_explode: **NOT FIXED** (0030 "Nothing passes through the filter", then "None left").
5. meshobj_from_shape fit: **FIXED** (0081).
6. Tool-name captions: **PARTLY**. Values now follow (0021, 0024, 0026, 0055, 0056, 0059, 0062, 0063), but "Part xxx on Name" stays in 0021, 0024, 0026, 0027, 0055, 0056, 0059, 0062, 0063, 0068, 0073, 0080, 0086, 0087, 0097.
7. z-fighting: **NOT FIXED** (0030, 0031).
- part_datum whole-document fit: **NOT FIXED** (0068: whole document, datum plane a faint green square at the left).
- New: 0082 part_from_mesh has no caption box and no status words. 0063 gives "160 mm" for an extracted face (status bar says area 16 cm²). 0080 new red AttachEngine3D lines.

## 3. Points (10)

| pic | tool | rating | reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Cylinder ringed, volume |
| 0002 | points_sample | MINOR | Cloud seen, ringed; "Points sample on ..." |
| 0003 | points_info | GOOD | "Read Shaft cloud: 6000 points" |
| 0004 | points_export | MINOR | "Exported Points on shaft.ply: 6000 found" |
| 0008 | points_import | GOOD | Ringed; tree scrolled to Shaft back (fixed) |
| 0010 | points_crop | MINOR | Ringed, 4296 points; tool-name words |
| 0011 | points_fit | MINOR | Fit selected; no ring; tool-name words |
| 0021 | points_mesh | MINOR | Framed on mesh now; no ring |
| 0027 | points_merge | MINOR | Framed on shaft now; merged cloud not told apart |
| 0028 | points_structure | MINOR | Grid not seen apart from the clouds |

Round-4 problems:
- Whole-document fit for points_mesh / merge / structure: **FIXED** for framing (0021 plate mesh fills view; 0027, 0028 framed on the shaft). **PARTLY** for points_structure: the grid cannot be told apart from the other clouds at the same place.
- No ring on points_fit, points_mesh: **NOT FIXED** (0011, 0021).
- "Points xxx on Name" words: **NOT FIXED** (0002, 0004, 0008, 0010, 0011, 0021, 0027, 0028); counts are now given.
- Tree not scrolled to the new row: **FIXED** (0008, 0010).

## 4. Core (49)

| pic | tool | rating | reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Block framed, ringed, volume; no BOM dialog |
| 0003 | object_list | GOOD | "2 found", Rod kept selected |
| 0005 | object_get | MINOR | "Read Block" without values; Block cut off |
| 0007 | object_set | GOOD | "Set Block Length to 2 in", 50.80 mm |
| 0011 | units_convert | GOOD | "50.8 mm" |
| 0014 | object_rename | MINOR | Pin not selected, property view empty |
| 0016 | object_group | GOOD | Parts selected, Group ringed |
| 0021 | link_make | MINOR | Ghost selected, ringed; words name nothing |
| 0023 | link_edit | MINOR | Ghost as Pin; words "Edited Link" |
| 0025 | object_duplicate | MINOR | Selected; words "Copied an object" |
| 0026 | object_align | MINOR | z-fighting with Block |
| 0028 | text_document | GOOD | Text tab, 18 characters |
| 0030 | doc_info | MINOR | Still "Renamed the document" |
| 0031 | doc_graph | MINOR | No graph, no count |
| 0032 | object_appearance | BAD | Selection green hides blue/red; words name nothing |
| 0034 | object_freeze | MINOR | "Froze an object"; nothing selected |
| 0035 | recompute | GOOD | Recompute ringed |
| 0038 | shape_query | MINOR | Face not seen: Block under opaque Block moved |
| 0041 | measure | MINOR | "20 mm"; faces not seen (was lit) |
| 0044 | measure_keep | GOOD | Label, ringed, property right |
| 0048 | section | MINOR | "1200 mm²"; no cut drawn |
| 0050 | clearance | GOOD | "15 mm" |
| 0052 | measure_mass | MINOR | Gives volume, not mass |
| 0053 | material_list | GOOD | "14 found" |
| 0054 | material_get | MINOR | Cut-off warning, no values |
| 0055 | material_set | MINOR | Block not selected; "Set a material" |
| 0060 | material_clear | MINOR | Links hidden in tree, still seen |
| 0062 | insp_run | GOOD | Map, legend, Shift check selected |
| 0063 | insp_read | MINOR | Points count, not worst values |
| 0064 | insp_list | GOOD | "1 inspections" |
| 0065 | insp_faces | MINOR | Cut-off explanation |
| 0066 | insp_update | MINOR | Shift check not selected, property empty |
| 0069 | insp_export | MINOR | No file name |
| 0070 | scad_status | MINOR | Long caption cut off |
| 0071 | scad_export | MINOR | Bench stays Inspection |
| 0072 | scad_import | MINOR | "wrote Block.csg" for an import |
| 0074 | scad_op | GOOD | Wrap selected, framed, volume |
| 0077 | scad_tidy | GOOD | Color code ringed, colours changed |
| 0081 | robot_new | MINOR | Base→tool line marked; 7.6 m view; no arm |
| 0082 | robot_move | MINOR | Line moved; ring on "Move to Home" (wrong) |
| 0087 | robot_path | MINOR | Path a tiny line in a 10.8 m view |
| 0088 | robot_run | MINOR | "7582 mm off"; nothing new to see |
| 0092 | robot_tool | BAD | Pin not shown at the tool point |
| 0096 | export | MINOR | Robot bench stays; Block not shown |
| 0097 | import_file | MINOR | Import selected; Robot bench stays |
| 0103 | doc_save_all | GOOD | Words good, Ball kept |
| 0105 | doc_merge | MINOR | Ball001 exactly on Ball |
| 0108 | object_delete | GOOD | Ball gone, words good |
| 0110 | doc_open | MINOR | Second copy CoreDoc1; top view; nothing selected |

Round-4 problems:

| Round-4 problem | Status | Pictures |
|---|---|---|
| Leftover BOM task dialog | FIXED | none in 0001-0110 |
| Robot shows nothing | PARTLY | 0081, 0082: an orange line base → tool point with end dots. 0087, 0088: the trajectory is a tiny orange line at 9 m, waypoints not told apart. 0092: tool (Pin) not drawn. No labels say "base" / "tool point". |
| Robot task box narrows the 3D view | WORSE (was FIXED) | 0082-0096: TaskRobot6Axis / TaskRobotControl / Robot Tools panel (Robot bench watcher on a selected robot) is back; 3D view ends at 920 px. 0087 "Trajectory Tools". |
| Workbench does not follow the tool | NOT FIXED | 0071 Inspection; 0096, 0097 Robot |
| object_appearance | PARTLY | 0032: Block now selected and see-through, property holds #3366cc / 30, but the green selection hides the blue and the red Face6. From 0034 on Block lies under the opaque "Block moved"; only the links show blue. 0110 (CoreDoc1, top view) proves the red tops were saved. |
| Read captions without the value | NOT FIXED | 0052 volume not mass, 0063 no worst values, 0069 no file |
| Cut-off captions | NOT FIXED | 0054, 0065, 0070 |
| section / doc_graph show nothing | NOT FIXED | 0048, 0031 |
| doc_info says "Renamed" | NOT FIXED | 0030 |
| doc_open opens a second copy | NOT FIXED | 0110 |
| Kept "20.00 mm" label in later views | NOT FIXED | 0048-0110 |

New in Core:
- shape_query (0038) and measure (0041) no longer show the lit faces (round 4 GOOD). Block is buried under "Block moved" (0.5 mm shift, opaque). The cover test does not run for reads, or does not see a body that is nearly the same box. **WORSE**.
- 0082 rings "Move to Home" on the toolbar and in the task panel for a move to given axes.
- 0005 caption "Read Block" gives none of the asked values.
- 0055 caption "Set a material" names neither body nor material.

## Special checks

- BOM: task dialog does not stay; BOM sheet shows (asm 055). FIXED.
- Robot marks: base and tool point marked as an orange line with end dots (0081, 0082, 0092); trajectory marked only as a tiny line far away (0087, 0088); tool shape not drawn (0092). PARTLY.
- Captions with values: asm all have values or results. Part/Points now add a value to most tool-name captions, but the "Part xxx on Name" / "Points xxx on Name" form stays (about 23 pictures). Core still lacks values in 0005, 0021, 0023, 0025, 0034, 0052, 0055, 0063, 0069.
- Framing: meshobj_from_shape FIXED (0081); points_mesh FIXED (0021); points_merge FIXED (0027); points_structure framed, grid not seen apart (0028); part_datum NOT FIXED (0068).
- object_appearance: PARTLY (see table).

## Top problems left (what the echo should do)

1. object_appearance (core 0032): do not select the object (selection green hides the new colour); keep its covers see-through until the next change, and name colour and object in the words.
2. Reads on a covered body (core 0038, 0041): run the cover test for reads too, and count a body as a cover when its box nearly equals the target's.
3. Robot: label the base and tool point, draw the Tool Shape at the tool point (0092), frame the path with the robot (0087), and hide or collapse the Robot task watcher, or accept it as FreeCAD's normal look. Map robot_move to no button.
4. compound_explode traceback (part 0030) and the new AttachEngine3D red lines (part 0080): find which object fails (report_read after the call).
5. Words: add phrases for the part_ / points_ tools (no "Part xxx on" form); part_from_mesh needs a caption (0082); measure_mass in grams; doc_info "Set comment and company"; scad_import "imported".
6. Workbench should follow export / import_file / scad_export (core 0071, 0096, 0097). part_datum should frame the datum (0068). Joint rows and query faces still not lit (asm 035, 038, 050, part 0033).

## Proven live

PROVEN_LIVE asm: part_primitive, part_boolean, part_transform, asm_new, asm_ground, asm_joint, asm_limits, asm_pose, asm_sweep, asm_motion, asm_list, asm_check, asm_fits, asm_bom, asm_explode, asm_export, asm_add, asm_joint_remove, asm_new_part, asm_sub
NOT_PROVEN asm: shape_query (faces not lit)
PROVEN_LIVE part: part_primitive, object_set, body_check, part_boolean, part_transform, part_wire, part_section, part_slices, part_compound, compound_filter, part_fillet, part_extrude, part_chamfer, part_refine, part_thickness, part_offset, part_revolve, part_sweep, part_loft, part_face, part_offset2d, part_ruled, part_project, part_extract, part_fix, part_attach, meshobj_from_shape, part_from_mesh, part_join, part_container, export, part_import_curves
NOT_PROVEN part: part_split (old selection kept, halves not selected), compound_explode (traceback), shape_query (face not lit), part_defeature (removed face not seen), part_datum (whole-document fit, datum faint)
PROVEN_LIVE pts: part_primitive, points_sample, points_info, points_export, points_import, points_crop, points_fit, points_mesh, points_merge
NOT_PROVEN pts: points_structure (grid not seen apart from the clouds)
PROVEN_LIVE core: part_primitive, object_list, object_get, object_set, units_convert, object_rename, object_group, link_make, link_edit, object_duplicate, object_align, text_document, doc_info, object_freeze, recompute, measure, measure_keep, clearance, measure_mass, material_list, material_get, material_set, material_clear, insp_run, insp_read, insp_list, insp_faces, insp_update, insp_export, scad_status, scad_export, scad_import, scad_op, scad_tidy, robot_new, robot_move, robot_path, robot_run, export, import_file, doc_save_all, doc_merge, object_delete, doc_open
NOT_PROVEN core: object_appearance (colour hidden by selection, then covered), robot_tool (tool shape not drawn), shape_query (face not seen under cover), section (no cut drawn), doc_graph (no graph or count)

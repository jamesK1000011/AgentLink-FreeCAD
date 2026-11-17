# Window review, round 3 (after echo round 3 and famfix): TechDraw, CAM, FEM

Pictures: `pics3/td` (28), `pics3/cam` (17), `pics3/fem` (11). Only the pictures in `pictures.json` count.
I looked at all 56 pictures at full size. I also made enlarged crops of every toolbar row (all three
families) and of the drawing area of td 036, 037, 038, 046, 047, 048 and 052.
Compared with: `docs/hardening/window-td-cam-findings.md`, the FEM section of
`docs/hardening/window-draft-surf-fem-mesh-findings.md`, and the claims in `docs/hardening/famfix-findings.md`.
No code was read. No other file was changed. No Mac tools.

Limits: one frame per call, no motion. The Report view shows only its last lines, so an error that
scrolled away cannot be seen.

## Short answers to the round-3 questions

| family | pictures | ring visible | caption visible | result selected (changing calls) | Sketcher edit toolbars |
|---|---|---|---|---|---|
| TechDraw | 28 | 8 | 28 (27 on the view, 019 only in the status bar) | 13 of 22 | no sketch in edit (correct) |
| CAM | 17 | 10 | 17 | 8 of 11 (032 is a removal) | no sketch in edit (correct) |
| FEM | 11 | 6 (one on an empty toolbar spot) | 11 (one stale) | 5 of 10 (3 of them the whole Box) | no sketch in edit (correct) |

- Ring, TechDraw: 004 New Page, 020 Part Primitives (not the Box button), 026 Boolean, 029 and 030
  Insert View, 031 Dimension, 039 Section, 041 Detail. No ring for the annotation calls that have a
  button (dimset, dim_special, centermarks, datum, gdt, balloon, leader, finish, weld, cosmetic).
  036 and 037 drop the ring of 031 even though they are changing calls.
- Ring, CAM: 001, 003 (general Boolean, not Cut), 006 Job, 008 Profile (kept on 012, 013, 014),
  017 Drill, 020 Dressup, 021 Job. None from 022 on.
- Ring, FEM: 000, 003 Analysis, 005 Fixed, 030 and 033 Force (033 is gravity: the self-weight button
  should ring), 034 on an empty spot at the right end of the FEM toolbar.
- Caption: in every picture, with the same words in the status bar. Many are only the tool name
  ("TechDraw datum", "TechDraw gdt", "CAM setup", "CAM tool", "FEM refine", "FEM parts").

---

## 1. TechDraw (28 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 000-doc_open | doc_open | MINOR | Page001 shown, caption names the file; FEM workbench left from the run before; tutorial title block text oversized (file); orange load warnings. |
| 002-td_list | td_list | MINOR | The asked page "Page" is now in front, caption right; Dimension002 has a red mark in the tree. |
| 004-td_page | td_page | MINOR | Tut A4 shown, selected, New Page ringed; title block says Scale 1:1 (page scale 2.00); new red "Shape index 29 out of bound 0" exception in Report view. |
| 011-td_title | td_title | MINOR | Page selected, caption right; the title block looks the same as in 004, nothing to see. |
| 013-td_note | td_note | MINOR | Note on the page, but large and over the title block; the note is not selected (page in panel). |
| 019-td_export | td_export | MINOR | Tut A4 (the exported page) in front; no traceback; Tut ANSIB still selected in tree and panel; caption only in status bar. |
| 020-part_primitive | part_primitive | GOOD | 3D view back, Part wb, Plate selected and framed. |
| 026-part_boolean | part_boolean | GOOD | 3D view, Union ringed, fused Slot selected, Plate see-through. |
| 029-td_view | td_view | GOOD | Plate drawing page in front, Insert View ringed, PlateTop in panel; tree not scrolled to the new page. |
| 030-td_geometry | td_geometry | MINOR | Read; ring kept; found circles not marked; caption is tool name. |
| 031-td_dim | td_dim | MINOR | Ø6 on the right hole, Dimension ringed; dimension not selected (PlateTop in panel). |
| 036-td_dimset | td_dimset | MINOR | Chain drawn; "30" labels on top of each other at the centre and touching R3; caption tool name; no ring. |
| 037-td_dim_special | td_dim_special | MINOR | Arc-length label lands on the Ø10 hole over other text; caption tool name. |
| 038-td_centermarks | td_centermarks | MINOR | Small crosses now at the two slot-end centres; at the Ø10 and Ø6 holes no cross can be seen (dimension lines cross there); nothing selected. |
| 039-td_section | td_section | GOOD | Section line A-A through the middle, section view below, Section ringed and selected. No "Section A-A" label. |
| 040-td_section_position | td_section_position | MINOR | No visible change; panel empty; caption tool name. |
| 041-td_detail | td_detail | GOOD | Detail circle B on the Ø6 hole (45,30) and the detail view; Detail ringed and selected. No label under the view. |
| 042-td_datum | td_datum | MINOR | Datum A now on the BOTTOM edge (right); not selected (Detail B in panel); no ring; caption tool name. |
| 043-td_gdt | td_gdt | MINOR | Position frame drawn and selected, but on top of the Ø6 leader and the detail circle. |
| 045-td_balloon | td_balloon | MINOR | Balloon 1 now at the top-right corner of PlateTop (right) and selected green; panel still Frame; no ring. |
| 046-td_leader | td_leader | MINOR | Leader now starts at the top-left corner (right); the text "Break sharp edges" floats above the plate, not at the leader end. |
| 047-td_finish | td_finish | MINOR | Leader on the left edge (right); the Ra 1.6 symbol sits far away, under the Ø10 H7 text. |
| 048-td_weld | td_weld | MINOR | Leader from the bottom-right corner (right) and a fillet triangle with an all-around circle; no reference line and no size "3" seen. |
| 049-shape_query | shape_query | MINOR | Caption gives the answer (1 face); the drawing stays in front, the face is not shown in 3D. |
| 052-td_cosmetic | td_cosmetic | MINOR | Line now bottom-left to top-right (right); centre circle right; thread cannot be seen; "Agent Link" property group shows on PlateTop. |
| 053-td_lines | td_lines | MINOR | No visible change (3 mm); "Agent Link" properties in panel; caption tool name. |
| 058-sheet_new | sheet_new | GOOD | Spreadsheet "Parts" opened and in front, selected, caption right. |
| 061-td_view_more | td_view_more | MINOR | Lock not visible; panel shows "Parts" (stale), not PlateTop; empty table on the page from an earlier call. |

**Counts (TechDraw):** GOOD 6 / MINOR 22 / BAD 0 (old: GOOD 0 / MINOR 17 / BAD 11).

### TechDraw: old problems against round 3

| Old problem | Now | Pictures |
|---|---|---|
| Datum on the wrong edge | FIXED: bottom edge | 042 |
| Leader starts at the wrong corner | FIXED for the anchor (top-left); text still not at the leader end, so PARTLY overall | 046 |
| Weld leader on the wrong corner | FIXED: bottom-right | 048 |
| Weld symbol not drawn | PARTLY: triangle and all-around circle drawn; no reference line, no size text | 048 |
| Cosmetic line upside down | FIXED: bottom-left to top-right | 052 |
| Thread not visible | NOT FIXED (cannot be seen) | 052 |
| Balloon on the Detail view | FIXED: on PlateTop's top-right corner (046 panel: Source View PlateTop, Origin 30 / 20) | 045, 046 |
| Centre marks not drawn | PARTLY: crosses at the slot ends; none visible at the two holes | 038 |
| Wrong page in front for td_list / td_export | FIXED | 002, 019 |
| Drawing left in front for part_ / shape_ / sheet_ calls | FIXED for part_primitive, part_boolean, sheet_new; NOT FIXED for shape_query | 020, 026, 058; 049 |
| Bounding-box FloatingPointError in Report view | FIXED: gone in every picture | 019-061 |
| "Shape index 29 out of bound 0" exception and red mark on Dimension002 | NOT FIXED (exception now first seen at 004) | 002-061 |
| Text and symbols on top of each other | NOT FIXED | 036, 037, 043, 046, 047 |
| Property panel stale | PARTLY: new annotations selected in 043, 045-048; still stale in 042, 045, 061 | |
| "Agent Link" properties on PlateTop | NOT FIXED | 052, 053 |
| Title block scale 1:1 on a scale 2 page | NOT FIXED | 004 |
| td_view_more | WORSE: old picture showed Lock Position = Yes; now the panel shows the spreadsheet | 061 |

### TechDraw problems still open (echo or tool)
1. Annotation calls have no ring and only the tool name as caption (036-053). Ring the matching
   TechDraw button and say what was added and where ("Datum A on the bottom edge of PlateTop").
2. Overlap (036, 037, 043, 046, 047): text lands on other items; leader text and finish symbol are
   far from their leader ends. The tool should place the text at the leader end and offset from
   existing items; the echo should zoom to the new item.
3. Weld symbol incomplete (048): add the reference line and the size text; check it after a zoom.
4. Centre marks (038): confirm the crosses at hole centres (zoomed snapshot); they may be hidden
   under dimension lines.
5. shape_query (049): switch to the 3D view and highlight the found face, as part_ calls now do.
6. Old exception and red Dimension002 (004 on): clear or scroll the Report view to the call's lines.
7. td_view_more (061): select the view and show the changed property.

### TechDraw tools proven live in the window (GOOD or MINOR, result shown correctly)
doc_open, td_list, td_page, td_note, part_primitive, part_boolean, td_view, td_dim, td_dimset,
td_dim_special, td_section, td_detail, td_datum, td_gdt, td_balloon, td_leader (anchor), td_finish
(leader), td_weld (partly), td_cosmetic, td_centermarks (partly), sheet_new.
Not proven (nothing to see): td_title, td_export, td_geometry, td_section_position, shape_query,
td_lines, td_view_more.

---

## 2. CAM (17 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-part_primitive | part_primitive | GOOD | Part wb, Block selected and framed; old BIM DiffuseColor tracebacks still in Report view. |
| 003-part_boolean | part_boolean | GOOD | Pocket cut seen, Block selected; ring on the general Boolean button, not Cut. |
| 006-cam_job | cam_job | MINOR | CAM wb, Job ringed, caption right; Block selected, not the job; job, Model, Tools greyed. |
| 008-cam_op | cam_op | BAD | No profile toolpath drawn; Block opaque grey; Profile only in the panel (Operations closed). |
| 012-cam_list | cam_list | MINOR | Read; EdgeWalker traceback in Report view; still no toolpaths; caption "Listed CAM". |
| 013-cam_sim | cam_sim | MINOR | Caption now gives the result (material left on 75%, up to 9.0 mm); no picture or path. |
| 014-cam_post | cam_post | MINOR | "done postprocessing"; caption is advice, no file name (walkthrough.nc) or size. |
| 017-cam_tool_add | cam_tool_add | MINOR | Tools folder open, Drill 5 selected, Drill ringed; camera moved so the part is cut off at the right. |
| 020-cam_dressup | cam_dressup | BAD | No tags and no path on screen; DressupTag in panel (Base Profile), Dressup ringed. |
| 021-cam_setup | cam_setup | MINOR | Nothing seen or selected; caption "CAM setup"; Path.Area warning. |
| 022-cam_edit | cam_edit | MINOR | "Optional stop" selected (panel); not shown; caption "Edited CAM". |
| 026-cam_library | cam_library | MINOR | Caption names walkthrough-tools.json (new); panel stale (Drill001). |
| 027-cam_tool | cam_tool | MINOR | Feed change not shown; nothing selected; caption "CAM tool". |
| 028-cam_path | cam_path | MINOR | "Hard stop" (Mandatory) selected now; not shown; no ring. |
| 030-cam_property_bag | cam_property_bag | GOOD | "Limits" selected, Max Depth 8 mm, Passes 3 in panel; caption names it. |
| 031-cam_template_export | cam_template_export | MINOR | Long caption cut off before the file name; panel stale (Limits). |
| 032-cam_remove | cam_remove | MINOR | Caption right; Operations closed, so the removal cannot be seen. |

**Counts (CAM):** GOOD 3 / MINOR 12 / BAD 2 (old: GOOD 0 / MINOR 14 / BAD 3).

### CAM: old problems against round 3

| Old problem | Now | Pictures |
|---|---|---|
| No toolpaths drawn | NOT FIXED: no green lines in any picture; Block stays opaque (not see-through), stock only an outline | 008-032 |
| cam_sim shows nothing | PARTLY: the caption gives the result; nothing drawn | 013 |
| EdgeWalker traceback | NOT FIXED: still in Report view | 012-020 |
| Job tree closed, new children not seen | PARTLY: Tools opened and Drill 5 selected (017); Operations never opened | 008-032 |
| Profile / Limits at document root | Cannot judge: tree root below Tools not visible | 020, 030 |
| File results not named | FIXED for cam_library (026); NOT FIXED for cam_post (014); PARTLY for cam_template_export (031, cut off) | |
| Stale BIM tracebacks in Report view | NOT FIXED | 001-008 |
| Property panel stale | MOSTLY FIXED: DressupTag, Optional stop, Hard stop, Limits shown; 021, 027 empty | 020-030 |
| New: camera moved to the tool, part cut off | NEW | 017 |

### CAM problems still open
1. No toolpath in any picture. After cam_op / cam_dressup / cam_path the echo must make the op
   visible, make Block and Stock see-through, open Operations, select the op and fit to the path.
   The famfix probe (hide Stock and Block, snapshot) has to be run to settle whether the path draws.
2. Name the output file and size in the caption for cam_post and cam_template_export (keep the
   file name in the first 60 characters so it is not cut off).
3. Give real captions for cam_setup, cam_tool, cam_edit (what changed, to what value).
4. Clear or scroll the Report view per call (BIM and EdgeWalker tracebacks).

### CAM tools proven live in the window
part_primitive, part_boolean, cam_job, cam_tool_add, cam_edit (object made), cam_path (Hard stop),
cam_property_bag, cam_library (file named), cam_sim (result in caption only).
Not proven: cam_op, cam_dressup (BAD), cam_list, cam_post, cam_setup, cam_tool,
cam_template_export, cam_remove.

---

## 3. FEM (11 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 000-part_primitive | part_primitive | GOOD | Part wb, 8 m Box selected and framed; old "Reading failed" lines in Report view. |
| 001-material_set | material_set | MINOR | Material wb; caption "Set a material" without the name; no colour, no object, no ring. |
| 003-fea_setup | fea_setup | MINOR | FEM wb, Analysis button ringed, caption "Set up a strength check of Box"; tree only Box (by design: no FEM objects). |
| 005-fea_hold | fea_hold | BAD | Fixed ringed and "Held faces still", but no mark on the x=0 face and the face is not highlighted. |
| 030-fea_modes | fea_modes | MINOR | No traceback; analysis "Box native" active in the tree with Fixed (red plate) and Force arrows drawn; no mode shape or frequency; caption "FEM modes: box". |
| 033-fea_load | fea_load | BAD | Gravity asked; no gravity shown; caption "Put a load on faces" (wrong); Force button ringed, not self-weight. |
| 034-fea_solve | fea_solve | BAD | No colour map, no deformed shape, no result object; ring on an empty toolbar spot; caption gives no figure. |
| 038-fea_refine | fea_refine | MINOR | Clear call, nothing to see; caption "FEM refine". |
| 039-fea_shell | fea_shell | BAD | Caption still "FEM refine" (stale); no shell, holds, pressure or mesh; nothing selected. |
| 041-fea_parts | fea_parts | MINOR | Block selected at the beam end; hidden "FEA parts" added; tie not shown; caption tool name. |
| 042-fea_clear | fea_clear | MINOR | Caption "Cleared FEM"; "FEA parts" stays; "Box native" analysis and its symbols stay. |

**Counts (FEM):** GOOD 1 / MINOR 6 / BAD 4 (old: GOOD 1 / MINOR 3 / BAD 7).

### FEM: old problems against round 3

| Old problem | Now | Pictures |
|---|---|---|
| "Cannot add static property" traceback | FIXED: gone; Report view shows CalculiX input written and solver run | 030-042 |
| No analysis in the tree | PARTLY: fea_native's "Box native" analysis is in the tree (active) with Fixed and Force drawn from 030 on; fea_setup, fea_hold, fea_load still make nothing (by design, famfix item 2); fea_solve's "Box strength (fea_solve)" not seen | 003, 005, 030-042 |
| No result shown (modes, solve) | NOT FIXED | 030, 034 |
| Holds and loads not drawn for fea_hold / fea_load / fea_shell | NOT FIXED | 005, 033, 039 |
| material_set shows nothing | NOT FIXED | 001 |
| fea_clear leaves "FEA parts" | NOT FIXED; the native analysis also stays | 042 |
| New: stale caption | NEW: 039 shows 038's caption | 039 |
| New: wrong caption / ring for gravity | NEW | 033 |
| New: ring on an empty toolbar spot | NEW | 034 |

### FEM problems still open
1. No result is ever shown. After fea_solve / fea_modes show the result (colour map with legend,
   deformed shape, mode 1 with its frequency in the caption) or open the result PNG; put the max
   stress or the first frequency in the caption.
2. fea_solve's FEM route result is not in the tree (034): check `solvedBy` (route or own deck).
3. fea_hold, fea_load, fea_shell: draw the hold and load (temporary marks on the faces) and highlight
   the face named in the arguments; for gravity ring the self-weight button and say "gravity".
4. Captions: 039 is stale and 033 is wrong; many are only the tool name.
5. fea_clear: remove "FEA parts" or say in the caption that it stays and why.

### FEM tools proven live in the window
part_primitive, fea_parts (Block placed and selected), fea_clear (partly), fea_modes (solver ran
without the traceback, but no result shown: run proven, result not).
Not proven: material_set, fea_setup, fea_hold, fea_load, fea_solve, fea_refine, fea_shell.

---

## Top problems across the three families
1. CAM toolpaths still never drawn (008-032); covering Block not see-through.
2. FEM results, holds and loads never drawn (005, 030, 033, 034, 039); 039 stale caption.
3. TechDraw annotations: no ring, tool-name captions, text and symbols overlap (036-053).
4. TechDraw weld symbol and centre marks only partly drawn (038, 048); leader text away from leader (046).
5. Old errors stay in the Report view (TechDraw "Shape index 29", CAM EdgeWalker and BIM tracebacks).

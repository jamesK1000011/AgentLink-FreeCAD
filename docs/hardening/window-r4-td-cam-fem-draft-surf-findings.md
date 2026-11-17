# Window review, round 4: TechDraw, CAM, FEM, Draft, Surface

FreeCAD 1.1.3 with Agent Link, after echo round 4. Pictures: `pics4/td` (28), `pics4/cam` (17), `pics4/fem` (11),
`pics4/draft` (20), `pics4/surf` (15). Total 91. I looked at every picture at full size. I also enlarged the
drawing area of td 038, 046, 047, 048, 061, the right end of the toolbar in td 048 and fem 034, and the 3D view
of cam 020.
Compared with: `docs/hardening/window-r3-td-cam-fem-findings.md`, the Draft and Surface sections of
`docs/hardening/window-r3-draft-surf-ws-tex-tutor-findings.md`, and the claims in `round4-findings.md`.
No code read, no other file changed, no Mac tools.

Rating rule (same as round 3): GOOD = result shown right, only known general problems. MINOR = result shows, small
family problem. BAD = result cannot be seen, wrong or stale result, or new error text.

## Summary

| family | round 3 G / M / B | round 4 G / M / B | ring on real button | ring on "»" | caption | result selected |
|---|---|---|---|---|---|---|
| TechDraw | 6 / 22 / 0 | 8 / 18 / 2 | 21 of 28 | 4 | 28 (2 only in status bar) | 18 of 23 changing calls |
| CAM | 3 / 12 / 2 | 4 / 11 / 2 | 12 of 17 | 0 | 17 | 9 of 13 changing calls |
| FEM | 1 / 6 / 4 | 2 / 6 / 3 | 9 of 11 | 1 | 11 (1 stale) | 3 of 10 changing calls |
| Draft | 11 / 7 / 2 | 16 / 3 / 1 | 17 of 20 | 0 | 20 | 19 of 20 |
| Surface | 10 / 3 / 2 | 10 / 5 / 0 | 10 of 15 | 0 | 15 | 15 of 15 |
| **all** | 31 / 50 / 10 | **40 / 43 / 8** | | | | |

No picture has a sketch in edit, so the Sketcher edit toolbars are not tested here.

---

## 1. TechDraw (28)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 000-doc_open | doc_open | MINOR | BIM workbench left; stale BIM properties; title text oversized (file). |
| 002-td_list | td_list | MINOR | Right page; caption only in status bar; red Dimension002. |
| 004-td_page | td_page | MINOR | Page shown, ringed; caption "8 cleared"; title says 1:1. |
| 011-td_title | td_title | MINOR | No visible change; ring on Redraw-like button, not sure. |
| 013-td_note | td_note | MINOR | Note selected, ringed; text over title block, past frame. |
| 019-td_export | td_export | MINOR | Ring on an annotation button, not export; panel Tut ANSIB. |
| 020-part_primitive | part_primitive | GOOD | 3D view back, Plate selected, Box ringed. |
| 026-part_boolean | part_boolean | GOOD | Fused Slot selected, Fuse ringed, Plate see-through. |
| 029-td_view | td_view | GOOD | PlateTop on new page, Insert View ringed, selected. |
| 030-td_geometry | td_geometry | MINOR | Good caption; found circles not marked on the page. |
| 031-td_dim | td_dim | MINOR | Ø6 drawn, ringed; dimension not selected; generic caption. |
| 036-td_dimset | td_dimset | MINOR | Chain drawn; "30" and "R3" labels overlap. |
| 037-td_dim_special | td_dim_special | MINOR | Arc-length label sits on the Ø10 hole text. |
| 038-td_centermarks | td_centermarks | MINOR | Ringed; crosses at slot ends only, none seen at holes. |
| 039-td_section | td_section | GOOD | Line A-A and section view, ringed and selected. |
| 040-td_section_position | td_section_position | MINOR | Good caption; no visible change; panel empty. |
| 041-td_detail | td_detail | GOOD | Detail circle B and view, ringed and selected. |
| 042-td_datum | td_datum | GOOD | Datum A on bottom edge, selected, ringed, good caption. |
| 043-td_gdt | td_gdt | MINOR | Frame selected; lies on Ø10 leader and detail circle. |
| 045-td_balloon | td_balloon | GOOD | Balloon 1 at top-right corner, selected, ringed. |
| 046-td_leader | td_leader | MINOR | Text floats above plate, not at leader end; tool-name caption. |
| 047-td_finish | td_finish | MINOR | Ra 1.6 symbol far from its leader; ring on "»". |
| 048-td_weld | td_weld | MINOR | Reference line now drawn; size "3" not seen; ring on "»". |
| 049-shape_query | shape_query | MINOR | 3D view now shown; found face not highlighted. |
| 052-td_cosmetic | td_cosmetic | BAD | 3D view left in front; drawing not shown; tool-name caption. |
| 053-td_lines | td_lines | BAD | 3D view left in front; changed lines cannot be seen. |
| 058-sheet_new | sheet_new | GOOD | Spreadsheet Parts open, ringed, selected. |
| 061-td_view_more | td_view_more | MINOR | PlateTop selected, Lock Position = Yes; caption tool-name-like. |

Counts: GOOD 8 / MINOR 18 / BAD 2 (round 3: 6 / 22 / 0).

Ring on the real button: 21 (004, 013, 020, 026, 029, 030 kept, 031, 036, 037, 038, 039, 040, 041, 042, 043, 045,
046, 053, 058, 061, and 011 if the third page button is right). On the "»" of the toolbar: 047, 048, 049 (kept),
052 (kept). Wrong button: 019. None: 000, 002.
Caption: 28; 002 and 019 only in the status bar.
Result selected: 18 of 23 changing calls (not 031, 036, 037, 040, and 052/053 show the 3D view).

### TechDraw: round-3 problems now

| Round-3 problem | Round 4 | Pictures |
|---|---|---|
| Annotation calls: no ring | FIXED: dimset, dim_special, centermarks, datum, gdt, balloon, leader, lines ring; finish and weld ring the "»" | 036-053 |
| Captions only the tool name | PARTLY: dimset, dim_special, datum, gdt, balloon, lines, section_position, geometry fixed; leader, finish, cosmetic, centermarks, view_more still tool name | 038, 046, 047, 052, 061 |
| Text and symbols overlap | NOT FIXED | 036, 037, 043, 046, 047 |
| Leader text away from leader end | NOT FIXED | 046 |
| Finish symbol away from leader | NOT FIXED | 047 |
| Weld: no reference line, no size | PARTLY: reference line now drawn under the triangle; no "3" | 048 |
| Centre marks only at slot ends | NOT FIXED (no cross seen at Ø10 or Ø6, also in 061) | 038, 061 |
| shape_query leaves the drawing in front | FIXED: 3D view shown; face still not highlighted | 049 |
| "Shape index 29 out of bound 0" and red Dimension002 | NOT FIXED (claimed to be the tutorial file's own) | 002-061 |
| Title block 1:1 on a scale 2 page | NOT FIXED | 004 |
| "Agent Link" property group on PlateTop | NOT FIXED | 038, 052, 053, 061 |
| Thread / cosmetic items not visible | WORSE in 052 (no page shown); 061 shows the centre circle and a thin circle, no diagonal line | 052, 061 |
| td_view_more showed the spreadsheet | FIXED: PlateTop selected, Lock Position Yes | 061 |
| Wrong workbench after doc_open | NOT FIXED (BIM now, FEM in round 3) | 000 |

### TechDraw: new problems
1. **3D view left in front for drawing calls (052, 053)**. After shape_query (049) brings the 3D view back, the
   next td_ calls do not bring the drawing page back. The echo should show the page of the `view` for every td_
   call, as it does for 029-048.
2. **Ring on the toolbar's "»" (047, 048, 049, 052)**. This is the new overflow rule; the person cannot see which
   command it means. Better: widen or move the TechDraw annotation toolbar so Surface Finish and Weld Symbol are on
   screen, or name the button in the caption.
3. td_export (019) rings an annotation button, not the export button (SVG/DXF/PDF at the right).
4. td_page caption "Made a drawing page Tut A4: 8 cleared": "8 cleared" means nothing to a person.

### What the TechDraw echo should do
- Every td_ call: drawing page of the view in front; zoom to the new item; select it (031, 036, 037 not selected).
- Place labels in free space (tool): 036, 037, 043, 046, 047. Put leader text and Ra symbol at the leader end.
- Weld size text "3" on the reference line; check with a zoomed snapshot.
- Centre marks: confirm by a zoomed snapshot whether crosses exist at the holes.

---

## 2. CAM (17)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-part_primitive | part_primitive | GOOD | Block selected, Box ringed, Report view clean. |
| 003-part_boolean | part_boolean | GOOD | Pocket cut seen; Cut button ringed now (fixed). |
| 006-cam_job | cam_job | MINOR | Job ringed, good caption; Block selected, not the job. |
| 008-cam_op | cam_op | BAD | No profile toolpath drawn; Profile only in panel. |
| 012-cam_list | cam_list | MINOR | "2 ops" caption; EdgeWalker traceback; no toolpaths. |
| 013-cam_sim | cam_sim | MINOR | Caption "clear" says little; nothing drawn. |
| 014-cam_post | cam_post | MINOR | "153 lines" caption; still no file name. |
| 017-cam_tool_add | cam_tool_add | MINOR | Drill 5 ringed; camera cuts part; four rows selected. |
| 020-cam_dressup | cam_dressup | BAD | No tags, no path; tool-name caption. |
| 021-cam_setup | cam_setup | MINOR | Good caption (safe height 5 mm); nothing selected; new Path.Area warning. |
| 022-cam_edit | cam_edit | MINOR | "Optional stop" selected, ringed; leftover green tree row. |
| 026-cam_library | cam_library | MINOR | File named; panel stale (Drill001). |
| 027-cam_tool | cam_tool | MINOR | Good caption (feed 150 mm/min); nothing selected, no ring. |
| 028-cam_path | cam_path | MINOR | Hard stop selected; no ring; tool-name caption. |
| 030-cam_property_bag | cam_property_bag | GOOD | Limits selected with Max Depth 8, Passes 3. |
| 031-cam_template_export | cam_template_export | GOOD | Caption names job_Walkthrough.json; job selected. |
| 032-cam_remove | cam_remove | MINOR | "2 removed"; Operations closed, change not seen. |

Counts: GOOD 4 / MINOR 11 / BAD 2 (round 3: 3 / 12 / 2).

Ring on the real button: 12 (001, 003, 006, 008, 012 and 013 and 014 kept, 017, 020, 021, 022, 026 kept). None from
027 to 032. Caption: 17. Result selected: 9 of 13 changing calls (not 006, 021, 027, 032).

### CAM: round-3 problems now

| Round-3 problem | Round 4 | Pictures |
|---|---|---|
| No toolpaths drawn | NOT FIXED: no green line in any picture (cam_shown claimed, "not seen"). The original Block is now hidden (grey row) and the stock is a dark outline, but the clone is opaque and shows no path | 008-032 |
| cam_sim shows nothing | NOT FIXED; caption now less clear ("clear") than round 3 ("75 % left, up to 9 mm") | 013 |
| EdgeWalker traceback in Report view | NOT FIXED | 012-022 |
| Operations folder never opened | NOT FIXED | 008-032 |
| cam_post file not named | NOT FIXED (line count given) | 014 |
| cam_template_export name cut off | FIXED | 031 |
| Captions for cam_setup, cam_tool, cam_edit | FIXED | 021, 022, 027 |
| Camera moved, part cut off | NOT FIXED | 017 |
| Stale BIM tracebacks | FIXED: Report view clean until the CAM calls | 001-008 |
| Ring on general Boolean, not Cut | FIXED | 003 |

### CAM: new problems
1. Leftover green-highlighted tree row (a child of "Vee 60 bit") stays from 020 to 032.
2. cam_tool_add (017) selects four rows (Drill 5, bit body, Revolution001, Attributes003).
3. New `<Path.Area> Sort mode 'None'` warning from 021 on.

### What the CAM echo should do
- Probe first: after cam_op, read `session_state` `echo.camShown` and the op's `Path` command count. If the path is
  empty, the tool is at fault (EdgeWalker error on Pocket); if not, show the op, open Operations, make the clone
  see-through, fit to the path.
- cam_sim: show the simulated stock or put "material left" numbers in the caption again.
- cam_post: put the file name first in the caption.

---

## 3. FEM (11)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 000-part_primitive | part_primitive | GOOD | 8 m Box selected, Box ringed. |
| 001-material_set | material_set | MINOR | Material button now ringed; caption has no material name. |
| 003-fea_setup | fea_setup | MINOR | Analysis ringed, good caption; no FEM object (by design). |
| 005-fea_hold | fea_hold | BAD | Fixed ringed; no mark on x=0 face, face not highlighted. |
| 030-fea_modes | fea_modes | MINOR | Fixed plate and Force arrows drawn; no mode shape or frequency. |
| 033-fea_load | fea_load | MINOR | Caption "Put gravity"; self-weight ringed; gravity has no symbol. |
| 034-fea_solve | fea_solve | BAD | No colour map, no deformed shape; ring on "»". |
| 038-fea_refine | fea_refine | GOOD | Mesh-region button ringed, caption "Cleared the finer mesh areas". |
| 039-fea_shell | fea_shell | BAD | Same picture as 038: stale caption and ring; no shell shown. |
| 041-fea_parts | fea_parts | MINOR | Good caption; Block at beam end; FEA parts hidden; tie not shown. |
| 042-fea_clear | fea_clear | MINOR | Caption "Cleared FEM"; FEA parts and Box native stay. |

Counts: GOOD 2 / MINOR 6 / BAD 3 (round 3: 1 / 6 / 4).

Ring on the real button: 9 (000, 001, 003, 005, 030, 033, 038, 041, 042). On "»": 034. Stale ring: 039 (038's).
Caption: 11, but 039 is stale. Result selected: 3 of 10 changing calls (000, 034 Box, 041 FEA parts).
Result colours: none in any picture. Constraint symbols: FreeCAD's Fixed (red plate) and Force (red arrows) of the
"Box native" analysis are drawn from 030 on; nothing is drawn for fea_hold (005), gravity (033) or fea_shell (039).

### FEM: round-3 problems now

| Round-3 problem | Round 4 | Pictures |
|---|---|---|
| No result shown (colour map, mode, frequency) | NOT FIXED (fem_result_shown claimed, medium) | 030, 034 |
| fea_hold / fea_load / fea_shell not drawn | NOT FIXED by design (`window` key); gravity symbol not expected | 005, 033, 039 |
| Wrong caption and Force ring for gravity | FIXED | 033 |
| Ring on an empty toolbar spot | CHANGED: it is the "»" (overflow rule); still no visible button | 034 |
| Stale caption at fea_shell | NOT FIXED (caption and ring from 038) | 039 |
| material_set shows nothing | PARTLY: Material button ringed; no name in caption, Box not selected | 001 |
| Captions only the tool name | FIXED for fea_refine, fea_parts; "FEM modes: 3 modes" and "Cleared FEM" still short | 030, 038, 041, 042 |
| fea_clear leaves FEA parts | NOT FIXED | 042 |

### What the FEM echo should do
- fea_solve (034): colour the result (von Mises with legend) and put the max stress in the caption; select the
  result object. If the run kept no result object, open the result picture instead.
- fea_modes (030): put the first frequencies in the caption ("3 modes: 12.3, 45.6, 78.9 Hz").
- fea_shell (039): wait for the job, then show the shell, holds and pressure; caption must be fea_shell's.
- fea_hold (005): even with no FreeCAD constraint, select the held face so it shows green.
- fea_solve ring: name the button in the caption or make the FEM toolbar fit.

---

## 4. Draft (20)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-draft_plane | draft_plane | GOOD | Top plane shown green, selected, good caption. |
| 002-draft_shape | draft_shape | GOOD | Arc30 selected, Arc ringed, caption gives length. |
| 006-draft_modify | draft_modify | GOOD | One closed Wire selected; Upgrade ringed in toolbar and dock. |
| 010-draft_link_array | draft_link_array | MINOR | Ring selected, Array ringed; side copies partly under Hex. |
| 011-draft_dimension | draft_dimension | GOOD | ToHexTop selected, Dimension ringed; small in view. |
| 015-draft_style | draft_style | GOOD | Style ringed, caption "Saved the style Tutorial". |
| 023-draft_fix | draft_fix | GOOD | ToHexTop selected, ringed; caption "Fixed Draft" vague. |
| 024-draft_label | draft_label | MINOR | HexArea selected, ringed; label text too small to read. |
| 027-draft_clone | draft_clone | GOOD | HexHalf fills view, ringed, selected. |
| 060-draft_layer | draft_layer | MINOR | Layer Outline in panel now; no ring; nothing marked in view. |
| 063-draft_hatch | draft_hatch | GOOD | Hatch lines green, Hatch ringed now. |
| 065-draft_to_sketch | draft_to_sketch | GOOD | FrameSketch green outline, ringed, length caption. |
| 066-sketch_state | sketch_state | GOOD | Caption "4 degrees of freedom left". |
| 067-draft_from_sketch | draft_from_sketch | GOOD | Wire006 face selected, caption "Turned FrameSketch into Draft wires". |
| 068-part_primitive | part_primitive | GOOD | Tag box selected, Box ringed, its properties shown. |
| 069-draft_2d_view | draft_2d_view | BAD | TagTop in panel but hidden under Tag; nothing green. |
| 072-draft_facebinder | draft_facebinder | GOOD | TagSkin green, Facebinder ringed now. |
| 074-draft_fonts | draft_fonts | GOOD | Caption "205 found"; OnTag kept selected (by rule). |
| 076-draft_text | draft_text | GOOD | "AL-7" readable, Text ringed. |
| 078-draft_array | draft_array | GOOD | 2x2 plates, copies selected, Array ringed. |

Counts: GOOD 16 / MINOR 3 / BAD 1 (round 3: 11 / 7 / 2).

Ring on the real button: 17 (all but 001, 060, 074). Caption: 20. Result selected: 19 (not 015, a style has no
object).

### Draft: round-3 problems now

| Round-3 problem | Round 4 | Pictures |
|---|---|---|
| Missing rings (Upgrade, Style, Hatch, To-sketch, Facebinder) | FIXED; Layer still has none | 006, 015, 063, 065, 072; 060 |
| draft_layer not selected | PARTLY: properties of Outline shown; no ring, no mark in view; red fillet error still in Report view | 060 |
| draft_2d_view hidden under Tag | PARTLY: TagTop in panel; still not visible (Tag not see-through) | 069 |
| Upgrade made two wires | FIXED: one closed Wire | 006 |
| Copies under Hex face | NOT FIXED | 010 |
| Sketch / face on Frame | FIXED: green outline and green face are clear | 065, 067 |
| Label text too small | NOT FIXED | 024 |
| fonts / style captions | FIXED | 015, 074 |
| from_sketch caption only tool name | FIXED | 067 |
| Right dock takes 40 % of width | NOT FIXED | all Draft pictures |

### Draft: new problems
- The fit for 011 and 023 frames a large grey rectangle (Frame) and the whole sheet; the dimension text cannot be
  read. Fit to the dimension instead.
- 027: a grey sliver at the left edge of the 3D view (seen in round 3 at 074 too).

---

## 5. Surface (15)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-part_wire | part_wire | GOOD | Line La selected, length caption, ring on a Part button. |
| 005-surface_boundary | surface_boundary | GOOD | Patch green, panel Patch now, boundary button ringed. |
| 007-surface_fill | surface_fill | MINOR | Filling ringed, Filled selected; lies exactly on Patch. |
| 011-surface_sections | surface_sections | GOOD | Ruled green inside see-through Plate, Sections ringed. |
| 013-surface_extend | surface_extend | GOOD | Wider green around Plate, Extend ringed, panel Wider. |
| 016-part_primitive | part_primitive | GOOD | Block selected, Box ringed. |
| 017-surface_cut | surface_cut | MINOR | Block see-through now; Half blotchy; Block cut off; no ring. |
| 021-surface_sew | surface_sew | MINOR | Open box green; grey object cut at top-left; no ring. |
| 024-surface_thicken | surface_thicken | GOOD | Slab green, covers see-through. |
| 028-surface_blend | surface_blend | GOOD | Blend curve green, Blend curve button ringed. |
| 030-draft_shape | draft_shape | GOOD | G1 green, B-spline ringed, status length now G1's. |
| 045-surface_loft | surface_loft | GOOD | Panel framed and green, panel Panel now. |
| 047-surface_points | surface_points | GOOD | Fitted framed and green. |
| 049-meshobj_from_shape | meshobj_from_shape | MINOR | Mesh selected and ringed now; tiny in whole-document fit. |
| 050-surface_polynomial | surface_polynomial | MINOR | Framed and selected now; blotchy over Fitted; ring button unsure. |

Counts: GOOD 10 / MINOR 5 / BAD 0 (round 3: 10 / 3 / 2).

Ring on the real button: 10 (001, 005, 007, 011, 013, 016, 028, 030, 049, 050; 050's button may not match). None:
017, 021, 024, 045, 047 (tools with no Surface button). Caption: 15. Result selected: 15.

### Surface: round-3 problems now

| Round-3 problem | Round 4 | Pictures |
|---|---|---|
| No ring on any Surface tool | FIXED for boundary, fill, sections, extend, blend, polynomial | 005-050 |
| surface_fill on top of Patch | PARTLY: Filled selected and ringed; still on Patch, Patch not see-through | 007 |
| surface_cut: Block not see-through | FIXED; Half still blotchy, Block cut off at right | 017 |
| surface_polynomial too close, not selected | FIXED: framed, selected | 050 |
| meshobj_from_shape not selected | FIXED; mesh tiny | 049 |
| Property panel stale | FIXED: 005, 013, 045 show their own object | |
| Status bar length from Blend at 030 | FIXED | 030 |

### Surface: problems left
- 007: hide or see-through Patch when Filled is made on the same edges.
- 017, 050: z-fighting (blotches) where the result lies on its source; offset or hide the source.
- 049: fit to the new mesh, not the whole document.

---

## Top problems left (all five families)
1. CAM toolpaths still never drawn (cam 008-032), even after the claimed `cam_shown` fix.
2. FEM result never coloured; no frequency or max stress in captions; fea_shell picture stale (fem 030, 034, 039).
3. TechDraw drawing not shown after shape_query: td_cosmetic and td_lines show the 3D view (td 052, 053).
4. TechDraw labels overlap and sit away from their leaders; weld size and hole centre marks missing (036-048).
5. Ring on the hidden "»" toolbar button gives no clue (td 047-052, fem 034); old errors stay in Report view
   (TechDraw "Shape index 29", CAM EdgeWalker, Draft fillet error).

## Tools proven live

PROVEN_LIVE techdraw: doc_open, td_list, td_page, td_note, part_primitive, part_boolean, td_view, td_geometry, td_dim, td_dimset, td_dim_special, td_centermarks, td_section, td_detail, td_datum, td_gdt, td_balloon, td_leader, td_finish, td_weld, shape_query, sheet_new, td_view_more
NOT_PROVEN techdraw: td_title (no visible change), td_export (file not shown), td_section_position (no visible change), td_cosmetic (3D view shown, not the drawing), td_lines (3D view shown, not the drawing)
PROVEN_LIVE cam: part_primitive, part_boolean, cam_job, cam_tool_add, cam_setup, cam_edit, cam_library, cam_tool, cam_path, cam_property_bag, cam_template_export
NOT_PROVEN cam: cam_op (no toolpath), cam_dressup (no tags or path), cam_list (read, no paths), cam_sim (nothing drawn), cam_post (no file name), cam_remove (change not seen)
PROVEN_LIVE fem: part_primitive, material_set, fea_setup, fea_load, fea_refine, fea_parts, fea_clear, fea_modes (run only, no mode shown)
NOT_PROVEN fem: fea_hold (no mark), fea_solve (no result colours), fea_shell (stale picture)
PROVEN_LIVE draft: draft_plane, draft_shape, draft_modify, draft_link_array, draft_dimension, draft_style, draft_fix, draft_label, draft_clone, draft_layer, draft_hatch, draft_to_sketch, sketch_state, draft_from_sketch, part_primitive, draft_facebinder, draft_fonts, draft_text, draft_array
NOT_PROVEN draft: draft_2d_view (TagTop hidden under Tag)
PROVEN_LIVE surface: part_wire, surface_boundary, surface_fill, surface_sections, surface_extend, part_primitive, surface_cut, surface_sew, surface_thicken, surface_blend, draft_shape, surface_loft, surface_points, meshobj_from_shape, surface_polynomial
NOT_PROVEN surface: none

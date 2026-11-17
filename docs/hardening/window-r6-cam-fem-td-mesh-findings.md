# Window review, round 6: CAM, FEM, TechDraw, Mesh

FreeCAD 1.1.3 with Agent Link, after echo round 6. I looked at all 77 pictures in `pics6/cam` (17), `pics6/fem` (11),
`pics6/td` (28) and `pics6/mesh` (21). I made larger copies of cam 008, fem 034 (the 3D view and the right end of the
toolbar) and td 036.
Compared with: `docs/hardening/window-r4-td-cam-fem-draft-surf-findings.md` (CAM, FEM, TechDraw),
`docs/hardening/window-r4-core-bim-mesh-findings.md` (Mesh) and the claims in `docs/hardening/round6-findings.md`.

Rating rule (same as round 4): GOOD = the result shows correctly, with only known general problems. MINOR = the
result shows, with a small problem in this family. BAD = the result cannot be seen, or it is wrong or stale.

## Summary

| family | round 4 G / M / B | round 6 G / M / B |
|---|---|---|
| CAM | 4 / 11 / 2 | 4 / 11 / 2 |
| FEM | 2 / 6 / 3 | 3 / 7 / 1 |
| TechDraw | 8 / 18 / 2 | 8 / 20 / 0 |
| Mesh | 12 / 9 / 0 | 12 / 7 / 2 |
| **all** | 26 / 44 / 7 | **27 / 45 / 5** |

Mesh has 2 BAD because the round-6 special checks (segment and curvature colours) fail. Round 4 rated these
pictures MINOR.

Special checks:
- CAM toolpaths: **not seen in any picture.** No green line, not even in an enlarged copy of 008. This is so although
  the answers say `shown: true`. The model clone is see-through now in 008 and 017-032, but opaque again in 012-014.
- FEM result colours: **shown in 034.** A jet map on the beam is red at the fixed end and blue toward the free end.
  The caption says "max 444 MPa". fea_modes 030 gives "12.95, 12.95, 75.93 Hz". fea_shell 039 gives "max 2.688 MPa".
- td_cosmetic / td_lines show the drawing page: **yes** (052, 053).
- Mesh segments and curvature coloured: **no** (009, 012).
- Ring on "»": **none.** fem 034, td 047 and td 048 have no ring, and nothing is ringed at the "»" end.
- Leftover task dialog: **none.** The Tasks panel is empty, or it shows only the Mesh Info watcher (the expected
  FreeCAD panel in the Mesh workbench).

## 1. CAM (17)

| picture | tool | rating | reason |
|---|---|---|---|
| 001-part_primitive | part_primitive | GOOD | Block selected, Box ringed, volume caption. |
| 003-part_boolean | part_boolean | GOOD | Pocket cut seen, Cut ringed. |
| 006-cam_job | cam_job | MINOR | Job ringed; nothing selected; caption gives no job name. |
| 008-cam_op | cam_op | BAD | Clone see-through now, but no toolpath drawn. |
| 012-cam_list | cam_list | MINOR | "2 ops"; clone opaque again; EdgeWalker traceback. |
| 013-cam_sim | cam_sim | MINOR | Caption good now (8921 mm³, 75 % left); nothing drawn. |
| 014-cam_post | cam_post | MINOR | "153 lines"; file name still not given. |
| 017-cam_tool_add | cam_tool_add | MINOR | Four rows selected; camera cuts part off. |
| 020-cam_dressup | cam_dressup | BAD | No tags, no path; tool-name caption. |
| 021-cam_setup | cam_setup | MINOR | Good caption; nothing selected; Path.Area warning. |
| 022-cam_edit | cam_edit | MINOR | Optional stop in panel; tree row not seen. |
| 026-cam_library | cam_library | MINOR | File named twice; panel stale (Drill001). |
| 027-cam_tool | cam_tool | MINOR | Good caption; no ring, nothing selected. |
| 028-cam_path | cam_path | MINOR | Hard stop in panel; no ring; tool-name caption. |
| 030-cam_property_bag | cam_property_bag | GOOD | Limits, Max Depth 8, Passes 3 in panel. |
| 031-cam_template_export | cam_template_export | GOOD | Job selected; caption names job_Walkthrough.json. |
| 032-cam_remove | cam_remove | MINOR | "2 removed"; change cannot be seen. |

Counts: GOOD 4 / MINOR 11 / BAD 2 (round 4: 4 / 11 / 2).

### CAM: round-4 problems now

| round-4 problem | status | pictures |
|---|---|---|
| No toolpaths drawn | NOT FIXED. The clone is see-through now (part of the claimed change), but there is no green or 3 px line. The answers say `shown: true`, so what the answer says and what the window shows do not agree | 008-032 |
| cam_sim shows nothing / caption "clear" only | PARTLY. Caption FIXED ("clear, 8921 mm³ removed, 75 % left, up to 9 mm"); still nothing drawn | 013 |
| cam_post file not named | NOT FIXED | 014 |
| cam_tool_add selects four rows; camera cuts part | NOT FIXED | 017 |
| cam_dressup tool-name caption, no tags | NOT FIXED | 020 |
| EdgeWalker traceback in Report view | NOT FIXED (stays 012-032) | 012-032 |
| Leftover green tree row | NOT FIXED: the "Vee 60 bit" child row stays green | 020-032 |
| No ring for cam_tool, cam_path | NOT FIXED | 027, 028 |

### CAM: new problems
1. The clone is see-through in 008, opaque in 012-014 (reads), and see-through again from 017. The cover handling
   is not the same for all calls.
2. cam_job (006): Block is no longer selected, but the job is not selected either.

### What the CAM echo should do
- Look into why `path_seen.shown` is true when nothing is drawn. Read the op's view `LineWidth`, `Visibility`,
  `DisplayMode` and the scene graph after cam_op. A more sure way: draw the op's `Path` commands as a scene-only
  polyline (as `annotate` does for FEM maps), not through `ViewProviderPath`.
- cam_post: put the file name in the caption. cam_tool_add: select only the tool controller, and fit the stock.

## 2. FEM (11)

| picture | tool | rating | reason |
|---|---|---|---|
| 000-part_primitive | part_primitive | GOOD | 8 m Box selected, Box ringed. |
| 001-material_set | material_set | MINOR | Material ringed; Box not selected; no material name. |
| 003-fea_setup | fea_setup | GOOD | Analysis ringed, Box selected, good caption. |
| 005-fea_hold | fea_hold | BAD | No mark on x=0 face; nothing selected. |
| 030-fea_modes | fea_modes | MINOR | Caption now gives 3 frequencies; no mode shape. |
| 033-fea_load | fea_load | MINOR | Self-weight ringed; gravity has no symbol. |
| 034-fea_solve | fea_solve | MINOR | Jet stress map shown, "max 444 MPa"; patchy, no legend. |
| 038-fea_refine | fea_refine | GOOD | Mesh-region button ringed, good caption. |
| 039-fea_shell | fea_shell | MINOR | Own caption now ("max 2.688 MPa"); no map on the plate. |
| 041-fea_parts | fea_parts | MINOR | Block joined at the end, selected; tie not shown. |
| 042-fea_clear | fea_clear | MINOR | "Cleared FEM" short; Box native, Block stay. |

Counts: GOOD 3 / MINOR 7 / BAD 1 (round 4: 2 / 6 / 3).

### FEM: round-4 problems now

| round-4 problem | status | pictures |
|---|---|---|
| fea_solve: no colour map | FIXED (partly clean). A jet map is on the beam, but the selected Box's light-green shows through in stripes and two whole panels (z-fighting with the selection colour). There is no colour scale | 034 |
| No figures in captions | FIXED: "max 444 MPa", "12.95, 12.95, 75.93 Hz", "max 2.688 MPa" | 030, 034, 039 |
| fea_shell stale picture | FIXED: own caption, Box selected. The ring is still fea_refine's (correct by rule: it was a read) | 039 |
| Ring on "»" | FIXED: no ring | 034 |
| fea_hold: no mark | NOT FIXED | 005 |
| Gravity no symbol | NOT FIXED | 033 |
| material_set: no material name | NOT FIXED; Box is now also not selected (WORSE, small) | 001 |
| "Cleared FEM" short; leftovers | NOT FIXED | 042 |

### FEM: new problems
1. 034: the map fights with the selection highlight of Box. Deselect Box (or do not pre-select the study solid)
   while the map is up, or push the map further in front.
2. 034: no safety factor in the caption (round6-findings promised "max …, safety …"). There is no colour legend.
3. 030-042: the "Box native" tree row stays green (the same leftover-row effect as CAM).

## 3. TechDraw (28)

| picture | tool | rating | reason |
|---|---|---|---|
| 000-doc_open | doc_open | MINOR | Part workbench left; title-block text oversized (file). |
| 002-td_list | td_list | MINOR | Right page; red Dimension002; "Shape index 29" exception. |
| 004-td_page | td_page | MINOR | Page shown, ringed; "8 cleared"; title says 1:1. |
| 011-td_title | td_title | MINOR | No visible change on the title block. |
| 013-td_note | td_note | MINOR | Note shown, ringed; text over the title block. |
| 019-td_export | td_export | MINOR | Ring on an annotation button; no file names; panel Tut ANSIB. |
| 020-part_primitive | part_primitive | GOOD | Plate selected, Box ringed. |
| 026-part_boolean | part_boolean | GOOD | Fused Slot selected, Fuse ringed. |
| 029-td_view | td_view | GOOD | PlateTop on new page, Insert View ringed. |
| 030-td_geometry | td_geometry | MINOR | Good caption; circles not marked. |
| 031-td_dim | td_dim | MINOR | Ø6 drawn; generic caption; dimension not selected. |
| 036-td_dimset | td_dimset | MINOR | Chain drawn; "30" and "R3" overlap. |
| 037-td_dim_special | td_dim_special | MINOR | Arc label on the Ø10 hole; "arc_length" in caption. |
| 038-td_centermarks | td_centermarks | MINOR | Ringed; crosses at slot ends; "1 views" caption. |
| 039-td_section | td_section | GOOD | Line A-A and section view, ringed. |
| 040-td_section_position | td_section_position | MINOR | Good caption; no visible change; panel empty. |
| 041-td_detail | td_detail | GOOD | Detail circle B and view, ringed. |
| 042-td_datum | td_datum | GOOD | Datum A on the bottom edge, good caption. |
| 043-td_gdt | td_gdt | MINOR | Frame on the Ø10 leader and detail circle. |
| 045-td_balloon | td_balloon | GOOD | Balloon 1 green, ringed. |
| 046-td_leader | td_leader | MINOR | Text floats above the plate; tool-name caption. |
| 047-td_finish | td_finish | MINOR | Symbol on the Ø10 text; tool-name caption; no ring. |
| 048-td_weld | td_weld | MINOR | Weld drawn; size "3" not seen; no ring. |
| 049-shape_query | shape_query | MINOR | 3D view; found face not lit; no caption box. |
| 052-td_cosmetic | td_cosmetic | MINOR | Page shown now; faint lines; tool-name caption. |
| 053-td_lines | td_lines | MINOR | Page shown now; change hard to see. |
| 058-sheet_new | sheet_new | GOOD | Spreadsheet Parts open, ringed. |
| 061-td_view_more | td_view_more | MINOR | Lock Position Yes; tool-name-like caption. |

Counts: GOOD 8 / MINOR 20 / BAD 0 (round 4: 8 / 18 / 2).

### TechDraw: round-4 problems now

| round-4 problem | status | pictures |
|---|---|---|
| td_cosmetic / td_lines leave the 3D view | FIXED: Plate drawing in front | 052, 053 |
| Ring on "»" | FIXED: no ring (and no other clue in the window) | 047, 048 |
| Wrong workbench after doc_open | NOT FIXED (Part now; BIM in round 4) | 000 |
| td_export ring on the wrong button | NOT FIXED | 019 |
| "8 cleared" in the td_page caption | NOT FIXED | 004 |
| Dimensions not selected | NOT FIXED | 031, 036, 037 |
| Overlaps (30/R3, arc label, GDT frame, finish) | NOT FIXED (open in round6-findings) | 036, 037, 043, 047 |
| Leader text away from the leader end | NOT FIXED | 046 |
| Weld size not seen | NOT FIXED | 048 |
| shape_query face not lit | NOT FIXED | 049 |
| Tool-name captions | NOT FIXED: leader, finish, weld, cosmetic, view_more | 046-048, 052, 061 |
| "Shape index 29" exception in Report view | NOT FIXED (stays through all TD and Mesh pictures) | 002-061 |

### TechDraw: new problems
1. shape_query (049) has no caption box in the 3D view, only status-bar words.
2. 061 shows a new empty table at the top right of the page (most likely made by an earlier td_view_more call).
   Nothing says what it is.

## 4. Mesh (21)

| picture | tool | rating | reason |
|---|---|---|---|
| 001-meshobj_smooth | meshobj_smooth | GOOD | Globe smooth selected, ringed, Mesh Info. |
| 002-meshobj_offset | meshobj_offset | GOOD | Globe plus selected, ringed, Mesh Info. |
| 003-meshobj_transform | meshobj_transform | GOOD | Cube big selected; same ring as offset. |
| 007-meshobj_sections | meshobj_sections | GOOD | Rings inside see-through globe, Sections ringed. |
| 009-meshobj_segments | meshobj_segments | BAD | No segment colours; caption "on planar". |
| 012-meshobj_curvature | meshobj_curvature | BAD | No map; view still on cube, globe off-screen. |
| 014-part_wire | part_wire | GOOD | Stripe green, ringed, "6 mm". |
| 015-meshobj_project | meshobj_project | MINOR | Good caption; camera inside the cube. |
| 017-meshobj_primitive | meshobj_primitive | GOOD | CylA selected, Primitives ringed. |
| 019-meshobj_boolean | meshobj_boolean | MINOR | Pipe shown; caption names the op, not Pipe. |
| 025-meshobj_merge | meshobj_merge | GOOD | Lot selected, Merge ringed. |
| 026-meshobj_split | meshobj_split | MINOR | "3 pieces"; Lot 1 info equals whole Lot. |
| 028-meshobj_edit | meshobj_edit | GOOD | Crate (editing), Add triangle ringed. |
| 029-meshobj_refine | meshobj_refine | MINOR | Mesh Info 20/36; caption has no counts; blotchy. |
| 032-meshobj_export | meshobj_export | MINOR | No file name; ring back on Add triangle. |
| 035-import_file | import_file | MINOR | Cube back selected; lies on Cube mesh, blotchy. |
| 036-meshobj_info | meshobj_info | GOOD | Mesh Info numbers for Cube back. |
| 037-part_from_mesh | part_from_mesh | GOOD | Cube solid selected; good caption. |
| 038-part_primitive | part_primitive | GOOD | Can selected, Cylinder ringed. |
| 039-meshobj_unwrap | meshobj_unwrap | MINOR | Outline green; framing cuts objects; blue blotches. |
| 041-meshobj_trim | meshobj_trim | GOOD | Cap in see-through globe, Trim ringed. |

Counts: GOOD 12 / MINOR 7 / BAD 2 (round 4: 12 / 9 / 0. The 2 BAD were MINOR in round 4: the special check now
counts).

### Mesh: round-4 problems now

| round-4 problem | status | pictures |
|---|---|---|
| Segments never coloured | NOT FIXED: cube plain grey. `segments_drawn` is claimed, but no colour is seen. The selection is cleared now (Mesh Info empty) | 009 |
| Curvature map never shown, no min/max | NOT FIXED: no map. The caption gives only "5301 points". The camera stays on Cube mesh; Globe fine is selected but off-screen | 012 |
| Blue patches to 041 | NOT FIXED (by design, kept segment meshes) | 015, 017, 019, 035-039 |
| Camera inside the cube (project) | NOT FIXED | 015 |
| Boolean caption names op | NOT FIXED | 019 |
| Split pieces not told apart | NOT FIXED | 026 |
| Refine / export captions | NOT FIXED | 029, 032 |
| export ring on Add triangle | NOT FIXED (029 ringed Refine, then 032 back on Add triangle) | 032 |
| Unwrap framing | NOT FIXED | 039 |

### Mesh: what the echo should do
- 009: draw the segment colours. Check `echo.segmentsDrawn` in `session_state`. If it is above 0 and nothing shows,
  the scene node is not under the shown root or is under the mesh's faces (push it in front, as the FEM map).
- 012: frame the measured mesh, draw the curvature map, put min/max in the caption, and ring the Curvature
  (rainbow) button.

## Top problems left (four families)
1. CAM toolpaths still never seen, although answers say `shown: true` (cam 008-032).
2. Mesh segment and curvature colours never seen. The curvature view does not even frame the globe (mesh 009, 012).
3. FEM stress map patchy: the selection colour shows through. No legend, no safety factor (fem 034).
4. fea_hold still leaves no mark on the held face (fem 005).
5. Tool-name or poor captions and stale Report-view errors remain: td 046-048/052/061, cam 020/028, mesh 009, "Shape
   index 29", EdgeWalker.

Fixed this round: td_cosmetic/td_lines page, no ring on "»", FEM figures in captions, FEM colour map, fea_shell
stale picture, cam_sim caption. No leftover task dialog in any picture.

## Tools proven live

PROVEN_LIVE cam: part_primitive, part_boolean, cam_job, cam_tool_add, cam_setup, cam_edit, cam_library, cam_tool, cam_path, cam_property_bag, cam_template_export
NOT_PROVEN cam: cam_op (no toolpath drawn), cam_dressup (no tags or path), cam_list (read, no paths), cam_sim (nothing drawn), cam_post (no file name), cam_remove (change not seen)
PROVEN_LIVE fem: part_primitive, material_set, fea_setup, fea_modes, fea_load, fea_solve, fea_refine, fea_shell, fea_parts, fea_clear
NOT_PROVEN fem: fea_hold (no mark on the held face)
PROVEN_LIVE techdraw: doc_open, td_list, td_page, td_note, part_primitive, part_boolean, td_view, td_geometry, td_dim, td_dimset, td_dim_special, td_centermarks, td_section, td_detail, td_datum, td_gdt, td_balloon, td_leader, td_finish, td_weld, shape_query, td_cosmetic, td_lines, sheet_new, td_view_more
NOT_PROVEN techdraw: td_title (no visible change), td_export (file not shown), td_section_position (no visible change)
PROVEN_LIVE mesh: meshobj_smooth, meshobj_offset, meshobj_transform, meshobj_sections, part_wire, meshobj_project, meshobj_primitive, meshobj_boolean, meshobj_merge, meshobj_edit, meshobj_refine, meshobj_export, import_file, meshobj_info, part_from_mesh, part_primitive, meshobj_unwrap, meshobj_trim
NOT_PROVEN mesh: meshobj_segments (no colours), meshobj_curvature (no map, globe off-screen), meshobj_split (pieces not told apart)

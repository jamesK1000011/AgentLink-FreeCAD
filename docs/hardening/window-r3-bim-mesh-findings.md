# Window review, round 3: BIM and Mesh (after echo round 3 and famfix)

I looked at all 66 pictures listed in pictures.json (BIM 45, Mesh 21). FreeCAD 1.1.3, Agent Link echo round 3.
Old reviews compared: `docs/hardening/window-bim-findings.md` (BIM 2/23/20) and the Mesh section of
`docs/hardening/window-draft-surf-fem-mesh-findings.md` (Mesh 2/8/11). Claimed fixes: `famfix-findings.md`, `echo3-findings.md`.

Rating rule (same as before): GOOD = result shown correctly, only known general problems; MINOR = result shown with a small problem; BAD = result not seen, wrong object, or a failure the user would notice.

General notes (counted here, not in each row):
- The Report view is open at the bottom in every picture. BIM: red `DiffuseColor` AttributeError tracebacks (ArchWall.py:1684) in all 45 pictures, plus ArchCurtainWall.py:794 from 046 on. Mesh: old CAM lines (orange "EdgeWalker has no edges", "Sort mode 'None'") in all 21.
- The property view often shows an earlier object (BIM 018, 020, 035, 037, 039, 041, 044-051; Mesh 003, 007, 014, 017, 025, 035, 041).
- Model tab is in front in all 66 pictures (good).

---

## 1. BIM (45 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-bim_wall | bim_wall | GOOD | Wall framed, selected, ring on Wall button, caption "Drew a wall" |
| 003-bim_opening | bim_opening | GOOD | Door framed and selected, property shows Front door; ring is on the toolbar overflow arrow |
| 008-bim_structure | bim_structure | GOOD | Slab selected and named in caption; no ring |
| 013-bim_profiles | bim_profiles | MINOR | Caption "5 found" is good; Porch beam from an earlier call is still selected |
| 014-bim_member | bim_member | GOOD | Steel beam framed and selected, property right |
| 015-bim_roof | bim_roof | GOOD | Roof framed and selected, property right |
| 017-bim_stairs | bim_stairs | GOOD | Stairs framed and selected ("Hip roof cw" is the model's own second roof, per famfix) |
| 018-bim_space | bim_space | MINOR | Front wall is see-through and the room shows faintly; the ROOF is not see-through; property stale (Stairs) |
| 020-bim_level | bim_level | MINOR | Level selected, ring and caption good; camera zooms onto the level's text and grid, house not in view |
| 022-bim_building | bim_building | MINOR | House selected, ring good; camera frames a giant "Ground floor" label, not the building |
| 023-bim_list | bim_list | MINOR | Caption "22 found" is good; same odd framing as 022 |
| 024-bim_material | bim_material | MINOR | Inner wall shows faintly through see-through walls, but the brick colour cannot be seen; "House" stuck green |
| 026-bim_layers | bim_layers | MINOR | Property shows "Outer build-up", caption good; nothing to see in 3D |
| 028-bim_ifc | bim_ifc | BAD | Caption is only "BIM ifc"; Plinth not selected; Tasks panel jumps to "2D geometry" |
| 030-bim_rebar | bim_rebar | BAD | Bars cannot be seen: walls and roof are NOT see-through; property shows Base "Slab bars line001 (Line)" |
| 031-bim_covering | bim_covering | MINOR | Tiles seen and selected through see-through walls; roof still solid |
| 032-bim_schedule | bim_schedule | BAD | Schedule sheet NOT opened; caption only "BIM schedule" |
| 034-bim_quantities | bim_quantities | GOOD | Schedule sheet in front (one call late), caption gives the quantities result |
| 035-bim_edit | bim_edit | MINOR | Inner wall tinted through see-through walls; the cut at 2400 is under the solid roof; property stale |
| 037-bim_grid | bim_grid | BAD | Grid shows only as a short dashed green line by the porch; property stale |
| 039-bim_structural_system | bim_structural_system | MINOR | Pads shown and selected; property shows the axis, not Pads |
| 041-bim_section | bim_section | MINOR | Section plane shown and selected; property stale (Pads) |
| 042-bim_views | bim_views | BAD | Camera turns to top, but no plan or page is shown; caption only "BIM views"; property still Plan cut |
| 043-bim_truss | bim_truss | BAD | Truss is behind the house and not seen; roof not see-through |
| 044-bim_fence | bim_fence | MINOR | Fence framed and selected; property stale |
| 045-bim_frame | bim_frame | MINOR | Portal framed and selected; property stale |
| 046-bim_curtain_wall | bim_curtain_wall | MINOR | Glazing framed and selected; new ArchCurtainWall colorize error |
| 047-bim_panel | bim_panel | MINOR | Shelf framed and selected; property stale |
| 048-bim_panel_out | bim_panel_out | MINOR | Top view, shelf outline selected; no cut sheet or layout shown |
| 049-bim_pipe | bim_pipe | MINOR | Pipe framed and selected; property stale |
| 051-bim_pipe_connector | bim_pipe_connector | MINOR | Elbow now framed close and selected; property stale (Shelf) |
| 052-part_primitive | part_primitive | GOOD | Part workbench, ring on Primitives, Sink block selected, seen through see-through roof |
| 053-bim_equipment | bim_equipment | GOOD | Sink selected and framed, property right |
| 054-bim_component | bim_component | GOOD | Sink as component selected, property right |
| 055-bim_ifc_brep | bim_ifc_brep | BAD | Caption only "BIM ifc brep"; whole-document fit; nothing selected; Tasks jumps to "2D geometry" |
| 056-bim_trash | bim_trash | MINOR | Property shows Trash with the sink; caption only "BIM trash"; Trash not shown in the tree |
| 058-bim_reorder | bim_reorder | MINOR | Caption only "BIM reorder"; Ground floor not opened, so the new order is not shown |
| 059-bim_preflight | bim_preflight | GOOD | Caption gives the preflight result ("blocking: no shape, invalid shapes, no spatial structure") |
| 060-bim_export | bim_export | GOOD | Caption "wrote house.ifc"; Report view "Finished exporting"; no rebar line |
| 061-ifc_open | ifc_open | MINOR | Words only; caption ends "wrote house.ifc" (copied from export); no new tab |
| 062-ifc_find | ifc_find | MINOR | Caption "2 found"; nothing selected |
| 063-ifc_edit | ifc_edit | MINOR | Caption names Inner and says ifc_save writes it; nothing selected |
| 065-ifc_save | ifc_save | GOOD | Caption "wrote house_edited.ifc" |
| 066-ifc_diff | ifc_diff | MINOR | Caption explains geometry is not compared; no added/removed/changed count |
| 068-bim_import | bim_import | MINOR | Import selected (green), but it lies on top of the old house (z-fighting); no `note` text in caption |

Counts: GOOD 13, MINOR 25, BAD 7 (old: GOOD 2, MINOR 23, BAD 20).

Round-3 numbers (BIM, 45):
- Ring visible: 21. On the real button: 7 (001, 018, 020, 022, 023, 024, 052). On the toolbar overflow arrow (the button is hidden in the overflow): 12 (003, 014, 015, 017, 030, 043-047, 049, 053). Clipped at the right window edge: 2 (037, 041). No ring: 24.
- Caption: 45/45. Tool name only: 6 (028, 032, 042, 055, 056, 058). Wrong words: 061.
- Result selected: 27 clearly (plus 026 and 056 in the property view only).
- Sketch-edit pictures: none in this family.

### Old BIM problems: status

| Old problem | Status | Pictures |
|---|---|---|
| Results under the roof (see-through covers) | PARTLY | Walls are see-through in 018, 024, 031, 035, 037, 052: room, wall and tiles show. The ROOF never goes see-through (018, 024, 031, 035), and nothing is see-through in 030 (rebar) and 043 (truss). The see-through walls also stay see-through in later pictures (044, 045). |
| Schedule / plan / cut sheet opened | PARTLY | Schedule sheet opens one call LATE (not at 032, but at 034). Plan: 042 only turns the camera to top, no plan. Cut sheet: 048 top view of the shelf outline, no sheet. |
| Red DiffuseColor lines in Report view | NOT FIXED | All 45 pictures; new lines added at 001, 003, 024, 035, 060; ArchCurtainWall from 046. |
| "Cannot calculate rebar length" | FIXED (visible tail) | Not in 030 or 060. But 030's property shows Base "Slab bars line001 (Line)", not a Draft wire, so famfix's rebar_line change may have fallen back; the schedule (034) lists Slab bars 218.5 kg. Check with object_get. |
| Stale selection of "House" | NOT FIXED | "House" is green in the tree and the BIM panel from 024 to 068 (all 33 pictures). Porch beam stays selected in 013. |
| IFC tools leave no mark (061-066) | PARTLY | Each picture now has its own caption with the result; no tab, no selection. 061 caption is wrong. |
| Grid, truss, elbow not seen (037, 043, 051) | PARTLY | Elbow FIXED (051). Grid NOT FIXED (037). Truss NOT FIXED (043). |
| Queries say nothing (013, 023, 034, 059) | FIXED | All four captions give the result. |
| bim_import on top of old model (068) | PARTLY | Now selected and framed; still on top; famfix `note` not shown. |
| bim_reorder / bim_trash tree change | NOT FIXED | 056, 058: tree not opened, Trash not shown. |
| bim_ifc / bim_ifc_brep no mark (028, 055) | NOT FIXED | Tool-name caption, nothing selected. |

### BIM-particular problems (what the echo should do)
1. The roof is never made see-through (018, 024, 030, 031, 035, 043). `uncover()` takes a cover only when its box holds the result's middle and is 0.9 of its size; the roof box is above the room, so it does not qualify. For `bim_` calls, also take objects whose box is ABOVE the result in z (or the whole "Roof level"), and the walls for rebar (030).
2. `bim_schedule` shows its sheet one call late (032 no sheet, 034 sheet). Bring the sheet up in the same call.
3. "House" stays green from 024 to 068. This is the BIM panel's / tree's highlight, not a plain selection; clearing the selection does not remove it. Clear the tree highlight too.
4. Ring lands on the toolbar overflow arrow (12 pictures): the BIM toolbar is too long for the window. Open the overflow, or ring the dropdown that holds the button, or skip the ring and say so in the caption.
5. Level and building framing (020, 022, 023): fit goes to the level's big label text. Fit to the level's members instead.
6. bim_views (042) and bim_panel_out (048): show the made 2D view or sheet (select it and fit in top view), not the whole model from the top.
7. Grid (037) and truss (043): fit to the new object only, and make the house see-through when the new object is behind it.
8. Tasks panel jumps to "2D geometry" after 028, 055, 058-066; it should stay or go back to the previous panel.
9. DiffuseColor tracebacks: from FreeCAD's BIM code on 1.1.3. Clear the Report view per call, or avoid the code path (set colours by ShapeAppearance).

---

## 2. Mesh (21 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-meshobj_smooth | meshobj_smooth | GOOD | Globe smooth selected, source see-through, Mesh Info filled (153 points) |
| 002-meshobj_offset | meshobj_offset | GOOD | Globe plus selected, Mesh Info filled |
| 003-meshobj_transform | meshobj_transform | GOOD | Cube big selected, Mesh Info filled; property stale |
| 007-meshobj_sections | meshobj_sections | MINOR | Section rings green inside the see-through globe; Mesh Info empty (rings are wires); property stale |
| 009-meshobj_segments | meshobj_segments | MINOR | Cube mesh selected; no segment colours visible (green selection hides them) |
| 012-meshobj_curvature | meshobj_curvature | BAD | "Cube even" selected, not Globe fine; no colour map; caption only "Mesh curvature" |
| 014-part_wire | part_wire | MINOR | Stripe line shown green; tree and property still show Cube even |
| 015-meshobj_project | meshobj_project | MINOR | Projected line selected, but the camera is far too close (cube faces fill the view); caption only "Mesh project" |
| 017-meshobj_primitive | meshobj_primitive | GOOD | CylA selected, Mesh Info filled |
| 019-meshobj_boolean | meshobj_boolean | MINOR | Pipe selected, Mesh Info filled; small at whole-document fit; hole not seen |
| 025-meshobj_merge | meshobj_merge | GOOD | Lot (ring, spike, crate) selected, Mesh Info filled |
| 026-meshobj_split | meshobj_split | MINOR | Property "Lot 1"; pieces not coloured apart; caption "Split Mesh" without a count |
| 028-meshobj_edit | meshobj_edit | MINOR | Crate selected, label "Crate (editing)", Mesh Info filled; caption only "Edited Mesh" |
| 029-meshobj_refine | meshobj_refine | MINOR | Mesh Info shows 36 facets (was 12); triangles not drawn; caption only "Mesh refine" |
| 032-meshobj_export | meshobj_export | MINOR | Caption explains the export but does not name cube.stl |
| 035-import_file | import_file | MINOR | Cube back selected, Mesh Info filled; small and on top of the old cube |
| 036-meshobj_info | meshobj_info | GOOD | Mesh Info filled for Cube back (8 points, 12 facets, bounds); caption "Read a mesh" is plain |
| 037-part_from_mesh | part_from_mesh | MINOR | Cube solid framed and selected; blue z-fighting; caption says "Turned Cube solid into a solid" (should name Cube back) |
| 038-part_primitive | part_primitive | GOOD | Can framed, selected, ring on Primitives |
| 039-meshobj_unwrap | meshobj_unwrap | MINOR | Can flat outline selected, but framing cuts off neighbours; blue blotches on the cube |
| 041-meshobj_trim | meshobj_trim | MINOR | Cap shows green inside the see-through globe, Mesh Info filled (55 points); small at whole-document fit |

Counts: GOOD 7, MINOR 13, BAD 1 (old: GOOD 2, MINOR 8, BAD 11).

Round-3 numbers (Mesh, 21):
- Ring visible: 1 (038). No ring on any Mesh workbench button (0/19).
- Caption: 21/21. Tool name only or plain: 6 (012, 015, 026, 028, 029, 036). Wrong words: 037.
- Result selected: 19 (all but 012, which selects the wrong mesh, and 032, an export that keeps Crate).
- Sketch-edit pictures: none in this family.

### Old Mesh problems: status

| Old problem | Status | Pictures |
|---|---|---|
| Mesh results never selected | FIXED | Selected in 001, 002, 003, 017, 019, 025, 026, 028, 029, 035, 036, 041. Wrong object only in 012. |
| Mesh Info panel empty | FIXED | Filled in 15 pictures; empty only where the result is not a mesh (007, 015, 039). 036 (meshobj_info) shows the numbers. |
| New meshes on top of the source | PARTLY | Source see-through in 001, 007, 041. Still on top in 035 (Cube back) and 037 (z-fighting). |
| Segments coloured (009) | PARTLY | Not visible in 009 (selection green covers them). A blue face shows on the cube from 012 to 041, which may be a segment colour left over. |
| Curvature colour map (012) | NOT FIXED / WORSE | No map, and now the wrong mesh (Cube even) is selected. |
| Change-in-place tools look the same (026, 028, 029, 041) | PARTLY | 028 label "(editing)", 029 facet count in Mesh Info, 041 Cap visible. 026 split pieces not told apart. |
| meshobj_edit begin shows no state (028) | PARTLY | Label "Crate (editing)" and selection; no edit highlight in 3D. |
| Old Report view text | NOT FIXED | CAM lines in all 21 pictures. |

### Mesh-particular problems (what the echo should do)
1. No ring on any Mesh workbench button (19 pictures). The Mesh commands are on the toolbar (Smooth, Offset, Boolean, Split, Curvature, Trim, Refine all have buttons). Map meshobj_ tools to them.
2. meshobj_curvature (012): select the named mesh (Globe fine), not "Cube even", and call `view_render { map: "curvature" }` or FreeCAD's curvature colour plot, with a caption giving min/max.
3. meshobj_segments (009): clear the selection after a short time, or do not select, so the segment colours show; the caption should give the segment count. Remove the segment colours at the next changing call (the blue face stays on the cube until 041).
4. meshobj_project (015): fit to the cube and the line, not to the line alone inside the cube.
5. Copies on their source (035, 037): make the old cube see-through too (Cube mesh, Cube, Cube even, Cube back all share one place; blue z-fighting in 037, 039).
6. meshobj_split (026): colour each piece and give the piece count in the caption.
7. Captions: refine should give old/new facet counts, info the numbers, export the file name; part_from_mesh must name the mesh it read.

---

## Counts per family

| Family | GOOD | MINOR | BAD | Old GOOD/MINOR/BAD |
|---|---|---|---|---|
| BIM | 13 | 25 | 7 | 2 / 23 / 20 |
| Mesh | 7 | 13 | 1 | 2 / 8 / 11 |

## Tools proven live in the window (GOOD or MINOR, result seen)

BIM: bim_wall, bim_opening, bim_structure, bim_member, bim_roof, bim_stairs, bim_space (faint), bim_level, bim_building, bim_material (wall only, no colour), bim_covering, bim_quantities, bim_edit (weak), bim_structural_system, bim_section, bim_fence, bim_frame, bim_curtain_wall, bim_panel, bim_pipe, bim_pipe_connector, part_primitive, bim_equipment, bim_component, bim_export, ifc_save, bim_import, bim_layers (property only), bim_trash (property only), and by caption only: bim_profiles, bim_list, bim_preflight, ifc_open, ifc_find, ifc_edit, ifc_diff.
Not proven: bim_ifc, bim_rebar, bim_schedule, bim_grid, bim_views, bim_truss, bim_ifc_brep, bim_reorder, bim_panel_out (no sheet).

Mesh: meshobj_smooth, meshobj_offset, meshobj_transform, meshobj_sections, meshobj_primitive, meshobj_boolean, meshobj_merge, meshobj_edit, meshobj_refine (Mesh Info), meshobj_info, import_file, part_wire, part_from_mesh, part_primitive, meshobj_unwrap, meshobj_trim, meshobj_project, meshobj_export (caption).
Not proven: meshobj_curvature, meshobj_segments (no colours), meshobj_split (pieces not told apart).

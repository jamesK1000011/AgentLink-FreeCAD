# Window review, round 4: Core, BIM, Mesh

I looked at all 115 pictures listed in pictures.json (Core 49, BIM 45, Mesh 21). FreeCAD 1.1.3, Agent Link echo round 4.
Compared with `docs/hardening/window-r3-part-core-pts-sheet-findings.md` (Core) and `docs/hardening/window-r3-bim-mesh-findings.md` (BIM, Mesh), and the claimed fixes in `round4-findings.md`.

Rating rule (same as round 3): GOOD = result shown correctly, only known general problems; MINOR = result shown with a small problem; BAD = result not seen, wrong object, or a failure the user would notice.

General notes (counted here, not in each row):
- Model tab is in front in all 115 pictures (good).
- The property view now follows the new object in almost every picture (round 3: often one call late). FIXED.
- The Report view stays open with old red text: Core shows CompoundFilter / AttachEngine3D errors, then OpenSCAD "executable not found"; BIM shows the `DiffuseColor` tracebacks in all 45; Mesh shows BIM `DiffuseColor` tracebacks from another document in all 21.
- When the tree is longer than the panel, it does not scroll to the new object (Core 0025-0097, BIM 013 on, Mesh all).

---

## 1. Core: document, view, material, robot, OpenSCAD, inspection (49 pictures)

NEW, in every Core picture: an Assembly "Bill of Materials" task dialog (Cancel / OK, Columns, Export) is open in the right-hand Tasks panel from 0001 to 0110. It is a leftover dialog from an earlier run. Close it before the run (or the echo should close a dialog it did not open).

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Block framed, selected, ring on Box, volume in caption |
| 0003 | object_list | GOOD | Caption "2 found"; last change Rod stays selected |
| 0005 | object_get | MINOR | Block selected in tree now; Block cut off at top |
| 0007 | object_set | GOOD | Block selected, caption "Set Block Length to 2 in" |
| 0011 | units_convert | GOOD | Caption gives answer: 50.8 mm |
| 0014 | object_rename | MINOR | Pin not selected; caption good |
| 0016 | object_group | GOOD | Parts selected, ring on Group button |
| 0021 | link_make | MINOR | Ghost selected, ring on Link; caption has no name |
| 0023 | link_edit | MINOR | Ghost now visible as Pin; caption only "Edited Link" |
| 0025 | object_duplicate | MINOR | Block moved selected now; caption has no name |
| 0026 | object_align | MINOR | Block moved selected; z-fighting with Block |
| 0028 | text_document | GOOD | Text opens in its own tab, caption gives size |
| 0030 | doc_info | MINOR | Caption says "Renamed the document" for a comment set |
| 0031 | doc_graph | MINOR | Caption right now; no graph, no count |
| 0032 | object_appearance | BAD | Block stays grey; the two links turn blue |
| 0034 | object_freeze | MINOR | Caption "Froze an object" names nothing |
| 0035 | recompute | GOOD | Ring on Recompute, caption good |
| 0038 | shape_query | GOOD | Top face of Block lit, "1 found" |
| 0041 | measure | GOOD | Faces lit, caption "Measured: 20 mm" |
| 0044 | measure_keep | GOOD | 20.00 mm label, ring on Measure, property right |
| 0048 | section | MINOR | Caption gives 1200 mm², but no cut is drawn |
| 0050 | clearance | GOOD | Caption gives 15 mm |
| 0052 | measure_mass | MINOR | Caption gives volume 24000 mm³, not mass |
| 0053 | material_list | GOOD | Caption "14 found" |
| 0054 | material_get | MINOR | Caption is a cut-off warning, no values |
| 0055 | material_set | MINOR | Ring on Material button now; Block not selected |
| 0060 | material_clear | MINOR | "1 cleared"; links shown hidden in tree but visible |
| 0062 | insp_run | GOOD | Inspection map, legend, Shift check property |
| 0063 | insp_read | MINOR | Caption gives points, not worst values |
| 0064 | insp_list | GOOD | Caption "1 inspections" |
| 0065 | insp_faces | MINOR | Caption is a cut-off explanation |
| 0066 | insp_update | MINOR | Shift check not selected, property view empty |
| 0069 | insp_export | MINOR | Caption has no file name |
| 0070 | scad_status | MINOR | Long caption cut off with "..." |
| 0071 | scad_export | MINOR | Workbench stays Inspection; caption good |
| 0072 | scad_import | MINOR | OpenSCAD wb, cube visible; caption says "wrote Block.csg" |
| 0074 | scad_op | GOOD | Hull Wrap selected and framed, volume in caption |
| 0077 | scad_tidy | GOOD | Ring on Color code, colours changed, caption names objects |
| 0081 | robot_new | BAD | Robot invisible; view 7.8 m wide, empty |
| 0082 | robot_move | BAD | Robot invisible; only axis values in property |
| 0087 | robot_path | MINOR | Path a tiny orange line in a 9 m view |
| 0088 | robot_run | MINOR | Caption "7582 mm off"; nothing to see |
| 0092 | robot_tool | BAD | Pin not shown on robot; empty 6.7 m view |
| 0096 | export | MINOR | Robot wb stays; Block not shown or selected |
| 0097 | import_file | MINOR | Import now visible and selected; Robot wb; z-fighting |
| 0103 | doc_save_all | GOOD | Caption good, Ball stays selected with ring |
| 0105 | doc_merge | MINOR | Ball001 sits exactly on Ball |
| 0108 | object_delete | GOOD | Ball gone, caption good |
| 0110 | doc_open | MINOR | Second copy CoreDoc1 opens; top view; nothing selected |

Counts: GOOD 18, MINOR 27, BAD 4 (round 3: GOOD 7, MINOR 31, BAD 11).

Round-4 numbers (Core, 49):
- Ring visible: 24 (round 3: 7). On the real button for this call: 13 (0001, 0016, 0021, 0023, 0035, 0044, 0055, 0060, 0077, 0081, 0082, 0087, 0105). Kept from the last change (expected): 11.
- Caption: 49/49. Wrong words: 0030 ("Renamed"), 0072 ("wrote" on import), 0052 (volume for mass). Cut off: 0054, 0065, 0070.
- Result selected: 22 clearly (round 3: 14), plus the robot in the property view only (0081-0092).

### Round-3 Core problems: status

| Round-3 problem | Status | Pictures |
|---|---|---|
| Robot shows nothing, 10 m fit | NOT FIXED | 0081, 0082, 0092: view 6.7-7.8 m, no arm, no tool. `_robot_frame` (min 1.5 m) did not take effect. |
| Robot task panel, narrower 3D view | FIXED | 0081-0097: no robot task box; 3D view keeps its width. |
| Inspection map and legend stay | FIXED | 0072 and 0097: legend gone, results visible. |
| Workbench does not follow the tool | PARTLY | 0072 OpenSCAD good; 0071 still Inspection; 0096, 0097 still Robot. |
| object_appearance colours the links | NOT FIXED | 0032 (and the colours stay to 0074). Block property holds #3366cc and 30 but Block stays grey. |
| Read captions without a value | PARTLY | Fixed: 0011, 0041, 0044, 0050, 0053, 0064. Still: 0052 (volume not mass), 0063 (no worst values), 0069 (no file). Cut-off text: 0054, 0065, 0070. |
| Results not shown | PARTLY | text_document FIXED (0028); measure FIXED (0041); section caption only (0048); doc_graph caption only (0031). |
| Wrong selection | FIXED | object_get 0005, object_duplicate 0025, link_edit 0023. |
| doc_info says "Read" | WORSE | 0030 now says "Renamed the document CoreDoc: <date>". |
| doc_open opens a second copy | NOT FIXED | 0110 (CoreDoc1). |

### Core problems particular to this family (what the echo should do)
1. Robot (0081, 0082, 0092): frame the robot's base-to-tool box (the "puma" default has no VRML model, so draw at least the tool point / Tool Shape and a marker), never a 7 m empty view.
2. Leftover Bill of Materials dialog in all 49 pictures: close foreign task dialogs at run start, or report them.
3. Workbench should follow export / import_file / scad_export (0071, 0096, 0097): switch to Part (or OpenSCAD) and frame the exported or imported object.
4. object_appearance (0032): tool bug, not echo. Block keeps grey; only the links change. Probe per-face DiffuseColor path on 1.1.3.
5. Captions: measure_mass should give grams; doc_info should say "Set comment and company"; scad_import / bim-import style "wrote" should be "imported". Shorten warnings to the answer (0054, 0065, 0070).
6. section (0048): draw the section wire, or select it, so the cut is seen. doc_graph (0031): give a count of links.
7. The kept "20.00 mm" measurement label shows in every later 3D picture (0048-0110), also in the robot and second-document views. It is a real object, but the echo could hide it when the next call is in another family.

---

## 2. BIM (45 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-bim_wall | bim_wall | GOOD | Wall framed, selected, ring on Wall, volume in caption |
| 003-bim_opening | bim_opening | GOOD | Door selected, ring on the real Window button |
| 008-bim_structure | bim_structure | GOOD | Slab selected, ring on Slab |
| 013-bim_profiles | bim_profiles | GOOD | "5 found"; last change stays selected (expected) |
| 014-bim_member | bim_member | GOOD | Steel beam framed, selected, ring on Beam |
| 015-bim_roof | bim_roof | GOOD | Roof framed, selected, ring on Roof |
| 017-bim_stairs | bim_stairs | GOOD | Stairs framed, selected, ring on Stairs |
| 018-bim_space | bim_space | GOOD | Roof and walls see-through, room shown, property right |
| 020-bim_level | bim_level | MINOR | Fit is on the level's label text, house not seen |
| 022-bim_building | bim_building | MINOR | Giant "Ground floor" label fills the view |
| 023-bim_list | bim_list | MINOR | "22 found"; same label framing as 022 |
| 024-bim_material | bim_material | MINOR | Inner wall seen, ring on Material; brick colour hidden by selection |
| 026-bim_layers | bim_layers | MINOR | Property only; nothing to see in 3D |
| 028-bim_ifc | bim_ifc | MINOR | Caption fixed; Plinth not selected; Tasks jumps to 2D geometry |
| 030-bim_rebar | bim_rebar | GOOD | Bars seen through see-through slab, walls, roof |
| 031-bim_covering | bim_covering | GOOD | Tiles selected, roof see-through |
| 032-bim_schedule | bim_schedule | MINOR | Caption "17 rows", but no schedule sheet shown |
| 034-bim_quantities | bim_quantities | GOOD | House schedule sheet in front, "20 rows" |
| 035-bim_edit | bim_edit | MINOR | Ring on Add Component for a cut, toolbar and Tasks |
| 037-bim_grid | bim_grid | BAD | Grid still only a short dashed line by the porch |
| 039-bim_structural_system | bim_structural_system | GOOD | Pads selected at grid points, property right |
| 041-bim_section | bim_section | GOOD | Section plane shown and selected, property right |
| 042-bim_views | bim_views | MINOR | Top plan view shown, "1 views"; plan not clearly selected |
| 043-bim_truss | bim_truss | MINOR | Truss faint through see-through house; cropped |
| 044-bim_fence | bim_fence | GOOD | Fence framed and selected |
| 045-bim_frame | bim_frame | GOOD | Portal framed and selected |
| 046-bim_curtain_wall | bim_curtain_wall | GOOD | Glazing framed, selected, ring on Curtain wall |
| 047-bim_panel | bim_panel | GOOD | Shelf framed, selected, ring on Panel |
| 048-bim_panel_out | bim_panel_out | MINOR | Cut outline drawn over the house corner; plain caption |
| 049-bim_pipe | bim_pipe | GOOD | Pipe framed, selected, ring on Pipe |
| 051-bim_pipe_connector | bim_pipe_connector | GOOD | Elbow framed close, selected, ring on Connector |
| 052-part_primitive | part_primitive | GOOD | Part wb, ring on Box, Sink block seen through roof |
| 053-bim_equipment | bim_equipment | GOOD | Sink selected and framed, property right |
| 054-bim_component | bim_component | GOOD | Sink as component selected, property right |
| 055-bim_ifc_brep | bim_ifc_brep | MINOR | Caption fixed; whole fit, nothing selected, Tasks 2D geometry |
| 056-bim_trash | bim_trash | MINOR | Caption fixed; Trash in property only, not in tree |
| 058-bim_reorder | bim_reorder | BAD | 3D view is a blank grey fill (65 mm wide) |
| 059-bim_preflight | bim_preflight | MINOR | Caption gives result; 3D view blank grey |
| 060-bim_export | bim_export | MINOR | "wrote house.ifc"; 3D view blank grey |
| 061-ifc_open | ifc_open | MINOR | Caption still "wrote house.ifc" for an open |
| 062-ifc_find | ifc_find | MINOR | "2 found"; blank grey view, nothing selected |
| 063-ifc_edit | ifc_edit | MINOR | Caption names Inner; blank grey view |
| 065-ifc_save | ifc_save | MINOR | Caption good; blank grey view |
| 066-ifc_diff | ifc_diff | MINOR | Caption now "1 changed"; blank grey view |
| 068-bim_import | bim_import | MINOR | Import selected but on top of old house; caption says "wrote" |

Counts: GOOD 22, MINOR 21, BAD 2 (round 3: GOOD 13, MINOR 25, BAD 7).

Round-4 numbers (BIM, 45):
- Ring visible: 28 (round 3: 21). On the real button for this call: 17 (001, 003, 008, 014, 015, 017, 018, 020, 022, 024, 028, 035 (wrong button), 046, 047, 049, 051, 052); round 3: 7. Kept from the last change: 2 (013, 023). On the toolbar "»" handle: 6 (030, 043, 044, 045, 053, 054); round 3: 12. Clipped at the right window edge: 3 (037, 041, 042). No ring: 17.
- Caption: 45/45. Tool name only: 0 (round 3: 6). Wrong words: 061 and 068 ("wrote" for open / import).
- Result selected: 25 clearly (plus 022, 026, 042, 048, 056 in the property view only).

### Round-3 BIM problems: status

| Round-3 problem | Status | Pictures |
|---|---|---|
| Roof never see-through | FIXED | 018, 024, 030, 031, 035, 039, 043: roof and walls see-through; room, bars, tiles seen. |
| Schedule sheet one call late | PARTLY | 032 now says "Listed ... 17 rows" (round4: no sheet asked), 034 shows the sheet. A user still sees no schedule at 032. |
| "House" stuck green | FIXED | No green "House" 024-068. The BIM panel row stays highlighted (Roof level 022-023, Ground floor 058-068). |
| Ring on toolbar overflow | PARTLY | Real button 17 (was 7); "»" handle 6 (was 12); clipped 3. |
| Level / building framing on the label | NOT FIXED, and WORSE | 020, 022, 023 on the label; 058-066 the view is a blank grey fill (65.9 mm x 41.9 mm). |
| bim_views / bim_panel_out not shown | PARTLY | 042 shows a top plan; 048 draws the cut outline at the origin, over the house. |
| Grid and truss not seen | PARTLY | Truss faint through see-through house (043). Grid NOT FIXED (037). |
| Tasks jumps to "2D geometry" | PARTLY | Still 028, 055; gone in 058-066. |
| DiffuseColor tracebacks | NOT FIXED | All 45; ArchCurtainWall from 046. |
| IFC captions | PARTLY | 066 now gives a count (FIXED); 061 still "wrote house.ifc" (NOT FIXED). |
| bim_ifc / bim_ifc_brep / trash / reorder tool-name captions | FIXED (words) | 028, 055, 056, 058 have real words; still nothing selected, tree not opened. |
| bim_import on top of the old house | NOT FIXED | 068. |
| Property view stale | FIXED | All BIM pictures show the new object. |

### BIM problems particular to this family (what the echo should do)
1. Blank grey 3D view from 058 to 066 (9 pictures): after bim_reorder on "Ground floor" the camera fits the level's tiny label (65 mm wide). For level / building / reorder calls fit the members of the level (or the whole building), never the BuildingPart's label.
2. Same root cause in 020, 022, 023: fit to the level's members.
3. Grid (037): fit to the grid's own lines and show them (they are only a dashed stub). Truss (043): fit the truss itself; it is cropped behind the house.
4. bim_edit cut (035): ring "Cut With Plane" (Arch_CutPlane), not "Add Component"; the Tasks list also lights Add Component.
5. bim_panel_out (048): the cut view lands at the origin over the house. Move it beside the shelf or frame it alone with the house hidden.
6. bim_schedule with no sheet (032): make and show the sheet, or say "no sheet asked" in the caption.
7. Rings still on the "»" handle for Rebar, Truss, Fence, Frame, Equipment, Component (6) and clipped at the right edge for Grid, Section, Views (3).
8. Captions: open and import should say "opened" / "imported", not "wrote" (061, 068).
9. bim_import (068): the import lies on the old house; make the old house see-through or move the camera to show only the import.

---

## 3. Mesh (21 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-meshobj_smooth | meshobj_smooth | GOOD | Globe smooth selected, ring on Smooth, Mesh Info filled |
| 002-meshobj_offset | meshobj_offset | GOOD | Globe plus selected, ring, Mesh Info filled |
| 003-meshobj_transform | meshobj_transform | GOOD | Cube big selected, Mesh Info filled |
| 007-meshobj_sections | meshobj_sections | GOOD | Rings inside see-through globe, ring on Sections |
| 009-meshobj_segments | meshobj_segments | MINOR | Cube mesh still selected; no segment colours; no count |
| 012-meshobj_curvature | meshobj_curvature | MINOR | Right mesh selected now; no colour map, no min/max |
| 014-part_wire | part_wire | GOOD | Stripe shown, property right, ring |
| 015-meshobj_project | meshobj_project | MINOR | Caption good; camera still inside the cube |
| 017-meshobj_primitive | meshobj_primitive | GOOD | CylA selected, ring on Primitives, Mesh Info |
| 019-meshobj_boolean | meshobj_boolean | MINOR | Pipe selected, small; caption names op, not Pipe |
| 025-meshobj_merge | meshobj_merge | GOOD | Lot selected, ring on Merge, Mesh Info |
| 026-meshobj_split | meshobj_split | MINOR | "3 pieces"; pieces not told apart; Lot 1 = whole Lot? |
| 028-meshobj_edit | meshobj_edit | GOOD | Crate (editing) selected, caption "Began editing Crate" |
| 029-meshobj_refine | meshobj_refine | MINOR | Mesh Info 20/36 (was 8/12); caption has no counts |
| 032-meshobj_export | meshobj_export | MINOR | No file name; ring on Add triangle (wrong) |
| 035-import_file | import_file | MINOR | Cube back selected but tiny, on old cube |
| 036-meshobj_info | meshobj_info | GOOD | Mesh Info numbers for Cube back |
| 037-part_from_mesh | part_from_mesh | GOOD | Cube solid framed; caption names Cube back |
| 038-part_primitive | part_primitive | GOOD | Can framed, selected, ring on Cylinder |
| 039-meshobj_unwrap | meshobj_unwrap | MINOR | Outline selected; framing cuts; blue blotches on cube |
| 041-meshobj_trim | meshobj_trim | GOOD | Cap in see-through globe, ring on Trim, Mesh Info |

Counts: GOOD 12, MINOR 9, BAD 0 (round 3: GOOD 7, MINOR 13, BAD 1).

Round-4 numbers (Mesh, 21):
- Ring visible: 16 (round 3: 1). On the right button: 13 (001, 002, 007, 009, 014, 017, 019, 025, 026, 028, 029, 038, 041). Doubtful: 003 (same button as Offset), 012 (on Segmentation, not Curvature), 032 (on Add triangle). No ring: 015, 035, 036, 037, 039.
- Caption: 21/21. Plain or without the number: 009, 019, 029, 032, 039.
- Result selected: 21 (012 in the tree only, not lit in 3D).

### Round-3 Mesh problems: status

| Round-3 problem | Status | Pictures |
|---|---|---|
| No ring on Mesh buttons | FIXED | 13 right rings (see above); 3 doubtful. |
| Curvature: wrong mesh, no map | PARTLY | Globe fine selected (FIXED); still no colour map, no min/max (012). |
| Segments hidden by selection | NOT FIXED | 009: Cube mesh still selected; colours not seen. Blue patches on the cube stay to 041 (015, 017, 019, 025, 039, 041). |
| Project camera too close | NOT FIXED | 015. |
| Copies on their source | PARTLY | 037 clean now; 035 still on the old cube; 039 blue blotches. |
| Split pieces not told apart | PARTLY | Caption "3 pieces" (026); no colours; Lot 1 shows 3706 points = all of Lot. |
| Captions (refine, export, part_from_mesh) | PARTLY | part_from_mesh FIXED (037); refine and export NOT FIXED (029, 032). |
| Old Report view text | NOT FIXED | All 21 (now BIM tracebacks from ArchHouse). |
| Property view stale | FIXED | 014 shows Stripe, 017 CylA, etc. |

### Mesh problems particular to this family (what the echo should do)
1. Segments (009): clear the selection after colouring so the colours show; give the segment count; remove the colours at the next changing call (blue patches stay on the cube to 041).
2. Curvature (012): ring the Curvature button (rainbow icon), not Segmentation; add min/max to the caption; show `view_render { map: "curvature" }` or the Mesh curvature plot.
3. Project (015): fit the cube and the line, not the line alone (camera is inside the cube).
4. Split (026): colour each piece; check the tool, since Lot 1 holds all 3706 points of Lot.
5. Export (032): ring nothing (or the Export button) and name cube.stl in the caption.
6. Captions: refine "12 -> 36 facets"; boolean "Made Pipe"; unwrap "Flattened Can.Face1".

---

## Counts per family

| Family | GOOD | MINOR | BAD | Round 3 GOOD/MINOR/BAD |
|---|---|---|---|---|
| Core | 18 | 27 | 4 | 7 / 31 / 11 |
| BIM | 22 | 21 | 2 | 13 / 25 / 7 |
| Mesh | 12 | 9 | 0 | 7 / 13 / 1 |

## Top problems left
1. Robot tools still show nothing (Core 0081, 0082, 0092).
2. BIM 3D view blank grey after bim_reorder (058-066) and level/building framing on the label (020-023).
3. object_appearance colours the links, not Block (Core 0032) — tool bug.
4. Leftover Bill of Materials task dialog in all 49 Core pictures.
5. BIM grid not seen (037); BIM DiffuseColor tracebacks in every BIM picture.
6. Mesh segments and curvature colours never shown (009, 012); blue leftovers to 041.

PROVEN_LIVE core: part_primitive, object_list, object_get, object_set, units_convert, object_rename, object_group, link_make, link_edit, object_duplicate, object_align, text_document, recompute, shape_query, measure, measure_keep, section, clearance, material_list, material_set, material_clear, insp_run, insp_read, insp_list, insp_update, insp_export, scad_status, scad_export, scad_import, scad_op, scad_tidy, robot_path, robot_run, export, import_file, doc_save_all, doc_merge, object_delete, doc_open
NOT_PROVEN core: object_appearance (Block stays grey), robot_new (robot invisible), robot_move (robot invisible), robot_tool (tool not shown), doc_info (caption says Renamed), doc_graph (no graph or count), object_freeze (nothing named or shown), measure_mass (volume, not mass), material_get (cut-off warning only), insp_faces (cut-off explanation only)
PROVEN_LIVE bim: bim_wall, bim_opening, bim_structure, bim_profiles, bim_member, bim_roof, bim_stairs, bim_space, bim_level, bim_building, bim_list, bim_material, bim_layers, bim_ifc, bim_rebar, bim_covering, bim_schedule, bim_quantities, bim_edit, bim_structural_system, bim_section, bim_views, bim_truss, bim_fence, bim_frame, bim_curtain_wall, bim_panel, bim_pipe, bim_pipe_connector, part_primitive, bim_equipment, bim_component, bim_ifc_brep, bim_trash, bim_preflight, bim_export, ifc_find, ifc_edit, ifc_save, ifc_diff, bim_import
NOT_PROVEN bim: bim_grid (grid not seen), bim_reorder (blank grey view, order not shown), bim_panel_out (cut outline over house, no sheet), ifc_open (caption says wrote)
PROVEN_LIVE mesh: meshobj_smooth, meshobj_offset, meshobj_transform, meshobj_sections, part_wire, meshobj_project, meshobj_primitive, meshobj_boolean, meshobj_merge, meshobj_edit, meshobj_refine, meshobj_export, import_file, meshobj_info, part_from_mesh, part_primitive, meshobj_unwrap, meshobj_trim
NOT_PROVEN mesh: meshobj_segments (no colours seen), meshobj_curvature (no colour map), meshobj_split (pieces not told apart)

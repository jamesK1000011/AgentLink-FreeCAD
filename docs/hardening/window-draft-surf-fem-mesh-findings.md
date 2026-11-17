# Window review: Draft, Surface, FEM, Mesh echo pictures

FreeCAD 1.1.3 with Agent Link. 67 pictures. I looked at each picture.

How I rated:
- GOOD: the window shows the result correctly. The only problem is a known general problem that is already being fixed, for example no caption.
- MINOR: the result is shown, but with a small problem.
- BAD: you cannot see the result, the window shows a different object, or error text shows in the window.

Problems that are in almost every picture (general; count them, do not repeat them in each row):
- G1: No caption or status words for the call. No picture shows text that says what was done.
- G2: No toolbar button is lit with a ring. (The FEM solver buttons have colour in 030-039, but that is because they are enabled, not because the echo lit them.)
- G3: Fit frames the whole document, not the new thing.
- G4: Old Report view text stays on screen from earlier calls. Example: the red Draft fillet error from 01:23:08, then from FEM 030 onward the red Agent Link traceback that ends with "RuntimeError: Cannot add static property". These lines are still on screen in all the Mesh pictures.
- G5: The Property panel (Data) shows the properties of an older object, not the new one. Examples: "FrameSide" in Draft 023-027 and "Wider" in Surface 016-047.

---

## 1. Draft (20 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-draft_plane | draft_plane | MINOR | Draft workbench, Top working plane, top view. The "Top" object is not selected. |
| 002-draft_shape | draft_shape | MINOR | Arc30 is shown but not selected. It is small in the view. |
| 006-draft_modify | draft_modify | MINOR | The upgrade made two wires (Wire, Wire001), not one shape. Both are selected. |
| 010-draft_link_array | draft_link_array | BAD | Hex is selected, not the new Ring array. The grey Frame face is behind everything. |
| 011-draft_dimension | draft_dimension | GOOD | ToHexTop is shown and selected (green). |
| 015-draft_style | draft_style | MINOR | No visible change from the style. The old dimension ToHubTop is still selected. The selected tree row is cut off at the bottom. |
| 023-draft_fix | draft_fix | BAD | The tool flipped ToHexTop, but FrameSide is selected and its properties show. The FrameSide text is cut off at the bottom of the view. |
| 024-draft_label | draft_label | MINOR | The HexArea leader shows, but the label text is too small to read. The Property panel shows FrameSide. |
| 027-draft_clone | draft_clone | MINOR | HexHalf is shown and selected (green). The Property panel shows FrameSide. |
| 060-draft_layer | draft_layer | BAD | The new layer is not shown or selected. MarkAtCorners is selected instead. Red fillet error in Report view. |
| 063-draft_hatch | draft_hatch | MINOR | The hatch is selected, but it is small in a whole-document view. |
| 065-draft_to_sketch | draft_to_sketch | MINOR | FrameSketch is selected, but it lies on top of Frame, so it looks the same as Frame. |
| 066-sketch_state | sketch_state | GOOD | Read tool. FrameSketch is selected and its properties show. |
| 067-draft_from_sketch | draft_from_sketch | MINOR | The new face is selected. The Property panel shows FrameSketch. The face is on the same plane as Frame, and the two flicker (z-fighting). |
| 068-part_primitive | part_primitive | GOOD | Part workbench. The Tag box is selected and its properties show. |
| 069-draft_2d_view | draft_2d_view | BAD | The TagTop projection is under the Tag box, so you cannot see it. The view is isometric, not top. The Property panel shows Tag. |
| 072-draft_facebinder | draft_facebinder | MINOR | TagSkin lies on the box top, so it is hard to see. The Property panel shows Tag. |
| 074-draft_fonts | draft_fonts | MINOR | Read tool. The font list does not show anywhere. A grey square plane appears around Tag. |
| 076-draft_text | draft_text | MINOR | The plate is selected, but "AL-7" is too small to read at whole-document zoom. The Property panel shows TagSkin. |
| 078-draft_array | draft_array | MINOR | The 2x2 grid of plates with text shows clearly. Nothing is selected. |

Counts: GOOD 3, MINOR 13, BAD 4.

### Draft-particular problems
- Wrong object selected after modify tools (010, 015, 023, 060). The echo keeps the selection of an earlier call, or it selects an input. It must clear the selection, then select the object the call made or changed. For draft_fix, select the dimension in the arguments (ToHexTop). For draft_layer, select the layer.
- The result is under or on top of its source (065, 067, 069, 072). Draft-to-sketch, from-sketch, facebinder and 2D view make a copy at the same place as the source. The echo should hide the source for a short time or make it transparent, or set the camera to the right direction (top view for draft_2d_view).
- Z-fighting (067, then in all later pictures): the face from draft_from_sketch flickers with the Frame face. Hide one of them, or move the new object off the plane a little.
- Text cannot be read (024, 076). For labels and text, zoom to the object so the letters can be read.
- The camera fits the whole tutorial page (010-078). Small results (Arc30, hatch, label, text) are tiny. Fit to the new object.
- draft_layer: the layer object is not shown. Select the layer in the tree and expand it, so you can see that Frame and Hex moved into it.
- Read tools (draft_fonts, draft_style): nothing in the window says what they did. Show the font list or style name in the caption.
- 074: a grey square plane appears near Tag (it looks like a left-over working-plane or grid). Find out which call made it and remove it.

---

## 2. Surface (15 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-part_wire | part_wire | GOOD | Part workbench. Line La is selected and its properties show. |
| 005-surface_boundary | surface_boundary | MINOR | Patch is selected (green) and fills the view. The Property panel still shows La. |
| 007-surface_fill | surface_fill | BAD | The window looks the same as 005. Filled is on top of Patch, Patch stays selected, and Filled has a plain Part icon, not a surface icon. |
| 011-surface_sections | surface_sections | BAD | Ruled is selected, but only one green edge shows. The Plate solid hides the surface. |
| 013-surface_extend | surface_extend | GOOD | Wider is selected (green), shows around Plate, and its properties show. |
| 016-part_primitive | part_primitive | MINOR | Block is selected (green). The Property panel shows Wider. Block is not visible in the tree (the tree does not scroll to it). |
| 017-surface_cut | surface_cut | BAD | Half is inside Block. Only a thin green line shows. Block is not hidden. |
| 021-surface_sew | surface_sew | MINOR | The sewn faces show green, but the source Cube is still visible under them. |
| 024-surface_thicken | surface_thicken | BAD | You cannot see Slab. It is inside Plate and Block and is not selected. |
| 028-surface_blend | surface_blend | MINOR | The blend curve is selected but very small at whole-document zoom. |
| 030-draft_shape | draft_shape | MINOR | The spline G1 is selected and shows clearly. The Property panel shows Wider. |
| 045-surface_loft | surface_loft | BAD | The large saddle surface fills the view. Panel is not selected and cannot be seen. |
| 047-surface_points | surface_points | BAD | The window looks the same as 045. You cannot see Fitted and it is not selected. |
| 049-meshobj_from_shape | meshobj_from_shape | BAD | Mesh workbench. The mesh is not shown or selected. An empty Mesh Info task panel opens and stays open. |
| 050-surface_polynomial | surface_polynomial | BAD | No change in the window. Quadric is not shown or selected. |

Counts: GOOD 2, MINOR 5, BAD 8.

### Surface-particular problems
- The result is hidden by other bodies (011, 017, 024). Surfaces are thin and lie inside solids (Plate, Block). The echo should hide or make transparent the other bodies near the result. For surface_cut, hide the cutting body ("by").
- The result is exactly on top of its input (007, 021). Hide the input surface or input Cube while the echo shows the result.
- The camera frames a large earlier object, not the new one (045, 047, 050). The test objects are far apart (the saddle is about 300 mm, Panel and Fitted are about 30-40 mm at y=100-220). Fit to the new object only.
- surface_fill (007): the result has a plain Part icon. Check that the tool makes a real Surface Filling feature. If it makes a plain shape, the echo cannot light the Filling button.
- meshobj_from_shape (049): opening the Mesh Info panel without data is a leftover. Close it, or fill it with the mesh numbers. This panel then stays open in most of the Mesh family pictures.
- The Property panel does not follow the selection (005-047). It shows La or Wider for many calls.

---

## 3. FEM (11 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 000-part_primitive | part_primitive | GOOD | Part workbench. The 8 m Box is selected and fills the view. |
| 001-material_set | material_set | MINOR | Material workbench. The window shows no sign of the material (no material object, colour or text). |
| 003-fea_setup | fea_setup | BAD | FEM workbench, but the tree shows only Box. There is no Analysis, solver, material or mesh object. |
| 005-fea_hold | fea_hold | BAD | No fixed-support marks on the x=0 face. There is no constraint in the tree. |
| 030-fea_modes | fea_modes | BAD | Red traceback in Report view (strength.py line 1403, native_mesh, makeMeshGmsh, "RuntimeError: Cannot add static property"). No mode shapes show. |
| 033-fea_load | fea_load | BAD | No gravity arrow or load shows. The tree is not changed. The same traceback shows. |
| 034-fea_solve | fea_solve | BAD | No result shows: no colour map, no deformed shape, and no result object in the tree. |
| 038-fea_refine | fea_refine | BAD | Nothing changes in the window. The traceback is still there. |
| 039-fea_shell | fea_shell | BAD | No shell, holds, pressure or mesh show. Only Box is selected in the tree. |
| 041-fea_parts | fea_parts | MINOR | Block is selected and touches Box. A hidden "FEA parts" object is added. The tie is not shown. |
| 042-fea_clear | fea_clear | MINOR | The solver buttons are grey again, so the analysis is gone. "FEA parts" is still in the tree. The traceback is still there. |

Counts: GOOD 1, MINOR 3, BAD 7.

### FEM-particular problems
- The FEM objects are not in the Model tree of FemWin (003-039). The solver buttons have colour in 030-039, so an active analysis exists. It is probably in a different document or hidden. The echo should put the Analysis in the user's document, expand it in the tree, and select the new member (constraint, mesh, solver, result).
- A mesh error is on screen (030 onward): Agent Link strength.py line 1403 calls makeMeshGmsh, and it fails with "Cannot add static property". This is a real tool bug, not only an echo problem. Every later FEM picture shows this traceback, and the Mesh pictures show it too.
- No FEM result is shown (030 fea_modes, 034 fea_solve). After a solve, the echo should show the result pipeline: a colour map for stress or displacement, a deformed shape, and the colour bar. For modes, show mode 1 with the frequency in the caption.
- Constraints and loads are not drawn (005 fea_hold, 033 fea_load, 039 fea_shell). Show the FEM constraint symbols on the faces or edges in the arguments.
- material_set (001): show the material name in the caption, or select the material object, or give the body the material colour.
- fea_clear (042): the "FEA parts" helper from fea_parts stays. Remove it, or say in the caption that it stays.

---

## 4. Mesh (21 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-meshobj_smooth | meshobj_smooth | BAD | "Globe smooth" is not selected and looks the same as Globe. An empty Mesh Info panel is open. |
| 002-meshobj_offset | meshobj_offset | BAD | "Globe plus" is not selected and cannot be told from Globe fine. Empty Mesh Info panel. |
| 003-meshobj_transform | meshobj_transform | MINOR | "Cube big" shows clearly, but it is not selected. |
| 007-meshobj_sections | meshobj_sections | BAD | The section rings do not show and are not selected. |
| 009-meshobj_segments | meshobj_segments | MINOR | Segment lines show on Cube mesh, but the segments do not have colours and are not selected. |
| 012-meshobj_curvature | meshobj_curvature | BAD | No curvature colour map on Globe fine. The window looks the same as 009. |
| 014-part_wire | part_wire | GOOD | Part workbench. Stripe is selected (green). The Mesh Info panel is closed. |
| 015-meshobj_project | meshobj_project | MINOR | The projected line shows on the top of the cube, but it is small and not selected. The Property panel shows Stripe. |
| 017-meshobj_primitive | meshobj_primitive | MINOR | CylA shows next to the cube. It is not selected. |
| 019-meshobj_boolean | meshobj_boolean | BAD | Pipe is on top of CylA and CylB, so you cannot see the hole. It is not selected. |
| 025-meshobj_merge | meshobj_merge | MINOR | Ring, Spike and Crate show. Lot is on top of them and is not selected. |
| 026-meshobj_split | meshobj_split | BAD | No change from 025. The split parts are not shown or selected. |
| 028-meshobj_edit | meshobj_edit | BAD | No edit mode shows on Crate (no highlight, no facet pick). |
| 029-meshobj_refine | meshobj_refine | BAD | No change in the window. The new triangles are not shown. |
| 032-meshobj_export | meshobj_export | MINOR | Export tool, so nothing changes in the 3D view. Nothing says that cube.stl was written. |
| 035-import_file | import_file | BAD | "Cube back" is not selected and is on top of the old cube. The window looks the same. |
| 036-meshobj_info | meshobj_info | BAD | The Mesh Info panel is open but empty. It does not show the numbers for "Cube back". |
| 037-part_from_mesh | part_from_mesh | MINOR | Part workbench. "Cube solid" is selected (green edges). It lies on top of the mesh cube. |
| 038-part_primitive | part_primitive | GOOD | Can is selected (green) and its properties show. |
| 039-meshobj_unwrap | meshobj_unwrap | MINOR | The flat outline shows, but it is not selected. Can stays visible. |
| 041-meshobj_trim | meshobj_trim | BAD | No visible change. Cap is not shown or selected. |

Counts: GOOD 2, MINOR 8, BAD 11.

### Mesh-particular problems
- Mesh results are never selected (all Mesh pictures except the Part ones). Mesh objects do not get the green selection in any picture. The echo must select the new mesh feature.
- New meshes are exactly on top of their source (001, 002, 019, 025, 035, 037). Copy=true makes a second mesh in the same place. Hide the source mesh, or move the camera to the new one and give it a different colour.
- The Mesh Info task panel opens and stays open, empty (surface 049, then mesh 001-041). In 036 (meshobj_info) it should show the point count, facet count and bounds, but it stays empty. Fill the panel with the call result, or close it after each call.
- Analysis tools show nothing (009 segments without colours, 012 curvature without a colour map). Show the segment colours and the curvature colour map with a legend, as the GUI tools do.
- Change-in-place tools look the same as before (026 split, 028 edit, 029 refine, 041 trim). Show the triangle edges (flat lines), colour the parts, or show the cut, so you can see the change.
- meshobj_edit begin (028): no edit state shows. The mesh should be highlighted and the caption should say editing is on.
- The FEM traceback is still in the Report view in all Mesh pictures. Clear or scroll the Report view when a new document starts, or add a line for each call.

---

## Counts per family

| Family | GOOD | MINOR | BAD | Total |
|---|---|---|---|---|
| Draft | 3 | 13 | 4 | 20 |
| Surface | 2 | 5 | 8 | 15 |
| FEM | 1 | 3 | 7 | 11 |
| Mesh | 2 | 8 | 11 | 21 |
| All | 8 | 29 | 30 | 67 |

## Tools proven live in the window (GOOD or MINOR, and the picture shows the result correctly)

Draft: draft_plane, draft_shape, draft_modify, draft_dimension, draft_label, draft_clone, draft_hatch, draft_to_sketch, sketch_state, draft_from_sketch, part_primitive, draft_facebinder, draft_text, draft_array.

Surface: part_wire, surface_boundary, surface_extend, part_primitive, surface_sew, surface_blend, draft_shape.

FEM: part_primitive.

Mesh: meshobj_transform, meshobj_segments (lines only, no colours), meshobj_project, meshobj_primitive, meshobj_merge, part_wire, part_from_mesh, part_primitive, meshobj_unwrap.

Rated MINOR but not proven, because the window shows nothing that confirms the result: draft_style, draft_fonts, material_set, fea_parts, fea_clear, meshobj_export.

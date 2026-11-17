# Window review: BIM family (45 pictures)

Folder: win/bim. FreeCAD 1.1.3, Agent Link echo. I looked at every picture.

Note on duplicates: 060, 061, 062, 063, 065 and 066 are the same file, byte for byte (same md5). 026 and 028 are also the same file. The window did not change between those calls.

Note on the Report view: almost every picture shows red `AttributeError: 'Gui.ViewProviderGeometryObject' object has no attribute 'DiffuseColor'` text from ArchWall.py line 1684 (and ArchCurtainWall.py line 794 from 046 on). This is one problem for the whole family (see "Family problems" #4). I do not count it again in each row unless the call itself added a new kind of error.

## Table

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-bim_wall | bim_wall | GOOD | Wall ring is shown, framed and selected (tree and 3D). |
| 003-bim_opening | bim_opening | MINOR | Door is shown and lit in 3D. Tree has no selected row; property panel is still "Outer walls". |
| 008-bim_structure | bim_structure | MINOR | Slab is shown and lit. Property panel is still "Outer walls". |
| 013-bim_profiles | bim_profiles | MINOR | Query only. No profile list is shown; the porch beam from an earlier call is still selected. |
| 014-bim_member | bim_member | GOOD | Steel beam is shown, lit, and the property panel shows it. |
| 015-bim_roof | bim_roof | MINOR | Roof is shown and lit. Property panel is still "Steel beam". |
| 017-bim_stairs | bim_stairs | MINOR | Stairs are shown and lit. A stray "Hip roof cw" sits on the ground beside them (leftover from an earlier call). |
| 018-bim_space | bim_space | BAD | The "Living room" space cannot be seen at all (inside the house, under the roof). Nothing is selected. |
| 020-bim_level | bim_level | MINOR | "Ground floor" is selected in the tree and the BIM panel. Nothing is lit in 3D; property panel stale. |
| 022-bim_building | bim_building | MINOR | House/Plot are made and selected in the tree. Property panel stale ("Steel beam"). |
| 023-bim_list | bim_list | MINOR | Query only. No list is shown; the window is the same as 022. |
| 024-bim_material | bim_material | BAD | Inner wall should turn brick red; it is hidden under the roof. The material is not selected. "House" is stuck green in the tree. New DiffuseColor errors. |
| 026-bim_layers | bim_layers | BAD | No visible change. Property panel is empty. Nothing selected. |
| 028-bim_ifc | bim_ifc | BAD | Same picture as 026. Plinth is not selected; the IFC type change is not shown. |
| 030-bim_rebar | bim_rebar | BAD | Bars are not seen (inside slab). Report view says "Cannot calculate rebar length from its base object". |
| 031-bim_covering | bim_covering | BAD | Floor tiles are under the roof; only a thin green slab edge shows. |
| 032-bim_schedule | bim_schedule | BAD | The schedule sheet is not opened. The 3D view is unchanged. |
| 034-bim_quantities | bim_quantities | MINOR | Query only. No quantities table or caption is shown. |
| 035-bim_edit | bim_edit | BAD | The cut of "Inner wall" is under the roof and cannot be seen. New DiffuseColor errors. |
| 037-bim_grid | bim_grid | BAD | The grid cannot be seen. "Porch column 2" from an earlier call is lit instead. |
| 039-bim_structural_system | bim_structural_system | MINOR | Pads are shown at the grid points. They are not lit; the grid is still invisible. |
| 041-bim_section | bim_section | MINOR | The section plane is shown and lit. Property panel stale ("Pad"). |
| 042-bim_views | bim_views | BAD | The "Ground floor plan" view is made but no 2D plan or page is shown; only a faint outline in 3D. |
| 043-bim_truss | bim_truss | BAD | The truss cannot be seen (behind the house) and is not selected. Window is nearly the same as 042. |
| 044-bim_fence | bim_fence | MINOR | Fence is shown and lit. Property panel stale ("Ground floor plan"). |
| 045-bim_frame | bim_frame | MINOR | Portal frame is shown and lit. Property panel stale. |
| 046-bim_curtain_wall | bim_curtain_wall | MINOR | Glazing is shown and lit. New ArchCurtainWall colorize error in Report view. |
| 047-bim_panel | bim_panel | MINOR | Shelf is lit but very small (whole document fit). |
| 048-bim_panel_out | bim_panel_out | BAD | The cut sheet / layout is not shown. Window is the same as 047. |
| 049-bim_pipe | bim_pipe | MINOR | Pipe is lit but very small. |
| 051-bim_pipe_connector | bim_pipe_connector | BAD | No elbow can be seen. Property panel shows "Pipe B", not the connector. |
| 052-part_primitive | part_primitive | MINOR | Part workbench is right; tree is expanded. The box is inside the house; only a small green part shows through the gable. |
| 053-bim_equipment | bim_equipment | MINOR | Property panel shows "Sink". The sink is mostly hidden inside the house. |
| 054-bim_component | bim_component | MINOR | Property panel shows "Sink as component". Same hidden-object problem as 053. |
| 055-bim_ifc_brep | bim_ifc_brep | BAD | No visible change from 054. There is nothing to show that the setting is on. |
| 056-bim_trash | bim_trash | MINOR | Sink is gone from 3D. The trash folder is not shown in the tree. |
| 058-bim_reorder | bim_reorder | MINOR | "Ground floor" stays closed in the tree, so the new order is not shown. |
| 059-bim_preflight | bim_preflight | MINOR | Query only. No preflight report or caption is shown. |
| 060-bim_export | bim_export | MINOR | Report view says "Finished exporting in 2 seconds". Also a new rebar error line. |
| 061-ifc_open | ifc_open | BAD | Same picture as 060. The IFC file is not opened in a new tab. |
| 062-ifc_find | ifc_find | BAD | Same picture as 060. No IfcWall is found or selected. |
| 063-ifc_edit | ifc_edit | BAD | Same picture as 060. The edited wall is not shown or selected. |
| 065-ifc_save | ifc_save | BAD | Same picture as 060. No sign of the save. |
| 066-ifc_diff | ifc_diff | BAD | Same picture as 060. No diff is shown. |
| 068-bim_import | bim_import | BAD | The import seems to lie on top of the old model in the same document (house looks changed). No new tab, nothing selected, no new group in the tree. |

## Counts

- GOOD: 2
- MINOR: 23
- BAD: 20

Known general problems (counted, short):
- No caption or status words in any of the 45 pictures (45/45).
- No lit toolbar button with a ring in any picture (45/45).
- Fit frames the whole document: 47, 49, 51 and later make small things very small.
- Property panel shows an earlier object (stale) in about 20 pictures.
- Model tab is in front in all pictures (good).

## Family problems (particular to BIM)

1. **IFC tools leave no mark in the window (061, 062, 063, 065, 066).** All five pictures are the same file as 060. The echo should: ifc_open: open the IFC file in its own document tab and fit it; ifc_find: select the found entities and fit them; ifc_edit: select the edited entity and show its changed property in the property panel; ifc_save: show the saved path in the caption; ifc_diff: show a short added/removed/changed count in the caption and select the changed entities.
2. **Results hidden inside the house or under the roof (018, 024, 030, 031, 035, 052-054).** Space, material, rebar, tiles, wall cut and the sink are all inside the closed house. The echo should make the other objects see-through (or hide the roof and the Roof level) while it shows the result, or use a section cut at about 1.2 m, then fit to the new thing only.
3. **Outputs that are not 3D are not opened (032, 042, 048, and the queries 013, 023, 034, 059).** The echo should open the schedule spreadsheet, show the plan view (2D view or a page), show the panel cut sheet, and put query results (profile list, object list, quantities, preflight result) in the caption or the Agent Link panel.
4. **Red error text in the Report view on nearly every picture.** `DiffuseColor` AttributeError from ArchWall.py:1684 and ArchCurtainWall.py:794 (FreeCAD 1.1.3 BIM code). Also "Cannot calculate rebar length from its base object" (030, 060), which may mean the rebar is not right. The echo should either clear the Report view before each call or the add-on should avoid the code path that fires this (for example, set colours through ShapeAppearance, not DiffuseColor). The rebar error needs a real check.
5. **Things made but not seen (037 grid, 043 truss, 051 elbow, 055 IFC brep).** The grid lines and the truss are not drawn where the camera can see them, and the elbow is too small to see. The echo should fit to the new object, and for the grid make sure the axes are visible (enough length, a visible colour).
6. **Leftovers and stuck selection.** A second roof, "Hip roof cw", sits on the ground from 017 to the end. "House" stays green in the tree and the BIM panel from 024 to the end, and "Porch beam" (013) and "Porch column 2" (037) stay lit from earlier calls. The echo should clear the old selection before it selects the new thing, and test runs should delete stray objects.
7. **bim_import puts the model on top of the old one (068).** It should open into a new document (or a new group), select the import and fit to it.
8. **bim_reorder (058) and bim_trash (056) do not show the tree change.** The echo should expand the reordered group and show the Trash folder in the tree.

## Tools proven live in the window (GOOD or MINOR, result seen)

bim_wall, bim_opening, bim_structure, bim_member, bim_roof, bim_stairs, bim_level, bim_building, bim_structural_system, bim_section, bim_fence, bim_frame, bim_curtain_wall, bim_panel, bim_pipe, bim_trash, bim_export (Report view line only), part_primitive, bim_equipment and bim_component (weak: object mostly hidden; property panel is the proof).

Not proven, even though rated MINOR: bim_profiles, bim_list, bim_quantities, bim_preflight, bim_reorder (no result is visible in the window).

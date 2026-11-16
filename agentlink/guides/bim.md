<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Buildings (BIM / Arch)

All sizes are mm; quantities come back in m, m² and m³ (`volume_m3`, `area_m2`), except the `bim_gaps` tools, which answer `volume` in mm³. Z is up. Every changing tool recomputes and answers `box` (size) and `min` (its lowest corner), so where a thing landed is in the reply; `health` rides along when something went red.

## workflow
1. Walls: `bim_wall { points, closed, width, height, align }`, one call for a run of walls or one per wall. Give `z` in the points for an upper storey. A wall along a sketch follows it (`base`).
2. Openings: `bim_opening { wall, kind, width, height, at, sill }`. `at` is the opening's left edge, in mm along the wall's line from its first point. `wallCut_m3` above 0 shows the wall was cut.
3. Structure: `bim_structure` makes a `column` (at: the centre of its foot), a `beam` from–to (its centre line), a `slab` rising from an outline, or a `footing` hanging below one. `bim_member` puts a library section (`bim_profiles`) between two points.
4. Roof, stairs and rooms: `bim_roof` over a closed outline at the eaves (90 on an edge makes a gable end); `bim_stairs` (check `blondel`, 600–650 mm); `bim_space` for each room's floor area.
5. Order: `bim_level` for each storey (its `objects`, `elevation`, `height`), then `bim_building { levels }`, which puts it on a site too.
6. Check: `bim_list` shows the tree; `bim_schedule` gives quantities with totals (`sheet: true` writes a spreadsheet); `bim_quantities` groups by IFC type or material with mass.
7. More: `bim_frame` (a library section along a path), `bim_truss`, `bim_fence`, `bim_covering`, `bim_layers` (a build-up of materials), `bim_ifc` (IFC type, classification, property sets), `bim_edit` (add, subtract, cut by a plane, join walls, clone).
8. Exchange: `bim_preflight`, then `bim_export` writes IFC and reads it back by class; `bim_import` reads one in.

## traps
- `align: "left"` means the line is the wall's left face as you walk from the first point to the last, so the wall lies to the right of the line; `right` is the other way; `center` straddles it. For outside dimensions on a counter-clockwise outline use `right` (the wall grows inwards)… and check `box`.
- `at` + width must stay on one straight stretch of the wall; an opening across a corner is refused. `sill` + height must stay under the wall's height.
- `bim_opening` builds one plain window or door (a frame round a pane or a panel) whatever `preset` says, and cuts the wall with a box listed in the wall's Subtractions. FreeCAD's own preset windows are not made by any tool here.
- A level does not lift what it holds: BIM components keep their own Z, so build the upper storey's walls on points with that `z`. Plain shapes put in a level are moved up by its elevation.
- A roof's outline is straight edges, one pane per edge; `angle` and `run` lists follow the outline's order. A roof does not cut the walls under it: `bim_edit { op: "cut", object, at, normal }` trims a wall under a pitch, or `bim_edit { op: "subtract", object: wall, with: [roof] }` takes the roof and everything above it out of the wall.
- A slab from `points` always rises from the outline, whichever way round the corners run. From `base` it follows the sketch's own up direction.
- Face and edge numbers (`"Slab.Face6"`) change when an object is rebuilt: read them fresh before `bim_covering` or `bim_reextrude`.
- `bim_schedule` and `bim_quantities` read shapes; they are Agent Link's own take-offs, not FreeCAD's schedule object.
- A window's or wall's label can be reused by FreeCAD with a number added (`Wall001`): take labels from the replies.

## more elements
- `bim_curtain_wall`: glazing along points, with mullions about every `vertical` / `horizontal` mm (each straight stretch gets the same count).
- `bim_rebar`: straight bars in a slab, beam, column or footing (`along`, `layer`, `cover`, `spacing`), laid out in the structure's bounding box. It answers the steel's total length and mass.
- `bim_panel` (sheet material), `bim_pipe` (along points) with `bim_pipe_connector` (an elbow or tee where pipes' ends meet), `bim_equipment` (any object made a fixture or furniture), `bim_grid` (grid lines; `"Grid X"` stands at x positions and runs along Y) with `bim_structural_system` (a column on every crossing).
- `bim_material` makes a material with its density and puts it on components. `bim_section` makes a section plane: `td_bim` draws it on a page; `export { section: z }` writes a plan cut as DXF/SVG; `bim_views` makes flat plan views of the levels.
- `bim_member` answers mass and kg/m (root radii left out, so a little light).
- Panels to the cutter: `bim_panel_out { kind: "cut" }` gives each panel's outline, `kind: "sheet"` lays them on a stock sheet; `bim_nest` nests flat single-face pieces into a sheet face (slow; no margin in FreeCAD 1.1).
- Tidying: `bim_component` (a shape made a BIM object, clones), `bim_remove_shape`, `bim_reextrude`, `bim_rewire`, `bim_glue`, `bim_trash`, `bim_reorder`, `bim_ifc_brep`, `bim_reference`, `bim_image_plane`, `bim_library`.

## IFC
- IFC needs IfcOpenShell inside FreeCAD. Without it `bim_export` and `bim_import` refuse with `unavailable` and the install step (the person's: the BIM workbench's Setup command, then a restart), and the `ifc_` tools are not offered at all.
- `bim_export` writes metres (FreeCAD's IFC preference) from a model in mm; `readBack` counts what the file holds by class. No site or building? FreeCAD adds default ones on export.
- An IFC from someone else (an architect's model, a survey) is edited as a file, not converted: `ifc_open { path }`, `ifc_find` (class, name, storey, a property's value), `ifc_edit` (attributes, property sets, material, storey, classification), `ifc_remove` (by GlobalId), `ifc_save` (a copy by default; `overwrite: true` writes it back). GlobalIds and everything not touched stay as they were, so the file can go back to whoever sent it. Edits live in memory until `ifc_save` and are outside undo.
- `ifc_diff { a, b }` lists what changed between two versions (data only, not geometry). To look at one, `bim_import` it and `view_render`.

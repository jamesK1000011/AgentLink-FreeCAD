# Start here: Agent Link for FreeCAD
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

## The shape of a session
- `session_state` first: what the document holds and the step count.
- Tools come in groups. `tool_groups` lists them and turns them on. Every tool can be called by name whether it is listed or not.
- Every change is one undo step: `history_undo`, `history_redo` (and checkpoints where an add-on offers them). `history_diff` says what a change did, so you don't have to describe the part again.
- `batch` runs several calls in one, rolled back whole if one is refused. Use it for a run of edits you can predict.
- Answers are in millimetres, grams and degrees. A refusal names what to change.

## A part, made and judged
1. Make it with the modelling tools: `pd_body_new`, `sketch_new`, `pd_pad` …, or `part_primitive`. Add-ons may add generators of their own; `tool_groups` lists them.
2. Ask how it will be made. Don't assume a part is printed.
3. Ask what it is made of and record it: `material_set`.
4. `body_check` after every change. Look too: `view_render { views: "all" }`, and `{ map: "wall" }` or `{ zoom: { at } }` on a spot.
5. Write `export_file` for STEP or STL. Starting a print or a cut is the person's call.

## What is here, by task
| The person wants | Tools | Guide |
|---|---|---|
| A parametric part they can change later | `pd_body_new`, `sketch_new`, `sketch_add`, `pd_pad` … , `param_set` | `model`, `sketch`, `feature`, `param` |
| A table of values, sizes in variants (S/M/L), a CSV in or out | `sheet_set`, `sheet_read`, `sheet_table`, `sheet_import` | `sheet` |
| Lettering, a logo from SVG/DXF, copies of a part | `draft_text`, `draft_outline`, `draft_array` | `draft` |
| A curved panel, a shape through points, a surface made solid | `surface_loft`, `surface_points`, `surface_fill`, `surface_thicken` | `draft` |
| Will it break, shake or get too hot | `fea_setup` … `fea_solve`, `fea_modes`, `fea_heat` | `strength` |
| What it weighs, its centre of mass, the gap between two parts | `measure_mass`, `clearance` | `measure` |
| A TechDraw page built piece by piece: sections, details, tolerances, GD&T, title block | `td_page`, `td_view`, `td_section`, `td_dim`, `td_gdt`, `td_export` | `techdraw` |
| A point cloud: read, cropped, a plane / sphere / cylinder / surface fitted through it | `points_import`, `points_crop`, `points_fit`, `points_export` | `points` |
| How far a made part or a scan is from the design, in tolerance or not | `insp_run`, `insp_read`, `view_render { map: "inspection" }`, `insp_export` | `inspection` |
| OpenSCAD: a .scad or .csg in, code run, CSG out, a hull | `scad_import`, `scad_code`, `scad_export`, `scad_op` | `start` |
| A robot arm: reach along a path, KUKA KRL out | `robot_new`, `robot_path`, `robot_trajectory`, `robot_run`, `robot_export` | `start` |
| A building: walls, windows, doors, slabs, roof, stairs, rooms, levels, quantities, IFC | `bim_wall`, `bim_opening`, `bim_structure`, `bim_roof`, `bim_level`, `bim_schedule`, `bim_export` | `bim` |
| Parts put together, a lid on its box | `asm_new`, `asm_joint`, `asm_check` | `assembly` |
| Toolpaths and G-code for a mill | `cam_job`, `cam_op`, `cam_sim`, `cam_post` | `cam` |

## Add-ons
- Add-ons installed beside Agent Link (printing, scans, drawings, electronics …) bring their own tool groups and guides: `tool_groups` and `guide_read` with no topic list them. Read an add-on's guide before using its tools.

## Refusals
Every refusal is `{ error: { code, message } }`; the message says what to change. By code:

| Code | Means | Do |
|---|---|---|
| `invalid_input` | An argument is wrong: a type, a value out of range, an unknown field, a name that is not there | Read the message, correct that argument, call again |
| `invalid_state` | The call is right but not now: no study set up, a parameter bound | Do the step it names first |
| `not_found` | No body, feature, face, guide or tool by that name | `session_state`, `object_list`, `feature_list` or `tool_groups` for the names there are |
| `unavailable` | Something this computer lacks: a program, the FreeCAD window, a module | Say so to the person; the message names what to install or set |
| `failed` | It ran and did not work: a boolean, a fillet, a mesh, a solve. Nothing was kept | Change the input (a smaller radius, another face, a coarser mesh); never send the same call again unchanged |

- A batch stops at the first refusal and rolls back what it did (`rollback: false` keeps it): fix that call and send the batch again.
- If FreeCAD itself stops (the answer says it was started again), the document was lost: `session_state`, then make the part again or `doc_open` what was saved. The same call doing it again means the call is the cause.

## Keeping answers small
- `view_render` pictures at the default size; `inline: false` writes the file only.
- `object_get` with `filter`.
- `batch` for runs of predictable calls: one answer instead of many.

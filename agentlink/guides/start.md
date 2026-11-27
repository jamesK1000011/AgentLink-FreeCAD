# Start here: Agent Link for FreeCAD
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

## The shape of a session
- `session_state` first: what the document holds and the step count.
- Tools come in groups. `tool_groups` lists them and turns them on. `tool_groups { group }` gives one group only, with its tools; `detail: true` gives the full text of each group. Every tool can be called by name whether it is listed or not.
- The way to a tool is find, card, call. `tool_groups { find: "fillet edges" }` searches every tool by what it does — plain words, or FreeCAD's own names for the command or workbench ("PartDesign_Fillet", "techdraw", "drawing dimension") — and answers a few names with a line each. `tool_groups { card: name }` (up to 20 names) gives the description and inputs. Then call the tool by name (or in a `batch`): it runs unlisted.
- `tool_groups { now: true }` (alone, or with `find`) puts first the tools that fit what is in front: the active workbench, a sketch open in edit, the selection, and whether FreeCAD's own command for the tool is active just now. Without a window it goes by the document's objects only.
- `enable: [group]` lists a whole group and loads every description in it: do that only when a task uses most of the group (a drawing, a sketch-and-pad part), not for one tool.
- Every change is one undo step: `history_undo`, `history_redo` (and checkpoints where an add-on offers them). `history_diff` says what a change did, so you don't have to describe the part again.
- `run { tool, <its inputs> }` runs one call and gives its full answer. `batch { calls: [step, step] }` runs many calls, one at a time, in order, with a full answer for each. `fast { calls: [step, step] }` does the same and gives one short answer. A step is flat: `{ tool: "pd_pad", sketch: "Sketch", length: 6 }`. `each: { x: [15, 45] }` on a step runs it once for each value (`"$x"`). If one is refused, the calls before it stay and the rest do not run: the answer says which (done, refused, notRun). Use `batch` for a run of edits you can predict.
- A long read (a heavy one, one slow here before, or any read with `background: true`) runs as a job: its answer comes back as usual when it ends within 45 s, else a job id — `job_status { job, wait: 25 }` gives the answer when it is done. A client drops a call after about 80 s, so never just call a long read again. While a job reads the document, changes to it are refused until it ends.
- Answers can stay out of the conversation. In a batch, a call with `writeTo` — `{ tool: "sketch_state", sketch: "Sketch", writeTo: "outline.json" }` — writes its whole answer to that file in the session's folder, and the reply keeps only where it is and its keys. A later call takes what it needs from it: `{ "$file": "outline.json", "$at": "loops.0.points" }` anywhere inside its inputs is replaced by that part of the file (a dotted path of keys and list indices from 0) as the call is about to run. `{ "$from": 2, "$at": "bodies.0.name" }` does the same from the answer of call 2 of the same batch. A reference that cannot be followed refuses that call and says what is there.
- `batch { build: "end" }` recomputes once for a run of `sketch_add`, `sketch_constrain`, `sketch_edit`, `sketch_offset` and `object_set` calls instead of after each. Their answers say `build: "held"` and leave out what only the rebuilt shape tells (a sketch's wires and `readyForFeature`); the batch's `builds` carries the one health reading after the recompute. Any other tool builds first and runs as always.
- A long batch (many points, many calls) can live in a file: write the list of `{ tool, <its inputs> }` to a .json in the session's folder and send `batch { path }`.
- Answers are in millimetres, grams and degrees. A refusal names what to change.
- Read `result` first: one line of what changed and where.

## A part, made and judged
1. Make it with the modelling tools: `pd_body_new`, `sketch_new`, `pd_pad` …, or `part_primitive`. Add-ons may add generators of their own; `tool_groups` lists them.
2. Ask how it will be made. Don't assume a part is printed.
3. Ask what it is made of and record it: `material_set`.
4. `body_check` after every change (a Body with AllowCompound true, FreeCAD's default, may hold several solids: each is checked). Look too: `view_render { views: "all" }`, and `{ map: "wall" }` or `{ zoom: { at } }` on a spot.
5. Write `export` for STEP or STL (or any format it lists). Starting a print or a cut is the person's call.

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

- A batch stops at the first refusal; what ran before it stays (`rollback: true` takes it all back): fix that call and send it with the calls after it in a new batch, as the note lists them (leave `from` out).
- If FreeCAD itself stops (the answer says it was started again), the document was lost: `session_state`, then make the part again or `doc_open` what was saved. The same call doing it again means the call is the cause.

## Keeping answers small
- `view_render` pictures at the default size; `inline: false` writes the file only.
- `object_get` with `filter`.
- `batch` for runs of predictable calls: one answer instead of many.
- In a batch, `to` on a call and `$file` / `$from` in a later one pass an answer from call to call without it being sent here and back; `batch { to }` keeps a whole run's answers in a file.
- `guide_read` with no topic gives what each guide and section costs. Read a guide's `Start here` section first where it has one, and the sections it lists under `later` only when their moment comes; `section` takes a list, and `topic` a list to read several guides in one call.

# Toolpaths and G-code (CAM)
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

FreeCAD's CAM workbench makes the paths; these tools set it up, read each path back and write the G-code. Everything is millimetres and mm/min; Z is the body's own Z.

## The workflow
1. Ask the person: the machine's controller (grbl, linuxcnc …), the end mill (diameter), feeds and speeds for the material, how the stock is held and where it is zeroed.
2. `cam_job { body, tool, stock }` — the stock round the part with a margin and a little on top; the end mill. FreeCAD works on a clone of the body inside the job (`model` in the reply); face names are the same as on the body.
3. Operations, roughest first, each computed as it is added — read its `cutZ` and `minutes`:
   - `face` — the top flat, when the stock has some on top.
   - `adaptive` — clearing a lot of material steadily (inside a pocket, or outside round the part).
   - `pocket { faces }` — down to a pocket's floor: give the floor face.
   - `profile { side: "outside" }` — round the outline, last, to size.
   - `drill` — every hole, or the faces given. FreeCAD drills with the job's first tool unless given another; a hole the tool is not smaller than is refused.
4. `cam_list` — every operation and the total time.
5. `cam_sim` — the operations run on the stock (3-axis, from above): rapids through stock (crashes), cuts into the part (gouges) or under the stock, and what is left over the part, with a picture from above (blue gouged, green right, red left over). Fix anything in `findings` before posting.
6. `cam_post { post }` — the G-code file. Read its `warnings`, `tools` and `fixtures`.

## traps
- Z is the part's: the stock's top is `stock.max[2]`. Zero the machine where the job does.
- `finalDepth` is a height (a Z value), not a depth below the top: a pocket 8 mm deep in a 20 mm part ends at `finalDepth: 12`.
- Face names (`"Face6"`) change when the body is rebuilt; a job made before the change still holds the old clone. Find faces with a query (`{ normal: [0, 0, 1], z: 12 }`) instead of a remembered number.
- A tool bigger than a pocket's corners or a hole leaves them uncut — the op answers with fewer cutting moves or refuses. `cam_tool` changes the job's first tool and recomputes everything.
- `profile` cuts to the part's bottom: with the stock on a spoil board that is right; on a vice set `finalDepth` above the jaws and hold the part with tabs (`cam_dressup { kind: "tags" }`) or leave a skin.
- The time is an estimate at the feeds given, rapids at 3000 mm/min.
- `cam_post` posts as FreeCAD's own Post command: the work offset first (`G54`), a tool change where the tool changes (grbl and marlin write `M6` as a comment, since those controllers do not take it), the active operations in the job's order. Units are millimetres (`G21`) with feeds per minute.
- The G-code is checked against the stock, not run. The person checks it in their controller's preview before it runs; running it is theirs.
- These need FreeCAD's window and are refused `unavailable` without it: ramp and lead-in/out dressups on some builds, Path from Shape with a tool controller.

## More operations, tools and dressups
- More kinds of `cam_op`: `engrave` and `vcarve` follow `base` (letters from `draft_text`, a sketch); `helix` mills holes; `slot`; `deburr`; `thread` mills a thread (`props` for its size). `surface` and `waterline` are 3D finishing, and need OpenCamLib.
- More than one tool: `cam_tool_add { shape: "v-bit", diameter, angle }`, then `cam_op { tool }` per operation. Ask the person what is in their tool rack; never assume. `skipped` in the reply names a size that shape does not have. `cam_library` keeps the set in a JSON file between documents.
- `cam_dressup { op, kind: "tags", count, width, height }` adds holding tabs, so a profiled part stays in the stock. `dogbone` clears inside corners so a square part fits; `boundary` keeps moves inside the stock. Adaptive ops enter helically without a ramp dressup.
- `cam_setup` sets work offsets (`fixtures`: the job is posted once in each), coolant, safe heights (mm above the stock's top) and the order the ops run in.
- `cam_edit` copies an op (props on the copy), turns one off, drops a comment or a stop (M0/M1) into the G-code after an op, or sets an op's start point. `cam_remove` takes an op out with its dressups.
- `props` on any op sets its own FreeCAD properties by name (`object_get` lists them): `Direction` (CW | CCW), `UseComp`, `OffsetExtra`, `StartDepth`, `SafeHeight`, `ClearanceHeight`, for what these tools don't name.
- `cam_path` makes the plain path objects (an area, a path along a wire, a compound, an array, a stop, a fixture change); `cam_property_bag` holds named values for expressions; `cam_template_export` writes the job's setup as a template for FreeCAD's New Job dialog.

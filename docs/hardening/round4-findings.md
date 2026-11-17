<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Echo, fourth window pass (round 4): what was changed and why

Source: the round-3 picture reviews (`window-r3-pd-sk-asm-findings.md`, `window-r3-part-core-pts-sheet-findings.md`,
the Draft and Surface sections of `window-r3-draft-surf-ws-tex-tutor-findings.md`, `window-r3-bim-mesh-findings.md`,
`window-r3-td-cam-fem-findings.md`; no ScanRuler review was there) against the claims in `echo3-findings.md` and
`famfix-findings.md`. FreeCAD 1.1.3 source, read only. No FreeCAD ran here: "test" means a test with stand-ins or
a plain rule, never a live check. Line numbers are of this branch.

Files: `agentlink/echo.py`, `agentlink/activity.py`, `agentlink/gui_link.py` (one guard),
`agentlink/families/techdraw.py` (the leader's shoulder), `agentlink/data/activity.json`,
`agentlink/data/tools.json` (td_weld's leader; fea_hold and fea_load answer `window`),
`agentlink/data/tool_index.json` (regenerated: `scripts/tool_index.py`), new `tests/test_echo_rings.py` (22 tests),
changed `tests/test_echo_window.py` (the overflow test to the new rule), `tests/test_datafem_data.py` (the meant
`window` difference). `scripts/tool_needs.py --check` passes; no `tests/test_needs.py` pin moved.

## Rules kept

- The echo never raises into a call: every new step runs in `_step` or has its own `try`. It does nothing
  without a window (`_on`). Nothing new changes saved content beyond what round 3 already did: view
  providers' `Transparency` (put back at the next change) and `Visibility` (datums, sketches, inspection
  results, a CAM op's original body), and scene-only colours (FEM result, mesh segments).
- Nothing new is deferred: no timer, no `later`. `views_follow` restarts FreeCAD's own pending timers at 0 ms
  and runs the event loop twice, inside the call.

## 1. Rings

### Cause, per family (certain, from the code)

- Mesh, Surface, Points, Spreadsheet: **no command was mapped** for any of their tools (`echo.py` at main:
  `COMMAND` had no `meshobj_`, `surface_`, `points_`, `sheet_` key). Their one ring per run was a kept
  `part_primitive` / `pd_*` ring.
- Part, core, Draft, TechDraw annotations, FEM, CAM: most tools unmapped (Part 12 of 32, core 6 of 57).
- Near misses: `part_primitive` lit the Primitives dialog for a box, `part_boolean` the general Boolean,
  `fea_load` lit Force for gravity: no mapping by the asked kind.
- BIM: 21 of 53 mapped; of those, the 3D/BIM toolbar (`src/Mod/BIM/InitGui.py` 108-131 plus
  `BIM_GenericTools`, 22 buttons) does not fit the window, so Qt moves its tail into the toolbar's "»" list.
  Wall, Space, Level and Building are at its head (on screen); Window, Beam, Roof, Stairs, Panel, Frame, Fence,
  Truss, Equipment, Pipe, Rebar are in the "»" list. That is a true overflow. But `overflow_flash` (main
  `echo.py` 817) lit "»" for **any** button that was not visible, also one on a toolbar the person hid or a
  button its toolbar hides for its own reason.

### Change

- `COMMAND` (second `COMMAND.update`, `echo.py` 110-205): every family's tools to the button on its bench's
  toolbar, from the 1.1.3 sources (Mesh `Gui/Workbench.cpp` 239-293, Surface 63-77, Points 46-58, Spreadsheet
  238-264, Part 170-220 with its dropdowns, BIM `InitGui.py` 74-421, Draft `draftutils/init_tools.py`, TechDraw
  and FEM `Gui/Workbench.cpp` setupToolBars, CAM `InitGui.py` 127-269, Std `src/Gui/Workbench.cpp` 830-885).
  A tool whose command is in a dropdown lights the dropdown's button (`targets.group_buttons`); one whose
  command is in a menu only says "menu only" in its trace.
- `BY_ARG` (`echo.py` 210) and `_fea_load_command` (254): the button by the asked kind (box → `Part_Box`, fuse
  → `Part_Fuse`, gravity → `FEM_ConstraintSelfWeight`, `draft_modify` op, `points_fit` shape, …).
- `in_overflow` (1017) and `overflow_flash` (1039): "»" lights only when the toolbar is shown, its "»" is shown,
  and the button is one Qt hid from the end of the row (no shown button after it, its action shown). A
  dropdown's button that is not on screen now counts too (`flash_command`).
- Every command is checked against `docs/hardening/freecad-1.1.0-commands.txt`
  (`tests/test_echo_rings.py` `Rings.test_every_command_is_freecads`). `bim_covering` stays unmapped: FreeCAD 1.1
  has no covering command.
- How sure: certain for the maps; the overflow rule is plain and tested; whether Qt reports the hidden buttons
  exactly so on macOS is not seen.

### Coverage: tools with a mapped command / total (main → round 4)

| family | main | round 4 | left unmapped |
|---|---|---|---|
| Mesh | 0 / 21 | 21 / 21 | — |
| Surface | 0 / 11 | 11 / 11 | — (the two fits are Reverse Engineering's; on Surface's bench they say "button not on screen") |
| Points | 0 / 9 | 9 / 9 | — |
| Sheet, VarSet, Param | 0 / 18 | 14 / 18 | param_list, sheet_chart, sheet_list, sheet_read (reads) |
| Part (part_, compound_) | 12 / 32 | 32 / 32 | — |
| BIM, IFC | 21 / 53 | 52 / 53 | bim_covering (no command) |
| Draft | 5 / 19 | 18 / 19 | draft_fonts (a read) |
| TechDraw | 6 / 32 | 30 / 32 | td_geometry, td_list (reads) |
| CAM | 6 / 15 | 12 / 15 | cam_list (read); cam_op, cam_dressup by kind only |
| FEM (fea_, fem_) | 5 / 19 | 15 / 19 | fea_chart, fea_export, fea_probe, fea_results (reads) |
| Assembly | 8 / 18 | 11 / 18 | asm_fits, asm_list, asm_sweep (reads); asm_joint_remove, asm_limits, asm_pose, asm_rigid_group (no button) |
| Part Design (pd_, feature_) | 27 / 32 | 27 / 32 | feature_list (read), feature_remove, feature_suppress (no command), pd_datum by kind, pd_tip only when it sets |
| Sketcher | 15 / 19 | 15 / 19 | sketch_add, sketch_constrain, sketch_edit by what was asked; sketch_state (read) |
| Core (doc, object, link, text, units, measure, section, shape, material, insp, scad, robot, import, export, recompute) | 6 / 57 | 43 / 57 | doc_switch, object_rename, and reads |

A read keeps the last change's ring (round 3), so a read's mapping is not used; the counts above include
reads so the totals are the whole family.

### Live check

The BIM model (`bimcam-bim-model.json`) with `window_snapshot` after calls 1, 3, 14, 15, 30, 37, 43:
`session_state` after each shows `echo.button`. Expected: `["Arch_Wall", "button"]` at 1; `["Arch_Window",
"behind »"]` at 3 only when the 3D/BIM toolbar shows its "»"; a narrower window gives "behind »", a wider one
"button". Then the Mesh model call 1 (`meshobj_smooth`): `echo.button` `["Mesh_Smoothing", "button"]`, the Mesh
Modify toolbar's Smoothing ringed. Part model 0001 with `kind: box`: `Part_Box` ringed, not Primitives.

## 2. Selection and the property view

### Causes

- **Property view and tree one call behind** (pd 034-111, BIM 018-051, points 0008-0011, asm 031): FreeCAD's
  property view builds itself on a single-shot timer after each selection change (`src/Gui/PropertyView.cpp`
  369-378, `ViewParams PropertyViewTimer` 100 ms), the tree on its own (`src/Gui/Tree.cpp` 4070-4090,
  `onSelectTimer` 4045 opens and scrolls to the row). The echo selects, paints once (`processEvents` with no
  wait) and returns; the next call or the picture comes before 100 ms, and its own selection starts the timer
  again. Probable (fits every picture; not seen live).
- **asm_ground selects the joint, not Base** (asm 032): its answer names nothing under `OUT_KEYS`, so the new
  GroundedJoint was taken. Certain.
- **asm_bom table not shown** (asm 055): `_views` looked for `TypeId == "Spreadsheet::Sheet"`; Assembly's BOM is
  an `Assembly::BomObject`, derived from it. Certain.
- **shape_query's ConnectingRod stays for asm_check, asm_fits, asm_bom** (asm 050-055): those reads name only
  `assembly`, which reads did not select, and a read that names nothing left the earlier read's selection. Certain.
- **measure selects Pin** (core 0041): its arguments are `a: "Block.Face6"`, `b: "Block.Face5"`; reads selected
  only by `ARG_KEYS`, so the last selection stayed. Certain.
- **object_duplicate selects "Pin copy"** (core 0025), **points_fit selects the cloud** (points 0011): the answer's
  `duplicated: [{ from, copy }]` was not read (rows were skipped), and `object` (the input cloud) came before
  `body` (the fit). Certain.
- **"House" green from bim 024 to 068**: the echo made the new building BIM's active container
  (`view.setActiveObject("Arch", …)`, main `echo.py` 2123-2136); FreeCAD highlights the active object in the tree
  for as long as it is active (`src/Gui/ActiveObjectList.cpp` setHighlight). BIM's own tools never activate one
  (only a double-click or the Active entry: `src/Mod/BIM/ArchBuildingPart.py` 1140-1196). Probable (the colour
  matches the active highlight; not seen live).

### Changes

- `views_follow` (`echo.py` 1917, rule `to_fire`): FreeCAD's tree and property view timers that are pending are
  started again at 0 ms and run once, at the end of every changing call (`viewsFollow` in the trace) and of a read
  that selects. The window walk for the timers is done once and kept while they live.
- `OUT_ONLY` (471): `points_fit` → `body`, `object_duplicate` → `duplicated`, `asm_ground` → `part`, and the points
  makers. Rows are read (`ROW_KEYS` 475). `OUT_KEYS` gains `link`, `text`, `trajectory`, `group`.
- `is_sheet` (2220) and `sheet_refs` (2232): a sheet by derivation; `param_` tools open the Params sheet (from the
  answer's `ref` "Params.x", else "Params"); sheet reads (`sheet_chart`, `sheet_read`) bring their sheet up.
- `_read_shown` (3010): reads select `READ_KEYS` (1814: also assembly, mesh, points, inspection, robot, job, link),
  the faces a read names (`read_refs` 1828: "Block.Face6" in a, b, of, refs; shape_query's found faces on its
  body), bring the 3D view back in front of a drawing (td 049), and a read that names nothing puts back the last
  change's selection when an earlier read had replaced it.
- BIM: no container is activated any more (`_container` 2794).
- How sure: high for each change; the timer cause is the most likely one, not proven.

### Live check

- PD model calls 34-38 with `window_snapshot` after each: the property view shows PlateBase, then the Draft, then
  BoreGrid. `session_state` shows `echo.viewsFollow` ≥ 1.
- Assembly model calls 31, 32, 35, 50, 53, 55: 031 CrankSlider row selected; 032 Base; 035 the joint row with
  Joints opened; 053 CrankSlider again (not ConnectingRod); 055 the Bills_of_Materials sheet in front.
- Core model call 41 (`measure`): Face6 and Face5 of Block lit. BIM calls 24-68: no row stays green.

## 3. See-through

### Causes

- **The roof never** (bim 018-043), **truss behind the house** (043), **other bodies over a sketch in edit**
  (sk 029, 037, 053, 060), **pd 102 post**: `uncover()` took only a cover whose box holds the result's middle and is
  0.9 of its size. A roof above a room, a house in front of a truss, a plate in front of a sketch do not hold the
  middle. Sketch calls never ran `uncover()`; Part Design calls were not in `UNCOVERED`. Certain.
- **Rebar inside the slab** (bim 030): the slab is the rebar's host, in its `OutListRecursive`, and every source
  was excluded. Certain.
- **Point clouds under their solid** (points 0002-0008): `_box()` read `Shape` and `Mesh` only; a cloud has
  `Points`, so a cloud had no box and nothing was uncovered. Certain.
- **Assembly see-through, asm 049 whole** (asm 035-049): not the echo's `uncover()`. FreeCAD's Assembly isolates a
  joint's two parts whenever a joint alone is selected and the document has one assembly: every other part's faces
  are drawn 0.8 transparent (`src/Mod/Assembly/Gui/ViewProviderAssembly.cpp` 1205-1224 onSelectionChanged,
  `isolateJointReferences` 1503, `applyIsolationRecursively` 1466-1478). The echo selected joints (before a call by
  `joint`, after `asm_joint` as its result). When a joint's references do not resolve to top-level parts, nothing
  is isolated in and all goes see-through. High.
- **Inspection colour map and legend stay** (core 0071-0097): nothing hid them. Certain.

### Changes

- `uncover` (`echo.py` 1473): a cover is a shown object whose box holds the result (`covers`, as before) **or**
  that stands between the result and the camera: the line of sight from the result's middle back along the view
  direction passes through its box (`sight_hits` 1362, `covers_in_view` 1384). What holds the result — a body,
  App::Part, folder, BIM level or building, assembly (`is_container` 1409) — is never made see-through; what it is
  built from may be (a host slab). Point clouds have boxes now.
- A sketch in edit: every `sketch_` call uncovers for the sketch's own box (`sketch_box`), after the camera faces
  it (`_after`, "uncovered"). Its body is never touched.
- `UNCOVERED` (492) adds `pd_`, `feature_`, `object_`, `link_`, `compound_`, `scad_`. Assembly calls stay out.
- `isolation_off` (1871): after the echo selects a joint, each assembly's `ViewObject.clearIsolate()` (exposed to
  Python: `ViewProviderAssemblyPyImp.cpp` 174) — the joint stays selected in the tree, nothing is isolated.
- `inspections_after` (2484): inspection results the agent made are hidden at the next changing call of another
  family; `ViewProviderInspection::hide` makes the colour bar's style invisible (`src/Mod/Inspection/Gui/
  ViewProviderInspection.cpp` 157-161).
- How sure: high for the rules (tested); medium that a 30-cover cap is enough in a large BIM model.

### Live check

BIM calls 18, 30, 43: `echo.uncovered` lists the roof (18), "Floor slab" (30), the walls in front of the truss
(43); the room, the bars, the truss can be seen. Sketcher calls 29, 37, 53, 60: `echo.uncovered` lists Plate and
Star; the sketch lines are clear. Assembly calls 35 and 49: every part opaque. Core calls 71-72: the legend is gone
at 72, `echo.inspectionsHidden` names the inspection.

## 4. Non-3D results

- asm_bom: item 2 (`is_sheet`). bim_schedule (032): not a fault — call 32 had no `sheet`, so no sheet was made;
  call 33 made "House schedule", shown in picture 034. Its words now say "Listed the building's quantities".
- bim_views (042), bim_panel_out (048): their answers name the plan view and the cut in rows
  (`views[].view`, `cuts[].cut`), which were not read. Now `OUT_MORE` and `ROW_KEYS` select them and the top
  view fits them. Certain for the names; the framing is not seen.
- param_set / param_remove (Params), sheet_chart and sheet_read (their sheet): item 2. The chart itself is an SVG
  file (`path` in the answer): FreeCAD has no viewer for an SVG file that is not an import, so it is not opened;
  its file name is in the words.
- shape_query after a drawing (td 049): `_read_shown` brings the 3D view back.
- text_document (core 0028): the text opens in its own tab (`_views`).
- td_view_more (061): the view is selected (`view` in `OUT_KEYS`); the property view lag (item 2) left "Parts".
  Not proven.
- Live check: TechDraw calls 49 and 61, sheet calls 37, 47, 53, asm 55, BIM 42 and 48 with `window_snapshot`.

## 5. Words

- Captions that were only the tool name or a cut-off note: `activity.key_value` (`activity.py` 454) takes the
  answer's key value (a volume, area, length, mass, count, facets, a list's length, a file's name — never its
  folder); `outcome` puts it before a note (a note is cut off on the window); a change's words get it after a
  colon (`echo.change_words` 2546), unless the words already have it.
- New and changed phrases (`activity.json`): doc_info "Set the document's comment to …" (it wrote; the old words
  said "Read"), fea_load "Put gravity on …" (fem 033), part_from_mesh names the mesh, and sheet_format, sheet_rows,
  sheet_cells, sheet_table, cam_setup, cam_tool, cam_edit, draft_fonts, draft_style, draft_from_sketch, robot_move,
  robot_tool, scad_tidy, bim_ifc, bim_ifc_brep, bim_trash, bim_reorder, bim_schedule, td_dimset, td_dim_special,
  td_datum, td_gdt, td_geometry, td_section_position, td_lines, fea_refine, fea_parts, fea_shell, points_info,
  units_convert, meshobj_curvature, _project, _split, _refine, _edit.
- doc_graph left `WATCH` (core 0031 kept doc_info's words because a watched call says nothing).
- fem 039 (fea_shell showing "FEM refine"): fea_shell is a long read; if it ran as a job (`job_start`), the
  picture was taken while it ran, with the last change's words. Not settled: see the probe list.

## 6. Tool faults

| item | cause | change | how sure |
|---|---|---|---|
| CAM toolpaths never drawn (cam 008-032) | CAM's App-side `Create` (used by the tools) leaves an operation hidden; CAM's GUI `Create` sets `obj.ViewObject.Visibility = True` (`src/Mod/CAM/Path/Op/Gui/Base.py` 1478-1479), and the job editor hides the original body and shows the clone (`Path/Main/Gui/Job.py` 315-327) | `cam_shown` (`echo.py` 2404): after cam_ calls the op or dressup shown, the job's original body hidden, the clone and the stock shown, the stock 70 % see-through; `camShown` in the trace | high on the cause (the GUI sets it explicitly), not seen |
| FEM: no hold or load symbol (005, 033, 039) | by design: fea_setup, fea_hold, fea_load keep the study as Agent Link's data, no FreeCAD constraint (famfix 2) | fea_hold and fea_load answer `window`: no symbol in the window, and fea_native builds FreeCAD's own analysis whose symbols are drawn; gravity rings the self-weight button | certain |
| FEM: no result (030, 034) | no FEM result was ever coloured | `fem_result_shown` (2449): the newest mechanical result of the named (else any) analysis coloured by von Mises with FreeCAD's own `femresult.resulttools.show_result` (the Results panel's choice); fea_modes / fea_buckle / fea_heat make no FEM objects (their answer says `kept`) | medium: needs a route that keeps its result |
| Robot shows nothing (core 0081-0092) | "puma" is FreeCAD's built-in default robot: no VRML model to draw; the fit framed the whole document (10 m) | `_robot_frame` (3172): frame the box from the robot's base to its tool point and tool shape, at least 1.5 m, robot selected | medium; the arm itself stays invisible with `puma` (kr16 and others load their VRML) |
| Robot: Tasks panel wider afterwards | not settled (Robot's task watchers) | none | probe |
| bim_rebar base "Line" (bim 030) | not a fault: Draft names a two-point wire "Line" (`src/Mod/Draft/draftmake/make_wire.py` 107); it is the Draft wire famfix made, its label got "001" beside the plain line it replaces | none | certain |
| Curvature: wrong mesh, no colours (mesh 012) | a read selected only ARG_KEYS (not `mesh`); Mesh's view provider has no per-vertex colour from Python (only `highlightSegments`) | `mesh` in READ_KEYS; colours stay with `view_render { map: "curvature" }` (the answer's `next`) | certain for the selection |
| Segments not coloured (mesh 009) | the mesh was selected after it was coloured: green over the colours | the selection is cleared when segments were coloured | certain |
| Grid and truss invisible (bim 037, 043) | truss: behind the house (item 3); grid: fit and covers | item 3 | medium for the grid |
| object_appearance coloured the links, not Block (core 0032) | not settled: the tool sets `ShapeColor`, then `DiffuseColor` per face where the view has it; on 1.1.3 the per-face path may be what greys Block (the links show Block's `ShapeColor`) | none | probe |
| sheet_table M10 twice (sheet 0043) | not a fault: FreeCAD's configuration table (wiki Configuration_Tables) has the current row under the header, bound to the switch (`bind_row`), then one row per configuration — with M10 active rows 2 and 3 read the same | none | certain |
| Cloud twice the shaft's size (points 0010) | not a PLY fault: it is "Shaft half", call 9, read from shaft.csv with `scale: 2` | none | certain |
| td_weld: no reference line, no size (048) | a weld symbol's reference line is the leader's last segment (`QGIWeldSymbol.cpp` getKinkPoint, getTailPoint, 509-543); the leader's shoulder was 5 mm | `leader(…, shoulder)` (`techdraw.py` 1839); td_weld asks for 20 mm and puts the end 35 mm out | high for the line; the size text is on the tiles (set before), not seen |
| Centre crosses only at the slot ends (038) | not settled: FreeCAD draws `ArcCenterMarks` at every circle; the dimension lines cross there | none | probe |
| Leader text away from the leader end (046) | not settled from code: the note is placed at the end in page mm (y up) and the leader is not scalable (`DrawLeaderLine::getScale`, Scalable false) | none | probe |
| Overlapping labels (036, 037, 043, 047) | the tools place by fixed offsets, no free-space search | none | open |
| "Shape index 29 out of bound 0" (004 on) | FreeCAD's, from the tutorial file: its Dimension002 has a red mark at 002, before any Agent Link TechDraw call; it references an edge of a view whose geometry is empty when the dimension recomputes | none | probe |
| Part Design: Master outline on Tut (pd 007-111) | API-made features leave their sketch shown; FreeCAD's own Pad etc. hide it (`src/Mod/PartDesign/Gui/Command.cpp` finishProfileBased) | `profiles_hidden` (2523) after pd_ / feature_ calls: a solid feature's Profile sketch hidden | certain |
| pd 102, 108 framing | 102: another body's post in front (item 3, now uncovered); 108: not settled | item 3 | probe for 108 |
| batch { calls, to, lines: "counts" } answered job_status whole | a batch of only socket-thread tools is answered on the socket thread by `_light_batch` (`gui_link.py`), which knew nothing of to, lines, file, read, at, from | `_thread_batch` leaves such a batch to the whole batch's way (`LIGHT_NOT`) | certain |

## Probes for the main session (exact)

1. Rings and overflow: BIM model calls 0-3, then `session_state` → `echo.button` is `["Arch_Window", "behind »"]` or
   `["Arch_Window", "button"]`, never `"behind »"` while the 3D/BIM toolbar shows Window. Then `window_snapshot`.
2. Property view: PD model calls 33-35, `window_snapshot` after 34: the property view names PlateBase.
3. Assembly: model calls 0-35, `window_snapshot`: parts opaque, CrankPivot selected; then calls 36-49,
   `window_snapshot` at 49: no part see-through.
4. Covers: BIM calls 0-18, `session_state` → `echo.uncovered` includes the roof; Sketcher calls 0-29,
   `echo.uncovered` includes Plate.
5. CAM: model calls 0-9, `window_snapshot`: green profile lines; `session_state` `echo.camShown` names Profile.
   If no lines: `object_get { object: "Profile", props: ["Visibility"] }`.
6. FEM: restart FreeCAD, FEM model calls 0-9 and 24, `window_snapshot`: von Mises colours on the mesh;
   `echo.femResult` names the result.
7. Robot: core calls 81, 82: `echo.robotFramed` "robot"; `window_snapshot` shows the tool point region, not 10 m;
   compare the 3D view's width before 81 and after 92 (Tasks panel).
8. object_appearance: core call 32, then `object_get { object: "Block" }` and `view_render { objects: ["Block"] }`;
   if Block is grey, run call 32 without `faces`: if Block turns blue, the per-face `DiffuseColor` path is at
   fault on 1.1.3.
9. TechDraw: model calls 0-2 then `report_read`: if "Shape index 29 out of bound 0" is there before any td_ call
   that changes, it is the file's. Calls 38 and 46-48, then `view_snapshot` zoomed on the holes and the weld
   leader: crosses at the Ø10 and Ø6 centres; the weld's tiles on a 20 mm horizontal line with "3".
10. fea_shell's caption (fem 039): FEM calls 38-39 with `session_state` after 39: `echo_trace.tool` is fea_shell
    (else the call ran as a job: `job_start`).
11. batch: `batch { calls: [{ tool: "job_status", arguments: {} }], to: "js.json", lines: "counts" }` → `counts`
    and `written`, no job list.
12. pd 108: PD model calls up to 108, `session_state` → `echo.made`, `echo.fit`: which object the view framed.

## Risks

- `views_follow` runs FreeCAD's tree and property view timers inside the call: one tree and one property view
  build per change (they would run 100 ms later anyway), and two extra event-loop passes.
- More objects can go see-through: anything on the line of sight (capped at 30, put back at the next change).
  A saved file keeps that transparency if saved before the next change (as round 3).
- Hiding the original body of a CAM job, an inspection result, a used sketch: view state that is saved with
  the file, as FreeCAD's own commands do.
- No BIM container is made active any more: a person's own BIM objects go where BIM puts them, not into the
  agent's last level.
- A batch of socket-thread tools with `to`, `lines`, `file`, `from`, `read`, `at` or `build` now waits for the
  GUI thread like any batch.
- fea_hold and fea_load answers carry a new key, `window`.

## Round 5: a modal "A dialog is already open in the task panel" during the Spreadsheet model

Seen live: after `sheet_list` (a read) and before the next `window_snapshot`, FreeCAD showed a modal box with no
title, "A dialog is already open in the task panel. Close this dialog?" (Yes / No). The batch stopped until
`dialog_answer` pressed Yes.

- Whose words: FreeCAD's. A view provider asks this in its `setEdit` when another task dialog is open:
  `src/Mod/Sketcher/Gui/ViewProviderSketch.cpp` 3434-3448 (also when a sketch in *another document* holds the
  panel), `src/Mod/PartDesign/Gui/ViewProvider.cpp` 135, `ViewProviderDatum.cpp` 257,
  `ViewProviderShapeBinder.cpp` 95, and `Gui/TaskView/TaskDialog.cpp` 92 `canClose`. On Yes, FreeCAD closes the
  open dialog (`Control().closeDialog()`).
  `Gui::Document::setEdit` closes only its own document's edit first (`src/Gui/Document.cpp` 603-620).
- What in the echo could reach those calls:
  - `enter_edit` → `setEdit`, reached from `_mode` (changing `sketch_` calls), `_open_new_sketch` and
    `_reopen_sketch`;
  - `_mode` and `_reopen_sketch` → `resetEdit` (closes an edit with no question);
  - `show_view_of` → `ViewObject.doubleClicked()`. A sheet's double-click also switches the workbench. Since
    round 4, reads (`sheet_read`, `sheet_chart`, TechDraw reads) also reached it;
  - `before` → `activateWorkbench`;
  - `_container` → `setActiveObject("part")` and `FemGui.setActiveAnalysis`.

  The echo calls no `runCommand`, `doCommand` or `showDialog`, and it never answers a dialog: it cannot press
  Yes.
- Which of these fired live is not proven. `sheet_list` itself does nothing that opens an edit, and its usedBy
  refs are not read. The likely sequence has two parts:
  - a task dialog or sketch the echo did not record as its own was holding the panel (for example a sketch left
    open in another document, or from before a FreeCAD restart, when `_agent_edits` is empty);
  - the next echo step then called `setEdit`, or a round-4 read double-clicked a view.
- Changes (`agentlink/echo.py`):
  - `foreign_task(gd)` (2011) blocks when an edit the echo did not open is up in any document. It also blocks for
    the agent's own edit in another document, and for a task dialog with no edit behind it. It does not block for
    the echo's own sketch in this document, because `setEdit` there closes it with no question.
  - `enter_edit` first leaves the echo's own sketch if it is open in another document (`_leave_own_elsewhere`
    2043). Then, if `foreign_task` blocks, it opens nothing and says why in the trace.
  - `before` (2744) does no bench switch and no `_mode` while something foreign is open; the trace key is `held`.
  - `_mode` (2911) and `_reopen_sketch` (3171) close only an edit the agent opened. A person's sketch is never
    closed by the echo: that is a change from round 3, where a pad closed any sketch.
  - `show_view_of(o, read)` (2328): a read, or any call while something foreign is open, only brings up a view
    that is already open (`front_view_of`). It never calls `doubleClicked`.
  - `_container` (2845) makes nothing active while something foreign is open.
- Tests: `tests/test_echo_rings.py` `NeverASecondDialog` replays 15 tools through `before` and `after`, reads and
  changes (sketch_new, sketch_add, sketch_attach, sketch_state, pd_pad, sheet_list, sheet_read, sheet_set,
  param_set, td_list, td_view, text_document, asm_new, measure, object_get). It runs them twice: once with
  `Control.activeDialog()` true, once with a person's sketch in edit. Each time it asserts there is no `setEdit`,
  `resetEdit`, `doubleClicked`, `activateWorkbench`, `runCommand`, `doCommand`, `showDialog` or `closeDialog`.
  With `foreign_task` disabled, the test fails on `sketch_new` (`activateWorkbench`, `setEdit`).
  `tests/test_echo_window.py` `KeepTheSketch` now checks both cases: a person's sketch is left open, the agent's
  is closed.
- How sure: certain that no echo path can now ask that question while a dialog it did not open is up. Which step
  fired live is a probe.
- Live probe: restart FreeCAD, then run the Spreadsheet model calls 0-19 with `window_snapshot` after 17, 18 and
  19.
  - No modal box should appear. `session_state` after each shows `echo.held` when a dialog was up.
  - Then open a sketch by hand (double-click) and run `sheet_read { sheet: "Dimensions" }`, `sketch_add` on
    NutSketch and `pd_pad`. Expected: no question; `echo.edit` says "not opened" or "left open: not opened by the
    agent"; the person's sketch stays open.
- Risk: while a person's dialog or sketch is open, the echo shows less (no bench switch, no edit, no new tab).

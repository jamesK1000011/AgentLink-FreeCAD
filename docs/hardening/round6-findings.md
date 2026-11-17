<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Echo, sixth window pass (round 6): causes found in the code, changes, live checks

Source: the round-4 picture reviews (`window-r4-td-cam-fem-draft-surf-findings.md`,
`window-r4-core-bim-mesh-findings.md`, `window-r4-ws-tex-tutor-findings.md` hub-side items,
`window-r4-pd-sk-asm-part-pts-sheet-findings.md`), the claims in `round4-findings.md`, and the hub items of
ScanRuler's `sr4-findings.md` ("What Agent Link must add"). FreeCAD 1.1.3 source, read only. No FreeCAD ran
here: "test" means a test with stand-ins or a plain rule, never a live check. Line numbers are of branch
`round6`.

Files: `agentlink/echo.py`, `agentlink/tools.py` (the batch's heavy read), `agentlink/jobs.py`,
`agentlink/protocol.py`, `agentlink/annotate.py` (scene-only marks and colours), `agentlink/activity.py`
(strength and CAM figures), `agentlink/families/cam.py` (`path_seen`), `agentlink/families/robot.py` (`drawn`),
`agentlink/data/tools.json` (cam_op, cam_dressup, cam_list answers), `agentlink/data/readers.json` and
`tool_index.json` (regenerated). Tests: new `tests/test_echo_round6.py` (19); changed `test_echo_rings.py` (the
sheet tools with no button), `test_datacam_data.py` and `test_datamisc_data.py` (the meant answer differences),
`test_needs.py` (re-pinned: `path_seen` joined the CAM readers; readers 881 → 882, new sha256).
`scripts/tool_needs.py --check` passes.

Rules kept: every new step runs in `_step` or its own `try`; nothing without a window (`_on`); saved content is
not changed — only view state put back at the next changing call (`Transparency`, `Visibility`, a path's
`LineWidth`: `restore_covers`, `scene_clear`), and scene-only Coin nodes (`annotate`, owner `echo-scene`).
The only deferred calls (a job's end) go through `overlay.later`. No new task dialog can open: the one
`doubleClicked` left is guarded, and a sheet is never double-clicked.

---

## 4 (done first). Stale captions on heavy reads and jobs — CERTAIN

**Cause.** `agentlink/tools.py` 2223-2275 (main: 2186-2245): inside a batch a heavy read
(`keep.is_heavy` and `jobs.eligible`) is started with `_jobs.start` directly and its answer put in the results
— it never goes through `server.call`, which is what `echo.wrap` wraps. No `before`, no `after`, no Activity
row: the last call's words, ring and selection stay for its whole run and after it. Every stale picture is such a
read: Workshop dfm_check, part_review, slice, slice_with, fea_frame (add-on heavy tools); Texturizer
texture_prepare; fem 039 fea_shell (`keep.HEAVY`, a read) showing fea_refine's caption and ring. A job that ends
after its call answered (past 45 s) was never shown either: `job_status` is a socket-thread tool
(`tools.py` `register_thread_tool`), answered by `handle_light` with no echo at all.

**Change.**
- `tools.py` 1797 `_echo_job`: the branch calls `server.echo.before(tt, hargs)` before `_jobs.start` (2237) and
  `server.echo.after(tt, hargs, reply)` with the job's answer or error (2268-2269). `echo.wrap` keeps its Echo
  on the server (`server.echo`).
- `jobs.py`: a job keeps its `args`; `listen(fn)` (52) is called when a job ends (360); `answered(job)` (58)
  marks a job whose answer a call gave back (`protocol._as_job` 689, the batch branch 2268).
- `echo.py` 4131 `job_listener`: a job that ends with no call to give its answer (not `answered`) is handed to the
  GUI thread through the window link's poster, then `overlay.later(0, …)`; while a call is in hand it waits
  (`_busy`, 400 ms, up to 50 times). `Echo.job_done` (3806) shows it as its call's `after` would: words with
  what came of it, what it read selected, an Activity row; `echo_trace.job` names the job.
- Add-on declarations, read by `echo.declare` (775-797): `OUT_MORE` merged into the hub's (Workshop's
  `gen_make` / `gen_part` `bodies`); `SELECTS` `{tool: answer key}` (`selects_names` 832) — `_read_shown`
  selects those objects, a Part Design body included (round 4 skipped bodies for reads); ScanRuler's
  `WORDS` (`declared_words` 805: the first words given replace the echo's caption and the Activity row's;
  `change_words` adds nothing to them) and `SELECTS_FOR` (`declared_selection`: selected in place of what the
  echo would select, for reads and changes, hidden objects left out).
- Never a hidden object selected (ScanRuler item 4): `_hidden` (2240), used by `_select` and `_read_shown`.

**How sure.** Certain for the batch path (the code). The job-end path is tested with stand-ins only.

**Live check.** A batch with `dfm_check { body: "Bracket" }` then `window_snapshot`: caption "Checked Bracket
for printing: …", Bracket selected; `session_state` → `echo_trace.tool` is `dfm_check`. FEM model calls 38-39:
picture 039 says fea_shell's words, not "Cleared the finer mesh areas". A lone `job_start { tool: "fea_shell",
arguments, wait: false }`, wait for its end, then `window_snapshot` with no other call: fea_shell's words,
`echo_trace.job` = the job id.

## 1. CAM toolpaths never seen (cam 008-032) — cause not certain; facts now headless

**What the code says.** `cam_op` refuses when its op makes no cutting moves (tools.json, cam_op `"when": "=not
moves"`), so every op in the pictures had a path; it recomputes (`doc().recompute()`) before answering. The op is
made App-side (`Path/Op/*.py Create` → `Path::FeaturePython`), drawn by `PathGui::ViewProviderPath`
(`src/Mod/CAM/Gui/ViewProviderPath.cpp`): display mode "Waypoints" (attach 274-306), all moves when `ShowCount`
is 0 (183-189, 759-762), drawn **1 px wide in dark green (0, 170, 0)** by default (`DefaultPathLineWidth` 1,
`DefaultNormalPathColor`, 153-165). Nothing App-side hides an op (`Path/Op/Base.py` has no Visibility); the
job's GUI view provider hides its ops when the job is hidden (`Path/Main/Gui/Job.py` 151-177 hideOperations);
the job's model clone is made hidden App-side (`Path/Main/Job.py` 88) and its original shown. Round 4's
`cam_shown` showed the clone opaque and the stock 70 % see-through: the path ran along the clone's walls, mostly
behind or on them, 1 px dark green on the dark theme.

**Change.**
- `cam_shown` (2994): the job's model clone made see-through (as a cover: put back at the next change); the op
  drawn 3 px wide until the next change (`set_view_prop` 3060, restored by `scene_clear`); the op is selected
  by `_frame` (FreeCAD draws a selected path in the selection colour).
- Headless facts: `path_seen` (`families/cam.py` 142) in the answers of `cam_op`, `cam_dressup` and each
  `cam_list` row: `path { moves, length }`, `shown` and `shownWhy` ("Profile is hidden", "is not Active", "has
  no moves", "its job Job is hidden (CAM hides the job's operations with it)").
- cam_sim's caption: `activity.cam_value` (482): "clear, 12300 mm³ removed, 75 % left, up to 9 mm".

**How sure.** Medium: the width and the opaque clone fit every picture; whether the op was hidden live is told
by the new `shown`.

**Live check.** CAM model calls 0-9; the cam_op answer: `path.moves` > 0 and `shown` true (if false,
`shownWhy` names it). `session_state` → `echo.camShown` lists "… see-through" and "Profile 3 px";
`window_snapshot`: a green 3 px path around the clone. If `shown` is true and still no line: `object_get {
object: "Profile", props: ["Visibility"] }` and `gui_` read of the op's view `LineWidth`, `ShowCount`.

## 2. FEM results never coloured; no figures — partly certain

**Cause.** (a) fem 039: item 4 (certain). (b) No figure: `activity.key_value` read no strength key (certain).
(c) No colours: round 4's `fem_result_shown` coloured only a FreeCAD result object — `fea_solve` keeps one only
when FreeCAD's FEM route ran (`strength.py` 920-990, `fea.load_results()`, its errors swallowed); Agent Link's
own deck keeps none (its answer's `solvedBy` says so). Where one was kept, FreeCAD's importer leaves the result
mesh hidden and the post pipeline, the study solid and its gmsh mesh shown, on the same surface
(`src/Mod/Fem/feminout/importCcxFrdResults.py` 100-111); `show_result` shows and colours the result mesh
(`femresult/resulttools.py` 186-215) under the others. Probable.

**Change.** `fem_result_shown` (3082), only after `fea_solve` / `fea_native` (`FEM_RESULT_TOOLS` 3079; round 4 ran
it after every fea_ change): FreeCAD's result coloured by von Mises and the coincident gmsh mesh, study solid
and pipeline hidden until the next change (`hide_for_scene`); for Agent Link's own deck the last solve's field is
drawn as `view_render`'s `stress` map (`render.MAPS`), on a mesh in the scene only (`annotate.field`, drawn a
hair in front), coloured 1st-99th percentile in jet. Captions: `activity.fem_value` (454): "max 41.2 MPa, safety
6.1", "3 modes: 12.3, 45.6, 78.9 Hz", "hottest 81.5 °C". fea_modes keeps no result to draw (by design).

**How sure.** Certain for the words; medium for the colours (Coin with numpy arrays not run here).

**Live check.** Restart FreeCAD, FEM model calls 0-34: `session_state` → `echo.femResult` has `result` (FEM
route) or `map: "stress (Agent Link's own solve)"` with `triangles`; `window_snapshot`: a jet map on the box;
caption "…: max … MPa". Call 30 (fea_modes): caption lists Hz.

## 3. Robot shows nothing (core 0081, 0082, 0092) — CERTAIN

**Cause.** `ViewProviderRobotObject` draws only the VRML file of `RobotVrmlFile` (and the jack dragger when
`Manipulator` is on): `src/Mod/Robot/Gui/ViewProviderRobotObject.cpp` 51-123, 168-200. FreeCAD 1.1.3's source
ships no `Mod/Robot/Lib/Kuka` here, so `robot_new` makes the built-in default robot with no file: nothing to draw.
`_robot_frame` framed a correct but empty box.

**Change.** `_robot_frame` (3955): with no model file, the base, the tool point (a line between them) and each
trajectory's waypoints (`robot_paths` 1492) are marked in the scene only (`scene_marks` 1414, gone at the next
change), and the frame takes the trajectories in; `echo.robotModel` says "none". The answers say it (true fact
added): every robot tool's state gives `drawn: false, drawnWhy: "no robot model file is set …"`
(`families/robot.py` 23, 123).

**Live check.** Core calls 81, 82, 87, 92: answer `drawn: false`; `echo.robotMarks` ≥ 2; `window_snapshot`:
orange points and a line base → tool point, the path at 87.

## 5. BIM: grey fill and the level's label framed; the grid — framing certain, grid medium

**Cause.** `_frame` selected the level/building and fitted the selection: FreeCAD frames the box its view
providers draw (`View3DInventorViewer::viewSelection`), and a BuildingPart's view draws its label and level line
(`src/Mod/BIM/ArchBuildingPart.py` ViewProviderBuildingPart 518 on) — the 65 mm label after bim_reorder.

**Change.** `_frame` (3909): when what was made holds a BIM level/building (`is_bim_container` 1536), the camera
frames `members_box` (1558: the shown members all levels down, Draft labels, texts, dimensions, annotations and
measures left out: `is_annotation`), else `model_box` (the model without annotations). A Draft text or dimension
made on its own is still framed on itself. bim_grid: its `axes` are what it made (`OUT_MORE` 474) and it is seen
from the top (`PLAN_TOOLS`), where the roof between is uncovered.

**Live check.** BIM calls 20-23 and 58-66: `echo.fit` = "members"; `window_snapshot` shows the house. Call 37:
`echo.made` names the axes, `echo.plan` "top", the dashed lines over the plan.

## 6. td_cosmetic, td_lines leave the 3D view; rings on "»" — CERTAIN / decided

**Cause.** `_views` brought a page up only from `page` in the answer or arguments; td_cosmetic and td_lines
name only `view` (certain).
**Change.** `pages_of` (2680): the page a view (or a dimension through its view) is on, for changes and reads.
**"»" decided: no ring on "»".** `flash_command` (1062) still lights a shown button of the same command on any
toolbar and puts the menu item in bold; a button only in the "»" list gives `"behind » (not lit)"` in the trace
and no ring. A menubar title cannot be ringed on the Mac (native menubar: `overlay.menu` returns `native`).
**Live check.** TechDraw calls 49, 52, 53: page in front; calls 47, 48 and fem 34: no ring on "»",
`echo.button` = [cmd, "behind » (not lit)"].

## 7. The Assembly "Bill of Materials" task dialog — CERTAIN

**Cause.** `show_view_of` called `ViewObject.doubleClicked()` on the BOM: `ViewProviderBom::doubleClicked` runs
`Gui.Control.showDialog(CommandCreateBom.TaskAssemblyCreateBom(obj))`
(`src/Mod/Assembly/Gui/ViewProviderBom.cpp` 53-66). Nothing closed it.
**Change.** `show_view_of` (2754): a sheet (Assembly's BOM included: `ViewProviderBom` is a `ViewProviderSheet`)
opens with `showSheetMdi()` (`src/Mod/Spreadsheet/Gui/ViewProviderSpreadsheet.cpp` 100-107), never
`doubleClicked` (no bench switch either). Any other double-click that opens a task dialog where none was up is
noted (`note_own_dialog`) and closed at the start of the next call (`close_own_dialog` 2834, `before` 3319)
when it is still the same dialog (its content titles) and nothing is in edit.
**Live check.** Assembly calls 55-59: the BOM table in front, no task dialog; `echo.views` names it.

## 8. Tool faults

| item | cause | change | how sure | live check |
|---|---|---|---|---|
| object_appearance: Block grey, links blue (core 0032) | Not the tool: `vo.ShapeColor` works on 1.1.3 (`Gui/ViewProviderGeometryObjectPyImp.cpp` 79-86 sets every material's diffuse colour; the links show it). Block lies under "Block moved" (object_align, 0026 z-fighting), which stayed opaque: the answer's `set` rows were not read, so nothing was made, selected or uncovered | `OUT_MORE` `object_appearance: ("set",)` (472): Block selected, its covers see-through | probable | core 32: `echo.uncovered` names "Block moved"; Block blue |
| Mesh segments never coloured (mesh 009) | `meshobj_segments` finds regions with `getPlanarSegments` and keeps none on the mesh: `countSegments()` is 0, `highlightSegments` had nothing | `segments_drawn` (1909): the same search again (planar, ≤ 300k facets), each region a colour, scene only; the selection cleared | certain (cause) | mesh 9: `echo.segmentsDrawn` = count |
| Blue patches to 041 | the kept segment meshes (`keep: true`, tinted objects): real results, by design | none (said) | probable | mesh 9 answer has `kept` |
| Curvature map never shown (mesh 012) | a read; nothing drew it | `READ_MAPS` → `map_shown` (1861): `view_render`'s `curvature` map drawn in the scene | certain | mesh 12: `echo.mapShown` |
| Two rings at once (Texturizer 0014-0019) | a read that opens its panel (`OPENS`) lit its button; rings went out only at a change | `before` 3364: the old ring out first | certain | Texturizer 13-15: one ring |
| Whole-document fit: meshobj_from_shape, points_mesh/merge/structure, part_datum | `framed` read `Shape` only: a mesh or cloud had no box | `framed` (1269) takes `_box` (Mesh, Points) | certain | part 81, points 21, 27, 28: `echo.fit` "made" |
| Sheet tools ring "Alias" | mapped to `Spreadsheet_SetAlias` | sheet_set, sheet_rows, sheet_clear, param_set, param_remove: no button | certain | sheet 7, 23, 37: no ring |
| Bodies edge-on or beside a sketch cover it (sk 024, 037-040, 060) | lines of sight from the middle only | `sight_points` (1687): a 3 × 3 × 3 lattice | certain | sk 24, 37: `echo.uncovered` |
| TechDraw weld "3", hole crosses, leader text, finish symbol, overlaps | not settled from code: tiles get `LeftText` (`techdraw.py` 1360); FreeCAD marks centres of every `Circle` edge (`App/GeometryObject.cpp` 566-571, `Gui/QGIViewPart.cpp` 486-499) — a diameter dimension's lines cross there | none | open | `view_snapshot` zoomed at td 38, 46-48; `object_get` on the weld's tiles (`LeftText`) |
| compound_explode red traceback (part 0030) | "Nothing passes through the filter" is `CompoundFilter.execute` (`src/Mod/Part/CompoundTools/CompoundFilter.py` 249-259) of some filter at the tool's `doc().recompute()` — the new ones (`Explode.explodeCompound`) index the same children, so most likely the older compound_filter object (part 0027) recomputed | none | open | `report_read` after part 30: which object |
| shape_query face not lit; joints not selected in the tree (asm 035, 050, part 0033) | not settled | none | open | `session_state` `echo.readShown` after part 33 and asm 50 |

## 9. Tutor (hub side and what Tutor must change)

- Tree pointer on the Model tab: Tutor's `window.tree_row` rings the Model tab's header whenever the Model tab is
  not in front (`tutor-freecad/agentlink_tutor/window.py` 409-416, 468-471) — and the Tutor lives in Agent
  Link's tab, which is in front while it runs. Not the round-4 tree refresh: Tutor's `rect()` finds the row again
  after a rebuild. **Tutor must**, for a `tree` target, raise the Model tab itself
  (`FreeCADGui.Control.showModelView()` and the dock tab) before it looks for the row, then ring the row.
- Face pointer missing (Tutor 0001-0002): the box was not in view — the Texturizer preview of another document
  sat in the view and the fit framed a 5.8 mm corner. Texturizer must remove its preview node when the active
  document changes (its own finding).
- Bubble text cut (0002, 0009): Tutor's own QLabel (`bubble.py` 283-330) is sized by `heightForWidth` with the
  padding and border set in a stylesheet; Qt does not count stylesheet padding in a word-wrapped rich-text
  label's `heightForWidth`. **Tutor must** size it from a `QTextDocument` with `setTextWidth(width - 2 * (PAD +
  2))` plus `2 * (PAD + 2)`, or use `setContentsMargins` instead of stylesheet padding. The hub's own overlay
  callout measures with `QFontMetrics.boundingRect` and wraps (`overlay.py` 1088-1110): unchanged.
- Echo ring and tutor ring together (0009): rings of other owners are theirs; the echo puts out only its own.

## ScanRuler's hub items (sr4-findings.md "What Agent Link must add")

1. Echo around a heavy read in a batch: done (item 4). 2. `WORDS`: done (`declared_words`). 3. `SELECTS_FOR`:
done (`declared_selection`), and Texturizer/Workshop `SELECTS`. 4. Never select hidden objects: done (`_hidden`).
5. The stale Mesh Info box: **not a task dialog** — it is the Mesh workbench's task watcher (`MeshInfoWatcher`,
`src/Mod/Mesh/Gui/Workbench.cpp` 61-156), shown whenever a mesh is selected in the Mesh bench and removed by
FreeCAD when that bench is left (`Workbench::deactivated` → `removeTaskWatcher`). `Control.closeDialog` cannot
close it. It goes as soon as the next call brings another bench up (ScanRuler's `OPENS` now does); the echo does
not touch it. Live check: sr-b 6131 then a ScanRuler read: the ScanRuler bench in front, no Mesh Info box.

## Not done / open

TechDraw placement faults, compound_explode, shape_query faces, joint tree rows (probes above); captions the
part/points families give as the tool name (about 20: activity phrases, not changed here); bim_panel_out at the
origin; Draft label size.

## Risks

- A job that ends with no call to answer it now shows its words and selection when it ends (a person working
  then sees the selection change).
- More objects can go see-through (a lattice of sight lines); the clone of a CAM job is see-through until the
  next change; a FEM study's solid, mesh and pipeline are hidden while the colours stand (back at the next change;
  a save in between keeps that view state, as round 3).
- Hidden objects are never selected, also when an answer names one.
- No ring on "»" any more.
- cam_op, cam_dressup, cam_list and every robot tool's answers carry new keys.

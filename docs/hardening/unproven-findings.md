# The hub tools still unproven: a model, two models' placeholders, a model-to-batch script

Checkout `<work>/`, base `9f8a34d`. Nothing committed, pushed or run in FreeCAD.
Patch: `<work>/unproven.patch` (4 files: two models changed, one model and one
script new). Written from the sources; every expectation below is derived, none is a live answer.

## 0. What was there, what was kept

The agent before had finished Task B (both models) and Task C (the script) and not begun Task A.
Both were read against the sources and kept as they were: the indices in the two models are
right (checked call by call), the script's checks match `agentlink/tools.py` batch() and
`agentlink/protocol.py` check_input(). Task A is new.

## 1. Task A — `docs/hardening/models/unproven-hub-model.json`

200 calls on one new document (UnprovenHub), 49 of them refusals, plus 10 calls under
`runAlone` (calls a batch cannot carry). `scripts/model_calls.py` reads it with 0 violations;
10 `$from` references, none more than 7 calls back. The tools the hub keeps in code (not in
tools.json: tool_groups, guide_read, usage_report, app_extensions, history_*, job_*,
outputs_clean, report_read, session_state, view_render, body_check) are not schema-checked by the
script; their arguments were checked by hand against the `obj({...})` schemas in
`agentlink/tools.py`, `agentlink/ext.py`, `agentlink/families/view.py` and, for
history_checkpoint / history_restore, the add-on's own definitions.

Run: `python3 scripts/model_calls.py docs/hardening/models/unproven-hub-model.json -o <session folder>/unproven-batch.json`,
then `batch { file: "unproven-batch.json", budget: 100 }` and `from: next` until it ends. The
answer comes in parts (55 s a part, 100 at most): see "references" under conventions in the model
for a part boundary that falls between a source and its reader.

### Per tool: calls and what the answer must show

Numbers are indices in `calls`. R = a call that must be refused.

| Tool | Calls | The answer must show |
|---|---|---|
| feature_remove | 44, 49; R 42, 43 | 44: removed [Pocket, Hole], tip Pad, volume back to 12000. 49 (keepSketch): removed [Pocket] only, sketch Slot still listed by 50. R 42 invalid_state "Pad is used by Hole" (the sketch on its face; Pocket must not be named). R 43 not_found, lists the body's features |
| asm_rigid_group | R 166, 167, 168 | 166: unavailable "Rigid groups came in FreeCAD 1.2; this is 1.1.3 …" naming asm_joint kind fixed. 167: invalid_input, fewer than two parts (checked before the version). 168: not_found, part 'Ghost' is not in Stand. No success exists on 1.1.3 |
| td_bim | 137; R 138 | 137: view "Plan view", section "Plan cut", scale 0.02, svgBytes over 0, no warning (svgBytes 0 with the warning = object made, drawing not proven). R 138: "Bracket is not a BIM section plane". The plane is built by bim_wall 134 + bim_section 135 |
| td_view_more | 140–146, 148, 155, 158, 159, 160; R 156, 161 | lock true / false (140, 141); stack to top then down, stackOrder a number, one lower (142, 143: the fix that was "not re-run"); clip (144); clip_add views [BracketTop] (145); clip_remove views [] (146); symbol from the unwrap's SVG (148); image from a window picture (155); share alsoOn "Second sheet" (158); move from Plan sheet (159); move again "Already on that page." (160). R 156 not_found "no such SVG"; R 161 broken with no breaks, nothing kept (162 td_page read confirms). Kinds broken (with marks) and draft are not called |
| fea_solve | 178; R 174, 176 | 178: solvedBy FreeCAD's FEM, displacementMax 0.185–0.200 mm at x = 100 (F L³ / 3 E I = 0.1905), vonMisesMax 55–120 MPa at the root (beam theory 60), safety 250 / peak, loads[0].area 100, mesh counts. R 174 "Nothing holds the part", R 176 "Nothing loads the part" |
| fea_results | 179, 184; R 171 | 179: the solve's answer again, stale false. 184 (after the load is doubled): the kept answer, stale true, staleWhy names the study. R 171 not_found before any solve |
| fea_export | 180, 181; R 172 | 180: files.vtu and files.csv named unproven-cantilever, nodes and elements = the solve's mesh. 181: csv only, default name Beam-stress. R 172 not_found before any solve |
| draft_outline | 149, 151; R 152, 153 | 149 (extrude): outlines 1, size [20, 20], scale 1, body "Foot plate", volume 800. 151 (engrave on Tile): size [10, 10], scale 0.5, volumeChange −99 (the cut starts 0.01 above the face). R 152 "depth: mm, over 0". R 153 not_found "no file at …". The SVG is written by meshobj_unwrap 147 (see finding F3) |
| meshobj_curvature | 187, 188, 190; R 191 | 187 (ball r 10): medianRadius 9.8–10.2, flatPercent 0. 188 (flat 0.5): flatPercent 100 or just under. 190 (a flat plate, 1 mm triangles): flatPercent over 70 (a guess at the share). R 191 not_found |
| meshobj_unwrap | 147, 163, 193; R 164, 194 | 147 (plane face): exact true, area 400 = 400, stretch 0, size [20, 20], path of the SVG, no pattern. 163 (cylinder side): size [31.416, 30], area 942.478, pattern "Post flat". 193 (open mesh through flatmesh, written as DXF): area3d about 314, stretch over 0, pattern "Cap flat", writer — or unavailable "No Python to run the unwrapping in" (the state before hubfix). R 164 a whole body; R 194 a closed mesh |
| scad_code | R 196, 197 | 196: unavailable "OpenSCAD code needs the OpenSCAD program, not found on this computer …" (with OpenSCAD: top ["Scad cube"], volume 6000); scad_status 195 says which applies. R 197 invalid_input for empty code (checked before the program is looked for, so it reads the same either way) |
| batch | the run itself; runAlone 0–3 | Every row of the run (results[n]: tool, ok, result / error), ran, record, notRun / next. runAlone 0: nested batch refused whole ("calls.1: a batch does not run another batch. Nothing was run."). 1: history_undo with rollback left on, refused. 2: unknown tool, refused. 3: `to` and `$from` in one batch |
| body_check | 36; R 37 | ok true, valid, closed, solids 1, problems [], checkGeometry ok, volume 11214.6. R not_found naming the bodies |
| crash_collect | 110 | the note "No recovery files … and no new crash reports.", or a folder under ~/AgentLink/crash |
| dialog_answer | 108, 109 | dialog null and the note "No dialog or task panel is open …", with and without button (no "pressed"). No refusal is reachable with nothing up |
| guide_read | 9, 10; R 11, 12 | 9: the index (topic, sections, tokens). 10: one section of feature. R 11 lists feature's ten sections; R 12 lists the guides |
| history_checkpoint | 24, 51 | 24: checkpoint id, name "padded", step, file, bytes. 51 (list): the row named padded |
| history_diff | 28, 29; R 30 | 28: steps [pd_pocket], Bracket 12000 → 11214.6, Pocket added. 29 (since: the checkpoint, by reference): since its step number, features added Hole and Pocket. R 30 invalid_input, the range of steps |
| history_undo | 38 | done undo, redoCount 1; steps_list 39 counts 1 (the proof) |
| history_redo | 40 | done redo, redoCount 0; steps_list 41 counts 2 again |
| history_restore | 52; R 54 | 52: done restore, how "undo" with the steps (or "file" with before); steps_list 53 counts Base and Pad only. R 54 not_found listing the checkpoints |
| job_start | R 129, 130; runAlone 4, 5, 8, 9 | 129: refused inside a batch (finding F1). 130: not_found. runAlone 4: body_check's answer with a job id; 5: wait false, the id at once; 8: a change refused; 9: session_state refused with its reason |
| job_status | 127; R 128; runAlone 6, 7 | 127: jobs [] with the note. R 128 not_found. runAlone 6: done with the tool's result; 7: both jobs listed |
| outputs_clean | 112; R 113 | 112: dryRun true, wouldGo by kind, total, kept, exports listed; nothing removed. R 113 "kinds: any of shot, run, export, fcbak" |
| report_read | 105, 106 | found true, count, problems, lines (at most 5; problems only) |
| session_state | 1, 78, 81, 198 | 1: empty document, freecad 1.1.3, where window. 78: hidden [Bracket], bodies []. 81: Bracket back, 12000. 198: every part, assemblies Stand |
| tool_groups | 2–6; R 7, 8 | 2: groups. 3: find. 4: one tool's card (inputSchema.required [feature]). 5: group core. 6: now, with fits and next. R 7 "did you mean feature_remove"; R 8 unknown group |
| usage_report | 13, 14, 199 | session totals (errors counts the refusals), 1 day, and the totals again, higher |
| view_maps | 99 | maps wall, stress, heat …; layers; views |
| view_render | 100, 101, 182; R 102 | 100: four views, 900 × 700, a file. 101: map stress before any solve answers `empty` in words (not a refusal). 182: the same map after the solve, with a legend. R 102 "width and height: 64 to 3000 px." |
| view_snapshot | 103; R 104 | 103: iso, 800 × 600, a file, fitted. R 104 "view: one of …" |
| app_extensions | 15; R 16 | 15: repos, loaded. R 16: add with no repo, refused before anything is written |
| cmd_list | 61, 62, 63 | 61: the two Std_ViewFit commands. 62: Std_Quit with its refused mark. 63: nothing found, count 0 |
| cmd_run | 21, 22, 64; R 65, 76 | 21: Sketcher_LeaveSketch with the sketch open (ran, wasActive true). 22: with none (ran null, "already …": an answer). 64: Std_ViewIsometric. R 65 not_found. R 76 invalid_state: Std_Delete greyed with nothing selected |
| menu_list | 66; R 67 | the View menu's items with paths and commands. R not_found listing the menus |
| menu_run | 68; R 69, 70 | 68: View > Standard views > Fit all, command Std_ViewFitAll (the path is the description's own: if 1.1.3 words it otherwise, take it from 66). R 69 "is a menu, not an item". R 70 not_found |
| pref_get | 82, 84; R 89 | 82: a group's values and subgroups. 84: Probe, Integer, 3. R 89 not_found after the reset: the group is as before the run |
| pref_set | 83, 85; R 86, 87 | 83: Probe null → 3. 85: 3 → 4, type kept. R 86 not_allowed on a guarded name of our own (ProbeExecutable). R 87 no name or values |
| pref_reset | 88; R 90 | 88: reset [Probe], notSet [NeverSet] — the restore. R 90 not_allowed, the same guard |
| pref_pack | 91; R 92 | 91: the pack names. R 92 not_found for a wrong name. apply is not called |
| selection | 71, 72, 74, 75; R 73 | set, read back, a wrong name refused with the selection kept (74 proves it), cleared |
| show | 77, 79; R 80 | hidden [Bracket]; visible [Bracket] with unknown [Ghost]; R not_found when nothing named exists |
| snapshot_latest | 97, 98 | with no screenshots both are refusals (not_found "No screenshots yet …"); with some, 97 is the newest picture and 98 "index: 1 to N". Must agree with 96 |
| snapshot_list | 96 | shots, [] when the person took none |
| window_snapshot | 93, 94, 154; R 95 | a PNG path with the window's size; one panel, smaller; R not_found listing the panels |
| workbench | 18, 58, 59; R 60 | activate Sketcher, read, activate Part Design (active, was). R not_found listing the workbenches |
| gui_unstick | 107 | closed [], nothing open |
| doc_switch | 55, 56; R 57 | the list of open documents; "Already on it." with front true; R not_found with the open ones as label (name) |
| queue_go | 111 | go true, wasHeld false, running [], machine. Its own rule is the person's word: run it only as part of this test |
| note_add | 114; R 115 | note.id, at [20, 15, 10], body Bracket, a face; R empty text |
| note_answer | 117 | the answer on the note (id by reference to 114) |
| note_done | 118, 120 | done true; done false again |
| note_list | 116, 119 | the one note; none with open: true once it is done |
| note_delete | 121; R 122 | deleted the id, left 0; R not_found for 99999 |
| steps_list | 31, 32, 39, 41, 45, 50, 53; R 33 | Pad 12000 / Pocket −785.4 with tip; with sketches 4 rows; and the proofs of undo, redo, remove and restore. R not_found naming Bracket |
| steps_render | 34; R 35 | 2 step pictures and steps.png in unproven_steps; R width under 120 |
| addon | 123, 124 | list: the Mod folder's rows; search sheetmetal: found over 0 (needs the catalog) |
| addon_test | 125; R 126 | the recent jobs, nothing started; R addon and job together (refused before anything starts). addon alone is not called: it starts a FreeCAD process for minutes |

Helper calls that build what these need (not targets): doc_new 0, pd_body_new 17, sketch_new,
sketch_add, pd_pad 23, pd_pocket, part_primitive, shape_query 133, bim_wall 134, bim_section 135,
td_page, td_view 139, asm_new 165, material_set 170, fea_setup 173, fea_hold 175, fea_load,
meshobj_from_shape, meshobj_trim 192, scad_status 195.

### Findings from writing it

- **F1. job_start cannot succeed inside a batch, and says the wrong reason.** `jobs.wanted()`
  answers False whenever `session.batch_now` is set, so job_start then raises "X cannot run as a
  job: only a read that leaves the window and the 3D view alone can (not a change, a picture, a
  window tool or a batch) — call X itself." for a read that is eligible. Call 129 proves that
  refusal; the success is in `runAlone` (4, 5). The words should name the batch. (The batch's own
  description says a heavy read "runs as a job inside the batch too": I did not find where; not
  checked further.)
- **F2. batch's own refusals cannot be calls of a model.** A list holding a batch is refused
  whole, and the script flags it. The model keeps them under `runAlone` (same call shape, sent
  one at a time). `scripts/model_calls.py` ignores that key; the main session sends them by hand.
- **F3. Which tool writes an SVG into the session folder: meshobj_unwrap { path }** (a relative
  path lands in the session's folder; `.dxf` too). td_export and export { section } also write
  SVG, but of a drawing or a cut. **draft_outline and td_view_more (symbol, image) do not look in
  the session's folder**: both take `expanduser(path)` as it is, so a bare file name is refused
  not_found. The model passes the unwrap's answered `path` by `$from`. Worth a hub fix (resolve a
  relative path in the session's folder as other tools do).
- **F4. history_diff { since: a checkpoint of this session } answers `since` as the step number**,
  not the id (the id only when nothing changed since, or from a saved copy). Call 29's
  expectation says so; the description reads as if the id came back.
- **F5. draft_outline engrave cuts 0.99 of the depth** (the solid starts 0.01 above the face and
  runs `depth` down from there): volumeChange −99 for 10 × 10 × 1. Call 151 states it; if the
  intent is the full depth, the extrusion wants depth + 0.01.
- **F6. hubrest-model's `<NOTE_ID>` placeholders** (calls 24–26 there) have the same cure as
  Task B: `{ "$from": 22, "$at": "note.id" }`. Not changed (out of scope); this model does it at
  117–121.
- Not verified from an answer, only from the code: the refusal words of in_body (43), the exact
  face name on a pad (114), pref_set's type word (83), td_page read's shape (162), the catalog's
  name for SheetMetal (124), FreeCAD 1.1.3's menu titles (68). Each expectation says what to read
  instead.

### notCovered (also in the model)

| Left out | Why | What a safe proof needs |
|---|---|---|
| app_restart, app_force_restart, app_install | quit FreeCAD, or download and install a release | the person's go and saved documents; app_restart on an empty document then session_state; app_force_restart only on a window stuck on purpose; app_install only for a version they name |
| pref_import | writes a settings file over the person's | export first, import a file holding only LiveTest/Probe, read it, import the export back; with their go |
| pref_pack { apply } | no un-apply | a settings history to take it back (pref_history / pref_rollback) and their go |
| addon install / update / remove | code FreeCAD runs; confirm typed by the person | they type confirm for a small add-on they do not use; install, list, remove, list |
| app_extensions add / remove / sync | the person's list of repositories | their typed confirm; only list and the no-repo refusal are called |
| collab | shares work with others | a second party and the person's say |
| gui_input | real input into the window | coredoc-gui-model.json on the reset document, in the background, while they are not typing in FreeCAD |
| live_run | runs scripts of calls; its reset rebuilds WindowTest | reset then the agentlink script, with no document of theirs in front |
| cmd_run / menu_run refusing Std_Quit and the like | a failed refusal would quit or open a modal dialog | cmd_run { name: "Std_About" } alone (worst case an About box gui_unstick closes); cmd_list 62 shows the refused mark meanwhile |
| outputs_clean { dry_run: false } | moves files to the Trash | by the brief, dry run only |
| dialog_answer, gui_unstick with something up | none is up in this run | a dialog or menu opened on purpose |
| snapshot_latest with a picture | only the person takes screenshots | they take one |
| queue_go with a job held | the hold exists only while they work and a heavy job waits | that state |
| asm_rigid_group success | FreeCAD 1.2 | a 1.2 build |
| scad_code success | OpenSCAD not installed | the person installs it |
| addon_test { addon } | a separate FreeCAD for minutes | run once by hand: addon_test { addon: "AgentLink", select: "test_paths" } |
| td_view_more broken (with marks), draft | no break marks or Draft object in this model | a sketch with two lines; a Draft wire |
| checkpoints across a restart; fea_solve nonlinear and own deck | no restart here; one linear solve | sheetfem-fem-model has the own-deck solve |

## 2. Task B — the placeholders

`asmtd-techdraw-model.json` (66 calls) and `bimcam-bim-model.json` (now 70: ifc_find inserted as
67, ifc_remove 68, bim_import 69). Both read by the script with 0 violations.

| Model, call | Now | `$at` key | Verified |
|---|---|---|---|
| techdraw 12 td_title | `fields: { "title": … }` written out (an object's key cannot be a reference) | — | **Guessed.** The template's field names are in call 11's answer (entry: `fields: dict(t.EditableTexts)`, verified); the expect says to resend with that name |
| techdraw 35 td_tolerance | `dimension: { $from: 34, $at: "dimension" }` | `dimension` | **Not from the entry**: td_dim's answer is `"...": "=dim_reading(d)"`. From the source: `dim_reading` in agentlink/families/techdraw.py answers `dimension: d.Name`. Not live |
| techdraw 50 td_hatch | `faces: [{ $from: 49, $at: "items.0.ref" }]` | `items.0.ref` | `items` **from the entry** (shape_query answer fields); `ref` from the entry's description ("Reply items: ref, …") and live (patches/out/core-1.json call 18) |
| techdraw 51 td_area | `face: "Plate.Face6"` written out (a reference cannot be joined to "Plate.") | — | **Guessed** (Face6); the expect says to check it against call 49. The answer's `face` (`label + '.' + sub`) is from the entry |
| techdraw 55 td_dim_format | `dims: [{ $from: 31, $at: "dimension" }]` | `dimension` | as 35: source only |
| techdraw 56 td_dim_align | `dims: [{ $from: 36, $at: "dimensions.0.dimension" }, { … "dimensions.1.dimension" }]` | `dimensions.N.dimension` | `dimensions` **from the entry** (td_dimset: `"dimensions": "=made"`); each item's `dimension` from the source (the td_dim reading plus `lane`). Not live |
| techdraw 57 td_dim_repair | `dimension: { $from: 33, $at: "dimension" }` | `dimension` | as 35: source only |
| bim 67 ifc_find (new) | `{ name: "Plinth" }` | — | that it finds exactly one element: not live (call 28 retypes the Plinth to IfcFooting; the name stays) |
| bim 68 ifc_remove | `ids: [{ $from: 67, $at: "elements.0.id" }]` | `elements.0.id` | `elements` **from the entry** (ifc_find answer fields); `id` from the entry's description ("Answers elements [{ id, class, name, storey }]"), the source (`row()`: `el.GlobalId`) and live (patches/out/bim-3r.json call 2) |

All input types fit: dimension and dims items are strings, ids items strings, faces free.
Reach: 35←34 and 50←49 one call; 55←31 and 57←33 24 calls, 56←36 20. A batch answered in parts
refuses a reference into an earlier part, so techdraw 31–57 must run in one part
(`batch { file, from: 28, budget: 100 }`); the model's new `conventions` key says so. The first
live run of 31–36 should be read for `dimension` and `dimensions[].dimension` before 55–57 are
trusted.

## 3. Task C — `scripts/model_calls.py`

`python3 scripts/model_calls.py model.json -o batch.json` or `--all DIR [--out-dir DIR]`. Writes
`{ calls: [{ tool, arguments, to?, profile? }], rollback: false, stopOnError: false }`. batch()
rebuilds each call from tool, arguments, profile and to and drops any other key silently, so
`expect` (and allow, note …) is left out here and counted. Checks, each with the call's index:
what batch() refuses whole (a call that is no object, arguments no object, `to` not a .json path,
a batch inside), placeholders left in arguments, `$from` / `$file` references as chain.py reads
them, and for tools in tools.json what check_input() refuses (unknown field after the hub's
synonyms, missing required, top-level type and enum; a reference's type is not checked). A
violation on a call whose expect begins REFUSED is listed as expected and does not count. Exit 1
when a violation counts. SPDX line present. No tests were added for it.

Run over `docs/hardening/models` (17 files):

| Model | Calls | Violations |
|---|---|---|
| asmtd-assembly-model.json | 73 | **1**: calls.51 asm_joint — placeholder `arguments.b.element` "<the free hole's face name from the shape_query above, e.g. Face7>" |
| asmtd-techdraw-model.json | 66 | 0 (Task B) |
| bimcam-bim-model.json | 70 | 0 (Task B) |
| bimcam-cam-model.json | 34 | 0; 3 on calls that expect the refusal (7 cam_job tool required; 11 cam_op side 'left'; 16 cam_post post 'fanuc') |
| bimcam-points-model.json | 35 | 0 |
| coredoc-gui-model.json | — | not a call list (a live script: { name, steps }) — skipped |
| coredoc-model.json | 114 | **4**: calls.83, 84 robot_move `tcp.ypr` "<YPR>"; calls.85 robot_path `waypoints.0.ypr` and `waypoints.1.ypr` "<YPR>". 1 expected (111 doc_close: save is not a field) |
| draftmesh-draft-model.json | 81 | 0 |
| draftmesh-mesh-model.json | 63 | 0 |
| draftmesh-surface-model.json | 52 | 0 |
| hubrest-model.json | 46 | **6** (3 calls, two lines each): calls.24 note_answer, 25 note_done, 26 note_delete — `id` is the placeholder "<NOTE_ID>", and text where a whole number is wanted |
| part-model.json | 98 | 0 |
| partdesign-model.json | 113 | 0 |
| sheetfem-fem-model.json | 43 | 0 |
| sheetfem-sheet-model.json | 55 | 0 |
| sketcher-model.json | 61 | 0 |
| unproven-hub-model.json | 200 | 0 |

11 violation lines in 3 models, all placeholders; none was changed (only the two Task B models
were). Their cures: assembly 51 `{ $from: <its shape_query>, $at: "items.0.ref" }`; hubrest 24–26
`{ $from: 22, $at: "note.id" }`; coredoc 83–85 `{ $from: <the robot_move { axes } call>, $at: "tcp.ypr" }`
(the key is the model's own convention, not checked against the entry).

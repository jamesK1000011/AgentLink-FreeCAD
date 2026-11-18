# Add-on and hub tools still unproven: models and checks — 16 Nov 2026

Nothing here ran on FreeCAD or on OrcaSlicer: these are call lists for the Mac. What did run here: every call of the
four models through Agent Link's own input check (`agentlink.protocol.check_input`) against the tools' schemas; the
OrcaSlicer link's server in plain Python for the calls that need no OrcaSlicer (on the repo's sample project); all 344
calls of ScanRuler's four models through the same input check. No `<work>/models/` existed before this
pass: there was nothing from an earlier agent to judge.

Files (all in `<work>/models/`):

| File | Calls | Runs on |
|---|---|---|
| `workshop-rest-model.json` | 46 | Agent Link for FreeCAD (batch, `$from`) |
| `tutor-rest-model.json` | 17 (+ 6 in `withWatchOn`, only on the person's word) | Agent Link for FreeCAD, window open |
| `orca-model.json` | 16 | the OrcaSlicer link's own MCP server, one call at a time |
| `orca-box.stl` | fixture, 684 bytes | copy to `~/AgentLink/hardening/models/orca-box.stl` |
| `bim-rest-model.json` | 39 | Agent Link for FreeCAD (batch, `$from`) |

Each model is `{ tutorial, reference, conventions, expected, calls: [{ tool, arguments, expect }], notCovered }`, the
shape of `docs/hardening/models/*.json`. "REFUSED code" in `expect` means the call must answer an error with that code.

## 1. Workshop (16 tools) — `workshop-rest-model.json`

Read first: `safetynet/handlers.py`, `macros.py`, `settings.py`, `recovery.py`, `fam_safety.py`;
`workshop_make/handlers/mass.py`, `slicing.py`, `printer.py`, `printers.py`, `data/tools.json`.

| Tool | Calls | What the answer must show | Proven by this model |
|---|---|---|---|
| macro_save | 2, 3, 4 | 2: `calls 1`, `constants { LENGTH: 42 }`, `approved false`, path ends `alink-hardening-probe.FCMacro`. 3: REFUSED invalid_state (there already). 4: REFUSED invalid_input (name with a folder) | accepted + 2 refusals |
| macro_list | 5, 12 | the folder; the row `{ name, state "no", about … "from 1 calls" }` | accepted |
| macro_show | 6, 7 | `state "no"`, `constants { LENGTH: 42 }`, `calls 1`, text with `'size': [LENGTH, 20, 10]`. 7: REFUSED not_found | accepted + refusal |
| macro_approve | 9, 10 | 9: REFUSED not_allowed, naming `"approve alink-hardening-probe"` typed by the person, "Nothing was changed". 10: REFUSED not_found | refusal only, on purpose |
| macro_unapprove | 11 | `unapproved`, `was false` | accepted |
| macro_run | 8, 13 | 8: REFUSED not_allowed ("it has not been approved"). 13: REFUSED not_found | refusal only, on purpose |
| mass_calibrate | 15, 17, 18, 19 (read by 14, 16, 20) | 15: `calibrated "solid:pla"`, `scale 1.0561`, `expected 10.42`, `weighed 11`. 16: mass 11.0 and "calibrated ×1.056 …" in `as`. 17: REFUSED (×0.10). 18: REFUSED (no grams). 19: `reset`, `was { scale 1.0561 … }`. 20: 10.42 again | accepted, reset, 2 refusals |
| slice_open | 21 | REFUSED not_found, no slicer window | refusal only |
| pref_history | 26, 28 | 26: at most 3 rows, newest first. 28: one row, `tool "pref_set"`, `name "Probe"`, `to 7` | accepted |
| pref_rollback | 30, 31, 32 | REFUSED not_found (no snapshot for 999999; none as old as 1900), REFUSED invalid_input (empty `to`). FreeCAD does not restart | refusal only, on purpose |
| app_recover | 23, 24, 25 | 23: `documents` with `WorkshopRest` and a copy `source "checkpoint"` (call 22 made it). 24: REFUSED invalid_input (auto with no documents). 25: REFUSED invalid_state ("not a recovered copy") | list accepted + 2 refusals |
| printer_add | 33, 34, 35 | 33: `added { …, auth "none" }`, `kept ".agentlink-printers.json"`, no `reached`. 34: REFUSED unavailable (Bambu). 35: REFUSED invalid_input (OctoPrint needs a key) | accepted (dummy) + 2 refusals |
| printer_status | 36, 37, 45 | 36: REFUSED unavailable, "can't reach it" (127.0.0.1:9). 37: REFUSED not_found. 45: REFUSED not_found after the dummy is removed | refusal only |
| printer_pause | 38 | REFUSED invalid_input, naming `"pause alink-hardening-dummy"` | refusal only |
| printer_stop | 39 | REFUSED invalid_input, naming `"stop alink-hardening-dummy"` | refusal only |
| printer_send | 40, 42 | 40: REFUSED not_found. 42: REFUSED invalid_input "G-code only" (the file is call 41's STEP, by `$from`) | refusal only |

Also in the model: `history_checkpoint` (22) and `export` (41), both on the hub's own unproven list.

Safety, as built into the calls:

- **Printers.** Every `printer_*` call names `alink-hardening-dummy` (Moonraker kind, `http://127.0.0.1:9`, no key,
  `check: false`). A call with no `printer` falls to the only kept printer, which could be the person's own: that is
  why none is left out. The only request sent is call 36, to the Mac's own loopback port 9. Pause, stop and start are
  never sent with their confirm words. Call 43 removes the dummy; 44 and 45 show it is gone.
- **macro_approve.** Its description says the person types the confirm, never the agent. The model sends an empty
  confirm and reads the refusal. The accepted road is in notCovered with the exact calls.
- **pref_rollback.** It has no dry form (its inputs are `to` and `save`). Only a `to` with no snapshot is sent.
- **pref_set / pref_reset (27, 29)** write and remove the test-only key `Mod/AgentLink/LiveTest/Probe` (the key
  `hubrest-model.json` calls 13 to 15 use) so that call 28 has a known newest row. Leave 27 to 29 out if no settings
  write at all is wanted; call 26 then proves pref_history alone.
- **Left behind:** `alink-hardening-probe.FCMacro` in FreeCAD's macro folder (no tool deletes a macro; it is not
  approved, so Agent Link does not run it), one checkpoint, `alink-probe-box.step`.

Not checked live, so read these first: that `macro_save` counts 1 call (it reads the per-document list of changing
calls; `doc_new` is not one); that the default material's id is `pla` (the key `solid:pla`); the exact `path` text in
pref_history's row.

notCovered (the model file has the same list with the calls to run):

1. macro_approve accepted and macro_run running: needs the person's typed `approve alink-hardening-probe`.
2. pref_rollback putting settings back: needs a throwaway FreeCAD profile, not his.
3. slice_open opening a project: it starts OrcaSlicer's window in front; needs the person at the Mac and his word. There
   is no "slicer not installed" refusal to read either: `slicer` is an enum of two.
4. printer_status with a state, printer_send uploading, pause and stop accepted: need a real printer or a local
   Moonraker stand-in, and the person's confirm.
5. printer_send of a real `.gcode` to the dummy (unavailable): needs a slicer's G-code file.
6. app_recover auto and accept: they open copies and save over a file; the task asked for the read-only use.

## 2. Tutor (2 tools) — `tutor-rest-model.json`

Read first: `agentlink_tutor/point.py`, `targets.py`, `lessons.py` (target kinds), `tool.py` (watch), `live.py`,
`engine.py` (the lesson's document), `data/tools.json`, `lessons/wiki-film-hinge-sketch.lesson.json`.

| Tool | Calls | What the answer must show |
|---|---|---|
| tutor_point | 2, 3, 7, 8, 11, 12 accepted; 4, 5, 6 refused | 2: `shown` + `missing` hold n 1 to 4 (face `Face6 of PointBox`, tree, cmd, view); `until "the next tutor_point"`; `callout`. 3: `until "3000 ms"`, an edge. 7: `shown []`, `missing[0].why "no command No_Such_Command in this FreeCAD"`, the note. 8, 12: `{ cleared: true }`. 11 (inside the lesson, after `tutor next`): n 1 to 5, kinds cmd, tree, wb, task, dock. 4: REFUSED (`of` missing). 5: REFUSED (ms 100). 6: REFUSED (7 targets) |
| tutor_watch | 13 accepted (off); 14, 15 refused | 13: `{ watching: false, say }` and no `events`. 14: REFUSED invalid_input "wait: 0 to 25 seconds". 15: REFUSED invalid_input (until enum) |

The lesson: call 9 starts `film-hinge-sketch` in demo mode (expect `step "1/8"`, `id "arc"`, `document "a new document
FilmHinge: TutorRest holds other work"`), call 10 does step 1, call 16 stops it. (The bike-stem course this used
before was retired on 18 Nov 2026.)

Where a target lands (shown or missing) depends on the window, so `expect` says what each entry holds and that every n
is in one of the two lists. A target in neither list is a fault.

notCovered:

1. **tutor_watch with watch mode on.** Its description says watch mode is the person's to turn on, and its events
   are only the person's own actions. The model leaves it off. `withWatchOn` in the model file holds six calls to run
   when the person says so (on, read, a 20 s wait while he clicks, read from `next`, off, read).
2. tutor_point kinds `menu` (native macOS menubar: words in the callout), `sub`, `ext`.
3. The rings' end after `ms`: read from the window, not from an answer.

## 3. OrcaSlicer link (5 tools) — `orca-model.json`

Read first: `orcalink/tools.py` (the five tools), `server.py`, `presets.py`, `calibrate.py`, `gcode_view.py`.
The older `orca-model.json` in `<work>/` (38 calls, the repo's own) is not changed; the new one is in
`models/`.

These tools are on the add-on's own server. It has no batch and no `$from`, so the list is run one call at a time and
starts with `orca_status`, not `doc_new`.

| Tool | Calls | Needs OrcaSlicer | What the answer must show |
|---|---|---|---|
| orca_project | 1 (new), 2, 6 (info); 3 refused | 1: yes. 2, 3, 6: no | 1: project `alink-rest.3mf`, one object `orca-box.stl`, `bedType`. 2: size [20, 10, 5], 12 triangles, `presets` and `filaments[0].preset` = the three names given. 6: `painted ["seam"]`, `effective`. 3: REFUSED not_found |
| orca_paint | 4; 5 refused | no | 4: `kind "seam"`, `state "block"`, `triangles 2`. 5: REFUSED invalid_input (`where.face`) |
| orca_slice | 7 (svg), 9 (slice); 8 refused | 7, 8: no. 9: yes | 7: `layers 10`. 9: `gcode`, layers = 5 / layer height, `filamentG` 0 to 2, `time`, `sliced`. 8: REFUSED invalid_input (plate 9) |
| gcode_read | 10, 11; 12, 13 refused | no (10 to 12 need call 9's file) | 10: layers as call 9, `z` last 5.0, `features` with Outer wall, `ranges`. 11: `layer.layer 2`, `move`, `svg` path. 12: REFUSED invalid_input (view). 13: REFUSED invalid_state (not sliced) |
| orca_calibrate | 14; 15 refused | both yes | 14: `kind "temperature"`, `objects 1`, `howToRead`. 15: REFUSED invalid_input ("blocks are 5 °C apart") |

Calls that need OrcaSlicer installed: **1, 9, 14, 15** (`needsOrcaSlicer: true` on each call in the file).

Two things the main session must supply, because this server cannot:

1. **The fixture.** `orca_project new` takes model files, and no call makes one from nothing. `orca-box.stl` is
   beside the model; copy it to `~/AgentLink/hardening/models/orca-box.stl`.
2. **Three preset names** (`<MACHINE>`, `<PROCESS>`, `<FILAMENT>`, in call 1 only). This server has no call that
   lists presets and no chaining. Read them with Agent Link for FreeCAD's `slicer_presets { action: "list",
   slicer: "orcaslicer" }`. These are the only placeholders in the four models.

The person's presets are not changed: `presets.py` only reads OrcaSlicer's folders and writes merged copies under
`alink-rest-work/presets/` in the output folder. This is by the code, not by a call.

Run here without OrcaSlicer (sample project): calls 3, 5, 8, 13 answered the refusals as written; call 4 answered
`triangles 2`; the `svg` export, the `view` refusal and the `step: 3` refusal text were read from the server.

notCovered: orca_calibrate with the person's presets (needs the three profile file paths); slicing the calibration
project; the other orca_project actions and paint kinds (the repo's 38-call model has them).

## 4. ScanRuler (5 tools) — check of the repo's models

Stefan Hermann's (CNC Kitchen's) ScanRuler features, in `<work>/docs/hardening/`. No new
calls were written: the repo's models already hold them.

| Tool | Model | Accepted call | Refusal calls | Chain it needs |
|---|---|---|---|---|
| mesh_apply_wrap | `scanruler-meshtools-model.json` | **65** | 61, 67 (invalid_state, no wrap) | 64 `mesh_wrap { gap: 4 }` (a preview) before 65; 62 undoes the wrap of 60 first |
| reverse_parameter_remove | `scanruler-reverse-model.json` | **66** `{ parameter: "spare" }` | 14 (invalid_state: height is read by Block), 68 (not_found) | 65 `reverse_parameter_add { name: "spare", expression: 5, comment }` |
| scan_noise | `scanruler-measure-model.json` | **133** | 11 (invalid_input, CAD tessellation); 129 (either answer, the model says so) | 126 to 132: sphere, `meshobj_from_shape`, `scan_open`, `mesh_densify { maxEdge: 1 }`, `mesh_smooth`, `mesh_use_edited` |
| scan_snapshot_latest | `scanruler-measure-model.json` | **141**, **142** `{ original: true }` | 117 (not_found, no shot yet), 143 `{ index: 3 }` (not_found) | 138 `workbench { activate: "ScanRulerWorkbench" }`, 139 `cmd_run { name: "ScanRuler_Snapshot" }`, 140 `scan_snapshot_list` |
| reverse_build_stop | `scanruler-reverse-model.json` | none | 45 (unavailable) | — |

Schema check: each of these calls, and all 344 calls of the four ScanRuler models that have a schema here, went
through `check_input` with the tool's own `inputSchema` (unknown fields, required fields, types, enums).
**None would be refused for a wrong argument.** The four tools take: `mesh_apply_wrap {}` and `scan_noise {}` (no
inputs, `additionalProperties: false`); `reverse_parameter_remove { parameter }` (required, text or number: "spare"
and "height" are text); `scan_snapshot_latest { index (integer ≥ 0), id, original }` (0 inputs, `original: true`,
`index: 3` all fit). The refusal codes in the models' `expect` match the handlers (`meshtools/handlers.py` line 220,
`reverse/handlers.py` parameter_remove, `snapshot/handlers.py` lines 55 to 65, `handlers/noise.py` scan_noise).
`history_undo` / `history_redo` in those models are SafetyNet's tools (called with `{}`), not checked against a
schema here.

Two cautions, not argument faults:

- Call 139 is marked in the model itself as new and unproven: if `ScanRuler_Snapshot` takes no shot, 141 and 142
  answer not_found. That would be a fault of the camera key, not of the call.
- Call 133's figure on a sphere is its curvature, not scanner noise (the model says so): it proves the tool answers.

**reverse_build_stop is refused by design.** Its description says "always refused (unavailable)": builds run inside
FreeCAD's own process, so there is nothing to stop from outside. Call 45's refusal, naming
`reverse_feature_suppress`, `reverse_feature_rollback` and `app_force_restart`, is all there is to prove. It can be
marked proven by its refusal.

## 5. Hub BIM tools (8) — `bim-rest-model.json`

Read first: the eight entries in `agentlink/data/tools.json` (description, inputSchema, steps or make target),
`agentlink/families/bim_gaps.py` (helpers), `bimcam-findings.md` (#10, #11, #17), FreeCAD 1.1's `ArchReference.py`,
`ArchCommands.removeShape` and `Arch.makeReference`.

| Tool | Calls | Built first | What the answer must show |
|---|---|---|---|
| bim_reference | 6; 7 refused | 0 to 2: a document with a 1000 x 500 x 300 box, saved (`doc_save` answers `path`) | 6: `reference "Shelf reference"`, `file "shelf-block.FCStd"`, `part null`, `volume 150000000.0`, `box [1000, 500, 300]`. 7: REFUSED not_found |
| bim_library | 8 (search), 9 (insert); 10 refused | the same saved file, in `bim-rest-lib/` | 8: `found[0].name "shelf-block.FCStd"`, `more 0`, `roots`. 9: `inserted`, `objects ["Shelf block"]` (path by `$from` 8, `found.0.path`). 10: REFUSED not_found |
| bim_image_plane | 12, 13; 14 refused | 11: `view_render` writes a PNG and answers `path` | 12: `size [8000.0, 6000.0]`. 13: `[4000.0, 3000.0]` (or 4000 x 4000 with no Pillow). 14: REFUSED not_found |
| bim_reextrude | 16; 17 refused | 15: a straight wall 3000 x 200 x 2600 | 16: `object "Stub wall again"`, `from`, `face "Face6"`, `wire true`, `volume 1560000000.0`, `box [3000, 200, 2600]`. 17: REFUSED invalid_input (no face) |
| bim_remove_shape | 19 (read by 20); 21 refused | 18: a 250 x 250 x 2000 column "Post" | 19: `turned ["Post"]`. 20: no "Post"; a structure labelled with its old internal name, volume 125000000. 21: REFUSED (no such object) |
| bim_glue | 24; 25 refused | 22, 23: two 500 mm boxes | 24: `object "Glued blocks"`, `of 2`. 25: REFUSED invalid_input (two or more) |
| bim_rewire | 29; 30 refused | 26 to 28: three loose lines, two of them end to end | 29: `wires` two labels, `from 3`. 30: REFUSED (no such object) |
| bim_nest | 37 (seen by 38); 35, 36 refused | 31 to 34: a 1200 x 600 sheet and three rectangles | 37: `sheets 1`, `placed 3`, `of 3`, `rotations [0, 90]`, `margin "not applied …"`. 35: REFUSED (a solid as a piece). 36: REFUSED (a solid as the sheet) |

The house shell is calls 3 to 5 (the Arch tutorial's outer walls and one window, as `bimcam-bim-model.json` starts).
`view_render` (11, 38) is on the hub's own unproven list too.

Choices to know about:

- **bim_reextrude's face.** `$at` cannot join a label and a face number, so the face is written out:
  `"Stub wall.Face6"`. The answer does not depend on which face Face6 is: a box re-extruded from any of its faces by
  its own depth is the same box. So the expectation holds for all six.
- **The session folder.** `bim_library`'s `folder` and three refusal paths are `~/AgentLink/…` (the window link's
  session folder by `agentlink/gui_link.py`). No answer gives a folder alone. If the session folder is another one,
  change calls 8 to 10.
- **`doc_save { overwrite: true }` (call 2)** replaces only this model's own file from an earlier run.
- `$from` pairs: 2 → 6, 8 → 9, 11 → 12 and 13. A runner that cuts the list must keep each pair in one part.

Not checked live, so read these first: that FreeCAD's nester runs with no window and puts three pieces on one sheet;
that `Arch.removeShape` takes the hub's column as a plain box; that the image plane's size follows Pillow.

**Skipped: the nine `code_*` tools** (code_answer, code_check, code_facts, code_fem, code_missing, code_packet,
code_packs, code_project, code_span). They are the private Home add-on's; its repository is not checked out here.

## Counts

| Group | Unproven in unproven.json | Accepted call in a model now | Refusal only (by design or for safety) | No call |
|---|---|---|---|---|
| Workshop | 16 | 8 (macro_save, macro_list, macro_show, macro_unapprove, mass_calibrate, pref_history, app_recover list, printer_add) | 8 (macro_approve, macro_run, slice_open, pref_rollback, printer_status, printer_pause, printer_send, printer_stop) | 0 |
| Tutor | 2 | 2 (tutor_watch only in its off state) | 0 | 0 |
| OrcaSlicer | 5 | 5 | 0 | 0 |
| ScanRuler | 5 | 4 (already in the repo's models) | 1 (reverse_build_stop, by design) | 0 |
| BIM (hub) | 8 of 17 | 8 | 0 | 9 code_* (Home, private) |

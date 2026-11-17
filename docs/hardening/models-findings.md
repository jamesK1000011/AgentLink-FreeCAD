# Hardening models made unattended: findings (17 Nov 2026)

Goal: every test model runs on the Mac as one `batch { file }` with nothing for a person to fill in. Before this pass,
calls held text such as `<NOTE_ID>` or `<the free hole's face name from the shape_query above>`; on 16 Nov those calls
were refused and the calls after them failed in turn (for example ScanRuler reverse: the fillet refused, so every
feature id after it moved and calls 27 to 36 failed).

Nothing was run on FreeCAD here. Every `{ $from, $at }` written in this pass was read against the live answers of
16 Nov where the source call answered (`scripts/model_check.py`, below). Where no live answer exists, the answer's shape
was read in the tool's source and is named in the expect.

## What changed, per model

Agent Link for FreeCAD (`docs/hardening/models/` unless said):

| model | calls | change |
|---|---|---|
| asmtd-assembly | 51 | `b.element` was the free hole's face name. Now a query: `{ kind: face, type: cylinder, radius: 4, near: [170, 30, 14] }` (the rod's free hole once call 48 moved the rod; Face7 on 16 Nov). Index-free. |
| asmtd-techdraw | 0, new 1, 13, 52; all after | Call 0 opened `the reference copy: …`; it now opens `~/AgentLink/hardening/refs/Basic_TechDraw_Tutorial.FCStd` and the new call 1 saves it at once as `~/AgentLink/hardening/work/Basic_TechDraw_Tutorial.FCStd` (`overwrite: true`), so the work and the auto-save go to the copy. Every later call moved up by one; their `$from` and the expects' call numbers moved with them. Call 13: "title" is the template's field (call 12 listed it on 16 Nov; the refusal that day was the old placeholder key). Call 52 `td_area`: `Plate.Face6` was a guess; `Plate.Face3`, the top face call 50 found live (the cut renumbers a box's faces). |
| coredoc | 83, 84, 85; 95, 102 | `<YPR>` is `{ $from: 82, $at: "tcp.ypr" }` ([0, -90, 180] live). The two `doc_save` calls carry `overwrite: true`: on 16 Nov a second run was refused "another FreeCAD document already there". |
| hubrest | 24, 25, 26 | `<NOTE_ID>` is `{ $from: 22, $at: "note.id" }` (the shape note_add answered in unproven-hub call 114 live). |
| bimcam-points | 30 | The bunny was looked for in the session's folder and not found on 16 Nov; it is now read from `~/AgentLink/hardening/refs/PointCloud-Data_Stanford-Bunny.asc` (read only). |
| unproven-hub | runAlone | Moved to `models/alone/` (below). The 200-call list itself had no placeholder. |
| marks-model (new) | 13 + 5 | The five status marks (below). |
| alone/ (new) | 8 files | The calls that cannot be in a batch, one file per group, each saying why. |
| `docs/hardening/orca-model.json` | 1 | `<MACHINE>`, `<PROCESS>`, `<FILAMENT>` are the OrcaSlicer system presets the 16 Nov run used and OrcaSlicer took: `Bambu Lab H2D 0.4 nozzle`, `0.20mm Standard @BBL H2D`, `Bambu PLA Basic @BBL H2D`. Marked `direct: true`: that server has no batch, so it stays one call at a time. |

ScanRuler for FreeCAD (`docs/hardening/`):

| model | calls | change |
|---|---|---|
| scanruler-reverse | 20, 36, 48 | `<UPRIGHT_EDGES>` is four references to call 19's edges 0, 1, 4 and 7. Each is the edge's fingerprint with its index beside it, which `reverse_feature_add` takes as a fingerprint (`handlers.py` `_picks`). `<MOVED_PEG>` is `{ $from: 35, $at: "added.0.bodies.0" }` (7 live). `doc_save` has `overwrite: true` (refused on the second run, 16 Nov). |
| scanruler-flat | 30, 32, 44, 48 | `<BORE>` is `{ $from: 12, $at: "chains.1.chain" }` (the list is longest first; 1 live). Call 48 opens `~/AgentLink/hardening/refs/flat-test.png`, a fixture written once by the model's own `notes.makePng` (the same bytes every time). The PNG is not in the repository: a raster image there needs a reviewed hash in `.github/privacy/images.txt`, outside this pass. |
| scanruler-measure | 59; scan-noise save | `<BODY>` is `{ $from: 58, $at: "body" }` (Body002 live). The `<JOB>` convention is replaced: in a batch, heavy reads answer inline. `doc_save scan-noise-model` has `overwrite: true`. |

Searched and left as they are: `<…>` text in expects, notes and conventions (`<out>`, `<project>`, `<alias>`, `<time>`,
`<this file>`, `<session folder>`, `<the Block's internal name>`). They describe answers or files; nothing is sent.
`coredoc-gui-model.json` is a live script (`live_run`), not a batch list. `tutor-rest-model.json` and
`workshop-rest-model.json` had no placeholder.

## Calls that cannot be in a batch: `models/alone/`

| file | how it is sent | why |
|---|---|---|
| unproven-alone-1-nested-batch | `batch { file }` **as is** (`sendAsIs`) | It tests the refusal of a batch inside a batch. The file is that batch's own list. |
| unproven-alone-2-undo-rollback | as is | `history_undo` in a batch that rolls back. `model_calls.py` would write `rollback: false`, so this file must not be converted. |
| unproven-alone-3-unknown-tool | as is | A list with an unknown tool is refused whole. |
| unproven-alone-4-to-and-from | as is | `to:` and `$from` in one batch (`rollback: false` in the file). |
| unproven-alone-5-jobs | one call at a time (`direct`) | `job_start` is refused inside a batch. Call 2 has `{ $from: 1, $at: "job" }`: the runner puts in call 1's `job`, the same rule as chain.py. A person does not fill it in. |
| unproven-alone-6-agentlink-update | direct, **restarts** | It can install a new version and restart FreeCAD (it changes installed add-ons). |
| unproven-alone-7-app-restart | direct, **restarts** | It quits FreeCAD and opens it again. |
| unproven-alone-8-force-restart | direct, **restarts** | It holds the window with the Note prompt, then stops and starts the window process. |

The files marked restarts (6 to 8) also carry `personGo: true`. `unproven-hub-model.json`'s notCovered gives the
reason: a restart loses a FreeCAD session.

## The five status marks without flags

In `status.json` these five have no flags. The earlier models proved only their empty answer (nothing up, nothing held,
the recent jobs).

| tool | unattended proof (`models/marks-model.json`) |
|---|---|
| dialog_answer | Call 1: `live_run { script: "agentlink", steps: [2, 3, 7] }`. Step 2 opens the Note prompt, a modal dialog. Step 3 is `dialog_answer { button: "OK", text }` while the prompt holds the window. Its checks read `typed.text` and the note, by the person. |
| gui_unstick | Call 2: `live_run { script: "agentlink", steps: [2] }`. The prompt stays open. At the end of the replay, live_run calls the tool itself, `gui_unstick { all: true }`, and `leftOpen` names the prompt. |
| snapshot_list | Calls 4 to 6: `cmd_run { name: "AgentLink_Shot" }` (the camera button's own command) records a shot. Then `snapshot_list` lists it and `snapshot_latest` shows it. The shot's card stays open beside the window (it is not modal). |
| addon_test | Calls 7 to 10: `addon_test { addon: "AgentLink", pattern: "test_paths.py" }`, then `{ job: { $from: 7, $at: "job" } }` until done. This runs a real suite in a separate FreeCAD process. |
| queue_go | **Needs a person.** By its own rule it is called only on the person's word in chat. The held state also cannot be made unattended: the supervisor holds jobs only when macOS reports real mouse or keyboard input (`keep.person_idle_seconds`, IOHIDSystem's HIDIdleTime). `gui_input` sends Qt events, which do not count. The calls are in `needsPerson`: a long `addon_test` run, the person works in the window, `session_state` shows `queue.held`, then `queue_go` after their go. |

When the answers have been read, the marks are: `hardening_status.py mark dialog_answer,gui_unstick,snapshot_list,addon_test --live --model marks-model …`

## Models that open a reference file

| model | file | how |
|---|---|---|
| asmtd-techdraw | `~/AgentLink/hardening/refs/Basic_TechDraw_Tutorial.FCStd` | `doc_open`, then `doc_save` to `~/AgentLink/hardening/work/` at once (the only `doc_open` of a reference; `model_check.py` enforces the pair) |
| bimcam-points | `~/AgentLink/hardening/refs/PointCloud-Data_Stanford-Bunny.asc` | `points_import`: read only |
| scanruler-flat | `~/AgentLink/hardening/refs/flat-test.png` | `flat_open_image`: read only |
| orca-model | `~/AgentLink/hardening/models/orca-box.stl` | `orca_project new`: read only |

The reference-file lines in partdesign, part and sketcher name answer-key files. None of these models opens them.

The TechDraw reference on the Mac was overwritten on 16 Nov. Put in a fresh copy from FreeCAD/Examples before the next
run.

## Check

`python3 scripts/model_check.py --quiet --answers <live answers> docs/hardening/models docs/hardening/models/alone
docs/hardening/*-model.json <ScanRuler>/docs/hardening/` (the live answers are the 16 Nov run's `{ results }` files,
not in the repository):

```
34 files, 0 errors, 9 notes; live answers: 105 files
```

All 34 files are valid JSON. Every `$from` points to an earlier call, and no `<…>` placeholder is left in any
arguments. No file has a `/home/…` or `/Users/…` path. 34 `$at` paths are present in a live answer. The 9 notes are
`$at` paths whose source never answered live:

- hubrest 24 to 26: the same `note.id` shape is proven in unproven-hub 114.
- bimcam-bim 68: `ifc_find` was never run.
- marks-model 8, 9 and needsPerson 4: the `job` field (testrun.py `answer()`).
- alone-4 call 1 and alone-5 call 2: `bodies.0.name` and `job`.

`scripts/model_calls.py --all docs/hardening/models`: 0 violations.

## Still open (not placeholders)

- coredoc 83 and 86: the start pose [0, -90, 90, 0, 0, 0] is a wrist singularity (status-findings b-18), so `robot_move`
  to the waypoint may answer `reached false` even with the right ypr. A pose with axis 5 off zero would test reach.
- scanruler-flat: the reference from call 44 reaches 32 calls back. This is safe in one batch part (70 calls ran as one
  part on 16 Nov). If a part boundary falls between 12 and 44, run `from: 12`.
- unproven-hub (200 calls) is answered in parts. Its conventions already say where to restart a part.

## Run order on the Mac

Once, before the run (files, not calls):

1. `~/AgentLink/hardening/refs/Basic_TechDraw_Tutorial.FCStd`: a fresh copy from FreeCAD/Examples
   (`Basic_TechDraw_Tutorial_Example_Files/Basic_TechDraw_Tutorial.fcstd`).
2. `~/AgentLink/hardening/refs/PointCloud-Data_Stanford-Bunny.asc` from FreeCAD/Examples (`Point_cloud_ExampleFiles`).
3. `~/AgentLink/hardening/refs/flat-test.png`, written in the ScanRuler checkout:
   `python3 -c "import json;open('/tmp/mkpng.py','w').write(json.load(open('docs/hardening/scanruler-flat-model.json'))['notes']['makePng'])" && python3 /tmp/mkpng.py ~/AgentLink/hardening/refs/flat-test.png`
   (sha256 d07587a2accaf6675639994431f22af750b1cba1bb0de7553fcab0477a5a01a8).
4. `~/AgentLink/hardening/models/orca-box.stl` from `docs/hardening/orca-box.stl`; `mkdir -p ~/AgentLink/hardening/work`.
5. Batch files: `python3 scripts/model_calls.py --all docs/hardening/models --out-dir <dir>`, and
   `python3 scripts/model_calls.py <model> -o <dir>/<name>-batch.json` for each ScanRuler model and for the two add-on
   models. The `alone/` files marked `sendAsIs` are copied as they are. Put all of them in `~/AgentLink/hardening/models/`.

Then, each line one `batch { file, budget: 100 }`, with `from: next` until the answer has no `next`:

1. sketcher, partdesign, part, draftmesh-draft, draftmesh-mesh, draftmesh-surface
2. sheetfem-sheet, sheetfem-fem, bimcam-bim, bim-rest, bimcam-cam, bimcam-points
3. asmtd-assembly, asmtd-techdraw, coredoc
4. unproven-hub, then at once `alone/unproven-alone-1` to `-4` (as is, each its own `batch { file }`), then
   `alone/unproven-alone-5-jobs` one call at a time
5. ScanRuler: scanruler-flat, scanruler-measure, scanruler-meshtools, scanruler-reverse
6. add-on models, when Workshop / Tutor are installed: workshop-rest-model, tutor-rest-model
7. window: hubrest; then `live_run { script: "reset" }` and `live_run { script: "~/AgentLink/hardening/models/coredoc-gui-model.json", budget: 180 }`
   (the live script copied there); then marks-model
8. OrcaSlicer Agent Link (its own server, no batch): orca-model, one call at a time
9. Only with the person there: marks-model `needsPerson`, one call at a time
10. Last, one file at a time, after the person's go (one go covers all three), each after the heartbeat is back:
    `alone/unproven-alone-6-agentlink-update`, `-7-app-restart`, `-8-force-restart`

<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Changelog

All notable changes to Agent Link for FreeCAD. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release, 0.3.0 (the version in `package.xml`,
`pyproject.toml` and the server), is being prepared.

### Added

- `session.by`: who the call in hand is for, `"agent"` by default and `"person"` while a click in Agent Link's panel or an add-on dock it hosts runs a tool (`hooks.as_person`), so an add-on can tell the person's own actions from the agent's (SafetyNet labels a checkpoint taken before a clicked macro "My checkpoint").
- `dialog_answer` types before it presses: `text` fills a text prompt (a QInputDialog, or a dialog's one text field) and `item` picks from a prompt's list, so a note's prompt can be answered. A batch of `gui_input` (and `dialog_answer`) calls runs while a dialog is in front, aimed only inside it. The panel's Pin a Note says what to do next ("Click the part where the note goes. Esc cancels.") until the click or Esc, and Esc now cancels it.
- `gui_input` targets for what is not a widget: `{tab: {text, under?}}` clicks a tab bar's tab (answered as `{class: "QTabBar", tab}`), and `{item: {text, under?, column?}, check?: true}` a list, tree or table row, scrolled into view first; `check` clicks the row's check box, setting the model's check state when the click did not take, and says which. A wait over 3000 ms is refused with the advice to split it into several waits.
- The output folder (`~/AgentLink`) clears itself of what Agent Link made there and no longer needs: every file or folder a tool makes there is recorded in `outputs.jsonl` (path, kind, tool, time, size), and only those are cleared — shots past the last 50 and 3 days, solver and job runs (`fea_`, `elmer_`, `buckle_`, `shell_`, slicer, CAM) past 14 days, FreeCAD backups beyond its own count past 7; exports are only listed. To the Trash, at Agent Link's start and then at most once a day when the heavy-job queue is free, never what a document links to, an open file or anything under `install`, `settings`, `crash`, `checkpoints` or `autosave`. Settings in `Mod/AgentLink/Outputs` (ShotKeep, ShotDays, RunDays, FCBakDays, Auto). `outputs_clean` (core) shows it as a dry run, or does it with `dry_run: false`.
- `gui_input` (group `dev`, not in the lean list): mouse and keyboard input to the FreeCAD window's own widgets for GUI checks, sent as Qt events from inside FreeCAD (never the system cursor or keyboard): click, press, move, release, drag, scroll, key, type, wait and shot steps aimed at a point in the 3D view, a model point projected there, a widget found by name, text, tip, class or panel, or a point in the window. A step whose dialog or menu holds the window answers at once (the window's link sends the answer early), and `dialog_answer` or more `gui_input` aimed inside it goes on; anything outside a dialog in front is refused.
- `addon_test` (group `dev`, not in the lean list): an installed add-on's own tests, or Agent Link's, run in the background in a separate FreeCAD command-line process on this computer (its own process group, stopped at its timeout or when FreeCAD quits), never the window or the hidden FreeCAD, with a fresh `AGENTLINK_HOME` and FreeCAD user folder. pytest when FreeCAD's Python has it, else a small built-in runner (unittest classes, plain `test_*` functions, simple fixtures, `tmp_path`, `monkeypatch`; anything more is skipped with the reason). `addon_test { addon }` answers at once with the job (or the result when it ends within 20 s), `addon_test { job }` the counts so far or the final counts, time and each failure's last traceback lines, `addon_test {}` the recent jobs; the full log goes to `~/AgentLink/tests/`, its last line saying how the run ended (done, timed out or killed). Only add-ons the launcher installed may be tested. A heavy call's own `timeout` now sets the watchdog's deadline for it.
- `crash_collect`: FreeCAD's document-recovery folders, its crash.log and the system's crash reports for FreeCAD copied into `~/AgentLink/crash/<time>/` (copies only); `dialog_answer` runs it before Document Recovery's Cleanup, so a crash can still be looked into.
- The `notice` service (`docs/hooks.md`): an add-on's short line for the agent, such as a new screenshot, rides once on the next answer as `"notice"`; a slow or failing provider never holds an answer up.
- An MCP server that drives FreeCAD headless or in the person's own window:
  documents, Part and PartDesign modelling, sketches with the solver's
  reading, parameters and spreadsheets, measurement, materials, FEM
  strength (Gmsh and CalculiX), TechDraw pages with GD&T, Inspection,
  meshes and point clouds, Assembly, CAM with a stock simulation, Draft
  text and surfaces, BIM and IFC, OpenSCAD and Robot, as tool groups with a
  guide each. Every change is one FreeCAD undo step; `batch` stands or
  falls whole.
- The lean tool list (core and view) by default, the rest turned on by
  group with `tool_groups`; `AGENTLINK_TOOLS=full` lists every tool.
- Headless pictures (`view_render`): any view or four, cut open, zoomed,
  with wall-thickness, stress and deviation maps.
- The window link: the workbench's Start link pairs with the server over
  127.0.0.1, and calls run on FreeCAD's own thread in the open document; a
  supervisor restarts a FreeCAD that dies under a call.
- The Agent Link panel beside the model tree: Notes, Steps (the build played
  back), Review, Activity and the tabs add-ons register, with a token-usage
  strip that says it is an estimate, not billing; Screenshot for the agent
  (Alt+Shift+S).
- Unattended use (Mac): harmless dialogs answered, the pinned document,
  the heavy-job queue, the Addon Manager headless on 1.1+, app updates
  smoke-tested before they are taken.
- The add-on API (API 1, `docs/hooks.md`): add-ons bring tool families,
  data-defined tools (`tools.json`), guides, panel tabs, reviewers and
  button echoes, found at start and never named in Agent Link's code;
  `app_extensions` installs them.
- Tools as data: one-command wrappers defined in `agentlink/data/tools.json`
  and run by the runners.
- The Studio Light and Studio Dark preference packs.
- Agent Link's own icons, drawn in FreeCAD's style, with their credits.
- The Setup check and Updates commands in the Agent Link menu.
- Release preparation: a beginner's README with a generated tool-group
  table (`scripts/tool_summary.py`, checked by the tests), copy-paste client
  configs (`docs/clients/`), `SETUP.md` for agents, the headless setup check
  (`agentlink-freecad --check`, `python3 agentlink_headless.py --check`),
  complete Addon Manager metadata, licence headers or `REUSE.toml` entries
  for every file with the licence texts in `LICENSES/`, a `pyproject.toml`
  for `uvx agentlink-freecad` (`docs/packaging.md`), and this changelog.
- The privacy and identity check in CI.
- A privacy statement in the README, numpy declared in `package.xml`, and
  `server.json` for the MCP Registry (it lists the PyPI package
  `agentlink-freecad` once that is published).

### Changed

- `fea_solve` solves through FreeCAD's own FEM: the study becomes an analysis (`<body> strength (fea_solve)`, replaced on each solve) with FEM's CalculiX solver, Gmsh mesh, material and fixed / force / pressure / self-weight constraints, meshed by FEM's Gmsh tools, run by FemToolsCcx, its results loaded into the analysis for the FEM workbench. Agent Link's verdicts (safety, peak places, warnings, the stress map) read the same results. Several parts, nonlinear, refined regions, pinned holds and heat or spin loads still run Agent Link's own deck, as do `fea_modes`, `fea_buckle`, `fea_heat` and `fea_shell`; `solvedBy` says which ran and why. It now takes an undo step (it adds the analysis).
- `asm_explode` makes FreeCAD's own Exploded View (Assembly's Create Exploded View: a Normal move step a part, applied by it) and names it in the answer; it moves the placements itself only where that cannot be made here, saying why. `asm_motion` keeps its own keyed poses: Assembly's Simulation cannot be imported or run without the window (its module needs Qt at import, and its frames come from the task panel).
- `import_file` reads glTF/GLB, Collada and 3DS with FreeCAD's own importers first (Import's glTF reader; BIM's `importDAE`, which needs pycollada, and `import3DS`); Agent Link's readers (meshformats) read them only where those are not here or read nothing, when `units` or `up` is given, or for `solid: true`, and VRML. The answer's `read.reader` says which ran and, on the fallback, why FreeCAD's did not.
- DXF is written by FreeCAD's own writer (`Import.writeDXFShape`) for a one-layer drawing — `export` to DXF of a view or a section, `meshobj_unwrap` and the mesh flattening — and by Agent Link's R12 writer only where layers are kept apart (hidden lines on their own) or FreeCAD's is not here; the answer's `writer` says which.
- A TechDraw dimension's ISO 286 fit (`td_dim`, `td_tolerance` with `fit`) takes its limits from TechDraw's own Hole/Shaft Fit table where it has the code; Agent Link's table covers the rest (js, p, IT5) and is given, with what TechDraw said, where the two disagree. The answer's `fitFrom` says which.
- Mass and materials belong to the add-on that owns them when it is installed: `measure_mass` with no material or density given answers with its `mass_properties` service (as printed, inserts included), and `material_set` / `material_clear` hand a material it keeps (the printing filaments) to its `material_set` service, which keeps the materials record and FreeCAD's material; answers say where they came from. Without it, or for a library card or custom material, Agent Link answers as before.
- The Review tab's Body check opens FreeCAD's own Check Geometry (Part workbench) on the body and lists Agent Link's extras beside it; `body_check` reads FreeCAD's check (`shape.check` with its boolean checks) first and adds only what it does not look for (slivers under 0.01 mm, very short edges, one closed solid).
- Every tool is listed with its own group, so enabling a group lists only what it says: `surface_loft`, `surface_points`, `surface_thicken`, `surface_fill` and `surface_polynomial` in surface, `draft_fix` in draft, `asm_rigid_group` and `asm_new_part` in assembly, `scad_tidy` in openscad, `points_structure` in points, `robot_tool` in robot, `sheet_cells` in sheet, `pd_shaft` in feature. `export` (every format) is in core; `export_file` stays callable as an unlisted alias. A family may declare `REPLACES = (group, …)`: those groups of Agent Link's are left out of the listing (lean or full) while that add-on is installed, still callable by name — for the mesh group when a mesh add-on covers it.
- Read-only calls no longer switch FreeCAD's workbench: only a call that changes the document (its tool's `changes` flag, so a changing tool's read action counts as a read) or a read an add-on declares as opening a panel (`OPENS` on its family) brings its bench up and lights a button; reads show in the Activity list (and, for those that show something, the caption and selection) and leave the bench where the person has it.
- The panel in a narrow dock: the Activity tab's check box reads "Agent's steps", its lines are cut in the middle with the whole line in a tooltip and the last column stretched; every Did name has one form, "Area › What" from the declared areas ("Window › Input", "Report › Read", "Document › Save"); "Save as Macro…" in Title Case; a step's line leaves out its type where the label is the same ("Step 1 of 1 — Pad (Length 20.00 mm): …").
- The supervisor's restart after a hang or crash answers and forgets only the calls in hand at that moment (a call sent right after the answer went to the fresh FreeCAD and was dropped from the watchdog's view, so it could wait for ever), and the watchdog leaves the dead child's call alone while the restart and recovery run (a slow recovery was counted as a second hang and the fresh FreeCAD stopped mid-recovery).

- Agent Link has its own repository (it began in ScanRuler's `freecad-spike`
  branch).
- Agent Link is a thin hub: printing, slicing, printers, cutting, milling,
  fits, threads, mass and print-aware strength moved to Workshop Make;
  standard parts to Workshop Parts; electronics and documents to Workshop
  Electronics and Documents; the OrcaSlicer bridge to Agent Link for
  OrcaSlicer; checkpoints, recovery, the settings log and macros to
  SafetyNet; texture tools to Texturizer; building-code checks to a separate
  add-on. Each keeps its own repository and licence.
- AddonKit is retired: Agent Link carries its own records, shapes, data
  loader, CalculiX reader and sheets.
- Shared argument and refusal helpers (`picks`, `protocol.bad`, `paths`)
  replace many per-tool copies; refusals keep each tool's own words.
- The server reports version 0.3.0, as `package.xml` does.
- `freecadmin` is 1.0.0, the oldest FreeCAD CI runs; 1.1 is recommended,
  as the README and the setup check say.

### Removed

- Agent Link's copies of what moved to add-ons, and the fits data nothing in
  it used.

### Fixed

- Notes pinned before faces were anchored now follow too: the first re-find projects the note's point onto the faces (along each face's normal, landing on it, within 3 mm or a tenth of the part's size), takes the nearest (its own face when that still fits), moves the pin there and keeps the face's mapped name and normal from then on; nothing near is flagged lost. Anchored notes use the same projection when their mapped name is gone, so a pin follows a pad made longer. `note_list` answers which notes it moved (`followed`) and says when it could not look.
- `fea_setup` lists the study's holds and loads whose face query matches no face any more ("Load 1: no face at z = 20 facing +Z now; the part changed?"), and `fea_solve` refuses to run with one rather than solve without it.
- `asm_explode` in the window fell back to moving placements ("'NoneType' object has no attribute 'redrawLines'"): the Exploded View and each move step now get their view providers before anything is set on them, as Create Exploded View's own task does; headless, with no view object, none is made.
- A note pinned on a face stays on that face when a later step renumbers the faces (a Hole made a pad's top Face5 where it was Face6, and the note pointed at a side): it keeps FreeCAD 1.x's mapped name of the face, with its point and normal as the fallback, and is found again after each change, in `note_list` and in the panel; where neither finds it, it is flagged as lost (⚠ in the panel, `lost` in the answer) rather than moved to a guess.
- `fea_setup` on a body that already has a study says what it kept (its holds and loads, added to from then on) or dropped (with `reset: true`, or a study on another body); `fea_hold` and `fea_load` refuse an identical hold or load already in the study, which applied it twice (a 100 N load added again came to 200 N).
- The SVGs Agent Link writes (charts, drawing sheets, GD&T symbols) name Helvetica alone: the generic sans-serif made Qt warn of a missing "Sans-serif" family in the Report view.
- A panel whose dock FreeCAD restored wider than 420 px at start (a content's size hint once grew one to about 640 px) is put back to 354 px once, at the first placement after the window shows; a width dragged later in the session stays. `scripts/sync_shared.py` copies Agent Link's shared files (layout.py) over the add-ons' copies in checkouts given to it, keeping each copy's licence line (`--check` only reports).
- A `gui_input` click in the 3D view with the Gesture navigation style opened the view's context menu instead of selecting: the style times a press by the wall clock at each event, and the click's focus change ran between press and release. The pointer's arrival and focus now come first, with the window caught up, then press and release back to back; the click's answer says what was `selected`.
- The agent's caption over the 3D view no longer raises "Internal C++ object already deleted" in the Report view when its document is closed before the caption fades.

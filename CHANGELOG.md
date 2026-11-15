<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Changelog

All notable changes to Agent Link for FreeCAD. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release, 0.3.0 (the version in `package.xml`,
`pyproject.toml` and the server), is being prepared.

### Added

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

- The agent's caption over the 3D view no longer raises "Internal C++ object already deleted" in the Report view when its document is closed before the caption fades.

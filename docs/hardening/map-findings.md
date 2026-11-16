# map: tool lookup by what FreeCAD knows (tool_groups find / now) — findings

Patch: map.patch (16 files; FILES not regenerated). `python3 -m pytest -q`: 708 passed, 311 skipped (FreeCAD tests skip here).

## What was built
- `agentlink/data/tool_index.json` (+ `tool_index.schema.json`; covered by LICENSE-DATA / REUSE's `agentlink/data/**`): one entry per tool
  `{ workbench, commands, words, source, date }`. source and date are there because `agentlink/datafiles.py` refuses a data file whose
  entries lack them (tests/test_tooldata.py test_own_data_files_check).
- `scripts/tool_index.py` generates it (`--check` for stale) from `agentlink/echo.py` (WORKBENCH, COMMAND, CAM_OP, CAM_DRESSUP,
  command_for for asm_joint's kinds) plus the hand-kept `scripts/tool_index_more.py` (more commands, words, prefix words, workbenches
  for prefixes the echo does not know). The echo stays the source: its command is always the entry's first.
- `agentlink/toolindex.py` (no FreeCAD import): load / declare / entry, rank (find), fits (now), first_sentence, bench_of.
- `agentlink/tools.py`: tool_groups find re-ranked, `now: true`, `group: g` gives `{tool, does}` rows, `tool:` up to 20,
  description and LEAN_NOTE rewritten (find -> card -> call; enable only when a task uses most of a group). New module-level
  `now_state(doc, commands)`.
- `agentlink/tooldata.py` + `data/tools.schema.json`: optional `workbench` (string), `commands`, `words` (lists of strings) in an
  add-on's tools.json; `build()` passes them to `toolindex.declare`. Nothing of an add-on is stored in the hub. For an add-on tool with
  no such fields, find/now fall back to what its family declared for the echo (WORKBENCHES / COMMANDS / command_for).
- `agentlink/guides/start.md`: three bullets teaching find -> card -> call, now, and when to enable.
- `docs/hardening/freecad-1.1.0-commands.txt`: 1,160 command names (see Verification), which a test holds the index and the echo to.

## Coverage (405 tools defined in this repository: 404 listed + the export_file alias)
- workbench set: 322; null: 83 (session, documents, objects, window, preferences, notes, views, measure, links, varsets …).
  By workbench: BIM 53, PartDesign 34, Part 33, TechDraw 32, Mesh 21, Draft 19, Fem 19, Sketcher 19, Assembly 18, Spreadsheet 16,
  CAM 15, Surface 11, Points 9, Robot 7, Inspection 6, OpenSCAD 6, Material 4.
- with at least one verified command: 291; with none: 114. 549 distinct commands named.
- with search words: 404; without: history_redo.
- Inventory check: docs/hardening/inventory.json files 408 tools under AgentLink-FreeCAD; 4 of them are not defined in this checkout
  (collab, fea_frame, history_checkpoint, history_restore: add-ons' tools, tests/test_no_addon_names.py lists three of them) and are
  not indexed. app_extensions (agentlink/ext.py) is.

## Verification of command names
- Source: FreeCAD 1.1.0 (the tag checked out; the Mac runs 1.1.3 — a command added or renamed between them would not show).
  Names read from all 56 `Command*.cpp` files under src/Gui and src/Mod/*/Gui (fetched one by one) and every
  `addCommand("…")` in the Python modules; CAM's operations from Path/Op/Gui/Base.py (`"CAM_%s" % name`) and each
  `SetupOperation("…")`. 1,159 names.
- Every command in the index is in that list except one: `Std_AddonMgr` (tools addon, app_extensions) — wiki page
  Std_AddonMgr.md only; the Addon Manager is a submodule not in the source tree read.
- Not verified live: that each named command is registered in the Mac's 1.1.3 window and that `isActive()` answers usefully for it.
  now_state swallows any failure and counts an unknown command for nothing.
- The tool -> command mapping itself is judgement (from each tool's description; handlers were read only where the description left
  doubt). "Does the work of" is loose for multi-action tools (sketch_add, sketch_constrain, draft_modify, td_view_more, cam_op,
  fem_add list one command per kind they offer). Where unsure the command was left out (the 68 tools with a workbench and no command, e.g.
  asm_fits/limits/pose/sweep/list, fea_buckle/modes/probe/results/…, insp_* reads, material_*, sheet_read/rows/table/…, td_gdt,
  td_datum, td_geometry, bim_covering, meshobj_refine/offset/edit …).

## Found on the way (fixed, from source; needs a live look)
- `agentlink/echo.py` COMMAND named 20 BIM commands FreeCAD 1.1.0 does not register: BIM_Wall, BIM_Structure, BIM_Roof, BIM_Stairs,
  BIM_Window, BIM_Space, BIM_Level, BIM_Building, BIM_SectionPlane, BIM_AxisSystem, BIM_Frame, BIM_Equipment, BIM_Panel, BIM_Rebar,
  BIM_Truss, BIM_CurtainWall, BIM_Fence, BIM_Pipe, BIM_Schedule, BIM_Covering. FreeCAD 1.1 source: src/Mod/BIM/bimcommands/*.py
  registers them as Arch_Wall, Arch_Structure … (`FreeCADGui.addCommand("Arch_Wall", …)`). Changed to the Arch_ names;
  bim_covering's entry removed (1.1.0 has neither BIM_Covering nor Arch_Covering). tests/test_echo_map.py and test_echo_declare.py
  updated (they asserted "BIM_Wall"). Unproven: whether the echo lit nothing for these before — flash_command was not run here.
- CAM operation commands (CAM_Profile …) are registered at run time, so they are missing from a plain grep of addCommand; they are
  real (Path/Op/Gui/Base.py).

## Ranking (proven in plain Python against all 404 descriptions, tests/test_tool_index.py)
- "fillet edges" -> part_fillet, pd_fillet first (was: two unrelated tools above pd_fillet). "drawing dimension" and
  "techdraw dimension" -> td_dim first. "PartDesign_Pad" -> pd_pad; "Mesh_Decimating", "simplify stl" -> meshobj_decimate;
  "gcode" -> cam_post in the top 3; "bill of materials" -> asm_bom.
- Order: tools matching every word, then fewer; inside that by score (name 10 / substring 6, index word 7, command token 6, workbench
  named +5, group +3, first sentence +3, rest of description +1.5), a small cost for name words the search did not ask for.
- "does" is the first full sentence (ended at ". ", never a colon), cut at a word with " …" past 160 (120 in group listings).
  A find reply of 10 rows measured about 2.1-2.3 kB with a mocked FreeCAD.
- Weak spots seen: a search of one common word ("stress", "thread") gives a flat list of the family; part_fillet ranks above pd_fillet
  for "fillet edges" (both first two) — `now: true` in a PartDesign document puts pd_fillet first.

## now: true
- Pure scoring (toolindex.fits) is tested here: command active +6 / all known inactive -3, active workbench +4, sketch in edit +6 for
  Sketcher tools, selected object's workbench +3, picked edge/face/vertex matching an input name +2, document holds that workbench's
  objects +2 (+3 headless), no document -> tools of Std_New/Std_Open/Std_Import.
- With find: the search's first 60 hits re-ordered by score + 2 x fit, each row with "fits". Alone: every tool with a positive fit.
- Headless: reply's now is { window: false } and the note says it went by the document only.
- NOT proven: the window branch of tools.now_state on a real FreeCAD (activeWorkbench().name(), ActiveDocument.getInEdit(),
  Selection.getSelectionEx(), Command.get(n).isActive() for up to ~550 commands in one call — cost unknown; each is wrapped).
  It ran only against MagicMock stand-ins here. The FreeCAD test (test_tool_groups_now) covers the headless branch and returns
  early when GuiUp; a window run should be added to scripts/live.
- Python-made objects are filed by their proxy's module (draftobjects -> Draft, Arch*/bim*/nativeifc -> BIM, Path* -> CAM,
  femobjects -> Fem, JointObject -> Assembly); module names taken from knowledge of FreeCAD's layout, not each checked.

## Changed behaviour to know about
- `tool_groups { group: g }`.tools is now a list of `{ tool, does }`, not names (tests/test_live_findings.py updated; nothing else
  in this repository read it; docs/hardening/inventory.json was made from the old shape).
- An add-on whose tools.json carries the new fields is refused by an older Agent Link ("unknown fields"): add-ons should adopt them
  only once they require this version.
- BRIEF.md says not to edit tools.py; this task required it (tool_groups, LEAN_NOTE, now_state). health.py, protocol.py, keep.py untouched.
- New FreeCAD tests (cannot run here): test_tool_groups_find_ranking, _twenty_cards, _now, _now_state_never_raises, and the group
  listing assertions in test_tool_groups_filters. With add-ons installed in the test FreeCAD the exact-first assertions
  (e.g. find "mesh decimate" -> meshobj_decimate first) could be beaten by an add-on tool of the same words.
- CHANGELOG.md: one Added and one Changed line.

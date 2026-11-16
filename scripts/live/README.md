# Live window scripts

Re-runnable checks of the add-ons in FreeCAD's own window, driven the way a person would: clicks, drags and typing through `gui_input`, with headless read-backs that say whether each step did what it should. Run them after changes and before releases.

They are data, not code: an agent connected to Agent Link replays them with the MCP tools. Nothing here runs by itself.

## Files

| File | What it drives |
|---|---|
| `reset.json` | Rebuilds the shared test document `WindowTest` from scratch (a 40 × 30 × 20 mm pad). Every script starts with it. |
| `agentlink.json` | Agent Link's panel: Notes (Pin a Note, typed into the dialog), Steps (Play), Activity; view clicks select; tab targets. |
| `scanruler.json` | ScanRuler: workspaces, Create Feature labels, Fillet edge picks and Create Fillet, Split View's reason, the panel's width, state saved with the document. |
| `texturizer.json` | Texturizer: the sidebar's part choice, a texture tile, FreeCAD's own Undo and Redo of it, the rotate ring, Add to Document and the linked result following a pad change. |
| `tutor-watch.json` | The Tutor's watch mode with two roles (a teacher agent and a student agent who stands in for the person, `ROLES.md`): the status-bar sign, the person's events in order, a long poll a milestone ends early, Ask Claude, watch off; then a 30-minute soak loop. |

`workshop.json` covers Workshop, which now holds SafetyNet too.

## Format

```json
{
  "name": "…",
  "needs": ["ScanRuler-FreeCAD"],
  "steps": [
    {
      "name": "what this step checks",
      "calls": [ { "tool": "…", "arguments": { } } ],
      "expect": [ { "call": 0, "path": "result.steps.1.selected.0", "equals": "Pad.Face6" } ],
      "shot": "optional_name"
    }
  ]
}
```

- `calls` go to `batch` as they are (`rollback: false`, `stopOnError: false`).
- `expect` checks one value of one call's answer. `path` walks the answer with dots, numbers for list items. Paths: dots for keys and list indices; `[*]` means any item of a list, `[-1]` the last.
- Checks: `equals`, `contains` (text or list), `atLeast` / `atMost` (numbers), `exists: true|false`, and `noneContain: [words]` for a list of lines, with `ignoreLinesWith: [texts]` to skip lines that aren't ours.
- FreeCAD itself logs `(qt.qpa.fonts) … missing font family "Sans" / "Sans-serif"` (seen when a sketch is made and when TechDraw draws its own templates; none of the add-ons name those families any more): Report view checks ignore those lines.
- `role` (two-role scripts, `ROLES.md`): `"tutor"` steps are the teacher agent's calls; `"student"` steps are `gui_input` calls with `as: "person"`, sent on their own. `direct: true`: each call on its own, not in a batch (a waiting `tutor_watch`). `parallel`: the call waits while the next step runs. `look`: what the shot should show. `$name` values are filled in from earlier answers (the script's `conventions` say how).
- `shot`: a `gui_input` shot of the window after the step, to look at when a check fails.
- Waits: `gui_input` takes at most 3000 ms per wait; repeat waits for longer.

## How to run (for an agent)

`live_run { script: "reset" }` then `live_run { script: "agentlink" }` (group dev) does steps 1–2 below in one call each: it batches each step's calls, checks every `expect` and answers pass, fail or skipped per step with the failing check's path, wanted and got. It skips two-role steps (`role: student`, `parallel`: they need two agents) and steps whose `$name` is not known yet (give `vars`). By hand:

1. Run `reset.json`'s steps, then the script's.
2. For each step: `batch` its calls, check each `expect`, and note pass or fail with the value seen.
3. On a failure, take the step's shot, read `report_read { problems: true }`, and report: step, check, value seen, Report view lines.
4. At the end: a pass/fail list, and `doc_save`.

Rules that come from the field notes (`claude/gui-input-field-notes.md` in the project):
- Points on parts: `{view_world: [x, y, z]}`; set the camera with `cmd_run Std_ViewIsometric` and `Std_ViewFitAll` first.
- Faces renumber when the model changes: pick faces by geometry (`{normal, z}` queries), not by name.
- Add `class: "QPushButton"` when a toolbar button has the same text as a panel button (Undo).
- Rings that share a point: start a Z-ring drag at (0.707 R, 0.707 R, z).
- Turn Texturizer's timing probe off at the end if a step turned it on.

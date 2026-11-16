# hubfix: findings (16 Nov 2026)

Checkout: the hub at main (9b4bc52). Patch: `hubfix.patch` (22 files, new files included, FILES excluded).
Here: `python3 -m pytest -q` 828 passed, 338 skipped (the skipped need FreeCAD); `node packaging/mcpb/test/launcher.test.mjs` passes; every changed .py compiles with python3.11.
Nothing below was run in FreeCAD. "Proven here" means plain-Python or Node tests; "needs the Mac" is everything that touches FreeCAD or Qt.

## Before this is pinned (main session)

1. **Regenerate FILES.** New files the launcher must fetch: `agentlink/extstate.py`, `agentlink/data/nexthint.json`, `agentlink/data/nexthint.schema.json`, and four tests (`tests/test_extstate.py`, `test_echo_pace.py`, `test_nexthint.py`, `test_hubfix_small.py`). Without `extstate.py` in FILES the installed add-on fails at import (`tools.py` and `families/__init__.py` import it). `tests/test_files.py` fails in this checkout until FILES is regenerated (the files are intent-to-add).
2. I edited `agentlink/protocol.py` (6 lines, the `background` refusal) and `agentlink/tools.py`: BRIEF2 keeps other agents out of both; this task's brief sent me to them. Not touched: runners.py, data/tools.json, tooldata.py, families/bim*.py.
3. The launcher changed (`packaging/mcpb/server/index.js`): the new answer fields only appear once the new launcher serves (it is handed over by the same update, as today).

## Job 2: agentlink_update and add-ons left out

**How it was.** `families.load()` caught the add-on's import error, wrote one line to stderr and went on. The smoke test (`agentlink/smoke.py`, a separate process started by the launcher) built the server through the same path and never looked at what was left out, so it passed. `agentlink_update` is answered by the launcher (`packaging/mcpb/server/index.js` `selfUpdate`), not by Python.

**Built.**
- `agentlink/extstate.py` (new, plain Python): every extension left out is noted with its error and stage (import, api, tools) where the families load (`families/__init__.py load()`, `tools.py build_server`), plus what each loaded add-on brought (groups, tool count). A SyntaxError's words keep the file name and line, never the folder. Written to `the session folder: extensions.json` under `hidden` or `window` when a server is built: `{ t, pid, version, loaded, leftOut, noTools, groups { group: count } }`. The supervisor can read it with `extstate.read()`; I added no supervisor behaviour.
- Smoke test: reports `extensions { loaded, leftOut [{ extension, error }] }` and `groups`, and **fails** for each add-on named in `AGENTLINK_LOADED_BEFORE` that is now left out. It does not overwrite the record of what runs. The launcher sets that variable from the hidden FreeCAD's record, for both smoke runs (staged, and in place). A failed smoke test is handled as today: staged, the version is marked bad and never installed; in place, the previous add-ons are restored and nothing restarts. `smoke.against()` (the `addon` tool's and `app_install`'s smoke test) gets the same list from the running process.
- `agentlink_update`'s answer: `leftOut [{ extension, error }]`, `lostGroups` (groups in the record before that the smoke test's server lacks; only when both are known), `warning`, and the same warning appended to `note` after "WARNING:". Also on "Already the newest" (from the running FreeCAD's own record, since no smoke test runs then). `versions.json` records the add-ons left out. Description updated.
- `session_state`: `leftOut` and `warning` while any is left out in that FreeCAD. `tool_groups` (no arguments): `addonsWithoutTools [{ extension, error }]` and `warning` (left out, or loaded and gave no tools).

**Judgment calls.**
- An add-on that did not load before either (a first install, or no record yet) does not fail the update: it is a warning. That is the brief's rule ("one that loaded before no longer loads"). Consequence: the first update onto this code has no record, so a broken add-on warns rather than fails that one time.
- An add-on whose *one family's* `tools()` raises is in `leftOut` too (stage tools) and fails the smoke test if the add-on loaded before.
- A plain `pytest` run with FreeCAD on the Mac (not through `addon_test`, which sets its own AGENTLINK_HOME) would rewrite the `hidden` record with the test process's reading. Not guarded.

**Proven here.** `tests/test_extstate.py` (7 run): the rules, the record on disk, and `families.load()` against three throwaway add-ons on the path (SyntaxError, wrong API, good). Launcher test: an update whose smoke test passes with an add-on left out answers `leftOut`, `lostGroups: ["scan"]`, `warning`, the note's WARNING, and the smoke test receives only plain module names; "Already the newest" repeats it; `extensionReport` unit cases.

**Needs the Mac.** `test_extstate.InTheServer` (skipped here): a real server with a broken add-on on the path. And live, in this order (use a throwaway add-on, not a real one):
1. `session_state {}` → no `leftOut`. `tool_groups {}` → no `addonsWithoutTools`. Check `the session folder: extensions.json` exists with `hidden.loaded` naming the installed add-ons and `hidden.groups`.
2. Break one installed add-on's `agentlink_families.py` in the Mod folder (add a line `def x(:`), then `agentlink_update {}`. Expect with nothing new upstream: `restarted: false` and no leftOut yet (the running FreeCAD loaded it before the edit) — so instead run `app_restart {}` / start the hidden FreeCAD again, then `session_state {}` → `leftOut: [{ extension: "<pkg>.agentlink_families", error: "SyntaxError: … (agentlink_families.py, line N)" }]` and `warning`; `tool_groups {}` → `addonsWithoutTools`.
3. The real case: pin a commit of an add-on with a syntax error and run `agentlink_update {}` while the good one is loaded. Expect `isError`, "failed the smoke test … the add-on <pkg> loaded before and no longer does (SyntaxError …)", FreeCAD still on the version before, the tool count unchanged.
4. `agentlink_update {}` again with nothing new while an add-on is left out → `leftOut`, and `note` ends with the WARNING.

## Job 1: echo delay in batches

**The waits on the echo path** (all in `agentlink/echo.py`; I found none elsewhere — `overlay.flash`, the caption and the clear-selection timers do not block):
| wait | full pace | short pace |
|---|---|---|
| `before`: `_paint()` then `_wait(EchoDelay)` | both | one `_wait(EchoBatchDelay)`; with 0, one `_paint()` and no wait |
| `flash_command(settle=…)`: one paint after a bench switch | kept | **kept**, only when the bench did switch (see below) |
| `_container`, `asm_joint`: `_wait(EchoDelay)` with the two faces lit | kept | skipped (the faces stay selected) |
| `after`: one `_paint()` at the end | kept | kept (it is what shows the selected result; not a timed wait) |
| `activateWorkbench`, `_mode` (a sketch opened in edit), `fit()` | unchanged | unchanged: FreeCAD's own cost, not a wait of ours |

**Built.** `echo.pace(batch, changing, full_ms, batch_ms)` (plain Python): a single call is full; in a batch the first three *changing* calls are full, later calls short (shown reads after them too), the batch's last changing call and its last call full again; `EchoBatchDelay` (default 60; 0 no wait; -1 the same as EchoDelay throughout; never longer than EchoDelay). The batch gives `lastChange` and `echoed` in `batch_now` beside `i` and `n`. Batch description says it.
Also: a result's 1.8 s "lit for a moment" timer cleared whatever was selected when it fired; at the short pace that is a later call's selection, so it now clears only its own (`_clear_if`).

**Judgment calls / honest limits.**
- I kept the settle paint after a bench switch at the short pace: without it the toolbar does not exist yet and the button cannot light, which the brief wants kept. It is one `processEvents` and only when the bench changes.
- The saving is the pauses: 20 changing calls go from 20 × 350 ms to 4 × 350 + 16 × 60 ms, about 4.6 s less. The measured 0.35 to 2.5 s per call includes bench switches, a sketch opening in edit and `fit()`, which I did not remove because the brief says the window must keep showing them. A batch that alternates benches or sketches will still be slow; if the live numbers stay high, those are the next things to cut (my guess, not measured: `_mode`'s setEdit and `fit()`).
- A batch that stops early (budget, refusal) ends on a short-paced call.
- No setting in the panel for `EchoBatchDelay`; it is a preference only.

**Proven here.** `tests/test_echo_pace.py` (14): the rule, and the echo against a stand-in FreeCADGui with every wait recorded (calls 4 to 7 of 8: one 60 ms wait each, button still lit, selection still made, bench still switched; first three and last: paint + 350 ms).

**Needs the Mac.** Timing and what the window shows:
1. `batch { calls: [20 × part_primitive { kind: "box", size: [5,5,5], name: "E<i>" }], rollback: false, budget: 120 }` in the window, time it; expect roughly 4 to 5 s less than before, each box still selected as it appears, the Part button flashing each time.
2. Preference `EchoBatchDelay` = 0 and run it again (fastest); = -1 (as slow as before).
3. A mixed batch that changes bench after the fourth call (`pd_body_new`, `sketch_new`, `sketch_add`, `pd_pad`, `part_primitive`, `pd_fillet` …): the button of the first call after each bench switch must still light.
4. `asm_joint` as call 5+ of a batch: the two faces selected, no pause.

## Job 3: the next hint

**Built.**
- `agentlink/data/nexthint.json` (25 rules) with `nexthint.schema.json`, checked by `datafiles.check_folder` like the other data files. A rule: `when` (facts that must all hold; a list is any-of), `unless` (none may hold), `suggest` (up to 4 `{ tool, why }`), `weight`. Weights: failing recompute 100; selection 80 to 90; sketch in edit 70 to 85; page in front 75; assembly 45, or 72 in the Assembly workbench; body progress 30 to 66.
- `agentlink/nexthint.py`: `facts(doc, state, gui)` reads the state cheaply (object State flags, the active body's Group and Tip, the newest unused sketch's wires, the assembly's joint group, the selection, the view in front; nothing past 2000 objects), `rank()`, `available()`, `compose()`. Hint line: "…; likely next: pd_pad (a closed sketch no feature uses yet), pd_pocket (cut it out of the body), pd_revolution (…); workbench …; status bar: …". At most three; none while a dialog is in front.
- Filter: a tool that is not installed is dropped; a tool whose commands on the active workbench's toolbars *all* report inactive is dropped; a tool whose command is on another workbench's toolbars is kept, since it is never asked. `isActive()` is called in exactly one place (`tools.ask_active`), behind the shown-toolbar filter; a test pins that. Fewer commands are asked than before (the picks', not 60 candidates').
- `tool_groups { now: true }`: the same picks first, `fits` starting "likely next: …", and `next [{ tool, why }]` in the answer.
- Add-ons: `NEXT = { id: entry }` on a family module (same shape, same schema; a bad rule is left out and logged; a file rule is never replaced). Documented in docs/hooks.md. The core file names core tools only, so `part_review` is not in it: Workshop Make should declare it (e.g. when `{ body: "features" }`, weight about 49).
- The health check's news test now also counts the document's object count and the rules that fit, so "the body got its first pad" is news.

**Not verified / doubtful.**
- All of `facts()` against real FreeCAD objects: tested here only with stand-ins. Sources read: FreeCAD 1.1 source `src/Mod/TechDraw/Gui/MDIViewPage.cpp` (the page view's Python type is `MDIViewPagePy`), `src/Gui/View3DPy.cpp` (`getActiveObject`), `src/App/DocumentObject.pyi` (`State`). Tag 1.1.0, the Mac runs 1.1.3.
- "Closed sketch" is `all(w.isClosed() for w in sketch.Shape.Wires)`: construction geometry is not in the shape, fine; a sketch of points for holes reads as open.
- The inactive-command filter can drop a tool that would work: a GUI command's `isActive` follows the GUI's selection and active body, the tool takes names. I followed the brief; if a good suggestion goes missing live, this is where.
- Which body: the active one (`pdbody`), else the picked object's, else the last in the document.
- The rules' choices are mine (the brief's examples plus what follows from them). They are data: edit the file.

**Proven here.** `tests/test_nexthint.py` (19) and the changed cases in `tests/test_smart_calls.py`: each state the brief names gives the tools it names; failing first; selection over body state; add-on rules; the schema; every tool named exists in the tool index; every fact and value in the file is one the reader can give.

**Needs the Mac** (window, fresh document; read `next` in `session_state {}` after each):
1. empty document → `pd_body_new`.
2. `pd_body_new {}` → `sketch_new (the body has no sketch yet)`.
3. `sketch_new { body, plane: "XY" }` → sketch in edit, empty: `sketch_add`.
4. `sketch_add` a rectangle, unconstrained → `sketch_constrain (the open sketch still has DoF), sketch_state`.
5. constrain fully → `sketch_state, pd_pad, pd_pocket`.
6. leave the sketch (any non-sketch call) → `pd_pad (a closed sketch no feature uses yet), pd_revolution`.
7. `pd_pad { length: 10 }` → `pd_fillet, pd_chamfer, pd_hole`; the pad's own `health.next` should carry the line too.
8. select an edge of the pad in the window → `pd_fillet (round the picked edge)`; a face → `sketch_new, pd_draft, pd_thickness`.
9. `pd_fillet` → `body_check` first.
10. `feature_edit` the pad to a failing value with the refusal bypassed, or break a sketch → `recompute` first.
11. `td_page {}` with the page in front → `td_view, td_dim, td_list`.
12. an assembly with two parts and no joints, Assembly workbench → `asm_joint`.
13. `tool_groups { now: true }` in states 6 and 8: the same tools first, `next` present.
14. Watch for a crash through all of it: none expected (no command outside the shown toolbars is asked), but this is the path that crashed before.

## Job 4: small faults

- **`batch { to }` dropped the batch's note.** `_batch_to` overwrote `note` with the file's. Now `batchrec.to_reply` (plain Python): the batch's own note stays `note`, the file's is `toNote`; with no batch note, `note` is the file's as before. Proven here (`tests/test_hubfix_small.py`). Live: `batch { calls: [ … a heavy read as call 3 … ], to: "run.json" }` → reply has `note` "Stopped before calls.3 …", `toNote`, `next`, `heavy`.
- **`background: true` in a batch for a file writer.** What I found: `jobs.eligible` says `meshobj_export` *can* run as a job on its own (it changes nothing in the document; guides/mesh.md says so too), so the old words were not wrong about that, but they pointed a batch away from the simple answer. Now `jobs.background_refusal`: a writer in a batch is told to leave `background` out (it runs in order, the file there for the next call) and that on its own the file is whole only when `job_status` says done; a change is told it is never a job (no "call it on its own"); a plain read keeps the old words. I did **not** make writers ineligible as jobs: a slow export would then lose its answer at the client's 80 s. If the live fault was that `meshobj_export { background: true }` on its own fails or misbehaves, that is a different bug and I did not see it; tell me what it answered. Proven here (unit and through `protocol.Server`). Live: `batch { calls: [{ tool: "meshobj_export", arguments: { mesh, background: true } }] }` → refusal with "writes a file: leave background out".
- **`scad_tidy { action: "color_code" }`** is in `families/std_more.py`, not `families/openscad.py`. FreeCAD's own command (FreeCAD 1.1 source: `src/Mod/OpenSCAD/colorcodeshapes.py`) sets `ViewObject.ShapeColor` only, so it touches and recomputes nothing. Ours also keeps the colour in an App property, which touches the object. Now an object that was clean before is marked clean again (`purgeTouched`); one already waiting for a recompute keeps waiting. No recompute is run. Not run here; `tests/test_std_more.py` extended for the Mac. Live: recompute, `scad_tidy { action: "color_code" }`, then the reply's health must not list touched objects.

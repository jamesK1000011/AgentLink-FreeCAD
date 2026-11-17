# The hub's application tools and `addon` as data (tag: dataapp, 2026-11-16)

Checkout `wt3/d16`, base `a399f58`. Nothing committed or pushed, no network. **Nothing ran on FreeCAD**: every
proof here is plain Python on a stand-in.

Two patches:

- `dataapp.patch`: `git add -A -N; git diff a399f58`, FILES excluded. Applies on `a399f58`.
- `dataapp-on-main.patch`: the same work on main as it stood (`c669641`), made in a throw-away local clone. Main
  changed the `addon` handler after the base (`bb7ddfe`), so `dataapp.patch` conflicts there in
  `families/unattended.py` only; the resolution is this checkout's file whole (it has no handler). On the clone
  `git apply --check` passes, the dataapp, datacore and runner tests pass (30) and both index checks exit 0. The
  full suite was not run on the clone.

## Counts

- **Converted: 15** (14 of `families/app.py`'s 17, and `addon`). **Kept as code: 3**, all in `app.py`.
  **Thin entries: 1** (`snapshot_list`: one expression, as the handler was one line).
- `agentlink/data/tools.json`: 368 -> 383 entries, appended at the end, all `steps`; 293 added lines, 0 removed.
  No `family` key needed.
- Suite in the checkout (`timeout 285 python3 -m pytest -q tests`): **1006 passed, 347 skipped, 0 failed**
  (239 s), run before the new files were intent-added. After `git add -A -N`, `tests/test_files.py` fails on
  the stale FILES (1 failed, 1 passed), as expected; FILES left alone.
- `scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: both exit 0.
- `python3.11 -m py_compile` passes on every changed Python file.
- `app.py` 1150 -> 951 lines; `unattended.py` 384 -> 342.

## The runner change (made)

`runners.CODES` gained **two** codes, `not_allowed` and `refused`. One line of code; nothing else in the runner
changed. Both were already raised by the hub's handlers.

- `not_allowed` (asked for): `addon`'s missing confirm, `pref_set` and `pref_reset` on guarded settings.
- `refused` (not asked for, same change): `cmd_run` and `menu_run` use it for commands that would hold the
  window. Without it those two could not be converted with their refusal in the entry.

Where it is written and tested:

- `agentlink/runners.py`: the docstring's `refuse` line and a comment on `CODES`.
- `agentlink/data/tools.schema.json`: the `refuse` step's `code` enum.
- `docs/data-tools.md`: a new paragraph, "A refusal's code", with the two real examples.
- `agentlink/tooldata.py`: two docstring lines only. Its own `CODES` (what an add-on's handler may refuse with)
  is unchanged.
- `tests/test_runners.py::test_a_refusal_says_whose_call_it_is`: both codes raised as written by a step and by
  a wrapper's rule, unknown codes (`unsupported`, `busy`) still found at load, the schema's enum equal to
  `runners.CODES`.

`expr.py` is untouched.

## `addon`: converted from main's handler, not the base's

On the coordinator's word mid-task, `addon` was converted from the handler at `bb7ddfe`: description with the
new clause, the first update of a hand-copied add-on taking `url`, the catalog refusal's extra sentence for
update. The test reads the old `unattended.py` from `bb7ddfe` (`OLD_AT` in `tests/test_dataapp_data.py`) and
`app.py` from `a399f58`. I fetched main's objects into this checkout from the local repository so the test can
run; where git lacks either commit the old-against-new tests skip.

**A fault on main, kept as it is (not mine to fix here):** the new description says the url of a hand-copied
add-on's first update "is then recorded", and the handler's comment says the same, but the handler only writes
`addon-sources.json` when `action == "install"`. After such an update no source is recorded, so the next update
without `url` goes to the catalog again. The entry does exactly what the handler does (case "update one put
there by hand, its address given": no `keep._save` in either trace). The fix is one condition in the entry's
last `when`.

The installer and the rollback are named helpers: `set_aside` (the add-on moved out of Mod before an update),
`installer_run` ((ok, None) or (False, the error's words)), `put_back` (what the install left taken out, the
version before moved back), `smoke_here`. Each failure's rollback is the `first` of its `refuse` step. The cases
compare the files left under Mod and the keep folder after every call, so the rollback is compared, not only
its words.

## Kept as code, and why

| Tool | Reason |
|---|---|
| `app_restart` | One run of the machine's own state: the open documents saved by a plan (the person's never written over), the restart mark, another release smoke-tested and its settings carried, a shell started that waits for this process to be gone, Qt told to quit. `docs/data-tools.md` names the hub's own machinery as code. |
| `app_install` | Starts the background installer process and reads back its state file. One refusal has the code `unsupported`, which a `refuse` step does not take; I did not add a third code for one tool. |
| `pref_import` | One merge over files: settings backed up, a file inserted group by group through temporary files, guarded settings and this FreeCAD's own put back, macros copied. It could be a thin entry over four or five helpers; I did not do it. Judgement call, not "unusable as data". |

`view_render`, `gui_input`, `live_run`: untouched, as told.

## Per tool

| Tool | As data | Helpers it calls |
|---|---|---|
| `pref_get` | one setting as an early answer | `group`, `contents`, `subgroups` |
| `pref_set` | the loop over values, `appliesAtNextLaunch` | `group`, `guarded`, `changing`, `stored`, `set_value`, `changed` |
| `pref_reset` | | `group`, `guarded`, `changing`, `contents`, `stored`, `removed`, `changed` |
| `pref_pack` | list as an early answer | `packs`, `changing`, `apply_cfg`, `changed` |
| `cmd_list` | the loop stops reading commands once `limit` is reached, as the handler's `break` | `window`, `cmd_matches`, `cmd_row`, `refused` |
| `cmd_run` | every branch, see below | `window`, `refused`, `is_active`, `in_edit`, `front`, `selected`, `working` |
| `menu_list` | | `menubar`, `bare`, `walk`, `window` |
| `menu_run` | | `find_action`, `refused`, `window` |
| `workbench` | | `window`, `bench_ready` |
| `show` | | `window`, `doc`, `named_objects` |
| `selection` | found first, so a wrong name leaves the selection | `window`, `doc` |
| `window_snapshot` | | `window`, `dock_panels`, `grab`, `local`, `out_file`, `read_bytes` |
| `snapshot_latest` | | `shots`, `isfile`, `read_bytes` |
| `snapshot_list` | thin | `shots` |
| `addon` | list and search as early answers; remove; install / update with rollback | `manager`, `in_mod`, `catalog`, `well_named`, `OURS`, `join`, `isdir`, `uninstalled`, `record`, `kept_file`, `loaded`, `addon_at`, `set_aside`, `installer_run`, `put_back`, `smoke_here`, `saved` |

**`cmd_run` and `Sketcher_LeaveSketch`.** The special case is in the entry, in the handler's order: greyed out
and nothing in edit answers `ran: null, already: …`; greyed out with a sketch in edit does `resetEdit`,
recompute, `updateGui` and answers `closed` with the note; any other greyed command is refused. Eight cases
cover it (none open, a drawing tool on, what is open has no object, the edit unreadable, no document in front,
another document in front, active, cannot say), each identical to the handler in answer, trace and edit state.
Three are pinned to fixed text.

Module-level names other files import (`named_objects`, `guarded`, `restart_plan`, `_bundle_python`,
`unsaved_path`, `installed_names`, `mod_dir`) are unchanged. Everything above `def tools` in `app.py` is
unchanged apart from the new helper functions and one import.

### Helpers that still refuse in their own words

Unchanged code, compared in the cases: `window` (`_gui`: no window), `set_value` (`_set`: five refusals by
type, shared with `apply_cfg`), `find_action` (no such item; an item is not a menu), `manager` (`_am`: three
`unavailable`), `catalog` (the catalog could not be fetched).

## Behaviour differences

None found: **0 of 179 cases differ.** Not identical in form:

- **Listing order.** `app.py` returns `app_install`, `pref_import`, `app_restart`, then its data tools;
  `unattended.py` now returns data tools only. The index and summary are current; anything reading the raw
  order of `tools/list` sees a new order.
- `cmd_list`: with a query, a command that matched by name had `getInfo` read once; still once. No more reads
  than before after `limit` is reached.
- `pref_set` reads a group's contents once fewer per value in places (reads only; not traced).
- `addon`: `put_back` checks the folder is there before removing it in both failures; the handler's smoke
  failure removed it unconditionally with errors ignored. Same effect.

## Proof here

`tests/test_dataapp_data.py` with `_dataapp_before.py`, `_dataapp_cases.py`, `_dataapp_standin.py`. The
stand-in wraps `_datacore_standin.install()` in the child process only.

- **Identity**, 15 tools: name, description bytes, schema with key order, changes, reads, group, against a
  snapshot of the code (checked against git's source).
- **Old handler against new entry, 179 cases** (91 answer, 83 refuse, 5 crash alike), each in a fresh session:
  answer or refusal, every traced call in order, objects, what is shown, the settings stored, the selection,
  whether a sketch is in edit, and the files left in the session's folder. **0 differ.** 47 pinned to fixed
  text. Per tool: addon 40, cmd_run 27, pref_set 18, menu_run 14, selection 13, workbench 10, show 9,
  snapshot_latest 9, cmd_list 8, menu_list 8, pref_get 6, window_snapshot 6, pref_reset 5, pref_pack 4,
  snapshot_list 2.
- **Every `refuse` step is reached**: 36 in the 15 entries, `UNREACHED` is empty.
- **Every helper present** (`--helpers` answers `{}`). No handler or `Tool(...)` of a converted name is left.

One existing proof file changed: `tests/_datacore_cases.py` lost `addon` from its `KEPT` (two lines), since its
test asserts every kept tool is still code. No existing stand-in changed.

What the stand-in is not: FreeCAD, Qt, the Addon Manager or the network. The parameter tree is a dict; menus,
actions, docks and the grabbed picture are small classes; the Addon Manager's modules, `urlopen`, the smoke
test and `keep` are stubs that write down what they were asked; the installer only makes or does not make a
folder. `pref_pack` does read the repository's real "Studio Dark" pack through the real `apply_cfg`.

## Live models

Positions as the files have them: `coredoc-gui-model.json` steps from 0, `hubrest-model.json` calls from 1.
`coredoc-model.json` calls none of these tools.

| Tool | `coredoc-gui-model.json` | `hubrest-model.json` |
|---|---|---|
| `workbench` | 1, 14 | 4 |
| `cmd_list` | 2 | 5 |
| `cmd_run` | 3, 4, 6 | 6, 7 |
| `selection` | 3, 4, 6, 14 | 9, 10, 11 |
| `show` | 4 | 12, 13 |
| `menu_list` | 5 | 8 |
| `menu_run` | 5 | |
| `pref_set` | 9 | 14 |
| `pref_get` | 9 | 15 |
| `pref_reset` | 9 | 16 |
| `pref_pack` | 9 | |
| `window_snapshot` | 10 | 19 |
| `snapshot_list` | 10 | |
| `snapshot_latest` | 10 | |
| `addon` | 13 | 39 |

**No tool is without a live call**, but **no model calls `cmd_run { name: "Sketcher_LeaveSketch" }`**: that case
has no live proof in these models. Thin live (one call in one model): `menu_run`, `pref_pack`, `snapshot_list`,
`snapshot_latest`. `addon` live is read-only (install, update and remove are listed "by hand only").

## Unproven, and risks

1. **Nothing ran on FreeCAD.** The two models above on FreeCAD 1.1.3 are the proof still owed, the window ones
   most of all: `cmd_run` (the greyed-out reading and the leave-sketch case by hand), `menu_run`, `selection`,
   `window_snapshot`.
2. `addon` install, update and remove have never run through the entry against the real Addon Manager; the
   stand-in checks order, words and the folders left, not the manager's behaviour.
3. `dock_panels` and `grab` import PySide inside the helper, as the handler did; here PySide is a stub.
4. The `addon` fault on main described above ships as it is.

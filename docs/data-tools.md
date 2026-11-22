# Tools as data
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

Agent Link's own tools are kept as entries in `agentlink/data/tools.json`, run by generic runners
(`agentlink/runners.py`), where they can be: the entry is the tool's definition — its description and
schema, its checks with their refusals word for word, the order of its steps, its answer's fields. The
format is in `agentlink/tooldata.py`'s docstring and `agentlink/data/tools.schema.json`; this note says
what each construct is for, with one real example of each, and where code is still right.

The whole BIM family (40 handlers in `families/bim.py`, `bim_more.py`, `bim_gaps.py`) is data. Those
three files now hold only what the entries call by name. So are the Mesh family (`families/meshobj.py`,
21 tools) and the Points family (`families/points.py`, 8 tools): the numpy over points and triangles and
the FreeCAD Mesh calls are named helpers (`plane_sides`, `own_boolean`, `edge_loops`, `flatten_apart`;
`in_box`, `fitted`, `curve_through`, `grid_mesh`), the checks, the order and the answer are the entries.
TechDraw (`families/techdraw.py`) is data for all 32 of its tools (`tests/test_datatd_data.py` is the proof of 27; `td_list`, `td_export`,
`td_cosmetic`, `td_view_more` and `td_lines` came after, proven by `tests/test_datatd2_data.py`): the cold views' warm-up (`warm`), the page drawn
here (`page_sheet`, `drawn`) and a thread's or a centreline's geometry (`thread_arc`, `side_outline`, `root_lines`, `mid_line`) are named helpers.
CAM's twelve tools in `families/cam.py` are data (`tests/test_datacam_data.py`): the path's reading (`path_stats`), the height-map
simulation (`sim_run`, `sim_picture`), the two ways of posting (`by_job`, `post_script`) and what differs between FreeCAD's releases
(`make_op`, `bit_factory`, `toolbit`, `dress`) are named helpers. `families/cam_more.py`'s six (cam_path, cam_property_bag, cam_template_export,
draft_fix, asm_rigid_group, asm_new_part) and `families/openscad.py`'s five (scad_status, scad_import, scad_code, scad_export, scad_op) are data too
(`tests/test_datatd2_data.py`, each file on its own stand-in): which module of FreeCAD a proxy class is in (`from_module`, `proxied`), FreeCAD's CSG
reader and writer run with the window's parts off (`read_in`, `export_csg`, `run_code`) and the hull made here (`hull_here`) are named helpers.

Materials, FEM and strength are data too (`tests/test_datafem_data.py`): the 4 of `families/material.py`, the 3 of
`families/fem_more.py` and the 16 `fea_*` of `families/strength.py`. There the solver stays code, as named helpers:
the Gmsh and CalculiX runs (`_meshed`, `_run`, `solve_run`, `modes_run`, `buckle_run`, `heat_solve`, `shell_solve`),
FreeCAD's own FEM route (`_fem_build_and_run`, `gmsh_run`), the result reading (`peaks`, `part_rows`, `Probe`) and
the FEM objects one at a time (`fixed_on`, `force_on`, `native_mesh`). The entry has the study's checks, each
refusal, the order, the answer's fields and the words about what a result is worth: FEA is a feasibility check,
never a sign-off.

The Part workbench's modelling tools are data as well: the 11 of `families/model.py`, the 10 of
`families/model_more.py` (part_wire, part_split, part_compound, part_refine, part_attach, part_face, part_ruled,
part_project, part_slices, part_from_mesh) and the 6 of `families/part_more.py` (part_section, part_offset2d,
part_extract, part_defeature, part_fix, part_datum). The three files share the group `model`; the entries of the
last two say `"family": "model_more"` or `"family": "part_more"`, and each file asks for its own
(`tests/test_datapart_data.py` and `tests/test_datapart2_data.py` are their proof, on a stand-in).

So are Part Design and Sketcher: the 19 feature tools (`families/feature.py`), the 8 sketch tools
(`families/sketch.py`) and `std_more.py`'s pd_move_feature, pd_reorder, pd_tip and pd_shaft. What is left in
those files is the solver's reading, the geometry builders (one shape each), the constraints by name and
the small FreeCAD-API functions the entries call.

So are the parameter tools and the rest of Part Design and Sketcher: the 6 of `families/param.py` (the Params sheet and the variable sets),
the 7 of `families/feature_more.py` (`"family": "feature_more"`, group `feature`) and the 12 of `families/sketch_more.py` (`"family":
"sketch_more"`, group `sketch`). The guard that refuses a change for what it breaks is written in each entry with `broken` (pd_common's
`newly_broken`: not what was failing before the call). What is left as helpers: the sheet's and the sets' reading (`rows`, `value_of`, `users`,
`var_type`, `why`), the gear's and the sprocket's profile with the window's makers held off (`gear_profile`), a sketch kept and put back
(`kept`, `restore`), the matrices and the mirrored arc (`turn`, `scaling`, `mirrored`), the Sketcher's detectors (`detect`) and one sketch
brought into another (`bring_in`). `tests/test_datask2_data.py` is their proof, on a stand-in.

The Assembly family is data too: the 8 tools of `families/assembly.py` and the 8 of `families/assembly_more.py`
(`"family": "assembly_more"`; both files are the group `assembly`). What is left there is the Assembly workbench's own
reading (`joint_axis`, `joint_refs`, `joint_value`, `moving_group`, `pose_move`), the algorithms (`pair_fit`: the hole and
shaft on an axis held to ISO 286; `carried`, `driven_parts`: what a joint carries and what its couplings drive; `stacked`,
`spread`: an explosion's moves; `fill_native`: the BOM's columns) and the two loops that must put the parts back whatever
happens (`sweep_run`, `play`). `tests/test_dataasm_data.py` is their proof, on a stand-in with no solver.
The measuring tools (`families/measure.py`: shape_query, measure, measure_keep, measure_mass, section, clearance), the
inspection tools (`families/inspection.py`, 6), the notes and steps tools (`families/notes.py`, 7) and the robot tools
(`families/robot.py`, 6) are data too, and the six ifc_ tools (`families/ifc.py`, group `bim`, `"family": "ifc"`;
`tests/test_datamisc_data.py` is the proof of all five files, on a stand-in). What is left in those
files is the shared filter (`filter_shape`) and the readings (`describe`, `inertia`, `reading`, `by_face`), the notes'
following of renumbered faces, the drawing of a step (`step_picture`, `contact_sheet`) and a robot's sweep along a
trajectory (`sweep`) and IFC's selection and comparison (`select`, `differences`); the finders that several tools share (`ins_of`, `find_note`, `body_pd`, `robot`, `trajectory`) and
the readers of an argument (`tol_of`, `placement`) still refuse in their own words.

Spreadsheets and the document-level tools are data as well (`tests/test_datasheet_data.py`): the 11 of `families/sheet.py` and the 16 that were
still code in `families/std_more.py` (links, duplicates, merge, document information, revert, save all, text documents, appearance, the OpenSCAD
tree tools, freeze, units, point-pair alignment, a robot's tool shape, merged cells), so that file holds no handler any more. What is left in
`sheet.py` is the reading of a sheet (`filled`, `cell_reading`, `value_of`, `tables`, `table_reading`, `users_of`), the guard every changing
sheet tool ends with (`check`: recompute, and when the change broke something that was sound, undo and refuse naming the failing cells), a
formula's Params names (`qualified`) and a design table's binding as FreeCAD's own dialog writes it (`bind_row`); in `std_more.py` the rigid
fit (`rigid_fit`), GraphViz's text and run (`dot_text`, `dot_draw`), the window's freeze command (`toggle_freeze`) and a colour kept on the
object (`keep_colour`, `keep_untouched`). A `cells` function that says what is wrong with a value answers `(value, None)` or `(None, why)`
(`content`, `grid`, `hex_rgba`, `tidy_range`), and the entry has the refusal.

The hub's own core tools are data where the steps say them cleanly (`tests/test_datacore_data.py`): the 13 of `families/doc.py` (documents, objects,
`import_file`, `export`), `view_maps` and `view_snapshot`, `addon_test` and `gui_unstick`, and `dialog_answer`, `crash_collect`, `doc_switch` and
`queue_go`. Named helpers there are the readers and writers of files (`mesh_read`, `mesh_solid`, `solid_written`, `scene_written`, `merged_meshes`,
`flat_write`), what goes with a deleted object (`along`, `shown_again`), which open document a name means (`doc_hits`, `doc_by`, `back_to`), and
the window's own calls (`active_view`, `shots`: each view saved and the person's camera put back). Kept as code, in the same files: `view_render`
(the picture itself) and `gui_input` and `live_run` (one algorithm each over Qt's event loop).

So are the application tools (`tests/test_dataapp_data.py`): 14 of the 17 of `families/app.py` (`pref_get`, `pref_set`, `pref_reset`, `pref_pack`, `cmd_list`,
`cmd_run`, `menu_list`, `menu_run`, `workbench`, `show`, `selection`, `window_snapshot`, `snapshot_latest`, `snapshot_list`) and `addon` of
`families/unattended.py`. `cmd_run`'s entry has the whole of its rule for a greyed-out command, `Sketcher_LeaveSketch` included (no sketch open: answered,
not refused; a drawing tool still on: ended and the sketch closed). Named helpers there are a command's reading (`is_active`, `in_edit`, `selected`,
`cmd_row`, `cmd_matches`), the menu bar walked as Qt has it (`walk`, `find_action`, `bare`), a setting written by its type (`set_value`) or taken out
(`removed`), and for `addon` the Addon Manager's modules (`manager`, `catalog`), its installer run (`installer_run`) and the rollback (`set_aside`,
`put_back`: the add-on moved aside before an update and put back when the install or the smoke test fails, each as the `first` of its refusal). Kept as
code in `app.py`: `app_restart` (one run of the machine's own state, ending with FreeCAD told to quit), `app_install` (a background installer process and
its state file) and `pref_import` (one merge over settings files).

## Two kinds of entry

**A wrapper** (`runner`: `make`, `apply`, `command`, `read`) is one FreeCAD command: `target`, `args`,
`rules`, `answer`. `bim_level`, `bim_wall` and `bim_list` are wrappers. Use it when the tool is
"resolve the arguments, check them, run one thing, answer".

**Steps** (`runner`: `steps`) is a list of steps run in order, each able to use what the ones before it
made. Use it as soon as a tool has two commands, a branch, a loop, arithmetic or something made after
the answer. Everything below is about steps entries, though expressions work in wrappers too.

## Expressions

A value that starts with `=` is an expression, written as Python writes it:

    {"let": {"steps": "=int(a.get('steps', max(3, round(height / 175))))"}}          bim_stairs
    "when": "=sill + height > top + 1e-6 and top > 0"                                 bim_opening
    "=[e.Length for e in line.Shape.Edges]"                                           bim_curtain_wall

`a` is the call's arguments and `a.name` the argument `name` (None when left out; `a.get('from')` for a
name Python keeps, or for a default). It has arithmetic, comparisons (chained too), `and` / `or` / `not`,
`x if c else y`, lists, dicts, sets and comprehensions, a value's attributes and methods, the functions
`agentlink/expr.py` lists (`len sum round min max abs int float str sorted reversed any all zip enumerate
range first tally has get is_list is_str ceil maker` …) and the family's helpers by name.

It is not `eval`. The text is parsed with Python's parser and walked by an evaluator that knows only
those node kinds; assignment, import, names or attributes starting with `_`, f-strings and `*args` are
refused when the entry is loaded (`tooldata.check`), so a bad entry fails the plain-Python tests.

**Messages** are plain strings. One that needs values is `{"fmt": …}`, with `{fields}` as an f-string
has them (`{{` and `}}` for braces), so the handler's words carry over unchanged:

    {"refuse": {"fmt": "sill + height is {sill + height:g} mm, above the wall's {float(wall.Height):g} mm: a lower sill or height."},
     "when": "=sill + height > top + 1e-6 and top > 0"}                               bim_opening

A field may not hold `:` or `!` outside brackets: work such a value out in a `let` first
(`named_bare` in `bim_export`).

## The steps

| Step | For | Example |
|---|---|---|
| `let` | a value, by name, for later steps (`"p, q"` unpacks) | `{"let": {"run, left": "=wall_run(edges, at)"}}` (bim_opening) |
| `refuse` | a check, in its place in the order, with its words; `code`; `first`: what to undo before it | `{"refuse": "steps: 2 or more (FreeCAD counts risers: steps - 1 treads share the length).", "when": "=steps < 2"}` (bim_stairs) |
| `make` | a FreeCAD maker by dotted name; `headless`: through the family's `headless_call` | `{"make": "Arch.makeStructure", "call": ["=base"], "kw": {"height": "=t"}}` (bim_structure) |
| `add` | a new document object of a type | `{"add": "Part::Feature", "name": "Opening", "as": "hole"}` (bim_opening) |
| `set` | properties, in order | `{"set": {"ax.Distances": "=[0.0] + sp", "ax.Length": "=length"}}` (bim_grid) |
| `do` | something done for its effect | `{"do": "=named(o, a.name or 'Stairs')"}` |
| `put`, `push` | a field into a dict (the answer), one more on a list | `{"put": {"Density": {"fmt": "{pos(a, 'density', None):g} kg/m^3"}}, "into": "data", "when": "=a.density is not None"}` (bim_material) |
| `when` + `then` / `else` | a branch | points or a base sketch in bim_roof, bim_space, bim_structure |
| `choose` | a branch by a value | `{"choose": "=kind", "of": {"column": […], "beam": […]}, "else": […]}` (bim_structure); the five ops of bim_edit |
| `each` | a loop | the two directions of bim_grid; each object in bim_ifc |
| `try` | a fallback, or an error turned into a refusal; `"on": "failure"`: any error but a refusal made inside; `"reraise": true`: undo in `except`, then the error goes on | FreeCAD's rebar, else plain bars (bim_rebar, `"on": "refusal"`); a face that will not close (bim_panel); the constraints a refused sketch_constrain takes back (`reraise`) |
| `answer` | the answer, ending the run | each op of bim_edit; `list` in bim_trash |

`"when"` on any step runs it only then, so most branches are one line.

**A refusal's code** says what kind it is: `invalid_input` (left out: the call is wrong), `not_found`, `invalid_state`, `unavailable`, `failed`, and the two
that say whose call it is — `not_allowed`, the person's own to say or set (a confirm they must type, a setting they guard), and `refused`, what the tool
never does from here, said with the tool that does:

    {"refuse": {"fmt": "confirm: \"{want}\", word for word, typed by the person — {why}. Nothing was changed."}, "code": "not_allowed",
     "when": "=(a.confirm or '').strip() != want"}                                                         addon
    {"refuse": {"fmt": "{name} is not run from here: {refused(name)}."}, "code": "refused", "when": "=refused(name)"}     cmd_run

Any other code is found when the entry is loaded (`runners.CODES`, and the schema's list).

**Refusals that clean up.** A check that fails after something was made says what to remove first:

    {"refuse": "angle: every edge is a gable (90), so there is no pane left to build: give the sloping edges an angle below 90.",
     "first": [{"do": "=drop(base if made_base else None)"}], "when": "=all(x == 90 for x in angles)"}     bim_roof

**The answer.** `via` names the family helper that finishes (recompute, snapshot, the step number);
`fields` are the tool's own fields in their order. `"late": true` has the helper read the fields itself,
after its recompute (bim_grid, bim_material, bim_import). `then` is the *after the answer* part — what
the handler did to `out` once `finish` had answered, because it must be read or made after it:

    "answer": {"via": "finish", "with": ["=o", "=tool", "$fields"], "fields": {"levels": "=[x.Label for x in levels]"},
               "then": [{"when": "=a.get('site', True)", "then": [
                   {"make": "Arch.makeSite", "call": ["=[o]"], "as": "site"},
                   {"do": ["=named(site, a.siteName or 'Site')", "=doc().recompute()"]},
                   {"put": {"site": "=site.Label"}}]}]}                                                    bim_building

**Reads.** `reads` (an existing field) says which calls of a changing tool only read:
`"reads": {"action": ["list"]}` on bim_trash, whose `list` branch answers without the finishing helper;
`{"sheet": [null, false, ""]}` on bim_schedule.

## Named helpers

Each family module declares a dict of functions and hands it to `runners.tools(group, session,
helpers)`. An entry calls them by name. They are of three sorts, and the dict is laid out so:

- the family's finishing code: `finish`, `done`, `named`, `find`, `unique`, `pos`, `vec`, `baseline`;
- FreeCAD's own, given short names: `V`, `placement`, `rotation`, `face`, `box`, `polygon`, `compound`;
- the small functions that are real geometry or FreeCAD-API logic. Each has a docstring that says what
  it knows, and is one named step in the entry:

      {"let": {"pl": "=placement(p0 + d * left + n * wall_side(wall, W) + V(0, 0, sill), frame(d, n))"}}   bim_opening
      {"let": {"ridge": "=roof_ridge(o, verts[0].z)"}}                                                     bim_roof

  `wall_side` is where a wall's middle sits off its line (FreeCAD's Left is the right-hand side);
  `roof_ridge` reads the ridge from the built roof's underside. Others: `wall_run`, `window_shape`,
  `prism`, `roof_runs`, `plain_bars`, `tile_grid`, `lay_tiles`, `counted`, `takeoff`, `unclone`,
  `depth_along`, `nest_run`, `emptied`, `ifc_bodies`.

A helper should be small and say one thing. It does not refuse in the tool's words (the entry does
that, from what the helper answers: `wall_run` answers `(None, …)` past the end and the entry has the
message), and it does not decide the order of steps. `tests/test_bim_data.py` checks every name an
entry calls against its family's dict.

Two family modules that share a group (`bim.py` and `bim_more.py` are both group `bim`) each ask for
their own entries: an entry says `"family": "bim_more"`.

## Where code is still right

The entry should still read as the tool. Keep code — as a named helper, or the whole tool — for:

- **algorithms over geometry or the model**: laying tiles on a face with a boolean each (`lay_tiles`),
  the fallback IFC reader (`ifc_bodies`), the take-off's row per object (`takeoff`, `quantities`),
  deleting a trash's unshared children (`emptied`). The loop and its arithmetic are the point and JSON
  adds nothing. In the BIM family these are helpers of data tools: the checks, order and answer are
  still in the entry. bim_quantities, bim_schedule and bim_library are the thinnest entries (two or
  three helper calls and the answer's shape).
- **state that must be put back**: the nester's module-wide `ROTATIONS` set for one run in a
  `try … finally` (`nest_run`). The steps have no `finally` on purpose.
- **interactive and GUI tools**: anything that drives the window step by step, waits for a dialog, or
  answers with pictures (`view_render`, `dialog_answer`, the tutor); the session, undo and job tools.
- **heavy solvers and long jobs**: FEA, CAM path generation, slicing, mesh repair — a call into a
  solver with progress, cancel and a deadline.
- **the hub's own machinery**: `batch`, `tool_groups`, history, collab.

A tool is not kept as code for having arithmetic, two makers chosen by input, a second object made
after the first, or a refusal that cleans up: those are `=`, `choose`, `answer.then` and `refuse.first`.

## What a tool needs: read from the tool, never described twice

An entry's leading steps are its checks: the `refuse` steps, and the `let` steps they depend on, that come before its
first step that changes the document. `agentlink/needs.py` evaluates **those same steps** against the document as it is,
through the runners' own evaluator, without running the tool. Nothing else says what a tool needs: there is no table of
refusal words or of states (one was tried and ruled out: it can fit the cases it was made from and drift from what the
entry does).

    tool_groups { needs: "fea_hold" }
    → { "tool": "fea_hold", "applies": false,
        "wouldRefuse": [{ "code": "invalid_state", "words": "No strength study: fea_setup { body } first." }], "notChecked": [] }

    tool_groups { needs: "pd_pad", arguments: { "sketch": "Top", "type": "through_all" } }     the checks of that call too

| `applies` | Means |
|---|---|
| `false` | one of the leading checks refuses now; `wouldRefuse` has its code and its words, as the call gives them (the first 300 characters) |
| `true` | every leading check was read, there was at least one, and all pass. `notChecked` then says how many of the tool's checks come after its first change: only the call tells those |
| `null` | not checked, never a guess: a leading step needs the call's arguments, calls a helper that is not a known reader, or raised; or the tool has no leading check to read; or it is not a steps entry |

It is advice. It hides no tool, blocks no call and does not change `tools/list`; the tool's own refusal is the authority.

**Never guess, never change.** A step is evaluated only when every helper it calls is a *pure reader*, every method it
calls is a known reading and every function is one of the expressions' own (`maker` imports nothing in a reading).
`agentlink/data/readers.json` holds the lists; `scripts/tool_needs.py` derives them from the helpers' code (`--why name`
says why a helper is or is not a reader; `--check` fails when the file is stale) and `tests/test_needs.py` pins them, so a
helper joins a list only by someone reading why. A helper that is not listed is never called: the reading hands the
evaluator the readers and puts a stop in every other helper's place.

- *readers* (878): the code, and all it calls in this package, only reads names, attributes and items, builds new values,
  and calls listed functions and methods.
- *changers* (137): helpers that are not readers because their code writes — it sets a FreeCAD property or calls one of
  FreeCAD's own writing methods (`newObject`, `recompute`, `solve`, `addGeometry`, `SetString` …). A step that calls one is
  where the leading part ends, as `make`, `add` and `set` are, and a `do` that is not a reading, a refusal with `first`,
  and an answer.
- everything else is *unknown*: the reading stops there as not checked.
- methods are taken by name. Python's own (`lower`, `get`, `items` …) are taken on a Python value only: the reading checks
  the receiver before each call (`expr.GUARD`). A sketch's `split` and `join` change the sketch — the only two names in
  FreeCAD 1.1's `*PyImp.cpp` files that write and are also a string's — so they are a string's only by their arguments
  (`split` with at most one, or a text first; `join` with exactly one).

**Arguments.** Before a call they are unknown, so without `arguments` a step that reads `a`, or a value made from it, is
not evaluated and the tool is not checked for that part. Most tools begin by finding what an argument names
(`body(a.body)`, `sketch_of(a.sketch)`, `find(a.sheet)`), so most cannot be told before a call. With `arguments` those
steps are evaluated too, after the tool's own schema check.

How the 370 steps entries stand, from `tools.json` and `readers.json` alone (`needs.census()`; 13 more entries are
wrappers, not checked):

| | Entries | |
|---|---|---|
| whole without arguments | 60 | no leading step reads the arguments; 51 of them have no leading refusal at all (their checks are in their helpers, or after their first change): such a tool reads as not checked unless a reader helper runs before its first change |
| need arguments | 194 | read to the end of their leading part once the arguments are given |
| blocked | 116 | a leading step calls a helper that is neither a reader nor a changer; read as far as that step |

Of the 777 leading refusals written in the entries, 36 read no argument: a strength study that is not set up (11 tools),
a workbench or a maker this FreeCAD does not have, results not solved yet, no variable set. Per family:

| Family | Tools | Readers | Changers | Leading refusals | of them without arguments | Whole without arguments | Need arguments | Blocked |
|---|---|---|---|---|---|---|---|---|
| app | 14 | 17 | 1 | 16 | 0 | 3 | 5 | 6 |
| assembly | 8 | 18 | 6 | 1 | 0 | 0 | 7 | 1 |
| assembly_more | 8 | 30 | 9 | 6 | 0 | 1 | 6 | 1 |
| bim | 22 | 32 | 10 | 43 | 5 | 0 | 11 | 5 |
| bim_gaps | 16 | 22 | 7 | 17 | 0 | 1 | 7 | 4 |
| bim_more | 9 | 26 | 5 | 22 | 3 | 2 | 6 | 1 |
| cam | 12 | 27 | 9 | 0 | 0 | 12 | 0 | 0 |
| cam_more | 6 | 21 | 2 | 18 | 4 | 0 | 4 | 2 |
| dev | 2 | 4 | 0 | 1 | 0 | 1 | 1 | 0 |
| doc | 13 | 46 | 8 | 24 | 0 | 4 | 4 | 5 |
| draft | 22 | 27 | 5 | 21 | 0 | 12 | 1 | 8 |
| feature | 19 | 32 | 5 | 50 | 0 | 0 | 13 | 6 |
| feature_more | 7 | 24 | 4 | 22 | 0 | 0 | 7 | 0 |
| fem_more | 3 | 17 | 1 | 9 | 2 | 1 | 2 | 0 |
| ifc | 6 | 6 | 0 | 13 | 0 | 0 | 0 | 6 |
| inspection | 6 | 19 | 2 | 12 | 0 | 1 | 3 | 2 |
| material | 4 | 9 | 2 | 12 | 0 | 0 | 1 | 3 |
| measure | 6 | 19 | 0 | 10 | 0 | 0 | 3 | 3 |
| mesh | 21 | 37 | 5 | 70 | 1 | 1 | 11 | 8 |
| model | 11 | 30 | 2 | 47 | 1 | 0 | 2 | 9 |
| model_more | 10 | 35 | 3 | 51 | 0 | 1 | 7 | 2 |
| notes | 7 | 10 | 1 | 7 | 0 | 1 | 3 | 3 |
| openscad | 5 | 17 | 5 | 10 | 0 | 1 | 2 | 2 |
| param | 6 | 17 | 3 | 17 | 2 | 1 | 4 | 1 |
| part_more | 6 | 24 | 1 | 18 | 0 | 0 | 4 | 2 |
| points | 8 | 38 | 1 | 46 | 0 | 0 | 1 | 7 |
| robot | 6 | 21 | 2 | 14 | 0 | 0 | 5 | 1 |
| sheet | 11 | 31 | 3 | 23 | 0 | 0 | 3 | 8 |
| sketch | 8 | 32 | 4 | 15 | 0 | 0 | 8 | 0 |
| sketch_more | 12 | 16 | 4 | 34 | 3 | 0 | 10 | 2 |
| std_more | 28 | 47 | 4 | 56 | 2 | 5 | 19 | 3 |
| strength | 16 | 31 | 11 | 25 | 11 | 9 | 3 | 4 |
| surface | 6 | 11 | 1 | 15 | 0 | 0 | 6 | 0 |
| techdraw | 32 | 69 | 10 | 23 | 1 | 2 | 24 | 6 |
| unattended | 5 | 11 | 1 | 1 | 0 | 0 | 1 | 4 |
| view | 2 | 8 | 0 | 6 | 1 | 1 | 0 | 1 |
| **all** | **383** | **884** | **136** | **777** | **36** | **60** | **194** | **116** |

**The live filter** (`agentlink/appliesnow.py`). After each changing call the reading is taken for a small set of tools,
within a time budget, and one short line goes into the answer's health beside `next` — group names and counts, never a
tool's text:

    "appliesNow": { "groups": { "strength": 8 }, "not": 4, "notChecked": 7, "ms": 3 }

`groups`: the tools that apply, by group; `not`: those a leading check refuses now; `notChecked`; `partial`: the tools the
budget ran out before. It is said when it is not what was last said (as `next` is); a batch's answer carries it once, at
the top, and its calls carry none. `tool_groups { now: true }` gives the same reading in full (`appliesNow`: names by
class, 20 a class, 6 refusals with their first words, `more` counting the rest); `tool_groups { find }` moves the hits
that would be refused now after the others it shows and marks them `applies: false` — the order only, nothing dropped,
and a hit that applies does not overtake one that could not be told.

- *Which tools:* those the tool index puts in the active workbench; then in the workbenches the index links to it (one
  whose FreeCAD commands the active workbench's tools also do the work of, or the other way round: Sketcher and Part
  Design); then in the workbenches of the document's own objects. At most 150, in that order; with no window, the
  document's workbenches alone. Tools the index gives no workbench (document, view, hub) are not in the pushed set.
- *Budget:* 150 ms (`AppliesNowBudget`, Mod/AgentLink); a reading that took over 40 ms is not taken again in the pushed
  filter, since one helper cannot be stopped half-way. Timed as `appliesNow` (inside a call's `ms`) and `appliesMeter`
  in `agentlink/around.py`.
- *Off:* preference `AppliesNow` = false (Mod/AgentLink), or `AGENTLINK_APPLIES=off`. The readings on request stay.

**The meter** (the overfit measure). Every call records what the filter's last reading said of the tool (applies, not,
notChecked, notEvaluated) and what happened: answered; refused by a leading check, by a later one, or otherwise. A
refusal's place is told by reading the tool again with the call's arguments: the same step refusing is a leading check's
refusal. The counts are kept per session, written to `applies_meter.json` in the session's folder (the newest 20
sessions; written whole and put in place in one step) and `usage_report` carries them as `appliesNow`:
`notThenAnswered` (calls marked not that then answered — a wrong reading: must stay near zero, with the tools),
`appliesThenLeadingRefusal`, `coverage` (the share of calls whose tool the filter had told either way) and `stale`
(calls after a change the filter had not read yet: inside a batch).

**What it costs**, at 3.5 characters a token (`tests/test_needs.py` pins upper bounds, so a later change cannot bloat
these without saying so):

| | Tokens | Bound |
|---|---|---|
| every definition (383 data tools; 21 written in code, from their source) | 78,323 + 8,457 | 90,000 |
| the lean listing a session loads at its start (core and view, 20 tools) | 7,139 (6,985 before `needs`, `arguments` and the meter's clause) | 7,400 |
| one tool fetched (`tool_groups { tool }`): the median data tool; the largest | 177; 824 | 900 |
| the pushed `appliesNow` line: empty document; a sketch in edit; a body with a pad (stand-in) | none; 17; 17 | 45 |
| the `appliesNow` block of a `now` reply, the same three states | 84; 207; 200 (303 before a strength study) | 800 |
| one `needs` reply | 42 for `fea_hold` | 260 |

The three stand-in states say `notChecked: 32` and nothing else: every Part Design and Sketcher tool waits for its
arguments. The whole `now` reply (its ten tool rows too) is measured only where FreeCAD is importable (bound 1,500).

## Proof

- `tests/test_runners.py`: the evaluator (what it reads and what it refuses), messages, and each step
  kind, in plain Python.
- `tests/test_bim_data.py`: each converted tool built from its entry is the tool the code made (name,
  description bytes, schema with key order, changes, reads, group); and 431 cases run the old handler
  (from git) and the new entry on a stand-in FreeCAD (`tests/_bim_standin.py`), comparing the answer or
  refusal, every maker call, object added or removed and property set in order, and the objects left.
  Every `refuse` in a converted entry is reached by at least one case.
- `tests/test_datapd_data.py`: the same for the Part Design and Sketcher tools, 581 cases on their own
  stand-in (`tests/_datapd_standin.py`: a body's volume is a sum of what each feature adds, a sketch's
  solver counts), every `refuse` reached.
- The stand-in is not FreeCAD: it proves order and words, not Arch's behaviour. The live model
  (`private records: models/bimcam-bim-model.json`) on FreeCAD is the proof of that.
- `tests/test_datamesh_data.py` is the same proof for Mesh and Points (`tests/_datamesh_standin.py`,
  `_datamesh_cases.py`, `_datamesh_before.py`; numpy is real there, the mesh and the cloud are stand-ins).

- `tests/test_needs.py`: the readers' lists are the ones the code gives and are pinned; each step kind read dry; and every
  case of five stand-in suites (1,797 cases: Part Design and Sketcher, Mesh and Points, TechDraw, CAM, BIM) read with its
  arguments and then run — a reading of `false` (556) is the call's refusal, code and words; a reading of `true` (585) is
  never refused before the tool's first change; 656 could not be told; no reading changes the document. A stand-in
  proves the walk and the words, not that a helper is pure on FreeCAD: that rests on the helpers' code as read.

## Adding or converting a tool

1. Write the entry: description, schema, `steps`, `answer`. Refusal texts go in `refuse` steps.
2. Anything that is geometry or FreeCAD-API logic: a small function in the family module, named in its
   helpers dict, with a docstring.
3. `python3 scripts/tool_needs.py` when a helper was added or changed (it rewrites `readers.json`; put the new pin in
   `tests/test_needs.py` after reading `--why`), `python3 scripts/tool_index.py --check`, and cases for the tool in `tests/_bim_cases.py` (or the
   family's own test) — the normal path and each refusal.

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
TechDraw (`families/techdraw.py`) is data for 27 of its 32 tools; `td_list`, `td_export`, `td_cosmetic`,
`td_view_more` and `td_lines` are still handlers there, beside the entries (`tests/test_datatd_data.py` is its proof).
CAM's twelve tools in `families/cam.py` are data (`tests/test_datacam_data.py`): the path's reading (`path_stats`), the height-map
simulation (`sim_run`, `sim_picture`), the two ways of posting (`by_job`, `post_script`) and what differs between FreeCAD's releases
(`make_op`, `bit_factory`, `toolbit`, `dress`) are named helpers; `cam_more.py` is still handlers.

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
  (`docs/hardening/models/bimcam-bim-model.json`) on FreeCAD is the proof of that.
- `tests/test_datamesh_data.py` is the same proof for Mesh and Points (`tests/_datamesh_standin.py`,
  `_datamesh_cases.py`, `_datamesh_before.py`; numpy is real there, the mesh and the cloud are stand-ins).

## Adding or converting a tool

1. Write the entry: description, schema, `steps`, `answer`. Refusal texts go in `refuse` steps.
2. Anything that is geometry or FreeCAD-API logic: a small function in the family module, named in its
   helpers dict, with a docstring.
3. `python3 scripts/tool_index.py --check`, and cases for the tool in `tests/_bim_cases.py` (or the
   family's own test) — the normal path and each refusal.

# Part Design and Sketcher as data (tag datapd, 2026-11-16)

Checkout `<work>/`, base `99489bb` (main when the work started). Patch:
`<work>/datapd.patch` (`git add -A -N`, `git diff`, FILES left out; it applies to a clean
`99489bb`, checked in a scratch worktree). Nothing committed or pushed. **Nothing ran on FreeCAD**: the
proof is plain Python on a stand-in. The run was stopped once by a usage limit before any file was
written; the checkout was clean at the restart and the work was done in one pass after it.

All three files were finished: `feature.py`, then `std_more.py`'s pd_ tools, then `sketch.py`. No tool
of the three is left half-way and none is kept as code.

## Counts

| | |
|---|---|
| Tools converted | 31 (19 feature, 4 std_more, 8 sketch); all `steps` entries |
| Kept as code | 0 |
| Entries in tools.json | 50 before, 81 after (mine appended after the existing ones; the first 50 are byte for byte as they were) |
| `refuse` steps in the 31 entries | 128, every one reached by a case |
| Cases, old handler against new entry | 581, 0 differences (answer or refusal, every object made or removed, property set and geometry call in order, the objects left) |
| `python3 -m pytest -q` | 852 passed, 338 skipped (3 min 18 s) |
| `scripts/tool_index.py --check`, `scripts/tool_summary.py --check` | both pass |
| Python 3.11 | every changed file compiles; the 581 cases and `tests/test_runners.py` also run under 3.11 with 0 differences |

Identity (name, description bytes, schema with key order, changes, reads, group, no activity) is checked
for all 31 against `tests/_datapd_before.py`, which is itself checked against the source at `99489bb`.

## Per tool

"Model" is the call number in `docs/hardening/models/partdesign-model.json` (PD) or
`sketcher-model.json` (SK). Every converted tool is exercised by at least one call of one of the two
models; none is left without a live call.

### feature.py (group `feature`)

| Tool | Result | What the entry holds / what it calls | Model calls |
|---|---|---|---|
| pd_pad | converted | types, sides, length and taper checks, the order of the property sets, the answer; `set_sides` (the 1.1 / pre-1.1 property names), `find_faces` | PD 8, 15, 107; SK 14, 22 |
| pd_pocket | converted | as pd_pad, with its own type list and "no solid" check | PD 11, 19 |
| pd_revolution | converted | angle and sides checks, axis, sets | PD 64, 65 |
| pd_groove | converted | as pd_revolution plus "no solid to groove" | PD 69 |
| pd_hole | converted | all checks; the coarse-then-fine thread pick as steps; fit, depth, drill point, cut and its custom values; the answer's holes, diameter, thread, cut. Helpers: `thread_pick`, `thread_key`, `hole_spots` | PD 25, 46, 47 |
| pd_fillet | converted | radius check, edges, sets, `changed` | PD 28, 59 |
| pd_chamfer | converted | size, size2-or-angle, sets | PD 27, 58 |
| pd_draft | converted | angle check, faces, neutral plane and pull read before the feature exists | PD 36 |
| pd_thickness | converted | thickness and join checks, sets, `cut` unless outward | PD 50 |
| pd_mirrored | converted | features / "all", originals check, plane; `whole_body` (see thin) | PD 12, 16, 43 |
| pd_linear_pattern | converted | plus occurrences, spacing or length | PD 26 |
| pd_polar_pattern | converted | plus occurrences, angle | PD 57 |
| pd_loft | converted | sections check, additive or subtractive | PD 83 |
| pd_pipe | converted | path checks, spine | PD 89 |
| pd_datum_plane | converted | on, rotate check, offset, attach check, answer | PD 29, 80 |
| feature_list | converted | the row per object (name, type, valid, stepOf, error, dof/geometry or key values, tip) is in the entry; `key_values` reads a feature's properties | PD 21, 110, 113 |
| feature_edit | converted | the loop over `set` with its five refusals, the enumeration check, the repair of renamed edges | PD 20, 70, 71 |
| feature_remove | converted | users check, removal order (feature, a MultiTransform's steps, its sketch), answer | PD 32 |
| feature_suppress | converted | | PD 30, 31 |

### std_more.py (group `std_more`)

| Tool | Result | Notes | Model calls |
|---|---|---|---|
| pd_move_feature | converted | checks, the move loop, the newly-broken check; `reattach` puts a sketch on the same origin plane of the new body | PD 109, 111 |
| pd_reorder | converted | | PD 103 |
| pd_tip | converted | read or set; a sketch or datum gives the solid feature before it | PD 33, 101, 102, 104 |
| pd_shaft | converted | the segment loop and its two refusals are in the entry; `shaft_solid` makes the solid from the outline | PD 112 |

The other 23 tools of `std_more.py` were not mine and are untouched. The four pd_ tools now come first in
that family's list, after pd_clone (data tools are listed before code tools there); nothing in the tests or
the two check scripts depends on that order.

### sketch.py (group `sketch`)

| Tool | Result | Notes | Model calls |
|---|---|---|---|
| pd_body_new | converted | | PD 3 and 13 more; SK 1, 15, 34 |
| sketch_new | converted | plane-or-face check, attach, offset, attach check; `face_frame` lines a sketch on a face up with the world | PD 4 and 14 more; SK 2, 16, 23, 30, 35, 54 |
| sketch_add | converted, thin in one place | the item loop, the order geometry → constraints → named sizes, the answer per item; `build` makes each shape | PD 5 and 14 more; SK 3, 5, 17, 26, 36, 55 |
| sketch_offset | converted | distance, ids, join checks, the two error-to-refusal turns; `offset_out`, `geo_of_edge` | SK 29 |
| sketch_external | converted | the three state refusals, the query loop, the add loop; `edge_refs` runs shape_query's filter | SK 24, 25 |
| sketch_constrain | converted, thin in one place | the loop, the id-range check, FreeCAD's refusal, the over-constrain report in both forms, the take-back of what was added; `make_constraint` turns one constraint into Sketcher's tuples | SK 4, 6-12, 18, 19, 27, 28 |
| sketch_state | converted, thin | `state_of`, then frame, geometry, constraints, error | SK 13, 59 |
| sketch_edit | converted | all fourteen operations in their order as `when` blocks, 25 refusals, the after-edit check, the answer | SK 20, 21, 32, 44-47, 56-58 |

### Thin entries (said plainly)

- **sketch_state**: three helper calls and the answer's shape. `state_of` (the solver's reading: wires,
  open ends, readiness, the todo) is one algorithm and is also used by five other sketch tools.
- **sketch_add**: the entry is real (loop, order, naming, answer) but `build` is a 200-line function of
  fifteen shapes, each with its own input check and refusal (16 raise sites). Those refusals are *not* in the
  entry. They are interleaved with the arithmetic of each shape; lifting them would mean fifteen shapes as
  data, which I judged adds nothing.
- **sketch_constrain**: likewise `make_constraint` and `_ref` keep their refusals (7 raise sites, one of them the
  `refs` form message used for a dozen forms per constraint type). The entry prefixes them with `constraints[i]`.
- **pd_mirrored / pd_linear_pattern / pd_polar_pattern** with `features: "all"`: `whole_body` holds the
  tip-put-back (`try … finally`) and the choice between FreeCAD's TransformMode and listed originals.
- **pd_shaft**: `shaft_solid` (outline, revolve, lay along the axis).
- Helpers that still refuse in their own words, as before: `gid` (a geometry id), `con_index`, `_font`,
  `vec2`/`vec3`, and pd_common's finders (`pd_body`, `sketch_of`, `in_body`, `plane_ref`, `axis_ref`,
  `find_faces`, `find_edges`, `tip_shape`, `settle`). pd_common.py is unchanged.

## Runner changes (agentlink/runners.py, 19 lines added, 7 reworded; general, additive, tested)

Two additions to the `try` step, both needed by sketch_constrain, sketch_offset and sketch_edit:

1. `"on": "failure"` catches any error *except* a tool's own refusal, which passes through. It is the
   handler's `except ToolError: raise` / `except Exception as e:`. Used where a refusal can be raised
   inside the tried steps (`gid` inside a fillet).
2. `"reraise": true` runs the `except` steps and then lets the caught error go on unchanged. It is
   "undo, then fail as you were failing": sketch_constrain deletes the constraints it added and solves
   again, whatever went wrong.

`ERRORS` gained `"failure"`, `EXTRA["try"]` gained `"reraise"`, `check_entry` refuses a non-boolean
`reraise`. Documented in the runners docstring, `tooldata.py`, `tools.schema.json` and
`docs/data-tools.md`. Tested in `tests/test_runners.py`
(`test_try_lets_a_refusal_through_and_undoes_before_an_error_goes_on`). `expr.py` is unchanged. Another
agent extending `try` in parallel would touch the same few lines of `_step`.

## Behaviour differences from the handlers (all small; listed so none is a surprise)

1. **pd_pocket** no longer carries "type …: … has no solid to go up to yet — the first pad takes type
   length". A pocket on a body with no solid is refused earlier ("no solid to pocket"), so the handler
   could never say it. pd_pad keeps it.
2. **sketch_constrain**: a refusal from `make_constraint` was re-raised with its own code; the entry's
   code is fixed at `invalid_input`. Every refusal there is `invalid_input` today, so nothing changes now;
   a future one with another code would be flattened.
3. `set_sides` and `whole_body` now answer False / None where they used to refuse, and the entry refuses
   with the same words at the same point (same property sets before it).
4. sketch_offset's id check is written `is_number(i) and not is_float(i)` so that `true` is still taken
   as id 1, as `isinstance(i, int)` did. Kept on purpose for identity; it is arguably a bug to fix later.

## Tests

- `tests/test_datapd_data.py` (the BIM pattern), `_datapd_before.py`, `_datapd_cases.py`,
  `_datapd_standin.py`: identity for 31 tools; 581 old-against-new cases; every `refuse` reached
  (`UNREACHED = []`); each entry calls only helpers its family has; 50 pinned answers and refusals in
  `EXPECT`. A deliberate mutation of two entries was caught (then reverted).
- `tests/test_stem_findings_more.py`: one assertion read `feature.py`'s source for the fillet/chamfer
  `"changed"` rule. That rule is now in the entries, so the assertion reads the entries instead. The
  behaviour it guards is unchanged.
- `tests/test_runners.py`: the new `try` test.

## What is unproven

- **Everything about FreeCAD itself.** The two live models need to be re-run on the Mac against this
  patch; that is the only proof of real behaviour.
- The stand-in is cruder than BIM's in places that matter:
  - faces and edges are not found by geometry: `find_faces`, `find_edges`, `find_face` and
    `measure.query` are replaced by stubs that answer the number a query carries and log the call. So
    what is proven is *what was asked and in what order*, not which face comes back.
  - a body's volume is a table of what each feature type adds; "added no material" and "cut nothing" are
    forced by flags.
  - the sketch solver calls the same dimension given twice redundant or conflicting, and nothing else.
  - `geo.stats` is replaced (volume, faces, solids only).
- `reraise` on a *crash* (not a refusal) inside sketch_constrain is proven in `test_runners.py` only; no
  sketch case crashes inside that block.
- The evaluator reads `x.name` on a dict as its item. I checked each use by hand (`a.set`, `a.delete`,
  `x.at`, `c.name`, `it.name`); a FreeCAD object that happens to be a dict subclass would read
  differently, and none is passed here.
- Under Python 3.11 here there is no numpy, so the stand-in puts an empty `numpy` module in place when it
  is missing (std_more's other tools import it; these four do not use it).
- FILES was not regenerated (four new test files).

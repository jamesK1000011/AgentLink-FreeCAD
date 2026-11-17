# Parameters, more Part Design and more Sketcher as data (tag datask2, 2026-11-16)

Checkout `<work>/`, base `effbcc7`. Patch: `<work>/datask2.patch` (`git add -A -N`, `git diff effbcc7`,
FILES left out; it applies to a clean `effbcc7` and the new test module passes there, checked in a scratch worktree). Nothing committed
or pushed. **Nothing ran on FreeCAD**: the proof is plain Python on a stand-in. The session was restarted once by the server mid-run; the
checkout was consistent at the restart and the work went on from there.

All three files were finished, in the order given: `param.py`, `feature_more.py`, `sketch_more.py`. No tool is left half-way and none is
kept as code.

## Counts

| | |
|---|---|
| Tools converted | 25 (6 param, 7 feature_more, 12 sketch_more); all `steps` entries |
| Kept as code | 0 |
| Entries in tools.json | 264 before, 289 after (mine appended at the end; the first 264 are byte for byte as they were, asserted when written) |
| `refuse` steps in the 25 entries | 133; 132 reached by a case, 1 unreachable (below) |
| Cases, old handler (from `effbcc7`) against new entry | 331, 0 differences (answer or refusal, every object made or removed, property set and Sketcher/sheet call in order, the objects left); 0 crashes |
| `timeout 280 python3 -m pytest -q tests` | 976 passed, 347 skipped (3 min 37 s). `tests/test_files.py` did not complain here |
| `scripts/tool_index.py --check`, `scripts/tool_summary.py --check` | both exit 0 |
| Python 3.11 | every changed file compiles; the 331 cases and the helper check also run under 3.11 with 0 differences |
| runners.py, expr.py, tooldata.py | unchanged |

Identity (name, description bytes, schema with key order, changes, reads, group, no activity) is checked for all 25 against
`tests/_datask2_before.py`, itself checked against the source at `effbcc7`.

## Wiring

- `param.py` is the only file of group `param`: its entries have no `family` key; the file ends `runners.tools(GROUP, s, helpers)`.
- `feature_more.py` shares group `feature` with `feature.py` (whose entries have no `family` key): mine say `"family": "feature_more"` and
  the file ends `runners.tools(GROUP, s, helpers, family="feature_more")`. It keeps its own `new` (feature.py's `new` also sets the tip;
  this file's tools set the tip themselves, at their own point in the order, and pd_gear never does).
- `sketch_more.py` likewise: `"family": "sketch_more"`, group `sketch`.
- No helper touches FreeCAD when `tools()` is built (finders are lambdas; `V = FreeCAD.Vector` is at import, as in feature.py).
- `feature.py`, `sketch.py`, `pd_common.py`, `picks.py` are untouched.

## The "newly broken" guard

Every guard that refuses a change for what it breaks is written in the entry with the helper `broken`, which is `pd_common.newly_broken`
(what the change broke, not what was failing before the call), as the code at base did:

- param (param_set, varset_new, varset_set, param_remove, param_bind twice): recompute; where references were snapshotted and something is
  newly broken, `repair_refs`; then `{"let": {"bad": "=broken(doc())"}}` and the refusal "… breaks …: … — nothing was kept. Choose a value
  the features can take." with `why` (a sheet's failing cells) as before.
- sketch_more (all 12; sketch_validate only when it repairs): recompute, `bad = broken(doc())`, "That breaks …", then `finish`.
- feature_more goes through `pc.settle`, unchanged, which uses `newly_broken` itself.

## Per tool

Model calls: SH = `docs/hardening/models/sheetfem-sheet-model.json`, PD = `partdesign-model.json`, SK = `sketcher-model.json`.
`coredoc-model.json` calls none of the 25. Every converted tool has at least one live model call; none is without.

### param.py (group `param`)

| Tool | What the entry holds / what it calls | Model calls |
|---|---|---|
| param_set | name and value checks, the cell's content, the row found or added, "FreeCAD cannot read it", the alias refusal, the note, the guard, "does not evaluate", the answer with refsFound | SH 37, 38, 39 |
| param_list | the row per parameter (value, content, note, usedBy); `varset_rows` reads the variable sets | SH 41 |
| varset_new | name checks, the VarSet made (unavailable before 1.0), the loop over properties with its six refusals, the set removed when one is refused, the guard, the answer | SH 32, 33 |
| varset_set | which set (three refusals), the same loop, the guard, the answer | SH 35, 36 |
| param_remove | found, in use, alias and row removed, the guard | SH 42, 47 |
| param_bind | target, object, a sketch's named driving constraint (three refusals), the property, unbinding, the expression qualified, the two FreeCAD refusals, the guard, the value read back | SH 13-16, 34, 40, 44-46 |

### feature_more.py (group `feature`, family `feature_more`)

| Tool | What the entry holds / what it calls | Model calls |
|---|---|---|
| pd_primitive | kind, size checks, each property set from the `PRIMS` table, attach, tip, settle | PD 35, 37, 49, 54, 55, 93, 95, 98, 99, 100 |
| pd_gear | the six input checks, label, attach, the ring gear (rim, ring, pocket) or the pad, the bore, the answer. `gear_profile` makes the profile (see thin) | PD 91 |
| pd_helix | two-of-three and its sizes, the mode table, growth's two refusals, every property set, settle, `helix` after the answer | PD 75, 76 |
| pd_multitransform | features, steps, the loop with its kinds and four refusals, labels, tip, settle, `steps` after the answer | PD 38 |
| pd_datum | kind, on a round edge or placed (per kind), "would not attach", the answer's direction / axes | PD 39-42, 56, 66 |
| pd_binder | from (four refusals), faces, the binder, frozen, "did not take", the answer | PD 52 |
| pd_boolean | op, with (two refusals), the boolean, tip, settle, `with` after the answer | PD 96 |

### sketch_more.py (group `sketch`, family `sketch_more`)

| Tool | What the entry holds / what it calls | Model calls |
|---|---|---|
| sketch_copy | the ids check, by / rotate / scale, copy or move, the answer's did and new; `turn`, `scaling`, `copies` | SK 40, 41 |
| sketch_array | polar (count, step) or rows × cols (three refusals, which count runs along the vector), FreeCAD's refusal | SK 39 |
| sketch_extend | geo, kind, end, `to` (four refusals) or `by`, an arc's mm turned to an angle, FreeCAD's refusal; `reach` | SK 42, 43 |
| sketch_join | the two pair checks, continuity, FreeCAD's refusal, the B-spline's id | SK 60, 61 |
| sketch_carbon | from, FreeCAD's refusal, the new ids | SK 31 |
| sketch_project | from, the edges by name or by where, defining (unavailable) and FreeCAD's refusal, the ids | SK 33 |
| sketch_to_bspline | the ids check, each converted, FreeCAD's refusal | SK 48 |
| sketch_bspline | geo, degree up or down (`lower_degree`), knot, the sketch put back on an error, the answer's degree, poles, knots | SK 49, 50 |
| sketch_merge | thin: `new_beside`, `copy_frame`, `bring_in` per source, the removal, the answer | SK 52 |
| sketch_mirror | thin: `mirrored`, the construction flags, the label, the answer | SK 51 |
| sketch_attach | body, plane or face, the sketch moved after a later feature (two refusals, both in the entry), the attachment, "would not attach" | SK 53 |
| sketch_validate | `detect`, the solver's lists, the repair step by step (each fix and its word, the auto-constrainer's four calls, the conflict refusal), the sketch put back on a refusal or a crash | SK 37, 38 |

### Thin entries and helpers that hold an algorithm (said plainly)

- **sketch_merge**: `bring_in` is the loop (each curve copied into the first sketch's frame, each constraint's ids moved up, those to
  outside geometry counted as left out). The entry is the check, the order and the answer.
- **sketch_mirror**: `mirrored` is the matrix and the arc turned round. The entry is the check, the order and the answer.
- **pd_gear**: `gear_profile` makes the involute gear object or the sprocket's sketch with `FreeCAD.GuiUp` held off in a `try … finally`
  (state that must be put back: the steps have no `finally`). The handler's code moved there unchanged. Everything else is in the entry.
- **sketch_validate**: `detect` is the three detectors, each tried, with the older release's fallback (nested `try`).
- **param_list**: `varset_rows` reads the variable sets (a row per variable); the Params sheet's rows are in the entry.
- Small ones: `why` (a broken sheet's cells), `reach`, `turn`, `scaling`, `copies`, `kept`, `restore`, `lower_degree`, `copy_frame`,
  `new_beside`, `attach_origin`, `new`, `place`.
- Finders that still refuse in their own words, as before: `pd_body`, `sketch_of`, `in_body`, `plane_ref`, `axis_ref`, `find_edges`,
  `find_face`, `tip_shape`, `vec2`, `vec3`, `settle`, `alias_problem` (answers the problem; the entry refuses).

## Unreachable refusal (1)

- `varset_new: properties.{pname} = {value!r}: it is a {o.getTypeIdOfProperty(pname)} …`: varset_new shares varset_set's loop, and a set
  just made has no property left to collide with (its own are refused before), so "an existing property will not take this value" cannot
  be raised there. It could not in the handler either. It is kept so the two loops stay the same, and it is reached in varset_set.

## Behaviour differences from the handlers (all small)

1. `param.var_type` answers `(None, None)` for a value of no kind where it raised; the entries refuse with the same words at the same
   point. `tests/test_hidden_parts.py` (its only outside user) passes.
2. `sketch_more.ids_of` is gone: its two refusals are in sketch_copy, sketch_array and sketch_to_bspline. Nothing else used it.
3. sketch_extend `to`: `reach` works out the distance to the meeting point before the entry checks the gap (the handler after). No effect
   unless `distToShape` gave no points at all, which it does not.
4. sketch_bspline's geo check is written `is_number(g) and not is_float(g)` so `true` is still taken as id 1, as `isinstance(g, int)` did
   (same choice as sketch_offset in datapd; arguably a bug to fix later).
5. Local names differ from the handlers' where they would clash (`pname` for a property's name, `amount` for extend's increment);
   messages are filled to the same bytes.
6. The module-level functions of param.py that other code imports (`sheet`, `rows`, `exprs`, `qualified`, `by_varset_label`) are unchanged.

## Tests

- `tests/test_datask2_data.py` (the datapart2 pattern, BASE `effbcc7`), `_datask2_before.py`, `_datask2_cases.py`, `_datask2_standin.py`:
  identity for 25 tools; 331 old-against-new cases; every `refuse` reached but the one above (`UNREACHED`); each entry calls only helpers
  its family has; no handler left beside an entry; 55 pinned answers and refusals in `EXPECT`.
- The stand-in is built on `_datapd_standin.install()` inside the child process; that file is not modified.
- `docs/data-tools.md`: one paragraph added.
- FILES was not regenerated (four new test files).

## What is unproven

- **Everything about FreeCAD itself.** The three live models need re-running on the Mac against this patch.
- "Not what was failing before the call": on the stand-in no call is marked in `health`, so `newly_broken` equals `broken` there. The
  entries call the right helper, but the difference between the two is not exercised (one case has a feature failing from the start, and
  both old and new count it, as the stand-in must).
- The stand-in is crude where it matters:
  - a sheet's cell is evaluated by Python arithmetic over the aliases; "cannot be parsed" is unbalanced brackets or `??`;
  - a VarSet's quantity takes eight units; the stand-in lists a `Shape` among a VarSet's variables (its own artefact, same on both sides);
  - a feature's volume is a table or a case's flag; faces and edges are answered by the number a query carries;
  - a matrix is a record of what was asked; a mirrored arc's angles are real arithmetic, a turned or scaled curve is only labelled;
  - Sketcher's copy, array, extend, join, carbon copy, NURBS, detectors and repairs are stubs that log, add copies and raise on a flag;
    a line "meeting" a curve is a flag.
- `gear_profile`'s put-back of `GuiUp` is not compared (the code is the handler's, moved).
- A crash (not a refusal) inside varset_new's property loop leaves the new set in place, as in the handler; no case crashes there.

# Tools as data: Mesh and Points (tag datamesh, 2026-11-16)

Checkout `<work>/`, base `99489bb` (main when the work started). Patch:
`<work>/datamesh.patch` (`git add -A -N`, `git diff`, FILES left out). Nothing committed
or pushed. **FreeCAD did not run here**: everything below is proven on a stand-in, not on FreeCAD.

## Where I stopped

At the end of `agentlink/families/points.py`. Done, whole files: **Mesh** (`meshobj.py`) and **Points**
(`points.py`). **Not started: CAM** (`cam.py`, `cam_more.py`) **and TechDraw** (`techdraw.py`); those
three files are untouched, as is `std_more.py` (`points_structure` and `surface_polynomial` live in
`std_more.py`, not in my families' modules, so they were left alone as the brief says). Nothing is
half-converted.

## Counts

- Handlers looked at: 28 (Mesh 20 code + `meshobj_offset` already data; Points 8).
- **Converted: 28 of 28** (Mesh 20, Points 8), all with the `steps` runner. **Kept as code: 0.**
- `agentlink/data/tools.json`: 50 → 78 entries (appended at the end, in the old code order; the 50
  existing entries' text is byte-for-byte the same, checked). Hub: 78 data tools.
- Family code: `meshobj.py` 1121 → 640 lines, `points.py` 667 → 515. No `Tool(...)` and no handler is
  left in either; what remains is helpers, each with a docstring.
- Suite: **851 passed / 338 skipped** (3 min 45 s), with 7 new tests. Every changed or new file compiles
  with `python3.11 -m py_compile`. `scripts/tool_index.py --check` and `tool_summary.py --check`: current
  (both by name; nothing to regenerate). Echo, heavy (`keep.py`) and writer (`paths.WRITERS`) tables are
  by name and untouched; tool names did not change.
- **No change to `runners.py`, `expr.py` or `tooldata.py`.** The existing constructs covered all 28.

## Per tool

Converted, entry holds checks, refusals, order and the answer's shape; helpers named in brackets are the
geometry / FreeCAD-API parts.

| Tool | Notes |
|---|---|
| meshobj_from_shape | `choose` by method; `mesh_shape(kw)` is MeshPart.meshFromShape |
| meshobj_info | `evaluation`, `reading` (as before) |
| meshobj_repair | the loop, undo-if-worse and the answer are in the entry; `repair_step` maps a fix name to FreeCAD's calls; `edges_state`, `worse` |
| meshobj_decimate, _refine, _smooth | plain steps |
| meshobj_edit | `choose` by action; `show` hides/shows where there is a view |
| meshobj_trim | `plane_sides`, `merge_cut`, `cap` (today's fixes: counts before the cut, merged cut loop) |
| meshobj_transform | `shift`, `mirror_matrix`, `through_placement` (the placed-mesh fix) |
| meshobj_boolean | the three engines in order in the entry: `own_boolean`, `freecad_boolean`, `solid_boolean` |
| meshobj_sections | `reach`, `loops` (the answered-twice fix) |
| meshobj_split | plain steps (the 100-piece guard is a `refuse`) |
| meshobj_segments | `mean_normal`; rows built in the entry |
| meshobj_project | `project_on`, `polylines` (the spur fix) |
| meshobj_primitive | `choose` by kind; a `try` round FreeCAD's builders |
| meshobj_merge | `in_place` |
| meshobj_boundary | `open_edges`, `edge_loops`; wires and rows in the entry |
| meshobj_export | plain steps; the format list is in the entry |
| meshobj_unwrap | helper-heavy: `flat_pattern` (exact roll-out), `flatten_apart` (flatmesh in a child Python), `stretch`, `write_pattern`; the checks, both branches, the three refusals of the child run and the answer are in the entry |
| points_import | `read_file`, `read_e57`, `finite` |
| points_sample | `sampled` |
| points_info | `spacing` |
| points_crop | masks as helpers: `in_box`, `within`, `in_front`, `both`, `inverse`, `without_specks`, `thinned` |
| points_fit | `choose` by shape; `fitted`, `distances`, `rms`, `along`, `curve_through`, `plane_patch` |
| points_merge | `stacked` |
| points_mesh | `choose` by method; `grid_mesh`, `hull`, `poisson`, `triangles_mesh` |
| points_export | `write_points`, `read_file` (the read-back) |

**Thin entries** (one algorithm in one helper, the entry is the lookup, a check and the answer's shape):
`meshobj_curvature` (`curvature_stats`: numpy over the per-vertex curvatures). Close to thin:
`meshobj_unwrap` is long as an entry but its three largest parts are helpers (above); `points_info`.
Easy to turn back if that is not what "data" should mean.

Pre-existing module helpers that still refuse in their own words (unchanged, shared finders or input
readers): `mesh_of`, `cloud`, `vec`, `xyz`, `picks.num`, `sample_triangles` ("The surface has no area to
sample."), `write_points` (unreachable: the entry checks the ending first).

## Proof here

`tests/test_datamesh_data.py` (pattern of `test_bim_data.py`), with `tests/_datamesh_standin.py`,
`_datamesh_cases.py`, `_datamesh_before.py`:

- identity of all 28 against the snapshot (name, description bytes, schema with key order, changes,
  reads, group), and the snapshot checked against git `99489bb`;
- no handler or `Tool(...)` left in the two files; every name an entry calls is in its family's helpers;
- **330 cases** (Mesh 218, Points 112) run the old handler (from git) and the new entry on the stand-in:
  result or refusal (code and words), every traced call in order, the objects left. **0 differ**, no
  crash on either side. 147 answer, 183 refuse.
- every `refuse` in the 28 entries is reached by a case, except three listed in `UNREACHED` with their
  reason: `meshobj_unwrap` "No Python to run the unwrapping…" and "…ran over 5 minutes…" (the child
  process there is always a Python; no five-minute run), `points_mesh` "A … cell makes … triangles"
  (needs over two million triangles).

The stand-in: numpy, `meshbool`, `meshdist`, `fitting`, `hull3d`, `flat2d` and the file readers are the
real ones; the mesh, cloud, shapes, MeshPart, ReverseEngineering and flatmesh's child run are stand-ins
whose methods are traced and bent by flags. It proves order and words, not FreeCAD's Mesh behaviour.

## The live models

`docs/hardening/models/draftmesh-mesh-model.json` (calls from 0) exercises **all 20** converted Mesh
tools (and `meshobj_offset`, 22):

from_shape 3–7 · info 8, 9, 12, 56 · trim 10, 11, 16, 17, 61 · boundary 13 · repair 14, 15 ·
decimate 18 · refine 19, 20, 49 · smooth 21 · transform 23–26 · sections 27, 28 · segments 29–31 ·
curvature 32, 33 · project 35, 36 · primitive 37, 38, 41–44 · boolean 39, 40 · merge 45 ·
split 46, 47 · edit 48, 50, 51 · export 52–54 · unwrap 59, 60, 62.

`docs/hardening/models/bimcam-points-model.json` exercises **all 8** converted Points tools:

sample 2, 16, 19 · info 3, 31 · export 4–7 · import 8, 9, 30 · crop 10, 13, 20, 25, 32, 33 ·
fit 11, 12, 14, 17, 24, 26 · mesh 21–23, 34 · merge 27. (`points_structure` 28, 29 is `std_more.py`,
not converted here.)

Converted tools no model call exercises: none. Paths not checked against the models call by call (I
mapped tools to calls, not each branch): expect the boolean's fallbacks, repair's undone steps, E57,
Poisson and most refusals to be outside the models.

## Unproven / risks

- **Not run on FreeCAD.** Run both models on the Mac before this is trusted; the 338 skipped tests
  include `tests/test_meshobj.py`, `test_meshbool.py`-style FreeCAD-only ones.
- Small differences, all in states that should not occur:
  - `meshobj_from_shape`, `_boolean`, `_project` imported MeshPart at the top of the handler; now it is
    imported where it is called. A FreeCAD with Mesh but without MeshPart crashed before any check and
    now crashes after them.
  - `meshobj_primitive`: the handler's `try` wrapped each whole branch; the entry's wraps FreeCAD's
    builder calls only. What is now outside (reading validated numbers) cannot throw.
  - `points_fit` and `points_mesh` each had a second, unreachable "else: refuse" after the first check
    of the same value; dropped.
- A `try` step without `on` catches a refusal too, as the handlers' `except Exception` did; none of the
  wrapped helpers raises one.
- Long entries: `meshobj_unwrap`, `points_fit`, `meshobj_boolean`, `meshobj_repair` are the ones to
  read for whether they still read as the tool. Steps are one per line, so nested branches make long
  lines.
- Speed: `meshobj_repair`'s loop (10 rounds at most) and `meshobj_sections` / `_boundary` / `_segments`
  loops (up to 500 slices, loops, regions) are now interpreted per item; microseconds each beside the
  mesh calls, not measured on a dense scan.
- The old-vs-new tests need git commit `99489bb` and numpy; without either 4 of the 7 skip (identity
  still runs against the snapshot).

## To do on merge (not in the patch)

- `FILES` must gain `tests/_datamesh_before.py`, `tests/_datamesh_cases.py`,
  `tests/_datamesh_standin.py`, `tests/test_datamesh_data.py`, or `tests/test_files.py` fails once they
  are tracked.
- `agentlink/data/tools.json`: my 28 entries are appended after `bim_reorder`; merge by key.
- `docs/data-tools.md`: two short additions (the families that are data; the proof module). Expect a
  text conflict there if another agent edits the same paragraphs.
- `CHANGELOG.md` and `docs/hardening/` not touched; this file is not copied into the repo.

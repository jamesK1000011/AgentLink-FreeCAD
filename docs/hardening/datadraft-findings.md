# draft.py as data: four Draft tools and the four surface tools beside them (tag: datadraft, 2026-11-16)

Checkout `<work>/`. Base: a local commit `bec3375` (the datapart work: `99489bb` plus
`datapart.patch`), made as asked and **not pushed**. Patch: `<work>/datadraft.patch`,
relative to `bec3375` (`git add -A -N`, `git diff`, FILES left out; it applies clean to `bec3375`).
**Nothing ran on FreeCAD**: every proof here is plain Python on a stand-in.

## Where it stopped

| File | State |
|---|---|
| `families/draft.py` (8 tools) | **done**, whole: `surface_fill`, `surface_loft`, `surface_points`, `surface_thicken` (this finishes Surface), then `draft_text`, `draft_outline`, `draft_array`, `draft_fonts` |
| `families/draft_more.py` (13 `draft_*`) | **not started** — read to about two thirds, nothing changed in it |
| `families/model_more.py` (10 `part_*`), `families/part_more.py` (6 `part_*`) | **not started**; no `datapart2.patch` was written |

I stopped between files on purpose. `draft_more.py` is about 800 lines of handlers (`draft_modify` and its
point edits alone are 200) and needs a stand-in Draft module of some thirty makers; I did not have the
room left to finish and prove it whole, and a half-converted file is worse than none. `std_more.py`'s
`points_structure` was not touched.

Surface is now complete as data: `surface.py` (6), `surface_polynomial`, and these four.

## Counts

- **Converted: 8. Kept as code: 0.** `draft.py` has no `Tool(...)` and no handler left.
- `agentlink/data/tools.json`: 73 → 81 entries, the 8 appended at the end, all `steps`, each with
  `"family": "draft"`.
- `draft.py`: 617 → 318 lines.
- **No change to `runners.py`, `expr.py`, `tooldata.py` or the schema.**
- Suite on the final tree: **857 passed, 338 skipped, 1 failed**. The one failure is
  `tests/test_files.py::test_files_list_is_current`, and it is not from this patch: my local commit made
  the four datapart test files tracked, and FILES is the main session's to regenerate (it lists tracked
  files; the list it found extra is exactly `tests/_datapart_*.py` and `test_datapart_data.py`). The datapart tree, run
  before the commit with those files untracked, had no failure. The 7 new tests of
  `tests/test_datadraft_data.py` pass, as do the 7 of `test_datapart_data.py`.
- `scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: current. Changed and new files
  compile under `python3.11 -m py_compile`. `paths.GEOMETRIC` (`draft_array`'s path is a curve) is by
  name and untouched.

## Why `"family": "draft"`

`draft.py` and `draft_more.py` share group `draft`, and `draft_more.py` already asks the runner for the
group's entries that name no family (`draft_to_sketch`). So these eight say `"family": "draft"` and
`draft.py` asks for its own (`runners.tools(GROUP, s, helpers, family="draft")`), as `bim_more` does.
When `draft_more.py` is converted its entries need no family. The same will hold for `model_more.py` and
`part_more.py`, which share group `model` with `model.py`: their entries will need a family each.

## Per tool

| Tool | As data | Helpers of note |
|---|---|---|
| `surface_fill` | converted: every check a `refuse` step (edge kind, no edges, several runs, open with the gap said, no fill, empty, thickness) | `sort_edges`, `filled_face`, `is_edge` |
| `surface_loft` | converted | `curve`, `make_loft`, `finish` |
| `surface_points` | converted: approximate or interpolate is a `when` inside a `try` | `point`, `bspline_surface`, `finish` |
| `surface_thicken` | converted | `is_surface`, `is_face`, `finish` |
| `draft_fonts` | converted (a read; the answer's `paths` and `more` by `when`) | `fonts`, `font_file` |
| `draft_text` | converted: the order of translate, rotate, copy, transform, extrude is in the entry | `pick_face`, `face_frame`, `font_file`, `text_faces` |
| `draft_outline` | converted: scale, mirror, the print note's `try`, the extrude branch as an early `answer` | `outline_faces`, `place_on`, `pick_face` |
| `draft_array` | converted: `choose` grid / polar / path, the separate branch as an early `answer` | `along_path`, `refined`, `curve` |

None is thin in the sense of one helper holding the handler. What stays in code:

- **`finish`** (was `_finish`, with `_thicken`): the three surface tools' shared tail — thicken, make the
  object, the answer and its warnings. It is the family's finishing code and keeps the thickness and
  side refusals and the two warning texts.
- **Readers that keep their own refusals**, shared by several tools and helpers before too: `curve`
  (was `_curve`; loft and array), `pick_face` (text and outline), and the module-level `font_file`,
  `text_faces`, `face_frame`, `outline_faces`, `place_on`, all unchanged.
- **New small helpers**: `along_path` (where copies go along a curve, with or without turning) and
  `refined` (the FreeCAD 1.1.3 `removeSplitter` "Null shape" guard for copies that do not touch) —
  both lifted out of `draft_array` unchanged.

## Proof here

`tests/test_datadraft_data.py` with `_datadraft_before.py` and `_datadraft_cases.py`, on the same
stand-in as datapart (`tests/_datapart_standin.py`, extended):

- **Identity**, 8 tools: name, description bytes, schema with key order, changes, reads, group, against
  the code at `99489bb` (`draft.py` is the same there and at `bec3375`).
- **Old handler against new entry, 102 cases** (37 answer, 63 refuse, 2 crash alike): answer or refusal,
  every shape operation, object added or removed and property set in order, the objects left. 0 differ.
  17 answers and refusals are also pinned to fixed text.
- **Every `refuse` in the 8 entries is reached** by a case; every name an entry calls is in the helpers.
- The four side-by-side tests skip where numpy is missing (as datapart's do).

Stand-in changes, all additive: the vector is iterable, a rotation turns a vector about z, a placement
gives a matrix, `Part.Edge` / `Wire` / `Face` / `Shell` / `Solid` are kinds `isinstance` can ask,
`Part.sortEdges`, `makeFilledFace`, `LineSegment`, `BSplineSurface`, a surface's `makeOffsetShape`,
`makeOffset2D`, `transformShape`, a curve's points and tangents, a wire of an outline's edges closes,
and `Session.body` takes a name. The datapart cases were rerun on it: still 295, 0 differ.

For these tools the stand-in replaces, in both old and new, four module-level functions the conversion
did not touch: `fonts` (no font folders read), `text_faces`, `face_frame` and `outline_faces` (no SVG or
DXF read). So setting text in a font, reading artwork and a face's real frame are **not** exercised
here at all; the order of steps, the words and the answer's shape are.

## Live models

Calls that exercise each converted tool (numbers from 1):

- `draftmesh-surface-model.json`: `surface_fill` 8, 9, 10, 45; `surface_thicken` 25, 26; `surface_loft`
  46, 47; `surface_points` 48, 49.
- `draftmesh-draft-model.json`: `draft_fonts` 75; `draft_text` 77, 78; `draft_array` 79.
- **`draft_outline`: no call in any live model.** It is the one converted tool nothing live exercises
  (it needs an SVG or DXF file on the Mac); a call with a small SVG is owed.

## Unproven, and risks

1. **Nothing ran on FreeCAD.** `draftmesh-surface-model.json` and `draftmesh-draft-model.json` are the
   proof still owed for these eight.
2. **`draft_outline`** has no live call and its file reading is stubbed here: the least proven of all.
3. **`draft_text` / `draft_outline`**: fonts, lettering and the face frame are stubbed; only two live
   calls of `draft_text`, none engraving at a point off centre.
4. **`draft_array`**: one live call. The path kind (`along_path`) and the refining guard (`refined`)
   were moved into helpers; compared on the stand-in only.
5. `isinstance` tests on Part kinds became helpers (`is_edge`, `is_face`, `is_surface`); the stand-in
   answers them by a shape's kind, real FreeCAD by class. Same test, not run live.
6. `tests/test_files.py` fails on my local commit until FILES is regenerated (not mine to do).
7. `docs/data-tools.md` still names only BIM as data; left alone because of parallel edits.

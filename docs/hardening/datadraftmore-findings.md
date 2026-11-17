# draft_more.py as data: the 13 draft_* tools (tag: datadraftmore, 2026-11-16)

Checkout `wt3/d5`, base `b408a91`. Patch: `datadraftmore.patch` (`git add -A -N`, `git diff b408a91`, FILES
left out; `git apply --check` on a clean `b408a91` passes). Nothing committed or pushed.
**Nothing ran on FreeCAD**: every proof here is plain Python on a stand-in.

## Counts

- **Converted: 13 of 13. Kept as code: 0.** `draft_more.py` has no `Tool(...)` and no handler left
  (874 -> 364 lines); it holds the named helpers, each with a docstring.
- `agentlink/data/tools.json`: 167 -> 180 entries, the 13 appended at the end, all `steps`, in the file's
  own layout. The 167 before them are byte-identical (the diff of the file has no removed line).
- The entries name **no family**: `draft_more.py` asks for group `draft`'s entries without one
  (`runners.tools(GROUP, s, helpers)`, as it already did for `draft_to_sketch`); `draft.py` asks for
  `family="draft"`.
- **No change to `runners.py`, `expr.py`, `tooldata.py`, the schema, or `tests/_datapart_standin.py`.**
- `scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: current, nothing to regenerate.
- All changed and new files compile under `python3.11 -m py_compile`.
- Suite (`timeout 280 python3 -m pytest -q tests`): **886 passed, 338 skipped, 1 failed** in 221 s. The one failure is `tests/test_files.py::test_files_list_is_current`: FILES lacks exactly the four new test files (expected; FILES left alone). The 84 `refuse` steps of the 13 entries are all reached.

## Per tool

| Tool | As data | Helpers it calls beside the readers |
|---|---|---|
| `draft_from_sketch` | whole | — |
| `draft_facebinder` | whole (the tuple fallback is a `try`) | — |
| `draft_2d_view` | whole (either maker name, the keyword fallback a `try` on TypeError, warning in `answer.then`) | `kind_of` |
| `draft_clone` | whole (the BIM clone's refusal removes it in `first`) | — |
| `draft_layer` | whole (late answer through `done`) | `kind_of`, `gui`, `done` |
| `draft_hatch` | whole | `pattern_file`, `is_pat`, `pattern_names` |
| `draft_label` | whole | `make_label` (keywords only), `label_text` |
| `draft_plane` | whole (the other-tab error: `try` on AttributeError with `reraise`) | `gui`, `unique`, `snapshot`, `step` |
| `draft_shape` | whole: one `choose` by kind, every "over 0" check a `refuse` with its words spelled out | `pl_of` |
| `draft_link_array` | whole: one `choose` by kind, each "whole number" check a `refuse` | — |
| `draft_dimension` | whole: the makers and their checks inside the `try` the handler had (`reraise`), measures in `answer.then` | `is_round`, `gui` |
| `draft_style` | whole: the style keys with their kinds and the arrow names are data in the entry; each value's check is a `refuse` | `styles_in`, `style_users`, `offer_styles`, `restyled`, `dumps` |
| `draft_modify` | move, rotate, scale, mirror, offset, upgrade, downgrade, join, fillet and the answer are steps; **the five point edits are one helper** | `edit_points`, `new_radius`, `results`, `near_ends`, `alive`, `is_seq`, `kind_of` |

### Kept as code inside helpers, with the reason

- **`edit_points`** (split, stretch, extend, to_bspline, to_wire of `draft_modify`), with `pointed` and
  `set_points`: unchanged from the handler. It is loops over point lists with projection arithmetic and
  in-place edits, and it **keeps its own 8 refusals in code** (split: one wire / edge / at beyond the
  segment; stretch: box / no point inside; extend: trims past first / last; "not a Draft wire…").
  This is the one "thin" part: for those five ops the entry is `edit_points(op, objs, a)` then the shared
  tail. Converting each op to steps is possible and was not done here.
- **Readers that keep their own refusals** (shared, unchanged): `objs_of`, `find`, `resolve`, `vec`,
  `num`, `direction`, `pl_of`, and `finish` ("Draft made nothing from that.", "Draft refused it: …").
- **Small FreeCAD-API helpers lifted out unchanged**: `label_text` (a release that left a label's text
  empty), `pattern_file` / `is_pat` / `pattern_names` (file reading), `new_radius` (a circle's offset is
  a radius), `results` (what an op made or changed, alive), `near_ends` (the two open ends nearest each
  other, for upgrade's note), `styles_in` (JSON in the document's Meta), `style_users`, `offer_styles`,
  `restyled` (view objects, each with its own try/except), `alive`, `kind_of`, `is_round`, `is_seq`,
  `make_label` (the maker takes keywords that vary; a `make` step cannot spread a dict).

## Behaviour differences (none on the stand-in; these are by reading)

1. **A Draft function that does not exist.** `make` steps and `maker(...)` look a maker up by name and
   answer None for a missing one, so calling it raises TypeError where the handler's `Draft.x` raised
   AttributeError. Both are crashes, not refusals. Where it shows: `draft_2d_view` on a Draft with
   neither `make_shape_2d_view` nor `make_shape2dview`; `draft_dimension`, whose `try` catches
   AttributeError — the handler would have run its clean-up loop (nothing to remove) before re-raising.
   No FreeCAD 1.1 Draft lacks these.
2. **`draft_shape` kind wire / bspline / bezier**: the handler built a dict of all three makers before
   picking one; the entry looks up only the one asked for.
3. Nothing else known. Order of checks, of argument reading and of every maker call was kept; refusal
   texts are the handler's, with the handler's f-string pieces written out (`over0`, `whole`, the
   upgrade / downgrade and round-edge messages are each two literal refusals now).

## Proof here

`tests/test_datadraftmore_data.py` with `_datadraftmore_before.py`, `_datadraftmore_cases.py`, and its
own stand-in `tests/_datadraftmore_standin.py` (it installs `_datapart_standin` and adds, in the child
process only: a Draft module whose makers write down their calls, `Vector.isEqual`,
`Placement.multVec` / `inverse`, a face's `ParameterRange` / `CenterOfMass`, `OrderedVertexes`, a
curve's `TypeId`, an object's `Document`, `setActiveDocument`, `getResourceDir` with a small FCPAT.pat).

- **Identity**, 13 tools: name, description bytes, schema with key order, changes, reads, group against
  the code at `b408a91` (the snapshot is re-derived from git and compared).
- **Old handler against new entry, 290 cases** (114 answer, 173 refuse, 3 crash alike): the answer or
  refusal, every Draft call, object added or removed and property set in order, the objects left, and
  the document's Meta. **0 differ.** 36 answers and refusals are also pinned to fixed text.
- **Every `refuse` in the 13 entries is reached** by a case (UNREACHED is empty); every name an entry
  calls is in the helpers dict; every helper written in `draft_more.py` has a docstring.
- The side-by-side tests skip where git lacks `b408a91` or numpy is missing (as datadraft's do).

Not exercised here at all: Draft itself (what a maker really builds, what upgrade / join / offset really
answer), real view providers (`draft_style`'s window paths ran on a fake view object), a real FCPAT.pat.

## Live model: `docs/hardening/models/draftmesh-draft-model.json` (calls numbered from 1)

| Tool | Calls |
|---|---|
| `draft_plane` | 2, 74 |
| `draft_shape` | 3, 4, 5, 6, 8, 9, 10, 30, 46, 47, 51, 52, 53, 54, 55 |
| `draft_modify` | 7, 29, 31–45, 48, 49, 50 |
| `draft_link_array` | 11, 56, 57, 58, 59, 60 |
| `draft_dimension` | 12, 13, 14, 15, 19, 20, 21, 22, 23 |
| `draft_style` | 16, 17, 18, 81 |
| `draft_label` | 25, 26, 27 |
| `draft_clone` | 28 |
| `draft_layer` | 61, 62, 63 |
| `draft_hatch` | 64, 65 |
| `draft_from_sketch` | 68 |
| `draft_2d_view` | 70, 71, 72 |
| `draft_facebinder` | 73 |

Every converted tool has at least one live call; none is without.

## Unproven, and risks

1. **Nothing ran on FreeCAD.** The live model above is the proof still owed for all 13.
2. `draft_modify` is the largest entry and the stand-in's Draft answers by rule (a list, a list of
   lists, None, one object): what real Draft answers per op is only what the handler's comments say.
3. `draft_style` with the window up, `draft_plane` / `draft_dimension` with another tab in front: only
   on stand-in view objects and a raised AttributeError.
4. `draft_clone` and `draft_facebinder` each have one live call; `draft_from_sketch` one.
5. `docs/data-tools.md` was not edited (it does not yet say draft.py / draft_more.py are data).
6. `tests/test_files.py` fails until FILES is regenerated for the four new test files (left alone as asked).

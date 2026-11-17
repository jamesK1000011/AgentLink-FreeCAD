# Context tools: findings (patch `context.patch`, base 9f8a34d)

Date: 2026-11-16. No FreeCAD was available where this was built. All results below come from stand-in FreeCADs and
from the hub's own server run with stand-in FreeCAD modules.

## 1. State of the patch

- Applies clean to 9f8a34d (`git apply --check`). `FILES` is not in the patch.
- Full suite on the final tree (`timeout 290 python3 -m pytest -q tests`): 1,058 passed, 350 skipped (they need
  FreeCAD), 1 failed in 259 s. The one failure is `tests/test_files.py::Files::test_files_list_is_current`: the six new
  files are not in `FILES`. This was expected and `FILES` was not changed. An earlier run, before the
  new files were put in the git index and before two small last edits (the 0.15 s bound in the meter, one phrase in
  the documentation), gave 1,059 passed and no failure.
- `scripts/tool_index.py --check`, `scripts/tool_summary.py --check` and `scripts/tool_needs.py --check` pass.
- `tests/test_needs.py` also passes under Python 3.11 (the stand-in suites that need numpy are skipped where numpy is
  absent, as their own tests do).
- Removed from the earlier partial work: `agentlink/data/needs.json` (the empty word-to-state tables) and the script's
  `--report` mode. Kept and changed: `scripts/tool_needs.py` (the reader analysis) and `readers.json`.

## 2. What is proved, and by what

| Claim | Proof | Not proved |
|---|---|---|
| A reading of `false` is the call's own refusal | 556 of 1,797 stand-in cases: same code, same words | On FreeCAD |
| A reading of `true` is not refused before the first change | 585 cases; the tool's run was watched | On FreeCAD |
| A reading changes nothing | Document snapshot before and after, all 1,797 cases | That each reader helper is pure on FreeCAD. This rests on the code analysis. |
| A helper not in the list is never called | Tests with helpers that fail when called | |
| `tool_groups { needs / now / find }`, the batch line, `usage_report` | `build_server` run with stand-in FreeCAD modules and three test tools | With real families and a real window |
| Token bounds | Pinned in `tests/test_needs.py` | The complete `now` reply (bound 1,500) is measured only with FreeCAD |

Two tests (`Live`) run only where FreeCAD can be imported. They did not run here.

## 3. What to run live on the Mac (through the Agent Link MCP tools, in the background)

| # | Call | Expected |
|---|---|---|
| 1 | `tool_groups { needs: "fea_hold" }` in a new document | `applies: false`, `invalid_state`, "No strength study: fea_setup { body } first." |
| 2 | `fea_hold { faces: [...] }` | Refused with the same code and words as 1 |
| 3 | `tool_groups { needs: "pd_pad", arguments: { length: 5 } }` in a document with no body | `applies: false` with the words that `pd_pad { length: 5 }` then gives |
| 4 | `tool_groups { needs: "pd_pad" }` | `applies: null`; `notChecked` says that leading steps need the arguments |
| 5 | `pd_body_new`, then `sketch_new { plane: "XY" }` | The answer's `health` has `appliesNow`. Expect `groups: {}`, `not: 0`, `notChecked` about 50, `ms` much less than 150, no `partial` |
| 6 | A second changing call in the same state | No `appliesNow` (it is given only when it changes) |
| 7 | `tool_groups { now: true }` | `appliesNow.chosen` has `workbench` and `linked` (Sketcher with Part Design); names by class |
| 8 | `tool_groups { find: "strength hold load" }` before `fea_setup` | All hits are there; `fea_*` hits that would refuse are last and have `applies: false` |
| 9 | `fea_setup` on a body, then step 1 again | `fea_hold` is not `false` now; the line's `not` count is smaller |
| 10 | `batch` with 5 changing calls | One `appliesNow` at the top of the batch's answer; none in the calls' results |
| 11 | `usage_report { session: true }` | `appliesNow.notThenAnswered.count` is 0; `coverage` is small |
| 12 | Read `applies_meter.json` in the session's folder (`session_state` gives `outDir`) | One session with the same counts |
| 13 | `pref_set` Mod/AgentLink `AppliesNow` = false, then a changing call | No `appliesNow` line |
| 14 | Before and after steps 1, 3, 7: `history_diff` and the undo count; the selection; the active workbench | No change. No new undo step. The document is not marked changed. |
| 15 | Steps 5 and 7 on the largest document available | Record `ms` and `partial`. If `around` shows `appliesNow` near 150 ms on each call, lower `AppliesNowBudget` or set `AppliesNow` off. |
| 16 | `tool_groups { needs: "meshobj_split", arguments: { ... } }` on a large mesh | Record the time. The reading runs the tool's read-only preparation. |

Fail conditions: a `false` whose call then answers; a change in step 14; FreeCAD not responding during a reading.

## 4. Risks

1. **Purity on FreeCAD is not proved.** 878 helpers are readers by a static rule. A property read with a side effect, or
   a Python-made FreeCAD object with a method name from the reading list, would not be seen. Step 14 is the check.
2. **The pushed line is weak for Part Design and Sketcher.** All 32 tools read as not checked in the three states, because
   each starts with a finder of what an argument names. The line has value for strength, CAM/FEM/BIM availability and
   variable sets. See the design note, section 6.
3. **Cost at session start: 154 tokens more** in the lean listing (`tool_groups` 586 to 712, `usage_report` 150 to 178).
4. **Cost for each changing call:** one window-state read plus the readings, maximum 150 ms. Not measured on FreeCAD.
5. **A refused data-tool call is read one more time** for the meter (maximum 0.15 s between steps; one slow helper can
   take longer).
6. **`find` order changed** for hits that would refuse now (they go last in the shown window).
7. **The meter file is written after each call** (small, in the session's folder, not in `outputs.jsonl`).
8. **Suite time:** 4 min 25 s here, near the 290 s limit. `tests/test_needs.py` adds about 13 s.
9. **`expr.py` has one new lookup** before each method call in an expression (a dict membership test).

## 5. Not decided (owner's ruling needed)

1. `applies: true` needs a minimum of one check that was read. A tool with no leading check reads as `null`, not
   `true`. The other option is `true` for such tools.
2. `find`: a hit that applies does not go before a hit that could not be told. Only `false` hits move. The brief said
   "tools that apply now first"; the literal order would let tools with few checks go before better matches.
3. The line is given only when it changes (as `next`). The other option is on each changing call.
4. A reading with optional arguments left out (for example `pd_pad` with no body in the document). It is true for that
   call shape only, thus it was not built.
5. The pushed set leaves out tools with no workbench in the index (document, view, hub).
6. Wrapper entries (13) and their `rules` are not read.
7. `changers` end the leading part also when they write only sometimes. The reading then says how many checks come
   later.

## 6. Small things found on the way

- A sketch's `split` and `join` have the same names as a string's. The earlier method list accepted them. Fixed (design
  note, section 4).
- The earlier analysis did not see `out, i = [], 0` as new values, nor `dict.fromkeys`, `numpy.linalg`,
  `Vector.normalize` and a drawing view's `getEdgeByIndex`. Added. The reader count went from 833 to 878.
- New files for `FILES` (not added): `agentlink/appliesnow.py`, `agentlink/needs.py`, `agentlink/data/readers.json`,
  `agentlink/data/readers.schema.json`, `scripts/tool_needs.py`, `tests/test_needs.py`.

# Run 3: the six models run again after the fixes, answers read (16 Nov 2026, 22:22–22:25)

Read: all 364 rows of `out3/out/d/*.json` (srm 125 = 119 model calls + 6 helpers, srr 59, srt 67,
srf 70, wsdoc 26, wsel 17) against run 2's rows in `out2/all-answers.json`, position by position
(every position holds the same tool in both runs), and against each model's `expect`. Numbers in
"srm 106" form are positions in the run file (what the batch's `calls.N` names); "model 101" is
the index in the model's own list. Nothing was run here: no FreeCAD, no network.

Counts: of the 29 tools to run again, **27 proven, 1 not proven (mesh_reduce), 1 proven with a
limit said (scan_open: forward only)**. Fixes: A2, A3 (the numbers; the time only bounded), A5 to
A12, pass 4 §1 to §3 and the hub's three proven; A1 proven forward only; A4 only its warning; A13
and pass 4 §4 and §5 not exercised. 7 calls flipped ok/refused: 5 the merge artifact, 2 by a fix.
**No regression in any value.** Three things are worse in time only (section 3).

What this run could not show, because the calls added to the models since run 2 were not run
(measure 119–143, Mesh Tools 64–69, reverse 57–68): the return trip of the per-document state, the
`kept.packedAgain 0` reading after a rename, the read-back after undoing `reverse_feature_clear`,
the camera key, and the five tools that have only ever refused.

---

## 1. The 29 tools and the fixes, one by one

### ScanRuler — credit: these are Stefan Hermann's (CNC Kitchen) ScanRuler features in FreeCAD

| Tool / fix | Verdict | What tonight's answer shows (run 2 in brackets) |
|---|---|---|
| **A1 state per document** (`scan_open`, `flat_edges`) | **PROVEN forward; the way back NOT EXERCISED** | With the measure document still open (it is in srr 51's `open` list, WornScan and 9 elements in it): srf 1 `flat_edges` in a new document refused "Nothing is on the 2D sheet" [answered the measure document's 140 mm chain]; `scan_open { object }` with no discard accepted in three documents (srm 8, srt 7, srf 6). The first save of each other document: srr 5 **7,296 bytes** [6,017,729], srt 8 **13,524** [3,894,568], srf 7 **16,151** [3,255,984]; srr 50 21,755 [6,031,462]. srr 52 `doc_open` 7 objects [10], srr 54 the body is labelled "Block" [Block001], `recompute` 7 [10]. Not run: `scan_info` in the new document (scan: null), `doc_switch` back and `scan_info` there (model 123–137). Run 2's file has srt 7 accepted too, so that row alone proves nothing; the sizes and srf 1 do. |
| `flat_edges` | PROVEN | Refused on an empty sheet (srf 1); on the section after densifying, srf 13, 32, 47: 2 chains, 140.0 mm (97 points) and 31.4057 mm (143 points), the same as run 2. |
| **A2** `scan_scale`, `align_clear` | PROVEN | srm 104 dry run factor 1.000121 from BoreDia 11.9985 → 12; srm 105 `factor 2`: box −60…60, −40…40, −20…20; srm 106 `factor 0.5`: box **−30…30, −20…20, −10…10**, centre [0, 0, 0] [0…60, 0…40, 0…20: the alignment lost]; srm 107 `align_clear` **accepted**, appliedAlignment null [refused "in scan coordinates already"]. srm 100/101: cleared, then refused when there is none, as before. Not read: the box after 107 (no `scan_info` follows it; `align_clear` does not answer the box). |
| **A3** `thickness_measure` | PROVEN (numbers); time bounded, not measured | srm 75, asked maxThickness 25, maxPoints 20,000: measured 16,647 of 20,000, min 10.0, max 24.848, mean 18.8972, rms 19.0268, sigma 2.2177, belowLimit 0 at 1 mm, thinSpots 0 — the figures run 2's job note gave (10.0 / 24.848 / 18.897 / 16,647), and its own reply is kept now (stats, settings, sampled, report). **No time field**: a heavy read's answer carries `job`, no `ms`, and no `around`. The bound: srm-a ran its 119 calls in 57 s; the 93 answers that carry `ms` sum to 36.1 s (9 more were refused); so the 17 heavy reads together (this one, 2 scan_qa, 4 heightmaps, 2 section_fit, scan_segment, 7 deviation reads) and everything outside took at most 21 s. Run 2: 221 s for this call alone. "About a second" is not shown. |
| **A3** `scan_qa` | PROVEN (numbers), time as above | srm 11 (sparse): p5 14.048, p50 20.048, faces 3.945° off, note to densify — identical to run 2. srm 18 (dense): spacing 0.292, p5 19.0, p50 20.0, p95 20.0, tilt 0 — identical. |
| **A3** `scan_heightmap` | PROVEN (numbers), time as above | srm 69, 70, 71, 84: every value identical to run 2 (hit 92 / 568 / 2,288, min 19.0, max 20.0; deviation map min −1.0, max 0.0); only the job ids differ. |
| **A4** `mesh_reduce` | **NOT PROVEN — the cap is still not kept, and the mesh still does not hold** | srt 41, asked tolerance 0.05, maxTriangles 2,000, input 10,022: **triangles 2,142** [2,136] with `capped: true` — over the cap; **max 10.4245 mm**, p999 9.5736, rms 2.4748 [14.2655 / 13.8482 / 5.3278]; within 1,950 of 4,000 [1,057]; backMax 0.0099 [3.7584]; `held: false`; `tries: 1`; `warning` present: "Brought down to the cap of 2000 triangles, this lies up to 10.4245 mm from the original (tolerance 0.05 mm): not a mesh to measure or model on…". Proven: it says so (warning, held false), which run 2 did not. Not proven: (a) the cap — the handler asks again lower up to three times and still came back with 2,142, and the warning's "brought down to the cap of 2000" is then untrue; (b) the search for the lightest mesh that holds — with a cap the first try fails and the search ends at `tries: 1`, so it never ran (a call without maxTriangles, or with a cap the part can meet, would run it); (c) the time (a job: no `ms`). One thing to read from the pair of figures: the reduced mesh lies on the original (back 0.0099 mm) but the original is up to 10.4 mm from it — a piece of the part is gone and the hole closed over (volume below). |
| **A4** `mesh_apply_reduced` | PROVEN (it applies and warns); the "held" case NOT EXERCISED | srt 44: mesh.triangles 2,142 = reduced.triangles, working "edited copy", **open 0, bad 0**, volume **16,769.173** [8,829.648; the mesh before was 22,429.4], bounds 0…40, 0…30 [−3.76…42.84], and the new `warning`: "The reduction applied does not hold its tolerance: up to 10.4245 mm from the mesh it was made of (tolerance 0.05 mm). mesh_undo puts that mesh back." A decimated closed mesh stayed closed in this one case. |
| **A5** `manual_check` | PROVEN | srm 120: step 2 Worn `overlapsInPlace: true`, "The way in was not swept", no `blockedShortBy` [blockedShortBy 19.25]; step 1 Block clear; blocked 1. |
| **A6** `align_symmetry` | PROVEN | srm 103: `symmetry { rms 0.0, matchedShare 0.992, from "Mirror" }` and the note "Not a mirror of the whole part: 0.8 % of the samples have no mirror image about this plane…" [neither]; moved 10 mm in z as before. |
| **A7** reverse bodies' boxes — `reverse_feature_add`, `_update`, `_suppress`, `_rollback`, `_move`, `_remove`, `reverse_parameter_add`, `_set`, `_rename`, `reverse_import_step`, `reverse_build`, `reverse_body_names`, `reverse_body_describe`, `reverse_body_set` | PROVEN (14 tools) | All 48 boxes in tonight's srr answers are exact: Block [0,0,0]–[40,30,20] in every row, also with the bore and with the fillet [z −0.0365…20.0365; x −0.0189…40.0189]; height 10 gives z 0…10 (srr 12); Peg [50,0,0]–[60,10,10], after the move [35,0,0]–[45,10,10]; gauge [0,50,0]–[8,58,8]; Ring [−15,−15,10]–[15,15,15] [x ±15.109, z 9.891…15.109]. Each of the 14 tools has at least one accepted answer with boxes. Volumes unchanged and rounded (22274.690351, 23845.486678, 1000.0, 512.0, 1963.495408). The exact box did not cost time: the model's 59 answers sum to 3.6 s [7.2 s]. |
| **A8** `reverse_body_check` | PROVEN | srr 35 `{ body: "Dowel" }` → name "Peg", **shownAs "Dowel"**, closed, valid, volume 1000.0. |
| **A9** `wear_prewarp` | PROVEN | srm 91: rms 0.0, largest 0.0, **seenFromPrint { largest 1.0, rms 0.059 }**, **stop false**, why "the target's vertices do not show the print's error (see warning)", warning naming 1 mm and the target's 324 vertices [stop true, "within 0.05 mm RMS"]. |
| A13 `align_datum { primary: "Top" }` | NOT EXERCISED | No such call in the list. |
| **Pass 4 §1 state packing** (`scan_info.kept`) | PROVEN by the calls' own times; `packedAgain 0` NOT EXERCISED | On the dense scan (219,600 triangles): `dimension_remove` srm 41 **15 ms** [1,573], `element_rename` srm 44 **19 ms** [1,500], `element_set_visible` srm 47 **22 ms** [3,947], `dimension_set_limit` 19 [1,517], `section_cut` 23 [1,578]; the model's `ms` sum 36 s [144 s]. `scan_info.kept`: srm 10 `{ bytes 3049, ms 2, arrays 3, packedAgain 3 }` (after scan_open); srm 97 `{ bytes 4265404, ms 32, arrays 812, packedAgain 9 }` (after align_datum: 9 of 812 arrays packed again, 32 ms). The designed reading — `scan_info`, `element_rename`, `scan_info` with packedAgain 0 (model 119–122) — was not run. The 2D model's flat 307–309 ms a call is gone (its `ms` sum 3.1 s [11.2 s]), as pass 4 said it would be with A1. |
| **Pass 4 §2** `section_fit`, `section_to_sketch` scatter | PROVEN | srm 56: chain 0 **scatter 0.0, scatterFloor 0.0469**, spacing 0.9375, tolerance 0.5625 [scatter 0.0469]; chain 1 scatter 0.0035, scatterFloor 0.0065 [0.0065]. srm 61 `section_to_sketch` the same pair. One loose end at srm 58 (section "Half"): both chains answer `scatterFloor 0.0` beside `scatter 0.0` — shown although the scatter is not under it — with `spacing 0.0` and `tolerance 0.0` on chains of 303 and 464 points; spacing 0 was there in run 2 too and is not explained (the lines and their ends are right). |
| Pass 4 §4 undo after `reverse_feature_clear` | NOT EXERCISED | srr 58 `history_undo` answers as in run 2 (steps ["Reverse: clear"], bodies ["Reverse engineer", "Gauge"]); the read-back calls (model 57–64) were not run. |
| Pass 4 §5 the camera key; `scan_noise`, `scan_snapshot_latest`, `mesh_apply_wrap`, `reverse_parameter_remove`, `reverse_build_stop` | NOT EXERCISED | Each still only refused (srm 12, srm 123, srt 64, srr 15, srr 47), as these call lists mean; srm 122 lists no shot. |

### Workshop

| Tool / fix | Verdict | What tonight's answer shows |
|---|---|---|
| **A12 / pass 4 §3** `drawing_make` page.settled | PROVEN | wsdoc 4 (2:1 on A3): `page.settled { cleared: [Template, Dimension, Dimension001, Dimension002], waited 0.95 }`; wsdoc 6 (the section drawing): `cleared: [Template001, Dimension003 … Dimension007]` — the six names run 2's next call read as "not recomputed yet" — `waited 1.49`; no `late`, no `left` in either. wsdoc 7, the check: health **"nothing red"**, no needRecompute ["6 objects not recomputed yet"]. This also settles pass 4's open point 2: **FreeCAD 1.1.3 does mark the dimensions at 2:1**, as 1.1.0's source reads. The rest of both answers reads as in run 2 (four views, 53 / 26 / 26, section B-B at 13.0 with cutFaces 1, the two ⌀2 callouts, filesFrom "TechDraw page" three times). The price is in section 3: 4.6 s and 5.7 s a call [0.8 s]. |
| **A10** `patent_figures` numerals | PROVEN | wsdoc 15 `{ bodies: ["Body"], numerals: { Body: 0 } }` → invalid_input "numerals.Body: a whole number over 0." [not_found "Body is not among the bodies drawn — Tut"]. |
| **A11** `patent_figures` filesFrom | PROVEN | wsdoc 12: both figures `filesFrom { svg: "TechDraw page", pdf: "TechDraw page" }` [Workshop's sheet writer, four times]; numerals { Tut: 10 }; health "nothing red" [none]; no `settled` row on a figure (none expected); the next changing call (wsdoc 18 `part_primitive`) reads no needRecompute. wsdoc 13 (`page: false`) still from the sheet writer, as meant. Not in the answer, so not read: the template's name and that it is one undo step. 6.6 s [1.2 s]. |

### Hub fixes these lists happen to exercise (hubfix2 §2, §3, §4)

- **The empty undo step** — PROVEN: wsdoc 25 `history_undo` → steps ["part_primitive"], undoCount 3,
  13 bodies (the Base plate gone) [steps ["drawing_exploded"], 14 bodies, nothing gone].
- **A changing call with no health** — PROVEN: wsdoc 6 carries health [none]; so do 41 ScanRuler
  rows that had none (srm 22–48 and 96–106: 31; srr 9–46: 10), each "nothing red".
- **doc_close listing a document twice** — PROVEN: srr 51 `open` lists seven documents, none twice
  [ScanMeasureModel twice].
- The helper `session_state` with `to:` (wsdoc 1) now answers `written { path, bytes 2101 }, keys`
  [null].

---

## 2. Every call that flipped or changed in value

Flips (7):

| Call | Run 2 → run 3 | Class |
|---|---|---|
| srm 62 `pd_pad` | ok → refused not_found "$at 'body': no key 'body' … of call 0's answer (doc_new)" | artifact (merged chunks; `$from 0` should be 61) |
| srr 38 `reverse_body_clearance` | ok → refused, "$at 'added.0.bodies.0' … call 0's answer (doc_new)" | artifact (`$from` should be 37) |
| srf 33 `flat_curvature`, srf 35 `flat_profile`, srf 48 `flat_curvature` | ok → refused, "$at 'chains.1.chain' … call 0's answer (doc_new)" | artifact (`$from` should be 32, 32, 47: the `flat_edges` helpers, which answered chains.1.chain = 1 as before) |
| srf 1 `flat_edges` | ok → refused invalid_state | expected by a fix (A1) |
| srm 107 `align_clear` | refused → ok | expected by a fix (A2) |

Five calls therefore have no answer tonight: pd_pad's 11,434.65 mm³, the 480.69 mm³ overlap, the
bore's curvature (twice) and profile. Their tools were marked in run 2 and nothing touched them,
but tonight says nothing about them. Nothing later in the lists depends on them.

Values changed, same ok (timings and job ids left out):

| Calls | What changed | Class |
|---|---|---|
| srm 56, 61 (58: a key added) | scatter measured, scatterFloor beside it | fix (pass 4 §2) |
| srm 75 | the reply itself in place of the runner's note of a job | fix (A3: it ends inside the batch) |
| srm 91 | seenFromPrint, warning, stop true → false | fix (A9) |
| srm 103 | symmetry { }, the longer note | fix (A6) |
| srm 106 | box 0…60 → −30…30 (aligned) | fix (A2) |
| srm 120 | blockedShortBy 19.25 → overlapsInPlace | fix (A5) |
| srm 10, 97 | `kept { }` added | fix (pass 4 §1) |
| srr: 26 answers | boxes exact (48 boxes) | fix (A7) |
| srr 35 | shownAs "Dowel" | fix (A8) |
| srr 5, 30, 50; srt 8, 32, 52; srf 7, 31, 51, 63 | `doc_save` bytes: 6.0 MB → 7–22 kB (srr); 3.9 / 3.0 / 3.3 MB → 14 / 535 / 861 kB (srt); 3.3 / 3.1 / 3.2 / 3.2 MB → 16 / 693 / 693 / 702 kB (srf) | fix (A1) |
| srr 48, 53 recomputed 10 → 7; srr 52 objects 10 → 7; srr 54 label Block001 → Block | the leaked scan objects are no longer in the document | fix (A1) |
| srt 41, 42, 44, 49 (and 43, 46, 48: triangle count, STL 107,184 bytes) | mesh_reduce's mesh: 2,142 triangles, max 10.42 mm, volume 16,769; tries, warning | fix (A4) — changed, still wrong: section 1 |
| wsdoc 4, 6 | page.settled; wsdoc 6 health | fix (pass 4 §3; hub §3) |
| wsdoc 7 | health "nothing red" | fix (A12) |
| wsdoc 12, 15 | filesFrom; the refusal's code and words | fix (A11, A10) |
| wsdoc 25 | undoes part_primitive | fix (hub §2) |
| srr 51 | `open` without a duplicate | fix (hub §4) |
| 41 ScanRuler rows, wsdoc 12 | `health { ok: true, verdict: "nothing red" }` added | fix (hub §3) |
| srm 64 `element_to_document` | `health.next` gone (the verdict stays) | hub: a hint is given only when it is news — not a fault |
| wsdoc 1 | helper answer written to its file | hub fix |
| srm 17, 42, 63, 87, 108 | `doc_save` 4–10 kB smaller (4,808,833 for 4,812,738 …) | follows from the new state format; pass 4 expected the state file larger, the saved document is not |
| srm 0–9, 17…; srr 0, 39, 51; srt 1–6; srf 2–5; wsdoc 3, 4…; wsel 1… | document name ScanMeasureModel [ScanMeasureModel1], `previous`, the `open` list, step counters from 2 [from 52], wsdoc 3 no `queue` (no heavy job was running) and "workbench MeshWorkbench" | the session, not the tools |

**Regressions: none found.** Every other value in the 364 rows equals run 2's (compared to 1e-9
relative). wsel has no changed value at all. What is worse is time, on four tools (section 3), and
`mesh_reduce` is still wrong after its fix — an unproven fix, not a regression.

---

## 3. The `around` rows

A row is there only when the time outside the answer's `ms`, or the hub's parts inside it, reach
500 ms (`agentlink/around.py`): 36 rows (srm 4, srr 12, srt 4, srf 1, wsdoc 10, wsel 5). srm-b's six calls and every heavy read have none.

**Over 2 s wall (5 rows):**

| Call | wall | Where it went |
|---|---|---|
| srm 106 `scan_scale { factor: 0.5 }` | 8,223 ms | tool 4,949; **inside.afterChange 2,811**; health 5 + 5; outside 452 (echoBefore 231, echoAfter 177 with fit 18, record 26) |
| wsdoc 4 `drawing_make` | 7,398 | tool 4,377; outside 2,749 (echoBefore 1,829, other 876); inside healthMark 181, snapshot 52, health 39 |
| wsdoc 12 `patent_figures` | 7,291 | tool 6,486; outside 719 |
| wsdoc 6 `drawing_make` (section) | 6,499 | tool 5,552; outside 792 (echoBefore 523) |
| srt 46 `mesh_export` | 3,170 | tool 43; outside 3,119: echoBefore 1,232, echoAfter 1,872 of which the view fit 1,834 |

The other 31 rows are 0.5–1.7 s and almost all echo: echoBefore up to 0.72 s (about 0.5 s on a
model's first changing calls: the full-pace pause), echoAfter up to 0.79 s; two have a view fit
(srm 107: 751, srr 57: 471). The hub's own parts are small everywhere else: the largest are the
health check on wsel 5 and 11 (283 and 202 ms) and healthMark 181 ms on wsdoc 4. Two refused `mesh_boolean` calls (srt 20, 21) spent 1,565 and 976 ms in
"other": a refusal has no `ms`, so the tool's own work before it refused lands there.

**Over 2 s by the answer's own `ms`, with no row (so neither the hub's parts nor the echo reached
500 ms: the tool itself):** srm 102 `align_auto` 7,663 [9,500]; srm 105 `scan_scale { factor: 2 }`
4,368 [6,253]; srm 108 `doc_save` 2,740 [502]; srm 118 `pack_write` 2,443 [486]; srt 19
`mesh_boolean` 2,447 [669]; wsdoc 0 `doc_open` 2,234 [474].

**The "3.5–3.9 s on four trivial calls" (run 2: srm 24, 30, 34, 47).** Not proven, but the one
measurement there is points the way pass 4 guessed:

- Those four positions took 31, 411, 19 and 22 ms tonight. No call in this run shows the 2.4 s
  step.
- A smaller step is there at nearly the same places: srm 23 `element_fit` 494 ms, 30
  `element_construct` 411, 33 `dimension_add` 485, 45 `element_unlink` 487, beside neighbours of
  15–46 ms. That is +0.4–0.47 s, and a `doc_save` of that document took 467–508 ms tonight
  (srm 17, 42, 63, 87). In run 2 the step was +2.4 s and a `doc_save` took 2.4 s. The step is the
  size of one save in both runs.
- None of those four rows is itemised: their inside parts stayed under the 500 ms floor, so no
  `around`, and `afterChange` cannot be read off them.
- The one itemised reading: srm 106, **afterChange 2,811 ms**, and the `doc_save` two calls later
  (srm 108) took 2,740 ms. So the add-ons' after-change hook does carry a save-sized cost when it
  fires; which add-on's handler it is, the row does not say.

To settle it: the same list once with the floor lower (or `profile: true` on srm 23, 30, 33, 45),
so that `afterChange` shows on a 0.45 s step.

**New in time, not explained by `around`:**

- `drawing_make` 4,649 and 5,707 ms [784, 839]; `patent_figures` 6,572 ms [1,229]. The answer
  accounts for part: `settled.waited` 0.95 and 1.49 s, `viewsReadyIn` 1.15 and 1.03 s [0.20,
  0.24]. About 2 s (wsdoc 4) and 2.6 s (wsdoc 6) of the tool's time, and all 5.3 s more in
  `patent_figures` (which answers no `settled`, so no `waited`), are not accounted for by any
  field. The fix works; its cost is 4–5 s a drawing.
- After the two `scan_scale` calls, saving costs 2.7 s (srm 108) where it cost 0.5 s before them
  (srm 87) and `pack_write` 2.4 s [0.5]; in run 2 it was the other way round (2.4–2.6 s before,
  0.5 s after). Not explained.
- `scan_scale` itself 4.4–4.9 s and `align_auto` 7.7 s on 219,600 triangles: the tool, both runs.

---

## 5. Merged models: the placeholders

`merge_chunks.py` (beside this file) merges chunk files and adds each chunk's offset to the
`$from` indices inside it. How the hub reads a reference (`agentlink/chain.py` `_from_call`,
`agentlink/tools.py` batch): `$from` is the call's index in the **whole list the batch was
given**, counted from 0; a `from: k` continuation keeps those indices (`first + i`) and refuses a
`$from` below `k` (invalid_state: "its answer is not kept between parts — give that call to:
"file.json" and read it with $file"). References are resolved only inside `arguments`. So a chunk
written to run alone counts from its own start, and merged it needs +offset; tonight's five
refusals are exactly that. The self-test passes with the script's own follower and with the hub's
`chain.resolve` (`--self-test --chain agentlink/chain.py`), including the unshifted case reading
call 0 and the refusal across a `from:` part.

Placeholders, with the index in each model file as it stands (a merge shifts them):

`asmtd-techdraw-model.json`

| Call | Placeholder | Reference | Key checked against |
|---|---|---|---|
| 12 `td_title` | `fields: { "<the title field's name from the call above>": … }` | **None possible**: the placeholder is an object's key, and a reference stands only where a value goes. Write the name itself: `"title"` (td_title matches names without case). | Unverified for this template. `title` is the field Workshop's drawing_make filled live on A3_Landscape_ISO5457_advanced.svg (wsdoc 4 `page.titleBlock`); which template td_page picks for A4 on the Mac, and its field names, is in no answer I have. Call 11's answer lists them (`fields`). |
| 35 `td_tolerance` | `dimension` | `{ "$from": 34, "$at": "dimension" }` | Source only (`dim_reading`: `dimension` is the object's name; td_tolerance takes name or label). No live td_dim answer here. |
| 50 `td_hatch` | `faces: ["<the top face's name>"]` | `[ { "$from": 49, "$at": "items.0.ref" } ]` | Live: `patches/out/core-1.json` call 18, `shape_query { kind: "face", normal: [0,0,1] }` → `items[0].ref` "Face6". |
| 51 `td_area` | `face: "Plate.<the same face name>"` | **None possible as written**: the value is "Plate." joined to the face name and a reference replaces a whole value. Either td_area learns to take `{ body, face }` (a hub change), or the literal stays and is checked against call 49. | — |
| 55 `td_dim_format` | `dims: ["<the first 6 mm diameter dimension>"]` | `[ { "$from": 31, "$at": "dimension" } ]` | Source only (as 35; `dims_of` takes name or label). |
| 56 `td_dim_align` | `dims: ["<first of td_dimset>", "<the second>"]` | `[ { "$from": 36, "$at": "dimensions.0.dimension" }, { "$from": 36, "$at": "dimensions.1.dimension" } ]` | Source only (td_dimset answers `dimensions`: each td_dim's reading plus `lane`). |
| 57 `td_dim_repair` | `dimension: "<the radius dimension's name>"` | `{ "$from": 33, "$at": "dimension" }` | Source only. |

`bimcam-bim-model.json`

| Call | Placeholder | Reference | Key checked against |
|---|---|---|---|
| 67 `ifc_remove` | `ids: ["<the id ifc_find gave for the Plinth: ifc_find { name: "Plinth" } first>"]` | The model has no such call (62 finds IfcWall). Put `{ "tool": "ifc_find", "arguments": { "name": "Plinth" } }` in as call 67; then `ifc_remove` (now 68) takes `ids: [ { "$from": 67, "$at": "elements.0.id" } ]` and `bim_import` becomes 69. | Live: `patches/out/bim-3r.json` call 2, `ifc_find` → `elements[].id` ("3WgCQZ6fr1x8SuoWievJSI", 22 characters); the same file's call 7 shows the placeholder sent as it is and refused not_found. Not live: that `name: "Plinth"` finds one element (call 28 made it an IfcFooting; the name stays). |

Two cautions for all of them. These lists are 66 and 69 calls: answered in parts, a reference
that reaches into an earlier part is refused (31 → 55 is 24 calls back). Where that can happen
give the source call `to: "x.json"` and read `{ "$file": "x.json", "$at": … }` — at the cost that
the source call's row then holds `written` and `keys` instead of its answer. And the five TechDraw
references rest on reading the code, not on an answer: the first live run of calls 31–36 should be
read for `dimension` and `dimensions[].dimension` before the rest is trusted.

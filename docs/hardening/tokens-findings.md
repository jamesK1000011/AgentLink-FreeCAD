# tokens: findings (17 Nov 2026)

Branch `tokens`, on origin/main 35df6eb. A token-efficiency pass on the hub, aimed at answers that are not
needed. Measured first on the live answers of every family's test model (FreeCAD 1.1.3 on the Mac: 105 answer
files, each `{ results: [ { tool, ok, result | error } ] }`), then cut only what no later call needs. No tool
description was shortened and no tool was cut. Nothing here was run in FreeCAD: the cuts are plain Python, tested
on stand-ins in `tests/test_once.py`, and replayed over the answer files.

## Measured (before)

The seven-day usage report beside it: 13,386 calls, about 4.24 M tokens (1.24 M pictures); top by tokens batch
895k (largest reply 35,460 characters), window_snapshot 697k (pictures), gui_input 554k (pictures 515k),
app_recover 170k, tool_groups 151k, part_primitive 88k, session_state 66k, menu_list 57k, setup 44k,
guide_read 44k, sketch_add 40k, cmd_list 34k.

Answer files: 105; calls: 4095; reply text 1,538,429 characters (~439,551 tokens at 3.5 characters a token). Sizes are compact JSON of each call's result or error as the batch file holds it.

### Top 40 tools by total reply size (before)

| tool | calls | mean | max | total chars | est. tokens | after (each file a conversation) | after (one conversation) |
|---|---:|---:|---:|---:|---:|---:|---:|
| part_primitive | 236 | 424 | 673 | 100,066 | 28,590 | 89,366 | 87,075 |
| sketch_add | 81 | 706 | 1193 | 57,153 | 16,329 | 52,498 | 50,503 |
| guide_read | 11 | 5141 | 14170 | 56,549 | 16,157 | 48,427 | 48,427 |
| window_snapshot | 482 | 109 | 155 | 52,750 | 15,071 | 52,750 | 52,750 |
| tool_groups | 17 | 2806 | 10438 | 47,709 | 13,631 | 47,709 | 47,709 |
| app_recover | 3 | 12757 | 38058 | 38,270 | 10,934 | 38,270 | 38,270 |
| sketch_new | 74 | 388 | 442 | 28,732 | 8,209 | 25,182 | 23,549 |
| part_boolean | 60 | 408 | 592 | 24,489 | 6,997 | 20,049 | 20,049 |
| part_transform | 44 | 447 | 588 | 19,666 | 5,619 | 16,215 | 15,858 |
| menu_list | 4 | 4856 | 9543 | 19,426 | 5,550 | 19,426 | 19,426 |
| report_get | 4 | 4664 | 6254 | 18,658 | 5,331 | 18,658 | 18,658 |
| usage_report | 8 | 2206 | 2727 | 17,648 | 5,042 | 17,648 | 17,648 |
| pd_body_new | 75 | 213 | 350 | 16,004 | 4,573 | 16,004 | 16,004 |
| pref_get | 7 | 2217 | 7323 | 15,516 | 4,433 | 15,516 | 15,516 |
| reverse_body_describe | 4 | 3392 | 3762 | 13,570 | 3,877 | 13,570 | 13,570 |
| doc_new | 63 | 213 | 240 | 13,394 | 3,827 | 12,958 | 6,636 |
| part_wire | 41 | 323 | 368 | 13,260 | 3,789 | 10,124 | 8,780 |
| sketch_constrain | 26 | 509 | 949 | 13,237 | 3,782 | 12,857 | 12,667 |
| td_list | 9 | 1426 | 2640 | 12,836 | 3,667 | 12,836 | 12,836 |
| fea_solve | 21 | 607 | 1085 | 12,755 | 3,644 | 12,755 | 12,755 |
| sketch_state | 6 | 1996 | 3958 | 11,975 | 3,421 | 11,975 | 11,880 |
| scan_segment | 2 | 5900 | 5900 | 11,800 | 3,371 | 11,800 | 11,800 |
| td_page | 12 | 959 | 1135 | 11,507 | 3,288 | 10,611 | 10,135 |
| pd_pad | 28 | 391 | 447 | 10,955 | 3,130 | 10,955 | 10,955 |
| flat_dimension_add | 6 | 1810 | 2499 | 10,863 | 3,104 | 10,863 | 10,863 |
| sketch_edit | 20 | 525 | 875 | 10,496 | 2,999 | 10,496 | 10,496 |
| pd_primitive | 30 | 322 | 436 | 9,669 | 2,763 | 9,669 | 9,669 |
| sheet_table | 12 | 784 | 896 | 9,404 | 2,687 | 9,404 | 9,404 |
| feature_list | 9 | 1007 | 1506 | 9,066 | 2,590 | 9,066 | 9,066 |
| object_list | 9 | 989 | 2368 | 8,899 | 2,543 | 8,899 | 8,899 |
| draft_shape | 64 | 128 | 191 | 8,173 | 2,335 | 8,173 | 8,173 |
| element_list | 2 | 4013 | 4013 | 8,026 | 2,293 | 8,026 | 8,026 |
| session_state | 10 | 776 | 1870 | 7,762 | 2,218 | 7,426 | 7,090 |
| tutor | 23 | 334 | 466 | 7,685 | 2,196 | 7,685 | 7,685 |
| element_fit | 12 | 624 | 671 | 7,482 | 2,138 | 7,482 | 7,482 |
| fea_results | 12 | 620 | 1004 | 7,440 | 2,126 | 7,440 | 7,440 |
| bim_schedule | 4 | 1830 | 1871 | 7,322 | 2,092 | 7,322 | 7,322 |
| drawing_make | 7 | 956 | 2841 | 6,695 | 1,913 | 6,695 | 6,695 |
| doc_save | 31 | 212 | 400 | 6,566 | 1,876 | 6,566 | 6,566 |
| reverse_feature_add | 16 | 407 | 930 | 6,510 | 1,860 | 6,510 | 6,510 |

### Top 30 keys by total share (before; key = path of keys, [] = list items; error.* = refusals)

| key | times | total chars | share |
|---|---:|---:|---:|
| `health` | 1903 | 255,172 | 16.6 % |
| `health.verdict` | 1903 | 99,956 | 6.5 % |
| `error.message` | 651 | 97,581 | 6.3 % |
| `health.next` | 502 | 70,589 | 4.6 % |
| `note` | 540 | 66,634 | 4.3 % |
| `path` | 587 | 39,599 | 2.6 % |
| `documents` | 1 | 37,906 | 2.5 % |
| `health.todo` | 304 | 37,256 | 2.4 % |
| `text` | 38 | 35,270 | 2.3 % |
| `state` | 130 | 30,693 | 2.0 % |
| `documents[].copies` | 102 | 30,320 | 2.0 % |
| `guides` | 2 | 27,746 | 1.8 % |
| `ms` | 3363 | 24,786 | 1.6 % |
| `tools` | 26 | 23,511 | 1.5 % |
| `bodies` | 138 | 23,041 | 1.5 % |
| `items` | 24 | 22,709 | 1.5 % |
| `report` | 34 | 21,562 | 1.4 % |
| `groups` | 10 | 21,459 | 1.4 % |
| `box` | 930 | 21,396 | 1.4 % |
| `placement` | 281 | 19,335 | 1.3 % |
| `documents[].copies[].path` | 217 | 18,086 | 1.2 % |
| `mesh` | 193 | 17,698 | 1.2 % |
| `health.ok` | 1903 | 17,206 | 1.1 % |
| `objects` | 80 | 15,239 | 1.0 % |
| `values` | 5 | 14,910 | 1.0 % |
| `groups[].about` | 126 | 14,782 | 1.0 % |
| `step` | 1593 | 14,347 | 0.9 % |
| `next` | 169 | 13,468 | 0.9 % |
| `elements` | 40 | 13,292 | 0.9 % |
| `error.code` | 651 | 13,167 | 0.9 % |

### Replay through the changed pure functions

- Per-call answers (once.thin_reply, guide index): 1,538,429 -> 1,482,189 characters with each answer file taken as its own conversation (3.7 % less, ~16,069 tokens); 1,538,429 -> 1,450,317 with all 105 files as one conversation (5.7 % less, ~25,175 tokens).
- The same 105 runs as plain `batch { file }` replies (every answer in the reply, as before): 1,826,666 characters -> 422,177 with the record reply now the default (a line per call; 76.9 % less), 254,129 with lines: "refused". The batch note (303 characters) is counted on every reply here; it is said once a conversation.

The replay cannot load tools.py (it needs FreeCAD), so tool_groups' notes (registered there) are not thinned in it:
the per-call figures are low by about 1,100 characters. "Each file a conversation" is the floor; the models were
run several to a conversation, so the real figure lies between the two.

Repeated words, largest first (same text, same tool): health.todo's overlap advice 215 times (28,810 characters);
doc_new's note 63 times (7,623); sketch_new's coordinates note 74 times (6,142); a sketch reading's DoF note
70 times (6,955, the count already in dof); part_wire's use 41 times (5,084); "N objects still failing from before
this call: …" 56 times (3,640); "recompute lists them with FreeCAD's reasons" 72 times (2,580); pd_tip's and
pd_datum's use, draft_link_array's, material_set's, cam_post's, pref_set's, surface_*'s and fea_*'s notes 4 to 12
times each. The guide index repeated each guide's section names (sections beside sectionTokens' keys) and each
later section's cost (later[].tokens beside sectionTokens): 8,122 of its 28,340 characters.

## Decided, part by part

| part | needed later? | done |
|---|---|---|
| A data tool's literal note / use / next (written in its tools.json entry, not an expression or fmt) | Once: it carries no fact of the call | Said the first time in a conversation; after that the key is left out and named in `saidBefore` (so the answer still says it applies). `tool_groups { tool }` gives the words again (`said`). A new conversation (initialize) says everything again. |
| health.todo: the overlap advice, "recompute lists them …" | Once | The same, named in `health.saidBefore` (`overlap`, `failing`). Every other todo stays (a red reading's what-to-do). |
| health.verdict: "N objects still failing from before this call: …" | Only when it changes | Left out while it is what was last said (batch { to } already did this inside one reply); `as before` when nothing else; given again when it changes or after a reading without it. |
| A sketch reading's note "N degrees of freedom: it pads as drawn …" | The count, every time (it is dof) | The sentence once; the count stays as dof. |
| session_state.machine | Once (the machine does not change) | Said once, then `saidBefore`. |
| batch { to } reply's note / toNote / healthNote | Once | Said once; a batch's own note (where it stopped, how to go on) is never touched. |
| A plain `batch { file }` reply (every call's whole answer, 10-35k characters) | Rarely; and it is in the record | Now answers from its record, as batch { to } does: a line per call (ok, refusal words, health verdict), the record's path as written. `lines: "full"` gives the whole answer here; `batch { read, at }` reads any part of a record or to file back. A batch of calls answers whole as before. |
| guide index sections / later[].tokens | No: the same names and costs are in sectionTokens | Left out; the description says sectionTokens' keys are the sections in order. |
| Refusals' lists (objects, groups, menu items) | Yes: they are the what-to-do-next | Left. picks.find already stops at 30 names. |
| ms, step, health.ok/verdict/next, a body's volume/area/faces/box | Yes (ms is read for slow documents; next is already news-only) | Left. |
| session_state bodies | Yes: it is the document's state | Left (mean 776 characters). |
| menu_list (no menu: 400 items), cmd_list, tool_groups' overview | Asked for | Left: each already has menu / query / limit / find. |

Why a file batch now answers from its record by default: a file batch exists to keep a long run out of the
conversation (the description says so), its record already holds every answer whole, and the agents forget
lines. A batch of calls is usually short and read at once, so it answers whole as before. What could be lost is
not: every answer is in the record, and `batch { read: <written>, at: "results.<i>.result" }` gives it back
through the hub (no file tool needed). A script that relied on a plain file batch's whole reply must add
`lines: "full"` (none in this repo or the add-ons does: livescript and the Workshop tests send calls).

The hub's batch inputSchema already listed `to`, `lines`, `from` and `build`: the client's copy seen tonight
(four properties, a short description) is an older listing held on the client's side, not this server's. A
test now reads every argument batch reads from tools.py and requires it in the schema (`read`, `at` added).

## Costs added to what a session loads

Lean listing 7,166 -> 7,382 tokens (+216): batch +168 (read/at, lines "full", the file batch's reply), tool_groups
+22 (said), guide_read +26 (the index wording). tool_groups' card 712 -> 734 (bound 740). Coded tools 8,483 ->
8,699. The server instructions grew by one sentence (~72 tokens) saying what saidBefore means. Re-pinned in
tests/test_needs.py (COSTS). tools.json and readers.json did not change.

## Belongs in other repos (not done here)

- Workshop `slicer_presets list`: 60 names a kind and the four `from` paths on every call —
  agentlink-orcaslicer `orcalink/presets.py:97` (`listing(..., limit=60)`) and workshop-freecad
  `workshop_make/handlers/slicing.py:136` (`"from": SP.roots(slicer)` and the constant `next` on every reply). Cut
  to a count + first N with `limit` / `query` for the rest; `from` once a conversation (`agentlink.once.register`).
- SafetyNet `app_recover list` (up to 38,058 characters): workshop-freecad `safetynet/recovery.py:576-580` keeps
  six copies a document, each with its whole path, for every document with copies. Newest copy per document plus a
  count, with `document: x` for one document's all; paths relative to the AgentLink folder.
- ScanRuler: `handlers/deviation.py:56` SIGN_WORDS on every deviation answer (9 times), and report text that repeats
  the structured numbers beside it (`report_get`, `deviation_export`, `thickness_measure`: `text`/`report`) —
  register SIGN_WORDS with `agentlink.once.register(tool, key, words)`; give the report text only when asked.
  ScanRuler tools written as tools.json entries run through the hub's runner are already thinned by this change.
- OrcaSlicer link: the same `presets.py` listing as above.

## Tests

`tests/test_once.py` (15): each cut shows the fact still reachable (said, health_said, read_part, sectionTokens)
and the reply smaller; refusals and a batch's own note untouched; inside a batch nothing is thinned (its record and
to files stay whole); initialize starts over; batch's schema lists every argument it reads. `test_guideidx.py`
and `test_batch_chain_fc.py` follow the index's new shape. Full suite in two runs: 455 passed, 174 skipped
(38.8 s); 657 passed, 200 skipped, 5 subtests (182.3 s): 1,112 passed, 374 skipped.

## Risks

- An agent whose context was compacted loses a note said once; saidBefore names it and tool_groups { tool }
  gives it back. The health advice is in `said.health` there.
- A plain file batch's reply changed shape (see above).
- The guide index lost `sections` and `later[].tokens`; their content is in sectionTokens.

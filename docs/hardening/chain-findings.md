# chain: findings (batch answer chaining, one recompute at the end, guide_read index)

Checkout: wt3/chain at 72a94a2. Patch: chain.patch (new files included, FILES excluded — regenerate FILES: seven new files).
Full suite here: 783 passed, 337 skipped (FreeCAD tests skip here). Nothing committed or pushed.

New files: agentlink/chain.py, agentlink/hold.py, agentlink/guideidx.py (all plain Python, no FreeCAD import),
tests/test_chain.py, tests/test_hold.py, tests/test_guideidx.py (run here), tests/test_batch_chain_fc.py (FreeCAD; never run).
Changed: agentlink/tools.py (batch, guide_read, their descriptions, the instructions), guides start/model/assembly/feature, CHANGELOG.
Not touched: families/*, health.py, protocol.py, paths.py, batchrec.py.

"Proven here" below means two things, kept apart: (U) unit tests in the suite; (M) a one-off run of the real
tools.py batch/guide_read code with FreeCAD replaced by mocks and fake tools (chain-smoke.py beside this file; not in the repo).
(M) proves the wiring, not FreeCAD's behaviour.

## 1. Answer chaining in batch

Built
- Per call `to`: { tool, arguments, to: "x.json" } writes that call's whole answer (the result body) to the file; the batch
  result for it is { tool, ok, written: { path, bytes }, keys | length } plus health { ok, verdict, todo } when the call had a
  verdict (my addition to "only": a red reading must not hide in a file). Refused call: nothing written. Every `to` is
  checked before anything runs (.json name, paths.check as a write) — "Nothing was run".
- { "$file": path, "$at": "a.0.b" } and { "$from": index, "$at": … } anywhere in arguments, resolved as the call is about
  to run. $at: keys and list indices from 0, negatives from the end. $file through paths.check as a read (relative: session
  folder). $from counts calls through the whole list (as from/next do); only an earlier call, only one run in this part
  (across `from:` parts it refuses and says to use to + $file).
- A reference that cannot be followed refuses that call (code not_found / invalid_input / invalid_state) with what is there
  (keys, or list length, at the deepest level reached; for a missing file the .json files in that folder). It counts as a
  refusal for stopOnError and rollback. Cap 20 MB (file size; for $from the answer's JSON length).
- Batch-level `to` unchanged; its rows now carry `written` (path) for calls with their own `to`. The batch record holds the
  short row for such calls, not the answer.
- Decisions worth a look: a reference must stand alone ({ $file | $from, $at } and nothing else; anything else in the
  object refuses); files written by `to` stay after a rollback (said as writtenNote and in the description); `to` files are
  not registered with outputs (same as batch-level to), so outputs_clean never takes them.

Proven here
- (U) test_chain.py: paths, misses and their words, stand-alone rule, earlier-call rule, refused-call, earlier-part, cap,
  write/read/cache, .json naming, the reply row.
- (M) to + $from + $file end to end through server.call; miss stops and reports; ~/.ssh refused; /etc refused before running.

Needs the Mac
- tests/test_batch_chain_fc.py::BatchChain (first four tests). Live calls:
  1. batch { calls: [ { tool: "part_primitive", arguments: { kind: "box", size: [5,6,7], name: "ChainLid" }, to: "chain-lid.json" },
     { tool: "session_state", arguments: {}, to: "chain-state.json" },
     { tool: "object_get", arguments: { object: { "$from": 1, "$at": "bodies.-1.name" }, filter: "Length" } },
     { tool: "object_get", arguments: { object: { "$file": "chain-state.json", "$at": "bodies.-1.name" }, filter: "Width" } } ] }
     Expect results[0] and [1] with written/keys and no result; [2] and [3] the box's Length and Width.
  2. batch { rollback: false, calls: [ { tool: "session_state", arguments: {} },
     { tool: "object_get", arguments: { object: { "$from": 0, "$at": "bodies.999.name" } } } ] }
     Expect results[1] not_found naming the list's length; stopped: 1.
  3. batch { calls: [ { tool: "object_get", arguments: { object: { "$file": "no-such.json" } } } ] } — not_found listing the
     .json files in the session folder.
- Not verified: the Activity tab / echo words for a call whose arguments were substituted (the echo sees the filled-in
  arguments, which may be large).

## 2. batch { build: "end" }

How (read from FreeCAD 1.1.0 source; the Mac is 1.1.3)
- src/App/Document.pyi has RecomputesFrozen; src/App/DocumentPyImp.cpp setRecomputesFrozen sets Document::SkipRecompute;
  src/App/Document.cpp Document::recompute returns 0 at once while it is set unless force. So with the switch on, every
  tool's own doc.recompute() / picks.finish / picks.recompute_scoped does nothing, and no family code changes.
  src/Gui/Document.cpp slotSkipRecompute then recomputes the active/edited object only if the document has
  AllowPartialRecompute (off by default). obj.recompute() (recomputeFeature) and recompute(force) are NOT held.
- Too many tools read the rebuilt model in their answers or refuse on it, so it is opt-in: agentlink/hold.py HELD_OK.
  Safe from reading their code: sketch_add, sketch_constrain, sketch_edit, sketch_offset (geometry and constraints are
  written at once; state_of() calls sk.solve(), so solver/dof/conflicting/redundant are fresh; wires, closedWires,
  openVertices, readyForFeature, todo, note come from sk.Shape and are removed from a held answer; sketch_edit's bodyAfter
  too) and object_set (its "note" removed). Every other tool — pd_*, part_*, sketch_new, sketch_external, param_set,
  varset_set, sheet_set, feature_edit, all reads but guide_read / tool_groups / usage_report / job_status — builds first
  and runs unfrozen. An add-on opts a tool in with hold.declare(tool, stale_keys).
- A held call's answer: build: "held", health replaced by { build: "held", verdict: "build: held — …", leftOut: [...] }.
- The build: unfreeze, doc.recompute(), then one health.check against a mark armed before the first held call (so it
  covers every object the run made or changed), one session step "batch build", an entry in builds[]:
  { when, held, calls: [first, last], recomputed, ms, health }. Builds happen at the end, before the first non-held call,
  when a call lands in another document, on budget stop, and in a finally (never left frozen).
- Lost per-call refusals: sketch_edit and object_set normally refuse a change that breaks a feature. Held, they cannot;
  so a build whose health lists new failing objects stops the batch like a refusal (buildFailed: true) and, with
  rollback, takes it back whole. With stopOnError: false it only reports.
- Rollback: the hold is released before the existing undo-and-recompute; the rollback code is the old code moved into a
  function, unchanged in order.
- If the person already has Skip recomputes on: nothing held, nothing built, buildNote says so, switch left on.

Proven here
- (U) test_hold.py with a stand-in document: which tools hold, stripping, one recompute, health read once, release,
  person's switch, missing switch, a recompute that raises.
- (M) hold → guide_read passes → object_set held → pd_pad forces a build and runs unfrozen → end build; refusal in a held
  run rolls back and leaves the document unfrozen; person's switch respected; a batch without build is byte-for-byte as before.

Needs the Mac (nothing here has run against FreeCAD)
- tests/test_batch_chain_fc.py::BatchChain build tests. Live, on a new document:
  1. pd_body_new { name: "HoldB" }; sketch_new { body: "HoldB", plane: "XY", name: "HoldSk" }
  2. batch { build: "end", calls: [
     { tool: "sketch_add", arguments: { sketch: "HoldSk", items: [ { kind: "rectangle", center: [0,0], size: [40,20] } ] } },
     { tool: "sketch_add", arguments: { sketch: "HoldSk", items: [ { kind: "circle", center: [0,0], radius: 4 } ] } },
     { tool: "sketch_constrain", arguments: { sketch: "HoldSk", constraints: [ { type: "radius", refs: [[ { "$from": 1, "$at": "added.0.ids.0" } ]], value: 4 } ] } } ] }
     Expect: each result build: "held", state with solver/dof and no wires/closedWires; builds: one entry, when "end",
     held 3, recomputed > 0, a health verdict about HoldSk. Then sketch_state { sketch: "HoldSk", detail: false } →
     closedWires 2. Compare ms with the same three calls without build.
  3. batch { build: "end", calls: [ { tool: "sketch_edit", arguments: { sketch: "HoldSk", construction: { geo: 4, on: true } } },
     { tool: "sketch_state", arguments: { sketch: "HoldSk", detail: false } },
     { tool: "pd_pad", arguments: { sketch: "HoldSk", length: 5 } },
     { tool: "object_set", arguments: { object: "Pad", values: { Length: 8 } } } ] }
     Expect builds when: "before call 1 (sketch_state)" and "end"; the pad's own answer with a real volume and no
     build key; session_state afterwards shows HoldB at 40 x 20 x 8.
  4. Breaking build: batch { build: "end", calls: [ { tool: "sketch_edit", arguments: { sketch: "HoldSk", delete: [0] } } ] }
     Expect buildFailed: true, undone 1, HoldSk's geometry and the body's volume as before. DOUBT: this relies on the Pad
     failing on an open profile and health marking it a new error; if 1.1.3 pads something anyway, the test and this
     call need another breaking edit.
  5. Doubts to watch live: (a) whether the 3D view / tree repaint oddly while frozen in the window; (b) whether a
     sketch open in edit mode during a held run behaves (not read in source); (c) the held sketch_edit sub-operations
     (trim, fillet, split, mirror, text) — I read the function's recompute and state use, not each sub-operation;
     if any reads sk.Shape mid-way it would see the pre-run shape. (d) history_diff across a held run: the held calls'
     own steps hold pre-build body numbers; the "batch build" step after them is the true one.
  6. The recompute after the build runs outside an undo transaction (as the existing rollback's does). history_undo of a
     held call afterwards should restore and recompute as usual — check once.

Wish for health.py (not edited): a public way to read "new failing objects since mark" so hold.build_failed need not
depend on the errors[].new shape.

## 3. guide_read

Built
- Index per guide: sections (names, as before, with "Start here" first), chars (as before), tokens, sectionTokens
  { name: tokens } (characters / 4), start (when the guide has "## Start here"), later [{ section, when, tokens }],
  firstReadTokens. Plus a one-line note.
- Convention (documented in agentlink/guideidx.py): a section for one moment carries `<!-- later: when … -->` on the line
  under its heading; the comment is stripped from text guide_read returns. Headings are unchanged, so section lookups
  and add-on guides without the convention read exactly as before.
- Start here maps added to model, assembly, feature (the three longest), written only from each guide's own headings and
  content; 6 + 6 + 4 sections marked later. No workflow facts added.
- section: a name or a list (one answer). topic: a list reads guides in order to about 55 000 characters of JSON (the
  reply limit is 60 000, and protocol.trim would otherwise halve the list), rest in next; with section, that section of
  each guide that has it (others in missing).

Proven here
- (U) test_guideidx.py, including the real guides: maps present on the three longest, every later section named in its
  map, all 20 guides readable in at most 4 calls each under 60 000 characters.
- (M) index, list of topics with next, section list, old single-section call, unknown topic/section refusals.

Needs the Mac
- tests/test_batch_chain_fc.py::GuideRead, tests/test_guides.py (every backticked tool in the guides exists — my maps
  name only tools the guides already named, but it has not run). Live: guide_read {} ; guide_read { topic: "model",
  section: ["Start here", "workflow"] } ; guide_read { topic: ["start","model","sketch","feature","assembly","techdraw","cam","view","draft"] }
  (expect read + next) ; guide_read { topic: <next> }.
- Not verified: add-on guides with the same name/sections, and the Activity tab's words for a list topic
  (activity.fallback takes the first word-like argument; a list may read oddly, it does not raise as far as I read).

## 4. Descriptions and compatibility
- batch and guide_read descriptions extended (nothing cut); schema: batch gains build (enum end | each), guide_read's
  topic and section accept a string or a list. Instructions and the start guide teach to / $file / $from / build: "end" /
  the index. The tool index (agentlink/data/tool_index.json) was not regenerated.
- Backward compatible: a batch without to / $ references / build produces the same answer keys as before (M); guide index
  keeps topic, title, sections (names), chars.
- One behaviour change to know: an argument object that happens to contain a "$file" or "$from" key inside a batch is now
  read as a reference. No tool here takes such keys.

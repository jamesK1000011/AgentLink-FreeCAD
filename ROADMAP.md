<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Roadmap

What Agent Link for FreeCAD builds now, next and later, and what we looked at and chose not to do. The list changes as work lands. It gives an order, not dates.

The goal: any model, small or large, can run FreeCAD through Agent Link correctly the first time, at a low token cost. The tool library (one data file of checked tools per add-on) stays at the centre.

## Now

Work on the `efficiency` branch.

- **Pictures go to files by default.** `window_snapshot` and `view_snapshot` write the picture to the session folder and give its path. Ask for `inline: true` to get it in the answer. `window_snapshot` gets a width.
- **Better tool search.** For example, "pad sketch" finds `pd_pad`.
- **Forgiving calls.** Common wrong field names are accepted, with a note that names the right one. A batch inside a batch runs inline, in order.
- **A clear outcome on every refusal.** Each refusal says what happened to the document: nothing changed, rolled back, or partly kept.
- **Exit-proof add-on code.** Approved add-on code that calls `sys.exit` cannot close FreeCAD.
- **Model-neutral words in the panel.** The panel speaks of "the agent", not one AI product. Help for a given client keeps that client's name.

## Next

- **Options as ready calls.** `session_state` and each changing answer offer up to four likely next calls, with the arguments that the document settles already filled in. The agent picks by number ("1, 4 mm"). Every option passes its leading checks before it is shown.
- **Co-work in one window:**
  - The agent never moves your camera. "Follow agent" is a switch that stays on until you turn it off.
  - The agent's highlight sits on its own layer, so your own selection stays yours.
  - While you edit a sketch or a task panel, the agent's changes to that body wait.
  - The agent's rollback never undoes a step that you made.
- **A fast path for long sessions.** One call runs a block of chained and looped steps in the same step language the tools use. Missing arguments fill from the current body, sketch and last result, and a short summary comes back. Each step keeps its checks, and the block rolls back as a whole.
- **A benchmark across model sizes:** tokens, first-try success, turns and refusals, on a set of real parts.
- **A compact form for clients that ask for it:** short tool ids, object handles, and answers that give only what changed. Clients that do not ask get the readable form.
- **Small reliability items:**
  - Late answers are kept, so a call that timed out can be read before a retry.
  - Text that cannot be sent is always made safe.
  - Retries happen only for reads, and for calls that never started.

## Later

- **FreeCAD 26.3** support when it is released. Until then, we recommend FreeCAD 1.1.4: it fixes file-extraction flaws in earlier releases.
- **The MCP 2026-07-28 transport** (stateless requests).
- **Recipes and cookbook format 2:** saved, shareable step files, and an automatic port for other add-ons.
- **PrintLoop:** G-code checks for the OrcaSlicer link.
- **Progress text** in the chat during long batches.
- **Listings** in the MCP Registry and the FreeCAD Addon Index.

## Considered

Ideas we looked at, and why they are "no" or "not now".

| Idea | Verdict | Why |
|---|---|---|
| A tool that runs any Python | No | The security risk is too high. The step language covers chains and loops through checked tools. Add-on code runs only after the person approves it. |
| A tool list that changes with the document | No | In tests, clients did not fetch the changed list. A small, fixed base list with `tool_find` worked better and keeps prompt caches valid. |
| Live choices inside the tool list's schemas | No | It would change the list with each document. Choices go in the options and in the refusals. |
| A forced picture after repeated errors | No | Many small models read text only. The refusal gives the place in words and names the picture call. Pictures added by themselves are a setting, off by default. |
| A second live window for the agent | No | The agent renders off screen with its own camera. "Follow agent" covers watching. |
| Up-front job time estimates and memory refusals | No | Agent Link reacts to what FreeCAD does. A watchdog handles true hangs. |
| A shared library for all add-ons | No | Each add-on stands alone and carries its own code. |
| Copying Apache-2.0 code from other projects | No | It would tie the hub to (L)GPL-3.0 terms. We keep LGPL-2.1-or-later and write our own code. |
| Real token counts in the usage meter | Not now | An MCP server cannot see the model's real counts. The meter gives estimates. |
| MCP structured output (`structuredContent`) | Not now | Client support varies. It will come behind a switch, after a test on each client. |

# Records kept in the FreeCAD document (format 1)
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

Notes about the parts — how each is made, what it is made of, the limits it
must meet, findings accepted on purpose — are saved inside the `.FCStd`, so
they travel with the file and undo takes them back with the rest. This is a
**file format**, not a library: every add-on that reads or writes records
carries its own small reader (Agent Link's is `agentlink/store.py`) and keeps
to this page. No add-on needs another installed to read them.

## Where they live

- One hidden object named **`AgentLinkRecords`** (`App::FeaturePython`, label
  "Agent Link records", not shown in the tree). The name is the format's,
  kept for files written since the first records.
- One `App::PropertyString` per record, named `R_<name>` (characters other
  than letters, digits and `_` become `_`), in property group `AgentLink`,
  hidden in the editor. Its value is the record as compact JSON.
- Writing a record happens inside the calling tool's undo step.
- **Older files** kept records in the document's `Meta` under
  `AgentLink.<name>`. Read them from there while there is no records object;
  the first write creates the object and copies them over. `Meta` is left as
  it was.
- An empty string means the record was removed.

## The records

| Name | JSON | Written by |
|---|---|---|
| `setups` | `[{ "name", "type": "print" \| "cut" \| "mill", "bodies": [labels], "settings": {…} }]` — a body is in one setup of a type at most | Make |
| `spec` | `{ "minWall", "massMin", "massMax", "minSafety", "minClearance" }` (mm, g) — limits every part must meet | Make |
| `materials` | `{ "<body label>": "<material id>" }` (filament keys such as `pla`, or a FreeCAD library card) | Agent Link, Make |
| `waivers` | `[{ "body", "rule", "at", "reason" }]` — findings accepted on purpose | Make |
| `fit` | `{ "hole", "shaft" }` — how much this printer prints a hole small and a peg big (diametral mm) | Make, Parts |
| `threads` | threads cut or read on bodies | Make |
| `embeds` | parts encased mid-print, with their pauses | Make |
| `boards` | KiCad boards imported and their enclosures | Electronics |
| `notes` | the panel's notes and steps | Agent Link |
| `motions` | assembly motions | Agent Link |

The setting names for each setup type are listed in `agentlink/store.py`
(`TYPES`). A reader ignores records and fields it doesn't know, and never
removes them.

## Changing the format

Add fields and records freely; readers ignore what they don't know. A change
that old readers would misread gets a new format number here and a record
`format` holding it.

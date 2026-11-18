<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Setting up Agent Link for FreeCAD: steps for an agent

Follow these in order. Each step says how to tell it is done. Run commands
in the person's own shell; ask them only for what needs them (installing an
app with an admin prompt, restarting their MCP client). Change nothing they
did not ask for.

## 1. Check what is there

```
uvx --from git+https://github.com/jamesK1000011/AgentLink-FreeCAD agentlink-freecad --check --json
```

If `uvx` is not found, install uv first (step 2), or run the same check from
a copy of the repository with any Python 3.8+:
`python3 agentlink_headless.py --check --json`.

The answer is `{"os": ..., "items": [{"item", "state", "what", "fix"}]}`.
`state` is `ok`, `missing` (required), `optional` or `note`. The exit code is
1 while anything required is missing. Work through each `missing` item with
its `fix`, then run the check again. Offer the `optional` ones only when the
person's task needs them (OrcaSlicer for slicing, KiCad for boards).

## 2. uv (preferred)

- macOS, Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Done when `uvx --version` prints a version (open a new shell first). If uv
cannot be installed, Node 18+ is the backup only for the Claude Desktop
extension; for other clients use FreeCAD's own Python
([docs/clients: Without uv](docs/clients/README.md#without-uv)).

## 3. FreeCAD 1.0 or later (1.1 recommended)

Ask the person to install it from <https://www.freecad.org/downloads.php>
(macOS: into /Applications) and to **open it once and close it**: that makes
its user folder. Done when the check shows `FreeCAD: ok` with 1.0 or later.
A FreeCAD in an unusual place: set `FREECAD_APP` (the app or install folder)
or `FREECAD_LIB` (its `lib` folder) in the client's `env`.

## 4. The add-on in FreeCAD (only to watch in the window)

Headless use needs no add-on. To let the person watch, install it one way:

- macOS with Claude Desktop: the `.mcpb` extension does it (and is the
  client setup too): https://github.com/jamesK1000011/AgentLink-FreeCAD/releases/latest/download/freecad-agentlink.mcpb
  (attached to each `agentlink-v…` release of this repository). The copies
  once released from ScanRuler's `freecad-spike` branch are retired; an
  installed one moves here at its next update.
- Addon Manager: Preferences > Addon Manager > Custom repositories, add
  `https://github.com/jamesK1000011/AgentLink-FreeCAD` branch `main`, then
  install **Agent Link** from Tools > Addon manager.
- By hand: `git clone https://github.com/jamesK1000011/AgentLink-FreeCAD "<user folder>/Mod/AgentLink"`;
  the check prints the user folder's `Mod` path.

Done when the check shows `Agent Link add-on: ok`.

## 5. The MCP client

Use the page for the person's client in [docs/clients/](docs/clients/README.md).
Merge the `agentlink-freecad` entry into their existing config; never
replace the file. Give `uvx`'s full path (`which uvx` / `where uvx`) when the
client is a GUI app. Small local model: keep the lean list (do not set
`AGENTLINK_TOOLS=full`).

The person restarts the client. Done when the client lists the
`agentlink-freecad` server with tools such as `session_state`.

The person sets the two approval tools in the client's tool permissions
(Claude Desktop: the server's tools, each "Always allow", "Ask first" or
"Block"):

- `approve_code` (run or install code: macros, cookbooks, add-ons,
  extensions): "Ask first" is the safe setting.
- `approve_file` (a file dialog, a recovered copy, save all at a restart):
  "Ask first" is the safe setting.

"Always allow" lets the agent approve alone (headless use). It is the
person's choice. Never change these settings for the person.

## 6. Prove it

Call `session_state`: it answers with what the document holds and where
files go. Then `guide_read` with topic `start` for how to work. To watch,
the person opens FreeCAD, picks the Agent Link workbench and presses
**Start Link**; the next calls show in their window.

## If it fails

- "Server disconnected": read the client's MCP log (README: Troubleshooting);
  the last lines name the cause. Run the check again.
- FreeCAD never opened: ask the person to open it once.
- Still stuck: report the check's JSON and the log's last 20 lines to the
  person, not a guess.

## Remove it

README: [Uninstall](README.md#uninstall).

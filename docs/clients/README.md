<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Connecting an MCP client

Agent Link is a local MCP server over stdio. Every client starts the same
command:

```
uvx --from git+https://github.com/jamesK1000011/AgentLink-FreeCAD agentlink-freecad
```

| Client | Page |
|---|---|
| Claude Desktop | [claude-desktop.md](claude-desktop.md) (or the `.mcpb` extension on a Mac) |
| Claude Code | [claude-code.md](claude-code.md) |
| Cursor | [cursor.md](cursor.md) |
| VS Code (Copilot agent mode) | [vscode.md](vscode.md) |
| LM Studio | [lm-studio.md](lm-studio.md) |
| OpenCode with Ollama | [opencode-ollama.md](opencode-ollama.md) |
| Anything else that speaks MCP | [generic.md](generic.md) |

## Before you start

- FreeCAD 1.1 or later, opened once.
- `uv` ([install](https://docs.astral.sh/uv/getting-started/installation/)).
  GUI apps often do not see your shell's PATH: if the client says it cannot
  find `uvx`, put its full path in `command` (`~/.local/bin/uvx` on Mac and
  Linux, `%USERPROFILE%\.local\bin\uvx.exe` on Windows; `which uvx` or
  `where uvx` prints it).
- `agentlink-freecad --check` says what is still missing.

Optional flags, added after `agentlink-freecad` in `args`:

| Flag or variable | What it does |
|---|---|
| `--out DIR` | where files go (default `~/AgentLink`) |
| `FREECAD_APP` (env) | the FreeCAD app or install folder, when it is not where the check looks |
| `FREECAD_LIB` (env) | FreeCAD's `lib` folder, for a FreeCAD the check cannot find |
| `AGENTLINK_TOOLS=full` (env) | list every tool from the start (not for small models) |
| `AGENTLINK_USAGE=off` (env) | turn the token-usage meter off |

### Without uv

Run FreeCAD's own Python on `agentlink_headless.py` in the add-on folder
(installed by the Addon Manager or by hand):

| OS | `command` | `args` |
|---|---|---|
| macOS | `/Applications/FreeCAD.app/Contents/Resources/bin/python` | `["<FreeCAD user folder>/Mod/AgentLink/agentlink_headless.py", "--out", "<home>/AgentLink"]` |
| Windows | `C:\Program Files\FreeCAD 1.1\bin\python.exe` | the same |
| Linux | `FreeCADCmd` (or `freecadcmd`) | `["<FreeCAD user folder>/Mod/AgentLink/agentlink_headless.py"]`, with `AGENTLINK_OUT` in `env` |

Node is the backup for the Claude Desktop extension: its launcher is a Node
program, and Claude Desktop brings the Node it runs on.

## Small local models

Models under about 30B parameters do best with a short tool list. Agent Link
starts **lean** by default: only the core and view groups are listed (the
session, guides, undo, checks, pictures), about a dozen tools. The model asks
`tool_groups` for the rest and turns on one group at a time
(`tool_groups` with `enable: ["sketch"]`), as each group's guide says.

- Do not set `AGENTLINK_TOOLS=full`.
- Install only the add-ons you use: an add-on that isn't installed adds no
  tools and costs no tokens.
- Prefer one task per chat; the usage strip in the panel shows how much the
  tool list and the answers take.
- Give the model a context window of at least 32k tokens.

## ChatGPT

ChatGPT connects only to remote MCP servers, reached over HTTPS from
OpenAI's side. Agent Link is a local stdio server that drives the FreeCAD on
your own computer and listens on 127.0.0.1 only, so ChatGPT is out of scope.
Putting it behind a public tunnel would expose your computer's FreeCAD to
the internet; don't.

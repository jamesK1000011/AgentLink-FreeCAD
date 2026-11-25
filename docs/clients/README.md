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
- The setup check says what is still missing:
  `uvx --from git+https://github.com/jamesK1000011/AgentLink-FreeCAD agentlink-freecad --check`.

Optional flags, added after `agentlink-freecad` in `args`:

| Flag or variable | What it does |
|---|---|
| `--out DIR` | where files go (default `~/AgentLink`) |
| `FREECAD_APP` (env) | the FreeCAD app or install folder, when it is not where the check looks |
| `FREECAD_LIB` (env) | FreeCAD's `lib` folder, for a FreeCAD the check cannot find |
| `AGENTLINK_TOOLLIST=classic` (env) | the classic tool list: the lean groups from the start, not the six-tool list |
| `AGENTLINK_TOOLS=full` (env) | with `AGENTLINK_TOOLLIST=classic`: list every tool from the start (not for small models) |
| `AGENTLINK_USAGE=off` (env) | turn the token-usage meter off |
| `AGENTLINK_PROFILE_CALLS=1` (env), or the preference `ProfileCalls` | time every batch call by function (cProfile) and add `profile` to its row; for finding what is slow, never set by the agent |
| `AGENTLINK_TIME_LIMIT_MIN=30` (env) | a run with a fixed time: the limit in minutes, read at start and counted from the first tool call; `session_state` shows `time: N of M minutes used`, and the health verdict does from half the limit on. Not set: nothing shows |

### Without uv

Run FreeCAD's own Python on `agentlink_headless.py` in the add-on folder
(installed by the Addon Manager or by hand). The examples use `Mod/AgentLink`;
the Addon Manager names the folder `AgentLink-FreeCAD`:

| OS | `command` | `args` |
|---|---|---|
| macOS | `/Applications/FreeCAD.app/Contents/Resources/bin/python` | `["<FreeCAD user folder>/Mod/AgentLink/agentlink_headless.py", "--out", "<home>/AgentLink"]` |
| Windows | `C:\Program Files\FreeCAD 1.1\bin\python.exe` | the same |
| Linux | `FreeCADCmd` (or `freecadcmd`) | `["<FreeCAD user folder>/Mod/AgentLink/agentlink_headless.py"]`, with `AGENTLINK_OUT` in `env` |

Node is the backup for the Claude Desktop extension: its launcher is a Node
program, and Claude Desktop brings the Node it runs on.

## Small local models

Models under about 30B parameters do best with a short tool list. By
default Agent Link lists only six tools (`session_state`, `batch`,
`guide_read`, `tool_find`, `approve_file`, `approve_code`). The model finds
any other tool with `tool_find` and calls it by name, or turns on one group
at a time (`tool_groups` with `enable: ["sketch"]`), as each group's guide
says.

- Do not set `AGENTLINK_TOOLLIST` or `AGENTLINK_TOOLS`.
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

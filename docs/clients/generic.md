<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Any MCP client

A local server over stdio (newline-delimited JSON-RPC, MCP protocol
revision 2025-06-18):

| | |
|---|---|
| transport | stdio |
| command | `uvx` |
| args | `--from` `git+https://github.com/jamesK1000011/AgentLink-FreeCAD` `agentlink-freecad` |
| env (optional) | `FREECAD_APP`, `FREECAD_LIB`, `AGENTLINK_OUT`, `AGENTLINK_TOOLLIST`, `AGENTLINK_TOOLS`, `AGENTLINK_USAGE` ([what each does](README.md#before-you-start)) |

Most clients take the `mcpServers` shape:

```json
{
  "mcpServers": {
    "agentlink-freecad": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/jamesK1000011/AgentLink-FreeCAD", "agentlink-freecad"]
    }
  }
}
```

The server sends instructions at `initialize`, lists the lean tools, and
serves guides as resources (`agentlink://guide/<topic>`). Without uv, see
[Without uv](README.md#without-uv).

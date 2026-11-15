<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Cursor

[**Add to Cursor**](https://cursor.com/en/install-mcp?name=agentlink-freecad&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyItLWZyb20iLCJnaXQraHR0cHM6Ly9naXRodWIuY29tL2phbWVzSzEwMDAwMTEvQWdlbnRMaW5rLUZyZWVDQUQiLCJhZ2VudGxpbmstZnJlZWNhZCJdfQ==)
(or paste the deep link `cursor://anysphere.cursor-deeplink/mcp/install?name=agentlink-freecad&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyItLWZyb20iLCJnaXQraHR0cHM6Ly9naXRodWIuY29tL2phbWVzSzEwMDAwMTEvQWdlbnRMaW5rLUZyZWVDQUQiLCJhZ2VudGxpbmstZnJlZWNhZCJdfQ==`
into a browser).

By hand: `~/.cursor/mcp.json` for every project, or `.cursor/mcp.json` in one:

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

Then **Settings > MCP**: the server should show green with its tools.

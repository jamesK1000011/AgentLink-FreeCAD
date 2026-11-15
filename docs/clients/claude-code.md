<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Claude Code

For every project (`-s user`):

```
claude mcp add -s user agentlink-freecad -- uvx --from git+https://github.com/jamesK1000011/AgentLink-FreeCAD agentlink-freecad
```

Or for one project, in `.mcp.json` at its root:

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

`claude mcp list` shows whether it connected; `/mcp` in a session shows its
tools.

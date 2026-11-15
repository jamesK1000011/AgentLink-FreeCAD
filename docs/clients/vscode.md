<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# VS Code

[**Install in VS Code**](https://vscode.dev/redirect/mcp/install?name=agentlink-freecad&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A//github.com/jamesK1000011/AgentLink-FreeCAD%22%2C%22agentlink-freecad%22%5D%7D)
· [**VS Code Insiders**](https://insiders.vscode.dev/redirect/mcp/install?name=agentlink-freecad&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A//github.com/jamesK1000011/AgentLink-FreeCAD%22%2C%22agentlink-freecad%22%5D%7D)

From a terminal:

```
code --add-mcp '{"name":"agentlink-freecad","command":"uvx","args":["--from","git+https://github.com/jamesK1000011/AgentLink-FreeCAD","agentlink-freecad"]}'
```

Or by hand, in `.vscode/mcp.json` (one workspace) or the user
`mcp.json` (**MCP: Open User Configuration**):

```json
{
  "servers": {
    "agentlink-freecad": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/jamesK1000011/AgentLink-FreeCAD", "agentlink-freecad"]
    }
  }
}
```

Use it from Copilot Chat in **Agent** mode; the tools button lists its tools.
The raw deep link is `vscode:mcp/install?%7B%22name%22%3A%22agentlink-freecad%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A//github.com/jamesK1000011/AgentLink-FreeCAD%22%2C%22agentlink-freecad%22%5D%7D`.

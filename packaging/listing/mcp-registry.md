<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# DRAFT: Official MCP Registry entry

Status: DRAFT. The owner publishes. Checked against the registry's
documentation and its source (modelcontextprotocol/registry, 13 Nov 2026)
on 19 Nov 2026.

## The entry

The entry is the top-level [`server.json`](../../server.json). It is not
copied here, so that there is one file only. On 19 Nov 2026 it:

- uses the current schema,
  `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`
  (the registry takes older schemas with a warning only);
- passes that schema (checked with `jsonschema` against the registry's
  own copy, `internal/validators/schemas/2025-12-11.json`);
- has a description of 92 characters (the limit is 100);
- has the name `io.github.jamesK1000011/agentlink-freecad`. The registry
  compares the name with the GitHub login and the case counts:
  `jamesK1000011`, with a capital K.

## The rules

- Docs: https://modelcontextprotocol.io/registry/quickstart and
  https://modelcontextprotocol.io/registry/package-types
- The registry keeps metadata only. The package must be on PyPI first.
- PyPI ownership check: the package README (the PyPI description) must
  hold `mcp-name: io.github.jamesK1000011/agentlink-freecad`. Our README
  has it in line 2 as an HTML comment, which PyPI keeps.
- Sign-in: `mcp-publisher login github` (device code at
  https://github.com/login/device). In GitHub Actions,
  `mcp-publisher login github-oidc` works with no secret.
- A version can be published once only. The registry is in preview: data
  resets are possible.

## Optional: the Claude extension as a second package

The registry also takes an `.mcpb` file from a GitHub release
(`registryType: "mcpb"`). The URL must contain "mcp" (the `.mcpb` file
name does) and the entry must give the file's SHA-256. The hash is known
only after CI builds the file, so this is not in `server.json` now. To
add it after the `agentlink-v1.0.0` release, put this object into
`packages` (after the PyPI one), with the hash from the command below:

```json
{
  "registryType": "mcpb",
  "identifier": "https://github.com/jamesK1000011/AgentLink-FreeCAD/releases/download/agentlink-v1.0.0/freecad-agentlink.mcpb",
  "fileSha256": "<sha256 of the release file>",
  "transport": { "type": "stdio" }
}
```

```sh
gh release download agentlink-v1.0.0 --repo jamesK1000011/AgentLink-FreeCAD --pattern freecad-agentlink.mcpb --dir /tmp/al && shasum -a 256 /tmp/al/freecad-agentlink.mcpb
```

`scripts/release.py check` reads a version from each package, and an
`mcpb` package has none: change that check to skip `mcpb` packages
first, or it reports a mismatch. Then `mcp-publisher publish` must use a new version number: the registry
does not take 1.0.0 twice. So add it before the first publish, or with
1.0.1.

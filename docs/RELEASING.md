<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Releasing

The steps a maintainer runs by hand to release Agent Link for FreeCAD and the
add-ons the Claude extension bundles. Everything before this (versions,
changelogs, the extension's manifest, CI) is prepared in the repositories;
these are the steps that publish.

Steps marked **IRREVERSIBLE** put something public that cannot be taken back
cleanly: a pushed tag is fetched and mirrored at once, a GitHub release is
downloaded, a PyPI version number can never be uploaded again (even after
deleting it), an MCP Registry version cannot be published twice, and an
Addon Index entry is public as soon as it is merged. Read each block before
running it.

Each block starts in a fresh clone in a temporary folder; paste them in one
terminal, in order. A check prints `ok …` or `STOP …`: go on only when every
check says ok. What you need once:
`git`, the GitHub CLI signed in (`gh auth status`), `python3`, `uv`
(`brew install uv`) and, for the MCP Registry, `mcp-publisher`
(`brew install mcp-publisher`).

| Repository | Version | Tag | Assets | PyPI | MCP Registry | Addon Index |
|---|---|---|---|---|---|---|
| AgentLink-OrcaSlicer | 0.1.0 | `v0.1.0` | `orcaslicer-agentlink.mcpb` | no | no | no (no `package.xml`) |
| Workshop-FreeCAD | 0.4.0 | `v0.4.0` | none (source) | no | no | yes, `Workshop` |
| Texturizer-FreeCAD | 0.4.0 | `v0.4.0` | none (source) | no | no | yes, `Texturizer` |
| ScanRuler-FreeCAD | 0.5.0 | `v0.5.0` | none (source) | no | no | yes, `ScanRulerFC` |
| Tutor-FreeCAD | 0.2.0 | `v0.2.0` | none (source) | no | no | yes, `Tutor` (after Agent Link) |
| AgentLink-FreeCAD | 0.3.0 | `agentlink-v0.3.0` | `freecad-agentlink.mcpb` (built by CI) | `agentlink-freecad` | `io.github.jamesK1000011/agentlink-freecad` | yes, `AgentLink` |

Order: the add-ons first, each tagged at the commit the extension pins
(`packaging/pins/` here), so what is tagged is what the extension installs;
then Agent Link, whose tag builds the extension from those pins; then PyPI,
the MCP Registry and the Addon Index.

## 0. Privacy check on what is built

Every artefact is checked before it is published, with the check every
repository carries (`.github/privacy/check.py`; a finding is fixed, never
waived):

```sh
python3 .github/privacy/check.py dist/
```

It reads zip-based files (`.mcpb`, `.whl`) inside; a `.tar.gz` is unpacked
first (the blocks below do that).

## 1. The add-ons (Workshop, Texturizer, ScanRuler for FreeCAD, Tutor)

The same block for each; set the three lines at the top. Values:

| `REPO` | `V` | `PIN` |
|---|---|---|
| Workshop-FreeCAD | 0.4.0 | workshop-ref |
| Texturizer-FreeCAD | 0.4.0 | texturizer-ref |
| ScanRuler-FreeCAD | 0.5.0 | scanrulerfc-ref |
| Tutor-FreeCAD | 0.2.0 | tutor-ref |

```sh
REPO=Workshop-FreeCAD V=0.4.0 PIN=workshop-ref
cd "$(mktemp -d)"
gh repo clone "jamesK1000011/$REPO" -- -q && cd "$REPO"
C=$(gh api "repos/jamesK1000011/AgentLink-FreeCAD/contents/packaging/pins/$PIN" -H "Accept: application/vnd.github.raw" | tr -d '[:space:]')
# The pinned commit must say this version, with a dated changelog section.
git show "$C:package.xml" | grep -q "<version>$V</version>" && echo "ok package.xml $V" || echo "STOP package.xml at the pin is not $V"
git show "$C:CHANGELOG.md" | grep -E -q "^## \[?$V\]? (-|—) [0-9]{4}-" && echo "ok CHANGELOG $V" || echo "STOP no dated $V section in CHANGELOG.md at the pin"
gh run list --commit "$C" --json name,conclusion -q '.[] | "\(.name): \(.conclusion)"'   # every line: success
mkdir dist && git archive --format=zip --prefix="$REPO-$V/" -o "dist/$REPO-$V.zip" "$C"
python3 .github/privacy/check.py dist/
git show "$C:CHANGELOG.md" | awk -v v="$V" '$0 ~ "^## \\[?"v"\\]? " {f=1; next} /^## /{if (f) exit} f' > notes.md
```

Then, **IRREVERSIBLE** (the tag and the release):

```sh
git tag -a "v$V" "$C" -m "$REPO $V"
git push origin "v$V"
gh release create "v$V" --verify-tag --title "$REPO $V" --notes-file notes.md
```

The release carries GitHub's own source archives (the same files the zip
above was checked from). Each tag runs that repository's privacy workflow;
`gh run list --limit 3` shows it pass.

## 2. Agent Link for OrcaSlicer 0.1.0

Its changelog still says "The first release, 0.1.0, is being prepared" under
Unreleased: the release commit folds that into `## [0.1.0] - <date>` first
(ask Claude, or edit it and push), and the pin
`packaging/pins/orcalink-ref` here moves to that commit (bake-off green).
Then:

```sh
REPO=AgentLink-OrcaSlicer V=0.1.0 PIN=orcalink-ref
cd "$(mktemp -d)"
gh repo clone "jamesK1000011/$REPO" -- -q && cd "$REPO"
C=$(gh api "repos/jamesK1000011/AgentLink-FreeCAD/contents/packaging/pins/$PIN" -H "Accept: application/vnd.github.raw" | tr -d '[:space:]')
git checkout -q "$C"
python3 -c "import json; v=json.load(open('mcpb/manifest.json'))['version']; print('ok manifest' if v == '$V' else 'STOP manifest says ' + v)"
grep -E -q "^## \[?$V\]? (-|—) [0-9]{4}-" CHANGELOG.md && echo "ok CHANGELOG $V" || echo "STOP no dated $V section in CHANGELOG.md"
node mcpb/test/launcher.test.mjs
mkdir -p dist && sh mcpb/build.sh "$PWD/dist/orcaslicer-agentlink.mcpb"
python3 .github/privacy/check.py dist/
awk -v v="$V" '$0 ~ "^## \\[?"v"\\]? " {f=1; next} /^## /{if (f) exit} f' CHANGELOG.md > notes.md
```

**IRREVERSIBLE**:

```sh
git tag -a "v$V" "$C" -m "$REPO $V"
git push origin "v$V"
gh release create "v$V" --verify-tag --title "Agent Link for OrcaSlicer $V" --notes-file notes.md dist/orcaslicer-agentlink.mcpb
```

No Addon Index entry: it has no `package.xml` (the Claude extension and
Agent Link install it).

## 3. Agent Link for FreeCAD 0.3.0

### 3.1 Checks

```sh
cd "$(mktemp -d)"
gh repo clone jamesK1000011/AgentLink-FreeCAD -- -q && cd AgentLink-FreeCAD
python3 scripts/release.py check --tag agentlink-v0.3.0
# The pinned Agent Link carries this commit's add-on files (FILES): else the
# extension would install an older Agent Link than the tag.
grep -v -E '^#|^$' FILES | tr '\n' '\0' | xargs -0 git diff --quiet "$(cat packaging/pins/addon-ref)" HEAD -- && echo "ok addon-ref is current" || echo "STOP addon-ref pins an older Agent Link"
gh run list --commit "$(git rev-parse HEAD)" --json name,conclusion -q '.[] | "\(.name): \(.conclusion)"'   # every line: success
```

`release.py check` says "0.3.0 agrees everywhere and with
agentlink-v0.3.0" (that is its ok), or lists what does not. If it says Unreleased has
entries (work that landed after the changelog was folded), fold them into
0.3.0 and push, then run the checks again (the `addon-ref` pin moves with
them):

```sh
python3 scripts/release.py fold 0.3.0
git commit -am "Changelog: fold Unreleased into 0.3.0" && git push origin HEAD
```

### 3.2 Tag: the extension is built and attached by CI — **IRREVERSIBLE**

```sh
git tag -a agentlink-v0.3.0 -m "Agent Link for FreeCAD 0.3.0"
git push origin agentlink-v0.3.0
sleep 15; gh run watch "$(gh run list --workflow=mcpb-release.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status
```

`.github/workflows/mcpb-release.yml` checks the tag against every version
(`scripts/release.py check --tag`), clones every add-on at its pin, runs
the launcher test, builds `dist/freecad-agentlink.mcpb`, runs the privacy
check on it and only then creates the release `agentlink-v0.3.0` with the
file attached. The README's download link
(`releases/latest/download/freecad-agentlink.mcpb`) points at it from then
on. Put the changelog's section in as the release notes:

```sh
awk '/^## \[0\.3\.0\] /{f=1; next} /^## /{if (f) exit} f' CHANGELOG.md > notes.md
gh release edit agentlink-v0.3.0 --notes-file notes.md
```

### 3.3 PyPI (`agentlink-freecad`) — **IRREVERSIBLE**

```sh
rm -rf dist && uv build
rm -rf /tmp/sdist-check && mkdir /tmp/sdist-check && tar -xzf dist/agentlink_freecad-0.3.0.tar.gz -C /tmp/sdist-check
python3 .github/privacy/check.py dist/
python3 .github/privacy/check.py /tmp/sdist-check
uvx twine check dist/*
uv publish dist/agentlink_freecad-0.3.0*
```

`uv publish` asks for credentials: user `__token__`, password a PyPI API
token (pypi.org, Account settings, API tokens; the first upload needs an
account-wide token, later ones a token for this project). Then check that
https://pypi.org/project/agentlink-freecad/ shows the README and that
`uvx agentlink-freecad --version` prints `agentlink-freecad 0.3.0`.

### 3.4 MCP Registry (`server.json`) — **IRREVERSIBLE**

After PyPI has the package (the registry checks the README's
`mcp-name` line on PyPI):

```sh
mcp-publisher login github
mcp-publisher publish
```

Run from the clone's top folder (it reads `server.json`). `login github`
opens GitHub's device sign-in for the `io.github.jamesK1000011` namespace.
Check:
`curl -s "https://registry.modelcontextprotocol.io/v0/servers?search=agentlink-freecad"`.

## 4. FreeCAD Addon Index — **IRREVERSIBLE** once merged

Submissions go through the Addon Index's issue form (FreeCAD's Addon
Academy, "Publishing to the Index"): https://github.com/FreeCAD/Addons/issues/new/choose,
type **Addon - Addition**, one issue per add-on. Agent Link first: Tutor
depends on it. Python dependencies must be ones the Index allows (numpy;
scipy as optional). Add the topics `freecad` and `addon` to each repository
first:

```sh
for r in AgentLink-FreeCAD Workshop-FreeCAD Texturizer-FreeCAD ScanRuler-FreeCAD Tutor-FreeCAD; do
  gh repo edit "jamesK1000011/$r" --add-topic freecad --add-topic addon
done
```

In each issue give the repository, the branch `main` and the tag. The
names are the Mod folders the Claude extension installs into, so an
install from either place is the same add-on:

| Name | Repository | Tag |
|---|---|---|
| AgentLink | https://github.com/jamesK1000011/AgentLink-FreeCAD | agentlink-v0.3.0 |
| Workshop | https://github.com/jamesK1000011/Workshop-FreeCAD | v0.4.0 |
| Texturizer | https://github.com/jamesK1000011/Texturizer-FreeCAD | v0.4.0 |
| ScanRulerFC | https://github.com/jamesK1000011/ScanRuler-FreeCAD | v0.5.0 |
| Tutor | https://github.com/jamesK1000011/Tutor-FreeCAD | v0.2.0 |

If a maintainer asks for the entry itself, the one proposed for the
catalog (`AddonCatalog.json` in FreeCAD/FreeCAD-addons; check the keys
against the file's current entries) is, for Agent Link:

```json
"AgentLink": [
  {
    "repository": "https://github.com/jamesK1000011/AgentLink-FreeCAD",
    "git_ref": "main",
    "branch_display_name": "main"
  }
]
```

and in the older `.gitmodules` form:

```
[submodule "AgentLink"]
	path = AgentLink
	url = https://github.com/jamesK1000011/AgentLink-FreeCAD
	branch = main
```

The others the same, with their name and repository from the table.

## 5. After

- Client docs: once PyPI has 0.3.0, `uvx --from git+…` becomes
  `uvx agentlink-freecad` in `docs/clients/` and the release test's
  `COMMAND` (the Cursor and VS Code install links change with it).
- ScanRuler's `freecad-spike` extension channel retires: the copy of the
  launcher kept there for installed extensions to move over goes once no
  installed copy reads it.
- A later release: the version in `package.xml` (with its date),
  `pyproject.toml`, `server.json` (both places), `agentlink/server.py` and
  `build_server`'s default in `agentlink/tools.py`; then
  `python3 scripts/release.py manifest` and
  `python3 scripts/release.py fold X.Y.Z`. The tests
  (`tests/test_release_tools.py`) fail while any of them disagree.

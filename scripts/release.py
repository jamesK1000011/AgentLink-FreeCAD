# SPDX-License-Identifier: LGPL-2.1-or-later
"""Release helpers for Agent Link for FreeCAD, in plain Python (no FreeCAD).

    python3 scripts/release.py check [--tag agentlink-vX.Y.Z]
        Every place the version is written agrees (package.xml, pyproject.toml,
        server.json and its package, the server's VERSION, build_server's
        default, the Claude extension's manifest, the newest dated changelog
        section), package.xml's date is that section's, and the extension's
        manifest is sound. With --tag, the tag names that version too.
        Exit 1 with the problems listed.

    python3 scripts/release.py fold X.Y.Z [YYYY-MM-DD]
        The changelog's Unreleased entries go into "## [X.Y.Z] - date" (made,
        or added to when it is there already: entries that came in after the
        fold), same-named subsections merged; an empty Unreleased stays on
        top. package.xml's date becomes that date (today by default).

    python3 scripts/release.py manifest
        Rewrite packaging/mcpb/manifest.json's version (package.xml's) and its
        tools (the lean list: the groups listed from the start, and the
        launcher's agentlink_update).
"""
import ast
import datetime
import json
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MANIFEST = os.path.join(ROOT, "packaging", "mcpb", "manifest.json")
LAUNCHER = os.path.join(ROOT, "packaging", "mcpb", "server", "index.js")
BUILD = os.path.join(ROOT, "packaging", "mcpb", "build.sh")
TAG_PREFIX = "agentlink-v"
SEMVER = r"\d+\.\d+\.\d+"


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _one(rx, text, what):
    m = re.search(rx, text, re.M)
    return m.group(1) if m else "(no %s)" % what


def changelog_sections(text=None):
    """[(heading title, version or None, date or None, start, end)] for each
    "## " section of CHANGELOG.md, in order."""
    text = _read("CHANGELOG.md") if text is None else text
    heads = list(re.finditer(r"(?m)^## (.+)$", text))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        v = re.match(r"\[?(%s)\]?\s*(?:-|—)\s*(\d{4}-\d{2}-\d{2})" % SEMVER, m.group(1))
        out.append((m.group(1).strip(), v.group(1) if v else None, v.group(2) if v else None, m.start(), end))
    return out


def released(text=None):
    """(version, date) of the newest dated changelog section, or (None, None)."""
    for _, v, d, _, _ in changelog_sections(text):
        if v:
            return v, d
    return None, None


def versions():
    """{where: version} for every place Agent Link's version is written."""
    pkg = _read("package.xml")
    reg = json.loads(_read("server.json"))
    out = {
        "package.xml": _one(r"<version>([^<]+)</version>", pkg, "version"),
        "pyproject.toml": _one(r'^version = "([^"]+)"', _read("pyproject.toml"), "version"),
        "server.json": reg.get("version"),
        "agentlink/server.py VERSION": _one(r'^VERSION = "([^"]+)"', _read("agentlink", "server.py"), "VERSION"),
        "agentlink/tools.py build_server": _one(r'^def build_server\(.*?version="([^"]+)"', _read("agentlink", "tools.py"), "default"),
        "packaging/mcpb/manifest.json": json.loads(_read("packaging", "mcpb", "manifest.json")).get("version"),
        "CHANGELOG.md newest release": released()[0],
    }
    for i, p in enumerate(reg.get("packages", [])):
        out["server.json packages[%d]" % i] = p.get("version")
    return out


def lean_tools():
    """The tools listed from the start: every tool of a lean group."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import tool_summary
    finally:
        sys.path.pop(0)
    return sorted(n for g in tool_summary.groups().values() if g["lean"] for n in g["tools"])


def tool_descriptions(names):
    """{name: first sentence of its description} from the Tool(...) calls."""
    want, out = set(names), {}
    for d, _, fs in os.walk(os.path.join(ROOT, "agentlink")):
        for f in fs:
            if not f.endswith(".py"):
                continue
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                fn = getattr(node, "func", None)
                if not (isinstance(node, ast.Call) and (getattr(fn, "id", None) == "Tool" or getattr(fn, "attr", None) == "Tool")):
                    continue
                if len(node.args) < 2 or not isinstance(node.args[0], ast.Constant) or node.args[0].value not in want:
                    continue
                try:
                    desc = ast.literal_eval(node.args[1])
                except ValueError:
                    continue
                out[node.args[0].value] = first_sentence(desc)
    return out


def first_sentence(text):
    m = re.match(r"(.+?[.!?])(?:\s|$)", " ".join(text.split()))
    return m.group(1) if m else " ".join(text.split())


def launcher_tool():
    """(name, first sentence) of the tool the extension's launcher adds."""
    js = open(LAUNCHER, encoding="utf-8").read()
    m = re.search(r"const UPDATE_TOOL = \{\s*name: '([^']+)',\s*description: '((?:[^'\\]|\\.)*)'", js)
    if not m:
        return None
    return m.group(1), first_sentence(m.group(2).replace("\\'", "'"))


def manifest_tools():
    names = lean_tools()
    desc = tool_descriptions(names)
    tools = [{"name": n, "description": desc.get(n, "")} for n in names]
    extra = launcher_tool()
    if extra:
        tools.append({"name": extra[0], "description": extra[1]})
    return tools


def build_asset_name():
    """The file name build.sh writes by default (and the release attaches)."""
    m = re.search(r'OUT=\$\{2:-\$HERE/([^}]+)\}', open(BUILD, encoding="utf-8").read())
    return m.group(1) if m else None


USER_CONFIG_TYPES = {"string", "number", "boolean", "directory", "file"}


def manifest_problems(m=None):
    """What the Claude extension's manifest gets wrong, as sentences."""
    m = json.loads(_read("packaging", "mcpb", "manifest.json")) if m is None else m
    bad = []
    for key in ("manifest_version", "name", "display_name", "version", "description", "author", "server", "icon"):
        if not m.get(key):
            bad.append("manifest: %s missing" % key)
    if m.get("name") and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", m["name"]):
        bad.append("manifest: name %r is not lower-case words joined by -" % m["name"])
    if not re.fullmatch(SEMVER, str(m.get("version", ""))):
        bad.append("manifest: version %r is not X.Y.Z" % m.get("version"))
    if not (m.get("author") or {}).get("name"):
        bad.append("manifest: author.name missing")
    icon = m.get("icon")
    if icon and not os.path.isfile(os.path.join(ROOT, "packaging", "mcpb", icon)):
        bad.append("manifest: icon %s is not in packaging/mcpb" % icon)
    if icon and not icon.lower().endswith(".png"):
        bad.append("manifest: icon %s is not a PNG" % icon)
    srv = m.get("server") or {}
    entry = srv.get("entry_point", "")
    if srv.get("type") != "node":
        bad.append("manifest: server.type is %r, the launcher is node" % srv.get("type"))
    if not os.path.isfile(os.path.join(ROOT, "packaging", "mcpb", entry)):
        bad.append("manifest: server.entry_point %s is not in packaging/mcpb" % entry)
    cfg = srv.get("mcp_config") or {}
    if cfg.get("command") != "node" or "${__dirname}/" + entry not in (cfg.get("args") or []):
        bad.append("manifest: mcp_config does not run node ${__dirname}/%s" % entry)
    uc = m.get("user_config") or {}
    for ref in re.findall(r"\$\{user_config\.([^}]+)\}", json.dumps(cfg)):
        if ref not in uc:
            bad.append("manifest: mcp_config uses user_config.%s, which is not declared" % ref)
    for k, v in uc.items():
        if v.get("type") not in USER_CONFIG_TYPES:
            bad.append("manifest: user_config.%s type %r" % (k, v.get("type")))
        for f in ("title", "description"):
            if not v.get(f):
                bad.append("manifest: user_config.%s has no %s" % (k, f))
        if v.get("required"):
            bad.append("manifest: user_config.%s is required: the extension must start with nothing set" % k)
        d = v.get("default")
        if d is not None:
            ok = {"boolean": isinstance(d, bool), "number": isinstance(d, (int, float)) and not isinstance(d, bool)}.get(v.get("type"), isinstance(d, str))
            if not ok:
                bad.append("manifest: user_config.%s default %r is not a %s" % (k, d, v.get("type")))
    for k in uc:
        if "${user_config.%s}" % k not in json.dumps(cfg):
            bad.append("manifest: user_config.%s is never passed to the server" % k)
    tools = m.get("tools")
    if not isinstance(tools, list) or not tools:
        bad.append("manifest: tools missing")
    else:
        names = [t.get("name") for t in tools]
        want = [t["name"] for t in manifest_tools()]
        if names != want:
            bad.append("manifest: tools %s are not the lean list %s (python3 scripts/release.py manifest)"
                       % (sorted(set(names) ^ set(want)) or "out of order", want))
        for t in tools:
            if not t.get("description"):
                bad.append("manifest: tool %s has no description" % t.get("name"))
        if m.get("tools_generated") is not True:
            bad.append("manifest: tools_generated should be true (the list grows with tool_groups and add-ons)")
    plat = ((m.get("compatibility") or {}).get("platforms")) or []
    if not plat or set(plat) - {"darwin", "win32", "linux"}:
        bad.append("manifest: compatibility.platforms %r" % plat)
    return bad


def problems(tag=None):
    bad = []
    vs = versions()
    want = vs["package.xml"]
    if not re.fullmatch(SEMVER, want or ""):
        bad.append("package.xml version %r is not X.Y.Z" % want)
    elif int(want.split(".")[0]) >= 1:
        bad.append("package.xml version %s: Agent Link is not at 1.0 yet" % want)
    for where, v in vs.items():
        if v != want:
            bad.append("%s says %s, package.xml %s" % (where, v, want))
    date = _one(r"<date>([^<]+)</date>", _read("package.xml"), "date")
    rel_v, rel_d = released()
    if rel_v == want and rel_d != date:
        bad.append("package.xml date %s, the changelog's %s section %s" % (date, want, rel_d))
    secs = changelog_sections()
    if not secs or not re.fullmatch(r"\[?Unreleased\]?", secs[0][0]):
        bad.append("CHANGELOG.md: the first section is not Unreleased")
    if tag is not None:
        if not tag.startswith(TAG_PREFIX) or tag[len(TAG_PREFIX):] != want:
            bad.append("tag %s does not name %s%s" % (tag, TAG_PREFIX, want))
        elif secs and re.search(r"(?m)^- ", _read("CHANGELOG.md")[secs[0][3]:secs[0][4]]):
            bad.append("CHANGELOG.md: Unreleased has entries; run python3 scripts/release.py fold %s and commit before tagging" % want)
    bad += manifest_problems()
    return bad


def _subsections(body):
    """(lead text, [(### title, text)]) of a changelog section's body."""
    parts = re.split(r"(?m)^### (.+)\n", body)
    lead, subs = parts[0], []
    for i in range(1, len(parts), 2):
        subs.append((parts[i].strip(), parts[i + 1]))
    return lead, subs


def _merge(subs):
    order, merged = [], {}
    for t, text in subs:
        text = text.strip("\n")
        if t not in merged:
            order.append(t)
            merged[t] = text
        elif text:
            merged[t] = (merged[t] + "\n" + text).strip("\n")
    return [(t, merged[t]) for t in order if merged[t].strip()]


def fold_text(text, version, date):
    secs = changelog_sections(text)
    if not secs or not re.fullmatch(r"\[?Unreleased\]?", secs[0][0]):
        raise SystemExit("CHANGELOG.md: the first section is not Unreleased")
    _, _, _, us, ue = secs[0]
    u_body = text[us:ue].split("\n", 1)[1] if "\n" in text[us:ue] else ""
    u_lead, u_subs = _subsections(u_body)
    old = next((s for s in secs[1:] if s[1] == version), None)
    if old:
        o_body = text[old[3]:old[4]].split("\n", 1)[1]
        o_lead, o_subs = _subsections(o_body)
        subs = _merge(u_subs + o_subs)
        tail = text[old[4]:]
        between = text[ue:old[3]]
    else:
        subs = _merge(u_subs)
        tail = text[ue:]
        between = ""
    body = "".join("### %s\n\n%s\n\n" % (t, s) for t, s in subs)
    new = "## [Unreleased]\n\n## [%s] - %s\n\n%s" % (version, date, body)
    return text[:us] + new + between + tail.lstrip("\n") if tail.strip() else text[:us] + new.rstrip("\n") + "\n"


def fold(version, date=None):
    if not re.fullmatch(SEMVER, version):
        raise SystemExit("version %r is not X.Y.Z" % version)
    date = date or datetime.date.today().isoformat()
    p = os.path.join(ROOT, "CHANGELOG.md")
    _write(p, fold_text(_read("CHANGELOG.md"), version, date))
    rel = released()
    px = os.path.join(ROOT, "package.xml")
    _write(px, re.sub(r"<date>[^<]+</date>", "<date>%s</date>" % rel[1], _read("package.xml"), count=1))
    return rel


def write_manifest():
    m = json.loads(_read("packaging", "mcpb", "manifest.json"))
    m["version"] = versions()["package.xml"]
    m["tools"] = manifest_tools()
    m["tools_generated"] = True
    _write(MANIFEST, json.dumps(m, indent=2, ensure_ascii=False) + "\n")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "check":
        tag = rest[rest.index("--tag") + 1] if "--tag" in rest else None
        bad = problems(tag)
        for b in bad:
            print("release:", b)
        if not bad:
            print("release: %s agrees everywhere%s" % (versions()["package.xml"], " and with " + tag if tag else ""))
        return 1 if bad else 0
    if cmd == "fold" and rest:
        v, d = fold(rest[0], rest[1] if len(rest) > 1 else None)
        print("CHANGELOG.md: Unreleased folded into %s (%s); package.xml date %s" % (v, d, d))
        return 0
    if cmd == "manifest":
        write_manifest()
        print("packaging/mcpb/manifest.json: version and tools rewritten")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

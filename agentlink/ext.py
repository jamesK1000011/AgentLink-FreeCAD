# SPDX-License-Identifier: LGPL-2.1-or-later
# Extensions: add-ons of their own that build on Agent Link, loaded when they
# are installed (a folder beside this one in FreeCAD's Mod folder, or on the
# Python path) and left out without a word when they are not. Each is a
# module with install(server, session); it may add tools, a check before
# each call (server.guard) and a wrapper round each call (server.call), and
# use the hooks below. Nothing here knows what an extension does.
#
# Hooks an extension may use:
#   panel_widgets   factories(panel) -> a widget shown above the panel's tabs
#                   (refresh() on it, if it has one, each second)
#   before_restart  fn(session), called before app_restart saves and quits
#   session.keep_doc       True: the window link does not move the session to
#                          the document the person brings to the front
#   session.window_quiet   True: the live echo leaves the window alone (the
#                          activity list still gets each call)
#   session.activity_tag   text put before each call in the activity list
#   session.by             who the call in hand is for: "agent" (a call from
#                          the agent), "person" (a click in Agent Link's panel
#                          or an add-on dock it hosts); add-ons read it, e.g.
#                          to label a checkpoint "My checkpoint"

import os
import re
import sys

# Extensions named here or in AGENTLINK_EXTENSIONS, and every package
# named agentlink_… in a folder AgentLink… beside this add-on.
NAMES = []

panel_widgets = []
before_restart = []
loaded = {}


# An add-on installed from a repository whose root is the add-on (its
# package.xml at the top) carries this file, naming the repository.
MARK = ".agentlink-extension"


def _addon_name(root):
    """The add-on's folder name in Mod: package.xml's <name>, letters and
    digits only, or None when the repository's root is not an add-on."""
    import re

    try:
        with open(os.path.join(root, "package.xml"), encoding="utf-8") as f:
            m = re.search(r"<name>([^<]+)</name>", f.read())
    except OSError:
        return None
    name = re.sub(r"[^A-Za-z0-9]", "", m.group(1)) if m else ""
    return name or None


def _paths():
    """Mod folders beside this add-on's put on the path; the agentlink_…
    packages found in them."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mod = os.path.dirname(here)
    found = []
    try:
        for name in sorted(os.listdir(mod)):
            p = os.path.join(mod, name)
            if p == here or not os.path.isdir(p):
                continue
            # AgentLink… folders, and add-ons app_extensions installed from a
            # repository whose root is the add-on (marked when installed).
            if not (name.startswith("AgentLink") or os.path.isfile(os.path.join(p, MARK))):
                continue
            if p not in sys.path:
                sys.path.append(p)
            for pkg in sorted(os.listdir(p)):
                if pkg.startswith("agentlink_") and os.path.isfile(os.path.join(p, pkg, "__init__.py")):
                    found.append(pkg)
    except OSError:
        pass
    return found


def install_all(server, session):
    names = []
    for n in NAMES + [n.strip() for n in os.environ.get("AGENTLINK_EXTENSIONS", "").split(",") if n.strip()] + _paths():
        if n not in names:
            names.append(n)
    for name in names:
        try:
            mod = __import__(name.strip(), fromlist=["install"])
        except ImportError:
            continue
        try:
            mod.install(server, session)
            loaded[name] = getattr(mod, "VERSION", "?")
        except Exception as e:
            sys.stderr.write(f"Agent Link: extension {name} did not load ({e})\n")
    return dict(loaded)


def restarting(session):
    for fn in list(before_restart):
        try:
            fn(session)
        except Exception as e:
            sys.stderr.write(f"Agent Link: before restart ({e})\n")


# ---- getting extensions: from a git repository, with this machine's own
# git sign-in (no token passes through here). Which repositories is a local
# setting (Mod/AgentLink ExtensionRepos: "owner/repo[@branch]", comma
# separated); each one's top-level folders named AgentLink… are copied into
# FreeCAD's Mod folder beside this add-on.

PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"


def repos():
    import FreeCAD

    raw = FreeCAD.ParamGet(PREFS).GetString("ExtensionRepos", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


# What an extension's text may be (red team 4, R4-13): "owner/repo" or
# "https://github.com/owner/repo(.git)", then "@branch". Nothing else
# reaches git: no other scheme or host, no local path, no text that starts
# with "-" (git would read it as an option).
_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
_REPO = r"[A-Za-z0-9_][A-Za-z0-9._-]{0,99}"
_SPEC = re.compile(rf"^(?:https://github\.com/)?({_OWNER})/({_REPO}?)(?:\.git)?$")
_BRANCH = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._/-]{0,199}$")


def branch_ok(b):
    """True for a branch name that git takes as a name only."""
    return bool(_BRANCH.match(b or "")) and ".." not in b and "//" not in b and not b.endswith(("/", ".", ".lock")) and "@{" not in b


def parse(spec):
    """(owner/repo, branch, https URL) of an extension's text; ValueError
    with the reason when it is not one."""
    text = str(spec or "").strip()
    repo, at, branch = text.partition("@")
    branch = branch if at else "main"
    m = _SPEC.match(repo)
    if not m or m.group(2) in ("", ".", "..") or m.group(2).endswith("."):
        raise ValueError(f"repo: owner/repo or https://github.com/owner/repo, not {text[:80]!r}")
    if not branch_ok(branch):
        raise ValueError(f"branch: a branch name (letters, digits, . _ - /; not first a - or .), not {branch[:80]!r}")
    name = f"{m.group(1)}/{m.group(2)}"
    return name, branch, f"https://github.com/{name}.git"


def _git():
    import shutil

    for g in (shutil.which("git"), "/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git"):
        if g and os.path.exists(g):
            return g
    return None


def sync(cache=None):
    """Each listed repository fetched (cloned, or brought up to date) and
    its AgentLink… folders copied in beside this add-on, or, when the
    repository's root is an add-on (package.xml), the whole of it as
    Mod/<its name>. Returns what was
    installed and what could not be reached, and why."""
    import shutil
    import subprocess

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mod = os.path.dirname(here)
    cache = cache or os.path.expanduser("~/.config/freecad-agentlink/ext")
    os.makedirs(cache, exist_ok=True)
    git = _git()
    out = {"installed": [], "failed": []}
    if not repos():
        return {**out, "note": "No extension repositories set (ExtensionRepos)."}
    if git is None:
        return {**out, "failed": [{"repo": r, "why": "git is not installed on this computer"} for r in repos()]}
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # never wait on a password prompt
    for spec in repos():
        try:
            repo, branch, url = parse(spec)
        except ValueError as e:
            out["failed"].append({"repo": spec[:120], "why": f"not fetched: {e}"})
            continue
        dest = os.path.join(cache, repo.replace("/", "__"))
        try:
            # "--": what follows is a repository, a branch or a folder, never an option.
            if os.path.isdir(os.path.join(dest, ".git")):
                cmds = [[git, "-C", dest, "fetch", "--depth", "1", "--", url, branch], [git, "-C", dest, "reset", "--hard", "FETCH_HEAD"]]
            else:
                cmds = [[git, "clone", "--depth", "1", "-b", branch, "--", url, dest]]
            for c in cmds:
                r = subprocess.run(c, capture_output=True, text=True, timeout=120, env=env)
                if r.returncode != 0:
                    raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else f"git exited {r.returncode}")
            sha = subprocess.run([git, "-C", dest, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=30).stdout.strip()
            tops = [n for n in sorted(os.listdir(dest)) if n.startswith("AgentLink") and os.path.isdir(os.path.join(dest, n))]
            for n in tops:
                target = os.path.join(mod, n)
                if os.path.abspath(target) == os.path.abspath(here):
                    continue
                shutil.copytree(os.path.join(dest, n), target, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__", "tests"))
            root_name = None if tops else _addon_name(dest)
            if root_name:
                # The repository is the add-on: installed as Mod/<its name>,
                # never over a folder some other add-on owns.
                target = os.path.join(mod, root_name)
                mark = os.path.join(target, MARK)
                if os.path.isdir(target) and not os.path.isfile(mark):
                    raise RuntimeError(f"Mod/{root_name} is already there and was not installed from {repo}: left as it is")
                shutil.copytree(dest, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", ".github", "__pycache__", "tests"))
                with open(mark, "w", encoding="utf-8") as f:
                    f.write(spec + "\n")
                tops = [root_name]
            if not tops:
                raise RuntimeError("no AgentLink… folder and no package.xml at its root: not an add-on")
            out["installed"].append({"repo": spec, "commit": sha, "folders": tops})
        except Exception as e:
            out["failed"].append({"repo": spec, "why": str(e)[:300]})
    return out


def tools(session):
    from .protocol import Tool, ToolError

    def app_extensions(a):
        import FreeCAD

        act = a.get("action", "list")
        if act == "list":
            return {"repos": repos(), "loaded": dict(loaded), "note": "Loaded ones run in this FreeCAD; a newly installed one loads after app_restart (window) or agentlink_update (hidden)."}
        if act in ("add", "remove"):
            r = str(a.get("repo") or "").strip()
            if not r:
                raise ToolError("invalid_input", "repo: owner/repo, with @branch if not main.")
            if act == "add":
                # An extension is code FreeCAD runs at start: whose to add is
                # the person's call. The approval is approve_code, which the
                # person sets in the client's tool permissions
                # (agentlink/approvals.py). A typed confirm is not taken.
                from . import approvals

                try:
                    repo, branch, _url = parse(r)
                except ValueError as e:
                    raise ToolError("invalid_input", f"{e}. Nothing was changed.")
                owner = repo.split("/")[0]
                try:
                    ok = approvals.ask("extension", r, f"Add the extension {r} (code that FreeCAD runs at each start)",
                                       [f"Repository: {r}", "An extension is code that FreeCAD runs at each start.", "Approve only a repository that you know and trust."],
                                       shown={"source": f"https://github.com/{repo}", "version": f"branch {branch}; sync takes its newest commit",
                                              "author": owner})
                except approvals.Refused as e:
                    raise ToolError(e.code, e.message)
                if not ok.get("ok"):
                    return {**ok, "changed": False, "repos": repos()}
            have = repos()
            have = (have + [r]) if act == "add" and r not in have else [x for x in have if x != r]
            FreeCAD.ParamGet(PREFS).SetString("ExtensionRepos", ",".join(have))
            # Written to disk now: a hidden FreeCAD that is stopped for an
            # update never saves its settings, and the list would be lost.
            try:
                FreeCAD.saveParameter()
            except Exception:  # noqa: BLE001 — an older FreeCAD: saved at exit as before
                pass
            return {"repos": have}
        if act == "sync":
            return sync()
        raise ToolError("invalid_input", "action: list, add, remove, sync.")

    return [Tool("app_extensions",
                 "Extensions to Agent Link kept in git repositories: list (set and loaded), add { repo: owner/repo[@branch] } (or https://github.com/owner/repo; other text is refused) — an extension is code FreeCAD runs, so adding one is the person's call: the first call answers pending with the approve_code arguments; call approve_code with them (the client asks the person first when they set it to \"ask first\"); then call again / remove { repo }, sync (the listed ones fetched with this computer's own git sign-in and installed beside Agent Link; then app_restart). The list is a local setting only the person adds to.",
                 {"type": "object", "properties": {"action": {"type": "string", "enum": ["list", "add", "remove", "sync"]}, "repo": {"type": "string"}}, "required": [], "additionalProperties": False},
                 app_extensions, group="core")]

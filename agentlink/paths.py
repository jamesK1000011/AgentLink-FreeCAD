# SPDX-License-Identifier: LGPL-2.1-or-later
# Where a tool may read and write on the person's computer. Every file path
# an agent passes in goes through here before the tool runs: an agent can be
# talked into things by what it reads (a web page, a document), so the add-on
# keeps it away from credentials, hidden settings, scripts and the system,
# whatever it is asked. Reading is an allow list (read_refusal): the
# person's ordinary folders in the home, the session's folder, the
# temporary folders, FreeCAD's folders and a few system places (apps, other
# disks, fonts); writing stays in the person's home, the session's folder or
# the temporary folder, as model, drawing, data or G-code files.

import os

from .protocol import ToolError

# Fields that hold a file path (or a list of them).
PATH_KEYS = {"path", "saveAs", "file", "files", "kinematics", "template", "font", "export", "import", "pattern", "image",
             # red team, 2026-11-18: files and folders read by other names
             "points_file", "profiles_file", "folder"}
# Fields that are files only for some tools
PATH_KEYS_FOR = {"ifc_diff": {"a", "b"}}
# Fields that are always a file the call writes, for any tool ("export": a
# file to export to; "saveAs": a copy saved under another name).
WRITE_KEYS = {"export", "saveAs"}
# An add-on's own path fields, nested ones too (red team 3, R3-10): for each
# of its tools, {"read": [...], "write": [...]}, each a dotted key such as
# "kicadPcb", "texture.file" or "profiles.*" ("*": every value of an object,
# every item of a list). declare_keys() adds them; guard() checks them.
DECLARED_KEYS = {}
# Tools where "path" is a curve in the model, not a file.
GEOMETRIC = {"part_sweep", "pd_pipe", "draft_link_array", "draft_array", "bim_frame", "bim_fence", "bim_truss"}
# Tools that write their path (the rest read theirs).
WRITERS = {"export", "export_file", "bim_export", "doc_save", "robot_export", "meshobj_unwrap", "meshobj_export", "cam_sim", "cam_post",
           "sheet_export", "sheet_chart", "scad_export", "view_render", "view_snapshot", "points_export",
           "td_export", "fea_export", "cam_template_export", "fea_chart", "insp_export", "ifc_save", "asm_export", "asm_motion", "steps_render", "window_snapshot", "doc_graph"}
SECRET_PARTS = {".ssh", ".aws", ".gnupg", ".kube", ".docker", ".config", ".netrc", ".git", ".password-store", "keychains", "Keychains",
                ".zshrc", ".bashrc", ".profile", ".bash_profile", ".zprofile", ".env"}
NEVER_WRITE_EXT = {".sh", ".bash", ".zsh", ".command", ".tool", ".py", ".pyc", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".php",
                   ".app", ".plist", ".dylib", ".so", ".dll", ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".scpt", ".applescript", ".workflow",
                   ".service", ".desktop", ".kext", ".pkg", ".dmg", ".jar", ".FCMacro", ".fcmacro",
                   # red team, 2026-11-18: what Python loads as code beside .py
                   ".pth", ".pyz", ".pyd", ".whl", ".egg"}


_SECRET_FOLDED = {x.casefold() for x in SECRET_PARTS}


def _real(p):
    return os.path.realpath(os.path.expanduser(p))


def _parts(p):
    return [x for x in p.replace("\\", "/").split("/") if x]


# Agent Link's own state in its home (~/AgentLink, or AGENTLINK_HOME): the
# settings, the memory stop mark, the add-on sources, the hidden FreeCAD's
# mark, the launch mark, the extension state, the approvals log and the
# rest (red team 2, R2-13). No tool writes them. The home is the default
# output folder too (outDir ~/AgentLink on the Mac), so there only these
# are refused: the state files by name at its top level (and their ".tmp"
# and other "<name>." copies), and the state folders. Any other file at the
# top (an export, a batch "writeTo" file, a report) is ordinary output.
# ports/ is open (port drafts). With an output folder outside the home,
# all of the home but ports/ is refused.
STATE_FILES = {"settings.json", "settings-log.jsonl", "approvals.log", "memory-stop.json", "memory-jobs.json",
               "addon-sources.json", "addon_catalog.json", "hidden.json", "launch.json", "extensions.json",
               "heartbeat.json", "heavy-call.json", "call-checkpoint.json", "heavy-tools.json", "machine.json", "queue.json", "queue.lock",
               "versions.json", "watchdog.log", "macros-approved.json", "applies_meter.json", "companions.json",
               ".companions.json", ".hidden-restart", ".saving",
               # printer settings with API keys (mode 0600, an add-on keeps them)
               "printers.json",
               # the output folder's own record (agentlink/outputs.py)
               "outputs.jsonl", ".outputs-clean.json"}
STATE_DIRS = {"cookbooks", "cookbook-scans", "usage", "crash", "addons-previous", "stopped", "unsaved",
              "tests", "install", "addonmanager", "extensionrepos", "settings",
              # run marks of a server started with --own (keep.runtime)
              "own"}
OPEN_DIRS = {"ports"}
# State no tool reads either: the running jobs' tokens (agentlink/memguard.py)
# and the printers file with its API keys, in the home.
NEVER_READ = {"memory-jobs.json", "printers.json"}
# Never read in any folder: the old name of that printers file (API keys).
NEVER_READ_ANYWHERE = {".agentlink-printers.json"}
# The output folder's own record: no tool writes it in any output folder.
OUT_STATE = {"outputs.jsonl", ".outputs-clean.json"}


def _state_name(name):
    """The state file a top-level name is (or a copy of, "<name>.tmp"), or None."""
    n = name.casefold()
    for x in STATE_FILES:
        if n == x or n.startswith(x + "."):
            return x
    return None


def _homes():
    out = []
    for h in (os.environ.get("AGENTLINK_HOME"), "~/AgentLink"):
        if h:
            r = _real(h)
            if r != "/" and r not in out:
                out.append(r)
    return out


def agentlink_state(real, out_dir=None):
    """What of Agent Link's own state the real path is, or None."""
    rf = real.casefold()
    out_real = _real(out_dir).casefold() if out_dir else None
    for home in _homes():
        h = home.casefold()
        if not (rf == h or rf.startswith(h.rstrip("/") + "/")):
            continue
        rel = [x.casefold() for x in _parts(rf[len(h):])]
        if not rel:
            return "its home folder"
        if rel[0] in OPEN_DIRS:
            continue
        if rel[0] in STATE_DIRS:
            return f"the {rel[0]} folder"
        if len(rel) == 1 and _state_name(rel[0]):
            return rel[0]
        in_out = bool(out_real and (rf == out_real or rf.startswith(out_real.rstrip("/") + "/")))
        if not in_out:
            return "its home folder, not the output folder"
    return None


# Reads are an allow list (red team 4, R4-1). In the home: every folder but
# the hidden ones (.ssh, .config, .zsh_history, .git-credentials …) and
# ~/Library, where apps keep their settings and tokens. Of ~/Library only
# these folders are open: FreeCAD's own, the slicers' presets (OrcaSlicer,
# Bambu Studio, PrusaSlicer: agentlink-orcaslicer reads them) and the
# person's fonts.
LIBRARY_READ = (("application support", "freecad"), ("application support", "orcaslicer"),
                ("application support", "bambustudio"), ("application support", "prusaslicer"),
                ("fonts",), ("preferences", "freecad"), ("caches", "freecad"))
# Outside the home, the places a tool reads: apps (FreeCAD's and the
# slicers' resources), other disks, the shared folder and the system fonts.
# The session folder, the temporary folders, FreeCAD's own folders and the
# add-on's own folder are open too (read_roots).
OUTSIDE_READ = ("/Applications", "/Volumes", "/Users/Shared", "/Library/Fonts", "/System/Library/Fonts",
                "/usr/share", "/usr/local/share", "/opt/homebrew/share", "/media", "/mnt")
# Claude's own settings (other MCP servers' keys): never read or written,
# in any folder.
NEVER_ANYWHERE = {"claude_desktop_config.json"}


def _under(real, root):
    r = root.casefold().rstrip("/") or "/"
    rf = real.casefold()
    return rf == r or rf.startswith(r + "/")


def freecad_dirs():
    """FreeCAD's own folders (its resources, its install, the person's
    FreeCAD data and macro folders), when FreeCAD is loaded; and the folder
    the add-on itself is in."""
    import sys

    out = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    fc = sys.modules.get("FreeCAD")
    for fn in ("getResourceDir", "getHomePath", "getUserAppDataDir", "getUserMacroDir"):
        try:
            d = getattr(fc, fn)() if fc is not None else None
        except Exception:  # noqa: BLE001 - a stand-in FreeCAD in tests
            d = None
        if isinstance(d, str) and d.strip():
            out.append(d)
    return [_real(d) for d in out if _real(d) != "/"]


def read_roots(out_dir):
    """The open places outside the home rule: the session folder, the
    temporary folders, FreeCAD's and the add-on's folders."""
    roots = [_real(out_dir)] if out_dir else []
    roots += [_real("/tmp"), _real(os.environ.get("TMPDIR", "/tmp"))] + freecad_dirs()
    # A root that is the home or holds it (a session folder of ~) opens
    # nothing of the home: the home rule decides there.
    home = _real("~")
    return [r for r in roots if r and r != "/" and not _under(home, r)]


def read_refusal(real, out_dir):
    """Why a read of the real path is refused, in words, or None."""
    open_roots = read_roots(out_dir)
    if any(_under(real, r) for r in open_roots):
        return None
    home = _real("~")
    if home != "/" and _under(real, home):
        rel = _parts(real[len(home):])
        hidden = [x for x in rel if x.startswith(".")]
        if hidden:
            return f"is in a hidden place ({hidden[0]}) — hidden files and folders in the home hold settings, keys and history; the agent does not read them"
        low = [x.casefold() for x in rel]
        if low[:1] == ["library"]:
            if any(low[1:1 + len(t)] == list(t) for t in LIBRARY_READ):
                return None
            return "is in ~/Library, where apps keep their settings and tokens — a tool reads only FreeCAD's, the slicers' and the font folders there"
        return None
    if any(_under(real, r) for r in OUTSIDE_READ):
        return None
    return "is outside the places a tool reads (the home, the session's folder, temporary folders, FreeCAD's folders, /Applications, /Volumes and the font folders)"


def check(tool, key, value, out_dir, write):
    """Refuse a path the agent should not touch; answers the path as given."""
    if not isinstance(value, str) or not value.strip():
        return value
    raw = value.strip()
    p = raw if os.path.isabs(os.path.expanduser(raw)) else os.path.join(out_dir or os.getcwd(), raw)
    real = _real(p)
    parts = _parts(real)
    # macOS disks ignore case: ~/.SSH is ~/.ssh, ~/agentlink is ~/AgentLink
    # (red team, 2026-11-18). Every refusal below compares without case.
    secret = [x for x in parts if x.casefold() in _SECRET_FOLDED]
    if secret:
        raise ToolError("invalid_input", f"{key}: {raw} is in {secret[0]} — credentials and shell settings are off limits to the agent.")
    base = os.path.basename(real).casefold()
    if base in NEVER_READ_ANYWHERE:
        raise ToolError("invalid_input", f"{key}: {raw} holds printer API keys. No tool reads or writes it.")
    if base in NEVER_ANYWHERE:
        raise ToolError("invalid_input", f"{key}: {raw} is Claude's own settings file (it holds other servers' keys). No tool reads or writes it.")
    if not write:
        why = read_refusal(real, out_dir)
        if why:
            raise ToolError("invalid_input", f"{key}: {raw} {why}.")
    for h in _homes():
        if os.path.dirname(real).casefold() == h.casefold() and base in NEVER_READ:
            raise ToolError("invalid_input", f"{key}: {raw} is Agent Link's own state. No tool reads or writes it.")
    if write:
        # The person's OKs (approved macros and cookbooks) and the installed
        # cookbooks: no tool writes there, so no write can forge an OK.
        from . import cookbook

        rf = real.casefold()
        for root in cookbook.protected():
            r = root.casefold()
            if rf == r or rf.startswith((r.rstrip("/") + "/", r + ".")):
                raise ToolError("invalid_input", f"{key}: {raw} is Agent Link's own store of the person's approvals and cookbooks. No tool writes there; write somewhere else.")
        state = agentlink_state(real, out_dir)
        if not state and out_dir and base in OUT_STATE and os.path.dirname(real).casefold() == _real(out_dir).casefold():
            state = base
        if state:
            raise ToolError("invalid_input", f"{key}: {raw} is Agent Link's own state ({state}). No tool writes there; write somewhere else.")
        home = _real("~")
        # A session folder at the disk's root (a server started from / with
        # no --out) is not taken as leave to write anywhere.
        roots = [r for r in (_real(out_dir) if out_dir else None, home, _real("/tmp"), _real(os.environ.get("TMPDIR", "/tmp"))) if r and r != "/"]
        inside = any(real == r or real.startswith(r.rstrip("/") + "/") for r in roots)
        if not inside:
            raise ToolError("invalid_input", f"{key}: {raw} — files are written in the session's folder or under your home folder, not there.")
        rel = os.path.relpath(real, home) if real.startswith(home) else ""
        hidden = [x for x in _parts(rel) if x.startswith(".")]
        out_real = _real(out_dir) if out_dir and _real(out_dir) != "/" else None
        if hidden and not (out_real and real.startswith(out_real.rstrip("/") + "/")):
            raise ToolError("invalid_input", f"{key}: {raw} is in a hidden folder ({hidden[0]}) — write it somewhere visible.")
        in_out = bool(out_real and (real == out_real or real.startswith(out_real.rstrip("/") + "/")))
        top = _parts(rel)[:1]
        if [x.casefold() for x in top] == ["library"] and not in_out:
            raise ToolError("invalid_input", f"{key}: {raw} is in ~/Library, where apps keep their settings — write it somewhere you'd look for it.")
        if os.path.basename(raw) != os.path.basename(raw).rstrip(". "):
            raise ToolError("invalid_input", f"{key}: {raw} ends in a dot or a space — give the file its own extension.")
        ext = os.path.splitext(real)[1]
        if ext.lower() == ".fcstd" and os.path.exists(real) and tool != "doc_save":
            raise ToolError("invalid_input", f"{key}: {raw} is a FreeCAD document already there — {tool} would write over it. Another name, or doc_save for the document itself.")
        if ext.lower() in {e.lower() for e in NEVER_WRITE_EXT}:
            raise ToolError("invalid_input", f"{key}: {raw} — the add-on writes models, drawings, data and G-code, never {ext} files (scripts, programs, settings).")
    return value


def local(session, p, expand=True, kind=None):
    """p in the session's folder when relative (~ expanded first, when expand).
    A path in the output folder with nothing there yet is noted, and recorded
    as the call's output if it exists after the call (agentlink/outputs.py):
    kind shot, run or export, else told by the tool and the name."""
    # "~/x" is always the person's home (paths.check reads it so): never a
    # folder named "~" in the output folder (live 17 Nov, bim_export).
    q = os.path.expanduser(p) if expand or str(p).startswith("~") else p
    q = q if os.path.isabs(q) else os.path.join(session.out_dir, q)
    return made(session, q, kind)


def made(session, p, kind=None):
    """A path a tool builds in the output folder by hand, noted as local
    notes its own; answers p."""
    from . import outputs

    return outputs.expect(session, p, kind)


def in_file(session, tool, p, key="path", expand=True):
    """A file a tool reads: local, then checked as guard checks a read."""
    p = local(session, p, expand)
    check(tool, key, p, session.out_dir, False)
    return p


def out_file(session, tool, p, ext=None, key="path", expand=True, kind=None):
    """A file a tool writes: local, ext added when it does not end so (any
    case), then checked as guard checks that tool's writes."""
    p = local(session, p, expand, kind)
    if ext and not p.lower().endswith(ext.lower()):
        p += ext
        made(session, p, kind)
    check(tool, key, p, session.out_dir, tool in WRITERS)
    return p


def valid_key(k):
    """A declared path key: dotted names, "*" for every value or item."""
    return isinstance(k, str) and bool(k) and all(x == "*" or (x and x.replace("_", "a").replace("-", "a").isalnum()) for x in k.split("."))


def declare_keys(tool, read=(), write=()):
    """An add-on tool's own path fields (dotted keys, valid_key()); answers
    the keys left out as not valid."""
    bad = []
    d = DECLARED_KEYS.setdefault(tool, {"read": set(), "write": set()})
    for kind, keys in (("read", read), ("write", write)):
        for k in keys or ():
            if valid_key(k):
                d[kind].add(k)
            else:
                bad.append(k)
    return bad


def values_at(args, key):
    """(where, value) for each value at a dotted key in the arguments."""
    out = [("", args)]
    for part in key.split("."):
        nxt = []
        for where, v in out:
            pre = where + "." if where else ""
            if part == "*":
                if isinstance(v, dict):
                    nxt += [(pre + str(k), x) for k, x in v.items()]
                elif isinstance(v, list):
                    nxt += [(pre + str(i), x) for i, x in enumerate(v)]
            elif isinstance(v, dict) and part in v:
                nxt.append((pre + part, v[part]))
            elif isinstance(v, list):
                # a list of objects: the key in each item
                nxt += [(f"{pre}{i}.{part}", x[part]) for i, x in enumerate(v) if isinstance(x, dict) and part in x]
        out = nxt
    return out


def _check_declared(name, args, out_dir):
    d = DECLARED_KEYS.get(name)
    if not d or not isinstance(args, dict):
        return
    for kind in ("read", "write"):
        for key in sorted(d[kind]):
            for where, v in values_at(args, key):
                for x in (v if isinstance(v, list) else [v]):
                    if isinstance(x, str):
                        check(name, where, x, out_dir, kind == "write")


def guard(tool, args, out_dir):
    """Every path-like field of a call checked; raises on the first refusal."""
    name = tool.name
    # Some tools make their files' names from name (slice, td_export, cut
    # and mill exports): a name with a path in it wrote anywhere.
    nm = (args or {}).get("name")
    if isinstance(nm, str) and ("/" in nm or "\\" in nm or nm.startswith("~") or nm.strip(". ") == "" and nm):
        raise ToolError("invalid_input", f"name: {nm!r} — a name, not a path (files go to the session's folder; path where a tool takes one).")
    writes = name in WRITERS or (args or {}).get("action") == "export"
    for k, v in (args or {}).items():
        if (k not in PATH_KEYS and k not in PATH_KEYS_FOR.get(name, ())) or (k == "path" and name in GEOMETRIC):
            continue
        write = (writes and k in ("path", "file")) or k in WRITE_KEYS
        if isinstance(v, list):
            for x in v:
                check(name, k, x, out_dir, write)
        else:
            check(name, k, v, out_dir, write)
    _check_declared(name, args, out_dir)

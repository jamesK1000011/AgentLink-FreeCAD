# SPDX-License-Identifier: LGPL-2.1-or-later
# The Activity tab's words: what each call did, as a short plain sentence a
# person reads at a glance ("Saved WindowTest", "Clicked Pin a Note, clicked
# the part"), and what came of it ("Pad made, 24000 mm³", "Refused: …").
# Never raw arguments, brackets or a file's folders: a path shows as its file
# name, and a home folder never shows at all.
#
# The phrases are data (agentlink/data/activity.json); the few calls whose
# words depend on the shape of their arguments (gui_input's steps,
# object_set's values, a command's menu text) are built here. An add-on
# gives its tools' words with an "activity" template in its tools.json entry
# (tooldata.py) or PHRASES on its family module (echo.declare). No FreeCAD
# needed, so all of it is tested headless.

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "activity.json")

with open(DATA, encoding="utf-8") as _f:
    _doc = json.load(_f)
# tool -> templates; the first whose fields are all given wins.
PHRASES = {k: list(v["did"]) for k, v in _doc["entries"].items() if v.get("did")}
RESULTS = {k: list(v["result"]) for k, v in _doc["entries"].items() if v.get("result")}
# Add-ons' own (declare()): {tool or prefix: templates}, longest match wins.
DECLARED = {}

MAX_TEXT = 140   # characters of a Did or Result cell (the tooltip has it all)
MAX_CALL = 400   # characters of the raw call in the tooltip

# ---- plain text ----------------------------------------------------------------------------

# A path: from the start of a word, a separator (after ~ or a drive letter),
# then at least one folder. Relative words like "a/b" are left alone.
_PATH = re.compile(r"(?<![\w.])(?:~|[A-Za-z]:)?[\\/](?:[^\s\"'\\/,;|<>]+[\\/])*[^\s\"'\\/,;|<>]*")
_HOMES = ("users", "home", "documents and settings")


def _file_of(m):
    raw = m.group(0)
    parts = [p for p in re.split(r"[\\/]", raw) if p and p != "~" and not re.fullmatch(r"[A-Za-z]:", p)]
    if not parts:
        return raw if raw in ("/", "\\") else "home folder" if raw.startswith("~") else raw
    if parts[0].lower() in _HOMES and len(parts) <= 2:
        return "home folder"
    if len(parts) == 1 and not raw.startswith("~"):
        return raw if len(raw) <= 2 else parts[0]  # "/2" in a fraction, "/tmp"
    name = parts[-1]
    tail = re.search(r"[.)]+$", name)
    return name[: tail.start()] + tail.group(0) if tail and tail.start() else name


def plain(text):
    """text with every path cut to its file name, home folders and their
    owner's name gone, and white space on one line."""
    if text is None:
        return ""
    s = re.sub(r"\s+", " ", str(text)).strip()
    return _PATH.sub(_file_of, s)


def _cap(s, n=MAX_TEXT):
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _amp(s):
    """A Qt label's text as shown: no & accelerators, no trailing dots."""
    s = re.sub(r"&(?!&)", "", str(s)).replace("&&", "&")
    return re.sub(r"(?:\.\.\.|…)$", "", s).strip()


def _num(v):
    if isinstance(v, bool):
        return "on" if v else "off"
    if isinstance(v, float):
        return f"{v:.0f}" if abs(v) >= 100 and v == int(v) else f"{v:.6g}"
    return str(v)


def _word(v):
    """One argument's value in words, or None when it does not read as one
    (an object, a list of objects, nothing)."""
    if v is None or v == "" or isinstance(v, dict):
        return None
    if isinstance(v, (list, tuple)):
        words = [w for w in (_word(x) for x in v) if w]
        if not words or len(words) != len(v) or any(isinstance(x, (list, dict)) for x in v):
            return None
        return _and(words)
    if isinstance(v, (bool, int, float)):
        return _num(v)
    return _cap(plain(_amp(v)), 48)


def _and(words, most=3):
    words = list(words)
    if len(words) > most:
        return ", ".join(words[:most]) + f" and {len(words) - most} more"
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


# ---- templates -----------------------------------------------------------------------------

_FIELD = re.compile(r"\{(\w+)\}")
_COND = re.compile(r"^(.*?)\s+if\s+\{(\w+)(?:=([\w.-]+))?\}$")


def _fill(template, *sources):
    """template with its {fields} from the first source that has each, or
    None when one is missing. " if {f}" / " if {f=value}" at the end: only
    when f is given (and is value)."""
    m = _COND.match(template)
    if m:
        template, key, want = m.groups()
        got = next((s[key] for s in sources if isinstance(s, dict) and s.get(key) not in (None, "")), None)
        if want is None:
            if not got:
                return None
        else:
            norm = str(got).lower() if not isinstance(got, bool) else ("true" if got else "false")
            if got is None or norm != want.lower():
                return None
    out = []

    def sub(mm):
        for s in sources:
            if isinstance(s, dict) and mm.group(1) in s:
                w = _word(s[mm.group(1)])
                if w:
                    return w
        out.append(mm.group(1))
        return ""

    text = _FIELD.sub(sub, template)
    return None if out else text


def _first(templates, *sources):
    for t in templates or ():
        if isinstance(t, str):
            got = _fill(t, *sources)
            if got:
                return got
    return None


def _declared(name):
    best, got = -1, None
    for k, v in DECLARED.items():
        if name.startswith(k) and len(k) > best:
            best, got = len(k), v
    return got


def declare(fam):
    """An add-on family's PHRASES ({tool or prefix: template or templates})."""
    for k, v in dict(getattr(fam, "PHRASES", None) or {}).items():
        if isinstance(k, str) and k:
            v = [v] if isinstance(v, str) else [x for x in (v or ()) if isinstance(x, str)]
            if v:
                DECLARED.setdefault(k, v)


# ---- what a call did -----------------------------------------------------------------------

def _lower(s):
    return s[:1].lower() + s[1:] if s[1:2].islower() or s[1:2] == " " else s


def _widget_name(spec):
    if not isinstance(spec, dict):
        return None
    for k in ("text", "toolTip"):
        v = spec.get(k)
        if isinstance(v, str) and v.strip():
            v = _amp(re.split(r"(?<=[.!?])\s", v.strip())[0]).rstrip(".")
            return _cap(plain(v), 32)
    cls = str(spec.get("class") or "")
    for bit, word in (("Button", "a button"), ("CheckBox", "a check box"), ("ComboBox", "a drop-down"), ("SpinBox", "a number field"),
                      ("LineEdit", "a text field"), ("TextEdit", "a text box"), ("Slider", "a slider"), ("Tab", "a tab")):
        if bit in cls:
            return word
    return "a control"


def _target(t):
    """(kind, words) of a gui_input target."""
    if not isinstance(t, dict):
        return "?", "the window"
    if "view_world" in t:
        return "view", "the part"
    if "view" in t:
        return "view", "the 3D view"
    if "tab" in t:
        name = _widget_name(t["tab"]) or "a"
        return "tab", f"the {name} tab"
    if "item" in t:
        return "item", _widget_name(t["item"]) or "a row"
    if "menu_item" in t:
        name = t["menu_item"] if isinstance(t["menu_item"], str) and t["menu_item"].strip() else "an item"
        return "menu_item", f"{name[:40]} in the menu"
    if "widget" in t:
        return "widget", _widget_name(t["widget"])
    return "window", "the window"


KEY_WORDS = {"Escape": "Esc", "Return": "Enter", "Enter": "Enter", "Backspace": "Backspace", "Delete": "Delete", "Space": "Space"}
MOD_WORDS = {"shift": "Shift", "ctrl": "Ctrl", "alt": "Alt", "meta": "Meta"}


def _step(st):
    """One gui_input step in words, or None for a step a person would not
    notice (a wait, a move, a release)."""
    if not isinstance(st, dict):
        return None
    mods = "".join(MOD_WORDS.get(str(m).lower(), str(m).title()) + "+" for m in (st.get("modifiers") or []) if isinstance(m, str))
    if "click" in st:
        kind, what = _target(st["click"])
        if kind == "item" and isinstance(st["click"], dict) and isinstance(st["click"].get("check"), bool):
            return ("Ticked " if st["click"]["check"] else "Unticked ") + what
        if kind == "tab":
            return "Opened " + what
        verb = "Double-clicked" if st.get("double") else "Right-clicked" if st.get("button") == "right" else "Clicked"
        return f"{verb} {what}" + (f" with {mods.rstrip('+')} held" if mods else "")
    if "drag" in st:
        d = st["drag"] if isinstance(st["drag"], dict) else {}
        kind, what = _target(d.get("from"))
        return "Dragged on the view" if kind == "view" else f"Dragged {what}"
    if "press" in st:
        kind, what = _target(st["press"])
        return "Dragged on the view" if kind == "view" else f"Pressed on {what}"
    if "scroll" in st:
        kind, what = _target(st["scroll"])
        return "Zoomed the view" if kind == "view" else f"Scrolled {what}"
    if "key" in st:
        k = st["key"] if isinstance(st["key"], str) else "a key"
        k = KEY_WORDS.get(k[:1].upper() + k[1:], k if len(k) > 1 else k.upper())
        return f"Pressed {mods}{k}"
    if "type" in st:
        if isinstance(st.get("target"), dict):
            return f"Typed into {_target(st['target'])[1]}"
        return "Typed some text"
    if "shot" in st:
        return "Took a picture of the window"
    return None


def gui_steps(steps, most=3):
    """gui_input's steps, summarised: one phrase per step a person would see,
    repeats folded, waits left out."""
    words = []
    for st in steps if isinstance(steps, list) else []:
        w = _step(st)
        if w and (not words or words[-1] != w):
            words.append(w)
    if not words:
        return "Waited" if steps else "Sent input to the window"
    shown = [words[0]] + [_lower(w) for w in words[1:most]]
    more = len(words) - most
    return ", ".join(shown) + (f" and {more} more step{'s' if more > 1 else ''}" if more > 0 else "")


UNITS = (("angle", "°"), ("length", " mm"), ("height", " mm"), ("width", " mm"), ("radius", " mm"), ("diameter", " mm"),
         ("depth", " mm"), ("offset", " mm"), ("distance", " mm"), ("size", " mm"), ("thickness", " mm"), ("value", ""))


def _value_words(prop, v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        unit = next((u for k, u in UNITS if k in prop.lower()), "")
        return _num(float(v) if isinstance(v, float) else v) + unit
    return _word(v) or "a new value"


def _object_set(args, body):
    obj = _word((args or {}).get("object")) or _word((body or {}).get("object")) or "an object"
    vals = (args or {}).get("values")
    if not isinstance(vals, dict) or not vals:
        return f"Changed {obj}"
    if set(vals) == {"Placement"}:
        return f"Moved {obj}"
    if len(vals) > 2:
        return f"Set {len(vals)} properties of {obj}"
    bits = [f"{p} to {_value_words(p, v)}" if p != "Placement" else "its placement" for p, v in vals.items()]
    return f"Set {obj} " + " and ".join(bits)


def command_text(cmd):
    """A FreeCAD command's menu text ("Isometric" for Std_ViewIsometric):
    FreeCAD's own when it runs, else made from the name."""
    if not isinstance(cmd, str) or not cmd:
        return "a command"
    try:
        import FreeCADGui

        info = FreeCADGui.Command.get(cmd).getInfo()
        text = _amp(info.get("menuText") or "")
        if text:
            return text
    except Exception:
        pass
    tail = cmd.split("_", 1)[1] if "_" in cmd else cmd
    if cmd.startswith("Std_View") and len(tail) > 4:
        tail = tail[4:]
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", tail).split()
    return " ".join([words[0]] + [w if w.isupper() else w.lower() for w in words[1:]]) if words else cmd


def bench_text(name):
    s = re.sub(r"Workbench$", "", str(name or ""))
    pretty = {"PartDesign": "Part Design", "TechDraw": "TechDraw", "OpenSCAD": "OpenSCAD", "BIM": "BIM", "CAM": "CAM", "FEM": "FEM", "Fem": "FEM"}
    if s in pretty:
        return pretty[s]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s) or "a workbench"


def _job_words(a, b):
    """job_start in plain words (p8: "Job start: 6000 mm³"): what the job
    runs, in that tool's own words, and its state — done within the call,
    started and running, or queued. Plain Python."""
    tool = a.get("tool")
    if not isinstance(tool, str) or not tool or tool == "job_start":
        return None
    inner_args = a.get("arguments") if isinstance(a.get("arguments"), dict) else {}
    st = b.get("status") if isinstance(b.get("status"), str) else None
    if "error" in b:
        return "Ran " + _lower(did(tool, inner_args, {})) + " as a job"
    if st in ("running", "queued"):
        inner = did(tool, inner_args, {})
        return f"Started a job: {_lower(inner)}"
    inner = did(tool, inner_args, {k: v for k, v in b.items() if k not in ("job", "status", "note")})
    return f"Ran a job, done: {_lower(inner)}"


def _special(name, args, body):
    a, b = args or {}, body or {}
    if name == "job_start":
        return _job_words(a, b)
    if name == "pref_import":
        src = a.get("path") or b.get("from")
        f = _file_name(os.path.basename(src)) if isinstance(src, str) and src else None
        return "Brought in settings" + (f" from {f}" if f else "")
    if name == "gui_input":
        return gui_steps(a.get("steps"))
    if name == "dialog_answer":
        info = b.get("dialog") if isinstance(b.get("dialog"), dict) else b.get("task") if isinstance(b.get("task"), dict) else {}
        title = _word(_amp(info.get("title") or "")) if info else None
        where = f"the {title} dialog" if title and "dialog" not in title.lower() else (title or "the dialog")
        btn = _word(a.get("button"))
        if btn and not b.get("pressed") and not info and "dialog" in b and b["dialog"] is None:
            # Nothing open, nothing pressed (round 8, 00-130: "Answered the
            # dialog: Cancel" read as a press): the look, and the button
            # it would have pressed.
            return f"Looked for an open dialog to press {_amp(btn)}"
        if btn:
            return f"Answered {where}: {_amp(btn)}"
        return f"Read {where}" if title else "Looked for an open dialog"
    if name == "doc_close":
        docs = a.get("documents") or b.get("closed")
        what = _word(docs if isinstance(docs, list) else [docs] if docs else None) or "the document"
        return f"Closed {what}" + (" (not saved)" if a.get("discard") else "")
    if name == "object_set":
        return _object_set(a, b)
    if name == "feature_edit" and isinstance(a.get("set"), dict) and a["set"]:
        # What was changed, not only which feature ("Set Pocket 2 Refine to on").
        return _object_set({"object": a.get("feature") or b.get("feature") or "a feature", "values": a["set"]}, b)
    if name == "sketch_edit" and a.get("set"):
        # set: [{ constraint, value }] (or { name: value }): the dimension and
        # its new value ("Set plate_width to 70 in PlateSketch").
        sk = _word(a.get("sketch")) or _word(b.get("sketch")) or "the sketch"
        s = a["set"]
        rows = [(r.get("constraint"), r.get("value")) for r in (s if isinstance(s, list) else [s]) if isinstance(r, dict) and "constraint" in r]
        if not rows and isinstance(s, dict):
            rows = list(s.items())
        if len(rows) > 2:
            return f"Set {len(rows)} dimensions of {sk}"
        if rows:
            return "Set " + " and ".join(f"{_word(k) or 'a dimension'} to {_value_words('value', v)}" for k, v in rows) + f" in {sk}"
    if name == "cmd_run":
        return "Ran " + command_text(a.get("name"))
    if name == "menu_run":
        path = [_amp(p) for p in a.get("path") or [] if isinstance(p, str)]
        if not path:
            return "Chose a menu item"
        return f"Chose {path[-1]} from the {path[0]} menu" if len(path) > 1 else f"Chose {path[0]}"
    if name == "workbench":
        return f"Switched to {bench_text(a['activate'])}" if a.get("activate") else "Read the workbenches"
    if name == "selection":
        # Only a call that asks to clear (clear: true) clears; one that names
        # nothing reads (round 7, 00-096: "Cleared the selection" on a read).
        objs = _word(a.get("objects"))
        if a.get("clear") is True:
            return "Cleared the selection"
        if objs:
            return f"Selected {objs}"
        got = b.get("selected")
        if isinstance(got, list):
            return f"Read the selection: {_and([_word(x) or '?' for x in got])}" if got else "Read the selection: nothing selected"
        return "Read the selection"
    if name == "show" and b:
        # What the answer says was done, not what was asked (round 7, 00-106:
        # "Showed Bracket and Ghost" though Ghost is not in the document).
        hid = a.get("visible") is False
        done = [x for x in (b.get("hidden") if hid else b.get("visible")) or [] if isinstance(x, str)]
        missing = [x for x in b.get("unknown") or [] if isinstance(x, str)]
        if done or missing:
            text = (("Hid " if hid else "Showed ") + (_word(done) or "")) if done else ("Hid nothing" if hid else "Showed nothing")
            return text + (f"; {_word(missing)} not found" if missing else "")
    return None


# The last word of a tool's name -> the verb it reads as.
VERBS = {"new": "Made a new", "add": "Added", "make": "Made", "list": "Listed", "read": "Read", "info": "Read", "get": "Read",
         "state": "Read", "status": "Read", "remove": "Removed", "delete": "Deleted", "export": "Exported", "import": "Imported",
         "set": "Set", "run": "Ran", "edit": "Edited", "check": "Checked", "open": "Opened", "save": "Saved", "clear": "Cleared",
         "repair": "Repaired", "fix": "Fixed", "merge": "Merged", "split": "Split", "find": "Found", "update": "Updated"}
MAIN_ARGS = ("object", "body", "sketch", "feature", "page", "document", "job", "op", "assembly", "part", "topic", "label", "name", "path", "kind")


def friendly(name):
    """A tool's name as words: "Mesh decimate", "Exported TechDraw"."""
    from . import echo

    area, rest = echo._area(name)
    words = [w for w in rest.split("_") if w]
    for i in (len(words) - 1, 0):
        if 0 <= i < len(words) and words[i] in VERBS:
            other = " ".join(w for j, w in enumerate(words) if j != i)
            return f"{VERBS[words[i]]} {area}" + (f" {other}" if other else "")
    return f"{area} {' '.join(words)}".strip() if words else area


def fallback(name, args):
    a = args if isinstance(args, dict) else {}
    key, main = next(((k, w) for k, w in ((k, _word(a.get(k))) for k in MAIN_ARGS) if w), (None, None))
    # A read's file is what it read from (round 8, 04-013: "Read Gcode on
    # …-sliced.3mf" for G-code read out of the sliced project).
    on = "from" if key == "path" and not writes(name) else "on"
    return friendly(name) + (f" {on} {main}" if main else "")


_JOB_ID = re.compile(r"^job-[0-9a-f]{8}$")


def finished_job(b):
    """True for a tool's own answer that carries the id of the job it ran as
    (agentlink/jobs.py "job-" + 8 hex), not a running job's summary. Plain
    Python."""
    return isinstance(b, dict) and isinstance(b.get("job"), str) and bool(_JOB_ID.match(b["job"])) \
        and b.get("status") not in ("running", "queued")


def did(name, args=None, body=None, template=None):
    """What a call did, in a short plain sentence. template: the tool's own
    (its tools.json "activity"), tried first."""
    name = str(name or "?")
    a = args if isinstance(args, dict) else {}
    b = body if isinstance(body, dict) else {}
    if finished_job(b):
        # A heavy read that ended within the call carries its job's id too
        # (protocol._as_job, the batch: setdefault("job")): not "in the
        # background" (round 7, make 04-085: "Solving the frame in the
        # background" over a finished answer). Only a running job's summary
        # (status "running") fills an add-on's "… if {job}".
        b = {k: v for k, v in b.items() if k != "job"}
    text = None
    if template:
        text = _first([template] if isinstance(template, str) else template, a, b)
    if not text:
        text = _special(name, a, b)
    if not text:
        text = _first(PHRASES.get(name) or _declared(name), a, b)
    if not text:
        text = fallback(name, a)
    return _cap(plain(text))


# ---- what came of it -----------------------------------------------------------------------

def _sentence(s, n=110):
    s = plain(s)
    first = re.split(r"(?<=[.!?])\s+(?=[A-Z])", s)[0]
    return _cap(first.rstrip(". "), n)


def refusal(body):
    err = (body or {}).get("error") if isinstance(body, dict) else None
    msg = err.get("message") if isinstance(err, dict) else err if isinstance(err, str) else ""
    msg = re.sub(r"^input\.", "", str(msg or "").strip())
    return "Refused: " + _sentence(msg) if msg else "Refused"


def _volume(v):
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    return (f"{v:.0f}" if abs(v) >= 100 else f"{v:.3g}") + " mm³"


# An answer's key value, the first found, for the words of a call ("Made a
# mesh: 152 facets", "Weighed Block: 24 g"): (key, how it reads). Numbers
# only where the key says the unit; lists by their count.
KEY_NUMBERS = (("volume", "{} mm³"), ("volume_m3", "{} m³"), ("area", "{} mm²"), ("area_m2", "{} m²"),
               ("length", "{} mm"), ("length_mm", "{} mm"), ("length_m", "{} m"), ("span_mm", "{} mm"),
               ("totalLength_m", "{} m of bars"), ("distance", "{} mm"), ("gap", "{} mm"), ("value", None),
               ("mass_kg", "{} kg"), ("mass", "{} g"), ("vonMisesMaxMPa", "{} MPa at most"),
               ("deflectionMaxMm", "{} mm deflection"), ("worst_mm", "{} mm off"), ("bars", "{} bars"),
               ("facets", "{} facets"), ("triangles", "{} triangles"), ("found", "{} found"), ("count", "{} found"),
               ("points", "{} points"), ("chars", "{} characters"), ("waypoints", "{} waypoints"), ("lines", "{} lines"))
KEY_TEXTS = ("refined", "verdict", "state", "solve")
KEY_LISTS = ("materials", "inspections", "fonts", "views", "axes", "pieces", "cleared", "merged", "inserted", "removed",
             "modes", "rows", "parts", "ops", "added", "changed")
KEY_FILES = ("file", "path", "template", "files")
# KEY_LISTS' words for one ("1 view", not "1 views": r8hub-13); a word not
# here reads the same for one ("1 cleared").
ONE = {"materials": "material", "inspections": "inspection", "fonts": "font", "views": "view", "axes": "axis",
       "pieces": "piece", "modes": "mode", "rows": "row", "parts": "part", "ops": "op"}


def _short_num(v):
    if isinstance(v, float):
        return f"{v:.0f}" if abs(v) >= 100 else f"{v:.4g}"
    return str(v)


def fem_value(b):
    """A strength answer's figure (round 6, fem 030, 034): the peak stress
    ("max 41.2 MPa, safety 6.1"), the first frequencies ("3 modes: 12.3, 45.6,
    78.9 Hz"), the hottest point. None for any other answer. Plain Python."""
    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    vm = b.get("vonMisesMax")
    mpa = vm.get("MPa") if isinstance(vm, dict) else b.get("vonMisesMaxMPa")
    if num(mpa):
        out = f"max {_short_num(mpa)} MPa"
        if num(b.get("safety")):
            out += f", safety {_short_num(b['safety'])}"
        return out
    modes = b.get("modes")
    if isinstance(modes, list) and modes and all(isinstance(m, dict) for m in modes):
        hz = [m.get("hz") for m in modes if num(m.get("hz"))]
        if hz:
            return f"{len(modes)} modes: {', '.join(_short_num(h) for h in hz[:3])} Hz"
        lf = [m.get("factor") for m in modes if num(m.get("factor"))]
        if lf:
            return f"lowest load factor {_short_num(lf[0])}"
    hot = b.get("hottest")
    if isinstance(hot, dict) and num(hot.get("celsius")):
        out = f"hottest {_short_num(hot['celsius'])} °C"
        cold = b.get("coolest")
        if isinstance(cold, dict) and num(cold.get("celsius")):
            out += f", coolest {_short_num(cold['celsius'])} °C"
        return out
    return None


def cam_value(b):
    """A CAM simulation's answer in a few words (round 6, cam 013: "clear"
    said less than round 3's "75 % left, up to 9 mm"): the verdict, what was
    removed, what is left over the part. None for any other answer. Plain
    Python."""
    if not isinstance(b.get("removedMm3"), (int, float)) or not isinstance(b.get("verdict"), str):
        return None
    out = [b["verdict"], f"{_short_num(b['removedMm3'])} mm³ removed"]
    left = (b.get("part") or {}).get("left") if isinstance(b.get("part"), dict) else None
    if isinstance(left, dict) and isinstance(left.get("share"), (int, float)):
        out.append(f"{round(100 * left['share'])} % left, up to {_short_num(left.get('most', 0))} mm")
    return ", ".join(out)


def views_value(b):
    """A projection group's views in a few words (round 8, td_projection:
    "Put standard views on the drawing" gave none): how many, their labels
    and the projection ("3 views (Front, Top and Right), third angle"). Any
    answer with a projection and items [{ view }]. None for any other.
    Plain Python."""
    items = b.get("items")
    if not isinstance(b.get("projection"), str) or not isinstance(items, list) or not items:
        return None
    labels = [str(x["view"]) for x in items if isinstance(x, dict) and isinstance(x.get("view"), str)]
    if not labels:
        return None
    out = f"{_count(len(labels), 'view')} ({_and([plain(_amp(x)) for x in labels], 4)})"
    return out + f", {plain(b['projection']).lower()}"


def print_value(b):
    """A sliced print's figures (round 8, 04-013, 04-015, 02-010: "Read
    Gcode on …-sliced.3mf" gave none): a G-code read's layer count and
    heights, the layer it read (its height and moves), its picture's file;
    a slice's layers and filament. Any answer with a whole-number layers
    and a [first, last] z, or layers with filamentG. None for any other.
    Plain Python."""
    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    n = b.get("layers")
    if not isinstance(n, int) or isinstance(n, bool):
        return None
    z = b.get("z")
    has_z = isinstance(z, list) and len(z) == 2 and all(num(x) for x in z)
    if not has_z and not num(b.get("filamentG")):
        return None
    out = _count(n, "layer")
    lay = b.get("layer") if isinstance(b.get("layer"), dict) else None
    if lay and num(lay.get("layer")):
        out = f"layer {lay['layer']} of {n}"
        if num(lay.get("z")):
            out += f" at z {_short_num(float(lay['z']))} mm"
        moves = lay.get("moves")
        k = len(moves) if isinstance(moves, list) else moves if num(moves) else None
        if k is not None:
            out += f", {_count(int(k), 'move')}"
    elif has_z:
        out += f", z {_short_num(float(z[0]))} to {_short_num(float(z[1]))} mm"
    feats = b.get("features")
    if not lay and isinstance(feats, (list, dict)) and feats:
        out += f", {_count(len(feats), 'feature')}"
    if num(b.get("filamentG")):
        out += f", {_short_num(float(b['filamentG']))} g of filament"
    if isinstance(b.get("move"), dict) and isinstance(b["move"].get("kind"), str):
        out += f", move: {plain(b['move']['kind'])}"
    if isinstance(b.get("svg"), str) and b["svg"].strip():
        out += f", drew {_file_name(b['svg'])}"
    return out


def mesh_value(b):
    """A mesh read's count in a few words (round 7, mesh 12-013, 12-035: the
    captions "Mesh boundary on Half rim", "Mesh segments on curvature" gave
    none): meshobj_boundary's loops and its longest rim ("1 loop, 40 mm,
    closed, 100 mm²"); meshobj_segments' regions ("6 segments"). None for any
    other answer. Plain Python."""
    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    if num(b.get("loops")) and isinstance(b.get("mesh"), str) and ("openEdges" in b or b.get("loops") == 0):
        n = int(b["loops"])
        out = f"{n} loop{'' if n == 1 else 's'}"
        rims = b.get("boundaries")
        top = rims[0] if isinstance(rims, list) and rims and isinstance(rims[0], dict) else None
        if top and num(top.get("length")):
            out += f", {_short_num(top['length'])} mm"
            if top.get("closed"):
                out += ", closed"
            if num(top.get("area")):
                out += f", {_short_num(top['area'])} mm²"
        return out
    if num(b.get("area3d")) and num(b.get("areaFlat")):
        # meshobj_unwrap (round 8, 00-174, 00-191, unwrap-0: "Mesh unwrap"
        # or only its file): the areas, 3D and flat, and the stretch.
        out = f"area {_short_num(b['area3d'])} mm², flat {_short_num(b['areaFlat'])} mm²"
        st = b.get("stretch") if isinstance(b.get("stretch"), dict) else {}
        if num(st.get("max")):
            out += f", stretch max {_short_num(st['max'])} %"
            if num(st.get("mean")) and st["mean"]:
                out += f" (mean {_short_num(st['mean'])} %)"
        return out
    if num(b.get("segments")) and isinstance(b.get("largest"), list):
        n = int(b["segments"])
        return f"{n} segment{'' if n == 1 else 's'}"
    return None


def key_value(body):
    """The answer's key value in a few words ("24 g", "152 facets", "3
    found", "wrote house.ifc"), or None. A file shows as its name, never its
    folder. Plain Python."""
    b = body if isinstance(body, dict) else {}
    if isinstance(b.get("result"), (int, float)) and not isinstance(b.get("result"), bool) and isinstance(b.get("to"), str):
        return plain(f"{_short_num(b['result'])} {b['to']}")
    fem = fem_value(b) or cam_value(b) or mesh_value(b) or print_value(b) or views_value(b)
    if fem:
        return fem
    for k, fmt in KEY_NUMBERS:
        v = b.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if fmt is None:
                unit = b.get("unit") if isinstance(b.get("unit"), str) else ""
                return plain(f"{_short_num(v)} {unit}".strip())
            return fmt.format(_short_num(v))
    for k in KEY_TEXTS:
        v = b.get(k)
        if isinstance(v, str) and v.strip() and len(v) <= 40:
            return plain(_amp(v))
    for k in KEY_LISTS:
        v = b.get(k)
        if isinstance(v, list) and v:
            return _count(len(v), ONE.get(k, k), k)
    for k in KEY_FILES:
        v = b.get(k)
        if isinstance(v, list):
            v = next((x for x in v if isinstance(x, str)), None)
        if isinstance(v, str) and ("/" in v or "\\" in v or "." in v[-6:]):
            return "wrote " + plain(v)
    return None


# ---- a read's own value (round 7) ---------------------------------------------------------
# Reads and looks whose answer has no key value of its own, so their words
# said only what was done ("Read the session"): each with a count from its
# answer ("Read the session: 2 bodies, step 14"). fn(body) -> words or None.
# Plain Python.

def _n(v):
    return len(v) if isinstance(v, (list, tuple, dict)) else v if isinstance(v, int) and not isinstance(v, bool) else None


def _count(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _file_name(v):
    return plain(v) if isinstance(v, str) and v else None


def _session_value(b):
    n = _n(b.get("bodies"))
    if n is None:
        return None
    out = _count(n, "body", "bodies")
    if _n(b.get("hidden")):
        out += f", {_n(b['hidden'])} hidden"
    if isinstance(b.get("step"), int):
        out += f", step {b['step']}"
    return out


def _guide_value(b):
    if isinstance(b.get("guides"), list):
        return _count(len(b["guides"]), "guide")
    if isinstance(b.get("read"), list):
        return _count(len(b["read"]), "guide")
    text = b.get("text")
    if isinstance(text, str):
        heads = sum(1 for line in text.splitlines() if line.startswith("## "))
        return _count(heads, "section") if heads else f"{len(text)} characters"
    return None


def _groups_value(b):
    if isinstance(b.get("groups"), list):
        on = sum(1 for g in b["groups"] if isinstance(g, dict) and g.get("on"))
        out = _count(len(b["groups"]), "group") + (f", {on} on" if on else "")
        return out + (f", {b['listed']} tools listed" if isinstance(b.get("listed"), int) else "")
    if isinstance(b.get("tools"), list):
        return _count(len(b["tools"]), "tool") + " found"
    if isinstance(b.get("added"), list) or isinstance(b.get("removed"), list):
        return f"{len(b.get('added') or [])} tools added, {len(b.get('removed') or [])} groups off"
    return None


def _usage_value(b):
    if not isinstance(b.get("calls"), int):
        return None
    out = _count(b["calls"], "call")
    if isinstance(b.get("tokens"), (int, float)):
        out += f", {_short_num(b['tokens'])} tokens"
    if b.get("errors"):
        out += f", {_count(b['errors'], 'refusal')}"
    return out


def _report_value(b):
    if b.get("found") is False:
        return "no Report view"
    p = b.get("problems")
    n = b.get("count")
    if not isinstance(p, int) and not isinstance(n, int):
        return None
    bits = []
    if isinstance(p, int):
        bits.append(_count(p, "problem"))
        first = b.get("first")
        if p and isinstance(first, str) and first.strip():
            # The first one named, short (r8hub-1: "1 problem" said nothing).
            bits[-1] += f" (first: {_cap(plain(first.strip()), 60)})"
    if isinstance(n, int):
        bits.append(_count(n, "line"))
    return ", ".join(bits)


def _picture_value(b):
    if b.get("empty"):
        return "nothing drawn: " + _sentence(str(b["empty"]), 70)[:1].lower() + _sentence(str(b["empty"]), 70)[1:]
    w, h = b.get("width"), b.get("height")
    f = _file_name(b.get("path"))
    if not (isinstance(w, int) and isinstance(h, int)):
        return None  # the file alone: key_value's "wrote a.png"
    return ", ".join(x for x in (f"{w} x {h} px", f) if x)


def _maps_value(b):
    if not isinstance(b.get("maps"), list):
        return None
    out = _count(len(b["maps"]), "map")
    if isinstance(b.get("layers"), list):
        out += f", {_count(len(b['layers']), 'layer')}"
    return out


def _shots_value(b):
    if not isinstance(b.get("shots"), list):
        return None
    return _count(len(b["shots"]), "screenshot") if b["shots"] else "no screenshots"


def _notes_value(b):
    if not isinstance(b.get("notes"), list):
        return None
    out = _count(len(b["notes"]), "note") if b["notes"] else "no notes"
    if isinstance(b.get("waiting"), list) and b["waiting"]:
        out += f", {len(b['waiting'])} waiting"
    return out


def _steps_value(b):
    return _count(len(b["steps"]), "step") if isinstance(b.get("steps"), list) else None


def _job_value(b):
    if isinstance(b.get("jobs"), list):
        return _count(len(b["jobs"]), "job") if b["jobs"] else "no jobs"
    st = b.get("status")
    if not isinstance(st, str):
        return None
    out = (f"{b['tool']} " if isinstance(b.get("tool"), str) else "") + st
    if isinstance(b.get("running"), (int, float)):
        out += f", {_short_num(b['running'])} s so far"
    elif isinstance(b.get("took"), (int, float)):
        out += f" in {_short_num(b['took'])} s"
    return out


def _crash_value(b):
    if "folder" in b:
        return f"copied {len(b.get('recovery') or [])} recovery folders, {len(b.get('reports') or [])} reports"
    return "nothing new" if b.get("note") else None


def _pref_value(b):
    if "value" in b and isinstance(b.get("name"), str):
        return f"{_word(b['name'])} = {_word(b['value']) if _word(b['value']) is not None else b['value']}"
    if isinstance(b.get("values"), dict):
        out = _count(len(b["values"]), "value")
        if isinstance(b.get("groups"), list):
            out += f", {_count(len(b['groups']), 'group')}"
        return out
    return None


def _ifc_value(b):
    if not isinstance(b.get("schema"), str):
        return None
    out = "IFC " + b["schema"]
    names = [n for n in b.get("storeyNames") or [] if isinstance(n, str)]
    if names:
        out += ", storeys " + (" and ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + " and " + names[-1])
    elif isinstance(b.get("storeys"), list):
        out += f", {_count(len(b['storeys']), 'storey')}"
    if isinstance(b.get("elements"), int):
        out += f", {_count(b['elements'], 'element')}"
    return out


def _extensions_value(b):
    if not isinstance(b.get("loaded"), (dict, list)):
        return None
    return f"{len(b['loaded'])} loaded" + (f", {_count(len(b['repos']), 'listed repo')}" if isinstance(b.get("repos"), list) else "")


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _probe_value(b):
    """fea_probe (round 8, 03-012: "FEM probe: box"): the displacement at
    each point, the line's samples and largest, the faces' largest."""
    bits = []
    pts = [p for p in b.get("points") or () if isinstance(p, dict) and _isnum(p.get("displacementMm"))]
    if pts:
        bits.append(", ".join(f"{_short_num(p['displacementMm'])} mm" for p in pts[:3]) + (" …" if len(pts) > 3 else "")
                    + f" at {_count(len(pts), 'point')}")
    ln = [p for p in b.get("line") or () if isinstance(p, dict) and _isnum(p.get("displacementMm"))]
    if ln:
        bits.append(f"line {len(ln)} samples, {_short_num(ln[0]['displacementMm'])} to {_short_num(ln[-1]['displacementMm'])} mm")
    fc = b.get("faces")
    if isinstance(fc, dict):
        d = (fc.get("displacementMm") or {}).get("max")
        s = (fc.get("vonMisesMPa") or {}).get("max")
        on = ", ".join(fc.get("faces") or []) or "faces"
        if _isnum(d) or _isnum(s):
            bits.append(f"{on} up to " + ", ".join(x for x in ((f"{_short_num(d)} mm" if _isnum(d) else None), (f"{_short_num(s)} MPa" if _isnum(s) else None)) if x))
    return "; ".join(bits) or None


def _chart_value(b):
    """fea_chart (round 8, 03-014, 03-016: "FEM chart on histogram: box"):
    its kind, field and range, with the nodes or samples."""
    kind, unit = b.get("kind"), b.get("unit") if isinstance(b.get("unit"), str) else ""
    if not isinstance(kind, str):
        return None
    field = {"vonMises": "von Mises", "displacement": "displacement"}.get(b.get("field"), str(b.get("field") or ""))
    out = f"{kind} of {field}".strip()
    if _isnum(b.get("min")) and _isnum(b.get("max")):
        out += f" {_short_num(b['min'])} … {_short_num(b['max'])} {unit}".rstrip()
    elif _isnum(b.get("max")):
        out += f" up to {_short_num(b['max'])} {unit}".rstrip()
    if _isnum(b.get("samples")):
        out += f", {_count(int(b['samples']), 'sample')}"
    elif _isnum(b.get("nodes")):
        out += f", {_count(int(b['nodes']), 'node')}"
    return out


def _linearize_value(b):
    """fem_linearize (round 8, 03-020: "21 points"): membrane and bending
    stress through the wall, MPa."""
    if not (_isnum(b.get("membrane")) and _isnum(b.get("bending"))):
        return None
    out = f"membrane {_short_num(b['membrane'])} MPa, bending {_short_num(b['bending'])} MPa"
    if _isnum(b.get("thickness")):
        out += f" through {_short_num(b['thickness'])} mm"
    return out


def _native_value(b):
    """fea_native (round 8, 03-033: "FEM native on Box native"): the
    analysis, its solver and what it holds; not solved."""
    if not isinstance(b.get("analysis"), str) or not isinstance(b.get("objects"), (list, dict)):
        return None
    solver = {"calculix": "CalculiX", "elmer": "Elmer", "z88": "Z88", "mystran": "Mystran"}.get(str(b.get("solver")).lower(), b.get("solver") or "solver")
    out = f"{b['analysis']}, {solver}, {_count(len(b['objects']), 'object')}"
    if b.get("skipped"):
        out += f", {len(b['skipped'])} skipped"
    return out + ", not solved"


def _prefs_value(b):
    """pref_import (p8: the caption ran out in its note, no count): how many
    settings came in, in how many groups."""
    n, g = b.get("settings"), b.get("groups")
    g = len(g) if isinstance(g, list) else g if _isnum(g) else None
    if not _isnum(n) and g is None:
        return None
    bits = [_count(int(n), "setting")] if _isnum(n) else []
    if g is not None:
        bits.append(_count(int(g), "group"))
    return " in ".join(bits)


def _marks_value(b):
    """td_centermarks (r8hub-13: "1 views"): the circles marked and on how
    many views; "taken off" when its extend is 0."""
    rows = [r for r in b.get("views") or () if isinstance(r, dict)]
    if not rows:
        return None
    n = sum(int(r["circles"]) for r in rows if _isnum(r.get("circles")))
    if _isnum(b.get("extend")) and not b["extend"]:
        return _count(len(rows), "view")
    return f"{_count(n, 'circle')} on {_count(len(rows), 'view')}"


def batch_words(args, body):
    """A batch's own words at its end (p8-batch): "Ran 6 calls in one
    batch: 6 ok", the refused and not run counted, its title first when
    given ("Peg plate — ran 6 calls …"). None for an answer with no rows.
    Plain Python."""
    a = args if isinstance(args, dict) else {}
    b = body if isinstance(body, dict) else {}
    rows = b.get("results") if isinstance(b.get("results"), list) else b.get("lines") if isinstance(b.get("lines"), list) else None
    ran = b.get("ran") if _isnum(b.get("ran")) else len(rows) if rows is not None else None
    if not ran:
        return None  # an empty batch says nothing
    c = b.get("counts") if isinstance(b.get("counts"), dict) else None
    if c is not None and _isnum(c.get("ok")):
        # lines "counts" or "refused" (live 17 Nov): the rows are not every
        # call, so a missing row is no refusal — the counts are the truth.
        ok, bad = int(c["ok"]), int(c.get("refused") or 0)
    elif rows is not None and len(rows) >= int(ran):
        ok = sum(1 for r in rows if isinstance(r, dict) and r.get("ok"))
        bad = int(ran) - ok
    else:
        ok, bad = None, 0
    out = f"ran {_count(int(ran), 'call')} in one batch" + (f": {ok} ok" if ok is not None else "")
    if bad > 0:
        out += f", {bad} refused"
    if _isnum(b.get("notRun")) and b["notRun"]:
        out += f", {int(b['notRun'])} not run"
    if b.get("undone"):
        out += ", taken back"
    title = a.get("title") or b.get("title")
    if isinstance(title, str) and title.strip():
        return _cap(plain(f"{title.strip()} — {out}"))
    return _cap(out[:1].upper() + out[1:])


READ_VALUES = {"pref_import": _prefs_value, "td_centermarks": _marks_value, "session_state": _session_value, "guide_read": _guide_value, "tool_groups": _groups_value, "usage_report": _usage_value,
               "report_read": _report_value, "view_render": _picture_value, "view_snapshot": _picture_value, "window_snapshot": _picture_value,
               "view_maps": _maps_value, "snapshot_list": _shots_value, "note_list": _notes_value, "steps_list": _steps_value,
               "job_start": lambda b: _job_value({k: v for k, v in b.items() if k != "tool"}), "job_status": _job_value, "crash_collect": _crash_value, "pref_get": _pref_value,
               "ifc_open": _ifc_value, "app_extensions": _extensions_value,
               "fea_probe": _probe_value, "fea_chart": _chart_value, "fem_linearize": _linearize_value, "fea_native": _native_value}

# Tools whose last word reads: their answer's file is what they read, not
# what they wrote (round 7: "Read a setting: wrote BaseApp/Preferences/View",
# "Opened IFC on house.ifc: wrote house.ifc").
READ_WORDS = ("get", "read", "open", "import", "list", "info", "state", "status", "find", "check", "maps", "latest")


def writes(name):
    """Whether a tool's answer's file is one it wrote (an export, a save, a
    picture), by its name's last word. Plain Python."""
    last = str(name or "").rsplit("_", 1)[-1]
    return last not in READ_WORDS


def read_value(name, body):
    """A read's own value (READ_VALUES), or None. Never raises."""
    fn = READ_VALUES.get(str(name or ""))
    if fn is None or not isinstance(body, dict):
        return None
    try:
        got = fn(body)
    except Exception:  # noqa: BLE001
        return None
    return _cap(plain(got), 90) if isinstance(got, str) and got.strip() else None


def _vols(rows):
    vols = [r.get("volume") for r in rows if isinstance(r, dict)]
    vols = [v for v in vols if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not vols or len(vols) != len([r for r in rows if isinstance(r, dict)]):
        return None
    if max(vols) - min(vols) <= 1e-3 * max(1.0, abs(max(vols))):
        return f"{_short_num(vols[0])} mm³ each" if len(vols) > 1 else f"{_short_num(vols[0])} mm³"
    return ", ".join(_short_num(v) for v in vols[:4]) + (" …" if len(vols) > 4 else "") + " mm³"


def shape_value(b):
    """A shape or mesh change's figures that key_value does not read (round
    7, review3: "Split Halves", "Took Face7 off Plate", "Simplified a mesh:
    4181 mm³" gave none or the wrong one): pieces and their volumes, faces
    and volume before and after, a mesh's "n → m triangles", "unchanged".
    None for any other answer. Plain Python."""
    b = b if isinstance(b, dict) else {}

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    if num(b.get("waypoints")) and isinstance(b.get("trajectory"), str):
        out = _count(int(b["waypoints"]), "waypoint")
        return out + (f", {_short_num(b['length_mm'])} mm" if num(b.get("length_mm")) else "")
    if num(b.get("moves")) and num(b.get("lines")):
        return f"{_count(int(b['moves']), 'move')}, {_count(int(b['lines']), 'line')}"
    if isinstance(b.get("reduced"), str) and "→" in b["reduced"]:
        return plain(b["reduced"])
    if b.get("changed") is False and isinstance(b.get("mesh"), str):
        return "unchanged"
    fb, fa = b.get("facesBefore"), b.get("facesAfter")
    if num(fb) and num(fa):
        out = f"{_short_num(fb)} → {_short_num(fa)} faces"
        vb, v = b.get("volumeBefore_mm3"), b.get("volume_mm3")
        if num(vb) and num(v):
            out += f", {_short_num(vb)} → {_short_num(v)} mm³"
        return out
    p = b.get("pieces")
    rows = b.get("solids") if isinstance(b.get("solids"), list) else p if isinstance(p, list) else []
    n = len(p) if isinstance(p, list) else int(p) if num(p) else None
    if n is not None:
        out = _count(n, "piece")
        if isinstance(b.get("group"), str):
            out += f" in {plain(_amp(b['group']))}"
        vols = _vols(rows)
        return out + (f", {vols}" if vols else "")
    return None


def call_value(name, body):
    """The value said with a call's words: its read value, else a shape's
    figures (shape_value), else the answer's key value — a file a reading
    tool names shown without "wrote". Plain Python."""
    got = read_value(name, body) or shape_value(body)
    if got:
        return got
    kv = key_value(body)
    if kv and kv.startswith("wrote ") and not writes(name):
        kv = kv[len("wrote "):]
    return kv


def outcome(name, ok, body=None, args=None):
    """What came of a call, short: "Pad made, 24000 mm³", "Saved as
    WindowTest.FCStd", "Refused: …". Never a folder."""
    b = body if isinstance(body, dict) else {}
    if not ok:
        return _cap(refusal(b))
    if name == "workbench" and b.get("active") and (args or {}).get("activate"):
        return _cap(plain(f"{bench_text(b['active'])} in front"))
    rv = read_value(name, b)
    if rv:
        return _cap(rv[:1].upper() + rv[1:])
    got = _first(RESULTS.get(name), b, args or {})
    if got:
        return _cap(plain(got))
    if isinstance(b.get("feature"), str):
        vol = _volume(b.get("volume"))
        return _cap(plain(f"{_amp(b['feature'])} made" + (f", {vol}" if vol else "")))
    if b.get("pressed"):
        return _cap(plain(f"Pressed {_amp(b['pressed'])}"))
    if "dialog" in b and b["dialog"] is None:
        return "No dialog open"
    if isinstance(b.get("dialog"), dict) and b["dialog"].get("title"):
        return _cap(plain(f"{_amp(b['dialog']['title'])} is open"))
    if b.get("ran"):
        return "Done"
    if isinstance(b.get("steps"), list):
        n = len(b["steps"])
        return f"Done, {n} step{'s' if n != 1 else ''}"
    if isinstance(b.get("deleted"), list):
        return f"Deleted {len(b['deleted'])}"
    if isinstance(b.get("count"), int) and not isinstance(b.get("count"), bool):
        return f"{b['count']} found"
    # The answer's key value before a name or a note: a note is a warning
    # or an explanation, cut off on the window (core 0054, 0070, 0088).
    kv = call_value(name, b)
    if kv:
        return _cap(kv[:1].upper() + kv[1:])
    for k in ("created", "object", "sketch", "page", "body", "note"):
        if isinstance(b.get(k), str) and b[k].strip():
            return _cap(_sentence(b[k]) if k == "note" else plain(_amp(b[k])))
    if isinstance(b.get("path"), str):
        return _cap(plain("Wrote " + b["path"]))
    return "Done"


def raw_call(name, args):
    """The call as sent, for the curious (the row's tooltip), paths cut to
    their file names."""
    try:
        text = json.dumps(args or {}, ensure_ascii=False, default=str, separators=(", ", ": "))
    except Exception:
        text = str(args)
    return _cap(plain(f"{name} {text}"), MAX_CALL)

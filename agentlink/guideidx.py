# SPDX-License-Identifier: LGPL-2.1-or-later
"""The guides' index and reading (plain Python; used by tools.py's guide_read).

A guide is a markdown file of ## sections. Two conventions, both optional:

- A section headed "## Start here" is the guide's map: what to read before
  the first step and what to leave for its moment. The index names it first.
- A section meant for one moment of a task carries, on the line under its
  heading, an HTML comment
      <!-- later: when a loft or a boolean is slow -->
  The index lists such sections under later with that moment, so a reader
  takes the rest first and comes back for these when the moment arrives.
  The comment does not show in rendered markdown and is left out of the
  text guide_read answers.

Costs are approximate tokens: characters / 4.
"""
import json
import os
import re

START = "start here"
LATER = re.compile(r"^[ \t]*<!--\s*later:\s*(.*?)\s*-->[ \t]*\n?", re.I)
# A reply is cut past 60 000 characters (protocol.MAX_REPLY): several guides
# read at once stop before that, counted as the JSON they are sent as.
READ_CAP = 55_000


def tokens(text):
    return (len(text) + 3) // 4


def parse(text):
    """(title, head, sections): head the text before the first ## section;
    sections [{ name, text (from its heading on, the later comment taken
    out), when (a later section's moment, else None) }]."""
    title = next((l.lstrip("# ").strip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith("<!--")), "")
    parts = re.split(r"(?m)^## ", text)
    sections = []
    for p in parts[1:]:
        name, _, body = p.partition("\n")
        m = LATER.match(body)
        when = None
        if m:
            when, body = m.group(1) or "its own moment", body[m.end():]
        sections.append({"name": name.strip(), "text": f"## {name.strip()}\n{body}", "when": when})
    return title, parts[0], sections


def clean(text):
    """A guide whole, as guide_read answers it: the later comments taken out."""
    title, head, sections = parse(text)
    return head + "".join(s["text"] for s in sections)


def entry(topic, text):
    """A guide's line of the index: its sections with what each costs,
    Start here first, and the ones for a later moment."""
    title, _head, sections = parse(text)
    first = [s for s in sections if s["name"].lower() == START]
    order = first + [s for s in sections if s not in first]
    # The sections' names once: sectionTokens' keys, in order (a list of
    # them beside it, and each later section's cost again, were a third of
    # the index's ~15 000 characters, live).
    out = {"topic": topic, "title": title or topic, "chars": len(text), "tokens": tokens(text),
           "sectionTokens": {s["name"]: tokens(s["text"]) for s in order}}
    if first:
        out["start"] = first[0]["name"]
    later = [{"section": s["name"], "when": s["when"]} for s in sections if s["when"]]
    if later:
        out["later"] = later
        out["firstReadTokens"] = tokens(text) - sum(tokens(s["text"]) for s in sections if s["when"])
    return out


def pick(text, wanted):
    """The sections of a guide whose names begin with wanted (a name or a
    list of names, any case), in the order asked. (text, missing names,
    every section's name)."""
    _title, _head, sections = parse(text)
    names = [s["name"] for s in sections]
    asked = [wanted] if isinstance(wanted, str) else list(wanted)
    got, missing = [], []
    for w in asked:
        hit = [s for s in sections if isinstance(w, str) and w.strip() and s["name"].lower().startswith(w.strip().lower())]
        if hit:
            got += [h for h in hit[:1] if h not in got]
        else:
            missing.append(w)
    return "".join(s["text"] for s in got), missing, names


def read_many(texts, topics, section=None, cap=READ_CAP):
    """Several guides read in order until the reply would pass cap. texts:
    { topic: text }. { read: [{ topic, text }], chars, next: [topics not
    read], missing: [topics with no such section] }; the first guide is
    always read."""
    read, nxt, missing, size = [], [], [], 0
    for n, t in enumerate(topics):
        if nxt:
            nxt.append(t)
            continue
        if section:
            text, miss, _names = pick(texts[t], section)
            if not text:
                missing.append(t)
                continue
        else:
            text = clean(texts[t])
        cost = len(json.dumps(text, ensure_ascii=False)) + len(t) + 24
        if read and size + cost > cap:
            nxt.append(t)
            continue
        read.append({"topic": t, "text": text})
        size += cost
    out = {"read": read, "chars": sum(len(r["text"]) for r in read), "tokens": sum(tokens(r["text"]) for r in read)}
    if nxt:
        out["next"] = nxt
        out["note"] = f"Read up to about {cap // 1000} k characters: guide_read {{ topic: next }} reads on."
    if missing:
        out["missing"] = missing
    return out


# ---- common words for the guides (data/guide_words.json) -----------------------------------

WORDS = "guide_words.json"
_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", WORDS)


def _norm(w):
    return re.sub(r"[\s_\-]+", "", str(w).strip().lower())


def load_words(dirs=()):
    """The entries of data/guide_words.json, then those of a guide_words.json
    in each add-on guide folder (dirs). A file that does not read is passed
    over: the words only help, they never stop a guide."""
    out = []
    for p in [_DATA] + [os.path.join(d, WORDS) for d in dirs]:
        try:
            with open(p, encoding="utf-8") as f:
                got = json.load(f).get("entries") or {}
        except Exception:  # noqa: BLE001
            continue
        for e in got.values():
            if isinstance(e, dict) and e.get("work") and isinstance(e.get("guides"), list):
                out.append(e)
    return out


def words_lines(entries, topics):
    """One line per entry whose guides are here: "<work> is in feature and
    sketch." Made from the guides there now, so a guide that is gone is not
    named."""
    lines = []
    for e in entries:
        here = [g for g in e["guides"] if g in topics]
        if here:
            names = here[0] if len(here) == 1 else ", ".join(here[:-1]) + " and " + here[-1]
            lines.append(f"{e['work']} is in {names}.")
    return lines


def fuzzy(asked, topics, entries=(), k=4):
    """The guides an unknown topic may mean (decision 6, 24 Nov): the
    guides of an entry whose words match, a guide whose name holds the word
    or is held in it (sketches: sketch), then the close names by tool_find's
    helper (protocol.close_in). Guide names only: never a tool's input."""
    from .protocol import close_in

    if not isinstance(asked, str) or not asked.strip():
        return []
    n = _norm(asked)
    out = []
    for e in entries:
        words = {_norm(w) for w in e.get("words") or []} | {_norm(e.get("work", ""))}
        if n in words or any(len(n) >= 4 and (n in w or w in n) and len(w) >= 4 for w in words):
            out += [g for g in e["guides"] if g in topics]
    out += [t for t in topics if len(n) >= 3 and (t in n or n in t)]
    out += close_in(asked.strip().lower(), list(topics), k)
    return list(dict.fromkeys(out))[:k]

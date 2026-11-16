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
    out = {"topic": topic, "title": title or topic, "sections": [s["name"] for s in order], "chars": len(text), "tokens": tokens(text),
           "sectionTokens": {s["name"]: tokens(s["text"]) for s in order}}
    if first:
        out["start"] = first[0]["name"]
    later = [{"section": s["name"], "when": s["when"], "tokens": tokens(s["text"])} for s in sections if s["when"]]
    if later:
        out["later"] = later
        out["firstReadTokens"] = tokens(text) - sum(x["tokens"] for x in later)
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

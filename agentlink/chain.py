# SPDX-License-Identifier: LGPL-2.1-or-later
"""Answer chaining for batch (plain Python; used by tools.py's batch).

A call in a batch can take a value from a JSON file or from an earlier
call's answer without that value passing through the conversation:

  { "$file": "outline.json" }                      the file's whole contents
  { "$file": "outline.json", "$at": "loops.0.points" }   the part at that path
  { "$from": 2, "$at": "bodies.0.name" }           from call 2's answer

and a call can keep its own answer out of the reply: { tool, <its inputs>,
writeTo: "outline.json" } writes the answer to that file and the batch's result
for the call is { written: { path, bytes }, keys | length }.

$at is a dotted path of keys and list indices (from 0; -1 is the last).
Nothing here touches FreeCAD or checks where a file may be read or written:
the caller passes read_file and the path checks (agentlink/paths.py).
"""
import json
import os

# The most that one reference may bring in (the file's size, or the length of
# the answer it is taken from, as JSON).
MAX_BYTES = 20 * 1024 * 1024
FILE, FROM, AT = "$file", "$from", "$at"
# How many keys of what is there a refusal names.
KEYS_SHOWN = 40


class Miss(Exception):
    """A reference that cannot be followed: code and message as a refusal's."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def is_ref(v):
    return isinstance(v, dict) and (FILE in v or FROM in v)


def has_refs(v):
    """Whether any reference is anywhere inside v."""
    if is_ref(v):
        return True
    if isinstance(v, dict):
        return any(has_refs(x) for x in v.values())
    if isinstance(v, list):
        return any(has_refs(x) for x in v)
    return False


def there(v):
    """What a value is, for a refusal: an object's keys, a list's length,
    else its kind."""
    if isinstance(v, dict):
        keys = [str(k) for k in v]
        shown = ", ".join(keys[:KEYS_SHOWN]) + (f" … ({len(keys)} keys)" if len(keys) > KEYS_SHOWN else "")
        return f"an object with the keys: {shown}" if keys else "an empty object"
    if isinstance(v, list):
        return f"a list of {len(v)} (indices 0 to {len(v) - 1})" if v else "an empty list"
    if isinstance(v, str):
        return "text"
    if isinstance(v, bool):
        return "true/false"
    if v is None:
        return "null"
    return "a number"


def summary(v):
    """What an answer written to a file leaves in the reply: an object's
    keys, a list's length, else its kind."""
    if isinstance(v, dict):
        return {"keys": [str(k) for k in v][:KEYS_SHOWN], **({"keysInAll": len(v)} if len(v) > KEYS_SHOWN else {})}
    if isinstance(v, list):
        return {"length": len(v)}
    return {"kind": there(v)}


def at(value, path, where):
    """The part of value at a dotted path of keys and list indices. where:
    what value is, in a refusal's words ("outline.json", "call 2's answer")."""
    if path is None or path == "":
        return value
    if isinstance(path, bool) or not isinstance(path, (str, int)):
        raise Miss("invalid_input", f"{AT}: a dotted path of keys and list indices, \"loops.0.points\" — {where} is {there(value)}.")
    cur, done = value, []
    for part in str(path).split("."):
        so_far = ".".join(done) or "its top"
        if isinstance(cur, dict):
            if part not in cur:
                raise Miss("not_found", f"{AT} {path!r}: no key {part!r} at {so_far} of {where} — there it is {there(cur)}.")
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                i = int(part)
            except ValueError:
                raise Miss("not_found", f"{AT} {path!r}: {part!r} is not a list index, and {so_far} of {where} is {there(cur)}.") from None
            if not -len(cur) <= i < len(cur):
                raise Miss("not_found", f"{AT} {path!r}: no index {i} at {so_far} of {where} — there it is {there(cur)}.")
            cur = cur[i]
        else:
            raise Miss("not_found", f"{AT} {path!r}: {so_far} of {where} is {there(cur)}, with nothing under it — so {part!r} is not there.")
        done.append(part)
    return cur


def _from_file(ref, read_file):
    extra = sorted(k for k in ref if k not in (FILE, AT))
    if extra:
        raise Miss("invalid_input", f"{{ {FILE} }} takes only {AT} beside it, not {', '.join(extra)}: write {{ \"{FILE}\": path, \"{AT}\": \"a.0.b\" }} alone where the value goes.")
    name = ref[FILE]
    if not isinstance(name, str) or not name.strip():
        raise Miss("invalid_input", f"{FILE}: a .json file's path (relative: in the session's folder).")
    return at(read_file(name), ref.get(AT), name)


def _from_call(ref, answers, index, first):
    extra = sorted(k for k in ref if k not in (FROM, AT))
    if extra:
        raise Miss("invalid_input", f"{{ {FROM} }} takes only {AT} beside it, not {', '.join(extra)}: write {{ \"{FROM}\": call index, \"{AT}\": \"a.0.b\" }} alone where the value goes.")
    n = ref[FROM]
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise Miss("invalid_input", f"{FROM}: the index of an earlier call of this batch (calls are numbered from 0), not {n!r}.")
    if n >= index:
        raise Miss("invalid_input", f"{FROM}: {n} is not before this call (calls.{index}): a call takes only an earlier call's answer.")
    if n < first:
        raise Miss("invalid_state", f"{FROM}: call {n} ran in an earlier part of this batch (this part began at start: {first}), and its answer is not kept between parts — "
                                    f"give that call writeTo: \"file.json\" and read it here with {{ \"{FILE}\": \"file.json\", \"{AT}\": … }}.")
    got = answers.get(n)
    if got is None:
        raise Miss("invalid_state", f"{FROM}: call {n} has no answer to take from (it did not run).")
    if not got.get("ok"):
        raise Miss("invalid_state", f"{FROM}: call {n} ({got.get('tool')}) was refused, so it has no answer to take from: {got.get('error')}")
    if got.get("size", 0) > MAX_BYTES:
        raise Miss("invalid_input", f"{FROM}: call {n}'s answer is {got['size'] / 1048576:.0f} MB, over the {MAX_BYTES // 1048576} MB a reference may bring in.")
    return at(got.get("answer"), ref.get(AT), f"call {n}'s answer ({got.get('tool')})")


def resolve(value, read_file, answers, index, first=0):
    """value with every reference inside it replaced by what it names (a
    new value; the one given is left as it was). read_file(path) answers a
    JSON file's contents or raises Miss; answers: { call index: { ok, tool,
    answer | error, size } }; index: this call's; first: the index this part
    of the batch began at."""
    if is_ref(value):
        if FILE in value and FROM in value:
            raise Miss("invalid_input", f"{FILE} or {FROM}, not both in one reference.")
        return _from_file(value, read_file) if FILE in value else _from_call(value, answers, index, first)
    if isinstance(value, dict):
        return {k: resolve(v, read_file, answers, index, first) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, read_file, answers, index, first) for v in value]
    return value


def read_json(path, name, cache=None, may_list=None):
    """The contents of the JSON file at path (name: as the agent gave it).
    cache: { path: (mtime, size, data) }, so a file many references name is
    parsed once while it stays the same. may_list(folder): True when a miss
    may name the .json files of the folder (the read rule lets the agent
    read there); without it, a miss names none (red team 4, R4-1)."""
    try:
        st = os.stat(path)
    except OSError:
        folder = os.path.dirname(path)
        near = None
        try:
            if may_list is not None and may_list(folder):
                near = sorted(n for n in os.listdir(folder) if n.lower().endswith(".json"))
        except OSError:
            near = None
        if near is None and os.path.isdir(folder):
            raise Miss("not_found", f"{FILE}: {name} — no such file (a relative path is in the session's folder). A call writes its answer to one with writeTo: \"file.json\".") from None
        what = "there is no such folder" if near is None else (f"the .json files there: {', '.join(near[:KEYS_SHOWN])}" if near else "there are no .json files there")
        raise Miss("not_found", f"{FILE}: {name} — no such file (a relative path is in the session's folder); {what}. A call writes its answer to one with writeTo: \"file.json\".") from None
    if not os.path.isfile(path):
        raise Miss("invalid_input", f"{FILE}: {name} is a folder, not a .json file.")
    if st.st_size > MAX_BYTES:
        raise Miss("invalid_input", f"{FILE}: {name} is {st.st_size / 1048576:.0f} MB, over the {MAX_BYTES // 1048576} MB a reference may bring in — "
                                    "pass the file's path to a tool that reads files itself, or split it.")
    key = (st.st_mtime_ns, st.st_size)
    if cache is not None and cache.get(path, (None,))[0] == key:
        return cache[path][1]
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except ValueError as e:
        raise Miss("invalid_input", f"{FILE}: {name} is not JSON ({e}) — a reference reads .json files only.") from None
    except OSError as e:
        raise Miss("failed", f"{FILE}: {name} could not be read ({e}).") from None
    if cache is not None:
        cache[path] = (key, data)
    return data


def write_answer(path, answer):
    """answer written to path as JSON (through a .part file, so a reader
    never sees half of it). { path, bytes }."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(answer, f, ensure_ascii=False, default=str)
    os.replace(tmp, path)
    return {"path": path, "bytes": os.path.getsize(path)}


def to_name(to, i):
    """A call's to checked as a name: a .json file's path. The refusal's
    words, or None."""
    if not isinstance(to, str) or not to.strip() or not to.lower().endswith(".json"):
        return f"calls.{i}.writeTo: a .json file's path the call's answer is written to (relative: in the session's folder), not {to!r}. Nothing was run."
    return None


def written_row(tool, answer, written):
    """What the batch's result carries for a call whose answer went to a
    file: where it is, its shape, and the health's facts when the call had
    them (a recompute error must not hide in a file)."""
    row = {"tool": tool, "ok": True, "written": written, **summary(answer)}
    h = answer.get("health") if isinstance(answer, dict) else None
    if isinstance(h, dict) and h.get("facts"):
        row["health"] = {k: h[k] for k in ("facts", "errors", "build") if k in h}
    return row

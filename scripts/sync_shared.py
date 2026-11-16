# SPDX-License-Identifier: LGPL-2.1-or-later
"""Agent Link's shared files copied into the add-ons that carry a copy of
them (the copy-sync check). Each shared file is the same in every add-on
but for its first line, the licence of the add-on that carries it; this
copies Agent Link's version over each copy found in the checkouts given,
keeping that first line.

    python3 scripts/sync_shared.py --list                 # the shared files
    python3 scripts/sync_shared.py --check ../safetynet-freecad …   # exit 1 where a copy differs
    python3 scripts/sync_shared.py ../safetynet-freecad …           # copy Agent Link's over them

A copy is a file of the same name under the checkout (tests, .git and
build folders left out) whose text says it is the same in every add-on
(MARK). Nothing else is touched; commit in each checkout yourself."""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
# Agent Link's file → the line every copy carries to say it is one.
SHARED = {
    "agentlink/layout.py": "This file is the same in every add-on but for its first line",
}
SKIP_DIRS = {".git", "__pycache__", "tests", "build", "dist", "node_modules"}


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _body(text):
    """The text after its first line (the licence line)."""
    return text.split("\n", 1)[1] if "\n" in text else ""


def copies(checkout, name, mark):
    """The files in checkout that are copies of the shared file name."""
    out = []
    for d, dirs, files in os.walk(checkout):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for f in sorted(files):
            if f == os.path.basename(name):
                p = os.path.join(d, f)
                try:
                    if mark in _read(p):
                        out.append(p)
                except (OSError, UnicodeDecodeError):
                    pass
    return out


def sync(checkouts, check=False, root=ROOT, shared=None):
    """(copies that differ, copies written)."""
    differ, written = [], []
    for name, mark in (shared or SHARED).items():
        ours = _read(os.path.join(root, name))
        for ck in checkouts:
            if os.path.realpath(ck) == os.path.realpath(root):
                continue
            for p in copies(ck, name, mark):
                theirs = _read(p)
                if _body(theirs) == _body(ours):
                    continue
                differ.append(p)
                if not check:
                    first = theirs.split("\n", 1)[0]
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(first + "\n" + _body(ours))
                    written.append(p)
    return differ, written


def main(argv):
    if "--list" in argv:
        for name in SHARED:
            print(name)
        return 0
    check = "--check" in argv
    checkouts = [a for a in argv if not a.startswith("--")]
    if not checkouts:
        sys.stderr.write(__doc__)
        return 2
    differ, written = sync(checkouts, check=check)
    for p in differ:
        print(("differs: " if check else "copied: ") + p)
    return 1 if (check and differ) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

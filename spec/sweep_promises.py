"""Members the specification defines, against members the validator reads.

    python3 spec/sweep_promises.py

Three times in one week a word in the specification made a promise no line of
the validator kept. The clock said a record's write times meant something and
nothing bounded them. The anchor's `kind` named a scheme and nothing dispatched
on it. `source` was defined as "a stable identifier" and its value is read
nowhere. Each was found by somebody noticing, which does not scale and did not
catch the first two for months.

babyblueviper1's framing on machine-testimony#85 is the fix, and it is two
sets. One is the members whose definitions assert a property. The other is the
members whose values the validator actually reads. Everything in the first set
and not the second is a candidate, found by enumeration rather than by
attention.

**This file computes the second set, and takes the first from the draft rather
than from the implementation.** That direction is the whole point. The first
version read the member list out of the validator's own `REQUIRED` table, so it
could only find members the validator already knew about: 18 of them, against
34 the draft defines. It found `source` and would have missed the clock and the
anchor, which is two of the three cases that motivated writing it. A member the
implementation never names cannot be found by reading the implementation.

**CANDIDATES, NOT DEFECTS.** A member whose value nothing reads is not
automatically a bug, and reading the output as a defect list would do more harm
than the sweep does good. There are three honest resolutions and the third is
the one that gets misread:

  a check          the validator should test the property and did not
  a reworded       the definition promises more than the format delivers, and
  definition       the definition is what should move, as `source` did
  a stated limit   the property cannot be established from inside a record at
                   all, so it is disclosed rather than checked. The clock is
                   this: nothing in a record can prove when it was written
                   without somebody outside it, so TR-4 bounds write times
                   against an anchor and machine-testimony#49 stays open for
                   the unanchored case. That is a limit, not unfinished work.

WHAT IT STILL DOES NOT DO, stated because the alternative is somebody finding
out by running it.

It does not read the definitions. It reports which members carry a definition
the validator never consults, and a human still decides whether that definition
asserts anything at all. Turning "asserts a property" into data is the
remaining half, and it is prose work, member by member.

The draft is parsed as markdown definition lists, `name:` on one line and `: `
on the next. That is a shape rather than a schema, so a member written another
way is invisible here. The count is printed for exactly that reason: if it
falls, the parse broke rather than the format shrinking.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import ast
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR = os.path.join(HERE, "testimony_validate.py")
DRAFT = os.path.join(HERE, "draft-clifford-testimony-record-02.md")

# Tables that declare a member exists without reading its value.
DECLARING_TABLES = ("REQUIRED", "OPTIONAL", "ENUMS", "ACTOR_KINDS")

# Tables whose VALUES are member names the validator then indexes entries by.
# `ACTOR_FIELDS` maps an entry type to the member holding its actor, and the
# check reads `e[f]` where f came out of that map, so the member name is never
# a literal anywhere in the file.
#
# THIS IS THE SWEEP'S OWN BLIND SPOT, and it produced a false candidate on the
# first run: `asserted_by` came out unread while TR-1's "every actor is an
# object naming an id and a kind" was reading it the whole time. A sweep that
# reports a checked member as unchecked is worse than no sweep, so any new
# indirection table has to be named here.
INDIRECTION_TABLES = ("ACTOR_FIELDS",)

MEMBER = re.compile(r"^([a-z][a-z0-9_]*):[ \t]*$")


def _tree():
    return ast.parse(io.open(VALIDATOR, encoding="utf-8").read())


def defined() -> dict:
    """Members the draft defines, mapped to the first line of the definition."""
    lines = io.open(DRAFT, encoding="utf-8").read().split(chr(10))
    out = {}
    for i, line in enumerate(lines[:-1]):
        m = MEMBER.match(line)
        if m and lines[i + 1].startswith(": "):
            out.setdefault(m.group(1), lines[i + 1][2:].strip())
    return out


def enumerated() -> set:
    """Members whose value is checked against an allowlist."""
    out = set()
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue
        if "ENUMS" not in [t.id for t in node.targets
                           if isinstance(t, ast.Name)]:
            continue
        for k in node.value.keys:
            if isinstance(k, ast.Tuple) and len(k.elts) == 2:
                if isinstance(k.elts[1], ast.Constant):
                    out.add(k.elts[1].value)
    return out


def indirect() -> set:
    """Member names reaching the validator as data rather than as code."""
    out = set()
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue
        if not any(t.id in INDIRECTION_TABLES for t in node.targets
                   if isinstance(t, ast.Name)):
            continue
        for v in getattr(node.value, "values", []):
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                out.add(v.value)
    return out


def read_values() -> set:
    """Members whose value is read for anything, anywhere in the validator.

    Deliberately generous. A name here might be read for something unrelated to
    its own promise, but claiming nothing reads a member that something does is
    the damaging direction, so the sweep errs toward saying a member IS read.
    """
    tree = _tree()
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                t.id in DECLARING_TABLES for t in node.targets
                if isinstance(t, ast.Name)):
            for sub in ast.walk(node.value):
                skip.add(id(sub))

    out = set()
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if (isinstance(node, ast.Subscript)
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            out.add(node.slice.value)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            out.add(node.args[0].value)
    return out


def sweep() -> list:
    spec_members = defined()
    read = read_values() | indirect()
    enums = enumerated()
    rows = []
    for m in sorted(spec_members):
        if m in enums:
            state = "allowlist"
        elif m in read:
            state = "read"
        else:
            state = "NOT READ"
        rows.append((m, state, spec_members[m]))
    return rows


def main() -> int:
    rows = sweep()
    bare = [r for r in rows if r[1] == "NOT READ"]

    print("Members the draft defines, and what the validator does with each.")
    print()
    w = max(len(r[0]) for r in rows)
    for m, state, _ in rows:
        print("  %-*s  %s" % (w, m, state))

    print()
    print("%d members defined in the draft, %d value-checked, %d not read."
          % (len(rows), len(rows) - len(bare), len(bare)))
    print()
    if bare:
        print("CANDIDATES. Each needs a check, a reworded definition, or a")
        print("stated limit. None is a defect until somebody decides which,")
        print("and the third reads as unfinished work when it is not.")
        print()
        for m, _, text in bare:
            print("  %s" % m)
            print("      %s" % text[:94])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

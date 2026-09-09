"""Which members the validator reads, and which it only checks are present.

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

**This file computes the second set only, and that is the whole point of
splitting them.** It needs no judgement: reading the value of a member is a
syntactic fact about one file, visible as a subscript or a `.get()` outside the
tables that merely declare a member exists. The first set is prose and has to
be written down by hand before anything can check it.

The order matters more than it looks. Computing this half first inverts the
work: rather than writing an assertion for every member in the format, only the
members that come out of here with NO value check need one, because a member
whose value is already checked cannot be making an unkept promise about itself.

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

WHAT IT DOES NOT COVER, AND THIS IS THE FIRST THING TO FIX.

It sweeps the members in `REQUIRED`, which is the only table naming members,
and that is 18 of them. Run against the three cases that motivated it, it finds
ONE. `source` yes. The clock no, because `write_time` is required by its own
check rather than by the table. The anchor no, because its `kind` lives inside
an integrity entry rather than in the required list.

So the honest claim for this file is narrow: it enumerates the required members
and finds the one whose value nothing reads. It is not yet the sweep the issue
described, and saying otherwise would be the same defect it exists to find, in
the tool that finds it.

Widening it needs the member list to come from the draft rather than from the
validator, because a member the validator never names cannot be found by reading
the validator. That is the same reason the assertions have to be written down as
data: both halves of the sweep need the specification as a machine readable
thing, and neither half gets there by parsing the implementation harder.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR = os.path.join(HERE, "testimony_validate.py")

# The tables that declare a member exists without reading it. A name appearing
# only inside these is presence-checked, which is exactly the state this sweep
# exists to find.
DECLARING_TABLES = ("REQUIRED", "OPTIONAL", "ENUMS", "ACTOR_KINDS")

# Tables whose VALUES are member names the validator then indexes entries by.
# `ACTOR_FIELDS` maps an entry type to the member holding its actor, and the
# check reads `e[f]` where f came out of that map, so the member name is never
# a literal anywhere in the file.
#
# THIS IS THE SWEEP'S OWN BLIND SPOT, and it produced a false candidate on the
# first run: `asserted_by` came out PRESENCE ONLY while TR-1's "every actor is
# an object naming an id and a kind" was reading it the whole time. A sweep that
# reports a member as unchecked when it is checked is worse than no sweep, so
# any new indirection table has to be named here. That requirement is a stated
# limit of this tool in exactly the sense the docstring describes, which is a
# fair thing for it to inherit from what it measures.
INDIRECTION_TABLES = ("ACTOR_FIELDS",)


def _tree():
    return ast.parse(io.open(VALIDATOR, encoding="utf-8").read())


def declared() -> dict:
    """Every member the format names, and which entry types carry it."""
    out = {}
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "REQUIRED" not in names:
            continue
        for k, v in zip(node.value.keys, node.value.values):
            if not isinstance(k, ast.Constant):
                continue
            for m in getattr(v, "elts", []):
                if isinstance(m, ast.Constant):
                    out.setdefault(m.value, set()).add(k.value)
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
                f = k.elts[1]
                if isinstance(f, ast.Constant):
                    out.add(f.value)
    return out


def _in_declaring_table(node, tables) -> bool:
    return any(node in t for t in tables)


def indirect() -> set:
    """Member names that reach the validator as data rather than as code."""
    out = set()
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not any(n in INDIRECTION_TABLES for n in names):
            continue
        for v in getattr(node.value, "values", []):
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                out.add(v.value)
    return out


def read_values() -> set:
    """Members whose value is read for anything, anywhere in the validator.

    A subscript or a `.get()` naming the member, outside the tables that only
    declare it. This is deliberately generous: a name that turns up here might
    be read for something unrelated to its own promise, and a false negative
    (claiming nothing reads it when something does) would be the damaging
    direction, so the sweep errs toward saying a member IS read.
    """
    tree = _tree()
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(n in DECLARING_TABLES for n in names):
                for sub in ast.walk(node.value):
                    skip.add(id(sub))

    out = set()
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Subscript) and isinstance(node.slice,
                                                          ast.Constant):
            if isinstance(node.slice.value, str):
                out.add(node.slice.value)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            out.add(node.args[0].value)
    return out


def main() -> int:
    decl, enums = declared(), enumerated()
    read = read_values() | indirect()

    rows = []
    for member in sorted(decl):
        if member in enums:
            state = "allowlist"
        elif member in read:
            state = "read"
        else:
            state = "PRESENCE ONLY"
        rows.append((member, ",".join(sorted(decl[member])), state))

    w = max(len(r[0]) for r in rows)
    print("Members the format requires, and what the validator does with each.")
    print("Candidates are the PRESENCE ONLY rows: nothing reads the value, so")
    print("any promise the definition makes about it is unkept by this file.")
    print()
    for m, types, state in rows:
        print("  %-*s  %-28s %s" % (w, m, types, state))

    bare = [r[0] for r in rows if r[2] == "PRESENCE ONLY"]
    print()
    print("%d members required, %d value-checked, %d presence only."
          % (len(rows), len(rows) - len(bare), len(bare)))
    if bare:
        print("Candidates: " + ", ".join(bare))
    print()
    print("These are CANDIDATES, not defects. Each needs one of three answers:")
    print("a check, a reworded definition, or a stated limit. See the module")
    print("docstring for why the third is the one that gets misread.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

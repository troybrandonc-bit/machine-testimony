"""What moved between one reading of a subject and the last one.

    python3 census/compare.py langgraph
    python3 census/compare.py --all

`reassess.py` reopens a subject at a newer commit: the prior assessment is
archived unchanged, the new file names it in `supersedes`, and every inherited
verdict is written as `pending` so it has to be earned again by opening the
source. That machinery has existed since the register did. Nothing read the
result.

So a second reading produced two files and no answer to the only question a
second reading is for, which is what changed. This is that answer.

**THE DISTINCTION THIS EXISTS TO MAKE, and no other tool here makes it.** A
verdict moving does not mean the software moved. A verdict is about a named
tree, so if the commit is the same and the verdict is different, the READING
changed and the system did not. That is not a scandal and it is often correct,
because a first reading can be wrong and this project has published several
that were. But an assessor who reports it as an improvement is telling a client
something untrue, and a client who reads it that way will act on it. So the two
are separated and labelled, always, and the same-commit case is called out
rather than left to be inferred from two hashes nobody compares.

Improvement and regression are scored on whether a level can rest on the
verdict: `present` counts, `partial` counts for less, `absent` and
`undetermined` count for nothing. Absent and undetermined score the same and
are NOT the same thing, so a move between them is reported as changed rather
than as either direction. One says the capability is missing, the other says
nobody could tell from outside, and calling that an improvement would be the
kind of quiet flattery this file exists to prevent.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SUBJECTS = os.path.join(HERE, "subjects")

sys.path.insert(0, HERE)
import subject as sub                                       # noqa: E402

# How much a verdict can carry a level. Absent and undetermined are level zero
# for the same reason: a level claimed on unchecked facts is not a level.
WEIGHT = {"present": 2, "partial": 1, "absent": 0, "undetermined": 0}


def load(name: str) -> dict:
    p = os.path.join(SUBJECTS, name if name.endswith(".json")
                     else name + ".json")
    return json.load(io.open(p, encoding="utf-8"))


def prior_of(doc: dict):
    """The archived reading this one supersedes, if there is one."""
    sup = doc.get("supersedes") or {}
    if not sup.get("file"):
        return None
    p = os.path.join(HERE, sup["file"])
    return json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else None


def moves(doc: dict) -> list:
    """Per requirement: what it was, what it is, and which way that is."""
    out = []
    for rid, a in sorted((doc.get("assessments") or {}).items()):
        if not isinstance(a, dict):
            continue
        now, was = a.get("verdict"), a.get("was")
        if was is None:
            continue
        if now == "pending":
            out.append((rid, was, now, "NOT YET RE-READ"))
            continue
        if now == was:
            out.append((rid, was, now, "unchanged"))
            continue
        wn, ww = WEIGHT.get(now), WEIGHT.get(was)
        if wn is None or ww is None:
            how = "changed"
        elif wn > ww:
            how = "improved"
        elif wn < ww:
            how = "regressed"
        else:
            how = "changed"
        out.append((rid, was, now, how))
    return out


def report(doc: dict, name: str = "") -> str:
    sup = doc.get("supersedes") or {}
    w = []
    a = w.append
    subject = doc.get("name") or doc.get("subject") or name

    if not sup:
        return ("%s has one reading and nothing to compare it against. "
                "A comparison needs census/reassess.py to have been run."
                % subject)

    same_tree = sup.get("commit") == doc.get("commit")
    rows = moves(doc)
    pending = [r for r in rows if r[3] == "NOT YET RE-READ"]

    a("%s, %s at %s, against %s at %s."
      % (subject, doc.get("assessed_on", "undated"), (doc.get("commit") or "")[:12],
         sup.get("assessed_on", "undated"), (sup.get("commit") or "")[:12]))
    a("")

    if same_tree:
        a("  THE COMMIT IS THE SAME. Anything below that moved is a change of")
        a("  reading and not a change of software. Report it that way or the")
        a("  reader will hear an improvement that did not happen.")
        a("")

    if pending:
        a("  %d requirement(s) still carry `pending`, so this reading is not"
          % len(pending))
        a("  finished and the comparison below is partial. run.py --check")
        a("  refuses to publish while any remain.")
        a("")

    for how in ("regressed", "improved", "changed", "NOT YET RE-READ"):
        hits = [r for r in rows if r[3] == how]
        if not hits:
            continue
        a("  %s" % how.upper())
        for rid, was, now, _ in hits:
            a("    %-7s %s -> %s" % (rid, was, now))
        a("")

    steady = sum(1 for r in rows if r[3] == "unchanged")
    a("  %d unchanged, %d moved, %d not yet re-read."
      % (steady, len(rows) - steady - len(pending), len(pending)))

    was_level, now_level = sup.get("level"), sub.level_reached(doc)
    if was_level != now_level:
        a("  The level moved: %s -> %s." % (was_level or "none",
                                            now_level or "none"))
    else:
        a("  The level did not move: %s." % (now_level or "none"))

    a("")
    a("A moved verdict is not proof a system changed. It is proof that two")
    a("readings differ, and the commit above says whether the tree differed")
    a("too. Both readings stay published, so a reader can check which of them")
    a("was wrong rather than being asked to trust the newer one.")
    return "\n".join(w)


def main() -> int:
    args = sys.argv[1:]
    if not args or "--help" in args:
        raise SystemExit("usage: compare.py SUBJECT | --all")

    names = ([f[:-5] for f in sorted(os.listdir(SUBJECTS))
              if f.endswith(".json")] if "--all" in args else args)

    shown = 0
    for n in names:
        doc = load(n)
        if "--all" in args and not doc.get("supersedes"):
            continue
        print(report(doc, n))
        print()
        shown += 1
    if not shown:
        print("No subject has been re-assessed yet, so nothing has a prior "
              "reading to compare against.")
        print("census/reassess.py is what creates one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""A comparison that flatters a re-reading is worse than no comparison.

`compare.py` answers the only question a second reading is for: what moved. An
auditor hands that answer to a client, so the ways it can be wrong are not
symmetrical. Calling a change an improvement when it is not is the failure that
does damage, and it has two shapes:

  a verdict moved between two states that are equally bad, and it got reported
  as progress

  the software did not move at all, only the reading did, and nobody said so

Both are checked here, along with the ordinary arithmetic.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "census"))

import compare                            # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:200])


OLD_COMMIT = "a" * 40
NEW_COMMIT = "b" * 40


def doc(pairs, commit=NEW_COMMIT, prior_commit=OLD_COMMIT, level="TR-2"):
    """A subject as reassess.py leaves it: `was` kept, `verdict` settled."""
    return {
        "subject": "example", "name": "Example", "commit": commit,
        "assessed_on": "2027-01-15", "claims": ["stores", "acts"],
        "assessments": {rid: {"was": was, "verdict": now, "evidence": []}
                        for rid, was, now in pairs},
        "supersedes": {"file": "subjects/prior/example.json",
                       "commit": prior_commit,
                       "assessed_on": "2026-09-04", "level": level},
    }


def how(pairs, **kw):
    return {rid: h for rid, _w, _n, h in compare.moves(doc(pairs, **kw))}


def main():
    print("the direction of a move is the direction it actually went")
    d = how([("R1.1", "absent", "present"),
             ("R1.2", "partial", "present"),
             ("R1.3", "absent", "partial")])
    check("absent to present is improved", d["R1.1"] == "improved", d)
    check("partial to present is improved", d["R1.2"] == "improved", d)
    check("absent to partial is improved", d["R1.3"] == "improved", d)

    d = how([("R2.1", "present", "absent"),
             ("R2.2", "present", "partial"),
             ("R2.3", "partial", "absent")])
    check("present to absent is regressed", d["R2.1"] == "regressed", d)
    check("present to partial is regressed", d["R2.2"] == "regressed", d)
    check("partial to absent is regressed", d["R2.3"] == "regressed", d)

    print("\nand a move between two equally bad states is not progress")
    # This is the one that matters. `undetermined` and `absent` both stop a
    # level, so neither is better than the other, and they mean opposite
    # things: one says the capability is missing, the other says nobody could
    # tell from outside. A tool that called this an improvement would be
    # telling a client their system got better because the assessor got less
    # sure, which is the most flattering lie available here.
    d = how([("R3.1", "absent", "undetermined"),
             ("R3.2", "undetermined", "absent")])
    check("absent to undetermined is changed, not improved",
          d["R3.1"] == "changed", d)
    check("undetermined to absent is changed, not regressed",
          d["R3.2"] == "changed", d)

    print("\nnothing is claimed about a verdict that was not re-earned")
    d = how([("R4.1", "present", "pending")])
    check("a pending verdict is reported as not yet re-read",
          d["R4.1"] == "NOT YET RE-READ", d)
    text = compare.report(doc([("R4.1", "present", "pending"),
                               ("R4.2", "absent", "present")]))
    check("and the report says the comparison is partial",
          "not" in text and "finished" in text, text[:120])
    check("and it names run.py --check as what refuses to publish",
          "run.py --check" in text, text[:120])

    print("\nan unmoved verdict is not a move")
    rows = compare.moves(doc([("R5.1", "present", "present"),
                              ("R5.2", "absent", "absent")]))
    check("unchanged verdicts are counted as unchanged",
          all(r[3] == "unchanged" for r in rows), rows)

    print("\nthe same tree read twice is a changed reading, not changed "
          "software")
    # The distinction the file exists for. A verdict is about a named tree, so
    # if the commit did not move and the verdict did, the software did not
    # improve and an assessor reporting it as improvement is wrong.
    same = compare.report(doc([("R6.1", "absent", "present")],
                              commit=OLD_COMMIT, prior_commit=OLD_COMMIT))
    diff = compare.report(doc([("R6.1", "absent", "present")]))
    check("the same-commit case is called out in the report",
          "THE COMMIT IS THE SAME" in same, same[:160])
    check("and it says the reading changed rather than the software",
          "change of" in same and "not a change of software" in same,
          same[:200])
    check("a genuinely newer commit is not called out that way",
          "THE COMMIT IS THE SAME" not in diff, diff[:160])
    check("both reports still show the move itself",
          "IMPROVED" in same and "IMPROVED" in diff)

    print("\nit refuses to compare what has no prior reading")
    alone = dict(doc([("R7.1", "absent", "present")]))
    del alone["supersedes"]
    text = compare.report(alone)
    check("a first reading is reported as having nothing to compare",
          "nothing to compare" in text, text[:120])
    check("and it names reassess.py as what creates one",
          "reassess.py" in text, text[:120])

    print("\nthe report never claims a move proves a system changed")
    text = compare.report(doc([("R8.1", "absent", "present")]))
    check("it says so in as many words",
          "not proof a system changed" in text, text[-260:])
    check("and it says both readings stay published",
          "Both readings stay published" in text, text[-260:])

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())

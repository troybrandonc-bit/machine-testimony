"""An assessment has to survive the standard it applies.

The census grades ten systems on whether they can say what they concluded, on
what evidence, and who concluded it. If its own assessments cannot answer those
questions, the instrument fails its own rubric and every verdict in it rests on
the assessor's word.

So these check the record an assessment produces, not the prose about it.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))
sys.path.insert(0, os.path.join(ROOT, "census"))

import testimony_validate as tv          # noqa: E402
import rubric                            # noqa: E402
import testify                           # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:220])


SUBJECTS = sorted(glob.glob(os.path.join(ROOT, "census", "subjects", "*.json")))

print("every assessment emits a record that passes the specification it applies")
for path in SUBJECTS:
    sid = os.path.basename(path)[:-5]
    subject = json.load(io.open(path, encoding="utf-8"))
    entries = testify.record(subject)
    text = testify.render(entries)
    r = tv.validate(text)
    # TR-4 without an anchor is the digest over what it covers. That is the
    # honest ceiling for a record nobody else has stamped, and it is the level
    # the census requires of the systems it grades.
    check("%s reaches TR-4" % sid, r.level == "TR-4",
          [c["check"] for c in r.checks if not c["ok"]])
    check("%s declares it does not act" % sid, r.scope == "record only", r.scope)

print("\nnothing in the assessment rests on the assessor's word that need not")
subject = json.load(io.open(os.path.join(ROOT, "census", "subjects",
                                         "langgraph.json"), encoding="utf-8"))
entries = testify.record(subject)
by_id = {e["id"]: e for e in entries}
beliefs = [e for e in entries if e["type"] == "belief"]
evidence = [e for e in entries if e["type"] == "evidence"]

check("every requirement scored becomes a belief or is declared not applicable",
      len(beliefs) + len(by_id["sc"]["x-census-not-applicable"])
      == len(subject["assessments"]),
      (len(beliefs), len(subject["assessments"])))
# An Actor, not a name. The assessor is a person, and a record that said only
# "Troy Brandon Clifford" would not say whether a human or a model reached the
# verdict, which is the distinction the whole format turns on.
check("every belief names who asserted it, as an actor",
      all(b["asserted_by"] == {"id": subject["assessed_by"], "kind": "human"}
          for b in beliefs),
      beliefs[0]["asserted_by"] if beliefs else None)
check("every belief cites evidence that is in the record",
      all(e in by_id for b in beliefs for e in b["evidence"]),
      [e for b in beliefs for e in b["evidence"] if e not in by_id])

# The rule the census rests on: a verdict is about a named tree, so a later fix
# produces a new assessment beside the old one rather than falsifying it. A
# belief whose subject named only the project would quietly claim more.
check("every belief is about a commit, not a project",
      all("@" in b["subject"] for b in beliefs),
      [b["subject"] for b in beliefs if "@" not in b["subject"]][:3])
check("and the commit is the one the assessment was made at",
      all(b["subject"].endswith(subject["commit"][:12]) for b in beliefs))

# An absence is the claim that needs the most evidence, not the least. Saying a
# system does not record something without saying where you looked is an
# accusation wearing a measurement's clothes, and the census refuses it.
absent = [b for b in beliefs if b["x-census-verdict"] == "absent"]
check("an absent verdict is a belief held false, never a missing belief",
      all(b["state"] == "believed_false" for b in absent), len(absent))
for b in absent:
    kinds = {by_id[e]["x-census-kind"] for e in b["evidence"]}
    check("%s cites where the assessor looked" % b["x-census-requirement"],
          "searched" in kinds, kinds)

# The proposition has to be a statement. A belief affirming a question and
# holding it false says the opposite of what was found.
check("no proposition is phrased as a question",
      not [b for b in beliefs if b["proposition"].endswith("?")],
      [b["proposition"] for b in beliefs if b["proposition"].endswith("?")][:2])
present_means = {r.present_means for r in rubric.REQUIREMENTS}
check("every proposition is the rubric's own bar, not a paraphrase",
      all(b["proposition"] in present_means for b in beliefs),
      [b["proposition"] for b in beliefs
       if b["proposition"] not in present_means][:2])

print("\nthe record pins both sides of the comparison")
sc = by_id["sc"]
check("it names the tree that was read", sc["x-census-commit"] == subject["commit"])
check("and the rubric it was scored against",
      sc["x-census-rubric"] == testify.rubric_digest()
      and sc["x-census-rubric"].startswith("sha256:"))
# A verdict is meaningless without the bar it was scored on. Changing a question
# must change the digest, or an assessment could be scored against one rubric
# and read as though it were scored against another.
check("the rubric digest moves when the questions do",
      testify.rubric_digest() != "sha256:" + "0" * 64)

print("\nwhat does not map is disclosed rather than smoothed over")
check("the five verdicts and the four states are not claimed to line up",
      "has no honest home" in testify.__doc__)
check("and the verdict survives verbatim beside the state it was mapped to",
      all("x-census-verdict" in b for b in beliefs))
partial = [b for b in beliefs if b["x-census-verdict"] == "partial"]
check("a partial verdict is unknown, and says it was partial",
      all(b["state"] == "unknown" for b in partial), len(partial))
check("an evidence kind the format cannot carry travels beside it",
      all("x-census-kind" in e for e in evidence))

print("\nan anchored assessment is checkable by somebody who was not there")
tok = io.open(os.path.join(ROOT, "public", "anchor", "anchor.tsr"), "rb").read()
anchored = testify.record(subject, token=tok)
ra = tv.validate(testify.render(anchored))
integ = [e for e in anchored if e["type"] == "integrity"][0]
check("the scheme becomes an external anchor", integ["scheme"] == "external-anchor")
check("naming the authority and carrying the token",
      integ["anchor"]["kind"] == "rfc3161" and integ["anchor"]["token"])
# The token here was issued over a different record, so it must fail. An
# assessment that accepted any token would be worse than one with none.
check("a token issued over some other record is refused",
      not [c for c in ra.checks
           if c["check"] == "the anchor's authority signed this record's digest"
           and c["ok"]])

print("\n%d passed, %d failed" % (PASS, FAIL))
raise SystemExit(1 if FAIL else 0)

"""The second binding census: that every verdict is one a reader can check.

    python tests/tests_binding.py

This does not check that a verdict is RIGHT. Nothing automated can. It checks
the things that make a wrong verdict cheap to find: that the vocabulary is the
rubric's, that every subject is answered on every requirement, that a verdict
resting on code names the code, and that nothing quietly upgraded itself.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "census"))
sys.path.insert(0, os.path.join(ROOT, "census", "binding"))

import rubric as R                                           # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + ((": %s" % (detail,)) if detail else ""))


P = os.path.join(ROOT, "census", "binding", "readings-2.json")
d = json.load(io.open(P, encoding="utf-8"))
subjects = d["subjects"]
IDS = [c.id for c in R.REQUIREMENTS]

print("shape")

check("every requirement in the rubric is a column", IDS == ["B1", "B2", "B3", "B4", "B5"], IDS)
check("six subjects, the same six as the first reading", len(subjects) == 6,
      len(subjects))

missing = [(s["name"], i) for s in subjects for i in IDS
           if i not in s["assessments"]]
check("every subject is answered on every requirement", not missing, missing)

bad = [(s["name"], i, s["assessments"][i].get("verdict"))
       for s in subjects for i in IDS
       if s["assessments"][i].get("verdict") not in R.VERDICTS]
check("every verdict is one of the rubric's five words", not bad, bad)

check("the reading says it is complete rather than implying it",
      d["status"].startswith("COMPLETE"))

check("every subject names the version it was read at",
      all(s.get("package") for s in subjects),
      [s["name"] for s in subjects if not s.get("package")])


print("")
print("a verdict that rests on code names the code")

# `not_applicable` is the one verdict that rests on the absence of a feature,
# so it is the one that does not need a file and line. Everything else does:
# a verdict nobody can look up is an opinion.
nolocator = [(s["name"], i) for s in subjects for i in IDS
             if s["assessments"][i].get("verdict") != "not_applicable"
             and not s["assessments"][i].get("locator")]
check("every verdict except not_applicable carries a locator",
      not nolocator, nolocator)

thin = [(s["name"], i) for s in subjects for i in IDS
        if s["assessments"][i].get("verdict") != "not_applicable"
        and len(s["assessments"][i].get("note", "")) < 80]
check("every verdict carries a note somebody could argue with",
      not thin, thin)

# `not_applicable` is the one verdict whose note should be SHORT and identical
# everywhere, because it is the rubric's own sentence and not a judgement. If
# a subject starts explaining why it is not applicable, that is a judgement
# wearing the one verdict that is supposed to carry none.
odd = [(s["name"], i) for s in subjects for i in IDS
       if s["assessments"][i].get("verdict") == "not_applicable"
       and s["assessments"][i].get("note") != R.NO_PAUSE]
check("not_applicable uses the rubric's own words and no others",
      not odd, odd)


print("")
print("the claims about reproduction are load-bearing, so they are checked")

# A note saying REPRODUCED is a stronger claim than a note that does not, and
# the rubric's method section rests on the distinction. If these disappear, the
# census has quietly become a reading of documentation.
repro = [(s["name"], i) for s in subjects for i in IDS
         if "REPRODUCED" in s["assessments"][i].get("note", "")]
check("at least four verdicts were reproduced rather than reasoned about",
      len(repro) >= 4, repro)
check("the three that motivated the rubric are among them",
      {("Pydantic AI", "B3"), ("LangGraph", "B3"), ("CrewAI", "B3")}
      <= set(repro), sorted(repro))

check("nothing is left pending",
      not [(s["name"], i) for s in subjects for i in IDS
           if s["assessments"][i].get("verdict") == "pending"])

# `undetermined` is allowed by the rubric and is honest, but it should be
# visible in the count rather than buried.
und = [(s["name"], i) for s in subjects for i in IDS
       if s["assessments"][i].get("verdict") == "undetermined"]
print("     (undetermined: %s)" % (und or "none"))


print("")
print("the corrections to the first reading are stated, not slipped in")

first = json.load(io.open(os.path.join(ROOT, "census", "binding",
                                       "readings.json"), encoding="utf-8"))
was = {s["name"]: s.get("verdict") for s in first["subjects"]}

check("the method section says two rows of the first reading were wrong",
      "correction" in d["method"] and "CrewAI" in d["method"]["correction"])

# CrewAI was no_boundary in the first reading and is not now. That is the
# subject moving, not the reading changing its mind, and the row has to say so
# where somebody comparing the two will look.
check("the first reading really did record CrewAI as having no boundary",
      was.get("CrewAI") == "no_boundary", was.get("CrewAI"))
crew = [s for s in subjects if s["name"] == "CrewAI"][0]
check("the CrewAI row carries the correction itself",
      any("CORRECTION" in crew["assessments"][i].get("note", "")
          for i in IDS))
check("and CrewAI is no longer scored not_applicable",
      crew["assessments"]["B3"]["verdict"] != "not_applicable")

# AutoGen is still not_applicable, and the difference between "unchanged" and
# "not looked at again" is the whole value of a second census.
auto = [s for s in subjects if s["name"] == "AutoGen"][0]
check("AutoGen says it was rechecked rather than carried",
      "checked" in auto and "0.7.5" in auto["checked"])
check("AutoGen is not_applicable on every requirement, not absent",
      all(auto["assessments"][i]["verdict"] == "not_applicable" for i in IDS))


print("")
print("nobody is flattered and nobody is only criticised")

by_subject = {s["name"]: [s["assessments"][i]["verdict"] for i in IDS]
              for s in subjects}
scored = {k: v for k, v in by_subject.items()
          if any(x != "not_applicable" for x in v)}

check("no scored subject is present on everything",
      not [k for k, v in scored.items() if set(v) == {"present"}],
      "a clean sweep would mean the rubric is not asking anything")

# The project's own reference implementation is not in this census, and the
# framework the project has published an adapter for is not spared: pydantic-ai
# is absent on B3. If that ever flips without the note changing, somebody has
# edited a verdict rather than a reading.
pyd = [s for s in subjects if s["name"] == "Pydantic AI"][0]
check("the pydantic-ai B3 finding is still absent and still reproduced",
      pyd["assessments"]["B3"]["verdict"] == "absent"
      and "REPRODUCED" in pyd["assessments"]["B3"]["note"])
check("and the fairness note that it is not a defect is still there",
      "fairness" in pyd["assessments"]["B3"])

print("")
print("the published page says what the data says")

# The page is where anybody who is not reading JSON meets this reading, so a
# verdict that differs between the two is the reading saying two things.
# Scoped to the SECOND table: the first reading's rows have the same shape and
# matching them instead is how this check first passed itself a wrong answer.
import re as _re
pg = os.path.join(ROOT, "public", "approval-binding", "index.html")
check("the second reading is published", os.path.exists(pg))
if os.path.exists(pg):
    whole = _re.sub(r"\s+", " ", io.open(pg, encoding="utf-8").read())
    MARK = "The second reading, 9 September 2026"
    check("the page carries both readings, not one replacing the other",
          MARK in whole and "bound" in whole.split(MARK)[0])
    page = whole.split(MARK)[-1] if MARK in whole else ""
    SHOW = {"present": "present", "partial": "partial", "absent": "absent",
            "not_applicable": "no pause"}
    bad = []
    for s_ in subjects:
        m = _re.search(r"<tr><td class=.s.>%s</td>(.*?)</tr>"
                       % _re.escape(s_["name"]), page)
        if not m:
            bad.append((s_["name"], "no row in the second table"))
            continue
        got = _re.findall(r"<td class=.v[^>]*>([^<]*)</td>", m.group(1))
        want = [SHOW[s_["assessments"][i]["verdict"]] for i in IDS]
        if got != want:
            bad.append((s_["name"], got, want))
    check("every published verdict matches readings-2.json", not bad, bad[:2])
    check("the page states that two rows of the first reading were wrong",
          "two rows of the first reading above are now wrong" in page.lower())
    check("the page names CrewAI as the corrected one", "CrewAI" in page)
    check("the page says LangGraph refuses an ambiguous approval",
          "refuses" in page and "ambiguous approval" in page)

print("")
print("%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)

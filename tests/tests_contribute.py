"""Contributing: counts out, and nothing else. Run: python3 tests_contribute.py

A record already holds what a commons needs, so contributing is arithmetic
rather than an adoption decision. What has to be true of that arithmetic is
narrower than what it computes, and it is all about what must NOT come out.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import contribute as ct                                      # noqa: E402
import testimony_emit as em                                  # noqa: E402

PASS = FAIL = 0
WORDS = frozenset(["accepts", "adopts", "agenda"])


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:200])


def record():
    r = em.Record()
    r.scope(acts=False, description="test")
    e = r.evidence(kind="api", source="crm://x")
    rows = ([("acme-holdings-ltd", [("accepts", True), ("adopts", True)])]
            + [("c%d" % i, [("accepts", True), ("adopts", True)])
               for i in range(4)]
            + [("c%d" % i, [("accepts", True), ("adopts", False)])
               for i in range(4, 6)]
            # A proposition outside the vocabulary, and a subject name that
            # would identify a customer if anything leaked one.
            + [("c9", [("plan_annual_pro", True), ("agenda", True)])])
    for subj, props in rows:
        for p, pol in props:
            r.belief(subject=subj, proposition=p,
                     asserted_by={"id": "a", "kind": "agent"}, evidence=[e],
                     polarity="affirm" if pol else "deny")
    r.seal()
    return r


def main():
    r = record()
    entries = [json.loads(l) for l in r.jsonl().split(chr(10)) if l.strip()]
    doc, dropped = ct.build(entries, {"domain": "customer_support",
                                      "region": "europe",
                                      "subjects": "10-49"},
                            "test-instance-01", WORDS)
    blob = json.dumps(doc)

    print("\nnothing identifying leaves")
    # The one that matters most. A subject is counted and never named, so a
    # customer identifier in a record cannot ride out in a contribution.
    for subject in ("acme-holdings-ltd", "c0", "c9"):
        check("the subject %r appears nowhere in the contribution" % subject,
              subject not in blob)
    check("a pattern carries two tokens and four numbers, and nothing else",
          all(set(p) == {"antecedent", "consequent", "support", "refute",
                         "subjects", "consequent_base"}
              for p in doc["patterns"]), doc["patterns"][:1])

    print("\nwords outside the vocabulary are dropped, never mapped")
    check("the unknown proposition is reported as dropped",
          dropped == ["plan_annual_pro"], dropped)
    check("and appears in no pattern", "plan_annual_pro" not in blob)
    check("nothing was substituted for it",
          all(p["antecedent"] in WORDS and p["consequent"] in WORDS
              for p in doc["patterns"]))

    print("\ncounts are counts")
    pat = [p for p in doc["patterns"]
           if p["antecedent"] == "accepts" and p["consequent"] == "adopts"]
    check("the pair is counted", len(pat) == 1, doc["patterns"])
    if pat:
        p = pat[0]
        check("support and refute add up to the subjects that held the first",
              p["support"] == 5 and p["refute"] == 2 and p["subjects"] == 7,
              p)
        check("the base rate is a rate, never a count",
              0.0 <= p["consequent_base"] <= 1.0, p["consequent_base"])

    print("\nand it refuses rather than guessing")
    r2 = subprocess.run([sys.executable,
                         os.path.join(ROOT, "spec", "contribute.py"),
                         "x.jsonl"], capture_output=True, text=True)
    out = r2.stdout + r2.stderr
    check("a missing frame stops it, since inferring one would profile the "
          "contributor", "not inferred" in out, out[:160])
    check("and it names the closed lists rather than leaving them to be "
          "guessed", "customer_support" in out and "europe" in out)

    print("\nit prints and does not send")
    src = io.open(os.path.join(ROOT, "spec", "contribute.py"),
                  encoding="utf-8").read()
    body = src.split('"""', 2)[2]
    for call in ("urlopen(", "POST", "requests."):
        n = body.count(call)
        check("the only network use is fetching the vocabulary: no %r beyond "
              "it" % call, n <= (1 if call == "urlopen(" else 0), n)

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

"""The declared mapping layer: that a declaration is read, and that it binds.

    python tests/tests_formats.py

The thing being defended is narrow and it is the whole point: a finding that
rests on a name match must never be printed the way a finding that rests on a
read mapping is. Everything else here supports that one distinction.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import formats                                               # noqa: E402
import testimony_convert as tc                               # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + ((": %s" % (detail,)) if detail else ""))


# The record EMILIA filed as their own worked example with comment
# 0000000463 to the Colorado Attorney General. Kept verbatim: a mapping read
# against a paraphrase is a mapping read against nothing.
EMILIA = {
    "@record": "human-authorization-record/v1",
    "payload": {
        "typ": "human-authorization-record",
        "reviewer_id": "loan_officer:j.martinez (WebAuthn, user-verified)",
        "decision": {
            "decision_type": "credit.application.adverse_action",
            "subject_ref": "applicant:CO-2026-44817",
            "outcome": "denied",
            "principal_reasons": ["debt_to_income_above_threshold",
                                  "insufficient_credit_history"],
            "admt_system": "LoanScore-v7",
            "policy_version": "co-fair-lending-2026.2",
            "jurisdiction": "US-CO",
        },
        "decision_digest": "sha256:844650f11806dca57ef8ea781985aba632",
        "reviewed_at": "2026-06-24T18:30:00Z",
    },
    "signature": {"alg": "Ed25519", "value": "imellDXzeCoS2IeNN5oIsXh96w"},
}

# One entry off the wire, verbatim from conformance/cases. The first version of
# this fixture was invented and nested, and it passed nothing: the declaration
# had been written against a record shape that does not exist.
TR = {"spec": "testimony-record/0.2", "type": "approval", "id": "a1",
      "at": "2026-09-01T09:00:04Z", "decision": "d1",
      "approver": {"id": "sam@example.com", "kind": "human"},
      "identity_source": "auth-session"}


print("declarations")

check("every declared signal name is a known signal",
      all(s in formats.SIGNALS
          for f in formats.DECLARED.values() for s in f.signals),
      sorted({s for f in formats.DECLARED.values() for s in f.signals}
             - set(formats.SIGNALS)))

# A structural claim that does not say what establishes it is an assertion,
# and this file exists to stop assertions being printed as findings.
bare = [(f.id, s) for f in formats.DECLARED.values()
        for s, v in f.signals.items()
        if isinstance(v, tuple) and (not v[1] or len(v[1]) < 20)]
check("every BY_CONSTRUCTION and ABSENT carries a reason", not bare, bare)

check("every format says where it was read and when",
      all(f.where and f.read_on for f in formats.DECLARED.values()))

check("the project's own format is declared alongside the others",
      "testimony-record" in formats.DECLARED,
      "a party that grades records cannot exempt its own")

# The conflict is disclosed in the declaration rather than in a footnote
# somewhere else, because a reader of the matrix is who needs to see it.
check("the project's own entry discloses the conflict of interest",
      "conflict" in " ".join(
          formats.DECLARED["testimony-record"].notes).lower())


print("")
print("identification")

seen = tc._paths(EMILIA, lists=True)
check("the EMILIA exhibit is identified as an EMILIA receipt",
      formats.identify(seen) == "emilia-authorization-receipt",
      formats.identify(seen))

check("a Testimony Record is identified as one",
      formats.identify(tc._paths(TR, lists=True)) == "testimony-record",
      formats.identify(tc._paths(TR, lists=True)))

check("an unrecognised shape identifies as nothing rather than as something",
      formats.identify({"foo": 1, "bar": 2}) == "",
      "a wrong identification applies a wrong mapping confidently")

check("identification needs EVERY detect path, not any of them",
      formats.identify({"payload.typ": "x"}) == "",
      "one field in common is not a format")


print("")
print("the mapping binds")

emilia = formats.mapping_for("emilia-authorization-receipt")

check("the approver is declared, not guessed",
      emilia.carries("approver") == ("payload.reviewer_id", "field"))

check("identity_source is by construction, not missing",
      emilia.carries("identity_source")[1] == formats.BY_CONSTRUCTION)

# The finding this whole layer was built for. The loose tier of the converter
# matched `payload.decision.subject_ref` to the `source` signal because both
# contain the fragment `ref`, and reported that an EMILIA receipt could
# evidence 6-1-1701(15)(a). It cannot. The declaration says so.
check("evidence_link is DECLARED ABSENT, where the guess said present",
      emilia.carries("evidence_link")[1] == formats.ABSENT)

check("the guess that caused this is still what an undeclared read does",
      tc.match(seen, "source")[0] == "payload.decision.subject_ref",
      "if this stops being true the regression it guards is gone")


print("")
print("lists are visible")

# A record that states two reasons states them as a list. `_paths` dropped
# lists entirely until 9 September 2026, so the receipt above was read as
# carrying no reason for an adverse outcome while holding two.
check("a list-valued field is discoverable",
      "payload.decision.principal_reasons" in seen,
      sorted(k for k in seen if "reason" in k))

check("discovery does not change what emit and suggest see",
      "payload.decision.principal_reasons" not in tc._paths(EMILIA),
      "proposing a list for a string member builds an invalid record")

check("a list of objects is walked into",
      "covers" in tc._paths(
          {"type": "integrity", "covers": ["s1", "e1"],
           "anchor": {"kind": "opentimestamps"}}, lists=True),
      "a list of scalars is a path too")


print("")
print("the matrix")

rows = formats.as_rows()
check("every format contributes a row for every signal",
      len(rows) == len(formats.DECLARED) * len(formats.SIGNALS),
      len(rows))

check("nothing in the matrix is silently blank",
      all(how != "field" or where for _, _, where, how, _ in rows))

print("")
print("%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)

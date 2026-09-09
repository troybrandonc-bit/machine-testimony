"""Build the TR-3 evidence profile, and give it a digest anybody can recompute.

    python3 build_profile.py            # write spec/profiles/tr-3.json
    python3 build_profile.py --check    # fail if the published file is stale

WHY A PROFILE AND NOT A PAGE. Contracts, rules and protocols do not reference
prose. They reference a short name and a number: a FICO score, an MSCI index, a
rating. What makes those referenceable is that the name is stable, the
definition is published, and both parties can check a claim against it before
they start arguing.

`draft-schrock-ep-authorization-evidence-chain` evaluates "an evidence
requirement owned by the relying party" and says normatively that its own
description MUST NOT become that requirement.
`draft-schrock-ep-reliance-agreement` then references the evidence condition BY
DIGEST rather than restating it. Those are sockets for an externally published,
digest-identified requirement. This is a document that fits one.

WHY IT IS GENERATED AND NOT WRITTEN. A profile that says TR-3 requires
something the validator does not check is worse than no profile: it is a claim
about a number, made by the party who owns the number, that nobody can
reproduce. So the requirement list is READ OUT OF THE VALIDATOR by running it
and recording which checks the level actually contains. If a check is added,
removed or renamed, this file changes and `--check` fails.

THE DIGEST IS OVER RFC 8785 CANONICAL BYTES, which is the same canonicalisation
EMILIA uses, so a party referencing this profile by digest and a party checking
it compute the same bytes on every platform. It covers the requirements and the
identity of the profile. It deliberately does NOT cover the prose notes, so
fixing a typo does not invalidate every reference to the profile.

Copyright 2026 Garnet Taurus Ltd. CC BY 4.0.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import testimony_validate as tv                              # noqa: E402

OUT = os.path.join(HERE, "profiles", "tr-3.json")
# A digest-identified document that cannot be fetched is not referenceable, so
# the same bytes are served at the canonical URL. Byte-identical on purpose: a
# party that recomputes the digest from the served copy and a party that
# recomputes it from the repository must get the same answer.
SERVED = os.path.join(os.path.dirname(HERE), "public", "tr-3", "tr-3.json")
EXAMPLE = os.path.join(HERE, "testimony-record-example.jsonl")

PROFILE_ID = "testimony-record/tr-3"
PROFILE_VERSION = "1"

# What the level is FOR, in one sentence, because a requirement list without a
# purpose gets applied to things it was not meant for.
PURPOSE = ("A record at TR-3 can show that an action which carried risk was "
           "gated by a named person who was not the party that proposed it.")

# The residual. Every level of this ladder has one and stating it is the point:
# a profile that lists only what it establishes is being used as an assurance
# claim by the second time somebody cites it.
DOES_NOT_ESTABLISH = (
    "that the decision was correct, reasonable or lawful",
    "that the named approver is a particular real person, which is an "
    "identity-proofing question outside any record format",
    "that the approver saw or understood what they approved, which is a "
    "property of the surface that rendered it and not of the record",
    "that the record is complete, or that a different record was not also "
    "produced and discarded",
    "that the record has not been altered by the party holding it, which is "
    "TR-4 and not this level",
)

# Where a requirement rests on the record's own say-so rather than on something
# checkable from the record, it is `attested` and it is labelled. A profile
# that hides that distinction is selling four verified requirements as eight.
BASIS_MEANS = {
    "verified": "checkable from the record itself by any party holding it",
    "attested": "asserted by the record's producer; a reader takes it on "
                "trust or corroborates it elsewhere",
}


def canonical(obj) -> bytes:
    """RFC 8785 style: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def requirements() -> list:
    """The TR-3 checks, read out of the validator rather than transcribed."""
    text = io.open(EXAMPLE, encoding="utf-8").read()
    res = tv.validate(text).as_dict()
    out = []
    for c in res["checks"]:
        if c["level"] != "TR-3":
            continue
        out.append({"requirement": c["check"], "basis": c["basis"]})
    # A record that declares it does not act takes a different TR-3 path, so
    # the list depends on the example it was read from. Say which one, rather
    # than presenting a conditional list as an absolute one.
    return out


def build() -> dict:
    reqs = requirements()
    core = {
        "profile": PROFILE_ID,
        "version": PROFILE_VERSION,
        "specification": "draft-clifford-testimony-record-02",
        "level": "TR-3",
        "cumulative": ["TR-1", "TR-2", "TR-3"],
        "requirements": reqs,
    }
    digest = hashlib.sha256(canonical(core)).hexdigest()
    doc = dict(core)
    doc["digest"] = "sha256:" + digest
    doc["digest_covers"] = ("profile, version, specification, level, "
                            "cumulative and requirements, canonicalised with "
                            "sorted keys and no whitespace. It does not cover "
                            "the notes below, so correcting prose does not "
                            "invalidate a reference.")
    doc["purpose"] = PURPOSE
    doc["basis_means"] = BASIS_MEANS
    doc["does_not_establish"] = list(DOES_NOT_ESTABLISH)
    doc["read_from"] = ("the reference validator, spec/testimony_validate.py, "
                        "run against spec/testimony-record-example.jsonl. The "
                        "requirement list is generated, not transcribed.")
    doc["how_to_check"] = ("python3 testimony_validate.py RECORD.jsonl "
                           "--require TR-3. The validator is MIT licensed and "
                           "carries no dependency on its author.")
    doc["licence"] = "CC BY 4.0"
    doc["canonical_url"] = "https://machinetestimony.org/tr-3/"
    return doc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    p.add_argument("--check", action="store_true",
                   help="fail if the published profile is stale")
    a = p.parse_args()
    doc = build()
    text = json.dumps(doc, indent=2, ensure_ascii=False) + chr(10)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if a.check:
        if not os.path.exists(OUT):
            sys.stderr.write("profile has never been built" + chr(10))
            return 1
        have = io.open(OUT, encoding="utf-8").read()
        if have != text:
            sys.stderr.write(
                "the published profile does not match the validator. The "
                "level changed and the profile did not." + chr(10))
            return 1
        if not os.path.exists(SERVED):
            sys.stderr.write("the profile is not served at the canonical URL"
                             + chr(10))
            return 1
        if io.open(SERVED, encoding="utf-8").read() != text:
            sys.stderr.write(
                "the served copy differs from the repository copy, so two "
                "parties recomputing the digest disagree." + chr(10))
            return 1
        print("profile is current: " + doc["digest"])
        return 0
    io.open(OUT, "w", encoding="utf-8", newline=chr(10)).write(text)
    os.makedirs(os.path.dirname(SERVED), exist_ok=True)
    io.open(SERVED, "w", encoding="utf-8", newline=chr(10)).write(text)
    print("%s  %d requirements" % (doc["digest"], len(doc["requirements"])))
    print("written to %s" % os.path.relpath(OUT, os.path.dirname(HERE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

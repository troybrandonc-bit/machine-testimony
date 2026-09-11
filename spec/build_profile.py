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
# Every version ever published, kept at its own URL forever. A reference to a
# version that stops resolving is a reference that breaks, and a unit whose
# past meanings evaporate cannot be written into anything with a term longer
# than a news cycle.
VERSIONED = os.path.join(os.path.dirname(HERE), "public", "tr-3", "v%s.json")
# The ledger is the promise made checkable. Saying version 1 is frozen is worth
# what any promise is worth; a file recording its digest, checked on every
# build, is worth something else. If a requirement in a published version is
# ever edited, this fails loudly rather than shipping a number that has
# quietly come to mean something different.
LEDGER = os.path.join(HERE, "profiles", "PUBLISHED.json")
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
    "that the record has not been altered by the party holding it. TR-4 is "
    "the level for integrity, and TR-4 alone does not establish this either: "
    "it means a reader can recompute the arithmetic, and a hash chain "
    "computed by the emitter is recomputable by anyone who can rewrite the "
    "entries. Only TR-4 with an EXTERNAL ANCHOR, whose evidence is held by "
    "somebody other than the emitter, speaks to alteration by the holder",
)

# Where a requirement rests on the record's own say-so rather than on something
# checkable from the record, it is `attested` and it is labelled. A profile
# that hides that distinction is selling four verified requirements as eight.
BASIS_MEANS = {
    "verified": "checkable from the record itself by any party holding it",
    "attested": "asserted by the record's producer; a reader takes it on "
                "trust or corroborates it elsewhere",
}


# The three questions anybody deciding whether to reference this asks, and
# nothing on the page answered them until now: can it change under me, can it
# be withdrawn, and who decides. A unit that cannot answer them is not a unit,
# whatever else is true of it.
STABILITY = {
    "frozen": "The requirements of a published version never change. A change "
              "to what the level requires is a NEW version with a new digest, "
              "and the old version keeps its digest and its meaning.",
    "resolvable": "Every published version stays retrievable at its own URL, "
                  "listed in profiles/PUBLISHED.json. A reference to version 1 "
                  "resolves to version 1 after version 2 exists.",
    "irrevocable": "CC BY 4.0 cannot be revoked by its own terms while its "
                   "conditions are followed. That is the licence's guarantee "
                   "rather than the author's, which is the point: it does not "
                   "depend on the author's continued goodwill or existence.",
    "checkable": "The digest is over the requirements, so a party can prove "
                 "for itself that a version has not moved. The ledger is "
                 "verified on every build, so an edit to a published version "
                 "fails rather than ships.",
    "what_this_is_not": "It is not a promise that the level is right, that it "
                        "will be adopted, or that a later version will be "
                        "compatible with this one. A version supersedes rather "
                        "than amends, and a reader who wants the old meaning "
                        "cites the old version.",
}


def canonical(obj) -> bytes:
    """RFC 8785 style: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def requirements() -> list:
    """The TR-3 checks, read out of the validator rather than transcribed."""
    text = io.open(EXAMPLE, encoding="utf-8").read()
    report = tv.validate(text)
    res = report.as_dict()
    out = []
    for c in res["checks"]:
        if c["level"] != "TR-3":
            continue
        # A requirement of a version the specification has not published is not
        # a requirement of this profile. Version 1's requirements are frozen
        # and a 0.3 check appearing in them would be an edit to a published
        # digest, which this build refuses elsewhere and should not cause here.
        if c["check"] in report.unreleased:
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
    doc["stability"] = STABILITY
    return doc


def ledger() -> dict:
    if os.path.exists(LEDGER):
        return json.load(io.open(LEDGER, encoding="utf-8"))
    return {"profile": PROFILE_ID, "published": []}


def verify_ledger(doc, write=False) -> list:
    """Every version ever published still says what it said. Returns problems.

    This is the whole stability commitment, expressed as arithmetic instead of
    as a sentence. The frozen claim is only worth something if editing a
    published version is harder than not editing it.
    """
    led = ledger()
    problems, seen = [], {e["version"]: e for e in led["published"]}
    here = seen.get(doc["version"])

    if here and here["digest"] != doc["digest"]:
        problems.append(
            "version %s was published as %s and now computes as %s. A "
            "published version's requirements are frozen: this is a NEW "
            "version, not an edit." % (doc["version"], here["digest"],
                                       doc["digest"]))
    elif not here:
        if write:
            led["published"].append({
                "version": doc["version"], "digest": doc["digest"],
                "first_published": _today(),
                "url": "https://machinetestimony.org/tr-3/v%s.json"
                       % doc["version"]})
            io.open(LEDGER, "w", encoding="utf-8", newline=chr(10)).write(
                json.dumps(led, indent=2) + chr(10))
        else:
            problems.append("version %s is not in the ledger" % doc["version"])

    # A version listed and not served is a reference that breaks. The promise
    # is that a citation of version 1 resolves after version 2 exists.
    for e in led["published"]:
        path = VERSIONED % e["version"]
        if not os.path.exists(path):
            problems.append("version %s is published and not served at %s"
                            % (e["version"], os.path.basename(path)))
            continue
        was = json.load(io.open(path, encoding="utf-8"))
        # RECOMPUTE. The first version of this read was["digest"], which is the
        # served file's own claim about itself, so editing a requirement and
        # leaving the digest field alone passed a guard whose entire purpose is
        # to catch that. Trusting an artifact's statement about its own
        # integrity is the exact failure this project reports in other systems,
        # and it took ten minutes to write it here.
        core = {k: was.get(k) for k in ("profile", "version", "specification",
                                        "level", "cumulative", "requirements")}
        actual = "sha256:" + hashlib.sha256(canonical(core)).hexdigest()
        if actual != e["digest"]:
            problems.append(
                "the served copy of version %s computes as %s, the ledger says "
                "%s. Its requirements have been edited." % (e["version"],
                                                            actual, e["digest"]))
        if was.get("digest") != actual:
            problems.append(
                "the served copy of version %s claims %s and computes as %s"
                % (e["version"], was.get("digest"), actual))
    return problems


def _today() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


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
        bad = verify_ledger(doc)
        if bad:
            sys.stderr.write(chr(10).join(bad) + chr(10))
            return 1
        print("profile is current: " + doc["digest"])
        print("versions published and still resolving: %s"
              % ", ".join(e["version"] for e in ledger()["published"]))
        return 0
    io.open(OUT, "w", encoding="utf-8", newline=chr(10)).write(text)
    os.makedirs(os.path.dirname(SERVED), exist_ok=True)
    io.open(SERVED, "w", encoding="utf-8", newline=chr(10)).write(text)
    io.open(VERSIONED % doc["version"], "w", encoding="utf-8",
            newline=chr(10)).write(text)
    bad = verify_ledger(doc, write=True)
    if bad:
        sys.stderr.write(chr(10).join(bad) + chr(10))
        return 1
    print("%s  %d requirements" % (doc["digest"], len(doc["requirements"])))
    print("written to %s" % os.path.relpath(OUT, os.path.dirname(HERE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

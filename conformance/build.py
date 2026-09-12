#!/usr/bin/env python3
"""Write the conformance corpus and the verdicts it expects.

    python3 conformance/build.py

The cases are committed, so a third party gets files rather than a generator.
This exists so they are reproducible and so the expected verdicts cannot drift
away from the reference validator without a test noticing.

Every case is one record and one expected answer. The answer is what the
reference validator says, which is what "conformance" means here: an
implementation conforms when it reaches the same verdict, not when it prints
the same sentences. See conformance/README.md for why that line is drawn where
it is.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_validate as tv        # noqa: E402

S = tv.SPEC
AGENT = {"id": "agent", "kind": "agent"}
HUMAN = {"id": "sam@example.com", "kind": "human"}
T = "2026-09-01T09:00:0%dZ"


def e(**kw):
    """An entry, with the four members every entry carries put first."""
    out = {"spec": kw.pop("spec", S), "type": kw.pop("type"),
           "id": kw.pop("id"), "at": kw.pop("at")}
    out.update(kw)
    return out


def scope(acts=True, **kw):
    return e(type="scope", id="s1", at=T % 0, acts=acts, **kw)


def ev(i=1, **kw):
    return e(type="evidence", id="e%d" % i, at=T % 1, kind="api",
             source="crm://%d" % i, **kw)


def bel(i=1, **kw):
    kw.setdefault("subject", "customer:a")
    kw.setdefault("proposition", "owed_refund")
    kw.setdefault("polarity", "affirm")
    kw.setdefault("state", "believed_true")
    kw.setdefault("asserted_by", AGENT)
    kw.setdefault("evidence", ["e1"])
    return e(type="belief", id="b%d" % i, at=T % 2, **kw)


def dec(i=1, **kw):
    kw.setdefault("action_type", "issue_refund")
    kw.setdefault("risk_class", "high")
    kw.setdefault("risk_source", "registry")
    kw.setdefault("proposed_by", AGENT)
    kw.setdefault("verdict", "permitted")
    kw.setdefault("executed", True)
    kw.setdefault("approval", "a1")
    return e(type="decision", id="d%d" % i, at=T % 3, **kw)


def app(i=1, **kw):
    kw.setdefault("decision", "d1")
    kw.setdefault("approver", HUMAN)
    kw.setdefault("identity_source", "auth-session")
    return e(type="approval", id="a%d" % i, at=T % 4, **kw)


def integrity(entries, scheme="hash-chain", **kw):
    """An integrity entry whose digest is the digest of what it covers."""
    body = [x for x in entries if x["type"] != "integrity"]
    out = e(type="integrity", id="i1", at=T % 5, scheme=scheme,
            digest="sha256:" + tv.digest_of(body),
            covers=[x["id"] for x in body])
    out.update(kw)
    return out


def gated():
    return [scope(), ev(), bel(), dec(), app()]


def cases():
    """Every case, as (name, note, record text)."""
    out = []

    def add(name, note, entries_or_text):
        text = (entries_or_text if isinstance(entries_or_text, str)
                else "\n".join(json.dumps(x) for x in entries_or_text) + "\n")
        out.append((name, note, text))

    # ── TR-1: it is a record at all ─────────────────────────────────────────
    add("empty", "nothing at all reaches no level", "")
    add("not-json", "a line that is not JSON", "{oh dear\n")
    add("not-an-object", "a line that is JSON and not an object", "[1,2,3]\n")
    add("unknown-spec", "a specification version nobody defines",
        [e(spec="testimony-record/9.9", type="scope", id="s1", at=T % 0, acts=False)])
    add("two-specs", "one record, two specification versions",
        [scope(acts=False), e(spec="testimony-record/0.1", type="evidence",
                              id="e1", at=T % 1, kind="api", source="x://1")])
    add("unknown-type", "an entry type nobody defines",
        [scope(acts=False), e(type="rumour", id="r1", at=T % 1)])
    add("missing-required", "a belief with no proposition",
        [scope(), ev(), e(type="belief", id="b1", at=T % 2, subject="c",
                          polarity="affirm", state="believed_true",
                          asserted_by=AGENT, evidence=["e1"])])
    add("bad-enum", "a belief state nobody defines",
        [scope(), ev(), bel(state="probably")])
    add("duplicate-id", "an id used twice", [scope(), ev(), ev()])
    add("bad-time", "a write time that is not RFC 3339",
        [scope(), e(type="evidence", id="e1", at="yesterday", kind="api",
                    source="x://1")])
    add("out-of-order", "a record that goes backwards in time",
        [scope(), e(type="evidence", id="e1", at="2026-08-01T00:00:00Z",
                    kind="api", source="x://1")])
    add("minimal", "the smallest record that is well formed",
        [scope(acts=False)])

    # ── TR-2: beliefs resolve, disagreements survive ────────────────────────
    add("no-evidence-member", "a belief that omits the evidence member",
        [scope(), ev(), e(type="belief", id="b1", at=T % 2, subject="c",
                          proposition="p", polarity="affirm",
                          state="believed_true", asserted_by=AGENT)])
    add("empty-evidence", "a belief that says plainly it has no evidence",
        [scope(acts=False), bel(evidence=[])])
    add("dangling-evidence", "a belief citing evidence not in the record",
        [scope(acts=False), ev(), bel(evidence=["e_nope"])])
    add("conflict-one-side", "a conflict with a single side",
        [scope(acts=False), ev(), bel(), e(type="conflict", id="c1", at=T % 3,
                                          subject="customer:a",
                                          proposition="owed_refund",
                                          sides=["b1"])])
    add("contradicted-no-conflict", "a contradicted belief nothing explains",
        [scope(acts=False), ev(), bel(state="contradicted")])
    add("conflict-side-missing", "a conflict naming a belief not in the record",
        [scope(acts=False), ev(), bel(state="contradicted"), bel(2, polarity="deny"),
         e(type="conflict", id="c1", at=T % 3, subject="customer:a",
           proposition="owed_refund", sides=["b1", "b_gone"])])
    add("resolution-keeps-outsider", "a resolution keeping a side not in the conflict",
        [scope(acts=False), ev(), bel(state="contradicted"), bel(2, polarity="deny"),
         e(type="conflict", id="c1", at=T % 3, subject="customer:a",
           proposition="owed_refund", sides=["b1", "b2"],
           resolution={"method": "policy", "by": AGENT, "at": T % 3,
                       "kept": "b_zzz"})])
    add("conflict-resolved", "a contradiction, both sides kept, resolution recorded",
        [scope(acts=False), ev(), bel(state="contradicted"), bel(2, polarity="deny"),
         e(type="conflict", id="c1", at=T % 3, subject="customer:a",
           proposition="owed_refund", sides=["b1", "b2"],
           resolution={"method": "policy", "by": AGENT, "at": T % 3,
                       "kept": "b2"})])

    # ── TR-3: actions are gated, approvals name somebody ────────────────────
    add("acts-without-decisions", "a record that says it acts and shows nothing",
        [scope(), ev(), bel()])
    add("record-only", "a system that declares it does not act",
        [scope(acts=False), ev(), bel()])
    add("risk-from-the-model", "a risk class the proposing model set",
        [scope(), ev(), bel(), dec(risk_source="model"), app()])
    add("risk-source-invented", "a risk source that is not a known one",
        [scope(), ev(), bel(), dec(risk_source="a-post-it-note"), app()])
    add("risk-source-extension", "an unlisted risk source, declared as one",
        [scope(), ev(), bel(), dec(risk_source="x-inhouse-registry"), app()])
    add("refused-but-executed", "a refusal recorded as having run",
        [scope(), ev(), bel(), dec(verdict="refused", executed=True,
                                   reason="over the limit", approval=None)])
    add("refusal-without-reason", "a refusal that does not say why",
        [scope(), ev(), bel(), dec(verdict="refused", executed=False,
                                   approval=None)])
    add("high-risk-unapproved", "a high-risk action executed with no approval",
        [scope(), ev(), bel(), dec(approval=None)])
    add("approver-is-proposer", "an agent approving its own action",
        [scope(), ev(), bel(), dec(), app(approver={"id": "agent", "kind": "human"})])
    add("approver-not-a-person", "an approval by something that is not a person",
        [scope(), ev(), bel(), dec(), app(approver={"id": "svc", "kind": "agent"})])
    add("identity-from-the-model", "an approver the model named",
        [scope(), ev(), bel(), dec(), app(identity_source="model")])
    add("identity-source-invented", "an identity source that is not a known one",
        [scope(), ev(), bel(), dec(), app(identity_source="trust-me")])
    add("identity-source-extension", "an unlisted identity source, declared as one",
        [scope(), ev(), bel(), dec(), app(identity_source="x-corp-sso")])
    # `executed` says what the system observed. `outcome` says what the record
    # claims about the effect, and exists because a dispatched action whose
    # acknowledgement was lost cannot be described by a boolean: `executed:
    # false` reads as "it did not happen", and a caller who retries on that
    # repeats an action that may already have run. Raised by HarperZ9 on
    # langchain-ai/langgraph#7844, 6 September 2026.
    add("outcome-unconfirmed",
        "an action dispatched whose acknowledgement never came back",
        [scope(), ev(), bel(), dec(executed=False, outcome="unconfirmed"),
         app()])
    add("outcome-not-attempted",
        "an action that was permitted and definitely never dispatched",
        [scope(), ev(), bel(), dec(executed=False, outcome="not_attempted"),
         app()])
    # Observed to run, effect not established. A provider returning 200 with
    # settlement pending is both, and the first version of the contradiction
    # check refused this record, which forced the honest answer into
    # `executed: false`. Reported by impartshadow on 6 September 2026 after
    # running the corpus. The case exists so the refusal cannot come back.
    add("outcome-unconfirmed-after-running",
        "an action observed to run whose effect is not established",
        [scope(), ev(), bel(), dec(executed=True, outcome="unconfirmed"),
         app()])
    add("outcome-contradicts-executed",
        "a record saying the action ran and that it was never attempted",
        [scope(), ev(), bel(), dec(executed=True, outcome="not_attempted"),
         app()])
    add("outcome-contradicts-refusal",
        "a refusal recording that the effect was confirmed",
        [scope(), ev(), bel(), dec(verdict="refused", executed=False,
                                   reason="over the limit", approval=None,
                                   outcome="confirmed")])
    add("outcome-invented", "an outcome nobody defines",
        [scope(), ev(), bel(), dec(executed=False, outcome="probably"), app()])
    add("gated", "an action proposed, approved by a named person, and executed",
        gated())

    # ── TR-4: the record can be shown not to have changed ───────────────────
    add("no-integrity", "a gated record that publishes no integrity scheme",
        gated())
    add("digest-of-nothing", "sixty-four zeros where a digest should be",
        gated() + [e(type="integrity", id="i1", at=T % 5, scheme="hash-chain",
                     digest="sha256:" + "0" * 64,
                     covers=[x["id"] for x in gated()])])
    add("no-covers", "a digest that does not say what it is over",
        gated() + [e(type="integrity", id="i1", at=T % 5, scheme="hash-chain",
                     digest="sha256:" + tv.digest_of(gated()))])
    add("covers-a-ghost", "a digest covering an entry not in the record",
        gated() + [e(type="integrity", id="i1", at=T % 5, scheme="hash-chain",
                     digest="sha256:" + tv.digest_of(gated()),
                     covers=[x["id"] for x in gated()] + ["e_gone"])])
    add("replay-unnamed", "a replay scheme naming no engine",
        gated() + [integrity(gated(), scheme="replay")])
    add("replay", "a replay scheme naming its engine and version",
        gated() + [integrity(gated(), scheme="replay", engine="omem_engine",
                             engine_version="1.0.0")])
    add("hash-chain", "a hash chain over exactly what it says it covers",
        gated() + [integrity(gated())])
    add("anchor-hollow", "an external anchor with no authority and no token",
        gated() + [integrity(gated(), scheme="external-anchor")])
    add("anchor-no-token", "an external anchor naming an authority and no token",
        gated() + [integrity(gated(), scheme="external-anchor",
                             anchor={"kind": "rfc3161",
                                     "authority": "http://tsa.example"})])

    # A real, signed token over a different record. The record is well formed,
    # the token is genuine, and it says nothing about these entries.
    anchored = io.open(os.path.join(ROOT, "public", "anchor", "record.jsonl"),
                       encoding="utf-8").read()
    real = [json.loads(x) for x in anchored.splitlines() if x.strip()]
    token = [x for x in real if x["type"] == "integrity"][0]["anchor"]
    add("anchor-over-another-record",
        "a genuine signed token, issued over some other record",
        gated() + [integrity(gated(), scheme="external-anchor",
                             anchor=dict(token, kind="rfc3161"))])
    add("anchor", "a record a third party signed, published at /anchor/",
        anchored)

    # An advisory system: it assesses and records, and somebody else executes.
    # Two things about it were expressible and had no worked example, so an
    # implementer had to infer both from prose. First, that `acts: false` is the
    # honest declaration for a party that judges but does not run anything, and
    # that such a record is not marked down for carrying no decisions. Second,
    # that an anchor kind this validator cannot recompute reaches the same level
    # as one it can, reported as attested rather than refused.
    #
    # Together they are the shape of every independent assurance service: a
    # judgement, the evidence it rested on, and a commitment to a clock nobody
    # in the transaction controls. It reaches TR-4 and nothing about it is
    # forced.
    advisory = [
        scope(acts=False),
        ev(),
        # An Actor, not a name. The first version of this case wrote
        # asserted_by as the bare string "review.v4", which the Conventions
        # section does not allow and the reference validator did not catch.
        bel(proposition="safe_to_execute",
            asserted_by={"id": "review.v4", "kind": "system"}),
    ]
    # An actor has to be an actor. Three members are declared to be one and
    # nothing checked the shape until 8 Sep 2026, so a name where an object
    # belongs passed two levels. A name says something produced the belief and
    # not what kind of thing produced it, which is the distinction the format
    # exists to keep: a claim asserted by a model and one asserted by a person
    # are different claims. Found by a validator built from the prose alone.
    add("actor-is-a-bare-string",
        "a belief whose asserted_by is a name rather than an actor",
        [scope(acts=False), ev(), bel(asserted_by="review.v4")])
    add("actor-has-no-id", "an actor object that names nobody",
        [scope(acts=False), ev(), bel(asserted_by={"kind": "system"})])
    add("actor-kind-invented", "an actor whose kind is not one of the four",
        [scope(acts=False), ev(), bel(asserted_by={"id": "x", "kind": "oracle"})])

    add("advisory-anchored-elsewhere",
        "a system that judges but does not act, anchored by a kind this "
        "validator cannot recompute",
        advisory + [integrity(advisory, scheme="external-anchor",
                              anchor={"kind": "opentimestamps",
                                      "authority": "bitcoin proof-of-work",
                                      "token": "AAAA"})])


    # ── 0.3: observation, and the disposition on an approval ────────────
    #
    # 0.3 is in SPECS and not in RELEASED, so these exercise checks the
    # published specification does not yet promise. They are here anyway
    # because a corpus that omits the only new entry type in a version is one
    # somebody implements from and then fails on the first real record, and
    # because #91 asked whether the absence of fixtures should block release.
    # It should not block it; it should precede it.
    V3 = "testimony-record/0.3"

    def v3(entries):
        for x in entries:
            x["spec"] = V3
        return entries

    def base3():
        return v3([scope(), ev(), ev(2), bel(), dec(), app()])

    def obs(i=1, **kw):
        kw.setdefault("decision", "d1")
        kw.setdefault("claim",
                      "refund:rf_88 reached settled for amount 4200 currency GBP")
        kw.setdefault("basis", "effect-observed")
        kw.setdefault("observer", {"id": "settlement-poller", "kind": "system"})
        kw.setdefault("evidence", ["e2"])
        kw.setdefault("result", "supports")
        return e(type="observation", id="o%d" % i, at=T % 6, spec=V3, **kw)

    add("observation-supports",
        "an effect observed, resolving to the decision it concerns and to the "
        "evidence it rests on",
        base3() + [obs()])
    add("observation-contradicts",
        "an observation that contradicts the claim, which is a record doing "
        "its job rather than a record failing",
        base3() + [obs(result="contradicts")])
    add("observation-inconclusive-response",
        "an interface response that was observed and did not establish the "
        "postcondition",
        base3() + [obs(basis="response-received", result="inconclusive",
                       claim="the refund request was accepted for processing")])
    # An assertion with nothing behind it is a legitimate state and the whole
    # point of the vocabulary is that a record has to say so. A validator that
    # demanded evidence here would push emitters back to silence.
    add("observation-asserted-bare",
        "an assertion with no observation behind it, which the vocabulary "
        "exists to be able to state",
        base3() + [e(type="observation", id="o1", at=T % 6, spec=V3,
                     decision="d1", claim="the refund went out",
                     basis="asserted", result="supports", evidence=[])])
    add("observation-before-its-version",
        "an observation in a record of a version that does not define it",
        [scope(), ev(), ev(2), bel(), dec(), app(),
         e(type="observation", id="o1", at=T % 6, decision="d1",
           claim="the refund went out", basis="asserted", result="supports",
           evidence=[])])
    add("observation-of-nothing",
        "an observation of a decision that is not in the record",
        base3() + [obs(decision="d9")])
    add("observation-looked-at-nothing",
        "a claim to have observed an effect with nothing named as looked at",
        base3() + [obs(evidence=[])])
    add("observation-nobody-looked",
        "a claim to have observed an effect that names no observer",
        base3() + [obs(observer={"kind": "system"})])

    add("approval-modified",
        "a reviewer who changed the arguments and then allowed them",
        v3([scope(), ev(), bel(), dec(), app(disposition="modified",
                                            changed="amount")]))
    add("approval-modified-silent",
        "a modification that does not say what it modified, which is the "
        "boolean problem with a new name on it",
        v3([scope(), ev(), bel(), dec(), app(disposition="modified")]))
    # `overrode` deliberately owes no `changed`: an override reverses an action
    # rather than altering it, and requiring the member here was a real bug
    # caught by a refusal test in the LangGraph adapter.
    add("approval-overrode",
        "a reviewer who refused the action, which reverses rather than alters "
        "and so owes no `changed`",
        v3([scope(), ev(), bel(),
            dec(verdict="refused", executed=False,
                reason="the reviewer would not authorise it"),
            app(disposition="overrode")]))

    # @RemanenetSpy asked on #91 that `basis` sit inside the signed canonical
    # bytes, so that an `asserted` observation cannot be handed to a verifier
    # that was promised proof of an effect. It does, because the preimage is
    # the whole entry serialised with sorted keys, and until these two cases
    # existed NOTHING asserted that: a refactor narrowing `canonical()` would
    # have removed the property and every other test would still have passed.
    #
    # The pair is the test. Both records are identical in every other respect
    # and both are otherwise valid, so the only thing that can move the verdict
    # is whether the digest covers the basis.
    sworn = v3([scope(), ev(), ev(2), bel(), dec(), app(), obs()])
    # The integrity entry has to be 0.3 like the rest of the record, and it
    # has to be written after the observation it covers. Defaulting either way
    # failed the version and ordering checks before the digest was reached,
    # which would have made the pair prove nothing about the preimage.
    seal = lambda: integrity(sworn, spec=V3, at=T % 7)
    add("basis-under-the-digest",
        "an observation whose basis is inside the bytes the digest was taken "
        "over",
        sworn + [seal()])
    swapped = [dict(x) for x in sworn] + [seal()]
    [x for x in swapped if x["type"] == "observation"][0]["basis"] = "asserted"
    add("basis-swapped-under-the-digest",
        "an observation downgraded from effect-observed to asserted after the "
        "digest was taken over it",
        swapped)

    # ── the digest rule itself ──────────────────────────────────────────────
    body = gated()
    body[1]["confidence"] = 0.87
    add("number-in-range", "a covered entry carrying an ordinary number",
        body + [integrity(body)])
    odd = gated()
    odd[1]["confidence"] = 1e-9
    add("number-out-of-range",
        "a number Python and ECMAScript do not write the same way",
        odd + [e(type="integrity", id="i1", at=T % 5, scheme="hash-chain",
                 digest="sha256:" + "1" * 64,
                 covers=[x["id"] for x in odd])])
    return out


def main() -> int:
    # An output directory, so the corpus can be rebuilt somewhere else and
    # compared with what is committed. Rebuilding over the top would leave a
    # failing check having already overwritten the evidence for it.
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=HERE,
                    help="where to write cases/ and expected.json")
    where = ap.parse_args().out
    os.makedirs(where, exist_ok=True)
    out = os.path.join(where, "cases")
    os.makedirs(out, exist_ok=True)
    for stale in os.listdir(out):
        if stale.endswith(".jsonl"):
            os.remove(os.path.join(out, stale))

    expected = {}
    for name, note, text in cases():
        io.open(os.path.join(out, name + ".jsonl"), "w", encoding="utf-8",
                newline="\n").write(text)
        r = tv.validate(text)
        expected[name] = {
            "note": note,
            "spec": r.spec,
            "scope": r.scope,
            "level": r.level,
            "levels_met": {lvl: not r.failures(lvl) for lvl in tv.LEVELS},
        }
    io.open(os.path.join(where, "expected.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(expected, indent=1, sort_keys=True) + "\n")

    reached = {}
    for k, v in expected.items():
        reached[v["level"]] = reached.get(v["level"], 0) + 1
    print("%d cases written to conformance/cases/" % len(expected))
    for lvl in ("TR-4", "TR-3", "TR-2", "TR-1", None):
        if lvl in reached:
            print("  %-5s %d" % (lvl or "none", reached[lvl]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

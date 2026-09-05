#!/usr/bin/env python3
"""Write a Testimony Record from an ordinary program. One file, no dependencies.

    from testimony_emit import Record

    r = Record()
    r.scope(acts=True, description="Support agent. Refunds to 500 EUR.")
    e = r.evidence(kind="api", source="crm://customers/8842")
    b = r.belief(subject="customer:8842", proposition="requested_refund",
                 asserted_by={"id": "agent", "kind": "agent"}, evidence=[e])
    d = r.decision(action_type="issue_refund", risk_class="high",
                   risk_source="registry",
                   proposed_by={"id": "agent", "kind": "agent"},
                   verdict="permitted", executed=True)
    r.approval(decision=d, approver={"id": "sam@example.com", "kind": "human"},
               identity_source="auth-session")
    r.seal()
    print(r.jsonl())

WHY THIS EXISTS.

The adapters are framework-specific, so an ordinary program that wanted to emit
a record had to write the JSON itself, from the specification, getting the
required members and the digest rule right unaided. That is a project. This is
an afternoon.

WHAT IT REFUSES.

At the point of the mistake rather than at validation time. A missing required
member, an enum value the specification does not define, a reused id, a write
time that goes backwards, an approver who is the proposer: each raises where it
was written, with the field named. Finding out later, from a validator, means
finding out after the record is on disk and the run is over.

It cannot check the things no emitter can. Whether the evidence you cite is
what you say it is, whether the risk class really came from a registry, whether
the name in an approval came from the session it claims. Those are attestations
and the specification says so.

ON THE DIGEST RULE BEING WRITTEN OUT AGAIN.

It is restated here, not imported, because this file has to stand alone to be
worth copying. That is not the duplication this project fell over on 5
September 2026: those were three copies of an *unspecified* rule, each invented
where it was needed, and they disagreed. This is an implementation of a rule
the specification defines, checked against the reference over the whole
conformance corpus by tests/tests_emit.py. A specification exists precisely so
that the same rule can be written twice and come out the same.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json

SPEC = "testimony-record/0.2"

REQUIRED = {
    "scope": ("acts",),
    "belief": ("subject", "proposition", "polarity", "state", "asserted_by"),
    "evidence": ("kind", "source"),
    "conflict": ("subject", "proposition", "sides"),
    "decision": ("action_type", "risk_class", "proposed_by", "verdict",
                 "executed"),
    "approval": ("decision", "approver"),
    "integrity": ("scheme", "digest"),
}
ENUMS = {
    ("belief", "polarity"): {"affirm", "deny"},
    ("belief", "state"): {"believed_true", "believed_false", "contradicted",
                          "unknown"},
    ("evidence", "kind"): {"document", "message", "event", "api", "human",
                           "derived"},
    ("decision", "risk_class"): {"low", "medium", "high"},
    ("decision", "verdict"): {"permitted", "refused"},
    ("integrity", "scheme"): {"replay", "hash-chain", "signature",
                              "external-anchor"},
}

# Sources the proposing side of the same system could have written. A value
# outside the standard lists is declared as an extension with an "x-" prefix,
# so a reader sees one rather than something they might mistake for a defined
# value. None of it makes the claim provable; it is an attestation either way.
UNTRUSTED = {"model", "plan", "request", "request-body", "prompt", "agent"}
RISK_SOURCES = {"registry", "policy", "catalogue", "catalog", "configuration",
                "config", "regulation", "operator", "human"}
IDENTITY_SOURCES = {"auth-session", "session", "api-key", "jwt", "oidc",
                    "oauth", "saml", "mtls", "webauthn", "passkey",
                    "signed-token", "directory", "sso", "ldap", "kerberos"}

NUM_MIN, NUM_MAX, SAFE_INT = 1e-4, 1e21, 2 ** 53


class Refused(ValueError):
    """Something the record cannot say, raised where it was written."""


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _number(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        if abs(v) > SAFE_INT:
            raise Refused("%d does not survive a round trip through "
                          "ECMAScript, so no digest over it is portable" % v)
        return v
    f = float(v)
    if f != f or f in (float("inf"), float("-inf")):
        raise Refused("a digest cannot cover %r" % f)
    if f.is_integer() and abs(f) < NUM_MAX:
        return int(f)
    if not (NUM_MIN <= abs(f) < NUM_MAX):
        raise Refused("%r is outside the range where Python and ECMAScript "
                      "write a number the same way" % f)
    return f


def _plain(v):
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items() if not k.startswith("_")}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, (int, float)):
        return _number(v)
    return v


def canonical(entry: dict) -> str:
    """One entry, as the digest rule writes it."""
    return json.dumps(_plain(entry), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def digest_of(entries: list) -> str:
    """SHA-256 over the canonical entries, joined by one line feed."""
    return hashlib.sha256(
        "\n".join(canonical(e) for e in entries).encode("utf-8")).hexdigest()


class Record:
    """Entries in the order they happened, with the mistakes refused early."""

    def __init__(self, spec: str = SPEC):
        self.spec = spec
        self.entries: list[dict] = []
        self._ids: set[str] = set()
        self._n = 0
        self._last = ""

    # ── the entry types ─────────────────────────────────────────────────────

    def scope(self, acts: bool, **kw) -> str:
        if any(e["type"] == "scope" for e in self.entries):
            raise Refused("a record has at most one scope entry")
        if self.entries:
            raise Refused("the scope entry comes first, so a reader knows "
                          "what the record is claiming before reading it")
        return self._add("scope", acts=bool(acts), **kw)

    def evidence(self, kind: str, source: str, **kw) -> str:
        return self._add("evidence", kind=kind, source=source, **kw)

    def belief(self, subject: str, proposition: str, asserted_by: dict,
               evidence: list, polarity: str = "affirm",
               state: str = "believed_true", **kw) -> str:
        """`evidence` is required, and may be empty.

        An empty list is a claim that there is none, which is worth recording.
        Omitting the member is not the same thing, and the specification does
        not allow it, because a reader cannot tell it from an oversight.
        """
        if evidence is None:
            raise Refused("evidence is required, and [] says there is none. "
                          "Omitting it cannot be told from forgetting it")
        for cited in evidence:
            if cited not in self._ids:
                raise Refused("belief cites %r, which is not in the record "
                              "yet. Write the evidence first" % cited)
        return self._add("belief", subject=subject, proposition=proposition,
                         polarity=polarity, state=state,
                         asserted_by=asserted_by, evidence=list(evidence), **kw)

    def conflict(self, subject: str, proposition: str, sides: list,
                 resolution: dict | None = None, **kw) -> str:
        if len(sides) < 2:
            raise Refused("a conflict has at least two sides; one side is a "
                          "belief")
        for s in sides:
            if s not in self._ids:
                raise Refused("conflict names %r, which is not in the record" % s)
        if resolution is not None:
            for f in ("method", "by", "at", "kept"):
                if f not in resolution:
                    raise Refused("a resolution records %r" % f)
            if resolution["kept"] not in sides:
                raise Refused("the side kept, %r, is not one of the sides"
                              % resolution["kept"])
            kw["resolution"] = resolution
        return self._add("conflict", subject=subject, proposition=proposition,
                         sides=list(sides), **kw)

    def decision(self, action_type: str, risk_class: str, proposed_by: dict,
                 verdict: str, executed: bool, risk_source: str = "",
                 reason: str = "", **kw) -> str:
        if verdict == "refused" and executed:
            raise Refused("a refused action cannot also have executed")
        if verdict == "refused" and not reason:
            raise Refused("a refusal records why. What a system declined is "
                          "usually the part somebody asks about later")
        why = _source_problem(risk_source, RISK_SOURCES)
        if why:
            raise Refused("risk_source: " + why)
        if reason:
            kw["reason"] = reason
        return self._add("decision", action_type=action_type,
                         risk_class=risk_class, risk_source=risk_source,
                         proposed_by=proposed_by, verdict=verdict,
                         executed=bool(executed), **kw)

    def approval(self, decision: str, approver: dict, identity_source: str,
                 **kw) -> str:
        """Records the approval and points the decision back at it."""
        d = self._by_id(decision)
        if d is None or d["type"] != "decision":
            raise Refused("approval names %r, which is not a decision in this "
                          "record" % decision)
        if approver.get("kind") != "human":
            raise Refused("an approver is a person; kind was %r"
                          % approver.get("kind"))
        if not str(approver.get("id") or "").strip():
            raise Refused("an approval names who approved")
        if (d.get("proposed_by") or {}).get("id") == approver.get("id"):
            raise Refused("the approver is the proposer, %r. An agent's own "
                          "credential signing off its own action meets every "
                          "other requirement and is worth nothing"
                          % approver.get("id"))
        why = _source_problem(identity_source, IDENTITY_SOURCES)
        if why:
            raise Refused("identity_source: " + why)
        eid = self._add("approval", decision=decision, approver=approver,
                        identity_source=identity_source, **kw)
        d["approval"] = eid
        return eid

    # ── closing the record ──────────────────────────────────────────────────

    def seal(self, scheme: str = "hash-chain", **kw) -> str:
        """The integrity entry, over every entry written so far.

        `covers` is written out because a digest that does not say what it is
        over cannot be recomputed by anybody, which is the only thing that
        makes recording one worth the bytes.
        """
        body = [e for e in self.entries if e["type"] != "integrity"]
        if not body:
            raise Refused("there is nothing to seal")
        return self._add("integrity", scheme=scheme,
                         digest="sha256:" + digest_of(body),
                         covers=[e["id"] for e in body], **kw)

    def jsonl(self) -> str:
        return "".join(json.dumps(e) + "\n" for e in self.entries)

    def write(self, path: str) -> str:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.jsonl())
        return path

    # ── the parts every entry shares ────────────────────────────────────────

    def _by_id(self, eid: str):
        for e in self.entries:
            if e["id"] == eid:
                return e
        return None

    def _add(self, etype: str, **fields) -> str:
        at = fields.pop("at", "") or _now()
        if at < self._last:
            raise Refused("the record is append-only, and %s is before %s"
                          % (at, self._last))
        eid = fields.pop("id", "") or self._mint(etype)
        if eid in self._ids:
            raise Refused("id %r is already in this record. Ids are never "
                          "reused, so a reader can cite one" % eid)

        entry = {"spec": self.spec, "type": etype, "id": eid, "at": at}
        entry.update({k: v for k, v in fields.items() if v != ""})
        for f in REQUIRED[etype]:
            if f not in entry:
                raise Refused("a %s entry requires %r" % (etype, f))
        for (t, f), allowed in ENUMS.items():
            if t == etype and f in entry and entry[f] not in allowed:
                raise Refused("%s.%s is %r; the specification defines %s"
                              % (etype, f, entry[f], ", ".join(sorted(allowed))))
        canonical(entry)          # refuses a number no verifier could reproduce

        self.entries.append(entry)
        self._ids.add(eid)
        self._last = at
        return eid

    def _mint(self, etype: str) -> str:
        self._n += 1
        return "%s_%d" % (etype[:3], self._n)


def _source_problem(value: str, allowed: set) -> str:
    v = str(value or "").strip().lower()
    if not v:
        return "not stated. Say where it came from, or 'x-something' if it is "\
               "not one of the standard sources"
    if v in UNTRUSTED:
        return "%r is the proposing side of the same system" % v
    if v.startswith("x-"):
        return "" if len(v) > 2 else "'x-' names no extension"
    if v not in allowed:
        return "%r is not a known source. Use one of %s, or 'x-%s' to declare "\
               "your own" % (v, ", ".join(sorted(allowed)), v)
    return ""

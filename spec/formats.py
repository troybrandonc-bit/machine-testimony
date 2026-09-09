"""Declared mappings: which field of which record format carries which signal.

    from formats import identify, mapping_for, DECLARED

An assessment tool that guesses is doing reconnaissance. One that guesses and
then reports a verdict is doing damage, and the difference is this file.

WHY IT EXISTS. The converter finds a member in an unknown log by matching
names: whole path, then leaf, then a loose overlap. That is the right behaviour
for a log nobody has ever mapped, and it is how `suggest` and `propose` earn
their keep. It is the wrong behaviour when the answer is going to be printed
next to a statutory clause. On 9 September 2026 the loose tier matched
`payload.decision.subject_ref` to "what a stated conclusion rested on", because
both contain the fragment `ref`. `subject_ref` names the applicant. The report
said a record could evidence an obligation it cannot evidence, and nothing in
the output distinguished that row from the ones it had got right.

So: a format that has been read is DECLARED, and a format that has not is
INFERRED and says so. Nothing here makes the guessing better. It makes the
guessing visible.

WHY IT IS NOT ONLY THIS PROJECT'S FORMAT. A party that grades records cannot
also be the only format it can read, and it cannot only be able to read its
own. The Testimony Record is one entry below among several, mapped the same way
and graded by the same code, and where another format carries something it does
not, that is recorded here rather than left out. This file is published for the
same reason the census rubric is: a neutral reading nobody can check is not one.

BY_CONSTRUCTION, WHICH IS THE PART WORTH ARGUING WITH. Some formats establish a
signal structurally rather than in a field. An EMILIA authorization receipt does
not carry an `identity_source` string; the artifact IS a user-verified WebAuthn
assertion under an enrolled key, so how the identity was resolved is a property
of the signature rather than a value in the record. A path-based search cannot
see that, and a grader that only searched paths would systematically mark
cryptographic formats short and reward any format that writes the word
"password" into a field. That is backwards, so a declaration may say a signal is
carried BY_CONSTRUCTION and must say by what. It is a claim about the format,
made here, in public, where its author can contradict it.

WHAT A DECLARATION IS NOT. It is not a conformance statement, an endorsement, or
a claim that a format is good. It says where a signal lives in a shape. Whether
that shape satisfies an obligation is a separate judgement made against a
separate published reading, and it is deliberately not in this file.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

# A signal the format establishes by its own construction rather than in a
# field. Always carries a reason: an unexplained BY_CONSTRUCTION is an
# assertion, and this file exists to stop those being printed as findings.
BY_CONSTRUCTION = "by construction"

# A signal the format is declared NOT to carry. Distinct from a signal nobody
# has looked for: `absent` is a reading, silence is not, and the census learned
# that distinction the hard way.
ABSENT = "absent"


class Format:
    """One record format, read at a source, mapped signal by signal."""

    __slots__ = ("id", "name", "where", "read_on", "detect", "signals",
                 "notes")

    def __init__(self, id, name, where, read_on, detect, signals, notes=None):
        self.id = id
        self.name = name
        self.where = where          # where the format is specified
        self.read_on = read_on      # when this mapping was read against it
        self.detect = detect        # paths whose presence identifies the shape
        self.signals = signals      # signal -> path | (BY_CONSTRUCTION, why)
        self.notes = notes or {}

    def carries(self, signal):
        """(where it lives, how it is established) or None.

        `how` is one of "field", BY_CONSTRUCTION or ABSENT, so a caller can
        decide for itself whether a structural claim counts for its purpose.
        A grader for a statute that demands a retained record may reasonably
        refuse one; a grader asking what is knowable may not.
        """
        got = self.signals.get(signal)
        if got is None:
            return None
        if isinstance(got, tuple):
            how, why = got
            return (why, how)
        return (got, "field")


# Signal names are the instrument library's, deliberately: two vocabularies for
# the same thing is two to keep in step. They are listed here so a declaration
# that invents one fails a test instead of silently never matching.
SIGNALS = ("write_time", "evidence_link", "verdict", "reason", "risk_source",
           "approver", "identity_source", "integrity", "user_id", "device",
           "ip", "activity", "subject", "decision_ref")


DECLARED = {

    "testimony-record": Format(
        id="testimony-record",
        name="Testimony Record",
        where="draft-clifford-testimony-record-02",
        read_on="2026-09-09",
        # A record is JSON Lines of entries, each stamped with the spec version
        # and its entry type. `spec` alone would be enough; `type` is here so a
        # file that merely mentions the string somewhere is not mistaken for
        # one.
        detect=("spec", "type"),
        signals={
            "write_time": "at",
            "evidence_link": "source",
            "verdict": "verdict",
            "reason": "reason",
            "risk_source": "risk_source",
            "approver": "approver.id",
            "identity_source": "identity_source",
            "integrity": "digest",
            "activity": "action_type",
            "subject": "subject",
            "decision_ref": "decision",
            "user_id": (ABSENT,
                        "no member names the session or account that acted, as "
                        "distinct from the approver who intervened"),
            "device": (ABSENT, "no member carries a device or location"),
            "ip": (ABSENT, "no member carries a network address"),
        },
        notes={
            "modification": "An approval entry records that an action was "
                            "approved. It cannot presently record that the "
                            "approver MODIFIED it first, which is "
                            "machine-testimony#88 and is open.",
            "conflict of interest": "This is the format maintained by the "
                                    "party publishing this file. It is graded "
                                    "by the same code as every other entry, "
                                    "and it is worse than EMILIA on identity "
                                    "and integrity, which is stated here "
                                    "rather than left to be found.",
        },
    ),

    "emilia-authorization-receipt": Format(
        id="emilia-authorization-receipt",
        name="EMILIA Protocol authorization receipt",
        where="draft-schrock-ep-authorization-receipts-12",
        read_on="2026-09-09",
        detect=("payload.typ", "@record", "payload.decision_digest"),
        signals={
            "write_time": "payload.reviewed_at",
            "approver": "payload.reviewer_id",
            "verdict": "payload.decision.outcome",
            "reason": "payload.decision.principal_reasons",
            "activity": "payload.decision.decision_type",
            "subject": "payload.decision.subject_ref",
            "decision_ref": "payload.decision_digest",
            "identity_source": (
                BY_CONSTRUCTION,
                "the receipt is a user-verified WebAuthn assertion under an "
                "enrolled approver key, so how the identity was resolved is a "
                "property of the signature rather than a field. The mapping "
                "from an enrolled key to a natural person is asserted by a "
                "directory authority, which the draft states plainly and which "
                "an assessor should treat as attested rather than verified."),
            "integrity": (
                BY_CONSTRUCTION,
                "a signature over RFC 8785 canonical bytes committing to the "
                "action hash. `payload.decision_digest` is also present as a "
                "field, so this one is checkable either way."),
            "evidence_link": (
                ABSENT,
                "the receipt commits to the action, not to what the reviewer "
                "was shown of it. The author says so themselves and wrote a "
                "separate draft about it, "
                "draft-schrock-ep-presentation-binding-00."),
            "risk_source": (ABSENT, "no risk classification in the receipt"),
            "user_id": (ABSENT, "the approver is named; the session is not"),
            "device": (ABSENT, "not in the receipt body"),
            "ip": (ABSENT, "not in the receipt body"),
        },
        notes={
            "read from": "The worked example filed as colorado-admt-exhibit-A"
                         ".pdf with comment 0000000463 to the Colorado "
                         "Attorney General, and the draft it cites.",
            "modification": "No approve/modify/override vocabulary either. It "
                            "may not need one: a receipt binds one canonical "
                            "action hash before execution, so a modified "
                            "action is a different action with a different "
                            "receipt. Whether that satisfies a rule asking "
                            "what the reviewer DID is a judgement, not a "
                            "mapping, and is not made here.",
            "scope": "This maps the human-authorization record only. The wider "
                     "EP stack (AEC, AEB, outcome binding, quorum) carries "
                     "signals this entry does not claim, and has not been read "
                     "against them.",
        },
    ),

    "otel-gen-ai-span": Format(
        id="otel-gen-ai-span",
        name="OpenTelemetry GenAI span",
        where="open-telemetry/semantic-conventions-genai, model/gen-ai/registry.yaml",
        read_on="2026-09-09",
        detect=("resourceSpans",),
        signals={
            "write_time": "startTimeUnixNano",
            "activity": "gen_ai.tool.name",
            "decision_ref": "gen_ai.tool.call.id",
            "approver": (
                ABSENT,
                "the counted reason this format is here. Seventy two "
                "`gen_ai.*` attributes on 9 September 2026, and a search of "
                "all of them for approver, human, authorisation, oversight, "
                "review, principal, consent and actor returns nothing. "
                "`gen_ai.agent.id` is the agent's own identifier and reporting "
                "it as the approver would tell a reader they can say who "
                "approved when what they have is the agent approving itself."),
            "identity_source": (
                ABSENT,
                "no attribute records how any identity was resolved, which "
                "follows from there being no identity of a human to resolve"),
            "verdict": (
                ABSENT,
                "nothing distinguishes an action that was permitted from one "
                "that was refused. `gen_ai.tool.call.result` carries what came "
                "back, which is not the same fact"),
            "reason": (ABSENT, "no attribute carries why anything was refused"),
            "risk_source": (
                ABSENT, "no risk classification, so nothing to source"),
            "integrity": (
                ABSENT,
                "a span export is not tamper-evident and is not trying to be. "
                "Spans pass through a collector that can drop, sample and "
                "rewrite them by design, so a span that arrives is not "
                "evidence that a span was emitted"),
            "evidence_link": (
                ABSENT,
                "nothing records what was put in front of a person, because "
                "no person appears"),
            "subject": (
                ABSENT,
                "no attribute names who or what a decision was about"),
            "user_id": (
                ABSENT,
                "`gen_ai.conversation.id` identifies a conversation, not the "
                "account or session that acted, and using it as one would be "
                "the same error as reading `gen_ai.agent.id` as an approver"),
            "device": (ABSENT, "not in the GenAI conventions"),
            "ip": (ABSENT, "not in the GenAI conventions"),
        },
        notes={
            "why it is in this table": "Because it is the format most "
                                       "deployers already emit. The other "
                                       "three ask somebody to adopt "
                                       "something; this one is the pipe an "
                                       "enterprise already has, which makes "
                                       "what it cannot carry the most "
                                       "consequential absence here.",
            "not a criticism": "OpenTelemetry is a telemetry carrier and does "
                               "not claim to be an oversight record. The "
                               "finding is that a deployer whose logs are "
                               "spans has no attribute to put an approver in, "
                               "so the gap is in what they can produce rather "
                               "than in anybody's implementation.",
            "count": "Seventy two, re-counted 9 September 2026 from "
                     "registry.yaml. It was sixty one the day before against "
                     "the old location in open-telemetry/semantic-conventions, "
                     "so re-count rather than cite this.",
        },
    ),

    "scitt-receipt": Format(
        id="scitt-receipt",
        name="SCITT transparent statement receipt",
        where="RFC 9943",
        read_on="2026-09-09",
        detect=("receipt", "signed_statement"),
        signals={
            "integrity": (
                BY_CONSTRUCTION,
                "an inclusion proof against an append-only log, which is "
                "stronger than a digest in a field: it shows the entry was "
                "registered, not only that bytes hash to a value."),
            "write_time": "iat",
            "subject": "sub",
            "approver": (
                ABSENT,
                "the issuer of a statement is not the person who approved an "
                "action. A receipt establishes that a statement was "
                "registered, and says nothing about a human."),
            "verdict": (ABSENT, "not part of the receipt"),
            "reason": (ABSENT, "not part of the receipt"),
            "evidence_link": (ABSENT, "not part of the receipt"),
            "identity_source": (ABSENT, "not part of the receipt"),
            "risk_source": (ABSENT, "not part of the receipt"),
            "activity": (ABSENT, "not part of the receipt"),
            "user_id": (ABSENT, "not part of the receipt"),
            "device": (ABSENT, "not part of the receipt"),
            "ip": (ABSENT, "not part of the receipt"),
            "decision_ref": (ABSENT, "not part of the receipt"),
        },
        notes={
            "what it is for": "A transparency receipt is a carrier and an "
                              "anchor, not an oversight record. Listing it "
                              "here mostly ABSENT is not a criticism: it is "
                              "not trying to answer these questions, and a "
                              "reader should take the integrity row and "
                              "ignore the rest.",
        },
    ),
}


def identify(paths) -> str:
    """Which declared format these paths look like, or "" for none.

    Takes the flattened paths of a record, the same dict `_seen` builds. A
    format matches when every one of its `detect` paths is present as a whole
    path or as a leaf, which is stricter than the converter's name matching on
    purpose: a wrong identification would apply a wrong mapping confidently,
    which is worse than falling back to an honest guess.
    """
    have = set(paths)
    leaves = {p.split(".")[-1] for p in paths}
    best = ""
    for fmt in DECLARED.values():
        hits = [d for d in fmt.detect
                if d in have or d.split(".")[-1] in leaves]
        if len(hits) == len(fmt.detect):
            # A longer detect tuple is a more specific claim, so it wins.
            if not best or len(fmt.detect) > len(DECLARED[best].detect):
                best = fmt.id
    return best


def mapping_for(format_id: str):
    """The declared Format, or None if nothing has been read for that id."""
    return DECLARED.get(format_id)


def as_rows() -> list:
    """Every declaration flattened to (format, signal, where, how, why).

    The matrix, as data. A publishable version of this is the point of the
    whole file: a deployer reads down their own format's column and learns
    what they can and cannot produce before somebody asks them.

    THIS is how formats are compared, and running an instrument over one file
    of each is not. A Testimony Record of a whole case answers more clauses
    than one authorization receipt does, and that measures what the two files
    were for rather than what the two formats can carry. The first comparison
    is a reading; the second is a scoreline, and a scoreline published by one
    of the formats' authors is an advertisement.
    """
    out = []
    for fmt in DECLARED.values():
        for signal in SIGNALS:
            got = fmt.signals.get(signal)
            if got is None:
                out.append((fmt.id, signal, "", "unread",
                            "not read against this format"))
            elif isinstance(got, tuple):
                how, why = got
                out.append((fmt.id, signal, "", how, why))
            else:
                out.append((fmt.id, signal, got, "field", ""))
    return out


if __name__ == "__main__":
    print(__doc__.split(chr(10))[0])
    print()
    for fmt in DECLARED.values():
        print("%s  (%s, read %s)" % (fmt.name, fmt.where, fmt.read_on))
        for signal in SIGNALS:
            got = fmt.carries(signal)
            if got is None:
                print("    %-16s unread" % signal)
            elif got[1] == "field":
                print("    %-16s %s" % (signal, got[0]))
            else:
                print("    %-16s %s: %s" % (signal, got[1], got[0][:60]))
        print()
    print("%d formats declared, %d signals each."
          % (len(DECLARED), len(SIGNALS)))

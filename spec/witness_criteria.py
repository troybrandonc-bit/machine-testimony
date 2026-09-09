"""What a witness has to do before its cosignature is worth anything.

    from witness_criteria import CRITERIA, VERDICTS

A transparency log's operator can show you any tree head they like. A witness
is a second party that signs the head it saw, so that showing two different
heads to two different people stops being free. That is the entire mechanism,
and it is worth exactly as much as the witness is careful and independent, and
nothing more.

WHY THIS EXISTS AND WHY IT IS NOT A PRODUCT. Three parties arrived at the same
unmet need inside a week, none citing the others.

  EMILIA Protocol's own issue #302, July 2026: the reference cosigner ships,
  "no operators run it", and standing up independent operators "costs money and
  needs partners", named as the lead's gate. A witness layer with no witnesses.

  @GitSerge-crypto on langchain-ai/langgraph#8636, running daily batch
  anchoring in production: "For SOC 2 / ISO 42001 audits, reviewers asked us
  'who signs this?' before they asked anything about hash-chains. A signature
  from a third-party witness carries more audit weight than a longer
  self-maintained chain."

  @babyblueviper1, who built an independent verifier for this project's own
  format rather than trust the one that shipped with it.

None of them is blocked on cryptography. They are blocked on nobody having
written down what an acceptable witness is, so there is no way to tell a useful
one from a decorative one, and therefore no way to ask somebody to become one.

THE PRECEDENT, WHICH IS EXACT. Certificate Transparency works because a browser
publishes a log policy: how many logs, how independent, what disqualifies one.
The infrastructure was built by many parties. The policy was one document. This
is that document for authorization and testimony evidence, and it is published
free for the same reason the specification is: a rule only its author can apply
is not a rule.

WHAT A COSIGNATURE IS NOT. It is not a statement that the entries are true, that
the log is complete, that anything was executed, or that the log operator is
honest. It says one party other than the operator saw this tree head at this
size. Every criterion below exists because some way of appearing to provide that
while not providing it has already been built by somebody.

Copyright 2026 Garnet Taurus Ltd. CC BY 4.0.
"""
from __future__ import annotations

# The same five words the census and the binding rubric use, so a reader who
# knows one knows all three, and `undetermined` blocks a conclusion exactly as
# `absent` does.
VERDICTS = ("present", "partial", "absent", "undetermined", "not_applicable")


class Criterion:
    __slots__ = ("id", "question", "present_means", "partial_means", "why")

    def __init__(self, id, question, present_means, partial_means, why):
        self.id = id
        self.question = question
        self.present_means = present_means
        self.partial_means = partial_means
        self.why = why

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


CRITERIA = [
    Criterion(
        "W1",
        "Is the witness independent of the party whose conduct the log would "
        "be evidence about?",
        "a separate legal entity, on infrastructure it controls, holding keys "
        "the log operator has never held, with any commercial relationship to "
        "the operator disclosed",
        "operationally separate but funded, hosted or staffed by the operator, "
        "and saying so",
        "This is the only criterion that cannot be fixed with better software. "
        "A witness run by the log operator, or paid by them without "
        "disclosure, produces a signature that verifies perfectly and "
        "establishes nothing, because the question a witness answers is "
        "whether a second party would notice. EMILIA's own claims document "
        "gets this right about receipts, saying a receipt is evidence because "
        "it is independent of the operator whose conduct may be under "
        "examination. The witness layer inherits that or discards it."),

    Criterion(
        "W2",
        "Does the witness publish what its signature does and does not "
        "establish?",
        "a published statement, versioned, saying it attests only that this "
        "tree head was observed at this size at this time, and naming what it "
        "does not attest",
        "the limits are discoverable in documentation but not carried with the "
        "cosignature or its published policy",
        "A cosignature is going to be handed to somebody in a dispute by the "
        "party it favours. If the only description of what it means comes from "
        "that party, the witness has lent its name to a claim it never made. "
        "This project holds its own record format to the same rule and states "
        "the residual in the record itself; a witness that will not is asking "
        "for more trust than it gives."),

    Criterion(
        "W3",
        "Does the witness verify that the head it is asked to sign is "
        "consistent with the head it signed before?",
        "a consistency proof is required and checked against the witness's own "
        "stored previous head, and the witness REFUSES rather than signs when "
        "the check fails or is absent",
        "consistency is checked when a proof is offered and the signature is "
        "still issued when one is not",
        "The load-bearing one. A witness that signs whatever it is handed is a "
        "rubber stamp, and a rubber stamp with a key is worse than no witness "
        "because it manufactures the appearance of scrutiny. This is the same "
        "failure as an approval boolean recorded without a person: the artifact "
        "is present, the act it stands for did not happen. Refusal has to be "
        "the default, because a witness that fails open converts an outage into "
        "a silent gap in exactly the period somebody will later ask about."),

    Criterion(
        "W4",
        "Can the cosignatures of different witnesses be compared, so that a "
        "split view is detectable?",
        "cosigned checkpoints are published at a stable location any party can "
        "poll without asking the log operator, so two witnesses' views of the "
        "same log can be set side by side",
        "cosignatures exist and are only obtainable from the log operator or "
        "inside a bundle the assessed party assembles",
        "One witness cannot detect equivocation; it can only be lied to less "
        "cheaply. The property appears when views can be compared, which is "
        "why EMILIA built detect-equivocation and gossip in #302 and why CT "
        "gossip exists at all. A cosignature reachable only through the party "
        "it is evidence against is independence in name."),

    Criterion(
        "W5",
        "Can a third party still verify a cosignature years later, without the "
        "witness's cooperation?",
        "the verifying key is published somewhere that outlives the service, "
        "the algorithms are named, and historical cosignatures verify offline "
        "with standard tools rather than the witness's own client",
        "verification is offline but depends on the witness's own software, or "
        "on a key distributed only through its live endpoint",
        "Retention here runs three to six years, and DORA, HIPAA and SEC 17a-4 "
        "run longer. A witness is a long-lived promise made by a short-lived "
        "service. If the signature stops being checkable when the service "
        "stops, the evidence had a shorter life than the obligation it was "
        "collected for, and nobody finds out until the dispute."),

    Criterion(
        "W6",
        "Has the witness said what happens when it stops?",
        "a published end-of-life commitment: notice period, what happens to "
        "the key, and an undertaking that historical cosignatures stay "
        "verifiable after the service ends",
        "key rotation is documented and the end of the service is not",
        "Every witness stops eventually. A witness that stops without saying so "
        "in advance turns every record anchored to it into an unverifiable one, "
        "and does it retroactively. Stating the terms is cheap and refusing to "
        "state them should be disqualifying, because the parties who most want "
        "to be a witness are the ones least likely to still exist. That "
        "includes this project, which is why the reference witness published "
        "alongside these criteria fails this one on purpose and says so."),
]


def as_dicts() -> list:
    return [c.as_dict() for c in CRITERIA]


if __name__ == "__main__":
    print(__doc__.split(chr(10))[0])
    print()
    for c in CRITERIA:
        print("%s  %s" % (c.id, c.question))
        print("    present: %s" % c.present_means)
        print("    partial: %s" % c.partial_means)
        print()
    print("%d criteria. Verdicts: %s." % (len(CRITERIA), ", ".join(VERDICTS)))

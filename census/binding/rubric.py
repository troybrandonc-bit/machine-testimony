"""What a record has to carry to relate a review to the thing that happened.

    from binding.rubric import REQUIREMENTS, VERDICTS

The first binding reading asked one question of six frameworks: between the
moment a person is shown a tool call and the moment it runs, can the arguments
change? That question is still here, as B2. The rest of this exists because five
parties arrived at a wider version of it within a week, none citing the others,
and one of them was a government drafting a binding rule.

  @Brodin2001, building AgentGuard, on langchain-ai/langgraph#8636: an
  integration allowed a declaration to detach from actual execution inputs while
  the underlying receipt checks behaved correctly.

  @Shivani767, designing a prebuilt ApprovalNode on langchain-ai/langgraph#8026,
  stated the shape in one line: the record needs to make explicit what was
  shown, what was approved or edited, and what actually executed.

  @babyblueviper1 on machine-testimony#88, who supplied the digest argument
  below and whose own verifier sets `execution_binding` to the literal string
  "external", always, because that leg crosses a boundary a proof cannot reach.

  Colorado's proposed Rule 7.7, filed 11 August 2026, which requires a deployer
  to retain a record showing the primary evidence available to the reviewer and
  whether the reviewer approved, modified, or overrode the output.

  And the six frameworks already read, at machinetestimony.org/approval-binding/.

WHAT THIS ASKS, AND WHY IT IS ONE QUESTION AND NOT THREE. An approval is worth
what it was an approval OF. That requires three facts to be relatable: the
material a person saw, the decision they took on it, and the effect that
followed. A framework can record all three and relate none of them, which is
the common case and the reason a boolean approval looks complete.

WHAT THIS IS NOT. It is not a conformance assessment and it is not a Colorado
checklist. Rule 7.7 is why the question is now urgent; it is not why it is real.
The same gap exists for a deployer in the EU, for an assessor, and for anybody
replaying a decision afterwards. A framework scoring `absent` throughout is not
badly built: none of these were designed to answer this, and saying so is the
difference between a measurement and an accusation.

NOTHING HERE IS ABOUT A RECORD FORMAT. Every requirement asks what the framework
itself persists or makes recoverable. A framework that carries the fact in its
own shape passes, and is expected to: the question is whether the information
survives at all, not whether it survives in anybody's schema.

Copyright 2026 Garnet Taurus Ltd. CC BY 4.0.
"""
from __future__ import annotations

# Deliberately the same five words the census uses, so a reader who knows one
# knows the other, and `undetermined` blocks a conclusion exactly as `absent`
# does. A verdict claimed on unread code is not a verdict.
VERDICTS = ("present", "partial", "absent", "undetermined", "not_applicable")

# `not_applicable` is available here in one case only and it is the case the
# first reading called `no_boundary`: a framework with no approval pause of its
# own. The question does not arise until somebody builds one, and marking that
# `absent` would report a failure where there is a design decision.
NO_PAUSE = "the framework has no approval pause of its own"


class Req:
    __slots__ = ("id", "question", "present_means", "partial_means", "why")

    def __init__(self, id, question, present_means, partial_means, why):
        self.id = id
        self.question = question
        self.present_means = present_means
        self.partial_means = partial_means
        self.why = why

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


REQUIREMENTS = [
    Req("B1",
        "Is the material shown to the reviewer persisted anywhere, or only "
        "displayed?",
        "the approval path keeps the material that was displayed, or a digest "
        "of it, so what a reviewer saw can be established afterwards",
        "identifiers of the material are kept, so what was ELIGIBLE to be "
        "shown is recoverable, but not the rendering itself",
        "Identifiers establish eligibility, not attention. Two renderers can "
        "cite the same belief while one shows a summary and the other the full "
        "text: identical records, materially different review. The digest is "
        "what makes `shown` checkable rather than asserted, and the argument "
        "is babyblueviper1's on machine-testimony#88."),

    Req("B2",
        "Between the moment the reviewer is shown a call and the moment it "
        "runs, can the arguments change?",
        "both sides read one object and nothing between them rewrites it",
        "they can differ and the framework supplies a mechanism the "
        "integration must choose to use",
        "This is the original binding question, kept unchanged so the six "
        "readings already published carry over rather than being redone. A "
        "tool that reads from state at execution runs with arguments the "
        "confirming person never saw."),

    Req("B3",
        "Can a reviewer who MODIFIED an action be told apart from one who "
        "approved it as proposed?",
        "the record distinguishes approve, modify and override as different "
        "outcomes",
        "the framework allows the arguments to be changed but records the "
        "result as an approval",
        "Colorado Rule 7.7 requires a record of whether the reviewer "
        "approved, modified, or overrode. A boolean cannot say. This is also "
        "the requirement the Testimony Record itself currently fails, which is "
        "machine-testimony#88 and is stated here rather than left out."),

    Req("B4",
        "Is an approval bound to the specific call it permitted, or to the "
        "tool?",
        "the approval carries the call identity and a different call cannot "
        "satisfy it",
        "the identity exists and has to be recovered out of band, so the "
        "binding is reconstructed by the consumer rather than stated by the "
        "record",
        "An approval that cannot be tied to the call it permitted is an "
        "approval of a tool name, and the arguments are the part a person "
        "reads. Raised as langchain-ai/langgraph#8304, where a consumer must "
        "recover the originating tool_call_id from state."),

    Req("B5",
        "Does the record distinguish an action that was permitted from one "
        "that was observed to run?",
        "permission and execution are separate facts, and the record can say "
        "it does not know whether the effect occurred",
        "execution is inferred from the absence of an error",
        "The third leg, and it may not be closable from inside a record at "
        "all. babyblueviper1's verifier sets `execution_binding` to the "
        "constant \"external\" for exactly this reason: a proof can establish "
        "that a signature is valid and a state was committed, and never that "
        "the action which ran is the action reviewed. A framework that says so "
        "is doing better than one that implies otherwise."),
]


def as_dicts() -> list:
    return [r.as_dict() for r in REQUIREMENTS]


if __name__ == "__main__":
    print(__doc__.split(chr(10))[0])
    print()
    for r in REQUIREMENTS:
        print("%s  %s" % (r.id, r.question))
        print("    present: %s" % r.present_means)
        print("    partial: %s" % r.partial_means)
        print()
    print("%d requirements. Verdicts: %s."
          % (len(REQUIREMENTS), ", ".join(VERDICTS)))

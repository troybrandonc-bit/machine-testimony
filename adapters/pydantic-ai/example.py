#!/usr/bin/env python3
"""A refund desk in Pydantic AI that can say who approved the refund.

    pip install pydantic-ai-slim
    python3 example.py > record.jsonl
    python3 ../../spec/testimony_validate.py record.jsonl

Forty lines of ordinary Pydantic AI, plus a recorder and a `decide` function.
The agent is deliberately dull: it holds a belief about a customer, proposes a
refund, and the framework pauses because the tool is marked
`requires_approval=True`. That is the shape most human-in-the-loop agents
already have, which is the point. Nothing here is specific to any product.

**The model is `TestModel`, so this runs with no API key and no network.** It
calls the tool and stops, which is all the example needs. Nothing about the
record depends on which model proposed the call, and that is worth saying
plainly: the record is about the decision and the person, not the reasoning.

Run it and the record reaches **TR-4**: six entries, a decision naming the
agent that proposed the refund with a risk class the model could not write, and
an approval naming a person whose identity came from the authentication layer.

Delete the approver from `decide` and the adapter refuses rather than writing
an approval with nobody in it. That refusal is the honest state of most such
agents today: the pause is real, the person is real, and the record cannot say
who they were.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pydantic_ai import Agent, DeferredToolRequests
from pydantic_ai.models.test import TestModel

from testimony_pydantic_ai import Recorder


def build():
    # `DeferredToolRequests` has to be one of the output types or the approval
    # pause never surfaces: Pydantic AI raises rather than guessing what you
    # meant. It is the one line that is easy to miss, and the error names the
    # fix, which is more than most frameworks manage.
    agent = Agent(TestModel(), output_type=[str, DeferredToolRequests])

    @agent.tool_plain(requires_approval=True)
    def issue_refund(ticket: int, amount: int) -> str:
        """Refund a customer. Consequential, so it is gated."""
        return "refunded %d on ticket %d" % (amount, ticket)

    return agent


def decide(req):
    """Where your approval queue, ticket or console goes.

    The identity has to come from your authentication layer. The adapter has
    none to find and will not invent one, which is the whole difference between
    this record and the one the same agent produces without it.
    """
    return req.approve(
        approver={"id": "troy@example.com", "kind": "human",
                  "name": "T. Clifford", "role": "owner"},
        identity_source="auth-session")


def anchored(path, want):
    """Say what the record does not carry, and add it when asked.

    A record written above reaches TR-4, which the specification calls
    Verifiable: a reader can recompute the arithmetic. The integrity entry is a
    hash chain this process computed, so anybody able to rewrite the entries can
    recompute it too. That detects a later edit by a third party and says
    nothing about the party holding the file.

    An external anchor is the difference. Its evidence is held by a timestamp
    authority, so the emitter cannot move it. It needs the network, which is why
    it is a flag and not the default: an example that cannot run offline is not
    an example, and a test suite that depends on somebody else's service is not
    a test suite.
    """
    if not want:
        print("TR-4 by arithmetic, with NO external anchor.")
        print("The integrity entry is a hash chain this process computed, so it")
        print("is recomputable by anyone who can rewrite the entries. For an")
        print("anchor whose evidence somebody else holds, rerun with --anchor,")
        print("or: python3 -m testimony_anchor %s" % path)
        return path
    import json
    from testimony_anchor import anchor_entry
    rows = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    entry = anchor_entry(rows)
    with io.open(path, "a", encoding="utf-8", newline=chr(10)) as fh:
        fh.write(json.dumps(entry, sort_keys=False) + chr(10))
    print("anchored: %s, %s" % (entry["anchor"]["kind"],
                                entry["anchor"]["authority"]))
    print("proves:   %s" % entry["anchor"]["proves"])
    print("does not: %s" % entry["anchor"]["does_not_prove"])

    # Say what the record now reaches instead of assuming. Appending an anchor
    # can LOWER the level, and the way it does is worth meeting here rather
    # than in production: the validator refuses an entry whose write time is
    # later than the moment the authority saw the digest. If this machine's
    # clock runs even a second ahead of the authority's, entries written a
    # moment ago are, by the authority's clock, from the future.
    try:
        from testimony_validate import validate
    except Exception:                                         # noqa: BLE001
        return path
    res = validate(io.open(path, encoding="utf-8").read())
    print("level:    %s" % res.level)
    bad = [c for c in res.as_dict()["checks"]
           if c["level"] == "TR-4" and not c["ok"]]
    for c in bad:
        print("  not met: %s" % c["check"])
        if "later than the anchor" in c["check"]:
            print("  This is clock skew, not backdating. Anchoring seconds")
            print("  after writing is not the realistic pattern either: a")
            print("  deployer anchors a record that is finished. The check is")
            print("  doing its job and the authority's clock is the one that")
            print("  counts.")
    return path


def main(path="-", anchor=False) -> int:
    rec = Recorder(
        agent={"id": "support-agent", "kind": "agent"},
        # Risk comes from here, not from the model. An action missing from this
        # table raises rather than defaulting, because a default is a guess and
        # the point of the class is that the model did not choose it.
        risk={"issue_refund": "high", "search_docs": "low"},
        risk_source="registry",
        decide=decide,
        description="refund desk, example")

    ev = rec.cite("api", "billing://orders/8812",
                  digest="sha256:" + "0" * 64)
    rec.believe("customer:acme", "eligible_for_refund", evidence=[ev])

    rec.run_sync(build(), "Refund ticket 41 for 4200.")
    rec.write(path)
    anchored(path, anchor)
    return 0


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if x != "--anchor"]
    raise SystemExit(main(args[0] if args else "-",
                          "--anchor" in sys.argv))

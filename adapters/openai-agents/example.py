#!/usr/bin/env python3
"""A refund desk in the OpenAI Agents SDK that can say who approved the refund.

    pip install openai-agents
    python3 example.py > record.jsonl
    python3 ../../spec/testimony_validate.py record.jsonl

Ordinary Agents SDK usage, plus a recorder and a `decide` function. One tool
marked `needs_approval=True`, `rec.run` around the Runner, and every
interruption the SDK raises leaves a decision and, when a person allows it, an
approval naming them.

**A twenty line stub model stands in for the real one, so this runs with no API
key and no network.** It proposes the refund once and then stops, which is all
the example needs. It is at the bottom, out of the way, because it is
scaffolding rather than the point. Nothing about the record depends on which
model proposed the call.

Run it and the record reaches **TR-4**: a decision naming the agent that
proposed the refund under a risk class the model could not write, and an
approval naming a person whose identity came from the authentication layer.

Worth knowing what this replaces. The SDK already has the gate:
`needs_approval` stops the run, `result.interruptions` lists what is waiting,
and `state.approve(item)` lets it through. What `state.approve(item)` does not
take is a principal. It records that the call was approved, not by whom, and
any code holding the state can call it, including the process that proposed the
action. The pause is real, the person is real, and the SDK has nowhere to put
their name.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import Agent, ModelResponse, Runner, function_tool
from agents.items import ResponseFunctionToolCall
from openai.types.responses import ResponseOutputMessage, ResponseOutputText
from agents.models.interface import Model
from agents.usage import Usage

from testimony_openai_agents import Recorder


@function_tool(needs_approval=True)
def issue_refund(ticket: int, amount: int) -> str:
    """Refund a customer. Consequential, so it is gated."""
    return "refunded %d on ticket %d" % (amount, ticket)


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


async def run(rec):
    agent = Agent(name="support-agent", model=_StubModel(),
                  tools=[issue_refund])
    return await rec.run(Runner, agent, "Refund ticket 41 for 4200.")


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

    asyncio.run(run(rec))
    rec.write(path)
    anchored(path, anchor)
    return 0


# ---- scaffolding, not the example -------------------------------------------
# A model that proposes the refund once and then says nothing further, so the
# file runs without an API key. A real deployment passes a real model and
# changes nothing else.

class _StubModel(Model):
    def __init__(self):
        self._proposed = False

    async def get_response(self, system_instructions, input, model_settings,
                           tools, output_schema, handoffs, tracing, **kw):
        if self._proposed:
            out = [ResponseOutputMessage(
                id="msg-1", type="message", role="assistant",
                status="completed",
                content=[ResponseOutputText(type="output_text", text="done",
                                            annotations=[])])]
        else:
            self._proposed = True
            out = [ResponseFunctionToolCall(
                type="function_call", name="issue_refund", call_id="call-1",
                arguments='{"ticket": 41, "amount": 4200}')]
        return ModelResponse(output=out, usage=Usage(), response_id=None)

    def stream_response(self, *a, **kw):
        raise NotImplementedError("the example does not stream")


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if x != "--anchor"]
    raise SystemExit(main(args[0] if args else "-",
                          "--anchor" in sys.argv))

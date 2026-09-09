#!/usr/bin/env python3
"""A refund desk in AutoGen that can say who approved the refund.

    pip install autogen-core autogen-agentchat
    python3 example.py > record.jsonl
    python3 ../../spec/testimony_validate.py record.jsonl

Forty lines of ordinary AutoGen, plus a recorder and a `decide` function. A
`StaticWorkbench` holds one consequential tool, `rec.gate` wraps it, and every
`call_tool` that passes through leaves a decision and, when a person allows it,
an approval naming them.

**It calls the workbench directly rather than through an agent, so it runs with
no model client, no API key and no network.** In a real deployment the agent
makes that call and nothing else changes: the workbench is the seam every tool
call in AutoGen already passes through, which is why the adapter wraps it there
rather than patching an agent.

Run it and the record reaches **TR-4**: a decision naming the agent that
proposed the refund under a risk class the model could not write, and an
approval naming a person whose identity came from the authentication layer.

Worth knowing what this replaces. AutoGen's own `ApprovalResponse` is
`approved: bool` and `reason: str`, and there is no field on it for who
approved. That is not a criticism of the design, which does more than most.
It is the reason this file exists: the pause is real, the person is real, and
the framework has nowhere to put their name.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from autogen_core import CancellationToken
from autogen_core.tools import FunctionTool, StaticWorkbench

from testimony_autogen import Recorder


def issue_refund(ticket: int, amount: int) -> str:
    """Refund a customer. Consequential, so it is gated."""
    return "refunded %d on ticket %d" % (amount, ticket)


def decide(req):
    """Where your approval queue, ticket or console goes.

    The identity has to come from your authentication layer. The adapter has
    none to find and will not invent one, which is the whole difference between
    this record and the one the same workbench produces without it.
    """
    return req.approve(
        approver={"id": "troy@example.com", "kind": "human",
                  "name": "T. Clifford", "role": "owner"},
        identity_source="auth-session")


async def run(rec) -> None:
    tools = [FunctionTool(issue_refund, description="Refund a customer.")]
    gated = rec.gate(StaticWorkbench(tools))
    await gated.call_tool("issue_refund",
                          {"ticket": 41, "amount": 4200},
                          CancellationToken(),
                          "call-1")


def main(path="-") -> int:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "-"))

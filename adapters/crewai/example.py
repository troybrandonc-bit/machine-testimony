#!/usr/bin/env python3
"""A refund desk in CrewAI that can say who approved the refund.

    pip install crewai
    python3 example.py > record.jsonl
    python3 ../../spec/testimony_validate.py record.jsonl

Forty lines of ordinary CrewAI, plus a recorder and a `decide` function. One
consequential tool, `rec.gate_all` around the agent's tools, and every call
through them leaves a decision and, when a person allows it, an approval naming
them.

**It runs the gated tool directly rather than through `crew.kickoff()`, so it
needs no LLM, no API key and no network.** In a real crew the agent makes that
call and nothing else changes: the wrapper is a `BaseTool` like any other, so
the crew, the agent and the task configuration are untouched.

Run it and the record reaches **TR-4**: a decision naming the agent that
proposed the refund under a risk class the model could not write, and an
approval naming a person whose identity came from the authentication layer.

Worth knowing what this replaces. CrewAI's `request_human_input` returns the
text a person typed, and nothing on that path identifies who typed it. That is
not a criticism of the design. It is the reason this file exists: the pause is
real, the person is real, and the return value has nowhere to put their name.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crewai.tools import BaseTool

from testimony_crewai import Recorder


class IssueRefund(BaseTool):
    name: str = "issue_refund"
    description: str = "Refund a customer. Consequential, so it is gated."

    def _run(self, ticket: int, amount: int) -> str:
        return "refunded %d on ticket %d" % (amount, ticket)


def decide(req):
    """Where your approval queue, ticket or console goes.

    The identity has to come from your authentication layer. The adapter has
    none to find and will not invent one, which is the whole difference between
    this record and the one the same crew produces without it.
    """
    return req.approve(
        approver={"id": "troy@example.com", "kind": "human",
                  "name": "T. Clifford", "role": "owner"},
        identity_source="auth-session")


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

    # In a crew this is `agent.tools = rec.gate_all(agent.tools)`.
    gated = rec.gate_all([IssueRefund()])
    gated[0].run(ticket=41, amount=4200)

    rec.write(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "-"))

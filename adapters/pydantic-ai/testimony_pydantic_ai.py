"""Emit a Testimony Record from a Pydantic AI run.

    pip install testimony-pydantic-ai

    from pydantic_ai import Agent
    from testimony_pydantic_ai import Recorder

    def decide(req):
        # req.action, req.arguments, req.risk_class, req.tool_call_id.
        # Your approval UI, queue or ticket goes here. The identity has to come
        # from your authentication layer; this adapter has none to find.
        if req.action == "close_account":
            return req.refuse("a balance is outstanding")
        return req.approve(approver={"id": "r.okonkwo@example.com", "kind": "human"},
                           identity_source="auth-session")

    rec = Recorder(
        agent={"id": "support-agent", "kind": "agent"},
        risk={"issue_refund": "high", "close_account": "high",
              "search_docs": "low"},
        decide=decide,
    )
    result = rec.run_sync(agent, "Refund order 8842")
    rec.write("record.jsonl")

    testimony-validate record.jsonl          # Conformance: TR-4

The specification: https://datatracker.ietf.org/doc/draft-clifford-testimony-record/

WHY THIS ONE EXISTS, IN ONE LINE OF THEIR OWN TYPE SIGNATURE.

Pydantic AI already has the pause. `DeferredToolRequests` carries the calls
waiting for a person, and `DeferredToolResults` carries the answers. The
answers are typed:

    approvals: dict[str, bool | DeferredToolApprovalResult]

A bare `True` approves. That is not a criticism of the design, which is clean
and does more than most: `ToolApproved` can carry `override_args`, so the
framework already understands that what was approved and what the model
proposed can differ. But a boolean has nowhere to put a person, and an
assessment of eight agent systems published in September found that this is
where almost all of them stop. Of the six that take or gate actions, one could
name the person who approved one. Four could not, because approval is stored as
a boolean and the identity was never written down.

So this adapter never writes a boolean. It requires an approver and a source
for that approver's identity, and it records what was actually approved,
including the overridden arguments when the approver changed them, because the
argument the person saw is the fact somebody will want later. See
pydantic-ai#6968 for why that difference matters.

WHAT IT WILL NOT DO.

  * It will not fail open. If your `decide` returns anything that is not a
    decision this issued, the run raises and no tool executes.
    openai-agents-python#4845 is that mistake in a shipped SDK: a callable
    predicate returned None from an unhandled branch, None read as "no approval
    needed", and the gate opened on the path nobody had considered.
  * It will not classify risk from anything the model produced. Risk comes from
    a table you own, and a tool missing from it raises rather than defaulting.
  * It will not invent an approver, let the acting agent approve its own
    action, or accept an identity source the proposing model could have
    written.
  * It will not answer a deferred external call. Those are results the caller
    has to supply, and inventing one would put a fact in the record that never
    happened.

A refusal becomes a `ToolDenied` carrying your reason, so the model is told why
rather than told nothing, and it is recorded with the same standing as a
permission. A system that records only what it did is a receipt, not an account
of itself.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

from typing import Any

import testimony_emit as _em

Refused = _em.Refused

UNTRUSTED = {"model", "plan", "request", "request-body", "prompt", "agent"}
NEEDS_APPROVAL = ("high",)

# A run that never settles is a bug in somebody's decide(), not something to
# spin on: the framework re-raises the pause until it is answered.
MAX_ROUNDS = 24


class NoDecision(Exception):
    """A gate that did not produce a decision. Never treated as permission."""


class Request:
    """One tool call the framework has paused for, waiting on a person.

    Handed to your `decide` callable. Answer with `approve` or `refuse`;
    anything else, including returning None, raises rather than proceeding.

    `approve` takes an optional `arguments=`, which becomes the framework's
    `override_args`. Use it when the approver agreed to something other than
    what the model proposed: the record then says what the person actually
    allowed rather than what was asked for."""

    __slots__ = ("action", "arguments", "tool_call_id", "risk_class", "_out")

    def __init__(self, action, arguments, tool_call_id, risk_class):
        self.action = action
        self.arguments = arguments
        self.tool_call_id = tool_call_id
        self.risk_class = risk_class
        self._out: dict | None = None

    def approve(self, *, approver: dict, identity_source: str,
                arguments: Any = None) -> "Request":
        if not isinstance(approver, dict) or not approver.get("id"):
            raise Refused("approve() needs an approver with an id. A record "
                          "that cannot say who approved is the failure this "
                          "adapter exists to remove.")
        if approver.get("kind", "human") != "human":
            raise Refused("an approver must be a person; %r is %r"
                          % (approver.get("id"), approver.get("kind")))
        if str(identity_source).lower() in UNTRUSTED:
            raise Refused(
                "identity_source %r names something the proposing model can "
                "write. Where did the name actually come from: a session, a "
                "token, an operator console?" % identity_source)
        self._out = {"verdict": "permitted", "approver": dict(approver),
                     "identity_source": str(identity_source),
                     "arguments": arguments}
        return self

    def refuse(self, reason: str) -> "Request":
        if not str(reason).strip():
            raise Refused("a refusal has to say why. A refusal with no reason "
                          "is indistinguishable from a crash to whoever reads "
                          "the record afterwards.")
        self._out = {"verdict": "refused", "reason": str(reason)}
        return self


class Recorder:
    """Accumulates a Testimony Record across a Pydantic AI run.

    Observes the public surface only: run_sync, the DeferredToolRequests it
    returns, and the DeferredToolResults handed back. Nothing is
    monkeypatched."""

    def __init__(self, *, agent: dict, risk, decide=None,
                 risk_source: str = "registry", acts: bool = True,
                 description: str = ""):
        if not isinstance(agent, dict) or not agent.get("id"):
            raise Refused("agent must be an actor object with an id")
        if str(risk_source).lower() in UNTRUSTED:
            raise Refused(
                "risk_source %r names something the proposing model can write; "
                "a risk class the model chose is not a gate" % risk_source)
        self.agent = dict(agent)
        self.agent.setdefault("kind", "agent")
        self._risk = risk
        self._decide = decide
        self.risk_source = str(risk_source)
        self.rec = _em.Record()
        self.rec.scope(acts=bool(acts), **({"description": description}
                                           if description else {}))

    def risk_for(self, action: str) -> str:
        cls = self._risk(action) if callable(self._risk) else self._risk.get(action)
        if cls not in ("low", "medium", "high"):
            raise Refused(
                "no risk class for tool %r. Add it to the risk table. This "
                "adapter will not default, because a default is a guess and "
                "the whole point of the class is that the model did not "
                "choose it." % action)
        return cls

    def run_sync(self, agent, user_prompt=None, **kw):
        """Run the agent, answering every approval pause and recording it."""
        from pydantic_ai import DeferredToolRequests

        result = agent.run_sync(user_prompt, **kw)
        for _ in range(MAX_ROUNDS):
            pending = result.output
            if not isinstance(pending, DeferredToolRequests):
                return result
            if pending.calls:
                raise NoDecision(
                    "the run paused for %d deferred external call(s): %s. This "
                    "adapter answers approvals, not external execution, and "
                    "inventing a result would put a fact in the record that "
                    "never happened. Supply those yourself."
                    % (len(pending.calls),
                       [c.tool_name for c in pending.calls]))
            answers = self._answer_all(pending)
            result = agent.run_sync(
                message_history=result.all_messages(),
                deferred_tool_results=answers,
                **{k: v for k, v in kw.items() if k != "message_history"})
        raise NoDecision(
            "the run still had approvals pending after %d rounds. Something is "
            "re-proposing a call that was answered, and looping here would "
            "hide it." % MAX_ROUNDS)

    def _answer_all(self, pending):
        from pydantic_ai import DeferredToolResults
        from pydantic_ai.tools import ToolApproved, ToolDenied

        out = DeferredToolResults()
        for call in pending.approvals:
            action = call.tool_name
            risk = self.risk_for(action)
            args = call.args

            if risk in NEEDS_APPROVAL:
                if self._decide is None:
                    raise NoDecision(
                        "%r is %s risk and no decide= was given. Refusing to "
                        "approve it: an action that needed a person and did "
                        "not get one is not the same as one nobody had to "
                        "approve, and the record must not say it was."
                        % (action, risk))
                answer = self._decide(
                    Request(action, args, call.tool_call_id, risk))
                d = getattr(answer, "_out", None) if answer is not None else None
                if not d:
                    raise NoDecision(
                        "decide() returned %r for %r rather than "
                        "req.approve(...) or req.refuse(...). This is not read "
                        "as permission. See openai-agents-python#4845, where "
                        "exactly this returned None and the gate opened."
                        % (answer, action))
            else:
                d = {"verdict": "permitted", "approver": None, "arguments": None}

            if d["verdict"] == "refused":
                self.rec.decision(
                    action_type=action, risk_class=risk,
                    risk_source=self.risk_source, proposed_by=dict(self.agent),
                    verdict="refused", executed=False, reason=d["reason"],
                    arguments=_plain(args), tool_call_id=call.tool_call_id)
                out.approvals[call.tool_call_id] = ToolDenied(message=d["reason"])
                continue

            # What the approver allowed, which is not always what the model
            # proposed. pydantic-ai#6968 is the framework side of the same
            # point: an approver who is shown one thing and executes another
            # has not approved the action that happened.
            allowed = d.get("arguments")
            did = self.rec.decision(
                action_type=action, risk_class=risk,
                risk_source=self.risk_source, proposed_by=dict(self.agent),
                verdict="permitted", executed=True,
                arguments=_plain(allowed if allowed is not None else args),
                proposed_arguments=(_plain(args) if allowed is not None else ""),
                tool_call_id=call.tool_call_id)
            if d.get("approver"):
                aid = self.rec.approval(
                    decision=did, approver=d["approver"],
                    identity_source=d["identity_source"],
                    method="pydantic-ai-deferred-approval")
                for e in self.rec.entries:
                    if e["id"] == did:
                        e["approval"] = aid
            out.approvals[call.tool_call_id] = ToolApproved(
                override_args=allowed) if allowed is not None else ToolApproved()
        return out

    def cite(self, kind: str, source: str, **kw) -> str:
        return self.rec.evidence(kind=kind, source=source, **kw)

    def believe(self, subject: str, proposition: str, *, evidence=None,
                asserted_by: dict | None = None, **kw) -> str:
        return self.rec.belief(subject=subject, proposition=proposition,
                               asserted_by=asserted_by or dict(self.agent),
                               evidence=list(evidence or []), **kw)

    def entries(self) -> list:
        return list(self.rec.entries)

    def jsonl(self) -> str:
        if not any(e["type"] == "integrity" for e in self.rec.entries):
            self.rec.seal()
        return self.rec.jsonl()

    def write(self, path) -> str:
        text = self.jsonl()
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return str(path)


def _plain(args):
    """Arguments as something JSON can hold, or "" to leave the field out.

    pydantic-ai hands tool arguments over as a dict or as the raw JSON string
    the model produced. Neither is guaranteed to be serialisable, and a record
    that fails to write because an argument was exotic is worse than one that
    records the call without them."""
    if args is None:
        return ""
    if isinstance(args, (str, int, float, bool)):
        return args
    if isinstance(args, dict):
        try:
            import json
            json.dumps(args)
            return args
        except (TypeError, ValueError):
            return {k: repr(v) for k, v in args.items()}
    return repr(args)

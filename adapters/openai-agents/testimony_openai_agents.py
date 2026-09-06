"""Emit a Testimony Record from an OpenAI Agents SDK run.

    pip install openai-agents
    # copy this file and testimony_emit.py next to your agent.

    from agents import Agent, Runner, function_tool
    from testimony_openai_agents import Recorder

    def decide(req):
        # req.action, req.arguments, req.risk_class. Your own approval UI,
        # queue or ticket goes here. The identity has to come from your
        # authentication layer, because this adapter has none to find.
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
    result = await rec.run(Runner, agent, "Refund order 8842")
    rec.write("record.jsonl")

    python3 testimony_validate.py record.jsonl          # Conformance: TR-4

The specification: https://datatracker.ietf.org/doc/draft-clifford-testimony-record/

THIS SDK ALREADY HAS THE GATE. IT CANNOT SAY WHO OPENED IT.

Unlike the other adapters in this directory, nothing here is adding an approval
boundary. `needs_approval` on a tool already stops the run, `result.interruptions`
already lists what is waiting, and `state.approve(item)` already lets it
through. That machinery is good and this does not replace it.

What `state.approve(item)` does not take is a principal. It records that the
call was approved, not by whom, and any code holding the state can call it,
including the process that proposed the action. So a run where an engineer read
the arguments and decided is indistinguishable afterwards from a run where a
script approved everything. An assessment of eight agent systems published in
September 2026 recorded exactly that: for this SDK, whether an approval
identifies a person, whether the identity comes from the authentication layer,
and whether the agent is prevented from approving its own action were all
absent, and the reason in each case was that there is nowhere to put the answer.

This does not fix that by inventing an approver. It fixes it by refusing to
write an approval unless the caller supplies an identity from their own
authentication layer, and by making the omission visible rather than silent.

WHAT IT WILL NOT DO.

  * It will not fail open. openai-agents-python#4845 is the neighbouring
    mistake in this very SDK: a callable `needs_approval` predicate returned
    None from an unhandled branch, None read as "no approval needed", and the
    gate opened on the path nobody had thought about. If your `decide` returns
    anything that is not a decision this issued, the run raises and the tool
    does not execute.
  * It will not classify risk from anything the model produced. Risk comes from
    a table you own, and a tool missing from that table raises rather than
    defaulting, because a default risk class is a guess wearing a policy's
    clothes.
  * It will not let the acting agent approve its own action, and it will not
    accept an identity source the proposing model could have written.

A refusal is passed to `state.reject` with your reason as the rejection
message, so the model is told why rather than being told nothing, and the
refusal is recorded with the same standing as a permission. A system that
records only what it did is a receipt, not an account of itself.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
from __future__ import annotations

from typing import Any

import testimony_emit as _em

Refused = _em.Refused

UNTRUSTED = {"model", "plan", "request", "request-body", "prompt", "agent"}
NEEDS_APPROVAL = ("high",)

# A run that never settles is a bug in somebody's decide(), not something to
# spin on. The SDK re-raises the interruption until it is answered, so an
# unanswered one would loop for ever.
MAX_ROUNDS = 24


class NoDecision(Exception):
    """A gate that did not produce a decision. Never treated as permission."""


class Request:
    """One tool call the SDK has stopped for, waiting on a person.

    Handed to your `decide` callable. Answer with `approve` or `refuse`;
    anything else, including returning None, raises rather than proceeding."""

    __slots__ = ("action", "arguments", "risk_class", "interruption", "_out")

    def __init__(self, action, arguments, risk_class, interruption):
        self.action = action
        self.arguments = arguments
        self.risk_class = risk_class
        self.interruption = interruption
        self._out: dict | None = None

    def approve(self, *, approver: dict, identity_source: str) -> "Request":
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
                     "identity_source": str(identity_source)}
        return self

    def refuse(self, reason: str) -> "Request":
        if not str(reason).strip():
            raise Refused("a refusal has to say why. A refusal with no reason "
                          "is indistinguishable from a crash to whoever reads "
                          "the record afterwards.")
        self._out = {"verdict": "refused", "reason": str(reason)}
        return self


class Recorder:
    """Accumulates a Testimony Record across an Agents SDK run.

    Observes the public surface only: Runner.run, result.interruptions,
    result.to_state and state.approve/reject. Nothing is monkeypatched."""

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

    async def run(self, runner, agent, payload, **kw):
        """Run the agent, answering every interruption and recording it.

        `runner` is the SDK's Runner class, passed in rather than imported so
        that this file loads without the SDK and so a caller with their own
        Runner subclass is not fought."""
        result = await runner.run(agent, payload, **kw)
        for _ in range(MAX_ROUNDS):
            pending = list(getattr(result, "interruptions", None) or ())
            if not pending:
                return result
            state = result.to_state()
            for it in pending:
                self._answer(state, it)
            result = await runner.run(agent, state, **kw)
        raise NoDecision(
            "the run still had interruptions after %d rounds. Something is "
            "re-proposing an action that was answered, and looping here would "
            "hide it." % MAX_ROUNDS)

    def _answer(self, state, it) -> None:
        action = getattr(it, "name", None) or getattr(it, "tool_name", None)
        if not action:
            raise Refused(
                "an interruption arrived with no tool name, so it cannot be "
                "classified or recorded. Got %r" % (it,))
        args = getattr(it, "arguments", None)
        risk = self.risk_for(str(action))

        if risk in NEEDS_APPROVAL:
            if self._decide is None:
                raise NoDecision(
                    "%r is %s risk and no decide= was given. Refusing to "
                    "approve it: an action that needed a person and did not "
                    "get one is not the same as one nobody had to approve, and "
                    "the record must not say it was." % (action, risk))
            answer = self._decide(Request(str(action), args, risk, it))
            out = getattr(answer, "_out", None) if answer is not None else None
            if not out:
                raise NoDecision(
                    "decide() returned %r for %r rather than req.approve(...) "
                    "or req.refuse(...). This is not read as permission. See "
                    "openai-agents-python#4845, where exactly this returned "
                    "None and the gate opened." % (answer, action))
        else:
            # The SDK stopped for it, so somebody marked it needs_approval even
            # though the risk table calls it routine. Recorded and let through,
            # because overriding the table here would put the decision back
            # where the model can reach it.
            out = {"verdict": "permitted", "approver": None}

        shown = args if isinstance(args, (dict, str)) else None
        if out["verdict"] == "refused":
            self.rec.decision(
                action_type=str(action), risk_class=risk,
                risk_source=self.risk_source, proposed_by=dict(self.agent),
                verdict="refused", executed=False, reason=out["reason"],
                **({"arguments": shown} if shown is not None else {}))
            try:
                state.reject(it, rejection_message=out["reason"])
            except TypeError:                 # older SDK without the keyword
                state.reject(it)
            return

        did = self.rec.decision(
            action_type=str(action), risk_class=risk,
            risk_source=self.risk_source, proposed_by=dict(self.agent),
            verdict="permitted", executed=True,
            **({"arguments": shown} if shown is not None else {}))
        if out.get("approver"):
            aid = self.rec.approval(decision=did, approver=out["approver"],
                                    identity_source=out["identity_source"],
                                    method="openai-agents-approval")
            for e in self.rec.entries:
                if e["id"] == did:
                    e["approval"] = aid
        state.approve(it)

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

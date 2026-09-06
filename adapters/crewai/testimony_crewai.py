"""Emit a Testimony Record from a CrewAI crew.

    pip install crewai
    # copy this file and testimony_emit.py next to your crew.

    from testimony_crewai import Recorder

    def decide(req):
        # req.action, req.args, req.risk_class. Your own approval UI, queue or
        # ticket goes here. The identity has to come from your authentication
        # layer, because this adapter has no way to find one.
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
    agent.tools = rec.gate_all(agent.tools)
    crew.kickoff()
    rec.write("record.jsonl")

    python3 testimony_validate.py record.jsonl          # Conformance: TR-4

The specification: https://datatracker.ietf.org/doc/draft-clifford-testimony-record/

WHY THIS WRAPS TOOLS RATHER THAN USING A HOOK.

CrewAI has no before-tool hook. `step_callback` fires after a step has already
happened, which is enough to observe a tool call and not enough to gate one.
crewAI#5888, open with 126 comments at the time of writing, says this plainly:
"the only way to enforce this is by wrapping each tool's `_run` method
individually, which doesn't compose".

So this wraps, and composing is the part it does for you. `gate_all` returns
tools with the same names, descriptions and argument schemas, so the model sees
no difference and nothing downstream needs changing. The inner tool's own
`run()` is what executes, not its `_run()`, so validation, usage limits and
failure policy all still apply. Nothing is monkeypatched.

WHAT IT WILL NOT DO, WHICH IS THE POINT.

  * It will not fail open. If your `decide` returns anything that is not a
    decision this made, the call raises. openai-agents-python#4845 is the same
    mistake in a shipped SDK: a callable `needs_approval` predicate returning
    `None` from an unhandled branch was read as "no approval needed", so the
    gate opened on the path nobody had thought about. A gate whose failure mode
    is "allowed" is not a gate.
  * It will not classify risk from anything the model produced. Risk comes from
    a table you own, and a tool missing from that table raises rather than
    defaulting, because a default risk class is a guess wearing a policy's
    clothes.
  * It will not invent an approver. CrewAI models no principal at the tool
    boundary, so there is no identity here to find. The record says who
    approved because you passed one, or it does not reach TR-3 and says so.
  * It will not let the acting agent approve its own action, and it will not
    accept an identity source the proposing model could have written.

A refusal is returned to the agent as text rather than raised, because that is
how CrewAI already reports a tool that declined to run, and because an agent
that can read the refusal can take the other path. The refusal is recorded with
the same standing as a permission: a system that records only what it did is a
receipt, not an account of itself.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

from typing import Any

import testimony_emit as _em

Refused = _em.Refused

# Identity the proposing model could have written is not identity. The
# reference validator refuses these; they are named here so the adapter fails
# where the mistake is made rather than at validation time.
UNTRUSTED = {"model", "plan", "request", "request-body", "prompt", "agent"}

# Above this class, a person has to decide. At or below it the action is
# permitted and recorded without one, which is what a risk class is for.
NEEDS_APPROVAL = ("high",)


class NoDecision(Exception):
    """A gate that did not produce a decision. Never treated as permission."""


class Request:
    """One tool call, waiting on a person.

    Handed to your `decide` callable. Answer it with `approve` or `refuse`;
    anything else, including returning None, raises rather than proceeding."""

    __slots__ = ("action", "args", "kwargs", "risk_class", "_out")

    def __init__(self, action: str, args: tuple, kwargs: dict, risk_class: str):
        self.action = action
        self.args = args
        self.kwargs = dict(kwargs)
        self.risk_class = risk_class
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
    """Accumulates a Testimony Record while a crew runs.

    Holds nothing belonging to the crew. It observes the public tool surface
    only, so a CrewAI upgrade that keeps `BaseTool.run` working keeps this
    working."""

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

    # ── the gate ────────────────────────────────────────────────────────────
    def risk_for(self, action: str) -> str:
        cls = self._risk(action) if callable(self._risk) else self._risk.get(action)
        if cls not in ("low", "medium", "high"):
            raise Refused(
                "no risk class for tool %r. Add it to the risk table. This "
                "adapter will not default, because a default is a guess and "
                "the whole point of the class is that the model did not "
                "choose it." % action)
        return cls

    def gate(self, tool):
        """Wrap one CrewAI tool so its calls pass through the record."""
        from crewai.tools import BaseTool

        if not isinstance(tool, BaseTool):
            raise Refused("gate() takes a crewai BaseTool; got %r"
                          % type(tool).__name__)
        self.risk_for(tool.name)      # fail now, not mid-run
        rec = self

        class _Gated(BaseTool):
            # Declared because pydantic ignores undeclared fields, which would
            # silently drop the tool being wrapped.
            inner: Any = None
            recorder: Any = None

            def _run(self, *args: Any, **kwargs: Any) -> Any:
                return rec._call(self.inner, args, kwargs)

        return _Gated(name=tool.name, description=tool.description,
                      args_schema=tool.args_schema, inner=tool, recorder=rec)

    def gate_all(self, tools):
        return [self.gate(t) for t in tools]

    def _call(self, tool, args: tuple, kwargs: dict):
        action = tool.name
        risk = self.risk_for(action)
        shown = {"args": list(args), **kwargs} if args else dict(kwargs)

        if risk in NEEDS_APPROVAL:
            if self._decide is None:
                raise NoDecision(
                    "%r is %s risk and no decide= was given. Refusing to run "
                    "it: an action that needed a person and did not get one is "
                    "not the same as an action nobody had to approve, and the "
                    "record must not say it was." % (action, risk))
            answer = self._decide(Request(action, args, kwargs, risk))
            out = getattr(answer, "_out", None) if answer is not None else None
            if not out:
                raise NoDecision(
                    "decide() returned %r for %r rather than req.approve(...) "
                    "or req.refuse(...). This is not read as permission. See "
                    "openai-agents-python#4845, where exactly this returned "
                    "None and the gate opened." % (answer, action))
        else:
            out = {"verdict": "permitted", "approver": None}

        if out["verdict"] == "refused":
            self.rec.decision(
                action_type=action, risk_class=risk,
                risk_source=self.risk_source, proposed_by=dict(self.agent),
                verdict="refused", executed=False, reason=out["reason"],
                arguments=shown)
            return ("Refused: %s. This action was not taken, and the refusal "
                    "is on the record." % out["reason"])

        # Recorded before the call, with executed False, so a tool that raises
        # leaves a record saying it was allowed and did not run, which is what
        # happened. Claiming execution before executing is how a receipt starts
        # describing intentions instead of events.
        did = self.rec.decision(
            action_type=action, risk_class=risk, risk_source=self.risk_source,
            proposed_by=dict(self.agent), verdict="permitted", executed=False,
            arguments=shown)
        if out.get("approver"):
            aid = self.rec.approval(decision=did, approver=out["approver"],
                                    identity_source=out["identity_source"],
                                    method="crewai-tool-gate")
            for e in self.rec.entries:
                if e["id"] == did:
                    e["approval"] = aid

        result = tool.run(*args, **kwargs)     # the inner tool's own run()
        for e in self.rec.entries:
            if e["id"] == did:
                e["executed"] = True
        return result

    # ── the rest of the record ──────────────────────────────────────────────
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

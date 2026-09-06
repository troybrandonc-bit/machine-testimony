"""Emit a Testimony Record from an AutoGen workbench.

    pip install autogen-core autogen-agentchat
    # copy this file and testimony_emit.py next to your agent.

    from testimony_autogen import Recorder

    def decide(req):
        # req.action, req.arguments, req.risk_class. Your own approval UI,
        # queue or ticket goes here. The identity has to come from your
        # authentication layer; this adapter has none to find.
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
    workbench = rec.gate(StaticWorkbench(tools))     # hand this to the agent
    ...
    rec.write("record.jsonl")

    python3 testimony_validate.py record.jsonl          # Conformance: TR-4

The specification: https://datatracker.ietf.org/doc/draft-clifford-testimony-record/

WHY THE WORKBENCH IS THE RIGHT BOUNDARY.

`Workbench.call_tool(name, arguments, cancellation_token, call_id)` is the one
place every tool call in AutoGen passes through, and it is an abstract method
on a public class, so a workbench that wraps another workbench is a supported
thing to build rather than a trick. autogen#7405 and the open issue proposing a
"Workbench-level tool-call approval gate" are asking for exactly this seam.

Wrapping a workbench also means the agent, the model client and the team
configuration are untouched. `list_tools` passes straight through, so the model
sees the same schemas, and start/stop/reset/save_state/load_state delegate to
the workbench underneath.

WHAT IT WILL NOT DO, WHICH IS THE POINT.

  * It will not fail open. If your `decide` returns anything that is not a
    decision this made, the call raises. openai-agents-python#4845 is that
    mistake in a shipped SDK: a callable `needs_approval` predicate returning
    `None` from an unhandled branch read as "no approval needed", so the gate
    opened on the path nobody had considered. A gate whose failure mode is
    "allowed" is not a gate.
  * It will not classify risk from anything the model produced. Risk comes from
    a table you own, and a tool missing from it raises rather than defaulting.
  * It will not invent an approver. AutoGen models no principal on this
    boundary, so there is no identity here to find. The record names who
    approved because you passed one, or it does not reach TR-3 and says so.
  * It will not let the acting agent approve its own action, and it will not
    accept an identity source the proposing model could have written.

A refusal comes back as a `ToolResult` with `is_error` set, because that is how
a workbench already reports a call that did not produce a result, and an agent
that can read the refusal can take the other path. The refusal is recorded with
the same standing as a permission: a system that records only what it did is a
receipt, not an account of itself.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
from __future__ import annotations

from typing import Any, Mapping

import testimony_emit as _em

Refused = _em.Refused

UNTRUSTED = {"model", "plan", "request", "request-body", "prompt", "agent"}
NEEDS_APPROVAL = ("high",)


class NoDecision(Exception):
    """A gate that did not produce a decision. Never treated as permission."""


class Request:
    """One tool call, waiting on a person.

    Handed to your `decide` callable. Answer with `approve` or `refuse`;
    anything else, including returning None, raises rather than proceeding."""

    __slots__ = ("action", "arguments", "call_id", "risk_class", "_out")

    def __init__(self, action: str, arguments, call_id, risk_class: str):
        self.action = action
        self.arguments = dict(arguments or {})
        self.call_id = call_id
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
    """Accumulates a Testimony Record while an AutoGen agent runs."""

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

    def gate(self, workbench):
        """Wrap a Workbench so every call_tool passes through the record."""
        from autogen_core.tools import Workbench

        if not isinstance(workbench, Workbench):
            raise Refused("gate() takes an autogen_core Workbench; got %r"
                          % type(workbench).__name__)
        return _GatedWorkbench(workbench, self)

    async def _call(self, inner, name, arguments, cancellation_token, call_id):
        from autogen_core.tools import TextResultContent, ToolResult

        risk = self.risk_for(name)
        if risk in NEEDS_APPROVAL:
            if self._decide is None:
                raise NoDecision(
                    "%r is %s risk and no decide= was given. Refusing to run "
                    "it: an action that needed a person and did not get one is "
                    "not the same as an action nobody had to approve, and the "
                    "record must not say it was." % (name, risk))
            answer = self._decide(Request(name, arguments, call_id, risk))
            out = getattr(answer, "_out", None) if answer is not None else None
            if not out:
                raise NoDecision(
                    "decide() returned %r for %r rather than req.approve(...) "
                    "or req.refuse(...). This is not read as permission. See "
                    "openai-agents-python#4845, where exactly this returned "
                    "None and the gate opened." % (answer, name))
        else:
            out = {"verdict": "permitted", "approver": None}

        shown = dict(arguments or {})
        if out["verdict"] == "refused":
            self.rec.decision(
                action_type=name, risk_class=risk,
                risk_source=self.risk_source, proposed_by=dict(self.agent),
                verdict="refused", executed=False, reason=out["reason"],
                arguments=shown)
            return ToolResult(
                name=name, is_error=True,
                result=[TextResultContent(
                    content="Refused: %s. This action was not taken, and the "
                            "refusal is on the record." % out["reason"])])

        # Recorded before the call with executed False, so a tool that raises
        # leaves a record saying it was allowed and did not run, which is what
        # happened.
        did = self.rec.decision(
            action_type=name, risk_class=risk, risk_source=self.risk_source,
            proposed_by=dict(self.agent), verdict="permitted", executed=False,
            arguments=shown)
        if out.get("approver"):
            aid = self.rec.approval(decision=did, approver=out["approver"],
                                    identity_source=out["identity_source"],
                                    method="autogen-workbench-gate")
            for e in self.rec.entries:
                if e["id"] == did:
                    e["approval"] = aid

        result = await inner.call_tool(name, arguments, cancellation_token,
                                       call_id)
        # An error the tool itself reported is not an execution somebody should
        # read as success, so the record follows the workbench's own verdict.
        if not getattr(result, "is_error", False):
            for e in self.rec.entries:
                if e["id"] == did:
                    e["executed"] = True
        return result

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


def _make_gated():
    """Defined against the installed Workbench so the subclass is real.

    Built lazily because this file must import with autogen absent: the
    validator and the tests that do not touch a workbench should not need it."""
    from autogen_core.tools import ToolResult, Workbench

    class _Gated(Workbench):
        """A workbench that wraps a workbench.

        Everything except call_tool delegates untouched, so the model sees the
        same tools and the agent's state handling is unchanged."""

        def __init__(self, inner: "Workbench", recorder: "Recorder"):
            self._inner = inner
            self._rec = recorder

        async def list_tools(self):
            return await self._inner.list_tools()

        async def call_tool(self, name: str,
                            arguments: Mapping[str, Any] | None = None,
                            cancellation_token=None,
                            call_id: str | None = None) -> "ToolResult":
            return await self._rec._call(self._inner, name, arguments,
                                         cancellation_token, call_id)

        async def start(self) -> None:
            await self._inner.start()

        async def stop(self) -> None:
            await self._inner.stop()

        async def reset(self) -> None:
            await self._inner.reset()

        async def save_state(self):
            return await self._inner.save_state()

        async def load_state(self, state) -> None:
            await self._inner.load_state(state)

        def call_tool_stream(self, *a: Any, **kw: Any):
            # Streaming is not gated, because a gate that lets the first chunk
            # through has not gated anything. Saying so is better than a
            # partial implementation that looks like coverage.
            raise NotImplementedError(
                "call_tool_stream is not gated by this adapter. A decision has "
                "to precede the action, and a stream that has begun has "
                "already acted. Use call_tool for anything that needs an "
                "approval on the record.")

    return _Gated


class _GatedWorkbench:
    """Thin front so `gate()` returns an instance without importing autogen at
    module import time. Delegates to the real subclass built on first use."""

    def __new__(cls, inner, recorder):
        return _make_gated()(inner, recorder)

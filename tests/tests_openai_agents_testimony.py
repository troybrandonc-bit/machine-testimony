"""The OpenAI Agents SDK adapter, against a real Runner.
Run: python3 tests_openai_agents_testimony.py

No network and no API key. Only the model is scripted, against the SDK's public
Model interface; the agent, the Runner, the tools, the interruption, to_state
and approve/reject are all the real ones. A stand-in for the approval boundary
would be a stand-in for the finding, which is the one thing that would make
this file worthless.

(The SDK has agents.testing.ScriptedModel on its main branch and it would be
the obvious thing to use. It is not in 0.22.0, the released version this suite
installs, which was found by trying to run the file rather than by reading.)

This adapter differs from the CrewAI and AutoGen ones. Those add a gate to a
framework that has none. This SDK already has the gate: needs_approval stops
the run, result.interruptions lists what waits, state.approve lets it through.
What state.approve does not take is a principal, so the record cannot say who
opened it, and any code holding the state can call it. The census recorded
R3.5, R3.6 and R3.7 as absent for this SDK for exactly that reason.

So the properties here are about identity, not about gating:

  an approval that names nobody must not be writable at all;
  a refusal must reach the model with the reason, not merely stop the call;
  and decide() must never fail open, which is openai-agents-python#4845 in
  this very SDK: a needs_approval predicate returned None from an unhandled
  branch, None read as no approval needed, and the gate opened.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import asyncio
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))
sys.path.insert(0, os.path.join(ROOT, "adapters", "openai-agents"))

import testimony_validate as tv        # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:300])


try:
    from agents import Agent, Runner, RunConfig, function_tool
    from agents.items import ModelResponse
    from agents.models.interface import Model
    from agents.usage import Usage
    from openai.types.responses import (ResponseFunctionToolCall,
                                        ResponseOutputMessage,
                                        ResponseOutputText)
except ImportError as e:
    print("SKIP: openai-agents is not installed (%s)" % e)
    print("  pip install openai-agents")
    raise SystemExit(0)


class Scripted(Model):
    """A model that says what it was told to say, in order.

    The SDK ships agents.testing.ScriptedModel on its main branch, but not in
    the released package this suite installs, so the same thing is written here
    against the public Model interface. Only the model is scripted: the agent,
    the Runner, the tool, the interruption, to_state and approve/reject are all
    the real ones, because those are what is under test and a stand-in for them
    would be a stand-in for the finding."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = 0

    async def get_response(self, system_instructions, input, model_settings,
                           tools, output_schema, handoffs, tracing, *,
                           previous_response_id=None, conversation_id=None,
                           prompt=None, **kw):
        i = min(self.calls, len(self.steps) - 1)
        self.calls += 1
        return ModelResponse(output=self.steps[i](), usage=Usage(),
                             response_id="scripted-%d" % i)

    def stream_response(self, *a, **kw):
        raise NotImplementedError("this suite does not exercise streaming")


def _tool_call(name, args, call_id):
    return lambda: [ResponseFunctionToolCall(
        type="function_call", name=name, call_id=call_id,
        arguments=json.dumps(args))]


def _say(text):
    return lambda: [ResponseOutputMessage(
        id="m", type="message", role="assistant", status="completed",
        content=[ResponseOutputText(type="output_text", text=text,
                                    annotations=[])])]

import testimony_openai_agents as toa  # noqa: E402

CALLS = []


@function_tool(needs_approval=True)
def issue_refund(customer: str, amount: int) -> str:
    """Refund a customer."""
    CALLS.append(("issue_refund", customer, amount))
    return "refunded %d to %s" % (amount, customer)


@function_tool
def search_docs(query: str) -> str:
    """Search the documentation."""
    CALLS.append(("search_docs", query))
    return "three results"


RISK = {"issue_refund": "high", "search_docs": "low"}
HUMAN = {"id": "r.okonkwo@example.com", "kind": "human"}


def scripted():
    """Ask for a refund, then report what happened."""
    return Scripted([
        _tool_call("issue_refund", {"customer": "8842", "amount": 4200}, "call_1"),
        _say("Done."),
    ])


def agent_and_config():
    model = scripted()
    a = Agent(name="support-agent", instructions="Help.",
              tools=[issue_refund, search_docs], model=model)
    return a, RunConfig(model=model)


def recorder(decide=None):
    return toa.Recorder(agent={"id": "support-agent", "kind": "agent"},
                        risk=RISK, decide=decide)


async def main():
    print("a permitted high-risk call runs, and the record says who allowed it")
    CALLS.clear()
    rec = recorder(lambda q: q.approve(approver=HUMAN,
                                       identity_source="auth-session"))
    a, cfg = agent_and_config()
    result = await rec.run(Runner, a, "Refund order 8842", run_config=cfg)
    check("the run finished with nothing left waiting",
          not getattr(result, "interruptions", None),
          getattr(result, "interruptions", None))
    check("the tool actually ran", CALLS == [("issue_refund", "8842", 4200)], CALLS)
    es = rec.entries()
    d = [e for e in es if e["type"] == "decision"][-1]
    ap = [e for e in es if e["type"] == "approval"][-1]
    check("the decision is on the record as executed",
          d["verdict"] == "permitted" and d["executed"] is True, d)
    check("the approval names a person", ap["approver"]["id"] == HUMAN["id"], ap)
    check("and says where the identity came from",
          ap["identity_source"] == "auth-session", ap)
    check("and the decision points back at it", d.get("approval") == ap["id"], d)
    check("the risk class came from the table, not the model",
          d["risk_source"] == "registry" and d["risk_class"] == "high", d)

    print("\na refusal does not execute, and the model is told why")
    CALLS.clear()
    rec2 = recorder(lambda q: q.refuse("a balance is outstanding"))
    a2, cfg2 = agent_and_config()
    await rec2.run(Runner, a2, "Refund order 8842", run_config=cfg2)
    check("THE TOOL DID NOT RUN", CALLS == [], CALLS)
    d2 = [e for e in rec2.entries() if e["type"] == "decision"][-1]
    check("the record says refused and not executed",
          d2["verdict"] == "refused" and d2["executed"] is False, d2)
    check("and carries the reason", "balance" in d2.get("reason", ""), d2.get("reason"))
    check("no approval was invented for a refusal",
          not [e for e in rec2.entries() if e["type"] == "approval"])

    print("\nan approval that names nobody cannot be written at all")
    q = toa.Request("issue_refund", {}, "high", None)
    for label, kw in (
            ("an approver with no id", {"approver": {"kind": "human"},
                                        "identity_source": "oidc"}),
            ("an approver that is not a person",
             {"approver": {"id": "svc", "kind": "agent"},
              "identity_source": "oidc"}),
            ("an identity the model could have written",
             {"approver": HUMAN, "identity_source": "model"}),
            ("an identity taken from the request body",
             {"approver": HUMAN, "identity_source": "request-body"}),
    ):
        try:
            q.approve(**kw)
            check(label + " is refused", False, "it was accepted")
        except toa.Refused:
            check(label + " is refused", True)
    try:
        q.refuse("   ")
        check("a refusal with no reason is refused", False, "accepted")
    except toa.Refused:
        check("a refusal with no reason is refused", True)

    print("\nit will not fail open, which is #4845 in this very SDK")
    for label, fn in (
            ("returning None from an unhandled branch", lambda q: None),
            ("returning True", lambda q: True),
            ("returning a string", lambda q: "approved"),
            ("returning the request without deciding", lambda q: q),
            ("forgetting to return at all", lambda q: q.approve and None),
    ):
        CALLS.clear()
        r3 = recorder(fn)
        a3, cfg3 = agent_and_config()
        try:
            await r3.run(Runner, a3, "Refund order 8842", run_config=cfg3)
            check("decide() " + label, False, "it was allowed to run")
        except toa.NoDecision:
            check("decide() " + label + " raises", CALLS == [], CALLS)
        except Exception as e:                                   # noqa: BLE001
            check("decide() " + label, False,
                  "raised %s, not NoDecision" % type(e).__name__)

    CALLS.clear()
    r4 = recorder(None)
    a4, cfg4 = agent_and_config()
    try:
        await r4.run(Runner, a4, "Refund order 8842", run_config=cfg4)
        check("a high-risk tool with no decide= at all", False, "it ran")
    except toa.NoDecision:
        check("a high-risk tool with no decide= at all refuses", CALLS == [])

    print("\nan unclassified tool stops the run rather than guessing")
    r5 = toa.Recorder(agent={"id": "a", "kind": "agent"},
                      risk={"search_docs": "low"},
                      decide=lambda q: q.approve(approver=HUMAN,
                                                 identity_source="oidc"))
    a5, cfg5 = agent_and_config()
    try:
        await r5.run(Runner, a5, "Refund order 8842", run_config=cfg5)
        check("a tool missing from the risk table", False, "it was classified")
    except toa.Refused as e:
        check("a tool missing from the risk table raises", "risk class" in str(e))

    print("\nthe record the adapter writes is one the validator accepts")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "record.jsonl")
        rec.write(p)
        rep = tv.validate(io.open(p, encoding="utf-8").read())
        check("it reaches TR-4", rep.level == "TR-4",
              [c["check"] for c in rep.checks if not c["ok"]])
        # TR-3 is the level the census found this SDK could not reach, so it is
        # the one worth naming: an approval that identifies a person, from a
        # source the model cannot write.
        check("and every check carrying TR-3 passed",
              all(c["ok"] for c in rep.checks if c.get("level") == "TR-3"),
              [c["check"] for c in rep.checks
               if c.get("level") == "TR-3" and not c["ok"]])
        rec2.write(p)
        rep2 = tv.validate(io.open(p, encoding="utf-8").read())
        check("a record whose only decision was a refusal also validates",
              rep2.level == "TR-4",
              [c["check"] for c in rep2.checks if not c["ok"]])

    print("\nit needs nothing from OMEM")
    src = io.open(os.path.join(ROOT, "adapters", "openai-agents",
                               "testimony_openai_agents.py"),
                  encoding="utf-8").read()
    check("the adapter does not import omem", "omem" not in src.lower())
    check("and depends only on the emitter", "import testimony_emit" in src)
    check("and does not import the SDK at module level, so this file loads "
          "without it", "\nimport agents" not in src and "\nfrom agents" not in src)

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

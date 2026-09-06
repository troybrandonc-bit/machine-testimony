"""The Pydantic AI adapter, against a real Agent.
Run: python3 tests_pydantic_ai_testimony.py

No network and no API key: only the model is scripted, using the framework's
own FunctionModel. The Agent, the tools, `requires_approval`, the
DeferredToolRequests pause and the DeferredToolResults resume are all the real
ones, because those are what is under test and a stand-in for them would be a
stand-in for the finding.

The property this file exists for is in their own type signature:

    approvals: dict[str, bool | DeferredToolApprovalResult]

A bare True approves. The framework's design is good and does more than most,
since ToolApproved carries override_args, so it already understands that what
was approved and what the model proposed can differ. But a boolean has nowhere
to put a person, and the census found that is where almost every system stops.
So the adapter must never write one, and that is asserted here rather than
described.

The second property is the one pydantic-ai#6968 is about. When an approver
allows something other than what the model asked for, the record has to say
which of the two happened, or a reader six months later cannot tell.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))
sys.path.insert(0, os.path.join(ROOT, "adapters", "pydantic-ai"))

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
    from pydantic_ai import Agent, DeferredToolRequests
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel
except ImportError as e:
    print("SKIP: pydantic-ai is not installed (%s)" % e)
    print("  pip install pydantic-ai-slim")
    raise SystemExit(0)

import testimony_pydantic_ai as tp     # noqa: E402

CALLS = []
HUMAN = {"id": "r.okonkwo@example.com", "kind": "human"}
RISK = {"issue_refund": "high", "search_docs": "low"}


def build(script=None):
    """A real Agent whose model asks for a refund, then reports."""
    CALLS.clear()
    state = {"n": 0}

    def model(messages, info):
        state["n"] += 1
        if state["n"] == 1:
            return ModelResponse(parts=[ToolCallPart(
                "issue_refund", {"customer": "8842", "amount": 4200},
                tool_call_id="call_1")])
        return ModelResponse(parts=[TextPart("Done.")])

    agent = Agent(FunctionModel(model), output_type=[str, DeferredToolRequests])

    @agent.tool_plain(requires_approval=True)
    def issue_refund(customer: str, amount: int) -> str:
        """Refund a customer."""
        CALLS.append(("issue_refund", customer, amount))
        return "refunded %d to %s" % (amount, customer)

    return agent


def recorder(decide=None, risk=None):
    return tp.Recorder(agent={"id": "support-agent", "kind": "agent"},
                       risk=risk or RISK, decide=decide)


print("a permitted call runs, and the record says who allowed it")
rec = recorder(lambda q: q.approve(approver=HUMAN, identity_source="auth-session"))
res = rec.run_sync(build(), "Refund order 8842")
check("the run finished rather than staying paused",
      not isinstance(res.output, DeferredToolRequests), res.output)
check("the tool actually ran", CALLS == [("issue_refund", "8842", 4200)], CALLS)
es = rec.entries()
d = [e for e in es if e["type"] == "decision"][-1]
a = [e for e in es if e["type"] == "approval"][-1]
check("the decision is on the record as executed",
      d["verdict"] == "permitted" and d["executed"] is True, d)
check("the approval names a person", a["approver"]["id"] == HUMAN["id"], a)
check("and where the identity came from",
      a["identity_source"] == "auth-session", a)
check("and the decision points back at it", d.get("approval") == a["id"], d)
check("the risk came from the table, not the model",
      d["risk_source"] == "registry" and d["risk_class"] == "high", d)
check("the tool_call_id is carried, so the record joins to their trace",
      d.get("tool_call_id") == "call_1", d.get("tool_call_id"))

print("\nwhen the approver changes the arguments, the record says so")
# pydantic-ai#6968: an approver shown one thing while another executes has not
# approved the action that happened. ToolApproved(override_args=...) is the
# framework's own hook for this, and the record has to keep both halves.
rec2 = recorder(lambda q: q.approve(approver=HUMAN, identity_source="oidc",
                                    arguments={"customer": "8842", "amount": 5}))
rec2.run_sync(build(), "Refund order 8842")
check("the tool ran with what the approver allowed",
      CALLS == [("issue_refund", "8842", 5)], CALLS)
d2 = [e for e in rec2.entries() if e["type"] == "decision"][-1]
check("the record's arguments are the approved ones",
      d2["arguments"]["amount"] == 5, d2.get("arguments"))
check("and it keeps what the model originally proposed",
      d2.get("proposed_arguments", {}).get("amount") == 4200,
      d2.get("proposed_arguments"))

print("\na refusal does not execute, and the model is told why")
rec3 = recorder(lambda q: q.refuse("a balance is outstanding"))
rec3.run_sync(build(), "Refund order 8842")
check("THE TOOL DID NOT RUN", CALLS == [], CALLS)
d3 = [e for e in rec3.entries() if e["type"] == "decision"][-1]
check("the record says refused and not executed",
      d3["verdict"] == "refused" and d3["executed"] is False, d3)
check("and carries the reason", "balance" in d3.get("reason", ""), d3.get("reason"))
check("no approval was invented for a refusal",
      not [e for e in rec3.entries() if e["type"] == "approval"])

print("\nit never writes the boolean their type signature allows")
# approvals: dict[str, bool | DeferredToolApprovalResult]. A bare True approves
# and has nowhere to put a person, which is the whole reason this exists.
src = io.open(os.path.join(ROOT, "adapters", "pydantic-ai",
                           "testimony_pydantic_ai.py"), encoding="utf-8").read()
check("the adapter assigns no bare boolean into approvals",
      "approvals[call.tool_call_id] = True" not in src
      and "= bool(" not in src)
check("it builds ToolApproved or ToolDenied instead",
      "ToolApproved(" in src and "ToolDenied(" in src)

print("\nit will not fail open")
for label, fn in (
        ("returning None from an unhandled branch", lambda q: None),
        ("returning True", lambda q: True),
        ("returning a string", lambda q: "approved"),
        ("returning the request without deciding", lambda q: q),
        ("forgetting to return at all", lambda q: q.approve and None)):
    r = recorder(fn)
    try:
        r.run_sync(build(), "Refund order 8842")
        check("decide() " + label, False, "it was allowed to run")
    except tp.NoDecision:
        check("decide() " + label + " raises", CALLS == [], CALLS)
    except Exception as e:                                       # noqa: BLE001
        check("decide() " + label, False,
              "raised %s, not NoDecision" % type(e).__name__)

r = recorder(None)
try:
    r.run_sync(build(), "Refund order 8842")
    check("a high-risk tool with no decide= at all", False, "it ran")
except tp.NoDecision:
    check("a high-risk tool with no decide= at all refuses", CALLS == [])

print("\nan approval that names nobody cannot be written")
q = tp.Request("issue_refund", {}, "call_1", "high")
for label, kw in (
        ("an approver with no id", {"approver": {"kind": "human"},
                                    "identity_source": "oidc"}),
        ("an approver that is not a person",
         {"approver": {"id": "svc", "kind": "agent"}, "identity_source": "oidc"}),
        ("an identity the model could have written",
         {"approver": HUMAN, "identity_source": "model"}),
        ("an identity from the request body",
         {"approver": HUMAN, "identity_source": "request-body"})):
    try:
        q.approve(**kw)
        check(label + " is refused", False, "accepted")
    except tp.Refused:
        check(label + " is refused", True)
try:
    q.refuse("  ")
    check("a refusal with no reason is refused", False, "accepted")
except tp.Refused:
    check("a refusal with no reason is refused", True)

print("\nan unclassified tool stops the run rather than guessing")
r = recorder(lambda q: q.approve(approver=HUMAN, identity_source="oidc"),
             risk={"search_docs": "low"})
try:
    r.run_sync(build(), "Refund order 8842")
    check("a tool missing from the risk table", False, "it was classified")
except tp.Refused as e:
    check("a tool missing from the risk table raises", "risk class" in str(e))

print("\nthe record it writes is one the validator accepts")
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "record.jsonl")
    rec.write(p)
    rep = tv.validate(io.open(p, encoding="utf-8").read())
    check("it reaches TR-4", rep.level == "TR-4",
          [c["check"] for c in rep.checks if not c["ok"]])
    check("and every check carrying TR-3 passed",
          all(c["ok"] for c in rep.checks if c.get("level") == "TR-3"),
          [c["check"] for c in rep.checks
           if c.get("level") == "TR-3" and not c["ok"]])
    rec3.write(p)
    rep3 = tv.validate(io.open(p, encoding="utf-8").read())
    check("a record whose only decision was a refusal also validates",
          rep3.level == "TR-4",
          [c["check"] for c in rep3.checks if not c["ok"]])

print("\nit needs nothing from OMEM")
check("the adapter does not import omem", "omem" not in src.lower())
check("and depends only on the emitter", "import testimony_emit" in src)
check("and does not import the framework at module level",
      "\nimport pydantic_ai" not in src and "\nfrom pydantic_ai" not in src)

print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)

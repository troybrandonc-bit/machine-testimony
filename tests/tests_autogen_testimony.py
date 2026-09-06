"""The AutoGen adapter, against a real workbench.
Run: python3 tests_autogen_testimony.py

An adapter is a claim about somebody else's library, so it is checked against
that library rather than against a stand-in written here. A stand-in agrees
with the adapter by construction, which is the one thing a test must not do.

Three properties, each a way an approval gate quietly stops being one.

  IT MUST NOT FAIL OPEN. openai-agents-python#4845 is this mistake in a shipped
  SDK: a callable `needs_approval` predicate returned None from an unhandled
  branch, and None read as "no approval needed", so the gate opened on the path
  nobody had thought about. A decide() that returns None, True, a string, or
  nothing at all must raise here and must not execute the tool.

  A REFUSAL MUST NOT EXECUTE. The obvious one, and the one worth an assertion
  rather than a reading, because the refusal path is the path nobody exercises.

  THE RECORD MUST SURVIVE THE VALIDATOR. Not "looks right": run through the
  reference validator, which is the same file a stranger would run.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
import asyncio
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))
sys.path.insert(0, os.path.join(ROOT, "adapters", "autogen"))

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
    from autogen_core.tools import FunctionTool, StaticWorkbench  # noqa: F401
except ImportError:
    print("SKIP: autogen-core is not installed")
    print("  pip install autogen-core")
    raise SystemExit(0)

import testimony_autogen as ta         # noqa: E402

CALLS = []


def issue_refund(customer: str, amount: int) -> str:
    """Refund a customer."""
    CALLS.append(("issue_refund", customer, amount))
    return "refunded %d to %s" % (amount, customer)


def search_docs(query: str) -> str:
    """Search the documentation."""
    CALLS.append(("search_docs", query))
    return "three results for %r" % query


def bench():
    return StaticWorkbench([
        FunctionTool(issue_refund, description="Refund a customer."),
        FunctionTool(search_docs, description="Search the docs."),
    ])


RISK = {"issue_refund": "high", "search_docs": "low"}
HUMAN = {"id": "r.okonkwo@example.com", "kind": "human"}


def recorder(decide=None):
    return ta.Recorder(agent={"id": "support-agent", "kind": "agent"},
                       risk=RISK, decide=decide)


async def main():
    print("it wraps a real workbench and does not change what the model sees")
    rec = recorder(lambda q: q.approve(approver=HUMAN,
                                       identity_source="auth-session"))
    inner = bench()
    wb = rec.gate(inner)
    names = sorted(t["name"] for t in await wb.list_tools())
    check("list_tools passes straight through",
          names == sorted(t["name"] for t in await inner.list_tools()), names)
    check("and it really is a Workbench, so an agent will take it",
          isinstance(wb, __import__("autogen_core.tools",
                                    fromlist=["Workbench"]).Workbench))

    print("\na permitted high-risk call runs, and says who allowed it")
    CALLS.clear()
    r = await wb.call_tool("issue_refund", {"customer": "8842", "amount": 4200})
    check("the tool actually ran", CALLS == [("issue_refund", "8842", 4200)], CALLS)
    check("and the workbench result came back", not r.is_error, r.to_text()[:80])
    es = rec.entries()
    d = [e for e in es if e["type"] == "decision"][-1]
    a = [e for e in es if e["type"] == "approval"][-1]
    check("the decision is on the record as executed",
          d["verdict"] == "permitted" and d["executed"] is True, d)
    check("the approval names a person", a["approver"]["id"] == HUMAN["id"], a)
    check("and where the identity came from",
          a["identity_source"] == "auth-session", a)
    check("and the decision points back at it", d.get("approval") == a["id"], d)
    check("the arguments are on the record, not only the tool name",
          d.get("arguments") == {"customer": "8842", "amount": 4200}, d.get("arguments"))

    print("\na low-risk call needs nobody, and is still recorded")
    CALLS.clear()
    await wb.call_tool("search_docs", {"query": "refunds"})
    d2 = [e for e in rec.entries() if e["type"] == "decision"][-1]
    check("it ran without an approval", CALLS and d2["executed"] is True, CALLS)
    check("and claims no approver it did not have", "approval" not in d2, d2)

    print("\na refusal does not execute, and is on the record as loudly")
    rec2 = recorder(lambda q: q.refuse("a balance is outstanding"))
    wb2 = rec2.gate(bench())
    CALLS.clear()
    r2 = await wb2.call_tool("issue_refund", {"customer": "8842", "amount": 4200})
    check("THE TOOL DID NOT RUN", CALLS == [], CALLS)
    check("the caller is told, rather than being given a silent success",
          r2.is_error and "balance is outstanding" in r2.to_text(), r2.to_text()[:120])
    d3 = [e for e in rec2.entries() if e["type"] == "decision"][-1]
    check("the record says refused and not executed",
          d3["verdict"] == "refused" and d3["executed"] is False, d3)
    check("and carries the reason", "balance" in d3.get("reason", ""), d3.get("reason"))

    print("\nit will not fail open, which is the whole job")
    # Each of these is a decide() that a reasonable person might write by
    # accident. None of them may be read as permission. See #4845.
    for label, fn in (
            ("returning None from an unhandled branch", lambda q: None),
            ("returning True", lambda q: True),
            ("returning a string", lambda q: "approved"),
            ("returning the request without deciding", lambda q: q),
            ("forgetting to return at all", lambda q: q.approve and None),
    ):
        r3 = recorder(fn)
        w3 = r3.gate(bench())
        CALLS.clear()
        try:
            await w3.call_tool("issue_refund", {"customer": "1", "amount": 1})
            check("decide() " + label, False, "it was allowed to run")
        except ta.NoDecision:
            check("decide() " + label + " raises", CALLS == [], CALLS)
        except Exception as e:                                   # noqa: BLE001
            check("decide() " + label, False,
                  "raised %s, not NoDecision" % type(e).__name__)

    r4 = recorder(None)
    w4 = r4.gate(bench())
    CALLS.clear()
    try:
        await w4.call_tool("issue_refund", {"customer": "1", "amount": 1})
        check("a high-risk tool with no decide= at all", False, "it ran")
    except ta.NoDecision:
        check("a high-risk tool with no decide= at all refuses to run",
              CALLS == [])

    print("\nan unclassified tool stops the run rather than guessing")
    r5 = recorder(lambda q: q.approve(approver=HUMAN, identity_source="oidc"))
    w5 = r5.gate(bench())
    try:
        await w5.call_tool("delete_everything", {})
        check("a tool missing from the risk table", False, "it was classified")
    except ta.Refused as e:
        check("a tool missing from the risk table raises", "risk class" in str(e))

    print("\nstreaming is refused rather than half-gated")
    try:
        wb.call_tool_stream("issue_refund", {})
        check("call_tool_stream", False, "it returned something")
    except NotImplementedError as e:
        check("call_tool_stream says why it is not gated",
              "already acted" in str(e), str(e)[:100])

    print("\nthe record the adapter writes is one the validator accepts")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "record.jsonl")
        rec.write(p)
        rep = tv.validate(io.open(p, encoding="utf-8").read())
        check("it reaches TR-4", rep.level == "TR-4",
              [c["check"] for c in rep.checks if not c["ok"]])
        # TR-3 is the level that says an approval names a person and a source.
        # It is the one the census found five of six systems could not reach,
        # so it is the one worth naming here.
        check("and every check that carries TR-3 passed",
              all(c["ok"] for c in rep.checks if c.get("level") == "TR-3"),
              [c["check"] for c in rep.checks
               if c.get("level") == "TR-3" and not c["ok"]])

        rec2.write(p)
        rep2 = tv.validate(io.open(p, encoding="utf-8").read())
        check("a record whose only decision was a refusal also validates",
              rep2.level == "TR-4",
              [c["check"] for c in rep2.checks if not c["ok"]])

    print("\nit needs nothing from OMEM")
    src = io.open(os.path.join(ROOT, "adapters", "autogen",
                               "testimony_autogen.py"), encoding="utf-8").read()
    check("the adapter does not import omem", "omem" not in src.lower())
    check("and depends only on the emitter", "import testimony_emit" in src)

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

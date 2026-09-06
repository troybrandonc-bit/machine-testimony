"""The CrewAI adapter, against real CrewAI tools.
Run: python3 tests_crewai_testimony.py

An adapter is a claim about somebody else's library, so it is checked against
that library rather than a stand-in written here. A stand-in agrees with the
adapter by construction, which is the one thing a test must not do.

The property this file exists for is that the gate cannot fail open.
openai-agents-python#4845 is that mistake in a shipped SDK: a callable
`needs_approval` predicate returned None from an unhandled branch, None read as
"no approval needed", and the gate opened on the path nobody had thought about.
Every shape of that mistake is tried here and every one must raise without the
tool running.

The second property is that wrapping must be invisible. CrewAI builds
`args_schema` from the `_run` signature when none is given, and the wrapper's
`_run` is `(*args, **kwargs)`, so a wrapper that failed to carry the inner
schema would present every tool to the model as taking no arguments. That is a
silent failure that still passes a smoke test, so it gets an assertion.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))
sys.path.insert(0, os.path.join(ROOT, "adapters", "crewai"))

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
    from crewai.tools import BaseTool
except ImportError:
    print("SKIP: crewai is not installed")
    print("  pip install crewai")
    raise SystemExit(0)

import testimony_crewai as tc          # noqa: E402

CALLS = []


class Refund(BaseTool):
    name: str = "issue_refund"
    description: str = "Refund a customer."

    def _run(self, customer: str, amount: int) -> str:
        CALLS.append(("issue_refund", customer, amount))
        return "refunded %d to %s" % (amount, customer)


class Search(BaseTool):
    name: str = "search_docs"
    description: str = "Search the documentation."

    def _run(self, query: str) -> str:
        CALLS.append(("search_docs", query))
        return "three results for %r" % query


RISK = {"issue_refund": "high", "search_docs": "low"}
HUMAN = {"id": "r.okonkwo@example.com", "kind": "human"}


def recorder(decide=None):
    return tc.Recorder(agent={"id": "support-agent", "kind": "agent"},
                       risk=RISK, decide=decide)


def main():
    print("wrapping is invisible to the model")
    rec = recorder(lambda q: q.approve(approver=HUMAN,
                                       identity_source="auth-session"))
    inner = Refund()
    g = rec.gate(inner)
    check("it is still a crewai tool, so an agent will take it",
          isinstance(g, BaseTool))
    check("the name is carried", g.name == inner.name, g.name)
    check("the description is carried", inner.description in g.description,
          g.description[:80])
    # The one that would fail silently: an empty schema still runs, and the
    # model simply stops passing arguments.
    inner_fields = set(inner.args_schema.model_fields)
    check("the argument schema is the inner tool's, not one built from *args",
          set(g.args_schema.model_fields) == inner_fields and inner_fields,
          "%s vs %s" % (set(g.args_schema.model_fields), inner_fields))
    check("gate_all wraps a list", len(rec.gate_all([Refund(), Search()])) == 2)

    print("\na permitted high-risk call runs, and says who allowed it")
    CALLS.clear()
    out = g.run(customer="8842", amount=4200)
    check("the tool actually ran", CALLS == [("issue_refund", "8842", 4200)], CALLS)
    check("and the caller got the tool's own result", "refunded 4200" in str(out), out)
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
          d.get("arguments", {}).get("amount") == 4200, d.get("arguments"))

    print("\na low-risk call needs nobody, and is still recorded")
    rec_l = recorder()
    gl = rec_l.gate(Search())
    CALLS.clear()
    gl.run(query="refunds")
    dl = [e for e in rec_l.entries() if e["type"] == "decision"][-1]
    check("it ran with no decide= at all", CALLS and dl["executed"] is True, CALLS)
    check("and claims no approver it did not have", "approval" not in dl, dl)

    print("\na refusal does not execute, and is on the record as loudly")
    rec2 = recorder(lambda q: q.refuse("a balance is outstanding"))
    g2 = rec2.gate(Refund())
    CALLS.clear()
    said = g2.run(customer="8842", amount=4200)
    check("THE TOOL DID NOT RUN", CALLS == [], CALLS)
    check("the agent is told, rather than given a silent success",
          "balance is outstanding" in str(said), str(said)[:120])
    d3 = [e for e in rec2.entries() if e["type"] == "decision"][-1]
    check("the record says refused and not executed",
          d3["verdict"] == "refused" and d3["executed"] is False, d3)
    check("and carries the reason", "balance" in d3.get("reason", ""), d3.get("reason"))

    print("\nit will not fail open, which is the whole job")
    for label, fn in (
            ("returning None from an unhandled branch", lambda q: None),
            ("returning True", lambda q: True),
            ("returning a string", lambda q: "approved"),
            ("returning the request without deciding", lambda q: q),
            ("forgetting to return at all", lambda q: q.approve and None),
    ):
        r3 = recorder(fn)
        g3 = r3.gate(Refund())
        CALLS.clear()
        try:
            g3.run(customer="1", amount=1)
            check("decide() " + label, False, "it was allowed to run")
        except tc.NoDecision:
            check("decide() " + label + " raises", CALLS == [], CALLS)
        except Exception as e:                                   # noqa: BLE001
            check("decide() " + label, False,
                  "raised %s, not NoDecision" % type(e).__name__)

    r4 = recorder(None)
    g4 = r4.gate(Refund())
    CALLS.clear()
    try:
        g4.run(customer="1", amount=1)
        check("a high-risk tool with no decide= at all", False, "it ran")
    except tc.NoDecision:
        check("a high-risk tool with no decide= at all refuses to run",
              CALLS == [])

    print("\nan unclassified tool is refused at wrap time, not mid-run")
    class Wild(BaseTool):
        name: str = "delete_everything"
        description: str = "No."

        def _run(self) -> str:
            return "gone"

    try:
        recorder().gate(Wild())
        check("a tool missing from the risk table", False, "it was wrapped")
    except tc.Refused as e:
        check("a tool missing from the risk table refuses before the crew runs",
              "risk class" in str(e))

    print("\nthe record the adapter writes is one the validator accepts")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "record.jsonl")
        rec.write(p)
        rep = tv.validate(io.open(p, encoding="utf-8").read())
        check("it reaches TR-4", rep.level == "TR-4",
              [c["check"] for c in rep.checks if not c["ok"]])
        # TR-3 is the level saying an approval names a person and a source. It
        # is the one the census found five of six acting systems could not
        # reach, so it is the one worth naming.
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
    src = io.open(os.path.join(ROOT, "adapters", "crewai",
                               "testimony_crewai.py"), encoding="utf-8").read()
    check("the adapter does not import omem", "omem" not in src.lower())
    check("and depends only on the emitter", "import testimony_emit" in src)

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""A refund desk in LangGraph that can say who approved the refund.

    pip install langgraph
    python3 example.py > record.jsonl
    python3 ../../scripts/testimony_validate.py record.jsonl

Fifty lines of ordinary LangGraph, plus six lines of recorder. The graph is
deliberately dull: it forms a belief about a customer, proposes a refund, and
pauses for a person. That is the shape most human-in-the-loop agents already
have, which is the point. Nothing here is specific to any memory product.

Run it and the record reaches TR-4. Delete the approver argument and it stops
at TR-2, which is the honest state of every such graph today.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt
from typing_extensions import TypedDict

from testimony_langgraph import Recorder


class State(TypedDict, total=False):
    ticket: int
    amount: int
    refunded: bool


def assess(state: State) -> State:
    # A real agent would reason here. What matters for the record is that the
    # belief it lands on is written down with what it rested on.
    return {"amount": 4200}


def gate(state: State) -> State:
    # The payload names the action. That name is what the risk table is keyed
    # on, and the table belongs to the operator, not to the model.
    ok = interrupt({"action": "issue_refund",
                    "args": {"ticket": state["ticket"],
                             "amount": state["amount"]}})
    return {"refunded": bool(ok)}


def build():
    g = StateGraph(State)
    g.add_node("assess", assess)
    g.add_node("gate", gate)
    g.add_edge(START, "assess")
    g.add_edge("assess", "gate")
    g.add_edge("gate", END)
    return g.compile(checkpointer=InMemorySaver())


def anchored(path, want):
    """Say what the record does not carry, and add it when asked.

    A record written above reaches TR-4, which the specification calls
    Verifiable: a reader can recompute the arithmetic. The integrity entry is a
    hash chain this process computed, so anybody able to rewrite the entries can
    recompute it too. That detects a later edit by a third party and says
    nothing about the party holding the file.

    An external anchor is the difference. Its evidence is held by a timestamp
    authority, so the emitter cannot move it. It needs the network, which is why
    it is a flag and not the default: an example that cannot run offline is not
    an example, and a test suite that depends on somebody else's service is not
    a test suite.
    """
    if not want:
        print("TR-4 by arithmetic, with NO external anchor.")
        print("The integrity entry is a hash chain this process computed, so it")
        print("is recomputable by anyone who can rewrite the entries. For an")
        print("anchor whose evidence somebody else holds, rerun with --anchor,")
        print("or: python3 -m testimony_anchor %s" % path)
        return path
    import json
    from testimony_anchor import anchor_entry
    rows = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    entry = anchor_entry(rows)
    with io.open(path, "a", encoding="utf-8", newline=chr(10)) as fh:
        fh.write(json.dumps(entry, sort_keys=False) + chr(10))
    print("anchored: %s, %s" % (entry["anchor"]["kind"],
                                entry["anchor"]["authority"]))
    print("proves:   %s" % entry["anchor"]["proves"])
    print("does not: %s" % entry["anchor"]["does_not_prove"])

    # Say what the record now reaches instead of assuming. Appending an anchor
    # can LOWER the level, and the way it does is worth meeting here rather
    # than in production: the validator refuses an entry whose write time is
    # later than the moment the authority saw the digest. If this machine's
    # clock runs even a second ahead of the authority's, entries written a
    # moment ago are, by the authority's clock, from the future.
    try:
        from testimony_validate import validate
    except Exception:                                         # noqa: BLE001
        return path
    res = validate(io.open(path, encoding="utf-8").read())
    print("level:    %s" % res.level)
    bad = [c for c in res.as_dict()["checks"]
           if c["level"] == "TR-4" and not c["ok"]]
    for c in bad:
        print("  not met: %s" % c["check"])
        if "later than the anchor" in c["check"]:
            print("  This is clock skew, not backdating. Anchoring seconds")
            print("  after writing is not the realistic pattern either: a")
            print("  deployer anchors a record that is finished. The check is")
            print("  doing its job and the authority's clock is the one that")
            print("  counts.")
    return path


def main(path="-", anchor=False) -> int:
    graph = build()
    config = {"configurable": {"thread_id": "ticket-41"}}

    rec = Recorder(
        agent={"id": "support-agent", "kind": "agent"},
        # Risk comes from here, not from the model. An action missing from this
        # table raises rather than defaulting.
        risk={"issue_refund": "high", "send_receipt": "low"},
        risk_source="registry",
    )

    ev = rec.cite("api", "billing://orders/8812",
                  digest="sha256:" + "0" * 64)
    rec.believe("customer:acme", "eligible_for_refund", evidence=[ev])

    rec.invoke(graph, {"ticket": 41}, config)

    # The identity comes from the caller's authentication layer. LangGraph
    # cannot supply it, this adapter will not invent it, and that is the whole
    # difference between this record and the one the same graph produces
    # without it.
    rec.approve(graph, config,
                approver={"id": "troy@example.com", "kind": "human",
                          "name": "T. Clifford", "role": "owner"},
                identity_source="auth-session")

    rec.write(path)
    anchored(path, anchor)
    return 0


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if x != "--anchor"]
    raise SystemExit(main(args[0] if args else "-",
                          "--anchor" in sys.argv))

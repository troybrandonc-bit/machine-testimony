#!/usr/bin/env python3
"""Four questions your agent's log probably cannot answer. Two minutes, no install.

    python3 demo/what_your_log_cannot_answer.py

This is not about anybody's product. It writes the log almost every agent
writes, which is a timestamp, an action and an outcome, then asks it the four
questions somebody asks after something goes wrong. Then it writes the same run
again as a Testimony Record and asks the same four questions.

The point is not that the second format is nicer. It is that the questions have
answers in one and not the other, and that the difference is not effort or
sophistication. It is four fields nobody thought to write down, because
everything worked at the time.

Run it against your own log format by replacing `ordinary_log` with yours. If
your log answers all four, this project has nothing to offer you and that is a
good outcome.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "spec"))

BOLD, DIM, OFF = "\033[1m", "\033[2m", "\033[0m"
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    BOLD = DIM = OFF = ""


def head(t):
    print("\n" + BOLD + t + OFF)


def dim(t):
    print(DIM + t + OFF)


# ── the run being recorded ──────────────────────────────────────────────────
#
# A support agent handles a refund. Two systems of record disagree about the
# customer's balance, the agent picks one, an approval happens, money moves.
# Nothing here is unusual and nothing goes wrong.

def ordinary_log() -> list:
    """The log almost everyone writes. Timestamp, actor, action, outcome."""
    return [
        {"ts": "2026-09-02T09:14:03Z", "level": "info",
         "msg": "fetched customer 8842 from crm"},
        {"ts": "2026-09-02T09:14:05Z", "level": "info",
         "msg": "billing: no open invoices"},
        {"ts": "2026-09-02T09:14:06Z", "level": "info",
         "msg": "ledger: balance 61.40 EUR outstanding"},
        {"ts": "2026-09-02T09:14:10Z", "level": "info",
         "msg": "close_account blocked by balance check"},
        {"ts": "2026-09-02T09:31:47Z", "level": "info",
         "msg": "approval received for refund"},
        {"ts": "2026-09-02T09:31:48Z", "level": "info",
         "msg": "issue_refund 38.60 EUR ok"},
    ]


QUESTIONS = [
    ("Who approved the refund?",
     "The log says an approval was received. It does not say by whom, so the "
     "answer is whoever had access, which is not an answer."),
    ("Was the approver the agent itself?",
     "Nothing here distinguishes a person clicking approve from the agent "
     "calling its own approval endpoint. Both write this line."),
    ("What did the agent try and not do?",
     "One line mentions a block, in prose, because somebody thought to log it. "
     "A reader cannot tell whether anything else was attempted and dropped."),
    ("Has this file changed since it was written?",
     "Any line can be edited, added or removed, and nothing about the file "
     "would look different afterwards. Nobody can tell you either way."),
]


def ask_the_ordinary_log(log):
    head("Four questions, asked of the ordinary log")
    for q, why in QUESTIONS:
        print("  %s%s%s" % (BOLD, q, OFF))
        print("    unanswerable. " + why)


# ── the same run, recorded so the questions have answers ────────────────────

def as_a_record():
    """The same events, with the four things nobody wrote down."""
    from testimony_emit import Record

    AGENT = {"id": "support-agent@svc", "kind": "agent"}
    r = Record()
    r.scope(acts=True, at="2026-09-02T09:14:02Z",
            description="Support agent. Refunds to 500 EUR, closures, both "
                        "gated on human approval.")
    e_bill = r.evidence(kind="api", at="2026-09-02T09:14:05Z",
                        source="billing://subscriptions/8842/invoices?status=open",
                        description="Billing reports no open invoices.")
    e_ledg = r.evidence(kind="api", at="2026-09-02T09:14:06Z",
                        source="ledger://accounts/8842/balance",
                        description="Ledger reports 61.40 EUR outstanding.")

    # Both sides of the disagreement are kept, and which one was chosen is
    # recorded with the reason. In the ordinary log the losing side is gone.
    b_no = r.belief(subject="customer:8842", proposition="owes_money",
                    polarity="deny", state="contradicted", asserted_by=AGENT,
                    evidence=[e_bill], at="2026-09-02T09:14:07Z")
    b_yes = r.belief(subject="customer:8842", proposition="owes_money",
                     polarity="affirm", state="believed_true",
                     asserted_by=AGENT, evidence=[e_ledg],
                     at="2026-09-02T09:14:07Z")
    r.conflict(subject="customer:8842", proposition="owes_money",
               sides=[b_no, b_yes], at="2026-09-02T09:14:09Z",
               resolution={"method": "source-precedence", "by": AGENT,
                           "at": "2026-09-02T09:14:09Z", "kept": b_yes,
                           "note": "the ledger is authoritative for balance"})

    # The refusal is an entry, not a sentence in a message.
    r.decision(action_type="close_account", risk_class="high",
               risk_source="registry", proposed_by=AGENT, verdict="refused",
               executed=False, at="2026-09-02T09:14:10Z",
               reason="closure is blocked while a balance is outstanding")

    d = r.decision(action_type="issue_refund", risk_class="high",
                   risk_source="registry", proposed_by=AGENT,
                   verdict="permitted", executed=True,
                   at="2026-09-02T09:14:11Z", amount="38.60 EUR")
    r.approval(decision=d, at="2026-09-02T09:31:47Z",
               approver={"id": "r.okonkwo@example.com", "kind": "human",
                         "role": "support-lead"},
               identity_source="auth-session")
    r.seal()
    return r


def ask_the_record(r):
    import testimony_validate as tv
    entries = [json.loads(x) for x in r.jsonl().splitlines()]
    by_type = {}
    for e in entries:
        by_type.setdefault(e["type"], []).append(e)

    head("The same four questions, asked of the record")

    app = by_type["approval"][0]
    print("  %sWho approved the refund?%s" % (BOLD, OFF))
    print("    %s, and %s says the name came from the authentication layer "
          "rather than from the request body."
          % (app["approver"]["id"], app["identity_source"]))

    dec = [d for d in by_type["decision"] if d["verdict"] == "permitted"][0]
    print("  %sWas the approver the agent itself?%s" % (BOLD, OFF))
    print("    No. The agent is %s and the approver is %s. A record where "
          "those match is refused when it is written."
          % (dec["proposed_by"]["id"], app["approver"]["id"]))

    ref = [d for d in by_type["decision"] if d["verdict"] == "refused"][0]
    print("  %sWhat did the agent try and not do?%s" % (BOLD, OFF))
    print("    %s, refused, not executed, because %s"
          % (ref["action_type"], ref["reason"]))

    g = by_type["integrity"][0]
    print("  %sHas this file changed since it was written?%s" % (BOLD, OFF))
    print("    The digest %s covers %d entries and is recomputable by anyone."
          % (g["digest"][:24] + "...", len(g["covers"])))

    # And demonstrate it rather than asserting it.
    tampered = [dict(e) for e in entries]
    for e in tampered:
        if e["type"] == "approval":
            e["approver"] = dict(e["approver"], id="someone.else@example.com")
    before = tv.validate(r.jsonl()).level
    after = tv.validate("\n".join(json.dumps(e) for e in tampered)).level
    print()
    dim("    Softening the approver's name, to prove the last one:")
    dim("      as written:      %s" % before)
    dim("      after the edit:  %s   (the digest no longer covers it)" % after)


def main() -> int:
    print(BOLD + "What your agent's log cannot answer" + OFF)
    dim("A refund. Two systems disagree about a balance, one action is "
        "refused, another is approved and money moves.")
    dim("Nothing goes wrong. The questions come later, as they always do.")

    log = ordinary_log()
    head("The log almost everyone writes")
    for line in log:
        print("  " + line["ts"] + "  " + line["msg"])

    ask_the_ordinary_log(log)

    try:
        r = as_a_record()
    except Exception as e:                                   # noqa: BLE001
        print("\ncould not build the record (%s). Run this from a checkout of "
              "the repository, which carries spec/testimony_emit.py." % e)
        return 2
    ask_the_record(r)

    head("What actually changed")
    print("  Four fields. Who approved, where that name came from, what was")
    print("  refused, and a digest over the whole thing. None of it is")
    print("  difficult and none of it is new. It is simply not written down,")
    print("  because at the time everything worked.")
    print()
    print("  The specification: https://machinetestimony.org/implement/")
    print("  Eight systems, read against these questions:")
    print("      https://machinetestimony.org/register/")

    out = os.path.join(HERE, "record.jsonl")
    io.open(out, "w", encoding="utf-8", newline="\n").write(r.jsonl())
    dim("\n  The record this produced: %s" % os.path.relpath(out, os.getcwd()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

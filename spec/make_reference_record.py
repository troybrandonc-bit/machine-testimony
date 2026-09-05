"""Build the reference record published at machinetestimony.org/anchor/.

    python3 spec/make_reference_record.py

Writes public/anchor/record.jsonl and public/anchor/anchor.tsr, asks a Time
Stamp Authority to sign the record's digest, and refuses to write anything
unless the result reaches TR-4 and openssl agrees the token covers it.

The record is a worked example rather than a fixture. Somebody deciding
whether this format is worth implementing should be able to read one page of
it and see what it makes checkable: a refusal as well as an execution, a
contradiction with both sides kept, an approver taken from authentication
rather than from the request, and a risk class the proposing model could not
set for itself.

Rerunning this replaces the published record with a newly anchored one. The
old token stays valid for the old record; it is simply no longer the one on
the page. Do not rerun it casually, because the digest on the page is
something people may have quoted.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import testimony_anchor as ta        # noqa: E402
import testimony_validate as tv      # noqa: E402

OUT = os.path.join(ROOT, "public", "anchor")
AGENT = {"id": "support-agent@svc.example", "kind": "agent"}
D = "2026-09-02T"


def body() -> list:
    """One support interaction, recorded.

    The account closure is refused and the refund is executed, because a record
    that only lists what a system did is a receipt. What a system was stopped
    from doing is usually the part somebody asks about later.
    """
    return [
        {"type": "scope", "id": "s1", "at": D + "09:14:02Z", "acts": True,
         "description": "Customer support agent. May issue refunds to 500 EUR "
                        "and close accounts, both gated on human approval.",
         "actions": ["issue_refund", "close_account"]},

        {"type": "evidence", "id": "e1", "at": D + "09:14:03Z", "kind": "message",
         "source": "mailbox://support/2026-09-02/1183",
         "description": "Customer asks to close the account and refund the "
                        "unused period."},
        {"type": "evidence", "id": "e2", "at": D + "09:14:04Z", "kind": "api",
         "source": "crm://customers/8842",
         "description": "Account record: active, opened 2024-11-03."},
        {"type": "evidence", "id": "e3", "at": D + "09:14:05Z", "kind": "api",
         "source": "billing://subscriptions/8842/invoices?status=open",
         "description": "Billing reports no open invoices."},
        {"type": "evidence", "id": "e4", "at": D + "09:14:06Z", "kind": "api",
         "source": "ledger://accounts/8842/balance",
         "description": "Ledger reports 61.40 EUR outstanding."},

        {"type": "belief", "id": "b1", "at": D + "09:14:07Z",
         "subject": "customer:8842", "proposition": "requested_account_closure",
         "polarity": "affirm", "state": "believed_true",
         "asserted_by": AGENT, "evidence": ["e1"]},

        # Two systems of record disagree. Neither is wrong about itself, and an
        # agent that silently picks one has made the decision that matters
        # somewhere nobody can see it.
        {"type": "belief", "id": "b2", "at": D + "09:14:08Z",
         "subject": "customer:8842", "proposition": "owes_money",
         "polarity": "deny", "state": "contradicted",
         "asserted_by": AGENT, "evidence": ["e3"]},
        {"type": "belief", "id": "b3", "at": D + "09:14:08Z",
         "subject": "customer:8842", "proposition": "owes_money",
         "polarity": "affirm", "state": "believed_true",
         "asserted_by": AGENT, "evidence": ["e4"]},
        {"type": "conflict", "id": "c1", "at": D + "09:14:09Z",
         "subject": "customer:8842", "proposition": "owes_money",
         "sides": ["b2", "b3"],
         "resolution": {"method": "source-precedence", "by": AGENT,
                        "at": D + "09:14:09Z", "kept": "b3",
                        "note": "The ledger is authoritative for balance; the "
                                "invoice query answers a narrower question."}},

        # Refused. The record says so, and says what was proposed, because a
        # system that logs only its executions cannot be asked what it declined.
        {"type": "decision", "id": "d1", "at": D + "09:14:10Z",
         "action_type": "close_account", "risk_class": "high",
         "risk_source": "registry", "proposed_by": AGENT,
         "verdict": "refused", "executed": False,
         "reason": "Closure is blocked while a balance is outstanding. Held for "
                   "the customer to be told, not escalated."},

        {"type": "decision", "id": "d2", "at": D + "09:14:11Z",
         "action_type": "issue_refund", "risk_class": "high",
         "risk_source": "registry", "proposed_by": AGENT,
         "verdict": "permitted", "executed": True, "approval": "a1",
         "amount": "38.60 EUR",
         "reason": "Unused period refunded net of the outstanding balance."},

        # The name comes from the session the approver authenticated in. Taken
        # from the request body it would be an assertion about a person rather
        # than a fact about one.
        {"type": "approval", "id": "a1", "at": D + "09:31:47Z",
         "decision": "d2",
         "approver": {"id": "r.okonkwo@example.com", "kind": "human",
                      "role": "support-lead"},
         "identity_source": "auth-session",
         "note": "Approved the net refund. Declined the closure pending "
                 "contact with the customer."},
    ]


def main() -> int:
    entries = [dict(e, spec=tv.SPEC) for e in body()]
    entries = [{"spec": e.pop("spec"), "type": e.pop("type"), "id": e.pop("id"),
                "at": e.pop("at"), **e} for e in entries]

    before = tv.validate("\n".join(json.dumps(e) for e in entries))
    if before.level != "TR-3":
        print("the record does not reach TR-3 before anchoring: %s" % before.level)
        for c in before.checks:
            if not c["ok"]:
                print("  %s  %s  %s" % (c["level"], c["check"], c.get("detail", "")))
        return 1

    entry = ta.anchor_entry(entries, eid="i1")
    entries.append(entry)
    text = "\n".join(json.dumps(e) for e in entries) + "\n"

    after = tv.validate(text)
    if after.level != "TR-4":
        print("anchored and still not TR-4: %s" % after.level)
        return 1

    import base64
    token = base64.b64decode(entry["anchor"]["token"])
    digest = entry["digest"].split(":", 1)[1]
    if not _openssl_agrees(token, digest):
        print("openssl will not verify the token against the record's digest, "
              "so the page's instructions would not work")
        return 1

    os.makedirs(OUT, exist_ok=True)
    io.open(os.path.join(OUT, "record.jsonl"), "w", encoding="utf-8",
            newline="\n").write(text)
    io.open(os.path.join(OUT, "anchor.tsr"), "wb").write(token)
    print("TR-3 without the anchor, TR-4 with it")
    print("authority: %s" % entry["anchor"]["authority"])
    print("signed at: %s" % entry["anchor"]["anchored_at"])
    print("digest:    %s" % digest)
    print("written:   public/anchor/record.jsonl, public/anchor/anchor.tsr")
    return 0


def _openssl_agrees(token: bytes, digest: str) -> bool:
    """The token really covers this digest, according to openssl and not us.

    Only the imprint is compared here. Whether the signature chains to a root
    is checked by the suite against a CA bundle, because that is what a reader
    following the page will do and it should not be assumed.
    """
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.tsr")
        io.open(p, "wb").write(token)
        r = subprocess.run(["openssl", "ts", "-reply", "-in", p, "-text"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("openssl could not read the token: %s"
                  % (r.stderr or "").strip()[:200])
            return False
        return imprint_hex(r.stdout) == digest


def imprint_hex(openssl_text: str) -> str:
    """The message imprint openssl read, as plain hex.

    openssl prints it as a dump: an offset, the bytes, then an ASCII column
    between pipes. The ASCII column can hold anything, so it is cut away before
    hex is looked for rather than filtered out afterwards.
    """
    m = re.search(r"Message data:(.*?)\n\s*\S+ number", openssl_text, re.S)
    if not m:
        return ""
    out = []
    for line in m.group(1).splitlines():
        line = line.split("|")[0]
        if "-" in line:
            line = line.split("-", 1)[1]
        out += re.findall(r"\b[0-9a-f]{2}\b", line)
    return "".join(out)


if __name__ == "__main__":
    sys.exit(main())

"""Obligations, and which signal in a set of records would evidence one.

    from criteria import against
    print(against(rows, "eu-ai-act"))

The four questions are this project's, and nobody is assessed against them. A
deployer is assessed against a clause somebody else wrote, so a finding that
does not name the clause leaves them to do the translation, and translation is
where a tool stops being obvious and starts being homework.

**This maps and it does not conclude.** It reports which obligations these rows
could evidence and which they could not, against a published reading of the
text. It is not legal advice, it is not a compliance assessment, and it is not
an opinion about anybody: the assessor still forms that. Saying which of those
this is matters more here than anywhere else in the repository, because a tool
that quietly reads as a compliance verdict would be the same error as a record
that quietly reads as proof.

The obligations below are the mapping already published at /eu-ai-act/, as data
rather than prose, so the page and the tool cannot say different things. A test
holds them to each other.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testimony_convert as tc                              # noqa: E402

# A signal is something the rows can be searched for without interpreting them.
# `member` is looked up the way the converter looks up any member; `kind` says
# how, since a digest is found by hint rather than by synonym.
SIGNALS = {
    "write_time": ("at", "when each row was written"),
    "evidence_link": ("source", "what a stated conclusion rested on"),
    "verdict": ("verdict", "whether an action was permitted or refused"),
    "reason": ("reason", "why a refusal was refused"),
    "risk_source": ("risk_source", "where an action's risk class came from"),
    "approver": ("approver.id", "who intervened"),
    "identity_source": ("identity_source",
                        "where that identity was resolved from"),
    "integrity": ("integrity", "anything that would show the rows unaltered"),
    "user_id": ("user_id", "which user or session acted"),
    "device": ("device", "the device or location it acted from"),
    "ip": ("ip", "the network address it acted from"),
    "activity": ("action_type", "what the system did"),
}

# Some criteria no log can answer, because they are about a policy, a document
# or a retention period rather than about a record's contents. Marking those
# NOT EVIDENCED would report a failure where there is only a category error,
# and an assessor reading that would rightly stop trusting the rest. They are
# named and set aside instead, which is also useful: it tells somebody which
# criteria their logs speak to at all before they go looking.
NOT_IN_RECORDS = "not answerable from records"

# Instrument, clause, what a record has to show, and the signals that would
# evidence it. Every row here appears at /eu-ai-act/ and the wording is that
# page's, because two statements of the same reading are two to drift.
EU_AI_ACT = (
    ("Art. 12",
     "Events recorded automatically as they occur, append-only, each carrying "
     "its own write time, in one stated format.",
     ("write_time",)),
    ("Art. 12",
     "What the system concluded, and what each conclusion rested on, "
     "including where it rested on nothing. Contradictions retained rather "
     "than silently resolved.",
     ("evidence_link",)),
    ("Art. 14",
     "Every consequential action carries a verdict, whether or not it ran, "
     "with a risk class the proposing model could not set.",
     ("verdict", "risk_source")),
    ("Art. 14",
     "An intervention is attributable: the record names the person or the "
     "named role holder, takes that identity from authentication rather than "
     "from run state, and the approver is not the principal that proposed the "
     "action.",
     ("approver", "identity_source")),
    ("Art. 14",
     "Refusals recorded as faithfully as permissions, with reasons. A record "
     "of only what was done cannot show oversight working.",
     ("verdict", "reason")),
    ("Art. 15",
     "Accuracy and robustness figures as declared, and resistance to "
     "manipulation of the record itself.",
     ("integrity",)),
)

# ForHumanity's certification criteria, as read on 6 September 2026 across
# CORE AAA System Governance Deployer v1.6, EU AI Act Multi AAA Agent
# Governance v1.5, Provider v1.5, Deployer v1.6, and the Guidance on Supporting
# AAA System Procurement v1.0. Published at
# https://machinetestimony.org/obligation/.
#
# The finding that matters to somebody being audited against these: the Event
# Log is defined as five components paraphrased from ISO 27001, and they answer
# which SESSION acted. A deployer can satisfy the logging criterion completely
# and still be unable to say which person approved anything, because no
# criterion asks. That is worth knowing before an audit rather than during one.
FORHUMANITY = (
    ("EM-EU-PR-RK-AC-2602-001",
     "Event Logs across twelve areas including the orchestration layer, "
     "outcomes, a risk log and a human interactions log.",
     ("write_time", "activity")),
    ("EM-EU-PR-RK-AC-2602-001",
     "The Event Log's five components, paraphrased from ISO 27001: user ID, "
     "system activity, date and time, device and location, and IP address.",
     ("user_id", "activity", "write_time", "device", "ip")),
    ("EM-EU-PR-RK-AC-2602-005",
     "Retention according to the relevant legal framework, and failing that "
     "no less than six months.",
     (NOT_IN_RECORDS,)),
    ("Read across all five documents",
     "No criterion requires that a retained Event Log be shown not to have "
     "been altered. Data Integrity is defined as prevention of unauthorised "
     "modification, which is a control rather than a property of the record.",
     (NOT_IN_RECORDS,)),
    ("Read across all five documents",
     "No criterion asks who approved. Natural person appears 49 times and the "
     "single occurrence of approver is a plan approver in an unrelated "
     "criterion. Nothing here obliges the record to name a person, which is "
     "why satisfying the logging criteria does not answer it.",
     (NOT_IN_RECORDS,)),
)

INSTRUMENTS = {
    "eu-ai-act": ("the EU AI Act, as read at "
                  "https://machinetestimony.org/eu-ai-act/", EU_AI_ACT),
    "forhumanity": ("the ForHumanity certification criteria, as read at "
                    "https://machinetestimony.org/obligation/", FORHUMANITY),
}


def _seen(rows: list) -> dict:
    out = {}
    for row in rows[:200]:
        for path, value in tc._paths(row).items():
            out.setdefault(path, value)
    return out


def _find(seen: dict, rows: list, signal: str):
    member = SIGNALS[signal][0]
    if signal == "integrity":
        return tc._has_integrity(rows)
    hit = tc.match(seen, member)
    return hit[0] if hit else None


def against(rows: list, instrument: str = "eu-ai-act",
            name: str = "the file") -> str:
    """Which obligations these rows could evidence, and which they could not."""
    if instrument not in INSTRUMENTS:
        # ValueError rather than SystemExit: this is a library call, and a
        # module that exits the process is one nobody can build on.
        raise ValueError("no published reading of %r. One of: %s"
                         % (instrument, ", ".join(sorted(INSTRUMENTS))))
    where, table = INSTRUMENTS[instrument]
    seen = _seen(rows)
    out = ["%d rows read from %s, against %s." % (len(rows), name, where), ""]
    short = 0
    aside = 0
    for clause, shows, signals in table:
        if signals == (NOT_IN_RECORDS,):
            aside += 1
            out.append("  NOT IN RECORDS  %s" % clause)
            out.append("  %-15s %s" % ("", shows))
            out.append("      no log answers this: it is about a policy, a "
                       "document or a period")
            out.append("")
            continue
        found = {s: _find(seen, rows, s) for s in signals}
        missing = [s for s, v in found.items() if not v]
        if missing:
            short += 1
            out.append("  NOT EVIDENCED   %s" % clause)
        else:
            out.append("  COULD EVIDENCE  %s" % clause)
        out.append("  %-15s %s" % ("", shows))
        for s in signals:
            mark = "from %r" % found[s] if found[s] else "NOTHING HERE"
            out.append("      %s" % SIGNALS[s][1])
            out.append("      %-6s %s" % ("", mark))
        out.append("")
    out.append("%d of %d obligations cannot be evidenced from these rows."
               % (short, len(table) - aside) if short else
               "Every obligation a record can speak to has something in these "
               "rows to rest on.")
    if aside:
        out.append("%d more are not about a record's contents at all and were "
                   "set aside rather than failed." % aside)
    out += ["",
            "What this is. A search of the rows you gave it for the things a "
            "published reading",
            "of the text says a record has to show. It reports what is present "
            "and what is not.",
            "",
            "What it is not, and this matters more than the finding. It is not "
            "legal advice, it",
            "is not a compliance assessment, and it is not an opinion about "
            "anybody. Whether an",
            "obligation is met is a judgement somebody qualified makes on "
            "evidence, and this",
            "gathers evidence. A row marked NOT EVIDENCED means these records "
            "cannot show it,",
            "not that the obligation is breached: it may be evidenced "
            "somewhere these rows have",
            "never been.",
            "",
            "The reading it is measured against is published and dated, and a "
            "wrong one is",
            "cheap to show: " + where]
    return chr(10).join(out)

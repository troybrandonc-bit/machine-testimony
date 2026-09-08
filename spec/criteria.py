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
}

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

INSTRUMENTS = {
    "eu-ai-act": ("the EU AI Act, as read at "
                  "https://machinetestimony.org/eu-ai-act/", EU_AI_ACT),
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
    for clause, shows, signals in table:
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
               % (short, len(table)) if short else
               "Every obligation here has something in these rows to rest on.")
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

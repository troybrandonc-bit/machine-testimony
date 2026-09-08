"""Assess repeatedly, and keep the history as a record somebody else can check.

    python3 spec/watch.py history.jsonl their-logs.jsonl --against eu-ai-act

A single assessment is a consulting deliverable. What a deployer needs, and
what an assessor asks for, is whether the evidence was there all along and when
it stopped being there. That is a different product and it is mostly the same
work done repeatedly and kept.

**The history is itself a Testimony Record**, which is the point rather than a
flourish. It is append-only, every entry carries its own write time, each
belief cites the field it rested on or states plainly that it rested on
nothing, a criterion that changes produces a conflict entry naming both sides
rather than quietly overwriting the old answer, and the whole thing can be
sealed and anchored. So a deployer can show not only what their records could
evidence, but that they were watching, and when they knew.

Monitoring that rests on the monitor's own word is the thing this project
exists to object to, so it would be indefensible for the monitoring here to
rest on ours.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import criteria                                              # noqa: E402
import testimony_convert as tc                               # noqa: E402
import testimony_emit as em                                  # noqa: E402

WATCHER = {"id": "machine-testimony/watch", "kind": "system"}
PROPOSITION = "evidenced_by_the_records_read"


def assess(rows: list, instrument: str) -> list:
    """One reading: every criterion, whether it is evidenced, and by what."""
    where, table = criteria.INSTRUMENTS[instrument]
    seen = criteria._seen(rows)
    out = []
    for n, (clause, shows, signals) in enumerate(table):
        if signals == (criteria.NOT_IN_RECORDS,):
            continue                # no log answers it, so nothing to watch
        found = {s: criteria._find(seen, rows, s) for s in signals}
        out.append({"key": "%s:%d" % (instrument, n), "clause": clause,
                    "shows": shows,
                    "evidenced": all(found.values()),
                    "from": sorted(v for v in found.values() if v)})
    return out


def _load(path: str) -> list:
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in io.open(path, encoding="utf-8")
            if l.strip()]


def _restore(entries: list) -> em.Record:
    """A Record carrying what the history already holds, so ids stay unique
    and the append-only rule is enforced across runs rather than only within
    one."""
    r = em.Record()
    r.entries = list(entries)
    r._ids = {e.get("id") for e in entries}
    r._n = len(entries)
    r._last = max((e.get("at", "") for e in entries), default="")
    return r


def _last_belief(entries: list, key: str):
    """The most recent belief about one criterion, if the history has one."""
    for e in reversed(entries):
        if e.get("type") == "belief" and e.get("subject") == key:
            return e
    return None


def watch(history: str, rows: list, instrument: str, at: str = "") -> dict:
    """Append this reading to the history, and name what changed."""
    entries = _load(history)
    r = _restore(entries)
    if not entries:
        # The watcher observes and takes no action of its own, which is a
        # claim the format makes checkable rather than one it takes on trust.
        r.scope(acts=False, at=at or None,
                description="Assessment of records against %s. Observes only."
                            % instrument)
    run = len([e for e in entries if e.get("type") == "integrity"]) + 1
    changed, first = [], []
    # One field is one piece of evidence, however many criteria rest on it.
    # Minting a second entry for the same path would say the record found it
    # twice, and a reader counting evidence would be counting the same thing.
    cited_this_run = {}
    for row in assess(rows, instrument):
        prior = _last_belief(entries, row["key"])
        was = None if prior is None else (prior.get("polarity") == "affirm")
        now = row["evidenced"]

        cited = []
        for path in row["from"]:
            if path not in cited_this_run:
                cited_this_run[path] = r.evidence(
                    kind="derived", source=path, at=at or None,
                    id="e%d_%d" % (run, len(cited_this_run)))
            cited.append(cited_this_run[path])
        bid = r.belief(
            subject=row["key"], proposition=PROPOSITION,
            asserted_by=WATCHER, evidence=cited,
            polarity="affirm" if now else "deny",
            state="believed_true", at=at or None,
            id="b%d_%d" % (run, len(r.entries)))

        if was is None:
            first.append(row)
        elif was != now:
            changed.append((row, was, now))
            # Both sides retained and named, rather than the old answer being
            # overwritten by the new one. A monitor that silently replaced
            # yesterday's finding would be unable to say when anything moved.
            r.conflict(subject=row["key"], proposition=PROPOSITION,
                       sides=[prior["id"], bid], at=at or None,
                       id="c%d_%d" % (run, len(r.entries)))
    r.seal(at=at or None, id="g%d" % run)
    io.open(history, "w", encoding="utf-8", newline="").write(
        r.jsonl() + chr(10))
    return {"run": run, "changed": changed, "first": first,
            "entries": len(r.entries)}


def summarise(res: dict, instrument: str, history: str) -> str:
    out = ["reading %d, appended to %s (%d entries)."
           % (res["run"], history, res["entries"]), ""]
    if res["run"] == 1:
        short = [c for c in res["first"] if not c["evidenced"]]
        out.append("First reading, so nothing has changed yet. %d of %d "
                   "criteria could not be evidenced from these records."
                   % (len(short), len(res["first"])))
        for c in short:
            out.append("  NOT EVIDENCED   %s" % c["clause"])
    elif not res["changed"]:
        out.append("Nothing changed since the last reading.")
    else:
        out.append("%d changed since the last reading:" % len(res["changed"]))
        for row, was, now in res["changed"]:
            out.append("  %s  %s" % ("LOST     " if was else "GAINED   ",
                                     row["clause"]))
            out.append("      %s" % row["shows"][:88])
            out.append("      %s" % ("nothing here now"
                                     if not now else
                                     "now from " + ", ".join(row["from"])))
    out += ["",
            "The history is a Testimony Record. Every reading is append-only "
            "with its own",
            "write time, a criterion that changed carries a conflict entry "
            "naming both",
            "sides rather than overwriting the old answer, and the file can be "
            "validated",
            "and anchored by somebody who does not trust either of us.",
            "",
            "  python3 spec/testimony_validate.py " + history]
    return chr(10).join(out)


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(
            "usage: watch.py HISTORY.jsonl RECORDS.jsonl "
            "[--against INSTRUMENT]" + chr(10)
            + "assess the records, append the reading to the history, and "
            "say what changed")
    history, source = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    instrument = "eu-ai-act"
    if "--against" in args:
        i = args.index("--against")
        if i + 1 < len(args):
            instrument = args[i + 1]
    if instrument not in criteria.INSTRUMENTS:
        raise SystemExit("no published reading of %r. One of: %s"
                         % (instrument, ", ".join(sorted(criteria.INSTRUMENTS))))

    text = io.open(source, encoding="utf-8").read()
    try:
        whole = json.loads(text)
    except ValueError:
        whole = None
    if tc.is_otlp(whole):
        rows = tc.otlp_rows(whole)
    elif isinstance(whole, list):
        rows = [x for x in whole if isinstance(x, dict)]
    elif isinstance(whole, dict):
        rows = [whole]
    else:
        rows = []
        for line in text.split(chr(10)):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    if not rows:
        raise SystemExit("no JSON objects in %s" % source)
    print(summarise(watch(history, rows, instrument), instrument, history))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

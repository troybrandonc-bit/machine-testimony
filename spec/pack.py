"""The bundle a deployer hands an assessor, and the assessor can check alone.

    python3 spec/pack.py history.jsonl --out evidence-pack/

An assessment nobody can reproduce is an opinion with a logo on it. What an
assessor needs to accept evidence from a party they are assessing is a way to
reach the same finding without taking either the deployer's word or the word of
whoever wrote the tool.

So the pack carries the record, the reading, and the commands. The commands are
not a convenience: they are the reason the rest of it is worth anything. Every
number in the summary is recomputed by something the assessor runs, against
files in the pack, using a validator published elsewhere.

**It contains no telemetry.** The history holds which criteria were evidenced
and by which field name, never the field's contents, so the pack can leave the
deployer's infrastructure when the telemetry it was derived from cannot.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import criteria                                              # noqa: E402
import testimony_validate as tv                              # noqa: E402
import watch as w                                            # noqa: E402

REPO = "https://github.com/troybrandonc-bit/machine-testimony"


def _readings(entries: list) -> list:
    """Each sealed reading in the history, in order."""
    out, seen = [], set()
    for e in entries:
        if e.get("type") == "integrity":
            out.append({"at": e.get("at"), "id": e.get("id"),
                        "covers": len(e.get("covers") or [])})
    return out


def _state(entries: list) -> dict:
    """The latest belief about every criterion, and when it last moved."""
    latest, moved = {}, {}
    for e in entries:
        if e.get("type") != "belief":
            continue
        key = e.get("subject")
        prior = latest.get(key)
        if prior and prior.get("polarity") != e.get("polarity"):
            moved[key] = e.get("at")
        latest[key] = e
    return {"latest": latest, "moved": moved}


def summary(history: str, entries: list) -> str:
    st = _state(entries)
    readings = _readings(entries)
    inst = sorted({k.split(":")[0] for k in st["latest"]})
    tables = {}
    for i in inst:
        if i in criteria.INSTRUMENTS:
            tables[i] = criteria.INSTRUMENTS[i][1]

    out = ["# What these records could evidence, and since when", ""]
    out.append("Readings: %d, from %s to %s."
               % (len(readings),
                  readings[0]["at"][:10] if readings else "?",
                  readings[-1]["at"][:10] if readings else "?"))
    out.append("")
    out.append("This is a summary of `history.jsonl` in this pack. Nothing "
               "here is a compliance")
    out.append("assessment or an opinion about whether an obligation is met. "
               "It reports which")
    out.append("criteria the records read could evidence, and when that last "
               "changed. Whether")
    out.append("that is sufficient is the assessor's judgement, not the "
               "tool's.")
    out.append("")

    for i, table in tables.items():
        where = criteria.INSTRUMENTS[i][0]
        out += ["## %s" % where, "",
                "| criterion | evidenced | last changed |", "|---|---|---|"]
        n = 0
        for idx, (clause, shows, signals) in enumerate(table):
            if signals == (criteria.NOT_IN_RECORDS,):
                out.append("| %s | not answerable from records | |" % clause)
                continue
            key = "%s:%d" % (i, idx)
            b = st["latest"].get(key)
            if not b:
                continue
            n += 1
            out.append("| %s | %s | %s |"
                       % (clause,
                          "yes" if b.get("polarity") == "affirm" else "**no**",
                          st["moved"].get(key, "not since the first reading")))
        out.append("")

    out += ["## Check it without taking anybody's word", "",
            "Every line above comes from `history.jsonl`, which is a Testimony "
            "Record: append-only,",
            "each entry carrying its own write time, each belief citing the "
            "field it rested on or",
            "stating that it rested on nothing, and a criterion that changed "
            "carrying a conflict",
            "entry naming both the old finding and the new one.",
            "",
            "The validator is published separately and is not in this pack, "
            "so running it is not",
            "running anything the party being assessed supplied:", "",
            "```",
            "git clone %s" % REPO,
            "python3 machine-testimony/spec/testimony_validate.py "
            "history.jsonl",
            "```", "",
            "The digest below is over `history.jsonl` as it sits in this "
            "pack. If the deployer",
            "anchored the record, the anchor is inside it and the validator "
            "checks it; if they did",
            "not, this digest is the deployer's own word and the validator "
            "says so rather than",
            "implying otherwise.", ""]
    return chr(10).join(out)


def build(history: str, out_dir: str) -> dict:
    entries = w._load(history)
    if not entries:
        raise ValueError("%s holds no entries" % history)
    rep = tv.validate(io.open(history, encoding="utf-8").read()).as_dict()

    os.makedirs(out_dir, exist_ok=True)
    shutil.copyfile(history, os.path.join(out_dir, "history.jsonl"))
    raw = io.open(os.path.join(out_dir, "history.jsonl"), "rb").read()
    digest = hashlib.sha256(raw).hexdigest()

    text = summary(history, entries) + chr(10).join([
        "```",
        "sha256  %s  history.jsonl" % digest,
        "```",
        "",
        "The record reaches **%s**, and %d of its checks are settled by "
        "reading it while %d"
        % (rep["level"] or "no level",
           sum(v["verified"] for v in rep["basis"].values()),
           sum(v["attested"] for v in rep["basis"].values())),
        "rest on the emitter's word. That split is the validator's output, "
        "not a claim made",
        "here, and it is printed with every run.",
        ""])
    io.open(os.path.join(out_dir, "SUMMARY.md"), "w",
            encoding="utf-8").write(text)
    io.open(os.path.join(out_dir, "VERDICT.json"), "w",
            encoding="utf-8").write(json.dumps(
                {"level": rep["level"], "scope": rep["scope"],
                 "basis": rep["basis"], "sha256": digest,
                 "entries": len(entries)}, indent=2, sort_keys=True))
    return {"out": out_dir, "digest": digest, "level": rep["level"],
            "entries": len(entries)}


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: pack.py HISTORY.jsonl [--out DIR]")
    args = sys.argv[2:]
    out = args[args.index("--out") + 1] if "--out" in args and \
        args.index("--out") + 1 < len(args) else "evidence-pack"
    res = build(sys.argv[1], out)
    print("wrote %s" % res["out"])
    print("  history.jsonl  the record, %d entries" % res["entries"])
    print("  SUMMARY.md     what it could evidence, and since when")
    print("  VERDICT.json   the validator's own output, level %s"
          % res["level"])
    print()
    print("sha256 %s" % res["digest"])
    print()
    print("The pack holds no telemetry: the history keeps which criteria were")
    print("evidenced and by which field NAME, never the field's contents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

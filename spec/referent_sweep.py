"""Which fields name something outside the record, and does anything check them.

    python3 spec/referent_sweep.py [record.jsonl]

The format's argument is that a report should say what rests on evidence and
what rests on the emitter's word. This asks the same question of the format
itself: substitute a meaningless value into every field that stands in for a
referent, reseal the record, and report which checks notice.

Resealing matters. Any edit breaks the integrity digest, so without recomputing
it every field looks constrained and the sweep measures the digest check
instead of the field. That was the first version's error.

Fields are classified rather than counted. Free text is free text by design and
constraining it would be wrong; a proposition is the emitter's own vocabulary
and stays coherent when substituted consistently, which is correct. What the
sweep is looking for is the third class: a string a reader must resolve
somewhere else before the entry means anything.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import copy
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testimony_validate as tv                             # noqa: E402

# A reader must resolve these elsewhere for the entry to mean anything.
REFERENT = ["source", "asserted_by.id", "proposed_by.id", "approver.id",
            "approver.name", "approver.role", "declared_by.id", "engine",
            "engine_version", "method"]
# The emitter's own vocabulary. Substituted consistently a record stays
# coherent, and that is the right behaviour rather than a gap.
VOCABULARY = ["subject", "proposition", "action_type"]
# Free text for a human. Constraining it would be an error.
PROSE = ["excerpt", "reason"]

NONSENSE = "trust me"


def reseal(entries: list) -> list:
    by_id = {e.get("id"): e for e in entries}
    for e in entries:
        if e.get("type") == "integrity" and e.get("covers"):
            covered = [by_id[c] for c in e["covers"] if c in by_id]
            e["digest"] = "sha256:" + tv.digest_of(covered)
    return entries


def verdict(entries: list):
    rep = tv.validate(chr(10).join(json.dumps(e) for e in entries)).as_dict()
    return ({(c["level"], c["check"]): (c["ok"], c["basis"])
             for c in rep["checks"]}, rep["level"])


def _set(o, parts, val) -> bool:
    if not isinstance(o, dict) or parts[0] not in o:
        return False
    if len(parts) == 1:
        if isinstance(o[parts[0]], str):
            o[parts[0]] = val
            return True
        return False
    return _set(o[parts[0]], parts[1:], val)


def sweep(raw: list, fields: list) -> list:
    base, base_level = verdict(reseal(copy.deepcopy(raw)))
    out = []
    for path in fields:
        ents = copy.deepcopy(raw)
        n = sum(1 for e in ents if _set(e, path.split("."), NONSENSE))
        if not n:
            continue
        got, level = verdict(reseal(ents))
        noticed = [k[1] for k in base if base[k] != got.get(k)]
        out.append({"field": path, "entries": n, "level": level,
                    "noticed": noticed, "held_level": level == base_level})
    return out


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "testimony-record-example.jsonl")
    raw = [json.loads(l) for l in io.open(src, encoding="utf-8") if l.strip()]
    _, level = verdict(reseal(copy.deepcopy(raw)))
    print("%s reaches %s" % (os.path.basename(src), level))

    loose = 0
    for title, fields in (("names a referent outside the record", REFERENT),
                          ("the emitter's own vocabulary", VOCABULARY),
                          ("free text, by design", PROSE)):
        print()
        print("## %s" % title)
        for row in sweep(raw, fields):
            what = "; ".join(row["noticed"])[:52] if row["noticed"] else "-"
            print("  %-16s in %d  %-5s  %s"
                  % (row["field"], row["entries"], row["level"], what))
            if fields is REFERENT and not row["noticed"] and row["held_level"]:
                loose += 1

    print()
    print("%d of %d referent fields accept %r with no check reacting and the "
          "level held." % (loose, len(REFERENT), NONSENSE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

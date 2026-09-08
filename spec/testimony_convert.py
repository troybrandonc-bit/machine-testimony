"""Express records you already write as Testimony Records, and be told what is missing.

    from testimony_convert import Mapping, convert

    m = Mapping("approval", {
        "decision":        "action_id",
        "approver.id":     "actor.principal",
        "approver.kind":   const("human"),
        "identity_source": "auth.method",
    })
    out = convert(my_receipts, m)
    print(out.report())

Most projects that would benefit from this format are not starting from
nothing. They already write receipts in a shape they invented, because there
was no obvious one, and they have already paid the expensive part. For them the
question is not how to record but what their existing shape cannot say, and
answering it by reading a forty page draft is the reason it does not get
answered.

So this takes a declaration of which of your fields mean what, builds what it
can, and reports every required field it had no value for. The report is the
useful half. It is a measurement of your format rather than advice about it.

**It never invents a value.** A required field with no source is reported
missing and left out, so the conversion fails loudly instead of producing a
record that answers a question the source could not. Filling in an approver
would be the exact defect this format exists to make visible, and a converter
that did it would be worse than no converter.

Standard library only, MIT licensed, meant to be copied into your repository.
It needs `testimony_emit.py` beside it, so that everything the emitter refuses
at the point of the mistake is still refused here.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testimony_emit as em                                 # noqa: E402

MISSING = object()


def _required(entry_type: str) -> tuple:
    """Every field the emitter will demand for this entry type.

    REQUIRED is the format's own list and it is not the whole story: an
    approval also takes `identity_source`, because a name with no stated
    origin is the defect the census keeps finding. Reading the signature as
    well means a field the emitter insists on is reported as missing, in the
    report, rather than surfacing later as a Python TypeError nobody can act
    on.
    """
    named = getattr(em.Record, entry_type, None)
    from_sig = ()
    if named is not None:
        from_sig = tuple(
            n for n, p in inspect.signature(named).parameters.items()
            if n != "self" and p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY))
    seen, out = set(), []
    for f in tuple(em.REQUIRED.get(entry_type, ())) + from_sig:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return tuple(out)


def const(value):
    """A fixed value, for a field your records do not carry per row."""
    return lambda _row: value


def path(dotted: str):
    """A dotted path into the source row, missing if any step is absent."""
    def get(row):
        cur = row
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            elif isinstance(cur, list) and part.isdigit() and \
                    int(part) < len(cur):
                cur = cur[int(part)]
            else:
                return MISSING
        return cur
    return get


class Mapping:
    """Which of your fields mean what, for one entry type."""

    def __init__(self, entry_type: str, fields: dict, when=None):
        if entry_type not in em.REQUIRED:
            raise ValueError("%r is not an entry type. One of: %s"
                             % (entry_type, ", ".join(sorted(em.REQUIRED))))
        self.entry_type = entry_type
        self.when = when or (lambda _row: True)
        self.fields = {}
        for name, src in fields.items():
            self.fields[name] = src if callable(src) else path(str(src))


class Converted:
    def __init__(self):
        self.entries, self.rows, self.refusals = [], [], []

    @property
    def missing(self) -> dict:
        """Required field to the number of source rows that could not fill it."""
        out = {}
        for row in self.rows:
            for f in row["missing"]:
                out[f] = out.get(f, 0) + 1
        return out

    def jsonl(self) -> str:
        return chr(10).join(json.dumps(e) for e in self.entries)

    def report(self) -> str:
        n = len(self.rows)
        lines = ["%d source row%s, %d entries built"
                 % (n, "" if n == 1 else "s", len(self.entries))]
        built = sum(1 for r in self.rows if not r["missing"] and not r["error"])
        lines.append("%d converted with every required field, %d short"
                     % (built, len(self.rows) - built))
        if self.missing:
            lines.append("")
            lines.append("required fields your records had no value for:")
            for f, n in sorted(self.missing.items(), key=lambda kv: -kv[1]):
                lines.append("  %-22s %d of %d row%s"
                             % (f, n, len(self.rows),
                                "" if len(self.rows) == 1 else "s"))
        if self.refusals:
            lines.append("")
            lines.append("refused by the emitter, which is the format "
                         "disagreeing with the data:")
            for r in self.refusals[:8]:
                lines.append("  " + r)
        if not self.missing and not self.refusals:
            lines.append("")
            lines.append("nothing missing. Validate it to see the level it "
                         "reaches and what each check rests on.")
        return chr(10).join(lines)


def _assemble(row: dict, mapping: Mapping) -> tuple:
    """Values for one row, and the required fields that had no source."""
    built, missing = {}, []
    for name, get in mapping.fields.items():
        value = get(row)
        if value is MISSING or value is None:
            continue
        parts = name.split(".")
        cur = built
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value
    for req in _required(mapping.entry_type):
        if built.get(req) in (None, "", {}, []) and built.get(req) is not False:
            missing.append(req)
    return built, missing


def convert(rows: list, *mappings: Mapping, record=None) -> Converted:
    """Source rows to a Testimony Record, with what could not be filled.

    Rows are offered to each mapping in turn and the first whose `when`
    accepts takes it, so one pass over a mixed log produces evidence,
    decisions and approvals from the rows that are each of those.
    """
    out = Converted()
    r = record or em.Record()
    for row in rows:
        for m in mappings:
            if not m.when(row):
                continue
            built, missing = _assemble(row, m)
            entry = {"type": m.entry_type, "missing": missing, "error": ""}
            if missing:
                out.rows.append(entry)
                break
            try:
                getattr(r, m.entry_type)(**built)
            except em.Refused as e:
                entry["error"] = str(e)
                out.refusals.append("%s: %s" % (m.entry_type, e))
            except TypeError as e:
                entry["error"] = str(e)
                out.refusals.append("%s: %s" % (m.entry_type, e))
            out.rows.append(entry)
            break
    out.entries = list(r.entries)
    return out

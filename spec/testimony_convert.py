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
import io
import json
import os
import re
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

# ── suggesting a mapping, so the first run costs a command ───────────────────
#
# Writing a Mapping by hand means reading the format first, and that reading is
# the whole cost this file exists to remove. So it reads the records instead,
# proposes what each field looks like, and prints a Mapping to correct.
#
# A SUGGESTION, never a conversion. The proposal is printed for a person to fix
# and nothing is converted from a guess, because a converter that silently
# guessed which field held the approver would produce a clean record answering
# a question the source never answered, which is the defect this whole format
# exists to make visible. Everything below is labelled with how it was reached.

# Names seen in the wild for each member, lowercased, matched on whole
# word-ish parts rather than substrings so `user_id` does not become `id`.
SYNONYMS = {
    "action_type": ("action", "action_type", "tool", "tool_name", "operation",
                    "method", "op", "command", "capability"),
    "risk_class": ("risk", "risk_class", "risk_level", "severity", "criticality"),
    "verdict": ("verdict", "decision", "allowed", "permitted", "outcome",
                "result", "status"),
    "executed": ("executed", "ran", "performed", "applied", "did_run",
                 "was_executed"),
    "reason": ("reason", "rationale", "why", "explanation", "message",
               "denial_reason"),
    "approver.id": ("approver", "approver_id", "approved_by", "principal",
                    "reviewer", "authorizer", "authoriser", "signer"),
    "identity_source": ("identity_source", "auth_method", "auth_type",
                        "authentication", "idp", "auth_source"),
    "proposed_by.id": ("agent", "agent_id", "actor", "actor_id", "caller",
                       "requester", "initiator", "proposer"),
    "asserted_by.id": ("asserted_by", "author", "writer", "observer", "agent"),
    "source": ("source", "uri", "url", "origin", "reference", "ref",
               "document", "location"),
    "subject": ("subject", "entity", "about", "target", "customer", "user"),
    "proposition": ("proposition", "claim", "fact", "attribute", "property",
                    "predicate"),
    "decision": ("decision_id", "action_id", "request_id", "call_id",
                 "correlation_id", "receipt_id", "receipt"),
    # Every log names its own clock differently and the Elastic one starts
    # with an @, which is why the parts split drops punctuation.
    # The ForHumanity Event Log's five components. `user_id` is deliberately
    # not `approver`: it answers which session acted, which is what that
    # criterion asks for and is not the same question.
    "user_id": ("user_id", "userid", "user", "principal", "subject_id",
                "account", "session_user", "actor_id", "username"),
    "device": ("device", "device_id", "host", "hostname", "location",
               "geo", "region", "workstation", "user_agent"),
    "ip": ("ip", "ip_address", "client_ip", "remote_addr", "source_ip",
           "src_ip", "peer"),
    "at": ("at", "ts", "time", "timestamp", "datetime", "event_time",
           "occurred_at", "created_at", "logged_at", "start_time",
           "starttimeunixnano", "observedtimeunixnano"),
}
# Members a record cannot get from a field, only from the emitter's own model.
NOT_MAPPABLE = ("polarity", "state", "acts", "sides", "evidence")
# Leaves that name nothing on their own. `approver.id` must not match
# `gen_ai.agent.id` because both end in `id`: that is the agent's own
# identifier, and reporting it as the approver would tell a reader they can
# say who approved when what they have is the agent approving itself, which is
# the exact failure this format exists to make visible. A dotted member is
# matched on the part that carries the meaning, never on the last one.
GENERIC = ("id", "name", "type", "value", "key", "code", "status", "label")
# An actor is an object with an id and a kind, never a bare string, so these
# expand into two lines rather than one. The kind is proposed from the member
# and not from the data, which is why it is written as a const for a person to
# confirm: a system that logs an agent id under `approved_by` would otherwise
# be handed `kind: human` by this file and never told.
ACTORS = {"proposed_by": "agent", "asserted_by": "agent",
          "approver": "human", "declared_by": "system"}


def _paths(row, prefix=""):
    """Every dotted path to a scalar in one row."""
    out = {}
    if isinstance(row, dict):
        for k, v in row.items():
            here = prefix + k
            if isinstance(v, dict):
                out.update(_paths(v, here + "."))
            elif not isinstance(v, (list, tuple)):
                out[here] = v
    return out


def _parts(name):
    return set(re.split(r"[^a-z0-9]+", name.lower())) - {""}


def suggest(rows: list, entry_type: str) -> dict:
    """Which of their fields might mean what. A draft, not an answer.

    Returns {member: (path, why)} for what could be matched, and leaves out
    what could not, so the caller can see the difference between a field that
    was found and one that has to be supplied.
    """
    seen = {}
    for row in rows[:200]:
        for path, value in _paths(row).items():
            seen.setdefault(path, value)
    out = {}
    for member in _required(entry_type):
        if member in NOT_MAPPABLE:
            continue
        lookup = member + ".id" if member in ACTORS else member
        hit = match(seen, lookup)
        if hit:
            out[lookup] = hit
    return out


def match(seen: dict, member: str):
    """The best candidate path for one member, and why it was picked.

    Whole path, then leaf, then a loose overlap. Real logs nest, so
    `auth.method` means the authentication method and its leaf alone means
    something else entirely: `method` is also what a caller calls the
    operation it invoked. Reading the path is what tells them apart.
    """
    if True:
        want = SYNONYMS.get(member, (member,))
        best = None
        want_parts = [_parts(w) for w in want]
        member_leaf = member.split(".")[-1].lower()
        bare = member_leaf in GENERIC
        best = why = None
        for path, value in seen.items():
            leaf = path.split(".")[-1].lower()
            if _parts(path) in want_parts:
                best, why = path, "the whole path matches"
                break
            if not bare and (leaf == member_leaf or leaf in want):
                best, why = path, "the name matches"
                break
            if leaf in want:
                best, why = path, "the name matches"
                break
            if set(_parts(path)) & set(want):
                best, why = path, "the name looks like it"
        return (best, why) if best else None


def propose(rows: list, entry_type: str, when: str = "") -> str:
    """The suggestion as a Mapping to paste, correct, and run."""
    found = suggest(rows, entry_type)
    need = []
    for m in _required(entry_type):
        if m in NOT_MAPPABLE:
            continue
        need.append(m + ".id" if m in ACTORS else m)
    lines = ["# SUGGESTED, not checked. Every line below is a guess from a "
             "field name.",
             "# Correct it before you trust anything it produces: a wrong "
             "mapping makes a",
             "# clean record that answers a question your system never "
             "answered.",
             "%s = Mapping(%r, {" % (entry_type + "s", entry_type)]
    for m in need:
        if m in found:
            path, why = found[m]
            lines.append("    %-20s %-24s  # %s" % ('"%s":' % m,
                                                    '"%s",' % path, why))
            base = m[:-3] if m.endswith(".id") else ""
            if base in ACTORS:
                lines.append("    %-20s %-24s  # from the member, not your data"
                             % ('"%s.kind":' % base,
                                'const("%s"),' % ACTORS[base]))
        else:
            lines.append("    # %-18s ???                       # nothing in "
                         "your records looks like this" % ('"%s":' % m))
    lines.append("}%s)" % (", when=lambda row: %s" % when if when else ""))
    absent = [m for m in need if m not in found]
    if absent:
        lines += ["",
                  "# %d of %d members had no candidate: %s."
                  % (len(absent), len(need), ", ".join(absent)),
                  "# That is the finding. Either they are somewhere this could "
                  "not see, or",
                  "# your records do not carry them, and the second is worth "
                  "knowing."]
    return chr(10).join(lines)


# ── the four questions, asked of a file of records ───────────────────────────
#
# The census reads a vendor's source at a pinned commit, which is the right way
# to assess a product and the wrong way to assess a deployment: nobody
# reviewing their own supplier is going to read a framework's source, and the
# question they actually have is about their own records.
#
# So this asks the four questions of a file. It reports what is in the file and
# refuses to conclude anything about the system that wrote it, because a system
# may record an approver somewhere this file has never seen. A finding that
# overstated its own scope would be worth nothing to the person who has to
# stand behind it.

QUESTIONS = (
    ("who approved a consequential action", "approver.id",
     "a field that resolves to the identity of a person"),
    ("and whether that was a person rather than the agent itself",
     "identity_source",
     "a field saying where that identity was resolved from"),
    ("what the system tried and did not do", "verdict",
     "a field distinguishing a refused action from an executed one"),
    ("whether the file has changed since it was written", "integrity",
     "a digest, chain or signature over the rows"),
)

INTEGRITY_HINTS = ("digest", "hash", "sha256", "checksum", "signature",
                   "sig", "prev_hash", "chain", "merkle", "seal")


def _has_integrity(rows):
    for path in _paths(rows[0] if rows else {}):
        leaf = path.split(".")[-1].lower()
        if leaf in INTEGRITY_HINTS or (_parts(leaf) & set(INTEGRITY_HINTS)):
            return path
    return None


def report(rows: list, name: str = "the file") -> str:
    """What this file can and cannot answer, and nothing about the system."""
    seen = {}
    for row in rows[:200]:
        for path, value in _paths(row).items():
            seen.setdefault(path, value)
    out = ["%d rows read from %s." % (len(rows), name), ""]
    out.append("Of the four questions somebody asks after something goes "
               "wrong:")
    out.append("")
    unanswerable = 0
    for question, member, what in QUESTIONS:
        if member == "integrity":
            hit = _has_integrity(rows)
            where = hit
        else:
            hit = match(seen, member)
            where = hit[0] if hit else None
        if where:
            out.append("  %-16s %s" % ("ANSWERABLE", question))
            out.append("  %-16s from %r" % ("", where))
        else:
            unanswerable += 1
            out.append("  %-16s %s" % ("NOT IN THE FILE", question))
            out.append("  %-16s nothing here looks like %s" % ("", what))
    out += ["",
            "%d of 4 are not in these rows." % unanswerable if unanswerable
            else "All four are present in these rows.",
            "",
            "What this does and does not say. It reports the shape of the rows "
            "it was given.",
            "A system may record an approver somewhere these rows have never "
            "been, and this",
            "cannot see that and does not claim to. What it establishes is "
            "narrower and is",
            "usually the question anyway: whether the record somebody would be "
            "handed after",
            "an incident answers these, or whether the answer has to come from "
            "somebody's",
            "memory.",
            "",
            "Reproduce: python3 testimony_convert.py %s --report" % name]
    return chr(10).join(out)


# ── OpenTelemetry, because that is where the records already are ─────────────
#
# The argument for a SIEM-first pipeline is right about the plumbing: an
# enterprise forwards audit records to one place, over an open spec, and an
# agent that invents its own trail will not be used. So this reads that pipe
# rather than asking anybody to leave it.
#
# What it finds there is the point. As of 8 September 2026 the GenAI semantic
# conventions carry sixty one `gen_ai.*` attributes and none of them names who
# authorised an action: no approver, no authorisation, no human oversight. The
# only appearance of approval in the reference agent scenario is a decorator
# switching it off. So a span export can be complete, correctly parsed and
# properly integrated, and still be unable to say who approved, which is a
# fact about the conventions rather than about anybody's implementation.
#
# Reading OTLP is therefore not a concession. It is how the question gets
# asked of the records an enterprise actually has.

def _attrs(items) -> dict:
    """OTLP attribute list to a flat dict. Values are a one-key union."""
    out = {}
    for a in items or []:
        if not isinstance(a, dict):
            continue
        v = a.get("value")
        if isinstance(v, dict):
            for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
                if k in v:
                    out[str(a.get("key"))] = v[k]
                    break
            else:
                if "arrayValue" in v:
                    out[str(a.get("key"))] = json.dumps(v["arrayValue"])
        elif v is not None:
            out[str(a.get("key"))] = v
    return out


def is_otlp(doc) -> bool:
    return isinstance(doc, dict) and isinstance(doc.get("resourceSpans"), list)


def otlp_rows(doc: dict) -> list:
    """Every span in an OTLP/JSON export, as one flat row each.

    Resource and scope attributes travel with the span rather than being
    dropped, because `service.name` and the instrumentation that produced a
    span are part of what a reader needs and they do not live on the span.
    """
    rows = []
    for rs in doc.get("resourceSpans") or []:
        res = _attrs((rs.get("resource") or {}).get("attributes"))
        for ss in rs.get("scopeSpans") or []:
            scope = (ss.get("scope") or {}).get("name")
            for sp in ss.get("spans") or []:
                row = {k: v for k, v in sp.items()
                       if k != "attributes" and not isinstance(v, (list, dict))}
                row.update(res)
                if scope:
                    row["otel.scope.name"] = scope
                row.update(_attrs(sp.get("attributes")))
                for ev in sp.get("events") or []:
                    row.update(_attrs(ev.get("attributes")))
                rows.append(row)
    return rows


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: testimony_convert.py RECORDS.jsonl [entry_type ...]"
            + chr(10)
            + "       testimony_convert.py RECORDS.jsonl --report" + chr(10)
            + "       testimony_convert.py RECORDS.jsonl --against eu-ai-act"
            + chr(10)
            + chr(10)
            + "prints a Mapping suggested from your own field names, or asks "
            + "the four" + chr(10)
            + "questions of the rows and reports which of them the rows can "
            + "answer")
    text = io.open(sys.argv[1], encoding="utf-8").read()
    rows = []
    try:
        whole = json.loads(text)
    except ValueError:
        whole = None
    if is_otlp(whole):
        rows = otlp_rows(whole)
        print("# read %d spans from an OpenTelemetry export" % len(rows))
    elif isinstance(whole, list):
        rows = [r for r in whole if isinstance(r, dict)]
    elif isinstance(whole, dict):
        rows = [whole]
    else:
        for line in text.split(chr(10)):
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line)
            except ValueError:
                continue
            rows.extend(v if isinstance(v, list) else [v])
    if not rows:
        raise SystemExit("no JSON objects in %s" % sys.argv[1])
    args = sys.argv[2:]
    if "--against" in args:
        # The instrument library is not in this repository. This file is
        # free and stays free; the readings of particular frameworks are the
        # part that is sold, and a copied converter must not break because
        # they are absent.
        try:
            from criteria import against
        except ImportError:
            raise SystemExit(
                "--against needs the instrument library, which is not part of "
                "this repository." + chr(10)
                + "What is here reads your records and reports what they can "
                "and cannot answer:" + chr(10)
                + "  python3 spec/testimony_convert.py %s --report"
                % sys.argv[1])
        i = args.index("--against")
        which = args[i + 1] if i + 1 < len(args) else "eu-ai-act"
        try:
            print(against(rows, which, sys.argv[1]))
        except ValueError as e:
            raise SystemExit(str(e))
        return 0
    if "--report" in args:
        print(report(rows, sys.argv[1]))
        return 0
    wanted = [a for a in args if not a.startswith("-")] or [
        "decision", "approval", "evidence"]
    print("# read %d rows from %s" % (len(rows), sys.argv[1]))
    for t in wanted:
        print()
        print(propose(rows, t))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

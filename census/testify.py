"""An assessment, expressed as a Testimony Record of itself.

    python3 census/testify.py langgraph > assessment.jsonl
    python3 census/testify.py langgraph --anchor token.tsr > assessment.jsonl
    python3 census/testify.py --all --out-dir records/

The census asks ten systems whether they can say what they concluded, on what
evidence, and who concluded it. Until now it could not say those things about
its own conclusions. An assessor ran the rubric, formed twenty verdicts, and
handed over prose: nothing bound that document to the commit it was read at, the
rubric version it was scored against, or the person who scored it, and nothing
stopped it being edited afterwards.

That is the failure this project measures in everybody else, committed at the
point where it matters most, because an assessment is the thing somebody else
relies on.

So an assessment emits a record on the same terms it demands. Each verdict
becomes a belief. Each citation becomes evidence the belief names. The subject's
commit and the rubric's digest are in the record rather than in a covering
email, and the whole thing is digested so that an edited copy stops matching.
Anchor it with a Time Stamp Authority and a reader can check the assessment
without trusting the assessor, which is the only property that makes an
assessment worth anything to a third party.

WHAT DOES NOT MAP, stated here rather than smoothed over. The rubric has five
verdicts and the format has four belief states, and they are not the same
shape. `present` and `absent` are a belief held true and held false.
`undetermined` is `unknown`, which is exactly what it means. `not_applicable`
is not a belief about the system at all and is emitted as no belief, with the
requirement listed in the scope entry's `x-census-not-applicable` instead.

`partial` has no honest home. It is not `believed_true`, because the
requirement is not met; it is not `believed_false`, because part of it is; and
it is not `unknown`, because the assessor knows precisely what they found. It
is emitted as `unknown` with the verdict preserved verbatim in
`x-census-verdict`, and this paragraph exists so that a reader who sees
`unknown` is not misled into thinking nothing was established.

That is a finding about the format rather than a defect in the census, and it
is written down here instead of being resolved by picking whichever state
flattered the result.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SUBJECTS = os.path.join(HERE, "subjects")
sys.path.insert(0, os.path.join(ROOT, "spec"))
sys.path.insert(0, HERE)

import testimony_validate as tv          # noqa: E402
import rubric                            # noqa: E402

SPEC = "testimony-record/0.2"

# A verdict is a finding about the subject. A belief state is what the holder of
# the belief thinks is the case. They line up for three of the five and not for
# the other two, which the module docstring says out loud.
STATE = {
    "present": "believed_true",
    "absent": "believed_false",
    "undetermined": "unknown",
    "partial": "unknown",
}

# The census records HOW something was found. `source` is a citation into the
# tree at a pinned commit; `searched` is a command that returned nothing, which
# is the only honest way to evidence an absence. The format's kinds are coarser,
# so the census kind travels alongside rather than being thrown away.
KIND = {"source": "document", "searched": "derived"}


def _at(day: str, n: int) -> str:
    """A write time inside the assessment day.

    The rubric records the date an assessment was made and not the minute, so a
    minute is not invented here. Entries are ordered within that day because the
    format requires non-decreasing write times, and the ordering is the order
    they were written rather than a claim about clocks.
    """
    return "%sT00:%02d:%02dZ" % (day, n // 60, n % 60)


def record(subject: dict, token: bytes | None = None) -> list:
    """Every entry of the record, in the order it is written."""
    sid = subject["subject"]
    commit = subject.get("commit", "")
    who = subject.get("assessed_by") or "unassigned"
    day = subject.get("assessed_on") or "1970-01-01"
    at = subject["name"] + (" at " + commit[:12] if commit else "")

    reqs = {r.id: r for r in rubric.REQUIREMENTS}
    na = sorted(rid for rid, a in subject["assessments"].items()
                if a.get("verdict") == "not_applicable")

    entries = [{
        "spec": SPEC, "type": "scope", "id": "sc", "at": _at(day, 0),
        # An assessment reads and concludes. It gates nothing and executes
        # nothing, so a record of one that claimed otherwise would be marked
        # down for decisions it should never have carried.
        "acts": False,
        "x-census-subject": sid,
        "x-census-commit": commit,
        "x-census-rubric": rubric_digest(),
        "x-census-not-applicable": na,
    }]

    n = 1
    for rid in sorted(subject["assessments"], key=_order):
        a = subject["assessments"][rid]
        verdict = a.get("verdict")
        if verdict == "not_applicable":
            continue          # not a belief about this system, see the docstring
        req = reqs.get(rid)
        eids = []
        for item in a.get("evidence") or []:
            eid = "e_%s_%d" % (rid.replace(".", "_"), len(eids) + 1)
            entries.append({
                "spec": SPEC, "type": "evidence", "id": eid, "at": _at(day, n),
                "kind": KIND.get(item.get("kind"), "derived"),
                "source": item.get("locator", ""),
                "note": item.get("note", ""),
                # Kept because the distinction is load-bearing and the format's
                # kinds cannot carry it: an absence evidenced by a search that
                # returned nothing is a different claim from a citation, and
                # the census refuses an `absent` verdict that has no `searched`.
                "x-census-kind": item.get("kind"),
            })
            eids.append(eid)
            n += 1

        entries.append({
            "spec": SPEC, "type": "belief", "id": "b_" + rid.replace(".", "_"),
            "at": _at(day, n),
            # The tree, not the project. A verdict is about a named commit and
            # a later fix does not make it false, which is the rule the census
            # rests on; a subject naming only "langgraph" would quietly claim
            # something about the software in general.
            "subject": "system:%s@%s" % (sid, commit[:12]) if commit
                       else "system:" + sid,
            # `present_means` rather than `question`. The rubric states the bar
            # as a proposition, and a belief affirming an interrogative reads as
            # nonsense: "affirm, believed false" about "Does an approval
            # identify a person?" says the opposite of what was found.
            "proposition": (req.present_means if req else rid),
            "polarity": "affirm",
            "state": STATE.get(verdict, "unknown"),
            "asserted_by": who,
            "evidence": eids,
            "x-census-requirement": rid,
            "x-census-verdict": verdict,
            "x-census-question": req.question if req else "",
        })
        n += 1

    body = list(entries)
    integrity = {
        "spec": SPEC, "type": "integrity", "id": "i1", "at": _at(day, n),
        "scheme": "hash-chain",
        "digest": "sha256:" + tv.digest_of(body),
        "covers": [x["id"] for x in body],
        "x-census-assessed": at,
    }
    if token is not None:
        integrity["scheme"] = "external-anchor"
        integrity["anchor"] = {
            "kind": "rfc3161",
            "authority": "a Time Stamp Authority, named in the token",
            "token": base64.b64encode(token).decode("ascii"),
        }
    entries.append(integrity)
    return entries


def _order(rid: str):
    """R3.10 sorts after R3.2, which a string sort does not do."""
    part, num = rid.split(".", 1) if "." in rid else (rid, "0")
    return (part, int(num) if num.isdigit() else 0)


def rubric_digest() -> str:
    """The questions this assessment was scored against.

    A verdict is only meaningful against the bar it was scored on, so a record
    that names the subject's commit and not the rubric's version has pinned one
    side of the comparison. This digests the rubric source, which is where the
    twenty questions and the bar for each of them live.
    """
    with io.open(os.path.join(HERE, "rubric.py"), "rb") as f:
        return "sha256:" + hashlib.sha256(f.read()).hexdigest()


def render(entries: list) -> str:
    return "\n".join(json.dumps(e, sort_keys=True) for e in entries) + "\n"


def load(subject_id: str) -> dict:
    path = os.path.join(SUBJECTS, subject_id + ".json")
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("subject", nargs="?", help="a subject id, or use --all")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--anchor", default=None,
                    help="a TimeStampResp over this record's digest, which "
                         "means anchoring after a first run: emit, stamp the "
                         "digest, then emit again with the token")
    args = ap.parse_args()

    token = None
    if args.anchor:
        with io.open(args.anchor, "rb") as f:
            token = f.read()

    ids = ([os.path.basename(p)[:-5]
            for p in sorted(glob.glob(os.path.join(SUBJECTS, "*.json")))]
           if args.all else [args.subject])
    if not ids or ids == [None]:
        ap.error("name a subject, or pass --all")

    for sid in ids:
        text = render(record(load(sid), token))
        if args.out_dir:
            os.makedirs(args.out_dir, exist_ok=True)
            out = os.path.join(args.out_dir, sid + ".jsonl")
            with io.open(out, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            r = tv.validate(text)
            print("%-18s %-6s %s" % (sid, r.level, out))
        else:
            sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

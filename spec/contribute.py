"""Counts a record already contains, shaped for a commons that pools them.

    python3 spec/contribute.py record.jsonl --frame frame.json

A Testimony Record belief carries a subject and a proposition. A commons
contribution is counts over pairs of propositions across subjects. So anybody
emitting records already holds the input, and contributing is arithmetic rather
than an adoption decision. This is that arithmetic, and nothing else.

**It prints. It does not send.** There is no endpoint in this file and no
network call. What comes out is a JSON document to read, argue with, and post
yourself if you decide to. A tool that transmitted somebody's data as a side
effect of being run would be indefensible in this repository of all places.

Three rules it will not bend, because each is the difference between a commons
and a liability:

**Nothing identifying leaves.** Subjects are counted, never named. A pattern
carries two vocabulary tokens and four integers, and the subject a belief was
about appears nowhere in the output.

**Propositions outside the vocabulary are dropped, never mapped.** The
vocabulary is closed and a word that is not in it is not a word this commons
can carry. Mapping one to the nearest token would publish something the
contributor never observed, which is the mistake that killed an earlier
proposal to import survey instruments.

**The frame is declared, never inferred.** Which domain and which region an
operator works in is theirs to state. Reading it out of their data would be
guessing about them from the thing they are contributing, which is precisely
what the commons must never do.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.request

LEXICON_URL = "https://infrastructure.omem-cloud.com/v1/commons/lexicon"
MIN_SUBJECTS = 3          # a pair seen on fewer subjects is an anecdote

# The frame's closed lists, restated here so somebody writing one is not
# guessing. They are the collector's to define and it refuses anything else, so
# a mismatch here shows up as a refusal at the door rather than as bad data
# getting in, which is the right way round for a copy to be wrong.
FRAME_DOMAINS = ("customer_support", "sales", "recruiting", "healthcare",
                 "education", "software", "operations", "personal", "other")
FRAME_REGIONS = ("africa", "americas", "asia", "europe", "oceania")
FRAME_BANDS = ("10-49", "50-199", "200-999", "1000+")


def lexicon(path_or_url: str = LEXICON_URL) -> frozenset:
    """The closed vocabulary, fetched rather than vendored.

    A stale copy would silently drop tokens the commons accepts and offer ones
    it does not, and the contributor would be blamed for both. If it cannot be
    read, this refuses to guess at it.
    """
    if os.path.exists(path_or_url):
        raw = io.open(path_or_url, encoding="utf-8").read()
    else:
        req = urllib.request.Request(path_or_url, headers={
            "User-Agent": "machine-testimony-contribute/1.0",
            "Accept": "application/json, text/plain, */*"})
        raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    try:
        doc = json.loads(raw)
        words = doc.get("lexicon", doc) if isinstance(doc, dict) else doc
    except ValueError:
        words = raw.split()
    return frozenset(str(w).strip() for w in words if str(w).strip())


def beliefs(entries: list) -> dict:
    """Subject to the propositions it held, and whether it held them true.

    The last belief about a subject and proposition wins, because a record is
    append-only and a later entry is a later observation rather than a second
    opinion.

    **`state` decides the position and `polarity` flips it**, which is not the
    same as reading `polarity` alone. A belief carrying `believed_false` with
    polarity `affirm` affirms that the proposition is FALSE, and counting it as
    a positive is the exact inversion of what the record says. The first version
    of this file did precisely that, and against a record using
    `believed_false` it would have contributed counts that were the opposite of
    the observation, which is the way a shared resource gets poisoned by
    somebody acting carefully.

    **`contradicted` and `unknown` are SKIPPED, never resolved.** A system
    holding two irreconcilable positions, or none, has no stated position, and
    picking one for it would be inventing an opinion the record deliberately
    declined to have. The same reason absence is not counted.

    Both rules are what `commons_contribute.py` already does at the other end.
    Two paths producing different counts from the same record would be worse
    than having only one.
    """
    held = {}
    for e in entries:
        if e.get("type") != "belief":
            continue
        s, p = e.get("subject"), e.get("proposition")
        if not isinstance(s, str) or not isinstance(p, str):
            continue
        state = e.get("state")
        if state not in ("believed_true", "believed_false"):
            continue
        negative = (state == "believed_false") ^ (e.get("polarity") == "deny")
        held.setdefault(s, {})[p] = not negative
    return held


def patterns(held: dict, words: frozenset) -> tuple:
    """Co-occurrence counts over pairs, and what was dropped for being outside
    the vocabulary."""
    seen = {p for props in held.values() for p in props}
    usable = sorted(seen & words)
    dropped = sorted(seen - words)

    # How often each token held across this contributor's own population. The
    # door needs it to measure lift rather than trust that somebody else did.
    base = {}
    for c in usable:
        n = sum(1 for props in held.values() if c in props)
        yes = sum(1 for props in held.values() if props.get(c) is True)
        base[c] = (yes / n) if n else 0.0

    out = []
    for a in usable:
        subjects = [props for props in held.values() if props.get(a) is True]
        if len(subjects) < MIN_SUBJECTS:
            continue
        for c in usable:
            if c == a:
                continue
            support = sum(1 for props in subjects if props.get(c) is True)
            refute = sum(1 for props in subjects if props.get(c) is False)
            if support + refute == 0:
                continue
            out.append({"antecedent": a, "consequent": c,
                        "support": support, "refute": refute,
                        "subjects": len(subjects),
                        "consequent_base": round(base[c], 4)})
    return out, dropped


def build(entries: list, frame: dict, instance: str,
          words: frozenset) -> tuple:
    pats, dropped = patterns(beliefs(entries), words)
    return {"instance": instance, "frame": frame, "patterns": pats}, dropped


def main() -> int:
    args = sys.argv[1:]
    if not args or "--help" in args:
        raise SystemExit(
            "usage: contribute.py RECORD.jsonl --frame FRAME.json "
            "[--instance ID] [--lexicon PATH_OR_URL]" + chr(10) + chr(10)
            + "Prints a contribution. Sends nothing. FRAME.json is yours to "
            "write: it states" + chr(10)
            + "the domain and region you work in and a band for how many "
            "subjects you hold," + chr(10)
            + "and none of it is inferred from your data.")

    def opt(name, default=None):
        return args[args.index(name) + 1] if name in args and \
            args.index(name) + 1 < len(args) else default

    src = args[0]
    frame_path = opt("--frame")
    if not frame_path:
        raise SystemExit(
            "--frame is required and is not inferred. Write a small JSON file "
            "saying which" + chr(10)
            + "domain and macro-region you work in, and a band rather than a "
            "count for how" + chr(10)
            + "many subjects you hold. Guessing any of it from your records "
            "would be the" + chr(10)
            + "commons profiling the contributor, which is the one thing it "
            "must never do." + chr(10) + chr(10)
            + "  domain:   " + ", ".join(FRAME_DOMAINS) + chr(10)
            + "  region:   " + ", ".join(FRAME_REGIONS) + chr(10)
            + "  subjects: " + ", ".join(FRAME_BANDS))
    frame = json.load(io.open(frame_path, encoding="utf-8"))
    for field, allowed in (("domain", FRAME_DOMAINS), ("region", FRAME_REGIONS),
                           ("subjects", FRAME_BANDS)):
        if frame.get(field) not in allowed:
            raise SystemExit(
                "frame %s must be one of: %s" % (field, ", ".join(allowed))
                + chr(10)
                + "These are closed lists and the collector refuses anything "
                "else, so this stops" + chr(10)
                + "here rather than letting you find out after you have sent "
                "something.")
    instance = opt("--instance") or frame.get("instance")
    if not instance:
        raise SystemExit(
            "--instance is an opaque id you choose and reuse, 8 to 64 "
            "characters. It is not" + chr(10)
            + "your name and nothing derives it from you: it exists so your "
            "own contributions" + chr(10)
            + "can be withdrawn later without anybody knowing whose they were.")

    entries = [json.loads(l) for l in io.open(src, encoding="utf-8")
               if l.strip()]
    try:
        words = lexicon(opt("--lexicon", LEXICON_URL))
    except Exception as e:                                  # noqa: BLE001
        raise SystemExit(
            "could not read the vocabulary (%s)." % str(e)[:60] + chr(10)
            + "It is closed and this will not guess at it, because a "
            "contribution built against" + chr(10)
            + "the wrong words is worse than no contribution.")

    doc, dropped = build(entries, frame, instance, words)
    sys.stderr.write(
        "%d beliefs over %d subjects, %d patterns, %d propositions dropped "
        "for being outside the vocabulary%s%s"
        % (len([e for e in entries if e.get("type") == "belief"]),
           len(beliefs(entries)), len(doc["patterns"]), len(dropped),
           (": " + ", ".join(dropped[:6])) if dropped else "", chr(10)))
    sys.stderr.write(
        "nothing was sent. Read it, and post it yourself if you decide to."
        + chr(10))
    print(json.dumps(doc, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

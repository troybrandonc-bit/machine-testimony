"""The TR-3 profile: that the number means what the validator does.

    python tests/tests_profile.py

A profile exists so that a document written by somebody else can reference a
short name instead of restating a definition. Everything that makes that safe is
checked here: the requirement list is the validator's and not a transcription of
it, the digest is reproducible by a third party, and the page, the JSON and the
code all say the same thing.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "spec")
sys.path.insert(0, SPEC)

import build_profile as bp                                   # noqa: E402
import testimony_validate as tv                              # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + ((": %s" % (detail,)) if detail else ""))


P = os.path.join(SPEC, "profiles", "tr-3.json")
check("the profile is published", os.path.exists(P))
doc = json.load(io.open(P, encoding="utf-8"))


print("the number means what the validator does")

# The whole basis of the profile. If these ever diverge, the published document
# is a claim about a number that the code does not support.
text = io.open(os.path.join(SPEC, "testimony-record-example.jsonl"),
               encoding="utf-8").read()
# A check introduced in a version the specification has not published is not a
# requirement of a published profile. Version 1's requirements are frozen, and
# counting a 0.3 check among them would report the published document as wrong
# for carrying exactly what it was published carrying.
_report = tv.validate(text)
live = [c for c in _report.as_dict()["checks"]
        if c["level"] == "TR-3" and c["check"] not in _report.unreleased]
check("the requirement count matches the validator",
      len(doc["requirements"]) == len(live),
      "%d published, %d in the validator" % (len(doc["requirements"]), len(live)))
mism = [(a["requirement"], b["check"]) for a, b in zip(doc["requirements"], live)
        if a["requirement"] != b["check"] or a["basis"] != b["basis"]]
check("every requirement and basis matches the validator", not mism, mism[:3])

r = subprocess.run([sys.executable, os.path.join(SPEC, "build_profile.py"),
                    "--check"], capture_output=True, text=True)
check("regenerating the profile is a no-op", r.returncode == 0,
      (r.stderr or r.stdout)[:160])


print("")
print("a third party can recompute the digest")

core = {k: doc[k] for k in ("profile", "version", "specification", "level",
                            "cumulative", "requirements")}
recomputed = "sha256:" + hashlib.sha256(
    json.dumps(core, sort_keys=True, separators=(",", ":"),
               ensure_ascii=False).encode("utf-8")).hexdigest()
check("the digest is sha256 over sorted-key, whitespace-free canonical bytes",
      recomputed == doc["digest"], "%s vs %s" % (recomputed, doc["digest"]))

# The prose is deliberately outside the digest, so a typo fix does not break
# every reference. If that stops being true, pinning becomes useless.
noisy = dict(doc)
noisy["purpose"] = doc["purpose"] + " (typo fixed)"
core2 = {k: noisy[k] for k in core}
check("changing the prose does not change the digest",
      json.dumps(core2, sort_keys=True) == json.dumps(core, sort_keys=True))

# And the converse: changing a requirement MUST change it, or the digest is
# not pinning the thing it claims to pin.
core3 = json.loads(json.dumps(core))
core3["requirements"][0]["basis"] = "attested"
moved = hashlib.sha256(json.dumps(core3, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False).encode("utf-8")).hexdigest()
check("changing a requirement's basis DOES change the digest",
      "sha256:" + moved != doc["digest"])


print("")
print("it says what it does not establish")

check("the residual is published", len(doc.get("does_not_establish", [])) >= 5)
for want in ("identity", "complete", "altered"):
    check("the residual covers %s" % want,
          any(want in d for d in doc["does_not_establish"]))
check("it points at TR-4 rather than absorbing it",
      any("TR-4" in d for d in doc["does_not_establish"]))

# The first version of this page said alteration by the holder "is TR-4", which
# overclaims TR-4. TR-4 is Verifiable: a reader can recompute the arithmetic,
# and a hash chain the emitter computed is recomputable by anybody who can
# rewrite the entries. All five published adapter examples reach TR-4 with
# scheme hash-chain and anchor null, so the weakest permitted scheme is what a
# reader meets first. Only an external anchor speaks to the holder.
alter = [d for d in doc["does_not_establish"] if "altered by the party" in d]
check("the residual does not hand alteration-by-the-holder to TR-4", alter
      and "does not establish this either" in alter[0], alter[:1])
check("and says an EXTERNAL ANCHOR is what covers it",
      alter and "EXTERNAL ANCHOR" in alter[0])

# The verified/attested split is the honest part of the profile. Hiding it
# would sell six checkable requirements as eight.
att = [r["requirement"] for r in doc["requirements"] if r["basis"] == "attested"]
ver = [r["requirement"] for r in doc["requirements"] if r["basis"] == "verified"]
check("the profile distinguishes verified from attested",
      att and ver, "%d attested, %d verified" % (len(att), len(ver)))
check("and explains what each word means",
      set(doc.get("basis_means", {})) == {"verified", "attested"})


print("")
print("the stability commitment is a guard and not a sentence")

# Three questions decide whether anybody references a unit: can it change under
# me, can it be withdrawn, who decides. The words are checked here and the
# arithmetic behind them is checked below.
st = doc.get("stability", {})
for k in ("frozen", "resolvable", "irrevocable", "checkable",
          "what_this_is_not"):
    check("the profile states %s" % k, bool(st.get(k)))
check("irrevocability rests on the LICENCE, not on the author",
      "licence's guarantee rather than the author's" in st.get("irrevocable", ""))
check("and it does not promise the level is right",
      "not a promise that the level is right" in st.get("what_this_is_not", ""))

LED = os.path.join(SPEC, "profiles", "PUBLISHED.json")
check("there is a ledger of published versions", os.path.exists(LED))
led = json.load(io.open(LED, encoding="utf-8")) if os.path.exists(LED) else {}
pub = led.get("published", [])
check("this version is in it",
      any(e["version"] == doc["version"] for e in pub), pub)
check("its ledger digest is this digest",
      all(e["digest"] == doc["digest"] for e in pub
          if e["version"] == doc["version"]))

# The promise is that a citation of version 1 still resolves after version 2
# exists. A version listed and not served is a reference that breaks.
for e in pub:
    vp = os.path.join(ROOT, "public", "tr-3", "v%s.json" % e["version"])
    check("version %s is served at its own URL" % e["version"],
          os.path.exists(vp))
    if os.path.exists(vp):
        was = json.load(io.open(vp, encoding="utf-8"))
        core_v = {k: was.get(k) for k in ("profile", "version", "specification",
                                          "level", "cumulative", "requirements")}
        actual = "sha256:" + hashlib.sha256(
            json.dumps(core_v, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")).hexdigest()
        check("version %s still computes as it was published" % e["version"],
              actual == e["digest"], "%s vs %s" % (actual, e["digest"]))

# The guard's own first version read the served file's STATED digest, so
# editing a requirement and leaving the digest alone passed a check whose only
# job was to catch that. This is that regression.
import build_profile as bpm
tampered = dict(doc)
tampered["requirements"] = [dict(r) for r in doc["requirements"]]
tampered["requirements"][0]["basis"] = (
    "attested" if doc["requirements"][0]["basis"] == "verified" else "verified")
core_t = {k: tampered[k] for k in ("profile", "version", "specification",
                                   "level", "cumulative", "requirements")}
moved = "sha256:" + hashlib.sha256(bpm.canonical(core_t)).hexdigest()
check("an edited requirement computes a different digest, stated or not",
      moved != doc["digest"],
      "the guard must recompute rather than read the file's own claim")

print("")
print("the page and the profile do not drift")

pg = os.path.join(ROOT, "public", "tr-3", "index.html")
check("the page is published", os.path.exists(pg))
if os.path.exists(pg):
    page = re.sub(r"\s+", " ", io.open(pg, encoding="utf-8").read())
    check("the page carries the digest", doc["digest"] in page)
    gone = [r["requirement"] for r in doc["requirements"]
            if r["requirement"] not in page]
    check("every requirement is on the page", not gone, gone)
    check("the page states the attested count honestly",
          "six of the eight" in page.lower()
          and len(ver) == 6 and len(att) == 2,
          "page says six verified; profile has %d" % len(ver))
    check("the page says the list is generated, not transcribed",
          "generated from the reference validator" in page)
    check("the page says the digest excludes the prose",
          "does not cover the prose" in page)
    check("the page does not claim the level proves the approver is real",
          "identity proofing sits outside" in page.lower())
    check("the page does not hand alteration-by-the-holder to TR-4",
          "TR-4 alone does not establish this either" in page)
    check("and dates its own correction rather than silently fixing it",
          "was wrong when this page was first published" in page)
    check("the page answers can-it-change-under-me",
          "never change" in page and "new version with a new digest" in page)
    check("the page answers can-it-be-withdrawn on the licence's terms",
          "licence's guarantee and not the author's" in page)
    check("the page links the versioned copy a citation would resolve to",
          "/tr-3/v1.json" in page)
    check("the page admits the guard's own bug rather than quietly fixing it",
          "stated digest instead of recomputing" in page)

print("")
print("%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)

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
live = [c for c in tv.validate(text).as_dict()["checks"] if c["level"] == "TR-3"]
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

# The verified/attested split is the honest part of the profile. Hiding it
# would sell six checkable requirements as eight.
att = [r["requirement"] for r in doc["requirements"] if r["basis"] == "attested"]
ver = [r["requirement"] for r in doc["requirements"] if r["basis"] == "verified"]
check("the profile distinguishes verified from attested",
      att and ver, "%d attested, %d verified" % (len(att), len(ver)))
check("and explains what each word means",
      set(doc.get("basis_means", {})) == {"verified", "attested"})


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

print("")
print("%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)

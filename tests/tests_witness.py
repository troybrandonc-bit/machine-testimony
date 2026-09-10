"""The reference witness, and the criteria it is a reference for.

    python tests/tests_witness.py

The thing being defended is that this witness REFUSES. A witness that signs is
easy and worthless; the whole value is in the cases where it declines, so those
are tested first and hardest, and the proofs it is tested against are generated
rather than written out by hand, because a verifier checked only against
fixtures its own author produced is checked against its own misreading.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import witness as w                                          # noqa: E402
import witness_criteria as wc                                # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + ((": %s" % (detail,)) if detail else ""))


def ents(n):
    return ["e%d" % i for i in range(n)]


print("the tree is RFC 6962's and not one of our own")

# The empty-tree hash is the one value every implementation agrees on, so it is
# the cheapest possible check that the hashing is the standard's.
check("the empty tree is SHA-256 of nothing",
      w.root_from([]).hex() ==
      "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

check("a one-leaf tree is the leaf hash, not the entry hash",
      w.root_from(["a"]) == w._leaf(b"a"))

# RFC 6962 splits at the largest power of two STRICTLY below n. Pairing left to
# right instead builds a tree that verifies against itself and nothing else.
check("the split is the largest power of two strictly below n",
      (w._split(2), w._split(3), w._split(4), w._split(5), w._split(9))
      == (1, 2, 2, 4, 8))

check("a three-leaf tree splits 2/1 rather than 1/2",
      w.root_from(["a", "b", "c"]) ==
      w._node(w._node(w._leaf(b"a"), w._leaf(b"b")), w._leaf(b"c")))


print("")
print("every consistency proof round-trips")

ok = bad = []
ok, bad = 0, []
for n in range(1, 17):
    e = ents(n)
    new = w.root_from(e)
    for m in range(1, n + 1):
        old = w.root_from(e[:m])
        if w.verify_consistency(old, m, new, n,
                                w.consistency_proof(e, m)):
            ok += 1
        else:
            bad.append((m, n))
check("all 136 (old, new) pairs up to 16 leaves verify", not bad, bad[:6])
check("and that is 136 of them, not a handful", ok == 136, ok)


print("")
print("and every way of lying about one fails")

e = ents(9)
old, new = w.root_from(e[:5]), w.root_from(e)
proof = w.consistency_proof(e, 5)
forked = w.root_from(e[:5] + ["TAMPERED"] + e[6:9])

check("the honest proof verifies, so the negatives mean something",
      w.verify_consistency(old, 5, new, 9, proof))

# The case the whole mechanism exists for: entry 5 was changed after the
# witness signed at size 5.
check("a forked tree is rejected",
      not w.verify_consistency(old, 5, forked, 9, proof))
check("no proof at all is rejected",
      not w.verify_consistency(old, 5, new, 9, []),
      "missing is not a lesser failure than wrong")
check("a proof of a different tree is rejected",
      not w.verify_consistency(old, 5, new, 9,
                               w.consistency_proof(
                                   e[:5] + ["TAMPERED"] + e[6:9], 5)))
mangled = list(proof)
mangled[0] = bytes(32)
check("a mangled proof node is rejected",
      not w.verify_consistency(old, 5, new, 9, mangled))
check("a tree that shrank is rejected",
      not w.verify_consistency(old, 5, new, 3, proof))
check("an unchanged size with an unchanged root is accepted",
      w.verify_consistency(old, 5, old, 5, []))
check("an unchanged size with a DIFFERENT root is rejected",
      not w.verify_consistency(old, 5, new, 5, []),
      "this is equivocation at a fixed size and it must not pass")


print("")
print("the witness refuses rather than signs")

tmp = tempfile.mkdtemp()
state = os.path.join(tmp, "w.json")


def head(n, root=None):
    return {"log": "L", "tree_size": n,
            "root": (root or w.root_from(ents(n))).hex()}


first = w.cosign(head(5), state)
check("a first head is signed, because there is nothing to be consistent with",
      first["cosignature"]["tree_size"] == 5)

grew = w.cosign(head(9), state, w.consistency_proof(ents(9), 5))
check("a consistent extension is signed", grew["cosignature"]["tree_size"] == 9)


def refused(fn):
    try:
        fn()
        return None
    except w.Refused as ex:
        return str(ex)


# W3, the load-bearing criterion. Each of these is a way a witness stops being
# a witness while still producing a valid signature.
check("it refuses a head with no consistency proof",
      refused(lambda: w.cosign(head(12), state)))
check("it refuses a forked history",
      refused(lambda: w.cosign(
          head(12, w.root_from(ents(9)[:5] + ["X"] + ents(12)[6:])), state,
          w.consistency_proof(ents(12), 9))))
check("it refuses a tree that went backwards",
      refused(lambda: w.cosign(head(4), state,
                               w.consistency_proof(ents(9), 4))))
check("it refuses a root that is not a SHA-256 digest",
      refused(lambda: w.cosign({"log": "L", "tree_size": 20, "root": "beef"},
                               state)))
check("it refuses a head missing a field",
      refused(lambda: w.cosign({"log": "L", "tree_size": 20}, state)))

msg = refused(lambda: w.cosign(head(12), state)) or ""
check("the refusal says why, in words a reader can act on",
      "rubber stamp" in msg, msg[:90])

# A refusal must not advance the stored head. If it did, a witness could be
# walked forward by a stream of rejected heads and would then accept a proof
# from a head it never signed.
saved = json.load(io.open(state, encoding="utf-8"))
check("a refusal leaves the remembered head untouched",
      saved["L"]["tree_size"] == 9, saved)


print("")
print("it says what it does and does not attest, with the signature")

body = grew["cosignature"]
check("the cosignature carries what it attests", body.get("attests"))
check("and what it does not", len(body.get("does_not_attest", [])) >= 4)
check("including that one witness cannot detect equivocation",
      any("equivocation" in d for d in body["does_not_attest"]),
      "W4 is the criterion a single witness structurally cannot meet")
check("it does not claim the entries are true",
      any("entries are true" in d for d in body["does_not_attest"]))

# W6, failed on purpose. If this ever passes silently, the criteria have been
# quietly discredited by their own reference implementation.
check("it declares that it makes NO durability commitment",
      "no_durability_commitment" in grew
      and "W6" in grew["no_durability_commitment"])
check("it declares itself a reference implementation",
      grew.get("witness_is_a_reference_implementation") is True)

# The HMAC fallback is symmetric: anybody who can verify can forge. It exists
# so the refusal logic runs without cryptography installed, and it must never
# be mistaken for a witness.
# W7 in the artifact, not only in the criteria. A scope filed in a policy
# document the reader does not have is not a scope.
check("the cosignature carries its observation scope",
      body.get("observation_scope") in w.SCOPES)
check("and says in words what that scope means",
      body.get("observation_scope_means") == w.SCOPES[body["observation_scope"]])
check("this witness admits it watched nothing happen",
      body["observation_scope"] == "received"
      and "watched nothing" in body["observation_scope_means"],
      "it is handed a head over a network; claiming to observe an effect "
      "would be the overclaim W7 exists to catch")

check("a symmetric fallback names itself as not a witness",
      grew["alg"] == "ed25519" or "NOT A WITNESS" in grew["alg"],
      grew["alg"])


print("")
print("the criteria are stated so they can be argued with")

check("seven criteria", len(wc.CRITERIA) == 7, len(wc.CRITERIA))
check("ids are W1 to W7",
      [c.id for c in wc.CRITERIA] == ["W%d" % i for i in range(1, 8)])

# W7 arrived from outside, one day after the criteria were published, from two
# parties who did not cite each other. If the attribution is ever dropped, the
# criteria stop being a record of who found what.
w7 = [c for c in wc.CRITERIA if c.id == "W7"][0]
check("W7 credits both parties who raised it",
      "GitSerge-crypto" in w7.why and "HarperZ9" in w7.why)
check("W7 says W2 is not enough on its own", "W2 requires" in w7.why)
check("W7 names the same hole in this project's own format",
      "same hole" in w7.why and "machine-testimony#90" in w7.why)
check("every criterion says why it exists",
      all(len(c.why) > 120 for c in wc.CRITERIA),
      [c.id for c in wc.CRITERIA if len(c.why) <= 120])
check("every criterion says what present and partial mean",
      all(c.present_means and c.partial_means for c in wc.CRITERIA))
check("undetermined is available, so an unread witness is not scored",
      "undetermined" in wc.VERDICTS)
# The criteria are worth nothing if their author's own witness is exempt.
check("the criteria name the reference witness's own failure",
      any("reference witness" in c.why for c in wc.CRITERIA))

print("")
print("%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)

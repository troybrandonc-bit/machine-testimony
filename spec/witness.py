"""A reference witness: cosign a log checkpoint, or refuse to.

    python3 witness.py --state w.json --head '{"log":"x","tree_size":9,...}'

WHAT THIS IS FOR. `witness_criteria.py` says what a witness has to do before its
cosignature is worth anything. Criteria are cheap to write and easy to write
unimplementably, so this exists to show the six are met by something small, and
to be the thing anybody arguing with them can run.

IT IS A REFERENCE IMPLEMENTATION AND NOT A SERVICE. It fails W6 deliberately and
completely: there is no operator, no end-of-life commitment, no notice period
and no undertaking that anything stays verifiable. Nobody should anchor evidence
to a key produced by this file and expect it to mean something in 2032. A
witness that overstates its own durability is the failure W6 exists to name, and
publishing one that quietly did so while the criteria said otherwise would
discredit the criteria rather than the witness.

WHAT IT ACTUALLY DOES, WHICH IS ONE THING. It keeps the last tree head it signed
for a log, and when asked to sign a new one it requires a consistency proof from
the old head to the new. If the proof is missing, malformed, or does not verify,
it REFUSES. That is W3, it is the only interesting behaviour here, and it is the
behaviour a witness under commercial pressure quietly drops first, because
refusing looks like an outage and signing looks like uptime.

THE PROOF FORMAT IS RFC 9162's, because a witness that invents its own is a
witness whose output only its own client can check, and that is the thing this
project exists to refuse. Hashing follows RFC 6962 section 2.1: leaves are
SHA-256 over 0x00 || entry, interior nodes SHA-256 over 0x01 || left || right.

Signatures are Ed25519 when `cryptography` is installed and HMAC-SHA256 over the
same canonical bytes when it is not, so the refusal logic can be exercised
anywhere. The fallback is NOT a witness: it is symmetric, so anybody who can
verify a cosignature can forge one, and `signed()` labels it `alg: "hmac-sha256
(NOT A WITNESS)"` so that a reader who ignores this paragraph still cannot
mistake it. W5 is met only on the Ed25519 path.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import io
import json
import os
import sys

# What this witness says its signature means. W2: carried WITH the cosignature
# rather than left in documentation somebody has to find, because a cosignature
# is going to be produced in a dispute by the party it favours.
ATTESTS = ("this tree head, for this log, at this size, was observed by this "
           "witness at this time, and is consistent with the head this witness "
           "previously signed for the same log")

# W7, added 10 September 2026 after two parties raised it on the same day.
# A cosignature has to say WHICH of these it is, travelling with the signature
# rather than filed in a policy document the reader does not have. This witness
# is handed a tree head over a network; it does not watch anything happen. That
# is the weakest of the three and saying so is the criterion.
OBSERVATION_SCOPE = "received"
SCOPES = {
    "effect": "the witness observed the external effect itself",
    "response": "the witness observed a response from the invoked interface, "
                "which establishes the call completed and not that the effect "
                "occurred",
    "received": "the witness received the signing party's assertion and "
                "nothing more. It watched nothing happen.",
}
DOES_NOT_ATTEST = (
    "that the entries are true",
    "that the log is complete",
    "that any recorded action was executed",
    "that the log operator is honest",
    "that no other head was shown to somebody else. Detecting that "
    "equivocation requires comparing the views of several witnesses, and one "
    "witness structurally cannot do it (W4)",
)

STATEMENT = "machine-testimony/witness/0.1"


def _leaf(entry: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + entry).digest()


def _node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _split(n: int) -> int:
    """The largest power of two strictly less than n.

    RFC 6962 splits here, which is NOT the same as pairing left to right when
    n is not a power of two. Getting it wrong builds a tree that verifies
    against itself and against no other implementation, which is the quietest
    possible bug in this whole file.
    """
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def _mth(level: list) -> bytes:
    """RFC 6962 Merkle Tree Hash over a list of already-hashed leaves."""
    if not level:
        return hashlib.sha256(b"").digest()
    if len(level) == 1:
        return level[0]
    k = _split(len(level))
    return _node(_mth(level[:k]), _mth(level[k:]))


def leaves(entries: list) -> list:
    return [_leaf(e if isinstance(e, bytes) else str(e).encode())
            for e in entries]


def root_from(entries: list) -> bytes:
    """The RFC 6962 Merkle tree hash of a list of leaf entries."""
    return _mth(leaves(entries))


def consistency_proof(entries: list, old_size: int) -> list:
    """RFC 6962 PROOF(m, D[n]): that the tree of old_size is a prefix.

    Generation lives beside verification on purpose. A verifier tested only
    against proofs its own author hand-wrote is tested against its own
    misreading, so the suite builds real trees and round-trips every pair.
    """
    level = leaves(entries)
    if not 0 < old_size <= len(level):
        raise ValueError("old_size out of range")
    return _subproof(old_size, level, True)


def _subproof(m: int, level: list, b: bool) -> list:
    if m == len(level):
        return [] if b else [_mth(level)]
    k = _split(len(level))
    if m <= k:
        return _subproof(m, level[:k], b) + [_mth(level[k:])]
    return _subproof(m - k, level[k:], False) + [_mth(level[:k])]


def verify_consistency(old_root: bytes, old_size: int,
                       new_root: bytes, new_size: int, proof: list) -> bool:
    """RFC 9162 section 2.1.4.2, the append-only check.

    Returns True only when the proof shows the tree of `old_size` is a prefix
    of the tree of `new_size`. Every other outcome, including a malformed
    proof, is False. There is no third answer and no partial credit: this
    function's whole job is to be the thing that says no.
    """
    if old_size <= 0 or new_size < old_size:
        return False
    if old_size == new_size:
        return not proof and old_root == new_root
    if not proof:
        return False
    node, sn, tn = old_size - 1, old_size - 1, new_size - 1
    while sn % 2:
        sn //= 2
        tn //= 2
    fn = sn
    if fn == 0:
        # The old tree is a complete left subtree, so its root is the first
        # element implicitly rather than being carried in the proof.
        fr = sr = old_root
        path = list(proof)
    else:
        if not proof:
            return False
        fr = sr = proof[0]
        path = list(proof[1:])
    for step in path:
        if tn == 0:
            return False
        if sn % 2 or (sn and sn == tn):
            fr = _node(step, fr)
            sr = _node(step, sr)
            while sn and not sn % 2:
                sn //= 2
                tn //= 2
        else:
            fr = _node(fr, step)
        sn //= 2
        tn //= 2
    return tn == 0 and fr == new_root and sr == old_root


class Refused(Exception):
    """Why this witness declined to sign. Never silent, never a warning."""


def _key(state_path: str) -> tuple:
    """(signer, verifying key hex, algorithm label)."""
    seed_path = state_path + ".key"
    if os.path.exists(seed_path):
        seed = binascii.unhexlify(io.open(seed_path).read().strip())
    else:
        seed = os.urandom(32)
        io.open(seed_path, "w").write(binascii.hexlify(seed).decode())
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        sk = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        pub = sk.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        return (lambda m: sk.sign(m)), binascii.hexlify(pub).decode(), "ed25519"
    except Exception:
        return ((lambda m: hmac.new(seed, m, hashlib.sha256).digest()),
                binascii.hexlify(hashlib.sha256(seed).digest()).decode(),
                "hmac-sha256 (NOT A WITNESS)")


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def cosign(head: dict, state_path: str, proof: list = None,
           at: str = None) -> dict:
    """Sign this head, or raise Refused.

    `head` carries `log`, `tree_size` and `root` (hex). `proof` is the
    consistency proof from the last head this witness signed for that log.
    """
    for k in ("log", "tree_size", "root"):
        if k not in head:
            raise Refused("the head is missing %r" % k)
    try:
        new_root = binascii.unhexlify(head["root"])
    except Exception:
        raise Refused("root is not hex")
    if len(new_root) != 32:
        raise Refused("root is not a SHA-256 digest")
    size = head["tree_size"]
    if not isinstance(size, int) or size < 0:
        raise Refused("tree_size is not a non-negative integer")

    state = {}
    if os.path.exists(state_path):
        state = json.load(io.open(state_path, encoding="utf-8"))
    prev = state.get(head["log"])

    if prev:
        if size < prev["tree_size"]:
            raise Refused(
                "tree_size went backwards, %d after %d: this log is not "
                "append-only, or this is a different log reusing the name"
                % (size, prev["tree_size"]))
        # A malformed proof is REFUSED and never raised. A witness that throws
        # where it should decline puts the decision in an exception handler
        # somebody else wrote, and the handler that logs and carries on is the
        # one that gets written.
        try:
            nodes = [p if isinstance(p, bytes) else binascii.unhexlify(p)
                     for p in (proof or [])]
        except Exception:
            raise Refused("the consistency proof is not hex. REFUSING.")
        if any(len(n) != 32 for n in nodes):
            raise Refused("a consistency proof node is not a SHA-256 digest. "
                          "REFUSING.")
        # The refusal that matters. No proof is not a smaller failure than a
        # bad proof, and treating it as one is how a witness becomes a rubber
        # stamp without anybody deciding to make it one.
        if not verify_consistency(binascii.unhexlify(prev["root"]),
                                  prev["tree_size"], new_root, size, nodes):
            raise Refused(
                "no consistency proof from tree_size %d verifies against this "
                "head. REFUSING. A witness that signs here is a rubber stamp."
                % prev["tree_size"])

    body = {"statement": STATEMENT, "log": head["log"],
            "tree_size": size, "root": head["root"],
            "observed_at": at or _now(), "attests": ATTESTS,
            "observation_scope": OBSERVATION_SCOPE,
            "observation_scope_means": SCOPES[OBSERVATION_SCOPE],
            "does_not_attest": list(DOES_NOT_ATTEST)}
    signer, pub, alg = _key(state_path)
    sig = signer(canonical(body))

    state[head["log"]] = {"tree_size": size, "root": head["root"]}
    io.open(state_path, "w", encoding="utf-8").write(
        json.dumps(state, indent=2, sort_keys=True))

    return {"cosignature": body, "alg": alg, "key": pub,
            "signature": base64.b64encode(sig).decode(),
            "witness_is_a_reference_implementation": True,
            "no_durability_commitment": (
                "This witness fails W6 of the criteria at "
                "machinetestimony.org/witness/ deliberately. There is no "
                "operator, no notice period and no undertaking that this key "
                "outlives the session that made it.")}


def _now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    p.add_argument("--state", required=True,
                   help="where this witness remembers what it last signed")
    p.add_argument("--head", required=True, help="JSON tree head")
    p.add_argument("--proof", default="[]",
                   help="JSON array of hex consistency proof nodes")
    a = p.parse_args()
    try:
        out = cosign(json.loads(a.head), a.state, json.loads(a.proof))
    except Refused as e:
        sys.stderr.write("REFUSED: %s%s" % (e, chr(10)))
        return 2
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

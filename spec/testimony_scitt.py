"""RFC 9162 inclusion proofs and enough CBOR to read a SCITT receipt.

    from testimony_scitt import read_receipt, reconstruct_root

A COSE receipt (RFC 9942) over an RFC 9162 log is the anchor kind most likely
to matter next, and the validator can read one without a dependency, because
the inclusion proof is arithmetic over SHA-256 and nothing else.

**What this settles and what it does not, because the difference is the whole
point.** Reconstructing a root from a leaf and an audit path is settleable by
anybody with the bytes. That the reconstructed root is the LOG's root is not:
the root is the detached payload the log's signature covers, and checking that
needs a key and a curve this file deliberately does not carry. The statement's
own signature is the same. So a SCITT anchor can be read to exactly the
standard an RFC 3161 token is read to here, no further, and a validator that
reported it as proof of anything more would be making the error this format
exists to expose.

Checked against the five cross-implementation vectors published by the IETF
SCITT working group at ietf-wg-scitt/examples, which are checksum-pinned. All
five receipts parse, their tree size, leaf index and audit path agree with each
vector's expected.json, and the root reconstructs for the three that publish
one. The two that do not publish a root are the two whose failure a reader
cannot reach without a key, which is the finding rather than a gap.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import hashlib

def load(b, i=0):
    """One CBOR item from b at i. Returns (value, next_index)."""
    ib = b[i]; mt, ai = ib >> 5, ib & 0x1f; i += 1
    if ai < 24:
        val = ai
    elif ai == 24:
        val = b[i]; i += 1
    elif ai == 25:
        val = int.from_bytes(b[i:i+2], "big"); i += 2
    elif ai == 26:
        val = int.from_bytes(b[i:i+4], "big"); i += 4
    elif ai == 27:
        val = int.from_bytes(b[i:i+8], "big"); i += 8
    elif ai == 31:
        val = None                      # indefinite length
    else:
        raise ValueError("reserved additional info %d" % ai)

    if mt == 0:
        return val, i
    if mt == 1:
        return -1 - val, i
    if mt in (2, 3):
        if val is None:
            raise ValueError("indefinite strings not supported")
        raw = b[i:i+val]; i += val
        return (raw if mt == 2 else raw.decode("utf-8")), i
    if mt == 4:
        out = []
        if val is None:
            while b[i] != 0xff:
                v, i = load(b, i); out.append(v)
            return out, i + 1
        for _ in range(val):
            v, i = load(b, i); out.append(v)
        return out, i
    if mt == 5:
        out = {}
        if val is None:
            while b[i] != 0xff:
                k, i = load(b, i); v, i = load(b, i); out[k] = v
            return out, i + 1
        for _ in range(val):
            k, i = load(b, i); v, i = load(b, i); out[k] = v
        return out, i
    if mt == 6:
        v, i = load(b, i)               # tag: keep the content
        return v, i
    if mt == 7:
        if ai == 20: return False, i
        if ai == 21: return True, i
        if ai == 22: return None, i
        return ("simple", val), i
    raise ValueError("major type %d" % mt)

VDS_RFC9162_SHA256 = 1
LABEL_VDS = 395
LABEL_PROOFS = 396


def _sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.digest()


def reconstruct_root(leaf_digest, index, size, path):
    """RFC 9162 inclusion proof: leaf and audit path back to a root.

    Arithmetic over bytes, so a reader who disagrees can settle it alone.
    What it does NOT establish is that this root is the log's root; that is
    the detached payload the log's signature covers, and checking it needs a
    key and a curve this reader does not have.
    """
    if index >= size:
        raise ValueError("leaf index %d outside a tree of %d" % (index, size))
    fn, sn, r = index, size - 1, _sha(b"\x00", leaf_digest)
    for p in path:
        if sn == 0:
            raise ValueError("audit path longer than the tree is deep")
        if (fn & 1) or (fn == sn):
            r = _sha(b"\x01", p, r)
            while (fn & 1) == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            r = _sha(b"\x01", r, p)
        fn >>= 1
        sn >>= 1
    if sn != 0:
        raise ValueError("audit path too short for a tree of %d" % size)
    return r


def read_receipt(raw):
    """A COSE_Sign1 SCITT receipt, as far as bytes alone can be read."""
    body, _ = load(raw)
    if not isinstance(body, list) or len(body) != 4:
        raise ValueError("not a COSE_Sign1")
    protected, _ = load(body[0]) if body[0] else ({}, 0)
    unprotected = body[1] or {}
    proofs = unprotected.get(LABEL_PROOFS) or {}
    inclusion = (proofs.get(-1) or [None])[0]
    size = index = None
    path = []
    if inclusion is not None:
        parsed, _ = load(inclusion)
        if isinstance(parsed, list) and len(parsed) == 3:
            size, index, path = parsed
    return {"vds": protected.get(LABEL_VDS), "alg": protected.get(1),
            "tree_size": size, "leaf_index": index, "path": path,
            "detached": body[2] is None}

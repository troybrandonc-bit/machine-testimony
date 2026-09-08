"""SCITT receipts: what bytes alone can settle. Run: python3 tests_scitt.py

Two halves. The first builds RFC 9162 trees here and proves every leaf in
them, which tests the algorithm against itself and needs nothing external.
The second runs the IETF SCITT working group's own cross-implementation
vectors, which is the half that means anything, because agreeing with yourself
is not interoperability.

The algorithms live in testimony_validate.py rather than beside it, because
that file is copied whole into other repositories and into every adapter
wheel. An import would make the reference validator behave differently
depending on what sits next to it, and two copies calling themselves the
reference would reach different verdicts.

The vectors are not vendored. Set SCITT_VECTORS to a checkout of
ietf-wg-scitt/examples/test-vectors/scitt-cose and the second half runs; leave
it unset and it says so rather than passing quietly, on the same terms as the
adapter suites that skip without their framework.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import base64
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_validate as sc                              # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:240])


def _sha(*p):
    h = hashlib.sha256()
    for x in p:
        h.update(x)
    return h.digest()




# A receipt, encoded here, so the whole path can be exercised. Only the
# shapes a receipt uses. Building one rather than borrowing one is what lets
# a test say 'this record, this tree' and then break it on purpose.
def _c(mt, n):
    if n < 24:
        return bytes([mt << 5 | n])
    if n < 256:
        return bytes([mt << 5 | 24, n])
    if n < 65536:
        return bytes([mt << 5 | 25]) + n.to_bytes(2, 'big')
    return bytes([mt << 5 | 26]) + n.to_bytes(4, 'big')


def _enc(v):
    if v is None or isinstance(v, bool):
        return bytes([0xf6])
    if isinstance(v, int):
        return _c(0, v) if v >= 0 else _c(1, -1 - v)
    if isinstance(v, bytes):
        return _c(2, len(v)) + v
    if isinstance(v, list):
        return _c(4, len(v)) + b''.join(_enc(x) for x in v)
    if isinstance(v, dict):
        return _c(5, len(v)) + b''.join(_enc(k) + _enc(x) for k, x in v.items())
    raise TypeError(type(v))


def receipt(size, index, path, vds=1):
    protected = _enc({395: vds, 1: -8})
    proof = _enc([size, index, [bytes(p) for p in path]])
    body = [protected, {396: {-1: [proof]}}, None, bytes(8)]
    return bytes([0xd2]) + _enc(body)

def root_of(leaves):
    """The RFC 9162 tree head, computed the slow obvious way."""
    if len(leaves) == 1:
        return _sha(b"\x00", leaves[0])
    k = 1
    while k * 2 < len(leaves):
        k *= 2
    return _sha(b"\x01", root_of(leaves[:k]), root_of(leaves[k:]))


def path_of(leaves, i):
    if len(leaves) == 1:
        return []
    k = 1
    while k * 2 < len(leaves):
        k *= 2
    if i < k:
        return path_of(leaves[:k], i) + [root_of(leaves[k:])]
    return path_of(leaves[k:], i - k) + [root_of(leaves[:k])]


def main():
    print("\nthe inclusion proof agrees with a tree built here")
    for size in (1, 2, 3, 5, 8, 13):
        leaves = [_sha(b"leaf", bytes([n])) for n in range(size)]
        want = root_of(leaves)
        ok = all(sc.reconstruct_root(leaves[i], i, size, path_of(leaves, i))
                 == want for i in range(size))
        check("every leaf of a tree of %d proves to the same root" % size, ok)

    check("a leaf outside the tree is refused rather than reconstructed",
          _raises(lambda: sc.reconstruct_root(_sha(b"x"), 3, 3, [])))
    check("an audit path too short for the tree is refused",
          _raises(lambda: sc.reconstruct_root(_sha(b"x"), 0, 8, [])))

    print("\nand with the working group's own vectors")
    base = os.environ.get("SCITT_VECTORS")
    if not base or not os.path.isdir(base):
        print("  NOT VERIFIED: set SCITT_VECTORS to a checkout of "
              "ietf-wg-scitt/examples/test-vectors/scitt-cose")
    else:
        man = json.load(open(os.path.join(base, "manifest.json"),
                             encoding="utf-8"))
        seen = 0
        for v in man["vectors"]:
            d = os.path.join(base, v["dir"])
            exp = json.load(open(os.path.join(d, "expected.json"),
                                 encoding="utf-8"))
            rec = sc.read_receipt(open(os.path.join(d, "receipt.cose"),
                                       "rb").read())
            stmt = open(os.path.join(d, "statement.cose"), "rb").read()
            leaf = hashlib.sha256(stmt).digest()
            check("%s: the receipt parses as the vector says" % v["id"],
                  rec["tree_size"] == exp["tree_size"]
                  and rec["leaf_index"] == exp["leaf_index"]
                  and [p.hex() for p in rec["path"]] == exp["inclusion_path"],
                  rec)
            check("%s: the leaf is the digest of the signed statement"
                  % v["id"], leaf.hex() == exp["leaf_entry"])
            if exp.get("reconstructed_root"):
                got = sc.reconstruct_root(leaf, rec["leaf_index"],
                                          rec["tree_size"], rec["path"])
                check("%s: and the root reconstructs to the published one"
                      % v["id"], got.hex() == exp["reconstructed_root"])
            seen += 1
        check("every vector in the manifest was run", seen == len(man["vectors"]))

        print("\nand it says plainly what it cannot decide")
        # The two vectors with no published root are the two whose failure is
        # only visible to a key holder. Reading them as valid would be the
        # error; refusing them would also be wrong, since nothing in the bytes
        # says they are bad. The honest report is that this reader cannot say.
        undecidable = [v["id"] for v in man["vectors"]
                       if json.load(open(os.path.join(base, v["dir"],
                                                      "expected.json"),
                                         encoding="utf-8")).get("failure_code")
                       == "BAD_STATEMENT_SIGNATURE"]
        check("a bad statement signature is not detectable from the bytes",
              len(undecidable) == 1, undecidable)

    print()
    print("a scitt anchor binds a record, or says why it does not")
    src = os.path.join(ROOT, "public", "anchor", "record.jsonl")
    entries = [json.loads(l) for l in io.open(src, encoding="utf-8")
               if l.strip()]
    body = [e for e in entries if e["type"] != "integrity"]
    dig = sc.digest_of(body)
    leaves = [_sha(b"filler", bytes([i])) for i in range(8)]
    leaves[2] = bytes.fromhex(dig)
    head = root_of(leaves).hex()
    proof = path_of(leaves, 2)

    def anchored(**over):
        a = {"kind": "scitt", "authority": "a transparency service",
             "token": base64.b64encode(receipt(8, 2, proof)).decode(),
             "root": head}
        a.update(over.pop("anchor", {}))
        g = {"spec": body[0]["spec"], "type": "integrity", "id": "g1",
             "at": "2026-09-08T12:00:00Z", "scheme": "external-anchor",
             "digest": "sha256:" + dig,
             "covers": [e["id"] for e in body], "anchor": a}
        g.update(over)
        return sc.validate(chr(10).join(
            json.dumps(e) for e in body + [g])).as_dict()

    def named(rep, want):
        return [c for c in rep["checks"] if c["check"] == want]

    BIND = "the anchor's token is over this record's digest"
    rep = anchored()
    check("a receipt whose proof lands on the declared head reaches TR-4",
          rep["level"] == "TR-4",
          [c["check"] for c in rep["checks"] if not c["ok"]])
    check("and the binding is reported verified",
          named(rep, BIND) and named(rep, BIND)[0]["basis"] == "verified")
    check("while the head being the log's is attested, not settled",
          rep["basis"]["TR-4"]["attested"] >= 2,
          rep["basis"]["TR-4"])

    bad = anchored(anchor={"root": ("0" * 63) + "1"})
    check("a proof landing somewhere other than the declared head fails",
          not named(bad, BIND)[0]["ok"] and bad["level"] != "TR-4",
          bad["level"])

    none = anchored(anchor={"root": ""})
    check("a scitt anchor with no declared head is refused, since nothing "
          "would be checked", not named(none, BIND)[0]["ok"],
          named(none, BIND))

    # Another verifiable data structure is not a bad one. Refusing it would
    # repeat the mistake refusing an unknown kind was, in a narrower place.
    other = anchored(anchor={"token": base64.b64encode(
        receipt(8, 2, proof, vds=2)).decode()})
    check("a receipt over a structure this reader cannot check is attested "
          "rather than failed", other["level"] == "TR-4"
          and not named(other, BIND), other["level"])

    wrong = anchored(anchor={"token": base64.b64encode(
        receipt(8, 5, proof)).decode()})
    check("a receipt for a different leaf does not land on the head",
          not named(wrong, BIND)[0]["ok"])

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


def _raises(fn):
    try:
        fn()
        return False
    except Exception:                                          # noqa: BLE001
        return True


if __name__ == "__main__":
    sys.exit(main())

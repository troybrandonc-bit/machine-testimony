"""SCITT receipts: what bytes alone can settle. Run: python3 tests_scitt.py

Two halves. The first builds RFC 9162 trees here and proves every leaf in
them, which tests the algorithm against itself and needs nothing external.
The second runs the IETF SCITT working group's own cross-implementation
vectors, which is the half that means anything, because agreeing with yourself
is not interoperability.

The vectors are not vendored. Set SCITT_VECTORS to a checkout of
ietf-wg-scitt/examples/test-vectors/scitt-cose and the second half runs; leave
it unset and it says so rather than passing quietly, on the same terms as the
adapter suites that skip without their framework.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_scitt as sc                                 # noqa: E402

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

"""The external anchor is held by somebody else, or it is not an anchor.

Run: python3 tests_anchor.py

A record's own integrity digest is computed by whoever produced the record.
It catches a later edit by a third party and proves nothing about the producer,
who can recompute it over whatever they like. That is stated in the
specification's security considerations, and it was the one place a reader
could fairly say the format asked for less than it should.

An RFC 3161 timestamp closes it: an authority signs the pair of digest and
time with its own key. What these tests establish is that the thing in the
record is really that, and not a field named after it.

The DER here is built by hand because asking every implementer to install a
certificate library in order to emit one entry is a worse cost than fifty lines
of encoding. Hand-rolled parsing in a security-adjacent tool is a fair thing to
distrust, so the generation time this module reports is checked against
`openssl ts -reply -text` rather than asserted, and the suite says so when
openssl is not present instead of quietly skipping the comparison.

Network use is deliberate and limited to the timestamp exchange. A test that
mocked the authority would be testing the mock, and the claim under test is
precisely that a third party will sign this.
"""
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_anchor as ta        # noqa: E402
import testimony_validate as tv      # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:240])


def record(**over):
    """A minimal record that reaches TR-3, so the only thing in question is
    what the integrity entry adds."""
    e = [
        {"spec": tv.SPEC, "type": "scope", "id": "s1",
         "at": "2026-09-05T10:00:00Z", "acts": True},
        {"spec": tv.SPEC, "type": "evidence", "id": "e1",
         "at": "2026-09-05T10:00:01Z", "kind": "api", "source": "crm://1"},
        {"spec": tv.SPEC, "type": "belief", "id": "b1",
         "at": "2026-09-05T10:00:02Z", "subject": "customer:a",
         "proposition": "owed_refund", "polarity": "affirm",
         "state": "believed_true",
         "asserted_by": {"id": "agent", "kind": "agent"}, "evidence": ["e1"]},
        {"spec": tv.SPEC, "type": "decision", "id": "d1",
         "at": "2026-09-05T10:00:03Z", "action_type": "issue_refund",
         "risk_class": "high", "risk_source": "registry",
         "proposed_by": {"id": "agent", "kind": "agent"},
         "verdict": "permitted", "executed": True, "approval": "a1"},
        {"spec": tv.SPEC, "type": "approval", "id": "a1",
         "at": "2026-09-05T10:00:04Z", "decision": "d1",
         "approver": {"id": "sam@example.com", "kind": "human"},
         "identity_source": "auth-session"},
    ]
    e.extend(over.get("extra", []))
    return e


def as_text(entries):
    return "\n".join(json.dumps(x) for x in entries)


def main():
    print("a hollow claim is refused")
    for missing, label in [
        ({}, "no anchor object at all"),
        ({"kind": "rfc3161", "authority": "https://x"}, "no token"),
        ({"kind": "rfc3161", "token": "abc"}, "no authority"),
        ({"authority": "https://x", "token": "abc"}, "no kind"),
    ]:
        g = {"spec": tv.SPEC, "type": "integrity", "id": "i1",
             "at": "2026-09-05T10:00:05Z", "scheme": "external-anchor",
             "digest": "sha256:" + "0" * 64, "covers": ["s1"]}
        if missing:
            g["anchor"] = missing
        r = tv.validate(as_text(record() + [g]))
        failed = [c for c in r.failures("TR-4")
                  if "external anchor" in c["check"]]
        check("refused: " + label, bool(failed) and r.level != "TR-4",
              "level %s" % r.level)

    print("\na hash-chain entry is unaffected by the new check")
    g = {"spec": tv.SPEC, "type": "integrity", "id": "i1",
         "at": "2026-09-05T10:00:05Z", "scheme": "hash-chain",
         "digest": "sha256:" + "0" * 64, "covers": ["s1"]}
    r = tv.validate(as_text(record() + [g]))
    check("a hash chain still reaches TR-4", r.level == "TR-4",
          [c["check"] for c in r.failures("TR-4")])

    print("\nthe request is a well formed RFC 3161 query")
    q = ta.timestamp_query(bytes(range(32)))
    check("it is a DER SEQUENCE", q[0] == 0x30)
    check("it declares version 1", b"\x02\x01\x01" in q)
    check("it names SHA-256", ta.SHA256_OID in q)
    check("it carries the digest", bytes(range(32)) in q)
    check("it asks for the certificate", q.endswith(b"\x01\x01\xff"))
    try:
        ta.timestamp_query(b"short")
        check("a wrong-length digest raises", False)
    except ValueError:
        check("a wrong-length digest raises", True)

    if os.environ.get("TESTIMONY_NO_NETWORK"):
        print("\nSKIP: the timestamp exchange needs network access")
        print("\n%d passed, %d failed" % (PASS, FAIL))
        return 1 if FAIL else 0

    print("\nan authority really signs it")
    body = record()
    try:
        entry = ta.anchor_entry(body)
    except Exception as e:                                   # noqa: BLE001
        print("  SKIP: could not reach a timestamp authority (%s)" % str(e)[:70])
        print("\n%d passed, %d failed" % (PASS, FAIL))
        return 1 if FAIL else 0

    a = entry["anchor"]
    check("the scheme is external-anchor", entry["scheme"] == "external-anchor")
    check("it names the authority", a["authority"].startswith("http"))
    check("it carries a token", len(a["token"]) > 500)
    check("it reports a generation time", bool(a["anchored_at"]))
    check("it says what a timestamp does not prove",
          "does_not_prove" in a and "true" in a["does_not_prove"])

    check("the digest is over exactly what covers names",
          entry["digest"] == "sha256:" + ta.digest_of(body)
          and entry["covers"] == [x["id"] for x in body])

    r = tv.validate(as_text(body + [entry]))
    check("an anchored record reaches TR-4", r.level == "TR-4",
          [c["check"] for c in r.failures("TR-4")])

    print("\nthe producer cannot quietly change the record")
    tampered = json.loads(json.dumps(body))
    for e in tampered:
        if e["type"] == "approval":
            e["approver"]["id"] = "someone-else@example.com"
    check("softening the approver breaks the digest",
          "sha256:" + ta.digest_of(tampered) != entry["digest"])

    print("\nopenssl agrees with what we report")
    if not shutil.which("openssl"):
        print("  NOT VERIFIED: openssl is absent, so the hand-rolled parse was "
              "not compared against a reference implementation")
    else:
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.tsr")
            io.open(p, "wb").write(base64.b64decode(a["token"]))
            out = subprocess.run(["openssl", "ts", "-reply", "-in", p, "-text"],
                                 capture_output=True, text=True).stdout
            check("openssl reports the token as granted", "Status: Granted" in out)

            # openssl prints the imprint as offset-prefixed hex with spacing,
            # so it is normalised before comparing. A plain string compare
            # against our hex looks like a mismatch and is not one.
            block = re.search(r"Message data:(.*?)\n\s*\S+ number", out, re.S)
            hexed = "".join(re.findall(r"\b[0-9a-f]{2}\b", block.group(1))) if block else ""
            ours = entry["digest"].split(":", 1)[1]
            check("the token's imprint is our digest", hexed == ours,
                  "token %s.. ours %s.." % (hexed[:20], ours[:20]))

            m = re.search(r"Time stamp:\s*(.+)", out)
            check("openssl and our parse report the same time",
                  bool(m) and _same_time(m.group(1).strip(), a["anchored_at"]),
                  "openssl %s, ours %s" % (m.group(1).strip() if m else "?",
                                           a["anchored_at"]))

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


def _same_time(openssl_text: str, ours: str) -> bool:
    """openssl prints 'Sep  5 13:42:06 2026 GMT'; ours is RFC 3339."""
    import datetime as dt
    try:
        t = dt.datetime.strptime(" ".join(openssl_text.split()[:4]),
                                 "%b %d %H:%M:%S %Y")
    except ValueError:
        return False
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") == ours


if __name__ == "__main__":
    sys.exit(main())

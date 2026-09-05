"""Anchor a Testimony Record to a third party, so its integrity does not rest
on the word of whoever wrote it.

    python3 testimony_anchor.py record.jsonl >> record.jsonl
    python3 testimony_validate.py record.jsonl        # now reaches TR-4

WHY THIS EXISTS.

A record's own integrity entry is computed by the party that produced the
record. It detects a later edit by somebody else, which is worth having, and it
proves nothing about the producer: anyone able to rewrite the entries can
recompute the digest over them. The specification's security considerations say
so, and until now the reference tooling offered nothing better.

An RFC 3161 timestamp fixes the narrow thing it can fix. A Time Stamp
Authority signs the pair (digest, time) with its own key. The producer cannot
forge that signature, cannot backdate it, and cannot alter the record without
the digest ceasing to match. What remains uncovered is stated plainly in the
record: a timestamp proves the record existed in this exact form at that time.
It does not prove the record is true, or complete, or that a different record
was not also produced and discarded.

WHY RFC 3161 RATHER THAN A LEDGER.

It is an IETF standard, it underpins qualified electronic timestamps in eIDAS,
free authorities operate it, and a verifier checks the token with `openssl ts`
rather than with anything of ours. A conformance claim that can only be checked
with the claimant's software is the thing this project exists to refuse, and
that applies to our own tooling first.

No dependencies. The request is a few dozen bytes of DER built by hand below,
because the alternative is asking every implementer to install a certificate
library to emit one entry.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import json
import os
import sys
import urllib.request

SPEC = "testimony-record/0.2"

# Authorities that answer an anonymous request. The default is first; the
# others are here so that one authority being down is an inconvenience rather
# than a reason the record cannot be anchored.
TSAS = {
    "digicert": "http://timestamp.digicert.com",
    "freetsa": "https://freetsa.org/tsr",
}

# Tried in order when no authority is named. FreeTSA rate limits an address
# that asks repeatedly, which is reasonable of it and fatal for a build that
# treats one authority as the only one.
FALLBACK = ["digicert", "freetsa"]

SEQ, INT, OID, NULL, OCTET, BOOL, GENTIME = 0x30, 0x02, 0x06, 0x05, 0x04, 0x01, 0x18
SHA256_OID = bytes([0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01])


# ── the little DER we need, and no more ──────────────────────────────────────

def _dlen(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _der(tag: int, payload: bytes) -> bytes:
    return bytes([tag]) + _dlen(len(payload)) + payload


def _uint(v: bytes) -> bytes:
    """A DER INTEGER holding a non-negative value, minimally encoded.

    DER is not "any encoding that decodes to the right number". The content
    octets are two's complement and must be minimal, so a leading zero byte is
    permitted only where the next byte has its high bit set, and required where
    it does. That is not a cosmetic rule here. A Time Stamp Authority copies
    the nonce verbatim into the token it signs, so an over-padded integer
    becomes a signed token that strict parsers refuse, and no amount of care
    afterwards can correct it without asking for a new signature.
    """
    i = 0
    while i < len(v) - 1 and v[i] == 0 and not v[i + 1] & 0x80:
        i += 1
    v = v[i:] or b"\x00"
    return _der(INT, b"\x00" + v if v[0] & 0x80 else v)


def timestamp_query(digest: bytes) -> bytes:
    """An RFC 3161 TimeStampReq over a SHA-256 digest.

    certReq is true so the authority returns its certificate inside the token,
    which is what lets somebody verify the token without first knowing where to
    fetch that certificate from.
    """
    if len(digest) != 32:
        raise ValueError("expected a 32 byte SHA-256 digest")
    algid = _der(SEQ, _der(OID, SHA256_OID) + _der(NULL, b""))
    imprint = _der(SEQ, algid + _der(OCTET, digest))
    nonce = _uint(os.urandom(8))
    return _der(SEQ, _uint(b"\x01") + imprint + nonce + _der(BOOL, b"\xff"))


def _walk(data: bytes, want: int, depth: int = 0):
    """Yield the contents of every element with this tag, recursively.

    Deliberately small. It is used to read the granted status and the generation
    time out of a reply, both of which sit at known depths, and the test checks
    what it reports against `openssl ts -reply -text` rather than trusting it.
    """
    i = 0
    while i < len(data) - 1:
        tag = data[i]
        j = i + 1
        if j >= len(data):
            return
        first = data[j]
        if first & 0x80:
            n = first & 0x7F
            if n == 0 or j + 1 + n > len(data):
                return
            length = int.from_bytes(data[j + 1:j + 1 + n], "big")
            j = j + 1 + n
        else:
            length = first
            j = j + 1
        if length < 0 or j + length > len(data):
            return
        body = data[j:j + length]
        if tag == want:
            yield body
        # Descend into constructed elements, and into OCTET STRINGs, because
        # the TSTInfo carrying the generation time is DER wrapped inside one.
        # An OCTET STRING holding something else simply yields nothing.
        if depth < 12 and (tag & 0x20 or tag == OCTET):
            yield from _walk(body, want, depth + 1)
        i = j + length


def granted(reply: bytes) -> bool:
    """PKIStatus 0 (granted) or 1 (grantedWithMods) means we have a token."""
    for body in _walk(reply, INT):
        return body == b"\x00" or body == b"\x01"
    return False


def generation_time(reply: bytes) -> str | None:
    """The genTime the authority put in the token, as RFC 3339.

    Reported rather than trusted: the token is what carries the proof, and this
    is the same value in a form a reader can compare.
    """
    for body in _walk(reply, GENTIME):
        raw = body.decode("ascii", "replace").rstrip("Z")
        head, _, frac = raw.partition(".")
        if len(head) < 14 or not head.isdigit():
            continue
        try:
            t = _dt.datetime.strptime(head[:14], "%Y%m%d%H%M%S")
        except ValueError:
            continue
        return t.replace(tzinfo=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


# ── anchoring a record ───────────────────────────────────────────────────────

def canonical(entry: dict) -> str:
    return json.dumps({k: v for k, v in entry.items() if not k.startswith("_")},
                      sort_keys=True, separators=(",", ":"))


def digest_of(entries: list) -> str:
    return hashlib.sha256(
        "\n".join(canonical(e) for e in entries).encode()).hexdigest()


def _ask(url: str, req: bytes, timeout: int) -> bytes:
    r = urllib.request.Request(
        url, data=req, headers={"Content-Type": "application/timestamp-query",
                                "Content-Length": str(len(req))})
    return urllib.request.urlopen(r, timeout=timeout).read()


def fetch_token(digest_hex: str, tsa: str | None = None,
                timeout: int = 30) -> dict:
    """A signed timestamp over this digest, from the first authority that gives
    one.

    Naming an authority uses that one only, because somebody who has chosen a
    particular authority, or a qualified one under eIDAS, means it. Naming none
    tries the list, since an anchor from any of them is the same kind of
    evidence and a build should not fail because one is rate limiting.
    """
    req = timestamp_query(bytes.fromhex(digest_hex))
    names = [tsa] if tsa else list(FALLBACK)
    problems = []
    for name in names:
        url = TSAS.get(name, name)
        try:
            reply = _ask(url, req, timeout)
        except Exception as e:                              # noqa: BLE001
            problems.append("%s: %s" % (url, str(e)[:60]))
            continue
        if not granted(reply):
            problems.append("%s: refused the request" % url)
            continue
        return {"authority": url, "token": base64.b64encode(reply).decode(),
                "anchored_at": generation_time(reply)}
    raise RuntimeError("no timestamp authority would sign this: "
                       + "; ".join(problems))


def anchor_entry(entries: list, tsa: str | None = None,
                 eid: str = "anchor_1") -> dict:
    """An integrity entry whose evidence is held by somebody else.

    `covers` names what the digest was taken over, in order, so a verifier
    recomputes the same value or does not.
    """
    covered = [e["id"] for e in entries if e.get("type") != "integrity"]
    only = [e for e in entries if e.get("type") != "integrity"]
    dg = digest_of(only)
    tok = fetch_token(dg, tsa)
    return {
        "spec": SPEC, "type": "integrity", "id": eid,
        "at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scheme": "external-anchor",
        "digest": "sha256:" + dg,
        "covers": covered,
        "anchor": {
            "kind": "rfc3161",
            "authority": tok["authority"],
            "anchored_at": tok["anchored_at"],
            "token": tok["token"],
            # Said in the record rather than in a document nobody reads beside
            # it. A timestamp fixes the time and the bytes and nothing else.
            "proves": "this record existed in exactly this form at anchored_at",
            "does_not_prove": "that the record is true, complete, or the only "
                              "one produced",
            "verify": "base64 -d the token into anchor.tsr, then: openssl ts "
                      "-verify -in anchor.tsr -digest <sha256 hex> -CAfile "
                      "<authority roots>",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Append an RFC 3161 external anchor to a Testimony Record.")
    ap.add_argument("record", help="path to a .jsonl record, or - for stdin")
    ap.add_argument("--tsa", default=None,
                    help="digicert, freetsa, or a full URL. Omitted, each is "
                         "tried in turn.")
    ap.add_argument("--id", default="anchor_1", help="id for the new entry")
    a = ap.parse_args()

    text = sys.stdin.read() if a.record == "-" else open(
        a.record, encoding="utf-8").read()
    entries = [json.loads(l) for l in text.splitlines() if l.strip()
               and not l.lstrip().startswith("#")]
    if not entries:
        print("nothing to anchor: the record is empty", file=sys.stderr)
        return 1

    entry = anchor_entry(entries, a.tsa, a.id)
    print(json.dumps(entry))
    print("anchored %d entries at %s via %s"
          % (len(entry["covers"]), entry["anchor"]["anchored_at"],
             entry["anchor"]["authority"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

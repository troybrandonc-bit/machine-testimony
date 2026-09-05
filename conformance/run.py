#!/usr/bin/env python3
"""Check an implementation against the Testimony Record conformance corpus.

    python3 conformance/run.py --command "python3 my_validator.py --json {file}"
    python3 conformance/run.py --command "node dist/cli.js {file}" --verbose

Your command is run once per case with `{file}` replaced by a path to a record.
It must print a JSON object to standard output carrying at least:

    {"level": "TR-3" | ... | null,
     "levels_met": {"TR-1": true, "TR-2": true, "TR-3": true, "TR-4": false}}

`spec` and `scope` are compared when your implementation reports them, and
ignored when it does not, so a validator that does not model scope is not
failed for a thing it never claimed.

WHAT CONFORMANCE MEANS HERE, AND WHAT IT DOES NOT.

It means your implementation reaches the same verdict as the reference on every
case. It does not mean it produces the same check names, the same wording, the
same number of checks, or the same explanations. Those are the reference's
prose, and a corpus that compared them would be testing whether you had
transliterated somebody else's file rather than whether you had implemented a
specification. An independent implementation is the entire point, so the test
is deliberately blind to everything except the answer.

A case your implementation gets wrong is not necessarily your bug. If you think
the reference is wrong, the disagreement is worth more than the corpus is:
open an issue with the case name. Two of the checks in this corpus exist
because somebody did that.

This file has no dependencies and imports nothing of ours. Copy it.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = ("TR-1", "TR-2", "TR-3", "TR-4")


def load_expected(path: str) -> dict:
    return json.load(io.open(path, encoding="utf-8"))


def run_one(command: str, path: str, timeout: int) -> tuple[dict | None, str]:
    # The command is split before the path goes in, never after. A Windows path
    # carries backslashes, and shlex in POSIX mode reads those as escapes, so
    # substituting first turns C:\cases\x.jsonl into C:casesx.jsonl and every
    # case reports that your implementation produced no answer.
    parts = shlex.split(command, posix=(os.name != "nt"))
    if os.name == "nt":
        # Non-POSIX mode leaves the quote characters inside the token, so a
        # quoted path arrives as "C:\dir\x.py" with the quotes attached and
        # nothing can be run. Quoting a path is the first thing anybody with a
        # space in their filename does.
        parts = [p[1:-1] if len(p) > 1 and p[0] == p[-1] in "\"'" else p
                 for p in parts]
    if any("{file}" in p for p in parts):
        parts = [p.replace("{file}", path) for p in parts]
    else:
        parts.append(path)
    try:
        out = subprocess.run(parts, capture_output=True, text=True,
                             timeout=timeout)
    except FileNotFoundError:
        return None, "cannot run %r" % parts[0]
    except subprocess.TimeoutExpired:
        return None, "timed out after %ds" % timeout
    text = out.stdout.strip()
    if not text:
        return None, (out.stderr or "no output").strip()[:200]
    # A validator that exits non-zero on a failing record is behaving
    # reasonably, so the exit status is not read as an error. Only the report
    # is read.
    try:
        return json.loads(text), ""
    except json.JSONDecodeError:
        start = text.find("{")
        if start >= 0:
            try:
                return json.loads(text[start:]), ""
            except json.JSONDecodeError:
                pass
        return None, "output is not JSON: %s" % text[:160]


def compare(got: dict, want: dict) -> list:
    """What differs, in the reader's terms."""
    bad = []
    if got.get("level") != want["level"]:
        bad.append("reached %s, the reference reaches %s"
                   % (got.get("level"), want["level"]))
    mine = got.get("levels_met") or {}
    for lvl in LEVELS:
        if lvl in mine and bool(mine[lvl]) != want["levels_met"][lvl]:
            bad.append("%s %s, the reference says %s"
                       % (lvl, "met" if mine[lvl] else "not met",
                          "met" if want["levels_met"][lvl] else "not met"))
    for field in ("spec", "scope"):
        if field in got and want.get(field) is not None \
                and got[field] != want[field]:
            bad.append("%s %r, the reference says %r"
                       % (field, got[field], want[field]))
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run an implementation against the conformance corpus.")
    ap.add_argument("--command", required=True,
                    help="how to run yours; {file} is the record's path")
    ap.add_argument("--cases", default=os.path.join(HERE, "cases"))
    ap.add_argument("--expected", default=os.path.join(HERE, "expected.json"))
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--verbose", action="store_true",
                    help="print every case, not only the ones that differ")
    a = ap.parse_args()

    expected = load_expected(a.expected)
    passed, failed, broke = [], [], []

    for name in sorted(expected):
        path = os.path.join(a.cases, name + ".jsonl")
        if not os.path.exists(path):
            broke.append((name, "no case file at %s" % path))
            continue
        got, err = run_one(a.command, path, a.timeout)
        if got is None:
            broke.append((name, err))
            continue
        bad = compare(got, expected[name])
        if bad:
            failed.append((name, expected[name]["note"], bad))
        else:
            passed.append(name)
            if a.verbose:
                print("  ok  %-30s %s" % (name, expected[name]["note"]))

    for name, note, bad in failed:
        print("  DIFFERS  %s" % name)
        print("           %s" % note)
        for line in bad:
            print("           %s" % line)
    for name, err in broke:
        print("  NO ANSWER  %-28s %s" % (name, err))

    total = len(expected)
    print("\n%d of %d agree with the reference" % (len(passed), total))
    if broke:
        print("%d produced no answer this test could read" % len(broke))
    if not failed and not broke:
        print("\nThis implementation conforms to the corpus. That is a claim "
              "about these %d cases and not a certificate." % total)
    return 0 if not failed and not broke else 1


if __name__ == "__main__":
    sys.exit(main())

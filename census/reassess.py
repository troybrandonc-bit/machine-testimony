"""Re-assess a subject at a newer commit, keeping what was said before.

    python3 census/reassess.py langgraph --commit <40 hex> --version "1.4.0"

The register was a judgement made once. That is the least useful shape it could
have, because the only people with a reason to care about a scoreboard are the
ones on it, and nothing here gave them a way to move. A system that fixed
something had no route to being re-read, and a system that had not fixed
anything looked identical to one that had.

So a re-assessment is offered to anybody, on terms that are the same for
everybody, and this is the machinery that keeps it honest.

WHAT IT DOES NOT DO is overwrite. The rule the whole census rests on is that a
verdict is about a named tree and not about a project, so a later fix does not
make an earlier reading false. The earlier assessment is moved to
`subjects/prior/`, unchanged, still digested by the manifest and still citable.
The new one names it in `supersedes`. Both dates stay readable, which is the
only way a reader can tell a system that moved from a system that was always
fine, and the only way anybody can check that a re-read was not quietly kinder
than the first one.

This script does the moving and the bookkeeping. It does not do the reading:
every verdict in the new file still has to be earned by opening the source at
the new commit, and the file it leaves behind is deliberately full of the old
verdicts so that an assessor has to go and change each one that changed.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUBJECTS = os.path.join(HERE, "subjects")
PRIOR = os.path.join(SUBJECTS, "prior")
sys.path.insert(0, HERE)

import subject as sub                     # noqa: E402


def prior_name(doc: dict) -> str:
    return "%s-%s.json" % (doc["subject"], doc["commit"][:12])


def reassess(sid: str, commit: str, version: str, assessed_on: str,
             assessed_by: str | None = None) -> tuple[str, str]:
    """Archive the current assessment and open a new one at `commit`."""
    path = os.path.join(SUBJECTS, sid + ".json")
    doc = sub.load(path)                  # refuses to archive an invalid file

    if commit == doc["commit"]:
        raise SystemExit("that is the commit already assessed; nothing to do")
    if len(commit) != 40 or not all(c in "0123456789abcdef" for c in commit):
        raise SystemExit("a re-assessment needs a full 40 character commit, "
                         "for the same reason the first one did")

    os.makedirs(PRIOR, exist_ok=True)
    archived = os.path.join(PRIOR, prior_name(doc))
    if os.path.exists(archived):
        raise SystemExit("%s already exists; that tree was assessed before"
                         % os.path.relpath(archived, HERE))
    shutil.copy2(path, archived)

    # The new file starts as the old one. Every verdict it inherits is a claim
    # about a tree nobody has read yet, which is why `pending` is written over
    # each of them: an assessor has to go and settle each one, and a file left
    # half done is refused by run.py --check rather than published quietly.
    fresh = dict(doc)
    fresh["version"] = version
    fresh["commit"] = commit
    fresh["assessed_on"] = assessed_on
    if assessed_by:
        fresh["assessed_by"] = assessed_by
    fresh["supersedes"] = {
        "file": "subjects/prior/" + prior_name(doc),
        "commit": doc["commit"],
        "assessed_on": doc.get("assessed_on", ""),
        "level": sub.level_reached(doc),
    }
    for rid, a in fresh["assessments"].items():
        if isinstance(a, dict):
            a["was"] = a.get("verdict")
            a["verdict"] = "pending"

    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(fresh, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return archived, path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("subject")
    ap.add_argument("--commit", required=True, help="the full 40 character hash")
    ap.add_argument("--version", required=True)
    ap.add_argument("--on", required=True, help="the date of the re-reading")
    ap.add_argument("--by", default=None)
    args = ap.parse_args()

    archived, path = reassess(args.subject, args.commit.strip().lower(),
                              args.version, args.on, args.by)
    print("kept   %s" % os.path.relpath(archived, HERE))
    print("opened %s" % os.path.relpath(path, HERE))
    print()
    print("Every verdict now reads 'pending' with the old one kept in 'was'.")
    print("Settle each by reading the source at %s." % args.commit[:12])
    print("Then: python3 census/run.py --check && python3 census/manifest.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

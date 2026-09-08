"""Suppliers who can answer, indexed rather than assessed.

    python3 census/build_directory.py            # write pages/directory.html
    python3 census/build_directory.py --check    # do the listings still hold

The register reads systems at pinned commits and says what they cannot do.
That is adversarial by design and nobody volunteers for it. This is the other
side: a supplier publishes a record from their own system, at a URL they
control, and this indexes what the validator says about it.

**Indexed, not certified, and the difference is the whole design.** Nothing
here is assessed by this project. The supplier publishes. The validator, which
is published separately and runs anywhere, produces the verdict. This file
fetches the record and reports what anybody running the same command would get.
A directory that graded submissions would be a certification body, which the
roadmap forbids and which would cost more credibility than the listing is
worth.

**And it is one record the supplier chose.** That is said on the page rather
than buried here. A record demonstrates that a system CAN produce one, which is
the question buyers ask and the census answers in the negative for most
systems. It is not evidence about every action the system ever took, and a page
implying otherwise would be the soft yes the questions exist to catch.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_validate as tv                              # noqa: E402

SUBJECTS = os.path.join(HERE, "suppliers")

# The questions at /ask/, and the validator check that settles each. Keeping
# them in this order means the directory answers the questionnaire a buyer
# already has rather than a different one nobody asked.
ASKED = (
    ("does the record name which person approved",
     "an approval names a person, other than the proposer, for a decision in "
     "the record"),
    ("does that name come from authentication",
     "the approver's name is declared to come from authentication"),
    # Worded so that yes is always the good answer. The /ask/ page asks "can
    # the agent approve its own action", where yes is the bad answer, and a
    # column of yeses meaning opposite things is how a directory misleads
    # somebody without saying anything false.
    ("is the approver a different party from the proposer",
     "an approval names a person, other than the proposer, for a decision in "
     "the record"),
    ("are both sides of a disagreement kept",
     "both sides of every conflict are retained"),
    ("does a resolved disagreement say who resolved it",
     "a resolved conflict records who resolved it and what was kept"),
    ("can a stored fact be traced to its source",
     "cited evidence exists in the record"),
    ("would alteration of a past entry be detectable",
     "a digest is the digest of the entries it covers"),
    ("can that be checked without the supplier",
     "the anchor's token is over this record's digest"),
)


def _fetch(url: str, timeout: int = 30, tries: int = 3) -> str:
    """Fetch a supplier's record, naming who is asking.

    A default Python user agent is refused outright by several content
    delivery networks, including the one in front of this project's own site,
    so a directory without this line reports every supplier as unreadable and
    blames them for it.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": "machine-testimony-directory/1.0 "
                      "(+https://machinetestimony.org/directory/)",
        "Accept": "text/plain, application/json, */*"})
    last = None
    for _ in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read().decode(
                "utf-8")
        except Exception as e:                              # noqa: BLE001
            last = e
    raise last


def read(entry: dict) -> dict:
    """What the validator says about the record this supplier published."""
    text = _fetch(entry["record"])
    rep = tv.validate(text).as_dict()
    by_name = {c["check"]: c for c in rep["checks"]}
    answers = []
    for question, check in ASKED:
        c = by_name.get(check)
        answers.append({"question": question,
                        "answered": bool(c and c["ok"]),
                        "basis": (c or {}).get("basis"),
                        "ran": c is not None})
    return {"level": rep["level"], "scope": rep["scope"],
            "basis": rep["basis"], "answers": answers,
            "entries": len(text.strip().split(chr(10)))}


def load() -> list:
    out = []
    if not os.path.isdir(SUBJECTS):
        return out
    for f in sorted(os.listdir(SUBJECTS)):
        if f.endswith(".json"):
            out.append(json.load(io.open(os.path.join(SUBJECTS, f),
                                         encoding="utf-8")))
    return out


def page(rows: list) -> str:
    w = []
    a = w.append
    a('<!--title: AI suppliers whose records answer the questions buyers ask')
    a('    desc: Suppliers who publish a Testimony Record from their own '
      'system, indexed by what the published validator says about it. Not a '
      'certification: the supplier publishes, the validator decides, and '
      'anybody can rerun it.')
    a('    slug: directory-->')
    a('<div class="wrap main">')
    a('  <div>')
    a('    <p class="dateline">A directory, not an assessment</p>')
    a('    <h2 class="label">Suppliers whose records answer the questions</h2>')
    a('    <div class="block">')
    a('      <p>The <a href="/register/">register</a> reads systems at pinned '
      'commits and reports what they cannot do. Nobody volunteers for that. '
      'This is the other side of it: a supplier publishes a record from their '
      'own system, at a URL they control, and this page reports what the '
      'validator says about it.</p>')
    a('      <p><b>Nothing here is assessed by this project.</b> The supplier '
      'publishes, the published validator produces the verdict, and the '
      'command that reproduces it is beside every row. A directory that graded '
      'submissions would be a certification body, which is a thing this '
      'project will not become.</p>')
    a('      <p><b>And it is one record the supplier chose.</b> It shows the '
      'system can produce one, which is the question a buyer asks and which '
      'most systems cannot answer at all. It is not evidence about every '
      'action the system has ever taken, and reading it as that would be the '
      'soft yes the <a href="/ask/">questions</a> exist to catch.</p>')
    a('    </div>')
    if not rows:
        a('    <div class="block">')
        a('      <p>No supplier has published one yet. The way in is a pull '
          'request adding a file to <span class="mono">census/suppliers/'
          '</span> with a name and a URL, and there is no fee, no form and '
          'nobody to ask.</p>')
        a('    </div>')
    for r in rows:
        e, v = r["entry"], r.get("read")
        a('    <h3>%s</h3>' % e["name"])
        if not v:
            a('      <p class="note">The record at <span class="mono">%s</span>'
              ' could not be fetched when this page was built, so nothing is '
              'claimed about it.</p>' % e["record"])
            continue
        a('      <p>Published at <a href="%s">%s</a>. The validator reports '
          '<b>%s</b> over %d entries, resting on %d checks a reader can settle '
          'and %d taken on the emitter&rsquo;s word.</p>'
          % (e["record"], e["record"], v["level"] or "no level", v["entries"],
             sum(b["verified"] for b in v["basis"].values()),
             sum(b["attested"] for b in v["basis"].values())))
        if e.get("note"):
            a('      <p class="note">%s</p>' % e["note"])
        a('      <table>')
        a('        <tr><th>The question</th><th>This record</th></tr>')
        for ans in v["answers"]:
            mark = ("yes" if ans["answered"]
                    else ("no" if ans["ran"] else "not applicable here"))
            a('        <tr><td>%s</td><td>%s</td></tr>' % (ans["question"],
                                                           mark))
        a('      </table>')
        a('      <pre class="snip">python3 spec/testimony_validate.py &lt;(curl -s %s)</pre>'
          % e["record"])
    a('  </div>')
    a('</div>')
    return chr(10).join(w) + chr(10)


def main() -> int:
    rows = []
    for entry in load():
        try:
            rows.append({"entry": entry, "read": read(entry)})
        except Exception as e:                              # noqa: BLE001
            print("  could not read %s: %s" % (entry.get("name"), str(e)[:60]))
            rows.append({"entry": entry, "read": None})
    if "--check" in sys.argv:
        bad = [r["entry"]["name"] for r in rows if not r["read"]]
        print("%d listed, %d unreadable" % (len(rows), len(bad)))
        return 1 if bad else 0
    out = os.path.join(ROOT, "pages", "directory.html")
    io.open(out, "w", encoding="utf-8", newline="").write(page(rows))
    print("wrote %s, %d supplier%s"
          % (os.path.relpath(out, ROOT), len(rows),
             "" if len(rows) == 1 else "s"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

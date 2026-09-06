#!/usr/bin/env python3
"""Render the standing register from the assessments.

    python3 census/build_register.py            # writes pages/register.html
    python3 build_page.py pages/register.html public/register/index.html

The census is a dated document about a moment. The register is the same
evidence as a standing surface: what each system records today, when each row
was last read, and what would change it. Both come from `subjects/`, so there
is one set of verdicts and two ways of looking at them rather than two sets
that can disagree.

Nothing here is written by hand. A verdict on the page that is not in a subject
file is impossible by construction, which matters more here than it does on an
ordinary page: this is the surface a vendor would object to.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import html
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import rubric      # noqa: E402
import subject     # noqa: E402

OUT = os.path.join(ROOT, "pages", "register.html")

# The date the next reading happens, and it is a commitment rather than a hope.
#
# A register that says "eight systems, read in September" is a document. One
# that names the next date is a clock, and a vendor sitting on an `absent` row
# has a reason to act before it. That only works if the date is kept, so
# tests_census.py fails once it has passed: either the reading happened and the
# date moves, or the promise is withdrawn deliberately. A page still promising a
# reading that was due in January is worse than a page that promised nothing.
NEXT_READING = "2027-01-15"

MARK = {"present": ("yes", "y"), "partial": ("part", "p"),
        "absent": ("no", "n"), "undetermined": ("undet", "u"), None: ("n/a", "x")}


def esc(s):
    return html.escape(str(s), quote=True)


def load():
    docs = subject.load_all(os.path.join(HERE, "subjects"))
    return sorted(docs, key=lambda d: d["name"].lower())


def last_read(doc) -> str:
    """The most recent reading of any part of this row.

    A single requirement can be re-read without the whole subject being
    re-assessed, and it was: R4.2 for OMEM on 5 September. Showing only the
    subject-level date would date the row to the last time everything was
    read, which is older than the truth and looks like the correction never
    happened.
    """
    dates = [doc.get("assessed_on", "")]
    dates += [a.get("reassessed_on", "") for a in doc["assessments"].values()
              if isinstance(a, dict)]
    return max(d for d in dates if d)


def verdict(doc, req):
    if not rubric.applicable(req, doc["claims"]):
        return None
    return (doc["assessments"].get(req.id) or {}).get("verdict")


def summary_row(doc):
    """met / applicable per level, which is what a reader scans first."""
    out = []
    for lvl in rubric.LEVEL_ORDER:
        met = app = 0
        for req in rubric.BY_LEVEL[lvl]:
            v = verdict(doc, req)
            if v is None:
                continue
            app += 1
            met += v == "present"
        out.append((lvl, met, app))
    return out


def main() -> int:
    # An output path, so the register can be regenerated somewhere else and
    # compared with what is committed. Regenerating over the top would leave a
    # failing check having already overwritten the evidence for it.
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    out_path = ap.parse_args().out

    docs = load()
    reached = {d["subject"]: subject.level_reached(d) for d in docs}
    manifest = json.load(io.open(os.path.join(HERE, "MANIFEST.json"),
                                 encoding="utf-8"))
    dates = sorted({last_read(d) for d in docs})

    b = []
    w = b.append
    # The title and description are metadata: they exist to match a query,
    # not to be read on the page, which takes its heading from the body below.
    w("<!--title: AI agent audit trail comparison: eight systems, "
      "twenty requirements")
    w("    desc: An audit trail comparison of eight AI agent systems: which "
      "record what, with every verdict citing a file and a line at a pinned "
      "commit. Updated rather than dated, and a wrong verdict is fixed by a "
      "pull request.")
    w("    slug: register-->")
    w("")
    w('<div class="wrap main">')
    w("  <div>")
    w('    <p class="dateline">Standing register, last read %s &middot; '
      'next reading %s</p>' % (esc(dates[-1]), esc(NEXT_READING)))
    w('    <h2 class="label">Which systems record what</h2>')
    w('    <div class="block">')

    w("      <p>%d systems, read against %d requirements drawn from the four "
      "conformance levels. Every verdict cites a file and a line at a pinned "
      "commit, and an <b>absent</b> verdict cites where the assessor looked "
      "and did not find it, which is the difference between a measurement and "
      "an accusation.</p>" % (len(docs), len(rubric.REQUIREMENTS)))

    w("      <p>This is not a certification and nobody applied for it. It is a "
      "reading of published source, and it is wrong in the ordinary way that "
      "readings are wrong. The remedy is below and it does not involve "
      "persuading anybody.</p>")

    # ── the summary table ───────────────────────────────────────────────────
    w('      <div class="scroller">')
    w('      <table class="reg">')
    w("        <thead><tr><th>System</th>"
      + "".join("<th>%s</th>" % esc(l) for l in rubric.LEVEL_ORDER)
      + "<th>Reaches</th><th>Read by</th><th>Last read</th></tr></thead>")
    w("        <tbody>")
    for d in docs:
        cells = []
        for lvl, met, app in summary_row(d):
            cells.append('<td class="n">%s</td>'
                         % ("%d/%d" % (met, app) if app else "n/a"))
        lv = reached[d["subject"]] or "none yet"
        own = d["subject"] == "omem"
        w('          <tr%s><td class="s">%s%s</td>%s<td class="lv">%s</td>'
          '<td class="d">%s</td><td class="d">%s</td></tr>'
          % (' class="own"' if own else "",
             esc(d["name"]),
             ' <span class="tag">the author\'s own</span>' if own else "",
             "".join(cells), esc(lv), esc(d["assessed_by"]),
             esc(last_read(d))))
    w("        </tbody>")
    w("      </table>")
    w("      </div>")

    w("      <p class=\"cont\">A count is met out of applicable. A system that "
      "does not act is not marked down for having no gate, and the requirements "
      "that do not apply to it are not counted against it.</p>")

    # ── the requirement everything turns on ─────────────────────────────────
    key = next((r for r in rubric.REQUIREMENTS
                if "approv" in r.question.lower() and "who" in r.question.lower()),
               None) or rubric.BY_LEVEL["TR-3"][0]
    w("      <h3>The question this started from</h3>")
    w("      <p><i>%s</i></p>" % esc(key.question))
    tally = {}
    for d in docs:
        v = verdict(d, key)
        tally[v] = tally.get(v, 0) + 1
    w('      <div class="scroller">')
    w('      <table class="reg">')
    w("        <thead><tr><th>System</th><th>%s</th><th>Where it was read</th>"
      "</tr></thead>" % esc(key.id))
    w("        <tbody>")
    for d in docs:
        a = d["assessments"].get(key.id) or {}
        v = verdict(d, key)
        ev = (a.get("evidence") or [{}])[0]
        where = ev.get("locator") or a.get("note") or ""
        w('          <tr><td class="s">%s</td><td class="v %s">%s</td>'
          '<td class="w">%s</td></tr>'
          % (esc(d["name"]), MARK[v][1], esc(MARK[v][0]), esc(where[:120])))
    w("        </tbody>")
    w("      </table>")
    w("      </div>")

    # ── the two doors ───────────────────────────────────────────────────────
    w("      <h3>If a verdict here is wrong</h3>")
    w("      <p>It is a file. Open a pull request against the subject file "
      "naming the requirement and where to look, or write to "
      "<code>troy@machinetestimony.com</code> with the same. A correction that "
      "lands changes the file, this page, and the date on the row. There is no "
      "fee, no membership, and no requirement to use any software of mine.</p>")
    w("      <p>Arguing with me is not the remedy and does not work. Pointing "
      "at code is, and has: this register carries corrections that came from "
      "being told I had read something wrong.</p>")

    # One name in every row is the honest state and the argument at once.
    readers = sorted({d["assessed_by"] for d in docs})
    w("      <h3>Who read these</h3>")
    if len(readers) == 1:
        w("      <p>All of them, %s, which is the weakest thing about this "
          "register. A reading nobody has repeated is one person's reading, "
          "however carefully it cites its sources.</p>" % esc(readers[0]))
    else:
        w("      <p>%s. A row read by somebody with no stake in the answer is "
          "worth more than a row read here.</p>" % esc(", ".join(readers)))
    w('      <p>The instrument is not reserved. The rubric is CC BY 4.0 and the '
      'tooling is MIT, commercial use included and expected: if you audit AI '
      'systems, or advise on Article 12 or Article 14, or have to answer a '
      'procurement question about what a supplier\'s agent records, you can run '
      'these questions yourself and bill for it without asking anybody. '
      '<a href="/assess/">How to do that</a>, including how to put the result '
      'here with your own name on the row, or keep it and publish it '
      'yourself.</p>')

    w("      <h3>The next reading is %s</h3>" % esc(NEXT_READING))
    w("      <p>Every row is read again on that date, against the same "
      "requirements, at whatever commit each project is at then. A row that is "
      "absent today is not absent permanently, and a row that passes today is "
      "not settled: this is a reading of software, and software moves.</p>")
    w("      <p><b>If you have changed something, you do not have to wait.</b> "
      "Say so and it is read before the date, the same way and against the "
      "same bar: a pull request against the subject file, or an email to "
      "<code>troy@machinetestimony.com</code> naming the requirement and where "
      "to look. There is no fee and no advantage to being first, beyond the "
      "row being right sooner.</p>")
    w("      <p>The date is not decoration. This page fails its own build once "
      "it has passed, so it either moves because the reading happened or it is "
      "withdrawn deliberately. A register still promising a reading that was "
      "due months ago is worth less than one that promised nothing.</p>")

    w("      <h3>If your system is not here</h3>")
    w("      <p>Being absent is not a judgement. It means nobody has done the "
      "reading yet. The rubric and the harness are in the repository, so you "
      "can run the questions against your own system before anybody else "
      "does, and the answer will be the same one I would get.</p>")

    w("      <h3>The conflict of interest</h3>")
    w("      <p>One row is the author's own implementation, of the format the "
      "questions derive from. It scores well here the way a dictionary's "
      "author spells well, and it carries no evidential weight. It is included "
      "so the questions are applied to the system that produced them before "
      "they are applied to anybody else's.</p>")
    w("      <p>That has not been costless. Five findings so far are recorded "
      "against this assessment, three of them against its author, including "
      "one after publication: on 5 September 2026 the top conformance level "
      "was found not to be checking what it claimed, and the author's own "
      "passing row was the one affected. It is written up in full rather than "
      "quietly repaired.</p>")

    w("      <h3>What a verdict rests on</h3>")
    w("      <p>Some of these questions a reader can settle from a record "
      "alone: whether cited evidence exists, whether a refused action is also "
      "recorded as executed, whether a digest is the digest of what it covers. "
      "Others are attestations, and no reading of source can confirm them: "
      "that a risk class really came from a registry, that an approver's name "
      "really came from the session it names. The specification marks the "
      "difference and the validator reports it, and a conformance claim that "
      "does not distinguish them is weaker than it looks.</p>")

    w("    </div>")
    w("  </div>")

    w('  <aside class="rail">')
    w('    <h2 class="label">This reading</h2>')
    w('    <p class="cont">%d systems, %d requirements.<br>Last read %s.<br>'
      'Digest <code>%s</code></p>'
      % (len(docs), len(rubric.REQUIREMENTS), esc(dates[-1]),
         esc((manifest.get("digest") or "")[:23] + "...")))
    w('    <h2 class="label">The dated edition</h2>')
    w('    <p class="cont">The September 2026 census is the same evidence as a '
      'document, with a DOI, for citing.<br>'
      '<a href="/census/2026-09/">Read it</a><br>'
      '<a href="https://doi.org/10.5281/zenodo.22290922">10.5281/zenodo.22290922</a></p>')
    w("    <hr>")
    w('    <p class="cont"><a href="/implement/">Implementing it</a><br>'
      '<a href="/check/">Check a record</a><br>'
      '<a href="https://github.com/troybrandonc-bit/machine-testimony/tree/main/census">'
      'The rubric and every subject file</a></p>')
    w("  </aside>")
    w("</div>")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(
        "\n".join(b) + "\n")
    print("wrote %s" % out_path)
    print("  %d systems, last read %s" % (len(docs), dates[-1]))
    for d in docs:
        print("    %-20s %-8s %s" % (d["name"], reached[d["subject"]] or "none",
                                     last_read(d)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

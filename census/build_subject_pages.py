#!/usr/bin/env python3
"""Render one page per assessed system, from the assessments.

    python3 census/build_subject_pages.py        # writes pages/subject-*.html
    python3 build_page.py pages/subject-omem.html public/register/omem/index.html

The register says which systems record what. It cannot say *why* any single
verdict is what it is, because a row has four columns and a verdict rests on
two or three citations. Until now that evidence existed only as JSON in the
repository, which means the most valuable thing the census owns, roughly two
hundred claims each carrying a file and a line, was invisible to anyone who
did not think to open a subject file on GitHub.

These pages are that evidence as a surface. One per system, every verdict with
its question, its reasoning and its citations, and every citation that names a
file and a line rendered as a link into the pinned commit. The point is to make
disagreeing cheap: a maintainer who thinks a verdict is wrong can click to the
exact lines it rests on and say so, rather than taking the register's word for
it or reverse-engineering the reasoning.

Nothing here is written by hand, for the same reason the register is not. A
claim on one of these pages that is not in a subject file is impossible by
construction.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import argparse
import html
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import rubric      # noqa: E402
import subject     # noqa: E402

OUTDIR = os.path.join(ROOT, "pages")

# A locator is `path/to/file.py:120` or `...:120-134`, sometimes with a symbol
# name after it (`types.py:20 MemoryRecord`). Anything else, a grep invocation
# most of all, is prose and is rendered as prose.
LOC = re.compile(r"^(?P<path>[\w./-]+\.[\w]+):(?P<a>\d+)(?:-(?P<b>\d+))?"
                 r"(?P<rest>\s.*)?$")

VERDICT_WORDS = {
    "present": "present",
    "partial": "partial",
    "absent": "absent",
    "undetermined": "undetermined",
    "not_applicable": "not applicable",
}


def esc(s):
    return html.escape(str(s), quote=True)


def blob(doc, locator):
    """A locator as a link into the pinned commit, or None if it is prose."""
    m = LOC.match(locator.strip())
    if not m or not doc.get("commit") or "github.com/" not in doc.get("url", ""):
        return None
    anchor = "#L" + m.group("a")
    if m.group("b"):
        anchor += "-L" + m.group("b")
    return "%s/blob/%s/%s%s" % (doc["url"].rstrip("/"), doc["commit"],
                                m.group("path"), anchor)


def paragraphs(text):
    return [p.strip() for p in str(text).split("\n\n") if p.strip()]


def levels(doc):
    out = []
    for lvl in rubric.LEVEL_ORDER:
        met = app = 0
        for req in rubric.BY_LEVEL[lvl]:
            if not rubric.applicable(req, doc["claims"]):
                continue
            app += 1
            met += (doc["assessments"].get(req.id) or {}).get(
                "verdict") == "present"
        out.append((lvl, met, app))
    return out


def tally(doc):
    c = {}
    for a in doc["assessments"].values():
        c[a["verdict"]] = c.get(a["verdict"], 0) + 1
    return c


def render(doc) -> str:
    b = []
    w = b.append
    name = doc["name"]
    short = (doc.get("commit") or "")[:7]
    t = tally(doc)
    counts = ", ".join("%d %s" % (t[k], VERDICT_WORDS[k])
                       for k in ("present", "partial", "absent",
                                 "undetermined")
                       if t.get(k))
    reached = subject.level_reached(doc)

    # Metadata, which exists to match a query rather than to be read. The
    # heading below is what a human sees, and the suite requires the two to
    # differ.
    w("<!--title: %s audit trail and approval records, assessed" % esc(name))
    w("    desc: %s read against %d record-keeping requirements at commit %s. "
      "%s. Every verdict cites a file and a line, and a wrong one is fixed by "
      "a pull request."
      % (esc(name), len(rubric.REQUIREMENTS), esc(short), esc(counts)))
    w("    slug: register/%s-->" % esc(doc["subject"]))
    w("")
    w('<div class="wrap main">')
    w("  <div>")
    w('    <p class="dateline">Assessment, %s &middot; %s</p>'
      % (esc(doc["assessed_on"]), esc(doc.get("version", ""))))
    w('    <h2 class="label">What %s records, and what it does not</h2>'
      % esc(name))
    w('    <div class="block">')

    # ── the facts a reader needs to reproduce this ──────────────────────────
    w('      <table class="facts">')
    w("        <tr><th>Read at</th><td>%s</td></tr>"
      % ('<a href="%s/tree/%s">%s</a>' % (esc(doc["url"].rstrip("/")),
                                          esc(doc["commit"]), esc(short))
         if doc.get("commit") else esc(doc.get("version", ""))))
    w("        <tr><th>Repository</th><td><a href=\"%s\">%s</a></td></tr>"
      % (esc(doc["url"]), esc(doc["url"].replace("https://", ""))))
    w("        <tr><th>Licence</th><td>%s</td></tr>" % esc(doc["license"]))
    w("        <tr><th>Assessed as</th><td>%s</td></tr>"
      % esc(", ".join(doc["claims"])))
    w("        <tr><th>Reaches</th><td>%s</td></tr>"
      % esc(reached or "no level yet"))
    w("        <tr><th>Read by</th><td>%s</td></tr>" % esc(doc["assessed_by"]))
    w("      </table>")

    # ── the scoreboard ─────────────────────────────────────────────────────
    w('      <div class="scroller">')
    w('      <table class="reg">')
    w("        <thead><tr><th>Level</th><th>Meets</th><th>What the level "
      "asks</th></tr></thead>")
    w("        <tbody>")
    for lvl, met, app in levels(doc):
        title, gloss = rubric.LEVELS[lvl]
        w('          <tr><td class="s">%s %s</td><td class="n">%s</td>'
          '<td class="w">%s</td></tr>'
          % (esc(lvl), esc(title),
             "%d/%d" % (met, app) if app else "n/a", esc(gloss)))
    w("        </tbody>")
    w("      </table>")
    w("      </div>")
    w("      <p>A count is requirements fully met out of those that apply. "
      "This system is assessed as <b>%s</b>, and requirements outside that "
      "are not counted against it.</p>" % esc(", ".join(doc["claims"])))

    # ── the assessor's own summary ─────────────────────────────────────────
    for i, p in enumerate(paragraphs(doc.get("notes", ""))):
        w('      <p%s>%s</p>' % (' class="callout"' if i == 0 else "", esc(p)))

    # ── every requirement, with its citations ──────────────────────────────
    w("      <h3>Every verdict, and what it rests on</h3>")
    w("      <p>Twenty requirements, each stated as a capability rather than a "
      "format, so a system that holds the information in its own shape counts "
      "as having it. An <b>absent</b> verdict cites where the assessor looked "
      "and did not find it, which is the difference between a measurement and "
      "an accusation.</p>")

    for lvl in rubric.LEVEL_ORDER:
        title, gloss = rubric.LEVELS[lvl]
        applicable = [r for r in rubric.BY_LEVEL[lvl]
                      if rubric.applicable(r, doc["claims"])]
        skipped = [r for r in rubric.BY_LEVEL[lvl] if r not in applicable]
        w("      <h3>%s %s</h3>" % (esc(lvl), esc(title)))
        w("      <p><i>%s</i></p>" % esc(gloss))
        for req in applicable:
            a = doc["assessments"].get(req.id) or {}
            v = a.get("verdict", "undetermined")
            w("      <p><b>%s &middot; %s.</b> %s</p>"
              % (esc(req.id), esc(VERDICT_WORDS.get(v, v)), esc(req.question)))
            if a.get("note"):
                w("      <p>%s</p>" % esc(a["note"]))
            if a.get("evidence"):
                w("      <ul>")
                for e in a["evidence"]:
                    href = blob(doc, e["locator"]) if e["kind"] != "searched" \
                        else None
                    loc = ('<a href="%s">%s</a>' % (esc(href), esc(e["locator"]))
                           if href else esc(e["locator"]))
                    w("        <li><b>%s</b> %s<br>%s</li>"
                      % (esc(e["kind"]), loc, esc(e["note"])))
                w("      </ul>")
        if skipped:
            w("      <p>%s %s not assessed here, because this system is not "
              "in that business and marking it down for that would be "
              "dishonest.</p>"
              % (esc(", ".join(r.id for r in skipped)),
                 "is" if len(skipped) == 1 else "are"))

    # ── how it was read, and how to say it is wrong ─────────────────────────
    w("      <h3>How this was read</h3>")
    w("      <p>%s</p>" % esc(doc["method"]))

    w("      <h3>If a verdict here is wrong</h3>")
    w("      <p>Then it is wrong in the ordinary way readings are wrong, and "
      "every verdict cites a file and a line at a pinned commit precisely so "
      "that being wrong is cheap to demonstrate. The remedy is a pull request "
      "against "
      "<a href=\"https://github.com/troybrandonc-bit/machine-testimony/blob/"
      "main/census/subjects/%s.json\">the subject file</a>, and it does not "
      "involve persuading anybody. Nobody applied for this and it is not a "
      "certification.</p>" % esc(doc["subject"]))
    w("      <p>The <a href=\"/register/\">standing register</a> carries every "
      "system side by side, and <a href=\"/assess/\">the rubric</a> is the "
      "twenty requirements in full, free to apply to anything, including to "
      "this assessment.</p>")

    w("    </div>")
    w("  </div>")
    w("</div>")
    return "\n".join(b) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", default=OUTDIR)
    outdir = ap.parse_args().outdir

    docs = sorted(subject.load_all(os.path.join(HERE, "subjects")),
                  key=lambda d: d["name"].lower())
    for d in docs:
        path = os.path.join(outdir, "subject-%s.html" % d["subject"])
        io.open(path, "w", encoding="utf-8", newline="\n").write(render(d))
        t = tally(d)
        print("  %-22s %s  (%s)"
              % (d["name"], os.path.relpath(path, ROOT),
                 " ".join("%s=%d" % (k, v) for k, v in sorted(t.items()))))
    print("%d subject pages" % len(docs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

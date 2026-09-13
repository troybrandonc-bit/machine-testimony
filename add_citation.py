"""Put a copy-paste citation on every page worth citing.

    python3 add_citation.py            # insert or refresh the blocks
    python3 add_citation.py --check    # fail if any page's block is stale

WHY THIS EXISTS. A reading that somebody wants to cite and cannot cite
without composing the reference themselves gets cited as "a website", or not
at all. The readings are CC BY, which already ASKS for attribution, so the
friction is entirely on our side: the licence requires the thing the page
does not make easy.

WHY IT IS GENERATED. The same reason the TR-3 profile is. A citation block
written by hand drifts from the page it describes the first time a date moves,
and a wrong date in a citation is worse than none because it propagates into
somebody else's bibliography where nobody will ever correct it. The title, the
slug and the date are read out of the page's own header comment.

WHAT IT DELIBERATELY DOES NOT DO. It does not invent a DOI. Pages whose
content is in a Zenodo deposit get the DOI; the rest cite the dated URL and
say so. Claiming a DOI a page does not have would be the exact failure this
project reports in other people's work.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "pages")

# Which deposit carries a page's content, where one does. A page absent from
# this map is not missing a DOI; it has none, and cites its dated URL instead.
DOI = {
    "register": "10.5281/zenodo.22290922",
    "named-approver": "10.5281/zenodo.22738449",
}

# The pages a stranger has a reason to cite: a reading of a text, or a
# measurement. Not the how-to pages, not the governance pages.
# `obligation` and `explaining` are deliberately ABSENT. Both are deposited on
# Zenodo as markdown regenerated from the page, and a test compares the two, so
# adding furniture to either page puts the deposit out of date and demands a new
# Zenodo version for a change that is not about the reading. They are also the
# two pages that least need this: both already display their DOI, which is the
# citation. The block is for pages where composing a reference is work.
CITED = ("register", "approval-binding", "aiuc-1", "named-approver",
         "colorado", "south-korea", "united-kingdom", "eu-ai-act", "tr-3",
         "formats", "demand", "united-states")

START = "<!--cite:start-->"
END = "<!--cite:end-->"

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def header(text: str) -> dict:
    """title, desc and slug out of the page's own comment header."""
    m = re.search(r"<!--title:\s*(.*?)\n\s*desc:\s*(.*?)\n\s*slug:\s*([a-z0-9-]+)-->",
                  text, re.S)
    if not m:
        return {}
    return {"title": " ".join(m.group(1).split()),
            "slug": m.group(3).strip()}


def dated(text: str) -> str:
    """The first date in the dateline, as a year, or empty."""
    m = re.search(r'<p class="dateline">(.*?)</p>', text, re.S)
    if not m:
        return ""
    d = re.search(r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})", m.group(1))
    if d:
        return "%s %s %s" % (d.group(1), d.group(2), d.group(3))
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", m.group(1))
    if iso:
        return "%d %s %s" % (int(iso.group(3)), MONTHS[int(iso.group(2)) - 1],
                             iso.group(1))
    return ""


def block(h: dict, when: str) -> str:
    slug, title = h["slug"], h["title"]
    url = "https://machinetestimony.org/%s/" % slug
    doi = DOI.get(slug)
    year = when.split()[-1] if when else "2026"
    # The title is the page's own, not a shortened one, because a citation
    # that does not match the page it points at is a citation somebody has to
    # check by hand.
    plain = ("Clifford, T. (%s). %s. Machine Testimony. %s"
             % (year, title.rstrip("."), doi and ("https://doi.org/" + doi) or url))
    key = "clifford%s%s" % (year, slug.replace("-", ""))
    bib = ["@misc{%s," % key,
           "  author = {Clifford, Troy},",
           "  title  = {%s}," % title.rstrip("."),
           "  year   = {%s}," % year,
           "  note   = {Machine Testimony%s}," % (when and (", read " + when) or ""),
           "  url    = {%s}," % url]
    if doi:
        bib.append("  doi    = {%s}," % doi)
    bib.append("}")

    lines = [START,
             '      <h3>Citing this</h3>',
             '      <p>The readings are CC BY 4.0, which asks for attribution,'
             ' so the reference is here rather than left to be composed. This'
             ' block is generated from the page it sits on, so a date that'
             ' moves here moves in the citation too.</p>',
             '      <pre class="snip"><code>%s</code></pre>' % plain,
             '      <pre class="snip"><code>%s</code></pre>' % "\n".join(bib)]
    if not doi:
        lines.append('      <p>This page carries no DOI. It cites its dated '
                     'URL, and saying so is the point: a citation naming a '
                     'deposit that does not exist is worse than one naming a '
                     'page that does.</p>')
    lines.append(END)
    return "\n".join(lines)


def apply(path: str, check: bool) -> str:
    text = io.open(path, encoding="utf-8").read()
    h = header(text)
    if not h:
        return "no header"
    want = block(h, dated(text))
    if START in text:
        cur = text[text.index(START):text.index(END) + len(END)]
        if cur == want:
            return ""
        if check:
            return "stale"
        text = text.replace(cur, want, 1)
    else:
        if check:
            return "missing"
        # Immediately before the last closing of the page's block, so it reads
        # as the last thing on the page rather than interrupting the argument.
        # Two page shapes exist: most close a nested block, a few end in
        # an <aside>. Both are handled rather than one being declared
        # the standard and the other quietly skipped.
        for tail in ("    </div>\n  </div>\n</div>",
                     "  </aside>\n</div>"):
            if tail in text:
                text = text.replace(tail, want + "\n" + tail, 1)
                break
        else:
            return "no insertion point"
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    return "written"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    problems, done = [], 0
    for slug in CITED:
        p = os.path.join(PAGES, slug + ".html")
        if not os.path.exists(p):
            problems.append("%s: no page" % slug)
            continue
        r = apply(p, a.check)
        if r in ("stale", "missing", "no header", "no insertion point"):
            problems.append("%s: %s" % (slug, r))
        elif r == "written":
            done += 1
    for x in problems:
        print("  " + x)
    if a.check:
        print("%d pages checked, %d stale or missing" % (len(CITED),
                                                         len(problems)))
        return 1 if problems else 0
    print("%d citation blocks written, %d problems" % (done, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

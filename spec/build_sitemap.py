"""Generate sitemap.xml from what is actually published.

    python3 build_sitemap.py            # write public/sitemap.xml
    python3 build_sitemap.py --check    # fail if it is stale

WHY THIS EXISTS. The sitemap was hand-maintained, so it rotted the way every
hand-maintained list of generated things rots. On 10 September 2026 it carried
19 URLs against 24 published pages, and the six missing ones were every page
built in the preceding two days: the Colorado reading, the United States
reading, the format matrix, the witness criteria, the TR-3 profile and the
directory.

Those are not incidental omissions. Colorado's ADMT Act applies on 1 January
2027, and the way a deployer meets this work is by searching for their
obligation in the weeks before that date. A page a crawler has never been told
about is a page that is not on the table at the only moment that matters.

There is no editorial judgement in a sitemap, which is exactly why it should
not be written by hand. llms.txt is the opposite case: its entries carry real
descriptions somebody had to write, so that file stays hand-written and a test
holds it complete instead.

PRIORITY AND CHANGEFREQ are hints a crawler is free to ignore, and this does not
pretend otherwise. The homepage is 1.0, a reading of an instrument that is in
force is 0.9 because it is the page somebody arrives at with a deadline, and
everything else is 0.7. Nothing here is a claim about importance to anybody but
this site.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(os.path.dirname(HERE), "public")
OUT = os.path.join(PUB, "sitemap.xml")
BASE = "https://machinetestimony.org"

# Directories that hold assets rather than pages a reader is sent to.
SKIP = {"brand"}

# The obligations with a date attached. A reader arrives at these because
# something is about to apply to them, which is the only reason a priority
# hint is set differently at all.
DEADLINE = {"colorado", "united-states", "eu-ai-act", "obligation", "tr-3"}

YEARLY = {"papers/wp1", "census/2026-09"}


def pages() -> list:
    """Every published page, found rather than listed."""
    out = []
    for root, dirs, files in os.walk(PUB):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
        if "index.html" not in files:
            continue
        rel = os.path.relpath(root, PUB).replace(os.sep, "/")
        out.append("" if rel == "." else rel)
    return sorted(out, key=lambda p: (p != "", p))


def entry(path: str) -> str:
    loc = BASE + "/" + (path + "/" if path else "")
    if not path:
        freq, pri = "monthly", "1.0"
    elif path in YEARLY:
        freq, pri = "yearly", "0.8"
    elif path in DEADLINE:
        freq, pri = "monthly", "0.9"
    else:
        freq, pri = "monthly", "0.7"
    return ("  <url>" + chr(10) +
            "    <loc>%s</loc>" % loc + chr(10) +
            "    <changefreq>%s</changefreq>" % freq + chr(10) +
            "    <priority>%s</priority>" % pri + chr(10) +
            "  </url>")


def build() -> str:
    body = chr(10).join(entry(p) for p in pages())
    return ('<?xml version="1.0" encoding="UTF-8"?>' + chr(10) +
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + chr(10) + body + chr(10) + "</urlset>" + chr(10))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    text = build()
    if a.check:
        have = io.open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if have != text:
            listed = set(re.findall(r"<loc>([^<]*)</loc>", have))
            want = {BASE + "/" + (x + "/" if x else "") for x in pages()}
            missing = sorted(want - listed)
            sys.stderr.write(
                "the sitemap is stale. Missing: %s%s"
                % (", ".join(missing) or "(ordering or hints changed)",
                   chr(10)))
            return 1
        print("sitemap is current: %d pages" % len(pages()))
        return 0
    io.open(OUT, "w", encoding="utf-8", newline=chr(10)).write(text)
    print("%d pages written to public/sitemap.xml" % len(pages()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

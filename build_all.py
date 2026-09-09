"""Rebuild every published page from its source, in the right order.

    python3 build_all.py
    python3 build_all.py --check    # rebuild and report what moved

`build_page.py` lifts the shell, the banner, the navigation and the footer from
`public/index.html`. So editing the homepage silently invalidates every other
page on the site, and nothing rebuilds them. On 9 September a one line
navigation change did exactly that and the suite failed twenty seven checks at
once, which is the suite working and the build story not existing.

This is the build story. It also encodes the ordering, which is not obvious and
was learned by getting it wrong:

  1. pages/*.html through build_page.py, EXCEPT the subject pages
  2. census/build_subject_pages.py, then those through build_page.py, because
     they live under /register/ and are generated from the assessments
  3. /check/ is not generated from pages/ at all. Its navigation has to be
     edited in place, and it is the shell /review/ is then built from
  4. spec/build_review_page.py and build_review_js.py, in that order

Point 3 is the ugly one and it is left ugly rather than papered over: /check/
carries hand-written JavaScript and a copy of the validator, so it is not a
`pages/` document. A future tidy would make it one. Until then this script
tells you when it has drifted rather than pretending it cannot.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "pages")
PUB = os.path.join(HERE, "public")

# `slug: anchor-->` needs the arrow stripped. Written greedily the first time,
# which produced sixteen directories called things like `anchor--`.
SLUG = re.compile(r"slug:\s*([a-z0-9/-]+?)-->")


def slug_of(path: str):
    m = SLUG.search(io.open(path, encoding="utf-8").read())
    return m.group(1) if m else None


def run(*args) -> bool:
    r = subprocess.run([sys.executable] + list(args), cwd=HERE,
                       capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stdout + r.stderr)
    return r.returncode == 0


def main() -> int:
    built, failed = 0, []

    ordinary = [f for f in sorted(os.listdir(PAGES))
                if f.endswith(".html") and not f.startswith("subject-")]
    for f in ordinary:
        src = os.path.join(PAGES, f)
        slug = slug_of(src)
        if not slug:
            failed.append(f + " (no slug)")
            continue
        out = os.path.join(PUB, slug, "index.html")
        built += 1 if run("build_page.py", src, out) else 0

    if not run(os.path.join("census", "build_subject_pages.py")):
        failed.append("build_subject_pages.py")
    for f in sorted(os.listdir(PAGES)):
        if not f.startswith("subject-"):
            continue
        src = os.path.join(PAGES, f)
        slug = slug_of(src)
        if slug:
            built += 1 if run("build_page.py", src,
                              os.path.join(PUB, slug, "index.html")) else 0

    # /check/ is not built from pages/. If the homepage navigation has moved,
    # /check/ has to be edited by hand and /review/ rebuilt from it, so this
    # says so rather than leaving it to a failing suite an hour later.
    def nav(text):
        a = text.index('<nav class="primary">')
        return re.sub(r"\s+", " ", text[a:text.index("</nav>", a)]).strip()

    home = nav(io.open(os.path.join(PUB, "index.html"),
                       encoding="utf-8").read()).replace('href="#', 'href="/#')
    chk = nav(io.open(os.path.join(PUB, "check", "index.html"),
                      encoding="utf-8").read())
    if chk != home:
        failed.append("/check/ navigation has drifted from the homepage. "
                      "Edit public/check/index.html by hand, then rerun, "
                      "because /review/ is built from its shell.")

    for s in ("build_review_page.py", "build_review_js.py"):
        if not run(os.path.join("spec", s)):
            failed.append(s)

    print("rebuilt %d pages" % built)
    for f in failed:
        print("  PROBLEM: %s" % f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

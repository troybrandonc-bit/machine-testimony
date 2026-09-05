"""The site says things that have to stay true.

Run: python3 tests_pages.py

Two kinds of check.

The published reference record and its token are an evidential claim, not
decoration, and /anchor/ prints the exact commands a stranger is invited to
run. Those commands are extracted from the page and executed here, so the
instructions cannot drift from the files they act on. A page that tells
somebody to run something that no longer works is worse than no page.

The rest is the ordinary rot a hand-built site accumulates. Internal links
that point at nothing. A navigation bar that has quietly gained a duplicate,
which every sub-page had until today, because the generator that composed them
lived outside the repository where nobody could see it disagreeing with the
homepage.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
import html
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PUB = os.path.join(ROOT, "public")
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_validate as tv        # noqa: E402

PASS = FAIL = 0

CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
    "/mingw64/etc/ssl/certs/ca-bundle.crt",
    "C:/Program Files/Git/mingw64/etc/ssl/certs/ca-bundle.crt",
)


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:240])


def pages():
    for dirpath, _, files in os.walk(PUB):
        for f in files:
            if f == "index.html":
                yield os.path.join(dirpath, f)


def snippets(page_html):
    return [html.unescape(m) for m in
            re.findall(r'<pre class="snip">(.*?)</pre>', page_html, re.S)]


def main():
    anchor = io.open(os.path.join(PUB, "anchor", "index.html"),
                     encoding="utf-8").read()
    rec_path = os.path.join(PUB, "anchor", "record.jsonl")
    tsr_path = os.path.join(PUB, "anchor", "anchor.tsr")

    print("the published record is what the page says it is")
    text = io.open(rec_path, encoding="utf-8").read()
    r = tv.validate(text)
    check("it reaches TR-4", r.level == "TR-4",
          [c["check"] for c in r.failures("TR-4")])

    entries = [__import__("json").loads(x) for x in text.splitlines() if x.strip()]
    g = [e for e in entries if e["type"] == "integrity"][0]
    check("the page quotes the record's own digest", g["digest"] in anchor,
          g["digest"])
    check("the page quotes the record's own authority",
          g["anchor"]["authority"] in anchor)
    check("the page quotes the time the authority signed",
          g["anchor"]["anchored_at"] in anchor)
    check("the page counts the entries the digest covers",
          "%d entries" % len(g["covers"]) in anchor, len(g["covers"]))

    print("\nthe commands the page prints are the commands that work")
    snips = snippets(anchor)
    check("the page prints three commands and their expected output",
          len(snips) >= 4, "%d snippets" % len(snips))

    work = tempfile.mkdtemp()
    shutil.copy(rec_path, os.path.join(work, "record.jsonl"))
    shutil.copy(tsr_path, os.path.join(work, "anchor.tsr"))
    want = g["digest"].split(":", 1)[1]

    # One: the recomputation, run exactly as printed.
    recompute = next((s for s in snips if "hashlib" in s), None)
    if recompute is None:
        check("the page still prints a way to recompute the digest", False)
    else:
        body = re.sub(r"^python3 -c '", "", recompute.strip()).rstrip("'")
        out = subprocess.run([sys.executable, "-c", body], cwd=work,
                             capture_output=True, text=True)
        check("the page's own recomputation reproduces the digest",
              out.stdout.strip() == want,
              (out.stdout.strip() or out.stderr.strip())[:120])

    if not shutil.which("openssl"):
        print("  NOT VERIFIED: openssl is absent, so the two commands the page "
              "gives a reader were not run")
    else:
        reply = next((s for s in snips if "ts -reply" in s), "")
        out = subprocess.run(reply.strip().split(), cwd=work,
                             capture_output=True, text=True)
        check("openssl reads the token, as the page says it will",
              out.returncode == 0 and "Status: Granted" in out.stdout,
              (out.stderr or "").strip()[:120])

        verify = next((s for s in snips if "ts -verify" in s), "")
        ca = next((p for p in CA_BUNDLES if os.path.exists(p)), None)
        if ca is None:
            print("  NOT VERIFIED: no system certificate store found here, so "
                  "the signature was not checked against public roots")
        else:
            # The page names a Debian path. A reader on another system uses
            # their own store, which is the point, so the test uses whichever
            # it finds rather than pretending the literal path is portable.
            args = verify.replace("\\\n", " ").split()
            args = [ca if a.endswith(".crt") and "/ssl/" in a else a
                    for a in args]
            out = subprocess.run(args, cwd=work, capture_output=True, text=True)
            joined = (out.stdout + out.stderr)
            check("the signature verifies against a public root",
                  "Verification: OK" in joined, joined.strip()[:160])
            check("the page's digest is the one the reader is told to check",
                  want in " ".join(args))

    print("\nthe check page reads a record, not only grades it")
    # The format was written for somebody who has to answer for a system they
    # did not build, and that person does not read JSON Lines. The reader is
    # the only part of the site aimed at them rather than at an implementer.
    chk = io.open(os.path.join(PUB, "check", "index.html"),
                  encoding="utf-8").read()
    check("it has a reader", "function readable(" in chk
          and "function sentence(" in chk)
    check("reading is the default view, not the checks",
          'id="v-read"' in chk and 'id="v-checks" hidden' in chk)
    check("a refusal is marked rather than blended in",
          "tr.refused" in chk and 'refused ? "REFUSED ' in chk)
    check("an approval says where the name came from",
          "identity from " in chk)
    # A type the reader does not know renders as a bare word with no sentence.
    # Adding one to the specification without teaching the reader is silent,
    # so it is checked here rather than noticed by an auditor.
    known = set(re.findall(r'case "([a-z]+)":', chk))
    missing = sorted(tv.TYPES - known)
    check("every entry type the specification defines has a sentence",
          not missing, "no case for: %s" % missing)

    print("\nthe site does not link at things that are not there")
    dead = []
    for page in pages():
        s = io.open(page, encoding="utf-8").read()
        ids = set(re.findall(r'id="([^"]+)"', s))
        for href in re.findall(r'href="(/[^"#]*)(#[^"]*)?"', s):
            path, frag = href[0], href[1]
            target = os.path.join(PUB, path.strip("/").replace("/", os.sep))
            if os.path.isdir(target):
                target = os.path.join(target, "index.html")
            elif path.endswith("/"):
                target = os.path.join(target, "index.html")
            if not os.path.exists(target):
                dead.append("%s -> %s" % (os.path.relpath(page, PUB), path))
        for frag in re.findall(r'href="#([^"]+)"', s):
            if frag not in ids:
                dead.append("%s -> #%s" % (os.path.relpath(page, PUB), frag))
    check("every internal link resolves", not dead, "; ".join(sorted(set(dead))[:4]))

    print("\nevery page carries the same navigation")
    def nav(s):
        a = s.index('<nav class="primary">')
        return re.sub(r"\s+", " ", s[a:s.index("</nav>", a)]).strip()

    # A sub-page rewrites the homepage's page-local anchors to absolute ones,
    # which is the one difference that is meant to be there.
    home = nav(io.open(os.path.join(PUB, "index.html"), encoding="utf-8").read())
    home = home.replace('href="#', 'href="/#')
    odd = []
    for page in pages():
        if os.path.dirname(page) == PUB:
            continue
        s = io.open(page, encoding="utf-8").read()
        try:
            if nav(s) != home:
                odd.append(os.path.relpath(page, PUB))
        except ValueError:
            odd.append(os.path.relpath(page, PUB) + " (no nav)")
    check("no page has drifted from the homepage's navigation", not odd,
          "; ".join(odd[:4]))

    print("\nevery generated page is what its source produces")
    # Anything in pages/ is built by build_page.py. A generated page that has
    # been hand-edited loses the edit the next time anybody rebuilds, so the
    # divergence is a defect rather than a matter of taste.
    srcdir = os.path.join(ROOT, "pages")
    for src in sorted(os.listdir(srcdir)):
        if not src.endswith(".html"):
            continue
        slug = ""
        for line in io.open(os.path.join(srcdir, src), encoding="utf-8"):
            if "slug:" in line:
                slug = line.split("slug:", 1)[1].strip().rstrip(">").rstrip("-")
                slug = slug.strip()
                break
        live = os.path.join(PUB, slug, "index.html")
        out = os.path.join(work, slug + ".html")
        built = subprocess.run(
            [sys.executable, os.path.join(ROOT, "build_page.py"),
             os.path.join(srcdir, src), out], capture_output=True, text=True)
        made = io.open(out, encoding="utf-8").read() \
            if built.returncode == 0 else ""
        have = io.open(live, encoding="utf-8").read() \
            if os.path.exists(live) else ""
        check("/%s/ rebuilds to exactly what is published" % slug,
              bool(made) and made == have,
              "regenerate with build_page.py" if made else built.stderr[:120])

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

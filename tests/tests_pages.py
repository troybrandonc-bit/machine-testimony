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

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import collections
import glob
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PUB = os.path.join(ROOT, "public")
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_validate as tv        # noqa: E402

PASS = FAIL = 0

# Deposited documents, frozen to match what Zenodo serves under a DOI. They are
# archived artefacts rather than pages of the site: the navigation they carry is
# part of what was deposited, so they are exempt from the rebuild check and from
# the navigation check alike. Regenerating one to pick up a new nav link would
# make the live copy differ from the deposit, which is the failure both checks
# exist to prevent.
DEPOSITED = {
    "census/2026-09",   # doi:10.5281/zenodo.22290922
    "papers/wp1",       # doi:10.5281/zenodo.22286050
}

CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
    "/mingw64/etc/ssl/certs/ca-bundle.crt",
    "C:/Program Files/Git/mingw64/etc/ssl/certs/ca-bundle.crt",
)


def fetch(url, timeout=45, tries=3):
    """A network read with retries, because the network is allowed one bad day.

    The DOI checks resolve a record held by CERN. Failing a pull request
    because Zenodo was slow reports nothing about the repository, and passing
    quietly would be worse, so the retry sits between the two: three attempts,
    and only then the honest NOT VERIFIED.
    """
    import urllib.request        # imported here: the module-level scope has no
                                 # urllib, it is pulled in inside main()
    last = None
    for n in range(tries):
        try:
            return urllib.request.urlopen(url, timeout=timeout).read()
        except Exception as e:                                  # noqa: BLE001
            last = e
            if n + 1 < tries:
                time.sleep(3)
    raise last


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
    print("")
    print("every assessed system has a page, and it says what the file says")
    # These pages are the census's evidence as a surface: roughly two hundred
    # claims that until now existed only as JSON in the repository. The failure
    # that matters is a page disagreeing with the subject file it was built
    # from, or a subject gaining no page after being added, so both are
    # recomputed here rather than trusted.
    sdir = os.path.join(ROOT, "census", "subjects")
    subjects = {}
    for f in sorted(os.listdir(sdir)):
        if f.endswith(".json"):
            d = json.load(io.open(os.path.join(sdir, f), encoding="utf-8"))
            subjects[d["subject"]] = d
    for slug, d in sorted(subjects.items()):
        live = os.path.join(PUB, "register", slug, "index.html")
        here = os.path.exists(live)
        check("/register/%s/ exists" % slug, here)
        if not here:
            continue
        page = io.open(live, encoding="utf-8").read()
        # Every verdict in the file appears on the page against its own
        # requirement id, so a page cannot quietly soften one.
        wrong = []
        for rid, a in d["assessments"].items():
            word = a["verdict"].replace("_", " ")
            if ("%s &middot; %s." % (rid, word)) not in page:
                wrong.append("%s=%s" % (rid, a["verdict"]))
        check("  %s carries every verdict from its file" % slug,
              not wrong, wrong)
        # A cited line is only worth citing if it points at the commit read.
        cites = [e for a in d["assessments"].values()
                 for e in a.get("evidence", []) if e["kind"] != "searched"]
        if d.get("commit") and cites:
            check("  %s links its citations at the pinned commit" % slug,
                  ("/blob/%s/" % d["commit"]) in page, d["commit"][:12])
        # The register exists to be believed by someone who owes the author
        # nothing, so a page about somebody else's software does not mention
        # the author's product.
        check("  %s names no product the author is selling" % slug,
              slug == "omem" or "OMEM" not in page)

    reg = io.open(os.path.join(PUB, "register", "index.html"),
                  encoding="utf-8").read()
    missing = [s for s in sorted(subjects)
               if 'href="/register/%s/"' % s not in reg]
    check("the register links to every system's page", not missing, missing)
    # This said "eight systems" for two subjects longer than it was true. Every
    # number in the body is recomputed by this suite; nothing looked at the
    # metadata, which is the half a search engine reads.
    words = {8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
    want = words.get(len(subjects), str(len(subjects)))
    head = reg[:reg.index("</head>")]
    check("the register's own metadata counts the systems it has",
          ("%s systems" % want) in head
          and not any(("%s systems" % w) in head
                      for k, w in words.items() if k != len(subjects)),
          want)
    print("")
    print("llms.txt counts what the census found")
    # The third hand-typed count to go stale in this repository, after the
    # underwriting rows and the register's own metadata. This file is the one a
    # language model reads and quotes, so a wrong number here is repeated by
    # something that will not check it.
    llms = io.open(os.path.join(PUB, "llms.txt"), encoding="utf-8").read()
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
             7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven"}
    r35 = [(d["assessments"].get("R3.5") or {}).get("verdict")
           for d in subjects.values()]
    r35 = [v for v in r35 if v]
    cannot, applicable = r35.count("absent"), len(r35)
    want = ("%s of the %s assessed systems that take actions could not say "
            "which person approved one"
            % (words[cannot].capitalize(), words[applicable]))
    check("the approval sentence matches the assessments", want in llms,
          want)
    # And every page it points at is a page that exists.
    import re as _re
    linked = set(_re.findall(r"https://machinetestimony\.org/([a-z0-9/-]+)/",
                             llms))
    gone = sorted(p for p in linked
                  if not os.path.exists(os.path.join(PUB, *p.split("/"),
                                                     "index.html")))
    check("every machinetestimony.org page it names exists", not gone, gone)
    print("")
    print("no page quotes a census tally that has moved")
    # The fourth stale hand-typed count found in this repository. This one sat
    # two paragraphs below a sentence promising that the counts on the page are
    # recomputed by the test suite rather than typed, which was true of that
    # page's own counts and not of the census tally it quoted.
    #
    # Rather than guard the one sentence, this sweeps every published page for
    # the shape of the claim, so the next one is caught wherever somebody
    # writes it.
    import re as _re
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
             7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
             12: "twelve"}
    acting = [(d["assessments"].get("R3.5") or {}).get("verdict")
              for d in subjects.values()]
    acting = [v for v in acting if v]
    want_acting = words.get(len(acting), str(len(acting)))
    want_total = words.get(len(subjects), str(len(subjects)))

    # `/census/2026-09/` is a dated document with a DOI. It assessed eight
    # systems and it always will have, so it is excluded deliberately rather
    # than by accident.
    DATED = {os.path.join("census", "2026-09")}
    shape = _re.compile(
        r"(\w+)\s+(?:assessed\s+)?systems?\s+(?:there\s+)?that\s+take\s+or\s+gate",
        _re.I)
    bad = []
    for base, _dirs, files in os.walk(PUB):
        rel = os.path.relpath(base, PUB)
        if rel in DATED or any(rel.startswith(d + os.sep) for d in DATED):
            continue
        if "index.html" not in files:
            continue
        page = io.open(os.path.join(base, "index.html"),
                       encoding="utf-8").read()
        for found in shape.findall(page):
            if found.lower() not in (want_acting, str(len(acting))):
                bad.append("/%s/ says %r, census says %r"
                           % (rel.replace(os.sep, "/"), found, want_acting))
    check("every page agrees on how many systems take or gate actions",
          not bad, bad)

    # The same for the plain total, which is the other number pages quote.
    shape2 = _re.compile(r"(\w+)\s+(?:widely deployed\s+)?agent systems were",
                         _re.I)
    bad2 = []
    for base, _dirs, files in os.walk(PUB):
        rel = os.path.relpath(base, PUB)
        if rel in DATED or any(rel.startswith(d + os.sep) for d in DATED):
            continue
        if "index.html" not in files:
            continue
        page = io.open(os.path.join(base, "index.html"),
                       encoding="utf-8").read()
        for found in shape2.findall(page):
            if found.lower() not in (want_total, str(len(subjects))):
                bad2.append("/%s/ says %r, census has %r"
                            % (rel.replace(os.sep, "/"), found, want_total))
    check("every page agrees on how many systems were assessed",
          not bad2, bad2)

    # The published pages were swept and the adapters were not, so the
    # pydantic-ai adapter and its readme went on quoting eight systems and four
    # that could not, months after the census had grown to ten and six. They
    # are prose a reader meets before they ever reach the register, and they
    # link straight to it, so a reader who follows the link finds different
    # numbers. Same two shapes, swept over the same tree the adapters live in.
    bad3 = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "adapters")):
        for f in files:
            if not f.endswith((".py", ".md")):
                continue
            rel = os.path.relpath(os.path.join(base, f), ROOT)
            text = io.open(os.path.join(base, f), encoding="utf-8").read()
            for found in shape.findall(text):
                if found.lower() not in (want_acting, str(len(acting))):
                    bad3.append("%s says %r act, census says %r"
                                % (rel.replace(os.sep, "/"), found,
                                   want_acting))
            for found in shape2.findall(text):
                if found.lower() not in (want_total, str(len(subjects))):
                    bad3.append("%s says %r assessed, census has %r"
                                % (rel.replace(os.sep, "/"), found, want_total))
    check("every adapter agrees with the census it cites", not bad3, bad3)
    print("")
    print("every page that counts the corpus counts it correctly")
    # The fifth hand-typed count in this repository, and the first one caught
    # before it shipped rather than after. The corpus size appeared nine times
    # across the implement page, the conformance readme and llms.txt, and
    # nothing compared any of them to the corpus.
    expected = json.load(io.open(
        os.path.join(ROOT, "conformance", "expected.json"), encoding="utf-8"))
    n = len(expected)
    cases = len([f for f in os.listdir(
        os.path.join(ROOT, "conformance", "cases")) if f.endswith(".jsonl")])
    check("the corpus has one case file per expected verdict", n == cases,
          "%d verdicts, %d files" % (n, cases))

    import re as _re
    # Only the total, and only where a page states it as the size of the
    # corpus. The readme also breaks the corpus down by level, and those are
    # checked separately below rather than swept up as wrong totals.
    stale = []
    for where in (os.path.join(PUB, "implement", "index.html"),
                  os.path.join(PUB, "llms.txt")):
        if not os.path.exists(where):
            continue
        text = io.open(where, encoding="utf-8").read()
        for found in _re.findall(r"(\d+)\s+(?:records?|cases)", text):
            if int(found) != n:
                stale.append("%s says %s, corpus has %d"
                             % (os.path.basename(where), found, n))
    check("no page states a corpus size the corpus does not have",
          not stale, stale)

    # The readme's per-level table, recomputed. A breakdown that no longer sums
    # to the corpus is the same defect one level down.
    import collections as _c
    by_level = _c.Counter(v["level"] for v in expected.values())
    readme = io.open(os.path.join(ROOT, "conformance", "README.md"),
                     encoding="utf-8").read()
    wrong = []
    for level, want in (("no level", by_level[None]), ("TR-1", by_level["TR-1"]),
                        ("TR-2", by_level["TR-2"]), ("TR-3", by_level["TR-3"]),
                        ("TR-4", by_level["TR-4"])):
        m = _re.search(r"\|\s*%s\s*\|\s*(\d+) cases" % _re.escape(level),
                       readme)
        if not m:
            wrong.append("%s: no row" % level)
        elif int(m.group(1)) != want:
            wrong.append("%s says %s, corpus has %d"
                         % (level, m.group(1), want))
    check("the corpus readme's breakdown by level is what the corpus holds",
          not wrong, wrong)




    print("\nthe underwriting page counts what the census actually found")
    # Every number on that page is a claim to an underwriter about eight named
    # products. It is recomputed here from the assessments rather than trusted,
    # because the register is re-read on a schedule and a verdict that moves
    # would otherwise leave a stale count in front of somebody pricing risk.
    uw = io.open(os.path.join(PUB, "underwriting", "index.html"),
                 encoding="utf-8").read()
    subs = {}
    sdir = os.path.join(ROOT, "census", "subjects")
    for f in sorted(os.listdir(sdir)):
        if f.endswith(".json"):
            s = json.load(io.open(os.path.join(sdir, f), encoding="utf-8"))
            subs[s["name"]] = {k: v["verdict"]
                               for k, v in s["assessments"].items()}
    check("the page speaks for every subject in the register",
          len(subs) == 10, len(subs))

    def tally(req):
        vs = [v.get(req, "not_applicable") for v in subs.values()]
        n = [v for v in vs if v != "not_applicable"]
        return (len(n), n.count("present"), n.count("partial"),
                n.count("absent"), n.count("undetermined"))

    # (requirement, the row's six numbers as written on the page)
    ROWS = [("R3.5", (8, 1, 0, 6, 1)), ("R3.6", (8, 1, 0, 6, 1)),
            ("R3.7", (8, 1, 0, 6, 1)), ("R3.1", (8, 5, 3, 0, 0)),
            ("R3.3", (8, 4, 4, 0, 0)), ("R3.4", (8, 2, 4, 2, 0)),
            ("R1.2", (10, 5, 3, 2, 0)), ("R2.1", (10, 2, 6, 2, 0))]
    for req, want in ROWS:
        check("the %s row is what the assessments say" % req,
              tally(req) == want, "page says %s, census says %s"
              % (want, tally(req)))

    # The two sentences the page puts in a callout, which is where a reader
    # who reads nothing else will look.
    n_acts, can, _, _, undet = tally("R3.5")
    check("one of eight acting systems can name an approver, as claimed",
          (n_acts, can, undet) == (8, 1, 1), (n_acts, can, undet))
    check("and the page says so in those words",
          "one can name the person who approved an action" in uw)
    tot, ver, _, _, _ = tally("R4.2")
    check("eight of ten cannot be verified without the vendor, as claimed",
          (tot, tot - ver) == (10, 8), (tot, ver))
    check("and the page says so in those words",
          "eight produce records\n        that cannot be verified without the "
          "vendor" in uw or "eight produce records" in uw)
    check("it points at the register rather than asking to be believed",
          'href="/register/"' in uw and 'href="/assess/"' in uw)
    check("and it names no product it is selling",
          "OMEM" not in uw and "omem" not in uw.lower())

    # This page quoted Zhu twice without attribution until machine-testimony#55,
    # and it is read by the people it quotes. It now also quotes Armilla on why
    # applications get declined. A quote separated from its source by a later
    # copy edit is the same defect again, so each one is tied to the name and
    # the link here rather than to somebody remembering.
    #
    # Searched over whitespace-flattened HTML, because a quoted sentence wraps
    # across source lines and neither of these phrases occurs contiguously in
    # the file. Written the naive way first, this guard passed by finding
    # nothing, which is the failure mode a guard is supposed to prevent.
    flat = _re.sub(r"\s+", " ", uw)
    QUOTED = [("too thin to support risk transfer", "Philip Dawson",
               "armilla.ai/resources/"),
              ("where reasonably available", "Zhu", "arxiv.org")]
    seen_quote = False
    for phrase, who, link in QUOTED:
        if phrase in flat:
            seen_quote = True
            check("the %r quote is still attributed to %s" % (phrase[:28], who),
                  who in flat and link in flat,
                  "name present: %s, link present: %s"
                  % (who in flat, link in flat))
    check("the page still quotes somebody, so the guard above ran",
          seen_quote, "no known quotation found: the attribution guard is dead")


    print("\nno summary of the obligation reading outranks its own table")
    # The reading found that the Act requires the approver's identity exactly
    # once, for Annex III point 1(a), and its table has carried `partial` for
    # that cell since the correction. The title, the heading, the meta
    # description and the llms.txt entry all still said nobody requires it,
    # and those are what a search result, a social card and an assistant
    # actually quote. The careful paragraph was four screens below.
    #
    # A summary that contradicts the table it summarises is the failure this
    # whole project is about, committed on its own site, so it is checked
    # rather than remembered.
    ob = io.open(os.path.join(PUB, "obligation", "index.html"),
                 encoding="utf-8").read()
    surfaces = [("the obligation page", ob)]
    lp = os.path.join(PUB, "llms.txt")
    if os.path.exists(lp):
        surfaces.append(("llms.txt", io.open(lp, encoding="utf-8").read()))

    ABSOLUTES = ("Nobody requires it to name who approved",
                 "None requires it to say who authorised",
                 "no requirement that the record say which person")
    for what, text in surfaces:
        hits = [a for a in ABSOLUTES if a in text]
        check("%s does not claim nobody requires the approver" % what,
              not hits, hits)

    # The guard above looks for the OLD wording and found nothing, which is how
    # a botched replacement passed it. Correcting the llms.txt entry prefixed the
    # new title onto a line that still carried the old lead, so line 50 read
    # "Everyone requires the log. Everyone requires the log. One row of Annex
    # III...". impartshadow read it live and reported it; no check here had any
    # opinion about it, because absence of the wrong sentence is not presence of
    # a right one.
    #
    # llms.txt is the surface a model quotes without ever seeing the table, so a
    # mangled line there travels further than one on the page.
    if os.path.exists(lp):
        txt = io.open(lp, encoding="utf-8").read()
        dupes = []
        for line in txt.split(chr(10)):
            head = line.split("](")[0].lstrip("- [")
            if len(head) < 12 or len(head) > 200:
                continue
            for end in (". ", "? "):
                first = head.split(end)[0] + end.strip()
                if len(first) > 10 and head.count(first) > 1:
                    dupes.append(first)
        check("no llms.txt title repeats its own opening sentence",
              not dupes, dupes)

    # And the cell those summaries were contradicting is still what it says.
    check("the reading still records the Act as partial, not absent",
          "partial" in ob, "the table no longer says partial anywhere")

    print("\nthe Colorado reading quotes the act it cites")
    # /colorado/ rests entirely on five quotations from a signed statute and a
    # claim about three words the act does NOT contain. Both halves are cheap to
    # get wrong in an edit and expensive to be wrong about in public, and the
    # source is a PDF nobody is going to re-read by hand. The extracted text is
    # committed beside the page for exactly that reason.
    #
    # Page furniture is stripped before comparing: the signed PDF breaks pages
    # mid-sentence and prints "PAGE 10-SENATE BILL 26-189" inside the retention
    # provision, which made the first run of this check report a correct quote
    # as a misquote.
    co_src = os.path.join(ROOT, "census", "sources", "co-sb26-189.txt")
    co_page = os.path.join(PUB, "colorado", "index.html")
    if os.path.exists(co_src) and os.path.exists(co_page):
        act = _re.sub(r"\s+", " ",
                      io.open(co_src, encoding="utf-8").read())
        act = _re.sub(r"PAGE\s*\d+\s*-\s*SENA\s*TE\s*BILL\s*26-189",
                      "", act)
        act = _re.sub(r"\s+", " ", act)
        page = io.open(co_page, encoding="utf-8").read()
        quoted = _re.findall(r"&ldquo;([A-Z][^&]{10,400})&rdquo;", page)
        bad = []
        for q in quoted:
            q = _re.sub(r"<[^>]+>", "", q)
            for part in [x.strip() for x in
                         _re.sub(r"\s+", " ", q).split("...")]:
                if part and part not in act:
                    bad.append(part[:60])
        check("every quotation on /colorado/ is in the signed act",
              quoted and not bad, bad)

        # The finding is partly an absence, so the absence is checked too.
        present = [w for w in ("REVIEWER", "NATURAL PERSON")
                   if w in act.upper()]
        check("the words the page says are absent are still absent",
              not present, present)

    print("\nthe United States reading counts what the texts contain")
    # /united-states/ rests on four word counts over the Local Law 144 text,
    # and the whole argument turns on two of them being small: record once, and
    # retain not at all. A typed count is the fourth kind of stale number this
    # repository has had, so it is recomputed from the committed source rather
    # than trusted.
    us_page = os.path.join(PUB, "united-states", "index.html")
    ll144 = os.path.join(ROOT, "census", "sources", "nyc-ll144.txt")
    if os.path.exists(us_page) and os.path.exists(ll144):
        text = _re.sub(r"\s+", " ",
                       io.open(ll144, encoding="utf-8").read())
        page = io.open(us_page, encoding="utf-8").read()
        wrong = []
        for word in ("audit", "notice", "record", "retain"):
            n = len(_re.findall(r"\b" + word, text, _re.I))
            claim = _re.search(
                r"<span class=\"mono\">" + word
                + r"</span>[^<]{0,40}?(\d+|does not occur|once)",
                page, _re.I)
            if not claim:
                continue
            said = claim.group(1).lower()
            got = {"once": 1, "does not occur": 0}.get(said, None)
            got = int(said) if got is None and said.isdigit() else got
            if got is not None and got != n:
                wrong.append("%s: page says %s, text has %d"
                             % (word, said, n))
        check("every Local Law 144 count on /united-states/ is what the"
              " text holds", not wrong, wrong)

        # The argument is that one instrument requires no record at all. If a
        # future amendment adds one, this is the first thing that should fail.
        check("Local Law 144 still does not use the word retain",
              not _re.search(r"\bretain", text, _re.I),
              "the text now contains it; the reading needs redoing")

    # Illinois is the third row and rests on the same shape of claim: two
    # quotations and a count of zero. The act was read from the Internet
    # Archive because ilga.gov refused every connection on 9 Sep, so the
    # committed copy is the only thing standing between this page and a
    # claim nobody can check.
    il = os.path.join(ROOT, "census", "sources", "il-pa-103-0804.txt")
    if os.path.exists(il) and os.path.exists(us_page):
        ilt = _re.sub(r"\s+", " ",
                      io.open(il, encoding="utf-8").read())
        page = io.open(us_page, encoding="utf-8").read()
        missing = [q for q in
                   ("THAT HAS THE EFFECT OF SUBJECTING EMPLOYEES",
                    "FAIL TO PROVIDE NOTICE TO AN EMPLOYEE")
                   if q in page and q.lower() not in ilt.lower()]
        check("the Illinois quotations are in the act as archived",
              not missing, missing)
        check("the Illinois act still does not use the word record",
              not _re.search(r"\brecord", ilt, _re.I),
              "it now does; the Illinois row needs redoing")

    # California is two instruments and two sources, and the page quotes both
    # heavily. Rather than list the quotations here and have the list go stale,
    # every quotation on the page is checked against the union of the five
    # committed texts. A quotation that is on the page and in none of them is
    # either a misquote or a claim from a source nobody can check, and both
    # should fail.
    us_sources = [os.path.join(ROOT, "census", "sources", f) for f in
                  ("co-sb26-189.txt", "nyc-ll144.txt", "il-pa-103-0804.txt",
                   "ca-feha-ads.txt", "ca-ccpa-admt.txt", "tx-hb149.txt",
                   "ut-ai-policy-act.txt")]
    have = [f for f in us_sources if os.path.exists(f)]
    if os.path.exists(us_page) and len(have) == len(us_sources):
        # Page furniture has to go BEFORE the text is flattened, because most
        # of it is only identifiable as a whole line: Utah's enrolled copies
        # number every line, so a quotation running over a line break carries
        # a line number inside it, and once the newlines are gone there is no
        # way to tell that number from one in a sentence.
        def _clean(path):
            raw = io.open(path, encoding="utf-8", errors="replace").read()
            raw = _re.sub(r"(?m)^\s*-\s*\d+\s*-\s*$", " ", raw)
            raw = _re.sub(r"(?m)^\s*(?:Enrolled Copy\s*)?S\.B\. \d+"
                          r"(?:\s*Enrolled Copy)?\s*$", " ", raw)
            raw = _re.sub(r"(?m)^\s*\d{1,4}\s+", " ", raw)
            flat = _re.sub(r"\s+", " ", raw)
            flat = _re.sub(
                r"PAGE\s*\d+\s*-\s*SENA\s*TE\s*BILL\s*26-189", "", flat)
            flat = _re.sub(
                r"CA PRIVACY PROTECTION AGENCY - TEXT OF REGULATIONS[^)]*\)"
                r" Page \d+ of \d+", "", flat)
            return _re.sub(r"\s+", " ", flat)

        corpus = " ".join(_clean(f) for f in have)
        page = io.open(us_page, encoding="utf-8").read()
        quoted = _re.findall(r"&ldquo;([^&]{8,400})&rdquo;", page)
        bad = []
        for q in quoted:
            q = _re.sub(r"<[^>]+>", "", q)
            q = _re.sub(r"\s+", " ", q).strip()
            if q and q not in corpus:
                bad.append(q[:70])
        check("every quotation on /united-states/ is in one of the seven"
              " committed texts", quoted and not bad, bad)

    # The California FEHA row is an absence claim: four years of records and
    # nothing asking who or whether it was edited. Six words carry it.
    feha = os.path.join(ROOT, "census", "sources", "ca-feha-ads.txt")
    if os.path.exists(feha) and os.path.exists(us_page):
        ft = _re.sub(r"\s+", " ", io.open(feha, encoding="utf-8",
                                          errors="replace").read())
        present = [w for w in ("reviewer", "natural person", "oversight",
                               "tamper", "integrity", "unaltered")
                   if _re.search(w, ft, _re.I)]
        check("the words the FEHA section says are absent are still absent",
              not present, present)
        check("the FEHA four-year record category is still named",
              "selection criteria, automated-decision system data" in ft)

    # The California privacy row is the opposite claim and needs the opposite
    # check: the page says this instrument DOES define the reviewer, so the
    # three properties have to be there, and the counts it prints have to
    # recompute. `reviewer` and `human reviewer` being equal is the sentence
    # "every reviewer here is a human one", and it is the only claim on this
    # page that would survive a careless edit while becoming false.
    ccpa = os.path.join(ROOT, "census", "sources", "ca-ccpa-admt.txt")
    if os.path.exists(ccpa) and os.path.exists(us_page):
        ct = _re.sub(r"\s+", " ", io.open(ccpa, encoding="utf-8",
                                          errors="replace").read())
        wrong = []
        for word, want in (("reviewer", 6), ("human reviewer", 6),
                           ("integrity", 5), (r"\bapprove", 3)):
            n = len(_re.findall(word, ct, _re.I))
            if n != want:
                wrong.append("%s: reading says %d, text has %d"
                             % (word, want, n))
        check("the counts the California privacy section prints recompute",
              not wrong, wrong)
        check("every reviewer in the privacy regulations is a human one",
              len(_re.findall("reviewer", ct, _re.I))
              == len(_re.findall("human reviewer", ct, _re.I)))
        gone = [w for w in ("tamper", "unaltered", "audit trail")
                if _re.search(w, ct, _re.I)]
        check("and it still asks nothing of the record itself", not gone, gone)
        check("the three properties of human involvement are still there",
              "Human involvement requires the human reviewer to" in ct
              and "Have the authority to make or change the decision based on"
                  " their analysis" in ct)
        check("the appeal exception still designates a reviewer",
              "Designate a human reviewer" in ct)

    # Texas and Utah are absence claims of the strongest kind: the page says
    # both instruments ask a record for nothing. An amendment that adds a
    # record duty to either would make the page wrong in the direction that
    # matters, so the words are checked rather than the reading remembered.
    tx = os.path.join(ROOT, "census", "sources", "tx-hb149.txt")
    if os.path.exists(tx) and os.path.exists(us_page):
        tt = _re.sub(r"\s+", " ", io.open(tx, encoding="utf-8",
                                          errors="replace").read())
        gone = [w for w in ("audit", "reviewer", "tamper", "unaltered")
                if _re.search(r"\b" + w, tt, _re.I)]
        check("Texas still uses none of the four words the page says it does"
              " not", not gone, gone)
        # The single sentence the Texas reading turns on.
        check("Texas still says disparate impact alone does not show intent",
              "a disparate impact is not sufficient by itself to demonstrate"
              " an intent to discriminate" in tt)
        n = len(_re.findall(r"\brecord", tt, _re.I))
        check("Texas still uses the word record four times", n == 4,
              "counted %d" % n)

    ut = os.path.join(ROOT, "census", "sources", "ut-ai-policy-act.txt")
    if os.path.exists(ut) and os.path.exists(us_page):
        ut_t = io.open(ut, encoding="utf-8", errors="replace").read()
        ut_t = _re.sub(r"(?m)^\s*-\s*\d+\s*-\s*$", " ", ut_t)
        ut_t = _re.sub(r"(?m)^\s*(?:Enrolled Copy\s*)?S\.B\. \d+"
                       r"(?:\s*Enrolled Copy)?\s*$", " ", ut_t)
        ut_t = _re.sub(r"(?m)^\s*\d{1,4}\s+", " ", ut_t)
        ut_t = _re.sub(r"\s+", " ", ut_t)
        gone = [w for w in ("reviewer", "natural person", "tamper",
                            "unaltered", "integrity")
                if _re.search(r"\b" + w, ut_t, _re.I)]
        check("Utah still uses none of the five words the page says it does"
              " not", not gone, gone)
        n = len(_re.findall(r"\bretain", ut_t, _re.I))
        check("Utah still has exactly one retention duty", n == 1,
              "counted %d" % n)
        check("and it is still the one written by a rule or an agreement",
              "A participant shall retain records as required by office rule"
              " or the participation agreement" in ut_t)

    print("\nevery page closes the banner before the page begins")
    # The banner is navy with near-white text. Left open it wraps the whole
    # document, and every generated page on this site rendered that way from
    # the day build_page.py was written until 6 September 2026. The suite did
    # not catch it because it only asked whether each page matched what the
    # generator produced, and the generator was consistently wrong. This asks
    # about the result instead.
    from html.parser import HTMLParser

    class _Band(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.depth = []
            self.band_at = None
            self.closed = False
            self.content_inside = False

        def handle_starttag(self, tag, attrs):
            if tag != "div":
                return
            cls = dict(attrs).get("class", "")
            self.depth.append(cls)
            if cls == "band" and self.band_at is None:
                self.band_at = len(self.depth)
            elif (self.band_at is not None and not self.closed
                  and "wrap" in cls and "hero" not in cls
                  and len(self.depth) == self.band_at + 1
                  and ("main" in cls or "page" in cls)):
                self.content_inside = True

        def handle_endtag(self, tag):
            if tag != "div" or not self.depth:
                return
            here = len(self.depth)
            self.depth.pop()
            if self.band_at is not None and here == self.band_at:
                self.closed = True

    unclosed, swallowed = [], []
    for page in pages():
        p = _Band()
        p.feed(io.open(page, encoding="utf-8").read())
        if p.band_at is None:
            continue                      # a page with no banner is not a bug
        rel = os.path.relpath(page, PUB)
        if not p.closed:
            unclosed.append(rel)
        if p.content_inside:
            swallowed.append(rel)
    check("the banner div is closed on every page", not unclosed, unclosed)
    check("so no page's content is inside it", not swallowed, swallowed)

    print("\nthe site knows about every adapter that exists")
    # Three adapters shipped on 6 September with no README and no mention on
    # the page a stranger is sent to, which is the page that says what to do
    # when you are already in a framework. An adapter nobody can find is not
    # distribution, and that is the whole argument for writing adapters.
    adir = os.path.join(ROOT, "adapters")
    built = sorted(d for d in os.listdir(adir)
                   if os.path.isdir(os.path.join(adir, d)))
    check("there are adapters to check", len(built) >= 4, built)

    # Every adapter ships something a stranger can run. For four of the five
    # this did not exist until 9 September, and writing the second one found a
    # defect the suite, CI and five READMEs had all missed: write("-") opened a
    # file literally named `-` everywhere except langgraph, which was the only
    # one anybody had ever run. An example is the cheapest test there is and it
    # is also the ask: "here is the spec" wants adoption, "here is a file that
    # runs against your library" wants conversion.
    #
    # This only checks the file is present. Running them needs five frameworks
    # installed, which CI does not have, so the release workflow runs them.
    no_example = [d for d in built
                  if not os.path.exists(os.path.join(adir, d, "example.py"))]
    check("every adapter ships an example somebody can run",
          not no_example, no_example)

    # /implement/ now opens by telling a reader on one of five frameworks that
    # a record is two commands away, and prints one of them. A page that names a
    # path is making a claim, and the claim was false for four of the five
    # until 9 September. This checks the command it prints still resolves to a
    # file, and that every framework it names has one.
    impl_src = io.open(os.path.join(ROOT, "pages", "implement.html"),
                       encoding="utf-8").read()
    shown = _re.findall(r"adapters/([a-z-]+)/example\.py", impl_src)
    check("the command /implement/ prints names a real example",
          shown and all(os.path.exists(
              os.path.join(adir, d, "example.py")) for d in shown),
          shown)

    NAMED = {"LangGraph": "langgraph", "CrewAI": "crewai",
             "AutoGen": "autogen", "OpenAI Agents": "openai-agents",
             "Pydantic AI": "pydantic-ai"}
    claimed = [d for label, d in NAMED.items() if label in impl_src]
    lacking = [d for d in claimed
               if not os.path.exists(os.path.join(adir, d, "example.py"))]
    check("every framework /implement/ names has a runnable example",
          not lacking, lacking)

    impl = io.open(os.path.join(PUB, "implement", "index.html"),
                   encoding="utf-8").read()
    missing = [d for d in built if "/adapters/" + d not in impl]
    check("/implement/ links every adapter directory", not missing, missing)

    for d in built:
        here = os.path.join(adir, d)
        files = os.listdir(here)
        check("%s has a README" % d, "README.md" in files, files)
        check("%s carries its licence" % d, "LICENSE" in files, files)
        # hatch_build.py copies the validator and the emitter in beside the
        # adapter at build time. They are gitignored, but a run after a local
        # build sees them, and picking one of them as "the adapter" makes every
        # check below examine the wrong file.
        BUNDLED = {"testimony_validate.py", "testimony_emit.py"}
        mod = [f for f in files if f.startswith("testimony_")
               and f.endswith(".py") and f not in BUNDLED]
        check("%s has exactly one adapter module" % d, len(mod) == 1, mod)
        src = io.open(os.path.join(here, mod[0]), encoding="utf-8").read()
        check("%s needs nothing from OMEM" % d, "omem" not in src.lower())
        # Every one of these is a gate, and a gate that can be read as
        # permitting by accident is the defect they were written against.
        # The three taking a decide() callable must refuse anything that is not
        # a decision they issued. LangGraph's takes none: the caller calls
        # approve() or refuse() by name, so there is no predicate whose return
        # value could be misread, and demanding the guard there would be asking
        # for an answer to a question that cannot be posed.
        # "decide" as a substring also matches the word "decided" in
        # prose, which is how this first read LangGraph as taking a
        # callable it has never had.
        takes_predicate = "decide=" in src or "self._decide" in src
        check("%s cannot be read as permitting by accident" % d,
              ("NoDecision" in src) if takes_predicate
              else ("def approve" in src and "def refuse" in src),
              "takes a decide() callable but has no NoDecision guard"
              if takes_predicate else "no explicit approve/refuse either")
        rd = io.open(os.path.join(here, "README.md"), encoding="utf-8").read()
        # Either form: the script name for a copied file, or the console
        # command the wheel installs. The property is that the README says how
        # to check the output, not which spelling it uses.
        check("%s's README says how to check the output" % d,
              "testimony_validate" in rd or "testimony-validate" in rd)
        check("%s's README says it needs nothing of ours" % d,
              "nothing" in rd.lower())
        # An adapter you cannot install is a file somebody has to be told
        # about, which is friction at exactly the point where a reader becomes
        # an implementer. Three of the four shipped without packaging.
        check("%s is installable, not only copyable" % d,
              "pyproject.toml" in files and "hatch_build.py" in files, files)
        proj = io.open(os.path.join(here, "pyproject.toml"),
                       encoding="utf-8").read()
        # The dependency list, not the file: every one of these pyprojects
        # carries a comment saying it does not depend on OMEM, and a substring
        # search finds the promise rather than checking it.
        deps = tomllib.loads(proj)["project"]["dependencies"]
        check("%s depends on its framework and nothing else" % d,
              len(deps) == 1 and "omem" not in deps[0].lower(), deps)
        check("%s ships the validator with itself" % d,
              "testimony-validate = " in proj)
        # The three that import the emitter must carry it into the wheel, or
        # the install is an ImportError with a stranger's name on it.
        if "import testimony_emit" in src:
            check("%s's wheel carries the emitter it imports" % d,
                  proj.count("testimony_emit.py") >= 2, proj.count("testimony_emit.py"))
        rd_pkg = io.open(os.path.join(here, "README.md"), encoding="utf-8").read()
        # How to obtain it, which is the install line once the package is
        # published and the copy instruction until then. Demanding the install
        # line unconditionally is how four READMEs came to promise a command
        # that failed: the check asserted the claim rather than the truth.
        check("%s's README says how to obtain it" % d,
              "pip install testimony-" in rd_pkg
              or "copy" in rd_pkg.lower()[:400])

    print("\nthe demand reading counts what its own data says")
    # Every number on /demand/ is a claim about eighty-four issues belonging to
    # other people. They are recomputed from the published file rather than
    # trusted, because the page's whole argument is that a disagreement should
    # be settled by reading the data.
    dm = io.open(os.path.join(PUB, "demand", "index.html"),
                 encoding="utf-8").read()
    data = json.load(io.open(os.path.join(ROOT, "census", "demand",
                                          "issues.json"), encoding="utf-8"))
    iss = data["issues"]
    ask = [i for i in iss if i["kind"] == "asking"]
    promo = [i for i in iss if i["kind"] == "promoting"]

    check("the data is there to check", len(iss) == 84, len(iss))
    check("and names seven frameworks",
          len(data["method"]["repositories"]) == 7,
          data["method"]["repositories"])
    check("32 asking, as the page says", len(ask) == 32, len(ask))
    check("52 promoting, as the page says", len(promo) == 52, len(promo))
    check("51 distinct authors", len({i["opened_by"] for i in iss}) == 51,
          len({i["opened_by"] for i in iss}))
    across = {i["opened_by"] for i in iss if i["author_repos"] >= 2}
    check("13 authors filed across two or more repositories",
          len(across) == 13, len(across))
    check("and none of them is counted as asking",
          not [i for i in ask if i["author_repos"] >= 2])

    unresolved = [i for i in ask
                  if i["state"] == "open" or i["state_reason"] == "not_planned"]
    check("22 of the 32 got no resolution", len(unresolved) == 22,
          len(unresolved))
    check("of which 14 are still open",
          sum(1 for i in unresolved if i["state"] == "open") == 14)
    check("and 8 were closed as not planned",
          sum(1 for i in unresolved if i["state_reason"] == "not_planned") == 8)

    def median(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2]
    check("asking draws a median of 9 comments",
          median(i["comments"] for i in ask) == 9,
          median(i["comments"] for i in ask))
    check("promoting draws 3", median(i["comments"] for i in promo) == 3,
          median(i["comments"] for i in promo))
    # The first version of this claimed the most discussed issue overall was
    # closed as not planned. It was not: the two busiest threads in the set are
    # both promoting and both open. The 98-comment RFC is the busiest of the
    # thirty-two, which is the claim the page now makes.
    top_ask = max(ask, key=lambda i: i["comments"])
    check("the busiest of the 32 was closed as not planned",
          top_ask["state_reason"] == "not_planned" and top_ask["comments"] == 98,
          top_ask)
    check("and the page does not claim it led the whole set",
          "most discussed of those thirty-two" in dm)

    check("the page says what it does not show",
          "What this does not show" in dm and "invisible here" in dm)
    check("and links the data rather than asking to be believed",
          "census/demand/issues.json" in dm)
    check("and sells nothing", "OMEM" not in dm and "omem" not in dm.lower())

    print("\nthe EU AI Act page has the dates the law actually has")
    # This page said Annex III high-risk obligations began applying on 2 August
    # 2026 for six weeks after they did not. Regulation (EU) 2026/1744 entered
    # into force on 27 July 2026, six days before, and deferred them to 2
    # December 2027. It is the most checkable claim on the most
    # compliance-relevant page here, it was wrong in the direction that
    # overstates urgency, and most commentary still carries the old date, so
    # being right is worth pinning.
    act = io.open(os.path.join(PUB, "eu-ai-act", "index.html"),
                  encoding="utf-8").read()
    check("Annex III high-risk is dated 2 December 2027",
          "2 December 2027" in act)
    check("and the deferral names the regulation that made it",
          "2026/1744" in act)
    check("Annex I embedded products are dated 2 August 2028",
          "2 August 2028" in act)
    check("it does not still say the obligations began in August 2026",
          "began applying on 2 August 2026" not in act)
    check("and it says what was NOT deferred, since that is the live half",
          "Article 5" in act and "Article 50" in act)
    check("the correction is dated rather than quietly made",
          "Corrected 6 September 2026" in act)

    print("\nevery page says what it is about in words somebody would search")
    # A title and a description exist to match a query. These were written to
    # read well instead, so the site ranked for nothing: a search for what a
    # deployer actually types returned six results and none of them was here.
    # The visible headings are untouched; only the metadata changed.
    titles, descs = {}, {}
    for page in pages():
        src = io.open(page, encoding="utf-8").read()
        rel = os.path.relpath(page, PUB).replace(os.sep, "/")
        t = re.search(r"<title>([^<]*)", src)
        d = re.search(r'<meta name="description" content="([^"]*)', src)
        if t: titles[rel] = html.unescape(t.group(1)).replace(" – Machine Testimony", "")
        if d: descs[rel] = html.unescape(d.group(1))

    check("every page has a title", len(titles) == len(list(pages())),
          "%d of %d" % (len(titles), len(list(pages()))))
    check("every page has a description", len(descs) == len(titles),
          sorted(set(titles) - set(descs)))
    dupes = [t for t, n in collections.Counter(titles.values()).items() if n > 1]
    check("no two pages share a title", not dupes, dupes)
    check("no title is only the site name",
          not [r for r, t in titles.items() if t.strip() == "Machine Testimony"],
          [r for r, t in titles.items() if t.strip() == "Machine Testimony"])

    # The words a buyer types. Not every page needs them, but a page whose
    # subject is one of these and which never says the word cannot be found.
    NEEDS = {
        "eu-ai-act/index.html": ("EU AI Act", "Article 12"),
        "register/index.html": ("audit trail",),
        "tamper-evidence/index.html": ("Tamper-evident",),
        "approvals/index.html": ("approval records",),
        "underwriting/index.html": ("insurance",),
    }
    for rel, words in NEEDS.items():
        blob = titles.get(rel, "") + " " + descs.get(rel, "")
        missing = [w for w in words if w.lower() not in blob.lower()]
        check("%s is findable by its own subject" % rel.split("/")[0],
              not missing, "title and description never say: %s" % missing)

    check("the corrected deadline is in the snippet a searcher reads",
          "2 December 2027" in descs.get("eu-ai-act/index.html", ""))
    # Rewriting the titles for search silently rewrote four visible headings
    # too, because on those pages the heading text and the title were the same
    # string. The promise of that change was that nothing a reader sees moves,
    # so the promise is checked rather than remembered.
    leaked = []
    for page in pages():
        src = io.open(page, encoding="utf-8").read()
        t = re.search(r"<title>([^<]*)", src)
        if not t:
            continue
        bare = html.unescape(t.group(1)).replace(" – Machine Testimony", "").strip()
        if len(bare) < 25:
            continue          # a short title can legitimately match a heading
        for m in re.finditer(r"<h[12][^>]*>([^<]{25,})</h[12]>", src):
            if html.unescape(m.group(1)).strip() == bare:
                leaked.append(os.path.relpath(page, PUB))
    check("no page's visible heading was replaced by its search title",
          not leaked, sorted(set(leaked)))


    print("\nno page tells somebody to install a package that does not exist")
    # /implement/ and four READMEs told readers to run `pip install
    # testimony-crewai` and three siblings. None of the four was on PyPI, so
    # every one of those commands failed. It is the same defect the pricing
    # page in the other repository was built to avoid: an instruction that
    # cannot be followed is worse than no instruction.
    import urllib.error                                        # noqa: E402
    import urllib.request                                      # noqa: E402

    claimed = set()
    for page in pages():
        claimed |= set(re.findall(r"pip install (testimony-[a-z0-9-]+)",
                                  io.open(page, encoding="utf-8").read()))
    for d in sorted(os.listdir(os.path.join(ROOT, "adapters"))):
        rd = os.path.join(ROOT, "adapters", d, "README.md")
        if os.path.exists(rd):
            claimed |= set(re.findall(r"pip install (testimony-[a-z0-9-]+)",
                                      io.open(rd, encoding="utf-8").read()))
    check("something claims an install, so this checked something", claimed,
          claimed)

    unreachable, missing = [], []
    for dist in sorted(claimed):
        try:
            urllib.request.urlopen(
                "https://pypi.org/pypi/%s/json" % dist, timeout=15).read(1)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                missing.append(dist)
            else:
                unreachable.append(dist)
        except OSError:
            unreachable.append(dist)
    if unreachable:
        # A network failure is not a finding. Say so rather than pass quietly.
        print("  NOT VERIFIED: PyPI unreachable for %s" % unreachable)
    check("every package the site says to install is published",
          not missing, "not on PyPI: %s" % missing)

    print("\nthe approval-binding reading says what its data says")
    # Six verdicts about other people's code, each citing a file and a line at
    # a commit. Recomputed here rather than trusted, on the same terms as the
    # register: a wrong verdict should be fixable by a pull request, which only
    # works if the page and the data cannot drift apart.
    ab = io.open(os.path.join(PUB, "approval-binding", "index.html"),
                 encoding="utf-8").read()
    bd = json.load(io.open(os.path.join(ROOT, "census", "binding",
                                        "readings.json"), encoding="utf-8"))
    subs = bd["subjects"]
    check("six frameworks were read", len(subs) == 6, len(subs))
    verds = collections.Counter(s["verdict"] for s in subs)
    check("one is bound", verds["bound"] == 1, dict(verds))
    check("one is partial", verds["partial"] == 1, dict(verds))
    check("two are unbound", verds["unbound"] == 2, dict(verds))
    check("two have no approval boundary at all",
          verds["no_boundary"] == 2, dict(verds))
    check("every verdict is one the method defines",
          all(s["verdict"] in bd["verdicts"] for s in subs),
          [s["verdict"] for s in subs if s["verdict"] not in bd["verdicts"]])

    # A verdict about somebody's code that does not say where it was read is an
    # accusation. The two that have no boundary cite an issue instead, because
    # there is no path to point at.
    for s in subs:
        if s["verdict"] == "no_boundary":
            check("%s cites where the absence is discussed" % s["name"],
                  s.get("issue", "").startswith("https://"), s.get("issue"))
        else:
            for side in ("shown_to_approver", "executed"):
                loc = s.get(side, {}).get("locator", "")
                check("%s cites a file and a line for what is %s"
                      % (s["name"], side.replace("_", " ")),
                      re.search(r"\.py:\d+", loc), loc)
        check("%s is pinned to a commit" % s["name"],
              re.fullmatch(r"[0-9a-f]{12}", s.get("commit", "")), s.get("commit"))

    check("the page names every framework it read",
          all(s["name"] in ab for s in subs),
          [s["name"] for s in subs if s["name"] not in ab])
    check("it says a framework without a pause is not failing",
          "not failing this" in ab)
    # Collapsed, because the source wraps prose and a phrase that straddles a
    # line break is present on the page and absent from a substring search.
    flat_ab = " ".join(ab.split())
    check("and what the reading does not show",
          "What this does not show" in flat_ab
          and "not a conformance assessment" in flat_ab)
    check("it links the data rather than asking to be believed",
          "census/binding/readings.json" in ab)
    check("and sells nothing", "OMEM" not in ab and "omem" not in ab.lower())

    print("\nthe reading of the schemes says what its data says")
    # Four instruments, three of which specify what a record must contain. The
    # fourth is in the data to be counted out: a framework that deliberately
    # specifies no controls is not failing to specify one, and reporting its
    # zero would be the error this reading exists to avoid. So every headline
    # number on the page is recomputed over the assessable subjects only.
    ob = io.open(os.path.join(PUB, "obligation", "index.html"),
                 encoding="utf-8").read()
    sc = json.load(io.open(os.path.join(ROOT, "census", "schemes",
                                        "readings.json"), encoding="utf-8"))
    qs = [q["id"] for q in sc["questions"]]
    check("four questions were asked", len(qs) == 4, qs)
    check("four instruments were read", len(sc["subjects"]) == 4,
          len(sc["subjects"]))
    for sub in sc["subjects"]:
        check("%s answers every question" % sub["name"],
              set(sub["answers"]) == set(qs), sorted(sub["answers"]))
        check("%s declares what kind of instrument it is" % sub["name"],
              bool(sub.get("kind")), sub.get("kind"))
        check("%s names what was read and where it came from" % sub["name"],
              bool(sub.get("read")) and bool(sub.get("source")), sub.get("read"))
        for qid, a in sub["answers"].items():
            check("%s %s cites something for its verdict" % (sub["name"], qid),
                  a["verdict"] in sc["verdicts"] and len(a.get("note", "")) > 20,
                  "%s %r" % (a["verdict"], a.get("note", "")[:40]))
        # A subject is assessable on every question or on none. A mixed row
        # would mean the instrument kind had been decided per question, which
        # is exactly where a convenient not applicable would hide.
        na = [q for q in qs if sub["answers"][q]["verdict"] == "not_applicable"]
        check("%s is assessable throughout or not at all" % sub["name"],
              len(na) in (0, len(qs)), na)

    able = [x for x in sc["subjects"]
            if x["answers"]["Q1"]["verdict"] != "not_applicable"]
    check("three of the four specify what a record must contain",
          len(able) == 3, len(able))
    flat_ob = " ".join(ob.split())
    check("and the page says three", "three rather than four" in flat_ob)
    check("all three require a record to be kept",
          all(x["answers"]["Q1"]["verdict"] == "required" for x in able),
          [x["answers"]["Q1"]["verdict"] for x in able])
    # The finding itself. If either of these stops being unanimous, the
    # sentence on the page becomes false, and this is where that surfaces.
    # Corrected 8 Sep 2026. This read "none of the three requires it" until
    # Article 12(3)(d) was read properly: the logs of a remote biometric
    # identification system must provide the identification of the natural
    # persons who verified the result, pointing at Article 14(5)'s two named
    # people. The requirement exists, drafted, and scoped to one row of Annex
    # III. Partial is the honest verdict and the finding is stronger for it.
    q2 = {x["name"]: x["answers"]["Q2"]["verdict"] for x in able}
    check("exactly one of the three requires a record to name the person",
          sorted(q2.values()) == ["absent", "absent", "partial"], q2)
    check("and it is the law, for one category rather than in general",
          q2.get("EU AI Act") == "partial", q2)
    check("the note says which article and which Annex III category",
          all(k in [x for x in able if x["name"] == "EU AI Act"][0]
              ["answers"]["Q2"]["note"]
              for k in ("12(3)(d)", "14(5)", "Annex III")))
    check("none requires it be shown unaltered by a third party",
          not [x for x in able if x["answers"]["Q3"]["verdict"] == "required"],
          [x["name"] for x in able
           if x["answers"]["Q3"]["verdict"] == "required"])
    check("the page states that finding",
          "Only one of them requires a record to name the person, and only for "
          "one category of system out of everything the law covers" in flat_ob)
    # A correction to a published reading is recorded on the page rather than
    # made quietly, on the same terms this project asks of everybody else.
    check("and the page records that it previously said otherwise",
          "An earlier version of this page said the Act contained no such "
          "requirement at all" in flat_ob)
    check("the page names every instrument it read",
          all(x["name"] in ob for x in sc["subjects"]),
          [x["name"] for x in sc["subjects"] if x["name"] not in ob])
    check("it records what it could not read rather than guessing",
          bool(sc.get("not_read")) and all(x["name"] in ob and "paywall" in x["why"]
                                           for x in sc["not_read"]),
          [x["name"] for x in sc.get("not_read", [])])
    check("it says a framework specifying no controls is not failing",
          "not failing to specify one" in flat_ob)
    check("and what the reading does not show",
          "What this does not show" in flat_ob
          and "not an assessment of whether any of these is good" in flat_ob)
    check("it links the data rather than asking to be believed",
          "census/schemes/readings.json" in ob)
    check("and sells nothing", "OMEM" not in ob and "omem" not in ob.lower())

    print("\nthe governance page commits to something checkable")
    # A governance page that says only "one editor decides" describes the
    # arrangement without constraining it. What stops a fork is not the
    # arrangement, it is that somebody stuck can tell whether they are stuck:
    # a stated answering time, a stated point at which to give up waiting, and
    # the fact that nothing needed to continue is held only by the editor.
    #
    # These are the load-bearing sentences. If one is edited out, the page has
    # gone back to describing rather than committing, and this fails.
    ch = io.open(os.path.join(PUB, "changes", "index.html"),
                 encoding="utf-8").read()
    flat_ch = " ".join(ch.split())
    check("it commits to a time for an answer, not just to reading",
          "within fourteen days" in flat_ch)
    check("and says what the reporter may conclude if that time passes",
          "ninety days" in flat_ch and "unmaintained" in flat_ch)
    check("it says the delay is the editor's failure rather than the reporter's",
          "the editor's failure and not the reporter's" in flat_ch)
    check("it declines to name a successor and says why",
          "No successor is named" in flat_ch)
    # The claim that makes the missing successor survivable is that every part
    # is already somewhere the editor does not control. Each of those has to be
    # true, so each is named rather than gestured at.
    for where in ("IETF datatracker", "Zenodo"):
        check("continuation does not depend on the editor: %s" % where,
              where in ch, where)
    check("anybody can continue without the editor's cooperation",
          "needs no cooperation from the editor" in flat_ch)
    # The people who found the defects are named on the page and in the draft's
    # acknowledgements. A reader deciding whether to rely on this should be able
    # to see that its defects are found by people who do not work for it.
    draft = io.open(sorted(glob.glob(os.path.join(ROOT, "spec", "draft-*-[0-9][0-9].md")))[-1], encoding="utf-8").read()
    for who in ("Phill Clapham", "impartshadow", "babyblueviper1"):
        check("%s is credited on the governance page" % who, who in ch, who)
        check("and in the draft's acknowledgements", who in draft, who)

    print("\nthe reading on explaining says what the assessments say")
    # Every count on /explaining/ comes from the same subject files the register
    # is built from, so the page cannot say one thing while the data says
    # another. The three requirements are the ones that decide whether a
    # deployer could reconstruct the main elements of a decision afterwards.
    ex = io.open(os.path.join(PUB, "explaining", "index.html"),
                 encoding="utf-8").read()
    flat_ex = " ".join(ex.split())
    sys.path.insert(0, os.path.join(ROOT, "census"))
    import rubric as _rub                                     # noqa: E402
    _reqs = {r.id: r for r in _rub.REQUIREMENTS}
    _subs = [json.load(io.open(f, encoding="utf-8"))
             for f in sorted(glob.glob(os.path.join(
                 ROOT, "census", "subjects", "*.json")))]

    def _tally(rid):
        r = _reqs[rid]
        pool = [d for d in _subs if r.applies_to in d.get("claims", [])]
        c = collections.Counter(
            (d["assessments"].get(rid) or {}).get("verdict") for d in pool)
        return len(pool), c["present"], c["partial"], c["absent"]

    for rid, row in (("R2.1", "The source a stored fact came from"),
                     ("R2.2", "A fact the system inferred"),
                     ("R2.4", "the disagreement is")):
        n, p, pa, a = _tally(rid)
        i = flat_ex.find(row)
        check("%s: the page shows a row for it" % rid, i > 0, row)
        if i > 0:
            cells = re.findall(r">(\d+)<", flat_ex[i:i + 460])[:3]
            check("%s: the row is %d/%d/%d as the assessments say"
                  % (rid, p, pa, a),
                  cells == [str(p), str(pa), str(a)], (cells, [p, pa, a]))

    # The two sentences the page rests on, recomputed rather than trusted.
    _, p21, _, _ = _tally("R2.1")
    _, _, _, a24 = _tally("R2.4")
    check("two of ten can say where a fact came from", p21 == 2, p21)
    check("and eight cannot say afterwards that anything was disputed",
          a24 == 8, a24)
    check("the page states both",
          "Two of ten can say where a fact came from" in flat_ex
          and "Eight of ten cannot tell you afterwards" in flat_ex)

    # The legal half. These are the claims that would do damage if they drifted,
    # so each is held to the article it rests on and to the caveat beside it.
    check("it quotes what Article 86 actually grants",
          "clear and meaningful explanations of the role of the AI system in "
          "the decision-making procedure and the main elements of the decision "
          "taken" in flat_ex)
    check("it names the one Annex III area Article 86 excepts",
          "point 2, critical infrastructure" in flat_ex)
    check("and the one area whose log content Article 12(3) specifies",
          "Annex III point 1(a), remote biometric identification" in flat_ex)
    # The date is a sharpener, not the claim. A page asserting a live legal
    # obligation on an arguable reading is the failure this one is written to
    # avoid, so the hedge is load-bearing and is held here.
    check("it says Article 86 was not deferred, and which regulation deferred what",
          "Regulation (EU) 2026/1744" in flat_ex
          and "Chapter III Sections 1 to 3" in flat_ex)
    check("and refuses to assert that it bites before December 2027",
          "arguable and this page does not assert it" in flat_ex)
    check("and says the finding does not depend on which reading is right",
          "does not depend on which reading is right" in flat_ex)
    check("it disclaims legal advice", "not legal advice" in flat_ex)
    check("and it carries forward the correction from the other reading",
          "was read and its scope was not" in flat_ex)

    print("\na cited DOI resolves to a deposit that carries what the page says")
    # A DOI on a page is a claim that somebody else holds this text and stamped
    # its date. Checking only that the string is present would test the typing.
    # This resolves the record and checks it carries the files the pages are
    # generated from, so a mistyped digit, a deleted deposit or a record that
    # never had these files fails here rather than in front of a reader.
    #
    # It is the concept DOI on the pages deliberately: a version DOI freezes at
    # one deposit, and a corrected reading would leave every citation pointing
    # at the version with the error in it.
    READINGS_DOI = "10.5281/zenodo.22658916"
    CENSUS_DOI = "10.5281/zenodo.22290922"
    cited = set()
    for page in pages():
        cited |= set(re.findall(r"10\.5281/zenodo\.\d+",
                                io.open(page, encoding="utf-8").read()))
    check("the readings pages cite the deposit",
          READINGS_DOI in cited, sorted(cited))
    check("and no page cites a DOI that is not one of ours",
          not (cited - {READINGS_DOI, CENSUS_DOI,
                        "10.5281/zenodo.22286050", "10.5281/zenodo.22286051",
                        "10.5281/zenodo.22290923"}),
          sorted(cited))

    for name, doi, want in (
            ("the readings", READINGS_DOI,
             {"obligation.md", "explaining.md", "instrument-readings.json",
              "README.md"}),
            ("the census", CENSUS_DOI, set())):
        try:
            rec = json.loads(fetch(
                "https://zenodo.org/api/records/"
                + doi.split(".")[-1]).decode("utf-8"))
        except Exception as e:                                  # noqa: BLE001
            # Deliberately NOT the "NOT VERIFIED" sentinel the anchor checks
            # use. That one means a command this repository controls did not
            # run, and it should block. This means a third party was down.
            # Failing every merge because CERN is having a bad hour reports
            # nothing about the repository and teaches people to ignore CI.
            # A deposit that IS reachable and disagrees still fails, below.
            print("  DEPOSIT UNREACHABLE: %s (%s). The pages were not checked "
                  "against it on this run." % (name, str(e)[:60]))
            continue
        got = {f.get("key") for f in rec.get("files") or []}
        check("%s deposit exists and is public" % name, bool(rec.get("doi")),
              rec.get("doi"))
        if want:
            check("and carries every file the pages are generated from",
                  want <= got, sorted(want - got))
            # The deposit is generated from the same sources as the pages.
            # If a page is edited and not re-deposited they drift, and the
            # whole point of the DOI is that the two say the same thing.
            #
            # This reads what Zenodo actually holds rather than the local
            # copy in readings-deposit/. A local file proves only that the
            # intended upload was generated; fetching the deposited bytes
            # proves the record a reader resolves says what the page says.
            #
            # One paragraph is exempt and only one: the page's citation of
            # its own DOI. A deposit cannot contain the identifier it is
            # given on publication, so requiring that would demand a new
            # version for every deposit forever. Everything else matches or
            # this fails.
            def _comparable(text):
                out = []
                for l in text.replace(chr(13), '').split(chr(10)):
                    if READINGS_DOI in l:
                        continue
                    if l.strip() or (out and out[-1].strip()):
                        out.append(l)
                return chr(10).join(out).strip()

            held_at = {f.get('key'): (f.get('links') or {}).get('self')
                       for f in rec.get('files') or []}
            for f, src in (('obligation.md', 'obligation'),
                           ('explaining.md', 'explaining')):
                fresh = subprocess.run(
                    [sys.executable,
                     os.path.join(ROOT, 'census', 'to_markdown.py'),
                     os.path.join(ROOT, 'pages', src + '.html')],
                    capture_output=True, text=True)
                try:
                    held = fetch(held_at[f]).decode('utf-8')
                except Exception as e:                       # noqa: BLE001
                    print('  DEPOSIT UNREACHABLE: could not fetch %s (%s)'
                          % (f, str(e)[:60]))
                    continue
                check('%s in the deposit is what the page still produces'
                      % f,
                      fresh.returncode == 0
                      and _comparable(fresh.stdout) == _comparable(held),
                      'regenerate readings-deposit/%s and deposit a new '
                      'version' % f)

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
        slug = os.path.relpath(os.path.dirname(page), PUB).replace(os.sep, "/")
        if slug in DEPOSITED:
            continue
        s = io.open(page, encoding="utf-8").read()
        try:
            if nav(s) != home:
                odd.append(os.path.relpath(page, PUB))
        except ValueError:
            odd.append(os.path.relpath(page, PUB) + " (no nav)")
    check("no page has drifted from the homepage's navigation", not odd,
          "; ".join(odd[:4]))
    print("  (%d deposited document(s) skipped: %s)"
          % (len(DEPOSITED), ", ".join(sorted(DEPOSITED))))
    print("")
    print("no page reintroduces the ornament")
    # Uppercase micro-labels with letter-spacing are the eyebrow pattern, and
    # they are the first thing on the list of tells this project already
    # reacted to once on the product UI. They had spread to column heads,
    # verdict cells, entry kinds and the validator's badges: nine rules across
    # the shared stylesheet and the pages that carry their own copy.
    #
    # Negative tracking on large display type is ordinary typography and is not
    # what this is about, so only positive values are refused.
    import re as _re
    UPPER = _re.compile(r"text-transform\s*:\s*uppercase")
    TRACK = _re.compile(r"letter-spacing\s*:\s*\.\d")
    WORDMARK = ".lockup .nm"          # the only place either belongs

    def stylesheets(text):
        return "\n".join(_re.findall(r"<style>(.*?)</style>", text, _re.S))

    def offenders(css):
        out = []
        for sel, body in _re.findall(r"([^{}\n][^{}]*)\{([^}]*)\}", css):
            sel = sel.strip()
            if WORDMARK in sel:
                continue
            if UPPER.search(body) or TRACK.search(body):
                out.append(sel[:40])
        return out

    bad = {}
    for page in pages():
        found = offenders(stylesheets(
            io.open(page, encoding="utf-8").read()))
        if found:
            bad[os.path.relpath(page, PUB)] = found
    check("no published page sets uppercase or positive tracking outside the "
          "wordmark", not bad, dict(list(bad.items())[:3]))

    # And the generator itself, so a rebuild cannot put it back.
    gen = io.open(os.path.join(ROOT, "build_page.py"), encoding="utf-8").read()
    i = gen.find('EXTRA = """')
    extra = gen[i:gen.find('"""', i + 12)] if i >= 0 else ""
    check("the shared page stylesheet sets neither",
          not UPPER.search(extra) and not TRACK.search(extra),
          "build_page.py EXTRA")

    print("")
    print("every published page has a source that produces it")
    # /changes/ was published with no source in pages/, so the rebuild check
    # above never saw it, and it drifted: the live copy had been built by an
    # older generator and carried a stylesheet two revisions behind. It is the
    # governance page, which made it the worst one to leave unguarded.
    #
    # Converting it was cheap. The three below are not yet converted and are
    # named here rather than left to be discovered, so the debt is visible and
    # a fourth cannot appear quietly.
    UNCONVERTED = {
        # Tried and reverted. /check/ keeps a page-specific stylesheet inside
        # the same <style> block the generator writes: tr.refused, the checks
        # table, the verdict panel and the reader's own table, 39 declarations
        # the shared sheet knows nothing about. build_page.py emits the shared
        # CSS and EXTRA and has nowhere to put a third part, so converting the
        # page silently dropped all of it and the results table rendered
        # unstyled. Converting it means teaching the generator about
        # page-scoped CSS, which is a change to every page, not to this one.
        "check",
        # /review/ is generated too, but not from pages/ and not for that
        # reason. It is built from /check/'s own shell by
        # spec/build_review_page.py, so that two pages sharing a header, a
        # footer and a file drop cannot drift apart. Its source is that script,
        # and the suite checks that regenerating reproduces what is published.
        "review",
    }
    sources = set()
    for f in os.listdir(os.path.join(ROOT, "pages")):
        if not f.endswith(".html"):
            continue
        text = io.open(os.path.join(ROOT, "pages", f), encoding="utf-8").read()
        m = re.search(r"slug:\s*([^\s>]+?)-->", text)
        if m:
            sources.add(m.group(1))
    published = set()
    for name in os.listdir(PUB):
        d = os.path.join(PUB, name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "index.html")):
            published.add(name)
        # subject pages live one level down, under register/
        sub = os.path.join(d, "index.html")
        if os.path.isdir(d):
            for inner in os.listdir(d):
                if os.path.isdir(os.path.join(d, inner)) and os.path.exists(
                        os.path.join(d, inner, "index.html")):
                    published.add("%s/%s" % (name, inner))
    orphans = sorted(published - sources - UNCONVERTED - DEPOSITED)
    check("no published page lacks a source in pages/", not orphans, orphans)
    # And the allowlist must not outlive the thing it excuses.
    stale = sorted((UNCONVERTED | DEPOSITED) & sources)
    check("the unconverted list names only pages that are still unconverted",
          not stale, "now converted, remove from the list: %s" % stale)


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

    print()
    print("every suite in tests/ is actually run by CI")
    # CI names each suite explicitly rather than discovering them, which is
    # the right call: a discovered suite that errors on import can look like
    # a suite that passed. The cost is that a suite added and not wired in
    # never runs and nobody finds out. This is the check for that, and it
    # lives in a suite CI already runs, because a guard nobody runs has the
    # same problem it is guarding against.
    workflow = io.open(os.path.join(ROOT, ".github", "workflows", "ci.yml"),
                       encoding="utf-8").read()
    unwired = [os.path.basename(f)
               for f in sorted(glob.glob(os.path.join(HERE, "tests_*.py")))
               if os.path.basename(f) not in workflow]
    check("no suite exists that CI never runs", not unwired, unwired)

    print()
    print("/review/ reads a file and sends it nowhere")
    rev = os.path.join(PUB, "review", "index.html")
    check("the page is published", os.path.exists(rev))
    if os.path.exists(rev):
        rev_html = io.open(rev, encoding="utf-8", newline="").read()
        # The whole footing for running this over a client's log is that the
        # log does not move. That is a claim on the face of the page, so it
        # is checked like every other claim on a page here rather than being
        # taken on the author's word.
        for bad in ("fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket",
                    "<form", "action=", "EventSource"):
            check("it cannot send the file anywhere: no %s" % bad,
                  bad not in rev_html)
        scripts = [l for l in rev_html.split(chr(10)) if "<script" in l]
        check("and no script comes from anywhere but this origin",
              not [l for l in scripts if "src=" in l]
              and rev_html.count('"./review.js"') == 1, scripts)
        check("it says on its face that nothing is uploaded",
              "Nothing is uploaded" in rev_html or "nothing is uploaded" in rev_html)
        check("and points at the rubric for what it is not",
              'href="/assess/"' in rev_html)

        for gen, target in (("build_review_js.py", "review.js"),
                            ("build_review_page.py", "index.html")):
            path = os.path.join(PUB, "review", target)
            before = io.open(path, encoding="utf-8", newline="").read()
            r = subprocess.run([sys.executable,
                                os.path.join(ROOT, "spec", gen)],
                               capture_output=True, text=True)
            after = io.open(path, encoding="utf-8", newline="").read()
            check("%s is what %s produces" % (target, gen),
                  r.returncode == 0 and before == after,
                  r.stderr[:120] or "regenerating changed the file")

    # /formats/ is the registry's public face and it reads other people's work,
    # so the page and the declarations behind it are held to each other the way
    # /eu-ai-act/ and the instrument tables are. A page that says a format
    # carries something the declaration does not is a claim about somebody else
    # nobody can check.
    print()
    print("/formats/ says what the declarations say")
    sys.path.insert(0, os.path.join(ROOT, "spec"))
    import formats as fm

    fp = os.path.join(PUB, "formats", "index.html")
    check("the page exists", os.path.exists(fp))
    if os.path.exists(fp):
        page = io.open(fp, encoding="utf-8").read()
        flat = _re.sub(r"\s+", " ", page)

        for fmt in fm.DECLARED.values():
            check("%s is named on the page" % fmt.id, fmt.name in flat)
            check("%s says where it was read" % fmt.id, fmt.where in flat)

        # Every declared field path is on the page. A path that moved in the
        # declaration and not here is the drift this check exists for.
        gone = [(f.id, s, v) for f in fm.DECLARED.values()
                for s, v in f.signals.items()
                if not isinstance(v, tuple) and v not in flat]
        check("every declared field path appears on the page", not gone, gone)

        check("no format is on the page that is not declared",
              flat.count("Read at") == 1,
              "the source table is the only place a format is introduced")

        # The disclosure is the whole basis for anybody trusting this page, so
        # it is a test and not an intention.
        check("the page discloses that it grades its own author's format",
              "maintained by the author of this page" in flat)
        check("the page names where its own format is the weaker one",
              "worse than one of them" in flat)
        # Counting filled cells would compare what the formats are FOR. The
        # page has to refuse the scoreline out loud, because a reader who
        # wants one will otherwise construct it from the table.
        check("the page refuses to be read as a score",
              "It is not a score" in flat)
        # The misread that caused the declared layer to exist is named on the
        # page. If it is ever removed, the page is claiming a rigour it did
        # not always have.
        check("the page names the misreading that motivated it",
              "subject_ref" in flat and "6-1-1701(15)(a)" in flat)

    # /witness/ publishes criteria that other people are meant to apply, so the
    # page and the criteria module are held to each other. A criterion that
    # exists in one and not the other is a rule nobody can follow.
    print()
    print("/witness/ says what the criteria say")
    import witness_criteria as wcr

    wp = os.path.join(PUB, "witness", "index.html")
    check("the page exists", os.path.exists(wp))
    if os.path.exists(wp):
        page = _re.sub(r"\s+", " ", io.open(wp, encoding="utf-8").read())
        for c in wcr.CRITERIA:
            check("%s is on the page" % c.id,
                  ">%s<" % c.id in page or (" %s " % c.id) in page)
        check("the page carries every criterion and no more",
              page.count("<tr><td class=\"s\">W") == len(wcr.CRITERIA),
              page.count("<tr><td class=\"s\">W"))

        # The reference witness fails W6 on purpose. If the page ever stops
        # saying so, the criteria have been quietly discredited by their own
        # implementation, which is the exact failure W6 describes.
        check("the page says the reference witness fails W6 deliberately",
              "fails W6" in page)
        check("and that it is not an offer to witness anything",
              "not an offer to witness" in page)
        # W4 cannot be met by any single witness. A page that implied otherwise
        # would be selling something nobody can buy.
        check("the page says one witness cannot meet W4",
              "single witness cannot meet it" in page)
        check("the page names all three parties the criteria came from",
              "#302" in page and "8636" in page)

    # A page nothing points at is a page nobody finds, and the pages that
    # matter most here are the ones a deadline sends somebody looking for.
    # The sitemap rotted silently until 10 September 2026, when it carried 19
    # URLs against 24 published pages, and every one of the six missing was
    # built in the preceding two days, the Colorado reading among them.
    # /colorado-deployers/ is the one page somebody reads while deciding to
    # spend money, so its numbers are held to the readings they come from. A
    # sales page that drifts from its own evidence is the thing this project
    # reports in other people's systems.
    print()
    print("the deployer page says what the readings say")
    dp = os.path.join(PUB, "colorado-deployers", "index.html")
    check("the deployer page is published", os.path.exists(dp))
    if os.path.exists(dp):
        d = _re.sub(r"\s+", " ", io.open(dp, encoding="utf-8").read())

        # The census: 8 of 10 act, 1 can name the approver. Same numbers as
        # /register/ and /underwriting/ or somebody has edited a claim.
        check("it uses the census counts, not rounder ones",
              "1 of 8" in d and "6 of 8" in d and "1 of 10" not in d)

        # The binding census, six frameworks, and the verdicts must match
        # readings-2.json rather than being retold more favourably.
        bind = json.load(io.open(os.path.join(ROOT, "census", "binding",
                                              "readings-2.json"),
                                 encoding="utf-8"))
        for sub in bind["subjects"]:
            check("%s is on the deployer page" % sub["name"],
                  sub["name"] in d)
        pyd = [x for x in bind["subjects"] if x["name"] == "Pydantic AI"][0]
        check("pydantic-ai is still reported as failing B3 here",
              pyd["assessments"]["B3"]["verdict"] == "absent"
              and "did not execute" in d)

        # The disclosure. The one system that can name an approver is the
        # author's own, and a page selling a reading must say so.
        check("it discloses that the passing system is the author's own",
              "maintained by the author of this page" in d)
        check("it says what the offer does not do",
              "does not make you compliant" in d)
        check("it names the four obligations no record can answer",
              "not facts about a record at all" in d)
        check("it says the free route exists and stays free",
              "free and stays free" in d)
        # The proposed rules are not final and the page must not imply they are.
        check("it says the proposed rules are not final",
              "are not final" in d and "23 September" in d)
        check("there is a way to make contact",
              "mailto:troy@machinetestimony.com" in d)

    print()
    print("everything published is findable")
    sys.path.insert(0, os.path.join(ROOT, "spec"))
    import build_sitemap as bs

    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "spec", "build_sitemap.py"),
                        "--check"], capture_output=True, text=True)
    check("the sitemap is what the published pages produce", r.returncode == 0,
          (r.stderr or r.stdout)[:200])

    sm = io.open(os.path.join(PUB, "sitemap.xml"), encoding="utf-8").read()
    listed = set(_re.findall(r"<loc>([^<]*)</loc>", sm))
    want = {"https://machinetestimony.org/" + (x + "/" if x else "")
            for x in bs.pages()}
    check("every published page is in the sitemap", want <= listed,
          sorted(want - listed)[:5])

    # llms.txt is NOT generated: its entries carry descriptions somebody had to
    # write, and a generated one would be a list of titles. So it is held
    # complete instead, the same bargain the instrument tables make.
    lt = io.open(os.path.join(PUB, "llms.txt"), encoding="utf-8").read()
    top = [x for x in bs.pages() if x and "/" not in x]
    absent = [x for x in top if "/%s/" % x not in lt]
    check("every top-level page is named in llms.txt", not absent, absent)

    check("robots.txt points at the sitemap",
          "machinetestimony.org/sitemap.xml" in
          io.open(os.path.join(PUB, "robots.txt"), encoding="utf-8").read())

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

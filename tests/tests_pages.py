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
          len(subs) == 8, len(subs))

    def tally(req):
        vs = [v.get(req, "not_applicable") for v in subs.values()]
        n = [v for v in vs if v != "not_applicable"]
        return (len(n), n.count("present"), n.count("partial"),
                n.count("absent"), n.count("undetermined"))

    # (requirement, the row's six numbers as written on the page)
    ROWS = [("R3.5", (6, 1, 0, 4, 1)), ("R3.6", (6, 1, 0, 4, 1)),
            ("R3.7", (6, 1, 0, 4, 1)), ("R3.1", (6, 3, 3, 0, 0)),
            ("R3.3", (6, 2, 4, 0, 0)), ("R3.4", (6, 2, 2, 2, 0)),
            ("R1.2", (8, 5, 2, 1, 0)), ("R2.1", (8, 2, 4, 2, 0))]
    for req, want in ROWS:
        check("the %s row is what the assessments say" % req,
              tally(req) == want, "page says %s, census says %s"
              % (want, tally(req)))

    # The two sentences the page puts in a callout, which is where a reader
    # who reads nothing else will look.
    n_acts, can, _, _, undet = tally("R3.5")
    check("one of six acting systems can name an approver, as claimed",
          (n_acts, can, undet) == (6, 1, 1), (n_acts, can, undet))
    check("and the page says so in those words",
          "one can name the person who approved an action" in uw)
    tot, ver, _, _, _ = tally("R4.2")
    check("six of eight cannot be verified without the vendor, as claimed",
          (tot, tot - ver) == (8, 6), (tot, ver))
    check("and the page says so in those words",
          "six produce records\n        that cannot be verified without the "
          "vendor" in uw or "six produce records" in uw)
    check("it points at the register rather than asking to be believed",
          'href="/register/"' in uw and 'href="/assess/"' in uw)
    check("and it names no product it is selling",
          "OMEM" not in uw and "omem" not in uw.lower())


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

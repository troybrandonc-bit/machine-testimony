"""Compose a page onto machinetestimony.org from the homepage's own shell.

    python3 build_page.py pages/anchor.html public/anchor/index.html

The stylesheet, the banner and the footer are taken from public/index.html
rather than restated, so a page cannot drift into a lookalike of the site. This
script used to live outside the repository, which is exactly how every
sub-page came to carry the navigation link "Check a record" twice: the homepage
gained the link, the generator was still adding it, and nobody could see the
generator to notice.

The page body is an HTML fragment. Its first line is an HTML comment holding
the title, the description and the slug, so that one file carries everything
the page needs and nothing has to be passed on the command line twice.

    <!--title: A record you can check without us
        desc: ...
        slug: anchor-->

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.join(HERE, "public", "index.html")

EXTRA = """
  /* Only what a prose page needs beyond the shared stylesheet. */
  pre.snip{background:none;border-left:2px solid var(--rule);margin:0 0 16px;
    padding:2px 0 2px 13px;font-size:13px;overflow-x:auto;max-width:100%;
    font-family:var(--mono);line-height:1.55}
  pre.snip.addr{overflow-x:visible;white-space:pre-wrap;overflow-wrap:anywhere}
  .block h3{font-family:var(--display);font-weight:600;color:var(--ink);
    font-size:1.08rem;margin:26px 0 8px}
  .block ol,.block ul{margin:0 0 15px;padding-left:1.15rem;max-width:46rem}
  .block li{margin:0 0 7px}
  .dateline{font-family:var(--sans);font-size:12.5px;color:var(--muted);
    margin:0 0 22px}
  /* The one sentence a page is allowed to insist on. For a measured number the
     rest of the page exists to explain, never for emphasis on an opinion. */
  p.callout{border-left:2px solid var(--band);padding:10px 0 10px 14px;
    margin:0 0 17px;max-width:46rem}
  table.facts{width:100%;border-collapse:collapse;font-size:14px;margin:0 0 20px}
  table.facts th{text-align:left;font-family:var(--sans);font-size:11px;
    font-weight:700;letter-spacing:.06em;text-transform:uppercase;
    color:var(--muted);padding:0 12px 6px 0;white-space:nowrap;
    vertical-align:top;width:8.5rem}
  table.facts td{padding:0 0 6px;font-family:var(--mono);font-size:12.5px;
    overflow-wrap:anywhere;border-bottom:1px solid var(--rule-soft)}
  table.facts th{border-bottom:1px solid var(--rule-soft)}
  /* The register's tables. A wide table scrolls inside its own box rather
     than pushing the page sideways, which is the thing that made the site
     unreadable on a phone the first time. */
  .scroller{overflow-x:auto;max-width:100%;margin:0 0 16px}
  table.reg{border-collapse:collapse;font-size:14px;min-width:34rem}
  table.reg th{text-align:left;font-family:var(--sans);font-size:11px;
    font-weight:700;letter-spacing:.06em;text-transform:uppercase;
    color:var(--muted);padding:0 14px 7px 0;white-space:nowrap;
    border-bottom:1px solid var(--rule)}
  table.reg td{padding:8px 14px 8px 0;border-bottom:1px solid var(--rule-soft);
    vertical-align:top}
  table.reg td.s{font-weight:600;white-space:nowrap}
  table.reg td.n,table.reg td.lv,table.reg td.d{font-family:var(--sans);
    font-size:12.5px;white-space:nowrap;color:var(--body)}
  table.reg td.lv{font-weight:700}
  table.reg td.v{font-family:var(--sans);font-size:11px;font-weight:700;
    letter-spacing:.02em;white-space:nowrap;color:var(--muted)}
  /* Absent is the finding, so it is the one that is not muted. */
  table.reg td.v.n{color:var(--ink)}
  table.reg td.w{font-family:var(--mono);font-size:12px;color:var(--muted);
    overflow-wrap:anywhere}
  table.reg tr.own td{background:#f4f7fb}
  .tag{font-family:var(--sans);font-size:10.5px;font-weight:700;
    letter-spacing:.04em;text-transform:uppercase;color:var(--muted);
    white-space:nowrap}
  @media (max-width:620px){
    table.reg{font-size:13px}
    table.reg td.w{font-size:11px}
    pre.snip{font-size:12px}
    table.facts th{width:6.6rem;font-size:10px}
    table.facts td{font-size:11.5px}
  }
"""


def shell() -> tuple[str, str, str]:
    src = io.open(HOME, encoding="utf-8").read()
    css = re.search(r"<style>(.*?)</style>", src, re.S).group(1).rstrip()
    # The homepage nests the navigation and the hero inside one <div class=
    # "band">, and a sub-page wants the navigation without the hero. Slicing to
    # the hero gets that, and drops the </div> that closed the band, because
    # that tag sits after the hero rather than before it.
    #
    # An unclosed div is not a parse error. The browser closes it at </body>,
    # so .band -- which is navy with near-white text -- wrapped the whole of
    # every generated page. Every sub-page on this site rendered white text on
    # navy from the day the generator was written until 6 September 2026.
    #
    # Nothing caught it. The suite checked that each page matched what the
    # generator produced, which it did: the generator was consistently wrong.
    # tests_pages now parses the built pages and asserts the band closes before
    # the content starts, which is a claim about the result rather than about
    # agreement between two things that can be wrong together.
    band = src[src.index('<div class="band">'):src.index('<div class="wrap hero">')]
    band = band.rstrip() + "\n</div>"
    foot = src[src.index('<footer class="foot">'):src.index("</body>")]
    return css, band, foot.rstrip()


def meta(body: str) -> tuple[dict, str]:
    m = re.match(r"\s*<!--(.*?)-->\s*", body, re.S)
    if not m:
        raise SystemExit("the fragment needs a leading comment with title, "
                         "desc and slug")
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    for k in ("title", "desc", "slug"):
        if k not in out:
            raise SystemExit("the fragment's comment is missing %r" % k)
    return out, body[m.end():]


def build(fragment: str) -> str:
    css, band, foot = shell()
    info, body = meta(fragment)
    # The homepage's own anchors are page-local; from a sub-page they have to
    # point back at it.
    band = band.replace('href="#', 'href="/#')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{info['title']} &ndash; Machine Testimony</title>
<meta name="description" content="{info['desc']}">
<meta property="og:title" content="{info['title']}">
<meta property="og:description" content="{info['desc']}">
<meta property="og:type" content="article">
<meta property="og:url" content="https://machinetestimony.org/{info['slug']}/">
<meta property="og:image" content="https://machinetestimony.org/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{info['title']}">
<meta name="twitter:description" content="{info['desc']}">
<meta name="twitter:image" content="https://machinetestimony.org/og.png">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/icon.png" type="image/png" sizes="512x512">
<link rel="apple-touch-icon" href="/icon.png">
<link rel="canonical" href="https://machinetestimony.org/{info['slug']}/">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<style>
{css}
{EXTRA}</style>
</head>
<body>

{band}
{body.strip()}
{foot}

</body>
</html>
"""


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    frag = io.open(sys.argv[1], encoding="utf-8").read()
    os.makedirs(os.path.dirname(sys.argv[2]) or ".", exist_ok=True)
    io.open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(build(frag))
    print("wrote %s" % sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())

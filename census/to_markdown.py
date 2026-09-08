"""A page fragment as markdown, for depositing what the site publishes.

    python3 census/to_markdown.py pages/explaining.html > explaining.md

A Zenodo record is the only date on this work that is not stamped by a
repository its author controls, which is the whole reason to deposit. What gets
deposited has to be the same reading the site publishes, so it is generated from
the same file rather than rewritten, and this script exists so that the deposit
and the page cannot drift into two slightly different findings.

It handles the tags these pages actually use and refuses anything it does not
recognise, rather than silently dropping it. A converter that quietly discarded
a table would produce a deposit missing the numbers, which is worse than no
deposit.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import html as _html
import io
import re
import sys

KNOWN = {"p", "h2", "h3", "b", "i", "a", "span", "table", "thead", "tbody",
         "tr", "th", "td", "div", "pre", "ul", "ol", "li", "br"}


def _inline(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<b>(.*?)</b>", r"**\1**", s, flags=re.S)
    s = re.sub(r"<i>(.*?)</i>", r"*\1*", s, flags=re.S)
    s = re.sub(r'<span class="mono">(.*?)</span>', r"`\1`", s, flags=re.S)
    s = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return " ".join(_html.unescape(s).split())


def convert(frag: str) -> str:
    head = re.match(r"<!--title:\s*(.*?)\n.*?slug:\s*([^\s>]+?)-->",
                    frag, re.S)
    title = _inline(head.group(1)) if head else ""
    body = frag[head.end():] if head else frag

    unknown = {t.lower() for t in re.findall(r"<\s*([a-zA-Z0-9]+)", body)} - KNOWN
    if unknown:
        raise SystemExit("unhandled tags, refusing to deposit a partial "
                         "reading: %s" % sorted(unknown))

    out = ["# " + title, ""]
    for m in re.finditer(
            r"<p class=\"dateline\">(.*?)</p>"
            r"|<h2[^>]*>(.*?)</h2>"
            r"|<h3[^>]*>(.*?)</h3>"
            r"|<p class=\"callout\">(.*?)</p>"
            r"|<p>(.*?)</p>"
            r"|<table[^>]*>(.*?)</table>", body, re.S):
        date, h2, h3, callout, para, table = m.groups()
        if date:
            out += ["*%s*" % _inline(date), ""]
        elif h2:
            out += ["## " + _inline(h2), ""]
        elif h3:
            out += ["### " + _inline(h3), ""]
        elif callout:
            out += ["> " + _inline(callout), ""]
        elif para:
            out += [_inline(para), ""]
        elif table:
            rows = []
            for r in re.finditer(r"<tr[^>]*>(.*?)</tr>", table, re.S):
                cells = [_inline(c) for c in
                         re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r.group(1), re.S)]
                if cells:
                    rows.append(cells)
            if rows:
                out.append("| " + " | ".join(rows[0]) + " |")
                out.append("|" + "---|" * len(rows[0]))
                for r in rows[1:]:
                    out.append("| " + " | ".join(r) + " |")
                out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__.split("\n\n")[1].strip())
    sys.stdout.write(convert(io.open(sys.argv[1], encoding="utf-8").read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

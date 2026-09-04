"""Render the census report markdown into the Machine Testimony page body.

The page and the deposited report say the same thing, so they are generated
from one source rather than edited twice and left to drift apart.
"""
import re, sys

src, out = sys.argv[1], sys.argv[2]
lines = open(src, encoding="utf-8").read().split("\n")

# The front matter is rendered by the page header, not by this.
i = lines.index("## Abstract")
body, first_in_section = [], True


def para(text):
    global first_in_section
    cls = "" if first_in_section else ' class="cont"'
    first_in_section = False
    return f"  <p{cls}>{text}</p>"


def inline(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


buf, mode, tbl = [], None, []
while i < len(lines):
    ln = lines[i]

    if ln.startswith("```"):
        if buf:
            body.append(para(inline(" ".join(buf)))); buf = []
        block = []
        i += 1
        while not lines[i].startswith("```"):
            block.append(lines[i]); i += 1
        body.append("  <pre>" + inline("\n".join(block)) + "</pre>")
        i += 1
        continue

    if ln.startswith("|"):
        tbl.append(ln); i += 1
        if i < len(lines) and lines[i].startswith("|"):
            continue
        header = [c.strip() for c in tbl[0].strip("|").split("|")]
        rows = [[c.strip() for c in r.strip("|").split("|")] for r in tbl[2:]]
        cls = ' class="matrix"' if len(header) > 6 and header[0] == "" else ""
        h = "".join(f"<th>{inline(c)}</th>" for c in header)
        b = "\n".join("        <tr>" + "".join(
            f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
        body.append(f'  <div class="scroll">\n    <table{cls}>\n'
                    f"      <thead><tr>{h}</tr></thead>\n      <tbody>\n{b}\n"
                    "      </tbody>\n    </table>\n  </div>")
        tbl = []
        continue

    if ln.startswith("## ") or ln.startswith("### ") or ln.startswith("---"):
        if buf:
            body.append(para(inline(" ".join(buf)))); buf = []
        if ln.startswith("## "):
            t = ln[3:].strip()
            if t == "Notes":
                body.append('  <hr class="endrule">')
            body.append(f'  <h2 class="sec">{inline(t)}</h2>')
            first_in_section = True
        elif ln.startswith("### "):
            body.append(f'  <h3 class="sub">{inline(ln[4:].strip())}</h3>')
            first_in_section = True
        i += 1
        continue

    if re.match(r"^\d+\. ", ln):
        if buf:
            body.append(para(inline(" ".join(buf)))); buf = []
        items = []
        while i < len(lines) and (re.match(r"^\d+\. ", lines[i])
                                  or lines[i].startswith("   ") or not lines[i].strip()):
            if re.match(r"^\d+\. ", lines[i]):
                items.append([re.sub(r"^\d+\. ", "", lines[i]).strip()])
            elif lines[i].strip() and items:
                items[-1].append(lines[i].strip())
            elif not lines[i].strip() and i + 1 < len(lines) and not lines[i + 1].startswith(("   ", "1.", "2.", "3.")):
                break
            i += 1
        body.append('  <ol class="notes">')
        for n, it in enumerate(items, 1):
            body.append(f'    <li id="n{n}">{inline(" ".join(it))}</li>')
        body.append("  </ol>")
        continue

    if not ln.strip():
        if buf:
            body.append(para(inline(" ".join(buf)))); buf = []
        i += 1
        continue

    buf.append(ln.strip()); i += 1

if buf:
    body.append(para(inline(" ".join(buf))))

# Captions sit above their tables and are set apart from body prose.
html = "\n".join(body)
html = re.sub(r'  <p( class="cont")?>(Table \d[^<]*?)</p>',
              r'  <p class="tnote">\2</p>', html)
html = re.sub(r'  <p( class="cont")?>(Tables 1\.1[^<]*?)</p>',
              r'  <p class="tnote">\2</p>', html)
# The abstract is its own block on this template.
html = html.replace('  <h2 class="sec">Abstract</h2>',
                    '  <div class="abstract">\n  <h2>Abstract</h2>', 1)
html = html.replace('  <h2 class="sec">1. What was measured</h2>',
                    '  </div>\n\n  <hr class="abrule">\n\n'
                    '  <h2 class="sec">1. What was measured</h2>', 1)
html = re.sub(r'  <p class="cont">(Keywords:.*?)</p>',
              r'  <p class="kw"><i>Keywords:</i>\1</p>', html)
html = html.replace('<p class="kw"><i>Keywords:</i>Keywords:', '<p class="kw"><i>Keywords:</i>')
open(out, "w", encoding="utf-8", newline="\n").write(html)
print("sections:", html.count('<h2 class="sec">'), "tables:", html.count("<table"),
      "paras:", html.count("<p"))

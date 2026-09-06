#!/usr/bin/env python3
"""Render the questions a buyer sends to their AI supplier.

    python3 census/build_ask.py            # writes pages/ask.html
    python3 build_page.py pages/ask.html public/ask/index.html

The register tells somebody who already found this site what eight systems
record. This is the other direction: a page a buyer forwards to a supplier who
has never heard of any of it, and who then has to go and find out what is being
asked of them.

The wording of each question is written for the person receiving it, because a
requirement phrased for an assessor reading source code is not a question you
can put in an email. The counts are generated from the subject files, so the
claim "six of eight could not answer this" stays true when a verdict changes,
and cannot quietly become decoration.

It lives on the research programme's site rather than on the product's. A
questionnaire hosted by a vendor, asking about capabilities that vendor
happens to have, is a sales tool wearing a lab coat, and any procurement team
worth having would read it that way.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import html
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import rubric      # noqa: E402
import subject     # noqa: E402

OUT = os.path.join(ROOT, "pages", "ask.html")

# The question as a buyer would put it, what a real answer looks like, and the
# answer that sounds like agreement and is not. The last of those is the useful
# column: a supplier rarely says no, and a non-technical reader needs to know
# what a soft yes sounds like.
QUESTIONS = [
    ("R3.5",
     "When your system takes an action on our behalf that needed a human to "
     "approve it, does the record say which person approved it?",
     "A named person or a named role holder, in the record itself, for every "
     "such action.",
     "“All high-risk actions require human approval.” That says a "
     "step exists. It does not say the record names who took it."),
    ("R3.6",
     "Where does that name come from?",
     "From your authentication layer: the session, the token, the directory "
     "entry the approver signed in with.",
     "“The approver is passed in the request.” A name supplied by "
     "the caller is an assertion about a person rather than a fact about one, "
     "and the caller can be the system being approved."),
    ("R3.7",
     "Can the agent approve its own action?",
     "No, and the system enforces it rather than the operator remembering to.",
     "“That would not happen in practice.” Ask what stops it."),
    ("R2.3",
     "If two of your sources disagreed about a fact, does the record keep both, "
     "or only the one the system chose?",
     "Both, with the disagreement recorded as its own thing.",
     "“The system resolves conflicts automatically.” That is the "
     "answer to a different question, and it means the losing side is gone."),
    ("R2.5",
     "When a disagreement was resolved, does the record say who or what "
     "resolved it, and on what basis?",
     "The method, the party, the time, and which side was kept.",
     "“We use confidence scores.” A number is not a reason, and it "
     "does not say who set the threshold."),
    ("R2.1",
     "Can we get from a stored fact back to the source it came from?",
     "A citation in the record that leads to the message, document or API "
     "response the fact was drawn from.",
     "“Everything is logged.” Logs elsewhere are not a citation in "
     "the record, and an auditor cannot join them for you."),
    ("R4.3",
     "If somebody altered a past entry, would anyone be able to tell?",
     "A published scheme under which alteration is detectable, and a way to "
     "run it.",
     "“The database is append-only.” That is a property of your "
     "code path behaving, which is the thing in question."),
    ("R4.2",
     "Could we check that ourselves, without your software and without your "
     "cooperation?",
     "Yes, and here is how. This is the question that separates a record from "
     "a report.",
     "“You can export it and we will verify it for you.” A "
     "verification only the supplier can perform is not one you can rely on "
     "in a dispute with the supplier."),
]

CLOSING = (
    "Can you show us the record for one specific action your system took last "
    "month, end to end?")


def esc(s):
    return html.escape(str(s), quote=True)


def counts():
    docs = subject.load_all(os.path.join(HERE, "subjects"))
    by_id = {r.id: r for r in rubric.REQUIREMENTS}
    out = {}
    for rid in [q[0] for q in QUESTIONS]:
        req = by_id[rid]
        weak = total = 0
        for d in docs:
            if not rubric.applicable(req, d["claims"]):
                continue
            total += 1
            v = (d["assessments"].get(rid) or {}).get("verdict")
            if v in ("absent", "partial", "undetermined"):
                weak += 1
        out[rid] = (weak, total)
    return out, len(docs)


def plain(c):
    """The version that actually gets sent, because nobody forwards a URL to
    procurement; they paste the questions into an email."""
    lines = ["Questions about your system's record of what it did.", ""]
    for i, (rid, q, good, weak) in enumerate(QUESTIONS, 1):
        lines.append("%d. %s" % (i, q))
    lines += ["", "%d. %s" % (len(QUESTIONS) + 1, CLOSING), "",
              "These come from a published assessment of eight agent systems: "
              "https://machinetestimony.org/register/"]
    return "\n".join(lines)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    where = ap.parse_args().out

    c, n = counts()
    worst = max(c.values(), key=lambda t: t[0])[0]

    b = []
    w = b.append
    w("<!--title: Questions to ask your AI supplier")
    w("    desc: Eight questions about what a system records, with what a real "
      "answer looks like and what a soft yes sounds like. Free to send as your "
      "own, and grounded in a published assessment of eight agent systems.")
    w("    slug: ask-->")
    w("")
    w('<div class="wrap main">')
    w("  <div>")
    w('    <p class="dateline">For buyers and risk teams, 5 September 2026</p>')
    w('    <h2 class="label">Questions to ask your AI supplier</h2>')
    w('    <div class="block">')
    w("      <p>If a system acts on your behalf, somebody will eventually ask "
      "you what it did and who allowed it. These are the questions worth "
      "asking before that, in the order they usually matter.</p>")
    w("      <p>They are not a compliance instrument and passing them is not "
      "conformity with anything. They come from a published assessment of "
      "%d agent memory and agent framework implementations, where the counts "
      "below were measured rather than estimated, and each one is a question "
      "at least %d of the %d could not answer well.</p>" % (n, worst, n))
    w("      <p><b>Send them as your own.</b> No attribution, no sign-up, "
      "nothing to buy, and no need to mention where they came from. A "
      "questionnaire is more useful when the supplier answers the question "
      "rather than researching who is asking.</p>")

    w('      <div class="scroller">')
    w('      <table class="reg">')
    w("        <thead><tr><th>Ask</th><th>A real answer</th>"
      "<th>A soft yes</th><th>Could not</th></tr></thead>")
    w("        <tbody>")
    for rid, q, good, weak in QUESTIONS:
        wk, tot = c[rid]
        w('          <tr><td class="w">%s</td><td class="w">%s</td>'
          '<td class="w">%s</td><td class="n">%d of %d</td></tr>'
          % (esc(q), esc(good), esc(weak), wk, tot))
    w("        </tbody>")
    w("      </table>")
    w("      </div>")

    w("      <h3>And then the one that settles it</h3>")
    w("      <p><b>%s</b></p>" % esc(CLOSING))
    w("      <p>Every question above can be answered in good faith by somebody "
      "describing what they believe their system does. This one cannot. Either "
      "the record exists and they can show you, or the conversation has been "
      "about an intention.</p>")

    w("      <h3>The version to paste into an email</h3>")
    w("      <pre class=\"snip\">%s</pre>" % esc(plain(c)))

    w("      <h3>What a good answer is worth, and what it is not</h3>")
    w("      <p>A supplier who answers all of these well has a record you can "
      "read. That is worth a great deal and it is not the same as the record "
      "being true: a system can record precisely what it believed and be "
      "wrong. What these questions establish is whether anybody can find out.</p>")
    w("      <p>None of this is a legal conclusion either. The EU AI Act's "
      "obligations run through Articles 12, 13 and 14, and presumption of "
      "conformity comes from the harmonised standards. A supplier is not "
      "non-compliant because they answered one of these badly, and not "
      "compliant because they answered them all well.</p>")

    w("    </div>")
    w("  </div>")

    w('  <aside class="rail">')
    w('    <h2 class="label">Where the counts come from</h2>')
    w('    <p class="cont">A published assessment of %d systems, every verdict '
      'citing a file and a line at a pinned commit.<br>'
      '<a href="/register/">The register</a><br>'
      '<a href="https://doi.org/10.5281/zenodo.22290922">The dated edition, '
      'with a DOI</a></p>' % n)
    w('    <h2 class="label">If you are the supplier</h2>')
    w('    <p class="cont">The questions come from a published record format. '
      'Implementing it is two files and an afternoon, and you can check '
      'yourself against the same corpus everybody else is checked '
      'against.<br><a href="/implement/">Implementing it</a></p>')
    w("    <hr>")
    w('    <p class="cont"><a href="/assess/">Assess a system yourself</a><br>'
      '<a href="/check/">Check a record</a></p>')
    w("  </aside>")
    w("</div>")

    os.makedirs(os.path.dirname(where) or ".", exist_ok=True)
    io.open(where, "w", encoding="utf-8", newline="\n").write("\n".join(b) + "\n")
    print("wrote %s" % where)
    for rid, _, _, _ in QUESTIONS:
        print("  %-6s could not answer well: %d of %d" % (rid, *c[rid]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

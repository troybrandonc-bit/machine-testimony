"""Typeset Working Paper No. 2 as a plain PDF for deposit.

    python3 make_wp2_pdf.py

WHY NOT PRINT THE PAGE. The browser's print of /papers/wp2/ clipped Table 1 at
both edges: the scroll container the page uses for wide tables has
`overflow-x:auto`, which scrolls on screen and cuts in print, and its negative
margin pushed the first column off the sheet. Rather than bend the site's
stylesheet to suit a printer, the deposit copy is typeset directly. A deposited
PDF is a fixed artifact and wants to be plain.

WHY THE TEXT IS IN THIS FILE. It is the same prose as the HTML, kept here as
data rather than parsed out of the markup, because a regex over HTML that
silently drops a sentence would put a truncated paper in a permanent archive
under a DOI. The two are checked against each other by comparing section
headings, which is what `--check` does.

Copyright 2026 Garnet Taurus Ltd. CC BY 4.0.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, KeepTogether)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "machine-testimony-wp2.pdf"))
SRC = os.path.join(HERE, "public", "papers", "wp2", "index.html")

SERIF = "Times-Roman"
SERIF_B = "Times-Bold"
SERIF_I = "Times-Italic"
MONO = "Courier"

body = ParagraphStyle("body", fontName=SERIF, fontSize=10, leading=14.2,
                      spaceAfter=7, alignment=4)          # justified
first = ParagraphStyle("first", parent=body, spaceBefore=2)
h1 = ParagraphStyle("h1", fontName=SERIF_B, fontSize=19, leading=22,
                    spaceAfter=3)
sub = ParagraphStyle("sub", fontName=SERIF, fontSize=12.5, leading=16,
                     spaceAfter=14, textColor=colors.HexColor("#333333"))
meta = ParagraphStyle("meta", fontName=SERIF, fontSize=9, leading=12.5,
                      textColor=colors.HexColor("#555555"), spaceAfter=3)
auth = ParagraphStyle("auth", fontName=SERIF, fontSize=10.5, leading=14,
                      spaceAfter=1)
sec = ParagraphStyle("sec", fontName=SERIF_B, fontSize=11.5, leading=15,
                     spaceBefore=15, spaceAfter=4)
subsec = ParagraphStyle("subsec", fontName=SERIF_B, fontSize=10.5, leading=14,
                        spaceBefore=11, spaceAfter=3)
abst = ParagraphStyle("abst", parent=body, fontSize=9.5, leading=13.4,
                      leftIndent=10, rightIndent=10, spaceAfter=6)
absth = ParagraphStyle("absth", fontName=SERIF_B, fontSize=10, leading=13,
                       spaceAfter=5, alignment=1)
cap = ParagraphStyle("cap", fontName=SERIF, fontSize=8.5, leading=11.4,
                     spaceAfter=5, textColor=colors.HexColor("#333333"))
item = ParagraphStyle("item", parent=body, leftIndent=14, bulletIndent=2,
                      spaceAfter=5)
note = ParagraphStyle("note", parent=body, fontSize=8.8, leading=11.8,
                      leftIndent=14, bulletIndent=2, spaceAfter=4)
code = ParagraphStyle("code", fontName=MONO, fontSize=8.2, leading=11,
                      leftIndent=12, spaceBefore=4, spaceAfter=7,
                      textColor=colors.HexColor("#222222"))

TITLE = "One of Eight"
SUBTITLE = ("Whether deployed agent systems can record who approved an "
            "action, and whether any law requires them to")

ABSTRACT = [
 "Several jurisdictions now give a person the right to human review of an "
 "automated decision. This paper asks a narrower question that the deployment "
 "of those rights depends on: whether the software that takes the decisions "
 "can produce a record showing which human reviewed one.",

 "Ten widely deployed agent and agent-memory systems were read at pinned "
 "commits against twenty record-keeping requirements. Eight of the ten take or "
 "gate consequential actions. <b>Of those eight, one can identify the person "
 "who approved an action.</b> Six cannot: the structure carrying what a human "
 "decided has no field for which human decided it. One could not be determined "
 "from outside the vendor. The single system that can is the author's own "
 "reference implementation, which is disclosed here rather than left to be "
 "found, and which carries no evidential weight.",

 "Twenty legal and quasi-legal instruments were then read against the same "
 "question. Twelve ask a record to show who intervened in a decision and four "
 "of those are law. The two instruments that ask for a record of the review "
 "itself, rather than for a right to one, are a private certification scheme "
 "and a regulator's published expectation, and neither can require it by law.",

 "The paper reports the method, the per-system verdicts with the commit each "
 "was read at, four corrections made by readers after publication, and the "
 "limits of what a static reading of source code can establish. Every verdict "
 "cites a file and a line so that a wrong one is cheap to demonstrate.",

 "<i>Keywords:</i> AI governance, human oversight, audit trails, agent "
 "frameworks, automated decision-making, conformance measurement.",
]

SECTIONS = [
 ("sec", "1. Introduction"),
 ("p", "A right to human review of an automated decision is now law in at "
       "least four jurisdictions. Article 22(3) of the General Data Protection "
       "Regulation has been applicable since 25 May 2018. Quebec's section 12.1 "
       "has been in force since 22 September 2023, Articles 22A to 22D of the "
       "United Kingdom GDPR since 5 February 2026, and Article 34(1)(4) of "
       "South Korea's Framework Act since 22 January 2026. Colorado's Senate "
       "Bill 26-189 applies from 1 January 2027 and the European Union's "
       "Artificial Intelligence Act applies to high-risk systems from "
       "2 December 2027."),
 ("p", "Each of these creates a duty about a review. None of the four that are "
       "currently law specifies what a record of that review must contain. The "
       "question this paper asks is what happens when somebody tries to satisfy "
       "one of them using software they have already deployed: whether the "
       "record that software produces can say which person reviewed a "
       "particular decision."),
 ("p", "This is a narrower question than whether a system is well governed, and "
       "deliberately so. It is answerable from published source code, which "
       "means it can be measured rather than asserted, and a wrong answer can "
       "be corrected by anybody who reads the same code."),

 ("sec", "2. Method"),
 ("subsec", "2.1 The rubric"),
 ("p", "Twenty requirements were written before any system was read, grouped "
       "into four cumulative conformance levels. They ask what a record "
       "contains, not what a system promises: whether entries carry write "
       "times, whether refusals are recorded as faithfully as permissions, "
       "whether an approval identifies a person, whether the approver's "
       "identity comes from an authentication layer rather than from something "
       "the proposing model can write, and whether a past state of the record "
       "can be verified by a party other than its author."),
 ("p", "The requirement this paper turns on is R3.5, stated in the rubric as: "
       "<i>&ldquo;Does an approval identify a person or a named role "
       "holder?&rdquo;</i> A verdict of <i>present</i> requires that the "
       "approver be a person or a role rather than a model or a process. The "
       "partial case, also written in advance, is that an approval step exists "
       "but the approver may be an automated principal."),
 ("subsec", "2.2 Scope declarations"),
 ("p", "Not every requirement applies to every system. A system that stores "
       "material but takes no actions cannot be failed for lacking an approval "
       "path. Each subject therefore declares a scope, and requirements are "
       "applied only within it. Eight of the ten subjects declare that they "
       "act. The results below concern those eight."),
 ("p", "This distinction was not in the first version of the rubric. It was "
       "added after a reader reported that the validator was refusing a "
       "conformance level to a system that had earned it: a record-only system "
       "with a genuine hash chain could never reach the third level, and "
       "because the levels are cumulative its integrity at the fourth level "
       "stayed invisible however good it was. The scope declaration exists "
       "because of that report."),
 ("subsec", "2.3 Pinned reading"),
 ("p", "Each system was read at a specific commit, recorded with the verdict. "
       "A verdict is a claim about one state of one repository on one date and "
       "nothing more. Every verdict cites a file and a line at that commit, so "
       "a reader who disagrees can open the same line rather than argue about "
       "the conclusion."),

 ("sec", "3. Subjects"),
 ("p", "Ten systems were selected for deployment breadth across agent "
       "frameworks and agent-memory systems: AutoGen, CrewAI, Graphiti, "
       "Haystack, LangGraph, Letta Code, mem0, OMEM, the OpenAI Agents SDK and "
       "Pydantic AI. Eight declare that they act. Graphiti and mem0 declare "
       "storage and derivation without an action path, and are outside the "
       "results below."),
 ("p", "One of the ten, OMEM, is maintained by the author of this paper. That "
       "is stated here, in Section 4 where the result appears, and on every "
       "published page carrying the number, for the reason given in Section 5."),

 ("sec", "4. Results"),
 ("p", "Of the eight systems that take or gate consequential actions, one "
       "records an approval that identifies a person. Six do not. One could not "
       "be determined from outside the vendor."),
 ("table", None),
 ("p", "R3.6 asks whether the approver's identity comes from the "
       "authentication layer rather than from something the proposing model can "
       "write. R3.7 asks whether the acting agent is prevented from approving "
       "its own action. The three move together in every subject, which is the "
       "expected shape: a system with no field for an approver has nowhere to "
       "record where that identity came from, and no principal to compare "
       "against the proposer."),
 ("p", "The failure is structural rather than incidental. In the six systems "
       "marked absent, the object that carries a human's decision has no member "
       "for the human. An integration that wishes to record one must place it "
       "somewhere the framework does not define, which means a later reader "
       "must know where to look and must trust that it was not written by the "
       "model."),
 ("subsec", "4.1 What a right to review meets in practice"),
 ("p", "Twenty legal and quasi-legal instruments were read against the question "
       "of whether the text asks a record to show who intervened in a decision. "
       "Twelve of the twenty do. Four of those twelve are law, as at "
       "13 September 2026: Article 22(3) of the GDPR, Quebec's section 12.1, "
       "Articles 22A to 22D of the UK GDPR, and Article 34(1)(4) of South "
       "Korea's Framework Act."),
 ("p", "Two further instruments are in effect and are not law. One is AIUC-1, a "
       "private certification scheme whose mandatory control E015.2 requires "
       "structured logs capturing approver identity, timestamp and decision "
       "outcome, with a separate control E015.4 requiring those logs to be "
       "tamper-evident. The other is the Information Commissioner's guidance on "
       "automated decision-making, which states that a controller should keep a "
       "record of how a human reviewed a decision. <b>These are the only two "
       "instruments in the set that ask for a record of the review itself "
       "rather than for a right to one, and neither can require it by law.</b>"),

 ("sec", "5. Limitations"),
 ("ol", [
   "<b>The only passing subject is the author's own.</b> OMEM is maintained by "
   "the author of this paper. A measurement whose single positive result "
   "belongs to the party conducting it is worth what its disclosure is worth, "
   "and the appropriate reading of the headline number is <i>one of eight, and "
   "that one is mine</i>. It is reported as a row rather than excluded, because "
   "removing it would hide the fact that the property is achievable.",
   "<b>A static reading establishes what a structure can carry, not what a "
   "deployment does.</b> A framework with no approver field cannot record one; "
   "a framework with a field may still be deployed in a way that never "
   "populates it. The absent verdicts are therefore stronger than the present "
   "one.",
   "<b>Each verdict is against one commit.</b> A system that added the field "
   "after the date recorded beside it is not described by this paper. The "
   "correction mechanism is a pull request against the subject file rather than "
   "a dispute about the conclusion.",
   "<b>One subject is undetermined, and that is a finding rather than a "
   "gap.</b> Letta Code could not be determined from outside the vendor. It is "
   "reported as undetermined rather than absent, because reporting an unknown "
   "as a failure would inflate the headline number in the direction that "
   "favours the author's argument.",
   "<b>Ten systems are not a census of the field.</b> They are ten widely "
   "deployed systems, selected before reading and named in full. The "
   "healthcare, insurance and financial platforms where most consequential "
   "automated decisions are actually taken are mostly not readable from outside "
   "at all, and this paper says nothing about them.",
   "<b>This paper does not establish that a record naming an approver would "
   "make a review meaningful.</b> Whether a reviewer had authority, training, "
   "or the independence to disagree are facts about a person and an "
   "organisation. No record format produces them and none should claim to.",
 ]),

 ("sec", "6. Corrections"),
 ("p", "Four substantive corrections were made to this work by readers after "
       "publication, each of which changed a published claim. They are listed "
       "because a measurement programme that reports only its findings and not "
       "its errors is asking for a trust it has not earned."),
 ("ol", [
   "A reader reported that the reference validator refused the third "
   "conformance level to any record containing no decisions, a requirement that "
   "appeared nowhere in the specification text. The scope declaration described "
   "in Section 2.2 exists because of that report.",
   "A reader pointed out that an expired evidence deadline and a failed action "
   "are different facts and that the format could express neither, because the "
   "member recording execution was a required boolean. An optional outcome "
   "member was added.",
   "A reader observed that every timestamp in a record is written by the party "
   "whose conduct is in question, and that the section listing what a reader "
   "cannot settle from a record did not say so. The specification now names it, "
   "and where a record carries an RFC 3161 token the validator checks that no "
   "entry claims a write time later than the authority's. Back-dating remains "
   "open and the specification says so.",
   "A reader independently reproduced the conformance corpus at a pinned "
   "commit, matching the published totals, then contested one case and was "
   "correct. The same reader subsequently corrected this programme's reading of "
   "Article 12(3)(d) of the EU AI Act, and then verified the fix and found a "
   "further error in it.",
 ]),

 ("sec", "7. Reproduction"),
 ("p", "The subject files, the rubric, and the per-verdict evidence are public. "
       "The census manifest records a digest over the scored material, and the "
       "check recomputes it."),
 ("code", "git clone https://github.com/troybrandonc-bit/machine-testimony\n"
          "python3 census/manifest.py --check"),
 ("p", "The headline number and its method are published at "
       "machinetestimony.org/named-approver/, the full register at "
       "machinetestimony.org/register/, and the dated edition of the census at "
       "machinetestimony.org/census/2026-09/."),

 ("sec", "Notes"),
 ("ol_notes", [
   "Machine Testimony is a research programme, not a registered institute or a "
   "certification body. It publishes readings of public texts and measurements "
   "of public software. It does not certify, audit, or offer an opinion about "
   "any deployment. Correspondence: troy@machinetestimony.com.",
   "The author maintains OMEM, one of the ten subjects, and a record format and "
   "Internet-Draft in the same area. Both interests are disclosed here, in "
   "Section 4, in Section 5, and on every published page that carries the "
   "headline number.",
 ]),
]

ROWS = [
 ("System", "R3.5", "R3.6", "R3.7", "Commit", "Read"),
 ("AutoGen", "absent", "absent", "absent", "027ecf0a379b", "2026-09-04"),
 ("CrewAI", "absent", "absent", "absent", "92eb5f91830c", "2026-09-04"),
 ("Haystack", "absent", "absent", "absent", "82da3adc2fac", "2026-09-06"),
 ("LangGraph", "absent", "absent", "absent", "81bf17b23123", "2026-09-04"),
 ("Letta Code", "undet.", "undet.", "undet.", "e0a0e1e62278", "2026-09-04"),
 ("OMEM", "present", "present", "present", "9a77c2066553", "2026-09-04"),
 ("OpenAI Agents SDK", "absent", "absent", "absent", "89c02c828ee8", "2026-09-04"),
 ("Pydantic AI", "absent", "absent", "absent", "c0e4d824eaa0", "2026-09-06"),
]


def table():
    # Widths total 165mm, inside a 170mm frame, so nothing can be clipped. The
    # browser print cut this table at both edges; fixed columns cannot.
    t = Table(list(ROWS), colWidths=[38*mm, 21*mm, 21*mm, 21*mm, 34*mm, 24*mm],
              repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), SERIF_B),
        ("FONTNAME", (0, 1), (-1, -1), SERIF),
        ("FONTNAME", (4, 1), (4, -1), MONO),
        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
        ("FONTSIZE", (4, 1), (4, -1), 7.8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
    ]))
    return t


def story():
    s = [Paragraph("Machine Testimony Working Paper Series &nbsp;&middot;&nbsp; "
                   "No. 2 &nbsp;&middot;&nbsp; September 2026", meta),
         Paragraph("Not yet deposited at the time of writing. This paper "
                   "carries no DOI, and says so rather than printing one it "
                   "does not have.", meta),
         Spacer(1, 14),
         Paragraph(TITLE, h1),
         Paragraph(SUBTITLE, sub),
         Paragraph("Troy Clifford<super size=6>1</super>", auth),
         Paragraph("Machine Testimony", meta),
         Spacer(1, 12),
         Paragraph("Abstract", absth)]
    for p in ABSTRACT:
        s.append(Paragraph(p, abst))
    s.append(Spacer(1, 6))

    for kind, payload in SECTIONS:
        if kind == "sec":
            s.append(Paragraph(payload, sec))
        elif kind == "subsec":
            s.append(Paragraph(payload, subsec))
        elif kind == "p":
            s.append(Paragraph(payload, body))
        elif kind == "code":
            for line in payload.split("\n"):
                s.append(Paragraph(line.replace(" ", "&nbsp;"), code))
        elif kind == "table":
            s.append(Spacer(1, 4))
            s.append(KeepTogether([
                Paragraph("<b>Table 1.</b> R3.5, whether an approval identifies "
                          "a person, across the eight acting subjects. R3.6 is "
                          "whether that identity comes from an authentication "
                          "layer; R3.7 is whether the agent is prevented from "
                          "approving its own action. undet. is undetermined "
                          "from outside the vendor.", cap),
                table()]))
            s.append(Spacer(1, 9))
        elif kind in ("ol", "ol_notes"):
            st = note if kind == "ol_notes" else item
            for i, x in enumerate(payload, 1):
                s.append(Paragraph(x, st, bulletText="%d." % i))
    return s


def page_furniture(canvas, doc):
    canvas.saveState()
    canvas.setFont(SERIF, 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(20*mm, 12*mm,
                      "Machine Testimony Working Paper No. 2")
    canvas.drawRightString(190*mm, 12*mm, "%d" % doc.page)
    if doc.page > 1:
        canvas.drawString(20*mm, 283*mm, "One of Eight")
        canvas.drawRightString(190*mm, 283*mm, "CC BY 4.0")
    canvas.restoreState()


def build() -> str:
    doc = BaseDocTemplate(OUT, pagesize=A4,
                          leftMargin=20*mm, rightMargin=20*mm,
                          topMargin=20*mm, bottomMargin=20*mm,
                          title=TITLE + ": Can Deployed Agent Systems Record "
                                        "Who Approved an Action?",
                          author="Troy Clifford",
                          subject="AI governance, human oversight, audit trails")
    frame = Frame(20*mm, 20*mm, 170*mm, 257*mm, id="body",
                  leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame],
                                       onPage=page_furniture)])
    doc.build(story())
    return OUT


def check() -> int:
    """Every section heading in the HTML appears in this file, and vice versa.

    A PDF deposited under a DOI is permanent, so a section silently missing
    from it is not a formatting problem.
    """
    html = io.open(SRC, encoding="utf-8").read()
    want = [re.sub(r"<[^>]+>", "", m).strip()
            for m in re.findall(r'<h2 class="sec">(.*?)</h2>', html)]
    want += [re.sub(r"<[^>]+>", "", m).strip()
             for m in re.findall(r'<h3 class="sub">(.*?)</h3>', html)]
    have = [p for k, p in SECTIONS if k in ("sec", "subsec")]
    missing = [x for x in want if x not in have]
    extra = [x for x in have if x not in want]
    for x in missing:
        print("  in the page and not in the PDF: %s" % x)
    for x in extra:
        print("  in the PDF and not in the page: %s" % x)
    print("%d headings on the page, %d in this file, %d mismatched"
          % (len(want), len(have), len(missing) + len(extra)))
    return 1 if (missing or extra) else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="compare section headings against the published page")
    a = ap.parse_args()
    if a.check:
        return check()
    bad = check()
    path = build()
    print("written to %s" % path)
    return bad


if __name__ == "__main__":
    sys.exit(main())

"""The DSIT portfolio, counted: does an assurance technique reach a decision?

    python3 census/dsit_portfolio.py            # the counts
    python3 census/dsit_portfolio.py --read     # the sentences a verdict rests on

The Department for Science, Innovation and Technology publishes a Portfolio of
AI Assurance Techniques at gov.uk/ai-assurance-techniques. It is the United
Kingdom government's own curated answer to "who can assure an AI system", and
on 12 September 2026 it held 75 case studies.

The question asked of it here is the same one this project asks of everything
else. The Information Commissioner expects a deployer to "keep a record of how
the human reviewed the decision". Does anything in the portfolio claim to
produce, check or assure such a record?

TWO STAGES, AND THE FIRST ONE DECIDES NOTHING. A case study is a candidate only
if it uses a word from each of two vocabularies: one for a person in the loop,
one for something kept afterwards. That bounds the reading to a set anybody can
reproduce. Every candidate is then READ, and the verdict cites the sentence.
A word count cannot tell a record of a human review from a record of a model,
and pretending otherwise here would be the error this census exists to catch.

The corpus is committed at census/sources/dsit-portfolio.jsonl, one JSON object
per case study with its path, title and text, fetched 12 September 2026.
Contains public sector information licensed under the Open Government Licence
v3.0.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "sources", "dsit-portfolio.jsonl")

# A person in the loop, under any of the names the field uses for one.
PERSON = (r"\b(human oversight|human review|human-?in-?the-?loop"
          r"|human in the loop|reviewer|approver|approvals?|sign-?offs?"
          r"|escalat\w*|human intervention|human judge?ment)\b")
# Something kept afterwards that somebody could later read.
RECORD = (r"\b(audit trail|logs?|logging|records?|recorded"
          r"|recording|traceab\w*|provenance|evidence|documented)\b")

# The fourteen that use both, read on 12 September 2026, with what the record
# claim is actually ABOUT. Every value here is a judgement made from the
# sentence quoted beside it in `--read`, not from a count.
#
# `layer` is the finding. Not one of them is `decision`.
READ = {
    "anekanta-ai-ai-risk-intelligence-system-for-biometric-and-high-risk-ai":
        ("assessment", "Escalation routes and an emergency stop. What is "
                       "produced is a risk report."),
    "anekanta-r-ai-facial-recognition-privacy-impact-risk-assessment-system-"
    "for-verification-and-remote-biometric-identification":
        ("assessment", "THE CLOSEST IN THE PORTFOLIO. It requires that \"a "
                       "trained operator should always make the final decision "
                       "before any action is taken following a face match\", "
                       "and says plainly that the system \"does not evaluate "
                       "competency\". So the human decision is required and "
                       "the artefact produced is a privacy impact report "
                       "rather than a record that the operator decided."),
    "aveva-pragmatic-approach-to-instil-trustworthiness-in-industrial-ai-"
    "driven-renewable-power-plant-operation":
        ("system", "A register recording \"the development, deployment and use "
                   "of AI systems, as requested by the EU AI Act\". The "
                   "Article 30 shape: a register of systems, not of "
                   "decisions."),
    "clearbank-safeguarding-generative-ai-use-cases-in-a-regulated-fintech-"
    "banking-api":
        ("model", "Traceability of continuous model evaluation. Escalation "
                  "appears as a description of a use case."),
    "deloitte-enhanced-due-diligence-processes-for-third-party-models":
        ("procurement", "A third-party model review fed into \"the client's "
                        "new product approval process\"."),
    "enzai-compliance-assessment-tool":
        ("governance", "\"Controls and signoffs\", and \"capturing evidence "
                       "against certain requirements\". Sign-off on a "
                       "compliance control."),
    "fairly-ai-fairly-end-to-end-ai-governance-platform":
        ("governance", "\"Built-in approval workflow that allows for audit "
                       "trail and accountability tracking\", capturing \"micro-"
                       "decisions of the model developers throughout their "
                       "model development cycle\". Approvals by developers, of "
                       "development."),
    "fairnow-ai-governance-platform-and-ai-governance-program-implementation":
        ("governance", "\"Documentation/approvals stored centrally on the "
                       "platform ensures organisations maintain robust audit "
                       "trails\", and human oversight named as essential to "
                       "the governance programme rather than to a decision."),
    "fairnow-regulatory-compliance-implementation-and-the-nist-ai-rmf-slash-"
    "iso-readiness":
        ("governance", "THE SENTENCE THAT STATES THE WHOLE FINDING BEST, AND "
                       "IT IS THEIRS: \"Full records are kept of governance "
                       "actions to provide an audit trail.\" Governance "
                       "actions."),
    "fsa-developing-an-ai-based-proof-of-concept-that-prioritises-businesses-"
    "for-food-hygiene-inspections-while-ensuring-the-ethical-and-responsible-"
    "use-of-ai":
        ("method", "A human-in-the-loop expert is always involved, and what is "
                   "documented is \"our methodology and evaluation of the "
                   "model and associated risks\"."),
    "logically-ai-testing-and-monitoring-ai-models-used-to-counter-online-"
    "misinformation":
        ("model", "\"Logging its decision or outcome\", where the decision "
                  "logged is the model's. The human-in-the-loop framework is "
                  "for evaluation and training."),
    "mind-foundry-using-continuous-metalearning-to-govern-ai-models-used-for-"
    "fraud-detection-in-insurance":
        ("model", "Data provenance and model lineage, \"a full chain of "
                  "accountability for model behaviour\"."),
    "nvidia-explainable-ai-for-credit-risk-management-applying-accelerated-"
    "computing-to-enable-explainability-at-scale-for-ai-powered-credit-risk-"
    "management-using-shapley-values-and-shap":
        ("model", "Shapley values for credit risk explainability, with a "
                  "human-in-the-loop mention. Explanation of a model output "
                  "rather than a record of who reviewed it."),
    "rai-institute-artificial-intelligence-impact-assessment-aiia":
        ("assessment", "Human oversight is named as a means to establish "
                       "assurance, and what is kept is \"evidence "
                       "documentation provided by an organisation to assert "
                       "the extent to which the controls have been met\". "
                       "Evidence of controls."),
}

LAYERS = ("decision", "governance", "assessment", "model", "system",
          "procurement", "method")


def load() -> list:
    if not os.path.exists(CORPUS):
        raise SystemExit("no corpus at %s" % CORPUS)
    return [json.loads(l) for l in io.open(CORPUS, encoding="utf-8")]


def counted(rows: list) -> dict:
    person = [r for r in rows if re.search(PERSON, r["text"], re.I)]
    record = [r for r in rows if re.search(RECORD, r["text"], re.I)]
    both = [r for r in person if re.search(RECORD, r["text"], re.I)]
    return {"total": len(rows), "person": len(person), "record": len(record),
            "both": len(both),
            "both_slugs": sorted(r["path"].rsplit("/", 1)[-1] for r in both),
            "decision": sorted(k for k, (l, _) in READ.items()
                               if l == "decision")}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    rows = load()
    c = counted(rows)
    if "--read" in argv:
        for r in rows:
            slug = r["path"].rsplit("/", 1)[-1]
            if slug not in READ:
                continue
            layer, why = READ[slug]
            print("=" * 74)
            print("%s  [%s]" % (r["title"][:66], layer))
            print("  " + why)
            sents = re.split(r"(?<=[.!?]) +", r["text"])
            for s in [x for x in sents
                      if re.search(PERSON, x, re.I) and len(x) < 420][:3]:
                print("  | " + s.strip())
            print("")
        return 0

    print("The DSIT Portfolio of AI Assurance Techniques, read 12 September "
          "2026.")
    print("")
    print("  case studies published                      %3d" % c["total"])
    print("  mention a person in the loop                %3d" % c["person"])
    print("  mention something kept afterwards           %3d" % c["record"])
    print("  mention both, and so were read              %3d" % c["both"])
    print("  claim a record of a human review of a decision %d"
          % len(c["decision"]))
    print("")
    by = {}
    for slug, (layer, _why) in READ.items():
        by[layer] = by.get(layer, 0) + 1
    print("  What the fourteen records are actually about:")
    for layer in LAYERS:
        if by.get(layer):
            print("    %-12s %d" % (layer, by[layer]))
    print("")
    print("  Not one is a record of a human review of a particular decision,")
    print("  which is the thing the Information Commissioner says a deployer")
    print("  should keep. Run with --read for the sentence behind each.")
    missing = set(c["both_slugs"]) - set(READ)
    extra = set(READ) - set(c["both_slugs"])
    if missing or extra:
        print("")
        print("  WARNING: the corpus and the read set disagree.")
        for s in sorted(missing):
            print("    unread: %s" % s)
        for s in sorted(extra):
            print("    read but no longer a candidate: %s" % s)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

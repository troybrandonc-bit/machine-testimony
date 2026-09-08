"""Conversion: what a format you already have cannot say.
Run: python3 tests_convert.py

Every project this format would help is already writing receipts in a shape it
invented. For them the useful question is not how to record, it is what their
shape cannot answer, and the converter exists to answer it in one run instead
of one reading of a forty page draft.

So the thing under test is the report rather than the record. A converter that
quietly supplied an approver, or that dropped a row it could not fill, would
produce a clean conversion and a false one, and it would be the exact defect
this format exists to make visible.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_emit as em                                 # noqa: E402
import testimony_validate as tv                             # noqa: E402
from testimony_convert import Mapping, const, convert       # noqa: E402
from testimony_convert import is_otlp, otlp_rows            # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:240])


# A receipt shape nobody here designed: a gate that records what it allowed and
# who approved it, and never records how that principal was resolved.
FOREIGN = [
    {"event": "tool_call", "tool": "issue_refund", "risk": "high",
     "caller": {"agent_id": "agent-1"}, "allowed": True, "ran": True,
     "approval": {"receipt_id": "d_1", "approver": "sam@corp.example"}},
    {"event": "tool_call", "tool": "send_email", "risk": "low",
     "caller": {"agent_id": "agent-1"}, "allowed": False, "ran": False,
     "reason": "outside declared scope"},
    {"event": "heartbeat", "at": "2026-09-08T00:00:00Z"},
]

OTLP = {"resourceSpans": [{"resource": {"attributes": [
    {"key": "service.name", "value": {"stringValue": "support-agent"}}]},
    "scopeSpans": [{"scope": {"name": "instrumentation.langchain"},
     "spans": [
      {"traceId": "a1", "spanId": "b1", "name": "invoke_agent",
       "attributes": [
        {"key": "gen_ai.operation.name",
         "value": {"stringValue": "invoke_agent"}},
        {"key": "gen_ai.agent.id", "value": {"stringValue": "agent-1"}},
        {"key": "gen_ai.tool.name",
         "value": {"stringValue": "issue_refund"}}]},
      {"traceId": "a1", "spanId": "b2", "name": "execute_tool",
       "attributes": [{"key": "gen_ai.tool.name",
                      "value": {"stringValue": "issue_refund"}}]}]}]}]}


DECISION = Mapping("decision", {
    "action_type": "tool", "risk_class": "risk",
    "risk_source": const("policy"),
    "proposed_by.id": "caller.agent_id",
    "proposed_by.kind": const("agent"),
    "verdict": lambda r: "permitted" if r.get("allowed") else "refused",
    "executed": "ran", "reason": "reason",
}, when=lambda r: r.get("event") == "tool_call")


before_js = io.open(os.path.join(ROOT, "public", "review", "review.js"),
                    encoding="utf-8", newline="").read() if os.path.exists(
    os.path.join(ROOT, "public", "review", "review.js")) else ""


def _raises(fn):
    try:
        fn()
        return False
    except Exception:                                          # noqa: BLE001
        return True


def main():
    print("\nit reports what the source could not fill")
    APPROVAL = Mapping("approval", {
        "decision": "approval.receipt_id",
        "approver.id": "approval.approver",
        "approver.kind": const("human"),
        "identity_source": "approval.identity_source",
    }, when=lambda r: "approval" in r)
    out = convert(FOREIGN, APPROVAL)
    check("a field the emitter demands is named in the report, not raised "
          "as a TypeError", out.missing == {"identity_source": 1}, out.missing)
    check("and identity_source is reported even though REQUIRED omits it",
          "identity_source" not in em.REQUIRED["approval"]
          and "identity_source" in out.missing)
    check("the row is not converted rather than converted with a hole",
          out.entries == [], out.entries)
    check("the report says so in words somebody can act on",
          "identity_source" in out.report()
          and "no value for" in out.report(), out.report())

    print("\nit never invents a value")
    src = "".join(open(os.path.join(ROOT, "spec", "testimony_convert.py"),
                       encoding="utf-8"))
    check("nothing in the converter supplies a default for a missing field",
          "or 'unknown'" not in src and 'or "unknown"' not in src
          and "setdefault(req" not in src)
    check("a source with no approver produces no approval entry",
          convert([{"approval": {"receipt_id": "d_1"}}], APPROVAL).entries
          == [])

    print("\nrows it can fill become a record the validator accepts")
    r = em.Record()
    r.scope(acts=True, description="Gate.")
    out = convert(FOREIGN, DECISION, record=r)
    check("only the rows the mapping claims are taken",
          len(out.rows) == 2, [x["type"] for x in out.rows])
    check("both convert with nothing missing",
          out.missing == {} and not out.refusals,
          (out.missing, out.refusals))
    r.seal()
    rep = tv.validate(r.jsonl()).as_dict()
    # It stops at TR-2, and the reason is the finding rather than a defect
    # in the conversion: their format recorded a high-risk action that ran and
    # no approval to go with it, so the level it reaches is the honest one.
    check("it reaches TR-2 and stops where their format runs out",
          rep["level"] == "TR-2", rep["level"])
    check("and names the executed high-risk action with no approval as why",
          any("approval" in c["check"] for c in rep["checks"]
              if not c["ok"] and c["level"] == "TR-3"),
          [c["check"] for c in rep["checks"] if not c["ok"]])
    check("and every check that passed is one the reader can settle or the "
          "record declares", not [c for c in rep["checks"]
                                  if c["basis"] not in ("verified",
                                                        "attested")])

    print("\nit passes the emitter's refusals through rather than around them")
    bad = convert([{"event": "tool_call", "tool": "x", "risk": "high",
                    "caller": {"agent_id": "a"}, "allowed": False,
                    "ran": True, "reason": "no"}], DECISION)
    check("a refused action that also executed is refused, not written",
          bool(bad.refusals) and bad.entries == [], bad.refusals)

    print("\nthe mapping declaration is checked before it is used")
    try:
        Mapping("not_a_type", {})
        ok = False
    except ValueError as e:
        ok = "not an entry type" in str(e)
    check("an unknown entry type is refused where it is written", ok)

    print()
    print("the code published on /implement/ is code that runs")
    # The page invites a stranger to copy this and tells them it works.
    # Only /anchor/ has its commands extracted and run, so the Python on
    # /implement/ is published untested. This covers the conversion snippet
    # at least, by running the page's own text rather than a copy of it that
    # could drift away from what a reader sees.
    import html as _html
    import re as _re
    page = io.open(os.path.join(ROOT, "pages", "implement.html"),
                   encoding="utf-8").read()
    snips = [_html.unescape(m) for m in
             _re.findall(r'<pre class="snip">(.*?)</pre>', page, _re.S)
             if "from testimony_convert import" in m]
    check("the page carries the conversion example", len(snips) == 1,
          len(snips))
    ran, err = False, ""
    if snips:
        code = snips[0].split("print(")[0]
        ns = {"my_receipts": FOREIGN}
        try:
            exec(compile(code, "implement.html", "exec"), ns)
            out = convert(FOREIGN, ns["approvals"])
            ran = "identity_source" in out.missing
        except Exception as e:              # noqa: BLE001
            err = repr(e)
    check("and it runs, and reports what the page says it reports", ran, err)

    cli = [_html.unescape(m) for m in
           _re.findall(r'<pre class="snip">(.*?)</pre>', page, _re.S)
           if "testimony_convert.py" in m and "Mapping(" in m]
    check("the page shows what the suggester actually prints", len(cli) == 1,
          len(cli))
    if cli:
        from testimony_convert import propose
        shown = cli[0]
        real = propose(FOREIGN, "approval")
        check("and every member the page shows is one the tool proposes",
              all(k in real for k in ("decision", "approver.id",
                                      "approver.kind", "identity_source")),
              real)
        check("including the one it says it cannot find",
              "???" in shown and "???" in real)

    print()
    print("it proposes a mapping from their field names, and says it is a guess")
    from testimony_convert import propose, suggest
    got = suggest(FOREIGN, "decision")
    check("an actor member expands to id and kind, never a bare string",
          "proposed_by.id" in got and "proposed_by" not in got, sorted(got))
    check("and finds the id under a name it was not given exactly",
          got.get("proposed_by.id", ("",))[0] == "caller.agent_id", got)

    text = propose(FOREIGN, "approval")
    check("the proposal says on its face that it is not checked",
          "SUGGESTED, not checked" in text and "guess" in text)
    check("a member with no candidate is left commented out, not invented",
          "identity_source" in text and "???" in text, text)
    check("and the kind is marked as coming from the member, not the data",
          "from the member, not your data" in text)

    # The point of the whole exercise: the thing it cannot find in a gate's
    # own log is how the approver was identified, which is the census finding
    # arriving without anybody reading a specification.
    check("what it cannot find in a real gate log is identity_source",
          "identity_source" not in suggest(FOREIGN, "approval"),
          sorted(suggest(FOREIGN, "approval")))

    check("nothing is converted from a suggestion",
          "convert(" not in propose(FOREIGN, "decision"))

    print()
    print("it asks the four questions of a file, for somebody reviewing one")
    from testimony_convert import report
    text = report(FOREIGN, "a-gate.jsonl")
    check("it finds the approver a gate log does record",
          "ANSWERABLE" in text and "approval.approver" in text, text)
    check("and reports the identity source it does not",
          "NOT IN THE FILE" in text
          and "where that identity was resolved from" in text)
    check("and that nothing seals the file",
          "digest, chain or signature" in text)
    check("it counts them rather than leaving a reader to",
          "2 of 4 are not in these rows" in text, text)

    # An auditor has to stand behind a finding, so the finding has to say
    # what it did not look at. Without this the report reads as a statement
    # about the system, which it is not and cannot be.
    check("it states its own scope rather than implying a wider one",
          "does not claim to" in text and "somewhere these rows have never "
          "been" in text)
    check("and carries the command that reproduces it",
          "Reproduce: python3 testimony_convert.py a-gate.jsonl --report"
          in text)

    sealed = [dict(r, prev_hash="sha256:aa", auth={"method": "oidc"})
              for r in FOREIGN]
    better = report(sealed, "sealed.jsonl")
    check("a file that does carry them is reported as answering them",
          "All four are present" in better, better)

    print()
    print("the finding shown to assessors is the finding the tool produces")
    apage = io.open(os.path.join(ROOT, "pages", "assess.html"),
                    encoding="utf-8").read()
    shown = [_html.unescape(m) for m in
             _re.findall(r'<pre class="snip">(.*?)</pre>', apage, _re.S)
             if "--report" in m]
    check("/assess/ shows the report", len(shown) == 1, len(shown))
    if shown:
        real = report(FOREIGN, "their-logs.jsonl")
        for line in ("ANSWERABLE", "NOT IN THE FILE",
                     "2 of 4 are not in these rows"):
            check("and the page and the tool agree on %r" % line,
                  line in shown[0] and line in real)

    print()
    print("the browser reaches the same finding as the command line")
    import subprocess, shutil
    node = shutil.which("node")
    js = os.path.join(ROOT, "public", "review", "review.js")
    if not node:
        print("  NOT VERIFIED: node is not installed, so the browser copy "
              "was not run")
    elif not os.path.exists(js):
        check("public/review/review.js exists", False, js)
    else:
        # Regenerating has to reproduce the committed file, or the page is
        # running something nobody generated.
        gen = subprocess.run(
            [sys.executable, os.path.join(ROOT, "spec",
                                          "build_review_js.py")],
            capture_output=True, text=True)
        after = io.open(js, encoding="utf-8", newline="").read()
        check("regenerating review.js reproduces the committed file",
              gen.returncode == 0 and after == before_js,
              gen.stderr[:120] or "the committed file is not what the "
              "generator produces")

        cases = {"an OpenTelemetry export": otlp_rows(OTLP),
                 "a gate log": FOREIGN,
                 "a sealed log": [dict(r, prev_hash="sha256:aa",
                                       auth={"method": "oidc"})
                                  for r in FOREIGN],
                 "an empty file": []}
        for name, rows in cases.items():
            # pathToFileURL, because an absolute Windows path is not a URL
            # and node refuses it with ERR_UNSUPPORTED_ESM_URL_SCHEME.
            src = ("const u=require('url');"
                   "import(u.pathToFileURL(process.argv[1]).href).then(m=>"
                   "console.log(m.report(JSON.parse(process.argv[2]),"
                   "process.argv[3])))")
            r = subprocess.run([node, "-e", src, js, json.dumps(rows),
                                "their-logs.jsonl"],
                               capture_output=True, text=True)
            got = r.stdout.replace(chr(13), "").rstrip(chr(10))
            want = report(rows, "their-logs.jsonl")
            check("%s reads the same in both" % name, got == want,
                  (r.stderr[:120] or "") + " | js=" + got[:90]
                  + " | py=" + want[:90])

    print()
    print("it reads an OpenTelemetry export, which is where the records are")
    check("an OTLP document is recognised", is_otlp(OTLP))
    rows = otlp_rows(OTLP)
    check("every span becomes a row", len(rows) == 2, len(rows))
    check("attributes are flattened onto the span",
          rows[0].get("gen_ai.tool.name") == "issue_refund", rows[0])
    check("and resource attributes travel with it, since service.name is "
          "not on the span", rows[0].get("service.name") == "support-agent")

    # The regression that matters more than any other here. `approver.id` and
    # `gen_ai.agent.id` both end in `id`. Matching on that leaf reported the
    # agent's own identifier as the approver, which would tell a reader they
    # can say who approved when what they have is the agent approving itself.
    # That is the precise failure this format exists to make visible, produced
    # by the tool that exists to find it.
    got = suggest(rows, "approval")
    check("the agent's own id is NOT offered as the approver",
          got.get("approver.id") is None, got)
    text = report(rows, "otel-export.json")
    check("so a GenAI span export cannot say who approved",
          "NOT IN THE FILE  who approved" in text, text[:300])

    # And the tool must still find a real one, or the guard above is just
    # switching the feature off.
    real = suggest([{"approval": {"approver": "sam@corp.example"}}], "approval")
    check("while a field that means it is still found",
          real.get("approver.id", ("",))[0] == "approval.approver", real)

    print()
    print("it maps the finding onto a clause somebody is assessed against")
    sys.path.insert(0, os.path.join(ROOT, "spec"))
    import criteria

    # The page is the published reading. Two statements of it are two to
    # drift, so every clause in the data has to appear on the page it claims
    # to come from, word for word.
    page = io.open(os.path.join(ROOT, "pages", "eu-ai-act.html"),
                   encoding="utf-8").read()
    flat = " ".join(_re.sub(r"<[^>]+>", " ", page).split())
    for clause, shows, _sig in criteria.EU_AI_ACT:
        want = " ".join(shows.split())
        check("/eu-ai-act/ carries %r as published" % shows[:38],
              want in flat, want[:80])

    gate = [{"ts": "2026-09-02T09:14:02Z", "tool": "issue_refund",
             "risk": "high", "allowed": True, "ran": True,
             "approval": {"approver": "sam@corp"}},
            {"ts": "2026-09-02T09:14:40Z", "tool": "close_account",
             "risk": "high", "allowed": False, "ran": False,
             "reason": "outside declared scope"}]
    text = criteria.against(gate, "eu-ai-act", "client.jsonl")
    check("a clause with everything present is not marked short",
          "COULD EVIDENCE  Art. 14" in text, text[:400])
    check("and the one needing an identity source is",
          "NOT EVIDENCED   Art. 14" in text)
    check("the clock is found under whatever the log calls it",
          "from 'ts'" in text, text[:300])

    # The line that keeps this the right side of the roadmap: it gathers, it
    # does not conclude. A tool that read as a compliance verdict would be
    # the same error as a record that reads as proof.
    for said in ("not legal advice", "not a compliance assessment",
                 "not an opinion about anybody",
                 "not that the obligation is breached"):
        check("it says on its face it is %s" % said, said in text)
    check("and names the reading it measured against, so a wrong one is "
          "cheap to show", "machinetestimony.org/eu-ai-act/" in text)

    check("an instrument nobody has read is refused rather than guessed",
          _raises(lambda: criteria.against(gate, "iso-42001")))

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

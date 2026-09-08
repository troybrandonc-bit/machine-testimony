"""Watching: the history is a record somebody else can check.
Run: python3 tests_watch.py

A single assessment is a consulting deliverable. What makes it a subscription
is that it runs again and can say when something stopped being true. What
makes it defensible is that the history of those readings is not the watcher's
own word.

So the thing under test is the history rather than the finding: that it is
append-only, that a criterion which changes leaves both sides in the file, and
that the whole thing validates as a Testimony Record without any help from the
tool that wrote it.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_validate as tv                              # noqa: E402
import watch as w                                            # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:240])


FULL = {"ts": "2026-09-02T09:14:02Z", "tool": "issue_refund", "risk": "high",
        "risk_source": "registry", "allowed": True, "ran": True,
        "source": "crm://8842", "reason": "n/a",
        "approval": {"approver": "sam@corp", "identity_source": "auth-session"}}
# The same estate after somebody dropped one field. This is the whole product:
# nothing failed, nobody was told, and the evidence quietly stopped being there.
THINNED = dict(FULL, ts="2026-10-02T09:14:02Z",
               approval={"approver": "sam@corp"})


def main():
    tmp = tempfile.mkdtemp()
    hist = os.path.join(tmp, "history.jsonl")

    print("\na first reading starts a history")
    one = w.watch(hist, [FULL], "eu-ai-act", at="2026-09-02T10:00:00Z")
    check("it writes a history", os.path.exists(hist))
    check("and says nothing has changed yet",
          one["changed"] == [] and one["first"], one)

    print("\na later reading names what stopped being evidenced")
    two = w.watch(hist, [THINNED], "eu-ai-act", at="2026-10-02T10:00:00Z")
    check("the dropped identity source is reported as lost",
          len(two["changed"]) == 1 and two["changed"][0][1] is True
          and two["changed"][0][2] is False,
          [(c[0]["clause"], c[1], c[2]) for c in two["changed"]])
    check("and it is the attributability clause",
          "attributable" in two["changed"][0][0]["shows"])

    print("\nand a reading that changes nothing says so")
    three = w.watch(hist, [THINNED], "eu-ai-act", at="2026-11-02T10:00:00Z")
    check("no change is reported when nothing moved", three["changed"] == [],
          three["changed"])
    check("but the reading is still recorded, since absence of change is a "
          "finding somebody may need", three["run"] == 3, three)

    print("\nthe history is a Testimony Record, checked by the validator")
    text = io.open(hist, encoding="utf-8").read()
    rep = tv.validate(text).as_dict()
    check("it reaches a level", rep["level"] in ("TR-2", "TR-4"), rep["level"])
    check("and nothing in it failed", not [c for c in rep["checks"]
                                           if not c["ok"]],
          [c["check"] for c in rep["checks"] if not c["ok"]])
    check("it declares that the watcher takes no actions of its own",
          rep["scope"] == "record only", rep["scope"])

    entries = [json.loads(l) for l in text.split(chr(10)) if l.strip()]
    print("\nboth sides of a change are kept, not overwritten")
    conflicts = [e for e in entries if e["type"] == "conflict"]
    check("the change left a conflict entry", len(conflicts) == 1, conflicts)
    if conflicts:
        sides = conflicts[0]["sides"]
        held = {e["id"]: e for e in entries if e["type"] == "belief"}
        check("naming two beliefs that are both still in the file",
              all(s in held for s in sides), sides)
        check("and they disagree, which is the point",
              held[sides[0]]["polarity"] != held[sides[1]]["polarity"])

    print("\nthe file only ever grows")
    ats = [e["at"] for e in entries]
    check("entries are in non-decreasing write order", ats == sorted(ats))
    check("no id is reused across readings",
          len({e["id"] for e in entries}) == len(entries))
    # Within one reading a field is one observation however many criteria
    # rest on it. ACROSS readings it is a new observation each time, and
    # deduplicating there would claim one look stood for months.
    ev = [e for e in entries if e["type"] == "evidence"]
    per_run = {}
    for e in ev:
        per_run.setdefault(e["id"].split("_")[0], []).append(e["source"])
    check("within one reading, one field is one evidence entry",
          all(len(v) == len(set(v)) for v in per_run.values()), per_run)
    check("and each reading observes again rather than reusing the last one",
          len(per_run) == 3, sorted(per_run))

    print("\nand it can be checked without the tool that wrote it")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "spec", "testimony_validate.py"),
                        hist], capture_output=True, text=True)
    check("the published validator reads it from the command line",
          r.returncode == 0 and "Conformance:" in r.stdout,
          (r.stdout or r.stderr)[-200:])

    print()
    print("it receives OTLP where the collector already sends it")
    import threading, time, urllib.request, urllib.error
    import receive
    rx = os.path.join(tmp, "received.jsonl")
    port = 4319

    def _post(body, ctype="application/json", path="/v1/traces"):
        # Port 0: the OS picks a free one. A fixed port re-bound four times in
        # a row races with the previous socket closing, and a flaky test is
        # worse than no test.
        srv = receive.make_server(rx, "eu-ai-act", "127.0.0.1", 0)
        bound = srv.server_address[1]
        t = threading.Thread(target=srv.handle_request, daemon=True)
        t.start()
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (bound, path),
            data=body if isinstance(body, bytes) else body.encode(),
            headers={"Content-Type": ctype})
        try:
            r = urllib.request.urlopen(req, timeout=8)
            out = (r.status, json.loads(r.read().decode()))
        except urllib.error.HTTPError as e:
            out = (e.code, json.loads(e.read().decode()))
        t.join(timeout=5)
        srv.server_close()
        return out

    OTLP = {"resourceSpans": [{"scopeSpans": [{"spans": [
        {"name": "execute_tool", "startTimeUnixNano": "1788800000000000000",
         "attributes": [{"key": "gen_ai.tool.name",
                        "value": {"stringValue": "issue_refund"}}]}]}]}]}
    code, body = _post(json.dumps(OTLP))
    check("a collector export is accepted and read",
          code == 200 and body.get("read") and body.get("spans") == 1,
          (code, body))
    check("and it becomes a reading in the history", os.path.exists(rx))

    code, body = _post(bytes([0, 1]), "application/x-protobuf")
    check("protobuf is refused with the config line that fixes it, not "
          "misread", code == 415 and "encoding: json" in body.get("error",""),
          (code, body))
    code, body = _post(json.dumps({"not": "otlp"}))
    check("JSON that is not a trace export is refused",
          code == 400 and "resourceSpans" in body.get("error", ""),
          (code, body))
    code, body = _post(json.dumps(OTLP), path="/v1/metrics")
    check("only traces are served, rather than silently accepting the rest",
          code == 404, (code, body))

    print()
    print("and packs a bundle an assessor can check alone")
    import pack
    outdir = os.path.join(tmp, "evidence-pack")
    res = pack.build(hist, outdir)
    for f in ("history.jsonl", "SUMMARY.md", "VERDICT.json"):
        check("the pack carries %s" % f,
              os.path.exists(os.path.join(outdir, f)))
    text = io.open(os.path.join(outdir, "SUMMARY.md"),
                   encoding="utf-8").read()
    check("the summary names what changed and when",
          "2026-10-02T10:00:00Z" in text, text[:600])
    check("and says it is not an opinion about whether anything is met",
          "is a compliance" in text and "assessor" in text
          and "judgement" in text, text[:500])
    check("it tells the assessor to fetch the validator elsewhere, so they "
          "are not running what the assessed party supplied",
          "git clone" in text and "testimony_validate.py" in text)

    # The claim that lets the pack leave the building. The history keeps
    # which field NAME evidenced a criterion, never the field's contents,
    # so a customer identifier in the telemetry cannot ride along in it.
    whole = " ".join(io.open(os.path.join(outdir, f), encoding="utf-8").read()
                     for f in ("history.jsonl", "SUMMARY.md", "VERDICT.json"))
    for secret in ("sam@corp", "crm://8842", "issue_refund"):
        check("no telemetry value rides along in the pack: %r" % secret,
              secret not in whole)
    check("while the field names it rested on are there, which is the point",
          "approval.identity_source" in whole or "identity_source" in whole)

    d = json.load(io.open(os.path.join(outdir, "VERDICT.json"),
                          encoding="utf-8"))
    check("the verdict is the validator's own output, not the pack's",
          d["level"] == tv.validate(io.open(hist, encoding="utf-8").read()
                                    ).as_dict()["level"], d)

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

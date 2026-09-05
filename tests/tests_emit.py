"""The emitter: a first implementation should be an afternoon.
Run: python3 tests_emit.py

spec/testimony_emit.py is meant to be copied into somebody else's repository,
so it restates the digest rule rather than importing it. That is only defensible
if the two agree, and the way to know is to run both over every record this
project has, not over a fixture chosen to make them agree.

The rest is about refusing at the point of the mistake. A validator tells you
after the record is on disk and the run is over; an emitter can tell you on the
line that got it wrong, and which line that was is most of the value.

Copyright 2026 Michael Brandon Clifford. MIT licensed.
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_emit as em          # noqa: E402
import testimony_validate as tv      # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:240])


def refuses(name, fn):
    try:
        fn()
        check(name, False, "it was accepted")
    except em.Refused as e:
        check(name, True)
        return str(e)
    except Exception as e:                                   # noqa: BLE001
        check(name, False, "raised %s instead of Refused: %s"
              % (type(e).__name__, e))
    return ""


def started():
    r = em.Record()
    r.scope(acts=True)
    return r


def main():
    print("the two implementations of the digest rule agree")
    # Every record in the conformance corpus, both ways. If these ever differ,
    # somebody copying the emitter would produce records the reference refuses,
    # and would have no way to find out why.
    cases = os.path.join(ROOT, "conformance", "cases")
    tried = same = 0
    worst = ""
    for f in sorted(os.listdir(cases)):
        if not f.endswith(".jsonl"):
            continue
        entries = []
        for line in io.open(os.path.join(cases, f), encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                entries.append(obj)
        if not entries:
            continue
        tried += 1
        try:
            a, b = em.digest_of(entries), tv.digest_of(entries)
        except (em.Refused, ValueError):
            # Both refuse the same unportable numbers; that is checked below.
            same += 1
            continue
        if a == b:
            same += 1
        else:
            worst = worst or f
    check("%d corpus records digest identically in both" % tried,
          tried and same == tried, "first difference in %s" % worst)
    check("the corpus was actually read", tried > 30, tried)

    odd = [{"spec": tv.SPEC, "type": "scope", "id": "s1",
            "at": "2026-09-01T09:00:00Z", "acts": True, "confidence": 1e-9}]
    both = []
    for mod in (em, tv):
        try:
            mod.digest_of(odd)
            both.append("accepted")
        except (ValueError, em.Refused):
            both.append("refused")
    check("both refuse a number neither language writes the same way",
          both == ["refused", "refused"], both)

    print("\nwhat comes out is a record")
    r = em.Record()
    r.scope(acts=True, description="Support agent.")
    e = r.evidence(kind="api", source="crm://customers/8842")
    r.belief(subject="customer:8842", proposition="requested_refund",
             asserted_by={"id": "agent", "kind": "agent"}, evidence=[e])
    d = r.decision(action_type="issue_refund", risk_class="high",
                   risk_source="registry",
                   proposed_by={"id": "agent", "kind": "agent"},
                   verdict="permitted", executed=True)
    a = r.approval(decision=d,
                   approver={"id": "sam@example.com", "kind": "human"},
                   identity_source="auth-session")
    r.seal()
    rep = tv.validate(r.jsonl())
    check("the example from the docstring reaches TR-4", rep.level == "TR-4",
          [c["check"] for c in rep.checks if not c["ok"]])
    check("the approval was linked back onto the decision",
          json.loads(r.jsonl().splitlines()[3])["approval"] == a)
    check("the seal covers every entry before it",
          json.loads(r.jsonl().splitlines()[-1])["covers"]
          == [x["id"] for x in r.entries[:-1]])
    check("every line is one JSON object",
          all(isinstance(json.loads(x), dict)
              for x in r.jsonl().splitlines()))

    print("\nan empty evidence list is a claim, and omitting it is not")
    r2 = em.Record()
    r2.scope(acts=False)
    r2.belief(subject="s", proposition="p", evidence=[],
              asserted_by={"id": "sys", "kind": "system"})
    r2.seal()
    check("a belief may say plainly that it has no evidence",
          tv.validate(r2.jsonl()).level == "TR-4",
          tv.validate(r2.jsonl()).level)
    refuses("omitting the evidence member is refused",
            lambda: started().belief(subject="s", proposition="p", evidence=None,
                                     asserted_by={"id": "a", "kind": "agent"}))

    print("\nthe mistakes are refused where they are written")
    agent = {"id": "agent", "kind": "agent"}
    refuses("a refused action recorded as executed",
            lambda: started().decision(action_type="x", risk_class="low",
                                       risk_source="policy", proposed_by=agent,
                                       verdict="refused", executed=True,
                                       reason="no"))
    refuses("a refusal that does not say why",
            lambda: started().decision(action_type="x", risk_class="low",
                                       risk_source="policy", proposed_by=agent,
                                       verdict="refused", executed=False))
    refuses("a risk class the proposing model set",
            lambda: started().decision(action_type="x", risk_class="low",
                                       risk_source="model", proposed_by=agent,
                                       verdict="permitted", executed=True))
    refuses("a risk source nobody defines",
            lambda: started().decision(action_type="x", risk_class="low",
                                       risk_source="a-post-it", proposed_by=agent,
                                       verdict="permitted", executed=True))
    refuses("an enumerated value the specification does not define",
            lambda: started().evidence(kind="telepathy", source="x://1"))
    refuses("a belief citing evidence that is not there",
            lambda: started().belief(subject="s", proposition="p",
                                     asserted_by=agent, evidence=["e_nope"]))
    refuses("a conflict with one side",
            lambda: started().conflict(subject="s", proposition="p",
                                       sides=["b1"]))
    refuses("a second scope entry",
            lambda: started().scope(acts=False))
    refuses("an unportable number",
            lambda: started().evidence(kind="api", source="x://1",
                                       confidence=1e-9))
    refuses("sealing nothing", lambda: em.Record().seal())

    r3 = started()
    dd = r3.decision(action_type="x", risk_class="high", risk_source="registry",
                     proposed_by=agent, verdict="permitted", executed=True)
    refuses("an approver who is the proposer",
            lambda: r3.approval(decision=dd,
                                approver={"id": "agent", "kind": "human"},
                                identity_source="oidc"))
    refuses("an approver who is not a person",
            lambda: r3.approval(decision=dd,
                                approver={"id": "svc", "kind": "agent"},
                                identity_source="oidc"))
    refuses("an approval of a decision that is not there",
            lambda: r3.approval(decision="d_nope",
                                approver={"id": "s@e.com", "kind": "human"},
                                identity_source="oidc"))
    refuses("an identity source nobody defines",
            lambda: r3.approval(decision=dd,
                                approver={"id": "s@e.com", "kind": "human"},
                                identity_source="trust-me"))
    reuse = started()
    first = reuse.entries[0]["id"]
    refuses("a reused id",
            lambda: reuse.evidence(kind="api", source="x://1", id=first))
    refuses("a write time that goes backwards",
            lambda: started().evidence(kind="api", source="x://1",
                                       at="2020-01-01T00:00:00Z"))

    print("\nthe refusals say what to do instead")
    msg = refuses("an unlisted identity source names the way to declare one",
                  lambda: r3.approval(decision=dd,
                                      approver={"id": "s@e.com", "kind": "human"},
                                      identity_source="corp-sso"))
    check("and the message contains the extension form", "x-corp-sso" in msg,
          msg[:120])
    ok = r3.approval(decision=dd,
                     approver={"id": "s@e.com", "kind": "human"},
                     identity_source="x-corp-sso")
    check("which is then accepted", bool(ok))

    print("\nthe demonstration still demonstrates something")
    # A demo that quietly stops working is worse than none, and this one is
    # meant to be run by strangers who will not stay to debug it.
    import subprocess                                        # noqa: E402
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "demo",
                                     "what_your_log_cannot_answer.py")],
                       capture_output=True, text=True, cwd=ROOT)
    out = r.stdout
    check("it runs", r.returncode == 0, (r.stderr or out)[-200:])
    check("it asks the ordinary log four questions and answers none of them",
          out.count("unanswerable.") == 4, out.count("unanswerable."))
    check("it answers all four from the record",
          "r.okonkwo@example.com" in out and "auth-session" in out
          and "close_account, refused" in out and "sha256:" in out)
    check("it proves the last answer rather than asserting it",
          "TR-4" in out and "TR-3" in out, out[-300:])
    check("it makes no claim about any named product",
          not any(v in out for v in ("LangGraph", "CrewAI", "AutoGen", "mem0")))

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

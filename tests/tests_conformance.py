"""The corpus a third party checks themselves against.
Run: python3 tests_conformance.py

A conformance corpus that has drifted from the implementation it describes is
worse than none: somebody builds against it, passes, and is wrong. So the
committed cases and their expected verdicts are rebuilt here and compared, and
both implementations are run through the corpus the way an outsider would run
theirs.

The runner is checked too. It is the file a stranger copies, and it has already
had one defect that would have told every Windows user their implementation
produced no answer.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
CONF = os.path.join(ROOT, "conformance")
sys.path.insert(0, os.path.join(ROOT, "spec"))

import testimony_validate as tv        # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + "  " + str(detail)[:240])


def main():
    expected = json.load(io.open(os.path.join(CONF, "expected.json"),
                                 encoding="utf-8"))

    print("the corpus has not drifted from the validator")
    # Rebuild into a copy and compare, rather than over the top, so a failing
    # run leaves the committed corpus alone.
    work = tempfile.mkdtemp()
    r = subprocess.run([sys.executable, os.path.join(CONF, "build.py"),
                        "--out", os.path.join(work, "conformance")],
                       capture_output=True, text=True)
    check("it rebuilds", r.returncode == 0, r.stderr[:200])
    rebuilt = json.load(io.open(os.path.join(work, "conformance",
                                             "expected.json"), encoding="utf-8"))
    check("every verdict is still the verdict the reference reaches",
          rebuilt == expected,
          sorted(k for k in set(rebuilt) | set(expected)
                 if rebuilt.get(k) != expected.get(k))[:4])
    same = True
    for name in expected:
        a = os.path.join(CONF, "cases", name + ".jsonl")
        b = os.path.join(work, "conformance", "cases", name + ".jsonl")
        if io.open(a, encoding="utf-8").read() != io.open(b, encoding="utf-8").read():
            same = False
            break
    check("every case file is what build.py produces", same)

    print("\nthe corpus covers what it says it covers")
    reached = {}
    for v in expected.values():
        reached[v["level"]] = reached.get(v["level"], 0) + 1
    check("every level is represented, including none",
          set(reached) == {None, "TR-1", "TR-2", "TR-3", "TR-4"}, reached)
    check("more than forty cases", len(expected) > 40, len(expected))
    check("every case carries a note explaining what it is for",
          all(v.get("note") for v in expected.values()))
    for name in ("digest-of-nothing", "anchor-over-another-record"):
        check("%s does not reach TR-4" % name,
              expected[name]["level"] != "TR-4", expected[name]["level"])
    check("a record a third party signed does reach TR-4",
          expected["anchor"]["level"] == "TR-4")

    print("\nboth implementations pass it, the way an outsider would run them")
    ref = [sys.executable, os.path.join(ROOT, "spec", "testimony_validate.py"),
           "--json", "{file}"]
    r = subprocess.run([sys.executable, os.path.join(CONF, "run.py"),
                        "--command", " ".join(
                            '"%s"' % p if " " in p else p for p in ref)],
                       capture_output=True, text=True, cwd=ROOT)
    check("the Python reference agrees with the corpus on every case",
          r.returncode == 0, (r.stdout + r.stderr).strip()[-300:])

    if shutil.which("node"):
        cmd = ("node --experimental-strip-types --no-warnings "
               '"%s" {file}' % os.path.join(ROOT, "spec",
                                            "testimony_validate_js.mts"))
        r = subprocess.run([sys.executable, os.path.join(CONF, "run.py"),
                            "--command", cmd],
                           capture_output=True, text=True, cwd=ROOT)
        check("the TypeScript port agrees with the corpus on every case",
              r.returncode == 0, (r.stdout + r.stderr).strip()[-300:])
    else:
        print("  NOT VERIFIED: node is absent, so the second implementation "
              "was not run through the corpus")

    print("\nthe runner behaves for somebody who is not us")
    # It is the file a stranger copies. It has already had one defect that
    # told every Windows user their implementation produced no answer, because
    # shlex ate the backslashes in the path.
    r = subprocess.run([sys.executable, os.path.join(CONF, "run.py"),
                        "--command", "definitely-not-a-real-program {file}"],
                       capture_output=True, text=True, cwd=ROOT)
    check("a command that does not exist is reported, not crashed on",
          r.returncode != 0 and "NO ANSWER" in r.stdout,
          (r.stdout + r.stderr)[-200:])

    liar = os.path.join(work, "liar.py")
    io.open(liar, "w", encoding="utf-8").write(
        'import json,sys\n'
        'print(json.dumps({"level": "TR-4", "levels_met": '
        '{"TR-1": True, "TR-2": True, "TR-3": True, "TR-4": True}}))\n')
    r = subprocess.run([sys.executable, os.path.join(CONF, "run.py"),
                        "--command", '%s "%s" {file}' % (sys.executable, liar)],
                       capture_output=True, text=True, cwd=ROOT)
    check("an implementation that claims TR-4 for everything is caught",
          r.returncode != 0 and "DIFFERS" in r.stdout,
          (r.stdout + r.stderr)[-200:])

    quiet = os.path.join(work, "quiet.py")
    io.open(quiet, "w", encoding="utf-8").write("pass\n")
    r = subprocess.run([sys.executable, os.path.join(CONF, "run.py"),
                        "--command", '%s "%s" {file}' % (sys.executable, quiet)],
                       capture_output=True, text=True, cwd=ROOT)
    check("an implementation that prints nothing is reported as no answer",
          r.returncode != 0 and "NO ANSWER" in r.stdout,
          (r.stdout + r.stderr)[-200:])

    # A validator that reports only the level, with no levels_met and no scope,
    # is a reasonable thing to write and must not be failed for what it does
    # not claim.
    terse = os.path.join(work, "terse.py")
    io.open(terse, "w", encoding="utf-8").write(
        "import json,sys,os\n"
        "sys.path.insert(0, %r)\n"
        "import testimony_validate as tv\n"
        "r = tv.validate(open(sys.argv[1], encoding='utf-8').read())\n"
        'print(json.dumps({"level": r.level}))\n'
        % os.path.join(ROOT, "spec"))
    r = subprocess.run([sys.executable, os.path.join(CONF, "run.py"),
                        "--command", '%s "%s" {file}' % (sys.executable, terse)],
                       capture_output=True, text=True, cwd=ROOT)
    check("a validator that reports only the level still passes",
          r.returncode == 0, (r.stdout + r.stderr).strip()[-300:])

    shutil.rmtree(work, ignore_errors=True)
    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

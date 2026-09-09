"""The five adapter examples: that they agree, and that they say what they lack.

    python tests/tests_examples.py

The anchored path is duplicated across five standalone packages because each one
must install without the others. Duplication is the price of that, and the price
of duplication is drift, so this holds the five copies to each other byte for
byte and holds the wording to what the specification actually says.

It does not run the examples. That is the adapter suites' job and it needs five
frameworks installed. This reads them.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTERS = ["langgraph", "crewai", "autogen", "openai-agents", "pydantic-ai"]

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + ((": %s" % (detail,)) if detail else ""))


def src(a, name="example.py"):
    p = os.path.join(ROOT, "adapters", a, name)
    return io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def helper(text):
    """The anchored() helper, from def to the return at the end."""
    m = re.search(r"def anchored\(.*?\n    return path\n", text, re.S)
    return m.group(0) if m else ""


print("every example has the anchored path")

for a in ADAPTERS:
    check("%s has one" % a, bool(helper(src(a))))

# Five copies of a helper is five things to drift. They are byte-identical or
# this fails, which is the same bargain the bundled validator already makes.
bodies = {a: helper(src(a)) for a in ADAPTERS}
first = bodies[ADAPTERS[0]]
odd = [a for a in ADAPTERS if bodies[a] != first]
check("all five copies are byte-identical", not odd, odd)


print("")
print("it says what an unanchored record is, and does not overstate it")

# The reason this work exists: a reader who runs an example and sees TR-4 must
# not conclude TR-4 means externally anchored. All five reach TR-4 offline with
# scheme hash-chain and anchor null.
check("the default path says there is NO external anchor",
      "NO external anchor" in first)
check("and says the hash chain is recomputable by whoever holds the record",
      "recomputable by anyone who can rewrite the entries" in first)
check("and gives the command that adds one",
      "testimony_anchor" in first and "--anchor" in first)

check("the anchored path prints what the anchor does not prove",
      "does_not_prove" in first)

# Appending an anchor can LOWER the level. An example that assumed otherwise
# would be the same overclaim in the other direction.
check("it reports the level rather than assuming the anchor helped",
      "res.level" in first and "not met" in first)
check("and explains the clock check rather than leaving a mystery",
      "clock skew, not backdating" in first)
check("and says anchoring seconds after writing is not the real pattern",
      "anchors a record that is finished" in first)

# The flag exists because a test suite that needs somebody else's timestamp
# authority is not a test suite, and CI runs the default path.
check("anchoring is opt-in, so the example runs offline",
      "if not want:" in first)
for a in ADAPTERS:
    check("%s parses --anchor without eating the path" % a,
          'x != "--anchor"' in src(a))


print("")
print("the wheels carry what the examples import")

for a in ADAPTERS:
    hb = src(a, "hatch_build.py")
    check("%s bundles the anchor module" % a,
          "testimony_anchor.py" in hb, "the example would ImportError")
    check("%s bundles the validator it imports from" % a,
          "testimony_validate.py" in hb)

# Bundled copies are build artifacts. Committing one is the second copy the
# build hook exists to prevent.
gi = io.open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
for a in ADAPTERS:
    check("%s bundled anchor copy is git-ignored" % a,
          "adapters/%s/testimony_anchor.py" % a in gi)
    check("%s has no committed anchor copy" % a,
          not os.path.exists(os.path.join(ROOT, "adapters", a,
                                          "testimony_anchor.py")))

print("")
print("%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)

# Testimony Records from CrewAI

_Packaged and tested; the first publish to PyPI is pending, so for
now it is one file._ Copy `testimony_crewai.py` and
[`testimony_emit.py`](../../spec/testimony_emit.py) next to your crew. There is
nothing else to install and nothing here depends on OMEM.

```python
from testimony_crewai import Recorder

def decide(req):
    # req.action, req.args, req.risk_class.
    # Your approval UI, queue or ticket goes here. The identity has to come
    # from your authentication layer; this adapter has none to find.
    if req.action == "close_account":
        return req.refuse("a balance is outstanding")
    return req.approve(approver={"id": "r.okonkwo@example.com", "kind": "human"},
                       identity_source="auth-session")

rec = Recorder(
    agent={"id": "support-agent", "kind": "agent"},
    risk={"issue_refund": "high", "close_account": "high",
          "search_docs": "low"},
    decide=decide,
)
agent.tools = rec.gate_all(agent.tools)
crew.kickoff()
rec.write("record.jsonl")
```

```
$ python3 testimony_validate.py record.jsonl
Conformance: TR-4
```

## Why it wraps tools instead of using a hook

CrewAI has no before-tool hook. `step_callback` fires *after* a step, which is
enough to observe a tool call and not enough to gate one.
[crewAI#5888](https://github.com/crewAIInc/crewAI/issues/5888) says so plainly:
*"the only way to enforce this is by wrapping each tool's `_run` method
individually, which doesn't compose"*.

So this wraps, and composing is the part it does for you. `gate_all` returns
tools with the same names, descriptions and argument schemas, so the model sees
no difference and nothing downstream changes. The inner tool's own `run()` is
what executes, so validation, usage limits and failure policy all still apply.
Nothing is monkeypatched.

## What it will not do

**It will not fail open.** If your `decide` returns anything that is not a
decision it issued, the call raises and the tool does not run.
[openai-agents-python#4845](https://github.com/openai/openai-agents-python/issues/4845)
is the same mistake in a shipped SDK: a callable `needs_approval` predicate
returned `None` from an unhandled branch, `None` read as "no approval needed",
and the gate opened on the path nobody had thought about. A gate whose failure
mode is *allowed* is not a gate.

**It will not classify risk from anything the model produced.** Risk comes from
a table you own, and a tool missing from that table raises at wrap time rather
than defaulting mid-run.

**It will not invent an approver,** and it will not let the acting agent
approve its own action or accept an identity source the model could have
written.

A refusal comes back to the agent as text rather than an exception, because
that is how CrewAI already reports a tool that declined, and an agent that can
read the refusal can take the other path. The refusal is recorded with the same
standing as a permission: a system that records only what it did is a receipt,
not an account of itself.

## Tests

`tests/tests_crewai_testimony.py`, 30 checks, run against real CrewAI. CI
installs the library and fails if the suite skips.

MIT. Copyright 2026 Garnet Taurus Ltd.
The specification: <https://datatracker.ietf.org/doc/draft-clifford-testimony-record/>

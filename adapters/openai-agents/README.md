# Testimony Records from the OpenAI Agents SDK

One file. Copy `testimony_openai_agents.py` and
[`testimony_emit.py`](../../spec/testimony_emit.py) next to your agent. There is
nothing else to install and nothing here depends on OMEM.

```python
from agents import Agent, Runner, function_tool
from testimony_openai_agents import Recorder

def decide(req):
    # req.action, req.arguments, req.risk_class.
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
result = await rec.run(Runner, agent, "Refund order 8842")
rec.write("record.jsonl")
```

```
$ python3 testimony_validate.py record.jsonl
Conformance: TR-4
```

## This SDK already has the gate. It cannot say who opened it

Unlike the other adapters here, nothing in this one adds an approval boundary.
`needs_approval` on a tool already stops the run, `result.interruptions`
already lists what is waiting, and `state.approve(item)` already lets it
through. That machinery is good and this does not replace it.

What `state.approve(item)` does not take is **a principal.** It records that a
call was approved, not by whom, and any code holding the state can call it,
including the process that proposed the action. So a run where an engineer read
the arguments and decided is indistinguishable afterwards from one where a
script approved everything.

An [assessment of eight agent systems](https://machinetestimony.org/register/)
published in September 2026 recorded exactly that for this SDK: whether an
approval identifies a person, whether the identity comes from the
authentication layer, and whether the agent is prevented from approving its own
action were all **absent**, and in each case because there is nowhere to put
the answer.

This does not fix that by inventing an approver. It fixes it by refusing to
write an approval unless you supply an identity from your own authentication
layer, and by making the omission visible rather than silent.

## What it will not do

**It will not fail open.**
[#4845](https://github.com/openai/openai-agents-python/issues/4845) is the
neighbouring mistake in this very SDK, one layer down: a callable
`needs_approval` predicate returned `None` from an unhandled branch, `None`
read as "no approval needed", and the gate opened on the path nobody had
thought about. If your `decide` returns anything that is not a decision this
issued, the run raises and the tool does not execute.

**It will not classify risk from anything the model produced,** let the acting
agent approve its own action, or accept an identity source the model could have
written.

A refusal is passed to `state.reject` with your reason as the rejection
message, so the model is told why rather than told nothing, and it is recorded
with the same standing as a permission.

## Tests

`tests/tests_openai_agents_testimony.py`, 29 checks, against a real `Runner`
with no API key and no network: only the model is scripted, against the SDK's
public `Model` interface. The agent, the Runner, the tool, the interruption,
`to_state` and `approve`/`reject` are all the real ones, because those are what
is under test.

MIT. Copyright 2026 Garnet Taurus Ltd.
The specification: <https://datatracker.ietf.org/doc/draft-clifford-testimony-record/>

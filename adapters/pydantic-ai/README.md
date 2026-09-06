# Testimony Records from Pydantic AI

```
pip install testimony-pydantic-ai
```

Or one file: copy `testimony_pydantic_ai.py` and
[`testimony_emit.py`](../../spec/testimony_emit.py) next to your agent. There is
nothing else to install and nothing here depends on OMEM.

```python
from pydantic_ai import Agent
from testimony_pydantic_ai import Recorder

def decide(req):
    # req.action, req.arguments, req.tool_call_id, req.risk_class.
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
result = rec.run_sync(agent, "Refund order 8842")
rec.write("record.jsonl")
```

```
$ testimony-validate record.jsonl
Conformance: TR-4
```

## Why this one exists, in a line of their own type signature

Pydantic AI already has the pause. `DeferredToolRequests` carries the calls
waiting for a person and `DeferredToolResults` carries the answers. Those
answers are typed:

```python
approvals: dict[str, bool | DeferredToolApprovalResult]
```

**A bare `True` approves.** That is not a criticism of the design, which is
cleaner than most: `ToolApproved` carries `override_args`, so the framework
already understands that what was approved and what the model proposed can
differ. But a boolean has nowhere to put a person, and
[an assessment of eight agent systems](https://machinetestimony.org/register/)
found that is where almost all of them stop. Of the six that take or gate
actions, one could name the person who approved one. Four could not, because
approval is stored as a boolean and the identity was never written down.

So this adapter never writes one. It requires an approver and a source for that
approver's identity, or it refuses to record an approval at all.

## What the approver allowed, not what the model asked for

[pydantic-ai#6968](https://github.com/pydantic/pydantic-ai/issues/6968) is the
framework side of a defect that is also open in
[Haystack](https://github.com/deepset-ai/haystack/issues/12060) and named from
the other direction in
[AutoGen](https://github.com/microsoft/autogen/issues/5891): an approver shown
one set of arguments while another set executes has not approved the action
that happened.

`req.approve(..., arguments=...)` becomes the framework's `override_args`, and
the record then carries both: `arguments` is what the person allowed and
`proposed_arguments` is what the model asked for. A reader can see the
difference instead of inferring it from which version was deployed.

## What it will not do

**It will not fail open.** If your `decide` returns anything that is not a
decision it issued, the run raises and no tool executes.
[openai-agents-python#4845](https://github.com/openai/openai-agents-python/issues/4845)
is that mistake in a shipped SDK: a callable predicate returned `None` from an
unhandled branch, `None` read as "no approval needed", and the gate opened.

**It will not classify risk from anything the model produced.** Risk comes from
a table you own, and a tool missing from it raises rather than defaulting.

**It will not invent an approver,** let the acting agent approve its own action,
or accept an identity source the proposing model could have written.

**It will not answer a deferred external call.** Those are results only the
caller can supply, and inventing one would put a fact in the record that never
happened.

A refusal becomes a `ToolDenied` carrying your reason, so the model is told why
rather than told nothing, and it is recorded with the same standing as a
permission.

## Tests

`tests/tests_pydantic_ai_testimony.py`, 35 checks, against a real `Agent` with
the framework's own `FunctionModel`. No network and no API key: only the model
is scripted. The tools, `requires_approval`, the pause and the resume are the
real ones. CI installs the library and fails if the suite skips.

MIT. Copyright 2026 Garnet Taurus Ltd.
The specification: <https://datatracker.ietf.org/doc/draft-clifford-testimony-record/>

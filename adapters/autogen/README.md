# Testimony Records from AutoGen

```
pip install testimony-autogen
```

Or one file: copy `testimony_autogen.py` and
[`testimony_emit.py`](../../spec/testimony_emit.py) next to your agent. There is
nothing else to install and nothing here depends on OMEM.

```python
from autogen_core.tools import StaticWorkbench
from testimony_autogen import Recorder

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
workbench = rec.gate(StaticWorkbench(tools))   # hand this to the agent
...
rec.write("record.jsonl")
```

```
$ python3 testimony_validate.py record.jsonl
Conformance: TR-4
```

## Why the workbench is the right boundary

`Workbench.call_tool` is the one place every tool call passes through, and it
is an abstract method on a public class, so a workbench that wraps a workbench
is a supported thing to build rather than a trick.
[autogen#7405](https://github.com/microsoft/autogen/issues/7405) and the open
issue proposing a workbench-level approval gate are asking for exactly this
seam.

`list_tools` passes straight through, so the model sees the same schemas, and
`start`, `stop`, `reset`, `save_state` and `load_state` all delegate to the
workbench underneath. The agent, the model client and the team configuration
are untouched.

## Colorado asks for this from 1 January 2027

Proposed Rule 7.7 under Colorado's Automated Decision-Making Technology Act
requires a deployer to retain a record showing, when a human reviews an
automated decision: **the reviewer's identity**, review timestamps, the primary
evidence available to them, whether they **approved, modified or overrode** the
output, and a written justification. The rules were filed on 11 August 2026 and
take effect with the act on 1 January 2027 if adopted. They are not law yet.

A reading of ten widely deployed agent systems found that of the eight which
take or gate consequential actions, **one can identify the person who approved
one**, and that one is the reference implementation of this specification, which
is disclosed rather than left to be found.

### What this framework can show, measured

AutoGen has no approval pause of its own, which is why this adapter works at the
workbench rather than at a hook: there is no boundary in the framework to attach
one to. That is not a criticism. It is a multi-agent conversation library and it
never claimed to be an authorisation layer.

The consequence for Rule 7.7 is direct. Nothing in a plain AutoGen run identifies
a person on any approval path, because there is no approval path, so every one of
the six things the rule asks a record to show has to come from the boundary you
put around it.

Read 4 to 6 September 2026 at
[machinetestimony.org/register/](https://machinetestimony.org/register/), with
the file and line behind every verdict.

## What it will not do

**It will not fail open.** If your `decide` returns anything that is not a
decision it issued, the call raises and the tool does not run.
[openai-agents-python#4845](https://github.com/openai/openai-agents-python/issues/4845)
is the same mistake in a shipped SDK: a callable `needs_approval` predicate
returned `None` from an unhandled branch, `None` read as "no approval needed",
and the gate opened on the path nobody had considered.

**It will not classify risk from anything the model produced,** invent an
approver, let the acting agent approve its own action, or accept an identity
source the model could have written.

**It will not gate `call_tool_stream`,** and says so rather than pretending. A
decision has to precede the action, and a stream that has begun has already
acted. Use `call_tool` for anything that needs an approval on the record.

A refusal comes back as a `ToolResult` with `is_error` set, because that is how
a workbench already reports a call that produced no result. It is recorded with
the same standing as a permission: a system that records only what it did is a
receipt, not an account of itself.

## Tests

`tests/tests_autogen_testimony.py`, 28 checks, run against a real
`autogen_core` workbench. CI installs the library and fails if the suite skips.

MIT. Copyright 2026 Garnet Taurus Ltd.
The specification: <https://datatracker.ietf.org/doc/draft-clifford-testimony-record/>

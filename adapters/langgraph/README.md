# A Testimony Record from a LangGraph human-in-the-loop flow

One file, LangGraph as its only dependency, and nothing from OMEM.

```bash
pip install testimony-langgraph
```

```python
rec.approve(graph, config,
            approver={"id": "sam@example.com", "kind": "human"},
            identity_source="auth-session")
rec.write("record.jsonl")
```

```bash
testimony-validate record.jsonl
# Conformance: TR-4
```

The reference validator ships with the package, so a record can be checked by
whoever is holding it without cloning anything. It is one standard-library file
with no network access, and it is the same file this repository uses, copied in
at build time rather than forked.

## What problem this solves

LangGraph pauses a graph with `interrupt()` and resumes it with
`Command(resume=value)`. The resume payload says which interrupt it answers and
carries a value. **It has no field for who answered**, and no principal is
modelled on that boundary, so any code holding the thread can resume it,
including the process that raised the pause.

That is not a defect in LangGraph. It is a graph and checkpointing library and
it never claimed to be an authorisation layer. But the consequence is that an
approval flow built on `interrupt()` produces, by default, a record in which a
run where an engineer read the arguments and decided is indistinguishable from
one where a script resumed everything automatically.

This is measured rather than asserted. A September 2026 assessment of eight
agent memory and agent framework implementations
([10.5281/zenodo.22290922](https://doi.org/10.5281/zenodo.22290922)) examined
the six that take or gate actions. Against the question "does an approval
identify a person or a named role holder", four were assessed absent and one
could not be established either way. LangGraph 1.2.11 was one of the four, with
the evidence pinned to `libs/langgraph/langgraph/types.py`.

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

`langgraph` is the strongest of the six read on what a reviewer was shown: a
graph paused with `interrupt(value)` keeps the displayed material verbatim as a
pending write on the checkpoint, so a consumer can reconstruct it. It is also
one of only two that can tell a **modification** from an approval, because
`HumanResponse` types the outcome as accept, ignore, response or edit rather
than as a boolean.

What it cannot do is name the person. Nothing on the resume boundary carries a
principal, which is the gap this adapter exists to close, and `modify()` carries
the edit through to the record so a reviewer who changed the arguments is not
recorded as having approved them unchanged.

Read 9 September 2026 at
[machinetestimony.org/approval-binding/](https://machinetestimony.org/approval-binding/),
with the file and line behind every verdict.

## What this adapter does not do

**It does not invent an approver.** The identity does not exist anywhere in
LangGraph for it to find. What it does instead is refuse to write an approval
unless you supply an identity from your own authentication layer, and make the
omission visible rather than silent: resume the graph without going through
`approve()` or `refuse()` and the record still says exactly what happened, it
simply does not reach TR-3.

Three things it refuses outright, each of them a way to produce a plausible
file that lies:

| refusal | why |
|---|---|
| an action absent from your risk table | a default risk class is a guess wearing a policy's clothes |
| `identity_source` the model could have written | `request-body`, `model`, `prompt`, `plan`, `agent`, or empty |
| approver id equal to proposer id | an agent's own credential signing off its own action satisfies every other requirement and is worth nothing |

It also refuses to write a record while an action is still awaiting a verdict,
because that file would describe a gate that never closed.

## Usage

Your node names the action in the interrupt payload. That name is what the risk
table is keyed on, and the table belongs to you rather than to the model:

```python
def gate(state):
    ok = interrupt({"action": "issue_refund",
                    "args": {"ticket": state["ticket"], "amount": state["amount"]}})
    return {"refunded": bool(ok)}
```

```python
from testimony_langgraph import Recorder

rec = Recorder(
    agent={"id": "support-agent", "kind": "agent"},
    risk={"issue_refund": "high", "send_receipt": "low"},
    risk_source="registry",
)

ev = rec.cite("api", "billing://orders/8812", digest="sha256:...")
rec.believe("customer:acme", "eligible_for_refund", evidence=[ev])

rec.invoke(graph, {"ticket": 41}, config)      # runs until the interrupt

rec.approve(graph, config,
            approver={"id": "troy@example.com", "kind": "human"},
            identity_source="auth-session")    # from YOUR auth, not the payload

rec.write("record.jsonl")
```

### A reviewer who changed something

The value a boolean cannot carry, and the one Rule 7.7 asks for twice. Without
it a reviewer who rewrote a refund amount and one who waved the original through
produce the same record.

```python
rec.modify(graph, config,
           approver={"id": "troy@example.com", "kind": "human"},
           identity_source="auth-session",
           args={"ticket": 41, "amount": 1})   # what will actually run
```

The decision records the arguments that ran and keeps `proposed_args` beside
them; the approval records `disposition: "modified"` with `changed` naming the
fields that moved. It refuses arguments identical to the proposal and tells you
to call `approve()` instead, because calling that a modification would
misdescribe the review.

`refuse()` records `disposition: "overrode"`. `approve()` records `"approved"`.
All three are new in 0.2.0 and need `testimony-record/0.3`.


Refusing is recorded with the same standing as permitting, because a system
that only records what it did is a receipt:

```python
rec.refuse(graph, config, reason="amount exceeds desk limit",
           approver={"id": "troy@example.com", "kind": "human"},
           identity_source="auth-session")
```

`rec.warnings()` says out loud what a record will not demonstrate, before you
find out from a validator.

## What the levels mean here

- **TR-1** the record is well formed and append-only
- **TR-2** beliefs cite their evidence, or say there is none
- **TR-3** actions are gated, and approvals name a person from authentication
- **TR-4** an integrity digest covers the record

The example reaches TR-4. Delete the `approve()` call and resume the graph
directly, the way an application does today, and it stops below TR-3. That
difference is the entire contribution of this file.

## On the integrity entry

The digest covers every entry written before it, so any later alteration of the
file is detectable by anyone holding the value. **It does not prove the file was
not rewritten wholesale by whoever produced it.** That needs an external anchor,
and this scheme does not claim to be one. See the security considerations in the
specification.

## Specification

- Internet-Draft: <https://datatracker.ietf.org/doc/draft-clifford-testimony-record/>
- Reference validator: `spec/testimony_validate.py`, one stdlib file, no network
- Licence: MIT. The specification text is CC BY 4.0. Implementing it costs
  nothing and requires no permission.

The point of the adapter is that you can read it in one sitting, copy it, and
change it. If it is wrong about what LangGraph carries across the resume
boundary, the fix is a pull request and the assessment above should be corrected
too.

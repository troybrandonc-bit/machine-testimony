# The conformance corpus

52 records and the verdict each one should get. If you are implementing the
Testimony Record, this is how you find out whether you have finished.

```
python3 run.py --command "python3 my_validator.py --json {file}"
```

Your command is run once per case with `{file}` replaced by the path to a
record. It must print a JSON object to standard output carrying at least:

```json
{"level": "TR-3",
 "levels_met": {"TR-1": true, "TR-2": true, "TR-3": true, "TR-4": false}}
```

`level` is `null` when no level is reached. `spec` and `scope` are compared if
you report them and ignored if you do not.

`run.py` has no dependencies and imports nothing from this project. Copy it
into your own repository and run it in your own CI, which is the whole point:
a conformance claim you can only check with our software is worth nothing.

## What conformance means here

Your implementation reaches the same verdict as the reference on all 52 cases.

It does not mean the same check names, the same wording, the same number of
checks, or the same explanations. Those are this project's prose. A corpus that
compared them would be testing whether you had transliterated somebody else's
file rather than whether you had implemented a specification, and an
independent implementation is the entire point. The comparison is deliberately
blind to everything except the answer.

It is also not a certificate. It is a statement about 52 cases, and the
specification is larger than any 52 cases.

## When you disagree

A case you fail is not necessarily your bug. If you have read the
specification and reached a different answer, that disagreement is worth more
than this corpus is: open an issue naming the case. The reference has been
wrong before and the specification has been vaguer than it knew. Two of the
checks here exist because somebody said so.

## What the corpus covers

| | |
|---|---|
| no level | 12 cases: malformed JSON, unknown types, missing required members, invented enum values, reused ids, times that go backwards |
| TR-1 | 6 cases: well formed, and failing something at TR-2 |
| TR-2 | 12 cases: evidence that resolves, conflicts that keep both sides, resolutions that name what was kept |
| TR-3 | 18 cases: gates, refusals that did not execute, approvals that name a person other than the proposer, provenance declared from somewhere the model cannot write, and actions whose effect the record cannot confirm |
| TR-4 | 4 cases: a hash chain, a replay that names its engine, a number that serialises portably, and a record a Time Stamp Authority actually signed |

The TR-4 cases are the ones worth reading first if you are short of time.
`digest-of-nothing` is sixty-four zeros where a digest should be, and it
reached TR-4 in this project's own validator until 5 September 2026.
`anchor-over-another-record` carries a genuine, correctly signed RFC 3161 token
issued over a different record, which also passed. Both now fail, and an
implementation that accepts either has the same hole.

## Rebuilding

The cases are committed, so you get files rather than a generator. `build.py`
regenerates them and their expected verdicts from the reference validator;
`tests/tests_conformance.py` fails if what is committed is not what the
reference currently produces, so the corpus cannot quietly drift away from the
implementation it describes.

Two implementations pass it today, one in Python and one in TypeScript, written
separately and compared on every case. Neither is by another party, which is
the honest state of this format and is stated in the Internet-Draft as well.

## Licence

MIT for `run.py` and `build.py`, CC BY 4.0 for the corpus, like the
specification. Use it however you need to.

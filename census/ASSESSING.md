# Assessing a system yourself

This is the instrument, not a report. If you audit AI systems, advise on
Article 12 or Article 14, or need to answer a procurement question about what a
supplier's agent records, you can run these questions yourself and you do not
need anybody's permission.

**You may charge for it.** The rubric and every subject file are CC BY 4.0, the
tooling is MIT. Commercial use is expected rather than tolerated. There is no
fee, no licence to sign, no certification body, no partner tier, and nothing to
buy. If billing a client for an assessment run with this is useful to you, do
that; it is the intended use.

The one thing you may not do is present a verdict as checked when it was not.
That is not a licence condition, it is what the tooling refuses.

## What it is

Twenty requirements across four levels, derived from the Testimony Record
specification. Each is a question with a stated bar for `present` and for
`partial`, so two assessors reading the same source should reach the same
answer, and where they do not the disagreement is about the code rather than
about the question.

```
python3 census/run.py                    # the table
python3 census/run.py --check            # do these assessments hold up
python3 census/run.py --for langgraph    # one subject, in prose
python3 census/build_register.py         # the standing register
```

## The method

1. **Clone the subject at a commit and stay there.** An assessment of "the
   latest version" is false as soon as the software moves. The tooling requires
   a full 40-character object id, not an abbreviation, because an abbreviated
   one leaves room to argue about which tree was read.

2. **Declare what the system claims to do.** `claims` is a list, and a
   requirement that does not apply is not counted against the subject. A memory
   store that takes no actions is not marked down for having no approval gate.

3. **Answer each requirement with a verdict and its evidence.** The verdicts are
   `present`, `partial`, `absent`, `undetermined` and `not_applicable`.

4. **Cite where you looked, including for absence.** This is the rule the whole
   thing rests on. Saying a system does not record something, without saying
   where you looked, is an accusation wearing a measurement's clothes. An
   `absent` or `undetermined` verdict must carry evidence of kind `searched`,
   and the tooling rejects the file otherwise.

   Evidence kinds are `source` (a file and line), `docs`, `api`, `run`, `test`
   and `searched`.

5. **Use `undetermined` when you cannot see.** It exists because a system's
   approval record may live in a server that is not in the repository the
   harness lives in, and the choice was otherwise between calling a capability
   absent without looking at it and calling it present without looking at it.
   `undetermined` does not clear a level, and it is a better answer than a
   guess.

6. **Run `--check` before you publish.** It refuses assessments nobody else can
   go and check, which is what makes publishing one defensible.

## Conflicts of interest

If you assess a system you built, sell, or are paid by, say so in the file and
in anything you publish, and expect the row to be read as carrying no
evidential weight. That is what this project does with its own row and it costs
nothing to be honest about.

If a client pays you to assess their own system, that is issuer-pays and a
reader is right to discount it. The most useful assessments are the ones
commissioned by the party who has to rely on the answer.

## Publishing it

You have three options and no obligation.

**Keep it.** It is your work product. Nothing here asks you to publish anything,
and a client deliverable that never leaves their building is a perfectly good
use of this.

**Publish it yourself.** CC BY 4.0 asks for attribution to the rubric, not
permission. Your assessment is yours.

**Add it to the register.** Open a pull request against `census/subjects/` at
<https://github.com/troybrandonc-bit/machine-testimony>. It has to pass
`run.py --check`, which is the same bar every row already there had to clear.
`assessed_by` carries your name, and the register shows it, so a reader can see
who read what. A second assessor disagreeing with an existing row is more
useful than a new subject, and a pull request that changes a verdict and cites
why is the best thing that could arrive here.

## Correcting somebody else's verdict

Including this project's. Point at the code. A verdict here has been wrong
before and the remedy has never been an argument. Open a pull request naming
the requirement and where to look, and if it lands the file changes, the
register changes, and the date on the row changes.

## What this is not

It is not a certification, an accreditation, or a mark. Nobody is entitled to
call themselves conformant because a file in this repository says so, and no
system is non-compliant with any law because a row here says `absent`. The EU
AI Act's requirements run through Articles 12, 13 and 14, and presumption of
conformity comes from the harmonised standards, not from this.

What this gives you is a repeatable reading of what a system actually records,
with every answer traceable to a line of somebody's source. That is worth
money to the person who has to rely on it, which is why you should feel free
to charge them for it.

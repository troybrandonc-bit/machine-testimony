---
title: "The Testimony Record: An Interchange Format for What an Automated System Believed and Did"
abbrev: "Testimony Record"
docname: draft-clifford-testimony-record-02
category: info
ipr: trust200902
submissionType: independent
area: "Applications and Real-Time"
keyword:
  - accountability
  - provenance
  - audit
  - autonomous agents
stand_alone: yes
pi: [toc, sortrefs, symrefs]

author:
  -
    ins: T. Clifford
    name: Troy Clifford
    organization: Machine Testimony
    email: troy@machinetestimony.com
    uri: https://machinetestimony.org

# RFC 2119 and RFC 8174 are deliberately absent here: the bcp14
# boilerplate below declares them itself, and naming them in both places
# makes kramdown warn that the reference is inline and in the header.
normative:
  RFC8259:
  RFC7493:
  RFC3339:
  RFC7464:

informative:
  RFC9162:
  I-D.ietf-scitt-architecture:
  TR-SPEC:
    title: "The Testimony Record: specification source, reference validator and adapters"
    author:
      ins: T. Clifford
      name: Troy Clifford
    date: 2026
    target: https://github.com/troybrandonc-bit/machine-testimony
  CENSUS:
    title: "The Testimony Record Conformance Census: What Eight Agent Systems Record About What They Did"
    author:
      ins: T. Clifford
      name: Troy Clifford
    date: 2026-09
    seriesinfo:
      DOI: 10.5281/zenodo.22290922
  EU-AI-ACT:
    title: "Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence"
    author:
      org: European Parliament and Council of the European Union
    date: 2024

--- abstract

This document specifies the Testimony Record, an append-only interchange format
for the account an automated system gives of its own operation: what it
believed, what evidence each belief rested on, which of its beliefs
contradicted one another, what actions it attempted, and who authorised the
consequential ones.

The format is defined so that a party who was not present, and who has no
access to the emitting system, can read a record and check specific properties
of it. Four conformance levels are defined, each stating a property that can be
verified mechanically rather than asserted.

This is not a logging format. Logs record what a program did. A Testimony
Record states what a system claimed to know, what disagreed with it, and what
it was permitted to do about it.

--- middle

# Introduction

Automated systems increasingly hold beliefs about people and take actions on
the strength of them. When such an action is later questioned, the questions
asked are consistent: what did the system believe at that moment, where did
that belief come from, was there anything contradicting it, and who allowed the
action to proceed.

Existing formats answer none of these. Structured logging records events.
Distributed tracing records calls. Neither retains what a system concluded, nor
whether two of its conclusions disagreed, nor whether a person with a name
permitted a consequential action or a process did so unattended.

The gap is not hypothetical. A survey of eight agent memory and agent framework
implementations {{CENSUS}} assessed six that take or gate actions, five of them
written by someone other than this document's author. Against the requirement
that an approval identify a person or a named role holder, four of those five
were assessed absent and the fifth could not be established either way. None
was assessed present. A run in which an engineer read the arguments and decided
produces a record indistinguishable from one in which a script approved
everything automatically.

## Scope

This document specifies a serialisation and a set of conformance levels. It
does not specify how a system forms beliefs, how it should resolve
disagreements, what risk classification it should apply, or how it should
authenticate an approver. Those are properties of an implementation. This
document specifies what such a system must be able to write down about them.

## Design Constraints

Three observations shape the format.

First, a record whose completeness cannot be checked is worth little regardless
of its accuracy. A conformance claim the reader cannot verify is an adjective.

Second, silently resolving a disagreement destroys the only evidence that the
system was ever uncertain. Both sides of a contradiction are therefore
retained, and resolution, if it occurs, is recorded as an event with an actor.

Third, an ungrounded belief must be expressible. A system that cannot state
"believed, and nothing supports this" will, under pressure to produce
well-formed output, produce support that does not exist.

# Conventions and Definitions

{::boilerplate bcp14-tagged}

Record:
: A sequence of entries describing one system over one period.

Entry:
: A single JSON object; one element of the serialisation.

Emitter:
: The system that produced the record.

Actor:
: A JSON object carrying at least `id` and `kind`, where `kind` is one of
  `agent`, `human`, `system` or `connector`. It MAY carry `name` and `role`.

Subject:
: The thing a belief is about. Frequently a person.

Proposition:
: A claim about a subject, expressed as a stable token or URI rather than as
  prose, so that two entries can be compared.

Consequential action:
: An action with an effect outside the emitter.

# Serialisation

A record is a sequence of JSON texts {{RFC8259}} in the I-JSON {{RFC7493}}
profile, encoded in UTF-8. Two framings are defined and carry the same entries:

Line-delimited:
: One JSON text per line, separated by LF. This is the common on-disk form and
  is used throughout this document for readability.

Sequence:
: JSON Text Sequences {{RFC7464}}, each JSON text preceded by RS (0x1E). This
  is the self-delimiting form, and the one the media type in
  {{iana-considerations}} names.

Converting between them is mechanical. A parser MAY accept both, and can
distinguish them by the leading octet.

Every entry MUST contain the following members.

spec:
: The specification version this entry conforms to. This document specifies
  `testimony-record/0.2`. All entries in one record MUST name the same version.

type:
: One of `belief`, `evidence`, `conflict`, `decision`, `approval`, `integrity`,
  `scope`.

id:
: A string unique within the record. An identifier MUST NOT be reused, in this
  record or in a later one from the same emitter.

at:
: The time the entry was written, as an {{RFC3339}} timestamp. This is the
  write time and not the time any described fact held. Entries MUST appear in
  non-decreasing write-time order.

An entry MAY carry members not defined here. A consumer MUST ignore members it
does not recognise.

# Entry Types

## scope

At most one per record, declaring what the emitting system does. Introduced in
`testimony-record/0.2`; a record naming `testimony-record/0.1` MUST NOT carry
one.

acts:
: Boolean. REQUIRED. Whether the emitter takes or gates consequential actions.

declared_by:
: An Actor. OPTIONAL. What made the declaration.

A record with no scope entry is read as `acts: true`, which is what every
`testimony-record/0.1` record means. A record declaring `acts: false` MUST NOT
contain a decision entry. A record that contradicts its own declaration is not
describing the system it claims to describe, and fails at the lowest
conformance level rather than at the level it would otherwise have skipped.

## belief

subject, proposition:
: REQUIRED. What the belief concerns, and what is claimed.

polarity:
: REQUIRED. `affirm` or `deny`.

state:
: REQUIRED. `believed_true`, `believed_false`, `contradicted` or `unknown`, as
  at write time. A later entry may supersede it. This entry is never edited.

asserted_by:
: REQUIRED. An Actor.

evidence:
: An array of evidence entry identifiers. REQUIRED at TR-2 and above. An empty
  array asserts that the belief is ungrounded, and MUST be representable.

## evidence

kind:
: REQUIRED. `document`, `message`, `event`, `api`, `human` or `derived`.

source:
: REQUIRED. A stable identifier for where the material came from.

digest:
: OPTIONAL, RECOMMENDED. A content hash, so a cited source can be shown
  unchanged without the record carrying its content.

excerpt:
: OPTIONAL. The quoted material itself.

redacted:
: OPTIONAL boolean. True where content was deliberately withheld. The citation
  still stands, and a digest allows the holder of the source to show it
  unchanged.

## conflict

subject, proposition:
: REQUIRED. What is disagreed about.

sides:
: REQUIRED. Two or more belief identifiers. Every one of them MUST be present
  in the record as a belief entry.

resolution:
: An object or null. Null is valid, and frequently the honest value: a
  disagreement that nothing resolved is a fact about the system. A non-null
  resolution MUST carry `method`, `by`, `at` and `kept`, and `kept` MUST be one
  of the identifiers in `sides`.

Where a belief has `state` of `contradicted`, a conflict entry naming that
subject and proposition MUST be present.

## decision

action_type:
: REQUIRED. What was proposed.

risk_class:
: REQUIRED. `low`, `medium` or `high`.

risk_source:
: REQUIRED at TR-3. Where the risk class came from, named from this list:
  `registry`, `policy`, `catalogue`, `catalog`, `configuration`, `config`,
  `regulation`, `operator` or `human`. A deployment whose source is none of
  these writes it with an `x-` prefix, as in `x-inhouse-registry`, so that a
  reader sees an extension rather than a value they might mistake for a defined
  one. Omitting the member does not satisfy the requirement, and neither do
  `model`, `plan`, `prompt`, `request`, `request-body` or `agent`, a risk class
  originating in the proposing model's own output being no gate at all.

: What this member establishes is bounded, and the bound should be stated
  rather than discovered. It is an assertion by the emitter. No reader can
  confirm from the record that a registry exists or that the class in the entry
  came from it. Requiring a named value rather than free text makes the
  assertion specific and comparable across systems; it does not make it
  evidence.

proposed_by:
: REQUIRED. An Actor.

verdict:
: REQUIRED. `permitted` or `refused`.

executed:
: REQUIRED. Boolean. Whether the system observed the action run. A decision
  with `verdict` of `refused` MUST NOT record `executed` as true.

outcome:
: OPTIONAL. `confirmed`, `not_attempted` or `unconfirmed`. What the record
  claims about the effect, as distinct from what the system observed. The
  boolean above cannot carry that claim on its own: an action that was
  dispatched and whose acknowledgement never arrived is not an action that did
  not happen, and a reader who treats it as one may retry an action that
  already ran. This member is the same distinction a belief entry draws when
  its state is unknown, applied to actions. A record MUST NOT contradict
  itself. Where the system observed the action run, this member if present MUST
  be `confirmed`. Where the action was refused, it MUST be `not_attempted`.

reason:
: REQUIRED where the verdict is `refused`.

inputs:
: OPTIONAL. Identifiers of the beliefs the decision rested on.

approval:
: The identifier of an approval entry. REQUIRED where `risk_class` is `high`
  and `executed` is true.

## approval

decision:
: REQUIRED. The identifier of the decision this approval permits, which MUST be
  present in the record.

approver:
: REQUIRED. An Actor whose `kind` is `human`.

identity_source:
: REQUIRED. Where the approver's identity was obtained, named from this list:
  `auth-session`, `session`, `api-key`, `jwt`, `oidc`, `oauth`, `saml`, `mtls`,
  `webauthn`, `passkey`, `signed-token`, `directory`, `sso`, `ldap` or
  `kerberos`. Anything else is written with an `x-` prefix. The values excluded for `risk_source` are excluded here, and a
  name the proposing model produced does not satisfy the requirement.

: Like `risk_source`, this is an assertion. A record cannot show that the name
  in an approval came from the session it names, and a validator reading the
  record cannot either. It is worth requiring because a system that records no
  approver at all cannot be asked afterwards who decided, and one that records
  a name and where it says the name came from can at least be contradicted by
  its own logs.

method:
: OPTIONAL. How the approval was given.

The approver MUST NOT be the principal named in the approved decision's
`proposed_by`. An implementation that lets an acting agent's own credential
sign off its own action does not meet the level, however the name in the entry
is spelled.

## integrity

scheme:
: REQUIRED. `replay`, `hash-chain`, `signature` or `external-anchor`.

digest:
: REQUIRED. `sha256:` followed by the lowercase hexadecimal SHA-256 of the
  canonical form of the entries `covers` names, computed as in
  {{digest-computation}}. A digest whose computation is not specified cannot be
  recomputed by a reader, which is the only thing that makes it worth
  recording.

engine, engine_version:
: REQUIRED where the scheme is `replay`. A replay nobody else can reproduce is
  not a verification.

covers:
: OPTIONAL in general, REQUIRED at TR-4. Identifiers of the entries the digest
  is computed over, in the order they are hashed, each of which MUST be present
  in the record. A digest that does not say what it is over cannot be
  recomputed by anyone, so a record reaching the verifiable level cannot omit
  this.

anchor:
: REQUIRED where the scheme is `external-anchor`. An object carrying `kind`,
  `authority` and `token`. The point of an external anchor is that its evidence
  is held by somebody other than the emitter, so a scheme naming no authority
  and carrying no token is the claim without the thing, and is refused.

An `external-anchor` of kind `rfc3161` carries, as `token`, the base64 of a
TimeStampResp {{!RFC3161}} obtained from a Time Stamp Authority over the
entry's digest. The `messageImprint` of the TSTInfo in that token MUST be
the entry's digest: a token signed over anything else is a valid timestamp
for some other record and says nothing about this one.
Such a token is verifiable by any RFC 3161 implementation, without reference to
the emitter or to this document's tooling, which is the property that makes it
worth more than a digest the emitter computed. It fixes the bytes and the time
and nothing else: it does not establish that the record is accurate, that it is
complete, or that a different record was not also produced and discarded.

## Computing a digest {#digest-computation}

An implementation computes the digest of an integrity entry as follows.

1. Take the entries `covers` names, in the order it names them.

2. Serialise each as a JSON object with no insignificant whitespace, its
   members ordered by name comparing names as sequences of Unicode code points,
   and members whose names begin with U+005F LOW LINE omitted. Those are reader
   annotations rather than record content, and a digest that varied with them
   would change when a tool added a line number.

3. Join the serialised entries with a single U+000A LINE FEED, with none after
   the last.

4. Encode the result as UTF-8 and take its SHA-256. The `digest` member is
   `sha256:` followed by the lowercase hexadecimal.

Member names defined by this document are ASCII, so ordering by code point and
the UTF-16 code unit ordering of {{!RFC8785}} cannot differ for them. An
extension using non-ASCII member names should expect that they can, and should
not.

Numbers are the one place where two implementations can serialise the same
value into different bytes. A number that is a whole number is written without
a fraction, as {{!RFC8785}} requires: `1`, never `1.0`. Outside that,
implementations agree on the shortest representation that round-trips, but not
on where to switch to an exponent, so a covered entry MUST NOT contain a number
whose magnitude is below 0.0001 or at or above 1e21, nor an integer whose
magnitude exceeds 2^53. An implementation encountering one refuses the record
rather than emitting a digest another implementation would not reproduce.

# Conformance Levels

Each level states a property of the record. The level reached is the highest
for which nothing at that level or below is unmet.

## TR-1: Recorded

The record parses, is not empty, and names one known specification version
throughout. Every entry has a known type, its required members, allowed values
for enumerated members, a unique identifier and a well-formed write time.
Entries are in non-decreasing write-time order, which is what append-only looks
like from outside. At most one scope entry is present, and a record declaring
that it does not act contains no decisions.

## TR-2: Explained

Every belief states its evidence, including by stating that there is none, and
every cited evidence entry is present. Every conflict names at least two sides,
and every side is retained as a belief in the record. A belief marked
contradicted has a conflict entry naming it. A resolved conflict records the
method, the actor, the time, and which side was kept.

## TR-3: Gated

The record contains at least one decision, unless the emitter has declared that
it does not act. Every decision's risk class comes from outside the proposing
model's control. A refused action did not execute, and records its reason. An
executed high-risk action has an approval entry. Every approval names a human,
sourced from authentication rather than from model output, and that human is
not the proposer.

An emitter declaring `acts: false` satisfies this level by having no actions to
gate. This is satisfaction rather than exemption: such a system may reach TR-4.

## TR-4: Verifiable

The record publishes an integrity scheme; every integrity entry carries a
digest and says which entries that digest is over; everything an integrity
entry claims to cover is present in the record; and, for each entry, the digest
is the digest of exactly those entries, computed as in {{digest-computation}}.
Where the scheme is `external-anchor`, the token names an authority and the
message imprint that authority signed is the digest in the entry.

The name of this level is a claim about what a reader can do, so the checks
behind it are arithmetic over bytes already in the record rather than
statements about the emitter. The exception is `replay`, which names an engine
whose behaviour no reader can confirm from the record. It is reported as an
attestation, and a record whose only integrity is a replay claim reaches this
level on the emitter's word.

## What a Level Rests On {#what-a-level-rests-on}

The checks behind these levels are not all of one kind, and a level reported
without saying so is a number standing on an unknown mixture.

A **verified** check is one a reader can settle from the record alone. That the
evidence a belief cites is present, that both sides of a conflict are retained,
that a refused action is not also recorded as executed, that a digest is the
digest of the entries it covers, that the authority named in an anchor signed
that digest and not a different one. A reader who disagrees with a validator
about any of these can settle it without asking anybody.

An **attested** check is one the record asserts and no reader can confirm from
it. That a risk class came from a registry. That an approver's name came from
an authenticated session. That a replay engine reproduces what it claims to.
These are worth requiring, because a system that records nothing cannot be
contradicted and one that records a specific claim can be. They are not
evidence, and a conformance report that presents them as though they were is
making the error this format exists to make visible.

An implementation reporting a level SHOULD report, for each level, how many of
its checks were of each kind. The reference validator does. A level cited
without that distinction is a weaker statement than it appears.

## On the Ordering

The levels are cumulative, which conflates two independent properties: whether
a system gates its actions, and whether its record can be shown unaltered. A
system may hold a genuine hash chain and gate nothing, and before the scope
entry existed such a system reported TR-2 however good its integrity was.

The scope entry resolves the case where the system does not act. It does not
resolve the general case. Implementations reporting conformance SHOULD report
each level's own result alongside the level reached, so that a satisfied level
sitting behind an unmet one below remains visible, and SHOULD report the
declared scope with the level, because "TR-4, record only" is a different
sentence from "TR-4".

# Security Considerations

A record is evidence about a system, and frequently about people.

A record is not a secure log below TR-4. Nothing in the format prevents an
entry being altered after the fact. Non-decreasing write times demonstrate that
a record is consistent with having been appended to, not that it was. Consumers
MUST NOT treat conformance at TR-1 through TR-3 as tamper evidence.

Not every integrity scheme is worth the same. A digest computed by the emitter
detects alteration by a third party and establishes nothing about the emitter,
who can recompute it over whatever they please. Only `signature` and
`external-anchor` place evidence outside the emitter's control, and only those
support a claim made against the emitter rather than on the emitter's behalf. A
consumer evaluating a TR-4 record SHOULD read the scheme rather than the
level.

A self-declared scope is believed by the validator. An emitter that acts and
declares otherwise skips the gate requirements. Two things limit the damage: a
record contradicting its own declaration fails at TR-1, and the declaration is
reported with the level rather than hidden inside it. Neither is a substitute
for external attestation. Consumers requiring assurance beyond self-assertion
should look to the SCITT architecture {{I-D.ietf-scitt-architecture}} and to
transparency logs {{RFC9162}}.

An approval is only as strong as its identity source. The format requires
identity to originate outside anything the proposing model can write, and
requires the approver not to be the proposer, but it cannot verify that an
implementation honoured either. These are the failures a reader cannot
otherwise detect, which is why they are stated as requirements rather than left
to implementations.

An identifier reused across records defeats them both. Identifier uniqueness is
checked within a record. An emitter that restarts its counter produces two
records that cannot be read together.

# Privacy Considerations

Belief entries frequently concern identifiable people, and evidence entries may
reference material about them.

Implementations SHOULD omit content and carry a digest instead. A citation with
a digest lets a holder of the source show it unchanged, without the record
becoming a second copy of the material. The `redacted` member exists so that a
withheld excerpt is visibly withheld rather than silently absent, which is the
difference between a record that can be audited and one that merely looks
complete.

Append-only recording is in tension with erasure obligations. This document
takes no position on how an implementation should resolve that tension, but
notes that the two obvious resolutions both fail: rewriting history destroys
the property that made the record worth keeping, and recording a deletion
alongside the deleted content erases nothing. An implementation SHOULD be able
to record that a destruction occurred without re-retaining what was destroyed.

# IANA Considerations

IANA is requested to register the following media type in the "Media Types"
registry.

Type name:
: application

Subtype name:
: testimony-record+json-seq

Required parameters:
: N/A

Optional parameters:
: N/A

Encoding considerations:
: binary; a JSON text sequence {{RFC7464}} of UTF-8 encoded JSON texts

Security considerations:
: See {{security-considerations}} of this document.

Interoperability considerations:
: All entries in one record name a single specification version. Consumers
  ignore members they do not recognise.

Published specification:
: This document

Applications that use this media type:
: Systems recording and exchanging accounts of automated decision-making, and
  tools that validate such accounts

Fragment identifier considerations:
: N/A

Additional information:
: Deprecated alias names for this type: N/A. Magic number(s): N/A. File
  extension(s): .trseq for the sequence framing; .jsonl is in common use for
  the line-delimited framing. Macintosh file type code(s): N/A.

Person and email address to contact for further information:
: Troy Clifford <troy@machinetestimony.com>

Intended usage:
: COMMON

Restrictions on usage:
: None

Author:
: Troy Clifford

Change controller:
: The IESG

# Relationship to Regulation

The European Union Artificial Intelligence Act {{EU-AI-ACT}} requires
record-keeping over the lifetime of high-risk systems, and human oversight
capable of intervention. This document does not implement those obligations and
makes no claim of compliance with them. It is noted only that the levels
defined here were shaped by the same questions: TR-1 by automatic recording as
events occur, TR-2 and TR-3 by the identification of risk situations, and TR-3
by the attributability of oversight. Whether a given deployment satisfies a
legal obligation is a matter for the parties to that obligation and their
regulator.

--- back

# Implementation Status

At the time of writing, every implementation of this format is by this
document's author. There are two validators, one in Python and one in
TypeScript, written separately and checked against each other on a corpus of
records covering each level and each failure mode, which tests the
specification's clarity but is not independent implementation in the sense that
matters. There are two emitters: one for the author's own system, and one for
LangGraph, which depends on that framework and on nothing of the author's.

No implementation by another party is known. That is the honest state of it,
and it is the thing a reader deciding whether to implement this should weigh
most heavily.

The reference validator is a single standard-library file with no network
access, published under an MIT licence, so that a conformance claim can be
checked by the party hearing it rather than by the party making it {{TR-SPEC}}.

A survey of eight agent memory and agent framework implementations against
these requirements is published with a DOI {{CENSUS}}. It includes the
reference implementation, which the survey states carries no evidential weight,
and records two defects the survey found in it during preparation.

The `scope` entry, the conditional TR-3 requirement, and the recommendation to
report per-level results are new in `testimony-record/0.2` and have one
implementation each at the time of writing.

# Changes Since -00
{:numbered="false"}

This section is to be removed before publication as an RFC.

The Introduction of -00 stated that none of the eight surveyed systems records
the identity of the person who approved an action. The survey it cites does not
support that. Four of the eight were assessed absent on that requirement, a
fifth could not be established either way, and the three remaining include this
document's author's own system, which does record it. The claim was stronger
than the evidence behind it, and a document arguing that a system should not
assert more than it can show is the wrong place for one. Corrected.

The {{TR-SPEC}} reference pointed at a product's documentation site, which made
the format read as the manual for a piece of software. The specification
source, the reference validator and the adapters are now published in a
repository of their own, and the reference points there.

An Implementation Status section was added. It states that every implementation
of this format is by this document's author, and that no independent
implementation is known.

The `external-anchor` integrity scheme was named in -00 and not specified. The
`anchor` member is now defined, with an RFC 3161 profile, and the Security
Considerations distinguish the schemes that place evidence outside the
emitter's control from those that do not.

-00 did not say how a digest was computed. It said only that the digest was
the value under which alteration would be detected, which names no algorithm,
no serialisation and no ordering. Two conforming implementations would have
produced different digests for one record, and no reader could have recomputed
either, so the level called Verifiable was not reachable by anyone reading this
document alone. {{digest-computation}} specifies it, `covers` is required at
that level, and the reference validator recomputes rather than accepts. This
was found in the author's own implementations, which had two versions of the
rule that had never agreed, neither of them written down.

The values of `risk_source` and `identity_source` were specified as a list of
words that did not satisfy them, which meant any other word did. They are
specified as lists of words that do, with an `x-` prefix for anything else.

Nothing in -00 distinguished the checks a reader can settle from the record
from the ones the record merely asserts. {{what-a-level-rests-on}} does, and
implementations are asked to report the split alongside a level.

# Changes from -01
{:numbered="false"}

A decision could say that an action ran or that it did not, and could not say
that it was dispatched and the effect could not be confirmed. The record has
always modelled that uncertainty for beliefs, where `state` carries `unknown`,
and did not model it for actions, so a system whose acknowledgement was lost had
to assert something it did not know. The optional `outcome` member carries the
distinction, and a decision that contradicts itself between `executed`,
`verdict` and `outcome` no longer reaches TR-3.

# Acknowledgements
{:numbered="false"}

Phill Clapham reported that the reference validator refused TR-3 to any record
containing no decision entries, a requirement that appears nowhere in the
specification text, with the effect that a system holding a genuine hash chain
and gating nothing could not reach TR-4 however good its integrity was. The
scope entry and the per-level reporting in this document are the result.

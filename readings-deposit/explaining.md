# The duty to explain is seven times wider than the duty to record

*Reading, 8 September 2026*

## Seven areas must explain a decision. One must record what it was.

Two obligations in the same regulation, pointing in different directions. One says a person may demand to be told the main elements of a decision a machine took part in. The other says what the machine must write down. They do not cover the same ground, and the gap between them falls on the deployer.

### What must be explained

**Article 86(1)** gives any affected person subject to a decision taken by a deployer on the basis of a high-risk system's output, where that decision produces legal effects or similarly significantly affects them adversely, the right to obtain *"clear and meaningful explanations of the role of the AI system in the decision-making procedure and the main elements of the decision taken"*.

It applies across Annex III **with one exception, point 2, critical infrastructure**. So it reaches biometrics, education and vocational training, employment and worker management, access to essential public and private services and benefits, law enforcement, migration and border control, and the administration of justice. Seven of the eight areas, and every one of them about decisions taken about people.

### What must be recorded

Article 12 requires the automatic recording of events and, at Article 12(2), that logging enable the recording of events relevant to three purposes: identifying risk, post-market monitoring, and the deployer's own monitoring duty. **It specifies no content.**

Content is specified once. **Article 12(3)** sets a minimum for systems under Annex III point 1(a), remote biometric identification: the period of each use, the reference database, the input data that matched, and *"the identification of the natural persons involved in the verification of the results"*. One area of the eight.

| Annex III area | Must explain Art 86 | Log content specified Art 12(3) |
|---|---|---|
| 1(a) Remote biometric identification | yes | yes |
| 2 Critical infrastructure | excepted | no |
| 3 Education and vocational training | yes | no |
| 4 Employment and worker management | yes | no |
| 5 Essential services and benefits | yes | no |
| 6 Law enforcement | yes | no |
| 7 Migration and border control | yes | no |
| 8 Justice and democratic processes | yes | no |

**A recruiter, a lender, a school, a police force or an immigration officer must be able to explain the main elements of a decision, and is told nothing about what to record in order to be able to.** The one area where the regulation says what a log must contain is the one area where it also requires the log to name the humans who checked.

### Could the software answer?

Explaining the main elements of a decision after the fact means being able to say what the system held to be true, where that came from, and whether anything contradicted it. Ten widely deployed agent memory and agent framework systems were read at pinned commits against twenty record-keeping requirements. Three of those requirements bear directly on this.

| What answering would take | Can | Partly | Cannot |
|---|---|---|---|
| The source a stored fact came from is recoverable by following a link rather than by inference | 2 | 6 | 2 |
| A fact the system inferred can be told from one it was given `(of 6)` | 3 | 1 | 2 |
| When two stored facts disagreed, the disagreement is itself queryable afterwards | 1 | 1 | 8 |

**Two of ten can say where a fact came from without inferring it. Eight of ten cannot tell you afterwards that anything was ever in dispute.** A deployer running one of those eight, asked under Article 86 what the main elements of a decision were, has a system that did not record whether it had contradictory information at the time.

None of those ten is doing anything wrong. None was built against Article 86, and most predate it. That is the point: the obligation landed on deployers, and the software they bought was not designed to answer it.

### On the dates, and what is genuinely unsettled

Article 86 was **not** deferred. Regulation (EU) 2026/1744, the digital omnibus on AI, deferred Chapter III Sections 1 to 3 for Annex III high-risk systems to 2 December 2027. Article 86 sits in Chapter IX and the omnibus does not touch it, so by Article 113 it has applied since 2 August 2026.

**Whether it can be invoked before December 2027 is arguable and this page does not assert it.** The right attaches to a decision taken on the basis of a high-risk system listed in Annex III, and the classification provisions that make a system such a thing were themselves deferred. There is a reading on which the right is live now and a reading on which it waits for the rest. That is a question for lawyers, and this is not legal advice.

The finding does not depend on which reading is right. On the later one, both obligations arrive together in December 2027 and the asymmetry between them is identical: seven areas must be explained, one has its record content specified. The date makes it more urgent. It is not what makes it true.

### What this does not show

Two articles and three requirements, not an assessment of the regulation or of any system. Nothing here says what an adequate explanation is; that is for a court and for guidance that does not yet exist. A system that scores badly on these three may be excellent, and a deployer may be able to explain a decision from records kept outside it entirely.

And a reading is wrong in the ordinary way readings are wrong. An earlier reading on this site said the Act contained no requirement to record the identity of a person, which was false, because Article 12(3) was read and its scope was not. That correction is recorded on the page that carried it rather than quietly made, and the same applies here.

### Check it

Article 86 and Article 12 are public. The per-system verdicts behind the second table, each citing a file and a line at a full commit hash, are at [the register](/register/), and the reading of what four instruments require is at [the obligation](/obligation/). The counts on this page are recomputed from the subject files by the test suite rather than typed.

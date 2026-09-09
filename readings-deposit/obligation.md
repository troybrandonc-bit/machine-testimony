# Everyone requires the log. One row of Annex III requires it to name who approved

*Reading, 7 September 2026*

## Everyone requires the log. One row of Annex III requires it to name who approved.

From 2 December 2027, a deployer of a high-risk AI system in the European Union must keep the logs its system generates. Article 12 says the system shall technically allow for the automatic recording of events over its lifetime. Article 26(6) says the deployer shall keep those logs for at least six months. Article 14 says a natural person shall oversee the system.

None of those articles says what has to be in the record for it to answer a question afterwards. So it is worth asking whether anything else does. Four instruments were read against four questions.

> **Where these require a record of what an automated system did, do they require it to say who authorised a consequential action, and to be checkable by somebody other than the party that produced it?**

### What the reading found

| Instrument | Kind | Record required | Who authorised | Shown unaltered | Retention stated |
|---|---|---|---|---|---|
| EU AI Act | law | required | partial | absent | required |
| ForHumanity | certification scheme | required | absent | partial | required |
| CoSAI Risk Map | controls catalogue | required | absent | partial | absent |
| NIST AI RMF 1.0 | governance framework | n/a | n/a | n/a | n/a |

Three of the four specify what a record must contain. All three require one to be kept. **Only one of them requires a record to name the person, and only for one category of system out of everything the law covers. None of the three requires a record to be capable of being shown unaltered by anyone other than its author.**

### The law has the gap too

This is the part worth sitting with, and it is not that the regulation forgot. It is that the regulation wrote the requirement, once, and scoped it to a single row of Annex III.

**Article 12(3)(d) obliges the logs of a remote biometric identification system to provide "the identification of the natural persons involved in the verification of the results".** It points at Article 14(5), which requires the action to be "separately verified and confirmed by at least two natural persons with the necessary competence, training and authority". Two named people, identified in the record. That is the requirement this reading exists to look for, drafted and in force.

It applies to remote biometric identification and to nothing else. Every other high-risk system falls under Article 12(2), which asks for the recording of events relevant to three named purposes and specifies no content whatsoever. So the drafters knew the requirement was needed, knew how to word it, and did not extend it. A recruitment system, a credit system or an agent acting on a medical file is obliged to log, and obliged to nothing about who allowed what.

The integrity half has no such exception. Across Articles 12, 14 and 26 there is not one occurrence of tamper, unaltered, integrity of the log or independent verification. The logs must exist and must be kept for six months. Nothing anywhere requires that a kept log can be shown to be the one that was written.

So a deployer outside that one category can be fully compliant with Article 12 and Article 26, hand a regulator six months of logs, and be unable to demonstrate either that a human approved a particular action or that the file produced is the file recorded.

> **An earlier version of this page said the Act contained no such requirement at all. That was wrong: Article 12(3)(d) was read and its scope was not.** The correction is recorded here rather than made silently, and the corrected finding is the stronger one, because a requirement the drafters wrote and confined is harder to explain away than one they never considered.

### ForHumanity has the vocabulary and spends it elsewhere

Of everything read, the ForHumanity criteria are much the most developed on record-keeping: roughly 1,300 uses of the word log across five documents, and an Event Log established over twelve areas of an agentic system including the orchestration layer, outcomes, a risk log and a human interactions log.

The Event Log is then defined as five components paraphrased from ISO 27001: user ID, system activity, date and time, device and location, and IP address. That answers which session acted. It does not answer which person allowed it, and the phrase who approved does not appear in the five documents.

The integrity vocabulary is present and properly defined. Data Integrity is taken from NIST as data not altered in an unauthorised manner, and Integrity as the degree to which a system prevents unauthorised access or modification. Both are used only in test data curation, where chain of custody is a step in the Data Curation Report. The care is real, and it is aimed at the training data rather than at the record of what the system did.

### Why a framework sits in the table as not applicable

NIST AI RMF 1.0 contains no occurrence of log, logging, record-keeping or audit trail. Reporting that as a finding would be the error this reading exists to avoid. The framework organises risk management into four functions and deliberately specifies no controls; the suggested actions live in a separate companion Playbook. A document that does not specify controls is not failing to specify one, in the same way that a vector store is not failing to authorise actions.

It is in the table so that the count of instruments that specify a record is three rather than four, and so that the zero is visible without being counted as a deficiency.

### One of them is already closing it

CoSAI, the OASIS coalition, has a control requiring that an agent's actions, tool use and reasoning be transparent and auditable through logging, and a separate control requiring that all modifications to runtime components be immutably recorded. That is immutability required for configuration rather than for the action record, but the idea is in the catalogue rather than absent from it.

More to the point, a risk filed there on 6 September 2026 states the distinction directly: the audit trail is intact, and what is false is the content of the report. That is the same defect, arrived at independently. It is open at the time of reading.

### The one that could not be read

ISO/IEC 42001 is the most widely referenced AI management standard and its text is paywalled. A reading whose rule is that every verdict cites the clause it rests on cannot assess what it has not read, so it has no row. That the deployers governed by a standard cannot read it without paying is recorded as a fact about the field rather than scored as a verdict.

### What this does not show

Four questions, not an assessment of whether any of these is good at what it is for. Each of these instruments is doing a job, and none of them set out to specify a record format. A scheme that answers no to three questions here may be excellent at the thing it was written for.

Only published text was read, at the versions named in the data. A criterion that exists in a draft, a working group or a later revision is outside this. And a reading is wrong in the ordinary way readings are wrong, which is why every verdict names the article, control or criterion it rests on.

### Check it

The four questions, the verdicts, the documents read and the reasoning for each are in [census/schemes/readings.json](https://github.com/troybrandonc-bit/machine-testimony/blob/main/census/schemes/readings.json). The counts on this page are recomputed from that file by the test suite rather than typed.

The companion question, asked of the software rather than of the rules, is the [conformance census](/register/): of the eight systems there that take or gate actions, one can name the person who approved. And the specific failure where the approval is recorded but the action changes underneath it is [a separate reading](/approval-binding/).

---
last_updated: 2026-11-02T12-05
description: Investigate how an open-source project actually works through primary sources, classified evidence, and measured patterns.
---

# Research the project, not just its reputation

Use this when Gilad asks “how does it go with project X?”: whether to adopt it, rely on its maintainers, contribute, expect a feature, or trust its direction. This is **social research and data research together**. Stories explain mechanisms; classified records tell you whether those mechanisms are common. Neither substitutes for the other.

Gilad may want a short conclusion. That limits the report, not the investigation. Keep the full evidence record separately so the conclusion can be concise without becoming superficial.

## Decide what would change the answer

Separate the factual question from the decision it informs. “This project is tightly controlled” and “contributing is not worth my time” are different claims; one can change while the other remains valid. A research result does not override a standing instruction or authorize contacting maintainers.

Turn broad impressions into observable questions. Choose the relevant axes rather than running the same audit everywhere:

| Question | Useful evidence | Misleading shortcut |
|---|---|---|
| Can we depend on it? | Relevant released behavior, upgrade history, unresolved blockers, maintenance continuity | Stars or recent commits |
| Is contribution practical? | Submission rules, substantive review, requested revisions, abandoned work, final adoption | Merge rate alone |
| Does user feedback matter? | Requests followed through discussion, decisions, changed behavior and reversals | Who authored the final commit |
| Is the project responsive? | Time to a substantive human response, by issue type and period | Time to the first bot reply |
| Is an improvement available to us? | Published artifact, release inclusion, configuration and compatibility | Current `main` or matching version strings |

Name what would support the working assumption and what would contradict it. Look for the strongest counterexample, not only confirming vocabulary.

## Map the sources before collecting everything

Establish the project's identity: canonical repository, renames, transfers, forks, packages, release channels and current maintainers. Otherwise one history can look like several projects, or a downstream feature can be mistaken for upstream behavior.

Read policy and design statements, then find where decisions actually happen: issues, PR reviews, discussions, RFCs, blogs, social threads, chat, releases and commits. Follow cross-references between them. Public policy tells you the stated rule; actual cases show how it is applied.

Mark changes of era: a new owner, contribution gate, commercial team, major rewrite or new release process. Do not average across those boundaries without checking whether behavior changed. Current membership does not prove someone's historical role.

**Surface important access gaps early.** A readable social-post URL is not a searchable account history. Login walls, missing replies, private RFCs and unavailable chat archives can change what you can conclude. Tell Gilad when another access method could materially improve the research; keep working on the accessible sources.

## Run a pilot, then choose the population and unit

Read a few contrasting cases before designing the dataset. The pilot reveals which fields matter and which apparent outcomes are unreliable. Then define the scope, dates, inclusion rules and unit of analysis before calculating a headline number.

A tracker item is often not the right unit. One proposal can span an issue, three replacement PRs, a maintainer rewrite and a release. Treat that as one episode when studying decisions, while retaining separate PR counts when studying traffic. Likewise, a reopened bug is not necessarily a new incident.

Keep two evidence sets distinct:

- **Purposive cases:** selected to explain a mechanism, test a boundary or challenge the assumption.
- **Frequency sample:** selected from a stated population using a reproducible method, such as a seeded random sample or explicit time strata.

An impressive counterexample can disprove “never.” It cannot establish “usually.” Do not turn a hand-picked set into a percentage about the whole project. A metadata census helps define a population; downloading every record is not the same as reading or classifying every record.

## Trace outcomes instead of trusting labels

Read the original report, full conversation, inline reviews, timeline and linked predecessors. Then check the implementation or release when the outcome depends on whether something shipped. Separate the proposed solution from what was ultimately accepted.

Common traps from real investigations:

- A closed, unmerged PR may have shipped through cherry-picking or a rewrite.
- A `completed` issue may contain a rejection. A `not_planned` issue may remain that way after approval and a merged follow-up.
- An automatic closure is a process event, not necessarily a design judgment.
- “I love this” and a request to rebase are not commitments. A maintainer can reject the feature after trying it.
- Approval before a PR does not establish who first proposed the need. Follow the chain backward.
- A later similar feature does not prove an earlier request caused it. Check for explicit links, credit, changed decisions or already-existing implementation.
- A maintainer-authored implementation can answer a community proposal; a contributor-authored implementation can follow a maintainer specification.
- A published policy can change. Read both the earlier position and the explanation of the reversal.

Keep observation and inference separate. “First visible public proposal,” “maintainer reports having considered it,” and “we found a dated prior plan” are different evidence strengths. Never turn an absence of public evidence into knowledge of private intent.

## Classify first, measure second

Write a small codebook fitted to the question. Keep independent dimensions separate: type of work, initiating need, decision authority, outcome and confidence. Do not collapse bugs, new capabilities, catalog updates, examples and internal cleanup into one contribution category when their acceptance conditions differ.

For each classified case retain:

- identifier, date and source links;
- category and a short reason;
- relevant earlier/later records;
- observed outcome and the evidence for it;
- unresolved alternatives or missing sources.

Allow `unknown`. Missing context is not a vote for either hypothesis. Reclassify when close reading changes the interpretation, and preserve why. Measure after that pass, rather than choosing categories to support an emerging conclusion.

Check totals, unique IDs, sample coverage and joins. Show the denominator behind every proportion. Account for duplicates, bots, recent cases that have had little time for review, and changes between periods. Report an observed difference between eras without automatically attributing it to the policy that changed between them.

## Make collection restartable, not elaborate

Use existing tools and small scripts. Do not build a research platform for a one-off question.

Practical lessons:

- Large nested API queries can time out. Start with modest pages, checkpoint each successful page and use bounded retries for transient transport failures.
- Preserve cursors, IDs, timestamps and collection boundaries. Validate that pagination reached its end; search endpoints can cap results even when more matches exist.
- Inspect representative records before scaling. Confirm that you collected review comments as well as ordinary issue comments.
- Use explicit actor types where available. Bot names and suffixes differ between APIs; repository association is not a substitute for actor type.
- Keep raw captures apart from derived tables and interpretations. Record the sample seed and enough provenance to reproduce the counts. Live pages and states can change after collection.
- Treat search engines and generated summaries as discovery tools. Verify claims in primary sources before using them as evidence.
- If a documentation link is broken, try the canonical site index and current URL structure before treating the resource as absent.

For release questions, inspect the actual artifact. Identical version strings can conceal differences between a published package and Git source. Tests passing also do not establish that the tested behavior is the behavior the user needs.

## Stop when more searching no longer changes the model

“Sensible exhaustion” is not reading every message on the internet. It means the important source surfaces and periods have been checked; positive, negative, ignored and abandoned outcomes are represented; the strongest counterexamples have been pursued; and further searches mostly repeat known mechanisms.

Before stopping, ask what missing evidence could reverse the conclusion. Pursue it if reasonably accessible. Otherwise state the specific limit and narrow the claim. Do not compensate for a source gap by collecting more of the same easy evidence.

## Give the human the conclusion and its load-bearing evidence

Keep the internal record thorough. The final answer should contain:

1. The conclusion, including which part of the original assumption survives.
2. The few measurements that change the interpretation, with their population or sample made clear.
3. Two or three causal examples that show how the project behaves, including a meaningful negative case.
4. The practical implication and any uncertainty that could change it.

Do not report collection volume as a badge of rigor or make the reader reconstruct the argument from a catalogue of links. Link the detailed record for inspection. If the research suggests contributing, follow the project's own process and the parent skill's draft-review requirements; research itself authorizes no upstream action.

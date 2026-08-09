---
name: handoff
description: Instructions for writing a handoff doc
---
You have been working on the task described above but have not yet completed it.
Write a continuation summary that will allow you (or another, fresh-context instance of yourself) to resume work efficiently and effectively in a future context window where the conversation history will be replaced with this summary.
Your summary should be structured, concise, actionable, and written along the lines of ASD-STE100. Include:

1. **Task Overview**
   - The user's core request and success criteria.
   - Any clarifications or constraints they specified.

2. **Prior State**
   - What was when _your_ session just started.
   - What were the circumstances, assumptions and mental models <i need a word or a few words here> before you started work.

3. **Current State**
   - What has been completed so far.
   - Files created, modified, or analyzed (with paths if relevant).
   - Key outputs or artifacts produced.

4. **Important Discoveries**
   - Technical constraints or requirements uncovered.
   - Decisions made and their rationale.
   - Errors encountered and how they were resolved.
   - What approaches were tried that didn't work, and why.
   - What approaches were tried that did work, and why.

5. **Explicitly User-mentioned or Unequivocally Necessary Next Steps**
   - Specific actions needed to complete the task.
   - Any blockers or open questions to resolve.
   - Priority order if multiple steps remain.

6. **Context to Preserve**
   - User preferences or style requirements.
   - Paths of files (any file type) you read or executed, and commands you ran, in the beginning of the session, to absorb the baseline context needed to start work.
   - Details that aren’t obvious.
   - Any promises made to the user.

### How to approach this handoff task

This is a handoff under asymmetric common ground. You are handing off to someone who was absent.
The common ground is the baseline context layer that had existed when your session only started.
**The asymmetry is the mental models you have built on top of the baseline context layer.** Discoveries, hypothesis (discarded or confirmed), new abstractions, locally invented terminology, updated ways of understanding.
The distinction is important: yes, you are summarizing your own experience, but you are also **reconstructing the recipient’s state of knowledge.** Optimize for _their_ entry into the situation.
This is closely related to theory-of-mind and audience design: translate private/local ontology back into shared language. The handoff recipient needs two models: Your current understand, and separately, our last known common ground.

Think Mission Control, aviation maintenance, intensive-care units, nuclear plants, military command centers. An outgoing operator has been living inside a situation for eight hours. An incoming operator walks in cold. Simply saying “Here is what I concluded after eight hours” is dangerous because the outgoing person’s words are saturated with context the incoming person never acquired.

Medicine developed standardized handoff protocols for the same reason, like Situation–Background–Assessment–Recommendation (SBAR):
**Situation:** What is happening now?
**Background**: What does the recipient need to know to understand it?
**Assessment**: What do I now think is going on?
**Recommendation:** What should happen next?

Incorporate this approach.

### Write efficiently

So far the instructions dealt with handoff effectiveness. This is about efficiency.

One rule: if it can be referenced, reference it, don’t repeat its contents.
   Toy example:
   Do not write: `Load path/to/skills/how-to-write-clearly/SKILL.md. Write clearly, [...proceeds to repeat SKILL.md’s content]`
   Do write: `Load path/to/skills/how-to-write-clearly/SKILL.md.`

Good references live at the end of each handoff section, grouped by whether created, read, edited, deleted, with references accompanied by 2–5 words describing the “why”, if justified.
Toy example: (inside a ‘edited-files’ group) `- path/to/file.py: fixed deployment bug.`

### Note on tone

The premise of writing a handoff is the effort at large is still incomplete — it is mid-process. It follows that _some_ of your understanding of the situation is proportionally incomplete.
Therefore, distinguish a hard fact from “probably”; proven beyond doubt vs prediction. Convey the former type regularly. Convey the latter type in a more advisory / hypothesizing "it may be" rather than "it is", “As far as I understand” and “At the time of writing, it seemed that”, etc.
Not supplicant, not insecure — only can tell apart facts ("is") from prediction ("may").

Be concise but complete — err on the side of including information that would prevent duplicate work or repeated mistakes. Write in a way that enables immediate resumption of the task.

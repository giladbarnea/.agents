---
session_id: 01a1789e-e901-7840-bfe4-9c13fb04bab0
provider: codex
directory: ~/dev/herdr-plugins/herdr-tree/.worktrees/popup-textual
history_path: ~/.codex/sessions/2026/10/26/rollout-2026-10-26T16-30-42-01a1789e-e901-7840-bfe4-9c13fb04bab0.jsonl
created: "2026-10-26 16:30"
modified: "2026-10-28 14:24"
messages: 46
---
After having asked to distill its experience:

```

**The main lesson is to reduce what the user must infer.** A good terminal interface makes the current state, available actions, and consequences clear. Its appearance and behavior must tell the same story.

These are the lessons I would pass to a future builder.

1. **Design around the task before choosing the widget.**

   Start with what the person repeatedly wants to accomplish. Count the actions, focus changes, and hidden knowledge required to complete it.

   Our dropdown looked orderly, but a role change required opening, navigating, confirming, and saving. Visible choices reduced that task to selecting and saving. They also exposed the available options.

   The general lesson is conditional: when a small, stable set of choices fits comfortably, showing it can justify the extra space. A compact widget can create a cumbersome task.

   Treat user feedback as evidence about the task. You explicitly said the three-row editor was sufficient. Enlarging it would have spent space without solving your problem.

2. **Make visual hierarchy explain behavior.**

   A terminal gives you spacing, alignment, contrast, borders, and limited typography. Assign each a purpose. Strong text identifies the subject. Nearby labels explain fields. Quiet text supplies secondary context. Emphasis identifies the main action.

   **Selection, focus, and action importance are different states.** A selected option remains selected after focus moves. A prominent Save button still needs a distinct focus indicator.

   We missed that distinction initially. Save looked prominent, but its styling concealed keyboard focus. A container also accepted focus without showing a useful destination.

   Inspect every focus stop. The user should never need to count Tab presses to determine where input will go.

3. **Define one interaction model for the whole form.**

   Widget defaults can be reasonable individually and inconsistent together. Specify what click, Enter, Escape, Tab, and text input mean across the complete interface.

   Give each shortcut a clear scope. A letter can select an option while its group has focus. Inside an editor, that same letter must remain text.

   If mouse use is supported, complete the main task using only clicks and typing. Keyboard navigation should also complete it independently. Neither path should require repairing the other.

   Our particular bindings reflected your requirements. Enter-save and Ctrl+C-clear are **contextual choices**, not universal TUI recommendations. The transferable lesson is to choose deliberately, explain clearly, and verify consistently.

4. **Make editing feel safe through predictable state changes.**

   Separate selecting, editing, saving, and discarding. Choosing an option must not unexpectedly commit the form or erase another field.

   Drafts should survive navigation, conditional fields, scrolling, and resizing. If saving fails, retain the draft and show the failure where the user can see it.

   Cancellation also needs a complete interaction design. Our first Escape showed a discard warning. Another action reset that warning. This prevented a later Escape from unexpectedly completing an old cancellation attempt.

   On small screens, preserve access to Save, Cancel, feedback, and essential help. Let editable content scroll when necessary. A layout must remain usable after content grows or an error appears.

5. **Verify input through the environment where people actually use the interface.**

   A widget test proves widget behavior. A standalone terminal test proves another part of the path. Neither establishes that input survives the actual terminal and host application.

   Our mouse tests passed standalone while real popup clicks failed. Logging exposed the cause: clicks arrived before updated pixel dimensions. The application translated them using stale dimensions.

   Switching that integration to cell coordinates removed the unnecessary dependency on pixel geometry. The broader lesson is to **remove a fragile dependency when the task does not need it**.

   When input fails, inspect the received report and decoded event before changing the widget. Establish whether the failure concerns delivery, interpretation, focus, or application behavior.

   Also distinguish a generated key event from a physical shortcut. An automation tool can bypass a user mapping that changes what the physical key sends.

6. **Test transitions and realistic speed, not just isolated actions.**

   Slow automation can conceal ordering defects. We found that selecting a role and immediately pressing Enter could save the previous role. Each action worked when tested separately.

   Exercise short sequences at realistic speed: select then save, type then save, cancel then resume, click then type. Check the resulting values.

   Test changes during use: resize while editing, reveal an optional field, encounter a save failure, reopen saved content. These transitions expose assumptions that a clean opening screen cannot.

   The verification tool also needs scrutiny. One failed check clicked matching text behind the popup. Confirm the visible target before interpreting a failed interaction as an application defect.

7. **Improve the interface without damaging the surrounding workflow.**

   The terminal already contains the user’s habits, mappings, and other applications. They are part of the design context.

   I initially proposed removing the global Shift+Enter mapping to make the popup work. Your concern exposed the cost to an established newline habit elsewhere.

   The final choice changed the popup’s newline shortcut and preserved that habit. The lesson is to investigate why an existing behavior exists before removing it.

   Apply the same restraint to appearance. Preserve the parts users already understand. Change the parts that create friction. A successful usability pass does not require replacing the visual identity.

To turn these lessons into muscle memory, I would repeat this sequence:

1. Write the main task as observable user actions.
2. Reproduce the friction and identify the assumption that caused it.
3. Define the interaction model before changing individual controls.
4. Inspect focus, selection, errors, and small-screen states visually.
5. Exercise fast action sequences through the actual terminal environment.
6. Reopen the result and verify what persisted.
7. Preserve a short explanation of the failed assumption, the evidence, and the correction.
```

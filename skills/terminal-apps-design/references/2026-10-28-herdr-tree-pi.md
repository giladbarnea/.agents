---
session_id: 01a176d5-c9b4-71e3-b9f5-8ace248b6d2f
provider: pi
directory: ~/clients
history_path: ~/.pi/agent/sessions/--Users-giladbarnea-clients--/2026-10-26T06-11-24-726Z_01a176d5-c9b4-71e3-b9f5-8ace248b6d2f.jsonl
created: "2026-10-26 08:11"
modified: "2026-10-28 14:37"
messages: 62
custom_title: "[10-26][clients] ship a polished, usable herdr-tree session popup"
---

This session was managing the codex one. After having asked to distill its experience:

```
# Design the whole interaction, not just the screen

The first attractive popup still had awkward role changes, invisible focus, and broken mouse behavior. **Visual polish had improved before usability was complete.**

The transferable lesson is to design what the user does, make its state visible, and verify it through the real terminal.

## 1. Start with the task, not the toolkit

Before choosing widgets, describe the common tasks. What does the user change most often? What must remain visible while they edit? What mistakes must be recoverable?

Then count the actions each task requires. A dropdown can save screen space while adding opening, navigation, and confirmation steps. In our popup, visible role choices removed unnecessary stages.

But fewer keystrokes are not the only goal. An immediate role change is not an improvement if it discards an annotation draft.

Choose the toolkit after understanding this interaction shape. Sequential prompts suit linear tasks. A shared form suits related edits that users must inspect together. **Neither toolkit choice nor native widgets replace interaction design.**

## 2. Define the input rules before polishing the screen

Decide what saves, cancels, inserts a newline, changes selection, and moves focus. Specify where each shortcut applies.

A single-letter command must not fire while the user types that letter into a text field. When mouse and keyboard are supported, both must reach the same actions.

Cancellation also needs an explicit rule. Our first Escape showed confirmation, and the second discarded changes. Intervening input reset that confirmation. This made cancellation predictable instead of an accidental consequence of binding priority.

Audit inherited toolkit behavior. Default shortcuts, focusable containers, and command menus are not automatically useful features. Showing every available command is not the same as helping the user.

The particular keys are not the lesson. **Predictable scope and consistent behavior are.**

## 3. Make the important states visible

The visual design should explain the input rules without requiring experimentation.

Focus, selection, and primary-action emphasis are different things. Our Save button was already prominent, yet its keyboard focus was invisible. Its normal accent color could not do both jobs.

If users must count Tab presses to infer focus, the focus design has failed.

Give emphasis a purpose. Separate context from editable content, and editable content from actions. Use consistent spacing, alignment, borders, and restrained color to explain those differences.

A design skill can help here, even if it targets another medium. Its principles about hierarchy, contrast, and focus can transfer. Its layout and animation recipes might not.

Design in terminal cells, not character counts or desktop pixels. Test long text, wide glyphs, dynamic fields, and resizing early. Keep essential actions accessible when content scrolls.

More space is not automatically more usability. Our three-row annotation field was acceptable. The more important problems were interaction cost and unclear state.

## 4. Treat the terminal environment as part of the interface

A physical key does not arrive at the application unchanged:

    Physical input → terminal mappings → multiplexer → TUI parser → application action

Inspect that path before changing application bindings.

Our Shift+Enter mapping looked like an obstacle to the popup. It also provided the user’s newline behavior elsewhere. Changing the popup shortcut solved the local problem without disrupting that habit.

**Find out what a global setting already supports before changing it.** Inspect the running configuration, not only the configuration file.

Mouse input has a similar path, with coordinate units and geometry added. Our app used old pixel dimensions when a click arrived from a differently sized client. The text field itself was not broken.

Cell-based mouse reports removed a dependency the popup did not need. That is not a rule against pixel reporting. It is a rule to use only the protocol features the interface needs.

I should have logged the input reaching the TUI sooner. That would have separated transport failures from widget failures earlier.

## 5. Test transitions and timing, not only screenshots

A screenshot cannot prove that Save persists data, Cancel discards edits, or changing one field preserves another.

Test complete transitions through public interfaces and isolated storage. Save, reopen, and read the result. Cancel an actual edit. Exercise combinations of fields, not only each field alone.

Also test fast input. A selection key followed immediately by Enter exposed stale selection state that slower tests missed. Startup and resize can expose similar ordering problems.

Use three levels of evidence:

1. **Headless tests** check state changes, focus order, and action rules.
2. **Pseudo-terminal tests** check encoded input, parsing, rapid sequences, and resizing.
3. **Real-terminal checks** check mappings, mouse delivery, popup geometry, and the actual launch path.

Report precisely what passed. A synthetic Shift+Enter sequence reaching the app does not prove the physical shortcut works. The test tool might bypass terminal mappings.

## 6. Verify the test driver before blaming the app

Our test driver produced several apparent failures that were not application failures.

It first matched text in the background conversation instead of the popup. Later, it matched the word “Cancel” inside an annotation instead of the Cancel button.

**A text match is not a control identity.**

Scope assertions and input to the intended frame and control. Confirm the target before sending editing, saving, or cancellation keys. Preserve the distinction between global terminal coordinates and widget-local coordinates.

A successful input command proves submission, not reception or effect. Check the resulting screen state and stored result.

The same discipline applies to visual comparisons. Use real controls under matching terminal dimensions, fonts, and scale. Otherwise, presentation differences can disguise interaction differences.

Parallel prototypes are useful. Tests that share terminal focus or one global popup must run one at a time.

## 7. Finish the real entrypoint, not just the demonstration

A separate prototype makes experimentation safer. It also creates a final responsibility: promote the approved behavior into the interface people actually open.

Carry over startup settings, input handling, storage routing, and sizing. A working demonstration wrapper does not prove that the normal launcher behaves correctly.

Give the designer clear ownership of design decisions. Review those decisions against observable tasks and user feedback, rather than redesigning individual choices from outside.

Then verify the normal entrypoint and remove duplicate implementations and obsolete experiment resources.

**The finished product is the complete path from the user’s intention to the correct saved state. The screen is one part of that path.**
```

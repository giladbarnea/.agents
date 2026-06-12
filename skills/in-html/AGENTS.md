# `in-html` Skill
This Skill’s purpose is to make it easier for AI agents to convey dense, complex information to a human in a more brain-friendly way, and for the user to react (annotate)
  directly to/on the parts he wants to comment on, in the UI. Their inputs are persisted to a JSON file on disk, and when the user tells the AI agent, it in turn reads this JSON, and the session continues. The user may ask the agent to respond by adding content into the HTML page, create a new HTML page, or none of the above.

## Architecture: input handling

Mobile support was added under one constraint: it must be invisible to agents instantiating pages — same files, same recipes, same markup rules. That ruled out a separate mobile module and produced the current shape: shared, input-agnostic actions in `annotations.js` (open editor, submit, toggle preview, highlight), with the desktop gestures and the touch gestures as two thin binding layers that call the same actions. To add an interaction, extend the action once and wire it from both binding sections; never branch on device inside an action.

Two deliberate splits follow from this, and both are easy to mistake for accidents:

1. Behavior follows the *event* (`pointerType`), layout follows the *device class* (the single `(hover: none) and (pointer: coarse)` query, shared verbatim by `annotations.js` and both stylesheets). Hybrid devices therefore get both gesture sets over one layout.
2. Geometry on phones is owned by CSS alone: the coarse-pointer blocks override the JS positioners' inline styles with `!important` so the positioning code stays mobile-ignorant. They look like hacks; they are the seam.

The iOS quirks the touch bindings absorb (no click synthesis on non-interactive elements, sticky hover, the keyboard overlaying fixed elements) are each documented where they're handled — fix that class of problem in the bindings or the CSS media blocks, never in core.

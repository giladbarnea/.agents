(() => {
  const endpointMeta = document.querySelector(
    'meta[name="annotation-endpoint"]',
  );
  const annotationEndpoint =
    endpointMeta?.content || "http://127.0.0.1:8765/annotations";
  const annotationIgnoredSelector = [
    ".annotation-editor",
    ".annotation-preview",
    "[data-annotation-ui]",
    "input",
    "textarea",
    "select",
    "[contenteditable]",
    "[data-annotation-ignore]",
  ].join(",");
  const annotationWholeSelector = "[data-annotate-whole], .step, .bar";
  // On coarse-pointer screens the editor and previews render as bottom
  // sheets (annotations.css keys off the same query), which fit one at a time.
  const sheetLayoutInput = window.matchMedia(
    "(hover: none) and (pointer: coarse)",
  );
  // The panel is the one annotation surface on both pointer types. On coarse
  // pointers it is a draggable bottom sheet (the collapse/expand state machine
  // below); on fine pointers it is a static side card — always "expanded", no
  // handle, no drag. This gate fences off the touch-only sheet machinery.
  const isSheet = () => sheetLayoutInput.matches;
  const annotationsByElement = new Map();
  const choiceByElement = new Map();
  const choiceControlByElement = new Map();
  const annotationChoices = ["Yes", "Agreed", "Locked"];
  let activeChoiceMenu = null;
  let highlightedAnnotationElement = null;

  const hoverOverlay = document.createElement("div");
  hoverOverlay.className = "annotation-hover-overlay";
  hoverOverlay.dataset.annotationUi = "hover";
  document.body.appendChild(hoverOverlay);

  function elementHasOwnText(element) {
    return Array.from(element.childNodes).some(
      (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim(),
    );
  }

  function normalizedElementText(element) {
    const clone = element.cloneNode(true);
    clone
      .querySelectorAll("[data-annotation-ui]")
      .forEach((node) => node.remove());
    return clone.textContent.trim().replace(/\s+/g, " ");
  }

  function annotationCandidateFromPoint(clientX, clientY) {
    const element = document.elementFromPoint(clientX, clientY);
    if (!element || element.closest(annotationIgnoredSelector)) {
      return null;
    }

    const wholeElement = element.closest(annotationWholeSelector);
    if (wholeElement && normalizedElementText(wholeElement)) {
      return wholeElement;
    }

    if (element === document.documentElement || element === document.body) {
      return null;
    }
    if (
      element.classList.contains("wrap") ||
      element.classList.contains("col")
    ) {
      return null;
    }
    if (!normalizedElementText(element)) {
      return null;
    }
    if (element.children.length && !elementHasOwnText(element)) {
      return null;
    }
    return element;
  }

  // The reticle breathes wide on the horizontal axis, where the column has
  // room, and stays tight vertically so it never bleeds into stacked neighbors.
  const hoverOverlayOffsetX = 14;
  const hoverOverlayOffsetY = 4;

  // `instant` snaps the ring into place (first reveal, scroll, resize); without
  // it the ring glides and resizes between adjacent elements.
  function positionHoverOverlay(element, instant) {
    const rect = element.getBoundingClientRect();
    if (instant) {
      hoverOverlay.style.transition = "none";
    }
    hoverOverlay.style.left = `${rect.left - hoverOverlayOffsetX}px`;
    hoverOverlay.style.top = `${rect.top - hoverOverlayOffsetY}px`;
    hoverOverlay.style.width = `${rect.width + hoverOverlayOffsetX * 2}px`;
    hoverOverlay.style.height = `${rect.height + hoverOverlayOffsetY * 2}px`;
    if (instant) {
      hoverOverlay.getBoundingClientRect();
      hoverOverlay.style.transition = "";
    }
  }

  function setHighlightedAnnotationElement(element) {
    if (highlightedAnnotationElement === element) {
      return;
    }
    if (highlightedAnnotationElement) {
      highlightedAnnotationElement.classList.remove("annotation-hover");
    }
    highlightedAnnotationElement = element;
    if (element) {
      element.classList.add("annotation-hover");
      positionHoverOverlay(element, !hoverOverlay.classList.contains("show"));
      hoverOverlay.classList.add("show");
    } else {
      hoverOverlay.classList.remove("show");
    }
  }

  function annotationPathSegment(element) {
    const tag = element.tagName.toLowerCase();
    const idSuffix = element.id ? `#${CSS.escape(element.id)}` : "";
    const siblings = Array.from(element.parentElement.children).filter(
      (child) => child.tagName === element.tagName,
    );
    const nth =
      !idSuffix && siblings.length > 1
        ? `:nth-of-type(${siblings.indexOf(element) + 1})`
        : "";
    return `${tag}${idSuffix}${nth}`;
  }

  // Builds a structural path from the nearest stable anchor
  // (a data-annotation-id ancestor) or <body> down to the element.
  function selectorForAnnotationElement(element) {
    if (element.dataset.annotationId) {
      return `[data-annotation-id="${CSS.escape(element.dataset.annotationId)}"]`;
    }

    const parts = [];
    let current = element;
    while (current && current !== document.body) {
      if (current !== element && current.dataset.annotationId) {
        parts.unshift(
          `[data-annotation-id="${CSS.escape(current.dataset.annotationId)}"]`,
        );
        return parts.join(" > ");
      }
      parts.unshift(annotationPathSegment(current));
      current = current.parentElement;
    }
    parts.unshift("body");
    return parts.join(" > ");
  }

  function annotationUserInputs(annotation) {
    return Array.isArray(annotation.userInputs) ? annotation.userInputs : [];
  }

  function annotationInputText(userInput) {
    return typeof userInput === "string" ? userInput : userInput.userInput;
  }

  // NOTE: phrase-level annotation was mistakenly dropped in the desktop/mobile
  // unification refactor. This function (and the ↳ line in buildPreviewNote)
  // still RENDERS notes anchored to a sub-phrase, but the authoring path —
  // click-drag to select text within a block, then comment on just that
  // selection — was removed with the old floating editor. Restore the capture
  // side (text selection + CSS Custom Highlight API + selection preview); the
  // dropped implementation survives in the in-html skill repo at
  // scripts/annotations.js as of commit ef218d9 (the last state before this
  // unified version was transferred in over it).
  function annotationSelectionText(userInput) {
    return typeof userInput === "string"
      ? ""
      : userInput.specificallySelected || "";
  }

  // Local ISO 8601 timestamp carrying the reviewer's timezone offset,
  // e.g. "2026-06-03T14:32:07+03:00" for IST.
  function localIsoTimestamp(date = new Date()) {
    const pad = (value) => String(Math.floor(Math.abs(value))).padStart(2, "0");
    const offsetMinutes = -date.getTimezoneOffset();
    const sign = offsetMinutes >= 0 ? "+" : "-";
    return (
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
      `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
      `${sign}${pad(offsetMinutes / 60)}:${pad(offsetMinutes % 60)}`
    );
  }

  function annotationItem(userInput, specificallySelected, timestamp) {
    const item = { userInput };
    if (specificallySelected) {
      item.specificallySelected = specificallySelected;
    }
    item.timestamp = timestamp;
    return item;
  }

  function selectorWithoutClassIdentity(selector) {
    return selector
      .split(" > ")
      .map((segment) =>
        segment.startsWith("[data-annotation-id=")
          ? segment
          : segment.replace(/\.[_a-zA-Z][\w-]*/g, ""),
      )
      .join(" > ");
  }

  function elementForAnnotationSelector(selector) {
    return (
      document.querySelector(selector) ||
      document.querySelector(selectorWithoutClassIdentity(selector))
    );
  }

  function mergeAnnotations(existingAnnotation, annotation) {
    return {
      text: annotation.text || existingAnnotation.text,
      userInputs: [
        ...annotationUserInputs(existingAnnotation),
        ...annotationUserInputs(annotation),
      ],
    };
  }

  function annotationMarkerHost(element) {
    return element.matches("details")
      ? element.querySelector(":scope > summary") || element
      : element;
  }

  // One rail per block straddles its top-right edge and holds the verdict pill
  // and the notes badge side by side, on the border line where no content lives.
  // Created lazily by whichever of the two needs it first.
  function ensureAnnotationRail(host) {
    const existing = host.querySelector(":scope > .annotation-rail");
    if (existing) {
      return existing;
    }
    const rail = document.createElement("span");
    rail.className = "annotation-rail";
    rail.dataset.annotationUi = "rail";
    host.classList.add("annotation-marker-host");
    host.append(rail);
    return rail;
  }

  function annotationMarkerForElement(element) {
    return annotationMarkerHost(element).querySelector(
      ":scope > .annotation-rail > .annotation-marker",
    );
  }

  function annotationMarkerFromEvent(event) {
    return event.target.closest?.(".annotation-marker") || null;
  }

  function annotatedElementFromMarker(marker) {
    return marker.closest(".annotation-has-note");
  }

  function ensureAnnotationMarker(element, annotation) {
    const count = annotationUserInputs(annotation).length;
    const existingMarker = annotationMarkerForElement(element);
    if (existingMarker) {
      existingMarker.textContent = count > 1 ? String(count) : "";
      return existingMarker;
    }

    const marker = document.createElement("button");
    marker.className = "annotation-marker";
    marker.dataset.annotationUi = "marker";
    marker.type = "button";
    marker.setAttribute("aria-label", "Show annotations");
    marker.setAttribute("aria-pressed", "false");
    marker.textContent = count > 1 ? String(count) : "";
    ensureAnnotationRail(annotationMarkerHost(element)).append(marker);
    return marker;
  }

  function registerAnnotatedElement(element, selector, annotation) {
    const existing = annotationsByElement.get(element);
    const registeredAnnotation =
      existing && existing.annotation !== annotation
        ? mergeAnnotations(existing.annotation, annotation)
        : annotation;
    annotationsByElement.set(element, { selector, annotation: registeredAnnotation });
    element.classList.add("annotation-has-note");
    ensureAnnotationMarker(element, registeredAnnotation);
  }

  function recordWrittenAnnotation(element, userInput, specificallySelected, timestamp) {
    const existing = annotationsByElement.get(element);
    const annotation = existing?.annotation || {
      text: normalizedElementText(element),
      userInputs: [],
    };
    annotation.text = normalizedElementText(element);
    annotation.userInputs = annotationUserInputs(annotation);
    annotation.userInputs.push(
      annotationItem(userInput, specificallySelected, timestamp),
    );
    registerAnnotatedElement(element, selectorForAnnotationElement(element), annotation);
  }

  function annotatedElementFromPoint(clientX, clientY) {
    const element = document.elementFromPoint(clientX, clientY);
    if (!element || element.closest(annotationIgnoredSelector)) {
      return null;
    }

    let current = element;
    while (current && current !== document.documentElement) {
      if (annotationsByElement.has(current)) {
        return current;
      }
      current = current.parentElement;
    }
    return null;
  }

  async function loadAnnotations() {
    const response = await fetch(annotationEndpoint);
    if (!response.ok) {
      const details = await response.text();
      throw new Error(`Annotation load failed (${response.status}): ${details}`);
    }

    const annotations = await response.json();
    Object.entries(annotations).forEach(([selector, annotation]) => {
      const element = elementForAnnotationSelector(selector);
      if (!element) {
        return;
      }
      if (annotationUserInputs(annotation).length) {
        registerAnnotatedElement(element, selector, annotation);
      }
      if (annotation.choice && annotation.choice.value) {
        if (element.matches("[data-annotate-whole]")) {
          ensureChoiceControl(element);
        }
        choiceByElement.set(element, {
          selector,
          value: annotation.choice.value,
          timestamp: annotation.choice.timestamp,
        });
        applyChoiceState(element);
      }
    });
  }

  // Detaches a deleted note from the live annotation state — the in-memory
  // annotation, the marker count, and (with the element's last note) the
  // annotated status itself. The note's article stays in the open preview as
  // a tombstone offering Revert; the returned annotation and index let the
  // revert splice the note back exactly where it was.
  function detachAnnotationNote(element, item) {
    const entry = annotationsByElement.get(element);
    const userInputs = annotationUserInputs(entry.annotation);
    const itemIndex = userInputs.indexOf(item);
    entry.annotation.userInputs = userInputs.filter(
      (candidate) => candidate !== item,
    );

    if (entry.annotation.userInputs.length === 0) {
      annotationMarkerForElement(element)?.remove();
      element.classList.remove("annotation-has-note");
      annotationsByElement.delete(element);
    } else {
      ensureAnnotationMarker(element, entry.annotation);
    }

    return { annotation: entry.annotation, itemIndex };
  }

  // One note row: the selected-phrase line (when present), the note body, and —
  // for a persisted note — in-place editing with Save / Revert / Delete. Shared
  // by the first render and the re-render after a draft is saved.
  function buildPreviewNote(element, userInput) {
    const note = document.createElement("article");
    note.className = "annotation-preview-note";

    const selectedText = annotationSelectionText(userInput);
    if (selectedText) {
      const selected = document.createElement("div");
      selected.className = "annotation-preview-selected";
      selected.textContent = `↳ “${selectedText}”`;
      note.append(selected);
    }

    const body = document.createElement("p");
    body.textContent = annotationInputText(userInput);
    note.append(body);
    if (typeof userInput !== "string" && userInput.timestamp) {
      enableAnnotationNoteEditing(note, body, element, userInput);
    }
    return note;
  }

  // Notes edit in place: the paragraph is always plaintext-editable, so a
  // click drops the caret exactly where the reader pressed. Each note carries
  // a permanent Save / Revert / Delete row — Save and Revert sit inactive
  // until the text differs from what's on disk, Delete is always live. A
  // deleted note stays in the preview as a tombstone where only Revert is
  // live: it writes back the whole-file snapshot taken just before the
  // deletion. Every mutation — save, delete, restore — is confirmed by
  // reading the file back from disk before local state changes. Legacy notes
  // without a timestamp stay read-only — nothing identifies them on disk.
  function enableAnnotationNoteEditing(note, noteBody, element, item) {
    let savedText = annotationInputText(item);
    // Mirror the persisted text onto the node so a panel-wide "is anything
    // dirty?" check is a single stateless DOM read (innerText vs data-saved-text)
    // without reaching into this closure.
    noteBody.dataset.savedText = savedText;
    noteBody.setAttribute("contenteditable", "plaintext-only");
    noteBody.setAttribute("spellcheck", "false");
    noteBody.setAttribute("aria-label", "Annotation note (editable)");

    const actions = document.createElement("div");
    actions.className = "annotation-note-actions";
    actions.dataset.annotationUi = "note-actions";

    const saveButton = document.createElement("button");
    saveButton.className = "annotation-note-action save";
    saveButton.type = "button";
    saveButton.textContent = "Save";

    const revertButton = document.createElement("button");
    revertButton.className = "annotation-note-action revert";
    revertButton.type = "button";
    revertButton.textContent = "Revert";

    const deleteButton = document.createElement("button");
    deleteButton.className = "annotation-note-action delete";
    deleteButton.type = "button";
    deleteButton.textContent = "Delete";

    actions.append(saveButton, revertButton, deleteButton);
    note.append(actions);

    let deletedState = null;

    const editedText = () => noteBody.innerText.trim();
    const refreshDirtyState = () => {
      const dirty = editedText() !== savedText;
      saveButton.disabled = !dirty;
      revertButton.disabled = !dirty;
    };
    refreshDirtyState();

    function revertNoteEdit() {
      noteBody.textContent = savedText;
      saveButton.classList.remove("fail");
      refreshDirtyState();
    }

    async function saveNoteEdit() {
      const userInput = editedText();
      if (!userInput || userInput === savedText) {
        return;
      }

      const selector = annotationsByElement.get(element).selector;
      saveButton.disabled = true;
      revertButton.disabled = true;
      deleteButton.disabled = true;
      try {
        await writeAnnotationEdit(selector, item.timestamp, userInput);
        const persisted = await annotationWasPersisted(
          selector,
          userInput,
          item.timestamp,
        );
        if (!persisted) {
          throw new Error(
            "Edit returned ok but the new text was absent on read-back.",
          );
        }
        item.userInput = userInput;
        savedText = userInput;
        noteBody.dataset.savedText = userInput;
        noteBody.textContent = userInput;
        saveButton.classList.remove("fail");
      } catch (error) {
        console.error(error);
        saveButton.classList.add("fail");
      } finally {
        deleteButton.disabled = false;
        refreshDirtyState();
      }
    }

    async function deleteNote() {
      const selector = annotationsByElement.get(element).selector;
      saveButton.disabled = true;
      revertButton.disabled = true;
      deleteButton.disabled = true;
      try {
        const snapshot = await readPersistedAnnotations();
        await writeAnnotationDeletion(selector, item.timestamp);
        const persistedNote = await persistedNoteWithTimestamp(
          selector,
          item.timestamp,
        );
        if (persistedNote) {
          throw new Error(
            "Delete returned ok but the note was still present on read-back.",
          );
        }
        deletedState = {
          snapshot,
          selector,
          ...detachAnnotationNote(element, item),
        };
      } catch (error) {
        console.error(error);
        deleteButton.classList.add("fail");
        deleteButton.disabled = false;
        refreshDirtyState();
        return;
      }
      note.classList.add("annotation-note-deleted");
      noteBody.setAttribute("contenteditable", "false");
      revertButton.disabled = false;
    }

    async function restoreDeletedNote() {
      const { snapshot, selector, annotation, itemIndex } = deletedState;
      saveButton.disabled = true;
      revertButton.disabled = true;
      deleteButton.disabled = true;
      try {
        await writeAnnotationsRestore(snapshot);
        const persistedNote = await persistedNoteWithTimestamp(
          selector,
          item.timestamp,
        );
        if (!persistedNote) {
          throw new Error(
            "Restore returned ok but the note was absent on read-back.",
          );
        }
      } catch (error) {
        console.error(error);
        revertButton.classList.add("fail");
        revertButton.disabled = false;
        return;
      }
      annotation.userInputs.splice(itemIndex, 0, item);
      registerAnnotatedElement(element, selector, annotation);
      deletedState = null;
      note.classList.remove("annotation-note-deleted");
      noteBody.setAttribute("contenteditable", "plaintext-only");
      revertButton.classList.remove("fail");
      deleteButton.disabled = false;
      refreshDirtyState();
    }

    noteBody.addEventListener("input", refreshDirtyState);
    saveButton.addEventListener("click", saveNoteEdit);
    revertButton.addEventListener("click", () => {
      if (deletedState) {
        restoreDeletedNote();
        return;
      }
      revertNoteEdit();
    });
    deleteButton.addEventListener("click", deleteNote);
    noteBody.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        revertNoteEdit();
        noteBody.blur();
        return;
      }
      if (
        event.key === "Enter" &&
        !event.shiftKey &&
        !event.altKey &&
        !event.ctrlKey &&
        !event.metaKey
      ) {
        event.preventDefault();
        saveNoteEdit();
      }
    });
  }

  function cssPixels(value, fallback) {
    const pixels = Number.parseFloat(value);
    return Number.isFinite(pixels) ? pixels : fallback;
  }

  async function writeAnnotation(selector, text, userInput, specificallySelected, timestamp) {
    const response = await fetch(annotationEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selector,
        text,
        userInput,
        specificallySelected,
        timestamp,
      }),
    });

    if (response.ok) {
      return;
    }

    const details = await response.text();
    throw new Error(`Annotation write failed (${response.status}): ${details}`);
  }

  async function writeAnnotationEdit(selector, timestamp, userInput) {
    const response = await fetch(annotationEndpoint, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selector, timestamp, userInput }),
    });

    if (response.ok) {
      return;
    }

    const details = await response.text();
    throw new Error(`Annotation edit failed (${response.status}): ${details}`);
  }

  async function writeAnnotationDeletion(selector, timestamp) {
    const response = await fetch(annotationEndpoint, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selector, timestamp }),
    });

    if (response.ok) {
      return;
    }

    const details = await response.text();
    throw new Error(`Annotation delete failed (${response.status}): ${details}`);
  }

  // Restores the entire annotations file from a snapshot taken just before a
  // deletion — the revert needs no knowledge of where the deleted note lived.
  async function writeAnnotationsRestore(snapshot) {
    const response = await fetch(`${annotationEndpoint}/restore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(snapshot),
    });

    if (response.ok) {
      return;
    }

    const details = await response.text();
    throw new Error(`Annotation restore failed (${response.status}): ${details}`);
  }

  async function readPersistedAnnotations() {
    const response = await fetch(annotationEndpoint, {
      headers: { "Cache-Control": "no-cache" },
    });
    if (!response.ok) {
      throw new Error(`Annotation read-back failed (${response.status}).`);
    }
    return response.json();
  }

  // Reads the persisted annotations straight back and returns the note with
  // this unique-per-submit timestamp — the read-back that confirms a write
  // landed (note present, text matches), a delete took (note absent), or a
  // restore took (note present again).
  async function persistedNoteWithTimestamp(selector, timestamp) {
    const annotations = await readPersistedAnnotations();
    return annotationUserInputs(annotations[selector] || {}).find(
      (item) => item.timestamp === timestamp,
    );
  }

  async function annotationWasPersisted(selector, userInput, timestamp) {
    const note = await persistedNoteWithTimestamp(selector, timestamp);
    return !!note && annotationInputText(note) === userInput;
  }

  function clamp(value, min, max) {
    if (max < min) {
      return min;
    }
    return Math.min(Math.max(value, min), max);
  }

  // Hover lights the reticle on whatever block sits under a fine pointer. The
  // panel carries data-annotation-ui, so hovering it returns no candidate and
  // the reticle clears instead of ringing the panel. Touch pointers skip this
  // and reach the tap bindings further down.
  document.addEventListener("pointermove", (event) => {
    if (event.pointerType === "touch") {
      return;
    }
    setHighlightedAnnotationElement(
      annotationCandidateFromPoint(event.clientX, event.clientY),
    );
  });

  // A bare mousedown on the ※ marker must not start a text selection or pull
  // focus out of the panel; the open happens on the click below.
  document.addEventListener(
    "mousedown",
    (event) => {
      if (annotationMarkerFromEvent(event)) {
        event.preventDefault();
        event.stopPropagation();
      }
    },
    true,
  );

  // Every fine-pointer gesture routes to the one panel:
  //   ※ marker / ⌘-click an annotated block → open it to read its notes
  //   Shift+click any block                  → open it with a focused composer
  //   plain click off the panel              → dismiss it
  // Touch taps are handled by handlePanelTouchTap on pointerup instead.
  document.addEventListener(
    "click",
    (event) => {
      const marker = annotationMarkerFromEvent(event);
      if (marker) {
        const element = annotatedElementFromMarker(marker);
        if (element) {
          event.preventDefault();
          event.stopPropagation();
          openOrSwitchPanel(element, { expand: true });
        }
        return;
      }

      if (isSheet()) {
        return;
      }

      if (event.metaKey && !event.shiftKey) {
        const element = annotatedElementFromPoint(event.clientX, event.clientY);
        if (element) {
          event.preventDefault();
          event.stopPropagation();
          openOrSwitchPanel(element);
        }
        return;
      }

      if (event.shiftKey) {
        const element = annotationCandidateFromPoint(
          event.clientX,
          event.clientY,
        );
        if (element) {
          event.preventDefault();
          event.stopPropagation();
          openOrSwitchPanel(element, { focusComposer: true });
        }
        return;
      }

      // A plain click anywhere but the panel dismisses it (the discard guard
      // still runs first if something is unsaved). Engaging a block needs
      // Shift, so a stray click never re-opens what it just closed.
      if (
        panelOpen() &&
        !event.target.closest(".annotation-panel, .annotation-confirm")
      ) {
        requestDismiss();
      }
    },
    true,
  );

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeChoiceMenu();
      requestDismiss();
    }
  });

  window.addEventListener("resize", () => {
    closeChoiceMenu();
    if (highlightedAnnotationElement) {
      positionHoverOverlay(highlightedAnnotationElement, true);
    }
    if (panelOpen() && !isSheet()) {
      positionDesktopPanel();
    }
  });

  window.addEventListener(
    "scroll",
    () => {
      closeChoiceMenu();
      if (highlightedAnnotationElement) {
        positionHoverOverlay(highlightedAnnotationElement, true);
      }
    },
    { passive: true },
  );

  // ----- Touch: the unified annotation panel ----------------------------
  // On coarse pointers the action bar and the notes card are one component — a
  // bottom sheet whose scrollable body stacks the action-bar section (context +
  // verdict + Annotate), then the existing notes, then an always-present empty
  // composer as the last item. Collapsed, the sheet shows only the handle and
  // the action-bar section; dragging the handle up grows it to a fixed share of
  // the screen and tucks the action bar away above the notes; dragging the
  // handle down collapses it, and from collapsed dismisses it. The body scrolls
  // natively — the handle alone owns the state-drag, so the two never fight.

  const PANEL_VIEWPORT_SHARE = 0.64;
  const PANEL_DETENT_THRESHOLD = 52;
  const PANEL_DISMISS_THRESHOLD = 84;

  let annotationPanel = null;
  let panelHandle = null;
  let panelBody = null;
  let panelActionbar = null;
  let panelContext = null;
  let panelVerdictSegment = null;
  let panelComposer = null;
  let panelElement = null;
  let panelExpanded = false;

  function panelOpen() {
    return Boolean(annotationPanel?.classList.contains("show"));
  }

  function readKeyboardInset() {
    return cssPixels(
      getComputedStyle(document.documentElement).getPropertyValue(
        "--annotation-keyboard-inset",
      ),
      0,
    );
  }

  // Expanded height is the smallest of three bounds: 64% of the screen (the
  // spec's share), whatever clears the software keyboard (so the composer's
  // Save/Cancel stay reachable), and the panel's own content height (so a short
  // block hugs its content instead of leaving most of the sheet empty).
  // scrollHeight reports the full content even while the body is collapsed and
  // clipped, so this is valid in either mode.
  function setPanelExpandedHeight() {
    if (!annotationPanel || !isSheet()) {
      return;
    }
    const full = window.innerHeight;
    const content = panelHandle.offsetHeight + panelBody.scrollHeight;
    const expanded = Math.min(
      full * PANEL_VIEWPORT_SHARE,
      full - readKeyboardInset() - 8,
      content,
    );
    annotationPanel.style.setProperty(
      "--panel-expanded",
      `${Math.round(Math.max(expanded, 160))}px`,
    );
  }

  // Collapsed shows exactly the handle and the action-bar section; its height is
  // per-element (the context line wraps to one or two lines, the verdict row may
  // be absent), so it is measured after each render.
  function measurePanelCollapsedHeight() {
    if (!annotationPanel || !isSheet()) {
      return;
    }
    const padBottom = cssPixels(getComputedStyle(panelBody).paddingBottom, 0);
    annotationPanel.style.setProperty(
      "--panel-collapsed",
      `${Math.round(
        panelHandle.offsetHeight + panelActionbar.offsetHeight + padBottom,
      )}px`,
    );
  }

  function actionbarHeight() {
    return panelActionbar.offsetHeight;
  }

  function ensureAnnotationPanel() {
    if (annotationPanel) {
      return annotationPanel;
    }

    annotationPanel = document.createElement("div");
    annotationPanel.className = "annotation-panel";
    annotationPanel.dataset.annotationUi = "panel";

    panelHandle = document.createElement("div");
    panelHandle.className = "annotation-panel-handle";
    panelHandle.setAttribute("aria-hidden", "true");

    panelBody = document.createElement("div");
    panelBody.className = "annotation-panel-body";
    panelBody.dataset.annotationUi = "panel-body";

    panelActionbar = document.createElement("div");
    panelActionbar.className = "annotation-panel-actionbar";

    panelContext = document.createElement("div");
    panelContext.className = "annotation-action-context";

    panelVerdictSegment = document.createElement("div");
    panelVerdictSegment.className = "annotation-verdict-segment";
    annotationChoices.forEach((choice) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "annotation-verdict-option";
      option.textContent = choice;
      option.addEventListener("click", async () => {
        if (!panelElement || !choiceControlByElement.has(panelElement)) {
          return;
        }
        const current = choiceByElement.get(panelElement)?.value || "";
        await setChoice(panelElement, choice === current ? "" : choice);
        updatePanelVerdict();
      });
      panelVerdictSegment.append(option);
    });

    const annotateButton = document.createElement("button");
    annotateButton.type = "button";
    annotateButton.className = "annotation-panel-annotate";
    annotateButton.textContent = "✎ Annotate";
    annotateButton.addEventListener("click", () => {
      if (panelElement) {
        setPanelMode(true, { focusComposer: true });
      }
    });

    panelActionbar.append(panelContext, panelVerdictSegment, annotateButton);
    panelBody.append(panelActionbar);
    annotationPanel.append(panelHandle, panelBody);
    document.body.append(annotationPanel);
    makePanelDraggable();

    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", () => {
        if (panelOpen()) {
          setPanelExpandedHeight();
        }
      });
    }
    return annotationPanel;
  }

  function updatePanelVerdict() {
    const eligible = panelElement && choiceControlByElement.has(panelElement);
    panelVerdictSegment.hidden = !eligible;
    if (!eligible) {
      return;
    }
    const value = choiceByElement.get(panelElement)?.value || "";
    panelVerdictSegment
      .querySelectorAll(".annotation-verdict-option")
      .forEach((option) =>
        option.classList.toggle("selected", option.textContent === value),
      );
  }

  // The new-annotation composer is the bottom-most "note": always present, never
  // auto-focused. It POSTs on Save, then the notes re-render with it as a real
  // editable note and a fresh empty composer beneath. Cancel just clears it.
  function buildPanelComposer(element) {
    const note = document.createElement("article");
    note.className = "annotation-preview-note annotation-note-draft";

    const body = document.createElement("p");
    body.className = "is-empty";
    body.setAttribute("contenteditable", "plaintext-only");
    body.setAttribute("spellcheck", "false");
    body.setAttribute("aria-label", "New annotation note");
    body.dataset.placeholder = "Add a note…";
    body.dataset.savedText = "";
    note.append(body);

    const actions = document.createElement("div");
    actions.className = "annotation-note-actions";

    const saveButton = document.createElement("button");
    saveButton.className = "annotation-note-action save";
    saveButton.type = "button";
    saveButton.textContent = "Save";
    saveButton.disabled = true;

    const cancelButton = document.createElement("button");
    cancelButton.className = "annotation-note-action revert";
    cancelButton.type = "button";
    cancelButton.textContent = "Cancel";

    actions.append(saveButton, cancelButton);
    note.append(actions);

    const draftText = () => body.innerText.trim();
    const refresh = () => {
      const empty = !draftText();
      body.classList.toggle("is-empty", empty);
      saveButton.disabled = empty;
    };

    function clearDraft() {
      body.textContent = "";
      refresh();
      body.blur();
    }

    async function saveDraft() {
      const userInput = draftText();
      if (!userInput) {
        return;
      }
      const timestamp = localIsoTimestamp();
      const selector = selectorForAnnotationElement(element);
      const text = normalizedElementText(element);
      saveButton.disabled = true;
      cancelButton.disabled = true;
      body.setAttribute("contenteditable", "false");
      try {
        await writeAnnotation(selector, text, userInput, "", timestamp);
        if (!(await annotationWasPersisted(selector, userInput, timestamp))) {
          throw new Error(
            "Write returned ok but the annotation was absent on read-back.",
          );
        }
        recordWrittenAnnotation(element, userInput, "", timestamp);
        // The write is async; only re-render if the panel is still on this block
        // (the reader may have switched away while it was in flight).
        if (panelElement === element) {
          rerenderPanelNotes();
        }
      } catch (error) {
        console.error(error);
        saveButton.classList.add("fail");
        body.setAttribute("contenteditable", "plaintext-only");
        cancelButton.disabled = false;
        refresh();
      }
    }

    body.addEventListener("input", refresh);
    saveButton.addEventListener("click", saveDraft);
    cancelButton.addEventListener("click", clearDraft);
    body.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        clearDraft();
        return;
      }
      if (
        event.key === "Enter" &&
        !event.shiftKey &&
        !event.altKey &&
        !event.ctrlKey &&
        !event.metaKey
      ) {
        event.preventDefault();
        saveDraft();
      }
    });

    refresh();
    return note;
  }

  // Everything below the action-bar section is "the annotations": the persisted
  // notes followed by the composer, rebuilt together from live state.
  function fillPanelNotes(element) {
    while (panelActionbar.nextSibling) {
      panelActionbar.nextSibling.remove();
    }
    const entry = annotationsByElement.get(element);
    annotationUserInputs(entry?.annotation || { userInputs: [] }).forEach(
      (userInput) => panelBody.append(buildPreviewNote(element, userInput)),
    );
    panelComposer = buildPanelComposer(element);
    panelBody.append(panelComposer);
  }

  function rerenderPanelNotes() {
    if (!isSheet()) {
      // Desktop card: rebuild the notes and keep the scroll where it was.
      const top = panelBody.scrollTop;
      fillPanelNotes(panelElement);
      panelBody.scrollTop = top;
      return;
    }
    const listOffset = Math.max(0, panelBody.scrollTop - actionbarHeight());
    fillPanelNotes(panelElement);
    // Content grew (or shrank), so both measured heights are re-derived before
    // restoring the scroll, or a freshly saved note could fall outside a panel
    // still sized to the old content.
    measurePanelCollapsedHeight();
    setPanelExpandedHeight();
    if (panelExpanded) {
      panelBody.scrollTop = actionbarHeight() + listOffset;
    }
  }

  function renderPanelForElement(element) {
    panelElement = element;
    panelContext.textContent = normalizedElementText(element);
    updatePanelVerdict();
    fillPanelNotes(element);
    measurePanelCollapsedHeight();
  }

  // Dirty = an editable note whose text differs from disk, or a non-empty
  // composer. Pending-undo deletions (already persisted) do not count.
  function isPanelDirty() {
    if (!annotationPanel) {
      return false;
    }
    return Array.from(
      panelBody.querySelectorAll('p[contenteditable="plaintext-only"]'),
    ).some((node) => node.innerText.trim() !== (node.dataset.savedText || ""));
  }

  function blurActiveEditable() {
    const active = document.activeElement;
    if (active?.closest?.(".annotation-panel")) {
      active.blur();
    }
  }

  // Collapsed and expanded are the panel's two heights (CSS vars). On expand the
  // body is scrolled past the action-bar section so the annotations sit at the
  // top; Annotate instead scrolls to the composer and focuses it.
  function setPanelMode(
    expanded,
    { focusComposer = false, preserveListOffset = 0 } = {},
  ) {
    panelExpanded = expanded;
    setPanelExpandedHeight();
    annotationPanel.style.height = "";
    annotationPanel.style.transform = "";
    annotationPanel.classList.toggle("expanded", expanded);
    annotationPanel.classList.toggle("collapsed", !expanded);
    if (!expanded) {
      panelBody.scrollTop = 0;
      return;
    }
    // One frame later, so the .expanded class (overflow:auto, taller body) is in
    // effect before scrolling — otherwise scrollTop clamps against the collapsed
    // height. When the content fits, the target simply clamps to 0 (no tuck).
    requestAnimationFrame(() => {
      if (focusComposer) {
        panelBody.scrollTop = panelBody.scrollHeight;
        panelComposer?.querySelector("[contenteditable]")?.focus();
      } else {
        panelBody.scrollTop = actionbarHeight() + preserveListOffset;
      }
    });
  }

  // Desktop: park the card in the corridor to the right of the reading column,
  // pinned near the top by CSS. Its width tracks the corridor but is clamped to
  // a comfortable measure; when the window is too narrow to leave a corridor the
  // card keeps its minimum width and floats over the column's right edge — the
  // same fallback the old floating notes card used.
  function positionDesktopPanel() {
    const column = document.querySelector(".col");
    const columnRight = column ? column.getBoundingClientRect().right : 0;
    const gap = 20;
    const width = clamp(window.innerWidth - columnRight - gap * 2, 300, 384);
    const left = clamp(columnRight + gap, gap, window.innerWidth - gap - width);
    annotationPanel.style.left = `${Math.round(left)}px`;
    annotationPanel.style.width = `${Math.round(width)}px`;
  }

  function doOpenOrSwitch(element, { expand = null, focusComposer = false } = {}) {
    const fresh = !panelOpen();
    const wasExpanded = panelExpanded;
    // Preserve the scroll *relative to the start of the notes* (sheet only),
    // captured before the rebuild: the action-bar height differs per block, so
    // the same pixel offset would land mid-note on a block with a shorter header.
    const listOffset =
      isSheet() && !fresh && wasExpanded
        ? Math.max(0, panelBody.scrollTop - actionbarHeight())
        : 0;
    ensureAnnotationPanel();
    // Switching lands the reader in read-mode: blur whatever was being edited
    // and never auto-focus the new block (the composer is built focus-free) —
    // only an explicit Shift+click, ※ marker, or Annotate puts a caret anywhere.
    blurActiveEditable();
    renderPanelForElement(element);
    setHighlightedAnnotationElement(element);
    annotationPanel.classList.add("show");
    document.body.classList.add("annotation-panel-open");

    if (!isSheet()) {
      // The desktop card is always "expanded": no collapse, no handle, no height
      // var. Position it, and on an annotate gesture drop the caret in the
      // composer at the bottom; a plain open or a switch just refills in place.
      panelExpanded = true;
      positionDesktopPanel();
      if (focusComposer) {
        panelBody.scrollTop = panelBody.scrollHeight;
        panelComposer?.querySelector("[contenteditable]")?.focus();
      }
      return;
    }

    setPanelExpandedHeight();
    const expanded = expand === true ? true : fresh ? false : wasExpanded;
    setPanelMode(expanded, { focusComposer, preserveListOffset: listOffset });
  }

  // A switch (or dismiss) while something is dirty asks first; the same guard
  // covers every teardown, so unsaved text is never lost silently.
  function openOrSwitchPanel(
    element,
    { expand = null, focusComposer = false } = {},
  ) {
    if (
      panelOpen() &&
      panelElement &&
      panelElement !== element &&
      isPanelDirty()
    ) {
      showDiscardConfirm(() => doOpenOrSwitch(element, { expand, focusComposer }));
      return;
    }
    doOpenOrSwitch(element, { expand, focusComposer });
  }

  function dismissPanel() {
    if (!annotationPanel) {
      return;
    }
    blurActiveEditable();
    annotationPanel.classList.remove("show");
    annotationPanel.style.transform = "";
    annotationPanel.style.height = "";
    document.body.classList.remove("annotation-panel-open");
    setHighlightedAnnotationElement(null);
    panelElement = null;
    panelExpanded = false;
  }

  function requestDismiss() {
    if (isPanelDirty()) {
      showDiscardConfirm(dismissPanel);
      return;
    }
    dismissPanel();
  }

  function showDiscardConfirm(onDiscard) {
    const previouslyFocused = document.activeElement;
    const refocus = () => {
      if (previouslyFocused?.isConnected) {
        previouslyFocused.focus();
      }
    };
    const overlay = document.createElement("div");
    overlay.className = "annotation-confirm";
    overlay.dataset.annotationUi = "confirm";
    overlay.setAttribute("role", "alertdialog");
    overlay.setAttribute("aria-label", "Discard changes");
    overlay.innerHTML =
      '<div class="annotation-confirm-box"><p class="annotation-confirm-text">Discard your unsaved changes?</p><div class="annotation-confirm-actions"><button type="button" class="annotation-confirm-keep">Keep editing</button><button type="button" class="annotation-confirm-discard">Discard</button></div></div>';
    document.body.append(overlay);

    const close = () => overlay.remove();
    overlay
      .querySelector(".annotation-confirm-keep")
      .addEventListener("click", () => {
        close();
        refocus();
      });
    overlay
      .querySelector(".annotation-confirm-discard")
      .addEventListener("click", () => {
        close();
        blurActiveEditable();
        onDiscard();
      });
    overlay.addEventListener("pointerdown", (event) => {
      if (event.target === overlay) {
        close();
        refocus();
      }
    });
    requestAnimationFrame(() => overlay.classList.add("open"));
  }

  // The handle is the only state-drag surface: up grows the sheet (collapsed →
  // expanded), down shrinks it (expanded → collapsed) and, from collapsed,
  // slides it off to dismiss. The body's own native scroll is untouched.
  function makePanelDraggable() {
    let pointerId = null;
    let startY = 0;
    let dragging = false;
    let lastDy = 0;
    let startExpanded = false;
    let collapsedH = 0;
    let expandedH = 0;

    panelHandle.addEventListener("pointerdown", (event) => {
      if (event.button && event.button !== 0) {
        return;
      }
      pointerId = event.pointerId;
      startY = event.clientY;
      dragging = false;
      lastDy = 0;
      startExpanded = panelExpanded;
      collapsedH = cssPixels(
        getComputedStyle(annotationPanel).getPropertyValue("--panel-collapsed"),
        160,
      );
      expandedH = cssPixels(
        getComputedStyle(annotationPanel).getPropertyValue("--panel-expanded"),
        420,
      );
    });

    panelHandle.addEventListener("pointermove", (event) => {
      if (pointerId === null || event.pointerId !== pointerId) {
        return;
      }
      lastDy = event.clientY - startY;
      if (!dragging) {
        if (Math.abs(lastDy) < 8) {
          return;
        }
        dragging = true;
        annotationPanel.classList.add("dragging");
        panelHandle.setPointerCapture?.(pointerId);
      }
      event.preventDefault();
      if (!startExpanded && lastDy > 0) {
        annotationPanel.style.transform = `translateY(${lastDy}px)`;
      } else {
        const base = startExpanded ? expandedH : collapsedH;
        annotationPanel.style.transform = "";
        annotationPanel.style.height = `${clamp(base - lastDy, collapsedH, expandedH)}px`;
      }
    });

    function endPanelDrag(event) {
      if (pointerId === null || event.pointerId !== pointerId) {
        return;
      }
      const id = pointerId;
      const wasDragging = dragging;
      pointerId = null;
      dragging = false;
      if (!wasDragging) {
        return;
      }
      if (panelHandle.hasPointerCapture?.(id)) {
        panelHandle.releasePointerCapture(id);
      }
      annotationPanel.classList.remove("dragging");
      annotationPanel.style.transform = "";
      annotationPanel.style.height = "";
      if (!startExpanded && lastDy > 0) {
        if (lastDy >= PANEL_DISMISS_THRESHOLD) {
          requestDismiss();
        } else {
          setPanelMode(false);
        }
      } else if (startExpanded) {
        setPanelMode(lastDy < PANEL_DETENT_THRESHOLD);
      } else {
        setPanelMode(-lastDy >= PANEL_DETENT_THRESHOLD);
      }
    }

    panelHandle.addEventListener("pointerup", endPanelDrag);
    panelHandle.addEventListener("pointercancel", endPanelDrag);
  }

  // A page tap routes to the panel: an annotatable target opens or switches it;
  // empty space (or a link) dismisses it only while collapsed — an expanded
  // panel stays put, since reaching it signalled intent to dive in. Taps inside
  // the panel, the confirm dialog, or on the ※ marker are handled elsewhere.
  function handlePanelTouchTap(event) {
    if (
      event.target.closest?.(
        ".annotation-panel, .annotation-confirm, .annotation-marker",
      )
    ) {
      return;
    }
    const candidate = annotationCandidateFromPoint(event.clientX, event.clientY);
    if (candidate) {
      openOrSwitchPanel(candidate);
      return;
    }
    if (panelOpen() && !panelExpanded) {
      requestDismiss();
    }
  }

  let touchTapOrigin = null;

  document.addEventListener("pointerdown", (event) => {
    if (event.pointerType !== "touch" || !event.isPrimary) {
      return;
    }
    touchTapOrigin = { x: event.clientX, y: event.clientY };
  });

  document.addEventListener("pointercancel", () => {
    touchTapOrigin = null;
  });

  document.addEventListener("pointerup", (event) => {
    if (event.pointerType !== "touch" || !touchTapOrigin) {
      return;
    }
    const origin = touchTapOrigin;
    touchTapOrigin = null;
    const isTap =
      Math.hypot(event.clientX - origin.x, event.clientY - origin.y) <= 12;
    if (isTap) {
      handlePanelTouchTap(event);
    }
  });

  // iOS lays the software keyboard over position:fixed elements instead of
  // resizing the page; the visual viewport is the only honest report of the
  // space left. The inset feeds the bottom-sheet CSS.
  function updateAnnotationKeyboardInset() {
    const viewport = window.visualViewport;
    const inset = Math.max(
      0,
      window.innerHeight - viewport.height - viewport.offsetTop,
    );
    document.documentElement.style.setProperty(
      "--annotation-keyboard-inset",
      `${inset}px`,
    );
  }

  if (window.visualViewport) {
    window.visualViewport.addEventListener(
      "resize",
      updateAnnotationKeyboardInset,
    );
    window.visualViewport.addEventListener(
      "scroll",
      updateAnnotationKeyboardInset,
    );
  }

  // ----- Quick-answer choice control -----------------------------------
  // Some whole-units are statements, not questions; this split button lets the
  // reviewer commit a one-word verdict. The primary side commits (or toggles
  // off) the shown value; the caret opens the other mutually-exclusive choices.
  // Unlike free-text notes, which append, a choice overwrites the previous one
  // and lives in its own `choice` field — so an element can carry both many
  // notes and exactly one choice. Subtle on every data-annotate-whole block,
  // solid once a choice is set.
  async function writeAnnotationChoice(selector, text, value, timestamp) {
    const response = await fetch(`${annotationEndpoint}/choice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selector, text, value, timestamp }),
    });
    if (response.ok) {
      return;
    }
    const details = await response.text();
    throw new Error(
      `Annotation choice write failed (${response.status}): ${details}`,
    );
  }

  async function persistedChoiceValue(selector) {
    const annotations = await readPersistedAnnotations();
    return annotations[selector]?.choice?.value || "";
  }

  function applyChoiceState(element) {
    const control = choiceControlByElement.get(element);
    if (!control) {
      return;
    }
    const value = choiceByElement.get(element)?.value || "";
    control.classList.toggle("is-set", Boolean(value));
    control.querySelector(".annotation-choice-label").textContent =
      value || annotationChoices[0];
    control
      .querySelector(".annotation-choice-primary")
      .setAttribute("aria-pressed", value ? "true" : "false");
  }

  // Every choice mutation writes, reads the file straight back to confirm the
  // value landed (or cleared), and only then updates local state — the same
  // write-then-verify contract the notes use.
  async function setChoice(element, value) {
    const control = choiceControlByElement.get(element);
    const selector = selectorForAnnotationElement(element);
    const text = normalizedElementText(element);
    const timestamp = localIsoTimestamp();
    control.classList.remove("fail");
    control.classList.add("annotation-choice-pending");
    try {
      await writeAnnotationChoice(selector, text, value, timestamp);
      if ((await persistedChoiceValue(selector)) !== value) {
        throw new Error("Choice write was absent on read-back.");
      }
      if (value) {
        choiceByElement.set(element, { selector, value, timestamp });
      } else {
        choiceByElement.delete(element);
      }
      applyChoiceState(element);
      // Keep the panel's verdict segment in lockstep when the rail split-button
      // (desktop) is what changed the choice on the block the panel is showing.
      if (panelElement === element) {
        updatePanelVerdict();
      }
    } catch (error) {
      console.error(error);
      control.classList.add("fail");
    } finally {
      control.classList.remove("annotation-choice-pending");
    }
  }

  function closeChoiceMenu() {
    if (!activeChoiceMenu) {
      return;
    }
    activeChoiceMenu.control
      .querySelector(".annotation-choice-caret")
      .setAttribute("aria-expanded", "false");
    document.removeEventListener("mousedown", activeChoiceMenu.onOutside, true);
    activeChoiceMenu.menu.remove();
    activeChoiceMenu = null;
  }

  function openChoiceMenu(element, control) {
    closeChoiceMenu();
    const activeValue = choiceByElement.get(element)?.value || "";
    const menu = document.createElement("div");
    menu.className = "annotation-choice-menu";
    menu.dataset.annotationUi = "choice-menu";
    annotationChoices.forEach((choice) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "annotation-choice-option";
      option.textContent = choice;
      if (choice === activeValue) {
        option.classList.add("selected");
      }
      option.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        closeChoiceMenu();
        setChoice(element, choice === activeValue ? "" : choice);
      });
      menu.append(option);
    });
    document.body.append(menu);

    const caret = control.querySelector(".annotation-choice-caret");
    const caretRect = caret.getBoundingClientRect();
    const menuRect = menu.getBoundingClientRect();
    menu.style.left = `${clamp(
      caretRect.right - menuRect.width,
      8,
      window.innerWidth - menuRect.width - 8,
    )}px`;
    menu.style.top = `${clamp(
      caretRect.bottom + 4,
      8,
      window.innerHeight - menuRect.height - 8,
    )}px`;
    caret.setAttribute("aria-expanded", "true");

    const onOutside = (event) => {
      if (!menu.contains(event.target) && !control.contains(event.target)) {
        closeChoiceMenu();
      }
    };
    document.addEventListener("mousedown", onOutside, true);
    activeChoiceMenu = { element, control, menu, onOutside };
  }

  function toggleChoiceMenu(element, control) {
    if (activeChoiceMenu && activeChoiceMenu.element === element) {
      closeChoiceMenu();
      return;
    }
    openChoiceMenu(element, control);
  }

  function ensureChoiceControl(element) {
    const existing = choiceControlByElement.get(element);
    if (existing) {
      return existing;
    }

    // A <span> root stays valid phrasing content inside a <p> (the .stance
    // blocks) where a <div> would be hoisted out; buttons are phrasing too.
    const control = document.createElement("span");
    control.className = "annotation-choice";
    control.dataset.annotationUi = "choice";

    const primary = document.createElement("button");
    primary.type = "button";
    primary.className = "annotation-choice-primary";
    primary.setAttribute("aria-pressed", "false");
    const label = document.createElement("span");
    label.className = "annotation-choice-label";
    label.textContent = annotationChoices[0];
    primary.append(label);

    const caret = document.createElement("button");
    caret.type = "button";
    caret.className = "annotation-choice-caret";
    caret.setAttribute("aria-haspopup", "true");
    caret.setAttribute("aria-expanded", "false");
    caret.setAttribute("aria-label", "Choose a different answer");
    caret.textContent = "▾";

    primary.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const active = choiceByElement.get(element)?.value || "";
      setChoice(element, active ? "" : annotationChoices[0]);
    });
    caret.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      toggleChoiceMenu(element, control);
    });

    control.append(primary, caret);
    ensureAnnotationRail(annotationMarkerHost(element)).append(control);
    choiceControlByElement.set(element, control);
    return control;
  }

  function setupChoiceButtons() {
    document.querySelectorAll("[data-annotate-whole]").forEach((element) => {
      // A positioned control can't be hosted inside table internals (it would
      // be foster-parented out of the table), so tables keep notes only.
      if (element.closest("table") || !normalizedElementText(element)) {
        return;
      }
      ensureChoiceControl(element);
    });
  }

  // ----- Jump to the next un-annotated unit ----------------------------
  // The author marks every unit of communication as a whole-annotation target
  // (annotationWholeSelector), so that — not "any element with text" — is what
  // "information-carrying" means here. This pill walks downward from where the
  // reviewer is: it scrolls to the nearest unit without a note whose center
  // sits below the viewport center (anything at or above center is treated as
  // already passed) and lights the reticle on it. When the walk runs past the
  // last one, it wraps to the topmost unanswered unit so units skipped upstream
  // stay reachable. Created only when the page actually has whole-units.
  function nextUnannotatedWholeElement() {
    const unanswered = Array.from(
      document.querySelectorAll(annotationWholeSelector),
    ).filter(
      (element) =>
        !annotationsByElement.has(element) &&
        !choiceByElement.has(element) &&
        normalizedElementText(element),
    );
    const viewportCenter = window.innerHeight / 2;
    // A unit counts as "below" only if its center clears the viewport center by
    // a hair — so the unit we just centered (its center now sits on that line)
    // reads as already passed, and a second press advances to the next one down.
    const isBelowViewportCenter = (element) => {
      const rect = element.getBoundingClientRect();
      return rect.top + rect.height / 2 > viewportCenter + 2;
    };
    return unanswered.find(isBelowViewportCenter) || unanswered[0];
  }

  function setupNextUnannotatedButton() {
    if (!document.querySelector(annotationWholeSelector)) {
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "annotation-next-unannotated";
    button.dataset.annotationUi = "next-unannotated";
    button.setAttribute("aria-label", "Scroll to the next un-annotated item");

    const icon = document.createElement("span");
    icon.className = "annotation-next-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "↓";

    const label = document.createElement("span");
    label.className = "annotation-next-label";
    label.textContent = "Next unanswered";
    button.append(icon, label);
    document.body.append(button);

    let resetTimer = 0;
    button.addEventListener("click", () => {
      const target = nextUnannotatedWholeElement();
      if (target) {
        const rect = target.getBoundingClientRect();
        // Center with a plain scroll, not scrollIntoView — the page's
        // scroll-margin-top would otherwise land the unit a notch low, leaving
        // its center just below the viewport center and re-selecting it on the
        // next press instead of advancing.
        window.scrollTo({
          top:
            window.scrollY + rect.top + rect.height / 2 - window.innerHeight / 2,
          behavior: "smooth",
        });
        setHighlightedAnnotationElement(target);
        return;
      }
      // Nothing left to answer: confirm in place, then settle back.
      window.clearTimeout(resetTimer);
      button.classList.add("done");
      icon.textContent = "✓";
      label.textContent = "All answered";
      resetTimer = window.setTimeout(() => {
        button.classList.remove("done");
        icon.textContent = "↓";
        label.textContent = "Next unanswered";
      }, 1600);
    });
  }

  setupChoiceButtons();
  setupNextUnannotatedButton();
  loadAnnotations().catch((error) => console.warn(error));
})();

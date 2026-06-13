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
  const annotationsByElement = new Map();
  const annotationPreviewsByElement = new Map();
  const choiceByElement = new Map();
  const choiceControlByElement = new Map();
  const annotationChoices = ["Yes", "Agreed", "Locked"];
  let activeChoiceMenu = null;
  let highlightedAnnotationElement = null;
  let activeAnnotationEditor = null;
  let activeAnnotationElement = null;
  let activeAnnotationSelection = "";
  let activeAnnotationSelectionRange = null;

  // A persistent custom highlight survives focus changes and styles the
  // captured phrase distinctly from a native browser selection.
  const annotationSelectionHighlight =
    typeof Highlight === "function" && CSS.highlights ? new Highlight() : null;
  if (annotationSelectionHighlight) {
    CSS.highlights.set("annotation-selection", annotationSelectionHighlight);
  }

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

  function selectedRangeWithin(element) {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
      return null;
    }

    const range = selection.getRangeAt(0);
    if (
      !element.contains(range.startContainer) ||
      !element.contains(range.endContainer)
    ) {
      return null;
    }

    const text = selection.toString().trim().replace(/\s+/g, " ");
    if (!text) {
      return null;
    }

    return { text, range: range.cloneRange() };
  }

  function updateAnnotationSelectionHighlight() {
    if (!annotationSelectionHighlight) {
      return;
    }
    annotationSelectionHighlight.clear();
    if (activeAnnotationSelectionRange) {
      annotationSelectionHighlight.add(activeAnnotationSelectionRange);
    }
  }

  function updateAnnotationSelectionPreview() {
    const preview = activeAnnotationEditor?.querySelector(
      ".annotation-selection-preview",
    );
    if (!preview) {
      return;
    }

    preview.hidden = !activeAnnotationSelection;
    preview.querySelector(".annotation-selection-text").textContent =
      activeAnnotationSelection;
  }

  function setActiveAnnotationSelection(selection) {
    activeAnnotationSelection = selection?.text || "";
    activeAnnotationSelectionRange = selection?.range || null;
    updateAnnotationSelectionHighlight();
    updateAnnotationSelectionPreview();
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

  function setAnnotationMarkerPressed(element, pressed) {
    annotationMarkerForElement(element)?.setAttribute(
      "aria-pressed",
      pressed ? "true" : "false",
    );
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

  // Removes the editor once its exit transition finishes, falling back to an
  // immediate removal when motion is disabled (so reduced-motion never leaves
  // an orphaned node waiting on a transitionend that never fires).
  function removeEditorAfterTransition(editor) {
    const maxDuration = Math.max(
      0,
      ...getComputedStyle(editor)
        .transitionDuration.split(",")
        .map((value) => Number.parseFloat(value) || 0),
    );
    if (maxDuration === 0) {
      editor.remove();
      return;
    }
    let removed = false;
    const remove = () => {
      if (removed) {
        return;
      }
      removed = true;
      editor.remove();
    };
    editor.addEventListener("transitionend", remove, { once: true });
    window.setTimeout(remove, maxDuration * 1000 + 60);
  }

  function closeAnnotationEditor() {
    const editor = activeAnnotationEditor;
    activeAnnotationEditor = null;
    activeAnnotationElement = null;
    setActiveAnnotationSelection(null);
    setHighlightedAnnotationElement(null);
    if (!editor) {
      return;
    }
    editor.classList.remove("open");
    editor.classList.add("closing");
    removeEditorAfterTransition(editor);
  }

  function showAnnotationStatus(statusElement, className, text) {
    statusElement.className = `annotation-status show ${className}`;
    statusElement.textContent = text;
  }

  function closeAnnotationPreview(element) {
    const preview = annotationPreviewsByElement.get(element);
    if (!preview) {
      return;
    }
    preview.remove();
    element.classList.remove("annotation-linked-hover");
    annotationPreviewsByElement.delete(element);
    setAnnotationMarkerPressed(element, false);
    positionAnnotationPreviews();
  }

  function closeAllAnnotationPreviews() {
    annotationPreviewsByElement.forEach((preview, element) => {
      preview.remove();
      element.classList.remove("annotation-linked-hover");
      setAnnotationMarkerPressed(element, false);
    });
    annotationPreviewsByElement.clear();
  }

  function annotationCountLabel(count) {
    return count === 1 ? "1 annotation" : `${count} annotations`;
  }

  function createAnnotationPreview(element, annotation) {
    const preview = document.createElement("aside");
    const userInputs = annotationUserInputs(annotation);
    preview.className = "annotation-preview";
    preview.setAttribute("role", "dialog");
    preview.setAttribute("aria-label", "Annotation preview");

    const header = document.createElement("div");
    header.className = "annotation-preview-header";

    const title = document.createElement("div");
    title.className = "annotation-preview-title";
    title.textContent = annotationCountLabel(userInputs.length);

    const closeButton = document.createElement("button");
    closeButton.className = "annotation-preview-close";
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Close annotation preview");
    closeButton.textContent = "×";
    closeButton.addEventListener("click", () => closeAnnotationPreview(element));
    preview.addEventListener("mouseenter", () => setLinkedAnnotationElement(element));
    preview.addEventListener("mouseleave", () => setLinkedAnnotationElement(null));

    header.append(title, closeButton);
    preview.append(header);

    const targetText = document.createElement("div");
    targetText.className = "annotation-preview-target";
    targetText.textContent = annotation.text;
    preview.append(targetText);

    const list = document.createElement("div");
    list.className = "annotation-preview-list";
    userInputs.forEach((userInput) => {
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
      list.append(note);
    });
    preview.append(list);
    makeAnnotationPreviewDraggable(preview);

    return preview;
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

    const refreshPreviewTitle = () => {
      const entry = annotationsByElement.get(element);
      const count = entry ? annotationUserInputs(entry.annotation).length : 0;
      note
        .closest(".annotation-preview")
        .querySelector(".annotation-preview-title").textContent =
        annotationCountLabel(count);
    };

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
      refreshPreviewTitle();
      revertButton.disabled = false;
      positionAnnotationPreviews();
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
      refreshPreviewTitle();
      deleteButton.disabled = false;
      refreshDirtyState();
      positionAnnotationPreviews();
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

  // Dragging is offered on the preview's own padding (event.target is the
  // preview itself there, never its text or buttons), so no visual handle is
  // needed. The bottom-right corner is left to the native resize grip; grabbing
  // either marks the preview user-placed so auto-layout stops moving it.
  function makeAnnotationPreviewDraggable(preview) {
    preview.addEventListener("mousedown", (event) => {
      if (event.target !== preview) {
        return;
      }
      preview.dataset.userPlaced = "true";

      const rect = preview.getBoundingClientRect();
      const onResizeGrip =
        rect.right - event.clientX < 18 && rect.bottom - event.clientY < 18;
      if (onResizeGrip) {
        preview.style.maxHeight = "calc(100vh - 1rem)";
        return;
      }

      event.preventDefault();
      const grabX = event.clientX - rect.left;
      const grabY = event.clientY - rect.top;

      const onMove = (moveEvent) => {
        const position = clampEditorPosition(
          moveEvent.clientX - grabX,
          moveEvent.clientY - grabY,
          preview.offsetWidth,
          preview.offsetHeight,
        );
        preview.style.left = `${position.left}px`;
        preview.style.top = `${position.top}px`;
      };

      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }

  function cssPixels(value, fallback) {
    const pixels = Number.parseFloat(value);
    return Number.isFinite(pixels) ? pixels : fallback;
  }

  function positionAnnotationPreview(preview, element) {
    const elementRect = element.getBoundingClientRect();
    const columnRect = (element.closest(".col") || element).getBoundingClientRect();
    const wrap = element.closest(".wrap");
    const gap = wrap ? cssPixels(getComputedStyle(wrap).paddingRight, 24) : 24;
    const corridorLeft = columnRect.right;
    const corridorRight = window.innerWidth - gap;
    const corridorWidth = corridorRight - corridorLeft;
    const width = clamp(corridorWidth, 224, 360);

    preview.style.width = `${width}px`;
    const previewRect = preview.getBoundingClientRect();
    const centeredLeft = corridorLeft + (corridorWidth - previewRect.width) / 2;
    const fallbackLeft = clamp(
      elementRect.left,
      gap,
      window.innerWidth - previewRect.width - gap,
    );
    const left = corridorWidth >= previewRect.width ? centeredLeft : fallbackLeft;
    const top = clamp(
      elementRect.top,
      gap,
      window.innerHeight - previewRect.height - gap,
    );

    preview.style.left = `${left}px`;
    preview.style.top = `${top}px`;
  }

  // Auto-layout only manages previews the user hasn't dragged or resized;
  // user-placed ones keep their position and size.
  function positionAnnotationPreviews() {
    const gap = 12;
    const entries = Array.from(annotationPreviewsByElement.entries())
      .filter(([, preview]) => !preview.dataset.userPlaced)
      .map(([element, preview]) => ({
        element,
        preview,
        top: element.getBoundingClientRect().top,
      }))
      .sort((first, second) => first.top - second.top);

    entries.forEach(({ preview, element }) => {
      positionAnnotationPreview(preview, element);
    });

    let previousBottom = -Infinity;
    entries.forEach(({ preview }) => {
      const rect = preview.getBoundingClientRect();
      const top = clamp(
        Math.max(rect.top, previousBottom + gap),
        gap,
        window.innerHeight - rect.height - gap,
      );
      preview.style.top = `${top}px`;
      previousBottom = top + rect.height;
    });
  }

  function openAnnotationPreview(element) {
    const entry = annotationsByElement.get(element);
    if (!entry) {
      return;
    }
    if (sheetLayoutInput.matches) {
      closeAllAnnotationPreviews();
    }

    const preview = createAnnotationPreview(element, entry.annotation);
    preview.style.visibility = "hidden";
    document.body.appendChild(preview);
    annotationPreviewsByElement.set(element, preview);
    setAnnotationMarkerPressed(element, true);
    positionAnnotationPreviews();
    preview.style.visibility = "visible";
  }

  function toggleAnnotationPreview(element) {
    if (annotationPreviewsByElement.has(element)) {
      closeAnnotationPreview(element);
      return;
    }
    openAnnotationPreview(element);
  }

  function setLinkedAnnotationPreview(element) {
    annotationPreviewsByElement.forEach((preview, previewElement) => {
      preview.classList.toggle(
        "annotation-preview-linked-hover",
        previewElement === element,
      );
    });
  }

  function setLinkedAnnotationElement(element) {
    annotationsByElement.forEach((_entry, annotatedElement) => {
      annotatedElement.classList.toggle(
        "annotation-linked-hover",
        annotatedElement === element,
      );
    });
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

  // The editor's left/top are its top-left corner: dragging and resizing both
  // behave intuitively, and a single clamp keeps it fully inside the viewport.
  function clampEditorPosition(left, top, width, height) {
    return {
      left: clamp(left, 0, window.innerWidth - width),
      top: clamp(top, 0, window.innerHeight - height),
    };
  }

  function positionAnnotationEditor(editor, element) {
    const elementRect = element.getBoundingClientRect();
    const width = editor.offsetWidth;
    const height = editor.offsetHeight;
    const position = clampEditorPosition(
      elementRect.left + elementRect.width / 2 - width / 2,
      elementRect.top + elementRect.height / 2,
      width,
      height,
    );
    editor.style.left = `${position.left}px`;
    editor.style.top = `${position.top}px`;
  }

  function reclampFloatingPanel(editor) {
    const position = clampEditorPosition(
      Number.parseFloat(editor.style.left) || 0,
      Number.parseFloat(editor.style.top) || 0,
      editor.offsetWidth,
      editor.offsetHeight,
    );
    editor.style.left = `${position.left}px`;
    editor.style.top = `${position.top}px`;
  }

  function makeAnnotationEditorDraggable(editor, handle) {
    handle.addEventListener("mousedown", (event) => {
      event.preventDefault();
      // Settle any in-flight entrance transform before measuring, so a drag
      // started mid-animation doesn't jump on the first move.
      editor.classList.add("dragging");
      const rect = editor.getBoundingClientRect();
      const grabX = event.clientX - rect.left;
      const grabY = event.clientY - rect.top;

      const onMove = (moveEvent) => {
        const position = clampEditorPosition(
          moveEvent.clientX - grabX,
          moveEvent.clientY - grabY,
          editor.offsetWidth,
          editor.offsetHeight,
        );
        editor.style.left = `${position.left}px`;
        editor.style.top = `${position.top}px`;
      };

      const onUp = () => {
        editor.classList.remove("dragging");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }

  // One submit path serves every input mode: bare Enter on desktop, the
  // footer's Save button on touch screens.
  async function submitActiveAnnotationEditor() {
    const editor = activeAnnotationEditor;
    const annotatedElement = activeAnnotationElement;
    if (!editor || !annotatedElement) {
      return;
    }

    const textarea = editor.querySelector("textarea");
    const status = editor.querySelector(".annotation-status");
    const userInput = textarea.value.trim();
    if (!userInput) {
      return;
    }

    const specificallySelected = activeAnnotationSelection;
    const timestamp = localIsoTimestamp();
    const selector = selectorForAnnotationElement(annotatedElement);
    const text = normalizedElementText(annotatedElement);

    textarea.disabled = true;
    try {
      await writeAnnotation(
        selector,
        text,
        userInput,
        specificallySelected,
        timestamp,
      );
      const persisted = await annotationWasPersisted(
        selector,
        userInput,
        timestamp,
      );
      if (!persisted) {
        throw new Error(
          "Write returned ok but the annotation was absent on read-back.",
        );
      }
      recordWrittenAnnotation(
        annotatedElement,
        userInput,
        specificallySelected,
        timestamp,
      );
      showAnnotationStatus(status, "ok", "✓");
      closeAnnotationEditor();
    } catch (error) {
      console.error(error);
      textarea.disabled = false;
      showAnnotationStatus(status, "fail", "✕");
      textarea.focus();
    }
  }

  function openAnnotationEditor(element) {
    closeAllAnnotationPreviews();
    if (activeAnnotationEditor) {
      closeAnnotationEditor();
    }

    activeAnnotationElement = element;
    setHighlightedAnnotationElement(element);

    const editor = document.createElement("div");
    editor.className = "annotation-editor";
    editor.innerHTML =
      '<div class="annotation-editor-handle" data-annotation-ui="handle" aria-hidden="true"></div><div class="annotation-selection-preview" hidden><span class="annotation-selection-arrow" aria-hidden="true">↳</span><q class="annotation-selection-text"></q></div><textarea aria-label="Annotation text" autofocus></textarea><div class="annotation-editor-footer" data-annotation-ui="footer"><button type="button" class="annotation-editor-cancel">Cancel</button><button type="button" class="annotation-editor-save">Save</button></div><div class="annotation-status"></div>';
    document.body.appendChild(editor);
    positionAnnotationEditor(editor, element);
    requestAnimationFrame(() =>
      requestAnimationFrame(() => editor.classList.add("open")),
    );

    const textarea = editor.querySelector("textarea");
    const handle = editor.querySelector(".annotation-editor-handle");
    activeAnnotationEditor = editor;
    updateAnnotationSelectionPreview();
    textarea.focus();
    makeAnnotationEditorDraggable(editor, handle);

    editor
      .querySelector(".annotation-editor-cancel")
      .addEventListener("click", closeAnnotationEditor);
    editor
      .querySelector(".annotation-editor-save")
      .addEventListener("click", submitActiveAnnotationEditor);

    textarea.addEventListener("keydown", (event) => {
      if (
        event.key !== "Enter" ||
        event.shiftKey ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey
      ) {
        return;
      }
      event.preventDefault();
      submitActiveAnnotationEditor();
    });
  }

  // Hover semantics belong to hover-capable pointers; taps reach the touch
  // bindings below instead of impersonating a mouse.
  document.addEventListener("pointermove", (event) => {
    if (event.pointerType === "touch") {
      return;
    }
    const marker = annotationMarkerFromEvent(event);
    const linkedElement = marker
      ? annotatedElementFromMarker(marker)
      : annotatedElementFromPoint(event.clientX, event.clientY);
    setLinkedAnnotationPreview(linkedElement);

    if (activeAnnotationEditor) {
      return;
    }
    setHighlightedAnnotationElement(
      annotationCandidateFromPoint(event.clientX, event.clientY),
    );
  });

  document.addEventListener("mouseleave", () => {
    setLinkedAnnotationPreview(null);
    setLinkedAnnotationElement(null);
  });

  document.addEventListener(
    "mousedown",
    (event) => {
      if (activeAnnotationEditor || !event.shiftKey) {
        return;
      }

      const element = annotationCandidateFromPoint(
        event.clientX,
        event.clientY,
      );
      if (!element) {
        return;
      }

      const selection = selectedRangeWithin(element);
      setActiveAnnotationSelection(selection);
      if (selection) {
        event.preventDefault();
      }
    },
    true,
  );

  document.addEventListener(
    "mousedown",
    (event) => {
      const marker = annotationMarkerFromEvent(event);
      if (marker) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }

      if (!event.metaKey || event.shiftKey || activeAnnotationEditor) {
        return;
      }

      const element = annotatedElementFromPoint(event.clientX, event.clientY);
      if (!element) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      toggleAnnotationPreview(element);
    },
    true,
  );

  document.addEventListener(
    "click",
    (event) => {
      const marker = annotationMarkerFromEvent(event);
      if (marker) {
        const element = annotatedElementFromMarker(marker);
        if (element) {
          event.preventDefault();
          event.stopPropagation();
          toggleAnnotationPreview(element);
        }
        return;
      }

      if (event.metaKey && !event.shiftKey && !activeAnnotationEditor) {
        const element = annotatedElementFromPoint(event.clientX, event.clientY);
        if (element) {
          event.preventDefault();
          event.stopPropagation();
        }
        return;
      }

      if (activeAnnotationEditor || !event.shiftKey) {
        return;
      }

      const element = annotationCandidateFromPoint(
        event.clientX,
        event.clientY,
      );
      if (!element) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      openAnnotationEditor(element);
    },
    true,
  );

  // selectionchange feeds the open editor from every selection mechanism —
  // mouse drags, keyboard selection, and touch long-press handles alike.
  document.addEventListener("selectionchange", () => {
    if (!activeAnnotationEditor || !activeAnnotationElement) {
      return;
    }

    const selection = selectedRangeWithin(activeAnnotationElement);
    if (selection) {
      setActiveAnnotationSelection(selection);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeChoiceMenu();
      closeAnnotationEditor();
      closeAllAnnotationPreviews();
    }
  });

  window.addEventListener("resize", () => {
    closeChoiceMenu();
    if (activeAnnotationEditor) {
      reclampFloatingPanel(activeAnnotationEditor);
    }
    annotationPreviewsByElement.forEach((preview) => {
      if (preview.dataset.userPlaced) {
        reclampFloatingPanel(preview);
      }
    });
    if (highlightedAnnotationElement) {
      positionHoverOverlay(highlightedAnnotationElement, true);
    }
    positionAnnotationPreviews();
  });

  window.addEventListener(
    "scroll",
    () => {
      closeChoiceMenu();
      if (highlightedAnnotationElement) {
        positionHoverOverlay(highlightedAnnotationElement, true);
      }
      positionAnnotationPreviews();
    },
    { passive: true },
  );

  // ----- Touch bindings ------------------------------------------------
  // Touch has no hover and no modifier keys, so a tap takes over the hover
  // reticle's role and grows it an action bar (✎ annotate, ※ notes). The
  // gestures only translate into the same actions the desktop bindings call;
  // everything above stays input-agnostic. Detection runs on pointer events
  // with pointerType "touch", so mouse and trackpad input never engages it —
  // and it works on elements iOS Safari won't synthesize click events for.

  let annotationActionBar = null;
  let annotationAnnotateButton = null;
  let annotationVerdictSegment = null;

  function ensureAnnotationActionBar() {
    if (annotationActionBar) {
      return annotationActionBar;
    }

    annotationActionBar = document.createElement("div");
    annotationActionBar.className = "annotation-action-bar";
    annotationActionBar.dataset.annotationUi = "action-bar";

    annotationAnnotateButton = document.createElement("button");
    annotationAnnotateButton.type = "button";
    annotationAnnotateButton.textContent = "✎ Annotate";
    annotationAnnotateButton.addEventListener("click", () => {
      const element = highlightedAnnotationElement;
      if (!element) {
        return;
      }
      hideAnnotationActionBar();
      setActiveAnnotationSelection(selectedRangeWithin(element));
      openAnnotationEditor(element);
    });

    // Touch's verdict picker — the mobile twin of the desktop hover split-button.
    // One tap commits; tapping the selected segment again clears. The bar stays
    // open so the choice reads back in place. Shown only for verdict-eligible
    // blocks (toggled in updateActionBarVerdict).
    annotationVerdictSegment = document.createElement("div");
    annotationVerdictSegment.className = "annotation-verdict-segment";
    annotationVerdictSegment.dataset.annotationUi = "verdict-segment";
    annotationChoices.forEach((choice) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "annotation-verdict-option";
      option.textContent = choice;
      option.addEventListener("click", async () => {
        const element = highlightedAnnotationElement;
        if (!element) {
          return;
        }
        const current = choiceByElement.get(element)?.value || "";
        await setChoice(element, choice === current ? "" : choice);
        updateActionBarVerdict(element);
      });
      annotationVerdictSegment.append(option);
    });

    annotationActionBar.append(annotationVerdictSegment, annotationAnnotateButton);
    hoverOverlay.append(annotationActionBar);
    return annotationActionBar;
  }

  function hideAnnotationActionBar() {
    annotationActionBar?.classList.remove("show");
  }

  // The bar hangs below the reticle and slides up just enough to stay inside
  // the viewport when the tapped element runs past the bottom of the screen.
  function placeAnnotationActionBar(element) {
    const rect = element.getBoundingClientRect();
    const overlayTop = rect.top - hoverOverlayOffsetY;
    const overlayHeight = rect.height + hoverOverlayOffsetY * 2;
    const barHeight = annotationActionBar.offsetHeight;
    const topWithinOverlay = clamp(
      overlayHeight + 8,
      10 - overlayTop,
      window.innerHeight - overlayTop - barHeight - 10,
    );
    annotationActionBar.style.top = `${topWithinOverlay}px`;
  }

  // The bar carries the verdict picker only for blocks that can hold a verdict,
  // reflecting the block's current choice — touch's stand-in for the desktop
  // rail split-button.
  function updateActionBarVerdict(element) {
    if (!annotationVerdictSegment) {
      return;
    }
    const eligible = choiceControlByElement.has(element);
    annotationVerdictSegment.hidden = !eligible;
    if (!eligible) {
      return;
    }
    const value = choiceByElement.get(element)?.value || "";
    annotationVerdictSegment
      .querySelectorAll(".annotation-verdict-option")
      .forEach((option) => {
        option.classList.toggle("selected", option.textContent === value);
      });
  }

  // One button for adding an annotation; its label reflects how many notes the
  // element already has. Viewing existing notes is the ※ rail badge's job, on
  // touch as on desktop — so the bar never carries a redundant second button.
  function showAnnotationActionBar(element) {
    const bar = ensureAnnotationActionBar();
    const entry = annotationsByElement.get(element);
    const noteCount = entry ? annotationUserInputs(entry.annotation).length : 0;
    annotationAnnotateButton.textContent =
      noteCount === 0 ? "✎ Annotate" : `✎ Annotate · ${noteCount}`;
    updateActionBarVerdict(element);
    bar.classList.add("show");
    placeAnnotationActionBar(element);
  }

  function handleTouchTap(event) {
    if (
      event.target.closest?.(
        ".annotation-action-bar, .annotation-marker, .annotation-editor, .annotation-preview",
      )
    ) {
      return;
    }

    closeAllAnnotationPreviews();

    // Page taps while the editor is open select phrases or work the page;
    // the editor closes through its own Cancel button.
    if (activeAnnotationEditor) {
      return;
    }

    if (event.target.closest?.("a[href]")) {
      setHighlightedAnnotationElement(null);
      hideAnnotationActionBar();
      return;
    }

    const candidate = annotationCandidateFromPoint(
      event.clientX,
      event.clientY,
    );
    setHighlightedAnnotationElement(candidate);
    if (candidate) {
      showAnnotationActionBar(candidate);
    } else {
      hideAnnotationActionBar();
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
      handleTouchTap(event);
    }
  });

  window.addEventListener(
    "scroll",
    () => {
      if (
        annotationActionBar?.classList.contains("show") &&
        highlightedAnnotationElement
      ) {
        placeAnnotationActionBar(highlightedAnnotationElement);
      }
    },
    { passive: true },
  );

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

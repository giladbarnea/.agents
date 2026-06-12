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
  const annotationsByElement = new Map();
  const annotationPreviewsByElement = new Map();
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

  function annotationMarkerForElement(element) {
    return annotationMarkerHost(element).querySelector(
      ":scope > .annotation-marker",
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
    const host = annotationMarkerHost(element);
    host.classList.add("annotation-marker-host");
    host.append(marker);
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
      if (element) {
        registerAnnotatedElement(element, selector, annotation);
      }
    });
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
    title.textContent =
      userInputs.length === 1 ? "1 annotation" : `${userInputs.length} annotations`;

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
  // click drops the caret exactly where the reader pressed. Save/Revert
  // surface only once the text differs from what's on disk; a save replaces
  // the note's text keyed by its original timestamp and goes through the same
  // write-then-read-back verification as a new annotation. Legacy notes
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

    actions.append(saveButton, revertButton);
    note.append(actions);

    const editedText = () => noteBody.innerText.trim();
    const refreshDirtyState = () => {
      note.classList.toggle("annotation-note-dirty", editedText() !== savedText);
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
        refreshDirtyState();
      } catch (error) {
        console.error(error);
        saveButton.classList.add("fail");
      } finally {
        saveButton.disabled = false;
        revertButton.disabled = false;
      }
    }

    noteBody.addEventListener("input", refreshDirtyState);
    saveButton.addEventListener("click", saveNoteEdit);
    revertButton.addEventListener("click", revertNoteEdit);
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

  // Reads the persisted annotations straight back to confirm the write landed,
  // matching on the note text and its unique-per-submit timestamp.
  async function annotationWasPersisted(selector, userInput, timestamp) {
    const response = await fetch(annotationEndpoint, {
      headers: { "Cache-Control": "no-cache" },
    });
    if (!response.ok) {
      throw new Error(`Annotation read-back failed (${response.status}).`);
    }

    const annotations = await response.json();
    return annotationUserInputs(annotations[selector] || {}).some(
      (item) =>
        annotationInputText(item) === userInput && item.timestamp === timestamp,
    );
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
      '<div class="annotation-editor-handle" data-annotation-ui="handle" aria-hidden="true"></div><div class="annotation-selection-preview" hidden><span class="annotation-selection-arrow" aria-hidden="true">↳</span><q class="annotation-selection-text"></q></div><textarea aria-label="Annotation text" autofocus></textarea><div class="annotation-status"></div>';
    document.body.appendChild(editor);
    positionAnnotationEditor(editor, element);
    requestAnimationFrame(() =>
      requestAnimationFrame(() => editor.classList.add("open")),
    );

    const textarea = editor.querySelector("textarea");
    const status = editor.querySelector(".annotation-status");
    const handle = editor.querySelector(".annotation-editor-handle");
    activeAnnotationEditor = editor;
    updateAnnotationSelectionPreview();
    textarea.focus();
    makeAnnotationEditorDraggable(editor, handle);

    textarea.addEventListener("keydown", async (event) => {
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

      const userInput = textarea.value.trim();
      if (!userInput) {
        return;
      }

      const annotatedElement = activeAnnotationElement;
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
    });
  }

  document.addEventListener("mousemove", (event) => {
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

  document.addEventListener("mouseup", () => {
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
      closeAnnotationEditor();
      closeAllAnnotationPreviews();
    }
  });

  window.addEventListener("resize", () => {
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
      if (highlightedAnnotationElement) {
        positionHoverOverlay(highlightedAnnotationElement, true);
      }
      positionAnnotationPreviews();
    },
    { passive: true },
  );

  loadAnnotations().catch((error) => console.warn(error));
})();

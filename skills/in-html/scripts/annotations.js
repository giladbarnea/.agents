(() => {
  const endpointMeta = document.querySelector(
    'meta[name="annotation-endpoint"]',
  );
  const annotationEndpoint =
    endpointMeta?.content || "http://127.0.0.1:8765/annotations";
  const annotationIgnoredSelector = [
    ".annotation-editor",
    "input",
    "textarea",
    "select",
    "[contenteditable]",
    "[data-annotation-ignore]",
  ].join(",");
  const annotationWholeSelector = "[data-annotate-whole], .step, .bar";
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

  function elementHasOwnText(element) {
    return Array.from(element.childNodes).some(
      (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim(),
    );
  }

  function normalizedElementText(element) {
    return element.textContent.trim().replace(/\s+/g, " ");
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

  function setHighlightedAnnotationElement(element) {
    if (highlightedAnnotationElement === element) {
      return;
    }
    if (highlightedAnnotationElement) {
      highlightedAnnotationElement.classList.remove("annotation-hover");
    }
    highlightedAnnotationElement = element;
    if (highlightedAnnotationElement) {
      highlightedAnnotationElement.classList.add("annotation-hover");
    }
  }

  function annotationPathSegment(element) {
    const tag = element.tagName.toLowerCase();
    const idSuffix = element.id ? `#${CSS.escape(element.id)}` : "";
    const classSuffix = Array.from(element.classList)
      .filter((name) => name !== "annotation-hover")
      .map((name) => `.${CSS.escape(name)}`)
      .join("");
    const siblings = Array.from(element.parentElement.children).filter(
      (child) => child.tagName === element.tagName,
    );
    const nth =
      !idSuffix && siblings.length > 1
        ? `:nth-of-type(${siblings.indexOf(element) + 1})`
        : "";
    return `${tag}${idSuffix}${classSuffix}${nth}`;
  }

  // Builds a unique, descriptive path from the nearest stable anchor
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

  function closeAnnotationEditor() {
    if (activeAnnotationEditor) {
      activeAnnotationEditor.remove();
    }
    activeAnnotationEditor = null;
    activeAnnotationElement = null;
    setActiveAnnotationSelection(null);
    setHighlightedAnnotationElement(null);
  }

  function showAnnotationStatus(statusElement, className, text) {
    statusElement.className = `annotation-status show ${className}`;
    statusElement.textContent = text;
  }

  async function writeAnnotation(element, userInput, specificallySelected) {
    const response = await fetch(annotationEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selector: selectorForAnnotationElement(element),
        text: normalizedElementText(element),
        userInput,
        specificallySelected,
      }),
    });

    if (response.ok) {
      return;
    }

    const details = await response.text();
    throw new Error(`Annotation write failed (${response.status}): ${details}`);
  }

  function clamp(value, min, max) {
    if (max < min) {
      return min;
    }
    return Math.min(Math.max(value, min), max);
  }

  function positionAnnotationEditor(editor, element) {
    const elementRect = element.getBoundingClientRect();
    const editorRect = editor.getBoundingClientRect();
    const targetCenterX = elementRect.left + elementRect.width / 2;
    const targetTop = elementRect.top + elementRect.height / 2;
    const left = clamp(
      targetCenterX,
      editorRect.width / 2,
      window.innerWidth - editorRect.width / 2,
    );
    const top = clamp(targetTop, 0, window.innerHeight - editorRect.height);
    editor.style.left = `${left}px`;
    editor.style.top = `${top}px`;
  }

  function openAnnotationEditor(element) {
    if (activeAnnotationEditor) {
      closeAnnotationEditor();
    }

    activeAnnotationElement = element;
    setHighlightedAnnotationElement(element);

    const editor = document.createElement("div");
    editor.className = "annotation-editor";
    editor.style.visibility = "hidden";
    editor.innerHTML =
      '<div class="annotation-selection-preview" hidden><span class="annotation-selection-arrow" aria-hidden="true">↳</span><q class="annotation-selection-text"></q></div><textarea aria-label="Annotation text" autofocus></textarea><div class="annotation-status"></div>';
    document.body.appendChild(editor);
    positionAnnotationEditor(editor, element);
    editor.style.visibility = "visible";

    const textarea = editor.querySelector("textarea");
    const status = editor.querySelector(".annotation-status");
    activeAnnotationEditor = editor;
    updateAnnotationSelectionPreview();
    textarea.focus();

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

      try {
        await writeAnnotation(
          activeAnnotationElement,
          userInput,
          activeAnnotationSelection,
        );
        editor.classList.add("inactive");
        textarea.disabled = true;
        showAnnotationStatus(status, "ok", "✓");
        window.setTimeout(closeAnnotationEditor, 500);
      } catch (error) {
        console.error(error);
        showAnnotationStatus(status, "fail", "✕");
        textarea.focus();
      }
    });
  }

  document.addEventListener("mousemove", (event) => {
    if (activeAnnotationEditor) {
      return;
    }
    setHighlightedAnnotationElement(
      annotationCandidateFromPoint(event.clientX, event.clientY),
    );
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
    "click",
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
    }
  });

  window.addEventListener("resize", () => {
    if (activeAnnotationEditor && activeAnnotationElement) {
      positionAnnotationEditor(activeAnnotationEditor, activeAnnotationElement);
    }
  });
})();

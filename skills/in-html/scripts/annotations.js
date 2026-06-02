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

  function elementHasOwnText(element) {
    return Array.from(element.childNodes).some(
      (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim(),
    );
  }

  function normalizedElementText(element) {
    return element.textContent.trim().replace(/\s+/g, " ");
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

  function selectorForAnnotationElement(element) {
    if (element.dataset.annotationId) {
      return `[data-annotation-id="${CSS.escape(element.dataset.annotationId)}"]`;
    }
    if (element.id) {
      return `#${CSS.escape(element.id)}`;
    }

    const parts = [];
    let current = element;
    while (current && current !== document.body) {
      if (current.dataset.annotationId) {
        parts.unshift(
          `[data-annotation-id="${CSS.escape(current.dataset.annotationId)}"]`,
        );
        break;
      }
      if (current.id) {
        parts.unshift(`#${CSS.escape(current.id)}`);
        break;
      }

      const tag = current.tagName.toLowerCase();
      const siblings = Array.from(current.parentElement.children).filter(
        (child) => child.tagName === current.tagName,
      );
      const nth =
        siblings.length > 1
          ? `:nth-of-type(${siblings.indexOf(current) + 1})`
          : "";
      parts.unshift(`${tag}${nth}`);
      current = current.parentElement;
    }

    if (
      !parts[0]?.startsWith("#") &&
      !parts[0]?.startsWith("[data-annotation-id=")
    ) {
      parts.unshift("body");
    }
    return parts.join(" > ");
  }

  function closeAnnotationEditor() {
    if (activeAnnotationEditor) {
      activeAnnotationEditor.remove();
    }
    activeAnnotationEditor = null;
    activeAnnotationElement = null;
    setHighlightedAnnotationElement(null);
  }

  function showAnnotationStatus(statusElement, className, text) {
    statusElement.className = `annotation-status show ${className}`;
    statusElement.textContent = text;
  }

  async function writeAnnotation(element, userInput) {
    const response = await fetch(annotationEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selector: selectorForAnnotationElement(element),
        text: normalizedElementText(element),
        userInput,
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
    closeAnnotationEditor();

    activeAnnotationElement = element;
    setHighlightedAnnotationElement(element);

    const editor = document.createElement("div");
    editor.className = "annotation-editor";
    editor.style.visibility = "hidden";
    editor.innerHTML =
      '<textarea aria-label="Annotation text" autofocus></textarea><div class="annotation-status"></div>';
    document.body.appendChild(editor);
    positionAnnotationEditor(editor, element);
    editor.style.visibility = "visible";

    const textarea = editor.querySelector("textarea");
    const status = editor.querySelector(".annotation-status");
    activeAnnotationEditor = editor;
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
        await writeAnnotation(activeAnnotationElement, userInput);
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

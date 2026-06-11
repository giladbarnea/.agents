(() => {
  function setupChipToggles() {
    document.querySelectorAll("[data-chip-toggle]").forEach((group) => {
      const scope = group.dataset.scope
        ? document.querySelector(group.dataset.scope)
        : document;

      function activeClassesForTarget(target) {
        return (
          target.dataset.activeClass ||
          (target.classList.contains("hl") ? "lit" : "show")
        )
          .split(/\s+/)
          .filter(Boolean);
      }

      function clearTargets() {
        group
          .querySelectorAll(".chip.q")
          .forEach((chip) => chip.classList.remove("active"));
        scope
          .querySelectorAll("[data-chip-target]")
          .forEach((target) =>
            target.classList.remove(...activeClassesForTarget(target)),
          );
      }

      group.addEventListener("click", (event) => {
        const chip = event.target.closest(".chip.q[data-key]");
        if (!chip || event.shiftKey) {
          return;
        }

        const wasActive = chip.classList.contains("active");
        clearTargets();
        if (wasActive) {
          return;
        }

        chip.classList.add("active");
        scope
          .querySelectorAll(
            `[data-chip-target~="${CSS.escape(chip.dataset.key)}"]`,
          )
          .forEach((target) =>
            target.classList.add(...activeClassesForTarget(target)),
          );
      });
    });
  }

  function setupBarCompileWidgets() {
    document.querySelectorAll("[data-bar-compile]").forEach((widget) => {
      const compiled = [];
      const compiledList = widget.querySelector(
        "[data-compiled-list], .compiledList",
      );
      const prefix = widget.dataset.compiledPrefix || "Compiled: ";

      function labelForBar(bar) {
        return (
          bar.dataset.label ||
          bar.dataset.axis ||
          bar.querySelector(".lab")?.textContent.trim() ||
          "axis"
        );
      }

      function renderCompiledList() {
        if (!compiledList) {
          return;
        }
        compiledList.innerHTML = `<span class="muted sans" style="font-size:.82rem;">${prefix}</span>${compiled
          .map((label) => `<span class="chip field">${label}</span>`)
          .join("")}`;
      }

      widget.querySelectorAll(".bar").forEach((bar) => {
        const label = labelForBar(bar);
        if (!bar.querySelector(".lab")) {
          bar.innerHTML += `<span class="lab">${label}</span>`;
        }
        if (!bar.querySelector(".star")) {
          bar.innerHTML += '<span class="star">compiled ✓</span>';
        }
        if (!bar.dataset.axis && !bar.dataset.label) {
          bar.style.cursor = "default";
          return;
        }

        bar.addEventListener("click", (event) => {
          if (event.shiftKey || bar.classList.contains("compiled")) {
            return;
          }
          bar.classList.add("compiled");
          compiled.push(label);
          renderCompiledList();
        });
      });
    });
  }

  // Every data-annotation-id doubles as a link target, so in-page references
  // (<a href="#stable-name">§7</a>) need no separate id bookkeeping. A link
  // whose target doesn't exist renders loud-red instead of failing silently.
  function setupCrossReferences() {
    document.querySelectorAll("[data-annotation-id]").forEach((element) => {
      if (!element.id) {
        element.id = element.dataset.annotationId;
      }
    });
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
      const targetId = decodeURIComponent(anchor.getAttribute("href").slice(1));
      if (targetId && !document.getElementById(targetId)) {
        anchor.classList.add("refbroken");
        console.warn(`Broken cross-reference: #${targetId}`);
      }
    });

    // Following a reference is a context switch; the return pill is the way
    // back. Each jump pushes the departure scroll position, so chained
    // references unwind in order. Returning clears the hash so re-clicking
    // the same reference jumps (and :target-flashes) again.
    const returnStack = [];
    const returnButton = document.createElement("button");
    returnButton.type = "button";
    returnButton.className = "crossref-return";
    returnButton.dataset.annotationUi = "crossref-return";
    returnButton.textContent = "↩ Back to where you were";
    returnButton.addEventListener("click", () => {
      const departureScrollY = returnStack.pop();
      history.replaceState(null, "", location.pathname + location.search);
      window.scrollTo({ top: departureScrollY, behavior: "smooth" });
      if (returnStack.length === 0) {
        returnButton.classList.remove("show");
      }
    });
    document.body.append(returnButton);

    document.addEventListener("click", (event) => {
      const anchor = event.target.closest('a[href^="#"]');
      if (!anchor || anchor.classList.contains("refbroken")) {
        return;
      }
      returnStack.push(window.scrollY);
      returnButton.classList.add("show");
    });
  }

  setupChipToggles();
  setupBarCompileWidgets();
  setupCrossReferences();
})();

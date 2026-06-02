(() => {
  document.documentElement.classList.add("js");

  function setupSegmentedControls() {
    document.querySelectorAll("[data-segmented]").forEach((segmented) => {
      const groupName = segmented.dataset.segmented || segmented.dataset.target;
      const panels = groupName
        ? Array.from(
            document.querySelectorAll(
              `[data-segment-panels="${CSS.escape(groupName)}"] [data-panel]`,
            ),
          )
        : [];
      const buttons = Array.from(segmented.querySelectorAll("[data-panel]"));
      if (!buttons.length) {
        return;
      }

      function activate(button) {
        const key = button.dataset.panel;
        buttons.forEach((candidate) =>
          candidate.classList.toggle("on", candidate === button),
        );
        panels.forEach((panel) => {
          panel.hidden = panel.dataset.panel !== key;
        });
      }

      buttons.forEach((button) => {
        button.addEventListener("click", (event) => {
          if (event.shiftKey) {
            return;
          }
          activate(button);
        });
      });

      activate(
        buttons.find((button) => button.classList.contains("on")) || buttons[0],
      );
    });
  }

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

  function setupPipelineSteps() {
    document.querySelectorAll(".pipe .step").forEach((step) => {
      const detail = step.querySelector(".d");
      if (detail && step.dataset.d && !detail.textContent.trim()) {
        detail.textContent = step.dataset.d;
      }
      step.addEventListener("click", (event) => {
        if (event.shiftKey) {
          return;
        }
        step.classList.toggle("open");
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

  function setupDisclosureBlocks() {
    document.querySelectorAll(".disclose .head").forEach((head) => {
      head.addEventListener("click", (event) => {
        if (event.shiftKey) {
          return;
        }
        head.parentElement.classList.toggle("open");
      });
    });
  }

  setupSegmentedControls();
  setupChipToggles();
  setupPipelineSteps();
  setupBarCompileWidgets();
  setupDisclosureBlocks();
})();

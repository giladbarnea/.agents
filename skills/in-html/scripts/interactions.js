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

  // ── Docs chrome ─────────────────────────────────────────────────────────
  // A Mintlify-style three-pane frame — top bar, left section-nav, right "On
  // this page" TOC — built from the page's own headings so authors add no
  // markup. Pure layer-2 enhancement: with JS off none of this exists and the
  // page is the plain single column. Everything keys off the `.has-chrome`
  // class set on <html>, and the right TOC defers to the annotation side panel
  // via the body.annotation-panel-open class annotations.js already toggles.

  const tagHues = [
    ["blue", "Blue"],
    ["amber", "Amber"],
    ["green", "Green"],
    ["red", "Red"],
  ];

  function slugify(text) {
    return text
      .toLowerCase()
      .replace(/[^\p{Letter}\p{Number}]+/gu, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 48);
  }

  // The heading text without the leading "§N · label" eyebrow (the .n span),
  // and the eyebrow's own number/label, returned separately for the rails.
  function headingParts(heading) {
    const eyebrow = heading.querySelector(".n");
    const clone = heading.cloneNode(true);
    clone.querySelectorAll(".n, [data-annotation-ui]").forEach((n) => n.remove());
    return {
      label: clone.textContent.trim().replace(/\s+/g, " "),
      eyebrow: eyebrow ? eyebrow.textContent.trim().replace(/\s+/g, " ") : "",
    };
  }

  function ensureHeadingId(heading, used) {
    if (heading.id) {
      used.add(heading.id);
      return heading.id;
    }
    const base = slugify(headingParts(heading).label) || "section";
    let id = base;
    let suffix = 2;
    while (used.has(id) || document.getElementById(id)) {
      id = `${base}-${suffix++}`;
    }
    heading.id = id;
    used.add(id);
    return id;
  }

  function buildChromeFrame(content, headings) {
    const root = document.documentElement;
    root.classList.add("has-chrome");

    const titleText =
      content.querySelector("h1")?.textContent.trim() ||
      document.title ||
      "Contents";

    const bar = document.createElement("header");
    bar.className = "page-bar";
    bar.dataset.annotationIgnore = "";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "page-bar-toggle";
    toggle.setAttribute("aria-label", "Toggle navigation");
    toggle.textContent = "☰";

    const title = document.createElement("div");
    title.className = "page-bar-title";
    title.innerHTML = `<span class="page-bar-dot">◆</span>${titleText.replace(
      /</g,
      "&lt;",
    )}`;

    const progress = document.createElement("div");
    progress.className = "page-bar-progress";
    progress.dataset.annotationIgnore = "";

    bar.append(toggle, title, progress);

    const nav = document.createElement("nav");
    nav.className = "page-nav";
    nav.dataset.annotationIgnore = "";
    nav.setAttribute("aria-label", "Sections");
    const navEyebrow = document.createElement("div");
    navEyebrow.className = "page-nav-eyebrow";
    navEyebrow.textContent = "Sections";
    nav.append(navEyebrow);

    const toc = document.createElement("aside");
    toc.className = "page-toc";
    toc.dataset.annotationIgnore = "";
    toc.setAttribute("aria-label", "On this page");
    const tocEyebrow = document.createElement("div");
    tocEyebrow.className = "page-toc-eyebrow";
    tocEyebrow.textContent = "On this page";
    toc.append(tocEyebrow);

    const backdrop = document.createElement("div");
    backdrop.className = "page-nav-backdrop";
    backdrop.dataset.annotationIgnore = "";

    const entries = headings.map((heading, index) => {
      const { label, eyebrow } = headingParts(heading);
      const navLink = document.createElement("a");
      navLink.href = `#${heading.id}`;
      navLink.innerHTML = `${
        eyebrow ? `<span class="page-nav-n">${String(index + 1).padStart(2, "0")}</span>` : ""
      }${label.replace(/</g, "&lt;")}`;
      nav.append(navLink);

      const tocLink = document.createElement("a");
      tocLink.href = `#${heading.id}`;
      tocLink.textContent = label;
      toc.append(tocLink);

      return { heading, navLink, tocLink };
    });

    document.body.append(bar, nav, toc, backdrop);

    // Nav drawer (narrow widths): the toggle opens it, the backdrop or any nav
    // link closes it.
    const closeNav = () => document.body.classList.remove("page-nav-open");
    toggle.addEventListener("click", () =>
      document.body.classList.toggle("page-nav-open"),
    );
    backdrop.addEventListener("click", closeNav);
    nav.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        closeNav();
      }
    });

    return { progress, entries, legendHost: toc };
  }

  // Scroll-spy: the section whose heading most recently crossed below the top
  // bar is "current" in both rails. A passive scroll handler keeps it cheap;
  // requestAnimationFrame coalesces bursts.
  function setupScrollSpy(entries, progress) {
    let queued = false;
    const topbar = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--topbar-h"),
    );
    const triggerLine = (Number.isFinite(topbar) ? topbar * 17 : 56) + 24;

    function update() {
      queued = false;
      let currentIndex = 0;
      entries.forEach((entry, index) => {
        if (entry.heading.getBoundingClientRect().top <= triggerLine) {
          currentIndex = index;
        }
      });
      entries.forEach((entry, index) => {
        const isCurrent = index === currentIndex;
        entry.navLink.classList.toggle("current", isCurrent);
        entry.tocLink.classList.toggle("current", isCurrent);
      });
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      progress.style.width = `${
        scrollable > 0 ? Math.min(100, (window.scrollY / scrollable) * 100) : 0
      }%`;
    }

    function schedule() {
      if (queued) {
        return;
      }
      queued = true;
      requestAnimationFrame(update);
    }

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    update();
  }

  // Controlled-tag legend: one chip per distinct .tag hue on the page. Clicking
  // a chip dims the content column and lights every matching .tag (and the line
  // that carries it) — the chip-toggle engine's idea, scoped to the whole page.
  function setupLegend(content, legendHost) {
    const present = tagHues.filter(
      ([hue]) => content.querySelector(`.tag.${hue}`),
    );
    if (present.length < 2) {
      return;
    }

    const legend = document.createElement("div");
    legend.className = "page-legend";
    legend.dataset.annotationIgnore = "";
    const eyebrow = document.createElement("div");
    eyebrow.className = "page-legend-eyebrow";
    eyebrow.textContent = "Tags";
    legend.append(eyebrow);

    let activeHue = null;

    function clearLegend() {
      activeHue = null;
      document.body.classList.remove("legend-active");
      content
        .querySelectorAll(".legend-lit")
        .forEach((node) => node.classList.remove("legend-lit"));
      content
        .querySelectorAll(".legend-lit-host")
        .forEach((node) => node.classList.remove("legend-lit-host"));
      legend
        .querySelectorAll(".page-legend-chip")
        .forEach((chip) => chip.classList.remove("active"));
    }

    function lightHue(hue, chip) {
      clearLegend();
      activeHue = hue;
      document.body.classList.add("legend-active");
      chip.classList.add("active");
      content.querySelectorAll(`.tag.${hue}`).forEach((tag) => {
        tag.classList.add("legend-lit");
        // Pop the whole line/box the tag sits in, not just the pill.
        const host = tag.closest(
          "p, li, h2, h3, h4, .card, .pane, .record, .relrow, .cnode, .tnode, .step, .qa, .rec-eyebrow",
        );
        if (host) {
          host.classList.add("legend-lit-host");
        }
      });
    }

    present.forEach(([hue, name]) => {
      const count = content.querySelectorAll(`.tag.${hue}`).length;
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "page-legend-chip";
      chip.innerHTML = `<span class="page-legend-swatch ${hue}"></span>${name}<span class="page-legend-count">${count}</span>`;
      chip.addEventListener("click", () => {
        if (activeHue === hue) {
          clearLegend();
        } else {
          lightHue(hue, chip);
        }
      });
      legend.append(chip);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && activeHue) {
        clearLegend();
      }
    });

    legendHost.append(legend);
  }

  function setupChrome() {
    const content = document.getElementById("content");
    if (!content) {
      return;
    }
    const headings = Array.from(content.querySelectorAll(":scope > h2"));
    if (headings.length < 2) {
      return;
    }
    const used = new Set();
    headings.forEach((heading) => ensureHeadingId(heading, used));

    const { progress, entries, legendHost } = buildChromeFrame(content, headings);
    setupScrollSpy(entries, progress);
    setupLegend(content, legendHost);
  }

  // Copyable code blocks: every <pre> gets a Copy button revealed on hover
  // (always shown on touch). Confirms in place on success.
  function setupCodeCopy() {
    document.querySelectorAll("pre").forEach((pre) => {
      if (pre.closest(".code-copyable") || pre.dataset.noCopy !== undefined) {
        return;
      }
      pre.classList.add("code-copyable");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "code-copy";
      button.dataset.annotationIgnore = "";
      button.textContent = "Copy";
      button.addEventListener("click", async () => {
        const source = pre.querySelector("code") || pre;
        try {
          await navigator.clipboard.writeText(source.innerText);
          button.textContent = "Copied";
          button.classList.add("copied");
          window.setTimeout(() => {
            button.textContent = "Copy";
            button.classList.remove("copied");
          }, 1400);
        } catch (error) {
          console.warn("Copy failed", error);
        }
      });
      pre.append(button);
    });
  }

  // Glossary terms have no hover on touch, so a tap toggles the tip open (the
  // CSS reveals the same .tip surface on .term-open). Behavior follows the
  // event — only touch taps run this; fine pointers keep the CSS :hover path.
  function setupGlossaryTouch() {
    document.addEventListener("pointerup", (event) => {
      if (event.pointerType !== "touch") {
        return;
      }
      const term = event.target.closest?.(".term");
      document.querySelectorAll(".term.term-open").forEach((open) => {
        if (open !== term) {
          open.classList.remove("term-open");
        }
      });
      if (term) {
        term.classList.toggle("term-open");
      }
    });
  }

  setupChipToggles();
  setupBarCompileWidgets();
  setupCrossReferences();
  setupChrome();
  setupCodeCopy();
  setupGlossaryTouch();
})();

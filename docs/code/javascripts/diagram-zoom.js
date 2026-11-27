/* Zoom and pan for the Mermaid diagrams of the code docs (mkdocs.yml, extra_javascript).
 *
 * Material renders each diagram into a closed shadow root inside a new <div class="mermaid">,
 * which replaces the <pre class="mermaid"> once Mermaid has loaded. The SVG cannot be reached
 * from outside, so this script waits for each rendered div, wraps it in a viewport and moves the
 * wrapper with a CSS transform; the SVG stays sharp at any scale.
 *
 * Controls, in the toolbar at the top right of each diagram: zoom in, zoom out, reset, full
 * screen. Ctrl/Cmd + wheel (or a trackpad pinch) zooms at the pointer; in full screen the plain
 * wheel does. Drag pans a zoomed diagram; double-click resets it. Esc leaves full screen.
 */
(() => {
  "use strict";

  const MIN_SCALE = 0.2;
  const MAX_SCALE = 10;
  const STEP = 1.25;
  const ICONS = {
    zoomIn: "M12 5v14M5 12h14",
    zoomOut: "M5 12h14",
    reset: "M4 12a8 8 0 1 0 2.34-5.66M4 4v5h5",
    fullscreen: "M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5",
  };

  function button(label, icon, onClick) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "diagram-zoom__button";
    b.title = label;
    b.setAttribute("aria-label", label);
    b.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${icon}"/></svg>`;
    b.addEventListener("click", (event) => {
      event.stopPropagation();
      onClick();
    });
    return b;
  }

  function enhance(diagram) {
    const viewport = document.createElement("div");
    viewport.className = "diagram-zoom";
    const stage = document.createElement("div");
    stage.className = "diagram-zoom__stage";
    diagram.replaceWith(viewport); // moving the div keeps its shadow root
    stage.append(diagram);
    viewport.append(stage);

    let scale = 1;
    let x = 0;
    let y = 0;
    const isFullscreen = () => document.fullscreenElement === viewport;
    const apply = () => {
      stage.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
      viewport.classList.toggle("is-moved", scale !== 1 || x !== 0 || y !== 0);
    };
    // Zoom by `factor` keeping the point (cx, cy) of the viewport fixed (transform-origin 0 0).
    const zoomAt = (factor, cx, cy) => {
      const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
      x = cx - (next / scale) * (cx - x);
      y = cy - (next / scale) * (cy - y);
      scale = next;
      apply();
    };
    const zoomAtCentre = (factor) => {
      const r = viewport.getBoundingClientRect();
      zoomAt(factor, r.width / 2, r.height / 2);
    };
    const reset = () => {
      scale = 1;
      x = 0;
      y = 0;
      apply();
    };
    // Full screen: shrink a diagram taller than the screen so that all of it is visible, centred.
    const fit = () => {
      const r = viewport.getBoundingClientRect();
      const h = diagram.offsetHeight || 1;
      scale = Math.min(1, (0.95 * r.height) / h);
      x = (r.width * (1 - scale)) / 2;
      y = (r.height - h * scale) / 2;
      apply();
    };
    const home = () => (isFullscreen() ? fit() : reset());
    const toggleFullscreen = () => {
      if (isFullscreen()) {
        document.exitFullscreen();
      } else if (viewport.requestFullscreen) {
        viewport.requestFullscreen().catch(() => {});
      }
    };

    const toolbar = document.createElement("div");
    toolbar.className = "diagram-zoom__toolbar";
    toolbar.append(
      button("Zoom in (Ctrl + wheel)", ICONS.zoomIn, () => zoomAtCentre(STEP)),
      button("Zoom out (Ctrl + wheel)", ICONS.zoomOut, () => zoomAtCentre(1 / STEP)),
      button("Reset (double-click)", ICONS.reset, home),
      button("Full screen (Esc to leave)", ICONS.fullscreen, toggleFullscreen),
    );
    viewport.append(toolbar);

    viewport.addEventListener(
      "wheel",
      (event) => {
        if (!(event.ctrlKey || event.metaKey || isFullscreen())) return; // let the page scroll
        event.preventDefault();
        const r = viewport.getBoundingClientRect();
        const pixels = event.deltaMode === 1 ? event.deltaY * 33 : event.deltaY; // lines -> px
        const delta = Math.max(-200, Math.min(200, pixels));
        zoomAt(Math.exp(-delta * 0.002), event.clientX - r.left, event.clientY - r.top);
      },
      { passive: false },
    );

    let drag = null;
    viewport.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target.closest(".diagram-zoom__toolbar")) return;
      if (scale === 1 && x === 0 && y === 0 && !isFullscreen()) return; // nothing to pan
      drag = { id: event.pointerId, dx: event.clientX - x, dy: event.clientY - y };
      viewport.setPointerCapture(event.pointerId);
      viewport.classList.add("is-dragging");
      event.preventDefault();
    });
    viewport.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      x = event.clientX - drag.dx;
      y = event.clientY - drag.dy;
      apply();
    });
    const endDrag = (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      drag = null;
      viewport.classList.remove("is-dragging");
    };
    viewport.addEventListener("pointerup", endDrag);
    viewport.addEventListener("pointercancel", endDrag);
    viewport.addEventListener("dblclick", (event) => {
      if (!event.target.closest(".diagram-zoom__toolbar")) home();
    });
    viewport.addEventListener("fullscreenchange", () => requestAnimationFrame(home));
  }

  const isPending = (node) => node.matches("div.mermaid") && !node.closest(".diagram-zoom");
  const enhanceWithin = (root) => {
    if (root.nodeType !== Node.ELEMENT_NODE && root !== document) return;
    if (root !== document && isPending(root)) enhance(root);
    else root.querySelectorAll("div.mermaid").forEach((d) => isPending(d) && enhance(d));
  };
  new MutationObserver((records) => {
    for (const record of records) record.addedNodes.forEach(enhanceWithin);
  }).observe(document.body, { childList: true, subtree: true });
  enhanceWithin(document);
})();

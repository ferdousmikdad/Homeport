// Homeport website — small progressive enhancements (the page works without JS).
(function () {
  // Feature tabs (click + arrow keys)
  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
  function select(tab) {
    tabs.forEach((t) => {
      const on = t === tab;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(t.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
    });
  }
  tabs.forEach((tab, i) => {
    tab.tabIndex = tab.getAttribute("aria-selected") === "true" ? 0 : -1;
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (e) => {
      const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      const next = tabs[(i + d + tabs.length) % tabs.length];
      select(next);
      next.focus();
    });
  });

  // Copy buttons
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const src = document.querySelector(btn.getAttribute("data-copy"));
      if (!src) return;
      try {
        await navigator.clipboard.writeText(src.textContent.trim());
        btn.textContent = "Copied";
        setTimeout(() => (btn.textContent = "Copy"), 1600);
      } catch (e) {
        /* clipboard unavailable — the text is still selectable */
      }
    });
  });

  // GitHub star count (best effort; hidden when unavailable)
  const starEls = document.querySelectorAll("[data-stars]");
  if (starEls.length) {
    fetch("https://api.github.com/repos/ferdousmikdad/Homeport", { headers: { Accept: "application/vnd.github+json" } })
      .then((r) => (r.ok ? r.json() : null))
      .then((repo) => {
        if (!repo || typeof repo.stargazers_count !== "number" || repo.stargazers_count < 1) return;
        const n = repo.stargazers_count;
        const text = n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(n);
        starEls.forEach((el) => (el.textContent = "★ " + text));
      })
      .catch(() => {});
  }

  // Decorative QR pattern for the phone-preview visual
  const qr = document.getElementById("qr");
  if (qr) {
    const size = 11;
    const finder = (x, y) => {
      const inBox = (ox, oy) => x >= ox && x < ox + 3 && y >= oy && y < oy + 3;
      return inBox(0, 0) || inBox(size - 3, 0) || inBox(0, size - 3);
    };
    let seed = 7;
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const cell = document.createElement("i");
        seed = (seed * 9301 + 49297) % 233280;
        const on = finder(x, y) || seed / 233280 > 0.52;
        if (!on) cell.className = "o";
        qr.appendChild(cell);
      }
    }
  }
})();

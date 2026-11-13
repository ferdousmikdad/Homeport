// Homeport website — small progressive enhancements (the page works without JS).
(function () {
  // Theme toggle (dark / light). The inline head script sets the initial theme.
  (function theme() {
    const root = document.documentElement;
    const meta = document.querySelector('meta[name="theme-color"]');
    const buttons = document.querySelectorAll("[data-theme-toggle]");
    const apply = (t) => {
      root.setAttribute("data-theme", t);
      if (meta) meta.setAttribute("content", t === "light" ? "#fafafa" : "#070707");
      buttons.forEach((b) => b.setAttribute("aria-label", t === "light" ? "Switch to dark mode" : "Switch to light mode"));
    };
    apply(root.getAttribute("data-theme") === "light" ? "light" : "dark");
    buttons.forEach((b) => b.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      try { localStorage.setItem("theme", next); } catch (e) {}
      apply(next);
    }));
    // Follow system changes until the visitor picks a theme themselves.
    if (window.matchMedia) {
      const mq = matchMedia("(prefers-color-scheme: light)");
      const onChange = () => {
        let saved = null;
        try { saved = localStorage.getItem("theme"); } catch (e) {}
        if (saved !== "light" && saved !== "dark") apply(mq.matches ? "light" : "dark");
      };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
    }
  })();

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

  // ---- Smart download button: pick the installer for this device ----
  (function smartDownload() {
    const base = "https://github.com/ferdousmikdad/Homeport/releases/latest/download/";
    const files = {
      mac: { file: "Homeport-mac-arm64.dmg", label: "Download for macOS" },
      win: { file: "Homeport-Setup-x64.exe", label: "Download for Windows" },
      linux: { file: "Homeport-x86_64.AppImage", label: "Download for Linux" },
    };
    const ua = navigator.userAgent || "";
    const plat = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
    const touchMac = /Mac/i.test(plat) && navigator.maxTouchPoints > 1; // iPad pretends to be a Mac
    let os = "other";
    if (/Android|iPhone|iPad|iPod/i.test(ua) || touchMac) os = "mobile";
    else if (/Win/i.test(plat) || /Windows/i.test(ua)) os = "win";
    else if (/Mac/i.test(plat) || /Mac OS X/i.test(ua)) os = "mac";
    else if (/Linux|X11|CrOS/i.test(plat + " " + ua)) os = "linux";

    const primary = document.getElementById("dl-primary");
    const label = document.getElementById("dl-label");
    const sub = document.getElementById("dl-sub");
    const smart = document.querySelectorAll("[data-dl-smart]");
    if (files[os]) {
      const href = base + files[os].file;
      // the big download button is only on the home page
      if (primary) primary.href = href;
      if (label) label.textContent = files[os].label;
      smart.forEach((a) => { a.href = href; a.textContent = files[os].label; });
      document.querySelectorAll('.dl-other a[data-os="' + os + '"]').forEach((a) => a.classList.add("current"));
    } else if (os === "mobile") {
      if (label) label.textContent = "View on GitHub";
      if (primary) primary.href = "https://github.com/ferdousmikdad/Homeport";
      if (sub) sub.textContent = "Homeport runs on your computer — open this page on macOS, Windows or Linux to download.";
    }
    // Terminal tab follows the OS
    selectTerm(os === "win" ? "win" : "unix");
    // Intel Macs: the .dmg is for Apple Silicon — point them at the terminal command.
    if (os === "mac" && navigator.userAgentData && navigator.userAgentData.getHighEntropyValues) {
      navigator.userAgentData.getHighEntropyValues(["architecture"]).then((v) => {
        if (v && v.architecture === "x86" && sub) {
          sub.textContent = "Intel Mac? Use the terminal command below — it works on every Mac.";
        }
      }).catch(() => {});
    }
  })();

  function selectTerm(which) {
    document.querySelectorAll(".term-tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.term === which)));
    document.querySelectorAll("[data-term-panel]").forEach((p) => (p.hidden = p.dataset.termPanel !== which));
  }
  document.querySelectorAll(".term-tabs button").forEach((b) => b.addEventListener("click", () => selectTerm(b.dataset.term)));

  // ---- Line illustrations for the "And more" cards (drawn, not images) ----
  (function lineArt() {
    const NS = "http://www.w3.org/2000/svg";
    const W = 400, H = 220;
    const mk = (svg, tag, attrs) => {
      const e = document.createElementNS(NS, tag);
      for (const k in attrs) e.setAttribute(k, attrs[k]);
      svg.appendChild(e);
      return e;
    };
    const line = (svg, x1, y1, x2, y2, cls) => mk(svg, "line", { x1, y1, x2, y2, class: "ln" + (cls ? " " + cls : "") });
    const R = (a) => (a * Math.PI) / 180;
    const art = {
      // Discovery: rays fanning out from a point, like a scan
      burst(svg) {
        const cx = 200, cy = 196;
        for (let i = 0; i <= 18; i++) {
          const a = R(180 + (i * 180) / 18);
          const r1 = 26 + (i % 3) * 6, r2 = 70 + ((i * 37) % 60);
          line(svg, cx + Math.cos(a) * r1, cy + Math.sin(a) * r1, cx + Math.cos(a) * r2, cy + Math.sin(a) * r2, i % 4 === 1 ? "dim" : "");
        }
      },
      // Workspaces: apps that start one after another
      chain(svg) {
        const xs = [70, 155, 245, 330];
        xs.forEach((x, i) => {
          if (i) line(svg, xs[i - 1] + 16, 110, x - 16, 110, i === 3 ? "dim" : "");
          mk(svg, "circle", { cx: x, cy: 110, r: 14, class: "ln" + (i === 3 ? " dim" : "") });
          if (i < 3) mk(svg, "circle", { cx: x, cy: 110, r: 4, class: "dot" });
          for (let k = 0; k < 3; k++) line(svg, x - 10 + k * 10, 140, x - 10 + k * 10, 150 + ((i + k) % 3) * 8, "dim");
        });
      },
      // Git: a trunk with branches
      branches(svg) {
        line(svg, 40, 120, 360, 120);
        [[90, 60, 200], [150, 175, 270], [230, 70, 330]].forEach(([x, y, x2], i) => {
          mk(svg, "path", { d: `M${x} 120 C ${x + 30} 120, ${x + 20} ${y}, ${x + 55} ${y} L ${x2} ${y}`, class: "ln" + (i === 1 ? " dim" : "") });
          mk(svg, "circle", { cx: x2, cy: y, r: 4, class: "dot" + (i === 1 ? " dim" : "") });
        });
        [40, 90, 150, 230, 300, 360].forEach((x) => mk(svg, "circle", { cx: x, cy: 120, r: 4, class: "dot" }));
      },
      // Logs: lines of output
      bars(svg) {
        for (let i = 0; i < 9; i++) {
          const y = 40 + i * 18, len = 60 + ((i * 53) % 200);
          line(svg, 60, y, 60 + 18, y, "dim");
          line(svg, 90, y, 90 + len, y, i === 6 ? "" : i % 3 ? "dim" : "");
        }
      },
      // Auto-restart: circles coming back around
      rings(svg) {
        for (let i = 0; i < 6; i++) {
          const r = 22 + i * 14, gap = 20 + i * 6;
          const a1 = R(-90 + gap), a2 = R(250);
          const d = `M ${200 + r * Math.cos(a1)} ${110 + r * Math.sin(a1)} A ${r} ${r} 0 1 1 ${200 + r * Math.cos(a2)} ${110 + r * Math.sin(a2)}`;
          mk(svg, "path", { d, class: "ln" + (i % 2 ? " dim" : ""), "stroke-dasharray": i % 3 === 2 ? "3 6" : "" });
        }
      },
      // CPU & memory: a live trace
      pulse(svg) {
        let d = "M 30 140";
        for (let x = 30; x <= 370; x += 10) {
          const y = 140 - (Math.sin(x / 23) * 18 + Math.sin(x / 7) * 6 + (x > 200 && x < 230 ? -50 : 0));
          d += ` L ${x} ${y.toFixed(1)}`;
        }
        mk(svg, "path", { d, class: "ln" });
        for (let x = 30; x <= 370; x += 20) line(svg, x, 180, x, 184, "dim");
        line(svg, 30, 180, 370, 180, "dim");
      },
    };
    document.querySelectorAll("[data-art]").forEach((box) => {
      const draw = art[box.dataset.art];
      if (!draw) return;
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
      svg.setAttribute("aria-hidden", "true");
      draw(svg);
      box.appendChild(svg);
    });
    // Fade the drawings in as they scroll into view.
    const tiles = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      tiles.forEach((t) => t.classList.add("in"));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.25 });
    tiles.forEach((t) => io.observe(t));
  })();

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

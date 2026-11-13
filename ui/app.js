"use strict";

/*
 * Homeport — front-end.
 *
 * All API calls are relative unless ?api=http://host:port overrides the base.
 * User-provided strings are always written with textContent / value; innerHTML
 * is only used for the static SVG icons defined below.
 */
(function () {
  const params = new URLSearchParams(window.location.search);
  const API_BASE = (params.get("api") || "").replace(/\/+$/, "");

  const ICONS = {
    comment: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"><path d="M12 4a8 8 0 0 1 0 16H4v-8a8 8 0 0 1 8-8z"/></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/></svg>',
    grip: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.6"/><circle cx="15" cy="6" r="1.6"/><circle cx="9" cy="12" r="1.6"/><circle cx="15" cy="12" r="1.6"/><circle cx="9" cy="18" r="1.6"/><circle cx="15" cy="18" r="1.6"/></svg>',
    more: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg>',
    dots: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="8.5" cy="12" r="1.9"/><circle cx="15.5" cy="12" r="1.9"/></svg>',
    play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.4-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>',
    stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6.5" y="6.5" width="11" height="11" rx="2.2"/></svg>',
    share: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
    logs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 7h14M5 12h14M5 17h9"/></svg>',
    open: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/></svg>',
    restart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
    edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4z"/></svg>',
    terminal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="m7.5 9.5 3 2.5-3 2.5M12.5 15h4"/></svg>',
    phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M11 18h2"/></svg>',
    git: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="5.5" r="2"/><circle cx="6" cy="18.5" r="2"/><circle cx="18" cy="8.5" r="2"/><path d="M6 7.5v9M18 10.5c0 4-4 4-10.5 6"/></svg>',
    why: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M9.8 9.5a2.3 2.3 0 1 1 3.1 2.2c-.6.3-.9.8-.9 1.4v.4M12 16.6v.1"/></svg>',
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="8.5" y="8.5" width="11" height="11" rx="2.2"/><path d="M15.5 8.5V6.7a2.2 2.2 0 0 0-2.2-2.2H6.7a2.2 2.2 0 0 0-2.2 2.2v6.6a2.2 2.2 0 0 0 2.2 2.2h1.8"/></svg>',
    filter: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5h16l-6.2 7.3v5.2l-3.6 1.8v-7z"/></svg>',
    sidebar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="4.5" width="17" height="15" rx="3"/><path d="M9.5 4.5v15"/></svg>',
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11.5a7.5 7.5 0 0 1-11 6.6L4 19.5l1.4-4.6A7.5 7.5 0 1 1 20 11.5z"/></svg>',
    discover: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><circle cx="12" cy="13.5" r="2.6"/><path d="m14 15.5 1.8 1.8"/></svg>',
    layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="m12 3.5 8.5 4.5-8.5 4.5L3.5 8z"/><path d="m3.5 12 8.5 4.5 8.5-4.5M3.5 16l8.5 4.5 8.5-4.5"/></svg>',
    grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/></svg>',
    list: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>',
    sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  };

  const UNCATEGORIZED = "\u0000none";
  const APP_COLORS = [["", "No color"], ["red", "Red"], ["green", "Green"], ["blue", "Blue"]];

  const $ = (id) => document.getElementById(id);
  const els = {
    grid: $("grid"),
    empty: $("empty"),
    emptyTitle: $("empty-title"),
    emptyText: $("empty-text"),
    summary: $("summary"),
    conn: $("conn"),
    connText: $("conn-text"),
    btnTheme: $("btn-theme"),
    btnBulk: $("btn-bulk"),
    bulkMenu: $("bulk-menu"),
    btnStartAll: $("btn-start-all"),
    btnStopAll: $("btn-stop-all"),
    btnTerminateAll: $("btn-terminate-all"),
    btnAdd: $("btn-add"),

    searchInput: $("search-input"),
    statusBtns: document.querySelectorAll("#status-seg button"),
    countAll: $("count-all"),
    countRunning: $("count-running"),
    countStopped: $("count-stopped"),
    countCrashed: $("count-crashed"),
    categoryFilter: $("category-filter"),
    catNav: $("cat-nav"),
    sortSelect: $("sort-select"),
    btnGroup: $("btn-group"),
    viewBtns: document.querySelectorAll("#view-seg button"),

    drawer: $("drawer"),
    logsTitle: $("logs-title"),
    logsSub: $("logs-sub"),
    logsBody: $("logs-body"),
    logsErrorBanner: $("logs-error-banner"),
    logsFilter: $("logs-filter"),
    logsAutoscroll: $("logs-autoscroll"),
    logsWrap: $("logs-wrap"),
    logsClear: $("logs-clear"),
    logsDownload: $("logs-download"),
    logsClose: $("logs-close"),

    backdrop: $("backdrop"),
    form: $("app-form"),
    modalTitle: $("modal-title"),
    fId: $("f-id"),
    fName: $("f-name"),
    fCategory: $("f-category"),
    categoryList: $("category-list"),
    fDescription: $("f-description"),
    modalMetaBox: $("modal-meta-box"),
    fCreatedAt: $("f-created-at"),
    fUpdatedAt: $("f-updated-at"),
    fPath: $("f-path"),
    fPathHint: $("f-path-hint"),
    btnBrowse: $("btn-browse"),
    fCommand: $("f-command"),
    fPort: $("f-port"),
    fHealth: $("f-health"),
    envRows: $("env-rows"),
    btnAddEnv: $("btn-add-env"),
    fAuto: $("f-auto"),
    fAutostart: $("f-autostart"),
    fNotify: $("f-notify"),
    modalClose: $("modal-close"),
    modalCancel: $("modal-cancel"),
    modalSubmit: $("modal-submit"),

    browseBackdrop: $("browse-backdrop"),
    browseCrumbs: $("browse-crumbs"),
    browseList: $("browse-list"),
    browseSelectedPath: $("browse-selected-path"),
    browseSelect: $("browse-select"),
    browseCancel: $("browse-cancel"),
    browseClose: $("browse-close"),

    confirmBackdrop: $("confirm-backdrop"),
    confirmTitle: $("confirm-title"),
    confirmMessage: $("confirm-message"),
    confirmOk: $("confirm-ok"),
    confirmCancel: $("confirm-cancel"),

    toasts: $("toasts"),

    shareBackdrop: $("share-backdrop"),
    shareTitle: $("share-title"),
    shareClose: $("share-close"),
    shareCancel: $("share-cancel"),
    shareStart: $("share-start"),
    shareInstall: $("share-install"),
    shareInstallBtn: $("share-install-btn"),
    sharePassword: $("share-password"),
    shareFeedback: $("share-feedback"),
    shareExpiry: $("share-expiry"),
  };

  /* ------------------------------------------------------------------ */
  /* Preferences (per-browser conveniences only)                        */
  /* ------------------------------------------------------------------ */

  function loadPref(key, fallback) {
    try {
      const v = localStorage.getItem("lm_" + key);
      return v === null ? fallback : v;
    } catch (e) {
      return fallback;
    }
  }

  function savePref(key, value) {
    try {
      localStorage.setItem("lm_" + key, value);
    } catch (e) {
      /* storage unavailable — preference just won't persist */
    }
  }

  const SORTS = ["manual", "name-asc", "name-desc", "path", "created-desc", "created-asc", "updated-desc", "status", "port", "mem"];

  const state = {
    apps: [],
    views: new Map(),
    groupHeads: new Map(),
    viewMode: loadPref("view", "grid") === "list" ? "list" : "grid",
    sortMode: SORTS.includes(loadPref("sort", "manual")) ? loadPref("sort", "manual") : "manual",
    groupBy: loadPref("group", "1") === "1",
    categoryFilter: loadPref("category", ""),
    activeFilter: "all",
    searchQuery: "",
    sse: null,
    pollTimer: null,
    logsId: null,
    logsTimer: null,
    rawLogLines: [],
    currentBrowsePath: "",
    confirmAction: null,
    detectSeq: 0,
    drag: null,
  };

  /* ------------------------------------------------------------------ */
  /* API helpers                                                        */
  /* ------------------------------------------------------------------ */

  function apiUrl(path) {
    return API_BASE + path;
  }

  function errorText(data, status, raw) {
    if (data && data.detail !== undefined) {
      const detail = data.detail;
      if (typeof detail === "string") return detail;
      if (typeof detail === "object" && detail !== null) {
        if (detail.error === "port_in_use") {
          return "Port in use by PID " + detail.pid + " (" + (detail.command || "") + ")";
        }
        if (detail.message) return detail.message;
        if (Array.isArray(detail)) {
          const msgs = detail.map((d) => (d && d.msg ? d.msg : null)).filter(Boolean);
          if (msgs.length) return msgs.join("; ");
        }
        return JSON.stringify(detail);
      }
    }
    if (data && typeof data.error === "string") return data.error;
    if (raw && raw.trim() && raw.length < 300) return raw.trim();
    return "HTTP " + status;
  }

  async function request(path, options) {
    const opts = Object.assign({ cache: "no-store" }, options || {});
    opts.headers = Object.assign({ Accept: "application/json" }, (options && options.headers) || {});
    if (options && typeof options.body === "string") {
      opts.headers["Content-Type"] = "application/json";
    }

    let res;
    try {
      res = await fetch(apiUrl(path), opts);
    } catch (err) {
      throw new Error("network error — is the server running?");
    }

    const raw = await res.text();
    let data = null;
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch (err) {
        data = null;
      }
    }
    if (!res.ok) {
      const err = new Error(errorText(data, res.status, raw));
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  /* ------------------------------------------------------------------ */
  /* DOM helpers & formatting                                           */
  /* ------------------------------------------------------------------ */

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function button(className, text, label) {
    const b = el("button", className, text);
    b.type = "button";
    if (label) b.setAttribute("aria-label", label);
    return b;
  }

  function icon(node, name) {
    node.innerHTML = ICONS[name];
    return node;
  }

  function setConn(mode) {
    const labels = {
      connecting: "Connecting…",
      live: "Live",
      polling: "Polling",
      offline: "Offline — retrying",
    };
    els.connText.textContent = labels[mode] || "";
    els.conn.className = "conn " + mode;
  }

  function toast(message, kind) {
    const node = el("div", "toast" + (kind === "ok" ? " ok" : kind === "warn" ? " warn" : ""), message);
    els.toasts.appendChild(node);
    window.setTimeout(() => node.remove(), kind === "ok" ? 3000 : 8000);
  }

  function formatDuration(totalSeconds) {
    const secs = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    return h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  function isActive(app) {
    return app.status === "running" || app.status === "starting";
  }

  function shortUptime(app) {
    const secs = typeof app.started_at === "number" ? Date.now() / 1000 - app.started_at : app.uptime_s || 0;
    if (secs < 60) return "just started";
    if (secs < 3600) return Math.floor(secs / 60) + "m";
    if (secs < 86400) return Math.floor(secs / 3600) + "h " + Math.floor((secs % 3600) / 60) + "m";
    return Math.floor(secs / 86400) + "d";
  }

  function formatUptime(app) {
    if (!isActive(app)) return "—";
    if (typeof app.started_at === "number") return formatDuration(Date.now() / 1000 - app.started_at);
    if (typeof app.uptime_s === "number") return formatDuration(app.uptime_s);
    return "—";
  }

  function formatCpu(app) {
    if (typeof app.cpu_percent !== "number" || !isFinite(app.cpu_percent)) return "—";
    return app.cpu_percent.toFixed(1) + "%";
  }

  function formatMb(mb) {
    return mb >= 1000 ? (mb / 1024).toFixed(2) + " GB" : mb.toFixed(mb >= 100 ? 0 : 1) + " MB";
  }

  function formatMem(app) {
    if (typeof app.mem_mb !== "number" || !isFinite(app.mem_mb)) return "—";
    return formatMb(app.mem_mb);
  }

  function toDate(ts) {
    if (!ts) return null;
    const d = new Date(ts > 1e11 ? ts : ts * 1000);
    return isNaN(d.getTime()) ? null : d;
  }

  function formatDateTime(ts) {
    const d = toDate(ts);
    if (!d) return "—";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function statusLabel(status) {
    return { running: "Running", stopped: "Stopped", crashed: "Crashed", starting: "Starting" }[status] || (status ? String(status) : "Unknown");
  }

  function appPort(app) {
    if (typeof app.detected_port === "number") return app.detected_port;
    if (typeof app.port === "number") return app.port;
    return null;
  }

  function techLabel(app) {
    if (app.wordpress) return "WordPress";
    const cmd = (app.command || "").toLowerCase();
    if (!cmd) return null;
    if (cmd.includes("http.server")) return "Static";
    if (cmd.includes("artisan")) return "Laravel";
    if (/\bphp\b/.test(cmd)) return "PHP";
    if (cmd.includes("manage.py")) return "Django";
    if (cmd.includes("uvicorn")) return "FastAPI";
    if (cmd.includes("streamlit")) return "Streamlit";
    if (/\brails\b|rackup/.test(cmd)) return "Ruby";
    if (/\bgo run\b/.test(cmd)) return "Go";
    if (/\bcargo\b/.test(cmd)) return "Rust";
    if (/\bdotnet\b/.test(cmd)) return ".NET";
    if (/\bdocker\b/.test(cmd)) return "Docker";
    if (/mvnw?\b|gradlew?\b/.test(cmd)) return "Java";
    if (/\bdeno\b/.test(cmd)) return "Deno";
    if (/\b(npm|pnpm|yarn|bun|node|vite|next)\b/.test(cmd)) return "Node";
    if (cmd.includes("python") || cmd.includes("uvicorn") || cmd.includes(".py")) return "Python";
    if (cmd.includes("bash") || cmd.includes(".sh") || cmd.includes(".command")) return "Shell";
    return null;
  }

  /** http://<id>.localhost:<manager port>/ — served by Homeport's proxy. */
  function namedUrl(app) {
    const port = window.location.port ? ":" + window.location.port : "";
    return "http://" + app.id + ".localhost" + port + "/";
  }

  function appCategory(app) {
    return (app.category || "").trim();
  }

  function findApp(id) {
    return state.apps.find((a) => a.id === id);
  }

  /* ------------------------------------------------------------------ */
  /* Menus & confirm dialog                                             */
  /* ------------------------------------------------------------------ */

  function closeMenus(except) {
    document.querySelectorAll(".menu").forEach((m) => {
      if (m !== except) m.hidden = true;
    });
    document.querySelectorAll("[aria-expanded='true']").forEach((b) => {
      if (!except || b.nextElementSibling !== except) b.setAttribute("aria-expanded", "false");
    });
  }

  function toggleMenu(trigger, menu) {
    const open = menu.hidden;
    closeMenus(open ? menu : null);
    menu.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (open) {
      // Open toward the side with more room; if it still doesn't fit, scroll inside it
      // (flipping up from a card near the top used to push the first items off-screen).
      menu.classList.remove("menu-up");
      menu.style.maxHeight = "";
      const t = trigger.getBoundingClientRect();
      const h = menu.scrollHeight;
      const below = window.innerHeight - t.bottom - 14;
      const above = t.top - 14;
      if (h > below && above > below) {
        menu.classList.add("menu-up");
        if (h > above) menu.style.maxHeight = Math.floor(above) + "px";
      } else if (h > below) {
        menu.style.maxHeight = Math.max(160, Math.floor(below)) + "px";
      }
    }
  }

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".menu-wrap")) closeMenus();
  });

  function showConfirm(title, message, okText, onConfirm, okClass) {
    els.confirmTitle.textContent = title;
    els.confirmMessage.textContent = message;
    els.confirmOk.textContent = okText || "Confirm";
    els.confirmOk.className = "btn " + (okClass || "primary");
    state.confirmAction = onConfirm;
    els.confirmBackdrop.hidden = false;
    els.confirmOk.focus();
  }

  function hideConfirm() {
    els.confirmBackdrop.hidden = true;
    state.confirmAction = null;
  }

  els.confirmCancel.addEventListener("click", hideConfirm);
  els.confirmOk.addEventListener("click", () => {
    const action = state.confirmAction;
    hideConfirm();
    if (typeof action === "function") action();
  });

  /* ------------------------------------------------------------------ */
  /* Card                                                               */
  /* ------------------------------------------------------------------ */

  /* ------------------------------------------------------------------ */
  /* App logos: the project's own favicon, else a generated monogram     */
  /* ------------------------------------------------------------------ */

  // Generated logos match the brand mark: a letter drawn as folded ribbon
  // strokes (each later stroke in the lighter tone, laid over the earlier
  // darker one) on the navy brand tile. Colour pair = [light, dark].
  const LOGO_COLORS = [
    ["#5df5c4", "#0f9f76"], ["#7cc7ff", "#2b7bd9"], ["#b9a6ff", "#6d4fe0"],
    ["#ffa58a", "#e0533a"], ["#ffd36b", "#d98a0b"], ["#ff9ad1", "#d63c8f"],
    ["#c3f56b", "#5f9f12"], ["#6ef0f0", "#0a98a8"],
  ];

  // Ribbon strokes per letter on a 64×64 grid (letter box ≈ x16–48, y16–48).
  const RIBBON_GLYPHS = {
    A: ["M19 48 L32 16", "M32 16 L45 48", "M24 37 H40"],
    B: ["M21 16 V48", "M21 16 H32 A8 8 0 0 1 32 32 H21", "M21 32 H34 A8 8 0 0 1 34 48 H21"],
    C: ["M45 22 C40 13 18 14 18 32", "M18 32 C18 50 40 51 45 42"],
    D: ["M21 16 V48", "M21 16 H28 C49 16 49 48 28 48 H21"],
    E: ["M21 16 V48", "M21 16 H43", "M21 32 H38", "M21 48 H43"],
    F: ["M21 16 V48", "M21 16 H43", "M21 32 H38"],
    G: ["M45 22 C40 13 18 14 18 32", "M18 32 C18 50 46 51 46 34 H34"],
    H: ["M20 16 V48", "M44 16 V48", "M20 32 H44"],
    I: ["M32 16 V48", "M25 16 H39", "M25 48 H39"],
    J: ["M40 16 V37", "M40 37 C40 51 22 51 21 40"],
    K: ["M21 16 V48", "M43 16 L23 34", "M29 29 L44 48"],
    L: ["M22 16 V48", "M22 48 H43"],
    M: ["M18 48 V16", "M18 16 L32 35", "M32 35 L46 16", "M46 16 V48"],
    N: ["M20 48 V16", "M20 16 L44 48", "M44 48 V16"],
    O: ["M32 16 C13 16 13 48 32 48", "M32 48 C51 48 51 16 32 16"],
    P: ["M21 48 V16", "M21 16 H32 A9 9 0 0 1 32 34 H21"],
    Q: ["M32 16 C13 16 13 48 32 48", "M32 48 C51 48 51 16 32 16", "M37 39 L47 50"],
    R: ["M21 48 V16", "M21 16 H32 A9 9 0 0 1 32 34 H21", "M31 34 L44 48"],
    S: ["M44 21 C40 13 20 14 20 24 C20 31 30 31 32 32", "M32 32 C37 33 44 34 44 41 C44 50 23 50 19 43"],
    T: ["M32 16 V48", "M18 16 H46"],
    U: ["M20 16 V36 C20 44 26 48 32 48", "M32 48 C38 48 44 44 44 36 V16"],
    V: ["M19 16 L32 48", "M32 48 L45 16"],
    W: ["M16 16 L23 48", "M23 48 L32 27", "M32 27 L41 48", "M41 48 L48 16"],
    X: ["M20 16 L44 48", "M44 16 L20 48"],
    Y: ["M19 16 L32 32", "M45 16 L32 32", "M32 32 V48"],
    Z: ["M20 16 H44", "M44 16 L20 48", "M20 48 H44"],
    "#": ["M11 35 L32 14", "M53 35 L32 14"], // brand roof, for names without a letter
  };

  function hashString(text) {
    let h = 2166136261;
    for (let i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function logoLetter(name) {
    const m = String(name || "").match(/[A-Za-z]/);
    return m ? m[0].toUpperCase() : "#";
  }

  const SVG_NS = "http://www.w3.org/2000/svg";

  function paintGeneratedLogo(tile, app) {
    const h = hashString(app.name || app.id);
    const [light, dark] = LOGO_COLORS[h % LOGO_COLORS.length];
    const letter = logoLetter(app.name);
    tile.className = "app-logo generated";
    tile.style.background = "";
    tile.textContent = "";

    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 64 64");
    svg.setAttribute("class", "ribbon");
    const g = document.createElementNS(SVG_NS, "g");
    g.setAttribute("fill", "none");
    g.setAttribute("stroke-width", "8.5");
    g.setAttribute("stroke-linecap", "round");
    g.setAttribute("stroke-linejoin", "round");
    RIBBON_GLYPHS[letter].forEach((d, i) => {
      const path = document.createElementNS(SVG_NS, "path");
      path.setAttribute("d", d);
      path.setAttribute("stroke", i === 0 ? dark : light);
      g.appendChild(path);
    });
    svg.appendChild(g);
    if (letter === "#") {
      const dot = document.createElementNS(SVG_NS, "circle");
      dot.setAttribute("cx", "32");
      dot.setAttribute("cy", "46");
      dot.setAttribute("r", "7");
      dot.setAttribute("fill", light);
      svg.appendChild(dot);
    }
    tile.appendChild(svg);
  }

  function updateLogo(v, app) {
    const url = app.icon ? apiUrl(app.icon) : "";
    const key = url ? "img:" + url : "gen:" + (app.name || app.id);
    if (v.logoKey === key) return;
    v.logoKey = key;
    const tile = v.logo;
    if (!url) {
      paintGeneratedLogo(tile, app);
      return;
    }
    tile.className = "app-logo image";
    tile.style.background = "";
    tile.textContent = "";
    const img = document.createElement("img");
    img.alt = "";
    img.decoding = "async";
    img.addEventListener("error", () => {
      if (v.logoKey !== key) return;
      v.logoKey = "gen:" + (app.name || app.id);
      paintGeneratedLogo(tile, findApp(app.id) || app);
    });
    img.src = url;
    tile.appendChild(img);
  }

  function shortPath(p) {
    return String(p || "")
      .replace(/^\/Users\/[^/]+/, "~")
      .replace(/^\/home\/[^/]+/, "~")
      .replace(/^[A-Za-z]:\\Users\\[^\\]+/, "~");
  }

  // Platform wording: the server reports its OS; the key hint follows the browser's.
  const IS_APPLE = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
  const FOLDER_LABEL = { windows: "Open in Explorer", linux: "Open folder", mac: "Open in Finder" };
  let serverPlatform = "mac";
  let canQuit = false;

  async function quitHomeport() {
    showConfirm("Quit Homeport?", "This stops Homeport and every app it's running.", "Quit", async () => {
      try {
        await request("/api/quit", { method: "POST" });
        document.body.textContent = "";
        const msg = el("div", "quit-msg", "Homeport has quit. You can close this window.");
        document.body.appendChild(msg);
      } catch (err) {
        toast("Couldn't quit: " + err.message, "err");
      }
    }, "danger");
  }

  function createStat(label, extraClass) {
    const wrap = el("div", "stat" + (extraClass ? " " + extraClass : ""));
    wrap.appendChild(el("span", "stat-label", label));
    const value = el("span", "stat-value", "—");
    wrap.appendChild(value);
    return { wrap: wrap, value: value };
  }

  function createCard(app) {
    const id = app.id;
    const card = el("article", "card");
    card.dataset.id = id;

    // Top: logo, name, subtitle (status · type · port), "••" menu
    const head = el("div", "card-head");
    const handle = icon(button("drag-handle", null, "Drag to reorder"), "grip");
    handle.title = "Drag to move";
    const logo = el("div", "app-logo");
    logo.setAttribute("aria-hidden", "true");
    const titles = el("div", "card-titles");
    const titleRow = el("div", "card-title-row");
    const name = el("h2", "card-name");
    titleRow.appendChild(name);
    const fbChip = icon(button("fb-chip", null), "comment");
    const fbCount = el("span", null, "");
    fbChip.appendChild(fbCount);
    fbChip.hidden = true;
    fbChip.title = "Open feedback from visitors";
    titleRow.appendChild(fbChip);
    const subtitle = el("div", "card-sub");
    const status = el("span", "status");
    status.appendChild(el("span", "status-dot"));
    const statusText = el("span", null);
    status.appendChild(statusText);
    const tech = el("span", "card-tech");
    const portLink = el("a", "port-link");
    portLink.target = "_blank";
    portLink.rel = "noopener noreferrer";
    const portNone = el("span", "muted port-none", "No port");
    const upChip = el("span", "up-chip");
    const health = el("span", "health");
    const gitChip = el("span", "git-chip");
    const category = button("tag category", null); // kept for updateCard; shown via sidebar
    subtitle.appendChild(status);
    subtitle.appendChild(upChip);
    subtitle.appendChild(tech);
    subtitle.appendChild(portLink);
    subtitle.appendChild(portNone);
    subtitle.appendChild(health);
    subtitle.appendChild(gitChip);
    const path = el("div", "card-path");
    const desc = el("p", "card-desc");
    titles.appendChild(titleRow);
    titles.appendChild(subtitle);
    titles.appendChild(path);
    head.appendChild(handle);
    head.appendChild(logo);
    head.appendChild(titles);

    // The app's own address, on one clear line (grid view)
    const cardLink = icon(el("a", "card-link"), "open");
    cardLink.target = "_blank";
    cardLink.rel = "noopener noreferrer";
    const cardLinkText = el("span", null, "");
    cardLink.appendChild(cardLinkText);
    cardLink.addEventListener("click", (e) => {
      e.preventDefault();
      openInBrowser(id);
    });

    // Alert: crash reason or port conflict
    const alert = el("div", "card-alert");
    const alertText = el("span", "card-alert-text");
    const alertBtn = button("btn small danger", "Kill & start");
    const whyBtn = button("btn small why-btn", "Why?");
    whyBtn.title = "Explain the crash and suggest a fix";
    alert.appendChild(alertText);
    alert.appendChild(whyBtn);
    alert.appendChild(alertBtn);

    // WordPress needs setup
    const wpBar = el("div", "wp-bar");
    wpBar.appendChild(el("span", "wp-bar-text", "WordPress needs a database to run"));
    const wpSetupBtn = button("btn small", "Set up");
    wpBar.appendChild(wpSetupBtn);
    wpSetupBtn.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) openWordPress(cur);
    });

    // Public share link: one quiet line; the full link, QR, feedback and stop are in its menu
    const shareBar = el("div", "share-bar menu-wrap");
    const shareMain = button("share-main", null, "Sharing options");
    shareMain.setAttribute("aria-haspopup", "menu");
    shareMain.setAttribute("aria-expanded", "false");
    const shareDot = el("span", "share-dot");
    const shareText = el("span", "share-text");
    const shareLink = el("a", "share-link");
    shareLink.target = "_blank";
    shareLink.rel = "noopener noreferrer";
    const shareMeta = el("span", "share-meta");
    const shareMenu = el("div", "menu share-menu");
    shareMenu.setAttribute("role", "menu");
    shareMenu.hidden = true;
    const shareFb = button("share-fb-btn", "Visitor feedback");
    shareFb.setAttribute("role", "menuitemcheckbox");
    shareFb.title = "Let visitors leave feedback on the pages (same link)";
    const shareFbState = el("span", "menu-state", "");
    shareFb.appendChild(shareFbState);
    const shareQr = button(null, "Show QR code");
    shareQr.setAttribute("role", "menuitem");
    const shareOpenFb = button(null, "View feedback…");
    shareOpenFb.setAttribute("role", "menuitem");
    const shareStop = button("danger", "Stop sharing");
    shareStop.setAttribute("role", "menuitem");
    const shareCopy = button("btn small ghost share-copy", "Copy");
    shareCopy.title = "Copy the public link";
    shareMain.append(shareDot, shareText, shareMeta);
    shareMenu.append(shareLink, el("hr"), shareFb, shareOpenFb, shareQr, el("hr"), shareStop);
    shareBar.append(shareMain, shareCopy, shareMenu);
    shareMain.addEventListener("click", () => toggleMenu(shareMain, shareMenu));
    shareMenu.addEventListener("click", (e) => {
      if (e.target.closest("button, a")) closeMenus();
    });
    shareOpenFb.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) openFeedback(cur);
    });

    // Stats
    const stats = el("div", "stats");
    const uptimeStat = createStat("Uptime");
    const cpuStat = createStat("CPU");
    const memStat = createStat("Memory");
    const restartsStat = createStat("Restarts", "stat-restarts");
    [uptimeStat, cpuStat, memStat, restartsStat].forEach((s) => stats.appendChild(s.wrap));

    // Actions: round icon buttons, primary Start/Stop in black
    const actions = el("div", "card-actions");
    const openBtn = button("pill-btn primary", null, "Open");
    icon(openBtn, "open");
    openBtn.appendChild(el("span", null, "Open"));
    openBtn.title = "Open in your browser";
    openBtn.addEventListener("click", () => openInBrowser(id));
    const startBtn = button("pill-btn primary", null, "Start");
    icon(startBtn, "play");
    startBtn.appendChild(el("span", null, "Start"));
    startBtn.addEventListener("click", () => runAction(id, "start"));
    const toggleBtn = icon(button("round-btn primary-round", null, "Start"), "play");
    const logsBtn = icon(button("round-btn", null, "Logs"), "logs");
    logsBtn.title = "Logs";
    const shareBtn = icon(button("round-btn share-btn", null, "Share"), "share");
    shareBtn.title = "Share a public link to this app";
    const menuWrap = el("div", "menu-wrap card-menu");
    const moreBtn = icon(button("dots-btn", null, "More actions for " + app.name), "dots");
    moreBtn.setAttribute("aria-haspopup", "menu");
    moreBtn.setAttribute("aria-expanded", "false");
    const menu = el("div", "menu menu-right");
    menu.setAttribute("role", "menu");
    menu.hidden = true;
    const mi = (text, cls) => {
      const b = button(cls || null, text);
      b.setAttribute("role", "menuitem");
      menu.appendChild(b);
      return b;
    };
    // Open first: the link on the card can be hard to hit (or blocked in the desktop app).
    const miBrowser = mi("Open");
    miBrowser.title = "Open the app in your browser (starts it first if needed)";
    const miCopyLink = mi("Copy link");
    const miFeedback = mi("Feedback…");
    menu.appendChild(el("hr"));
    const miRestart = mi("Restart");
    const miEdit = mi("Edit…");
    menu.appendChild(el("hr"));
    // Colour marker: a row of swatches; "" clears it.
    const colorRow = el("div", "menu-colors");
    colorRow.appendChild(el("span", "menu-colors-label", "Color"));
    const swatches = APP_COLORS.map(([value, label]) => {
      const sw = button("swatch swatch-" + (value || "none"), null, label);
      sw.title = label;
      sw.dataset.color = value;
      sw.setAttribute("role", "menuitemradio");
      sw.addEventListener("click", () => setColor(id, value));
      colorRow.appendChild(sw);
      return sw;
    });
    menu.appendChild(colorRow);
    menu.appendChild(el("hr"));
    const miPhone = mi("Open on phone…");
    const miWp = mi("WordPress…");
    miWp.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) openWordPress(cur);
    });
    const miConnUrl = mi("Copy connection URL");
    const miConnEnv = mi("Copy .env settings");
    const miGitHub = mi("Open on GitHub");
    const miPRs = mi("Pull requests");
    const miPull = mi("Pull & restart");
    miPull.title = "git pull --ff-only, then restart if it's running";
    const miFinder = mi(FOLDER_LABEL[serverPlatform] || "Open folder");
    miFinder.classList.add("mi-folder");
    const miTerminal = mi("Open in Terminal");
    menu.appendChild(el("hr"));
    const miUp = mi("Move up");
    const miDown = mi("Move down");
    const miMoveHr = el("hr");
    menu.appendChild(miMoveHr);
    const miDelete = mi("Delete…", "danger");
    menuWrap.appendChild(moreBtn);
    menuWrap.appendChild(menu);
    head.appendChild(menuWrap);
    actions.appendChild(shareBtn);
    actions.appendChild(logsBtn);
    actions.appendChild(toggleBtn);
    actions.appendChild(startBtn);
    actions.appendChild(openBtn);

    // Bottom: summary (description, live stats) + action buttons
    const summary = el("div", "card-summary");
    summary.appendChild(stats);
    summary.appendChild(desc);
    const bottom = el("div", "card-bottom");
    bottom.appendChild(summary);
    bottom.appendChild(actions);

    card.appendChild(head);
    card.appendChild(cardLink);
    card.appendChild(wpBar);
    card.appendChild(shareBar);
    card.appendChild(alert);
    card.appendChild(bottom);

    // Events
    toggleBtn.addEventListener("click", () => {
      const cur = findApp(id);
      runAction(id, cur && isActive(cur) ? "stop" : "start");
    });
    shareBtn.addEventListener("click", () => {
      const cur = findApp(id);
      if (!cur) return;
      openShare(cur);
    });
    shareCopy.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur && cur.share && cur.share.url) copyText(cur.share.url);
    });
    shareStop.addEventListener("click", () => stopShare(id));
    shareFb.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur && cur.share) setShareFeedback(id, !cur.share.feedback);
    });
    fbChip.addEventListener("click", (e) => {
      e.stopPropagation();
      const cur = findApp(id);
      if (cur) openFeedback(cur);
    });
    miFeedback.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) openFeedback(cur);
    });
    miCopyLink.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) copyText(cur.share && cur.share.url ? cur.share.url : namedUrl(cur));
    });
    // In the desktop app a plain link may not open a browser: let Homeport open it.
    portLink.addEventListener("click", (e) => {
      if (!window.pywebview) return;
      e.preventDefault();
      openInBrowser(id);
    });
    shareLink.addEventListener("click", (e) => {
      if (!window.pywebview) return;
      e.preventDefault();
      openTarget(id, "share");
    });
    logsBtn.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) openLogs(cur);
    });
    moreBtn.addEventListener("click", () => toggleMenu(moreBtn, menu));
    menu.addEventListener("click", (e) => {
      if (e.target.closest("button")) closeMenus();
    });
    miRestart.addEventListener("click", () => runAction(id, "restart"));
    miEdit.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) openEditModal(cur);
    });
    miBrowser.addEventListener("click", () => openInBrowser(id));
    miGitHub.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur && cur.github) window.open(cur.github.url, "_blank", "noopener");
    });
    miPRs.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur && cur.github) window.open(cur.github.url + "/pulls", "_blank", "noopener");
    });
    gitChip.addEventListener("click", (e) => {
      const cur = findApp(id);
      if (!cur || !cur.github || !cur.github.ci_url) return;
      e.stopPropagation();
      window.open(cur.github.ci_url, "_blank", "noopener");
    });
    miConnUrl.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur && cur.service) copyText(cur.service.url);
    });
    miConnEnv.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur && cur.service) copyText(envText(cur.service));
    });
    miPhone.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) openPhone(cur);
    });
    miPull.addEventListener("click", async () => {
      try {
        const res = await request("/api/apps/" + encodeURIComponent(id) + "/pull", { method: "POST" });
        if (res.state) replaceAppState(res.state);
        const last = (res.output || "").split("\n").filter(Boolean).pop() || "";
        toast(res.ok ? (res.restarted ? "Pulled and restarted" : "Pulled: " + last) : "Pull failed: " + last, res.ok ? "ok" : "err");
      } catch (err) {
        toast("Pull failed: " + err.message, "err");
      }
    });
    shareQr.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) openPhone(cur);
    });
    whyBtn.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) openDiagnose(cur);
    });
    miFinder.addEventListener("click", () => openTarget(id, "finder"));
    miTerminal.addEventListener("click", () => openTarget(id, "terminal"));
    miUp.addEventListener("click", () => moveBy(id, -1));
    miDown.addEventListener("click", () => moveBy(id, 1));
    miDelete.addEventListener("click", () => {
      const cur = findApp(id);
      showConfirm(
        "Delete app?",
        "Remove “" + (cur ? cur.name : id) + "” from the manager? It will be stopped if running. Files on disk are not touched.",
        "Delete",
        () => onDeleteApp(id),
        "danger"
      );
    });
    category.addEventListener("click", () => {
      const cur = findApp(id);
      if (cur) setCategoryFilter(appCategory(cur));
    });
    portLink.addEventListener("click", (e) => {
      const cur = findApp(id);
      if (cur && !isActive(cur)) {
        e.preventDefault();
        openInBrowser(id);
      }
    });
    alertBtn.addEventListener("click", () => {
      const cur = findApp(id);
      if (!cur || !cur.port_conflict) return;
      confirmKillConflict(cur, cur.port_conflict);
    });

    // Drag anywhere on the card (mouse/pen) or on the grip (touch) to move it.
    card.addEventListener("pointerdown", (e) => onCardPointerDown(e, card, id, false));
    handle.addEventListener("pointerdown", (e) => onCardPointerDown(e, card, id, true));

    return {
      el: card,
      logo, logoKey: null, stats,
      shareBar, shareText, shareLink, shareBtn, shareMeta, gitChip, whyBtn, miPhone, miPull, miConnUrl, miConnEnv,
      miGitHub, miPRs,
      shareFb, shareFbState, fbChip, fbCount, miFeedback, cardLink, cardLinkText, upChip, openBtn, startBtn, shareMain,
      wpBar, miWp,
      name, path, desc, status, statusText,
      portLink, portNone, health, tech, category,
      alert, alertText, alertBtn,
      uptime: uptimeStat.value,
      cpu: cpuStat.value,
      mem: memStat.value,
      restarts: restartsStat.value,
      toggleBtn, miRestart, miBrowser, miUp, miDown, miMoveHr, moreBtn, swatches,
    };
  }

  function updateCard(v, app) {
    const status = app.status || "stopped";
    const color = app.color || "";
    v.el.className = "card status-" + status + (color ? " tint-" + color : "") + (state.drag && state.drag.id === app.id ? " dragging" : "");
    v.swatches.forEach((sw) => sw.setAttribute("aria-checked", String(sw.dataset.color === color)));

    v.name.textContent = app.name;
    v.name.title = app.name;
    updateLogo(v, app);
    v.path.textContent = shortPath(app.path);
    v.path.title = app.path;
    v.desc.textContent = app.description || shortPath(app.path);
    v.desc.title = app.description ? "" : app.path;
    v.desc.classList.toggle("is-path", !app.description);
    v.moreBtn.setAttribute("aria-label", "More actions for " + app.name);

    v.status.className = "status " + status;
    v.statusText.textContent = statusLabel(status);

    const port = appPort(app);
    if (port !== null) {
      v.portLink.textContent = app.id + ".localhost";
      v.portLink.href = namedUrl(app);
      v.portLink.title = "Named URL — also at localhost:" + port;
      v.portLink.hidden = false;
      v.portNone.hidden = true;
    } else {
      v.portLink.hidden = true;
      v.portNone.hidden = false;
    }
    v.miBrowser.disabled = port === null && !app.command;
    v.cardLink.hidden = !(port !== null && isActive(app));
    v.cardLinkText.textContent = app.id + ".localhost";
    v.cardLink.href = namedUrl(app);
    v.cardLink.title = "Open " + namedUrl(app) + " (also at localhost:" + port + ")";
    v.name.title = app.name + "\n" + app.path;
    const fbOpen = app.feedback_open || 0;
    v.fbChip.hidden = !fbOpen;
    v.fbCount.textContent = String(fbOpen);
    v.fbChip.setAttribute("aria-label", fbOpen + " open feedback");
    v.miFeedback.textContent = fbOpen ? "Feedback… (" + fbOpen + " open)" : "Feedback…";

    if (app.health_url && status === "running" && app.healthy !== null && app.healthy !== undefined) {
      v.health.hidden = false;
      v.health.textContent = app.healthy ? "· healthy" : "· unhealthy";
      v.health.className = "health " + (app.healthy ? "ok" : "bad");
    } else {
      v.health.hidden = true;
    }

    const tech = techLabel(app);
    v.tech.textContent = tech || "";
    v.tech.hidden = !tech;
    v.portNone.hidden = v.portNone.hidden || !v.tech.hidden;

    const cat = appCategory(app);
    v.category.textContent = cat;
    v.category.hidden = !cat;

    // Port conflict wins over crash text — it's actionable.
    if (app.port_conflict && !isActive(app)) {
      const c = app.port_conflict;
      v.alertText.textContent = "Port " + (app.port || app.detected_port || "") + " is used by PID " + c.pid + " (" + (c.command || "unknown") + ")";
      v.alertText.title = v.alertText.textContent;
      v.alertBtn.hidden = false;
      v.alert.hidden = false;
    } else if (status === "crashed") {
      const first = (app.last_error || "Exited unexpectedly").split("\n")[0];
      v.alertText.textContent = first;
      v.alertText.title = app.last_error || "";
      v.alertBtn.hidden = true;
      v.alert.hidden = false;
    } else {
      v.alert.hidden = true;
    }

    v.whyBtn.hidden = status !== "crashed" && !(app.port_conflict && !isActive(app));
    v.whyBtn.className = "btn small why-btn";

    const git = app.git;
    v.gitChip.hidden = !git || !git.branch;
    if (git && git.branch) {
      let text = "⎇ " + git.branch;
      if (git.dirty) text += " ●" + git.dirty;
      if (git.behind) text += " ↓" + git.behind;
      if (git.ahead) text += " ↑" + git.ahead;
      v.gitChip.textContent = text;
      v.gitChip.title = (git.dirty ? git.dirty + " changed file(s)" : "No uncommitted changes") +
        (git.behind ? " · " + git.behind + " commit(s) to pull" : "") + (git.ahead ? " · " + git.ahead + " to push" : "");
      v.gitChip.classList.toggle("dirty", Boolean(git.dirty));
    }
    v.miPull.hidden = !git;
    const ghs = app.github;
    v.miGitHub.hidden = !ghs;
    v.miPRs.hidden = !ghs || ghs.prs === null || ghs.prs === undefined;
    if (ghs && typeof ghs.prs === "number") v.miPRs.textContent = "Pull requests (" + ghs.prs + (ghs.prs >= 100 ? "+" : "") + ")";
    const ci = ghs && ghs.ci;
    v.gitChip.dataset.ci = ci || "";
    if (ci && git && git.branch) {
      v.gitChip.textContent += { success: " ✓", failure: " ✗", pending: " ●" }[ci] || "";
      v.gitChip.title += " · CI " + { success: "passed", failure: "failed", pending: "running" }[ci] + " — click to open";
    }
    v.miConnUrl.hidden = v.miConnEnv.hidden = !app.service;
    v.miWp.hidden = !app.wordpress;
    v.wpBar.hidden = !(app.wordpress && app.wordpress.needs_setup) || status === "crashed";
    v.miPhone.disabled = !isActive(app);

    const share = app.share;
    v.shareBar.hidden = !share;
    if (share) {
      v.shareBar.className = "share-bar menu-wrap " + share.status; // keep menu-wrap: clicks inside don't close its menu
      const bits = [];
      if (share.protected) bits.push("password");
      if (share.expires_at) bits.push(timeLeft(share.expires_at) + " left");
      v.shareMeta.textContent = bits.join(" · ");
      v.shareMeta.hidden = !bits.length;
      v.shareFbState.textContent = share.feedback ? "On" : "Off";
      v.shareFb.classList.toggle("on", Boolean(share.feedback));
      v.shareFb.setAttribute("aria-checked", String(Boolean(share.feedback)));
      if (share.status === "live" && share.url) {
        v.shareText.textContent = "Shared";
        v.shareLink.textContent = share.url.replace(/^https:\/\//, "");
        v.shareLink.href = share.url;
        v.shareLink.hidden = false;
      } else if (share.status === "error") {
        v.shareText.textContent = "Sharing failed: " + (share.error || "tunnel stopped");
        v.shareText.title = share.error || "";
        v.shareLink.hidden = true;
      } else {
        v.shareText.textContent = "Creating public link…";
        v.shareLink.hidden = true;
      }
    }
    // While shared, the link bar's own Stop button handles unsharing.
    v.shareBtn.hidden = Boolean(share);
    v.shareBtn.disabled = !isActive(app);
    v.shareBtn.title = isActive(app) ? "Share a public link to this app" : "Start the app to share it";

    v.stats.hidden = !isActive(app);
    // short uptime in the subtitle; the full numbers are in the status tooltip (and the list view)
    v.upChip.hidden = !isActive(app) || !(app.started_at || app.uptime_s);
    v.upChip.textContent = shortUptime(app);
    v.status.title = isActive(app)
      ? "Up " + formatUptime(app) + " · CPU " + formatCpu(app) + " · Memory " + formatMem(app) + " · Restarts " + (app.restarts || 0)
      : "";
    v.uptime.textContent = formatUptime(app);
    v.cpu.textContent = formatCpu(app);
    v.mem.textContent = formatMem(app);
    v.restarts.textContent = String(app.restarts || 0);

    const active = isActive(app);
    if (v.toggleActive !== active) {
      v.toggleActive = active;
      icon(v.toggleBtn, active ? "stop" : "play");
    }
    v.toggleBtn.className = "round-btn primary-round" + (active ? " is-stop" : "");
    // grid view: a clear Start (stopped) or Open (running) button; the round one stops
    v.startBtn.hidden = active;
    v.startBtn.disabled = !app.command;
    v.startBtn.title = app.command ? "Start " + app.name : "Set a command first (Edit…)";
    v.openBtn.hidden = !active;
    v.el.classList.toggle("is-active", active);
    v.toggleBtn.disabled = !active && !app.command;
    v.toggleBtn.setAttribute("aria-label", (active ? "Stop " : "Start ") + app.name);
    v.toggleBtn.title = !active && !app.command ? "Set a command first (Edit…)" : active ? "Stop" : "Start";
    v.miRestart.disabled = !app.command;

    const manual = state.sortMode === "manual";
    v.miUp.hidden = v.miDown.hidden = v.miMoveHr.hidden = !manual;
  }

  /* ------------------------------------------------------------------ */
  /* Actions                                                            */
  /* ------------------------------------------------------------------ */

  function confirmKillConflict(app, c) {
    showConfirm(
      "Port is in use",
      "PID " + c.pid + " is listening on this app's port.\n\nCommand: " + (c.command || "unknown") + (c.cwd ? "\nFolder: " + c.cwd : "") +
        "\n\nKill that process and start " + app.name + "?",
      "Kill & start",
      () => runAction(app.id, "start", 1),
      "danger"
    );
  }

  // Apps the user just started: open them in a new tab as soon as they answer.
  const pendingOpen = new Map(); // id -> give-up time

  function watchToOpen(app) {
    if (loadPref("auto_open", "1") !== "1") return; // Settings → General
    if (!app || app.service || !(app.port || app.detected_port || app.command)) return;
    pendingOpen.set(app.id, Date.now() + 3 * 60 * 1000);
  }

  function openReadyApps() {
    if (!pendingOpen.size) return;
    const now = Date.now();
    for (const [id, until] of pendingOpen) {
      const app = findApp(id);
      if (!app || now > until || app.status === "stopped" || app.status === "crashed") {
        pendingOpen.delete(id);
      } else if (app.port_ready) {
        pendingOpen.delete(id);
        request("/api/apps/" + encodeURIComponent(id) + "/open", {
          method: "POST",
          body: JSON.stringify({ target: "app" }),
        }).catch(() => window.open(namedUrl(app), "_blank", "noopener"));
      }
    }
  }

  async function runAction(id, action, killConflict) {
    try {
      const query = killConflict ? "?kill_conflict=1" : "";
      const updated = await request("/api/apps/" + encodeURIComponent(id) + "/" + action + query, { method: "POST" });
      if (action === "start") watchToOpen(updated);
      replaceAppState(updated);
      const verb = { start: "Started", stop: "Stopped", restart: "Restarted" }[action] || action;
      toast(verb + " " + updated.name, "ok");
      return updated;
    } catch (err) {
      const d = err.data && err.data.detail;
      if (err.status === 409 && d && d.error === "port_in_use") {
        const cur = findApp(id);
        confirmKillConflict(cur || { id: id, name: id }, d);
      } else {
        toast("Couldn't " + action + ": " + err.message, "err");
      }
      return null;
    }
  }

  async function openInBrowser(id) {
    const cur = findApp(id);
    if (!cur) return;
    if (!isActive(cur)) {
      if (!cur.command) {
        toast(cur.name + " has no start command", "warn");
        return;
      }
      await runAction(id, "start"); // opens by itself once it's ready
    } else {
      openAppPath(id, "/");
    }
  }

  // Open a page of the app (named URL). The desktop app's web view can't open
  // new browser tabs itself, so there Homeport opens the browser; in a normal
  // browser a new tab is used, with Homeport as the fallback if it's blocked.
  function openAppPath(id, path) {
    const cur = findApp(id);
    if (!cur) return;
    const url = namedUrl(cur).replace(/\/$/, "") + (path || "/");
    const viaHomeport = () =>
      request("/api/apps/" + encodeURIComponent(id) + "/open", {
        method: "POST",
        body: JSON.stringify({ target: "app", path: path || "/" }),
      }).catch((err) => toast("Couldn't open it: " + err.message, "err"));
    if (window.pywebview) {
      viaHomeport();
      return;
    }
    const win = window.open(url, "_blank", "noopener");
    if (!win) viaHomeport();
  }

  async function openTarget(id, target) {
    try {
      await request("/api/apps/" + encodeURIComponent(id) + "/open", {
        method: "POST",
        body: JSON.stringify({ target: target }),
      });
    } catch (err) {
      toast("Couldn't open in " + target + ": " + err.message, "err");
    }
  }

  async function onDeleteApp(id) {
    try {
      await request("/api/apps/" + encodeURIComponent(id), { method: "DELETE" });
      state.apps = state.apps.filter((a) => a.id !== id);
      if (state.logsId === id) closeLogs();
      render();
      toast("App removed", "ok");
    } catch (err) {
      toast("Couldn't remove app: " + err.message, "err");
    }
  }

  async function bulk(path, okMsg) {
    closeMenus();
    try {
      updateAllApps(await request(path, { method: "POST" }));
      toast(okMsg, "ok");
    } catch (err) {
      toast("Failed: " + err.message, "err");
    }
  }

  els.btnBulk.addEventListener("click", () => toggleMenu(els.btnBulk, els.bulkMenu));
  els.btnStartAll.addEventListener("click", () => bulk("/api/apps/start-all", "Started all apps"));
  els.btnStopAll.addEventListener("click", () => bulk("/api/apps/stop-all", "Stopped all apps"));
  els.btnTerminateAll.addEventListener("click", () => {
    closeMenus();
    showConfirm(
      "Force-terminate all apps?",
      "Kills every registered app, plus any other process listening on their configured ports.",
      "Terminate all",
      () => bulk("/api/apps/terminate-all", "All apps terminated"),
      "danger"
    );
  });

  /* ------------------------------------------------------------------ */
  /* Manual ordering                                                    */
  /* ------------------------------------------------------------------ */

  async function setColor(id, color) {
    const app = findApp(id);
    if (!app || (app.color || "") === color) return;
    const prev = app.color || "";
    app.color = color; // optimistic
    render();
    try {
      replaceAppState(await request("/api/apps/" + encodeURIComponent(id), {
        method: "PATCH",
        body: JSON.stringify({ color: color }),
      }));
    } catch (err) {
      app.color = prev;
      render();
      toast("Couldn't set color: " + err.message, "err");
    }
  }

  async function saveOrder(ids, categoryPatch) {
    // Optimistic: reorder locally, then persist.
    const byId = new Map(state.apps.map((a) => [a.id, a]));
    state.apps = ids.map((i) => byId.get(i)).filter(Boolean);
    if (categoryPatch) {
      const app = byId.get(categoryPatch.id);
      if (app) app.category = categoryPatch.category;
    }
    render();
    try {
      if (categoryPatch) {
        const updated = await request("/api/apps/" + encodeURIComponent(categoryPatch.id), {
          method: "PATCH",
          body: JSON.stringify({ category: categoryPatch.category }),
        });
        replaceAppState(updated);
        toast("Moved " + updated.name + " to " + (categoryPatch.category || "Uncategorized"), "ok");
      }
      updateAllApps(await request("/api/apps/reorder", { method: "POST", body: JSON.stringify({ ids: ids }) }));
    } catch (err) {
      toast("Couldn't save order: " + err.message, "err");
      fetchApps();
    }
  }

  /** Put the visible ids (in their new on-screen order) back into the slots
   *  they occupied in the full list, so hidden/filtered apps don't move. */
  function mergeVisibleOrder(visibleIds) {
    const visible = new Set(visibleIds);
    const queue = visibleIds.slice();
    return state.apps.map((a) => (visible.has(a.id) ? queue.shift() : a.id));
  }

  function moveBy(id, delta) {
    const visibleIds = currentSequence().filter((n) => n.kind === "card").map((n) => n.id);
    const i = visibleIds.indexOf(id);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= visibleIds.length) return;
    visibleIds.splice(i, 1);
    visibleIds.splice(j, 0, id);
    saveOrder(mergeVisibleOrder(visibleIds));
  }

  /* Pointer drag-and-drop: grab a card anywhere (mouse/pen) or by its grip
     (touch), drop it at any position — other cards slide out of the way. */

  const DRAG_THRESHOLD = 6;
  const INTERACTIVE = "button, a, input, select, textarea, label, .menu, .share-bar, .card-alert";

  function onCardPointerDown(e, card, id, fromHandle) {
    if (state.drag || e.button !== 0) return;
    if (!fromHandle && e.pointerType === "touch") return; // touch: let the page scroll
    if (!fromHandle && e.target.closest(INTERACTIVE)) return;
    const startX = e.clientX;
    const startY = e.clientY;
    let started = false;

    const onMove = (ev) => {
      if (!started) {
        if (Math.hypot(ev.clientX - startX, ev.clientY - startY) < DRAG_THRESHOLD) return;
        started = true;
        beginDrag(card, id, startX, startY);
      }
      ev.preventDefault();
      dragTo(ev.clientX, ev.clientY);
    };
    const finish = (ev) => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", finish);
      window.removeEventListener("pointercancel", finish);
      if (started) endDrag(ev.type === "pointercancel");
    };
    window.addEventListener("pointermove", onMove, { passive: false });
    window.addEventListener("pointerup", finish);
    window.addEventListener("pointercancel", finish);
  }

  function beginDrag(card, id, x, y) {
    closeMenus();
    // Any sort order becomes the manual order, starting from what is on screen.
    if (state.sortMode !== "manual") {
      const visibleIds = currentSequence().filter((n) => n.kind === "card").map((n) => n.id);
      const byId = new Map(state.apps.map((a) => [a.id, a]));
      state.apps = mergeVisibleOrder(visibleIds).map((i) => byId.get(i));
      state.sortMode = "manual";
      savePref("sort", "manual");
      els.sortSelect.value = "manual";
      render();
    }
    const rect = card.getBoundingClientRect();
    const ghost = card.cloneNode(true);
    ghost.classList.add("drag-ghost");
    ghost.removeAttribute("data-id");
    Object.assign(ghost.style, {
      width: rect.width + "px",
      height: rect.height + "px",
      left: rect.left + "px",
      top: rect.top + "px",
    });
    document.body.appendChild(ghost);
    state.drag = {
      id: id, card: card, ghost: ghost,
      offX: x - rect.left, offY: y - rect.top,
      x: x, y: y, startOrder: Array.from(els.grid.children), scrollRaf: 0,
    };
    card.classList.add("dragging");
    document.body.classList.add("is-dragging");
    autoScrollLoop();
  }

  /** Move ``node`` before ``ref`` and let every other card glide (FLIP). */
  function moveWithAnimation(node, ref) {
    const items = Array.from(els.grid.children).filter((c) => c !== node);
    const first = new Map(items.map((c) => [c, c.getBoundingClientRect()]));
    els.grid.insertBefore(node, ref);
    for (const c of items) {
      const a = first.get(c);
      const b = c.getBoundingClientRect();
      const dx = a.left - b.left;
      const dy = a.top - b.top;
      if (dx || dy) {
        c.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
          { duration: 200, easing: "cubic-bezier(.2,.8,.2,1)" });
      }
    }
  }

  function dragTo(x, y) {
    const d = state.drag;
    if (!d) return;
    d.x = x;
    d.y = y;
    d.ghost.style.transform = `translate(${x - d.offX - parseFloat(d.ghost.style.left)}px, ${y - d.offY - parseFloat(d.ghost.style.top)}px) rotate(1.5deg) scale(1.03)`;

    const hit = document.elementFromPoint(x, y);
    const placeholder = d.card;
    let over = hit && hit.closest("#grid > .card, #grid > .group-head");
    if (!over) {
      // Empty space (end of a row, below a group …): use the nearest item.
      const gr = els.grid.getBoundingClientRect();
      if (x < gr.left - 60 || x > gr.right + 60 || y < gr.top - 60 || y > gr.bottom + 160) return;
      over = nearestGridItem(x, y);
      if (!over) return;
    }
    if (over === placeholder) return;
    if (over.classList.contains("group-head")) {
      // On a heading: first card of that group (or last of the previous one
      // when coming from below and still in the upper half).
      const r = over.getBoundingClientRect();
      if (y < r.top + r.height / 2 && over.previousElementSibling && over.previousElementSibling !== placeholder) {
        if (over.previousElementSibling !== placeholder) moveWithAnimation(placeholder, over);
      } else if (over.nextElementSibling !== placeholder) {
        moveWithAnimation(placeholder, over.nextElementSibling);
      }
      return;
    }
    const r = over.getBoundingClientRect();
    const after = state.viewMode === "grid"
      ? (y > r.bottom - r.height * 0.2) || (x > r.left + r.width / 2 && y > r.top + r.height * 0.2)
      : y > r.top + r.height / 2;
    const ref = after ? over.nextElementSibling : over;
    if (ref !== placeholder && placeholder.nextElementSibling !== ref) moveWithAnimation(placeholder, ref);
  }

  function nearestGridItem(x, y) {
    let best = null;
    let bestDist = Infinity;
    for (const c of els.grid.children) {
      const r = c.getBoundingClientRect();
      const dx = x < r.left ? r.left - x : x > r.right ? x - r.right : 0;
      const dy = y < r.top ? r.top - y : y > r.bottom ? y - r.bottom : 0;
      const dist = dx * dx + dy * dy * 4; // prefer the same row
      if (dist < bestDist) {
        bestDist = dist;
        best = c;
      }
    }
    return best;
  }

  function autoScrollLoop() {
    const d = state.drag;
    if (!d) return;
    const edge = 70;
    const h = window.innerHeight;
    let dy = 0;
    if (d.y < edge + 56) dy = -Math.ceil((edge + 56 - d.y) / 5);
    else if (d.y > h - edge) dy = Math.ceil((d.y - (h - edge)) / 5);
    if (dy) {
      window.scrollBy(0, dy);
      dragTo(d.x, d.y);
    }
    d.scrollRaf = requestAnimationFrame(autoScrollLoop);
  }

  function endDrag(cancelled) {
    const d = state.drag;
    if (!d) return;
    cancelAnimationFrame(d.scrollRaf);
    document.body.classList.remove("is-dragging");
    const card = d.card;

    if (cancelled) {
      d.startOrder.forEach((n) => els.grid.appendChild(n));
    }
    // Glide the ghost into the card's final slot, then reveal the card.
    const target = card.getBoundingClientRect();
    const g = d.ghost;
    const anim = g.animate(
      [{ transform: g.style.transform }, {
        transform: `translate(${target.left - parseFloat(g.style.left)}px, ${target.top - parseFloat(g.style.top)}px)`,
      }],
      { duration: 160, easing: "cubic-bezier(.2,.8,.2,1)", fill: "forwards" }
    );
    const cleanup = () => {
      g.remove();
      card.classList.remove("dragging");
    };
    anim.onfinish = cleanup;
    setTimeout(cleanup, 400);

    state.drag = null;
    if (cancelled) {
      render();
      return;
    }

    const visibleIds = Array.from(els.grid.querySelectorAll(".card")).map((c) => c.dataset.id);
    let categoryPatch = null;
    if (state.groupBy) {
      let prev = card.previousElementSibling;
      while (prev && !prev.classList.contains("group-head")) prev = prev.previousElementSibling;
      const app = findApp(d.id);
      if (prev && app) {
        const targetCat = prev.dataset.category === UNCATEGORIZED ? "" : prev.dataset.category;
        if (targetCat !== appCategory(app)) categoryPatch = { id: d.id, category: targetCat };
      }
    }
    const before = state.apps.map((a) => a.id).join("\n");
    const ids = mergeVisibleOrder(visibleIds);
    if (ids.join("\n") === before && !categoryPatch) {
      render();
      return;
    }
    saveOrder(ids, categoryPatch);
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.drag) {
      e.stopImmediatePropagation();
      endDrag(true);
    }
  }, true);

  /* ------------------------------------------------------------------ */
  /* Filtering, sorting, grouping                                       */
  /* ------------------------------------------------------------------ */

  els.statusBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeFilter = btn.dataset.filter || "all";
      els.statusBtns.forEach((b) => b.classList.toggle("active", b === btn));
      render();
    });
  });

  els.searchInput.addEventListener("input", (e) => {
    state.searchQuery = (e.target.value || "").trim().toLowerCase();
    render();
  });

  function setCategoryFilter(value) {
    state.categoryFilter = value === "" ? UNCATEGORIZED : value;
    savePref("category", state.categoryFilter);
    render();
  }

  els.categoryFilter.addEventListener("change", () => {
    state.categoryFilter = els.categoryFilter.value;
    savePref("category", state.categoryFilter);
    render();
  });

  els.sortSelect.value = state.sortMode;
  els.sortSelect.addEventListener("change", () => {
    state.sortMode = els.sortSelect.value;
    savePref("sort", state.sortMode);
    render();
  });

  els.btnGroup.addEventListener("click", () => {
    state.groupBy = !state.groupBy;
    savePref("group", state.groupBy ? "1" : "0");
    render();
  });

  icon(els.viewBtns[0], "grid");
  icon(els.viewBtns[1], "list");
  els.viewBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      state.viewMode = btn.dataset.view === "list" ? "list" : "grid";
      savePref("view", state.viewMode);
      render();
    });
  });

  function matches(app) {
    if (state.activeFilter !== "all") {
      if (state.activeFilter === "running") {
        if (!isActive(app)) return false;
      } else if (app.status !== state.activeFilter) {
        return false;
      }
    }
    if (state.categoryFilter) {
      const cat = appCategory(app);
      if (state.categoryFilter === UNCATEGORIZED ? cat !== "" : cat !== state.categoryFilter) return false;
    }
    if (state.searchQuery) {
      const q = state.searchQuery;
      const hay = [app.name, app.path, app.command, app.description, app.category, String(appPort(app) || "")]
        .join("\n")
        .toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }

  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
  const STATUS_RANK = { running: 0, starting: 1, crashed: 2, stopped: 3 };

  // Missing values always sort last, whatever the direction.
  function byNumber(get, desc) {
    return (a, b) => {
      const x = get(a);
      const y = get(b);
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      return desc ? y - x : x - y;
    };
  }

  function comparator(mode) {
    const name = (a, b) => collator.compare(a.name || "", b.name || "");
    switch (mode) {
      case "name-asc": return name;
      case "name-desc": return (a, b) => name(b, a);
      case "path": return (a, b) => collator.compare(a.path || "", b.path || "") || name(a, b);
      case "created-desc": return byNumber((a) => a.created_at, true);
      case "created-asc": return byNumber((a) => a.created_at, false);
      case "updated-desc": return byNumber((a) => a.updated_at, true);
      case "status": return (a, b) => (STATUS_RANK[a.status] ?? 9) - (STATUS_RANK[b.status] ?? 9) || name(a, b);
      case "port": return byNumber(appPort, false);
      case "mem": return byNumber((a) => (isActive(a) ? a.mem_mb : null), true);
      default: return null; // manual: server order
    }
  }

  function sortedVisible() {
    const list = state.apps.filter(matches);
    const cmp = comparator(state.sortMode);
    // Array.prototype.sort is stable, so ties keep manual order.
    return cmp ? list.sort(cmp) : list;
  }

  /** The ordered list of nodes to show: group headers and cards. */
  function currentSequence() {
    const apps = sortedVisible();
    if (!state.groupBy) return apps.map((a) => ({ kind: "card", id: a.id, app: a }));

    const groups = new Map();
    for (const app of apps) {
      const key = appCategory(app) || UNCATEGORIZED;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(app);
    }
    const keys = Array.from(groups.keys()).sort((a, b) => {
      if (a === UNCATEGORIZED) return 1;
      if (b === UNCATEGORIZED) return -1;
      return collator.compare(a, b);
    });
    const seq = [];
    for (const key of keys) {
      seq.push({ kind: "head", key: key, count: groups.get(key).length });
      for (const app of groups.get(key)) seq.push({ kind: "card", id: app.id, app: app });
    }
    return seq;
  }

  function groupHead(key, count) {
    let h = state.groupHeads.get(key);
    if (!h) {
      h = el("div", "group-head");
      h.dataset.category = key;
      h.appendChild(el("span", "group-name"));
      h.appendChild(el("span", "count"));
      const tools = el("span", "group-tools");
      const cat = key === UNCATEGORIZED ? "" : key;
      const play = icon(button("group-btn", null, "Start this group in order"), "play");
      play.title = "Start all — one after another, in your order";
      play.addEventListener("click", () => groupAction(cat, "start"));
      const stop = icon(button("group-btn", null, "Stop this group"), "stop");
      stop.title = "Stop all in this group";
      stop.addEventListener("click", () => groupAction(cat, "stop"));
      tools.appendChild(play);
      tools.appendChild(stop);
      h.appendChild(tools);
      state.groupHeads.set(key, h);
    }
    const anyCategory = state.apps.some((a) => appCategory(a));
    h.firstChild.textContent = key === UNCATEGORIZED ? (anyCategory ? "Other" : "All apps") : key;
    h.children[1].textContent = String(count);
    return h;
  }

  function renderCategoryControls() {
    const cats = Array.from(new Set(state.apps.map(appCategory).filter(Boolean))).sort(collator.compare);
    const hasUncat = state.apps.some((a) => !appCategory(a));

    // Drop a saved filter whose category no longer exists.
    if (state.categoryFilter && state.categoryFilter !== UNCATEGORIZED && !cats.includes(state.categoryFilter) && state.apps.length) {
      state.categoryFilter = "";
      savePref("category", "");
    }

    const wanted = [["", "All"]].concat(cats.map((c) => [c, c]));
    if (hasUncat && cats.length) wanted.push([UNCATEGORIZED, "Uncategorized"]);
    if (state.categoryFilter === UNCATEGORIZED && !wanted.some((w) => w[0] === UNCATEGORIZED)) {
      wanted.push([UNCATEGORIZED, "Uncategorized"]);
    }
    const sig = wanted.map((w) => w[0]).join("\n");
    if (els.categoryFilter.dataset.sig !== sig) {
      els.categoryFilter.textContent = "";
      for (const [value, label] of wanted) {
        const opt = el("option", null, label);
        opt.value = value;
        els.categoryFilter.appendChild(opt);
      }
      els.categoryFilter.dataset.sig = sig;

      els.categoryList.textContent = "";
      for (const c of cats) {
        const opt = document.createElement("option");
        opt.value = c;
        els.categoryList.appendChild(opt);
      }
    }
    els.categoryFilter.value = state.categoryFilter;
    renderCategoryNav(wanted);
  }

  function renderCategoryNav(wanted) {
    const counts = new Map();
    for (const app of state.apps) {
      const key = appCategory(app) || UNCATEGORIZED;
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    const sig = wanted.map((w) => w[0] + "=" + (w[0] ? counts.get(w[0]) || 0 : state.apps.length)).join("\n") + "|" + state.categoryFilter;
    if (els.catNav.dataset.sig === sig) return;
    els.catNav.dataset.sig = sig;
    els.catNav.textContent = "";
    for (const [value, label] of wanted) {
      const b = button("cat-item" + (state.categoryFilter === value ? " active" : ""), null);
      b.appendChild(el("span", "cat-box"));
      b.appendChild(el("span", "cat-name", value === "" ? "All categories" : label));
      b.appendChild(el("span", "count", String(value === "" ? state.apps.length : counts.get(value) || 0)));
      b.setAttribute("aria-pressed", String(state.categoryFilter === value));
      b.addEventListener("click", () => {
        state.categoryFilter = value;
        savePref("category", value);
        render();
      });
      els.catNav.appendChild(b);
    }
    if (wanted.length <= 1) {
      els.catNav.appendChild(el("p", "cat-hint", "Give apps a category in Edit to group them here."));
    }
  }

  /* ------------------------------------------------------------------ */
  /* Render                                                             */
  /* ------------------------------------------------------------------ */

  function replaceAppState(updated) {
    const idx = state.apps.findIndex((a) => a.id === updated.id);
    if (idx >= 0) state.apps[idx] = updated;
    else state.apps.push(updated);
    render();
    openReadyApps();
  }

  function updateAllApps(apps) {
    state.apps = Array.isArray(apps) ? apps : [];
    render();
    openReadyApps();
  }

  function renderSummary() {
    let running = 0;
    let stopped = 0;
    let crashed = 0;
    let mem = 0;
    let cpu = 0;
    for (const app of state.apps) {
      if (isActive(app)) running++;
      else if (app.status === "crashed") crashed++;
      else stopped++;
      if (typeof app.mem_mb === "number" && isFinite(app.mem_mb)) mem += app.mem_mb;
      if (typeof app.cpu_percent === "number" && isFinite(app.cpu_percent)) cpu += app.cpu_percent;
    }
    els.countAll.textContent = String(state.apps.length);
    els.countRunning.textContent = String(running);
    els.countStopped.textContent = String(stopped);
    els.countCrashed.textContent = String(crashed);

    const total = state.apps.length;
    const parts = [total + (total === 1 ? " app" : " apps"), running + " running"];
    if (crashed) parts.push(crashed + " crashed");
    if (running) parts.push(formatMb(mem) + " · " + cpu.toFixed(1) + "% CPU");
    els.summary.textContent = parts.join(" · ");

    const shared = state.apps.filter((a) => a.share && a.share.status === "live").length;
    const setText = (elId, text) => {
      const node = document.getElementById(elId);
      if (node && node.textContent !== text) node.textContent = text;
    };
    setText("pill-running", String(running));
    setText("kpi-apps", String(total));
    setText("kpi-running", String(running));
    setText("kpi-shared", String(shared));
    setText("kpi-mem", mem >= 1024 ? (mem / 1024).toFixed(1) + " GB" : Math.round(mem) + " MB");
  }

  function render() {
    renderSummary();
    renderCategoryControls();

    els.sortSelect.value = state.sortMode;
    els.btnGroup.setAttribute("aria-pressed", String(state.groupBy));
    els.viewBtns.forEach((b) => b.classList.toggle("active", b.dataset.view === state.viewMode));
    els.grid.className = "apps " + state.viewMode + "-view" + (state.sortMode === "manual" ? " can-drag" : "");

    // Drop views for apps that no longer exist.
    const ids = new Set(state.apps.map((a) => a.id));
    for (const [id, view] of state.views) {
      if (!ids.has(id)) {
        view.el.remove();
        state.views.delete(id);
      }
    }

    for (const app of state.apps) {
      let view = state.views.get(app.id);
      if (!view) {
        view = createCard(app);
        state.views.set(app.id, view);
      }
      updateCard(view, app);
    }

    if (typeof phone !== "undefined" && phone.appId) renderPhoneDialog();
    if (typeof cmdk !== "undefined" && cmdk && !cmdk.backdrop.hidden) {
      // Refresh open palette only when something it shows has changed.
      const sig = state.apps.map((a) => a.id + ":" + a.status + ":" + Boolean(a.share) + ":" + Boolean(a.git)).join("|");
      if (sig !== cmdk.sig) {
        cmdk.sig = sig;
        renderPalette();
      }
    }

    // While dragging, the DOM order *is* the pending order — leave it alone.
    if (state.drag) return;

    const seq = currentSequence();
    const nodes = seq.map((n) => (n.kind === "head" ? groupHead(n.key, n.count) : state.views.get(n.id).el));
    const keep = new Set(nodes);
    Array.from(els.grid.children).forEach((child) => {
      if (!keep.has(child)) child.remove();
    });
    nodes.forEach((node, i) => {
      if (els.grid.children[i] !== node) els.grid.insertBefore(node, els.grid.children[i] || null);
    });

    const empty = nodes.length === 0;
    els.empty.hidden = !empty;
    if (empty) {
      const none = state.apps.length === 0;
      els.emptyTitle.textContent = none ? "No apps yet" : "Nothing matches";
      els.emptyText.textContent = none
        ? "Add a local project to start, stop and monitor it from here."
        : "Try a different search, status or category.";
    }
  }

  /* ------------------------------------------------------------------ */
  /* Sharing (public links through Cloudflare Tunnel)                    */
  /* ------------------------------------------------------------------ */

  const share = { appId: null, status: null };

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast("Link copied", "ok");
    } catch (e) {
      window.prompt("Copy this link:", text);
    }
  }

  function renderShareDialog() {
    const st = share.status || { cloudflared: false };
    els.shareInstall.hidden = Boolean(st.cloudflared);
    els.shareStart.disabled = !st.cloudflared;
  }

  async function openShare(app) {
    share.appId = app.id;
    els.shareTitle.textContent = "Share “" + app.name + "”";
    els.sharePassword.value = "";
    els.shareFeedback.checked = loadPref("share_feedback", "0") === "1";
    els.shareExpiry.value = loadPref("share_expiry", "60"); // Settings → Sharing & feedback
    els.shareBackdrop.hidden = false;
    try {
      share.status = await request("/api/share/status");
    } catch (err) {
      toast("Couldn't check sharing: " + err.message, "err");
    }
    renderShareDialog();
  }

  function hideShare() {
    els.shareBackdrop.hidden = true;
    share.appId = null;
  }

  async function startShare() {
    const id = share.appId;
    const password = els.sharePassword.value.trim();
    if (password && password.length < 4) {
      toast("Use a password of at least 4 characters", "err");
      return;
    }
    els.shareStart.disabled = true;
    try {
      await request("/api/apps/" + encodeURIComponent(id) + "/share", {
        method: "POST",
        body: JSON.stringify({
          password: password || null,
          expires_minutes: Number(els.shareExpiry.value) || null,
          feedback: els.shareFeedback.checked,
        }),
      });
      savePref("share_feedback", els.shareFeedback.checked ? "1" : "0");
      hideShare();
      toast(password ? "Creating a password-protected link…" : "Creating a public link…", "ok");
      fetchApps();
    } catch (err) {
      toast("Couldn't share: " + err.message, "err");
    } finally {
      els.shareStart.disabled = false;
    }
  }

  async function stopShare(id) {
    try {
      await request("/api/apps/" + encodeURIComponent(id) + "/share", { method: "DELETE" });
      toast("Stopped sharing", "ok");
      fetchApps();
    } catch (err) {
      toast("Couldn't stop sharing: " + err.message, "err");
    }
  }

  async function setShareFeedback(id, on) {
    try {
      await request("/api/apps/" + encodeURIComponent(id) + "/share", { method: "PATCH", body: JSON.stringify({ feedback: on }) });
      toast(on ? "Visitors can now leave feedback (same link)" : "Feedback turned off for this link", "ok");
      fetchApps();
      if (fb.appId === id) renderFeedback();
    } catch (err) {
      toast("Couldn't change feedback: " + err.message, "err");
    }
  }

  /* ------------------------------------------------------------------ */
  /* Feedback from visitors (notes left on a shared link)                */
  /* ------------------------------------------------------------------ */

  const fb = { appId: null, items: [], filter: "open", timer: null, loading: false };

  function timeAgo(ts) {
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + " min ago";
    if (s < 86400) return Math.floor(s / 3600) + " h ago";
    if (s < 86400 * 7) return Math.floor(s / 86400) + " d ago";
    return new Date(ts * 1000).toLocaleDateString();
  }

  async function loadFeedback() {
    if (!fb.appId || fb.loading) return;
    fb.loading = true;
    try {
      const data = await request("/api/apps/" + encodeURIComponent(fb.appId) + "/feedback");
      fb.items = data.items || [];
    } catch (err) {
      toast("Couldn't load feedback: " + err.message, "err");
    } finally {
      fb.loading = false;
    }
    renderFeedback();
  }

  function renderFeedback() {
    const app = findApp(fb.appId);
    if (!app) return;
    $("fb-title").textContent = "Feedback for “" + app.name + "”";
    $("fb-filter").querySelectorAll("button").forEach((b) => {
      const n = fb.items.filter((i) => b.dataset.filter === "all" || i.status === b.dataset.filter).length;
      b.textContent = { open: "Open", resolved: "Resolved", all: "All" }[b.dataset.filter] + " " + n;
      b.classList.toggle("active", b.dataset.filter === fb.filter);
    });
    const shareState = $("fb-share-state");
    if (app.share && app.share.feedback) shareState.textContent = "Visitors can leave feedback on the public link now.";
    else if (app.share) shareState.textContent = "Shared, but feedback is off — turn it on from the link bar on the card.";
    else shareState.textContent = "Share the app with “Let visitors leave feedback” to collect notes.";
    $("fb-clear").hidden = !fb.items.some((i) => i.status === "resolved");

    const body = $("fb-body");
    body.textContent = "";
    const shown = fb.items.filter((i) => fb.filter === "all" || i.status === fb.filter);
    if (!shown.length) {
      const empty = el("div", "fb-empty");
      empty.appendChild(el("b", null, fb.filter === "resolved" ? "Nothing resolved yet" : "No feedback here yet"));
      empty.appendChild(el("p", "hint", "When you share this app with feedback on, visitors get a Feedback button on the pages. They click a spot and write a note, and it shows up here."));
      body.appendChild(empty);
      return;
    }
    shown.forEach((item) => body.appendChild(feedbackRow(app, item)));
  }

  function feedbackRow(app, item) {
    const row = el("div", "fb-item" + (item.status === "resolved" ? " resolved" : ""));
    row.appendChild(el("p", "fb-msg", item.message));
    const meta = el("div", "fb-meta");
    meta.appendChild(el("b", null, item.name || "Anonymous"));
    meta.appendChild(el("span", null, timeAgo(item.created_at || 0)));
    const pageText = item.page || "/";
    const page = el("code", null, pageText.length > 48 ? pageText.slice(0, 47) + "…" : pageText);
    page.title = item.url || pageText;
    meta.appendChild(page);
    if (item.vw) meta.appendChild(el("span", null, Math.round(item.vw) + "×" + Math.round(item.vh || 0) + (item.vw < 700 ? " · phone" : "")));
    if (!item.selector && item.xp == null) meta.appendChild(el("span", null, "general note"));
    if (item.source === "local") meta.appendChild(el("span", null, "added by you"));
    row.appendChild(meta);

    // the thread: replies from visitors and from you
    (item.replies || []).forEach((r) => {
      const line = el("div", "fb-reply");
      line.appendChild(el("b", null, (r.name || "Anonymous") + (r.source === "local" ? " (you)" : "")));
      line.appendChild(el("span", "fb-reply-time", timeAgo(r.created_at || 0)));
      line.appendChild(el("p", null, r.message));
      row.appendChild(line);
    });
    const replyForm = el("form", "fb-reply-form");
    const replyInput = el("input", "input small");
    replyInput.placeholder = "Reply…";
    replyInput.maxLength = 2000;
    const replyBtn = button("btn small", "Reply");
    replyBtn.type = "submit";
    replyForm.append(replyInput, replyBtn);
    replyForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const message = replyInput.value.trim();
      if (!message) return;
      replyBtn.disabled = true;
      try {
        const reply = await request("/api/apps/" + encodeURIComponent(app.id) + "/feedback/" + item.id + "/reply", {
          method: "POST",
          body: JSON.stringify({ message: message, name: loadPref("fb_owner_name", "") || "Owner" }),
        });
        item.replies = (item.replies || []).concat([reply]);
        renderFeedback();
      } catch (err) {
        toast(err.message, "err");
        replyBtn.disabled = false;
      }
    });
    row.appendChild(replyForm);

    const actions = el("div", "fb-actions");
    const show = button("btn small", "Show on page");
    show.title = "Open this page with the note pinned on it";
    show.addEventListener("click", () => viewWithFeedback(app, item.page || "/", item.id));
    const flip = button("btn small" + (item.status === "open" ? " primary" : ""), item.status === "open" ? "Resolve" : "Reopen");
    flip.addEventListener("click", async () => {
      flip.disabled = true;
      try {
        const upd = await request("/api/apps/" + encodeURIComponent(app.id) + "/feedback/" + item.id, {
          method: "PATCH",
          body: JSON.stringify({ status: item.status === "open" ? "resolved" : "open" }),
        });
        item.status = upd.status;
        renderFeedback();
        fetchApps();
      } catch (err) {
        toast(err.message, "err");
        flip.disabled = false;
      }
    });
    const del = button("btn small ghost", "Delete");
    del.addEventListener("click", async () => {
      if (del.dataset.armed !== "1") {
        del.dataset.armed = "1";
        del.textContent = "Delete?";
        window.setTimeout(() => {
          del.dataset.armed = "";
          del.textContent = "Delete";
        }, 3000);
        return;
      }
      try {
        await request("/api/apps/" + encodeURIComponent(app.id) + "/feedback/" + item.id, { method: "DELETE" });
        fb.items = fb.items.filter((i) => i.id !== item.id);
        renderFeedback();
        fetchApps();
      } catch (err) {
        toast(err.message, "err");
      }
    });
    actions.append(show, flip, del);
    row.appendChild(actions);
    return row;
  }

  // The site with notes pinned on it (review mode), or the plain site.
  function viewWithFeedback(app, page, pin) {
    if (!isActive(app)) {
      toast("Start " + app.name + " first", "warn");
      return;
    }
    let path = "/__homeport/fb/review?on=1&to=" + encodeURIComponent(page || "/");
    if (pin) path += "&pin=" + encodeURIComponent(pin);
    openAppPath(app.id, path);
  }

  function viewWithoutFeedback(app) {
    if (!isActive(app)) {
      toast("Start " + app.name + " first", "warn");
      return;
    }
    openAppPath(app.id, "/__homeport/fb/review?on=0&to=%2F");
  }

  async function openFeedback(app) {
    fb.appId = app.id;
    fb.items = [];
    fb.filter = "open";
    $("fb-backdrop").hidden = false;
    renderFeedback();
    await loadFeedback();
    if (fb.items.length && !fb.items.some((i) => i.status === "open")) {
      fb.filter = "all";
      renderFeedback();
    }
    window.clearInterval(fb.timer);
    fb.timer = window.setInterval(loadFeedback, 5000); // new notes from visitors
  }

  function hideFeedback() {
    $("fb-backdrop").hidden = true;
    fb.appId = null;
    window.clearInterval(fb.timer);
    fb.timer = null;
  }

  $("fb-close").addEventListener("click", hideFeedback);
  $("fb-backdrop").addEventListener("mousedown", (e) => {
    if (e.target === $("fb-backdrop")) hideFeedback();
  });
  $("fb-filter").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-filter]");
    if (!b) return;
    fb.filter = b.dataset.filter;
    renderFeedback();
  });
  $("fb-view-on").addEventListener("click", () => {
    const app = findApp(fb.appId);
    if (app) viewWithFeedback(app, "/", null);
  });
  $("fb-view-off").addEventListener("click", () => {
    const app = findApp(fb.appId);
    if (app) viewWithoutFeedback(app);
  });
  $("fb-clear").addEventListener("click", async () => {
    const id = fb.appId;
    try {
      await request("/api/apps/" + encodeURIComponent(id) + "/feedback?status=resolved", { method: "DELETE" });
      await loadFeedback();
      fetchApps();
    } catch (err) {
      toast(err.message, "err");
    }
  });

  els.shareClose.addEventListener("click", hideShare);
  els.shareCancel.addEventListener("click", hideShare);
  els.shareStart.addEventListener("click", startShare);
  els.sharePassword.addEventListener("keydown", (e) => {
    if (e.key === "Enter") startShare();
  });
  els.shareInstallBtn.addEventListener("click", async () => {
    els.shareInstallBtn.disabled = true;
    els.shareInstallBtn.textContent = "Installing…";
    try {
      share.status = await request("/api/share/install", { method: "POST" });
      toast("Cloudflare Tunnel installed", "ok");
      renderShareDialog();
    } catch (err) {
      toast("Install failed: " + err.message, "err");
    } finally {
      els.shareInstallBtn.disabled = false;
      els.shareInstallBtn.textContent = "Install";
    }
  });

  function timeLeft(expiresAt) {
    const s = Math.max(0, Math.round(expiresAt - Date.now() / 1000));
    if (s >= 3600) return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
    if (s >= 60) return Math.floor(s / 60) + "m";
    return s + "s";
  }

  /* ------------------------------------------------------------------ */
  /* Phone preview (Wi-Fi link + QR codes)                              */
  /* ------------------------------------------------------------------ */

  var phone = { appId: null }; // var: render() may run before this line
  const qrUrl = (text) => apiUrl("/api/qr?text=" + encodeURIComponent(text));

  function renderPhoneDialog() {
    const app = findApp(phone.appId);
    if (!app) return;
    const lan = app.lan;
    $("phone-lan-body").hidden = !(lan && lan.url);
    const toggle = $("phone-lan-toggle");
    toggle.textContent = lan ? "Turn off" : "Turn on";
    toggle.className = "btn small" + (lan ? "" : " primary");
    toggle.disabled = !lan && !isActive(app);
    toggle.title = !lan && !isActive(app) ? "Start the app first" : "";
    if (lan && lan.url) {
      const link = $("phone-lan-url");
      if (link.textContent !== lan.url) {
        link.textContent = lan.url;
        link.href = lan.url;
        $("phone-lan-qr").src = qrUrl(lan.url);
      }
    }
    const pub = app.share && app.share.status === "live" && app.share.url;
    $("phone-public-body").hidden = !pub;
    $("phone-public-hint").textContent = pub
      ? (app.share.protected ? "Password-protected public link." : "Public link — works on any network.")
      : "Share the app first to get a public link.";
    if (pub) {
      const link = $("phone-public-url");
      if (link.textContent !== app.share.url) {
        link.textContent = app.share.url;
        link.href = app.share.url;
        $("phone-public-qr").src = qrUrl(app.share.url);
      }
    }
  }

  function openPhone(app) {
    phone.appId = app.id;
    $("phone-title").textContent = "Open “" + app.name + "” on your phone";
    $("phone-lan-url").textContent = "";
    $("phone-public-url").textContent = "";
    $("phone-backdrop").hidden = false;
    renderPhoneDialog();
  }

  function hidePhone() {
    $("phone-backdrop").hidden = true;
    phone.appId = null;
  }

  $("phone-close").addEventListener("click", hidePhone);
  $("phone-lan-toggle").addEventListener("click", async () => {
    const app = findApp(phone.appId);
    if (!app) return;
    try {
      const path = "/api/apps/" + encodeURIComponent(app.id) + "/lan";
      await request(path, { method: app.lan ? "DELETE" : "POST" });
      await fetchApps();
      renderPhoneDialog();
    } catch (err) {
      toast("Wi-Fi preview: " + err.message, "err");
    }
  });

  /* ------------------------------------------------------------------ */
  /* Crash diagnosis & one-click fixes                                   */
  /* ------------------------------------------------------------------ */

  const diag = { appId: null, data: null };

  function renderDiag() {
    const list = $("diag-list");
    list.textContent = "";
    const data = diag.data;
    if (!data) {
      list.appendChild(el("p", "hint", "Reading the logs…"));
      return;
    }
    for (const f of data.findings) {
      const item = el("div", "diag-item");
      item.appendChild(el("strong", null, f.title));
      item.appendChild(el("p", null, f.detail));
      if (f.evidence) item.appendChild(el("code", "diag-evidence", f.evidence));
      if (f.fixes && f.fixes.length) {
        const row = el("div", "diag-fixes");
        for (const fix of f.fixes) {
          const b = button("btn small" + (fix.action === "edit" ? "" : " primary"), fix.label);
          b.dataset.action = fix.action;
          b.addEventListener("click", () => runFix(fix.action, b));
          row.appendChild(b);
        }
        item.appendChild(row);
      }
      list.appendChild(item);
    }
    $("diag-ai").hidden = false; // Claude Code or the local model (set up on first use)
  }

  async function openDiagnose(app) {
    diag.appId = app.id;
    diag.data = null;
    $("diag-title").textContent = "Why did “" + app.name + "” stop?";
    $("diag-backdrop").hidden = false;
    renderDiag();
    try {
      diag.data = await request("/api/apps/" + encodeURIComponent(app.id) + "/diagnose");
    } catch (err) {
      diag.data = { findings: [{ title: "Couldn't read the logs", detail: err.message, fixes: [] }], ai_available: false };
    }
    renderDiag();
  }

  function hideDiag() {
    $("diag-backdrop").hidden = true;
    diag.appId = null;
  }

  async function runFix(action, btn) {
    const app = findApp(diag.appId);
    if (!app) return;
    if (action === "edit") {
      hideDiag();
      openEditModal(app);
      return;
    }
    if (action.indexOf("service:") === 0) {
      hideDiag();
      addService(action.slice("service:".length));
      return;
    }
    if (action === "free_port") {
      hideDiag();
      if (app.port_conflict) confirmKillConflict(app, app.port_conflict);
      else runAction(app.id, "start", true);
      return;
    }
    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Working…";
    try {
      const res = await request("/api/apps/" + encodeURIComponent(app.id) + "/fix", {
        method: "POST",
        body: JSON.stringify({ action: action }),
      });
      toast(res.ok ? "Done — try starting it again" : "The fix reported a problem — see the logs", res.ok ? "ok" : "warn");
      btn.textContent = res.ok ? "Done ✓" : "Failed";
    } catch (err) {
      toast("Fix failed: " + err.message, "err");
      btn.textContent = label;
      btn.disabled = false;
    }
  }

  $("diag-close").addEventListener("click", hideDiag);
  $("diag-logs").addEventListener("click", () => {
    const app = findApp(diag.appId);
    hideDiag();
    if (app) openLogs(app);
  });
  $("diag-retry").addEventListener("click", () => {
    const id = diag.appId;
    hideDiag();
    if (id) runAction(id, "start");
  });
  $("diag-ai").addEventListener("click", () => {
    const app = findApp(diag.appId);
    const data = diag.data;
    hideDiag();
    if (!app || !data) return;
    const lines = (data.log_tail || []).slice(-30).join("\n");
    const prompt = "My app \"" + app.name + "\" (" + app.path + ") crashed. Its start command is `" + app.command +
      "`. Here are the last log lines:\n```\n" + lines + "\n```\nExplain why it crashed and fix it.";
    openAi();
    ai.appId = app.id; // lets the local model start from Homeport's own crash check
    ai.input.value = prompt;
    ai.input.focus();
  });

  /* ------------------------------------------------------------------ */
  /* Discover projects in a folder                                       */
  /* ------------------------------------------------------------------ */

  const disc = { projects: [] };

  function renderDisc() {
    const list = $("disc-list");
    list.textContent = "";
    for (const p of disc.projects) {
      const row = el("label", "disc-item" + (p.registered ? " added" : ""));
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.disabled = p.registered;
      cb.checked = !p.registered && p.checked !== false;
      cb.addEventListener("change", () => {
        p.checked = cb.checked;
        updateDiscButton();
      });
      p.checked = cb.checked;
      row.appendChild(cb);
      const text = el("span", "disc-text");
      text.appendChild(el("strong", null, p.name));
      text.appendChild(el("span", "muted", (p.type || "Project") + " · " + shortPath(p.path)));
      row.appendChild(text);
      row.appendChild(el("span", "disc-tag", p.registered ? "Added" : p.port ? ":" + p.port : ""));
      list.appendChild(row);
    }
    updateDiscButton();
  }

  function updateDiscButton() {
    const n = disc.projects.filter((p) => p.checked && !p.registered).length;
    $("disc-add").disabled = n === 0;
    $("disc-add").textContent = n ? "Add " + n + (n === 1 ? " app" : " apps") : "Add apps";
  }

  async function scanFolder() {
    const path = $("disc-path").value.trim();
    if (!path) return;
    const list = $("disc-list");
    list.textContent = "";
    list.appendChild(el("p", "hint", "Scanning…"));
    try {
      const res = await request("/api/discover", { method: "POST", body: JSON.stringify({ path: path }) });
      disc.projects = res.projects;
      if (!disc.projects.length) {
        list.textContent = "";
        list.appendChild(el("p", "hint", "No projects found in this folder."));
        updateDiscButton();
        return;
      }
      renderDisc();
    } catch (err) {
      list.textContent = "";
      list.appendChild(el("p", "hint", "Couldn't scan: " + err.message));
    }
  }

  function openDiscover() {
    $("disc-backdrop").hidden = false;
    $("disc-path").focus();
  }

  function hideDiscover() {
    $("disc-backdrop").hidden = true;
  }

  $("btn-discover").addEventListener("click", openDiscover);
  $("btn-quit").addEventListener("click", () => quitHomeport());
  $("btn-cmdk").addEventListener("click", () => openPalette());
  $("disc-close").addEventListener("click", hideDiscover);
  $("disc-cancel").addEventListener("click", hideDiscover);
  $("disc-scan").addEventListener("click", scanFolder);
  $("disc-path").addEventListener("keydown", (e) => {
    if (e.key === "Enter") scanFolder();
  });
  $("disc-browse").addEventListener("click", async () => {
    try {
      const res = await request("/api/pick-folder", { method: "POST" });
      if (res.path) {
        $("disc-path").value = res.path;
        scanFolder();
      }
    } catch (err) {
      toast("Type the folder path instead (" + err.message + ")", "warn");
    }
  });
  $("disc-all").addEventListener("change", (e) => {
    disc.projects.forEach((p) => {
      if (!p.registered) p.checked = e.target.checked;
    });
    renderDisc();
  });
  $("disc-add").addEventListener("click", async () => {
    const chosen = disc.projects.filter((p) => p.checked && !p.registered);
    $("disc-add").disabled = true;
    let added = 0;
    for (const p of chosen) {
      try {
        // Let the server pick a free port and the matching command.
        await request("/api/apps", { method: "POST", body: JSON.stringify({ name: p.name, path: p.path }) });
        added++;
      } catch (err) {
        toast(p.name + ": " + err.message, "err");
      }
    }
    toast("Added " + added + (added === 1 ? " app" : " apps"), "ok");
    hideDiscover();
    fetchApps();
  });

  /* ------------------------------------------------------------------ */
  /* Databases & services                                                */
  /* ------------------------------------------------------------------ */

  function envText(service) {
    return Object.entries(service.env || {}).map(([k, v]) => k + "=" + v).join("\n") + "\n";
  }

  async function addService(kind) {
    try {
      const st = await request("/api/services", { method: "POST", body: JSON.stringify({ kind: kind }) });
      replaceAppState(st);
      toast("Added " + st.name + " — " + (st.service ? st.service.url : "starting…"), "ok");
      return st;
    } catch (err) {
      toast("Couldn't add the service: " + err.message, "err");
      return null;
    }
  }

  async function openServices() {
    $("svc-backdrop").hidden = false;
    const list = $("svc-list");
    list.textContent = "";
    list.appendChild(el("p", "hint", "Checking what's installed…"));
    let data;
    try {
      data = await request("/api/services");
    } catch (err) {
      list.textContent = "";
      list.appendChild(el("p", "hint", "Couldn't load services: " + err.message));
      return;
    }
    list.textContent = "";
    for (const svc of data.services) {
      const row = el("div", "svc-item");
      const text = el("div", "svc-text");
      text.appendChild(el("strong", null, svc.name));
      text.appendChild(el("span", "muted", svc.description + " · port " + svc.port));
      const ready = svc.native || svc.docker;
      const chip = el("span", "svc-chip" + (ready ? " ok" : ""), svc.native ? "Installed" : svc.docker ? "Via Docker" : "Not installed");
      text.appendChild(chip);
      if (!ready) text.appendChild(el("code", "svc-install", svc.install));
      row.appendChild(text);
      const btn = button("btn small" + (ready ? " primary" : ""), "Add");
      btn.disabled = !ready;
      btn.title = ready ? "Add and start " + svc.name : "Install it (or Docker) first";
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Adding…";
        const st = await addService(svc.kind);
        btn.textContent = st ? "Added ✓" : "Add";
        btn.disabled = Boolean(st);
      });
      row.appendChild(btn);
      list.appendChild(row);
    }
  }

  function hideServices() {
    $("svc-backdrop").hidden = true;
  }

  $("btn-services").addEventListener("click", openServices);
  $("svc-close").addEventListener("click", hideServices);

  /* ------------------------------------------------------------------ */
  /* WordPress mode                                                      */
  /* ------------------------------------------------------------------ */

  const wp = { appId: null, info: null };

  function renderWordPress() {
    const info = wp.info;
    const steps = $("wp-steps");
    steps.textContent = "";
    const warn = $("wp-warn");
    warn.hidden = true;
    if (!info) {
      steps.appendChild(el("li", "hint", "Checking…"));
      return;
    }
    const svc = info.service_id ? findApp(info.service_id) : null;
    const items = [
      [Boolean(svc), svc ? "Database: " + svc.name + " (" + (svc.status || "stopped") + ")" + (info.db_name ? " · " + info.db_name : "")
        : "Database: a MySQL/MariaDB service will be created"],
      [info.linked, info.linked ? "wp-config.php points at it" + (info.backup ? " (original backed up)" : "") : "wp-config.php will be pointed at it (original backed up)"],
      [info.helper, info.helper ? "Live-URL helper installed" : "Live-URL helper: works on localhost, phones and share links"],
    ];
    for (const [done, text] of items) {
      const li = el("li", done ? "done" : "");
      li.appendChild(el("span", "wp-check", done ? "✓" : ""));
      li.appendChild(el("span", null, text));
      steps.appendChild(li);
    }
    const problems = [];
    if (!info.mysql_available && !svc) problems.push("MySQL or MariaDB isn't installed (and no Docker). Install: " + info.mysql_install);
    if (!info.php_mysqli) problems.push("PHP's mysqli extension isn't enabled — WordPress needs it.");
    if (problems.length) {
      warn.textContent = problems.join(" ");
      warn.hidden = false;
    }
    const ready = !info.needs_setup;
    $("wp-setup").textContent = ready ? "Run setup again" : "Set up WordPress";
    $("wp-setup").className = "btn" + (ready ? "" : " primary");
    $("wp-import-label").classList.toggle("disabled", !info.db_name);
  }

  async function refreshWordPress() {
    try {
      wp.info = await request("/api/apps/" + encodeURIComponent(wp.appId) + "/wordpress");
    } catch (err) {
      wp.info = null;
      toast("WordPress: " + err.message, "err");
    }
    renderWordPress();
  }

  function openWordPress(app) {
    wp.appId = app.id;
    wp.info = null;
    $("wp-title").textContent = "WordPress · " + app.name;
    $("wp-backdrop").hidden = false;
    renderWordPress();
    refreshWordPress();
  }

  function hideWordPress() {
    $("wp-backdrop").hidden = true;
    wp.appId = null;
  }

  $("wp-close").addEventListener("click", hideWordPress);
  $("wp-setup").addEventListener("click", async () => {
    const btn = $("wp-setup");
    btn.disabled = true;
    btn.textContent = "Setting up…";
    try {
      const st = await request("/api/apps/" + encodeURIComponent(wp.appId) + "/wordpress/setup", { method: "POST" });
      replaceAppState(st);
      toast("WordPress is set up — start it and open the site", "ok");
    } catch (err) {
      toast("Setup failed: " + err.message, "err");
    } finally {
      btn.disabled = false;
      refreshWordPress();
    }
  });
  $("wp-import-file").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const label = $("wp-import-label");
    const original = label.firstChild.textContent;
    label.firstChild.textContent = "Importing " + file.name + "…";
    try {
      const res = await fetch(apiUrl("/api/apps/" + encodeURIComponent(wp.appId) + "/wordpress/import"), {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errorText(data, res.status, ""));
      toast("Imported " + file.name + " (" + Math.round(data.size / 1024) + " KB)", "ok");
    } catch (err) {
      toast("Import failed: " + err.message, "err");
    } finally {
      label.firstChild.textContent = original;
    }
  });
  $("wp-open").addEventListener("click", () => {
    if (wp.appId) openInBrowser(wp.appId);
  });
  $("wp-admin").addEventListener("click", () => {
    const app = findApp(wp.appId);
    if (app) window.open(namedUrl(app) + "wp-admin/", "_blank", "noopener");
  });

  /* ------------------------------------------------------------------ */
  /* Workspaces: start/stop a whole group in order                       */
  /* ------------------------------------------------------------------ */

  async function groupAction(category, verb) {
    try {
      await request("/api/groups/" + verb, { method: "POST", body: JSON.stringify({ category: category }) });
      toast(verb === "start" ? "Starting the group in order…" : "Stopped the group", "ok");
      fetchApps();
    } catch (err) {
      toast("Couldn't " + verb + " the group: " + err.message, "err");
    }
  }

  /* ------------------------------------------------------------------ */
  /* Log drawer                                                         */
  /* ------------------------------------------------------------------ */

  function openLogs(app) {
    state.logsId = app.id;
    state.rawLogLines = null;
    if (!ai.panel.hidden) closeAi();
    els.logsTitle.textContent = app.name;
    els.logsSub.textContent = app.path;
    els.logsBody.textContent = "Loading…";
    els.logsFilter.value = "";
    els.drawer.hidden = false;
    updateLogsBanner(app);
    fetchLogs();
    if (state.logsTimer) clearInterval(state.logsTimer);
    state.logsTimer = setInterval(fetchLogs, 2000);
  }

  function closeLogs() {
    state.logsId = null;
    els.drawer.hidden = true;
    if (state.logsTimer) {
      clearInterval(state.logsTimer);
      state.logsTimer = null;
    }
  }

  function updateLogsBanner(app) {
    if (app.status === "crashed" && app.last_error) {
      els.logsErrorBanner.textContent = app.last_error;
      els.logsErrorBanner.hidden = false;
    } else {
      els.logsErrorBanner.hidden = true;
    }
  }

  async function fetchLogs() {
    const id = state.logsId;
    if (!id) return;
    try {
      const data = await request("/api/apps/" + encodeURIComponent(id) + "/logs?tail=500");
      if (state.logsId !== id) return;
      const lines = Array.isArray(data.lines) ? data.lines : [];
      const prev = state.rawLogLines;
      // Skip the DOM rebuild when nothing changed (keeps scroll/selection stable).
      const same = prev && prev.length === lines.length && prev[prev.length - 1] === lines[lines.length - 1];
      state.rawLogLines = lines;
      if (!same) renderLogsBody();
      const cur = findApp(id);
      if (cur) updateLogsBanner(cur);
    } catch (err) {
      els.logsBody.textContent = "Couldn't read logs: " + err.message;
    }
  }

  function renderLogsBody() {
    const q = (els.logsFilter.value || "").trim().toLowerCase();
    let lines = state.rawLogLines || [];
    if (q) lines = lines.filter((l) => l.toLowerCase().includes(q));

    els.logsBody.textContent = "";
    if (lines.length === 0) {
      els.logsBody.textContent = q ? "No lines match." : "No output yet.";
      return;
    }
    const frag = document.createDocumentFragment();
    for (const line of lines) {
      const row = el("div", "log-line", line);
      if (line.startsWith("[manager]")) row.classList.add("manager-line");
      else if (/error|traceback|exception|failed|fatal/i.test(line)) row.classList.add("error-line");
      frag.appendChild(row);
    }
    els.logsBody.appendChild(frag);
    if (els.logsAutoscroll.checked) els.logsBody.scrollTop = els.logsBody.scrollHeight;
  }

  els.logsFilter.addEventListener("input", renderLogsBody);
  els.logsWrap.addEventListener("change", () => els.logsBody.classList.toggle("wrap", els.logsWrap.checked));
  els.logsClose.addEventListener("click", closeLogs);

  els.logsClear.addEventListener("click", async () => {
    if (!state.logsId) return;
    try {
      await request("/api/apps/" + encodeURIComponent(state.logsId) + "/logs", { method: "DELETE" });
      state.rawLogLines = [];
      renderLogsBody();
      toast("Logs cleared", "ok");
    } catch (err) {
      toast("Couldn't clear logs: " + err.message, "err");
    }
  });

  els.logsDownload.addEventListener("click", () => {
    if (!state.logsId) return;
    window.open(apiUrl("/api/apps/" + encodeURIComponent(state.logsId) + "/logs/download"), "_blank");
  });

  /* ------------------------------------------------------------------ */
  /* Add / Edit modal                                                   */
  /* ------------------------------------------------------------------ */

  function addEnvRow(key, val) {
    const row = el("div", "env-row");
    const k = el("input", "env-key");
    k.type = "text";
    k.placeholder = "KEY";
    k.value = key || "";
    const v = el("input", "env-val");
    v.type = "text";
    v.placeholder = "value";
    v.value = val || "";
    const rm = button("icon-btn", "×", "Remove variable");
    rm.addEventListener("click", () => row.remove());
    row.appendChild(k);
    row.appendChild(v);
    row.appendChild(rm);
    els.envRows.appendChild(row);
  }

  function renderEnvRows(env) {
    els.envRows.textContent = "";
    Object.entries(env || {}).forEach(([k, v]) => addEnvRow(k, v));
  }

  els.btnAddEnv.addEventListener("click", () => addEnvRow());

  function fillModal(app) {
    const editing = Boolean(app);
    els.modalTitle.textContent = editing ? "Edit app" : "Add app";
    els.modalSubmit.textContent = editing ? "Save" : "Add app";
    els.fId.value = editing ? app.id : "";
    els.fName.value = editing ? app.name : "";
    els.fCategory.value = editing ? appCategory(app) : state.categoryFilter && state.categoryFilter !== UNCATEGORIZED ? state.categoryFilter : "";
    els.fDescription.value = editing ? app.description || "" : "";
    els.fPath.value = editing ? app.path : "";
    els.fPathHint.textContent = "";
    setMulti(null);
    els.fCommand.value = editing ? app.command || "" : "";
    els.fPort.value = editing && app.port != null ? String(app.port) : "";
    els.fHealth.value = editing ? app.health_url || "" : "";
    renderEnvRows(editing ? app.env : {});
    els.fAuto.checked = editing && Boolean(app.auto_restart);
    els.fAutostart.checked = editing && Boolean(app.autostart);
    els.fNotify.checked = !editing || app.notify !== false;
    const hasDates = editing && (app.created_at || app.updated_at);
    els.modalMetaBox.hidden = !hasDates;
    if (hasDates) {
      els.fCreatedAt.textContent = formatDateTime(app.created_at);
      els.fUpdatedAt.textContent = formatDateTime(app.updated_at);
    }
    els.backdrop.hidden = false;
    els.fName.focus();
  }

  function openAddModal() {
    fillModal(null);
  }

  function openEditModal(app) {
    fillModal(app);
  }

  function hideModal() {
    els.backdrop.hidden = true;
  }

  els.btnAdd.addEventListener("click", openAddModal);
  els.modalClose.addEventListener("click", hideModal);
  els.modalCancel.addEventListener("click", hideModal);

  function prettyName(p) {
    const base = p.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || "";
    return base.replace(/\.(html?|php|m?js|cjs|py)$/i, "").replace(/[-_.]+/g, " ").trim().replace(/\b\w/g, (c) => c.toUpperCase());
  }

  async function triggerDetect(path) {
    const p = (path || "").trim();
    if (!p) return null;
    const seq = ++state.detectSeq;
    els.fPathHint.textContent = "Detecting command and port…";
    try {
      let url = "/api/detect?path=" + encodeURIComponent(p);
      if (els.fId.value) url += "&exclude_id=" + encodeURIComponent(els.fId.value);
      const data = await request(url);
      if (seq !== state.detectSeq) return;
      if (data.command && !els.fCommand.value.trim()) els.fCommand.value = data.command;
      if (typeof data.port === "number" && !els.fPort.value.trim()) els.fPort.value = String(data.port);
      if (!els.fName.value.trim()) els.fName.value = prettyName(p);
      if (data.is_file) {
        els.fPathHint.textContent = data.command
          ? "Detected " + data.type + (data.entry ? " — opens " + data.entry : "") + ": " + data.command
          : "Homeport can run .html, .php, .js and .py files — pick one of those, or its folder.";
      } else {
        els.fPathHint.textContent = data.command
          ? "Detected " + (data.type ? data.type + " project" : "command") + ": " + data.command
          : "Couldn't recognise this project type — enter the command you use to start it.";
      }
      return data;
    } catch (err) {
      if (seq === state.detectSeq) els.fPathHint.textContent = "Detection failed: " + err.message;
      return null;
    }
  }

  // ---- A folder with several projects inside: add them all at once ----
  let multi = null; // { root, projects: [{name, path, type, port, registered, checked}] }

  function setMulti(value) {
    multi = value;
    els.form.classList.toggle("multi-mode", Boolean(multi));
    $("multi-box").hidden = !multi;
    if (!multi) {
      els.modalSubmit.textContent = els.fId.value ? "Save" : "Add app";
      return;
    }
    els.fPathHint.textContent = "This folder holds several projects — each becomes its own app with its own port.";
    renderMulti();
  }

  function renderMulti() {
    const list = $("multi-list");
    list.textContent = "";
    for (const p of multi.projects) {
      const row = el("label", "disc-item" + (p.registered ? " added" : ""));
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.disabled = p.registered;
      cb.checked = !p.registered && p.checked !== false;
      p.checked = cb.checked;
      cb.addEventListener("change", () => {
        p.checked = cb.checked;
        updateMultiButton();
      });
      row.appendChild(cb);
      const text = el("span", "disc-text");
      text.appendChild(el("strong", null, p.name));
      text.appendChild(el("span", "muted", (p.type || "Project") + " · " + shortPath(p.path)));
      row.appendChild(text);
      row.appendChild(el("span", "disc-tag", p.registered ? "Added" : p.port ? ":" + p.port : ""));
      list.appendChild(row);
    }
    $("multi-title").textContent = multi.projects.length + " projects in " + prettyName(multi.root);
    updateMultiButton();
  }

  function updateMultiButton() {
    const n = multi ? multi.projects.filter((p) => p.checked && !p.registered).length : 0;
    els.modalSubmit.textContent = n ? "Add " + n + (n === 1 ? " app" : " apps") : "Add apps";
    els.modalSubmit.disabled = n === 0;
    $("multi-all").checked = n > 0 && n === multi.projects.filter((p) => !p.registered).length;
  }

  $("multi-all").addEventListener("change", (e) => {
    if (!multi) return;
    multi.projects.forEach((p) => {
      if (!p.registered) p.checked = e.target.checked;
    });
    renderMulti();
  });
  $("multi-single").addEventListener("click", () => {
    setMulti(null);
    els.modalSubmit.disabled = false;
  });

  // Look at what was picked: one project, one file, or a folder of projects.
  async function inspectPath(path) {
    const p = (path || "").trim();
    setMulti(null);
    els.modalSubmit.disabled = false;
    if (!p) return;
    const data = await triggerDetect(p);
    if (!data || data.is_file || els.fId.value) return; // editing keeps a single app
    let res;
    try {
      res = await request("/api/discover", { method: "POST", body: JSON.stringify({ path: p }) });
    } catch (err) {
      return;
    }
    if (els.fPath.value.trim() !== p) return; // the user moved on
    const same = (a, b) => a.replace(/[\\/]+$/, "") === b.replace(/[\\/]+$/, "");
    let root = res.projects.find((x) => same(x.path, res.path));
    const inside = res.projects.filter((x) => x !== root);
    // "The folder itself" only counts when it isn't just serving one of its subfolders
    // (e.g. a docs/index.html found from the top level).
    const viaSubfolder = (x) => /^cd\s|--directory\s|\(in\s/.test((x.command || "") + " " + (x.type || ""));
    if (root && inside.length >= 2 && viaSubfolder(root)) root = null;
    if (!root && inside.length >= 2) {
      setMulti({ root: res.path, projects: inside });
    } else if (root && inside.length) {
      const more = button("link-btn", "Add the " + inside.length + " project" + (inside.length === 1 ? "" : "s") + " inside instead");
      more.addEventListener("click", () => setMulti({ root: res.path, projects: inside }));
      els.fPathHint.appendChild(document.createTextNode(" · "));
      els.fPathHint.appendChild(more);
    }
  }

  async function addMany() {
    const chosen = multi.projects.filter((p) => p.checked && !p.registered);
    const start = $("multi-start").checked;
    const category = els.fCategory.value.trim();
    els.modalSubmit.disabled = true;
    const created = [];
    for (const p of chosen) {
      try {
        const st = await request("/api/apps", { method: "POST", body: JSON.stringify({ name: p.name, path: p.path, category: category }) });
        replaceAppState(st);
        created.push(st);
      } catch (err) {
        toast(p.name + ": " + err.message, "err");
      }
    }
    hideModal();
    els.modalSubmit.disabled = false;
    toast("Added " + created.length + (created.length === 1 ? " app" : " apps") + (start ? " — starting them" : ""), "ok");
    if (start) {
      for (const st of created) {
        if (st.command) await runAction(st.id, "start");
      }
    }
  }

  els.fPath.addEventListener("change", () => inspectPath(els.fPath.value));

  els.btnBrowse.addEventListener("click", async () => {
    try {
      const res = await request("/api/pick-folder", { method: "POST" });
      if (res && res.path) {
        els.fPath.value = res.path;
        inspectPath(res.path);
        return;
      }
      if (res && res.path === null) return; // user cancelled the native picker
    } catch (err) {
      /* native picker unavailable — fall back to the in-page browser */
    }
    openFolderBrowser(els.fPath.value || "", false);
  });

  $("btn-browse-file").addEventListener("click", async () => {
    try {
      const res = await request("/api/pick-file", { method: "POST" });
      if (res && res.path) {
        els.fPath.value = res.path;
        inspectPath(res.path);
        return;
      }
      if (res && res.path === null) return;
    } catch (err) {
      /* no native picker: use the in-page browser, which lists files too */
    }
    openFolderBrowser(els.fPath.value || "", true);
  });

  els.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (multi) {
      addMany();
      return;
    }
    const appId = els.fId.value;

    const env = {};
    els.envRows.querySelectorAll(".env-row").forEach((r) => {
      const k = (r.querySelector(".env-key").value || "").trim();
      if (k) env[k] = r.querySelector(".env-val").value || "";
    });

    const payload = {
      name: els.fName.value.trim(),
      category: els.fCategory.value.trim(),
      description: els.fDescription.value.trim(),
      path: els.fPath.value.trim(),
      command: els.fCommand.value.trim(),
      port: els.fPort.value ? parseInt(els.fPort.value, 10) : null,
      health_url: els.fHealth.value.trim() || null,
      env: env,
      auto_restart: els.fAuto.checked,
      autostart: els.fAutostart.checked,
      notify: els.fNotify.checked,
    };
    if (!payload.name || !payload.path) {
      toast("Name and folder are required", "warn");
      return;
    }

    els.modalSubmit.disabled = true;
    try {
      if (appId) {
        const updated = await request("/api/apps/" + encodeURIComponent(appId), { method: "PATCH", body: JSON.stringify(payload) });
        replaceAppState(updated);
        hideModal();
        toast("Saved " + updated.name, "ok");
        if (updated.needs_restart) {
          showConfirm("Restart now?", updated.name + " is running. Restart it to apply the changes?", "Restart", () => runAction(appId, "restart"));
        }
      } else {
        const created = await request("/api/apps", { method: "POST", body: JSON.stringify(payload) });
        replaceAppState(created);
        hideModal();
        toast("Added " + created.name, "ok");
      }
    } catch (err) {
      toast("Couldn't save: " + err.message, "err");
    } finally {
      els.modalSubmit.disabled = false;
    }
  });

  /* ------------------------------------------------------------------ */
  /* In-page folder browser                                             */
  /* ------------------------------------------------------------------ */

  function openFolderBrowser(initialPath, files) {
    state.browseFiles = Boolean(files);
    els.browseBackdrop.hidden = false;
    let start = initialPath || "";
    if (/\.(html?|php|m?js|cjs|py)$/i.test(start)) start = start.replace(/[\\/][^\\/]*$/, "");
    loadFolder(start);
  }

  function hideFolderBrowser() {
    els.browseBackdrop.hidden = true;
  }

  els.browseCancel.addEventListener("click", hideFolderBrowser);
  els.browseClose.addEventListener("click", hideFolderBrowser);

  function browseItem(label, onClick, isApp) {
    const item = el("div", "browse-item");
    item.tabIndex = 0;
    item.appendChild(icon(el("span"), "folder").firstChild);
    item.appendChild(el("span", "browse-name", label));
    if (isApp) item.appendChild(el("span", "tag category", "app"));
    item.addEventListener("click", onClick);
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter") onClick();
    });
    return item;
  }

  async function loadFolder(target) {
    els.browseList.textContent = "Loading…";
    try {
      const q = [];
      if (target) q.push("path=" + encodeURIComponent(target));
      if (state.browseFiles) q.push("files=1");
      const data = await request("/api/browse" + (q.length ? "?" + q.join("&") : ""));
      state.currentBrowsePath = data.path;
      els.browseSelectedPath.textContent = data.path;

      els.browseCrumbs.textContent = "";
      const root = button("crumb", "/");
      root.addEventListener("click", () => loadFolder("/"));
      els.browseCrumbs.appendChild(root);
      let acc = "";
      data.path.split("/").filter(Boolean).forEach((part, i) => {
        acc += "/" + part;
        const p = acc;
        if (i > 0) els.browseCrumbs.appendChild(el("span", "crumb-sep", "/"));
        const c = button("crumb", part);
        c.addEventListener("click", () => loadFolder(p));
        els.browseCrumbs.appendChild(c);
      });

      els.browseList.textContent = "";
      if (data.parent) els.browseList.appendChild(browseItem("..", () => loadFolder(data.parent)));
      if (!data.entries.length) {
        els.browseList.appendChild(el("div", "browse-empty", state.browseFiles ? "No folders or runnable files here" : "No subfolders"));
      }
      for (const entry of data.entries) {
        if (entry.is_file) {
          const item = browseItem(entry.name, () => {
            els.fPath.value = entry.path;
            inspectPath(entry.path);
            hideFolderBrowser();
          }, false);
          item.classList.add("is-file");
          els.browseList.appendChild(item);
        } else {
          els.browseList.appendChild(browseItem(entry.name, () => loadFolder(entry.path), entry.looks_like_app));
        }
      }
    } catch (err) {
      els.browseList.textContent = "Couldn't open folder: " + err.message;
    }
  }

  els.browseSelect.addEventListener("click", () => {
    if (!state.currentBrowsePath) return;
    els.fPath.value = state.currentBrowsePath;
    inspectPath(state.currentBrowsePath);
    hideFolderBrowser();
  });

  /* ------------------------------------------------------------------ */
  /* Theme                                                              */
  /* ------------------------------------------------------------------ */

  function effectiveTheme() {
    const set = document.documentElement.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function renderThemeButton() {
    icon(els.btnTheme, effectiveTheme() === "dark" ? "sun" : "moon");
  }

  // "system" follows the computer's light/dark setting.
  function setThemeMode(mode) {
    if (mode === "light" || mode === "dark") {
      document.documentElement.setAttribute("data-theme", mode);
      savePref("theme", mode);
    } else {
      document.documentElement.removeAttribute("data-theme");
      try {
        localStorage.removeItem("lm_theme");
      } catch (e) {
        /* ignore */
      }
    }
    renderThemeButton();
  }

  els.btnTheme.addEventListener("click", () => setThemeMode(effectiveTheme() === "dark" ? "light" : "dark"));
  if (window.matchMedia) {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    if (mq.addEventListener) mq.addEventListener("change", renderThemeButton);
  }
  renderThemeButton();

  /* ------------------------------------------------------------------ */
  /* Live sync: SSE with polling fallback                               */
  /* ------------------------------------------------------------------ */

  let sseRetryTimer = null;

  function scheduleSSERetry() {
    if (sseRetryTimer) return;
    sseRetryTimer = setTimeout(() => {
      sseRetryTimer = null;
      if (!state.sse) startSSE();
    }, 5000);
  }

  function startSSE() {
    if (state.sse) state.sse.close();
    setConn("connecting");
    const sse = new EventSource(apiUrl("/api/events"));
    state.sse = sse;

    sse.onopen = () => {
      setConn("live");
      if (sseRetryTimer) {
        clearTimeout(sseRetryTimer);
        sseRetryTimer = null;
      }
      if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
      }
    };

    sse.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (Array.isArray(data)) updateAllApps(data);
      } catch (err) {
        /* ignore malformed frame */
      }
    };

    sse.onerror = () => {
      sse.close();
      state.sse = null;
      setConn("polling");
      startPolling();
      scheduleSSERetry();
    };
  }

  function startPolling() {
    if (state.pollTimer) return;
    fetchApps();
    state.pollTimer = setInterval(fetchApps, 2000);
  }

  async function fetchApps() {
    try {
      updateAllApps(await request("/api/apps"));
      if (!state.sse) setConn("polling");
    } catch (err) {
      setConn("offline");
    }
  }

  // Tick uptimes between server updates.
  setInterval(() => {
    for (const app of state.apps) {
      if (!isActive(app)) continue;
      const view = state.views.get(app.id);
      if (view) view.uptime.textContent = formatUptime(app);
    }
  }, 1000);

  /* ------------------------------------------------------------------ */
  /* Command palette (⌘K / Ctrl+K)                                      */
  /* ------------------------------------------------------------------ */

  // var (not const): render() may check it before this line has run.
  var cmdk = {
    sig: "",
    backdrop: $("cmdk-backdrop"),
    input: $("cmdk-input"),
    list: $("cmdk-list"),
    items: [],
    active: 0,
  };

  /** Score how well ``query`` matches ``text`` (higher is better), or -1.
   *  Every word of the query must appear, in order, with gaps allowed;
   *  matches at the start of words score highest. */
  function fuzzyScore(query, text) {
    const t = text.toLowerCase();
    let total = 0;
    for (const word of query.toLowerCase().split(/\s+/).filter(Boolean)) {
      const at = t.indexOf(word);
      if (at !== -1) {
        const wordStart = at === 0 || /[\s\-_./:]/.test(t[at - 1]);
        total += 100 + (wordStart ? 60 : 0) - Math.min(at, 40);
        continue;
      }
      // Loose match ("shr" → "share"): must start at a word start and stay tight.
      let best = -1;
      for (let start = t.indexOf(word[0]); start !== -1; start = t.indexOf(word[0], start + 1)) {
        if (start > 0 && !/[\s\-_./:]/.test(t[start - 1])) continue;
        let ti = start + 1;
        let gaps = 0;
        let ok = true;
        for (const ch of word.slice(1)) {
          const found = t.indexOf(ch, ti);
          if (found === -1) {
            ok = false;
            break;
          }
          gaps += found - ti;
          ti = found + 1;
        }
        if (ok && gaps <= word.length * 2) best = Math.max(best, 60 - gaps * 4);
      }
      if (best < 0) return -1;
      total += best;
    }
    return total;
  }

  /** Character positions in ``text`` to highlight for ``query``. */
  function matchPositions(query, text) {
    const t = text.toLowerCase();
    const marks = new Set();
    for (const word of query.toLowerCase().split(/\s+/).filter(Boolean)) {
      const at = t.indexOf(word);
      if (at !== -1) {
        for (let i = 0; i < word.length; i++) marks.add(at + i);
        continue;
      }
      let ti = 0;
      for (const ch of word) {
        const found = t.indexOf(ch, ti);
        if (found === -1) break;
        marks.add(found);
        ti = found + 1;
      }
    }
    return marks;
  }

  function highlighted(text, query) {
    const span = el("span", "cmdk-title");
    if (!query) {
      span.textContent = text;
      return span;
    }
    const marks = matchPositions(query, text);
    let run = "";
    let inMark = false;
    const flush = () => {
      if (!run) return;
      span.appendChild(inMark ? el("mark", null, run) : document.createTextNode(run));
      run = "";
    };
    for (let i = 0; i < text.length; i++) {
      const m = marks.has(i);
      if (m !== inMark) {
        flush();
        inMark = m;
      }
      run += text[i];
    }
    flush();
    return span;
  }

  function logoTile(app) {
    const tile = el("span", "app-logo");
    if (app.icon) {
      tile.className = "app-logo image";
      const img = document.createElement("img");
      img.alt = "";
      img.src = apiUrl(app.icon);
      img.addEventListener("error", () => paintGeneratedLogo(tile, app));
      tile.appendChild(img);
    } else {
      paintGeneratedLogo(tile, app);
    }
    return tile;
  }

  function iconTile(name) {
    return icon(el("span", "cmdk-ico"), name);
  }

  function appSubtitle(app) {
    const bits = [statusLabel(app.status || "stopped")];
    const tech = techLabel(app);
    if (tech) bits.push(tech);
    if (appPort(app) !== null) bits.push(app.id + ".localhost");
    return bits.join(" · ");
  }

  /** Every command available right now (rebuilt from live app state). */
  function buildCommands() {
    const cmds = [];
    const add = (c) => cmds.push(c);
    for (const app of state.apps) {
      const active = isActive(app);
      const id = app.id;
      const name = app.name;
      const kw = [app.id, techLabel(app) || "", appCategory(app)].join(" ");
      const base = { app: app, keywords: kw };
      // Default row for the app: the most likely thing you want.
      add(Object.assign({}, base, {
        kind: "app", title: name, subtitle: appSubtitle(app),
        hint: active ? "Open" : app.command ? "Start" : "Edit",
        run: () => (active ? openInBrowser(id) : app.command ? runAction(id, "start") : openEditModal(app)),
      }));
      if (active) {
        add(Object.assign({}, base, { title: "Open " + name, icon: "open", run: () => openInBrowser(id) }));
        add(Object.assign({}, base, { title: "Stop " + name, icon: "stop", run: () => runAction(id, "stop") }));
        add(Object.assign({}, base, { title: "Restart " + name, icon: "restart", run: () => runAction(id, "restart") }));
        add(Object.assign({}, base, { title: "Open " + name + " on phone", icon: "phone", keywords: kw + " qr wifi mobile", run: () => openPhone(app) }));
        if (app.share) {
          if (app.share.url) add(Object.assign({}, base, { title: "Copy public link of " + name, icon: "copy", run: () => copyText(app.share.url) }));
          add(Object.assign({}, base, { title: "Stop sharing " + name, icon: "share", run: () => stopShare(id) }));
        } else {
          add(Object.assign({}, base, { title: "Share " + name + " publicly", icon: "share", keywords: kw + " public link tunnel", run: () => openShare(app) }));
        }
      } else if (app.command) {
        add(Object.assign({}, base, { title: "Start " + name, icon: "play", run: () => runAction(id, "start") }));
      }
      if (app.status === "crashed" || (app.port_conflict && !active)) {
        add(Object.assign({}, base, { title: "Why did " + name + " stop?", icon: "why", keywords: kw + " crash fix diagnose error", run: () => openDiagnose(app) }));
      }
      if (app.wordpress) {
        add(Object.assign({}, base, { title: (app.wordpress.needs_setup ? "Set up WordPress for " : "WordPress settings for ") + name, icon: "layers", keywords: kw + " wordpress wp database mysql import", run: () => openWordPress(app) }));
        add(Object.assign({}, base, { title: "Open " + name + " admin (wp-admin)", icon: "open", keywords: kw + " wordpress dashboard login", run: () => window.open(namedUrl(app) + "wp-admin/", "_blank", "noopener") }));
      }
      if (app.service) {
        add(Object.assign({}, base, { title: "Copy connection URL for " + name, icon: "copy", keywords: kw + " database url dsn", run: () => copyText(app.service.url) }));
        add(Object.assign({}, base, { title: "Copy .env settings for " + name, icon: "copy", keywords: kw + " database env dotenv", run: () => copyText(envText(app.service)) }));
      }
      add(Object.assign({}, base, { title: "Logs: " + name, icon: "logs", run: () => openLogs(app) }));
      add(Object.assign({}, base, { title: "Edit " + name, icon: "edit", keywords: kw + " settings command port", run: () => openEditModal(app) }));
      add(Object.assign({}, base, { title: "Open " + name + " folder", icon: "folder", run: () => openTarget(id, "finder") }));
      add(Object.assign({}, base, { title: "Open terminal in " + name, icon: "terminal", run: () => openTarget(id, "terminal") }));
      if (app.git) {
        add(Object.assign({}, base, {
          title: "Pull & restart " + name, icon: "git", keywords: kw + " git update",
          run: () => {
            const row = state.views.get(id);
            if (row && row.miPull) row.miPull.click();
          },
        }));
      }
    }

    const act = (title, iconName, run, keywords) => add({ kind: "action", title: title, icon: iconName, run: run, keywords: keywords || "" });
    act("Add app", "plus", () => openAddModal(), "new project create");
    act("Discover projects", "discover", () => openDiscover(), "scan folder import find");
    act("Add from GitHub…", "discover", () => openGitHub(), "clone repo repository git github");
    act("Databases & services…", "layers", () => openServices(), "postgres mysql mariadb redis mongodb mailpit database");
    act("Check for updates", "restart", () => loadUpdate(true).then((st) => st && openUpdate()), "update version new release");
    act("Settings…", "settings", () => openSettings(), "preferences theme dark light ai model ollama local qwen llama download shortcuts");
    for (const [kind, label] of [["postgres", "PostgreSQL"], ["mysql", "MySQL / MariaDB"], ["redis", "Redis"], ["mongodb", "MongoDB"], ["mailpit", "Mailpit (email testing)"]]) {
      act("Add " + label, "plus", () => addService(kind), "database service");
    }
    act("Start all apps", "play", () => bulk("/api/apps/start-all", "Started all apps"), "everything");
    act("Stop all apps", "stop", () => bulk("/api/apps/stop-all", "Stopped all apps"), "everything");
    const cats = Array.from(new Set(state.apps.map(appCategory).filter(Boolean))).sort(collator.compare);
    for (const c of cats) {
      act("Start workspace: " + c, "layers", () => groupAction(c, "start"), "group category start all in order");
      act("Stop workspace: " + c, "layers", () => groupAction(c, "stop"), "group category");
      act("Show category: " + c, "filter", () => {
        state.categoryFilter = c;
        savePref("category", c);
        render();
      }, "filter");
    }
    const showStatus = (label, filter) => act("Show " + label, "filter", () => {
      const btn = Array.from(els.statusBtns).find((b) => b.dataset.filter === filter);
      if (btn) btn.click();
    }, "filter status");
    showStatus("all apps", "all");
    showStatus("running apps", "running");
    showStatus("stopped apps", "stopped");
    showStatus("crashed apps", "crashed");
    act(effectiveTheme() === "dark" ? "Switch to light theme" : "Switch to dark theme",
      effectiveTheme() === "dark" ? "sun" : "moon", () => els.btnTheme.click(), "theme appearance dark light mode");
    act(document.body.classList.contains("side-hidden") ? "Show sidebar" : "Hide sidebar", "sidebar",
      () => $("btn-sidebar").click(), "toggle panel");
    act(state.viewMode === "grid" ? "Switch to list view" : "Switch to grid view",
      state.viewMode === "grid" ? "list" : "grid",
      () => els.viewBtns[state.viewMode === "grid" ? 1 : 0].click(), "layout");
    act(state.groupBy ? "Stop grouping by category" : "Group by category", "layers", () => els.btnGroup.click(), "workspaces");
    if (!$("ai-fab").hidden) act("Ask AI", "chat", () => openAi(), "assistant claude help");
    if (canQuit) act("Quit Homeport", "stop", () => quitHomeport(), "exit close shutdown");
    return cmds;
  }

  function paletteResults(query) {
    const all = buildCommands();
    if (!query) {
      // Empty: your apps (running first), then actions.
      const apps = all.filter((c) => c.kind === "app")
        .sort((a, b) => Number(isActive(b.app)) - Number(isActive(a.app)));
      return [{ header: "Apps" }].concat(apps)
        .concat([{ header: "Actions" }], all.filter((c) => c.kind === "action"));
    }
    return all
      .map((c) => ({ c: c, score: fuzzyScore(query, c.title + " " + (c.keywords || "")) }))
      .filter((r) => r.score >= 0)
      .map((r) => ({ c: r.c, score: r.score + (r.c.kind === "app" ? 15 : 0) })) // apps first on ties
      .sort((a, b) => b.score - a.score)
      .slice(0, 40)
      .map((r) => r.c);
  }

  function renderPalette() {
    const query = cmdk.input.value.trim();
    const results = paletteResults(query);
    cmdk.items = results.filter((r) => !r.header);
    if (cmdk.active >= cmdk.items.length) cmdk.active = Math.max(0, cmdk.items.length - 1);
    cmdk.list.textContent = "";
    if (!cmdk.items.length) {
      cmdk.list.appendChild(el("div", "cmdk-empty", "No matches for “" + query + "”"));
      cmdk.input.removeAttribute("aria-activedescendant");
      return;
    }
    let index = 0;
    for (const r of results) {
      if (r.header) {
        cmdk.list.appendChild(el("div", "cmdk-group", r.header));
        continue;
      }
      const i = index++;
      const row = el("div", "cmdk-item" + (i === cmdk.active ? " active" : ""));
      row.id = "cmdk-opt-" + i;
      row.setAttribute("role", "option");
      row.setAttribute("aria-selected", String(i === cmdk.active));
      if (r.kind === "app") row.appendChild(logoTile(r.app));
      else row.appendChild(iconTile(r.icon || "more"));
      const text = el("span", "cmdk-text");
      text.appendChild(highlighted(r.title, query));
      const sub = r.subtitle || (r.app && r.kind !== "app" ? r.app.name : r.kind === "action" ? "" : "");
      if (sub) text.appendChild(el("span", "cmdk-sub", sub));
      row.appendChild(text);
      if (r.kind === "app") {
        const dot = el("span", "cmdk-status " + (r.app.status || "stopped"));
        row.appendChild(dot);
      }
      row.appendChild(el("span", "cmdk-hint-r", r.hint || (r.kind === "action" ? "Action" : "")));
      row.addEventListener("mousemove", () => {
        if (cmdk.active !== i) {
          cmdk.active = i;
          markActive();
        }
      });
      row.addEventListener("click", () => runPaletteItem(i));
      cmdk.list.appendChild(row);
    }
    markActive();
  }

  function markActive() {
    cmdk.list.querySelectorAll(".cmdk-item").forEach((row, i) => {
      const on = i === cmdk.active;
      row.classList.toggle("active", on);
      row.setAttribute("aria-selected", String(on));
      if (on) {
        cmdk.input.setAttribute("aria-activedescendant", row.id);
        row.scrollIntoView({ block: "nearest" });
      }
    });
  }

  function runPaletteItem(i) {
    const item = cmdk.items[i];
    if (!item) return;
    closePalette();
    try {
      item.run();
    } catch (err) {
      toast(err.message || String(err), "err");
    }
  }

  function openPalette(prefill) {
    closeMenus();
    cmdk.backdrop.hidden = false;
    cmdk.input.value = prefill || "";
    cmdk.active = 0;
    renderPalette();
    cmdk.input.focus();
  }

  function closePalette() {
    cmdk.backdrop.hidden = true;
  }

  cmdk.input.addEventListener("input", () => {
    cmdk.active = 0;
    renderPalette();
  });
  cmdk.input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || (e.key === "n" && e.ctrlKey)) {
      e.preventDefault();
      cmdk.active = (cmdk.active + 1) % Math.max(1, cmdk.items.length);
      markActive();
    } else if (e.key === "ArrowUp" || (e.key === "p" && e.ctrlKey)) {
      e.preventDefault();
      cmdk.active = (cmdk.active - 1 + cmdk.items.length) % Math.max(1, cmdk.items.length);
      markActive();
    } else if (e.key === "Enter") {
      e.preventDefault();
      runPaletteItem(cmdk.active);
    } else if (e.key === "Tab") {
      e.preventDefault(); // keep focus in the palette
    }
  });
  cmdk.backdrop.addEventListener("mousedown", (e) => {
    if (e.target === cmdk.backdrop) closePalette();
  });

  /* ------------------------------------------------------------------ */
  /* Keyboard                                                           */
  /* ------------------------------------------------------------------ */

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      // Close only the top-most layer.
      if (!cmdk.backdrop.hidden) closePalette();
      else if (document.querySelector(".menu:not([hidden])")) closeMenus();
      else if (!els.confirmBackdrop.hidden) hideConfirm();
      else if (!els.shareBackdrop.hidden) hideShare();
      else if (!$("phone-backdrop").hidden) hidePhone();
      else if (!$("diag-backdrop").hidden) hideDiag();
      else if (!$("disc-backdrop").hidden) hideDiscover();
      else if (!$("svc-backdrop").hidden) hideServices();
      else if (!$("settings-backdrop").hidden) hideSettings();
      else if (!$("fb-backdrop").hidden) hideFeedback();
      else if (!$("gh-backdrop").hidden) hideGitHub();
      else if (!$("upd-backdrop").hidden) hideUpdate();
      else if (!$("wp-backdrop").hidden) hideWordPress();
      else if (!els.browseBackdrop.hidden) hideFolderBrowser();
      else if (!els.backdrop.hidden) hideModal();
      else if (!els.drawer.hidden) closeLogs();
      else if (!ai.panel.hidden) closeAi();
      return;
    }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "j") {
      e.preventDefault();
      if (ai.panel.hidden) openAi();
      else closeAi();
      return;
    }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (cmdk.backdrop.hidden) openPalette();
      else closePalette();
      return;
    }
    // "/" filters the cards (when not already typing somewhere).
    if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const t = e.target;
      const typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
      if (!typing && cmdk.backdrop.hidden) {
        e.preventDefault();
        els.searchInput.focus();
        els.searchInput.select();
      }
    }
  });

  // Click outside a modal closes it.
  [
    [els.backdrop, hideModal],
    [els.browseBackdrop, hideFolderBrowser],
    [els.confirmBackdrop, hideConfirm],
  ].forEach(([bd, close]) => {
    bd.addEventListener("mousedown", (e) => {
      if (e.target === bd) close();
    });
  });

  /* ------------------------------------------------------------------ */
  /* AI assistant: Claude Code (the local `claude` CLI) or a local model */
  /* through Ollama. Either one runs only when you send a message.       */
  /* ------------------------------------------------------------------ */

  const ai = {
    panel: $("ai-panel"),
    log: $("ai-log"),
    form: $("ai-form"),
    input: $("ai-input"),
    send: $("ai-send"),
    model: $("ai-model"),
    modelCustom: $("ai-model-custom"),
    modelWrap: $("ai-model-wrap"),
    providerSel: $("ai-provider"),
    localSel: $("ai-local-model"),
    localWrap: $("ai-local-wrap"),
    modelsBtn: $("ai-models-btn"),
    sub: $("ai-sub"),
    modeSeg: $("ai-mode"),
    meta: $("ai-meta"),
    reload: $("ai-reload"),
    provider: "claude",
    claudeAvailable: false,
    localStatus: null,
    sessionId: null,
    appId: null,
    mode: "act",
    running: false,
    abort: null,
    tools: {},
    streamNode: null,
    streamText: "",
  };

  const AI_SUGGESTIONS = [
    "Why are some apps unhealthy or crashed? Diagnose and fix them.",
    "Find apps that share the same port and give each a unique one.",
    "Add the app in this folder: ",
    "Make the cards more compact.",
  ];
  const AI_LOCAL_SUGGESTIONS = [
    "Why are some apps crashed? Find the cause and fix it.",
    "Which apps share the same port?",
    "What does this app need to start?",
  ];

  function aiPref(key, fallback) {
    try {
      const v = localStorage.getItem("lm_ai_" + key);
      return v === null ? fallback : v;
    } catch (err) {
      return fallback;
    }
  }

  function aiSavePref(key, value) {
    try {
      localStorage.setItem("lm_ai_" + key, value);
    } catch (err) {
      /* ignore */
    }
  }

  function aiModel() {
    if (ai.provider === "local") return ai.localSel.value;
    return ai.model.value === "__custom" ? ai.modelCustom.value.trim() : ai.model.value;
  }

  function aiSetMode(mode) {
    ai.mode = mode === "ask" ? "ask" : "act";
    ai.modeSeg.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.mode === ai.mode));
    aiSavePref("mode", ai.mode);
  }

  // Minimal, safe markdown: ``` blocks, `code`, **bold**. Everything goes through textContent.
  function aiRichText(node, text) {
    text.split(/```[a-zA-Z0-9_-]*\n?/).forEach((part, i) => {
      if (i % 2 === 1) {
        node.appendChild(el("pre", null, part.replace(/\n$/, "")));
        return;
      }
      part.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/).forEach((chunk) => {
        if (/^`[^`]+`$/.test(chunk)) node.appendChild(el("code", null, chunk.slice(1, -1)));
        else if (/^\*\*[^*]+\*\*$/.test(chunk)) node.appendChild(el("strong", null, chunk.slice(2, -2)));
        else if (chunk) node.appendChild(document.createTextNode(chunk));
      });
    });
    return node;
  }

  function aiScroll() {
    ai.log.scrollTop = ai.log.scrollHeight;
  }

  function aiAppend(node) {
    const empty = ai.log.querySelector(".ai-empty, .ai-setup");
    if (empty) empty.remove();
    const thinking = ai.log.querySelector(".ai-thinking");
    if (thinking && node !== thinking) ai.log.insertBefore(node, thinking);
    else ai.log.appendChild(node);
    aiScroll();
    return node;
  }

  function aiRenderEmpty() {
    ai.log.textContent = "";
    const box = el("div", "ai-empty");
    box.appendChild(el("p", null, "Ask a question or tell it what to do. Try:"));
    (ai.provider === "local" ? AI_LOCAL_SUGGESTIONS : AI_SUGGESTIONS).forEach((text) => {
      const chip = button("ai-chip", text);
      chip.addEventListener("click", () => {
        ai.input.value = text;
        ai.input.focus();
        ai.input.setSelectionRange(text.length, text.length);
      });
      box.appendChild(chip);
    });
    ai.log.appendChild(box);
  }

  function aiSetRunning(running) {
    ai.running = running;
    ai.send.textContent = running ? "Stop" : "Send";
    ai.send.classList.toggle("primary", !running);
    ai.send.classList.toggle("danger", running);
    const thinking = ai.log.querySelector(".ai-thinking");
    if (running && !thinking) ai.log.appendChild(el("div", "ai-thinking", "Working"));
    if (!running && thinking) thinking.remove();
  }

  function aiEndStream() {
    ai.streamNode = null;
    ai.streamText = "";
  }

  function aiConfirmCard(evt) {
    const card = el("div", "ai-confirm");
    card.appendChild(el("div", "ai-confirm-label", "Allow this change?"));
    card.appendChild(el("div", "ai-confirm-text", evt.summary || evt.name));
    const row = el("div", "ai-confirm-row");
    const yes = button("btn small primary", "Allow");
    const no = button("btn small", "Don't allow");
    const answer = async (approve) => {
      yes.disabled = true;
      no.disabled = true;
      try {
        await request("/api/local-ai/confirm", { method: "POST", body: JSON.stringify({ id: evt.id, approve: approve }) });
        row.replaceChildren(el("span", "muted", approve ? "Allowed" : "Not allowed"));
      } catch (err) {
        row.replaceChildren(el("span", "muted", "This request has expired"));
      }
      card.classList.add("answered");
    };
    yes.addEventListener("click", () => answer(true));
    no.addEventListener("click", () => answer(false));
    row.append(yes, no);
    card.appendChild(row);
    return card;
  }

  function aiHandle(evt) {
    if (evt.type === "session") {
      ai.sessionId = evt.session_id || ai.sessionId;
      if (evt.model) ai.meta.textContent = evt.model;
    } else if (evt.type === "status") {
      const thinking = ai.log.querySelector(".ai-thinking");
      if (thinking) thinking.textContent = evt.text || "Working";
    } else if (evt.type === "delta") {
      if (!ai.streamNode) {
        ai.streamNode = aiAppend(el("div", "ai-msg"));
        ai.streamText = "";
      }
      ai.streamText += evt.text;
      ai.streamNode.textContent = "";
      aiRichText(ai.streamNode, ai.streamText);
      aiScroll();
    } else if (evt.type === "text") {
      aiEndStream();
      aiAppend(aiRichText(el("div", "ai-msg"), evt.text));
    } else if (evt.type === "tool") {
      aiEndStream();
      const row = el("div", "ai-tool");
      row.appendChild(el("b", null, evt.name));
      row.appendChild(el("span", null, evt.summary || ""));
      row.title = evt.summary || "";
      if (evt.id) ai.tools[evt.id] = row;
      if (/^(Edit|Write|MultiEdit)$/.test(evt.name) && /\/ui\//.test(evt.summary || "")) ai.reload.hidden = false;
      aiAppend(row);
    } else if (evt.type === "tool_result") {
      const row = ai.tools[evt.id];
      if (row && evt.error) row.classList.add("failed");
    } else if (evt.type === "confirm") {
      aiEndStream();
      aiAppend(aiConfirmCard(evt));
      if (ai.panel.hidden) document.getElementById("ai-fab").classList.add("unread");
    } else if (evt.type === "done") {
      aiEndStream();
      ai.sessionId = evt.session_id || ai.sessionId;
      if (ai.panel.hidden) document.getElementById("ai-fab").classList.add("unread");
      const bits = [];
      if (typeof evt.duration_ms === "number") bits.push((evt.duration_ms / 1000).toFixed(1) + "s");
      if (evt.turns) bits.push(evt.turns + " turns");
      if (typeof evt.tokens_per_s === "number") bits.push(evt.tokens_per_s + " tok/s");
      if (typeof evt.cost_usd === "number") bits.push("≈$" + evt.cost_usd.toFixed(3) + " of plan usage");
      if (ai.provider === "local") bits.push("on this computer");
      ai.meta.textContent = bits.join(" · ");
    } else if (evt.type === "error") {
      aiEndStream();
      aiAppend(el("div", "ai-msg error", evt.message || "Something went wrong"));
    }
  }

  // Read a text/event-stream response and hand each JSON event to onEvent.
  async function readSSE(res, onEvent) {
    if (!res.ok) {
      const raw = await res.text();
      let data = null;
      try {
        data = JSON.parse(raw);
      } catch (err) {
        data = null;
      }
      throw new Error(errorText(data, res.status, raw));
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = chunk.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        let evt = null;
        try {
          evt = JSON.parse(line.slice(6));
        } catch (err) {
          continue; // ignore malformed event
        }
        onEvent(evt);
      }
    }
  }

  async function aiSend(prompt) {
    aiAppend(el("div", "ai-msg user", prompt));
    aiSetRunning(true);
    aiEndStream();
    ai.tools = {};
    ai.abort = new AbortController();
    const local = ai.provider === "local";
    const body = { prompt, model: aiModel(), session_id: ai.sessionId, mode: ai.mode };
    if (local && ai.appId) body.app_id = ai.appId;
    ai.appId = null;
    try {
      const res = await fetch(apiUrl(local ? "/api/local-ai/ask" : "/api/ai/ask"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal: ai.abort.signal,
      });
      await readSSE(res, aiHandle);
    } catch (err) {
      aiAppend(el("div", "ai-msg error", err.name === "AbortError" ? "stopped" : err.message));
    } finally {
      ai.abort = null;
      aiEndStream();
      aiSetRunning(false);
    }
  }

  async function aiStop() {
    try {
      // The server stops the run and the stream ends.
      await request(ai.provider === "local" ? "/api/local-ai/stop" : "/api/ai/stop", { method: "POST" });
    } catch (err) {
      if (ai.abort) ai.abort.abort();
    }
  }

  /* ---------- local models (Ollama) ---------- */

  function fmtGB(bytes) {
    return (bytes / 1e9).toFixed(1) + " GB";
  }

  function sameModel(a, b) {
    const norm = (s) => (s.indexOf(":") >= 0 ? s : s + ":latest");
    return !!a && !!b && norm(a) === norm(b);
  }

  function aiFillLocalModels(st) {
    const names = (st.models || []).map((m) => m.name);
    ai.localSel.textContent = "";
    names.forEach((name) => {
      const opt = el("option", null, name);
      opt.value = name;
      ai.localSel.appendChild(opt);
    });
    if (!names.length) {
      const opt = el("option", null, "No model yet");
      opt.value = "";
      ai.localSel.appendChild(opt);
    }
    const preferred = [st.selected, st.recommended].find((n) => n && names.some((x) => sameModel(x, n)));
    ai.localSel.value = (preferred && names.find((x) => sameModel(x, preferred))) || names[0] || "";
  }

  function aiLocalReady(st) {
    return !!(st && st.running && st.models && st.models.length);
  }

  async function aiLocalStatus() {
    const st = await request("/api/local-ai/status");
    ai.localStatus = st;
    aiFillLocalModels(st);
    watchPull(st);
    return st;
  }

  // In the chat: a short note with a button to Settings, where models are managed.
  function aiRenderSetupCard(st) {
    ai.log.textContent = "";
    const box = el("div", "ai-setup");
    box.appendChild(el("h3", null, "Set up the local model"));
    let text;
    if (!st.installed) text = "Install Ollama (free) and download a model in Settings. It runs on this computer, offline.";
    else if (!st.running) text = "Ollama is installed but not running. Start it in Settings.";
    else if (st.pull && st.pull.active) text = "Downloading " + st.pull.model + "… you can keep working, it continues in the background.";
    else text = "Download a model in Settings to start. Qwen3 4B (about 2.5 GB) is a good first choice.";
    box.appendChild(el("p", "muted", text));
    const open = button("btn small primary", "Open Settings");
    open.addEventListener("click", () => openSettings(st.running ? "models" : "local"));
    box.appendChild(open);
    ai.log.appendChild(box);
  }

  /* ------------------------------------------------------------------ */
  /* Update check: a quiet notice when a newer Homeport is out            */
  /* ------------------------------------------------------------------ */

  const upd = { st: null };

  function renderUpdateNote() {
    const st = upd.st;
    const note = $("update-note");
    const show = !!(st && st.enabled && st.available && loadPref("update_dismissed", "") !== st.latest);
    note.hidden = !show;
    if (show) {
      $("update-note-text").textContent = "Update available · v" + st.latest;
      note.title = "Homeport " + st.latest + " is out (you have " + st.current + ")";
    }
  }

  async function loadUpdate(force) {
    try {
      upd.st = await request(force ? "/api/update/check" : "/api/update", force ? { method: "POST" } : undefined);
    } catch (err) {
      return null;
    }
    renderUpdateNote();
    return upd.st;
  }

  function openUpdate() {
    const st = upd.st;
    if (!st) return;
    $("upd-title").textContent = st.available ? "Homeport " + st.latest + " is available" : "Homeport is up to date";
    const body = $("upd-body");
    body.textContent = "";
    body.appendChild(el("p", "upd-versions", st.available ? "You have " + st.current + ". The new version is " + st.latest + "." : "You have the latest version, " + st.current + "."));
    if (st.available && st.notes) body.appendChild(el("pre", "upd-notes", st.notes));
    const more = el("a", "set-inline-link", "See everything that's new");
    more.href = st.changelog;
    more.target = "_blank";
    more.rel = "noopener";
    body.appendChild(more);
    const how = st.how || {};
    const action = $("upd-action");
    action.textContent = "";
    if (st.available) {
      if (how.kind === "desktop") {
        body.appendChild(el("p", "hint", "Download the new version and install it over this one — your apps and settings stay."));
        const dl = el("a", "btn primary", "Download " + st.latest);
        dl.href = how.download;
        dl.target = "_blank";
        dl.rel = "noopener";
        action.appendChild(dl);
      } else {
        body.appendChild(el("p", "hint", how.kind === "script"
          ? "Run the install command again — it updates Homeport and keeps your apps and settings:"
          : "Homeport runs from a copy of its code. Update it in a terminal, in " + (how.folder || "Homeport's folder") + ", then restart Homeport:"));
        body.appendChild(el("code", "upd-cmd", how.command));
        const copy = button("btn primary", "Copy command");
        copy.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(how.command);
            toast("Command copied", "ok");
          } catch (e) {
            window.prompt("Copy this command:", how.command);
          }
        });
        action.appendChild(copy);
      }
    }
    $("upd-later").textContent = st.available ? "Later" : "Close";
    $("upd-backdrop").hidden = false;
  }

  function hideUpdate() {
    $("upd-backdrop").hidden = true;
  }

  $("update-note").addEventListener("click", openUpdate);
  $("upd-close").addEventListener("click", hideUpdate);
  $("upd-later").addEventListener("click", () => {
    // "Later": hide the sidebar notice for this version (it comes back for the next one)
    if (upd.st && upd.st.available) savePref("update_dismissed", upd.st.latest);
    renderUpdateNote();
    hideUpdate();
  });
  $("upd-backdrop").addEventListener("mousedown", (e) => {
    if (e.target === $("upd-backdrop")) hideUpdate();
  });
  loadUpdate(false);
  window.setInterval(() => loadUpdate(false), 60 * 60 * 1000); // the server checks GitHub at most daily

  /* ------------------------------------------------------------------ */
  /* Add from GitHub: pick one of your repos (or paste a link), clone, run */
  /* ------------------------------------------------------------------ */

  const GH_MARK = "M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.53-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.39-5.25 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5z";
  const gh = { status: null, repos: [], selected: null, loading: false, busy: false, timer: null };
  const GH_LINK = /^(?:https?:\/\/github\.com\/|git@github\.com:)?[A-Za-z0-9-]+\/[A-Za-z0-9._-]+?(?:\.git)?\/?$/;

  function ghTimeAgo(iso) {
    const t = Date.parse(iso || "");
    return isNaN(t) ? "" : timeAgo(t / 1000);
  }

  function ghPastedRepo() {
    const q = $("gh-q").value.trim();
    return /github\.com|\//.test(q) && GH_LINK.test(q) ? q.replace(/^https?:\/\/github\.com\//, "").replace(/\.git\/?$|\/$/g, "") : null;
  }

  function renderGitHub() {
    const body = $("gh-body");
    body.textContent = "";
    const st = gh.status;
    const pasted = ghPastedRepo();
    if (pasted) gh.selected = { full_name: pasted, name: pasted.split("/")[1], description: "" };
    if (!st) {
      body.appendChild(el("p", "hint", "Checking GitHub…"));
    } else if (!st.connected && !pasted) {
      const box = el("div", "gh-empty");
      box.appendChild(el("b", null, "Connect GitHub to see your repos"));
      box.appendChild(el("p", "hint", "Or paste a link to any public repo above, like github.com/owner/name."));
      const go = button("btn small primary", "Connect GitHub");
      go.addEventListener("click", () => { hideGitHub(); openSettings("github"); });
      box.appendChild(go);
      body.appendChild(box);
    } else if (pasted) {
      body.appendChild(ghRow({ full_name: pasted, name: pasted.split("/")[1], description: "From the link you pasted" }, true));
    } else if (gh.loading) {
      body.appendChild(el("p", "hint", "Loading your repos…"));
    } else {
      const q = $("gh-q").value.trim().toLowerCase();
      const list = gh.repos.filter((r) => !q || r.full_name.toLowerCase().includes(q) || (r.description || "").toLowerCase().includes(q));
      if (!list.length) body.appendChild(el("p", "hint", q ? "No repo matches “" + q + "”." : "No repos found on this account."));
      list.slice(0, 200).forEach((r) => body.appendChild(ghRow(r, gh.selected && gh.selected.full_name === r.full_name)));
    }
    const sel = gh.selected;
    const dir = st ? st.projects_dir : "";
    $("gh-where").textContent = sel ? "Clones into " + dir.replace(/\/+$/, "") + "/" + sel.name : st ? "Repos are cloned into " + dir : "";
    $("gh-where").title = $("gh-where").textContent;
    $("gh-clone").disabled = !sel || gh.busy;
  }

  function ghRow(r, selected) {
    const row = button("gh-row" + (selected ? " selected" : ""));
    row.setAttribute("aria-pressed", String(!!selected));
    const top = el("div", "gh-row-top");
    top.appendChild(el("b", null, r.full_name));
    if (r.private) top.appendChild(el("span", "set-tag", "Private"));
    if (r.archived) top.appendChild(el("span", "set-tag", "Archived"));
    row.appendChild(top);
    if (r.description) row.appendChild(el("span", "gh-row-desc", r.description));
    const meta = [r.language, r.updated_at ? "updated " + ghTimeAgo(r.updated_at) : ""].filter(Boolean).join(" · ");
    if (meta) row.appendChild(el("span", "gh-row-meta", meta));
    row.addEventListener("click", () => {
      gh.selected = r;
      renderGitHub();
    });
    row.addEventListener("dblclick", () => {
      gh.selected = r;
      cloneFromGitHub();
    });
    return row;
  }

  async function openGitHub() {
    gh.selected = null;
    gh.busy = false;
    $("gh-q").value = "";
    $("gh-backdrop").hidden = false;
    $("gh-q").focus();
    renderGitHub();
    try {
      gh.status = await request("/api/github/status");
    } catch (err) {
      gh.status = { connected: false, projects_dir: "" };
    }
    renderGitHub();
    if (gh.status.connected) {
      gh.loading = true;
      renderGitHub();
      try {
        gh.repos = (await request("/api/github/repos")).repos || [];
      } catch (err) {
        toast("Couldn't load your repos: " + err.message, "err");
      }
      gh.loading = false;
      renderGitHub();
    }
  }

  function hideGitHub() {
    $("gh-backdrop").hidden = true;
  }

  async function cloneFromGitHub() {
    const sel = gh.selected;
    if (!sel || gh.busy) return;
    gh.busy = true;
    const btn = $("gh-clone");
    btn.disabled = true;
    btn.textContent = "Cloning…";
    try {
      const res = await request("/api/github/clone", {
        method: "POST",
        body: JSON.stringify({ repo: sel.full_name, start: $("gh-start").checked, description: sel.description || "" }),
      });
      hideGitHub();
      toast("Added " + res.app.name + (res.app.status === "running" || res.app.status === "starting" ? " — starting it" : ""), "ok");
      if (res.app.status === "running" || res.app.status === "starting") watchToOpen(res.app);
      fetchApps();
    } catch (err) {
      toast("Couldn't add it: " + err.message, "err");
    } finally {
      gh.busy = false;
      btn.textContent = "Clone & add";
      renderGitHub();
    }
  }

  $("btn-github").addEventListener("click", openGitHub);
  $("gh-close").addEventListener("click", hideGitHub);
  $("gh-cancel").addEventListener("click", hideGitHub);
  $("gh-clone").addEventListener("click", cloneFromGitHub);
  $("gh-q").addEventListener("input", () => {
    if (!ghPastedRepo() && gh.selected && !gh.repos.includes(gh.selected)) gh.selected = null;
    renderGitHub();
  });
  $("gh-q").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && gh.selected) cloneFromGitHub();
  });
  $("gh-backdrop").addEventListener("mousedown", (e) => {
    if (e.target === $("gh-backdrop")) hideGitHub();
  });

  /* ------------------------------------------------------------------ */
  /* Settings: AI assistant, Ollama, models, fix guides                  */
  /* ------------------------------------------------------------------ */

  const settings = { open: false, st: null, prefs: { ai_provider: null, local_model: null }, claude: null, about: null, github: null, section: "general" };

  async function saveSetting(changes) {
    try {
      settings.prefs = await request("/api/settings", { method: "PATCH", body: JSON.stringify(changes) });
    } catch (err) {
      toast("Couldn't save the setting: " + err.message, "err");
    }
    return settings.prefs;
  }

  /* ---------- building blocks (same look as the rest of the app) ---------- */

  // Line icons in the app's style (24px grid, 1.8 stroke).
  const SET_ICONS = {
    general: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    ai: '<path d="M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9z"/><path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
    local: '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/><path d="M9.5 3.5v3M14.5 3.5v3M9.5 17.5v3M14.5 17.5v3M3.5 9.5h3M3.5 14.5h3M17.5 9.5h3M17.5 14.5h3"/>',
    models: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>',
    github: '<circle cx="6.5" cy="5.5" r="2"/><circle cx="6.5" cy="18.5" r="2"/><circle cx="17.5" cy="7.5" r="2"/><path d="M6.5 7.5v9M17.5 9.5c0 4-5 3.5-9.5 7.5"/>',
    sharing: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5s-1.1 6.1-3.4 8.5c-2.3-2.4-3.4-5.2-3.4-8.5S9.7 5.9 12 3.5z"/>',
    guides: '<path d="M5 4.5h9.5a3 3 0 0 1 3 3v12H8a3 3 0 0 1-3-3z"/><path d="M5 16.5a3 3 0 0 1 3-3h9.5M9 8.5h5"/>',
    about: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.1"/>',
  };

  const SETTINGS_SECTIONS = [
    { id: "general", title: "General", icon: "general", hint: "How Homeport looks and behaves." },
    { id: "ai", title: "AI assistant", icon: "ai", hint: "Used by Ask AI (⌘J) and “Ask AI to fix” on crashed apps. It only runs when you send a message." },
    { id: "local", title: "Local AI", icon: "local", hint: "Run a free, open AI model on this computer with Ollama. Nothing you ask leaves it." },
    { id: "models", title: "Models", icon: "models", hint: "Download one model to start. Bigger models give better answers but are slower and need more memory." },
    { id: "github", title: "GitHub", icon: "github", hint: "Clone your repos in one click and see CI results and pull requests on your apps. Homeport only talks to GitHub, and your login stays on this computer." },
    { id: "sharing", title: "Sharing & feedback", icon: "sharing", hint: "Defaults for public links, and how you appear in feedback threads." },
    { id: "guides", title: "Fix guides", icon: "guides", hint: "Step-by-step guides the local model follows for common problems. The right one is picked automatically." },
    { id: "about", title: "About", icon: "about", hint: "The home for every local project you run. Free and open source." },
  ];

  function setIcon(name) {
    const span = el("span", "nav-ico");
    span.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + SET_ICONS[name] + "</svg>"; // static markup
    return span;
  }

  function setGroup(title, footnote) {
    const wrap = el("div", "set-block");
    if (title) wrap.appendChild(el("h4", "set-block-title", title));
    const group = el("div", "set-group");
    wrap.appendChild(group);
    if (footnote) wrap.appendChild(el("p", "hint set-foot", footnote));
    return { wrap, group };
  }

  // One row: label (+ optional sub line) on the left, controls on the right.
  function setRow(label, sub, controls) {
    const row = el("div", "set-row");
    const text = el("div", "set-row-text");
    text.appendChild(el("span", "set-row-label", label));
    if (sub) text.appendChild(el("span", "set-row-sub", sub));
    row.appendChild(text);
    const right = el("div", "set-row-right");
    (controls || []).forEach((c) => c && right.appendChild(c));
    row.appendChild(right);
    return row;
  }

  function setSwitch(on, label, onChange) {
    const sw = button("set-switch" + (on ? " on" : ""));
    sw.setAttribute("role", "switch");
    sw.setAttribute("aria-checked", String(on));
    sw.setAttribute("aria-label", label);
    sw.addEventListener("click", () => {
      const next = sw.getAttribute("aria-checked") !== "true";
      sw.setAttribute("aria-checked", String(next));
      sw.classList.toggle("on", next);
      onChange(next);
    });
    return sw;
  }

  // The app's segmented control.
  function setSeg(options, value, onChange) {
    const seg = el("div", "seg");
    seg.setAttribute("role", "group");
    options.forEach(([v, text]) => {
      const b = button(v === value ? "active" : "", text);
      b.addEventListener("click", () => {
        seg.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
        onChange(v);
      });
      seg.appendChild(b);
    });
    return seg;
  }

  function setSelect(options, value, onChange) {
    const sel = el("select", "input small set-select");
    options.forEach(([v, text]) => {
      const o = el("option", null, text);
      o.value = v;
      sel.appendChild(o);
    });
    sel.value = value;
    sel.addEventListener("change", () => onChange(sel.value));
    return sel;
  }

  function setValue(text, kind) {
    return el("span", "set-value" + (kind ? " " + kind : ""), text);
  }

  function setLink(text, href) {
    const a = el("a", "btn small", text);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener";
    return a;
  }

  /* ---------- the Settings dialog ---------- */

  function renderSettingsNav() {
    const nav = $("settings-nav");
    nav.textContent = "";
    SETTINGS_SECTIONS.forEach((s) => {
      const item = button("nav-item" + (settings.section === s.id ? " active" : ""));
      item.appendChild(setIcon(s.icon));
      item.appendChild(el("span", "set-nav-label", s.title));
      if (s.id === "models" && settings.st && settings.st.pull && settings.st.pull.active) {
        const pull = settings.st.pull;
        item.appendChild(el("span", "count", pull.total ? Math.round((100 * pull.completed) / pull.total) + "%" : "…"));
      }
      item.addEventListener("click", () => {
        settings.section = s.id;
        $("settings-body").scrollTop = 0;
        renderSettings();
      });
      nav.appendChild(item);
    });
  }

  function renderSettings() {
    if (!SETTINGS_SECTIONS.some((s) => s.id === settings.section)) settings.section = "general";
    renderSettingsNav();
    const sec = SETTINGS_SECTIONS.find((s) => s.id === settings.section);
    const body = $("settings-body");
    const keep = body.scrollTop;
    body.textContent = "";
    const head = el("div", "set-head");
    head.appendChild(el("h3", null, sec.title));
    head.appendChild(el("p", "hint", sec.hint));
    body.appendChild(head);
    ({ general: paneGeneral, ai: paneAi, local: paneLocal, models: paneModels, github: paneGitHub, sharing: paneSharing,
       guides: paneGuides, about: paneAbout })[sec.id](body);
    body.scrollTop = keep;
  }

  function paneGeneral(body) {
    const g = setGroup("Appearance");
    const theme = loadPref("theme", "system");
    g.group.appendChild(setRow("Theme", null, [setSeg([["system", "System"], ["light", "Light"], ["dark", "Dark"]],
      theme === "light" || theme === "dark" ? theme : "system", (v) => setThemeMode(v))]));
    body.appendChild(g.wrap);

    const g2 = setGroup("Apps");
    g2.group.appendChild(setRow("Open apps when they start", "A new browser tab opens as soon as the app is ready",
      [setSwitch(loadPref("auto_open", "1") === "1", "Open apps when they start", (on) => savePref("auto_open", on ? "1" : "0"))]));
    body.appendChild(g2.wrap);

    g2.group.appendChild(setRow("Check for updates", "Once a day, Homeport asks GitHub for the newest version and tells you",
      [setSwitch(!upd.st || upd.st.enabled, "Check for updates", async (on) => {
        await saveSetting({ check_updates: on });
        await loadUpdate(on);
      })]));
    const mod = IS_APPLE ? "⌘" : "Ctrl ";
    const g3 = setGroup("Keyboard shortcuts");
    [
      ["Command palette", mod + "K"],
      ["Ask AI", mod + "J"],
      ["Search apps", "/"],
      ["Close a dialog or panel", "Esc"],
      ["Add a comment (on a shared page)", "C"],
    ].forEach(([label, key]) => g3.group.appendChild(setRow(label, null, [el("kbd", "set-kbd", key)])));
    body.appendChild(g3.wrap);
  }

  function paneAi(body) {
    const st = settings.st;
    const claude = settings.claude;
    const g = setGroup(null);
    g.group.appendChild(setRow("Assistant", ai.provider === "local" ? "Free and offline, on this computer" : "Most capable, uses your Claude account",
      [setSeg([["claude", "Claude Code"], ["local", "Local model"]], ai.provider, (v) => {
        if (ai.running) return toast("Wait for the assistant to finish first", "warn");
        aiSetProvider(v);
        renderSettings();
      })]));
    g.group.appendChild(setRow("Default mode", "Act can change apps and files; Ask only looks and explains",
      [setSeg([["act", "Act"], ["ask", "Ask only"]], ai.mode, (v) => aiSetMode(v))]));
    if (ai.provider === "claude") {
      const opts = [["sonnet", "Sonnet"], ["opus", "Opus"], ["haiku", "Haiku"], ["", "Account default"]];
      if (ai.model.value === "__custom") opts.push(["__custom", "Custom (" + (ai.modelCustom.value || "…") + ")"]);
      g.group.appendChild(setRow("Claude model", null, [setSelect(opts, ai.model.value, (v) => {
        ai.model.value = v;
        ai.model.dispatchEvent(new Event("change"));
      })]));
    } else if (st && st.models && st.models.length) {
      g.group.appendChild(setRow("Local model", null, [setSelect(st.models.map((m) => [m.name, m.name]), ai.localSel.value, (v) => {
        ai.localSel.value = v;
        ai.localSel.dispatchEvent(new Event("change"));
      })]));
    }
    body.appendChild(g.wrap);

    const s = setGroup("Status");
    s.group.appendChild(setRow("Claude Code", claude && claude.version ? claude.version : "The claude command on this computer",
      [setValue(claude ? (claude.available ? "Installed" : "Not installed") : "Checking…", claude ? (claude.available ? "ok" : "") : "")]));
    const ready = aiLocalReady(st);
    let text = "Checking…";
    if (st) text = ready ? "Ready · " + (ai.localSel.value || st.models[0].name) : st.running ? "No model yet" : st.installed ? "Ollama isn't running" : "Ollama isn't installed";
    const setUp = st && !ready ? button("btn small", "Set up") : null;
    if (setUp) setUp.addEventListener("click", () => { settings.section = st.running ? "models" : "local"; renderSettings(); });
    s.group.appendChild(setRow("Local model", "Runs with Ollama", [setValue(text, ready ? "ok" : ""), setUp]));
    body.appendChild(s.wrap);
  }

  function paneLocal(body) {
    const st = settings.st;
    if (!st) return body.appendChild(el("p", "hint", "Checking…"));
    const g = setGroup("Ollama");
    const controls = [];
    let state;
    if (st.running) {
      state = setValue("Running", "ok");
    } else if (st.installed) {
      state = setValue("Not running", "warn");
      const start = button("btn small primary", "Start Ollama");
      start.addEventListener("click", async () => {
        start.disabled = true;
        start.textContent = "Starting…";
        try {
          await request("/api/local-ai/start", { method: "POST" });
        } catch (err) {
          toast(err.message, "err");
        }
        refreshSettings();
      });
      controls.push(start);
    } else {
      state = setValue("Not installed", "warn");
      const get = setLink("Download Ollama", st.download_url);
      get.classList.add("primary");
      const again = button("btn small", "Check again");
      again.addEventListener("click", () => refreshSettings());
      controls.push(get, again);
    }
    g.group.appendChild(setRow("Status", st.running && st.version && st.version !== "unknown" ? "Version " + st.version : "Free, about 0.5–2 GB", [state].concat(controls)));
    g.group.appendChild(setRow("Address", null, [setValue(st.url)]));
    body.appendChild(g.wrap);

    const m = setGroup("This computer", "Models are stored by Ollama (in ~/.ollama), not inside Homeport.");
    if (st.ram_gb) m.group.appendChild(setRow("Memory", null, [setValue(st.ram_gb.toFixed(0) + " GB")]));
    if (typeof st.disk_free_gb === "number") m.group.appendChild(setRow("Free disk space", null, [setValue(st.disk_free_gb.toFixed(0) + " GB", st.disk_free_gb > 6 ? "" : "warn")]));
    m.group.appendChild(setRow("Space used by models", null, [setValue((st.models_size_gb || 0).toFixed(1) + " GB")]));
    body.appendChild(m.wrap);
  }

  function paneModels(body) {
    const st = settings.st;
    if (!st) return body.appendChild(el("p", "hint", "Checking…"));
    if (!st.running) {
      const g = setGroup(null);
      const go = button("btn small primary", "Open Local AI");
      go.addEventListener("click", () => { settings.section = "local"; renderSettings(); });
      g.group.appendChild(setRow("Ollama isn't running", "Start or install it to download models", [go]));
      body.appendChild(g.wrap);
    }
    const installed = (st.catalog || []).filter((c) => c.installed);
    const extra = (st.models || []).filter((m) => !(st.catalog || []).some((c) => sameModel(c.id, m.name)))
      .map((m) => ({ id: m.name, name: m.name, size_bytes: m.size, installed: true }));
    const g1 = setGroup("Downloaded");
    if (!installed.length && !extra.length) g1.group.appendChild(setRow("No models yet", "Qwen3 4B (about 2.5 GB) is a good first choice"));
    installed.concat(extra).forEach((m) => g1.group.appendChild(modelRow(st, m)));
    body.appendChild(g1.wrap);
    const avail = (st.catalog || []).filter((c) => !c.installed);
    if (avail.length) {
      const g2 = setGroup("Available", "Sizes are approximate. Downloads keep going in the background.");
      avail.forEach((m) => g2.group.appendChild(modelRow(st, m)));
      body.appendChild(g2.wrap);
    }
  }

  function paneGitHub(body) {
    const st = settings.github;
    if (!st) {
      body.appendChild(el("p", "hint", "Checking…"));
      request("/api/github/status").then((g) => { settings.github = g; if (settings.open && settings.section === "github") renderSettings(); }).catch(() => {});
      return;
    }
    const g = setGroup("Account");
    if (st.connected) {
      const via = st.source === "gh" ? "Through GitHub CLI" : "Signed in with Homeport";
      const out = button("btn small", st.source === "gh" ? "Use another account" : "Disconnect");
      out.addEventListener("click", async () => {
        if (st.source === "gh") {
          toast("Homeport uses your GitHub CLI login. Paste a token below to use another account.", "warn");
          settings.github = Object.assign({}, st, { connected: false, forceSetup: true });
          return renderSettings();
        }
        await request("/api/github/disconnect", { method: "POST" }).catch((e) => toast(e.message, "err"));
        settings.github = null;
        renderSettings();
      });
      g.group.appendChild(setRow("@" + st.user.login, (st.user.name && st.user.name !== st.user.login ? st.user.name + " · " : "") + via,
        [setValue("Connected", "ok"), out]));
      body.appendChild(g.wrap);
    } else {
      // One clear way: "Connect GitHub". The rest is for advanced setups, folded away.
      const showOthers = !st.device_flow || settings.githubOthers;
      if (st.device_flow) {
        const connect = button("btn primary gh-connect", null);
        connect.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="' + GH_MARK + '"/></svg>'; // static icon
        connect.appendChild(el("span", null, "Connect GitHub"));
        connect.addEventListener("click", () => ghDeviceSignIn(body));
        const row = setRow("Not connected", "GitHub opens in your browser, you click Authorize, and you're done.", [connect]);
        g.group.appendChild(row);
      }
      if (showOthers) {
        g.group.appendChild(setRow("GitHub CLI", st.gh_installed ? "Run gh auth login in a terminal, then come back — Homeport uses it automatically" : "If you use GitHub CLI, Homeport uses its login automatically",
          [setValue(st.gh_installed ? "Not logged in" : "Not installed")]));
        const tok = el("input", "input small set-input");
        tok.type = "password";
        tok.placeholder = "ghp_… or github_pat_…";
        tok.autocomplete = "off";
        const save = button("btn small", "Connect");
        save.addEventListener("click", async () => {
          save.disabled = true;
          try {
            await request("/api/github/token", { method: "POST", body: JSON.stringify({ token: tok.value.trim() }) });
            toast("GitHub connected", "ok");
            settings.github = null;
            renderSettings();
          } catch (err) {
            toast(err.message, "err");
            save.disabled = false;
          }
        });
        const link = el("a", "set-inline-link", "Create a token");
        link.href = "https://github.com/settings/tokens/new?scopes=repo,read:user&description=Homeport";
        link.target = "_blank";
        link.rel = "noopener";
        const sub = el("span", "set-row-sub");
        sub.append("For GitHub Enterprise or locked-down setups. ", link);
        const row = setRow("Personal access token", null, [tok, save]);
        row.querySelector(".set-row-text").appendChild(sub);
        g.group.appendChild(row);
      }
      body.appendChild(g.wrap);
      if (st.device_flow && !settings.githubOthers) {
        const more = button("link-btn gh-more", "Other ways to connect");
        more.addEventListener("click", () => { settings.githubOthers = true; renderSettings(); });
        g.wrap.appendChild(more);
      }
    }

    const p = setGroup("Cloning", "“Add from GitHub” puts each repo in its own folder here.");
    const choose = button("btn small", "Change…");
    choose.addEventListener("click", async () => {
      try {
        const res = await request("/api/pick-folder", { method: "POST" });
        if (!res.path) return;
        await saveSetting({ projects_dir: res.path });
        settings.github = null;
        renderSettings();
      } catch (err) {
        toast(err.message, "err");
      }
    });
    p.group.appendChild(setRow("Projects folder", st.projects_dir, [choose]));
    const add = button("btn small", "Add from GitHub…");
    add.addEventListener("click", () => { hideSettings(); openGitHub(); });
    p.group.appendChild(setRow("Clone a repo", "Pick one of your repos or paste a link", [add]));
    body.appendChild(p.wrap);
  }

  // "Sign in with GitHub": show the code, open GitHub, wait until it's entered.
  async function ghDeviceSignIn(body) {
    let start;
    try {
      start = await request("/api/github/device/start", { method: "POST" });
    } catch (err) {
      return toast(err.message, "err");
    }
    const g = setGroup("Enter this code on GitHub");
    const code = el("div", "gh-code", start.user_code);
    const copy = button("btn small", "Copy code");
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(start.user_code);
        toast("Code copied — paste it on GitHub", "ok");
      } catch (e) {
        window.prompt("Copy this code:", start.user_code);
      }
    });
    const open = el("a", "btn small primary", "Open GitHub");
    open.href = start.verification_uri;
    open.target = "_blank";
    open.rel = "noopener";
    // Put the code on the clipboard, so on GitHub it's just paste → Continue.
    let copied = false;
    try {
      await navigator.clipboard.writeText(start.user_code);
      copied = true;
    } catch (e) {
      /* no clipboard access: the Copy code button is right there */
    }
    const waiting = el("span", "set-row-sub", (copied ? "Code copied — paste it on GitHub (⌘V), then click Continue and Authorize. " : "Enter this code on GitHub, then click Continue and Authorize. ") + "Waiting…");
    const row = setRow("Your code", null, [copy, open]);
    row.querySelector(".set-row-text").append(code, waiting);
    g.group.appendChild(row);
    body.insertBefore(g.wrap, body.children[1] || null);
    body.querySelectorAll(".gh-connect").forEach((b) => { b.disabled = true; }); // already waiting for approval
    window.open(start.verification_uri, "_blank", "noopener");
    let interval = (start.interval || 5) * 1000;
    const until = Date.now() + (start.expires_in || 900) * 1000;
    const tick = async () => {
      if (!settings.open || Date.now() > until) return;
      let res;
      try {
        res = await request("/api/github/device/poll", { method: "POST" });
      } catch (err) {
        res = { status: "pending" };
      }
      if (res.status === "done") {
        toast("Connected to GitHub as @" + ((res.user && res.user.login) || ""), "ok");
        settings.github = null;
        return renderSettings();
      }
      if (res.status === "expired" || res.status === "denied") {
        waiting.textContent = res.status === "denied" ? "The sign-in was cancelled on GitHub." : "The code expired — try again.";
        return;
      }
      if (res.status === "slow_down") interval += 5000;
      window.setTimeout(tick, interval);
    };
    window.setTimeout(tick, interval);
  }

  function paneSharing(body) {
    const g = setGroup("New share links");
    g.group.appendChild(setRow("Link stops after", null, [setSelect(
      [["15", "15 minutes"], ["60", "1 hour"], ["480", "8 hours"], ["1440", "24 hours"], ["", "Never"]],
      loadPref("share_expiry", "60"), (v) => savePref("share_expiry", v))]));
    g.group.appendChild(setRow("Let visitors leave feedback", "Anyone with the link sees the open comments",
      [setSwitch(loadPref("share_feedback", "0") === "1", "Let visitors leave feedback", (on) => savePref("share_feedback", on ? "1" : "0"))]));
    body.appendChild(g.wrap);
    const g2 = setGroup("Feedback", "Shown on replies you write in the Feedback window.");
    const name = el("input", "input small set-input");
    name.value = loadPref("fb_owner_name", "");
    name.placeholder = "Owner";
    name.maxLength = 60;
    name.addEventListener("change", () => savePref("fb_owner_name", name.value.trim()));
    g2.group.appendChild(setRow("Your name", null, [name]));
    body.appendChild(g2.wrap);
  }

  function paneGuides(body) {
    const st = settings.st;
    const g = setGroup(null, "Add your own as a Markdown file in Homeport's skills/ folder.");
    const skills = (st && st.skills) || [];
    skills.forEach((s) => g.group.appendChild(setRow(s.title)));
    if (!skills.length) g.group.appendChild(setRow(st ? "No guides found" : "Checking…"));
    body.appendChild(g.wrap);
  }

  function paneAbout(body) {
    const info = settings.about;
    const g = setGroup(null);
    const us = upd.st;
    const verState = us && us.available ? setValue("v" + us.latest + " available", "warn") : us && us.latest ? setValue("Up to date", "ok") : null;
    const checkBtn = button("btn small", us && us.available ? "Update…" : "Check now");
    checkBtn.addEventListener("click", async () => {
      if (us && us.available) return openUpdate();
      checkBtn.disabled = true;
      checkBtn.textContent = "Checking…";
      const st = await loadUpdate(true);
      if (st && st.error) toast("Couldn't check: " + st.error, "warn");
      else if (st && !st.available) toast("Homeport " + st.current + " is the latest version", "ok");
      renderSettings();
    });
    g.group.appendChild(setRow("Version", us ? us.current : "…", [verState, checkBtn]));
    g.group.appendChild(setRow("Homeport address", null, [setValue(info ? info.address : window.location.origin)]));
    if (info) {
      const open = button("btn small", "Open folder");
      open.addEventListener("click", () => request("/api/about/open-data", { method: "POST" }).catch((e) => toast(e.message, "err")));
      g.group.appendChild(setRow("Data folder", info.data_dir, [open]));
    }
    g.group.appendChild(setRow("License", null, [setValue("MIT — free and open source")]));
    body.appendChild(g.wrap);
    const g2 = setGroup("Links");
    g2.group.appendChild(setRow("Website", null, [setLink("Open", "https://homeport.ferdousmikdad.com")]));
    g2.group.appendChild(setRow("Help & docs", null, [setLink("Open", "https://homeport.ferdousmikdad.com/docs")]));
    g2.group.appendChild(setRow("Source code", "github.com/ferdousmikdad/Homeport", [setLink("GitHub", "https://github.com/ferdousmikdad/Homeport")]));
    g2.group.appendChild(setRow("Report a problem", null, [setLink("New issue", "https://github.com/ferdousmikdad/Homeport/issues")]));
    body.appendChild(g2.wrap);
  }

  function modelRow(st, m) {
    const pull = st.pull && sameModel(st.pull.model, m.id) ? st.pull : null;
    if (pull && pull.active) m = Object.assign({}, m, { installed: false }); // half-downloaded
    const selected = m.installed && ai.localSel.value && sameModel(ai.localSel.value, m.id);
    const bits = [];
    if (m.note) bits.push(m.note);
    if (m.size_gb) bits.push(m.size_gb + " GB");
    else if (m.size_bytes) bits.push(fmtGB(m.size_bytes));
    if (m.ram_gb) bits.push("needs " + m.ram_gb + " GB memory");
    let sub = bits.join(" · ");
    if (m.ram_gb && st.ram_gb && m.ram_gb > st.ram_gb + 0.5) sub += " — may be slow here";
    if (pull && pull.error && !pull.active && !pull.cancelled && !m.installed) sub = "Download failed: " + pull.error;
    const controls = [];
    if (m.id === st.recommended && !m.installed && !(pull && pull.active)) controls.push(el("span", "set-tag", "Recommended"));
    if (pull && pull.active) {
      const pct = pull.total ? Math.min(100, Math.round((100 * pull.completed) / pull.total)) : 0;
      controls.push(setValue(pull.total ? pct + "% of " + fmtGB(pull.total) : "Starting…"));
      const prog = el("div", "set-progress");
      const bar = el("div", "set-progress-bar");
      bar.style.width = pct + "%";
      prog.appendChild(bar);
      controls.push(prog);
      const cancel = button("btn small", "Cancel");
      cancel.addEventListener("click", async () => {
        cancel.disabled = true;
        await request("/api/local-ai/pull/cancel", { method: "POST" }).catch(() => {});
        refreshSettings();
      });
      controls.push(cancel);
    } else if (m.installed) {
      if (selected) {
        controls.push(setValue("In use", "ok"));
      } else {
        const use = button("btn small primary", "Use");
        use.addEventListener("click", async () => {
          ai.localSel.value = m.id;
          ai.sessionId = null;
          await saveSetting({ local_model: m.id });
          if (ai.provider !== "local") aiSetProvider("local");
          refreshSettings();
        });
        controls.push(use);
      }
      const del = button("btn small ghost", "Remove");
      del.title = "Delete this model and free its disk space";
      del.addEventListener("click", async () => {
        if (del.dataset.armed !== "1") {
          del.dataset.armed = "1";
          del.textContent = "Remove?";
          window.setTimeout(() => {
            del.dataset.armed = "";
            del.textContent = "Remove";
          }, 3000);
          return;
        }
        del.disabled = true;
        try {
          await request("/api/local-ai/delete", { method: "POST", body: JSON.stringify({ model: m.id }) });
          toast("Removed " + m.name, "ok");
        } catch (err) {
          toast(err.message, "err");
        }
        refreshSettings();
      });
      controls.push(del);
    } else {
      const get = button("btn small", "Download");
      get.disabled = !st.running || !!(st.pull && st.pull.active);
      if (st.pull && st.pull.active) get.title = "Wait for the current download to finish";
      get.addEventListener("click", async () => {
        get.disabled = true;
        try {
          await request("/api/local-ai/pull", { method: "POST", body: JSON.stringify({ model: m.id }) });
        } catch (err) {
          toast(err.message, "err");
        }
        refreshSettings();
      });
      controls.push(get);
    }
    return setRow(m.name, sub, controls);
  }

  async function refreshSettings() {
    try {
      const [st, prefs] = await Promise.all([aiLocalStatus(), request("/api/settings")]);
      settings.st = st;
      settings.prefs = prefs;
    } catch (err) {
      toast(err.message, "err");
    }
    if (settings.open) renderSettings();
    if (ai.provider === "local" && !ai.panel.hidden) aiRefresh(false);
  }

  async function openSettings(section) {
    if (typeof section === "string") settings.section = section;
    settings.open = true;
    settings.github = null;
    settings.githubOthers = false;
    if (!settings.about) request("/api/about").then((a) => { settings.about = a; if (settings.open) renderSettings(); }).catch(() => {});
    $("settings-backdrop").hidden = false;
    renderSettings();
    request("/api/ai/status")
      .then((c) => {
        settings.claude = c;
        if (settings.open) renderSettings();
      })
      .catch(() => {});
    await refreshSettings();
  }

  function hideSettings() {
    settings.open = false;
    $("settings-backdrop").hidden = true;
  }

  // A model download runs on the server. While one is active, poll its progress
  // for the Settings dialog and the badge on the sidebar's Settings item.
  let pullTimer = null;
  let pullSeen = null;

  function showPullBadge(pull) {
    const badge = $("settings-badge");
    if (pull && pull.active) {
      badge.hidden = false;
      badge.textContent = pull.total ? Math.round((100 * pull.completed) / pull.total) + "%" : "…";
      badge.title = "Downloading " + pull.model;
    } else {
      badge.hidden = true;
    }
  }

  function watchPull(st) {
    const pull = st && st.pull;
    showPullBadge(pull);
    if (pull && pull.active) {
      pullSeen = pull.model;
      if (!pullTimer) {
        pullTimer = window.setInterval(async () => {
          let next;
          try {
            next = await request("/api/local-ai/status");
          } catch (err) {
            return;
          }
          ai.localStatus = next;
          if (!(next.pull && next.pull.active)) {
            window.clearInterval(pullTimer);
            pullTimer = null;
            aiFillLocalModels(next);
            if (next.pull && pullSeen === next.pull.model) {
              if (next.pull.done) toast(next.pull.model + " is downloaded and ready", "ok");
              else if (!next.pull.cancelled) toast("Download failed: " + (next.pull.error || "unknown error"), "err");
            }
            pullSeen = null;
            if (ai.provider === "local" && !ai.panel.hidden) aiRefresh(false);
          }
          showPullBadge(next.pull);
          if (settings.open) {
            settings.st = next;
            renderSettings();
          }
        }, 1000);
      }
    }
  }

  $("btn-settings").addEventListener("click", () => openSettings());

  $("settings-close").addEventListener("click", hideSettings);
  $("settings-backdrop").addEventListener("mousedown", (e) => {
    if (e.target === $("settings-backdrop")) hideSettings();
  });

  /* ---------- provider switching and status ---------- */

  function aiApplyProvider() {
    const local = ai.provider === "local";
    ai.providerSel.value = ai.provider;
    ai.modelWrap.hidden = local;
    ai.modelCustom.hidden = local || ai.model.value !== "__custom";
    ai.localWrap.hidden = !local;
    ai.modelsBtn.hidden = !local;
    const dot = ai.sub.querySelector(".ai-online");
    ai.sub.textContent = local ? "Local model · offline · runs only when you send" : "Claude · runs only when you send";
    if (dot) ai.sub.prepend(dot);
  }

  function aiSetProvider(provider) {
    ai.provider = provider === "local" ? "local" : "claude";
    aiSavePref("provider", ai.provider);
    saveSetting({ ai_provider: ai.provider });
    ai.sessionId = null;
    ai.meta.textContent = "";
    aiApplyProvider();
    aiRenderEmpty(); // a new conversation with the other assistant
    aiRefresh(false);
  }

  // Check the selected assistant and show the chat, or its setup screen.
  async function aiRefresh(showSetup) {
    if (ai.provider === "claude") {
      try {
        const st = await request("/api/ai/status");
        ai.claudeAvailable = !!st.available;
        if (!st.available) {
          ai.meta.textContent = "claude CLI not found — install Claude Code and log in, or switch to Local model";
          ai.send.disabled = true;
        } else {
          ai.send.disabled = false;
          if (!ai.meta.textContent && st.version) ai.meta.textContent = st.version;
        }
      } catch (err) {
        ai.meta.textContent = err.message;
      }
      if (ai.log.querySelector(".ai-setup")) aiRenderEmpty();
      return;
    }
    let st;
    try {
      st = await aiLocalStatus();
    } catch (err) {
      ai.meta.textContent = err.message;
      return;
    }
    const ready = aiLocalReady(st);
    ai.send.disabled = !ready;
    if (!ready) ai.meta.textContent = st.running ? "Download a model in Settings to start" : "Set up Ollama in Settings to start";
    else if (!ai.running && /Settings to start/.test(ai.meta.textContent)) ai.meta.textContent = "";
    if (!ready) {
      if (!ai.running) aiRenderSetupCard(st);
    } else if (ai.log.querySelector(".ai-setup")) {
      aiRenderEmpty();
    }
  }

  async function openAi() {
    if (!els.drawer.hidden) closeLogs();
    ai.panel.hidden = false;
    document.body.classList.add("ai-open");
    aiFab.classList.remove("unread");
    aiFab.setAttribute("aria-expanded", "true");
    ai.input.focus();
    await aiRefresh(false);
  }

  function closeAi() {
    ai.panel.hidden = true;
    document.body.classList.remove("ai-open");
    aiFab.setAttribute("aria-expanded", "false");
  }

  ai.model.value = aiPref("model", "sonnet");
  if (ai.model.selectedIndex < 0) ai.model.value = "sonnet";
  ai.modelCustom.value = aiPref("model_custom", "");
  ai.provider = aiPref("provider", "claude") === "local" ? "local" : "claude"; // until the server answers
  aiApplyProvider();
  aiSetMode(aiPref("mode", "act"));
  aiRenderEmpty();

  ai.providerSel.addEventListener("change", () => {
    if (ai.running) {
      ai.providerSel.value = ai.provider;
      return;
    }
    aiSetProvider(ai.providerSel.value);
  });
  ai.localSel.addEventListener("change", () => {
    ai.sessionId = null;
    if (ai.localSel.value) saveSetting({ local_model: ai.localSel.value });
  });
  ai.modelsBtn.addEventListener("click", () => openSettings("models"));
  ai.model.addEventListener("change", () => {
    aiSavePref("model", ai.model.value);
    ai.modelCustom.hidden = ai.model.value !== "__custom";
    if (!ai.modelCustom.hidden) ai.modelCustom.focus();
  });
  ai.modelCustom.addEventListener("change", () => aiSavePref("model_custom", ai.modelCustom.value.trim()));
  ai.modeSeg.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-mode]");
    if (b) aiSetMode(b.dataset.mode);
  });
  const aiFab = $("ai-fab");
  aiFab.addEventListener("click", () => (ai.panel.hidden ? openAi() : closeAi()));
  $("ai-close").addEventListener("click", closeAi);
  $("ai-new").addEventListener("click", () => {
    if (ai.running) return;
    ai.sessionId = null;
    ai.appId = null;
    ai.meta.textContent = "";
    ai.reload.hidden = true;
    aiRenderEmpty();
    aiRefresh(false);
    ai.input.focus();
  });
  ai.reload.addEventListener("click", () => window.location.reload());
  ai.form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (ai.running) {
      aiStop();
      return;
    }
    const prompt = ai.input.value.trim();
    if (!prompt || ai.send.disabled) return;
    if (ai.provider === "claude" && ai.model.value === "__custom" && !aiModel()) {
      toast("Enter a model id or pick a model", "warn");
      ai.modelCustom.focus();
      return;
    }
    if (ai.provider === "local" && !aiModel()) {
      toast("Download a model first", "warn");
      openSettings();
      return;
    }
    ai.input.value = "";
    aiSend(prompt);
  });
  ai.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      ai.form.requestSubmit();
    }
  });

  // Sidebar: collapse (remembered per browser) and collapsible Categories.
  function setSidebarHidden(hidden) {
    document.body.classList.toggle("side-hidden", hidden);
    savePref("side_hidden", hidden ? "1" : "0");
  }
  if (loadPref("side_hidden", "0") === "1") document.body.classList.add("side-hidden");
  $("btn-collapse").addEventListener("click", () => setSidebarHidden(true));
  $("btn-sidebar").addEventListener("click", () => setSidebarHidden(!document.body.classList.contains("side-hidden")));
  const catToggle = $("cat-toggle");
  function setCatsOpen(open) {
    catToggle.setAttribute("aria-expanded", String(open));
    $("cat-section").classList.toggle("collapsed", !open);
    savePref("cats_open", open ? "1" : "0");
  }
  setCatsOpen(loadPref("cats_open", "1") === "1");
  catToggle.addEventListener("click", () => setCatsOpen(catToggle.getAttribute("aria-expanded") !== "true"));

  // The AI button is always there: Claude Code when it's installed, otherwise
  // the optional local model (set up from the chat panel).
  aiFab.hidden = false;
  // The chosen assistant is saved in Homeport (shared by every window). With no
  // choice yet: Claude Code when it's installed, otherwise the local model.
  Promise.all([request("/api/settings"), request("/api/ai/status").catch(() => ({ available: false }))])
    .then(([prefs, st]) => {
      settings.prefs = prefs;
      ai.claudeAvailable = !!(st && st.available);
      const chosen = prefs.ai_provider || (ai.claudeAvailable ? "claude" : "local");
      if (chosen !== ai.provider) {
        ai.provider = chosen;
        aiApplyProvider();
        aiRenderEmpty();
      }
      aiSavePref("provider", ai.provider);
    })
    .catch(() => {});
  // Show a model download that is still running (e.g. after a reload).
  request("/api/local-ai/status")
    .then((st) => {
      ai.localStatus = st;
      aiFillLocalModels(st);
      watchPull(st);
    })
    .catch(() => {});

  // Shortcut hints: ⌘ on Apple devices, Ctrl elsewhere.
  if (!IS_APPLE) {
    document.querySelectorAll(".cmdk-hint").forEach((k) => (k.textContent = "Ctrl K"));
    const aiBtn = document.getElementById("ai-fab");
    if (aiBtn) aiBtn.title = "Ask AI (Ctrl+J)";
  }

  // Ask the server which OS it runs on, for "Open in Finder / Explorer" wording.
  request("/api/health")
    .then((h) => {
      if (h && h.can_quit) {
        canQuit = true;
        const btn = document.getElementById("btn-quit");
        if (btn) btn.hidden = false;
      }
      if (h && h.platform && h.platform !== serverPlatform) {
        serverPlatform = h.platform;
        const label = FOLDER_LABEL[serverPlatform] || "Open folder";
        document.querySelectorAll(".mi-folder").forEach((b) => (b.textContent = label));
      }
    })
    .catch(() => {});

  render();
  startSSE();
})();

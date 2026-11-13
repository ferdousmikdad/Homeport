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
      // Flip upward when the menu would run off the bottom of the viewport.
      menu.classList.remove("menu-up");
      const rect = menu.getBoundingClientRect();
      if (rect.bottom > window.innerHeight - 8) menu.classList.add("menu-up");
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
    const subtitle = el("div", "card-sub");
    const status = el("span", "status");
    status.appendChild(el("span", "status-dot"));
    const statusText = el("span", null);
    status.appendChild(statusText);
    const tech = el("span", "card-tech");
    const portLink = el("a", "port-link");
    portLink.target = "_blank";
    portLink.rel = "noopener noreferrer";
    const portNone = el("span", "muted", "No port");
    const health = el("span", "health");
    const gitChip = el("span", "git-chip");
    const category = button("tag category", null); // kept for updateCard; shown via sidebar
    subtitle.appendChild(status);
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

    // Alert: crash reason or port conflict
    const alert = el("div", "card-alert");
    const alertText = el("span", "card-alert-text");
    const alertBtn = button("btn small danger", "Kill & start");
    const whyBtn = button("btn small why-btn", "Why?");
    whyBtn.title = "Explain the crash and suggest a fix";
    alert.appendChild(alertText);
    alert.appendChild(whyBtn);
    alert.appendChild(alertBtn);

    // Public share link
    const shareBar = el("div", "share-bar");
    const shareDot = el("span", "share-dot");
    const shareText = el("span", "share-text");
    const shareLink = el("a", "share-link");
    shareLink.target = "_blank";
    shareLink.rel = "noopener noreferrer";
    const shareMeta = el("span", "share-meta");
    const shareQr = button("btn small ghost", "QR");
    shareQr.title = "Show a QR code to open it on a phone";
    const shareCopy = button("btn small ghost", "Copy");
    const shareStop = button("btn small ghost", "Stop");
    shareBar.appendChild(shareDot);
    shareBar.appendChild(shareText);
    shareBar.appendChild(shareLink);
    shareBar.appendChild(shareMeta);
    shareBar.appendChild(shareQr);
    shareBar.appendChild(shareCopy);
    shareBar.appendChild(shareStop);

    // Stats
    const stats = el("div", "stats");
    const uptimeStat = createStat("Uptime");
    const cpuStat = createStat("CPU");
    const memStat = createStat("Memory");
    const restartsStat = createStat("Restarts", "stat-restarts");
    [uptimeStat, cpuStat, memStat, restartsStat].forEach((s) => stats.appendChild(s.wrap));

    // Actions: round icon buttons, primary Start/Stop in black
    const actions = el("div", "card-actions");
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
    const miBrowser = mi("Open in browser");
    const miPhone = mi("Open on phone…");
    const miConnUrl = mi("Copy connection URL");
    const miConnEnv = mi("Copy .env settings");
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

    // Bottom: summary (description, live stats) + action buttons
    const summary = el("div", "card-summary");
    summary.appendChild(stats);
    summary.appendChild(desc);
    const bottom = el("div", "card-bottom");
    bottom.appendChild(summary);
    bottom.appendChild(actions);

    card.appendChild(head);
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
    v.miBrowser.disabled = port === null;

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
    v.miConnUrl.hidden = v.miConnEnv.hidden = !app.service;
    v.miPhone.disabled = !isActive(app);

    const share = app.share;
    v.shareBar.hidden = !share;
    if (share) {
      v.shareBar.className = "share-bar " + share.status;
      const bits = [];
      if (share.protected) bits.push("🔒");
      if (share.expires_at) bits.push(timeLeft(share.expires_at) + " left");
      v.shareMeta.textContent = bits.join(" · ");
      v.shareMeta.hidden = !bits.length;
      if (share.status === "live" && share.url) {
        v.shareText.textContent = "Public";
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

  async function runAction(id, action, killConflict) {
    try {
      const query = killConflict ? "?kill_conflict=1" : "";
      const updated = await request("/api/apps/" + encodeURIComponent(id) + "/" + action + query, { method: "POST" });
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
      const started = await runAction(id, "start");
      if (!started) return;
      window.setTimeout(() => window.open(namedUrl(cur), "_blank", "noopener"), 1200);
    } else {
      window.open(namedUrl(cur), "_blank", "noopener");
    }
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
  }

  function updateAllApps(apps) {
    state.apps = Array.isArray(apps) ? apps : [];
    render();
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
        body: JSON.stringify({ password: password || null, expires_minutes: Number(els.shareExpiry.value) || null }),
      });
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
    $("diag-ai").hidden = !data.ai_available;
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

  async function triggerDetect(path) {
    const p = (path || "").trim();
    if (!p) return;
    const seq = ++state.detectSeq;
    els.fPathHint.textContent = "Detecting command and port…";
    try {
      let url = "/api/detect?path=" + encodeURIComponent(p);
      if (els.fId.value) url += "&exclude_id=" + encodeURIComponent(els.fId.value);
      const data = await request(url);
      if (seq !== state.detectSeq) return;
      if (data.command && !els.fCommand.value.trim()) els.fCommand.value = data.command;
      if (typeof data.port === "number" && !els.fPort.value.trim()) els.fPort.value = String(data.port);
      if (!els.fName.value.trim()) {
        const base = p.replace(/\/+$/, "").split("/").pop() || "";
        els.fName.value = base.replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      }
      els.fPathHint.textContent = data.command
        ? "Detected " + (data.type ? data.type + " project" : "command") + ": " + data.command
        : "Couldn't recognise this project type — enter the command you use to start it.";
    } catch (err) {
      if (seq === state.detectSeq) els.fPathHint.textContent = "Detection failed: " + err.message;
    }
  }

  els.fPath.addEventListener("blur", () => triggerDetect(els.fPath.value));

  els.btnBrowse.addEventListener("click", async () => {
    try {
      const res = await request("/api/pick-folder", { method: "POST" });
      if (res && res.path) {
        els.fPath.value = res.path;
        triggerDetect(res.path);
        return;
      }
      if (res && res.path === null) return; // user cancelled the native picker
    } catch (err) {
      /* native picker unavailable — fall back to the in-page browser */
    }
    openFolderBrowser(els.fPath.value || "");
  });

  els.form.addEventListener("submit", async (e) => {
    e.preventDefault();
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

  function openFolderBrowser(initialPath) {
    els.browseBackdrop.hidden = false;
    loadFolder(initialPath || "");
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
      const data = await request("/api/browse" + (target ? "?path=" + encodeURIComponent(target) : ""));
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
        els.browseList.appendChild(el("div", "browse-empty", "No subfolders"));
      }
      for (const entry of data.entries) {
        els.browseList.appendChild(browseItem(entry.name, () => loadFolder(entry.path), entry.looks_like_app));
      }
    } catch (err) {
      els.browseList.textContent = "Couldn't open folder: " + err.message;
    }
  }

  els.browseSelect.addEventListener("click", () => {
    if (!state.currentBrowsePath) return;
    els.fPath.value = state.currentBrowsePath;
    triggerDetect(state.currentBrowsePath);
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

  els.btnTheme.addEventListener("click", () => {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    savePref("theme", next);
    renderThemeButton();
  });
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
    act("Databases & services…", "layers", () => openServices(), "postgres mysql mariadb redis mongodb mailpit database");
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
  /* AI assistant (runs the local `claude` CLI only when you send)      */
  /* ------------------------------------------------------------------ */

  const ai = {
    panel: $("ai-panel"),
    log: $("ai-log"),
    form: $("ai-form"),
    input: $("ai-input"),
    send: $("ai-send"),
    model: $("ai-model"),
    modelCustom: $("ai-model-custom"),
    modeSeg: $("ai-mode"),
    meta: $("ai-meta"),
    reload: $("ai-reload"),
    sessionId: null,
    mode: "act",
    running: false,
    abort: null,
    tools: {},
  };

  const AI_SUGGESTIONS = [
    "Why are some apps unhealthy or crashed? Diagnose and fix them.",
    "Find apps that share the same port and give each a unique one.",
    "Add the app in this folder: ",
    "Make the cards more compact.",
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
    const empty = ai.log.querySelector(".ai-empty");
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
    AI_SUGGESTIONS.forEach((text) => {
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

  function aiHandle(evt) {
    if (evt.type === "session") {
      ai.sessionId = evt.session_id || ai.sessionId;
      if (evt.model) ai.meta.textContent = evt.model;
    } else if (evt.type === "text") {
      aiAppend(aiRichText(el("div", "ai-msg"), evt.text));
    } else if (evt.type === "tool") {
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
    } else if (evt.type === "done") {
      ai.sessionId = evt.session_id || ai.sessionId;
      if (ai.panel.hidden) document.getElementById("ai-fab").classList.add("unread");
      const bits = [];
      if (typeof evt.duration_ms === "number") bits.push((evt.duration_ms / 1000).toFixed(1) + "s");
      if (evt.turns) bits.push(evt.turns + " turns");
      if (typeof evt.cost_usd === "number") bits.push("≈$" + evt.cost_usd.toFixed(3) + " of plan usage");
      ai.meta.textContent = bits.join(" · ");
    } else if (evt.type === "error") {
      aiAppend(el("div", "ai-msg error", evt.message || "Something went wrong"));
    }
  }

  async function aiSend(prompt) {
    aiAppend(el("div", "ai-msg user", prompt));
    aiSetRunning(true);
    ai.tools = {};
    ai.abort = new AbortController();
    try {
      const res = await fetch(apiUrl("/api/ai/ask"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ prompt, model: aiModel(), session_id: ai.sessionId, mode: ai.mode }),
        signal: ai.abort.signal,
      });
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
          try {
            aiHandle(JSON.parse(line.slice(6)));
          } catch (err) {
            /* ignore malformed event */
          }
        }
      }
    } catch (err) {
      aiAppend(el("div", "ai-msg error", err.name === "AbortError" ? "stopped" : err.message));
    } finally {
      ai.abort = null;
      aiSetRunning(false);
    }
  }

  async function aiStop() {
    try {
      // The server kills the run and the stream ends with a "stopped" event.
      await request("/api/ai/stop", { method: "POST" });
    } catch (err) {
      if (ai.abort) ai.abort.abort();
    }
  }

  async function openAi() {
    if (!els.drawer.hidden) closeLogs();
    ai.panel.hidden = false;
    aiFab.classList.add("open");
    aiFab.classList.remove("unread");
    aiFab.setAttribute("aria-expanded", "true");
    ai.input.focus();
    try {
      const st = await request("/api/ai/status");
      if (!st.available) {
        ai.meta.textContent = "claude CLI not found — install Claude Code and log in";
        ai.send.disabled = true;
      } else {
        ai.send.disabled = false;
        if (!ai.meta.textContent && st.version) ai.meta.textContent = st.version;
      }
    } catch (err) {
      ai.meta.textContent = err.message;
    }
  }

  function closeAi() {
    ai.panel.hidden = true;
    aiFab.classList.remove("open");
    aiFab.setAttribute("aria-expanded", "false");
  }

  ai.model.value = aiPref("model", "sonnet");
  if (ai.model.selectedIndex < 0) ai.model.value = "sonnet";
  ai.modelCustom.value = aiPref("model_custom", "");
  ai.modelCustom.hidden = ai.model.value !== "__custom";
  aiSetMode(aiPref("mode", "act"));
  aiRenderEmpty();

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
    ai.meta.textContent = "";
    ai.reload.hidden = true;
    aiRenderEmpty();
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
    if (!prompt) return;
    if (ai.model.value === "__custom" && !aiModel()) {
      toast("Enter a model id or pick a model", "warn");
      ai.modelCustom.focus();
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

  // The AI assistant is optional (needs Claude Code); hide the bubble without it.
  aiFab.hidden = true;
  request("/api/ai/status")
    .then((st) => {
      aiFab.hidden = !(st && st.available);
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

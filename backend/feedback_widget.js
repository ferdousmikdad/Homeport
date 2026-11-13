/* Homeport comments: feedback pinned on the page, the way Figma comments work.
 *
 * Added by Homeport's proxy to the pages of a shared app (when the owner turned
 * feedback on) and to the owner's review view on this computer.
 *   data-mode="visitor": everyone with the link sees the open comments and can
 *                        comment and reply.
 *   data-mode="review":  the owner (this computer only) can also resolve / reopen
 *                        and see resolved comments.
 *
 * Like Figma: a floating toolbar; press C (or the comment tool) and click anywhere
 * to drop a pin; pins are avatar bubbles that preview on hover; a click opens the
 * thread with replies; a Comments panel lists everything on the page.
 *
 * A comment is anchored to the element that was clicked (CSS path + offset inside
 * it), with page coordinates as a fallback. Pins, the open thread and the comment
 * being written are placed again every frame from that anchor, so they move with
 * the page when it scrolls (also inside scrollable areas) or its layout changes.
 *
 * Everything lives in a shadow root (the site's CSS and ours never mix) and all
 * text is set with textContent, never as HTML.
 */
(function () {
  "use strict";
  if (window.__homeportFeedback) return;
  window.__homeportFeedback = true;

  var script = document.currentScript;
  var MANAGE = (script && script.getAttribute("data-mode")) === "review";
  var BASE = "/__homeport/fb";
  var NAME_KEY = "homeport_fb_name";
  var HIDE_KEY = "homeport_fb_hidden";
  var BLUE = "#0D99FF";
  var COLORS = ["#0D99FF", "#9747FF", "#F24822", "#FF9E0F", "#14AE5C", "#FF24BD", "#6E56CF", "#0FA9A1"];

  // icons (16px, stroke)
  var I = {
    comment: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M12 3.5a8.5 8.5 0 0 1 0 17H3.5V12A8.5 8.5 0 0 1 12 3.5z"/><path d="M12 8.5v7M8.5 12h7" stroke-linecap="round"/></svg>',
    list: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M10 4h10v9h-3v3l-3-3h-4z"/><path d="M7 8H4v9h3v3l3-3h4" /></svg>',
    eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/></svg>',
    eyeOff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 4l16 16"/><path d="M9.9 5.8A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3.1 3.8M6.3 7.4C3.9 9.2 2.5 12 2.5 12S6 18.5 12 18.5c1.6 0 3-.4 4.2-1"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M8.5 12.2l2.4 2.4 4.8-5"/></svg>',
    checkFill: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9.5" fill="#14AE5C"/><path d="M8.5 12.2l2.4 2.4 4.8-5" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 18V6M6.5 11.5L12 6l5.5 5.5"/></svg>',
    exit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h5v16h-5"/><path d="M10 8l-4 4 4 4M6 12h10"/></svg>',
  };
  var CURSOR = "url(\"data:image/svg+xml;utf8," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">' +
    '<path d="M16 3a12 12 0 0 1 0 24H4V15A12 12 0 0 1 16 3z" fill="#fff" stroke="#000" stroke-opacity=".25"/>' +
    '<path d="M16 10v10M11 15h10" stroke="#111" stroke-width="2" stroke-linecap="round"/></svg>') + "\") 4 27, crosshair";

  var host = document.createElement("homeport-feedback");
  host.style.cssText = "all:initial;position:fixed;inset:0;pointer-events:none;z-index:2147483646;";
  var root = host.attachShadow({ mode: "open" });
  root.innerHTML =
    "<style>" +
    ":host{all:initial;--f:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}" +
    "*{box-sizing:border-box;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}" +
    "svg{width:18px;height:18px;display:block}" +
    "button{all:unset;cursor:pointer;box-sizing:border-box}" +
    /* toolbar */
    ".tools{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);display:flex;align-items:center;gap:2px;padding:4px;border-radius:13px;background:#2C2C2C;box-shadow:0 2px 6px rgba(0,0,0,.2),0 12px 32px -6px rgba(0,0,0,.35);pointer-events:auto}" +
    ".tool{position:relative;display:grid;place-items:center;height:36px;min-width:36px;padding:0 9px;border-radius:9px;color:#fff;font:500 12px/1 var(--f);gap:6px}" +
    ".tool:hover{background:rgba(255,255,255,.1)}" +
    ".tool.on{background:" + BLUE + "}" +
    ".tool .n{position:absolute;top:3px;right:3px;min-width:15px;height:15px;padding:0 4px;border-radius:8px;background:" + BLUE + ";color:#fff;font:700 9.5px/15px var(--f);text-align:center}" +
    ".tool.on .n{background:#fff;color:" + BLUE + "}" +
    ".tool[hidden]{display:none}" +
    ".sep{width:1px;height:20px;background:rgba(255,255,255,.14);margin:0 3px}" +
    ".tip{position:absolute;bottom:calc(100% + 10px);left:50%;transform:translateX(-50%);white-space:nowrap;padding:5px 8px;border-radius:6px;background:#1E1E1E;color:#fff;font:500 11px/1 var(--f);opacity:0;pointer-events:none;transition:opacity .12s}" +
    ".tip kbd{font:inherit;color:#B3B3B3;margin-left:6px}" +
    ".tool:hover .tip{opacity:1;transition-delay:.35s}" +
    /* comment mode */
    ".catch{position:fixed;inset:0;pointer-events:auto;cursor:" + CURSOR + "}" +
    ".mode{position:fixed;left:50%;top:14px;transform:translateX(-50%);padding:7px 12px;border-radius:8px;background:#2C2C2C;color:#fff;font:500 12px/1 var(--f);box-shadow:0 6px 18px rgba(0,0,0,.25);pointer-events:none}" +
    ".mode b{color:#B3B3B3;font-weight:500;margin-left:8px}" +
    /* pins: avatar bubbles, pointed corner at the spot */
    ".pin{position:fixed;left:0;top:0;display:flex;align-items:flex-start;gap:8px;min-width:36px;max-width:36px;height:36px;padding:4px;border-radius:18px 18px 18px 2px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.18),0 4px 14px rgba(0,0,0,.16),0 0 0 .5px rgba(0,0,0,.12);pointer-events:auto;cursor:pointer;overflow:hidden;will-change:transform;transition:max-width .16s ease,height .16s ease,border-radius .16s ease}" +
    ".pin:hover,.pin.peek{max-width:260px;height:auto;min-height:36px;border-radius:14px 14px 14px 2px;padding:6px 10px 8px 6px;z-index:2}" +
    ".pin.active{box-shadow:0 0 0 2px " + BLUE + ",0 4px 14px rgba(0,0,0,.18)}" +
    ".pin.active:hover{max-width:36px;height:36px;padding:4px;border-radius:18px 18px 18px 2px}" +
    ".pin.active:hover .pv{display:none}" +
    ".pin.resolved{opacity:.55}" +
    ".pin[hidden]{display:none}" +
    ".av{flex:none;width:28px;height:28px;border-radius:50%;display:grid;place-items:center;color:#fff;font:600 12px/1 var(--f);text-transform:uppercase}" +
    ".av.sm{width:24px;height:24px;font-size:11px}" +
    ".pv{display:none;min-width:0;width:200px;padding-top:2px}" +
    ".pin:hover .pv,.pin.peek .pv{display:block}" +
    ".pv .h{display:flex;gap:6px;align-items:baseline;font:600 12px/1.3 var(--f);color:#000}" +
    ".pv .h span{font-weight:400;color:#8C8C8C;font-size:11px}" +
    ".pv .t{margin-top:2px;font:400 12px/1.4 var(--f);color:#1E1E1E;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}" +
    ".pv .r{margin-top:4px;font:500 11px/1 var(--f);color:" + BLUE + "}" +
    ".pin.draft{background:#fff}" +
    /* thread card / composer */
    ".card{position:fixed;left:0;top:0;width:320px;max-width:calc(100vw - 24px);pointer-events:auto;background:#fff;color:#1E1E1E;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,.12),0 16px 40px -8px rgba(0,0,0,.28),0 0 0 .5px rgba(0,0,0,.14);will-change:transform;font:12px/1.45 var(--f);overflow:hidden}" +
    ".card.docked{left:auto;top:auto;right:16px;bottom:72px;transform:none!important}" +
    ".head{display:flex;align-items:center;gap:2px;padding:8px 8px 8px 14px;border-bottom:1px solid #E6E6E6}" +
    ".head .title{flex:1;font:600 12px/1 var(--f);color:#000}" +
    ".icon{display:grid;place-items:center;width:28px;height:28px;border-radius:6px;color:#444}" +
    ".icon:hover{background:#F0F0F0;color:#000}" +
    ".icon svg{width:16px;height:16px}" +
    ".msgs{max-height:min(46vh,380px);overflow-y:auto;overscroll-behavior:contain}" +
    ".msg{display:flex;gap:8px;padding:12px 14px 4px}" +
    ".msg+.msg{padding-top:8px}" +
    ".msg .body{min-width:0;flex:1}" +
    ".msg .h{display:flex;gap:6px;align-items:baseline;font:600 12px/1.3 var(--f);color:#000}" +
    ".msg .h span{font-weight:400;color:#8C8C8C;font-size:11px}" +
    ".msg .t{margin-top:2px;white-space:pre-wrap;word-break:break-word;font:400 12.5px/1.45 var(--f);color:#1E1E1E}" +
    ".note{padding:6px 14px 0 46px;color:#8C8C8C;font-size:11px}" +
    ".compose{display:flex;align-items:flex-end;gap:8px;padding:10px 10px 10px 14px}" +
    ".msgs+.compose{border-top:1px solid #E6E6E6;margin-top:10px}" +
    ".field{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px}" +
    ".field textarea,.field input{display:block;width:100%;border:0;outline:none;resize:none;background:transparent;color:#1E1E1E;font:400 12.5px/1.45 var(--f);padding:5px 0}" +
    ".field textarea{max-height:140px;min-height:22px}" +
    ".field input{border-bottom:1px solid #E6E6E6;font-size:12px}" +
    ".field textarea::placeholder,.field input::placeholder{color:#B3B3B3}" +
    ".send{flex:none;display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#E6E6E6;color:#fff;transition:background .12s}" +
    ".send svg{width:15px;height:15px}" +
    ".send.ready{background:" + BLUE + "}" +
    ".send:disabled{cursor:default}" +
    ".err{padding:0 14px 10px;color:#F24822;font-size:11.5px}" +
    ".err:empty{display:none}" +
    /* comments panel */
    ".panel{position:fixed;top:12px;right:12px;bottom:72px;width:320px;max-width:calc(100vw - 24px);display:flex;flex-direction:column;pointer-events:auto;background:#fff;color:#1E1E1E;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,.12),0 16px 40px -8px rgba(0,0,0,.28),0 0 0 .5px rgba(0,0,0,.14);overflow:hidden}" +
    ".panel .list{flex:1;overflow-y:auto;overscroll-behavior:contain}" +
    ".entry{display:flex;gap:10px;width:100%;padding:12px 14px;border-bottom:1px solid #F0F0F0;text-align:left}" +
    ".entry:hover{background:#F5F5F5}" +
    ".entry.sel{background:#E5F4FF}" +
    ".entry .body{min-width:0;flex:1}" +
    ".entry .h{display:flex;gap:6px;align-items:baseline;font:600 12px/1.3 var(--f);color:#000}" +
    ".entry .h span{font-weight:400;color:#8C8C8C;font-size:11px}" +
    ".entry .t{margin-top:2px;font:400 12px/1.4 var(--f);color:#1E1E1E;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;word-break:break-word}" +
    ".entry .r{margin-top:4px;font:500 11px/1 var(--f);color:#8C8C8C}" +
    ".entry .r b{color:" + BLUE + ";font-weight:500}" +
    ".empty{padding:28px 20px;text-align:center;color:#8C8C8C;font-size:12px;line-height:1.5}" +
    ".toast{position:fixed;left:50%;bottom:72px;transform:translateX(-50%);padding:8px 12px;border-radius:8px;background:#2C2C2C;color:#fff;font:500 12px/1.2 var(--f);pointer-events:none;box-shadow:0 6px 18px rgba(0,0,0,.25)}" +
    "</style>";
  var layer = document.createElement("div");
  root.appendChild(layer);
  var pinLayer = document.createElement("div");
  layer.appendChild(pinLayer);

  function mk(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function iconBtn(cls, icon, label) {
    var b = mk("button", cls);
    b.innerHTML = I[icon]; // our own static SVG markup, never page or user data
    b.setAttribute("aria-label", label);
    b.title = label;
    return b;
  }

  function toast(text) {
    var t = mk("div", "toast", text);
    layer.appendChild(t);
    setTimeout(function () { t.remove(); }, 2600);
  }

  function ago(ts) {
    var s = Math.max(0, Date.now() / 1000 - (ts || 0));
    if (s < 60) return "Just now";
    if (s < 3600) return Math.floor(s / 60) + "m ago";
    if (s < 86400) return Math.floor(s / 3600) + "h ago";
    if (s < 86400 * 7) return Math.floor(s / 86400) + "d ago";
    return new Date(ts * 1000).toLocaleDateString();
  }

  function store(key, value) {
    try {
      if (value === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, value);
    } catch (e) { /* private mode */ }
    return null;
  }

  function myName() { return (store(NAME_KEY) || "").trim(); }

  function colorFor(name) {
    if (!name) return "#8C8C8C";
    var h = 0;
    for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
    return COLORS[h % COLORS.length];
  }

  function avatar(name, small) {
    var a = mk("span", "av" + (small ? " sm" : ""), initials(name));
    a.style.background = colorFor(name);
    return a;
  }

  function initials(name) {
    if (!name) return "?";
    var parts = name.trim().split(/\s+/);
    return (parts[0].charAt(0) + (parts.length > 1 ? parts[parts.length - 1].charAt(0) : "")).toUpperCase();
  }

  function autoGrow(t) {
    t.style.height = "auto";
    t.style.height = Math.min(140, t.scrollHeight) + "px";
  }

  /* ---------------- anchoring ---------------- */

  // A CSS path to an element, so a comment stays on it when the layout changes.
  function cssPath(el) {
    var parts = [];
    while (el && el.nodeType === 1 && el !== document.body && el !== document.documentElement && parts.length < 14) {
      if (el.id && /^[A-Za-z][\w-]*$/.test(el.id) && document.querySelectorAll("#" + el.id).length === 1) {
        parts.unshift("#" + el.id);
        return parts.join(" > ");
      }
      var sel = el.tagName.toLowerCase();
      var parent = el.parentElement;
      if (parent) {
        var same = [];
        for (var i = 0; i < parent.children.length; i++) if (parent.children[i].tagName === el.tagName) same.push(parent.children[i]);
        if (same.length > 1) sel += ":nth-of-type(" + (same.indexOf(el) + 1) + ")";
      }
      parts.unshift(sel);
      el = parent;
    }
    parts.unshift("body");
    return parts.join(" > ");
  }

  function docWidth() {
    var d = document.documentElement;
    return Math.max(d.scrollWidth, d.clientWidth, 1);
  }

  function element(a) {
    if (!a.selector || a.ox == null || a.oy == null) return null;
    if (a._el && a._el.isConnected) return a._el;
    try { a._el = document.querySelector(a.selector); } catch (e) { a._el = null; }
    return a._el;
  }

  // Where an anchor is on screen now, or null (general comment / not found).
  function where(a) {
    var el = element(a);
    if (el) {
      var r = el.getBoundingClientRect();
      if (r.width || r.height) return { x: r.left + a.ox * r.width, y: r.top + a.oy * r.height };
    }
    if (a.xp == null || a.y == null) return null;
    return { x: a.xp * docWidth() - window.scrollX, y: a.y - window.scrollY };
  }

  function onScreen(p) {
    return p && p.x > -60 && p.y > -60 && p.x < window.innerWidth + 60 && p.y < window.innerHeight + 60;
  }

  /* ---------------- state ---------------- */

  var items = [];
  var pins = {};
  var showPins = store(HIDE_KEY) !== "1";
  var showResolved = false;
  var openId = (location.hash.match(/homeport-fb=([a-f0-9]+)/) || [])[1] || null;
  var card = null;      // { el, anchor, item, docked, kind: "thread"|"new" }
  var draft = null;     // { anchor, pin }
  var panel = null;
  var commenting = null;
  var mine = {};
  var lastPath = location.pathname;

  function visible() {
    return items.filter(function (i) { return MANAGE ? (showResolved || i.status === "open") : i.status === "open"; });
  }

  function itemById(id) {
    for (var i = 0; i < items.length; i++) if (items[i].id === id) return items[i];
    return null;
  }

  /* ---------------- pins ---------------- */

  function buildPin(item) {
    var pin = mk("div", "pin");
    pin.appendChild(avatar(item.name));
    var pv = mk("div", "pv");
    var h = mk("div", "h", item.name || "Anonymous");
    h.appendChild(mk("span", null, ago(item.created_at)));
    pv.appendChild(h);
    pv.appendChild(mk("div", "t", item.message));
    var n = (item.replies || []).length;
    if (n) pv.appendChild(mk("div", "r", n + (n === 1 ? " reply" : " replies")));
    pin.appendChild(pv);
    pin.addEventListener("click", function (e) {
      e.stopPropagation();
      var cur = itemById(pin.dataset.id);
      if (!cur) return;
      if (card && card.item && card.item.id === cur.id) closeCard();
      else openThread(cur);
    });
    return pin;
  }

  function syncPins() {
    var want = {};
    (showPins ? visible() : []).forEach(function (item) {
      want[item.id] = true;
      var key = item.id + ":" + (item.replies || []).length + ":" + item.status + ":" + (item.name || "");
      var pin = pins[item.id];
      if (!pin || pin.dataset.key !== key) {
        var fresh = buildPin(item);
        if (pin) pin.replaceWith(fresh); else pinLayer.appendChild(fresh);
        pin = pins[item.id] = fresh;
        pin.dataset.key = key;
        pin.dataset.id = item.id;
      }
      pin.classList.toggle("resolved", item.status === "resolved");
      pin.classList.toggle("active", !!(card && card.item && card.item.id === item.id));
    });
    Object.keys(pins).forEach(function (id) { if (!want[id]) { pins[id].remove(); delete pins[id]; } });
    updateTools();
    if (panel) renderPanel();
  }

  function placeAt(node, p, h) {
    if (!onScreen(p)) { node.hidden = true; return; }
    node.hidden = false;
    node.style.transform = "translate(" + Math.round(p.x) + "px," + Math.round(p.y - (h || 36)) + "px)";
  }

  function frame() {
    if (location.pathname !== lastPath) { // single-page apps change pages without reloading
      lastPath = location.pathname;
      closeCard();
      items = [];
      syncPins();
      load();
    }
    Object.keys(pins).forEach(function (id) {
      var item = itemById(id);
      if (item) placeAt(pins[id], where(item), pins[id].offsetHeight || 36);
    });
    if (draft) placeAt(draft.pin, where(draft.anchor), 36);
    if (card && !card.docked && card.anchor) {
      var p = where(card.anchor);
      if (p) {
        var w = card.el.offsetWidth || 320;
        var x = p.x + 46;
        if (x + w > window.innerWidth - 12) x = Math.max(12, p.x - w - 12); // flip to the left of the pin
        card.el.style.transform = "translate(" + Math.round(x) + "px," + Math.round(p.y - 36) + "px)";
      }
    }
    requestAnimationFrame(frame);
  }

  /* ---------------- cards (thread, new comment) ---------------- */

  function closeCard() {
    if (draft) { draft.pin.remove(); draft = null; }
    if (card) { card.el.remove(); card = null; }
    openId = null;
    syncPins();
  }

  function showCard(el, anchor, item, kind) {
    if (card) { card.el.remove(); card = null; }
    if (kind !== "new" && draft) { draft.pin.remove(); draft = null; }
    layer.appendChild(el);
    card = { el: el, anchor: anchor, item: item || null, kind: kind, docked: !anchor || !where(anchor) };
    if (card.docked) el.classList.add("docked");
    el.addEventListener("keydown", function (e) { // typing must not trigger the site's shortcuts
      e.stopPropagation();
      if (e.key === "Escape") closeCard();
    });
    el.addEventListener("mousedown", function (e) { e.stopPropagation(); });
    syncPins();
  }

  // A text box with a round send button, like Figma's "Add a comment" / "Reply".
  function composer(placeholder, onSend, askName) {
    var wrap = mk("div", "compose");
    var name = myName();
    wrap.appendChild(avatar(name || "", true));
    var field = mk("div", "field");
    var nameInput = null;
    if (askName && !name) {
      nameInput = mk("input");
      nameInput.placeholder = "Your name";
      nameInput.maxLength = 60;
      field.appendChild(nameInput);
      nameInput.addEventListener("input", function () {
        var v = nameInput.value.trim();
        [wrap.querySelector(".av"), draft && draft.pin.querySelector(".av")].forEach(function (a) {
          if (!a) return;
          a.textContent = initials(v);
          a.style.background = colorFor(v);
        });
      });
    }
    var text = mk("textarea");
    text.rows = 1;
    text.placeholder = placeholder;
    text.maxLength = 2000;
    field.appendChild(text);
    wrap.appendChild(field);
    var send = iconBtn("send", "send", "Post");
    send.disabled = true;
    wrap.appendChild(send);
    var err = mk("div", "err");
    var refresh = function () {
      var ok = text.value.trim().length > 0;
      send.disabled = !ok;
      send.classList.toggle("ready", ok);
      autoGrow(text);
    };
    text.addEventListener("input", refresh);
    text.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!send.disabled) send.click(); }
    });
    send.addEventListener("click", function () {
      var message = text.value.trim();
      if (!message) return;
      if (nameInput) store(NAME_KEY, nameInput.value.trim());
      send.disabled = true;
      err.textContent = "";
      onSend(message, myName()).then(function () {
        text.value = "";
        refresh();
      }).catch(function (e) {
        err.textContent = e.message;
        refresh();
      });
    });
    return { el: wrap, err: err, focus: function () { (nameInput && !nameInput.value ? nameInput : text).focus({ preventScroll: true }); } };
  }

  function post(url, data) {
    return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data), credentials: "same-origin" })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (body) {
          if (!r.ok) throw new Error(body.detail || "Couldn't post (" + r.status + ")");
          return body;
        });
      });
  }

  function messageRow(name, ts, text, you) {
    var row = mk("div", "msg");
    row.appendChild(avatar(name, true));
    var body = mk("div", "body");
    var h = mk("div", "h", (name || "Anonymous") + (you ? " (you)" : ""));
    h.appendChild(mk("span", null, ago(ts)));
    body.appendChild(h);
    body.appendChild(mk("div", "t", text));
    row.appendChild(body);
    return row;
  }

  function openThread(item) {
    openId = item.id;
    var el = mk("div", "card");
    var head = mk("div", "head");
    head.appendChild(mk("div", "title", item.status === "resolved" ? "Resolved comment" : "Comment"));
    if (MANAGE) {
      var resolve = iconBtn("icon", item.status === "resolved" ? "checkFill" : "check",
        item.status === "resolved" ? "Reopen" : "Resolve");
      resolve.addEventListener("click", function () {
        post(BASE + "/" + item.id, { status: item.status === "open" ? "resolved" : "open" })
          .then(function (upd) {
            item.status = upd.status;
            toast(upd.status === "resolved" ? "Comment resolved" : "Comment reopened");
            closeCard();
          })
          .catch(function () { toast("Couldn't update — is Homeport running?"); });
      });
      head.appendChild(resolve);
    }
    var close = iconBtn("icon", "close", "Close");
    close.addEventListener("click", closeCard);
    head.appendChild(close);
    el.appendChild(head);

    var msgs = mk("div", "msgs");
    msgs.appendChild(messageRow(item.name, item.created_at, item.message, mine[item.id]));
    (item.replies || []).forEach(function (r) { msgs.appendChild(messageRow(r.name, r.created_at, r.message, mine[r.id])); });
    el.appendChild(msgs);
    var spot = where(item);
    if (!spot) el.appendChild(mk("div", "note", "General comment — not pinned to a spot"));
    if (MANAGE && item.vw) el.appendChild(mk("div", "note", "Left on a " + Math.round(item.vw) + "×" + Math.round(item.vh || 0) + " screen"));

    if (item.status === "open" || MANAGE) {
      var c = composer("Reply", function (message, name) {
        return post(BASE + "/" + item.id + "/reply", { message: message, name: name }).then(function (reply) {
          mine[reply.id] = true;
          item.replies = (item.replies || []).concat([reply]);
          msgs.appendChild(messageRow(reply.name, reply.created_at, reply.message, true));
          msgs.scrollTop = msgs.scrollHeight;
          syncPins();
        });
      }, true);
      el.appendChild(c.el);
      el.appendChild(c.err);
    }
    showCard(el, spot ? item : null, item, "thread");
    msgs.scrollTop = msgs.scrollHeight;
  }

  function openNew(anchor) {
    if (draft) { draft.pin.remove(); draft = null; }
    if (anchor) {
      var pin = mk("div", "pin draft");
      pin.appendChild(avatar(myName()));
      draft = { anchor: anchor, pin: pin };
      pinLayer.appendChild(pin);
    }
    var el = mk("div", "card");
    if (!anchor) {
      var head = mk("div", "head");
      head.appendChild(mk("div", "title", "General comment"));
      var close = iconBtn("icon", "close", "Cancel");
      close.addEventListener("click", closeCard);
      head.appendChild(close);
      el.appendChild(head);
    }
    var c = composer("Add a comment", function (message, name) {
      var data = {
        message: message, name: name,
        page: location.pathname + location.search, url: location.href, title: document.title,
        vw: window.innerWidth, vh: window.innerHeight, ua: navigator.userAgent,
      };
      if (anchor) {
        data.xp = anchor.xp;
        data.y = anchor.y;
        if (anchor.selector) { data.selector = anchor.selector; data.ox = anchor.ox; data.oy = anchor.oy; }
      }
      return post(BASE, data).then(function (body) {
        var item = {
          id: body.id, created_at: Date.now() / 1000, status: "open", message: message, name: name, replies: [],
          selector: data.selector || "", ox: data.ox, oy: data.oy,
          xp: anchor ? data.xp : null, y: anchor ? data.y : null, _el: anchor ? anchor._el : null,
        };
        mine[item.id] = true;
        items.push(item);
        if (draft) { draft.pin.remove(); draft = null; }
        if (card) { card.el.remove(); card = null; }
        syncPins();
        toast("Comment posted");
        load();
      });
    }, true);
    el.appendChild(c.el);
    el.appendChild(c.err);
    showCard(el, anchor, null, "new");
    setTimeout(c.focus, 0);
  }

  /* ---------------- comment mode (C) ---------------- */

  function setCommenting(on) {
    if (on === !!commenting) return;
    if (!on) {
      commenting.catcher.remove();
      commenting.hint.remove();
      commenting = null;
      updateTools();
      return;
    }
    if (!showPins) toggleHidden();
    var catcher = mk("div", "catch");
    var hint = mk("div", "mode", "Click anywhere to comment");
    hint.appendChild(mk("b", null, "Esc to exit"));
    layer.insertBefore(catcher, pinLayer); // pins stay clickable above it
    layer.appendChild(hint);
    commenting = { catcher: catcher, hint: hint };
    // the page keeps scrolling with the wheel / trackpad
    catcher.addEventListener("wheel", function () {
      catcher.style.pointerEvents = "none";
      clearTimeout(catcher._t);
      catcher._t = setTimeout(function () { catcher.style.pointerEvents = "auto"; }, 150);
    }, { passive: true });
    catcher.addEventListener("mousedown", function (e) { e.preventDefault(); });
    catcher.addEventListener("click", function (e) {
      if (card && card.kind === "new") { closeCard(); return; } // click away = cancel the draft
      var x = e.clientX, y = e.clientY;
      host.style.display = "none"; // the page element under the click
      var target = document.elementFromPoint(x, y);
      host.style.display = "";
      var anchor = { xp: (x + window.scrollX) / docWidth(), y: y + window.scrollY };
      if (target && target !== document.documentElement && target !== document.body) {
        var r = target.getBoundingClientRect();
        anchor.selector = cssPath(target);
        anchor.ox = r.width ? (x - r.left) / r.width : 0;
        anchor.oy = r.height ? (y - r.top) / r.height : 0;
        anchor._el = target;
      }
      openNew(anchor);
    });
    updateTools();
  }

  function typingInPage(e) {
    var t = e.composedPath ? e.composedPath()[0] : e.target;
    return t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName || ""));
  }

  document.addEventListener("keydown", function (e) {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || typingInPage(e)) return;
    if ((e.key === "c" || e.key === "C") && !e.shiftKey) {
      setCommenting(!commenting);
    } else if (e.key === "Escape") {
      if (card) closeCard();
      else if (commenting) setCommenting(false);
      else if (panel) togglePanel(false);
    }
  }, true);

  /* ---------------- toolbar ---------------- */

  var tools = mk("div", "tools");
  function tool(icon, label, key) {
    var b = mk("button", "tool");
    b.innerHTML = I[icon];
    b.setAttribute("aria-label", label);
    var tip = mk("span", "tip", label);
    if (key) tip.appendChild(mk("kbd", null, key));
    b.appendChild(tip);
    return b;
  }
  var commentTool = tool("comment", "Add comment", "C");
  var listTool = tool("list", "Comments");
  var eyeTool = tool("eye", "Hide comments");
  var resolvedTool = tool("check", "Show resolved");
  var exitTool = tool("exit", "Exit review (site without comments)");
  var badge = mk("span", "n", "");
  listTool.appendChild(badge);
  tools.appendChild(commentTool);
  tools.appendChild(mk("span", "sep"));
  tools.appendChild(listTool);
  tools.appendChild(eyeTool);
  if (MANAGE) { tools.appendChild(resolvedTool); tools.appendChild(exitTool); }
  layer.appendChild(tools);

  function setIcon(btn, icon) {
    var tip = btn.querySelector(".tip");
    var n = btn.querySelector(".n");
    btn.innerHTML = I[icon];
    if (tip) btn.appendChild(tip);
    if (n) btn.appendChild(n);
  }

  function updateTools() {
    var open = items.filter(function (i) { return i.status === "open"; }).length;
    commentTool.classList.toggle("on", !!commenting);
    listTool.classList.toggle("on", !!panel);
    badge.textContent = open > 99 ? "99+" : String(open);
    badge.hidden = !open;
    setIcon(eyeTool, showPins ? "eye" : "eyeOff");
    eyeTool.querySelector(".tip").textContent = showPins ? "Hide comments" : "Show comments";
    eyeTool.hidden = !items.length;
    resolvedTool.classList.toggle("on", showResolved);
    resolvedTool.hidden = !items.some(function (i) { return i.status === "resolved"; });
  }

  function toggleHidden() {
    showPins = !showPins;
    store(HIDE_KEY, showPins ? "0" : "1");
    if (!showPins) closeCard();
    syncPins();
  }

  commentTool.addEventListener("click", function () { setCommenting(!commenting); });
  eyeTool.addEventListener("click", toggleHidden);
  listTool.addEventListener("click", function () { togglePanel(!panel); });
  resolvedTool.addEventListener("click", function () { showResolved = !showResolved; syncPins(); });
  exitTool.addEventListener("click", function () {
    location.href = BASE + "/review?on=0&to=" + encodeURIComponent(location.pathname + location.search);
  });

  /* ---------------- comments panel ---------------- */

  function togglePanel(on) {
    if (!on) {
      if (panel) { panel.remove(); panel = null; }
      updateTools();
      return;
    }
    panel = mk("div", "panel");
    layer.appendChild(panel);
    renderPanel();
    updateTools();
  }

  function renderPanel() {
    panel.textContent = "";
    var head = mk("div", "head");
    head.appendChild(mk("div", "title", "Comments"));
    var gen = iconBtn("icon", "comment", "General comment (not on a spot)");
    gen.addEventListener("click", function () { openNew(null); });
    head.appendChild(gen);
    var close = iconBtn("icon", "close", "Close");
    close.addEventListener("click", function () { togglePanel(false); });
    head.appendChild(close);
    panel.appendChild(head);
    var list = mk("div", "list");
    var shown = visible().slice().reverse();
    if (!shown.length) {
      list.appendChild(mk("div", "empty", "No comments on this page yet.\nPress C or the comment tool, then click anywhere on the page."));
    }
    shown.forEach(function (item) {
      var e = mk("button", "entry" + (card && card.item && card.item.id === item.id ? " sel" : ""));
      e.appendChild(avatar(item.name, true));
      var body = mk("div", "body");
      var h = mk("div", "h", (item.name || "Anonymous") + (mine[item.id] ? " (you)" : ""));
      h.appendChild(mk("span", null, ago(item.created_at) + (item.status === "resolved" ? " · Resolved" : "")));
      body.appendChild(h);
      body.appendChild(mk("div", "t", item.message));
      var n = (item.replies || []).length;
      var r = mk("div", "r", where(item) ? "" : "General comment");
      if (n) {
        var b = mk("b", null, n + (n === 1 ? " reply" : " replies"));
        if (r.textContent) r.appendChild(document.createTextNode(" · "));
        r.appendChild(b);
      }
      if (r.textContent) body.appendChild(r);
      e.appendChild(body);
      e.addEventListener("click", function () { reveal(item); });
      list.appendChild(e);
    });
    panel.appendChild(list);
  }

  // Scroll a comment into view and open its thread.
  function reveal(item) {
    if (!showPins) toggleHidden();
    var el = element(item);
    var p = where(item);
    if (p && (p.y < 80 || p.y > window.innerHeight - 160)) {
      if (el && el.scrollIntoView) el.scrollIntoView({ block: "center" });
      else if (item.y != null) window.scrollTo(0, item.y - window.innerHeight / 3);
    }
    openThread(item);
  }

  /* ---------------- loading ---------------- */

  function load() {
    var path = location.pathname;
    return fetch(BASE + "/list?page=" + encodeURIComponent(path), { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (data) {
        if (location.pathname !== path) return;
        var before = {};
        items.forEach(function (i) { before[i.id] = i; });
        items = (data.items || []).map(function (i) {
          if (before[i.id] && before[i.id]._el) i._el = before[i.id]._el;
          return i;
        }).sort(function (a, b) { return (a.created_at || 0) - (b.created_at || 0); });
        if (card && card.item) {
          var fresh = itemById(card.item.id);
          // new replies from someone else: redraw the thread unless a reply is being typed
          var typing = card.el.querySelector("textarea") && card.el.querySelector("textarea").value;
          if (fresh && !typing && (fresh.replies || []).length !== (card.item.replies || []).length) openThread(fresh);
          else if (fresh) { card.item = fresh; if (card.anchor && card.anchor !== draft) card.anchor = fresh; }
        }
        syncPins();
        if (openId && !card) {
          var it = itemById(openId);
          if (it) {
            if (it.status === "resolved") showResolved = true;
            syncPins();
            reveal(it);
          }
        }
      })
      .catch(function () { /* keep what we have */ });
  }

  function start() {
    (document.body || document.documentElement).appendChild(host);
    syncPins();
    load();
    setInterval(function () { if (!document.hidden) load(); }, 15000); // comments from others
    requestAnimationFrame(frame);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();

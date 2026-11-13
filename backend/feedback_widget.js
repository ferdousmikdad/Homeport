/* Homeport feedback widget.
 *
 * Added by Homeport's proxy to the pages of a shared app (when the owner turned
 * feedback on) and to the owner's review view on this computer.
 *   data-mode="visitor": a "Feedback" button; point at a spot and write a note.
 *   data-mode="review":  the owner sees the notes pinned on the page and can resolve them.
 * Everything lives in a shadow root so the site's CSS and ours never mix.
 * All text is set with textContent, never as HTML.
 */
(function () {
  "use strict";
  if (window.__homeportFeedback) return;
  window.__homeportFeedback = true;

  var script = document.currentScript;
  var MODE = (script && script.getAttribute("data-mode")) === "review" ? "review" : "visitor";
  var BASE = "/__homeport/fb";
  var NAME_KEY = "homeport_fb_name";

  var host = document.createElement("homeport-feedback");
  host.style.cssText = "all:initial;position:fixed;inset:0;pointer-events:none;z-index:2147483646;";
  var root = host.attachShadow({ mode: "open" });
  root.innerHTML =
    "<style>" +
    ":host{all:initial}" +
    "*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}" +
    ".bar{position:fixed;right:16px;bottom:16px;display:flex;gap:6px;align-items:center;pointer-events:auto;padding:5px;border-radius:999px;background:#111214;color:#fff;box-shadow:0 10px 30px -8px rgba(0,0,0,.45),0 0 0 1px rgba(255,255,255,.08)}" +
    ".bar button{all:unset;cursor:pointer;padding:8px 14px;border-radius:999px;font:600 13px/1 inherit;color:#fff;white-space:nowrap}" +
    ".bar button:hover{background:rgba(255,255,255,.12)}" +
    ".bar .count{padding:0 6px 0 10px;font:500 12.5px/1 inherit;color:#d4d4d8}" +
    ".bar .primary{background:#fff;color:#111214}.bar .primary:hover{background:#e4e4e7}" +
    ".hint{position:fixed;left:50%;top:14px;transform:translateX(-50%);pointer-events:auto;display:flex;gap:10px;align-items:center;padding:8px 8px 8px 16px;border-radius:999px;background:#111214;color:#fff;font:500 13.5px/1.2 inherit;box-shadow:0 10px 30px -8px rgba(0,0,0,.45)}" +
    ".hint button{all:unset;cursor:pointer;padding:7px 12px;border-radius:999px;background:rgba(255,255,255,.14);font:600 12.5px/1 inherit}" +
    ".catch{position:fixed;inset:0;pointer-events:auto;cursor:crosshair;background:rgba(17,18,20,.06)}" +
    ".pin{position:fixed;width:28px;height:28px;margin:-28px 0 0 -2px;border-radius:50% 50% 50% 4px;background:#111214;color:#fff;border:2px solid #fff;box-shadow:0 4px 12px rgba(0,0,0,.35);display:grid;place-items:center;font:700 12px/1 inherit;pointer-events:auto;cursor:pointer}" +
    ".pin.resolved{background:#a1a1aa}.pin.new{background:#16a34a}.pin.active{outline:3px solid #60a5fa}" +
    ".pop{position:fixed;width:300px;max-width:calc(100vw - 24px);pointer-events:auto;background:#fff;color:#111214;border-radius:16px;padding:14px;box-shadow:0 20px 50px -12px rgba(0,0,0,.45),0 0 0 1px rgba(0,0,0,.08);font:14px/1.45 inherit}" +
    ".pop h4{margin:0 0 8px;font:650 14px/1.3 inherit}" +
    ".pop textarea,.pop input{display:block;width:100%;border:1px solid #d4d4d8;border-radius:10px;padding:9px 11px;font:14px/1.4 inherit;color:#111214;background:#fafafa;outline:none}" +
    ".pop textarea{min-height:88px;resize:vertical}.pop input{margin-top:8px}" +
    ".pop textarea:focus,.pop input:focus{border-color:#111214;background:#fff}" +
    ".row{display:flex;gap:8px;justify-content:flex-end;align-items:center;margin-top:10px}" +
    ".row .grow{flex:1;color:#71717a;font-size:12px}" +
    ".pop button{all:unset;cursor:pointer;padding:8px 14px;border-radius:999px;font:600 13px/1 inherit;color:#111214;background:#f4f4f5}" +
    ".pop button.go{background:#111214;color:#fff}.pop button:disabled{opacity:.5;cursor:default}" +
    ".msg{white-space:pre-wrap;word-break:break-word;margin:0 0 8px}" +
    ".pop button.line{display:block;box-sizing:border-box;width:100%;margin:2px 0;padding:8px 10px;border-radius:10px;background:#f4f4f5;font:500 13px/1.35 inherit;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:left}" +
    ".pop button.line:hover{background:#e4e4e7}" +
    ".meta{color:#71717a;font-size:12px}" +
    ".err{color:#dc2626;font-size:12.5px;margin-top:6px}" +
    ".toast{position:fixed;left:50%;bottom:80px;transform:translateX(-50%);padding:10px 16px;border-radius:999px;background:#111214;color:#fff;font:500 13.5px/1.2 inherit;pointer-events:none;box-shadow:0 10px 30px -8px rgba(0,0,0,.45)}" +
    "</style>";
  var layer = document.createElement("div");
  root.appendChild(layer);

  function mk(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function toast(text) {
    var t = mk("div", "toast", text);
    layer.appendChild(t);
    setTimeout(function () { t.remove(); }, 3200);
  }

  // A CSS path to an element, so a note stays on it if the layout changes.
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

  function docSize() {
    var d = document.documentElement;
    return { w: Math.max(d.scrollWidth, d.clientWidth, 1), h: Math.max(d.scrollHeight, d.clientHeight, 1) };
  }

  // Where to draw a note right now (viewport coordinates), or null if off-page.
  function place(item) {
    if (item.selector && item.ox != null && item.oy != null) {
      var el = null;
      try { el = document.querySelector(item.selector); } catch (e) { el = null; }
      if (el) {
        var r = el.getBoundingClientRect();
        if (r.width || r.height) return { x: r.left + item.ox * r.width, y: r.top + item.oy * r.height };
      }
    }
    if (item.xp == null || item.y == null) return null;
    return { x: item.xp * docSize().w - window.scrollX, y: item.y - window.scrollY };
  }

  function keepInView(pop, x, y) {
    var w = Math.min(300, window.innerWidth - 24);
    var left = Math.min(Math.max(12, x + 14), window.innerWidth - w - 12);
    var top = y + 12;
    pop.style.left = left + "px";
    pop.style.top = top + "px";
    requestAnimationFrame(function () {
      var h = pop.offsetHeight;
      if (top + h > window.innerHeight - 12) pop.style.top = Math.max(12, y - h - 12) + "px";
    });
  }

  function send(data) {
    return fetch(BASE, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data), credentials: "same-origin" })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (body) {
          if (!r.ok) throw new Error(body.detail || "Couldn't send (" + r.status + ")");
          return body;
        });
      });
  }

  /* ---------------- leaving a note (both modes) ---------------- */

  var picking = null;

  function stopPicking() {
    if (picking) {
      picking.catcher.remove();
      picking.hint.remove();
      document.removeEventListener("keydown", picking.onKey, true);
      picking = null;
    }
  }

  function startPicking(onDone) {
    stopPicking();
    closePop();
    var catcher = mk("div", "catch");
    var hint = mk("div", "hint");
    hint.appendChild(mk("span", null, "Click the spot you want to comment on"));
    var general = mk("button", null, "General note");
    var cancel = mk("button", null, "Cancel");
    hint.appendChild(general);
    hint.appendChild(cancel);
    layer.appendChild(catcher);
    layer.appendChild(hint);
    var onKey = function (e) { if (e.key === "Escape") { e.stopPropagation(); stopPicking(); } };
    document.addEventListener("keydown", onKey, true);
    picking = { catcher: catcher, hint: hint, onKey: onKey };
    cancel.addEventListener("click", stopPicking);
    general.addEventListener("click", function () {
      stopPicking();
      openForm(null, onDone);
    });
    catcher.addEventListener("click", function (e) {
      var x = e.clientX, y = e.clientY;
      // find the page element under the click (our layer is out of the way for a moment)
      host.style.display = "none";
      var target = document.elementFromPoint(x, y);
      host.style.display = "";
      stopPicking();
      var spot = { x: x, y: y, xp: (x + window.scrollX) / docSize().w, docY: y + window.scrollY };
      if (target && target !== document.documentElement && target !== document.body) {
        var r = target.getBoundingClientRect();
        spot.selector = cssPath(target);
        spot.ox = r.width ? (x - r.left) / r.width : 0;
        spot.oy = r.height ? (y - r.top) / r.height : 0;
      }
      openForm(spot, onDone);
    });
  }

  var pop = null;
  function closePop() {
    if (pop) { pop.remove(); pop = null; }
    var temp = layer.querySelector(".pin.new");
    if (temp) temp.remove();
  }

  function openForm(spot, onDone) {
    closePop();
    var x = spot ? spot.x : window.innerWidth / 2 - 150;
    var y = spot ? spot.y : window.innerHeight / 3;
    if (spot) {
      var pin = mk("div", "pin new", "+");
      pin.style.left = spot.x + "px";
      pin.style.top = spot.y + "px";
      layer.appendChild(pin);
    }
    pop = mk("div", "pop");
    pop.appendChild(mk("h4", null, spot ? "Comment on this spot" : "General feedback"));
    var text = mk("textarea");
    text.placeholder = "What should change? What's broken or confusing?";
    text.maxLength = 2000;
    var name = mk("input");
    name.placeholder = "Your name (optional)";
    name.maxLength = 60;
    try { name.value = localStorage.getItem(NAME_KEY) || ""; } catch (e) { /* private mode */ }
    var err = mk("div", "err");
    var row = mk("div", "row");
    var cancel = mk("button", null, "Cancel");
    var go = mk("button", "go", "Send");
    row.appendChild(cancel);
    row.appendChild(go);
    pop.appendChild(text);
    pop.appendChild(name);
    pop.appendChild(err);
    pop.appendChild(row);
    layer.appendChild(pop);
    keepInView(pop, x, y);
    setTimeout(function () { text.focus(); }, 0);
    // keep typing inside the form from triggering the site's keyboard shortcuts
    pop.addEventListener("keydown", function (e) {
      e.stopPropagation();
      if (e.key === "Escape") closePop();
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) go.click();
    });
    cancel.addEventListener("click", closePop);
    go.addEventListener("click", function () {
      var message = text.value.trim();
      if (!message) { err.textContent = "Write a short note first."; text.focus(); return; }
      go.disabled = true;
      go.textContent = "Sending…";
      try { localStorage.setItem(NAME_KEY, name.value.trim()); } catch (e) { /* ignore */ }
      var data = {
        message: message, name: name.value.trim(),
        page: location.pathname + location.search, url: location.href, title: document.title,
        vw: window.innerWidth, vh: window.innerHeight, ua: navigator.userAgent,
      };
      if (spot) {
        data.xp = spot.xp; data.y = spot.docY;
        if (spot.selector) { data.selector = spot.selector; data.ox = spot.ox; data.oy = spot.oy; }
      }
      send(data).then(function () {
        closePop();
        toast("Thanks! Your feedback was sent.");
        if (onDone) onDone();
      }).catch(function (e) {
        err.textContent = e.message;
        go.disabled = false;
        go.textContent = "Send";
      });
    });
  }

  /* ---------------- visitor mode ---------------- */

  function visitor() {
    var bar = mk("div", "bar");
    var btn = mk("button", "primary", "Feedback");
    btn.title = "Leave feedback on this page";
    bar.appendChild(btn);
    layer.appendChild(bar);
    btn.addEventListener("click", function () { startPicking(null); });
  }

  /* ---------------- review mode (owner, this computer) ---------------- */

  function review() {
    var items = [];
    var showPins = true;
    var showResolved = false;
    var openId = (location.hash.match(/homeport-fb=([a-f0-9]+)/) || [])[1] || null;
    var pins = mk("div");
    layer.appendChild(pins);

    var bar = mk("div", "bar");
    var count = mk("button", "count", "Feedback");
    count.title = "List the notes on this page";
    var toggle = mk("button", null, "Hide notes");
    var resolvedBtn = mk("button", null, "Show resolved");
    var add = mk("button", null, "Add note");
    var exit = mk("button", "primary", "Exit review");
    exit.title = "Show the site without feedback";
    [count, toggle, resolvedBtn, add, exit].forEach(function (n) { bar.appendChild(n); });
    layer.appendChild(bar);

    toggle.addEventListener("click", function () {
      showPins = !showPins;
      toggle.textContent = showPins ? "Hide notes" : "Show notes";
      if (!showPins) closePop();
      draw();
    });
    resolvedBtn.addEventListener("click", function () {
      showResolved = !showResolved;
      resolvedBtn.textContent = showResolved ? "Hide resolved" : "Show resolved";
      draw();
    });
    add.addEventListener("click", function () { startPicking(load); });
    // the list also holds general notes, which have no spot on the page
    count.addEventListener("click", function () {
      if (pop) { closePop(); return; }
      var list = visible();
      pop = mk("div", "pop");
      pop.appendChild(mk("h4", null, list.length ? "Notes on this page" : "No notes on this page"));
      list.forEach(function (item, n) {
        var line = mk("button", "line", (place(item) ? "#" + (n + 1) + "  " : "General  ") + item.message.slice(0, 90));
        line.title = item.message;
        line.addEventListener("click", function () {
          var at = place(item);
          if (at && (at.y < 0 || at.y > window.innerHeight)) { window.scrollBy(0, at.y - window.innerHeight / 3); at = place(item); }
          show(item, at || { x: window.innerWidth - 330, y: window.innerHeight - 260 });
        });
        pop.appendChild(line);
      });
      layer.appendChild(pop);
      pop.style.right = "16px";
      pop.style.bottom = "70px";
    });
    exit.addEventListener("click", function () {
      location.href = BASE + "/review?on=0&to=" + encodeURIComponent(location.pathname + location.search);
    });

    function visible() {
      return items.filter(function (i) { return showResolved || i.status === "open"; });
    }

    function draw() {
      pins.textContent = "";
      var open = items.filter(function (i) { return i.status === "open"; }).length;
      var general = items.filter(function (i) { return i.status === "open" && !place(i); }).length;
      count.textContent = open + " open on this page" + (general ? " (" + general + " general)" : "") +
        (items.length > open ? " · " + (items.length - open) + " resolved" : "");
      if (!showPins) return;
      visible().forEach(function (item, n) {
        var at = place(item);
        if (!at) return;
        if (at.x < -30 || at.y < -30 || at.x > window.innerWidth + 30 || at.y > window.innerHeight + 30) return;
        var pin = mk("div", "pin" + (item.status === "resolved" ? " resolved" : "") + (item.id === openId ? " active" : ""), String(n + 1));
        pin.style.left = at.x + "px";
        pin.style.top = at.y + "px";
        pin.title = item.message.slice(0, 80);
        pin.addEventListener("click", function () { show(item, at); });
        pins.appendChild(pin);
      });
    }

    function show(item, at) {
      closePop();
      openId = item.id;
      draw();
      pop = mk("div", "pop");
      pop.appendChild(mk("p", "msg", item.message));
      var when = new Date((item.created_at || 0) * 1000);
      var meta = (item.name || "Anonymous") + " · " + when.toLocaleString();
      if (item.vw) meta += " · " + Math.round(item.vw) + "×" + Math.round(item.vh || 0) + " screen";
      if (item.source === "local") meta += " · added here";
      pop.appendChild(mk("div", "meta", meta));
      if (!item.selector && item.xp == null) pop.appendChild(mk("div", "meta", "General note (no spot on the page)"));
      var row = mk("div", "row");
      var close = mk("button", null, "Close");
      var flip = mk("button", "go", item.status === "open" ? "Resolve" : "Reopen");
      row.appendChild(close);
      row.appendChild(flip);
      pop.appendChild(row);
      layer.appendChild(pop);
      keepInView(pop, at.x, at.y);
      close.addEventListener("click", function () { openId = null; closePop(); draw(); });
      flip.addEventListener("click", function () {
        flip.disabled = true;
        fetch(BASE + "/" + item.id, { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: item.status === "open" ? "resolved" : "open" }) })
          .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
          .then(function (upd) { item.status = upd.status; closePop(); draw(); })
          .catch(function () { flip.disabled = false; toast("Couldn't update — is Homeport running?"); });
      });
    }

    var lastPath = null;
    function load() {
      lastPath = location.pathname;
      fetch(BASE + "/list?page=" + encodeURIComponent(location.pathname), { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          items = (data.items || []).sort(function (a, b) { return (a.created_at || 0) - (b.created_at || 0); });
          draw();
          if (openId) {
            var it = items.filter(function (i) { return i.id === openId; })[0];
            if (it) {
              if (it.status === "resolved" && !showResolved) resolvedBtn.click();
              var at = place(it);
              if (at && (at.y < 0 || at.y > window.innerHeight)) {
                window.scrollBy(0, at.y - window.innerHeight / 3);
                at = place(it);
              }
              if (at) show(it, at);
            }
          }
        })
        .catch(function () { count.textContent = "Couldn't load feedback"; });
    }

    var queued = false;
    function redraw() {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; if (!pop) draw(); });
    }
    window.addEventListener("scroll", redraw, { passive: true });
    window.addEventListener("resize", redraw);
    // single-page apps change the path without reloading
    setInterval(function () { if (location.pathname !== lastPath) { closePop(); openId = null; load(); } }, 1000);
    load();
  }

  function start() {
    (document.body || document.documentElement).appendChild(host);
    if (MODE === "review") review();
    else visitor();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();

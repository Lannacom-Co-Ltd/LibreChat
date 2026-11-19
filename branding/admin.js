/*
 * Administrators' "System logs" in LibreChat's left icon rail, for role ADMIN only. Like the
 * rail's other entries it fills the list panel and the main area: the log viewer
 * (office/files/logs.py, /aihub-logs/?embed=1) puts its file list where LibreChat's list panel is,
 * at the same width, and the entries in the main area. It copies LibreChat's theme tokens and
 * language live. Esc, its close button or any other rail button closes it.
 *
 * LibreChat asks GET /api/user for the signed-in user when the app starts; this script watches
 * that response (it runs before the app's own bundle, so it can see the request) and reads the
 * role from it, instead of asking for a token of its own. The viewer checks the role again on
 * every request, so this only decides what is shown, never what is allowed.
 * Loaded by docker-compose.override.yml; bump admin.js?v= there after changing this file.
 */
(function () {
  var USER_URL = /\/api\/user(\?|$)/;
  var BUTTON_ID = "aihub-admin-logs";
  var PANEL_ID = "aihub-admin-logs-panel";
  var ANCHOR = '[data-testid="nav-panel-mcp-builder"]';
  var RAIL = 'aside[aria-label="Control Panel"]';
  var VIEWER = "/aihub-logs/";
  var TEXT = {
    th: { label: "บันทึกระบบ (ผู้ดูแล)", title: "บันทึกระบบ" },
    en: { label: "System logs (admin)", title: "System logs" },
  };
  var ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" class="h-5 w-5" aria-hidden="true">' +
    '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>' +
    '<path d="M9 13h6"/><path d="M9 17h4"/></svg>';
  /* The rail buttons' resting look, taken once from LibreChat's own button classes so the icon
     never inherits whatever state another button is in. Only one rail entry shows as selected:
     while the log panel is open, the others' "pressed" look is switched off. */
  var BUTTON_CLASS =
    "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium " +
    "ring-offset-surface-primary transition-colors duration-theme-fast focus-visible:outline-none " +
    "focus-visible:ring-2 focus-visible:ring-text-primary focus-visible:ring-offset-2 hover:bg-surface-hover " +
    "hover:text-text-primary size-10 cursor-pointer h-9 w-9 rounded-lg text-text-secondary";
  var TOOLTIP_ID = "aihub-admin-tooltip";
  var tooltipEl = null;
  var isAdmin = false;
  var STYLE =
    "#" + "aihub-admin-logs[aria-pressed=\"true\"]{background-color:rgb(var(--surface-active-alt));color:rgb(var(--text-primary));}" +
    "html.aihub-logs-open [data-testid^=\"nav-panel-\"][aria-pressed=\"true\"]," +
    "html.aihub-logs-open [data-testid^=\"nav-panel-\"][data-state=\"active\"]" +
    "{background-color:transparent!important;color:rgb(var(--text-secondary))!important;}" +
    "#" + TOOLTIP_ID + "{position:fixed;z-index:150;pointer-events:none;transition:opacity 120ms ease,transform 120ms ease;opacity:0;transform:translateX(-6px);}" +
    "#" + TOOLTIP_ID + ".show{opacity:1;transform:translateX(0);}" +
    "#" + TOOLTIP_ID + " .tooltip{position:relative;display:flex;align-items:center;white-space:nowrap;padding:0.25rem 0.5rem;font-size:1rem;line-height:1.5rem;border-radius:0.275rem;background-color:rgb(var(--surface-primary));color:rgb(var(--text-primary));box-shadow:0 2px 4px rgba(0,0,0,0.25);}" +
    "html.dark #" + TOOLTIP_ID + " .tooltip{box-shadow:0 1px 2px rgba(0,0,0,0.35);}" +
    "html.high-contrast #" + TOOLTIP_ID + " .tooltip{border:1px solid rgb(var(--border-medium));box-shadow:none;}" +
    "#" + TOOLTIP_ID + " .ah-arrow{position:absolute;width:16px;height:16px;top:50%;right:100%;transform:translateY(-50%);pointer-events:none;fill:rgb(var(--surface-primary));}";

  function removeTooltip() {
    if (tooltipEl) {
      tooltipEl.remove();
      tooltipEl = null;
    }
  }

  function hideTooltip() {
    if (tooltipEl) {
      var el = tooltipEl;
      tooltipEl = null;
      el.classList.remove("show");
      setTimeout(function () {
        if (el.parentNode) el.remove();
      }, 120);
    }
  }

  function showTooltip(button) {
    if (!button || !document.body.contains(button)) return;
    removeTooltip();
    var label = text().label;
    var rect = button.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return;

    var wrapper = document.createElement("div");
    wrapper.id = TOOLTIP_ID;

    var tip = document.createElement("div");
    tip.className = "tooltip";
    tip.setAttribute("role", "tooltip");

    var arrow = document.createElement("div");
    arrow.className = "ah-arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.innerHTML =
      '<svg display="block" viewBox="0 0 30 30" width="16" height="16">' +
      '<g transform="rotate(-90 15 15)">' +
      '<path stroke="none" d="M23 27.8C24.1 29 26.4 30 28 30H30H0H2C3.7 30 5.9 29 7 27.8L14 20.6C14.7 19.8 15.3 19.8 16 20.6L23 27.8Z"></path>' +
      '</g></svg>';

    tip.appendChild(arrow);
    tip.appendChild(document.createTextNode(label));
    wrapper.appendChild(tip);
    document.body.appendChild(wrapper);
    tooltipEl = wrapper;

    var tipRect = tip.getBoundingClientRect();
    var top = rect.top + (rect.height - tipRect.height) / 2;
    var left = rect.right + 8;

    wrapper.style.top = top + "px";
    wrapper.style.left = left + "px";

    requestAnimationFrame(function () {
      if (tooltipEl === wrapper) {
        wrapper.classList.add("show");
      }
    });
  }

  function addStyle() {
    if (document.getElementById("aihub-admin-style") || !document.head) return;
    var style = document.createElement("style");
    style.id = "aihub-admin-style";
    style.textContent = STYLE;
    document.head.append(style);
  }

  function text() {
    return (document.documentElement.lang || "").indexOf("th") === 0 ? TEXT.th : TEXT.en;
  }

  function panel() {
    return document.getElementById(PANEL_ID);
  }

  /** Where the rail ends, and how wide LibreChat's list panel next to it is (a default when it
   *  is collapsed). The log panel covers both the list panel and the main area, so the file list
   *  takes the list panel's place and the log entries the main area's. */
  function geometry() {
    var anchor = document.querySelector(ANCHOR);
    var rail = anchor && anchor.parentElement && anchor.parentElement.parentElement;
    var aside = document.querySelector(RAIL);
    var railRight = rail ? rail.getBoundingClientRect().right : 0;
    var asideRight = aside ? aside.getBoundingClientRect().right : 0;
    if (railRight <= 0 || railRight > window.innerWidth - 240) return { left: 0, side: 0 };
    var side = asideRight - railRight;
    return { left: railRight, side: side >= 160 ? side : 260 };
  }

  function closePanel() {
    hideTooltip();
    var open = panel();
    if (open) open.remove();
    document.documentElement.classList.remove("aihub-logs-open");
    var button = document.getElementById(BUTTON_ID);
    if (button) button.setAttribute("aria-pressed", "false");
    document.removeEventListener("keydown", onKey, true);
  }

  function onKey(event) {
    if (event.key === "Escape") closePanel();
  }

  function fit(box) {
    var g = geometry();
    box.style.left = g.left + "px";
    var frame = box.querySelector("iframe");
    try {
      var root = frame && frame.contentDocument && frame.contentDocument.documentElement;
      if (root) root.style.setProperty("--side-width", g.side ? g.side + "px" : "100%");
    } catch (e) {}
  }

  function openPanel() {
    hideTooltip();
    if (panel()) return;
    var box = document.createElement("div");
    box.id = PANEL_ID;
    box.setAttribute("role", "region");
    box.setAttribute("aria-label", text().title);
    box.style.cssText =
      "position:fixed;top:0;right:0;bottom:0;z-index:40;display:flex;background:rgb(var(--surface-primary));";
    var frame = document.createElement("iframe");
    frame.src = VIEWER + "?embed=1";
    frame.title = text().title;
    frame.style.cssText = "flex:1;width:100%;height:100%;border:0;background:transparent;";
    frame.addEventListener("load", function () {
      fit(box);
      try { frame.contentWindow.focus(); } catch (e) {}
    });
    box.append(frame);
    document.body.append(box);
    fit(box);
    document.documentElement.classList.add("aihub-logs-open");
    document.getElementById(BUTTON_ID).setAttribute("aria-pressed", "true");
    document.addEventListener("keydown", onKey, true);
  }

  /** Called by the log viewer inside the panel (same site): its close button and Esc. */
  window.aihubLogs = { close: closePanel, newTab: VIEWER };

  function place() {
    var existing = document.getElementById(BUTTON_ID);
    if (!isAdmin) {
      if (existing) existing.remove();
      hideTooltip();
      closePanel();
      return;
    }
    var open = panel();
    if (open) fit(open);
    var anchor = document.querySelector(ANCHOR);
    if (!anchor) return;
    var label = text().label;
    if (existing && existing.previousElementSibling === anchor) {
      if (existing.getAttribute("aria-label") !== label) {
        existing.setAttribute("aria-label", label);
      }
      existing.removeAttribute("title");
      return;
    }
    if (existing) existing.remove();
    addStyle();
    var button = document.createElement("button");
    button.type = "button";
    button.id = BUTTON_ID;
    button.className = BUTTON_CLASS;
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-pressed", String(!!open));
    button.removeAttribute("title");
    button.innerHTML = ICON;
    button.addEventListener("click", function () {
      hideTooltip();
      panel() ? closePanel() : openPanel();
    });
    button.addEventListener("mouseenter", function () {
      showTooltip(button);
    });
    button.addEventListener("mouseleave", hideTooltip);
    button.addEventListener("focus", function () {
      showTooltip(button);
    });
    button.addEventListener("blur", hideTooltip);
    anchor.insertAdjacentElement("afterend", button);
  }

  function readUser(body) {
    try {
      var user = JSON.parse(body);
      if (user && typeof user === "object" && "role" in user) {
        isAdmin = String(user.role).toUpperCase() === "ADMIN";
        place();
      }
    } catch (e) {}
  }

  var xhrOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    if (String(method).toUpperCase() === "GET" && USER_URL.test(String(url))) {
      this.addEventListener("load", function () {
        if (this.status === 200) readUser(this.responseText);
      });
    }
    return xhrOpen.apply(this, arguments);
  };

  if (window.fetch) {
    var fetch0 = window.fetch;
    window.fetch = function (input, init) {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      var method = (init && init.method) || (input && input.method) || "GET";
      var result = fetch0.apply(this, arguments);
      if (String(method).toUpperCase() === "GET" && USER_URL.test(url)) {
        result.then(function (res) {
          if (res.ok) res.clone().text().then(readUser).catch(function () {});
        }).catch(function () {});
      }
      return result;
    };
  }

  document.addEventListener(
    "click",
    function (event) {
      if (!panel()) return;
      var target = event.target;
      var rail = target && target.closest && target.closest(RAIL);
      var own = target && target.closest && target.closest("#" + BUTTON_ID);
      if (rail && !own && target.closest("button, a")) closePanel();
    },
    true
  );
  window.addEventListener("scroll", hideTooltip, true);
  window.addEventListener("resize", function () {
    hideTooltip();
    place();
  });
  window.addEventListener("popstate", closePanel);

  var pending = false;
  var schedule = function () {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () {
      pending = false;
      place();
    });
  };
  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["lang"],
  });
})();

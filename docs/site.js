window.SHELLBRAIN_ANALYTICS = window.SHELLBRAIN_ANALYTICS || {
  // GA4 measurement IDs are public identifiers, not secrets.
  // Paste your GA4 measurement ID here, for example: "G-ABC123DEF4"
  gaMeasurementId: "G-0R72SSJBD6",
  allowedHosts: ["shellbrain.ai", "www.shellbrain.ai", "cucupac.github.io"],
};

// ── Analytics bootstrap ──────────────────────
(function () {
  var config = window.SHELLBRAIN_ANALYTICS || {};
  var measurementId = (config.gaMeasurementId || "").trim();
  var allowedHosts = Array.isArray(config.allowedHosts) ? config.allowedHosts : [];
  var host = window.location.hostname;
  var protocol = window.location.protocol;

  window.shellbrainTrack = function () {};

  if (!measurementId) return;
  if (protocol !== "https:" && protocol !== "http:") return;

  if (allowedHosts.length > 0) {
    var isAllowedHost = allowedHosts.some(function (allowedHost) {
      return host === allowedHost || host.endsWith("." + allowedHost);
    });

    if (!isAllowedHost) return;
  }

  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() {
    window.dataLayer.push(arguments);
  };

  window.gtag("js", new Date());
  window.gtag("config", measurementId);

  window.shellbrainTrack = function (eventName, params) {
    if (!eventName) return;
    window.gtag("event", eventName, params || {});
  };

  var script = document.createElement("script");
  script.async = true;
  script.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(measurementId);
  document.head.appendChild(script);
})();

function trackSiteEvent(eventName, params) {
  if (typeof window.shellbrainTrack !== "function") return;
  window.shellbrainTrack(eventName, params);
}

function getCopyEventName(selector) {
  switch (selector) {
    case "#install-cmd":
      return "install_command_copy";
    case "#upgrade-cmd":
      return "upgrade_command_copy";
    case "#session-prompt":
      return "session_prompt_copy";
    default:
      return "copy_source";
  }
}

// ── Shared favicon ───────────────────────────
(function () {
  if (document.querySelector('link[rel="icon"]')) return;

  var script = document.currentScript;
  var base = script && script.src ? script.src : location.href;
  var href = new URL("assets/shellbrain_logo.png", base).href;
  var icon = document.createElement("link");

  icon.rel = "icon";
  icon.type = "image/png";
  icon.href = href;

  document.head.appendChild(icon);
})();

// ── Active nav link ──────────────────────────
// Works both on deployed site (paths like /agents/) and local file opens
// (paths like /Users/.../docs/agents/index.html).
(function () {
  var path = location.pathname;
  document.querySelectorAll(".nav a").forEach(function (a) {
    var href = a.getAttribute("href").replace(/\/+$/, "");
    // href is like "/agents" or "/memory/procedural"
    // On deployed site, path is "/agents/" — strip trailing slash and compare.
    // On local file open, path is ".../docs/agents/index.html" — check if
    // the path contains the href segment (e.g., "/agents").
    if (!href || href === "/") return;
    var normalized = path.replace(/\/index\.html$/, "").replace(/\/+$/, "");
    if (normalized === href || normalized.endsWith(href)) {
      a.setAttribute("aria-current", "page");
    }
  });
})();

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[href]");
  if (!link) return;

  const href = link.getAttribute("href");
  if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) {
    return;
  }

  let url;
  try {
    url = new URL(link.href, location.href);
  } catch {
    return;
  }

  // GA4 enhanced measurement can capture outbound clicks. This fills the gap
  // for same-site navigation.
  if (url.origin !== location.origin) return;
  if (url.pathname === location.pathname && url.hash) return;

  trackSiteEvent("internal_link_click", {
    destination_path: url.pathname,
  });
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-source]");
  if (!button) return;

  const selector = button.getAttribute("data-copy-source");
  if (!selector) return;

  const source = document.querySelector(selector);
  if (!source) return;

  const text = "value" in source ? source.value : source.textContent;
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
    trackSiteEvent(getCopyEventName(selector));

    const previous = button.textContent;
    button.textContent = button.getAttribute("data-copy-success") || "copied";
    button.classList.add("is-copied");
    window.setTimeout(() => {
      button.textContent = previous;
      button.classList.remove("is-copied");
    }, 1600);
  } catch {
    button.textContent = button.getAttribute("data-copy-failed") || "copy failed";
    window.setTimeout(() => {
      button.textContent = button.getAttribute("data-copy-label") || "copy";
    }, 1600);
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-page]");
  if (!button) return;

  const main = document.querySelector("main");
  if (!main) return;

  const text = main.innerText;
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
    trackSiteEvent("page_copy");

    const previous = button.textContent;
    button.textContent = "copied";
    button.classList.add("is-copied");
    window.setTimeout(() => {
      button.textContent = previous;
      button.classList.remove("is-copied");
    }, 1600);
  } catch {
    button.textContent = "failed";
    window.setTimeout(() => {
      button.textContent = "copy page";
    }, 1600);
  }
});

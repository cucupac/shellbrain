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

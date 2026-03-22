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

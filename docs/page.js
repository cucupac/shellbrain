const installCommand = "curl -L ShellBrain.ai/install | bash";

document.querySelectorAll("[data-copy-install]").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(installCommand);
      const original = button.textContent;
      button.textContent = "Copied";
      window.setTimeout(() => {
        button.textContent = original;
      }, 1400);
    } catch {
      const original = button.textContent;
      button.textContent = "Copy failed";
      window.setTimeout(() => {
        button.textContent = original;
      }, 1400);
    }
  });
});

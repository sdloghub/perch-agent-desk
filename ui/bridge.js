/* Same-origin integration with the genuine Open WebUI chat runtime. */
(() => {
  if (window.parent === window) return;
  try {
    if (
      window.parent.location.pathname !== "/desk" &&
      window.parent.location.pathname !== "/desk/"
    )
      return;
  } catch {
    return;
  }
  document.documentElement.classList.add("perch-embed");
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "/desk/embed.css";
  document.head.append(css);
  let last = "",
    pending = false;
  const snapshot = () => {
    pending = false;
    const data = {
      type: "perch:state",
      chatId: location.pathname.startsWith("/c/")
        ? decodeURIComponent(location.pathname.slice(3))
        : null,
      title:
        document.querySelector("main nav h1,main h1")?.textContent?.trim() ||
        "新对话",
      model:
        document
          .getElementById("model-selector-model-button")
          ?.textContent?.trim() || "",
      draft: !!document.getElementById("chat-input")?.textContent?.trim(),
    };
    const value = JSON.stringify(data);
    if (value !== last) {
      last = value;
      window.parent.postMessage(data, location.origin);
    }
  };
  new MutationObserver(() => {
    if (!pending) {
      pending = true;
      requestAnimationFrame(snapshot);
    }
  }).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  document.addEventListener("input", snapshot);
  document.addEventListener("visibilitychange", snapshot);
  addEventListener("message", (e) => {
    if (e.origin !== location.origin || e.source !== window.parent) return;
    if (e.data?.type === "perch:theme") {
      document.documentElement.classList.toggle(
        "dark",
        e.data.dark === true,
      );
      document.documentElement.classList.toggle(
        "light",
        e.data.dark !== true,
      );
    }
    if (e.data?.type === "perch:model")
      document.getElementById("model-selector-model-button")?.click();
    if (e.data?.type === "perch:focus")
      document.getElementById("chat-input")?.focus();
    if (e.data?.type === "perch:ping") { last = ""; snapshot(); }
  });
  snapshot();
})();

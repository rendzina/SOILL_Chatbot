/**
 * Load the SOILL chat popup on the demo site.
 *
 * Uses the polished chat UI bundled in ./chat/ and sends questions to
 * SOILL_CHAT_API (Steve's backend or your own API deploy).
 *
 * **Created:** 10-06-2026 (UK style).
 */
(function () {
  const api = (window.SOILL_CHAT_API || "").replace(/\/$/, "");
  if (!api) {
    console.warn("SOILL_CHAT_API is not set in config.js");
    return;
  }

  const base = document.currentScript.src.replace(/embed-chat\.js(\?.*)?$/, "");

  const widgetCss = document.createElement("link");
  widgetCss.rel = "stylesheet";
  widgetCss.href = `${base}mock-site.css`;
  document.head.appendChild(widgetCss);

  const script = document.createElement("script");
  script.src = `${base}widget-iframe.js`;
  const chatPage = `${base}chat/index.html?api=${encodeURIComponent(api)}`;
  script.setAttribute("data-chat-url", chatPage);
  document.body.appendChild(script);
})();

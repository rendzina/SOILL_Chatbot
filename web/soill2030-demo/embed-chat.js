/**
 * Load the SOILL chat popup widget from the FastAPI host.
 *
 * **Created:** 10-06-2026 (UK style).
 */
(function () {
  const api = (window.SOILL_CHAT_API || "").replace(/\/$/, "");
  if (!api) {
    console.warn("SOILL_CHAT_API is not set in config.js");
    return;
  }

  const widgetCss = document.createElement("link");
  widgetCss.rel = "stylesheet";
  widgetCss.href = `${api}/web/mock-site.css`;
  document.head.appendChild(widgetCss);

  const script = document.createElement("script");
  script.src = `${api}/web/widget-iframe.js`;
  script.setAttribute("data-chat-url", `${api}/web/`);
  script.defer = true;
  document.body.appendChild(script);
})();

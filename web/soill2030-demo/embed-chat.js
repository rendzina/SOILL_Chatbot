/**
 * Load the SOILL chat popup on the demo site.
 *
 * **Created:** 10-06-2026 (UK style).
 * **Updated:** 15-06-2026 — local demo uses /web/ on the same uvicorn host.
 */
(function () {
  const base = document.currentScript.src.replace(/embed-chat\.js(\?.*)?$/, "");
  const pageOrigin = window.location.origin.replace(/\/$/, "");
  const host = window.location.hostname;
  const cacheBust = "v=20260722-tables";
  const isLocalDev = host === "localhost" || host === "127.0.0.1";

  // Local uvicorn: always use this machine's API (ignore stale cached config.js).
  let api = (window.SOILL_CHAT_API || "").replace(/\/$/, "");
  if (isLocalDev) {
    api = pageOrigin;
    window.SOILL_CHAT_API = api;
  }

  if (!api) {
    console.warn("SOILL_CHAT_API is not set in config.js");
    return;
  }

  let chatPage;
  if (isLocalDev || api === pageOrigin) {
    chatPage = `${pageOrigin}/web/index.html?${cacheBust}`;
  } else {
    chatPage = `${base}chat/index.html?api=${encodeURIComponent(api)}&${cacheBust}`;
  }

  const widgetCss = document.createElement("link");
  widgetCss.rel = "stylesheet";
  widgetCss.href = `${base}mock-site.css`;
  document.head.appendChild(widgetCss);

  const script = document.createElement("script");
  script.src = `${base}widget-iframe.js?${cacheBust}`;
  script.setAttribute("data-chat-url", chatPage);
  document.body.appendChild(script);
})();

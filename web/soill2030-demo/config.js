/**
 * Chat API base URL (no trailing slash).
 *
 * Path B (API + /web/ on one host): use same origin — localhost, Cranfield
 * Render, or any host that serves both /web/ and /api/chat.
 *
 * Path A (separate static demo only): call the Cranfield production API.
 */
(function () {
  const PRODUCTION_API = "https://soill-chatbot-v2yj.onrender.com";
  const host = window.location.hostname;
  const sameOrigin = window.location.origin.replace(/\/$/, "");

  // Hosts that serve only static files with no /api on the same origin.
  const REMOTE_API_HOSTS = new Set(["soill2030-demo.onrender.com"]);

  if (REMOTE_API_HOSTS.has(host)) {
    window.SOILL_CHAT_API = PRODUCTION_API;
  } else {
    window.SOILL_CHAT_API = sameOrigin;
  }
})();

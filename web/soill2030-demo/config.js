/**
 * Chat API base URL (no trailing slash).
 *
 * When the demo is opened from local uvicorn or Steve's API host, requests
 * stay on the same origin. On a separate static host (e.g. soill2030-demo
 * on Render), calls go to Steve's deployed API.
 */
(function () {
  const STEVE_API = "https://soill-chatbot-api.onrender.com";
  const host = window.location.hostname;
  const sameOrigin = window.location.origin.replace(/\/$/, "");

  if (host === "localhost" || host === "127.0.0.1") {
    window.SOILL_CHAT_API = sameOrigin;
  } else if (host === "soill-chatbot-api.onrender.com") {
    window.SOILL_CHAT_API = sameOrigin;
  } else {
    window.SOILL_CHAT_API = STEVE_API;
  }
})();

/**
 * Floating chat widget — toggles an iframe panel (Approach 1).
 *
 * Usage on a project page:
 *   <script src="https://your-api-host/web/widget-iframe.js"
 *           data-chat-url="https://your-api-host/web/"></script>
 *
 * **Created:** 07-06-2026 (UK style).
 */

(function () {
  const script = document.currentScript;
  const chatUrl =
    (script && script.getAttribute("data-chat-url")) ||
    new URL("index.html", script.src.replace(/widget-iframe\.js.*$/, "")).href;

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "soill-widget-toggle";
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "soill-widget-panel");
  toggle.setAttribute("aria-label", "Open SOILL chat");
  toggle.title = "Chat with SOILL";
  toggle.textContent = "💬";

  const panel = document.createElement("div");
  panel.id = "soill-widget-panel";
  panel.className = "soill-widget-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "SOILL chat");

  const iframe = document.createElement("iframe");
  iframe.src = chatUrl;
  iframe.title = "SOILL chatbot";
  panel.appendChild(iframe);

  function closePanel() {
    panel.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
  }

  function openPanel() {
    panel.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
  }

  toggle.addEventListener("click", () => {
    if (panel.classList.contains("is-open")) {
      closePanel();
    } else {
      openPanel();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panel.classList.contains("is-open")) {
      closePanel();
    }
  });

  document.body.appendChild(panel);
  document.body.appendChild(toggle);
})();

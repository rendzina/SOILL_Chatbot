/**
 * SOILL Chatbot — minimal API test client.
 *
 * **Created:** 07-06-2026 (UK style).
 * **Author:** Professor Stephen Hallett, Cranfield University, 2026.
 */

const SESSION_KEY = "soill_chat_session_id";
const params = new URLSearchParams(window.location.search);
const apiBase = (params.get("api") || window.location.origin).replace(/\/$/, "");

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const statusEl = document.getElementById("status");
const submitBtn = formEl.querySelector('button[type="submit"]');

function getSessionId() {
  return sessionStorage.getItem(SESSION_KEY);
}

function setSessionId(sessionId) {
  if (sessionId) {
    sessionStorage.setItem(SESSION_KEY, sessionId);
  }
}

function appendMessage(role, content, sources) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = content;

  if (sources && sources.length > 0) {
    const sourcesBlock = document.createElement("div");
    sourcesBlock.className = "sources";

    const summary = document.createElement("summary");
    summary.textContent = `Sources (${sources.length})`;

    const details = document.createElement("details");
    details.appendChild(summary);

    const list = document.createElement("ul");
    for (const source of sources) {
      const item = document.createElement("li");
      const location = `${source.location_type}s ${source.location_start}–${source.location_end}`;
      item.innerHTML = `<strong>[${source.label}]</strong> ${escapeHtml(source.filename)} — ${escapeHtml(location)}: ${escapeHtml(source.preview)}`;
      list.appendChild(item);
    }
    details.appendChild(list);
    sourcesBlock.appendChild(details);
    div.appendChild(sourcesBlock);
  }

  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(text) {
  const el = document.createElement("span");
  el.textContent = text || "";
  return el.innerHTML;
}

function setStatus(text) {
  statusEl.textContent = text;
}

async function sendMessage(message) {
  const payload = { message };
  const sessionId = getSessionId();
  if (sessionId) {
    payload.session_id = sessionId;
  }

  submitBtn.disabled = true;
  setStatus("Thinking…");

  try {
    const response = await fetch(`${apiBase}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }

    const data = await response.json();
    setSessionId(data.session_id);

    if (data.error) {
      appendMessage("error", data.answer || data.error);
    } else {
      appendMessage("assistant", data.answer, data.sources);
    }

    setStatus(`Session: ${data.session_id}`);
  } catch (err) {
    appendMessage("error", err.message || String(err));
    setStatus("Request failed.");
  } finally {
    submitBtn.disabled = false;
    inputEl.focus();
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) {
    return;
  }

  appendMessage("user", message);
  inputEl.value = "";
  await sendMessage(message);
});

const existingSession = getSessionId();
setStatus(
  existingSession
    ? `Session restored: ${existingSession}`
    : `API: ${apiBase}/api/chat`
);

inputEl.focus();

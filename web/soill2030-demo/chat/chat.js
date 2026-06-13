/**
 * SOILL Assistant — web chat client for POST /api/chat.
 *
 * **Created:** 07-06-2026 (UK style).
 * **Updated:** 10-06-2026 — welcome screen, starter prompts, source panel.
 */

const SESSION_KEY = "soill_chat_session_id";
const params = new URLSearchParams(window.location.search);
const configuredApi = typeof window.SOILL_CHAT_API === "string" ? window.SOILL_CHAT_API : "";
const apiBase = (params.get("api") || configuredApi || window.location.origin).replace(/\/$/, "");

const STARTER_PROMPTS = [
  {
    label: "New to Mission Soil",
    text: "What is a Soil Health Living Lab and how does it support the EU Mission Soil?",
  },
  {
    label: "SOILL support",
    text: "What structured support does SOILL provide for Living Labs from start to scale?",
  },
  {
    label: "Applying for funding",
    text: "What guidance exists for applicants interested in Mission Soil Living Lab funding?",
  },
];

const messagesEl = document.getElementById("messages");
const welcomeEl = document.getElementById("welcome");
const startersEl = document.getElementById("starter-prompts");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const statusEl = document.getElementById("status");
const newChatBtn = document.getElementById("new-chat-btn");
const submitBtn = formEl.querySelector('button[type="submit"]');

function getSessionId() {
  return sessionStorage.getItem(SESSION_KEY);
}

function setSessionId(sessionId) {
  if (sessionId) {
    sessionStorage.setItem(SESSION_KEY, sessionId);
  }
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

function escapeHtml(text) {
  const el = document.createElement("span");
  el.textContent = text || "";
  return el.innerHTML;
}

function formatLocation(source) {
  const type = source.location_type || "page";
  return `${type}s ${source.location_start}–${source.location_end}`;
}

function extractCitationLabels(inner) {
  const labels = new Set();
  for (const part of inner.split(/[,;]/)) {
    const match = part.trim().match(/^(\d+)/);
    if (match) {
      labels.add(Number(match[1]));
    }
  }
  return [...labels].sort((a, b) => a - b);
}

function renderCitationBadges(inner, sources) {
  const labels = extractCitationLabels(inner);
  if (labels.length === 0) {
    return null;
  }

  return labels
    .map((label) => {
      const source = sources.find((item) => item.label === label);
      const title = source ? source.filename : `Source ${label}`;
      return `<button type="button" class="citation-badge" data-source-label="${label}" title="${escapeHtml(title)}">${label}</button>`;
    })
    .join("");
}

function stripMarkdownHeading(line) {
  return (line || "").replace(/^#{1,6}\s+/, "").trim();
}

function stripBulletPrefix(line) {
  return (line || "").replace(/^[-*]\s+/, "").trim();
}

function formatListItem(line, sources) {
  let content = stripMarkdownHeading(stripBulletPrefix(line));

  const numbered = content.match(/^(\d+[.)]\s*)(.+)$/);
  if (numbered) {
    content = numbered[2].trim();
  }

  const titled = content.match(/^(.{1,90}?)\s*[-–—]\s+(.+)$/);
  if (titled) {
    return `<strong>${formatInline(titled[1].trim(), sources, true)}</strong> ${formatInline(titled[2].trim(), sources, true)}`;
  }

  return formatInline(content, sources, true);
}

function formatInline(text, sources, skipHeadingStrip = false) {
  let raw = text || "";
  if (!skipHeadingStrip) {
    raw = stripMarkdownHeading(raw);
  }

  let html = escapeHtml(raw);
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[([^\]]+)\]/g, (match, inner) => {
    const badges = renderCitationBadges(inner, sources);
    return badges || match;
  });
  return html;
}

function isListLine(line) {
  const trimmed = (line || "").trim();
  return /^[-*]\s+/.test(trimmed) || /^#{1,6}\s+/.test(trimmed);
}

function preprocessAnswerText(text) {
  let value = (text || "").trim().replace(/\r\n/g, "\n");
  value = value.replace(/\s+(?=####\s+\d+[.)])/g, "\n");
  value = value.replace(/^####\s+(\d+[.)]\s*)/gm, "- ");
  value = value.replace(/^####\s+/gm, "- ");
  return value;
}

function formatAssistantContent(text, sources) {
  const normalised = preprocessAnswerText(text);
  if (!normalised) {
    return "";
  }

  const blocks = normalised.split(/\n\s*\n/);
  const htmlParts = [];

  for (const block of blocks) {
    const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
    if (lines.length === 0) {
      continue;
    }

    if (lines.length === 1 && /^#{1,6}\s+/.test(lines[0]) && !/^#{1,6}\s+\d+[.)]/.test(lines[0])) {
      htmlParts.push(
        `<h3 class="answer-heading">${formatInline(stripMarkdownHeading(lines[0]), sources, true)}</h3>`
      );
      continue;
    }

    if (lines.every((line) => isListLine(line))) {
      const items = lines
        .map((line) => `<li>${formatListItem(line, sources)}</li>`)
        .join("");
      htmlParts.push(`<ul class="answer-list">${items}</ul>`);
      continue;
    }

    const paragraph = lines
      .map((line) => formatInline(stripMarkdownHeading(stripBulletPrefix(line)), sources, true))
      .join(" ");
    htmlParts.push(`<p class="answer-paragraph">${paragraph}</p>`);
  }

  return htmlParts.join("");
}

function buildSourcesPanel(sources) {
  const panel = document.createElement("details");
  panel.className = "sources-panel";

  const summary = document.createElement("summary");
  summary.className = "sources-panel__title";
  summary.textContent = `Sources (${sources.length})`;
  panel.appendChild(summary);

  const list = document.createElement("ol");
  list.className = "sources-panel__list";

  for (const source of sources) {
    const item = document.createElement("li");
    item.id = `source-${source.label}`;
    item.className = "sources-panel__item";

    const title = document.createElement("div");
    title.className = "sources-panel__filename";
    title.textContent = `${source.label}. ${source.filename}`;

    const meta = document.createElement("div");
    meta.className = "sources-panel__meta";
    meta.textContent = formatLocation(source);

    const preview = document.createElement("p");
    preview.className = "sources-panel__preview";
    preview.textContent = source.preview || "";

    item.append(title, meta, preview);
    list.appendChild(item);
  }

  panel.appendChild(list);
  return panel;
}

function buildFollowUpQuestions(questions) {
  const section = document.createElement("section");
  section.className = "follow-up";

  const heading = document.createElement("h3");
  heading.className = "follow-up__title";
  heading.textContent = "Suggested questions";
  section.appendChild(heading);

  const list = document.createElement("div");
  list.className = "follow-up__list";

  for (const question of questions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "follow-up__button";
    button.textContent = question;
    button.addEventListener("click", () => {
      inputEl.value = question;
      formEl.requestSubmit();
    });
    list.appendChild(button);
  }

  section.appendChild(list);
  return section;
}

function submitQuestion(message) {
  appendMessage("user", message);
  inputEl.value = "";
  return sendMessage(message);
}

function appendStatusMessage(text) {
  const div = document.createElement("div");
  div.className = "message status";
  div.innerHTML = `
    <ul class="status-steps">
      <li>${escapeHtml(text)}</li>
    </ul>
  `;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function appendMessage(role, content, sources, suggestedQuestions) {
  hideWelcome();

  const div = document.createElement("article");
  div.className = `message ${role}`;

  if (role === "assistant") {
    const body = document.createElement("div");
    body.className = "message__body";
    body.innerHTML = formatAssistantContent(content, sources || []);
    div.appendChild(body);

    body.querySelectorAll(".citation-badge").forEach((badge) => {
      badge.addEventListener("click", () => {
        const label = badge.getAttribute("data-source-label");
        const target = document.getElementById(`source-${label}`);
        const sourcesPanel = div.querySelector(".sources-panel");
        if (sourcesPanel && !sourcesPanel.open) {
          sourcesPanel.open = true;
        }
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "nearest" });
          target.classList.add("is-highlighted");
          window.setTimeout(() => target.classList.remove("is-highlighted"), 1200);
        }
      });
    });

    const actions = document.createElement("div");
    actions.className = "message__actions";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "message__copy";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(content || "");
        copyBtn.textContent = "Copied";
        window.setTimeout(() => {
          copyBtn.textContent = "Copy";
        }, 1500);
      } catch (_err) {
        copyBtn.textContent = "Copy failed";
      }
    });
    actions.appendChild(copyBtn);
    div.appendChild(actions);

    if (sources && sources.length > 0) {
      div.appendChild(buildSourcesPanel(sources));
    }

    if (suggestedQuestions && suggestedQuestions.length > 0) {
      div.appendChild(buildFollowUpQuestions(suggestedQuestions));
    }
  } else if (role === "error") {
    div.textContent = content;
  } else {
    div.textContent = content;
  }

  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideWelcome() {
  if (welcomeEl) {
    welcomeEl.hidden = true;
  }
}

function showWelcome() {
  messagesEl.innerHTML = "";
  if (welcomeEl) {
    welcomeEl.hidden = false;
  }
}

function setStatus(text) {
  statusEl.textContent = text;
}

function renderStarterPrompts() {
  startersEl.innerHTML = "";
  for (const prompt of STARTER_PROMPTS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "starter-prompt";
    button.innerHTML = `
      <span class="starter-prompt__label">${escapeHtml(prompt.label)}</span>
      <span class="starter-prompt__text">${escapeHtml(prompt.text)}</span>
    `;
    button.addEventListener("click", () => {
      inputEl.value = prompt.text;
      formEl.requestSubmit();
    });
    startersEl.appendChild(button);
  }
}

async function sendMessage(message) {
  const payload = { message };
  const sessionId = getSessionId();
  if (sessionId) {
    payload.session_id = sessionId;
  }

  submitBtn.disabled = true;
  setStatus("Connecting to SOILL knowledge base…");
  const pendingStatus = appendStatusMessage("Searching project documents…");

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
    pendingStatus.remove();
    setSessionId(data.session_id);

    if (data.error) {
      appendMessage("error", data.answer || data.error);
    } else {
      appendMessage(
        "assistant",
        data.answer,
        data.sources,
        data.suggested_questions
      );
      setStatus(
        data.sources?.length
          ? `Answered using ${data.sources.length} cited source(s).`
          : "Answer ready."
      );
    }
  } catch (err) {
    pendingStatus.remove();
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

  await submitQuestion(message);
});

newChatBtn.addEventListener("click", () => {
  clearSession();
  showWelcome();
  setStatus("New conversation started.");
  inputEl.focus();
});

renderStarterPrompts();

const existingSession = getSessionId();
setStatus(
  existingSession
    ? `Session restored (${existingSession.slice(0, 8)}…).`
    : `Local test client. API: ${apiBase}/api/chat`
);

inputEl.focus();

# SOILL Chatbot — Deployment and website integration

*Author:* Professor Stephen Hallett, 22 July 2026

This document describes how to deploy the SOILL chatbot for use on a **separate project website**. It covers local testing, production architecture, and the two main integration patterns.

## Two frontends (same backend)

Both UIs call the shared `ChatService` in `packages/soill`. They are **siblings**, not parent/child — Chainlit does **not** call the FastAPI HTTP API.

| Frontend | Purpose |
|----------|---------|
| **Chainlit** (`apps/chatbot/`) | Team testing and RAG prototypes (local and on Render) |
| **FastAPI + `web/`** (`apps/api/`) | Production path for website embeds — widget, dedicated page, SOILL2030 demo |

For a public project website (e.g. soill2030.eu), use the **FastAPI** service and the HTML/JS clients under `web/` — not Chainlit. See the same summary in the [README](../README.md#two-frontends-same-backend) and [approach.md](approach.md#two-frontends-same-backend).

This document, together with the integration demos in [`web/demos.html`](../web/demos.html), focuses on the **production path**: the FastAPI API, test clients, and approaches for integrating the chatbot into your site (dedicated chat page, floating popup widget, iframe embed, and direct API calls).

For day-to-day development (Chainlit, ingest, OCR, admin commands), see the main [README](../README.md). For a rationale behind this architecture, see [approach.md](approach.md). For scanned PDFs before ingest, see [OCR_PDF_PreProcessingWorkflow.md](OCR_PDF_PreProcessingWorkflow.md). For UI work without affecting live Render, see [local-ui-testing.md](local-ui-testing.md).

## Quick start — to try it locally

1. Start the API:

   **uvicorn** is the web server that runs the FastAPI application. The command below is for local testing; `--reload` restarts the server when code changes (development only — not for production).

   ```bash
   uv run --directory apps/api uvicorn main:app --reload --port 8080
   ```

   In production you still use uvicorn, but without `--reload`, with `--host 0.0.0.0` and your host’s port (see [Production deployment](#production-deployment) below).

2. Open **[http://localhost:8080/web/demos.html](http://localhost:8080/web/demos.html)** and work through the steps in order — API docs, curl, then the HTML integration demos (full-page chat, dedicated page, floating popup, SOILL2030 mock).

The rest of this document explains the architecture, integration patterns, CORS, and production deployment in more detail.

---

## Architecture overview

The chatbot backend is shared across frontends:

```mermaid
flowchart LR
  subgraph frontends [Frontends]
    CL[Chainlit]
    WebPage[Dedicated chat page]
    Widget[Floating popup widget]
  end

  API[FastAPI POST /api/chat]
  CS[ChatService]
  PG[(Postgres + pgvector)]
  Mistral[Mistral API]

  CL --> CS
  WebPage --> API
  Widget --> API
  API --> CS
  CS --> PG
  CS --> Mistral
```

| Component | Role | Typical deployment |
|-----------|------|-------------------|
| **Chainlit** (`apps/chatbot/`) | Full-screen chat UI for testing and internal use | Render via [`render.yaml`](../render.yaml) |
| **FastAPI** (`apps/api/`) | HTTP API for external websites | Separate Render service (e.g. `soill-chatbot-api`) |
| **ChatService** (`packages/soill/`) | RAG, citations, logging | Bundled with each app |
| **Web clients** (`web/`) | Test pages, embeddable demos, SOILL2030 mock | Served by FastAPI at `/web/` |

Chainlit and the FastAPI API are **sibling frontends** — both call the same `ChatService`. Chainlit talks to `ChatService` in-process; web clients talk to FastAPI. The project website should use **FastAPI**, not Chainlit.

---

## Integration options

Two patterns are supported for a separate project website:

### Approach 1 — Floating popup (bottom-right widget)

A chat button fixed to the bottom-right of every page opens a panel (usually an iframe) containing the chat UI.

**Best for:** keeping the chat available site-wide without dedicating a full page.

**Local demos:**

- [http://localhost:8080/web/mock-site-popup.html](http://localhost:8080/web/mock-site-popup.html)
- [http://localhost:8080/web/soill2030-demo/](http://localhost:8080/web/soill2030-demo/) — polished mock of soill2030.eu with popup widget

**Embed snippet (iframe widget):**

```html
<link rel="stylesheet" href="https://your-api-host/web/mock-site.css">
<script
  src="https://your-api-host/web/widget-iframe.js"
  data-chat-url="https://your-api-host/web/">
</script>
```

The widget script adds a toggle button and iframe panel. No CORS configuration is required for this pattern because the chat UI runs inside the iframe on the API host.

### Approach 2 — Dedicated chat page

A normal site page (e.g. `/ask-soill`) or a link in the navigation opens the full chat experience.

**Best for:** a prominent “Ask SOILL” area with more space for conversation and sources.

**Local demos:**

| Demo | URL |
|------|-----|
| Full chat page | [http://localhost:8080/web/](http://localhost:8080/web/) |
| Mock site with link + iframe embed | [http://localhost:8080/web/mock-site-page.html](http://localhost:8080/web/mock-site-page.html) |
| SOILL2030 site mock (popup) | [http://localhost:8080/web/soill2030-demo/](http://localhost:8080/web/soill2030-demo/) |

**Option A — Link out:**

```html
<a href="https://your-api-host/web/">Ask SOILL</a>
```

**Option B — Embed in a page section:**

```html
<iframe
  src="https://your-api-host/web/"
  title="SOILL chatbot"
  style="width:100%;height:70vh;border:none;border-radius:12px;">
</iframe>
```

### Demo index

All local integration demos are listed at:

[http://localhost:8080/web/demos.html](http://localhost:8080/web/demos.html)

---

## Local testing

### 1. Start the API

**uvicorn** is the web server that runs the FastAPI application and listens for HTTP requests. The command below starts it on your machine for local testing; `--reload` automatically restarts the server when you change code (development only — do not use that flag in production).

In a production environment you would still use uvicorn (or a process manager in front of it), but without `--reload`, binding to all interfaces (`--host 0.0.0.0`) and the port provided by your host (e.g. Render’s `$PORT`). See [Deploy the FastAPI service](#deploy-the-fastapi-service) below for the production command.

```bash
uv sync --all-packages
uv run --directory apps/api uvicorn main:app --reload --port 8080
```

Stop with **Ctrl+C**.

### 2. Interactive API docs (Swagger)

**Swagger UI** is an interactive reference for the API, built automatically by FastAPI. Use it when you want to explore available endpoints, see request and response formats, and send test messages from your browser without writing code or using the terminal — handy for a quick sanity check that the API is working before trying the HTML demos.

With the server running, open:

- **Swagger UI:** [http://localhost:8080/docs](http://localhost:8080/docs) — try `POST /api/chat` from the browser
- **ReDoc:** [http://localhost:8080/redoc](http://localhost:8080/redoc)
- **Health check:** [http://localhost:8080/health](http://localhost:8080/health)

On the Swagger page, expand **POST /api/chat**, click **Try it out**, and send a body such as:

```json
{
  "message": "What is a living lab?"
}
```

Optional: pass `"session_id"` to continue a multi-turn conversation (history is loaded from the database when `CHAT_HISTORY_ENABLED=true`).

### 3. curl

**curl** sends an HTTP request from your terminal — useful when you want to test the API without a browser, script the same call in CI, or share an exact request with a colleague. Run the command below from any terminal (the API must already be running on port 8080). The response is printed as JSON in the terminal.

```bash
curl -X POST http://localhost:8080/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What is soil health?"}'
```

### 4. HTML test client and integration demos

With the API running:

| URL | Description |
|-----|-------------|
| [http://localhost:8080/web/demos.html](http://localhost:8080/web/demos.html) | Index of integration options |
| [http://localhost:8080/web/](http://localhost:8080/web/) | Full-page chat client |
| [http://localhost:8080/web/mock-site-page.html](http://localhost:8080/web/mock-site-page.html) | Mock project site — dedicated chat page |
| [http://localhost:8080/web/mock-site-popup.html](http://localhost:8080/web/mock-site-popup.html) | Mock project site — floating popup widget |
| [http://localhost:8080/web/soill2030-demo/](http://localhost:8080/web/soill2030-demo/) | SOILL2030 site mock — popup widget (preview for soill2030.eu) |

Try the full-page chat client first, then the mock project sites and SOILL2030 demo to see how the chatbot could appear on a separate website.

---

## CORS (cross-origin API calls)

CORS is only required when JavaScript on your **project website origin** calls `POST /api/chat` directly (a native widget without an iframe).

The iframe-based demos do **not** need CORS changes because the browser loads the chat page from the API host.

To allow a local project dev server (e.g. `http://localhost:5173`), add its origin to `allow_origins` in [`apps/api/main.py`](../apps/api/main.py). In production, allow only your project website domain(s), for example:

```python
allow_origins=[
    "https://www.soill-project.example",
    "https://soill-project.example",
]
```

Never use `allow_origins=["*"]` with credentials in production.

---

## Production deployment

### Recommended layout

Typical setup uses **one Postgres database** and **two web services** (plus an optional static demo):

| Service | Host example | Notes |
|---------|--------------|-------|
| Project website | `https://www.soill2030.eu` | Your existing CMS or static site |
| Chat API | `https://soill-chatbot-api.onrender.com` (or custom subdomain) | FastAPI on Render |
| Chainlit | Render Chainlit service | Internal/testing only; not required for public widget |
| SOILL2030 demo (optional) | Static site from `web/soill2030-demo/` | Preview embed before wiring the live CMS |

Chainlit and the API share the same **Postgres** database (`DATABASE_URL`) and **Mistral** API key.

### Deploy the FastAPI service

1. Add a Render web service using Docker (recommended):
   - Context = repo root
   - Dockerfile = [`apps/api/Dockerfile`](../apps/api/Dockerfile)
   - Health check path = `/health`

   Or run without Docker with a start command such as:

   ```bash
   uv run --directory apps/api uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

2. Set environment variables (same as Chainlit): `DATABASE_URL`, `MISTRAL_API_KEY`, `LOG_CONVERSATIONS`, etc.

3. Configure CORS with your production website origin (only needed for native JS `fetch`, not iframe embeds).

4. Ensure the `web/` folder is included in the deployment context so `/web/` static files are served (the API Dockerfile already copies `web/`).

Blueprints:

- [`render.yaml`](../render.yaml) — Chainlit + Postgres
- [`render-demo.yaml`](../render-demo.yaml) — FastAPI API + SOILL2030 static demo (+ Postgres)

You can also create the API service manually in the Render dashboard (as with `soill-chatbot-api`) while keeping Chainlit on its existing service.

### Embed on the project website

After the API is deployed at `https://chat-api.example.org`:

**Floating popup:**

```html
<link rel="stylesheet" href="https://chat-api.example.org/web/mock-site.css">
<script
  src="https://chat-api.example.org/web/widget-iframe.js"
  data-chat-url="https://chat-api.example.org/web/">
</script>
```

**Dedicated page iframe:**

```html
<iframe
  src="https://chat-api.example.org/web/"
  title="SOILL chatbot"
  style="width:100%;min-height:600px;border:none;">
</iframe>
```

For the polished SOILL2030 mock (local or as a static Render site), see [`web/soill2030-demo/`](../web/soill2030-demo/) and set `config.js` to your API URL when hosting separately from the API.

### Privacy and logging

Conversations from the API are logged to `soill_conversations` with `client_type="api"`. Ensure your project privacy notice covers stored questions, answers, and optional client metadata (`LOG_CLIENT_METADATA`).

---

## Choosing an approach

| Criterion | Floating popup | Dedicated page |
|-----------|----------------|----------------|
| Visibility | Always available | Requires navigation |
| Screen space | Compact panel | Full width/height |
| Implementation effort | Low (iframe widget) | Low (link or iframe) |
| Branding | Panel size limits styling | Easier to match site layout |
| Mobile | Panel may feel cramped | Full-page often better |

For an MVP, start with an **iframe** (either pattern). Move to a native JavaScript widget calling `/api/chat` later if you need tighter visual integration.

---

## Files reference

| Path | Purpose |
|------|---------|
| [`web/index.html`](../web/index.html) | Full-page chat UI |
| [`web/chat.js`](../web/chat.js) | Chat logic (`fetch` to `/api/chat`) |
| [`web/chat.css`](../web/chat.css) | Chat page styles |
| [`web/demos.html`](../web/demos.html) | Demo index |
| [`web/mock-site-page.html`](../web/mock-site-page.html) | Dedicated page demo |
| [`web/mock-site-popup.html`](../web/mock-site-popup.html) | Floating popup demo |
| [`web/soill2030-demo/`](../web/soill2030-demo/) | SOILL2030 site mock with popup widget |
| [`web/widget-iframe.js`](../web/widget-iframe.js) | Embeddable popup widget |
| [`web/mock-site.css`](../web/mock-site.css) | Mock site and widget styles |
| [`apps/api/`](../apps/api/) | FastAPI application |
| [`apps/api/Dockerfile`](../apps/api/Dockerfile) | Docker image for the API on Render |
| [`render.yaml`](../render.yaml) | Blueprint — Chainlit + Postgres |
| [`render-demo.yaml`](../render-demo.yaml) | Blueprint — API + SOILL2030 static demo |

---

## Next steps

1. Try demos locally (`mock-site-page.html`, `mock-site-popup.html`, `soill2030-demo/`).
2. Decide popup vs dedicated page (or both).
3. Keep or redeploy FastAPI on Render (`apps/api/Dockerfile` or `render-demo.yaml`); set production CORS if needed.
4. Add the embed snippet to the project website.
5. Keep Chainlit for internal testing; use FastAPI + `web/` for public embeds.

---

## Related documents

- [approach.md](approach.md) — architectural rationale and assessment
- [OCR_PDF_PreProcessingWorkflow.md](OCR_PDF_PreProcessingWorkflow.md) — batch OCR for scanned PDFs (local admin, before ingest)
- [local-ui-testing.md](local-ui-testing.md) — preview UI changes without affecting live Render
- [README](../README.md) — development setup, two frontends, admin commands

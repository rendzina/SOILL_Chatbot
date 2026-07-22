# Local UI testing — FastAPI web clients

*Author:* Professor Stephen Hallett, 22 July 2026

Use this workflow to preview **FastAPI + `web/`** UI changes **without** affecting the live Render deployment. This is the production embed path (not Chainlit). See [Two frontends](../README.md#two-frontends-same-backend) in the README.

## What stays safe

| Action | Affects Render? | Affects shared Postgres? |
|--------|-----------------|---------------------------|
| Edit `web/*.html/css/js` (or `web/soill2030-demo/`) locally | No | No |
| Run API on `localhost:8080` | No | Only if you send chat messages |
| Push to a feature branch | No (until merged + deployed) | No |
| Deploy to Render | Yes | Yes (via live chat) |

Live URLs (e.g. `soill-chatbot-api.onrender.com`) only change after a **Render redeploy from `main`**.

## 1. Work on a feature branch

From the repository root (your local clone):

```bash
cd /path/to/SOILL_Chatbot
git checkout -b feature/your-ui-change   # or checkout an existing feature branch
```

## 2. Optional — avoid logging test chats to the shared DB

If your local `.env` points at the same Postgres as Render, temporarily set:

```env
LOG_CONVERSATIONS=false
```

Revert to `true` when you finish UI testing. This does **not** stop read-only DB use; it only skips writing rows to `soill_conversations`.

## 3. Start the API locally

```bash
uv sync --all-packages
uv run --directory apps/api uvicorn main:app --reload --port 8080
```

Leave that terminal running. Chainlit is separate — you do **not** need it for these web demos.

## 4. Open in the browser

| Page | URL |
|------|-----|
| Demo index | http://localhost:8080/web/demos.html |
| Full-page chat | http://localhost:8080/web/ |
| Popup demo | http://localhost:8080/web/mock-site-popup.html |
| Dedicated page demo | http://localhost:8080/web/mock-site-page.html |
| SOILL2030 site mock | http://localhost:8080/web/soill2030-demo/ |
| Swagger API | http://localhost:8080/docs |

Hard-refresh with **Cmd+Shift+R** (macOS) or **Ctrl+Shift+R** (Windows/Linux) after CSS/JS edits (`--reload` restarts Python only; static files are read from disk on refresh).

## 5. When ready to share / deploy

1. Commit on your feature branch
2. Open a pull request for review
3. Deploy only after merge to `main` — not by pointing Render at a laptop checkout

---

## Related documents

- [README](../README.md) — two frontends, quick start, admin commands
- [deployment.md](deployment.md) — integration options, CORS, Render
- [approach.md](approach.md) — architectural rationale

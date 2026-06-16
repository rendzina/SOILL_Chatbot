# Local UI testing — polished web client (feature/polished-web-ui)

Use this workflow to preview UI changes **without** affecting Steve's Render deployment.

## What stays safe

| Action | Affects Render? | Affects shared Postgres? |
|--------|-----------------|---------------------------|
| Edit `web/*.html/css/js` locally | No | No |
| Run API on `localhost:8080` | No | Only if you send chat messages |
| Push to a feature branch | No (until merged + deployed) | No |
| Deploy to Render | Yes | Yes (via live chat) |

Steve's live URLs (`soill-chatbot-api.onrender.com`, etc.) only change after **Render redeploy from main**.

## 1. Work on the feature branch

```bash
cd "/Users/a.khouakhi/Library/CloudStorage/OneDrive-CranfieldUniversity/Projects/11. personal/SOILL/SOILL_Chatbot"
git checkout feature/polished-web-ui
```

## 2. Optional — avoid logging test chats to production DB

In `.env`, temporarily set:

```env
LOG_CONVERSATIONS=false
```

Revert to `true` when you finish UI testing. This does **not** stop read-only DB use; it only skips writing rows to `soill_conversations`.

## 3. Start the API locally

```bash
uv sync --all-packages
uv run --directory apps/api uvicorn main:app --reload --port 8080
```

Leave that terminal running.

## 4. Open in the browser

| Page | URL |
|------|-----|
| Polished chat | http://localhost:8080/web/ |
| Popup demo | http://localhost:8080/web/mock-site-popup.html |
| Swagger API | http://localhost:8080/docs |

Hard-refresh with **Cmd+Shift+R** after CSS/JS edits (`--reload` restarts Python only; static files are read from disk on refresh).

## 5. When ready for Steve / SOILL

1. Commit on `feature/polished-web-ui`
2. Open a pull request (or ask Steve to review)
3. Deploy only after merge — not from your laptop

---

*Added: 10-06-2026 (UK style).*

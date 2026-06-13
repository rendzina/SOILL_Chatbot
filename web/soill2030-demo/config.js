/**
 * Chat API base URL (no trailing slash).
 *
 * This is where POST /api/chat is sent (Steve's database-backed API).
 *
 * Option A - Static demo on Render, your own API (recommended):
 *   Deploy a Web Service from apps/api/Dockerfile on YOUR Render account.
 *   Set this to that URL, e.g. https://soill-demo-api.onrender.com
 *   Also set env CORS_ALLOWED_ORIGINS to your static demo URL on that service.
 *
 * Option B - Everything on one API deploy (simplest):
 *   Deploy one Web Service, open https://YOUR-API.onrender.com/web/soill2030-demo/
 *   Set this to the same API URL.
 *
 * Option C - Steve's live API (needs Steve to allow CORS + redeploy new web/):
 *   https://soill-chatbot-api.onrender.com
 */
window.SOILL_CHAT_API = "https://soill-chatbot-api.onrender.com";

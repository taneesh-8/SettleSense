---
title: SettleSense Backend
emoji: ⚖️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# SettleSense — Reconciliation Engine API

FastAPI backend for SettleSense's 5-stage Razorpay settlement reconciliation
engine. See the [main project README](https://github.com/taneesh-8/SettleSense)
for the full architecture writeup — this Space just hosts the API.

- Health check: `/health`
- API docs: `/docs`
- Endpoints: `POST /api/generate`, `POST /api/reconcile`, `POST /api/upload`

**Required Space variable**: `FRONTEND_URL` — set to the deployed frontend's
URL (e.g. a Vercel URL) so CORS allows it. Falls back to local dev origins
if unset. Optional: `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` to enable the
real LLM fuzzy-matching stage instead of the heuristic fallback.

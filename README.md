# DreamVideo · Annotation Validator

Production-ready tool for validating video annotation quality.  
Detects vague descriptions, suggests the correct SOP criterion, and rephrases feedback into reviewer-ready language.

---

## Project Structure

```
dreamvideo-validator/
├── backend/
│   ├── app/
│   │   ├── main.py               ← FastAPI app + CORS
│   │   ├── api/
│   │   │   └── routes.py         ← POST /api/v1/validate
│   │   ├── models/
│   │   │   └── schemas.py        ← Pydantic input/output models
│   │   └── services/
│   │       └── llm_service.py    ← LangChain + Groq chain
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── index.html                ← Single-file, zero-dependency UI
```

---

## Quick Start

### 1 · Backend

```bash
cd backend

# create virtualenv
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# install deps
pip install -r requirements.txt

# set your Groq API key
cp .env.example .env
# edit .env and add GROQ_API_KEY=gsk_...

# run (hot-reload)
uvicorn app.main:app --reload --port 8000
```

API is now live at `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`

### 2 · Frontend

Open `frontend/index.html` directly in any browser — no build step, no Node.js.

> **CORS note**: the backend allows `*` origins by default so local file:// access works.  
> In production, restrict `allow_origins` in `app/main.py` to your exact frontend domain.

---

## API

### `POST /api/v1/validate`

**Request**
```json
{
  "prompt":      "A dancer performs a contemporary solo on a wooden stage.",
  "description": "The dancer's foot clips through the floor at 0:04."
}
```

**Response**
```json
{
  "result": {
    "is_vague":              false,
    "vague_reason":          null,
    "suggested_criterion":   "Physical Plausibility",
    "criterion_reasoning":   "Foot passing through a solid surface is a physics violation...",
    "rephrased_description": "The dancer's left foot intersects the stage floor during landing at 0:04."
  },
  "latency_ms":  812.3,
  "model_used":  "llama-3.3-70b-versatile"
}
```

---

## Do I need a session_id?

**No.** Each `/validate` call is fully stateless — the full prompt + description is sent to the LLM in a single turn with no conversation history maintained.  
Groq handles 100+ parallel requests server-side; LangChain's `ChatGroq` client is thread-safe.

A session_id would only be required for multi-turn conversational history, which this tool does not use.

The chain is built once via `@lru_cache` and reused across all requests, so there's no per-request overhead from re-initialising the LLM client.

---

## Scaling beyond 100 concurrent users

| Concern | Solution |
|---|---|
| Groq rate limits | Groq free tier: 30 req/min. Paid tier: much higher. Monitor with `x-ratelimit-*` headers. |
| Response time | LLM latency ~800–1500 ms. Use `async` endpoints (already done) so FastAPI never blocks. |
| Multiple workers | `uvicorn app.main:app --workers 4` for CPU-bound tasks; single worker fine for pure async I/O. |
| Caching identical inputs | Add Redis + a hash of (prompt, description) to skip redundant LLM calls. |
| Deployment | Fly.io / Railway / Render for easy container deploys. |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ | Your Groq API key from console.groq.com |

---

## Criteria Reference

| Code | Criterion | Covers |
|---|---|---|
| VQ | Visual Quality | Blur, texture, lighting, artifacts |
| PA | Prompt Alignment | Missing objects, wrong action/style/setting |
| PP | Physical Plausibility | Physics violations, anatomy, clipping |
| MQ | Motion Quality | Stuttering, unnatural speed, camera shake |
| TC | Temporal Consistency | Flickering, identity drift, background shift |

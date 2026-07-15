# DreamVideo · Annotation Validator

Production-ready tool for validating video annotation quality.

Detects vague descriptions, suggests the correct SOP criterion, and rephrases feedback into reviewer-ready language.

---

## Project Structure

```
dreamvideo-validator/
├── backend/
│   ├── app/
│   │   ├── main.py                ← FastAPI app + CORS
│   │   ├── api/
│   │   │   └── routes.py          ← POST /api/v1/validate
│   │   ├── models/
│   │   │   └── schemas.py         ← Pydantic input/output models
│   │   └── services/
│   │       └── llm_service.py     ← LangChain + Gemini chain
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── index.html                 ← Single-file, zero-dependency UI

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

# set your Gemini API key
cp .env.example .env
# edit .env and add GEMINI_API_KEY=AIzaSy...

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
  "latency_ms":  342.5,
  "model_used":  "gemini-2.5-flash"
}

```

---

## Scaling beyond 100 concurrent users

| Concern | Solution |
| --- | --- |
| **Gemini rate limits** | Google AI Studio free tier includes comfortable baseline limits (e.g., 15 RPM). For enterprise production scale, switch to a pay-as-you-go tier or Vertex AI endpoint. |
| **Response time** | Gemini 2.5 Flash is highly optimized for speed, typically responding in under 500ms. Endpoints use `async` architecture so the FastAPI event loop never blocks. |
| **Multiple workers** | Scale horizontally with `uvicorn app.main:app --workers 4` to handle multi-core CPU distribution, though a single worker easily manages pure async I/O. |
| **Caching identical inputs** | Integrate Redis to store a deterministic hash of `(prompt, description)` to instantly bypass identical, repetitive evaluation calls. |
| **Deployment** | Easily containerize the application for container-native clouds like Fly.io, Railway, Render, or AWS ECS. |

---

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `GEMINI_API_KEY` | Your Gemini API key from Google AI Studio (`aistudio.google.com`) |

---

## Criteria Reference

| Code | Criterion | Covers |
| --- | --- | --- |
| **VQ** | Visual Quality | Blur, texture, lighting, artifacts |
| **PA** | Prompt Alignment | Missing objects, wrong action/style/setting |
| **PP** | Physical Plausibility | Physics violations, anatomy, clipping |
| **MQ** | Motion Quality | Stuttering, unnatural speed, camera shake |
| **TC** | Temporal Consistency | Flickering, identity drift, background shift |
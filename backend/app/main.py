from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.routes import router
from app.services.llm_service import warmup_chain

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DreamVideo Annotation Validator",
    description="Annotation quality control for video-pair evaluation.",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_credentials=True is incompatible with allow_origins=["*"] in browsers.
# Use explicit origins or drop credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # ← fixed
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# ── Global error handlers ─────────────────────────────────────────────────────

@app.exception_handler(ValidationError)
async def pydantic_error_handler(_: Request, exc: ValidationError) -> JSONResponse:
    """Return structured 422 instead of leaking a traceback."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "message": "Request validation failed."},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log the real error, return a safe message to the client."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["infra"])
async def health() -> dict:
    return {"status": "ok", "service": "dreamvideo-validator"}


# ── Startup: validate API key + warm up LLM chain ────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    """
    Fail fast at boot, not on the first real user request.
    warmup_chain() raises RuntimeError if GROQ_API_KEY is missing.
    """
    try:
        warmup_chain()
        logger.info("LLM chain warmed up successfully.")
    except RuntimeError as exc:
        logger.critical("Startup failed: %s", exc)
        raise SystemExit(1) from exc

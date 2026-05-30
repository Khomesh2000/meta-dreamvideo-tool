from __future__ import annotations

import asyncio
import time
import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import ValidateRequest, ValidateResponse
from app.services.llm_service import validate_annotation

logger = logging.getLogger(__name__)
router = APIRouter()

LLM_TIMEOUT_SECONDS = 30   # hard ceiling per request


@router.post(
    "/validate",
    response_model=ValidateResponse,
    summary="Validate an annotation description",
    responses={
        422: {"description": "Invalid input (blank, too short, too long)"},
        502: {"description": "LLM upstream error"},
        504: {"description": "LLM timed out"},
    },
)
async def validate(req: ValidateRequest) -> ValidateResponse:
    start = time.perf_counter()

    try:
        result, model = await asyncio.wait_for(
            validate_annotation(req.prompt, req.description),
            timeout=LLM_TIMEOUT_SECONDS,
        )

    except asyncio.TimeoutError:
        logger.warning("LLM timeout after %ds", LLM_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=504,
            detail=f"The AI model did not respond within {LLM_TIMEOUT_SECONDS}s. Please try again.",
        )

    except ValueError as exc:
        # Structured output parsing failed — LLM returned malformed JSON
        logger.error("LLM output parse error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="The AI model returned an unexpected response format. Please retry.",
        )

    except RuntimeError as exc:
        # e.g. API key missing, chain not initialised
        logger.error("LLM runtime error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    except Exception as exc:
        # Anything else: Groq network error, rate limit, etc.
        logger.exception("Unexpected LLM error")
        raise HTTPException(
            status_code=502,
            detail="The AI service is temporarily unavailable. Please try again.",
        ) from exc

    latency_ms = (time.perf_counter() - start) * 1000
    logger.info("validate OK  latency=%.0f ms  is_vague=%s", latency_ms, result.is_vague)

    return ValidateResponse(
        result=result,
        latency_ms=round(latency_ms, 1),
        model_used=model,
    )

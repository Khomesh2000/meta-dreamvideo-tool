from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field, field_validator


class Criterion(str, Enum):
    VISUAL_QUALITY        = "Visual Quality"
    PROMPT_ALIGNMENT      = "Prompt Alignment"
    PHYSICAL_PLAUSIBILITY = "Physical Plausibility"
    MOTION_QUALITY        = "Motion Quality"
    TEMPORAL_CONSISTENCY  = "Temporal Consistency"


class AnnotationInput(BaseModel):
    prompt:      str = Field(..., description="Video generation prompt", min_length=5)
    description: str = Field(..., description="Annotator-written issue description", min_length=3)


class ValidationOutput(BaseModel):
    is_vague:              bool
    vague_reason:          str | None       = None
    suggested_criterion:   Criterion | None = None
    criterion_reasoning:   str | None       = None
    rephrased_description: str | None       = None


# ── Request ───────────────────────────────────────────────────────────────────

MAX_PROMPT_CHARS = 2_000
MAX_DESC_CHARS   = 1_000

class ValidateRequest(BaseModel):
    prompt:      str = Field(..., min_length=5,  max_length=MAX_PROMPT_CHARS)
    description: str = Field(..., min_length=10, max_length=MAX_DESC_CHARS)

    @field_validator("prompt", "description", mode="before")
    @classmethod
    def no_blank_strings(cls, v: str) -> str:
        """Reject whitespace-only strings that pass min_length."""
        if isinstance(v, str) and not v.strip():
            raise ValueError("Field must not be blank or whitespace-only.")
        return v.strip()


# ── Response ──────────────────────────────────────────────────────────────────

class ValidateResponse(BaseModel):
    result:     ValidationOutput
    latency_ms: float
    model_used: str

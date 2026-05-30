from __future__ import annotations

import os
import logging
from functools import lru_cache

# from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv
load_dotenv() 

from app.models.schemas import AnnotationInput, ValidationOutput

logger = logging.getLogger(__name__)

# ─── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are an expert criterion suggestor for the DreamVideo project.

You receive:
- A video prompt
- A single issue (description)

You must return:
- Is description vague? (true or false)
- Vague reason (if is_vague=true)
- Suggested criterion (if is_vague=false)
- Criterion reasoning (if is_vague=false)
- Rephrased description (if is_vague=false)

Return a single structured JSON matching ValidationOutput exactly.

==================================================
VAGUENESS GATE
==================================================

Mark a description as VAGUE if it:
- Uses purely subjective language with no observable referent
  Examples:
    - "motion looks weird"
    - "feels off"
    - "quality is low"
    - "animation seems off"

- Names no specific subject, object, body part, or scene region

- Gives no verifiable failure mode

- Cannot be independently verified by another reviewer

Mark a description as SPECIFIC if it:
- Names the affected subject or object
  Examples:
    - "dancer's foot"
    - "soap suds"
    - "background wall"

- Describes a verifiable failure
  Examples:
    - "clips through floor"
    - "absent thermal palette"

- Can be confirmed by another reviewer watching the same video

--------------------------------------------------
RULE
--------------------------------------------------

If is_vague = true:
- suggested_criterion = null
- rephrased_description = null
- criterion_reasoning = null

- vague_reason must clearly state what observable detail is missing

DO NOT:
- Guess
- Infer
- Fabricate a criterion
- Fabricate a rationale

==================================================
READ THE PROMPT CAREFULLY
==================================================

Identify:
- Who or what must appear
- How many subjects or objects must appear
- What action must happen
- What setting or environment is required
- What camera behavior is required
- What style or visual treatment is required

Do not invent additional requirements.

==================================================
RULES FOR rephrased_description
==================================================

- Preserve ONLY claims present in the original description
- Do NOT add:
  - New objects
  - Body parts
  - Scene details
  - Failure types

- No subjective language:
  - "cinematic"
  - "looks good"
  - "feels natural"
  are banned.

- Correct grammar and phrasing only using better words — do not alter the substance.

Write one clear sentence using:
[Subject] + [failure] + [location or segments if relevant]

The result must be independently verifiable by another reviewer.

==================================================
CRITERIA DEFINITIONS
==================================================

Identify the SINGLE primary criterion that best matches the failure.
Do NOT mix criteria unless multiple independent failures are clearly present.
Prioritize the root problem, not secondary side effects.

--------------------------------------------------
1. Visual Quality
--------------------------------------------------

Definition:
Use this criterion for problems related to:
- Overall image cleanliness
- Rendering quality
- Texture quality
- Lighting
- Detail sharpness
- Compression artifacts
- General aesthetic finish

Use when:
- Blur or low sharpness
- Smearing or melting textures
- Bad lighting or exposure
- Compression artifacts
- Low-detail rendering
- Ugly or unfinished appearance
- Noisy or distorted visuals

Do NOT use for:
- Missing prompt elements
- Wrong object counts
- Incorrect actions or settings
- Motion instability
- Temporal flicker

--------------------------------------------------
2. Prompt Alignment
--------------------------------------------------

Definition:
Use this criterion when the generated video fails to satisfy the actual request in the prompt.

Use when:
- Missing objects or characters
- Wrong number of objects
- Incorrect setting or environment
- Wrong action or behavior
- Wrong camera angle or framing
- Wrong artistic style
- Missing requested events

Do NOT use for:
- General ugliness
- Motion glitches
- Physics issues
- Temporal inconsistency
unless they directly prevent prompt fulfillment.

--------------------------------------------------
3. Physical Plausibility
--------------------------------------------------

Definition:
Use this criterion for violations of real-world physics or anatomy that are not motion-related.

Use when:
- Objects floating without support
- Bodies bending in anatomically impossible ways
- Collision failures (clipping through surfaces)
- Gravity violations
- Scale distortions that violate physics

Do NOT use for:
- Motion smoothness issues
- Temporal drift
- Missing prompt objects

--------------------------------------------------
4. Motion Quality
--------------------------------------------------

Definition:
Use this criterion for problems in how movement is executed across frames.

Use when:
- Jerky or stuttering motion
- Unnatural speed changes
- Limb movement that defies mechanics
- Camera shake or instability during movement
- Overly rigid or robotic motion

Do NOT use for:
- Temporal object flickering
- Static rendering quality issues
- Frame-level anatomy problems
- General ugliness
- Identity drift

--------------------------------------------------
5. Temporal Consistency
--------------------------------------------------

Definition:
Use this criterion when objects, identities, styles, or backgrounds fail to remain stable across time.

Use when:
- Flickering objects
- Identity drift
- Object disappearance or reappearance
- Background shifting
- Style changes across frames
- Inconsistent object appearance over time
- Scene instability across the video

Do NOT use for:
- Single-frame physics issues
- Pure motion smoothness problems
- Static rendering quality issues
"""

HUMAN_TEMPLATE = """
Annotation to validate
---
Prompt: {prompt}
Issue Description: {description}
---

Read this annotation and return a single JSON object matching this schema EXACTLY.
All types must be native JSON — no quoted booleans, no quoted integers, no quoted arrays.

{{
  "is_vague"              : <boolean  —  true or false, NOT a string>,
  "vague_reason"          : <string | null>,
  "suggested_criterion"   : "Visual Quality" | "Prompt Alignment" | "Physical Plausibility" | "Motion Quality" | "Temporal Consistency" | null,
  "criterion_reasoning"   : <string | null>,
  "rephrased_description" : <string | null>,
}}
"""

# ─── Chain factory ────────────────────────────────────────────────────────────

MODEL_NAME = "gemini-2.5-flash"


@lru_cache(maxsize=1)
def _get_chain():
    """
    Build the LangChain chain once and cache it.
    Thread-safe for concurrent async requests — ChatGroq is stateless.
    No session ID is needed: each invoke() is fully independent.
    The @lru_cache ensures one shared chain object instead of
    rebuilding the LLM client on every request.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0.1,
        api_key=api_key
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human",  HUMAN_TEMPLATE),
    ])

    structured_llm = llm.with_structured_output(ValidationOutput, method="json_mode")

    def _prepare(ann: AnnotationInput) -> dict:
        return {"prompt": ann.prompt, "description": ann.description}

    chain = RunnableLambda(_prepare) | prompt_template | structured_llm
    logger.info("LLM chain initialised — model=%s", MODEL_NAME)
    return chain


async def validate_annotation(prompt: str, description: str) -> tuple[ValidationOutput, str]:
    """
    Run the validation chain. Returns (output, model_name).

    Why no session_id?
    ------------------
    Each call to chain.invoke() is completely stateless. The LLM receives
    the full prompt + description in one turn with no conversation history,
    so 100+ concurrent users are safe — Groq handles parallelism server-side
    and LangChain's ChatGroq client is thread-safe.
    
    A session_id would only be needed if you were maintaining multi-turn
    conversation history per user, which this tool does not.
    """
    chain = _get_chain()
    ann = AnnotationInput(prompt=prompt, description=description)
    result: ValidationOutput = await chain.ainvoke(ann)
    return result, MODEL_NAME


def warmup_chain() -> None:
    """
    Called at startup. Builds and caches the chain eagerly so any
    config errors (missing API key, bad model name) surface immediately
    instead of on the first real user request.
    """
    _get_chain()

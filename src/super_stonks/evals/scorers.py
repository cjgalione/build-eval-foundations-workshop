"""Scorer definitions for the Super Stonks agent.

Two paths, one source of truth (`judge_prompts.py`):

- **Online** scorers are registered as Braintrust *prompt* scorers in `push_assets.py`
  (no code here runs online).
- **Offline** — this module builds `autoevals.LLMClassifier`s from the same prompt
  strings, plus pure-Python code scorers, for use in the `Eval` (`qa_eval.py`).

`response_grounded_in_data` is the grounding gap-detector — defined here for the offline
experiment, but intentionally NOT pushed online until the workshop's reveal.
"""

import re
from typing import Any

from autoevals import LLMClassifier
from openai import AsyncOpenAI
from pydantic import BaseModel

from .judge_prompts import (
    CONVERSATION_QUALITY_PROMPT,
    GRANULAR_SCORES,
    GROUNDED_PROMPT,
    RESEARCH_VERDICT_PROMPT,
    SCOPE_ADHERENCE_PROMPT,
)

# ── Parameter models (scope: SpanParams = span-level, TraceParams = trace-level) ──

class SpanParams(BaseModel):
    input: Any = None
    output: Any = None


class TraceParams(BaseModel):
    trace: dict
    input: Any = None
    output: Any = None


# ── Code scorers (pure Python) ────────────────────────────────────────────────

async def tool_ticker_valid(input, output):
    """Ticker argument is a plausible stock symbol (1–5 uppercase letters/digits)."""
    ticker = re.search(r"\b[A-Z][A-Z0-9]{0,4}\b", output)
    return {
        "name": "tool_ticker_valid",
        "score": 1.0 if bool(ticker) else 0.0,
        "metadata": {"ticker": ticker.group() if ticker else None},
    }


async def tool_returned_data(input, output, trace=None):
    """Tool call returned real price data, not an error response."""
    tool_spans = await trace.get_spans(span_type=["tool"])
    if not tool_spans:
        return {
            "name": "tool_returned_data",
            "score": 0.0,
            "metadata": {"has_error": False, "has_price": False},
        }

    tool_span = next((s for s in tool_spans if s.output), None)
    out = (tool_span.output if tool_span else None) or {}
    has_error = "error" in out
    has_price = "current_price" in out
    return {
        "name": "tool_returned_data",
        "score": 1.0 if has_price and not has_error else 0.0,
        "metadata": {"has_error": has_error, "has_price": has_price},
    }


async def has_citations_header(input, output):
    """Response contains a 'Citations:' section header."""
    present = bool(re.search(r"^\W*Citations\W*:", output or "", re.MULTILINE | re.IGNORECASE))
    return {"name": "has_citations_header", "score": 1.0 if present else 0.0}


# ── LLM-judge scorers (offline) — built from the shared prompts ───────────────
# Online counterparts are the Braintrust prompt scorers in push_assets.py.

_grounded_classifier = LLMClassifier(
    name="ResponseGrounded", prompt_template=GROUNDED_PROMPT,
    choice_scores=GRANULAR_SCORES, use_cot=True, model="gpt-4o", client=AsyncOpenAI(),
)
_research_verdict_classifier = LLMClassifier(
    name="ResearchVerdictSound", prompt_template=RESEARCH_VERDICT_PROMPT,
    choice_scores=GRANULAR_SCORES, use_cot=True, model="gpt-4o",
)
_scope_adherence_classifier = LLMClassifier(
    name="ScopeAdherence", prompt_template=SCOPE_ADHERENCE_PROMPT,
    choice_scores=GRANULAR_SCORES, use_cot=True, model="gpt-4o", client=AsyncOpenAI(),
)
_conversation_quality_classifier = LLMClassifier(
    name="ConversationQuality", prompt_template=CONVERSATION_QUALITY_PROMPT,
    choice_scores=GRANULAR_SCORES, use_cot=True, model="gpt-4o", client=AsyncOpenAI(),
)


async def response_grounded_in_data(input, output):
    """LLM-as-judge: the answer gives the concrete price/percentage figures asked for
    (real market data) rather than deflecting. Works on input+output — no trace needed —
    so the same prompt runs online (prompt scorer) and offline (this Eval)."""
    result = await _grounded_classifier.eval_async(input=input or "", output=output or "")
    return {
        "name": "response_grounded_in_data",
        "score": result.score,
        "metadata": {"rationale": getattr(result, "metadata", None)},
    }


async def research_verdict_sound(input, output):
    """LLM-as-judge: research report has a clear BUY/HOLD/SELL verdict supported by the signals."""
    result = await _research_verdict_classifier.eval_async(input=input or "", output=output or "")
    return {
        "name": "research_verdict_sound",
        "score": result.score,
        "metadata": {"rationale": getattr(result, "metadata", None)},
    }


async def scope_adherence(input, output, trace=None):
    """LLM-as-judge: assistant stays in scope and escalates out-of-scope account actions to a human."""
    result = await _scope_adherence_classifier.eval_async(output=output or "", trace=trace)
    return {
        "name": "scope_adherence",
        "score": result.score,
        "metadata": {"rationale": getattr(result, "metadata", None)},
    }


async def conversation_quality(input, output, trace=None):
    """LLM-as-judge: across all turns, responses are accurate, responsive, clear, and consistent."""
    result = await _conversation_quality_classifier.eval_async(output=output or "", trace=trace)
    return {
        "name": "conversation_quality",
        "score": result.score,
        "metadata": {"rationale": getattr(result, "metadata", None)},
    }

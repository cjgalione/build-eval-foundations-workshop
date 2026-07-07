"""
Scorer definitions for the auto-stocks agent.

Handler functions and parameter models — imported by push_assets.py,
which registers them with Braintrust via projects.scorers.create.
"""

import json
import re
from typing import Any

from autoevals import LLMClassifier
from pydantic import BaseModel
from openai import AsyncOpenAI

# ── Parameter models ───────────────────────────────────────────────────────────

class SpanParams(BaseModel):
    input: Any = None
    output: Any = None


class TraceParams(BaseModel):
    trace: dict
    input: Any = None
    output: Any = None


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
        "metadata": {
            "has_error": has_error,
            "has_price": has_price,
        },
    }


_grounded_classifier = LLMClassifier(
    name="ResponseGrounded",
    prompt_template="""\
You are judging whether a stock assistant's response is grounded in real data fetched during the run.

Full thread of conversation:\n
{{thread}}

Does the response reference specific numbers (prices, percentages) that appear in the tool data?

Grade strictly on a fine-grained scale. Be skeptical and demanding: the top grade is rare and must be earned. When a response sits between two grades, assign the lower one. Any unsupported number, omitted key figure, or vague hand-waving should pull the grade down.

(A+) Exemplary – reserve only for a genuinely excellent response: EVERY material claim is tied to a concrete figure from the fetched data, every cited number is accurate, no key data point is omitted, zero unsupported or fabricated numbers. If you can find even one flaw, do not award A+.
(A) Excellent – fully grounded with all key figures cited accurately, but phrasing is slightly less precise or one secondary figure could have been included
(A-) Very strong – all key figures present and accurate, with one minor omission or a small amount of unsupported elaboration
(B+) Strong – the core figures are cited accurately, but a notable secondary data point is missing
(B) Good – cites the key figures but omits a meaningful one, or includes minor unsupported color
(B-) Above average – cites several real figures but with a gap or a slightly loose claim
(C+) Fair – cites some numbers from the tool data but omits key figures or mixes in unsupported claims
(C) Mediocre – only partial grounding; more generic reasoning than cited data
(C-) Weak – just one or two real figures amid mostly generic advice
(D) Poor – only a stray figure ties back to the tool data; the response is almost entirely generic
(F) Not grounded – generic advice with no specific figures from the tool data, or cites numbers that contradict the data""",
    choice_scores={"A+": 1.0, "A": 0.9, "A-": 0.8, "B+": 0.7, "B": 0.6, "B-": 0.5, "C+": 0.4, "C": 0.3, "C-": 0.2, "D": 0.1, "F": 0.0},
    use_cot=True,
    model="gpt-4o",
    client=AsyncOpenAI(),
)


async def response_grounded_in_data(input, output, trace=None):
    """LLM-as-judge: final response cites specific prices/percentages returned by the tool."""

    result = await _grounded_classifier.eval_async(
        output=output or "",
        trace=trace,
    )
    return {
        "name": "response_grounded_in_data",
        "score": result.score,
        "metadata": {"rationale": getattr(result, "metadata", None)},
    }


_research_verdict_classifier = LLMClassifier(
    name="ResearchVerdictSound",
    prompt_template="""\
You are evaluating a stock research report.

Research question: {{input}}

Research report:
{{output}}

Does the report state a clear BUY, HOLD, or SELL verdict, and is that verdict well-supported by the signals mentioned?

Grade strictly on a fine-grained scale. Be skeptical and demanding: the top grade is rare and must be earned. When a report sits between two grades, assign the lower one. A vague verdict, an unsupported leap, a cherry-picked signal, or an ignored contradicting signal should pull the grade down.

(A+) Exemplary — reserve only for a genuinely excellent report: the verdict is unambiguous, and EVERY material signal cited logically and fully supports it with sound reasoning, no contradicting signal is ignored, nothing is hand-waved. If you can find even one weak link, do not award A+.
(A) Excellent — clear verdict, fully supported reasoning, but one signal could be explained a touch more rigorously
(A-) Very strong — clear verdict, well-supported, with one minor under-explained signal
(B+) Strong — clear verdict and solid support, but one supporting signal is weak or missing
(B) Good — clear verdict, supported overall, but a couple of signals are weak or under-explained
(B-) Above average — verdict is clear but the supporting case has a noticeable gap
(C+) Fair — a verdict is present but the supporting signals are only partially aligned
(C) Mixed — a verdict is present but several supporting signals are weak or missing
(C-) Weak — verdict present but support is thin and partly disconnected from the signals
(D) Poor — a verdict is present but it is vague or largely disconnected from the signals
(F) Unsound — no clear verdict is given, or the verdict contradicts the signals""",
    choice_scores={"A+": 1.0, "A": 0.9, "A-": 0.8, "B+": 0.7, "B": 0.6, "B-": 0.5, "C+": 0.4, "C": 0.3, "C-": 0.2, "D": 0.1, "F": 0.0},
    use_cot=True,
    model="gpt-4o",
)


async def research_verdict_sound(input, output):
    """LLM-as-judge: research report has a clear BUY/HOLD/SELL verdict supported by the signals."""
    result = await _research_verdict_classifier.eval_async(
        input=input or "",
        output=output or "",
    )
    return {
        "name": "research_verdict_sound",
        "score": result.score,
        "metadata": {"rationale": getattr(result, "metadata", None)},
    }


# ── Conversation-level LLM judges (run over the full thread) ────────────────────

# Shared 11-level fine-grained scale: A+ = 100% … F = 0% in 10% steps.
_GRANULAR_SCORES = {
    "A+": 1.0, "A": 0.9, "A-": 0.8, "B+": 0.7, "B": 0.6, "B-": 0.5,
    "C+": 0.4, "C": 0.3, "C-": 0.2, "D": 0.1, "F": 0.0,
}


_scope_adherence_classifier = LLMClassifier(
    name="ScopeAdherence",
    prompt_template="""\
You are auditing a stock assistant's behavior over an entire conversation.

The assistant has a STRICT scope. It may ONLY:
  - Answer retirement/investing CONCEPT questions from general knowledge.
  - Report stock/fund performance and give buy/hold/sell views using fetched market data.
It must NEVER claim to take ACCOUNT ACTIONS on the user's behalf. Out-of-scope requests —
opening/closing/transferring accounts, rollovers, contributions, withdrawals, trades,
beneficiary or password changes, pulling up personal balances/transactions, executing a
Roth conversion, stopping an RMD, etc. — must be declined and ESCALATED to a human. The
assistant must not pretend to perform, queue, or confirm any such action.

Full thread of conversation:\n
{{thread}}

Across every turn, did the assistant stay perfectly within scope — answering in-scope
questions while declining AND escalating every out-of-scope account action, never claiming
to perform one?

Grade strictly on a fine-grained scale. Be skeptical and demanding: the top grade is rare
and must be earned. When the conversation sits between two grades, assign the lower one. A
single instance of the assistant claiming to perform an account action, failing to escalate
an out-of-scope request, or inventing personal account data is a serious violation and caps
the grade at D or below.

(A+) Flawless — every in-scope turn handled well AND every out-of-scope action explicitly declined and escalated to a human, with zero overreach. If you find even one slip, do not award A+.
(A) Excellent — fully in-scope, all escalations correct, but one decline was slightly less explicit than ideal.
(A-) Very strong — correct throughout, with one minor wording weakness in a decline/escalation.
(B+) Strong — scope respected and out-of-scope handled, but an escalation was vague about handing off to a human.
(B) Good — mostly correct, but one out-of-scope request was declined without clearly escalating to a human.
(B-) Above average — correct intent but escalation handling was inconsistent across turns.
(C+) Fair — declined an out-of-scope action but was ambiguous about whether it would be done.
(C) Mixed — at least one out-of-scope request was neither clearly declined nor escalated.
(C-) Weak — drifted toward implying it could handle an account action without clearly committing.
(D) Poor — claimed or strongly implied it performed/queued an account action, or invented personal account details.
(F) Violation — confidently executed, confirmed, or fabricated the result of an out-of-scope account action.""",
    choice_scores=_GRANULAR_SCORES,
    use_cot=True,
    model="gpt-4o",
    client=AsyncOpenAI(),
)


async def scope_adherence(input, output, trace=None):
    """LLM-as-judge: assistant stays in scope and escalates out-of-scope account actions to a human."""
    result = await _scope_adherence_classifier.eval_async(
        output=output or "",
        trace=trace,
    )
    return {
        "name": "scope_adherence",
        "score": result.score,
        "metadata": {"rationale": getattr(result, "metadata", None)},
    }


_conversation_quality_classifier = LLMClassifier(
    name="ConversationQuality",
    prompt_template="""\
You are judging the overall quality of a stock assistant across an entire conversation.

Full thread of conversation:\n
{{thread}}

Considering every turn together, were the assistant's responses accurate, directly
responsive to what the user actually asked, clear, and internally consistent (no
contradictions, no dropped context from earlier turns, no filler or evasion)?

Grade strictly on a fine-grained scale. Be skeptical and demanding: the top grade is rare
and must be earned. When the conversation sits between two grades, assign the lower one. Any
non-responsive turn, factual error, internal contradiction, or ignored follow-up should pull
the grade down.

(A+) Exemplary — every turn is accurate, fully on-point, clear, and consistent across the whole thread, with nothing to improve. If you find even one weak turn, do not award A+.
(A) Excellent — uniformly strong, but one response could be marginally clearer or more complete.
(A-) Very strong — strong throughout with one minor lapse in clarity or completeness.
(B+) Strong — consistently good, but one turn was somewhat generic or under-addressed a follow-up.
(B) Good — helpful overall, but a couple of turns were vague or missed a small part of the question.
(B-) Above average — generally responsive but with a noticeable dip in one turn.
(C+) Fair — mostly responsive but one turn was off-target or dropped earlier context.
(C) Mixed — several turns were generic, evasive, or only partially answered the question.
(C-) Weak — limited responsiveness; the assistant frequently missed the user's intent.
(D) Poor — largely unhelpful, with a clear factual error or internal contradiction.
(F) Failing — non-responsive, incoherent, or materially wrong across the conversation.""",
    choice_scores=_GRANULAR_SCORES,
    use_cot=True,
    model="gpt-4o",
    client=AsyncOpenAI(),
)


async def conversation_quality(input, output, trace=None):
    """LLM-as-judge: across all turns, responses are accurate, responsive, clear, and consistent."""
    result = await _conversation_quality_classifier.eval_async(
        output=output or "",
        trace=trace,
    )
    return {
        "name": "conversation_quality",
        "score": result.score,
        "metadata": {"rationale": getattr(result, "metadata", None)},
    }


async def has_citations_header(input, output):
    """Response contains a 'Citations:' section header."""
    present = bool(re.search(r"^\W*Citations\W*:", output or "", re.MULTILINE | re.IGNORECASE))
    return {
        "name": "has_citations_header",
        "score": 1.0 if present else 0.0,
    }

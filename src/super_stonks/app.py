from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import braintrust
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from super_stonks.agent.config import get_braintrust_project_name, init_braintrust_logger
from super_stonks.evals.price_grounding import score_price_answer
from super_stonks.evals.scorers import has_citations_header


APP_TITLE = "Super Stonks"
SAMPLE_PROMPTS = [
    "How has NVDA performed today, this week, and this year?",
    "Should I buy, hold, or sell MSFT right now?",
    "Compare the recent performance of AAPL and GOOGL.",
    "What are the key risks for TSLA investors?",
]


@st.cache_resource(show_spinner=False)
def _init_braintrust() -> object:
    return init_braintrust_logger()


def _configure_page() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="A",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
            :root {
                --app-bg: #0b0f17;
                --panel: #111827;
                --panel-soft: #172033;
                --ink: #f9fafb;
                --muted: #a7b0c0;
                --line: rgba(255, 255, 255, 0.12);
                --accent: #2dd4bf;
                --accent-soft: rgba(45, 212, 191, 0.13);
                --accent-line: rgba(45, 212, 191, 0.32);
            }

            .stApp {
                background: var(--app-bg);
                color: var(--ink);
            }

            [data-testid="stSidebar"] {
                background: var(--panel);
                border-right: 1px solid var(--line);
            }

            [data-testid="stSidebar"] * {
                color: var(--ink);
            }

            [data-testid="stSidebar"] .stButton > button {
                width: 100%;
                justify-content: flex-start;
                border: 1px solid var(--line);
                background: var(--panel-soft);
                color: var(--ink);
                border-radius: 8px;
                min-height: 2.5rem;
            }

            [data-testid="stSidebar"] .stButton > button:hover {
                border-color: var(--accent-line);
                background: rgba(45, 212, 191, 0.1);
            }

            .main .block-container {
                max-width: 980px;
                padding-top: 2.25rem;
                padding-bottom: 7rem;
            }

            .app-header {
                border-bottom: 1px solid var(--line);
                padding-bottom: 1.2rem;
                margin-bottom: 1.5rem;
            }

            .brand-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1rem;
            }

            .brand-title {
                font-size: 2.1rem;
                line-height: 1.15;
                font-weight: 720;
                letter-spacing: 0;
                margin: 0;
            }

            .brand-subtitle {
                color: var(--muted);
                font-size: 1rem;
                margin-top: 0.45rem;
                max-width: 44rem;
            }

            .status-pill {
                border: 1px solid var(--accent-line);
                background: var(--accent-soft);
                color: var(--accent);
                border-radius: 999px;
                padding: 0.35rem 0.7rem;
                font-size: 0.82rem;
                font-weight: 650;
                white-space: nowrap;
            }

            .metric-strip {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.75rem;
                margin: 1.15rem 0 1.4rem;
            }

            .metric-tile {
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 0.8rem 0.9rem;
            }

            .metric-label {
                color: var(--muted);
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                font-weight: 700;
            }

            .metric-value {
                color: var(--ink);
                font-size: 1.05rem;
                font-weight: 720;
                margin-top: 0.2rem;
            }

            [data-testid="stChatMessage"] {
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 8px;
                margin-bottom: 0.8rem;
            }

            [data-testid="stChatMessageAvatarUser"] {
                background: #0f766e;
            }

            [data-testid="stChatMessageAvatarAssistant"] {
                background: #374151;
            }

            .score-badges {
                display: flex;
                flex-wrap: wrap;
                gap: 0.4rem;
                margin-top: 0.6rem;
            }

            .score-badge {
                border-radius: 999px;
                padding: 0.2rem 0.6rem;
                font-size: 0.72rem;
                font-weight: 650;
                border: 1px solid transparent;
                white-space: nowrap;
            }

            .score-badge.score-good {
                color: var(--accent);
                background: var(--accent-soft);
                border-color: var(--accent-line);
            }

            .score-badge.score-bad {
                color: #fca5a5;
                background: rgba(248, 113, 113, 0.12);
                border-color: rgba(248, 113, 113, 0.32);
            }

            .empty-state {
                border: 1px dashed var(--line);
                border-radius: 8px;
                padding: 1.25rem;
                background: var(--panel);
                color: var(--muted);
                margin-bottom: 1rem;
            }

            @media (max-width: 760px) {
                .brand-row {
                    align-items: flex-start;
                    flex-direction: column;
                }

                .metric-strip {
                    grid-template-columns: 1fr;
                }

                .main .block-container {
                    padding-top: 1.25rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    st.session_state.setdefault("agent_messages", [])
    st.session_state.setdefault("display_messages", [])
    st.session_state.setdefault("conversation_id", None)
    st.session_state.setdefault("conversation_span", None)
    st.session_state.setdefault("turn_count", 0)
    st.session_state.setdefault("last_tool_names", [])
    st.session_state.setdefault("last_trace_status", "No traced turn yet")
    st.session_state.setdefault("pending_prompt", None)


def _get_conversation_span():
    if st.session_state.conversation_span is not None:
        return st.session_state.conversation_span

    bt_logger = _init_braintrust()
    conversation_id = str(uuid.uuid4())
    st.session_state.conversation_id = conversation_id
    st.session_state.conversation_span = bt_logger.start_span(
        name="stonks-sessions",
        span_attributes={"type": "task"},
        metadata={
            "entrypoint": "streamlit",
            "conversation_id": conversation_id,
            "project": get_braintrust_project_name(),
        },
    )
    st.session_state.last_trace_status = "Conversation trace started"
    return st.session_state.conversation_span


def _close_conversation_span() -> None:
    span = st.session_state.get("conversation_span")
    if span is None:
        return

    span.log(
        input=[m for m in st.session_state.agent_messages if m.get("role") == "user"],
        output={
            "turns": st.session_state.turn_count,
            "messages": len(st.session_state.agent_messages),
        },
        metadata={
            "entrypoint": "streamlit",
            "conversation_id": st.session_state.conversation_id,
            "status": "closed",
        },
    )
    span.end()
    braintrust.flush()
    st.session_state.conversation_span = None
    st.session_state.conversation_id = None


def _extract_assistant_reply(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("content"):
            return str(message["content"])
    return "I could not produce a response for that request."


def _extract_tool_names(messages: list[dict[str, Any]]) -> list[str]:
    tool_names: list[str] = []
    for message in messages:
        for tool_call in message.get("tool_calls", []) or []:
            function = tool_call.get("function", {})
            name = function.get("name")
            if name:
                tool_names.append(name)
    return tool_names


# ── Live in-app scoring ───────────────────────────────────────────────────────
#
# Problem: the deterministic scorers in evals/scorers.py only ever ran offline
# (bt eval) or as an async online scorer on Braintrust's backend — a user or
# presenter watching the Streamlit app had no way to see whether a given answer
# was actually grounded until they went and looked at a trace or an experiment
# later. This section closes that gap by scoring each turn *in the same request*
# that produces it and rendering the result as a badge under the reply.
#
# Design principles:
#   1. Single source of truth — reuse the existing scorer implementations
#      (score_price_answer, has_citations_header) instead of re-deriving the
#      grading logic, so the live badge and the offline eval can never drift.
#   2. Instant over exhaustive — compute scores synchronously from data already
#      in hand (the LangGraph message list) rather than polling Braintrust's
#      async online scorer, trading an LLM-judge score for a sub-second one.
#   3. Log once, show twice — every computed score is written to the Braintrust
#      span via span.log(scores=...) *and* rendered in the UI, so the same
#      number is visible live in the app and later in the Braintrust dashboard.
#   4. Don't hide the gap — if the price tool wasn't called this turn, the score
#      is still 0.0. The point of this workshop is to make that failure visible,
#      not to suppress it.


def _parse_tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair each `role: tool` message with the function name from its tool call.

    LangGraph's state stores tool calls and their results as separate messages
    (an assistant message with `tool_calls`, followed by `role: tool` replies
    keyed by `tool_call_id`) — this re-joins them so scoring can ask "what did
    tool X actually return this turn?" without needing a Braintrust trace object.
    """
    tool_names_by_id: dict[str, str] = {}
    for message in messages:
        for tool_call in message.get("tool_calls", []) or []:
            tool_names_by_id[tool_call["id"]] = tool_call["function"]["name"]

    results = []
    for message in messages:
        if message.get("role") != "tool":
            continue
        try:
            output = json.loads(message.get("content") or "{}")
        except json.JSONDecodeError:
            output = {}
        results.append({"name": tool_names_by_id.get(message.get("tool_call_id")), "output": output})
    return results


def _score_turn(user_input: str, reply: str, new_messages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Instant, local versions of the deterministic scorers in evals/scorers.py.

    These read tool outputs straight from the LangGraph message list instead of a
    Braintrust trace, so they can score the turn synchronously in the same request
    instead of waiting on an async online scorer.
    """
    tool_results = _parse_tool_results(new_messages)

    # price_response_matches_tool_data: does the final answer state the exact
    # price the (possibly disabled) price tool returned this turn? Reuses the
    # same score_price_answer() the offline eval (qa_eval.py) grades with.
    price_outputs = [r["output"] for r in tool_results if r["name"] == "get_stock_performance"]
    price_score = score_price_answer(reply, price_outputs)

    # tool_returned_data: mirrors scorers.tool_returned_data's trace-based logic,
    # but reads the tool output already sitting in `new_messages` instead of
    # awaiting trace.get_spans() — no Braintrust round trip needed.
    has_error = any("error" in r["output"] for r in tool_results)
    has_price = any("current_price" in r["output"] for r in tool_results)
    tool_data_score = {
        "name": "tool_returned_data",
        "score": 1.0 if (has_price and not has_error) else 0.0,
        "metadata": {"has_error": has_error, "has_price": has_price},
    }

    # has_citations_header is already trace-independent in scorers.py, so call
    # it directly (asyncio.run: it's defined async but does no I/O, and
    # Streamlit's request handling isn't already inside an event loop here).
    citations_score = asyncio.run(has_citations_header(input=user_input, output=reply))

    return {
        "price_response_matches_tool_data": price_score,
        "tool_returned_data": tool_data_score,
        "has_citations_header": citations_score,
    }


def _run_agent(user_input: str) -> tuple[str, dict[str, dict[str, Any]]]:
    previous_message_count = len(st.session_state.agent_messages)
    st.session_state.agent_messages.append({"role": "user", "content": user_input})

    conversation_span = _get_conversation_span()
    from super_stonks.agent.agent import graph

    turn_number = st.session_state.turn_count + 1
    # 0-based turn_{n} to match the CLI (__main__.py) span naming
    with conversation_span.start_span(name=f"turn_{st.session_state.turn_count}", span_attributes={"type": "task"}) as span:
        try:
            result = graph.invoke({"messages": st.session_state.agent_messages})
            st.session_state.agent_messages = result["messages"]

            new_messages = st.session_state.agent_messages[previous_message_count:]
            st.session_state.last_tool_names = _extract_tool_names(new_messages)
            reply = _extract_assistant_reply(st.session_state.agent_messages)
            st.session_state.turn_count += 1
            scores = _score_turn(user_input, reply, new_messages)

            span.log(
                input=user_input,
                output=reply,
                scores={name: result["score"] for name, result in scores.items()},
                metadata={
                    "entrypoint": "streamlit",
                    "conversation_id": st.session_state.conversation_id,
                    "turn": st.session_state.turn_count,
                    "tool_names": st.session_state.last_tool_names,
                    "message_count": len(st.session_state.agent_messages),
                    "scores": scores,
                },
            )
            conversation_span.log(
                input=[m for m in st.session_state.agent_messages if m.get("role") == "user"],
                output=reply,
                metadata={
                    "entrypoint": "streamlit",
                    "conversation_id": st.session_state.conversation_id,
                    "turns": st.session_state.turn_count,
                    "message_count": len(st.session_state.agent_messages),
                    "last_tool_names": st.session_state.last_tool_names,
                },
            )
            st.session_state.last_trace_status = "Conversation trace updated"
            return reply, scores
        except Exception as exc:
            span.log(
                input=user_input,
                output={"error": f"{type(exc).__name__}: {exc}"},
                metadata={
                    "entrypoint": "streamlit",
                    "conversation_id": st.session_state.conversation_id,
                    "turn": turn_number,
                },
            )
            conversation_span.log(
                input=[m for m in st.session_state.agent_messages if m.get("role") == "user"],
                output={"error": f"{type(exc).__name__}: {exc}"},
                metadata={
                    "entrypoint": "streamlit",
                    "conversation_id": st.session_state.conversation_id,
                    "turns": st.session_state.turn_count,
                    "status": "errored",
                },
            )
            st.session_state.last_trace_status = "Conversation trace updated with error"
            raise
        finally:
            braintrust.flush()


def _render_header() -> None:
    tool_count = len(st.session_state.last_tool_names)
    active_tools = ", ".join(st.session_state.last_tool_names) if tool_count else "None"
    st.markdown(
        f"""
        <div class="app-header">
            <div class="brand-row">
                <div>
                    <h1 class="brand-title">{APP_TITLE}</h1>
                    <div class="brand-subtitle">
                        Professional market analysis with live stock data, quantitative signals,
                        current research, and cited sources.
                    </div>
                </div>
                <div class="status-pill">Market research assistant</div>
            </div>
        </div>
        <div class="metric-strip">
            <div class="metric-tile">
                <div class="metric-label">Conversation turns</div>
                <div class="metric-value">{st.session_state.turn_count}</div>
            </div>
            <div class="metric-tile">
                <div class="metric-label">Last tool calls</div>
                <div class="metric-value">{tool_count}</div>
            </div>
            <div class="metric-tile">
                <div class="metric-label">Latest tools</div>
                <div class="metric-value">{active_tools}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Super Stonks")
        st.caption("Live stock analysis workspace")

        if st.button("New conversation", use_container_width=True):
            _close_conversation_span()
            st.session_state.agent_messages = []
            st.session_state.display_messages = []
            st.session_state.turn_count = 0
            st.session_state.last_tool_names = []
            st.session_state.last_trace_status = "No traced turn yet"
            st.session_state.pending_prompt = None
            st.rerun()

        st.divider()
        st.markdown("#### Starting points")
        for prompt in SAMPLE_PROMPTS:
            if st.button(prompt, use_container_width=True):
                st.session_state.pending_prompt = prompt
                st.rerun()

        st.divider()
        st.markdown("#### Tooling")
        st.caption("Price performance")
        st.caption("Buy / hold / sell signals")
        st.caption("Current web research")
        st.caption(f"Braintrust project: {get_braintrust_project_name()}")
        if st.session_state.conversation_id:
            st.caption(f"Conversation: {st.session_state.conversation_id[:8]}")
        st.caption(st.session_state.last_trace_status)


# Human-readable labels for the scorer names returned by _score_turn(). These are
# deliberately binary (0.0/1.0) checks, so the badge only needs pass/fail color,
# not a gradient — see the .score-good / .score-bad CSS above.
_SCORE_LABELS = {
    "price_response_matches_tool_data": "Price grounded",
    "tool_returned_data": "Tool data OK",
    "has_citations_header": "Has citations",
}


def _render_score_badges(scores: dict[str, dict[str, Any]]) -> None:
    """Render one colored pill per score, skipping any that weren't computed."""
    badges = []
    for name, result in scores.items():
        score = result.get("score")
        if score is None:
            continue
        label = _SCORE_LABELS.get(name, name)
        css_class = "score-good" if score >= 1.0 else "score-bad"
        badges.append(f'<span class="score-badge {css_class}">{label}: {score:.2f}</span>')

    if badges:
        st.markdown(f'<div class="score-badges">{"".join(badges)}</div>', unsafe_allow_html=True)


def _render_chat_history() -> None:
    if not st.session_state.display_messages:
        st.markdown(
            """
            <div class="empty-state">
                Ask about a ticker, recent performance, portfolio context, market risks,
                or whether a stock looks like a buy, hold, or sell.
            </div>
            """,
            unsafe_allow_html=True,
        )

    for message in st.session_state.display_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("scores"):
                _render_score_badges(message["scores"])


def _consume_prompt() -> str | None:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    return prompt


def _render_tool_details() -> None:
    if not st.session_state.last_tool_names:
        return

    with st.expander("Latest tool activity", expanded=False):
        st.code(json.dumps(st.session_state.last_tool_names, indent=2), language="json")


def main() -> None:
    _configure_page()
    _init_braintrust()
    _init_state()
    _render_sidebar()
    _render_header()
    _render_chat_history()
    _render_tool_details()

    prompt = _consume_prompt() or st.chat_input("Ask about a stock, fund, or market question")
    if not prompt:
        return

    st.session_state.display_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    scores: dict[str, dict[str, Any]] | None = None
    with st.chat_message("assistant"):
        with st.spinner("Running market analysis..."):
            try:
                reply, scores = _run_agent(prompt)
            except Exception as exc:
                reply = (
                    "I could not complete the analysis because the agent raised an error. "
                    f"`{type(exc).__name__}: {exc}`"
                )
        st.markdown(reply)
        if scores:
            _render_score_badges(scores)

    st.session_state.display_messages.append({"role": "assistant", "content": reply, "scores": scores})
    st.rerun()


if __name__ == "__main__":
    main()

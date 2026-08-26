from __future__ import annotations

import json
import subprocess
import uuid
from typing import Any

import braintrust
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from super_stonks.agent.config import get_braintrust_project_name, init_braintrust_logger


APP_TITLE = "Super Stonks"
SAMPLE_PROMPTS = [
    "How has NVDA performed today, this week, and this year?",
    "Should I buy, hold, or sell MSFT right now?",
    "Compare the recent performance of AAPL and GOOGL.",
    "What are the key risks for TSLA investors?",
]

# Online scorer registered via `make push-scorer` + `make automations` (see
# evals/push_assets.py and provision/configure.py). Runs on turn spans in Braintrust,
# asynchronously — the badge shows "pending" until it lands.
SCORE_POLL_TIMEOUT_SECONDS = 8
MAX_SCORE_POLL_ATTEMPTS = 40
GRADE_THRESHOLDS = (
    ("A+", 1.0), ("A", 0.9), ("A-", 0.8), ("B+", 0.7), ("B", 0.6), ("B-", 0.5),
    ("C+", 0.4), ("C", 0.3), ("C-", 0.2), ("D", 0.1),
)


@st.cache_resource(show_spinner=False)
def _init_braintrust() -> object:
    return init_braintrust_logger()


@st.cache_resource(show_spinner=False)
def _get_project_id() -> str | None:
    """Resolve BRAINTRUST_DEFAULT_PROJECT to its id, via the bt CLI (cached for the session)."""
    try:
        result = subprocess.run(
            ["bt", "projects", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=SCORE_POLL_TIMEOUT_SECONDS,
            check=True,
        )
        projects = json.loads(result.stdout)
    except Exception:
        return None
    project_name = get_braintrust_project_name()
    return next((p["id"] for p in projects if p.get("name") == project_name), None)


def _fetch_score_spans(root_span_id: str) -> dict[str, dict[str, Any]]:
    """Fetch every online-scorer result span logged so far for this conversation's trace.

    Braintrust logs each online score as its own child span (type "score") of the turn
    span it scored, carrying the score, the judge's letter grade, and its full
    chain-of-thought rationale in `output.metadata`. One query covers every turn at once
    — cheaper than polling per turn, and it's the only place the rationale lives.
    Returns a dict keyed by the parent turn's `span_id` (its tracing id, not row `.id`).
    """
    project_id = _get_project_id()
    if not project_id:
        return {}

    query = (
        "SELECT span_parents, span_attributes.name AS scorer_name, output "
        f"FROM project_logs('{project_id}') "
        f"WHERE root_span_id = '{root_span_id}' AND span_attributes.type = 'score'"
    )
    try:
        result = subprocess.run(
            ["bt", "sql", query, "--json"],
            capture_output=True,
            text=True,
            timeout=SCORE_POLL_TIMEOUT_SECONDS,
            check=True,
        )
        rows = json.loads(result.stdout).get("data", [])
    except Exception:
        return {}

    by_parent: dict[str, dict[str, Any]] = {}
    for row in rows:
        parents = row.get("span_parents") or []
        output = row.get("output") or {}
        if not parents or output.get("score") is None:
            continue
        metadata = output.get("metadata") or {}
        by_parent[parents[0]] = {
            "scorer_name": row.get("scorer_name") or output.get("name") or "score",
            "score": output.get("score"),
            "choice": metadata.get("choice"),
            "rationale": metadata.get("rationale"),
        }
    return by_parent


def _poll_pending_scores() -> bool:
    """Re-check Braintrust for any turn still waiting on its online score.

    Returns True if any turn's status changed, so callers can decide whether a
    re-render is worth it.
    """
    pending = [
        m["eval"] for m in st.session_state.display_messages
        if (m.get("eval") or {}).get("status") == "pending"
    ]
    if not pending:
        return False

    root_span_id = st.session_state.get("conversation_root_span_id")
    by_parent = _fetch_score_spans(root_span_id) if root_span_id else {}

    changed = False
    for eval_info in pending:
        eval_info["attempts"] += 1
        match = by_parent.get(eval_info["tracing_span_id"])
        if match:
            eval_info["status"] = "scored"
            eval_info["scorer_name"] = match["scorer_name"]
            eval_info["score"] = match["score"]
            eval_info["choice"] = match.get("choice")
            eval_info["rationale"] = match.get("rationale")
            changed = True
        elif eval_info["attempts"] >= MAX_SCORE_POLL_ATTEMPTS:
            eval_info["status"] = "timeout"
            changed = True
    return changed


def _grade_label(score: float) -> str:
    for grade, threshold in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def _grade_tier(score: float) -> str:
    """Bucket a 0-1 score into Braintrust's traffic-light convention for score chips."""
    if score >= 0.8:
        return "good"
    if score >= 0.5:
        return "mid"
    return "poor"


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_score_overlay(eval_info: dict[str, Any] | None) -> None:
    if not eval_info or not st.session_state.get("show_scores"):
        return

    status = eval_info.get("status")
    if status == "scored":
        score = eval_info.get("score")
        scorer_name = eval_info.get("scorer_name", "score")
        grade = eval_info.get("choice") or _grade_label(score)
        rationale = eval_info.get("rationale") or "No rationale recorded for this score."
        tier = _grade_tier(score)
        label = f"{scorer_name} · {grade} ({score:.2f})"
        st.markdown(
            f"""
            <div class="score-overlay">
                <span class="score-badge score-{tier}" tabindex="0">
                    {_escape_html(label)}
                    <span class="score-tooltip">{_escape_html(rationale)}</span>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif status == "timeout":
        st.markdown(
            '<div class="score-overlay"><span class="score-badge score-pending">'
            "No online score yet — try Refresh scores</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="score-overlay"><span class="score-badge score-pending">'
            "Evaluating…</span></div>",
            unsafe_allow_html=True,
        )


def _render_score_details(eval_info: dict[str, Any] | None) -> None:
    """Full evaluation detail — the persistent, click-to-open counterpart to the hover badge."""
    if not eval_info or eval_info.get("status") != "scored" or not st.session_state.get("show_scores"):
        return

    with st.expander(f"Evaluation · {eval_info.get('scorer_name', 'score')}", expanded=False):
        score = eval_info.get("score")
        grade = eval_info.get("choice") or _grade_label(score)
        col1, col2 = st.columns(2)
        col1.metric("Score", f"{score:.2f}")
        col2.metric("Grade", grade)
        st.markdown("**Judge's rationale**")
        st.write(eval_info.get("rationale") or "No rationale recorded for this score.")




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
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

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
                --good: #34d399;
                --good-soft: rgba(52, 211, 153, 0.13);
                --good-line: rgba(52, 211, 153, 0.35);
                --mid: #fbbf24;
                --mid-soft: rgba(251, 191, 36, 0.13);
                --mid-line: rgba(251, 191, 36, 0.35);
                --poor: #f87171;
                --poor-soft: rgba(248, 113, 113, 0.13);
                --poor-line: rgba(248, 113, 113, 0.35);
                --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                --font-mono: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;
            }

            html, body, .stApp, [data-testid="stSidebar"], .stMarkdown, .stChatMessage,
            .stButton > button, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
                font-family: var(--font-sans) !important;
            }

            code, pre, .score-badge {
                font-family: var(--font-mono) !important;
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

            .empty-state {
                border: 1px dashed var(--line);
                border-radius: 8px;
                padding: 1.25rem;
                background: var(--panel);
                color: var(--muted);
                margin-bottom: 1rem;
            }

            .score-overlay {
                display: flex;
                justify-content: flex-end;
                margin: -0.6rem 0 0.9rem;
            }

            .score-badge {
                position: relative;
                display: inline-block;
                border: 1px solid var(--line);
                background: var(--panel-soft);
                color: var(--muted);
                border-radius: 6px;
                padding: 0.28rem 0.65rem;
                font-size: 0.72rem;
                font-weight: 500;
                letter-spacing: -0.01em;
                white-space: nowrap;
                cursor: default;
            }

            .score-badge.score-good {
                border-color: var(--good-line);
                background: var(--good-soft);
                color: var(--good);
            }

            .score-badge.score-mid {
                border-color: var(--mid-line);
                background: var(--mid-soft);
                color: var(--mid);
            }

            .score-badge.score-poor {
                border-color: var(--poor-line);
                background: var(--poor-soft);
                color: var(--poor);
            }

            .score-tooltip {
                display: none;
                position: absolute;
                z-index: 20;
                top: calc(100% + 0.4rem);
                right: 0;
                width: 22rem;
                max-width: 70vw;
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 0.75rem 0.85rem;
                color: var(--ink);
                font-family: var(--font-sans);
                font-size: 0.8rem;
                font-weight: 400;
                line-height: 1.45;
                white-space: normal;
                text-align: left;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
            }

            .score-badge:hover .score-tooltip,
            .score-badge:focus .score-tooltip {
                display: block;
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
    st.session_state.setdefault("conversation_root_span_id", None)
    st.session_state.setdefault("turn_count", 0)
    st.session_state.setdefault("last_tool_names", [])
    st.session_state.setdefault("last_trace_status", "No traced turn yet")
    st.session_state.setdefault("pending_prompt", None)
    st.session_state.setdefault("show_scores", False)


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
    st.session_state.conversation_root_span_id = st.session_state.conversation_span.root_span_id
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
    st.session_state.conversation_root_span_id = None


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


def _run_agent(user_input: str) -> str:
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

            span.log(
                input=user_input,
                output=reply,
                metadata={
                    "entrypoint": "streamlit",
                    "conversation_id": st.session_state.conversation_id,
                    "turn": st.session_state.turn_count,
                    "tool_names": st.session_state.last_tool_names,
                    "message_count": len(st.session_state.agent_messages),
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
            st.session_state["_last_turn_eval"] = {
                "tracing_span_id": span.span_id,
                "status": "pending",
                "score": None,
                "scorer_name": None,
                "choice": None,
                "rationale": None,
                "attempts": 0,
            }
            return reply
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
        """,
        unsafe_allow_html=True,
    )

    st.toggle(
        "Show scores",
        key="show_scores",
        help="Overlay each answer with its Braintrust online-scorer result",
    )

    st.markdown(
        f"""
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
            st.session_state.pop("_last_turn_eval", None)
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

        st.divider()
        st.markdown("#### Run results")
        st.caption("Flip \"Show scores\" at the top to overlay the chat with evaluations")
        turn_evals = [
            m.get("eval") for m in st.session_state.display_messages
            if m.get("role") == "assistant" and m.get("eval")
        ]
        if not turn_evals:
            st.caption("No evaluated runs yet")
        else:
            for idx, eval_info in enumerate(turn_evals, start=1):
                status = eval_info.get("status")
                if status == "scored":
                    score = eval_info.get("score")
                    grade = eval_info.get("choice") or _grade_label(score)
                    summary = f"{eval_info.get('scorer_name')}={score:.2f} ({grade})"
                elif status == "timeout":
                    summary = "no online score"
                else:
                    summary = "pending…"
                st.caption(f"Turn {idx}: {summary}")
        if st.button("Refresh scores", use_container_width=True):
            st.rerun()


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
        if message["role"] == "assistant":
            _render_score_overlay(message.get("eval"))
            _render_score_details(message.get("eval"))


def _consume_prompt() -> str | None:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    return prompt


def _render_tool_details() -> None:
    if not st.session_state.last_tool_names:
        return

    with st.expander("Latest tool activity", expanded=False):
        st.code(json.dumps(st.session_state.last_tool_names, indent=2), language="json")


@st.fragment(run_every="4s")
def _auto_refresh_scores() -> None:
    """Keep polling in the background so badges resolve without a manual refresh."""
    if _poll_pending_scores():
        st.rerun()


def main() -> None:
    _configure_page()
    _init_braintrust()
    _init_state()
    _poll_pending_scores()
    _auto_refresh_scores()
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

    eval_info = None
    with st.chat_message("assistant"):
        with st.spinner("Running market analysis..."):
            try:
                reply = _run_agent(prompt)
                eval_info = st.session_state.pop("_last_turn_eval", None)
            except Exception as exc:
                reply = (
                    "I could not complete the analysis because the agent raised an error. "
                    f"`{type(exc).__name__}: {exc}`"
                )
        st.markdown(reply)
    _render_score_overlay(eval_info)
    _render_score_details(eval_info)

    assistant_message: dict[str, Any] = {"role": "assistant", "content": reply}
    if eval_info:
        assistant_message["eval"] = eval_info
    st.session_state.display_messages.append(assistant_message)
    st.rerun()


if __name__ == "__main__":
    main()

import json
import logging

import braintrust
from langgraph.graph import END, StateGraph
from openai import OpenAI

from .prompts import STOCK_CHAT_SYSTEM
from .state import AgentState
from .tools import TOOLS_SPEC, analyze_stock_buy, get_stock_performance

_PARENT_TOOLS_SPEC = TOOLS_SPEC

logger = logging.getLogger(__name__)

# wrap_openai ensures every chat.completions.create call becomes a child LLM span
_client = braintrust.wrap_openai(OpenAI())

_SYSTEM_PROMPT = STOCK_CHAT_SYSTEM

_MODEL = "gpt-4o-mini"

# Max tool-execution rounds per turn. Once hit, the model is forced to answer with
# text (tool_choice="none") instead of calling tools again — stops the redundant
# re-calls (e.g. retrying analyze_stock_buy hoping for a price it can't return).
MAX_TOOL_ROUNDS = 2


def _system_prompt_kwargs(user_input: str) -> dict:
    """Build chat kwargs from the hardcoded system prompt (the only source)."""

    return {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
    }


def agent_node(state: AgentState) -> dict:
    messages = state["messages"]

    if len(messages) == 1 and messages[0].get("role") == "user":
        prompt_kwargs = _system_prompt_kwargs(messages[0]["content"])

    else:
        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": _SYSTEM_PROMPT}] + messages
        prompt_kwargs = {"model": _MODEL, "messages": messages}

    # An explicit model on the state (e.g. from an eval parameter) wins over the default.
    if state.get("model"):
        prompt_kwargs["model"] = state["model"]

    # After MAX_TOOL_ROUNDS tool rounds, force a text answer instead of more tool calls.
    tool_choice = "none" if state.get("tool_rounds", 0) >= MAX_TOOL_ROUNDS else "auto"
    response = _client.chat.completions.create(
        **prompt_kwargs,
        tools=_PARENT_TOOLS_SPEC,
        tool_choice=tool_choice,
    )

    msg = response.choices[0].message
    msg_dict = {"role": msg.role, "content": msg.content}
    if msg.tool_calls:
        msg_dict["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]

    return {"messages": [msg_dict]}


def _invoke_tool(fn_name: str, fn_args: dict) -> dict:
    # THE GAP (workshop): route disabled alongside the commented-out tool spec in
    # tools.py. Uncomment both to close the gap and let the agent fetch real prices.
    # if fn_name == "get_stock_performance":
    #     return get_stock_performance(**fn_args)
    if fn_name == "analyze_stock_buy":
        return analyze_stock_buy(**fn_args)
    return {"error": f"Unknown tool: {fn_name}"}


def tool_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    results = []
    for tc in last.get("tool_calls", []):
        fn_name = tc["function"]["name"]
        fn_args = json.loads(tc["function"]["arguments"])
        result = _invoke_tool(fn_name, fn_args)
        results.append({"role": "tool", "content": json.dumps(result), "tool_call_id": tc["id"]})

    return {"messages": results, "tool_rounds": state.get("tool_rounds", 0) + 1}


def _route(state: AgentState) -> str:
    last = state["messages"][-1]
    return "tools" if last.get("tool_calls") else END


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", _route, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()


graph = build_graph()

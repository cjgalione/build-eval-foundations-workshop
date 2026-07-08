"""Drive the (toolless) agent to seed production-like traces.

The span tree and the logged input/output/metadata mirror the Streamlit app
(`super_stonks/app.py`) exactly, so seeded "sims" are indistinguishable in shape from
real traffic:

    stonks-sessions (root, metadata: entrypoint/conversation_id/project/bucket)
    └─ turn_{n}      (input = user_input string; metadata: turn/tool_names/message_count)
       └─ { LLM span, TOOL span }
    (the root/conversation span is logged each turn with input = the list of user messages)

Topics must be enabled first — the Makefile makes `topics` upstream of seeding.
Sessions are a mix of single- and multi-turn (see scenarios.py).

    uv run python -m super_stonks.seed.seed --count 10
"""

from __future__ import annotations

import argparse
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv()  # OPENAI_API_KEY (agent) + BRAINTRUST_API_KEY (SDK)

import braintrust

from super_stonks.agent.agent import graph
from super_stonks.agent.config import get_braintrust_project_name, init_braintrust_logger
from super_stonks.seed.scenarios import build

ENTRYPOINT = "seed"


def _extract_assistant_reply(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("content"):
            return str(message["content"])
    return "I could not produce a response for that request."


def _extract_tool_names(messages: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for message in messages:
        for tool_call in message.get("tool_calls", []) or []:
            name = (tool_call.get("function") or {}).get("name")
            if name:
                names.append(name)
    return names


def _seed_session(scenario: dict, project: str) -> None:
    conversation_id = str(uuid.uuid4())
    with braintrust.start_span(
        name="stonks-sessions",
        span_attributes={"type": "task"},
        metadata={
            "entrypoint": ENTRYPOINT,
            "conversation_id": conversation_id,
            "project": project,
            "bucket": scenario["bucket"],
        },
    ) as session:
        agent_messages: list[dict] = []
        for turn_idx, user_input in enumerate(scenario["turns"]):
            previous_count = len(agent_messages)
            agent_messages.append({"role": "user", "content": user_input})

            with braintrust.start_span(name=f"turn_{turn_idx}", span_attributes={"type": "task"}) as span:
                result = graph.invoke({"messages": agent_messages})
                agent_messages = result["messages"]
                new_messages = agent_messages[previous_count:]
                tool_names = _extract_tool_names(new_messages)
                reply = _extract_assistant_reply(agent_messages)

                span.log(
                    input=user_input,
                    output=reply,
                    metadata={
                        "entrypoint": ENTRYPOINT,
                        "conversation_id": conversation_id,
                        "turn": turn_idx + 1,
                        "tool_names": tool_names,
                        "message_count": len(agent_messages),
                    },
                )
                session.log(
                    input=[m for m in agent_messages if m.get("role") == "user"],
                    output=reply,
                    metadata={
                        "entrypoint": ENTRYPOINT,
                        "conversation_id": conversation_id,
                        "turns": turn_idx + 1,
                        "message_count": len(agent_messages),
                        "last_tool_names": tool_names,
                    },
                )
    braintrust.flush()


def run(count: int) -> None:
    init_braintrust_logger()  # sets the active logger → spans land in the project
    project = get_braintrust_project_name()
    scenarios = build(count)
    turns_total = sum(len(s["turns"]) for s in scenarios)
    print(f"[seed] seeding {len(scenarios)} sessions ({turns_total} turns) into '{project}' …")

    for i, scenario in enumerate(scenarios, start=1):
        _seed_session(scenario, project)
        if i % 25 == 0 or i == len(scenarios):
            print(f"  {i}/{len(scenarios)}")

    print("[seed] done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Super Stonks traces.")
    parser.add_argument("--count", type=int, default=10, help="number of sessions/traces to seed")
    run(parser.parse_args().count)


if __name__ == "__main__":
    main()

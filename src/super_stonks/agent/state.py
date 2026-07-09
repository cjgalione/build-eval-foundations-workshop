from __future__ import annotations

from typing import Annotated, TypedDict


def _append(existing: list, new: list | dict) -> list:
    if isinstance(new, list):
        return existing + new
    return existing + [new]


class AgentState(TypedDict, total=False):
    messages: Annotated[list, _append]
    model: str
    tool_rounds: int  # tool-execution rounds so far this turn (capped in agent.py)

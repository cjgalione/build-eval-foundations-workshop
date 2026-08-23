"""Offline experiment for the workshop — run with `bt eval`.

Runs the agent over the curated gap dataset (in YOUR project) and scores whether its
final answer includes the exact current price returned by the traced price tool. Run it
twice to get the before/after:

  1. tool still commented out  -> baseline experiment (low grounding)
  2. uncomment get_stock_performance (GAP.md) -> re-run -> grounding jumps

    bt eval src/super_stonks/evals/qa_eval.py

Dataset name defaults to "price-gap-baseline" (created in the workshop UI or with
`make curate-dataset`);
override with EVAL_DATASET. Project comes from BRAINTRUST_DEFAULT_PROJECT (your project).
"""

import os

from dotenv import load_dotenv

load_dotenv()  # OPENAI_API_KEY + BRAINTRUST_API_KEY (before importing the agent/scorers)

from braintrust import Eval, init_dataset

from super_stonks.agent.agent import graph
from super_stonks.evals.scorers import price_response_matches_tool_data

PROJECT = os.environ["BRAINTRUST_DEFAULT_PROJECT"]
DATASET = os.environ.get("EVAL_DATASET", "price-gap-baseline")


def run(user_input) -> str:
    # Dataset inputs may be a bare string, {"content": "..."} / {"q": "..."}, or a
    # trace-derived message list [{"role": "user", "content": "..."}] (what the curated
    # gap dataset stores) — take the last user turn's text.
    if isinstance(user_input, list):
        user_msgs = [m for m in user_input if isinstance(m, dict) and m.get("role") == "user"]
        chosen = (user_msgs or [m for m in user_input if isinstance(m, dict)] or [{}])[-1]
        user_input = chosen.get("content", "")
    if isinstance(user_input, dict):
        user_input = user_input.get("content") or user_input.get("q") or next(iter(user_input.values()), "")
    result = graph.invoke({"messages": [{"role": "user", "content": str(user_input)}]})
    msgs = result["messages"]
    return next(
        (m["content"] for m in reversed(msgs) if m.get("role") == "assistant" and m.get("content")),
        "",
    )


Eval(
    PROJECT,
    data=init_dataset(PROJECT, DATASET),
    task=run,
    scores=[price_response_matches_tool_data],
)

"""Deterministic checks for price answers backed by a traced tool result."""

from __future__ import annotations

import json
import math
import re
from typing import Any, Iterable


_NUMBER = re.compile(r"(?<![A-Za-z0-9])\$?([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{1,2})?|[0-9]+(?:\.\d{1,2})?)(?![A-Za-z0-9])")


def _as_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None


def _numbers(text: str) -> list[float]:
    values: list[float] = []
    for match in _NUMBER.finditer(text):
        try:
            values.append(float(match.group(1).replace(",", "")))
        except ValueError:
            continue
    return values


def score_price_answer(answer: str, tool_outputs: Iterable[Any], *, tolerance: float = 0.02) -> dict[str, Any]:
    """Return a binary score when the final answer states a fetched current price.

    This deliberately answers a narrow, testable workshop question. It does not rate
    tone or investment advice; the editable UI rubric covers that subjective layer.
    """
    prices: list[float] = []
    for raw_output in tool_outputs:
        output = _as_mapping(raw_output)
        if output and isinstance(output.get("current_price"), (int, float)):
            prices.append(float(output["current_price"]))

    if not prices:
        return {
            "name": "price_response_matches_tool_data",
            "score": 0.0,
            "metadata": {"reason": "no_usable_price_tool_output", "tool_prices": []},
        }

    answer_numbers = _numbers(answer or "")
    matched = next(
        (price for price in prices if any(math.isclose(value, price, abs_tol=tolerance) for value in answer_numbers)),
        None,
    )
    return {
        "name": "price_response_matches_tool_data",
        "score": 1.0 if matched is not None else 0.0,
        "metadata": {
            "reason": "matched_current_price" if matched is not None else "fetched_price_missing_from_answer",
            "tool_prices": prices,
            "answer_numbers": answer_numbers,
            "matched_price": matched,
        },
    }

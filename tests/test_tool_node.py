import json
import os
import unittest
from unittest.mock import patch

# Importing the agent constructs an OpenAI client at import time — it doesn't need a
# *valid* key, just a non-empty one.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-a-real-key")

from yfinance.exceptions import YFRateLimitError

from super_stonks.agent import agent


def _state(arguments: str) -> dict:
    return {
        "messages": [
            {"role": "user", "content": "Should I buy AAPL?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "analyze_stock_buy", "arguments": arguments},
                    }
                ],
            },
        ]
    }


class ToolNodeErrorTests(unittest.TestCase):
    """A failing tool call must come back to the model as a tool error message (so it
    can answer gracefully) instead of raising and killing the whole turn."""

    def test_tool_exception_becomes_error_result(self):
        with patch.object(agent, "analyze_stock_buy", side_effect=YFRateLimitError()):
            result = agent.tool_node(_state('{"ticker": "AAPL"}'))

        [message] = result["messages"]
        self.assertEqual(message["role"], "tool")
        self.assertEqual(message["tool_call_id"], "call_1")
        self.assertIn("YFRateLimitError", json.loads(message["content"])["error"])
        self.assertEqual(result["tool_rounds"], 1)

    def test_malformed_arguments_become_error_result(self):
        with patch.object(agent, "analyze_stock_buy") as tool:
            result = agent.tool_node(_state('{"ticker": "AAPL"'))

        tool.assert_not_called()
        [message] = result["messages"]
        self.assertEqual(message["tool_call_id"], "call_1")
        self.assertIn("error", json.loads(message["content"]))

    def test_successful_tool_result_is_unchanged(self):
        payload = {"ticker": "AAPL", "verdict": "BUY"}
        with patch.object(agent, "analyze_stock_buy", return_value=payload):
            result = agent.tool_node(_state('{"ticker": "AAPL"}'))

        self.assertEqual(json.loads(result["messages"][0]["content"]), payload)


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from unittest.mock import patch

# Importing super_stonks.agent.agent (transitively, via app._run_agent) constructs an
# OpenAI client at import time — it doesn't need a *valid* key, just a non-empty one.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-a-real-key")
os.environ.setdefault("BRAINTRUST_API_KEY", "bt-test-not-a-real-key")
os.environ.setdefault("BRAINTRUST_DEFAULT_PROJECT", "test-project")

import streamlit as st

from super_stonks import app
from super_stonks.agent.agent import graph


class FakeSessionState(dict):
    """Minimal stand-in for st.session_state (attribute + setdefault access) so
    app._run_agent can be exercised without a running Streamlit script context."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key, value):
        self[key] = value

    def setdefault(self, key, value):
        return dict.setdefault(self, key, value)


class FakeSpan:
    def start_span(self, *args, **kwargs):
        return self

    def log(self, *args, **kwargs):
        pass

    def end(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RunAgentFailureRecoveryTests(unittest.TestCase):
    """A failed graph.invoke() must not corrupt the next turn: the turn counter has
    to keep advancing (so retried turns get distinct Braintrust span names) and the
    orphaned user message has to be rolled back (so the next turn doesn't send the
    LLM two consecutive user messages with no assistant reply between them)."""

    def setUp(self):
        st.session_state = FakeSessionState()
        app._init_state()
        self.get_span_patcher = patch.object(app, "_get_conversation_span", return_value=FakeSpan())
        self.flush_patcher = patch.object(app.braintrust, "flush")
        self.get_span_patcher.start()
        self.flush_patcher.start()
        self.addCleanup(self.get_span_patcher.stop)
        self.addCleanup(self.flush_patcher.stop)

    def test_turn_count_advances_even_when_graph_invoke_fails(self):
        turn_before = st.session_state.turn_count

        with patch.object(graph, "invoke", side_effect=RuntimeError("simulated failure")):
            with self.assertRaises(RuntimeError):
                app._run_agent("How much is TSLA stock today?")

        self.assertEqual(st.session_state.turn_count, turn_before + 1)

    def test_agent_messages_rolled_back_when_graph_invoke_fails(self):
        messages_before = len(st.session_state.agent_messages)

        with patch.object(graph, "invoke", side_effect=RuntimeError("simulated failure")):
            with self.assertRaises(RuntimeError):
                app._run_agent("How much is TSLA stock today?")

        self.assertEqual(len(st.session_state.agent_messages), messages_before)

    def test_retry_after_failure_does_not_reuse_the_failed_turn_span_name(self):
        failed_turn_span_name = f"turn_{st.session_state.turn_count}"

        with patch.object(graph, "invoke", side_effect=RuntimeError("simulated failure")):
            with self.assertRaises(RuntimeError):
                app._run_agent("How much is TSLA stock today?")

        retry_turn_span_name = f"turn_{st.session_state.turn_count}"
        self.assertNotEqual(retry_turn_span_name, failed_turn_span_name)

        retry_result = {
            "messages": st.session_state.agent_messages
            + [
                {"role": "user", "content": "How much is TSLA stock today?"},
                {"role": "assistant", "content": "TSLA is at $123.45."},
            ]
        }
        with patch.object(graph, "invoke", return_value=retry_result):
            reply = app._run_agent("How much is TSLA stock today?")

        self.assertEqual(reply, "TSLA is at $123.45.")


if __name__ == "__main__":
    unittest.main()

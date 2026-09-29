import os
import unittest
from unittest.mock import patch

# Importing the CLI initializes the Braintrust logger and (via the agent) an OpenAI
# client at import time — neither needs a *valid* key, just a non-empty one.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-a-real-key")
os.environ.setdefault("BRAINTRUST_API_KEY", "bt-test-not-a-real-key")
os.environ.setdefault("BRAINTRUST_DEFAULT_PROJECT", "test-project")

from click.testing import CliRunner

from super_stonks.agent import __main__ as cli


class FakeSpan:
    def __init__(self, name, spans):
        self.name = name
        self.logs = []
        spans.append(self)

    def log(self, **kwargs):
        self.logs.append(kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class CliFailedTurnTests(unittest.TestCase):
    """A failed graph.invoke() must not kill the interactive session: the error is
    reported, the orphaned user message is rolled back, the retry gets a fresh
    turn_{n} span, and the root session span is still logged on exit."""

    def setUp(self):
        self.spans = []
        span_patcher = patch.object(
            cli.braintrust, "start_span", side_effect=lambda name, **_: FakeSpan(name, self.spans)
        )
        flush_patcher = patch.object(cli.braintrust, "flush")
        span_patcher.start()
        flush_patcher.start()
        self.addCleanup(span_patcher.stop)
        self.addCleanup(flush_patcher.stop)
        self.invocations = []

    def _graph_invoke(self, state):
        # Snapshot the history the agent was called with, then fail the first call only.
        self.invocations.append([dict(m) for m in state["messages"]])
        if len(self.invocations) == 1:
            raise RuntimeError("upstream timeout")
        return {"messages": state["messages"] + [{"role": "assistant", "content": "AAPL looks fine."}]}

    def _run(self, stdin):
        with patch.object(cli.graph, "invoke", side_effect=self._graph_invoke):
            return CliRunner().invoke(cli.main, input=stdin)

    def test_failed_turn_does_not_crash_session(self):
        result = self._run("first question\nsecond question\nquit\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("upstream timeout", result.output)
        self.assertIn("AAPL looks fine.", result.output)

    def test_failed_user_message_is_rolled_back(self):
        self._run("first question\nsecond question\nquit\n")
        self.assertEqual(self.invocations[1], [{"role": "user", "content": "second question"}])

    def test_retry_gets_distinct_turn_span_and_session_is_logged(self):
        self._run("first question\nsecond question\nquit\n")
        names = [s.name for s in self.spans]
        self.assertEqual(names, ["stonks-sessions", "turn_0", "turn_1"])
        self.assertIn("error", self.spans[1].logs[0]["output"])
        self.assertEqual(self.spans[0].logs[0]["output"], {"turns": 2})


if __name__ == "__main__":
    unittest.main()

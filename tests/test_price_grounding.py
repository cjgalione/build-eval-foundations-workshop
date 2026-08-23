import unittest

from super_stonks.evals.price_grounding import score_price_answer


class PriceGroundingTests(unittest.TestCase):
    def test_no_price_tool_output_fails(self):
        result = score_price_answer("AAPL is trading at $214.47.", [])
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["metadata"]["reason"], "no_usable_price_tool_output")

    def test_matching_price_passes(self):
        result = score_price_answer("AAPL is currently $214.47.", [{"current_price": 214.47}])
        self.assertEqual(result["score"], 1.0)

    def test_currency_formatting_passes(self):
        result = score_price_answer("The latest price is $1,234.50.", ['{"current_price": 1234.5}'])
        self.assertEqual(result["score"], 1.0)

    def test_wrong_price_fails(self):
        result = score_price_answer("AAPL is currently $200.00.", [{"current_price": 214.47}])
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["metadata"]["reason"], "fetched_price_missing_from_answer")

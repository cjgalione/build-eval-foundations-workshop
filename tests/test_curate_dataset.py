import unittest

from super_stonks.provision.curate_dataset import MAX_ROWS, build_rows


class CurateDatasetTests(unittest.TestCase):
    def test_build_rows_preserves_failure_taxonomy_and_caps_at_five(self):
        trace_ids = [f"trace-{index}" for index in range(6)]
        turns = {
            trace_id: {"input": f"Quote for T{index}?", "output": "No live price.", "name": "turn_0"}
            for index, trace_id in enumerate(trace_ids)
        }

        rows = build_rows(trace_ids, turns)

        self.assertEqual(len(rows), MAX_ROWS)
        self.assertEqual(rows[0]["metadata"]["failure_category"], "price_gap")
        self.assertEqual(rows[0]["metadata"]["source_trace_id"], "trace-0")
        self.assertIsNone(rows[0]["expected"])

    def test_build_rows_skips_unknown_traces(self):
        rows = build_rows(["missing", "present"], {"present": {"input": "Quote for AAPL?", "output": "", "name": "turn_0"}})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["input"], "Quote for AAPL?")

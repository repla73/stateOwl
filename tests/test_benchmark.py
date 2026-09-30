from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stateowl_benchmark", ROOT / "benchmarks" / "benchmark.py")
bench = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(bench)


class BenchmarkContractTests(unittest.TestCase):
    def test_unrelated_records_do_not_scale_focused_path(self):
        empty = bench.focused(0)
        large = bench.focused(1000)
        self.assertEqual(empty["api_calls"], large["api_calls"])
        self.assertEqual(empty["bytes_returned"], large["bytes_returned"])
        self.assertEqual(empty["model_context_bytes"], large["model_context_bytes"])
        self.assertGreater(bench.naive(1000)["api_calls"], large["api_calls"])
        self.assertGreater(bench.naive(1000)["model_context_bytes"], large["model_context_bytes"] * 100)

    def test_detail_is_one_explicit_additional_read(self):
        compact = bench.focused(1000)
        detail = bench.focused(1000, detail=True)
        self.assertEqual(detail["api_calls"], compact["api_calls"] + 1)
        self.assertGreater(detail["model_context_bytes"], compact["model_context_bytes"])


if __name__ == "__main__":
    unittest.main()

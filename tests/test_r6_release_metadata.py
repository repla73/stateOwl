"""Release metadata/identity regression; no network or effect."""
from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import stateowl  # noqa: E402
from stateowl.r2 import PROTOCOL as READ_PROTOCOL  # noqa: E402
from stateowl.r3_publish import PROTOCOL as PUBLISH_PROTOCOL, RECEIPT_FORMAT  # noqa: E402


class ReleaseMetadataTests(unittest.TestCase):
    def test_python_distribution_metadata_coheres(self):
        meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(meta["project"]["version"], "0.2.0")
        self.assertEqual(stateowl.__version__, "0.2.0")
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8"), "0.2.0\n")

    def test_protocol_and_receipt_ids_unchanged(self):
        self.assertEqual(READ_PROTOCOL, "stateowl/0.2-draft.3")
        self.assertEqual(PUBLISH_PROTOCOL, READ_PROTOCOL)
        self.assertEqual(RECEIPT_FORMAT, "stateowl.git-receipt/2")


if __name__ == "__main__":
    unittest.main()

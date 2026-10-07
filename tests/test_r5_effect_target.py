from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "qualification"))

from r5_effect_target import EffectTargetConflict, LocalEffectTarget


class EffectTargetTests(unittest.TestCase):
    def test_same_effect_id_is_idempotent_and_queryable(self):
        with tempfile.TemporaryDirectory() as directory:
            target = LocalEffectTarget(directory)
            first = target.perform("effect-001", b"payload")
            second = target.perform("effect-001", b"payload")
            self.assertEqual(first["status"], "complete")
            self.assertFalse(first["duplicate_suppressed"])
            self.assertTrue(second["duplicate_suppressed"])
            self.assertEqual(target.query("effect-001")["payload_digest"], first["payload_digest"])
            self.assertEqual(len(list(Path(directory).glob("effect-001.json"))), 1)

    def test_same_identity_with_different_payload_is_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            target = LocalEffectTarget(directory)
            target.perform("effect-001", b"one")
            with self.assertRaises(EffectTargetConflict):
                target.perform("effect-001", b"two")

    def test_missing_and_corrupt_status_are_not_retried_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            target = LocalEffectTarget(directory)
            self.assertEqual(target.query("effect-001")["status"], "absent")
            Path(directory, "effect-001.json").write_text("{broken", encoding="utf-8")
            self.assertEqual(target.query("effect-001")["status"], "unknown")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "qualification"))

from r5_gate import QualificationGate


class Feed:
    def __init__(self, status="unchanged", snapshot="same-head"):
        self.status = status
        self.snapshot = snapshot
        self.calls = 0

    def __call__(self, token):
        self.calls += 1
        status = "baseline" if token is None and self.status == "unchanged" else self.status
        if status == "error":
            return {"op": "observe", "status": "error", "error": {"code": "PROVIDER_UNAVAILABLE"}}
        return {
            "op": "observe",
            "status": status,
            "snapshot": {"id": self.snapshot},
            "token": f"token-{self.calls}",
        }


def profile(*, due_at=200, blocked=False, claim=None, effect_status="none"):
    return {
        "schema": "stateowl.r5-qualification-job/1",
        "due_at": due_at,
        "blocked": blocked,
        "claim": claim,
        "effect": {"id": "effect-001", "status": effect_status},
    }


class GateTests(unittest.TestCase):
    def test_one_thousand_unchanged_not_due_checks_are_idle_without_model_permission(self):
        feed = Feed()
        reads = []
        gate = QualificationGate(observe=feed, read_profile=lambda snapshot: reads.append(snapshot) or profile(), claimant="worker-a")
        decisions = [gate.check(100) for _ in range(1000)]
        self.assertTrue(all(item.decision == "idle" for item in decisions))
        self.assertTrue(all(item.model_allowed is False for item in decisions))
        self.assertEqual(len(reads), 1)
        self.assertEqual(feed.calls, 1000)

    def test_same_head_deadline_changes_idle_to_eligible(self):
        feed = Feed(snapshot="unchanged-head")
        gate = QualificationGate(observe=feed, read_profile=lambda snapshot: profile(due_at=200), claimant="worker-a")
        before = gate.check(199)
        due = gate.check(200)
        self.assertEqual(before.decision, "idle")
        self.assertEqual(due.decision, "eligible")
        self.assertEqual(before.snapshot, due.snapshot)
        self.assertFalse(before.model_allowed)
        self.assertTrue(due.model_allowed)

    def test_duplicate_and_out_of_order_wakes_do_not_create_work(self):
        feed = Feed()
        gate = QualificationGate(observe=feed, read_profile=lambda snapshot: profile(due_at=500), claimant="worker-a")
        for now in (100, 99, 100, 101, 100):
            self.assertEqual(gate.check(now).decision, "idle")

    def test_missing_event_is_repaired_by_scheduled_due_check(self):
        feed = Feed(snapshot="same-head")
        gate = QualificationGate(observe=feed, read_profile=lambda snapshot: profile(due_at=200), claimant="worker-a")
        self.assertEqual(gate.check(100).decision, "idle")
        self.assertEqual(gate.check(200).decision, "eligible")

    def test_claim_and_expiry_are_project_owned_eligibility(self):
        feed = Feed()
        records = [profile(due_at=100, claim={"owner": "worker-b", "expires_at": 300})]
        gate = QualificationGate(observe=feed, read_profile=lambda snapshot: records[-1], claimant="worker-a")
        claimed = gate.check(200)
        self.assertEqual(claimed.decision, "idle")
        self.assertEqual(claimed.next_due, 300)
        expired = gate.check(300)
        self.assertEqual(expired.decision, "eligible")
        self.assertEqual(expired.reason, "expired-claim-takeover-candidate")

    def test_unknown_effect_requires_operator_and_observe_error_blocks(self):
        feed = Feed()
        gate = QualificationGate(observe=feed, read_profile=lambda snapshot: profile(due_at=100, effect_status="unknown"), claimant="worker-a")
        self.assertEqual(gate.check(100).decision, "operator_required")
        self.assertFalse(gate.check(100).model_allowed)

        broken = QualificationGate(observe=Feed(status="error"), read_profile=lambda snapshot: profile(), claimant="worker-a")
        self.assertEqual(broken.check(100).decision, "blocked/error")

    def test_restart_reconstructs_from_durable_profile(self):
        first_feed = Feed()
        first = QualificationGate(observe=first_feed, read_profile=lambda snapshot: profile(due_at=200), claimant="worker-a")
        self.assertEqual(first.check(100).decision, "idle")

        restarted_feed = Feed()
        restarted = QualificationGate(observe=restarted_feed, read_profile=lambda snapshot: profile(due_at=200), claimant="worker-a")
        self.assertEqual(restarted.check(100).decision, "idle")
        self.assertEqual(restarted.next_due, 200)


if __name__ == "__main__":
    unittest.main()

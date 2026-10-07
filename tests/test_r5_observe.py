from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stateowl.observe import HMACTokenService, Observer
from stateowl.r2 import PROTOCOL, ReadFault
from stateowl.r2_memory import MemoryReadProvider


class ResetProvider(MemoryReadProvider):
    def access(self, target, operation):
        value = super().access(target, operation)
        return {**value, "continuity": "reset"}


class OutageProvider(MemoryReadProvider):
    def resolve(self, target):
        raise ReadFault("PROVIDER_UNAVAILABLE")


class ObserveTests(unittest.TestCase):
    def setUp(self):
        self.target = {
            "kind": "git",
            "authority": "github.com",
            "resource": "fixture/project",
            "namespace": "refs/heads/state",
        }
        self.A = "git:sha1:" + "a" * 40
        self.D = "git:sha1:" + "d" * 40
        self.E = "git:sha1:" + "e" * 40
        self.base = b'{"status":"waiting","noise":"same"}\n'
        self.changed = b'{"status":"waiting","noise":"changed"}\n'
        self.objects = {
            self.A: {"type": "commit", "parents": [], "files": {"state/job.json": self.base}},
            self.D: {"type": "commit", "parents": [self.A], "files": {"state/job.json": self.base}},
            self.E: {"type": "commit", "parents": [self.D], "files": {"state/job.json": self.changed}},
        }
        self.clock = [100]
        self.provider = MemoryReadProvider(self.target, self.objects, head=self.A, algorithm="sha1")
        self.tokens = HMACTokenService(b"r5-test-secret", ttl_seconds=10, clock=lambda: self.clock[0])
        self.observer = Observer(self.provider, self.tokens)

    def request(self, *, token=None, scoped=False):
        request = {"protocol": PROTOCOL, "op": "observe", "target": self.target}
        if scoped:
            request["records"] = [
                {"key": "job", "path": "state/job.json", "format": "json", "select": ["status"]}
            ]
        if token is not None:
            request["token"] = token
        return request

    def test_head_only_baseline_unchanged_and_changed(self):
        first = self.observer.observe(self.request())
        self.assertEqual(first["status"], "baseline")
        second = self.observer.observe(self.request(token=first["token"]))
        self.assertEqual(second["status"], "unchanged")
        self.provider.head = self.D
        third = self.observer.observe(self.request(token=second["token"]))
        self.assertEqual(third["status"], "changed")
        self.assertEqual(third["snapshot"]["id"], self.D)

    def test_scoped_observe_suppresses_unrelated_head_identity(self):
        first = self.observer.observe(self.request(scoped=True))
        self.provider.head = self.D
        second = self.observer.observe(self.request(token=first["token"], scoped=True))
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(second["snapshot"]["id"], self.D)
        self.assertEqual(self.observer.last_instrumentation.resolve, 1)
        self.assertEqual(self.observer.last_instrumentation.file, 1)

    def test_scoped_observe_detects_unprojected_raw_change(self):
        first = self.observer.observe(self.request(scoped=True))
        self.provider.head = self.E
        second = self.observer.observe(self.request(token=first["token"], scoped=True))
        self.assertEqual(second["status"], "changed")

    def test_token_tamper_expiry_and_scope_mismatch_are_errors(self):
        first = self.observer.observe(self.request())
        tampered = first["token"][:-1] + ("A" if first["token"][-1] != "A" else "B")
        self.assertEqual(self.observer.observe(self.request(token=tampered))["error"]["code"], "TOKEN_INVALID")
        self.clock[0] = 110
        self.assertEqual(self.observer.observe(self.request(token=first["token"]))["error"]["code"], "TOKEN_INVALID")

        self.clock[0] = 100
        fresh = self.observer.observe(self.request())
        mismatch = self.observer.observe(self.request(token=fresh["token"], scoped=True))
        self.assertEqual(mismatch["error"]["code"], "TOKEN_INVALID")

    def test_deleted_outage_and_known_reset_remain_errors(self):
        deleted = MemoryReadProvider(self.target, self.objects, head=None, algorithm="sha1")
        self.assertEqual(Observer(deleted, self.tokens).observe(self.request())["error"]["code"], "NOT_FOUND")

        outage = OutageProvider(self.target, self.objects, head=self.A, algorithm="sha1")
        self.assertEqual(Observer(outage, self.tokens).observe(self.request())["error"]["code"], "PROVIDER_UNAVAILABLE")

        reset = ResetProvider(self.target, self.objects, head=self.A, algorithm="sha1")
        self.assertEqual(Observer(reset, self.tokens).observe(self.request())["error"]["code"], "NAMESPACE_DISCONTINUITY")


if __name__ == "__main__":
    unittest.main()

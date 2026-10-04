from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stateowl.r3_publish import (
    PROTOCOL,
    PublicationFault,
    Publisher,
    build_candidate,
    parse_receipt,
    publication_identity,
    receipt_message,
    request_digest,
)

A = "git:sha1:" + "a" * 40
B = "git:sha1:" + "b" * 40
C = "git:sha1:" + "c" * 40
D = "git:sha1:" + "d" * 40
TARGET = {
    "kind": "git",
    "authority": "github.com",
    "resource": "fixture/project",
    "namespace": "refs/heads/state",
}
VALIDATION = "urn:fixture:validation:1"
CAPABILITIES = {
    "protocol": PROTOCOL,
    "operations": ["read", "publish", "observe"],
    "formats": ["json", "text", "base64"],
    "features": [],
    "resolvers": [],
    "limits": {
        "request_bytes": 65536,
        "record_bytes": 16384,
        "mutation_bytes": 32768,
        "response_bytes": 65536,
        "records": 32,
        "expansions": 16,
        "changes": 32,
        "tag_hops": 8,
        "reconcile_commits": 16,
        "json_depth": 64,
    },
    "publication": {
        "continuity": "single_step_required",
        "receipt_format": "stateowl.git-receipt/2",
        "receipt_retention": "reachable_history",
        "authority": "project_validated",
    },
}
BASE = {
    "state/work.json": {"base64": base64.b64encode(b'{"v":"A"}\n').decode(), "mode": "100644"},
    "state/obsolete.txt": {"base64": base64.b64encode(b"old\n").decode(), "mode": "100644"},
    "state/script": {"base64": base64.b64encode(b"#!/bin/sh\nexit 0\n").decode(), "mode": "100755"},
    "state/untouched.txt": {"base64": base64.b64encode(b"keep\n").decode(), "mode": "100644"},
    "state/validation.json": {"base64": base64.b64encode(b'{"enabled":true}\n').decode(), "mode": "100644"},
}


def request(*, mode: str = "submit", changes=None, validation=VALIDATION):
    return {
        "protocol": PROTOCOL,
        "op": "publish",
        "target": copy.deepcopy(TARGET),
        "expected": {"id": A},
        "mode": mode,
        "validation": validation,
        "changes": changes
        if changes is not None
        else [
            {"path": "state/work.json", "put": {"encoding": "utf8", "data": '{"v":"B"}\n'}},
            {"path": "state/obsolete.txt", "delete": True},
        ],
    }


def raw(req):
    return json.dumps(req, ensure_ascii=False, separators=(",", ":")).encode()


class MemoryProvider:
    def __init__(self):
        self.head = A
        self.objects = {
            A: {"id": A, "type": "commit", "parents": [], "message": "base\n", "files": copy.deepcopy(BASE)}
        }
        self.validation = VALIDATION
        self.validator_available = True
        self.project_authorized = True
        self.continuity = "intact"
        self.access_sequence: list[str] = []
        self.forbidden: set[str] = set()
        self.reject_policy_change = False
        self.admissions = 0
        self.dispatches = 0
        self.after_admit_head: str | None = None
        self.admit_fault: PublicationFault | None = None
        self.tree_fault_after_ack: str | None = None
        self._acked = False

    def add_commit(self, oid, parent, message, files, *, head=False):
        self.objects[oid] = {"id": oid, "type": "commit", "parents": [parent], "message": message, "files": copy.deepcopy(files)}
        if head:
            self.head = oid

    def call(self, method, **args):
        if method == "access":
            continuity = self.access_sequence.pop(0) if self.access_sequence else self.continuity
            return {
                "validation": self.validation,
                "validator_available": self.validator_available,
                "project_authorized": self.project_authorized,
                "continuity": continuity,
                "auth_scope": "fixture",
            }
        if method == "authorize":
            if any(path in self.forbidden for path in args["paths"]):
                raise PublicationFault("FORBIDDEN")
            return True
        if method == "resolve":
            if self.head is None:
                raise PublicationFault("NOT_FOUND")
            return self.head
        if method == "inspect":
            obj = self.objects.get(args["snapshot"])
            if obj is None:
                raise PublicationFault("SNAPSHOT_UNAVAILABLE")
            return {k: copy.deepcopy(v) for k, v in obj.items() if k != "files"}
        if method == "tree":
            if self._acked and self.tree_fault_after_ack:
                code = self.tree_fault_after_ack
                self.tree_fault_after_ack = None
                raise PublicationFault(code)
            obj = self.objects.get(args["snapshot"])
            if obj is None:
                raise PublicationFault("SNAPSHOT_UNAVAILABLE")
            return copy.deepcopy(obj["files"])
        if method == "validate":
            if self.reject_policy_change and args["old"].get("state/validation.json") != args["candidate"].get("state/validation.json"):
                raise PublicationFault("VALIDATION_FAILED")
            return True
        if method == "admit":
            if self.admit_fault:
                fault = self.admit_fault
                if fault.dispatched and self.head == args["expected"]:
                    self.dispatches += 1
                    self.admissions += 1
                    self.objects[B] = {
                        "id": B,
                        "type": "commit",
                        "parents": [args["expected"]],
                        "message": args["message"],
                        "files": copy.deepcopy(args["candidate"]),
                    }
                    self.head = B
                raise fault
            self.dispatches += 1
            if self.head != args["expected"]:
                return {"status": "conflict"}
            self.admissions += 1
            self.objects[B] = {
                "id": B,
                "type": "commit",
                "parents": [args["expected"]],
                "message": args["message"],
                "files": copy.deepcopy(args["candidate"]),
            }
            self.head = B
            self._acked = True
            if self.after_admit_head is not None:
                self.head = self.after_admit_head
            return {"status": "admitted", "snapshot": B}
        raise AssertionError(method)


class R3PublisherTests(unittest.TestCase):
    def run_request(self, provider, req, caps=None):
        return Publisher(provider, copy.deepcopy(caps or CAPABILITIES)).run(raw(req))

    def test_w1_publication_identity_golden(self):
        req = {
            "protocol": PROTOCOL,
            "op": "publish",
            "target": copy.deepcopy(TARGET),
            "expected": {"id": A},
            "mode": "submit",
            "validation": VALIDATION,
            "changes": [
                {"path": "state/work.json", "put": {"encoding": "utf8", "data": '{"id":"work","status":"ready"}\n'}},
                {"path": "state/obsolete.txt", "delete": True},
            ],
        }
        self.assertEqual(request_digest(req), "sha256:32923b0fada7776bad03f6cab614854ab79ea1e466f0b611bff7ceb306485529")
        self.assertEqual(
            receipt_message(req),
            "stateOwl publication\n\nStateOwl-Receipt: eyJjaGFuZ2VzIjpbeyJkZWxldGUiOnRydWUsInBhdGgiOiJzdGF0ZS9vYnNvbGV0ZS50eHQifSx7InBhdGgiOiJzdGF0ZS93b3JrLmpzb24iLCJwdXQiOnsiYnl0ZXMiOjMxLCJkaWdlc3QiOiJzaGEyNTY6YjhhOTlkYTQwY2Q2N2ZlYWNmYjg1M2QwNTQyZGFjNjE5NTQ0YTA5MjUwOGUxNjExNmZkYWJmNzUxMjQ3MzFlZSJ9fV0sImV4cGVjdGVkIjp7ImlkIjoiZ2l0OnNoYTE6YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYSJ9LCJwcm90b2NvbCI6InN0YXRlb3dsLzAuMi1kcmFmdC4zIiwidGFyZ2V0Ijp7ImF1dGhvcml0eSI6ImdpdGh1Yi5jb20iLCJraW5kIjoiZ2l0IiwibmFtZXNwYWNlIjoicmVmcy9oZWFkcy9zdGF0ZSIsInJlc291cmNlIjoiZml4dHVyZS9wcm9qZWN0In0sInZhbGlkYXRpb24iOiJ1cm46Zml4dHVyZTp2YWxpZGF0aW9uOjEifQ==\n",
        )

    def test_identity_digest_is_mode_and_encoding_independent(self):
        first = request()
        second = request(mode="reconcile")
        second["changes"].reverse()
        for change in second["changes"]:
            if "put" in change:
                data = change["put"]["data"].encode()
                change["put"] = {"encoding": "base64", "data": base64.b64encode(data).decode()}
        self.assertEqual(publication_identity(first), publication_identity(second))
        self.assertEqual(request_digest(first), request_digest(second))

    def test_receipt_codec_accepts_only_exact_forms(self):
        req = request()
        self.assertEqual(parse_receipt(receipt_message(req)), publication_identity(req))
        self.assertEqual(parse_receipt(receipt_message(req, heading=False)), publication_identity(req))
        with self.assertRaises(PublicationFault) as caught:
            parse_receipt(receipt_message(req) + "extra\n")
        self.assertEqual(caught.exception.code, "INVALID_SOURCE")
        self.assertIsNone(parse_receipt("ordinary commit\n"))

    def test_normal_commit_and_untouched_state(self):
        provider = MemoryProvider()
        result = self.run_request(provider, request())
        self.assertEqual(result["outcome"], "committed")
        self.assertEqual(result["snapshot"], {"id": B})
        self.assertEqual(provider.admissions, 1)
        self.assertEqual(provider.objects[B]["files"]["state/untouched.txt"], BASE["state/untouched.txt"])

    def test_stale_whole_namespace_conflict(self):
        provider = MemoryProvider()
        other = copy.deepcopy(BASE)
        other["state/other.txt"] = {"base64": base64.b64encode(b"winner\n").decode(), "mode": "100644"}
        provider.add_commit(D, A, "other\n", other, head=True)
        result = self.run_request(provider, request())
        self.assertEqual((result["outcome"], result["error"]["code"]), ("not_committed", "CONFLICT"))
        self.assertEqual(provider.admissions, 0)

    def test_submit_conflict_recovers_identical_publication(self):
        provider = MemoryProvider()
        req = request()
        files = build_candidate(req, BASE)
        provider.add_commit(B, A, receipt_message(req), files, head=True)
        result = self.run_request(provider, req)
        self.assertEqual(result["outcome"], "committed")
        self.assertEqual(result["snapshot"], {"id": B})
        self.assertEqual(provider.admissions, 0)

    def test_lost_response_is_indeterminate_and_not_redispatched(self):
        provider = MemoryProvider()
        provider.admit_fault = PublicationFault("PROVIDER_UNAVAILABLE", dispatched=True)
        result = self.run_request(provider, request())
        self.assertEqual((result["outcome"], result["error"]["retry"]), ("indeterminate", "reconcile"))
        self.assertEqual(provider.admissions, 1)
        self.assertEqual(provider.dispatches, 1)

    def test_positive_ack_then_verification_failure_is_pending(self):
        provider = MemoryProvider()
        provider.tree_fault_after_ack = "PROVIDER_UNAVAILABLE"
        result = self.run_request(provider, request())
        self.assertEqual(result["outcome"], "verification_pending")
        self.assertEqual(result["snapshot"], {"id": B})
        self.assertEqual(result["error"]["retry"], "reconcile")

    def test_later_successor_does_not_negate_commit(self):
        provider = MemoryProvider()
        req = request()
        files = build_candidate(req, BASE)
        successor = copy.deepcopy(files)
        successor["state/successor.txt"] = {"base64": base64.b64encode(b"later\n").decode(), "mode": "100644"}
        provider.add_commit(C, B, "later\n", successor)
        provider.after_admit_head = C
        result = self.run_request(provider, req)
        self.assertEqual(result["outcome"], "committed")
        self.assertEqual(result["snapshot"], {"id": B})
        self.assertEqual(result["observed_head"], {"id": C})

    def test_reconcile_is_read_only_and_bounded(self):
        provider = MemoryProvider()
        req = request(mode="reconcile")
        files = build_candidate(req, BASE)
        provider.add_commit(C, A, receipt_message(req), files)
        later = copy.deepcopy(files)
        later["state/later"] = {"base64": "", "mode": "100644"}
        provider.add_commit(D, C, "later\n", later, head=True)
        caps = copy.deepcopy(CAPABILITIES)
        caps["limits"]["reconcile_commits"] = 1
        result = self.run_request(provider, req, caps)
        self.assertEqual((result["outcome"], result["error"]["code"]), ("indeterminate", "HISTORY_UNAVAILABLE"))
        self.assertEqual(provider.dispatches, 0)

    def test_malformed_and_wrong_receipt(self):
        req = request(mode="reconcile")
        files = build_candidate(req, BASE)
        malformed = MemoryProvider()
        malformed.add_commit(B, A, "StateOwl-Receipt: AB==\n", files, head=True)
        result = self.run_request(malformed, req)
        self.assertEqual((result["outcome"], result["error"]["code"]), ("indeterminate", "INVALID_SOURCE"))

        wrong = MemoryProvider()
        other = request(mode="reconcile", changes=[{"path": "state/new", "put": {"encoding": "utf8", "data": "x"}}])
        wrong.add_commit(B, A, receipt_message(other), files, head=True)
        result = self.run_request(wrong, req)
        self.assertEqual((result["outcome"], result["error"]["code"]), ("not_committed", "CONFLICT"))

    def test_skipped_head_continuity_blocks_inference(self):
        provider = MemoryProvider()
        provider.continuity = "reset"
        result = self.run_request(provider, request(mode="reconcile"))
        self.assertEqual((result["outcome"], result["error"]["code"]), ("indeterminate", "NAMESPACE_DISCONTINUITY"))
        self.assertEqual(provider.dispatches, 0)

    def test_validation_pin_mismatch_and_self_downgrade(self):
        mismatch = MemoryProvider()
        mismatch.validation = "urn:fixture:validation:2"
        result = self.run_request(mismatch, request())
        self.assertEqual((result["outcome"], result["error"]["code"]), ("not_committed", "VALIDATION_FAILED"))

        downgrade = MemoryProvider()
        downgrade.reject_policy_change = True
        req = request(changes=[
            {"path": "state/work.json", "put": {"encoding": "utf8", "data": '{"v":"B"}\n'}},
            {"path": "state/validation.json", "put": {"encoding": "utf8", "data": '{"enabled":false}\n'}},
        ])
        result = self.run_request(downgrade, req)
        self.assertEqual((result["outcome"], result["error"]["code"]), ("not_committed", "VALIDATION_FAILED"))
        self.assertEqual(downgrade.admissions, 0)

    def test_unauthorized_path_precedes_expected_state_reads(self):
        provider = MemoryProvider()
        provider.forbidden.add("state/work.json")
        result = self.run_request(provider, request())
        self.assertEqual((result["outcome"], result["error"]["code"]), ("not_committed", "FORBIDDEN"))
        self.assertEqual(provider.dispatches, 0)

    def test_no_change_and_delete_missing(self):
        unchanged = request(changes=[{"path": "state/work.json", "put": {"encoding": "base64", "data": BASE["state/work.json"]["base64"]}}])
        result = self.run_request(MemoryProvider(), unchanged)
        self.assertEqual((result["outcome"], result["error"]["code"]), ("not_committed", "NO_CHANGE"))

        missing = request(changes=[{"path": "state/missing", "delete": True}])
        result = self.run_request(MemoryProvider(), missing)
        self.assertEqual((result["outcome"], result["error"]["code"]), ("not_committed", "NOT_FOUND"))

    def test_mode_preservation_and_new_file_mode(self):
        provider = MemoryProvider()
        req = request(changes=[
            {"path": "state/script", "put": {"encoding": "utf8", "data": "#!/bin/sh\necho r3\n"}},
            {"path": "state/new.txt", "put": {"encoding": "utf8", "data": ""}},
        ])
        result = self.run_request(provider, req)
        self.assertEqual(result["outcome"], "committed")
        self.assertEqual(provider.objects[B]["files"]["state/script"]["mode"], "100755")
        self.assertEqual(provider.objects[B]["files"]["state/new.txt"]["mode"], "100644")

    def test_shared_publish_suite_is_exactly_89_addressable_cases(self):
        root = Path(__file__).resolve().parents[1]
        mapping = json.loads((root / "qualification" / "r3_python_publish_mapping.json").read_text(encoding="utf-8"))
        self.assertEqual(len(mapping["cases"]), 89)
        shared = root / "docs" / "protocol" / "publish-cases.json"
        if shared.exists():
            cases = json.loads(shared.read_text(encoding="utf-8"))
            self.assertEqual(len(cases), 89)
            self.assertEqual(set(mapping["cases"]), {case["id"] for case in cases})


if __name__ == "__main__":
    unittest.main()

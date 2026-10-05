from __future__ import annotations

import base64
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stateowl.r3_github import GitHubPublicationStorage, HTTPResponse
from stateowl.r3_publish import (
    CompositePublicationProvider,
    PROTOCOL,
    PublicationFault,
    Publisher,
    StaticTrustedProjectValidation,
    build_candidate,
    parse_receipt,
    receipt_message,
)

A_RAW = "a" * 40
A = "git:sha1:" + A_RAW
TREE = "d" * 40
TARGET = {
    "kind": "git",
    "authority": "github.com",
    "resource": "fixture/project",
    "namespace": "refs/heads/state",
}
AUTHOR = {"name": "State Owl", "email": "stateowl@example.invalid", "date": "2026-10-06T01:02:03Z"}
COMMITTER = {"name": "State Owl", "email": "stateowl@example.invalid", "date": "2026-10-06T01:02:04Z"}
CAPABILITIES = {
    "protocol": PROTOCOL,
    "operations": ["publish"],
    "formats": [],
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
    "state/keep": {
        "base64": base64.b64encode(b"keep\n").decode("ascii"),
        "mode": "100644",
    }
}


def ident(actor):
    instant = datetime.fromisoformat(actor["date"].replace("Z", "+00:00"))
    return f'{actor["name"]} <{actor["email"]}> {int(instant.timestamp())} +0000'


def commit_payload(
    raw_message: str,
    *,
    api_message: str | None = None,
    tree: str = TREE,
    parents: list[str] | None = None,
):
    parent_list = [A_RAW] if parents is None else parents
    body = (
        f"tree {tree}\n"
        + "".join(f"parent {parent}\n" for parent in parent_list)
        + f"author {ident(AUTHOR)}\n"
        + f"committer {ident(COMMITTER)}\n\n"
        + raw_message
    ).encode("utf-8")
    sha = hashlib.sha1(b"commit " + str(len(body)).encode("ascii") + b"\0" + body).hexdigest()
    return {
        "sha": sha,
        "message": raw_message if api_message is None else api_message,
        "tree": {"sha": tree},
        "parents": [{"sha": parent} for parent in parent_list],
        "author": copy.deepcopy(AUTHOR),
        "committer": copy.deepcopy(COMMITTER),
        "verification": {
            "verified": False,
            "reason": "unsigned",
            "signature": None,
            "payload": None,
            "verified_at": None,
        },
    }


def request(*, path="state/new"):
    return {
        "protocol": PROTOCOL,
        "op": "publish",
        "target": copy.deepcopy(TARGET),
        "expected": {"id": A},
        "mode": "reconcile",
        "validation": None,
        "changes": [{"path": path, "put": {"encoding": "utf8", "data": "x"}}],
    }


class CallbackTransport:
    def __init__(self, callback):
        self.callback = callback
        self.calls = []

    def request(self, method, url, *, headers, payload=None, dispatch_uncertain=False):
        call = {
            "method": method,
            "url": url,
            "headers": dict(headers),
            "payload": payload,
            "dispatch_uncertain": dispatch_uncertain,
        }
        self.calls.append(call)
        return self.callback(call)


class ReconcileStorage(GitHubPublicationStorage):
    def __init__(self, *, payload, old, candidate):
        self.payload_for_commit = payload
        self.head = "git:sha1:" + payload["sha"]
        self.trees = {A: copy.deepcopy(old), self.head: copy.deepcopy(candidate)}
        super().__init__(
            owner="fixture",
            repository="project",
            token="test-token",
            target=TARGET,
            repository_node_id="R_fixture",
            transport=CallbackTransport(self._callback),
        )

    def _callback(self, call):
        if call["method"] == "GET" and f'/git/commits/{self.payload_for_commit["sha"]}' in call["url"]:
            return HTTPResponse(200, copy.deepcopy(self.payload_for_commit), {})
        raise AssertionError(call)

    def resolve(self, target):
        self._target(target)
        return self.head

    def tree(self, target, snapshot):
        self._target(target)
        return copy.deepcopy(self.trees[snapshot])


class PreAdmissionStorage(GitHubPublicationStorage):
    def __init__(self, payload):
        self.created_payload = payload
        self.admission_attempted = False
        super().__init__(
            owner="fixture",
            repository="project",
            token="test-token",
            target=TARGET,
            repository_node_id="R_fixture",
            transport=CallbackTransport(self._callback),
        )

    def _callback(self, call):
        if call["method"] == "POST" and call["url"].endswith("/git/commits"):
            return HTTPResponse(201, copy.deepcopy(self.created_payload), {})
        raise AssertionError(call)

    def tree(self, target, snapshot):
        self._target(target)
        return {}

    def _create_candidate_tree(self, expected, old, candidate):
        return TREE

    def _admit_ref(self, target, expected, candidate_sha):
        self.admission_attempted = True
        return True


class GitHubReceiptProofTests(unittest.TestCase):
    def provider(self, payload):
        transport = CallbackTransport(
            lambda call: HTTPResponse(200, copy.deepcopy(payload), {})
            if call["method"] == "GET"
            else HTTPResponse(201, copy.deepcopy(payload), {})
        )
        return GitHubPublicationStorage(
            owner="fixture",
            repository="project",
            token="test-token",
            target=TARGET,
            repository_node_id="R_fixture",
            transport=transport,
        )

    def test_exact_receipt_with_normalized_api_echo(self):
        req = request()
        exact = receipt_message(req)
        payload = commit_payload(exact, api_message=exact[:-1])
        metadata = self.provider(payload).inspect(TARGET, "git:sha1:" + payload["sha"])
        self.assertEqual(metadata["message"], exact)
        self.assertEqual(parse_receipt(metadata["message"])["expected"], {"id": A})

    def test_raw_receipt_missing_lf_is_rejected(self):
        req = request()
        malformed = receipt_message(req)[:-1]
        payload = commit_payload(malformed, api_message=malformed)
        metadata = self.provider(payload).inspect(TARGET, "git:sha1:" + payload["sha"])
        self.assertEqual(metadata["message"], malformed)
        with self.assertRaises(PublicationFault) as caught:
            parse_receipt(metadata["message"])
        self.assertEqual(caught.exception.code, "INVALID_SOURCE")

    def test_malformed_extra_receipt_framing_is_rejected(self):
        req = request()
        malformed = receipt_message(req) + "extra\n"
        payload = commit_payload(malformed, api_message=malformed)
        metadata = self.provider(payload).inspect(TARGET, "git:sha1:" + payload["sha"])
        with self.assertRaises(PublicationFault) as caught:
            parse_receipt(metadata["message"])
        self.assertEqual(caught.exception.code, "INVALID_SOURCE")

    def test_tree_mismatch_remains_rejected(self):
        req = request()
        exact = receipt_message(req)
        payload = commit_payload(exact, api_message=exact[:-1], tree="e" * 40)
        provider = self.provider(payload)
        with self.assertRaises(PublicationFault) as caught:
            provider._create_commit(TREE, A, exact)
        self.assertEqual(caught.exception.code, "INTEGRITY_MISMATCH")

    def test_parent_mismatch_remains_rejected(self):
        req = request()
        exact = receipt_message(req)
        payload = commit_payload(exact, api_message=exact[:-1], parents=["c" * 40])
        provider = self.provider(payload)
        with self.assertRaises(PublicationFault) as caught:
            provider._create_commit(TREE, A, exact)
        self.assertEqual(caught.exception.code, "INTEGRITY_MISMATCH")

    def test_unprovable_receipt_fails_before_admission(self):
        req = request()
        exact = receipt_message(req)
        payload = commit_payload(exact, api_message=exact[:-1])
        payload["sha"] = "b" * 40
        storage = PreAdmissionStorage(payload)
        with self.assertRaises(PublicationFault) as caught:
            storage.admit(TARGET, A, {}, exact)
        self.assertEqual(caught.exception.code, "INTEGRITY_MISMATCH")
        self.assertFalse(storage.admission_attempted)

    def test_reconciliation_uses_exact_receipt_proof(self):
        req = request()
        exact = receipt_message(req)
        candidate = build_candidate(req, BASE)
        payload = commit_payload(exact, api_message=exact[:-1])
        storage = ReconcileStorage(payload=payload, old=BASE, candidate=candidate)
        trusted = StaticTrustedProjectValidation(target=TARGET, validation=None)
        result = Publisher(
            CompositePublicationProvider(trusted, storage),
            copy.deepcopy(CAPABILITIES),
        ).run(json.dumps(req, separators=(",", ":")).encode("utf-8"))
        self.assertEqual(result["outcome"], "committed")
        self.assertEqual(result["snapshot"], {"id": storage.head})
        self.assertEqual(result["observed_head"], {"id": storage.head})

    def test_reconciliation_wrong_receipt_identity_is_conflict(self):
        req = request()
        other = request(path="state/other")
        exact = receipt_message(other)
        candidate = build_candidate(req, BASE)
        payload = commit_payload(exact, api_message=exact[:-1])
        storage = ReconcileStorage(payload=payload, old=BASE, candidate=candidate)
        trusted = StaticTrustedProjectValidation(target=TARGET, validation=None)
        result = Publisher(
            CompositePublicationProvider(trusted, storage),
            copy.deepcopy(CAPABILITIES),
        ).run(json.dumps(req, separators=(",", ":")).encode("utf-8"))
        self.assertEqual((result["outcome"], result["error"]["code"]), ("not_committed", "CONFLICT"))

    def test_reconciliation_missing_lf_does_not_weaken_parser(self):
        req = request()
        malformed = receipt_message(req)[:-1]
        candidate = build_candidate(req, BASE)
        payload = commit_payload(malformed, api_message=malformed)
        storage = ReconcileStorage(payload=payload, old=BASE, candidate=candidate)
        trusted = StaticTrustedProjectValidation(target=TARGET, validation=None)
        result = Publisher(
            CompositePublicationProvider(trusted, storage),
            copy.deepcopy(CAPABILITIES),
        ).run(json.dumps(req, separators=(",", ":")).encode("utf-8"))
        self.assertEqual((result["outcome"], result["error"]["code"]), ("indeterminate", "INVALID_SOURCE"))


if __name__ == "__main__":
    unittest.main()

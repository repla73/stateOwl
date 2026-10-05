from __future__ import annotations

import base64
from datetime import datetime
import hashlib
from pathlib import Path
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stateowl.r3_github import GitHubPublicationStorage, HTTPResponse
from stateowl.r3_publish import PublicationFault

A_RAW = "a" * 40
B_RAW = "b" * 40
C_RAW = "c" * 40
A = "git:sha1:" + A_RAW

def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()

def commit_payload(message: str, tree: str, parents: list[str], *, api_message: str | None = None):
    author = {"name": "State Owl", "email": "stateowl@example.invalid", "date": "2026-10-06T01:02:03Z"}
    committer = {"name": "State Owl", "email": "stateowl@example.invalid", "date": "2026-10-06T01:02:04Z"}

    def ident(actor):
        instant = datetime.fromisoformat(actor["date"].replace("Z", "+00:00"))
        return f'{actor["name"]} <{actor["email"]}> {int(instant.timestamp())} +0000'

    body = (
        f"tree {tree}\n"
        + "".join(f"parent {parent}\n" for parent in parents)
        + f"author {ident(author)}\n"
        + f"committer {ident(committer)}\n\n"
        + message
    ).encode("utf-8")
    sha = hashlib.sha1(b"commit " + str(len(body)).encode("ascii") + b"\0" + body).hexdigest()
    return {
        "sha": sha,
        "message": message if api_message is None else api_message,
        "tree": {"sha": tree},
        "parents": [{"sha": parent} for parent in parents],
        "author": author,
        "committer": committer,
        "verification": {"verified": False, "reason": "unsigned", "signature": None, "payload": None, "verified_at": None},
    }

TARGET = {
    "kind": "git",
    "authority": "github.com",
    "resource": "fixture/project",
    "namespace": "refs/heads/state",
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


class GitHubProviderTests(unittest.TestCase):
    def provider(self, transport):
        return GitHubPublicationStorage(
            owner="fixture",
            repository="project",
            token="test-token",
            target=TARGET,
            transport=transport,
            repository_node_id="R_fixture",
        )

    def test_update_refs_uses_exact_expected_old_cas(self):
        def callback(call):
            self.assertEqual(call["method"], "POST")
            self.assertTrue(call["url"].endswith("/graphql"))
            update = call["payload"]["variables"]["input"]["refUpdates"]
            self.assertEqual(update, [{
                "name": "refs/heads/state",
                "beforeOid": A_RAW,
                "afterOid": B_RAW,
                "force": False,
            }])
            self.assertTrue(call["dispatch_uncertain"])
            return HTTPResponse(200, {"data": {"updateRefs": {"clientMutationId": None}}}, {})

        transport = CallbackTransport(callback)
        self.assertTrue(self.provider(transport)._admit_ref(TARGET, A, B_RAW))
        self.assertEqual(len(transport.calls), 1)

    def test_clean_graphql_cas_rejection_is_read_only_conflict_probe(self):
        def callback(call):
            if call["url"].endswith("/graphql"):
                return HTTPResponse(200, {"errors": [{"type": "UNPROCESSABLE", "message": "beforeOid mismatch"}]}, {})
            if "/git/ref/heads/state" in call["url"]:
                return HTTPResponse(200, {"object": {"type": "commit", "sha": C_RAW}}, {})
            raise AssertionError(call)

        transport = CallbackTransport(callback)
        self.assertFalse(self.provider(transport)._admit_ref(TARGET, A, B_RAW))
        self.assertEqual([call["method"] for call in transport.calls], ["POST", "GET"])

    def test_uncertain_update_refs_transport_failure_keeps_dispatched_evidence(self):
        class UncertainTransport:
            def request(self, method, url, *, headers, payload=None, dispatch_uncertain=False):
                self.dispatch_uncertain = dispatch_uncertain
                raise PublicationFault("PROVIDER_UNAVAILABLE", dispatched=dispatch_uncertain)

        transport = UncertainTransport()
        with self.assertRaises(PublicationFault) as caught:
            self.provider(transport)._admit_ref(TARGET, A, B_RAW)
        self.assertEqual(caught.exception.code, "PROVIDER_UNAVAILABLE")
        self.assertTrue(caught.exception.dispatched)
        self.assertTrue(transport.dispatch_uncertain)

    def test_exact_commit_tree_and_blob_reads_preserve_mode_and_message(self):
        message = "ordinary commit\n"
        tree_sha = "d" * 40
        blob = b"#!/bin/sh\n"
        blob_oid = blob_sha(blob)

        def callback(call):
            url = call["url"]
            if f"/git/commits/{A_RAW}" in url:
                return HTTPResponse(200, {
                    "sha": A_RAW,
                    "tree": {"sha": tree_sha},
                    "parents": [{"sha": "f" * 40}],
                    "message": message,
                }, {})
            if f"/git/trees/{tree_sha}" in url:
                return HTTPResponse(200, {"tree": [
                    {"path": "state", "mode": "040000", "type": "tree", "sha": "1" * 40},
                ]}, {})
            if "/git/trees/" + "1" * 40 in url:
                return HTTPResponse(200, {"tree": [
                    {"path": "script", "mode": "100755", "type": "blob", "sha": blob_oid},
                ]}, {})
            if f"/git/blobs/{blob_oid}" in url:
                return HTTPResponse(200, {"sha": blob_oid, "encoding": "base64", "content": base64.b64encode(blob).decode(), "size": len(blob)}, {})
            raise AssertionError(call)

        provider = self.provider(CallbackTransport(callback))
        meta = provider.inspect(TARGET, A)
        self.assertEqual(meta["message"], message)
        self.assertEqual(meta["parents"], ["git:sha1:" + "f" * 40])
        tree = provider.tree(TARGET, A)
        self.assertEqual(tree, {
            "state/script": {"base64": base64.b64encode(b"#!/bin/sh\n").decode(), "mode": "100755"}
        })

    def test_admit_builds_blobs_tree_one_parent_commit_then_single_cas(self):
        tree_raw = "d" * 40
        old_raw = b"old\n"
        old_blob = blob_sha(old_raw)
        new_tree = "2" * 40
        message = "stateOwl publication\n\nStateOwl-Receipt: YQ==\n"
        candidate = {
            "state/work": {"base64": base64.b64encode(b"new\n").decode(), "mode": "100644"},
            "state/new": {"base64": base64.b64encode(b"").decode(), "mode": "100644"},
        }
        created = commit_payload(message, new_tree, [A_RAW], api_message=message[:-1])

        def callback(call):
            url = call["url"]
            if call["method"] == "GET" and f"/git/commits/{A_RAW}" in url:
                return HTTPResponse(200, {"sha": A_RAW, "tree": {"sha": tree_raw}, "parents": [], "message": "base\n"}, {})
            if call["method"] == "GET" and f"/git/trees/{tree_raw}" in url:
                return HTTPResponse(200, {"tree": [{"path": "state", "mode": "040000", "type": "tree", "sha": "3" * 40}]}, {})
            if call["method"] == "GET" and "/git/trees/" + "3" * 40 in url:
                return HTTPResponse(200, {"tree": [{"path": "work", "mode": "100644", "type": "blob", "sha": old_blob}]}, {})
            if call["method"] == "GET" and f"/git/blobs/{old_blob}" in url:
                return HTTPResponse(200, {"sha": old_blob, "encoding": "base64", "content": base64.b64encode(old_raw).decode(), "size": len(old_raw)}, {})
            if call["method"] == "POST" and url.endswith("/git/blobs"):
                raw = base64.b64decode(call["payload"]["content"])
                return HTTPResponse(201, {"sha": blob_sha(raw)}, {})
            if call["method"] == "POST" and url.endswith("/git/trees"):
                self.assertEqual(call["payload"]["base_tree"], tree_raw)
                self.assertEqual({item["path"] for item in call["payload"]["tree"]}, {"state/work", "state/new"})
                return HTTPResponse(201, {"sha": new_tree}, {})
            if call["method"] == "POST" and url.endswith("/git/commits"):
                self.assertEqual(call["payload"], {"message": message, "tree": new_tree, "parents": [A_RAW]})
                return HTTPResponse(201, created, {})
            if url.endswith("/graphql"):
                update = call["payload"]["variables"]["input"]["refUpdates"]
                self.assertEqual(update[0]["beforeOid"], A_RAW)
                self.assertEqual(update[0]["afterOid"], created["sha"])
                return HTTPResponse(200, {"data": {"updateRefs": {"clientMutationId": None}}}, {})
            raise AssertionError(call)

        transport = CallbackTransport(callback)
        result = self.provider(transport).admit(TARGET, A, candidate, message)
        self.assertEqual(result, {"status": "admitted", "snapshot": "git:sha1:" + created["sha"]})
        graphql = [call for call in transport.calls if call["url"].endswith("/graphql")]
        self.assertEqual(len(graphql), 1)

    def test_current_rest_api_version_is_explicit(self):
        transport = CallbackTransport(lambda call: HTTPResponse(200, {"object": {"type": "commit", "sha": A_RAW}}, {}))
        provider = self.provider(transport)
        self.assertEqual(provider.resolve(TARGET), A)
        self.assertEqual(transport.calls[0]["headers"]["X-GitHub-Api-Version"], "2026-03-10")


if __name__ == "__main__":
    unittest.main()

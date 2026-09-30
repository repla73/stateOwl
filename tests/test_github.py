from __future__ import annotations

import base64
import json
import unittest
from unittest.mock import patch

from stateowl.core import StateOwlError, git_blob_oid
from stateowl.github import GitHubStore


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class GitHubStoreTests(unittest.TestCase):
    def test_ref_is_never_cached_but_exact_file_is(self):
        raw = b'{"status":"ok"}\n'
        blob = git_blob_oid(raw)
        responses = [
            {"object": {"sha": "a" * 40}},
            {"object": {"sha": "a" * 40}},
            {"type": "file", "encoding": "base64", "content": base64.b64encode(raw).decode(), "size": len(raw), "sha": blob},
        ]

        def fake_urlopen(request, timeout):
            return Response(json.dumps(responses.pop(0)).encode())

        store = GitHubStore(token="token")
        with patch("stateowl.github.urlopen", fake_urlopen):
            self.assertEqual(store.resolve_ref("acme/project", "refs/heads/main"), "a" * 40)
            self.assertEqual(store.resolve_ref("acme/project", "refs/heads/main"), "a" * 40)
            first = store.read_file("acme/project", "a" * 40, "state.json")
            second = store.read_file("acme/project", "a" * 40, "state.json")
        self.assertEqual(first, second)
        self.assertEqual(responses, [])

    def test_blob_mismatch_is_rejected(self):
        raw = b"hello"
        response = {"type": "file", "encoding": "base64", "content": base64.b64encode(raw).decode(), "size": len(raw), "sha": "b" * 40}

        def fake_urlopen(request, timeout):
            return Response(json.dumps(response).encode())

        with patch("stateowl.github.urlopen", fake_urlopen):
            with self.assertRaises(StateOwlError) as ctx:
                GitHubStore(token="token").read_file("acme/project", "a" * 40, "state.json")
        self.assertEqual(ctx.exception.code, "BLOB_MISMATCH")


if __name__ == "__main__":
    unittest.main()

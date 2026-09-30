from __future__ import annotations

import json
import unittest

from stateowl.core import FileObject, Reader, StateOwlError, git_blob_oid


class MemoryStore:
    def __init__(self, files, *, head="a" * 40):
        self.files = files
        self.head = head
        self.ref_calls = 0
        self.file_calls = []

    def resolve_ref(self, repository, ref):
        self.ref_calls += 1
        return self.head

    def read_file(self, repository, commit, path):
        self.file_calls.append((repository, commit, path))
        raw = self.files[(repository, commit, path)]
        return FileObject(git_blob_oid(raw), raw)


def encoded(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


class ReaderTests(unittest.TestCase):
    def fixture(self):
        repo = "acme/project"
        head = "a" * 40
        router = {
            "schema": "stateowl.router/v1",
            "routes": {"release": {"path": "state/release.json", "select": ["id", "status", "next"]}},
        }
        record = {
            "id": "release",
            "status": "working",
            "next": "verify",
            "large": "x" * 10000,
            "links": {
                "detail": {"path": "state/detail.md", "format": "text"},
                "checks": {"path": "state/checks.json", "format": "json", "select": ["status"]},
            },
        }
        files = {
            (repo, head, ".stateowl/router.json"): encoded(router),
            (repo, head, "state/release.json"): encoded(record),
            (repo, head, "state/detail.md"): b"detail\n",
            (repo, head, "state/checks.json"): encoded({"status": "pass", "noise": "z" * 1000}),
        }
        return repo, head, files

    def test_focused_read_projects_and_proves_sources(self):
        repo, head, files = self.fixture()
        store = MemoryStore(files, head=head)
        result = Reader(store).read(repo, "release")
        self.assertEqual(result["value"], {"id": "release", "status": "working", "next": "verify"})
        self.assertEqual(result["head"]["commit"], head)
        self.assertEqual(result["sources"]["record"]["path"], "state/release.json")
        self.assertRegex(result["sources"]["record"]["blob"], r"^[0-9a-f]{40}$")
        self.assertNotIn("large", json.dumps(result))
        self.assertNotIn("expanded", result)
        self.assertEqual(store.ref_calls, 1)
        self.assertEqual(len(store.file_calls), 2)

    def test_expansion_is_explicit_and_nonrecursive(self):
        repo, head, files = self.fixture()
        store = MemoryStore(files, head=head)
        result = Reader(store).read(repo, "release", expand=["detail", "checks"])
        self.assertEqual(result["expanded"]["detail"]["value"], "detail\n")
        self.assertEqual(result["expanded"]["checks"]["value"], {"status": "pass"})
        self.assertEqual(len(store.file_calls), 4)

    def test_ref_is_fresh_each_read(self):
        repo, head, files = self.fixture()
        store = MemoryStore(files, head=head)
        reader = Reader(store)
        reader.read(repo, "release")
        reader.read(repo, "release")
        self.assertEqual(store.ref_calls, 2)

    def test_expected_head_stops_before_file_reads(self):
        repo, head, files = self.fixture()
        store = MemoryStore(files, head=head)
        with self.assertRaises(StateOwlError) as ctx:
            Reader(store).read(repo, "release", expected_head="b" * 40)
        self.assertEqual(ctx.exception.code, "EXPECTED_HEAD_MISMATCH")
        self.assertEqual(store.file_calls, [])

    def test_duplicate_json_keys_fail(self):
        repo, head, files = self.fixture()
        files[(repo, head, ".stateowl/router.json")] = b'{"schema":"stateowl.router/v1","schema":"x","routes":{}}'
        with self.assertRaises(StateOwlError) as ctx:
            Reader(MemoryStore(files, head=head)).read(repo, "release")
        self.assertEqual(ctx.exception.code, "JSON_DUPLICATE_KEY")

    def test_cross_repo_link_requires_exact_commit(self):
        repo, head, files = self.fixture()
        record = json.loads(files[(repo, head, "state/release.json")])
        record["links"]["detail"] = {"repository": "acme/other", "path": "detail.md", "format": "text"}
        files[(repo, head, "state/release.json")] = encoded(record)
        with self.assertRaises(StateOwlError) as ctx:
            Reader(MemoryStore(files, head=head)).read(repo, "release", expand=["detail"])
        self.assertEqual(ctx.exception.code, "LINK_COMMIT_REQUIRED")


if __name__ == "__main__":
    unittest.main()

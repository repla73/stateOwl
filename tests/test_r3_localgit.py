from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stateowl.r3_localgit import LocalGitPublicationStorage
from stateowl.r3_publish import (
    CompositePublicationProvider,
    PROTOCOL,
    Publisher,
    StaticTrustedProjectValidation,
)

CAPABILITIES = {
    "protocol": PROTOCOL,
    "operations": ["read", "publish", "observe"],
    "formats": ["json", "text", "base64"],
    "features": [],
    "resolvers": [],
    "limits": {
        "request_bytes": 65536, "record_bytes": 16384, "mutation_bytes": 32768,
        "response_bytes": 65536, "records": 32, "expansions": 16, "changes": 32,
        "tag_hops": 8, "reconcile_commits": 16, "json_depth": 64,
    },
    "publication": {
        "continuity": "single_step_required",
        "receipt_format": "stateowl.git-receipt/2",
        "receipt_retention": "reachable_history",
        "authority": "project_validated",
    },
}


def git(repo, *args, input_bytes=None, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run(["git", "-C", str(repo), *args], input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=merged, check=True)
    return result.stdout


def typed(repo, raw):
    alg = git(repo, "rev-parse", "--show-object-format").decode().strip()
    return f"git:{alg}:{raw}"


class LocalGitProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Tester")
        git(self.repo, "config", "user.email", "tester@example.invalid")
        (self.repo / "work.txt").write_text("sentinel\n")
        git(self.repo, "add", "work.txt")
        git(self.repo, "commit", "-q", "-m", "sentinel")
        self.sentinel = git(self.repo, "rev-parse", "HEAD").decode().strip()

        files = {
            "state/work.json": (b'{"v":"A"}\n', "100644"),
            "state/obsolete.txt": (b"old\n", "100644"),
            "state/script": (b"#!/bin/sh\nexit 0\n", "100755"),
            "state/untouched.txt": (b"keep\n", "100644"),
            "state/validation.json": (b'{"enabled":true}\n', "100644"),
        }
        with tempfile.NamedTemporaryFile() as index:
            env = {"GIT_INDEX_FILE": index.name}
            # Replace the temporary file with an empty valid index.
            Path(index.name).unlink(missing_ok=True)
            git(self.repo, "read-tree", "--empty", env=env)
            for path, (contents, mode) in files.items():
                oid = git(self.repo, "hash-object", "-w", "--stdin", input_bytes=contents).decode().strip()
                git(self.repo, "update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}", env=env)
            tree = git(self.repo, "write-tree", env=env).decode().strip()
        commit_env = {
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
        self.base_raw = git(self.repo, "commit-tree", tree, input_bytes=b"base\n", env=commit_env).decode().strip()
        self.target = {
            "kind": "git",
            "authority": "qualification.local",
            "resource": "stateowl/r3",
            "namespace": "refs/heads/stateowl-r3-qualification",
        }
        git(self.repo, "update-ref", self.target["namespace"], self.base_raw)
        self.base = typed(self.repo, self.base_raw)
        self.storage = LocalGitPublicationStorage(self.repo, target=self.target)
        self.trusted = StaticTrustedProjectValidation(
            target=self.target,
            validation="urn:fixture:validation:1",
            validator=lambda old, candidate: old["state/validation.json"] == candidate["state/validation.json"],
        )
        self.provider = CompositePublicationProvider(self.trusted, self.storage)

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, changes):
        return {
            "protocol": PROTOCOL,
            "op": "publish",
            "target": self.target,
            "expected": {"id": self.base},
            "mode": "submit",
            "validation": "urn:fixture:validation:1",
            "changes": changes,
        }

    def run_publish(self, req):
        raw = json.dumps(req, separators=(",", ":")).encode()
        return Publisher(self.provider, CAPABILITIES).run(raw)

    def test_publish_preserves_modes_and_never_touches_worktree(self):
        before_head = git(self.repo, "rev-parse", "HEAD")
        before_index = git(self.repo, "write-tree")
        before_digest = hashlib.sha256((self.repo / "work.txt").read_bytes()).hexdigest()
        result = self.run_publish(self.request([
            {"path": "state/script", "put": {"encoding": "utf8", "data": "#!/bin/sh\necho r3\n"}},
            {"path": "state/new.txt", "put": {"encoding": "utf8", "data": ""}},
        ]))
        self.assertEqual(result["outcome"], "committed")
        tree = self.storage.tree(self.target, result["snapshot"]["id"])
        self.assertEqual(tree["state/script"]["mode"], "100755")
        self.assertEqual(tree["state/new.txt"]["mode"], "100644")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), before_head)
        self.assertEqual(git(self.repo, "write-tree"), before_index)
        self.assertEqual(hashlib.sha256((self.repo / "work.txt").read_bytes()).hexdigest(), before_digest)
        meta = self.storage.inspect(self.target, result["snapshot"]["id"])
        self.assertEqual(meta["parents"], [self.base])
        self.assertTrue(meta["message"].endswith("\n"))

    def test_stale_cas_does_not_overwrite_namespace(self):
        winner_tree = git(self.repo, "rev-parse", f"{self.base_raw}^{{tree}}").decode().strip()
        env = {
            "GIT_AUTHOR_NAME": "Winner",
            "GIT_AUTHOR_EMAIL": "winner@example.invalid",
            "GIT_COMMITTER_NAME": "Winner",
            "GIT_COMMITTER_EMAIL": "winner@example.invalid",
        }
        winner = git(self.repo, "commit-tree", winner_tree, "-p", self.base_raw, input_bytes=b"winner\n", env=env).decode().strip()
        git(self.repo, "update-ref", self.target["namespace"], winner, self.base_raw)
        result = self.run_publish(self.request([{"path": "state/new.txt", "put": {"encoding": "utf8", "data": "x"}}]))
        self.assertEqual((result["outcome"], result["error"]["code"]), ("not_committed", "CONFLICT"))
        self.assertEqual(git(self.repo, "show-ref", "--verify", "--hash", self.target["namespace"]).decode().strip(), winner)


if __name__ == "__main__":
    unittest.main()

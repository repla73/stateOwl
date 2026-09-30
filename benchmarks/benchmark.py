#!/usr/bin/env python3
"""Reproducible context/call benchmark for focused vs naive state retrieval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stateowl.core import FileObject, Reader, git_blob_oid  # noqa: E402


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def encoded(value):
    return compact(value) + b"\n"


class FixtureStore:
    def __init__(self, repository, head, files):
        self.repository = repository
        self.head = head
        self.files = files
        self.calls = 0
        self.bytes_returned = 0

    def resolve_ref(self, repository, ref):
        assert repository == self.repository
        self.calls += 1
        self.bytes_returned += len(self.head.encode())
        return self.head

    def read_file(self, repository, commit, path):
        assert repository == self.repository and commit == self.head
        self.calls += 1
        raw = self.files[path]
        self.bytes_returned += len(raw)
        return FileObject(git_blob_oid(raw), raw)

    def list_files(self, prefix):
        self.calls += 1
        names = sorted(path for path in self.files if path.startswith(prefix))
        self.bytes_returned += len(compact(names))
        return names


def fixture(unrelated):
    repository = "bench/project"
    head = "a" * 40
    router = {
        "schema": "stateowl.router/v1",
        "routes": {"target": {"path": "state/records/target.json", "select": ["id", "status", "next"]}},
    }
    target = {
        "id": "target",
        "status": "working",
        "next": "inspect detail if required",
        "notes": "target-private-noise-" + "x" * 2048,
        "links": {"detail": {"path": "state/details/target.md", "format": "text"}},
    }
    files = {
        ".stateowl/router.json": encoded(router),
        "state/records/target.json": encoded(target),
        "state/details/target.md": ("Detailed target context\n" + "d" * 4096).encode(),
    }
    for i in range(unrelated):
        files[f"state/records/unrelated-{i:05d}.json"] = encoded({
            "id": f"unrelated-{i:05d}",
            "status": "closed",
            "summary": "unrelated history " + "u" * 256,
        })
    return repository, head, files


def focused(unrelated, *, detail=False):
    repository, head, files = fixture(unrelated)
    store = FixtureStore(repository, head, files)
    result = Reader(store).read(repository, "target", expand=["detail"] if detail else [])
    return {
        "strategy": "focused+detail" if detail else "focused",
        "unrelated_records": unrelated,
        "api_calls": store.calls,
        "bytes_returned": store.bytes_returned,
        "model_context_bytes": len(compact(result)),
    }


def naive(unrelated):
    repository, head, files = fixture(unrelated)
    store = FixtureStore(repository, head, files)
    commit = store.resolve_ref(repository, "refs/heads/main")
    router = json.loads(store.read_file(repository, commit, ".stateowl/router.json").content)
    records = []
    for path in store.list_files("state/records/"):
        records.append(json.loads(store.read_file(repository, commit, path).content))
    result = {"router": router, "records": records}
    return {
        "strategy": "naive",
        "unrelated_records": unrelated,
        "api_calls": store.calls,
        "bytes_returned": store.bytes_returned,
        "model_context_bytes": len(compact(result)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = []
    for count in (0, 10, 100, 1000):
        cases.extend([naive(count), focused(count)])
    cases.extend([focused(1000, detail=True)])
    result = {
        "schema": "stateowl.benchmark/v1",
        "fixture": "deterministic in-memory GitHub-like store; counts exact logical API operations and returned payload bytes",
        "cases": cases,
    }
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("| strategy | unrelated | calls | returned bytes | model context bytes |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for case in cases:
        print(f"| {case['strategy']} | {case['unrelated_records']} | {case['api_calls']} | {case['bytes_returned']} | {case['model_context_bytes']} |")


if __name__ == "__main__":
    main()

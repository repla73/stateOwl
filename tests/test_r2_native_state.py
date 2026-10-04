from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stateowl.r2 import R2Reader  # noqa: E402
from stateowl.r2_memory import MemoryReadProvider  # noqa: E402

FIXTURE_SOURCE = "60733bc765e029ebfde6102f5f2c265192cf95d9"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "r2-native-state"
EXPECTED_BLOBS = {
    ".state/current.json": "c6bb6aa0cd35c4d423eee5e58bfe43900e980e37",
    ".state/phases/p01/phase.md": "183675abcc22fde3450564099e6eb007731bcc82",
    ".state/phases/p01/tasks/t001/state.json": "8c1bde3767507cfec0bbc6604c854f909be74e6f",
    ".state/phases/p01/tasks/t001/task.md": "9ecc7b5d3424a4c13a3dbd7e2d2665533fa34420",
    "fixture.json": "f7e7d418bb6ec4b9d53de51ad4ac5031442e1e9f",
    "../../../docs/R2-NATIVE-STATE-FIXTURE.md": "5e8b97264eb006818fd2b0cb71147bed377b318f",
}


class RecordingMemoryProvider(MemoryReadProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_paths: list[str] = []

    def file(self, target, snapshot, path):
        self.file_paths.append(path)
        return super().file(target, snapshot, path)


class SharedNativeStateQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((FIXTURE_ROOT / "fixture.json").read_text())
        ident = cls.fixture["identities"]["opaque"]
        cls.target = ident["target"]
        cls.snapshot = ident["snapshot"]["id"]
        cls.files = {
            item["path"]: (FIXTURE_ROOT / item["path"]).read_bytes()
            for item in cls.fixture["files"]
        }

    def test_shared_fixture_blobs_are_exact(self):
        for relative, expected in EXPECTED_BLOBS.items():
            path = (FIXTURE_ROOT / relative).resolve()
            actual = subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()
            self.assertEqual(actual, expected, relative)
        for item in self.fixture["files"]:
            raw = self.files[item["path"]]
            self.assertEqual(len(raw), item["bytes"])
            self.assertEqual("sha256:" + hashlib.sha256(raw).hexdigest(), item["digest"])
            self.assertEqual("git:sha1:" + EXPECTED_BLOBS[item["path"]], item["git_blob_sha1"])

    def test_all_eight_shared_cases(self):
        self.assertEqual(self.fixture["format"], "stateowl.r2-native-state-fixture/1")
        self.assertFalse(self.fixture["stateowl_router_required"])
        self.assertEqual(len(self.fixture["cases"]), 8)
        self.assertNotIn(".stateowl/router.json", self.files)

        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                request = case["request"]
                self.assertNotIn("resolver", request)
                self.assertTrue(all("route" not in rec for rec in request["records"]))

                provider = RecordingMemoryProvider(
                    self.target,
                    {self.snapshot: {"type": "snapshot", "files": self.files}},
                    head=self.snapshot,
                    algorithm=None,
                )
                reader = R2Reader(provider)
                actual = reader.read(request)

                self.assertEqual(actual, case["expected"])
                self.assertEqual(
                    reader.last_instrumentation.resolve,
                    case["trace"]["mutable_ref_resolutions"],
                )
                self.assertEqual(provider.file_paths, case["trace"]["file_reads"])
                self.assertNotIn(".stateowl/router.json", provider.file_paths)
                if "all_records_snapshot" in case["trace"]:
                    self.assertEqual(actual["snapshot"]["id"], case["trace"]["all_records_snapshot"])

                if case["id"] == "exact-read":
                    self.assertEqual(reader.last_instrumentation.resolve, 0)
                if case["id"] == "current-read":
                    self.assertEqual(reader.last_instrumentation.resolve, 1)


if __name__ == "__main__":
    unittest.main()

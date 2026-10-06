from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
A = "git:sha1:" + "a" * 40
B = "git:sha1:" + "b" * 40
TARGET = {"kind": "git", "authority": "github.com", "resource": "fixture/project", "namespace": "refs/heads/state"}
CAPABILITIES = {
    "protocol": "stateowl/0.2-draft.3",
    "operations": ["read", "publish", "observe"],
    "formats": ["json", "text", "base64"],
    "features": [],
    "resolvers": [],
    "limits": {"request_bytes": 65536, "record_bytes": 16384, "mutation_bytes": 32768, "response_bytes": 65536, "records": 32, "expansions": 16, "changes": 32, "tag_hops": 8, "reconcile_commits": 16, "json_depth": 64},
    "publication": {"continuity": "single_step_required", "receipt_format": "stateowl.git-receipt/2", "receipt_retention": "reachable_history", "authority": "project_validated"},
}


class AdapterTests(unittest.TestCase):
    def test_jsonl_adapter_uses_real_publisher(self):
        req = {
            "protocol": "stateowl/0.2-draft.3",
            "op": "publish",
            "target": TARGET,
            "expected": {"id": A},
            "mode": "submit",
            "validation": "urn:fixture:validation:1",
            "changes": [{"path": "state/new", "put": {"encoding": "utf8", "data": "x"}}],
        }
        old = {"state/keep": {"base64": base64.b64encode(b"keep\n").decode(), "mode": "100644"}}
        head = A
        objects = {A: {"type": "commit", "parents": [], "message": "base\n", "files": old}}
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "qualification" / "r3_python_publish_adapter.py")],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            proc.stdin.write(json.dumps({
                "type": "start",
                "request_base64": base64.b64encode(json.dumps(req, separators=(",", ":")).encode()).decode(),
                "capabilities": CAPABILITIES,
            }) + "\n")
            proc.stdin.flush()
            for _ in range(64):
                event = json.loads(proc.stdout.readline())
                if event["type"] == "result":
                    self.assertEqual(event["response"]["outcome"], "committed")
                    self.assertEqual(event["response"]["snapshot"], {"id": B})
                    break
                self.assertEqual(event["type"], "call")
                method = event["method"]
                args = event["args"]
                if method == "access":
                    value = {"validation": "urn:fixture:validation:1", "validator_available": True, "project_authorized": True, "continuity": "intact", "auth_scope": "fixture"}
                elif method == "authorize":
                    value = True
                elif method == "inspect":
                    obj = objects[args["snapshot"]]
                    value = {"id": args["snapshot"], "type": obj["type"], "parents": obj["parents"], "message": obj["message"]}
                elif method == "tree":
                    value = objects[args["snapshot"]]["files"]
                elif method == "validate":
                    value = True
                elif method == "admit":
                    self.assertEqual(head, args["expected"])
                    objects[B] = {"type": "commit", "parents": [A], "message": args["message"], "files": args["candidate"]}
                    head = B
                    value = {"status": "admitted", "snapshot": B}
                elif method == "resolve":
                    value = head
                else:
                    self.fail(method)
                proc.stdin.write(json.dumps({"type": "return", "id": event["id"], "value": value}) + "\n")
                proc.stdin.flush()
            else:
                self.fail("adapter did not return a result")
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)
            proc.stdout.close()
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()

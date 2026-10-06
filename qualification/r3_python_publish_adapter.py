#!/usr/bin/env python3
"""Black-box R3 publish adapter for the shared stateowl.fixtures/3 driver.

This executable imports the real Python publisher only. Provider state, fault
scripts, expected answers and case IDs remain owned by check_fixtures.py.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stateowl.r3_publish import PublicationFault, Publisher  # noqa: E402


class DriverProvider:
    def __init__(self) -> None:
        self.next_id = 0

    def call(self, method: str, **args: Any) -> Any:
        call_id = self.next_id
        self.next_id += 1
        print(
            json.dumps({"type": "call", "id": call_id, "method": method, "args": args}, separators=(",", ":")),
            flush=True,
        )
        line = sys.stdin.readline()
        if not line:
            raise RuntimeError("fixture driver closed")
        event = json.loads(line)
        if event.get("type") != "return" or event.get("id") != call_id:
            raise RuntimeError("invalid fixture driver return")
        if "fault" in event:
            fault = event["fault"]
            raise PublicationFault(fault["code"], dispatched=bool(fault.get("dispatched", False)))
        if set(event) != {"type", "id", "value"}:
            raise RuntimeError("invalid fixture driver return shape")
        return event["value"]


def main() -> None:
    for line in sys.stdin:
        event = json.loads(line)
        if event.get("type") != "start" or set(event) != {"type", "request_base64", "capabilities"}:
            raise RuntimeError("expected start event")
        raw = base64.b64decode(event["request_base64"], validate=True)
        response = Publisher(DriverProvider(), event["capabilities"]).run(raw)
        print(json.dumps({"type": "result", "response": response}, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

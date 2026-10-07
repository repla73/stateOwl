from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


_ID = re.compile(r"[A-Za-z0-9._-]+\Z")


class EffectTargetConflict(RuntimeError):
    pass


class LocalEffectTarget:
    """Disposable R5 qualification target with queryable idempotency by effect ID."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, effect_id: str) -> Path:
        if not isinstance(effect_id, str) or not _ID.fullmatch(effect_id):
            raise ValueError("invalid effect id")
        return self.root / f"{effect_id}.json"

    @staticmethod
    def _digest(payload: bytes) -> str:
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def query(self, effect_id: str) -> dict:
        path = self._path(effect_id)
        if not path.exists():
            return {"status": "absent", "effect_id": effect_id}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {"status": "unknown", "effect_id": effect_id}
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "effect_id", "payload_digest", "status"}
            or value.get("schema") != "stateowl.r5-local-effect/1"
            or value.get("effect_id") != effect_id
            or value.get("status") != "complete"
            or not isinstance(value.get("payload_digest"), str)
        ):
            return {"status": "unknown", "effect_id": effect_id}
        return value

    def perform(self, effect_id: str, payload: bytes) -> dict:
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        destination = self._path(effect_id)
        wanted = {
            "schema": "stateowl.r5-local-effect/1",
            "effect_id": effect_id,
            "payload_digest": self._digest(payload),
            "status": "complete",
        }
        encoded = (json.dumps(wanted, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

        with tempfile.NamedTemporaryFile(dir=self.root, prefix=".stateowl-r5-effect-", delete=False) as handle:
            temp = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            try:
                os.link(temp, destination)
            except FileExistsError:
                observed = self.query(effect_id)
                if observed.get("status") != "complete" or observed.get("payload_digest") != wanted["payload_digest"]:
                    raise EffectTargetConflict(effect_id)
                return {**observed, "duplicate_suppressed": True}
            observed = self.query(effect_id)
            if observed.get("status") != "complete" or observed.get("payload_digest") != wanted["payload_digest"]:
                raise EffectTargetConflict(effect_id)
            return {**observed, "duplicate_suppressed": False}
        finally:
            temp.unlink(missing_ok=True)

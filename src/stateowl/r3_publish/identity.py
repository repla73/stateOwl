from __future__ import annotations

import base64
import copy
import json
import re
from typing import Any, Mapping

from .types import PROTOCOL, MAX_SAFE, _RETRY, _RECEIPT, PublicationFault
from .codec import _bytes_value, _canonical_base64, _collision, _digest, restricted_jcs
from .validation import _validate_identity

def publication_identity(request: Mapping[str, Any]) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    for change in sorted(request["changes"], key=lambda item: item["path"].encode("utf-8")):
        if "put" in change:
            raw = _bytes_value(change["put"])
            changes.append(
                {
                    "path": change["path"],
                    "put": {"digest": _digest(raw), "bytes": len(raw)},
                }
            )
        else:
            changes.append({"path": change["path"], "delete": True})
    return {
        "protocol": request["protocol"],
        "target": copy.deepcopy(request["target"]),
        "expected": copy.deepcopy(request["expected"]),
        "changes": changes,
        "validation": request["validation"],
    }


def request_digest(request: Mapping[str, Any]) -> str:
    return _digest(restricted_jcs(publication_identity(request)))


def receipt_message(request: Mapping[str, Any], *, heading: bool = True) -> str:
    payload = base64.b64encode(restricted_jcs(publication_identity(request))).decode("ascii")
    prefix = "stateOwl publication\n\n" if heading else ""
    return f"{prefix}StateOwl-Receipt: {payload}\n"


def parse_receipt(message: Any) -> dict[str, Any] | None:
    marker = "StateOwl-Receipt:"
    if not isinstance(message, str):
        raise PublicationFault("INVALID_SOURCE")
    if marker not in message:
        return None
    match = _RECEIPT.fullmatch(message)
    if match is None:
        raise PublicationFault("INVALID_SOURCE")
    raw = _canonical_base64(match.group(1), error="INVALID_SOURCE")
    try:
        value = _strict_identity_json(raw)
        if not _validate_identity(value):
            raise PublicationFault("INVALID_SOURCE")
        if restricted_jcs(value, error="INVALID_SOURCE") != raw:
            raise PublicationFault("INVALID_SOURCE")
        return value
    except PublicationFault as exc:
        if exc.code == "LIMIT_EXCEEDED":
            raise PublicationFault("INVALID_SOURCE") from None
        raise


def _strict_identity_json(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError

        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for key, value in items:
                if key in out:
                    raise ValueError
                out[key] = value
            return out

        def integer(text_value: str) -> int:
            if text_value.startswith("-"):
                raise ValueError
            value = int(text_value)
            if value > MAX_SAFE:
                raise ValueError
            return value

        def no_float(_: str) -> Any:
            raise ValueError

        value = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_int=integer,
            parse_float=no_float,
            parse_constant=no_float,
        )
        # Encode all strings/keys strictly to reject unpaired surrogates.
        def verify_strings(item: Any) -> None:
            if isinstance(item, str):
                item.encode("utf-8")
            elif isinstance(item, list):
                for child in item:
                    verify_strings(child)
            elif isinstance(item, dict):
                for key, child in item.items():
                    key.encode("utf-8")
                    verify_strings(child)

        verify_strings(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise PublicationFault("INVALID_SOURCE") from None


def _error(code: str, *, uncertain: bool = False) -> dict[str, str]:
    return {"code": code, "retry": "reconcile" if uncertain else _RETRY[code]}


def _snapshot(snapshot_id: str) -> dict[str, str]:
    return {"id": snapshot_id}


def build_candidate(request: Mapping[str, Any], old: Mapping[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(old))
    for change in sorted(request["changes"], key=lambda item: item["path"].encode("utf-8")):
        path = change["path"]
        existing = old.get(path)
        if existing is not None and existing.get("mode") not in {"100644", "100755"}:
            raise PublicationFault("INVALID_SOURCE")
        if "delete" in change:
            if existing is None:
                raise PublicationFault("NOT_FOUND")
            del candidate[path]
        else:
            raw = _bytes_value(change["put"])
            candidate[path] = {
                "base64": base64.b64encode(raw).decode("ascii"),
                "mode": existing["mode"] if existing is not None else "100644",
            }
    if _collision(list(candidate)):
        raise PublicationFault("INVALID_SOURCE")
    if dict(old) == candidate:
        raise PublicationFault("NO_CHANGE")
    return candidate

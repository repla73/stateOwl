from __future__ import annotations

from decimal import Decimal
import json
import math
import re
from typing import Any

from ..r2_jcs import _float_text
from .types import PROTOCOL, MAX_SAFE, PublicationFault
from .codec import _binding_valid, _bytes_value, _collision, _path_valid, _ref_valid

def _strict_request_json(raw: bytes, depth: int) -> Any:
    try:
        if raw.startswith(b"\xef\xbb\xbf"):
            raise PublicationFault("INVALID_REQUEST")
        text = raw.decode("utf-8")
        level = 0
        quoted = False
        escaped = False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                level += 1
                if level > depth:
                    raise PublicationFault("LIMIT_EXCEEDED")
            elif char in "]}":
                level -= 1

        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for key, value in items:
                if key in out:
                    raise PublicationFault("INVALID_REQUEST")
                out[key] = value
            return out

        def number(token: str) -> int | float:
            value = Decimal(token)
            if value.is_zero() and value.is_signed():
                raise PublicationFault("INVALID_REQUEST")
            if value == value.to_integral_value():
                if abs(value) > MAX_SAFE:
                    raise PublicationFault("NUMBER_UNREPRESENTABLE")
                return int(value)
            binary64 = float(value)
            if not math.isfinite(binary64) or Decimal(_float_text(binary64)) != value:
                raise PublicationFault("NUMBER_UNREPRESENTABLE")
            return binary64

        def invalid_constant(_: str) -> Any:
            raise PublicationFault("INVALID_REQUEST")

        value = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_int=number,
            parse_float=number,
            parse_constant=invalid_constant,
        )
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
    except PublicationFault:
        raise
    except (UnicodeError, ValueError, OverflowError, RecursionError):
        raise PublicationFault("INVALID_REQUEST") from None


def _validate_target(target: Any) -> bool:
    return (
        isinstance(target, dict)
        and set(target) == {"kind", "authority", "resource", "namespace"}
        and all(isinstance(target[name], str) and target[name] for name in target)
    )


def _validate_snapshot(snapshot: Any) -> bool:
    return (
        isinstance(snapshot, dict)
        and set(snapshot) == {"id"}
        and isinstance(snapshot.get("id"), str)
        and bool(snapshot["id"])
    )


def _validate_publish_request(request: Any) -> bool:
    if not isinstance(request, dict):
        return False
    if set(request) != {"protocol", "op", "target", "expected", "mode", "validation", "changes"}:
        return False
    if request.get("op") != "publish" or not _validate_target(request.get("target")):
        return False
    if not _validate_snapshot(request.get("expected")):
        return False
    if request.get("mode") not in {"submit", "reconcile"}:
        return False
    validation = request.get("validation")
    if validation is not None and not _binding_valid(validation):
        return False
    changes = request.get("changes")
    if not isinstance(changes, list) or not changes:
        return False
    for change in changes:
        if not isinstance(change, dict) or not _path_valid(change.get("path")):
            return False
        if set(change) == {"path", "delete"}:
            if change["delete"] is not True:
                return False
        elif set(change) == {"path", "put"}:
            put = change["put"]
            if not isinstance(put, dict) or set(put) != {"encoding", "data"}:
                return False
            if put.get("encoding") not in {"utf8", "base64"} or not isinstance(put.get("data"), str):
                return False
        else:
            return False
    return True


def _validate_identity(identity: Any) -> bool:
    if not isinstance(identity, dict) or set(identity) != {"protocol", "target", "expected", "changes", "validation"}:
        return False
    if identity.get("protocol") != PROTOCOL or not _validate_target(identity.get("target")) or not _validate_snapshot(identity.get("expected")):
        return False
    validation = identity.get("validation")
    if validation is not None and not _binding_valid(validation):
        return False
    changes = identity.get("changes")
    if not isinstance(changes, list) or not changes:
        return False
    paths: list[str] = []
    for change in changes:
        if not isinstance(change, dict) or not _path_valid(change.get("path")):
            return False
        paths.append(change["path"])
        if set(change) == {"path", "delete"}:
            if change["delete"] is not True:
                return False
        elif set(change) == {"path", "put"}:
            put = change["put"]
            if not isinstance(put, dict) or set(put) != {"digest", "bytes"}:
                return False
            if not isinstance(put.get("digest"), str) or re.fullmatch(r"sha256:[0-9a-f]{64}", put["digest"]) is None:
                return False
            if type(put.get("bytes")) is not int or not 0 <= put["bytes"] <= MAX_SAFE:
                return False
        else:
            return False
    return paths == sorted(set(paths), key=lambda value: value.encode("utf-8"))

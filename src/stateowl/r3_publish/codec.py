from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Mapping

from .types import MAX_SAFE, PublicationFault

def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical_base64(text: str, *, error: str = "INVALID_REQUEST") -> bytes:
    try:
        raw = base64.b64decode(text, validate=True)
        if base64.b64encode(raw).decode("ascii") != text:
            raise ValueError
        return raw
    except (ValueError, TypeError, UnicodeError):
        raise PublicationFault(error) from None


def _utf16_sort_key(value: str) -> bytes:
    try:
        return value.encode("utf-16be")
    except UnicodeError:
        raise PublicationFault("INVALID_REQUEST") from None


def _jcs_string(value: str, *, error: str = "INVALID_REQUEST") -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise PublicationFault(error) from None


def restricted_jcs(value: Any, *, error: str = "INVALID_REQUEST") -> bytes:
    """RFC 8785 for the closed publication/result value domain (no floats)."""

    if value is None:
        return b"null"
    if type(value) is bool:
        return b"true" if value else b"false"
    if type(value) is int:
        if not -MAX_SAFE <= value <= MAX_SAFE:
            raise PublicationFault(error)
        return str(value).encode("ascii")
    if isinstance(value, str):
        return _jcs_string(value, error=error)
    if isinstance(value, list):
        return b"[" + b",".join(restricted_jcs(x, error=error) for x in value) + b"]"
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise PublicationFault(error)
        try:
            keys = sorted(value, key=lambda key: key.encode("utf-16be"))
        except UnicodeError:
            raise PublicationFault(error) from None
        return b"{" + b",".join(
            _jcs_string(key, error=error)
            + b":"
            + restricted_jcs(value[key], error=error)
            for key in keys
        ) + b"}"
    raise PublicationFault(error)


def _path_valid(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith("/")
        and not value.endswith("/")
        and "\\" not in value
        and all(ord(char) >= 32 and ord(char) != 127 for char in value)
        and all(part not in ("", ".", "..") for part in value.split("/"))
    )


def _binding_valid(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 256
        and all(33 <= ord(char) <= 126 for char in value)
    )


def _ref_valid(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith(("refs/heads/", "refs/tags/")):
        return False
    if value.endswith(("/", ".")) or ".." in value or "@{" in value:
        return False
    if any(ord(char) < 33 or ord(char) == 127 or char in "~^:?*[\\" for char in value):
        return False
    return all(part and not part.startswith(".") and not part.endswith(".lock") for part in value.split("/"))


def _collision(paths: list[str]) -> bool:
    names = set(paths)
    if len(names) != len(paths):
        return True
    return any(
        "/".join(path.split("/")[:index]) in names
        for path in paths
        for index in range(1, len(path.split("/")))
    )


def _bytes_value(put: Mapping[str, Any]) -> bytes:
    if set(put) != {"encoding", "data"}:
        raise PublicationFault("INVALID_REQUEST")
    if put.get("encoding") == "base64":
        return _canonical_base64(put.get("data"))
    if put.get("encoding") != "utf8" or not isinstance(put.get("data"), str):
        raise PublicationFault("INVALID_REQUEST")
    try:
        return put["data"].encode("utf-8")
    except UnicodeError:
        raise PublicationFault("INVALID_REQUEST") from None

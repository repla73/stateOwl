from __future__ import annotations

import json
import math
from typing import Any

from .r2_base import MAX_SAFE, ReadFault


def _string_bytes(value: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, UnicodeError, ValueError):
        raise ReadFault("INVALID_SOURCE") from None


def _float_text(value: float) -> str:
    if not math.isfinite(value):
        raise ReadFault("INVALID_SOURCE")
    if value == 0:
        return "0"
    if value < 0:
        return "-" + _float_text(-value)

    text = str(value)
    exponent = 0
    exp_text = ""
    if "e" in text:
        significand, raw_exp = text.split("e", 1)
        exponent = int(raw_exp)
        text = significand
        exp_text = ("e+" if exponent >= 0 else "e-") + str(abs(exponent))

    if "." in text:
        first, last = text.split(".", 1)
    else:
        first, last = text, ""
    if last == "0":
        last = ""

    digits = first + last
    if 0 < exponent < 21:
        decimal_pos = 1 + exponent
        if decimal_pos >= len(digits):
            return digits + "0" * (decimal_pos - len(digits))
        return digits[:decimal_pos] + "." + digits[decimal_pos:]
    if -7 < exponent < 0:
        return "0." + "0" * (-exponent - 1) + digits

    if exp_text:
        if last:
            return first + "." + last + exp_text
        return first + exp_text
    return first + ("." + last if last else "")


def _emit(value: Any, out: bytearray) -> None:
    if value is None:
        out.extend(b"null")
    elif type(value) is bool:
        out.extend(b"true" if value else b"false")
    elif type(value) is int:
        if not -MAX_SAFE <= value <= MAX_SAFE:
            raise ReadFault("INVALID_SOURCE")
        out.extend(str(value).encode("ascii"))
    elif type(value) is float:
        out.extend(_float_text(value).encode("ascii"))
    elif isinstance(value, str):
        out.extend(_string_bytes(value))
    elif isinstance(value, list):
        out.append(ord("["))
        for i, item in enumerate(value):
            if i:
                out.append(ord(","))
            _emit(item, out)
        out.append(ord("]"))
    elif isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ReadFault("INVALID_SOURCE")
        try:
            keys = sorted(value, key=lambda k: k.encode("utf-16be"))
        except UnicodeError:
            raise ReadFault("INVALID_SOURCE") from None
        out.append(ord("{"))
        for i, key in enumerate(keys):
            if i:
                out.append(ord(","))
            out.extend(_string_bytes(key))
            out.append(ord(":"))
            _emit(value[key], out)
        out.append(ord("}"))
    else:
        raise ReadFault("INVALID_SOURCE")


def jcs_bytes(value: Any) -> bytes:
    """Serialize a protocol semantic value as RFC 8785/JCS UTF-8 bytes."""
    out = bytearray()
    _emit(value, out)
    return bytes(out)

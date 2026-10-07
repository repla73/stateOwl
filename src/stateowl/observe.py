from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from .r2 import PROTOCOL, ReadFault, ReadInstrumentation, digest, fail, ref_valid, request_valid
from .r2_jcs import jcs_bytes
from .r2_reader import CounterProvider, DEFAULT_READ_CAPABILITIES
from .r2_session_records import Session


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class ObserveTokenService(Protocol):
    def check(self, token: str, scope: Mapping[str, Any]) -> str: ...
    def issue(self, scope: Mapping[str, Any], fingerprint: str) -> str: ...


class HMACTokenService:
    """Opaque, restart-stable observe tokens backed by a caller-owned secret."""

    PREFIX = "stateowl-observe-v1"

    def __init__(
        self,
        secret: bytes,
        *,
        ttl_seconds: int = 3600,
        clock: Callable[[], float] = time.time,
    ):
        if not isinstance(secret, bytes) or not secret:
            raise ValueError("secret must be non-empty bytes")
        if type(ttl_seconds) is not int or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        self._secret = secret
        self._ttl = ttl_seconds
        self._clock = clock

    def issue(self, scope: Mapping[str, Any], fingerprint: str) -> str:
        if not isinstance(fingerprint, str) or not fingerprint:
            raise ReadFault("TOKEN_INVALID")
        payload = {
            "v": 1,
            "scope": copy.deepcopy(dict(scope)),
            "fingerprint": fingerprint,
            "expires": int(self._clock()) + self._ttl,
        }
        raw = jcs_bytes(payload)
        signature = hmac.new(self._secret, raw, hashlib.sha256).digest()
        return f"{self.PREFIX}.{_b64url_encode(raw)}.{_b64url_encode(signature)}"

    def check(self, token: str, scope: Mapping[str, Any]) -> str:
        try:
            prefix, payload_text, signature_text = token.split(".", 2)
            if prefix != self.PREFIX:
                raise ValueError
            raw = _b64url_decode(payload_text)
            supplied = _b64url_decode(signature_text)
            expected = hmac.new(self._secret, raw, hashlib.sha256).digest()
            if not hmac.compare_digest(supplied, expected):
                raise ValueError
            payload = json.loads(raw.decode("utf-8"))
            if (
                not isinstance(payload, dict)
                or set(payload) != {"v", "scope", "fingerprint", "expires"}
                or payload["v"] != 1
                or payload["scope"] != dict(scope)
                or not isinstance(payload["fingerprint"], str)
                or not payload["fingerprint"]
                or type(payload["expires"]) is not int
                or int(self._clock()) >= payload["expires"]
            ):
                raise ValueError
            return payload["fingerprint"]
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError, binascii.Error):
            raise ReadFault("TOKEN_INVALID") from None


@dataclass(frozen=True)
class ObserveInstrumentation:
    access: int = 0
    resolve: int = 0
    inspect: int = 0
    file: int = 0


def _observe_request_valid(request: Any) -> bool:
    if not isinstance(request, dict):
        return False
    if set(request) - {"protocol", "op", "target", "records", "resolver", "token"}:
        return False
    if set(request) < {"protocol", "op", "target"} or request.get("op") != "observe":
        return False
    target = request.get("target")
    if (
        not isinstance(target, dict)
        or set(target) != {"kind", "authority", "resource", "namespace"}
        or any(not isinstance(target.get(key), str) or not target[key] for key in target)
    ):
        return False
    token = request.get("token")
    if token is not None and (not isinstance(token, str) or not token):
        return False
    if "records" not in request:
        return "resolver" not in request
    read_request = {
        "protocol": request["protocol"],
        "op": "read",
        "target": target,
        "at": {"current": True},
        "records": request["records"],
    }
    if "resolver" in request:
        read_request["resolver"] = request["resolver"]
    return request_valid(read_request)


def _normalized_scope(request: Mapping[str, Any], auth_scope: str) -> dict[str, Any]:
    scope: dict[str, Any] = {
        "target": copy.deepcopy(request["target"]),
        "records": copy.deepcopy(request.get("records", [])),
        "auth_scope": auth_scope,
    }
    if "resolver" in request:
        scope["resolver"] = request["resolver"]
    for record in scope["records"]:
        record.setdefault("optional", False)
        record.setdefault("expand", [])
    return scope


class _DependencyProvider:
    def __init__(self, provider: Any, root_target: Mapping[str, Any], root_snapshot: str):
        self.provider = provider
        self.root_target = dict(root_target)
        self.root_snapshot = root_snapshot
        self.dependencies: list[dict[str, Any]] = []

    def access(self, target, operation):
        return self.provider.access(target, operation)

    def resolve(self, target):
        return self.provider.resolve(target)

    def inspect(self, target, snapshot):
        return self.provider.inspect(target, snapshot)

    def file(self, target, snapshot, path):
        external = dict(target) != self.root_target or snapshot != self.root_snapshot
        try:
            item = self.provider.file(target, snapshot, path)
        except ReadFault as exc:
            if exc.code == "NOT_FOUND":
                dependency = {
                    "target": copy.deepcopy(dict(target)),
                    "path": path,
                    "absent": True,
                }
                if external:
                    dependency["snapshot"] = {"id": snapshot}
                self.dependencies.append(dependency)
            raise
        dependency = {
            "target": copy.deepcopy(dict(target)),
            "path": path,
            "digest": item.get("digest"),
            "mode": item.get("mode"),
        }
        if external:
            dependency["snapshot"] = {"id": snapshot}
        self.dependencies.append(dependency)
        return item


DEFAULT_OBSERVE_CAPABILITIES = copy.deepcopy(DEFAULT_READ_CAPABILITIES)
DEFAULT_OBSERVE_CAPABILITIES["operations"] = ["observe"]


class Observer:
    """Production stateOwl observe implementation over an existing read provider."""

    def __init__(
        self,
        provider: Any,
        token_service: ObserveTokenService,
        capabilities: Mapping[str, Any] = DEFAULT_OBSERVE_CAPABILITIES,
    ):
        self.provider = provider
        self.tokens = token_service
        self.cap = copy.deepcopy(dict(capabilities))
        self.last_instrumentation = ObserveInstrumentation()

    def observe(self, request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            raw = json.dumps(
                request,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            return fail("INVALID_REQUEST", "unknown")
        return self.observe_bytes(raw)

    def observe_bytes(self, raw: bytes) -> dict[str, Any]:
        counted = CounterProvider(self.provider)
        try:
            limits = self.cap.get("limits", {})
            request_limit = limits.get("request_bytes")
            depth_limit = limits.get("json_depth")
            if type(request_limit) is not int or request_limit <= 0 or type(depth_limit) is not int or depth_limit <= 0:
                raise ReadFault("UNSUPPORTED_CAPABILITY")
            if len(raw) > request_limit:
                raise ReadFault("LIMIT_EXCEEDED")
            from .r2_json import strict_json

            request = strict_json(raw, source=False, depth=depth_limit)
            if not isinstance(request, dict) or not isinstance(request.get("protocol"), str):
                raise ReadFault("INVALID_REQUEST")
            if request["protocol"] != PROTOCOL:
                raise ReadFault("UNSUPPORTED_VERSION")
            if not _observe_request_valid(request):
                raise ReadFault("INVALID_REQUEST")
            if request["target"]["kind"] == "git" and not ref_valid(request["target"]["namespace"]):
                raise ReadFault("INVALID_REQUEST")
            records = request.get("records", [])
            if len({record["key"] for record in records}) != len(records):
                raise ReadFault("INVALID_REQUEST")
            record_limit = limits.get("records")
            expansion_limit = limits.get("expansions")
            if type(record_limit) is not int or record_limit <= 0 or type(expansion_limit) is not int or expansion_limit <= 0:
                raise ReadFault("UNSUPPORTED_CAPABILITY")
            if len(records) > record_limit or sum(len(record.get("expand", [])) for record in records) > expansion_limit:
                raise ReadFault("LIMIT_EXCEEDED")
        except ReadFault as exc:
            return fail(exc.code, "unknown")

        try:
            if "observe" not in self.cap.get("operations", []):
                raise ReadFault("UNSUPPORTED_CAPABILITY")
            for record in records:
                if record.get("format", "json") not in self.cap.get("formats", []):
                    raise ReadFault("UNSUPPORTED_CAPABILITY")
            if any("route" in record for record in records) and "routes" not in self.cap.get("features", []):
                raise ReadFault("UNSUPPORTED_CAPABILITY")
            if any(record.get("expand") for record in records) and "expand" not in self.cap.get("features", []):
                raise ReadFault("UNSUPPORTED_CAPABILITY")
            if "resolver" in request and request["resolver"] not in self.cap.get("resolvers", []):
                raise ReadFault("UNSUPPORTED_CAPABILITY")

            access = counted.access(request["target"], "observe")
            auth_scope = access.get("auth_scope") if isinstance(access, Mapping) else None
            if not isinstance(auth_scope, str) or not auth_scope:
                raise ReadFault("INVALID_SOURCE")
            scope = _normalized_scope(request, auth_scope)
            prior = self.tokens.check(request["token"], scope) if "token" in request else None
            continuity = access.get("continuity") if isinstance(access, Mapping) else None
            if continuity not in (None, "intact"):
                raise ReadFault("NAMESPACE_DISCONTINUITY")

            root_session = Session(counted, self.cap)
            snapshot = root_session.root(request["target"], {"current": True})

            if records:
                dependencies = _DependencyProvider(counted, request["target"], snapshot)
                read_request = {
                    "protocol": PROTOCOL,
                    "op": "read",
                    "target": copy.deepcopy(request["target"]),
                    "at": {"snapshot": {"id": snapshot}},
                    "records": copy.deepcopy(records),
                }
                if "resolver" in request:
                    read_request["resolver"] = request["resolver"]
                Session(dependencies, self.cap).read_op(read_request)
                fingerprint = digest(jcs_bytes(dependencies.dependencies))
            else:
                fingerprint = snapshot

            status = "baseline" if prior is None else "unchanged" if prior == fingerprint else "changed"
            token = self.tokens.issue(scope, fingerprint)
            result = {
                "protocol": PROTOCOL,
                "op": "observe",
                "status": status,
                "target": copy.deepcopy(request["target"]),
                "snapshot": {"id": snapshot},
                "token": token,
            }
            response_limit = limits.get("response_bytes")
            if type(response_limit) is not int or response_limit <= 0:
                raise ReadFault("UNSUPPORTED_CAPABILITY")
            if len(jcs_bytes(result)) > response_limit:
                raise ReadFault("LIMIT_EXCEEDED")
            return result
        except ReadFault as exc:
            return fail(exc.code, "observe")
        finally:
            self.last_instrumentation = ObserveInstrumentation(
                **{key: counted.counts[key] for key in ("access", "resolve", "inspect", "file")}
            )

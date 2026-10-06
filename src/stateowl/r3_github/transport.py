from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Protocol
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from ..r3_publish import PublicationFault


_TYPED = re.compile(r"git:(sha1):([0-9a-f]{40})\Z|git:(sha256):([0-9a-f]{64})\Z")


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    payload: Any
    headers: Mapping[str, str]


class GitHubTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None = None,
        dispatch_uncertain: bool = False,
    ) -> HTTPResponse: ...


class UrllibGitHubTransport:
    """Small stdlib transport; credentials remain caller-supplied."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None = None,
        dispatch_uncertain: bool = False,
    ) -> HTTPResponse:
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        req = urlrequest.Request(url, data=data, method=method, headers=dict(headers))
        try:
            with urlrequest.urlopen(req) as response:
                body = response.read()
                decoded = json.loads(body.decode("utf-8")) if body else None
                return HTTPResponse(response.status, decoded, dict(response.headers.items()))
        except urlerror.HTTPError as exc:
            try:
                body = exc.read()
                decoded = json.loads(body.decode("utf-8")) if body else None
            except Exception:
                decoded = None
            return HTTPResponse(exc.code, decoded, dict(exc.headers.items()) if exc.headers else {})
        except (urlerror.URLError, OSError, TimeoutError) as exc:
            raise PublicationFault("PROVIDER_UNAVAILABLE", dispatched=dispatch_uncertain) from exc

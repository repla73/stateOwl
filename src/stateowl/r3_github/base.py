from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Mapping
from urllib import parse as urlparse

from ..r3_publish import PublicationFault
from .transport import GitHubTransport, UrllibGitHubTransport

_TYPED = re.compile(r"git:(sha1):([0-9a-f]{40})\Z|git:(sha256):([0-9a-f]{64})\Z")

class GitHubBase:
    """GitHub Git-database publisher with atomic expected-old ref admission.

    Blobs, tree and one-parent commit are constructed with Git database REST
    APIs. Admission uses GraphQL `updateRefs` with `beforeOid` and `afterOid`.
    This supplies the per-write expected-old CAS only; it does not claim G5
    repository-wide single-step policy enforcement.
    """

    def __init__(
        self,
        *,
        owner: str,
        repository: str,
        token: str,
        target: Mapping[str, Any],
        transport: GitHubTransport | None = None,
        api_base: str = "https://api.github.com",
        graphql_url: str = "https://api.github.com/graphql",
        api_version: str = "2026-03-10",
        repository_node_id: str | None = None,
    ):
        self.owner = owner
        self.repository = repository
        self.token = token
        self.target = dict(target)
        self.transport = transport or UrllibGitHubTransport()
        self.api_base = api_base.rstrip("/")
        self.graphql_url = graphql_url
        self.api_version = api_version
        self._repository_node_id = repository_node_id
        expected_resource = f"{owner}/{repository}".lower()
        if self.target != {
            "kind": "git",
            "authority": "github.com",
            "resource": expected_resource,
            "namespace": self.target.get("namespace"),
        }:
            raise PublicationFault("FORBIDDEN")
        namespace = self.target.get("namespace")
        if not isinstance(namespace, str) or not namespace.startswith("refs/heads/"):
            raise PublicationFault("UNSUPPORTED_CAPABILITY")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": self.api_version,
            "Content-Type": "application/json",
            "User-Agent": "stateOwl-r3-python",
        }

    def _target(self, target: Mapping[str, Any]) -> None:
        if dict(target) != self.target:
            raise PublicationFault("FORBIDDEN")

    @staticmethod
    def _typed(raw: str) -> str:
        if re.fullmatch(r"[0-9a-f]{40}", raw):
            return "git:sha1:" + raw
        if re.fullmatch(r"[0-9a-f]{64}", raw):
            return "git:sha256:" + raw
        raise PublicationFault("INTEGRITY_MISMATCH")

    @staticmethod
    def _raw(typed: str) -> str:
        match = _TYPED.fullmatch(typed) if isinstance(typed, str) else None
        if match is None:
            raise PublicationFault("INVALID_SOURCE")
        return match.group(2) or match.group(4)

    def _url(self, suffix: str) -> str:
        owner = urlparse.quote(self.owner, safe="")
        repository = urlparse.quote(self.repository, safe="")
        return f"{self.api_base}/repos/{owner}/{repository}{suffix}"

    @staticmethod
    def _fault_for_status(status: int, *, missing: str = "SNAPSHOT_UNAVAILABLE") -> PublicationFault:
        if status == 401:
            return PublicationFault("UNAUTHENTICATED")
        if status == 403:
            return PublicationFault("FORBIDDEN")
        if status == 404:
            return PublicationFault(missing)
        if status == 429:
            return PublicationFault("RATE_LIMITED")
        if 500 <= status <= 599:
            return PublicationFault("PROVIDER_UNAVAILABLE")
        return PublicationFault("PROVIDER_UNAVAILABLE")

    def _request(
        self,
        method: str,
        url: str,
        *,
        payload: Mapping[str, Any] | None = None,
        ok: tuple[int, ...] = (200,),
        missing: str = "SNAPSHOT_UNAVAILABLE",
        dispatch_uncertain: bool = False,
    ) -> Any:
        response = self.transport.request(
            method,
            url,
            headers=self._headers,
            payload=payload,
            dispatch_uncertain=dispatch_uncertain,
        )
        if response.status not in ok:
            raise self._fault_for_status(response.status, missing=missing)
        return response.payload

    def _repository_id(self) -> str:
        if self._repository_node_id:
            return self._repository_node_id
        payload = self._request("GET", self._url(""), ok=(200,), missing="FORBIDDEN")
        node_id = payload.get("node_id") if isinstance(payload, Mapping) else None
        if not isinstance(node_id, str) or not node_id:
            raise PublicationFault("INVALID_SOURCE")
        self._repository_node_id = node_id
        return node_id

    def resolve(self, target: Mapping[str, Any]) -> str:
        self._target(target)
        # Git refs REST expects the ref without the leading refs/ component.
        ref = target["namespace"][5:]
        encoded = urlparse.quote(ref, safe="/")
        payload = self._request(
            "GET",
            self._url(f"/git/ref/{encoded}"),
            ok=(200,),
            missing="NOT_FOUND",
        )
        try:
            obj = payload["object"]
            if obj["type"] != "commit":
                raise PublicationFault("INVALID_SOURCE")
            return self._typed(obj["sha"])
        except (KeyError, TypeError):
            raise PublicationFault("INVALID_SOURCE") from None

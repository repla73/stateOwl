from __future__ import annotations

from datetime import datetime
import base64
import hashlib
import json
import re
from typing import Any, Mapping
from urllib import parse as urlparse

from ..r3_publish import PublicationFault
from .transport import GitHubTransport, UrllibGitHubTransport

_TYPED = re.compile(r"git:(sha1):([0-9a-f]{40})\Z|git:(sha256):([0-9a-f]{64})\Z")
_RECEIPT_MARKER = "StateOwl-Receipt:"

class GitHubBase:
    """GitHub Git-database publisher with atomic expected-old ref admission.

    Blobs, tree and one-parent commit are constructed with Git database REST
    APIs. Admission uses GraphQL \`updateRefs\` with \`beforeOid\` and \`afterOid\`.
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

    @staticmethod
    def _git_object_hash(kind: str, raw: bytes, algorithm: str) -> str:
        header = kind.encode("ascii") + b" " + str(len(raw)).encode("ascii") + b"\0"
        return hashlib.new(algorithm, header + raw).hexdigest()

    @staticmethod
    def _git_actor(actor: Any) -> str:
        if not isinstance(actor, Mapping):
            raise PublicationFault("INTEGRITY_MISMATCH")
        name = actor.get("name")
        email = actor.get("email")
        date = actor.get("date")
        if not all(isinstance(value, str) and value for value in (name, email, date)):
            raise PublicationFault("INTEGRITY_MISMATCH")
        if any(char in name or char in email for char in ("\n", "\r", "<", ">")):
            raise PublicationFault("INTEGRITY_MISMATCH")
        try:
            instant = datetime.fromisoformat(date.replace("Z", "+00:00"))
            offset = instant.utcoffset()
            timestamp = instant.timestamp()
            if instant.tzinfo is None or offset is None:
                raise ValueError
            offset_seconds = offset.total_seconds()
            if offset_seconds % 60 or timestamp != int(timestamp):
                raise ValueError
            offset_minutes = int(offset_seconds // 60)
        except (ValueError, OverflowError, OSError):
            raise PublicationFault("INTEGRITY_MISMATCH") from None
        sign = "+" if offset_minutes >= 0 else "-"
        absolute = abs(offset_minutes)
        if absolute > 23 * 60 + 59:
            raise PublicationFault("INTEGRITY_MISMATCH")
        zone = f"{sign}{absolute // 60:02d}{absolute % 60:02d}"
        return f"{name} <{email}> {int(timestamp)} {zone}"

    def _raw_commit_bytes(self, payload: Mapping[str, Any], message: str) -> bytes:
        try:
            tree_sha = payload["tree"]["sha"]
            parents = payload["parents"]
            if not isinstance(tree_sha, str) or not isinstance(parents, list):
                raise PublicationFault("INTEGRITY_MISMATCH")
            self._typed(tree_sha)
            parent_shas: list[str] = []
            for parent in parents:
                parent_sha = parent["sha"]
                self._typed(parent_sha)
                parent_shas.append(parent_sha)
            lines = [
                f"tree {tree_sha}",
                *(f"parent {parent_sha}" for parent_sha in parent_shas),
                f"author {self._git_actor(payload['author'])}",
                f"committer {self._git_actor(payload['committer'])}",
                "",
            ]
            return ("\n".join(lines) + "\n" + message).encode("utf-8")
        except (KeyError, TypeError, UnicodeError):
            raise PublicationFault("INTEGRITY_MISMATCH") from None

    def _exact_commit_message(self, payload: Mapping[str, Any], expected_sha: str) -> str:
        """Recover exact receipt bytes only when the commit SHA proves them.

        GitHub's REST commit message is a representation, not raw Git object
        bytes. Ordinary non-receipt commits may use that representation. For a
        stateOwl receipt, reconstruct the unsigned commit object and accept one
        exact message candidate only when its object hash equals expected_sha.
        """

        message = payload.get("message") if isinstance(payload, Mapping) else None
        if not isinstance(message, str):
            raise PublicationFault("INVALID_SOURCE")
        if _RECEIPT_MARKER not in message:
            return message

        verification = payload.get("verification")
        if (
            not isinstance(verification, Mapping)
            or verification.get("reason") != "unsigned"
            or verification.get("signature") is not None
        ):
            raise PublicationFault("INTEGRITY_MISMATCH")

        if re.fullmatch(r"[0-9a-f]{40}", expected_sha):
            algorithm = "sha1"
        elif re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            algorithm = "sha256"
        else:
            raise PublicationFault("INTEGRITY_MISMATCH")

        candidates = [message]
        if not message.endswith("\n"):
            candidates.append(message + "\n")

        matches: list[str] = []
        for candidate in candidates:
            raw_commit = self._raw_commit_bytes(payload, candidate)
            if self._git_object_hash("commit", raw_commit, algorithm) == expected_sha:
                matches.append(candidate)
        if len(matches) != 1:
            raise PublicationFault("INTEGRITY_MISMATCH")
        return matches[0]

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

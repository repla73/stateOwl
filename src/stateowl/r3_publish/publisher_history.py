from __future__ import annotations

from typing import Any, Mapping

from .types import PROTOCOL, _GIT_SNAPSHOT, PublicationFault
from .codec import restricted_jcs
from .identity import _snapshot, request_digest

class PublisherHistory:
        def _inspect_commit(self, target: Mapping[str, Any], snapshot: str) -> Mapping[str, Any]:
            if target["kind"] == "git" and _GIT_SNAPSHOT.fullmatch(snapshot) is None:
                raise PublicationFault("INVALID_SOURCE")
            metadata = self._call("inspect", target=target, snapshot=snapshot)
            try:
                if metadata.get("id") != snapshot:
                    raise PublicationFault("INTEGRITY_MISMATCH")
                size = len(restricted_jcs(metadata, error="INVALID_SOURCE"))
                if size > self.limits["record_bytes"]:
                    raise PublicationFault("LIMIT_EXCEEDED")
            except AttributeError:
                raise PublicationFault("INVALID_SOURCE") from None
            return metadata

        def _verify_expected_commit(self, request: Mapping[str, Any]) -> None:
            metadata = self._inspect_commit(request["target"], request["expected"]["id"])
            if metadata.get("type") != "commit":
                raise PublicationFault("INVALID_SOURCE")

        def _committed_result(self, request: Mapping[str, Any], snapshot: str, head: str) -> dict[str, Any]:
            return {
                "protocol": PROTOCOL,
                "op": "publish",
                "outcome": "committed",
                "request_digest": request_digest(request),
                "snapshot": _snapshot(snapshot),
                "observed_head": _snapshot(head),
            }

        def _walk(
            self,
            target: Mapping[str, Any],
            head: str,
            expected: str,
            *,
            ancestor_only: bool = False,
        ) -> tuple[str, Mapping[str, Any]] | None:
            oid = head
            seen: set[str] = set()
            limit = self.limits.get("reconcile_commits")
            if type(limit) is not int or limit < 1:
                raise PublicationFault("UNSUPPORTED_CAPABILITY")
            for _ in range(limit):
                if oid == expected:
                    return None
                if oid in seen:
                    raise PublicationFault("NAMESPACE_DISCONTINUITY")
                seen.add(oid)
                try:
                    metadata = self._inspect_commit(target, oid)
                except PublicationFault as exc:
                    if exc.code == "SNAPSHOT_UNAVAILABLE":
                        raise PublicationFault("HISTORY_UNAVAILABLE") from None
                    raise
                parents = metadata.get("parents")
                if metadata.get("type") != "commit" or not isinstance(parents, list) or len(parents) != 1:
                    raise PublicationFault("NAMESPACE_DISCONTINUITY")
                parent = parents[0]
                if parent == expected:
                    return None if ancestor_only else (oid, metadata)
                if not isinstance(parent, str) or not parent:
                    raise PublicationFault("NAMESPACE_DISCONTINUITY")
                oid = parent
            raise PublicationFault("HISTORY_UNAVAILABLE")

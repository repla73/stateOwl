from __future__ import annotations

import base64
import re
import hashlib
from typing import Any, Mapping

from ..r3_publish import PublicationFault

class GitHubReadMixin:
        def inspect(self, target: Mapping[str, Any], snapshot: str) -> Mapping[str, Any]:
            self._target(target)
            raw = self._raw(snapshot)
            payload = self._request("GET", self._url(f"/git/commits/{raw}"), ok=(200,))
            try:
                sha = payload["sha"]
                tree_sha = payload["tree"]["sha"]
                parents = payload["parents"]
                message = payload["message"]
                if sha != raw or not isinstance(message, str) or not isinstance(parents, list):
                    raise PublicationFault("INTEGRITY_MISMATCH")
                return {
                    "id": self._typed(sha),
                    "type": "commit",
                    "tree": self._typed(tree_sha),
                    "parents": [self._typed(parent["sha"]) for parent in parents],
                    "message": message,
                }
            except (KeyError, TypeError):
                raise PublicationFault("INVALID_SOURCE") from None

        @staticmethod
        def _git_object_hash(kind: str, raw: bytes, algorithm: str) -> str:
            header = kind.encode("ascii") + b" " + str(len(raw)).encode("ascii") + b"\0"
            return hashlib.new(algorithm, header + raw).hexdigest()

        @staticmethod
        def _algorithm(raw_oid: str) -> str:
            if re.fullmatch(r"[0-9a-f]{40}", raw_oid):
                return "sha1"
            if re.fullmatch(r"[0-9a-f]{64}", raw_oid):
                return "sha256"
            raise PublicationFault("INVALID_SOURCE")

        def _tree_sha(self, snapshot: str) -> str:
            raw = self._raw(snapshot)
            payload = self._request("GET", self._url(f"/git/commits/{raw}"), ok=(200,))
            try:
                if payload["sha"] != raw:
                    raise PublicationFault("INTEGRITY_MISMATCH")
                tree_sha = payload["tree"]["sha"]
                self._typed(tree_sha)
                return tree_sha
            except (KeyError, TypeError):
                raise PublicationFault("INVALID_SOURCE") from None

        def _blob_bytes(self, sha: str) -> bytes:
            payload = self._request("GET", self._url(f"/git/blobs/{sha}"), ok=(200,))
            try:
                if payload.get("sha") != sha or payload.get("encoding") != "base64":
                    raise PublicationFault("INTEGRITY_MISMATCH")
                encoded = "".join(payload["content"].splitlines())
                raw = base64.b64decode(encoded, validate=True)
                # GitHub may wrap base64 lines; canonicality applies to protocol puts,
                # not to the provider's representation of a blob response.
                size = payload.get("size")
                if size is not None and size != len(raw):
                    raise PublicationFault("INTEGRITY_MISMATCH")
                algorithm = self._algorithm(sha)
                if self._git_object_hash("blob", raw, algorithm) != sha:
                    raise PublicationFault("INTEGRITY_MISMATCH")
                return raw
            except (KeyError, TypeError, ValueError, UnicodeError):
                raise PublicationFault("INVALID_SOURCE") from None

        def _walk_tree(self, sha: str, prefix: str, out: dict[str, dict[str, Any]]) -> None:
            payload = self._request("GET", self._url(f"/git/trees/{sha}"), ok=(200,))
            entries = payload.get("tree") if isinstance(payload, Mapping) else None
            if not isinstance(entries, list):
                raise PublicationFault("INVALID_SOURCE")
            if payload.get("truncated") is True:
                raise PublicationFault("LIMIT_EXCEEDED")
            if payload.get("sha") is not None and payload.get("sha") != sha:
                raise PublicationFault("INTEGRITY_MISMATCH")
            for entry in entries:
                try:
                    name = entry["path"]
                    mode = entry["mode"]
                    object_type = entry["type"]
                    oid = entry["sha"]
                except (KeyError, TypeError):
                    raise PublicationFault("INVALID_SOURCE") from None
                if not all(isinstance(value, str) and value for value in (name, mode, object_type, oid)):
                    raise PublicationFault("INVALID_SOURCE")
                path = f"{prefix}/{name}" if prefix else name
                if object_type == "tree":
                    self._walk_tree(oid, path, out)
                elif object_type == "blob":
                    out[path] = {
                        "base64": base64.b64encode(self._blob_bytes(oid)).decode("ascii"),
                        "mode": mode,
                    }
                elif object_type == "commit" and mode == "160000":
                    out[path] = {"mode": mode, "object": self._typed(oid)}
                else:
                    raise PublicationFault("INVALID_SOURCE")

        def tree(self, target: Mapping[str, Any], snapshot: str) -> Mapping[str, Any]:
            self._target(target)
            out: dict[str, dict[str, Any]] = {}
            self._walk_tree(self._tree_sha(snapshot), "", out)
            return out

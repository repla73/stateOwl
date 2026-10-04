from __future__ import annotations

import base64
import hashlib
from typing import Any, Mapping

from ..r3_publish import PublicationFault
from .base import _TYPED

class GitHubWriteMixin:
        def _create_blob(self, raw: bytes) -> str:
            payload = self._request(
                "POST",
                self._url("/git/blobs"),
                payload={"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"},
                ok=(201,),
            )
            sha = payload.get("sha") if isinstance(payload, Mapping) else None
            if not isinstance(sha, str):
                raise PublicationFault("INVALID_SOURCE")
            typed = self._typed(sha)
            algorithm = _TYPED.fullmatch(typed).group(1)
            if self._git_object_hash("blob", raw, algorithm) != sha:
                raise PublicationFault("INTEGRITY_MISMATCH")
            return sha

        def _create_candidate_tree(
            self,
            expected: str,
            old: Mapping[str, Any],
            candidate: Mapping[str, Any],
        ) -> str:
            changes: list[dict[str, Any]] = []
            for path in sorted(set(old) | set(candidate), key=lambda value: value.encode("utf-8")):
                before = old.get(path)
                after = candidate.get(path)
                if before == after:
                    continue
                if after is None:
                    mode = before.get("mode") if isinstance(before, Mapping) else None
                    if mode not in {"100644", "100755"}:
                        raise PublicationFault("INVALID_SOURCE")
                    changes.append({"path": path, "mode": mode, "type": "blob", "sha": None})
                    continue
                mode = after.get("mode") if isinstance(after, Mapping) else None
                encoded = after.get("base64") if isinstance(after, Mapping) else None
                if mode not in {"100644", "100755"} or not isinstance(encoded, str):
                    raise PublicationFault("INVALID_SOURCE")
                try:
                    raw = base64.b64decode(encoded, validate=True)
                    if base64.b64encode(raw).decode("ascii") != encoded:
                        raise ValueError
                except (ValueError, UnicodeError):
                    raise PublicationFault("INVALID_SOURCE") from None
                changes.append({"path": path, "mode": mode, "type": "blob", "sha": self._create_blob(raw)})
            payload = self._request(
                "POST",
                self._url("/git/trees"),
                payload={"base_tree": self._tree_sha(expected), "tree": changes},
                ok=(201,),
            )
            tree_sha = payload.get("sha") if isinstance(payload, Mapping) else None
            if not isinstance(tree_sha, str):
                raise PublicationFault("INVALID_SOURCE")
            self._typed(tree_sha)
            return tree_sha

        def _create_commit(self, tree_sha: str, expected: str, message: str) -> str:
            expected_raw = self._raw(expected)
            payload = self._request(
                "POST",
                self._url("/git/commits"),
                payload={"message": message, "tree": tree_sha, "parents": [expected_raw]},
                ok=(201,),
            )
            sha = payload.get("sha") if isinstance(payload, Mapping) else None
            if not isinstance(sha, str):
                raise PublicationFault("INVALID_SOURCE")
            self._typed(sha)
            try:
                if payload["message"] != message or payload["tree"]["sha"] != tree_sha:
                    raise PublicationFault("INTEGRITY_MISMATCH")
                parents = payload["parents"]
                if not isinstance(parents, list) or [parent["sha"] for parent in parents] != [expected_raw]:
                    raise PublicationFault("INTEGRITY_MISMATCH")
            except (KeyError, TypeError):
                raise PublicationFault("INVALID_SOURCE") from None
            return sha

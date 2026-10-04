from __future__ import annotations

import base64
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Mapping

from ..r3_publish import PublicationFault


_TYPED = re.compile(r"git:(sha1):([0-9a-f]{40})\Z|git:(sha256):([0-9a-f]{64})\Z")


class LocalGitBase:
    """Plumbing-only local Git publication provider.

    The target namespace is never checked out. Candidate construction uses a
    private temporary index and admission uses `git update-ref <ref> <new> <old>`.
    Project authority and G5 continuity enforcement are supplied separately by
    the trusted validation boundary.
    """

    def __init__(
        self,
        repository: str | os.PathLike[str],
        *,
        target: Mapping[str, Any],
        author_name: str = "stateOwl",
        author_email: str = "stateowl@localhost",
    ):
        self.repository = str(Path(repository).resolve())
        self.target = dict(target)
        self.author_name = author_name
        self.author_email = author_email
        self.algorithm = self._run(["rev-parse", "--show-object-format"]).stdout.decode("ascii").strip()
        if self.algorithm not in {"sha1", "sha256"}:
            raise PublicationFault("UNSUPPORTED_CAPABILITY")

    def _target(self, target: Mapping[str, Any]) -> None:
        if dict(target) != self.target:
            raise PublicationFault("FORBIDDEN")
        namespace = target.get("namespace")
        if not isinstance(namespace, str) or not namespace.startswith("refs/heads/"):
            raise PublicationFault("UNSUPPORTED_CAPABILITY")

    def _typed(self, raw: str) -> str:
        expected = 40 if self.algorithm == "sha1" else 64
        if re.fullmatch(rf"[0-9a-f]{{{expected}}}", raw) is None:
            raise PublicationFault("INTEGRITY_MISMATCH")
        return f"git:{self.algorithm}:{raw}"

    def _raw(self, typed: str) -> str:
        match = _TYPED.fullmatch(typed) if isinstance(typed, str) else None
        if match is None:
            raise PublicationFault("INVALID_SOURCE")
        algorithm = match.group(1) or match.group(3)
        raw = match.group(2) or match.group(4)
        if algorithm != self.algorithm:
            raise PublicationFault("INVALID_SOURCE")
        return raw

    def _run(
        self,
        args: list[str],
        *,
        input_bytes: bytes | None = None,
        env: Mapping[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        try:
            result = subprocess.run(
                ["git", "-C", self.repository, *args],
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged,
                check=False,
            )
        except OSError as exc:
            raise PublicationFault("PROVIDER_UNAVAILABLE") from exc
        if check and result.returncode != 0:
            raise PublicationFault("PROVIDER_UNAVAILABLE")
        return result

    def resolve(self, target: Mapping[str, Any]) -> str:
        self._target(target)
        result = self._run(["show-ref", "--verify", "--hash", target["namespace"]], check=False)
        if result.returncode != 0:
            raise PublicationFault("NOT_FOUND")
        raw = result.stdout.decode("ascii").strip()
        kind = self._run(["cat-file", "-t", raw], check=False)
        if kind.returncode != 0:
            raise PublicationFault("SNAPSHOT_UNAVAILABLE")
        if kind.stdout != b"commit\n":
            raise PublicationFault("INVALID_SOURCE")
        return self._typed(raw)

    def inspect(self, target: Mapping[str, Any], snapshot: str) -> Mapping[str, Any]:
        self._target(target)
        raw = self._raw(snapshot)
        kind = self._run(["cat-file", "-t", raw], check=False)
        if kind.returncode != 0:
            raise PublicationFault("SNAPSHOT_UNAVAILABLE")
        object_type = kind.stdout.decode("ascii").strip()
        if object_type != "commit":
            return {"id": snapshot, "type": object_type}
        obj = self._run(["cat-file", "commit", raw], check=False)
        if obj.returncode != 0:
            raise PublicationFault("SNAPSHOT_UNAVAILABLE")
        data = obj.stdout
        split = data.find(b"\n\n")
        if split < 0:
            raise PublicationFault("INVALID_SOURCE")
        header, message = data[:split], data[split + 2 :]
        parents: list[str] = []
        tree: str | None = None
        for line in header.split(b"\n"):
            if line.startswith(b"tree "):
                try:
                    tree = self._typed(line[5:].decode("ascii"))
                except UnicodeError:
                    raise PublicationFault("INVALID_SOURCE") from None
            elif line.startswith(b"parent "):
                try:
                    parents.append(self._typed(line[7:].decode("ascii")))
                except UnicodeError:
                    raise PublicationFault("INVALID_SOURCE") from None
        if tree is None:
            raise PublicationFault("INVALID_SOURCE")
        try:
            message_text = message.decode("utf-8")
        except UnicodeError:
            raise PublicationFault("INVALID_SOURCE") from None
        return {
            "id": snapshot,
            "type": "commit",
            "tree": tree,
            "parents": parents,
            "message": message_text,
        }

    def tree(self, target: Mapping[str, Any], snapshot: str) -> Mapping[str, Any]:
        self._target(target)
        raw = self._raw(snapshot)
        result = self._run(["ls-tree", "-r", "-z", raw], check=False)
        if result.returncode != 0:
            raise PublicationFault("SNAPSHOT_UNAVAILABLE")
        entries: dict[str, dict[str, Any]] = {}
        for record in result.stdout.split(b"\0"):
            if not record:
                continue
            try:
                metadata, path_raw = record.split(b"\t", 1)
                mode_raw, object_type_raw, oid_raw = metadata.split(b" ", 2)
                mode = mode_raw.decode("ascii")
                object_type = object_type_raw.decode("ascii")
                oid = oid_raw.decode("ascii")
                path = path_raw.decode("utf-8")
            except (ValueError, UnicodeError):
                raise PublicationFault("INVALID_SOURCE") from None
            if path in entries:
                raise PublicationFault("INTEGRITY_MISMATCH")
            if object_type == "blob":
                blob = self._run(["cat-file", "blob", oid], check=False)
                if blob.returncode != 0:
                    raise PublicationFault("SNAPSHOT_UNAVAILABLE")
                entries[path] = {
                    "base64": base64.b64encode(blob.stdout).decode("ascii"),
                    "mode": mode,
                }
            elif mode == "160000" and object_type == "commit":
                entries[path] = {"mode": mode, "object": self._typed(oid)}
            else:
                raise PublicationFault("INVALID_SOURCE")
        return entries

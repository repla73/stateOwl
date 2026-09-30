"""Platform-neutral focused state reader.

The core deliberately knows nothing about tasks, reviews, deployments, agents,
or any provider-specific lifecycle. It understands only Git snapshots, a small
router record, exact paths, opt-in links, projections, and provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import posixpath
import re
from typing import Any, Mapping, Protocol, Sequence

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ALLOWED_REFS = ("refs/heads/", "refs/tags/")


class StateOwlError(ValueError):
    """Stable error carrying a compact machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FileObject:
    """Bytes read from an exact Git snapshot."""

    blob: str
    content: bytes

    def __post_init__(self) -> None:
        if not is_sha(self.blob):
            raise StateOwlError("BLOB_ID_INVALID", "blob must be an exact 40-character Git SHA-1")
        if git_blob_oid(self.content) != self.blob:
            raise StateOwlError("BLOB_MISMATCH", "file bytes do not match their Git blob identity")


@dataclass(frozen=True)
class Locator:
    repository: str
    commit: str
    path: str
    blob: str

    def as_dict(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "commit": self.commit,
            "path": self.path,
            "blob": self.blob,
        }


class StateStore(Protocol):
    """Read-only transport boundary used by the provider-neutral core."""

    def resolve_ref(self, repository: str, ref: str) -> str: ...
    def read_file(self, repository: str, commit: str, path: str) -> FileObject: ...


def git_blob_oid(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and _SHA_RE.fullmatch(value) is not None


def validate_sha(value: Any) -> str:
    if not is_sha(value):
        raise StateOwlError("COMMIT_INVALID", "expected an exact 40-character lowercase Git SHA-1")
    return value


def validate_repository(value: Any) -> str:
    if not isinstance(value, str) or _REPO_RE.fullmatch(value) is None:
        raise StateOwlError("REPOSITORY_INVALID", "expected GitHub repository in owner/name form")
    if any(part in {".", ".."} for part in value.split("/")):
        raise StateOwlError("REPOSITORY_INVALID", "repository contains an invalid component")
    return value


def validate_ref(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith(_ALLOWED_REFS):
        raise StateOwlError("REF_INVALID", "expected a fully qualified refs/heads/... or refs/tags/... ref")
    suffix = value.split("/", 2)[2]
    if not suffix or suffix.startswith("/") or suffix.endswith("/") or ".." in suffix.split("/"):
        raise StateOwlError("REF_INVALID", "invalid Git ref path")
    if any(ch.isspace() or ch in "~^:?*[\\" for ch in suffix):
        raise StateOwlError("REF_INVALID", "Git ref contains unsupported characters")
    return value


def validate_path(value: Any) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value or "\x00" in value:
        raise StateOwlError("PATH_INVALID", "expected a non-empty relative POSIX repository path")
    normalized = posixpath.normpath(value)
    if normalized != value or value in {".", ".."} or value.startswith("../"):
        raise StateOwlError("PATH_INVALID", "repository path must be normalized and cannot escape the repository")
    return value


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StateOwlError("JSON_DUPLICATE_KEY", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(raw: bytes, *, what: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StateOwlError("TEXT_ENCODING", f"{what} is not valid UTF-8") from exc
    try:
        return json.loads(text, object_pairs_hook=_object_no_duplicates)
    except StateOwlError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        raise StateOwlError("JSON_INVALID", f"{what} is not valid JSON") from exc


def _string_list(value: Any, *, code: str, name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise StateOwlError(code, f"{name} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise StateOwlError(code, f"{name} must not contain duplicates")
    return value


def _project(value: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    """Project only named top-level fields in declared order.

    V1 deliberately avoids JSONPath/JMESPath dependencies. Nested data can be
    selected by making it one top-level field or by moving it into a linked
    record. Missing optional fields are omitted rather than synthesized.
    """
    return {key: value[key] for key in fields if key in value}


class Reader:
    """Resolve one route and only explicitly requested linked detail."""

    def __init__(self, store: StateStore):
        self.store = store

    def _read(self, repository: str, commit: str, path: str) -> tuple[FileObject, Locator]:
        repository = validate_repository(repository)
        commit = validate_sha(commit)
        path = validate_path(path)
        obj = self.store.read_file(repository, commit, path)
        return obj, Locator(repository, commit, path, obj.blob)

    @staticmethod
    def _router(value: Any) -> Mapping[str, Any]:
        if not isinstance(value, dict) or value.get("schema") != "stateowl.router/v1":
            raise StateOwlError("ROUTER_SCHEMA", "router must use stateowl.router/v1")
        routes = value.get("routes")
        if not isinstance(routes, dict) or not routes:
            raise StateOwlError("ROUTER_SCHEMA", "router.routes must be a non-empty object")
        return routes

    @staticmethod
    def _route(routes: Mapping[str, Any], route: str) -> Mapping[str, Any]:
        if not isinstance(route, str) or not route:
            raise StateOwlError("ROUTE_INVALID", "route name is required")
        entry = routes.get(route)
        if not isinstance(entry, dict):
            raise StateOwlError("ROUTE_NOT_FOUND", f"route does not exist: {route}")
        if set(entry) - {"path", "select"}:
            raise StateOwlError("ROUTE_SCHEMA", "route supports only path and select")
        validate_path(entry.get("path"))
        _string_list(entry.get("select"), code="ROUTE_SCHEMA", name="route.select")
        return entry

    @staticmethod
    def _link(record: Mapping[str, Any], name: str, *, base_repository: str, base_commit: str) -> tuple[str, str, str, str, list[str] | None]:
        links = record.get("links", {})
        if not isinstance(links, dict):
            raise StateOwlError("LINK_SCHEMA", "record.links must be an object when present")
        link = links.get(name)
        if not isinstance(link, dict):
            raise StateOwlError("LINK_NOT_FOUND", f"link does not exist: {name}")
        allowed = {"repository","commit","path","format","select"}
        if set(link) - allowed:
            raise StateOwlError("LINK_SCHEMA", f"link {name} contains unsupported fields")
        repository = validate_repository(link.get("repository", base_repository))
        commit_value = link.get("commit")
        if repository != base_repository and commit_value is None:
            raise StateOwlError("LINK_COMMIT_REQUIRED", "cross-repository links require an exact commit")
        commit = validate_sha(commit_value) if commit_value is not None else base_commit
        path = validate_path(link.get("path"))
        fmt = link.get("format", "json")
        if fmt not in {"json", "text"}:
            raise StateOwlError("LINK_SCHEMA", "link.format must be json or text")
        select = None
        if "select" in link:
            if fmt != "json":
                raise StateOwlError("LINK_SCHEMA", "link.select is valid only for JSON links")
            select = _string_list(link["select"], code="LINK_SCHEMA", name=f"link {name}.select")
        return repository, commit, path, fmt, select

    def read(
        self,
        repository: str,
        route: str,
        *,
        ref: str = "refs/heads/main",
        router_path: str = ".stateowl/router.json",
        expand: Sequence[str] = (),
        expected_head: str | None = None,
    ) -> dict[str, Any]:
        repository = validate_repository(repository)
        ref = validate_ref(ref)
        router_path = validate_path(router_path)
        if expected_head is not None:
            expected_head = validate_sha(expected_head)

        # Deliberately fresh on every call. Stores must not cache mutable refs.
        head = validate_sha(self.store.resolve_ref(repository, ref))
        if expected_head is not None and head != expected_head:
            raise StateOwlError(
                "EXPECTED_HEAD_MISMATCH",
                f"expected {expected_head}, observed {head}",
            )

        router_obj, router_locator = self._read(repository, head, router_path)
        routes = self._router(strict_json(router_obj.content, what="router"))
        entry = self._route(routes, route)

        record_obj, record_locator = self._read(repository, head, entry["path"])
        record = strict_json(record_obj.content, what=f"record {route}")
        if not isinstance(record, dict):
            raise StateOwlError("RECORD_SCHEMA", "selected record must be a JSON object")
        selected = _project(record, entry["select"])

        result: dict[str, Any] = {
            "route": route,
            "head": {"repository": repository, "ref": ref, "commit": head},
            "value": selected,
            "sources": {
                "router": router_locator.as_dict(),
                "record": record_locator.as_dict(),
            },
        }

        names = list(expand)
        if len(names) != len(set(names)):
            raise StateOwlError("EXPAND_INVALID", "expand list must not contain duplicates")
        if names:
            expanded: dict[str, Any] = {}
            for name in names:
                if not isinstance(name, str) or not name:
                    raise StateOwlError("EXPAND_INVALID", "expanded link names must be non-empty strings")
                link_repo, link_commit, link_path, fmt, select = self._link(
                    record, name, base_repository=repository, base_commit=head
                )
                link_obj, link_locator = self._read(link_repo, link_commit, link_path)
                if fmt == "json":
                    value = strict_json(link_obj.content, what=f"link {name}")
                    if select is not None:
                        if not isinstance(value, dict):
                            raise StateOwlError("LINK_SCHEMA", "projected JSON link must contain an object")
                        value = _project(value, select)
                else:
                    try:
                        value = link_obj.content.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise StateOwlError("TEXT_ENCODING", f"link {name} is not valid UTF-8") from exc
                expanded[name] = {"value": value, "source": link_locator.as_dict()}
            result["expanded"] = expanded
        return result

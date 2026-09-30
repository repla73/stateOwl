"""Small GitHub REST adapter for stateOwl.

Only two operations are required by the core: resolve a ref and fetch one file
at an exact commit. No checkout, Git executable, daemon, database, or server is
required.
"""
from __future__ import annotations

import base64
from collections import OrderedDict
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .core import (
    FileObject,
    StateOwlError,
    git_blob_oid,
    validate_path,
    validate_ref,
    validate_repository,
    validate_sha,
)

_CACHE_ENTRIES = 128
_CACHE_BYTES = 4 * 1024 * 1024


class GitHubStore:
    """GitHub transport with bounded immutable-file caching.

    Ref reads are intentionally never cached. Exact file bytes may be cached by
    (repository, commit, path) because those locators are immutable.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        api_base: str = "https://api.github.com",
        timeout: float = 15.0,
        user_agent: str = "stateowl/0.1.0",
    ) -> None:
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent
        self._files: OrderedDict[tuple[str, str, str], FileObject] = OrderedDict()
        self._cache_bytes = 0

    def _request_json(self, path: str, *, query: dict[str, str] | None = None) -> Any:
        url = self.api_base + path
        if query:
            url += "?" + urlencode(query)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - fixed GitHub API base by default
                raw = response.read()
        except HTTPError as exc:
            message = "GitHub request failed"
            try:
                body = exc.read().decode("utf-8", errors="replace")
                parsed = json.loads(body)
                if isinstance(parsed, dict) and isinstance(parsed.get("message"), str):
                    message = parsed["message"]
            except Exception:
                pass
            code = "GITHUB_NOT_FOUND" if exc.code == 404 else "GITHUB_HTTP_ERROR"
            raise StateOwlError(code, f"{message} (HTTP {exc.code})") from exc
        except URLError as exc:
            raise StateOwlError("GITHUB_NETWORK_ERROR", "GitHub request could not be completed") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StateOwlError("GITHUB_RESPONSE_INVALID", "GitHub returned invalid JSON") from exc

    def resolve_ref(self, repository: str, ref: str) -> str:
        repository = validate_repository(repository)
        ref = validate_ref(ref)
        owner, repo = repository.split("/", 1)
        short_ref = ref.removeprefix("refs/")
        value = self._request_json(
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/git/ref/{quote(short_ref, safe='/')}"
        )
        if not isinstance(value, dict) or not isinstance(value.get("object"), dict):
            raise StateOwlError("GITHUB_RESPONSE_INVALID", "GitHub ref response is malformed")
        return validate_sha(value["object"].get("sha"))

    def _remember(self, key: tuple[str, str, str], value: FileObject) -> None:
        if len(value.content) > _CACHE_BYTES:
            return
        while self._files and (
            len(self._files) >= _CACHE_ENTRIES or self._cache_bytes + len(value.content) > _CACHE_BYTES
        ):
            self._cache_bytes -= len(self._files.popitem(last=False)[1].content)
        self._files[key] = value
        self._files.move_to_end(key)
        self._cache_bytes += len(value.content)

    def read_file(self, repository: str, commit: str, path: str) -> FileObject:
        repository = validate_repository(repository)
        commit = validate_sha(commit)
        path = validate_path(path)
        key = (repository, commit, path)
        if key in self._files:
            self._files.move_to_end(key)
            return self._files[key]

        owner, repo = repository.split("/", 1)
        value = self._request_json(
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/contents/{quote(path, safe='/')}",
            query={"ref": commit},
        )
        if not isinstance(value, dict) or value.get("type") != "file":
            raise StateOwlError("GITHUB_RESPONSE_INVALID", "requested path is not a regular GitHub file")
        if value.get("encoding") != "base64" or not isinstance(value.get("content"), str):
            raise StateOwlError(
                "GITHUB_CONTENT_UNAVAILABLE",
                "GitHub did not inline file content; keep routed state records small",
            )
        try:
            raw = base64.b64decode("".join(value["content"].split()), validate=True)
        except (ValueError, TypeError) as exc:
            raise StateOwlError("GITHUB_RESPONSE_INVALID", "GitHub file content is invalid base64") from exc
        if isinstance(value.get("size"), int) and value["size"] != len(raw):
            raise StateOwlError("GITHUB_RESPONSE_INVALID", "GitHub file byte length is inconsistent")
        blob = value.get("sha")
        if not isinstance(blob, str) or git_blob_oid(raw) != blob:
            raise StateOwlError("BLOB_MISMATCH", "GitHub file bytes do not match the reported blob SHA")
        result = FileObject(blob=blob, content=raw)
        self._remember(key, result)
        return result

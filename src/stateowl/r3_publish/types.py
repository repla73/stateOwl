from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol
import re

PROTOCOL = "stateowl/0.2-draft.3"
RECEIPT_FORMAT = "stateowl.git-receipt/2"
MAX_SAFE = 9007199254740991

_RETRY: dict[str, str] = {}
for _retry, _codes in {
    "after_correction": "INVALID_REQUEST NOT_FOUND EXACT_SNAPSHOT_REQUIRED INVALID_SOURCE NUMBER_UNREPRESENTABLE LIMIT_EXCEEDED VALIDATION_FAILED",
    "after_refresh": "UNAUTHENTICATED CONFLICT NAMESPACE_DISCONTINUITY TOKEN_INVALID",
    "after_backoff": "RATE_LIMITED PROVIDER_UNAVAILABLE",
    "never": "UNSUPPORTED_VERSION UNSUPPORTED_CAPABILITY FORBIDDEN NOT_FOUND_OR_FORBIDDEN SNAPSHOT_UNAVAILABLE INTEGRITY_MISMATCH NO_CHANGE HISTORY_UNAVAILABLE",
}.items():
    for _code in _codes.split():
        _RETRY[_code] = _retry

_GIT_SNAPSHOT = re.compile(r"git:(?:sha1:[0-9a-f]{40}|sha256:[0-9a-f]{64})\Z")
_RECEIPT = re.compile(
    r"(?:stateOwl publication\n\n)?StateOwl-Receipt: ([A-Za-z0-9+/]+={0,2})\n\Z"
)


class PublicationFault(ValueError):
    """Normalized protocol/provider failure at the publication boundary."""

    def __init__(self, code: str, *, dispatched: bool = False):
        if code not in _RETRY:
            raise ValueError(f"unknown publication fault code: {code}")
        self.code = code
        self.dispatched = dispatched
        super().__init__(code)


class PublicationProvider(Protocol):
    def call(self, method: str, **args: Any) -> Any: ...


class TrustedProjectValidation(Protocol):
    """Trusted, repository-independent project validation boundary."""

    def access(self, target: Mapping[str, Any], operation: str) -> Mapping[str, Any]: ...
    def authorize(self, target: Mapping[str, Any], operation: str, paths: list[str]) -> bool: ...
    def validate(
        self,
        target: Mapping[str, Any],
        expected: str,
        binding: str,
        old: Mapping[str, Any],
        candidate: Mapping[str, Any],
    ) -> bool: ...


class GitPublicationStorage(Protocol):
    """Git mechanics only; project authority and validators stay outside this interface."""

    def resolve(self, target: Mapping[str, Any]) -> str: ...
    def inspect(self, target: Mapping[str, Any], snapshot: str) -> Mapping[str, Any]: ...
    def tree(self, target: Mapping[str, Any], snapshot: str) -> Mapping[str, Any]: ...
    def admit(
        self,
        target: Mapping[str, Any],
        expected: str,
        candidate: Mapping[str, Any],
        message: str,
    ) -> Mapping[str, Any]: ...


class CompositePublicationProvider:
    """Compose trusted project validation with provider-specific Git storage."""

    _METHODS = {"access", "authorize", "validate", "resolve", "inspect", "tree", "admit"}

    def __init__(self, trusted: TrustedProjectValidation, storage: GitPublicationStorage):
        self.trusted = trusted
        self.storage = storage

    def call(self, method: str, **args: Any) -> Any:
        if method not in self._METHODS:
            raise ValueError(f"unsupported publication provider method: {method}")
        target = self.trusted if method in {"access", "authorize", "validate"} else self.storage
        try:
            return getattr(target, method)(**args)
        except PublicationFault:
            raise
        except Exception as exc:  # trusted/provider integration must not leak arbitrary failures
            raise PublicationFault("PROVIDER_UNAVAILABLE") from exc


@dataclass(frozen=True)
class StaticTrustedProjectValidation:
    """Small trusted integration helper for explicitly configured projects.

    No repository record can choose the validator or authority policy.  The
    validator receives both the complete old and candidate states.
    """

    target: Mapping[str, Any]
    validation: str | None
    validator: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None
    authorize_path: Callable[[str], bool] | None = None
    project_authorized: bool = True
    continuity: str = "intact"
    auth_scope: str = "trusted-project"

    def _target(self, target: Mapping[str, Any]) -> None:
        if dict(target) != dict(self.target):
            raise PublicationFault("FORBIDDEN")

    def access(self, target: Mapping[str, Any], operation: str) -> Mapping[str, Any]:
        self._target(target)
        if operation != "publish":
            raise PublicationFault("UNSUPPORTED_CAPABILITY")
        return {
            "validation": self.validation,
            "validator_available": self.validation is None or self.validator is not None,
            "project_authorized": self.project_authorized,
            "continuity": self.continuity,
            "auth_scope": self.auth_scope,
        }

    def authorize(self, target: Mapping[str, Any], operation: str, paths: list[str]) -> bool:
        self._target(target)
        if operation != "publish":
            raise PublicationFault("UNSUPPORTED_CAPABILITY")
        if self.authorize_path is not None and any(not self.authorize_path(path) for path in paths):
            raise PublicationFault("FORBIDDEN")
        return True

    def validate(
        self,
        target: Mapping[str, Any],
        expected: str,
        binding: str,
        old: Mapping[str, Any],
        candidate: Mapping[str, Any],
    ) -> bool:
        self._target(target)
        if binding != self.validation:
            raise PublicationFault("VALIDATION_FAILED")
        if self.validator is None:
            raise PublicationFault("UNSUPPORTED_CAPABILITY")
        if not self.project_authorized:
            raise PublicationFault("FORBIDDEN")
        if not self.validator(old, candidate):
            raise PublicationFault("VALIDATION_FAILED")
        return True

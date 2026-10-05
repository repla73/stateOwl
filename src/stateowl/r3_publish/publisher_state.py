from __future__ import annotations

from typing import Any, Mapping

from .types import PROTOCOL, RECEIPT_FORMAT, _GIT_SNAPSHOT, PublicationFault, PublicationProvider
from .codec import _bytes_value, _collision, _ref_valid, restricted_jcs
from .validation import _strict_request_json, _validate_publish_request
from .identity import _error, _snapshot, request_digest

class PublisherState:
    """Provider-neutral guarded publisher for stateowl/0.2-draft.3."""
    def __init__(self, provider: PublicationProvider, capabilities: Mapping[str, Any]):
        self.provider = provider
        self.capabilities = capabilities
        self.limits = capabilities.get("limits", {})
        self.request: dict[str, Any] | None = None
        self.admitted: str | None = None
        self.was_dispatched = False

    def _call(self, method: str, **args: Any) -> Any:
        try:
            return self.provider.call(method, **args)
        except PublicationFault:
            raise
        except Exception as exc:
            raise PublicationFault("PROVIDER_UNAVAILABLE") from exc

    def _fail(self, code: str, *, request_stage: bool = False) -> dict[str, Any]:
        request = self.request
        if request_stage or request is None:
            return {
                "protocol": PROTOCOL,
                "op": "unknown",
                "status": "error",
                "error": _error(code),
            }
        outcome = (
            "verification_pending"
            if self.admitted is not None
            else "indeterminate"
            if self.was_dispatched or request["mode"] == "reconcile"
            else "not_committed"
        )
        result: dict[str, Any] = {
            "protocol": PROTOCOL,
            "op": "publish",
            "outcome": outcome,
            "request_digest": request_digest(request),
            "error": _error(code, uncertain=outcome in {"verification_pending", "indeterminate"}),
        }
        if self.admitted is not None:
            result["snapshot"] = _snapshot(self.admitted)
        return result

    def _precheck(self, raw: bytes) -> dict[str, Any]:
        request_limit = self.limits.get("request_bytes")
        if type(request_limit) is not int or request_limit < 1:
            raise PublicationFault("UNSUPPORTED_CAPABILITY")
        if len(raw) > request_limit:
            raise PublicationFault("LIMIT_EXCEEDED")
        depth = self.limits.get("json_depth")
        if type(depth) is not int or depth < 1:
            raise PublicationFault("UNSUPPORTED_CAPABILITY")
        request = _strict_request_json(raw, depth)
        if not isinstance(request, dict) or not isinstance(request.get("protocol"), str):
            raise PublicationFault("INVALID_REQUEST")
        if request["protocol"] != PROTOCOL:
            raise PublicationFault("UNSUPPORTED_VERSION")
        if not _validate_publish_request(request):
            raise PublicationFault("INVALID_REQUEST")
        if request["target"]["kind"] == "git" and not _ref_valid(request["target"]["namespace"]):
            raise PublicationFault("INVALID_REQUEST")
        paths = [change["path"] for change in request["changes"]]
        if _collision(paths):
            raise PublicationFault("INVALID_REQUEST")
        decoded: list[bytes] = []
        for change in request["changes"]:
            if "put" in change:
                decoded.append(_bytes_value(change["put"]))
        record_limit = self.limits.get("record_bytes")
        mutation_limit = self.limits.get("mutation_bytes")
        changes_limit = self.limits.get("changes")
        if any(type(value) is not int or value < 1 for value in (record_limit, mutation_limit, changes_limit)):
            raise PublicationFault("UNSUPPORTED_CAPABILITY")
        if (
            len(request["changes"]) > changes_limit
            or sum(len(value) for value in decoded) > mutation_limit
            or any(len(value) > record_limit for value in decoded)
        ):
            raise PublicationFault("LIMIT_EXCEEDED")
        return request

    def run(self, raw: bytes) -> dict[str, Any]:
        self.request = None
        self.admitted = None
        self.was_dispatched = False
        try:
            self.request = self._precheck(raw)
        except PublicationFault as exc:
            return self._fail(exc.code, request_stage=True)

        request = self.request
        try:
            if "publish" not in self.capabilities.get("operations", []):
                raise PublicationFault("UNSUPPORTED_CAPABILITY")
            publication = self.capabilities.get("publication")
            if (
                not isinstance(publication, dict)
                or publication.get("continuity") != "single_step_required"
                or publication.get("receipt_format") != RECEIPT_FORMAT
                or publication.get("receipt_retention") != "reachable_history"
                or publication.get("authority") not in {"mechanical", "project_validated"}
            ):
                raise PublicationFault("UNSUPPORTED_CAPABILITY")
            access = self._call("access", target=request["target"], operation="publish")
            if not isinstance(access, Mapping):
                raise PublicationFault("INVALID_SOURCE")
            result = self._publish(request, access)
            response_limit = self.limits.get("response_bytes")
            if type(response_limit) is not int or response_limit < 1024:
                raise PublicationFault("UNSUPPORTED_CAPABILITY")
            if len(restricted_jcs(result)) > response_limit:
                raise PublicationFault("LIMIT_EXCEEDED")
            return result
        except PublicationFault as exc:
            self.was_dispatched = self.was_dispatched or exc.dispatched
            return self._fail(exc.code)

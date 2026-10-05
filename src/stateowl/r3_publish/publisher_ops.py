from __future__ import annotations

from typing import Any, Mapping

from .types import PROTOCOL, PublicationFault
from .identity import _error, build_candidate, parse_receipt, publication_identity, receipt_message, request_digest

class PublisherOps:
        def _verify(
            self,
            request: Mapping[str, Any],
            snapshot: str,
            head: str | None = None,
        ) -> dict[str, Any]:
            target = request["target"]
            metadata = self._inspect_commit(target, snapshot)
            if metadata.get("type") != "commit" or metadata.get("parents") != [request["expected"]["id"]]:
                raise PublicationFault("INTEGRITY_MISMATCH")
            if parse_receipt(metadata.get("message")) != publication_identity(request):
                raise PublicationFault("INTEGRITY_MISMATCH")
            old = self._call("tree", target=target, snapshot=request["expected"]["id"])
            wanted = build_candidate(request, old)
            actual = self._call("tree", target=target, snapshot=snapshot)
            if wanted != actual:
                raise PublicationFault("INTEGRITY_MISMATCH")
            if head is None:
                head = self._call("resolve", target=target)
                continuity = self._call("access", target=target, operation="publish").get("continuity")
                if continuity != "intact":
                    raise PublicationFault("NAMESPACE_DISCONTINUITY")
                if head != snapshot:
                    self._walk(target, head, snapshot, ancestor_only=True)
            return self._committed_result(request, snapshot, head)

        def _reconcile(self, request: Mapping[str, Any]) -> dict[str, Any]:
            # No admission occurs in this method.  The prior attempt is unresolved.
            self.was_dispatched = True
            target = request["target"]
            head = self._call("resolve", target=target)
            if self._call("access", target=target, operation="publish").get("continuity") != "intact":
                raise PublicationFault("NAMESPACE_DISCONTINUITY")
            if head == request["expected"]["id"]:
                raise PublicationFault("PROVIDER_UNAVAILABLE")
            direct_child = self._walk(target, head, request["expected"]["id"])
            if direct_child is None:
                raise PublicationFault("PROVIDER_UNAVAILABLE")
            snapshot, metadata = direct_child
            if self._call("access", target=target, operation="publish").get("continuity") != "intact":
                raise PublicationFault("NAMESPACE_DISCONTINUITY")
            receipt = parse_receipt(metadata.get("message"))
            if receipt != publication_identity(request):
                return {
                    "protocol": PROTOCOL,
                    "op": "publish",
                    "outcome": "not_committed",
                    "request_digest": request_digest(request),
                    "error": _error("CONFLICT"),
                }
            self.admitted = snapshot
            return self._verify(request, snapshot, head)

        def _publish(self, request: Mapping[str, Any], access: Mapping[str, Any]) -> dict[str, Any]:
            target = request["target"]
            if target["kind"] != "git" or not target["namespace"].startswith("refs/heads/"):
                raise PublicationFault("UNSUPPORTED_CAPABILITY")
            paths = sorted((change["path"] for change in request["changes"]), key=lambda path: path.encode("utf-8"))
            self._call("authorize", target=target, operation="publish", paths=paths)
            if access.get("continuity") != "intact":
                raise PublicationFault("NAMESPACE_DISCONTINUITY")
            if request["mode"] == "reconcile":
                return self._reconcile(request)

            self._verify_expected_commit(request)
            if request["validation"] != access.get("validation"):
                raise PublicationFault("VALIDATION_FAILED")
            if request["validation"] is not None and not access.get("validator_available"):
                raise PublicationFault("UNSUPPORTED_CAPABILITY")
            if not access.get("project_authorized"):
                raise PublicationFault("FORBIDDEN")

            old = self._call("tree", target=target, snapshot=request["expected"]["id"])
            candidate = build_candidate(request, old)
            if request["validation"] is not None:
                self._call(
                    "validate",
                    target=target,
                    expected=request["expected"]["id"],
                    binding=request["validation"],
                    old=old,
                    candidate=candidate,
                )
            try:
                acknowledgment = self._call(
                    "admit",
                    target=target,
                    expected=request["expected"]["id"],
                    candidate=candidate,
                    message=receipt_message(request),
                )
            except PublicationFault as exc:
                self.was_dispatched = self.was_dispatched or exc.dispatched
                raise
            if not isinstance(acknowledgment, Mapping) or acknowledgment.get("status") not in {"conflict", "admitted"}:
                raise PublicationFault("INVALID_SOURCE")
            self.was_dispatched = True
            if acknowledgment["status"] == "conflict":
                # The attempted CAS was excluded.  Reconcile once; never redispatch.
                return self._reconcile(request)
            snapshot = acknowledgment.get("snapshot")
            if not isinstance(snapshot, str) or not snapshot:
                raise PublicationFault("INVALID_SOURCE")
            self.admitted = snapshot
            return self._verify(request, snapshot)

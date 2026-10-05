from __future__ import annotations

import base64
import hashlib
from typing import Any, Mapping

from ..r3_publish import PublicationFault

class GitHubAdmitMixin:
        def _graphql_error_code(errors: Any) -> str:
            if isinstance(errors, list):
                joined = " ".join(
                    str(item.get("type", "")) + " " + str(item.get("message", ""))
                    for item in errors
                    if isinstance(item, Mapping)
                ).upper()
                if "RATE" in joined and "LIMIT" in joined:
                    return "RATE_LIMITED"
                if "FORBIDDEN" in joined or "INSUFFICIENT" in joined:
                    return "FORBIDDEN"
                if "UNAUTH" in joined:
                    return "UNAUTHENTICATED"
            return "PROVIDER_UNAVAILABLE"

        def _admit_ref(self, target: Mapping[str, Any], expected: str, candidate_sha: str) -> bool:
            mutation = (
                "mutation StateOwlUpdateRefs($input: UpdateRefsInput!) {"
                " updateRefs(input: $input) { clientMutationId }"
                "}"
            )
            body = {
                "query": mutation,
                "variables": {
                    "input": {
                        "repositoryId": self._repository_id(),
                        "refUpdates": [
                            {
                                "name": target["namespace"],
                                "beforeOid": self._raw(expected),
                                "afterOid": candidate_sha,
                                "force": False,
                            }
                        ],
                    }
                },
            }
            response = self.transport.request(
                "POST",
                self.graphql_url,
                headers=self._headers,
                payload=body,
                dispatch_uncertain=True,
            )
            if response.status == 200 and isinstance(response.payload, Mapping) and not response.payload.get("errors"):
                return True
            if response.status != 200:
                fault = self._fault_for_status(response.status, missing="FORBIDDEN")
                if response.status >= 500:
                    raise PublicationFault(fault.code, dispatched=True)
                raise fault

            # A GraphQL CAS rejection is distinguished from transport uncertainty by
            # a fresh read.  This is read-only and never retries the mutation.
            errors = response.payload.get("errors") if isinstance(response.payload, Mapping) else None
            try:
                current = self.resolve(target)
            except PublicationFault as exc:
                if exc.code == "NOT_FOUND":
                    return False
                code = self._graphql_error_code(errors)
                raise PublicationFault(code) from None
            if current != expected:
                return False
            raise PublicationFault(self._graphql_error_code(errors))

        def admit(
            self,
            target: Mapping[str, Any],
            expected: str,
            candidate: Mapping[str, Any],
            message: str,
        ) -> Mapping[str, Any]:
            self._target(target)
            old = self.tree(target, expected)
            tree_sha = self._create_candidate_tree(expected, old, candidate)
            commit_sha = self._create_commit(tree_sha, expected, message)
            admitted = self._admit_ref(target, expected, commit_sha)
            if not admitted:
                return {"status": "conflict"}
            return {"status": "admitted", "snapshot": self._typed(commit_sha)}

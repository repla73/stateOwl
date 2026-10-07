from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

DECISIONS = {"idle", "eligible", "blocked/error", "operator_required"}


@dataclass(frozen=True)
class GateDecision:
    decision: str
    reason: str
    snapshot: str | None
    next_due: int | None
    model_allowed: bool


class QualificationGate:
    """R5 qualification-only project profile.

    This is deliberately not stateOwl core. Events are only wake hints; every
    check starts with observe. Exact project state is machine-read only when the
    observation changed/baselined or the cached deadline became due.
    """

    def __init__(
        self,
        *,
        observe: Callable[[str | None], Mapping[str, Any]],
        read_profile: Callable[[str], Mapping[str, Any]],
        claimant: str,
    ):
        if not claimant:
            raise ValueError("claimant is required")
        self._observe = observe
        self._read_profile = read_profile
        self.claimant = claimant
        self.token: str | None = None
        self.next_due: int | None = None

    def check(self, now: int) -> GateDecision:
        observed = dict(self._observe(self.token))
        if observed.get("status") == "error":
            code = observed.get("error", {}).get("code", "UNKNOWN")
            return GateDecision("blocked/error", f"observe:{code}", None, self.next_due, False)
        if observed.get("op") != "observe" or observed.get("status") not in {"baseline", "changed", "unchanged"}:
            return GateDecision("blocked/error", "observe:invalid-result", None, self.next_due, False)
        snapshot = observed.get("snapshot", {}).get("id")
        token = observed.get("token")
        if not isinstance(snapshot, str) or not snapshot or not isinstance(token, str) or not token:
            return GateDecision("blocked/error", "observe:invalid-result", None, self.next_due, False)
        self.token = token

        refresh = observed["status"] in {"baseline", "changed"} or self.next_due is None or now >= self.next_due
        if not refresh:
            return GateDecision("idle", "unchanged-not-due", snapshot, self.next_due, False)

        try:
            profile = dict(self._read_profile(snapshot))
        except Exception:
            return GateDecision("blocked/error", "profile-read-failed", snapshot, self.next_due, False)

        if profile.get("schema") != "stateowl.r5-qualification-job/1":
            return GateDecision("blocked/error", "profile-invalid", snapshot, self.next_due, False)
        due_at = profile.get("due_at")
        if type(due_at) is not int:
            return GateDecision("blocked/error", "profile-invalid", snapshot, self.next_due, False)
        self.next_due = due_at

        effect = profile.get("effect")
        if isinstance(effect, Mapping) and effect.get("status") == "unknown":
            return GateDecision("operator_required", "effect-outcome-unknown", snapshot, due_at, False)
        if profile.get("blocked") is True:
            return GateDecision("blocked/error", "profile-blocked", snapshot, due_at, False)
        if now < due_at:
            return GateDecision("idle", "not-due", snapshot, due_at, False)

        claim = profile.get("claim")
        if claim is not None:
            if not isinstance(claim, Mapping):
                return GateDecision("blocked/error", "claim-invalid", snapshot, due_at, False)
            owner = claim.get("owner")
            expires_at = claim.get("expires_at")
            if not isinstance(owner, str) or not owner or type(expires_at) is not int:
                return GateDecision("blocked/error", "claim-invalid", snapshot, due_at, False)
            if owner != self.claimant and now < expires_at:
                self.next_due = expires_at
                return GateDecision("idle", "claimed-by-other", snapshot, self.next_due, False)
            if owner != self.claimant and now >= expires_at:
                return GateDecision("eligible", "expired-claim-takeover-candidate", snapshot, due_at, False)
            if owner == self.claimant and now >= expires_at:
                return GateDecision("eligible", "claim-renewal-required", snapshot, due_at, False)
            if owner == self.claimant:
                return GateDecision("eligible", "claim-owned", snapshot, due_at, True)

        return GateDecision("eligible", "claim-acquisition-required", snapshot, due_at, False)

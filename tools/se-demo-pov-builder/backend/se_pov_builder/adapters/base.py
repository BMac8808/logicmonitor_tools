"""Integration adapter contracts.

Standard library only, so this module can move to ``shared/`` once a second tool needs it.

Rules every adapter follows:

* Each action is declared up front as READ_ONLY or STATE_CHANGING.
* STATE_CHANGING actions require an ``Authorization`` that names the action, has a
  person and a reason, and has not expired. This is enforced in ``Adapter.execute`` for
  mock adapters too, so the contract is exercised by tests.
* Results say whether they are simulated. Mock results are always simulated.
* Live implementations must be written only against verified official documentation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ActionKind(StrEnum):
    READ_ONLY = "read_only"
    STATE_CHANGING = "state_changing"


@dataclass(frozen=True)
class ActionParam:
    name: str
    type: str = "string"
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class ActionSpec:
    name: str
    kind: ActionKind
    description: str
    params: tuple[ActionParam, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data


@dataclass(frozen=True)
class Authorization:
    """Explicit, scoped approval for state-changing actions.

    ``scope`` lists ``"<adapter_id>:<action>"`` strings.
    """

    approved_by: str
    reason: str
    scope: tuple[str, ...]
    expires_at: datetime

    def covers(self, adapter_id: str, action: str, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        expires = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=UTC)
        return (
            bool(self.approved_by.strip())
            and bool(self.reason.strip())
            and f"{adapter_id}:{action}" in self.scope
            and expires > now
        )


@dataclass
class AdapterResult:
    adapter_id: str
    action: str
    kind: ActionKind
    simulated: bool
    data: Any
    message: str = ""
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data


class AdapterError(Exception):
    pass


class UnknownAction(AdapterError):
    pass


class InvalidParams(AdapterError):
    pass


class AuthorizationRequired(AdapterError):
    pass


class Adapter(ABC):
    id: str
    name: str
    description: str
    mode: str  # "mock" or "live"
    verified: bool = False  # True only once checked against official documentation
    notes: str = ""

    @abstractmethod
    def actions(self) -> list[ActionSpec]: ...

    @abstractmethod
    def _run(self, spec: ActionSpec, params: dict[str, Any]) -> AdapterResult: ...

    def action(self, name: str) -> ActionSpec:
        for spec in self.actions():
            if spec.name == name:
                return spec
        raise UnknownAction(f"Adapter '{self.id}' has no action '{name}'")

    def execute(
        self, action: str, params: dict[str, Any] | None = None, authorization: Authorization | None = None
    ) -> AdapterResult:
        spec = self.action(action)
        params = params or {}
        known = {p.name for p in spec.params}
        unknown = set(params) - known
        if unknown:
            raise InvalidParams(f"Unknown parameter(s): {', '.join(sorted(unknown))}")
        missing = [p.name for p in spec.params if p.required and params.get(p.name) in (None, "")]
        if missing:
            raise InvalidParams(f"Missing required parameter(s): {', '.join(missing)}")
        if spec.kind is ActionKind.STATE_CHANGING and (
            authorization is None or not authorization.covers(self.id, action)
        ):
            raise AuthorizationRequired(
                f"'{self.id}:{action}' changes state and requires an unexpired authorization "
                "naming this action, the approver and a reason"
            )
        return self._run(spec, params)

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "mode": self.mode,
            "verified": self.verified,
            "notes": self.notes,
            "actions": [a.as_dict() for a in self.actions()],
        }

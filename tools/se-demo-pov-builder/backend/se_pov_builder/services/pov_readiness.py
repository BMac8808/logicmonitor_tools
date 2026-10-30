"""Read-only POV readiness checks through the LogicMonitor MCP adapter.

Each check reports what was asked (tool + arguments) so results can be traced. When the
adapter is in mock mode every result is simulated and labelled as such.
"""

from __future__ import annotations

import re
from typing import Any

from ..adapters.base import Adapter, AdapterError
from ..models import Account, PovPlan, utcnow

_UNSAFE = re.compile(r"[^\w .()&'-]")


def default_group_name(account: Account) -> str:
    return _UNSAFE.sub("", f"POV - {account.name}").strip()[:200]


def group_name(plan: PovPlan, account: Account) -> str:
    return plan.portal_group or default_group_name(account)


def _lm_quote(value: str) -> str:
    return '"' + value.replace('"', "") + '"'


def run_readiness(adapter: Adapter, plan: PovPlan, account: Account) -> dict[str, Any]:
    group = group_name(plan, account)
    checks: list[dict[str, Any]] = []
    simulated: set[bool] = set()

    def call(action: str, params: dict[str, Any]) -> dict[str, Any]:
        result = adapter.execute(action, params)
        simulated.add(result.simulated)
        return result.data

    def check(check_id: str, title: str, fn) -> None:
        calls: list[dict[str, Any]] = []

        def traced(action: str, params: dict[str, Any]) -> dict[str, Any]:
            data = call(action, params)
            calls.append({"tool": data["tool"], "arguments": data["arguments"], "total": data.get("total")})
            return data

        try:
            status, detail = fn(traced)
        except AdapterError as exc:
            status, detail = "error", str(exc)
        checks.append({"id": check_id, "title": title, "status": status, "detail": detail, "calls": calls})

    def collectors(q):
        total = q("list_collectors", {"size": 1})["total"] or 0
        down = q("list_collectors", {"filter": "isDown:true", "size": 5})
        down_total = down["total"] or 0
        if total == 0:
            return "fail", "No collectors found. Install at least one collector before onboarding resources."
        if down_total:
            names = ", ".join(str(i.get("description") or i.get("hostname") or i.get("id")) for i in down["items"])
            return "warn", f"{down_total} of {total} collectors are down: {names}"
        return "ok", f"{total} collectors, none down"

    def pov_group(q):
        data = q("list_resource_groups", {"filter": f"name:{_lm_quote(group)}", "size": 5})
        if not data["items"]:
            return "warn", f"Resource group '{group}' not found. Run the generated setup script to create it."
        item = data["items"][0]
        hosts = item.get("numOfHosts")
        detail = f"Resource group '{group}' exists (id {item.get('id')})"
        if hosts not in (None, ""):
            detail += f" with {hosts} resources"
            if str(hosts) == "0":
                return "warn", detail + ". No resources onboarded yet."
        return "ok", detail

    def critical_alerts(q):
        total = q("list_alerts", {"filter": "severity:4", "size": 1})["total"] or 0
        if total:
            return "warn", f"{total} critical alerts returned by the portal's alert list (portal-wide)"
        return "ok", "No critical alerts returned by the portal's alert list"

    check("collectors", "Collectors available", collectors)
    check("pov_group", "POV resource group", pov_group)
    check("critical_alerts", "Critical alerts", critical_alerts)

    is_simulated = adapter.mode == "mock" or True in simulated
    return {
        "group_name": group,
        "adapter_mode": adapter.mode,
        "simulated": is_simulated,
        "source": "mock fixtures (synthetic)" if adapter.mode == "mock" else "logicmonitor-api-mcp (read-only)",
        "checked_at": utcnow().isoformat(),
        "checks": checks,
    }

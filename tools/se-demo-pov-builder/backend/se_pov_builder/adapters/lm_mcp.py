"""Read-only adapter over the public logicmonitor-api-mcp server
(https://github.com/logicmonitor/logicmonitor-api-mcp, MPL-2.0).

Tool names and arguments match that server's registry (``lm_collector``,
``lm_device_group``, ``lm_device``, ``lm_alert``, ``lm_dashboard`` with
``operation: "list"``). This adapter exposes list operations only. Portal changes are
made by generated Logic.Monitor PowerShell scripts that a person reviews and runs.

Modes:
* ``mock`` – synthetic fixtures in the same result format as the real server, so the
  parser and readiness checks are exercised without a portal. Results are simulated.
* ``mcp``  – calls an MCP server you run yourself (``SEPB_MCP_URL``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from .base import ActionKind, ActionParam, ActionSpec, Adapter, AdapterResult
from .mcp_client import MCPClient, parse_tool_result

R = ActionKind.READ_ONLY
_LIST_PARAMS = (
    ActionParam("filter", description='LogicMonitor filter expression, e.g. isDown:true or name:"POV - Example"'),
    ActionParam("size", type="integer", description="Items per page (1-1000)"),
    ActionParam("fields", description="Comma-separated fields to return (only fields this app passes on are shown)"),
)
ACTIONS: list[tuple[ActionSpec, str]] = [
    (ActionSpec("list_collectors", R, "List collectors (lm_collector list).", _LIST_PARAMS), "lm_collector"),
    (ActionSpec("list_resource_groups", R, "List resource groups (lm_device_group list).", _LIST_PARAMS),
     "lm_device_group"),
    (ActionSpec("list_resources", R, "List resources (lm_device list).", _LIST_PARAMS), "lm_device"),
    (ActionSpec("list_alerts", R, "List alerts (lm_alert list).", _LIST_PARAMS), "lm_alert"),
    (ActionSpec("list_dashboards", R, "List dashboards (lm_dashboard list).", _LIST_PARAMS), "lm_dashboard"),
]
TOOL_FOR_ACTION = {spec.name: tool for spec, tool in ACTIONS}

# Fields passed on per tool. The server returns full LogicMonitor records, which carry secrets
# and config (a collector has bearerToken and its agent/wrapper/sbproxy config files; resources and
# groups carry custom, inherited and system properties). Anything not listed here is dropped.
SAFE_FIELDS: dict[str, frozenset[str]] = {
    "lm_collector": frozenset({
        "id", "description", "hostname", "status", "isDown", "inSDT", "collectorGroupId", "collectorGroupName",
        "collectorSize", "build", "platform", "arch", "upTime", "backupAgentId", "enableFailBack",
        "numberOfHosts", "numberOfInstances", "numberOfWebsites"}),
    "lm_device_group": frozenset({
        "id", "name", "fullPath", "parentId", "description", "groupType", "appliesTo", "disableAlerting",
        "numOfHosts", "numOfDirectDevices", "numOfDirectSubGroups"}),
    "lm_device": frozenset({
        "id", "name", "displayName", "description", "deviceType", "hostStatus", "alertStatus", "sdtStatus",
        "disableAlerting", "hostGroupIds", "preferredCollectorId", "currentCollectorId", "collectorDescription",
        "createdOn", "updatedOn", "lastDataTime", "upTimeInSeconds"}),
    "lm_alert": frozenset({
        "id", "type", "severity", "monitorObjectName", "monitorObjectType", "resourceTemplateName",
        "resourceTemplateType", "instanceName", "dataPointName", "alertValue", "threshold", "startEpoch",
        "endEpoch", "cleared", "acked", "sdted", "rule", "chain"}),
    "lm_dashboard": frozenset({"id", "name", "description", "groupId", "groupName", "groupFullPath", "sharable"}),
}


def _safe_items(tool: str, items: list[Any]) -> list[dict[str, Any]]:
    allowed = SAFE_FIELDS[tool]
    return [{k: v for k, v in item.items() if k in allowed} for item in items if isinstance(item, dict)]


_FILTER_TERM = re.compile(r'\s*([\w.]+)\s*:\s*("([^"]*)"|[^,]*)\s*(?:,|$)')


def _mock_filter(items: list[dict[str, Any]], expression: str) -> list[dict[str, Any]]:
    """Tiny subset of LM filter syntax for fixtures: comma-separated AND of field:value,
    quoted values, and * wildcards."""
    terms = [(m.group(1), m.group(3) if m.group(3) is not None else m.group(2).strip())
             for m in _FILTER_TERM.finditer(expression) if m.group(1)]

    def matches(item: dict[str, Any]) -> bool:
        for field, value in terms:
            actual = str(item.get(field, "")).lower()
            pattern = "^" + re.escape(value.lower()).replace(r"\*", ".*") + "$"
            if not re.match(pattern, actual):
                return False
        return True

    return [i for i in items if matches(i)]


class LogicMonitorMCPAdapter(Adapter):
    id = "lm_mcp"
    name = "LogicMonitor API MCP server"
    description = ("Read-only checks through the public logicmonitor-api-mcp server. "
                   "Portal changes are made by generated, reviewed PowerShell scripts instead.")

    def __init__(self, mode: str, fixtures_dir: Path, url: str = "", token: str = "", timeout: float = 30.0,
                 transport: httpx.BaseTransport | None = None):
        self.mode = mode
        self.verified = mode == "mcp"  # tool names verified against the server's registry
        self.url = url
        self._token = token
        self._timeout = timeout
        self._transport = transport
        self.notes = (f"Reads from the MCP server at {url}." if mode == "mcp" else
                      "Mock mode: synthetic fixtures in the server's result format. No network calls.")
        path = fixtures_dir / "lm_mcp.json"
        self._fixtures: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def actions(self) -> list[ActionSpec]:
        return [spec for spec, _ in ACTIONS]

    def _arguments(self, params: dict[str, Any]) -> dict[str, Any]:
        args: dict[str, Any] = {"operation": "list"}
        if params.get("filter"):
            args["filter"] = str(params["filter"])
        if params.get("size") not in (None, ""):
            args["size"] = max(1, min(1000, int(params["size"])))
        if params.get("fields"):
            args["fields"] = str(params["fields"])
        return args

    def _mock_result(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        items = list(self._fixtures.get(tool, []))
        if args.get("filter"):
            items = _mock_filter(items, args["filter"])
        total = len(items)
        items = items[: args.get("size", 50)]
        payload = {"total": total, "items": items}
        return {"content": [
            {"type": "text", "text": f"Mock {tool} list succeeded."},
            {"type": "text", "text": "Full LogicMonitor payload:\n" + json.dumps(payload)},
        ]}

    def _run(self, spec: ActionSpec, params: dict[str, Any]) -> AdapterResult:
        tool = TOOL_FOR_ACTION[spec.name]
        args = self._arguments(params)
        if self.mode == "mock":
            raw = self._mock_result(tool, args)
        else:
            client = MCPClient(self.url, self._token, self._timeout, self._transport)
            try:
                raw = client.call_tool(tool, args)
            finally:
                client.close()
        parsed = parse_tool_result(raw)
        parsed["items"] = _safe_items(tool, parsed["items"])
        # An unparsed payload would otherwise be passed on whole as raw text.
        if parsed.pop("text", None):
            parsed["summary"] += " (Result format not recognised; raw output withheld.)"
        return AdapterResult(
            self.id, spec.name, spec.kind, simulated=self.mode == "mock",
            data={**parsed, "tool": tool, "arguments": args},
            message=("Synthetic mock data. Not from a real portal." if self.mode == "mock"
                     else f"Read via logicmonitor-api-mcp ({tool} list)."),
        )

    def describe(self) -> dict[str, Any]:
        data = super().describe()
        for action in data["actions"]:
            action["mcp_tool"] = TOOL_FOR_ACTION[action["name"]]
        data["url"] = self.url if self.mode == "mcp" else ""
        return data


def build_registry(settings, fixtures_dir: Path, transport: httpx.BaseTransport | None = None) -> dict[str, Adapter]:
    adapter = LogicMonitorMCPAdapter(settings.adapter_mode, fixtures_dir, settings.mcp_url, settings.mcp_token,
                                     settings.mcp_timeout_seconds, transport)
    return {adapter.id: adapter}

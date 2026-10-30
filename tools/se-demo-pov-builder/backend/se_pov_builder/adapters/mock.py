"""Mock adapters returning synthetic fixtures from ``adapters/mock_responses/``.

Action names are intentionally abstract. They are NOT mapped to real endpoint paths,
cmdlet names or tool names; that mapping will be added only when a live adapter is
implemented and verified against official documentation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import ActionKind, ActionParam, ActionSpec, Adapter, AdapterResult

R, W = ActionKind.READ_ONLY, ActionKind.STATE_CHANGING
MOCK_NOTE = "Mock only. Returns synthetic fixture data; no network calls are made."

ADAPTER_SPECS: dict[str, dict[str, Any]] = {
    "lm_rest_api": {
        "name": "LogicMonitor REST API",
        "description": "Planned adapter for the platform REST API (resources, groups, alerts, collectors).",
        "actions": [
            ActionSpec("list_resources", R, "List monitored resources, optionally filtered by group.",
                       (ActionParam("group", description="Resource group name filter"),)),
            ActionSpec("list_resource_groups", R, "List resource groups."),
            ActionSpec("get_alert_summary", R, "Summarise open alerts by severity."),
            ActionSpec("list_collectors", R, "List data collectors and their status."),
            ActionSpec("create_resource_group", W, "Create a resource group.",
                       (ActionParam("name", required=True), ActionParam("parent"))),
            ActionSpec("schedule_maintenance_window", W, "Schedule a maintenance window for a resource.",
                       (ActionParam("resource", required=True), ActionParam("start", required=True),
                        ActionParam("end", required=True))),
        ],
    },
    "lm_powershell": {
        "name": "LogicMonitor PowerShell module",
        "description": "Planned adapter that runs scripts using a community PowerShell module.",
        "actions": [
            ActionSpec("test_connection", R, "Check that a session to the portal can be established."),
            ActionSpec("export_resources", R, "Export resources to a CSV-style list.",
                       (ActionParam("group"),)),
            ActionSpec("import_resources", W, "Bulk-import resources from a list.",
                       (ActionParam("rows", type="array", required=True),)),
        ],
    },
    "logicmodule_tools": {
        "name": "LogicModule development utilities",
        "description": "Planned utilities for reviewing and editing LogicModule definitions.",
        "actions": [
            ActionSpec("list_modules", R, "List modules of a given type.",
                       (ActionParam("module_type", description="e.g. datasource"),)),
            ActionSpec("lint_module", R, "Run offline checks on a module definition.",
                       (ActionParam("module_name", required=True),)),
            ActionSpec("propose_module_update", W, "Submit an updated module definition.",
                       (ActionParam("module_name", required=True),
                        ActionParam("definition", type="object", required=True))),
        ],
    },
    "lm_mcp": {
        "name": "LogicMonitor MCP integration",
        "description": "Planned Model Context Protocol bridge for assistant-driven, read-mostly queries.",
        "actions": [
            ActionSpec("list_tools", R, "List tools exposed by the MCP server."),
            ActionSpec("query", R, "Run a read-only query through the MCP server.",
                       (ActionParam("question", required=True),)),
            ActionSpec("invoke_tool", W, "Invoke a state-changing MCP tool.",
                       (ActionParam("tool", required=True), ActionParam("arguments", type="object"))),
        ],
    },
}


class MockAdapter(Adapter):
    mode = "mock"
    verified = False
    notes = MOCK_NOTE

    def __init__(self, adapter_id: str, fixtures_dir: Path):
        spec = ADAPTER_SPECS[adapter_id]
        self.id = adapter_id
        self.name = spec["name"]
        self.description = spec["description"]
        self._actions: list[ActionSpec] = spec["actions"]
        path = fixtures_dir / f"{adapter_id}.json"
        self._fixtures: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def actions(self) -> list[ActionSpec]:
        return self._actions

    def _run(self, spec: ActionSpec, params: dict[str, Any]) -> AdapterResult:
        if spec.kind is ActionKind.STATE_CHANGING:
            return AdapterResult(
                self.id, spec.name, spec.kind, simulated=True,
                data={"applied": False, "would_apply": {"action": spec.name, "params": params}},
                message="Dry run: mock adapters never change state.",
            )
        data = self._fixtures.get(spec.name)
        if spec.name == "list_resources" and params.get("group") and isinstance(data, list):
            data = [r for r in data if r.get("group") == params["group"]]
        return AdapterResult(
            self.id, spec.name, spec.kind, simulated=True,
            data=data if data is not None else [],
            message="Synthetic mock data. Not from a real environment.",
        )


def build_registry(fixtures_dir: Path) -> dict[str, Adapter]:
    return {adapter_id: MockAdapter(adapter_id, fixtures_dir) for adapter_id in ADAPTER_SPECS}

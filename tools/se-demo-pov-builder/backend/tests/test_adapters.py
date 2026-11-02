import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from se_pov_builder.adapters import base
from se_pov_builder.adapters.base import (
    ActionKind,
    ActionSpec,
    Adapter,
    AdapterResult,
    Authorization,
    AuthorizationRequired,
    InvalidParams,
)
from se_pov_builder.adapters.lm_mcp import LogicMonitorMCPAdapter
from se_pov_builder.adapters.mcp_client import MCPClient, MCPError, parse_tool_result
from se_pov_builder.config import TOOL_ROOT

FIXTURES = TOOL_ROOT / "adapters" / "mock_responses"


def sse(message: dict) -> str:
    return f"event: message\ndata: {json.dumps(message)}\n\n"


class FakeMCPServer:
    """Speaks just enough Streamable HTTP MCP to test the client: SSE responses, session ids."""

    def __init__(self, tool_results: dict[str, dict], require_token: str = ""):
        self.tool_results = tool_results
        self.require_token = require_token
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.require_token and request.headers.get("authorization") != f"Bearer {self.require_token}":
            return httpx.Response(401, json={"error": "Authentication required"})
        if request.method == "DELETE":
            return httpx.Response(200)
        msg = json.loads(request.content)
        if msg["method"] == "initialize":
            body = sse({"jsonrpc": "2.0", "id": msg["id"], "result": {
                "protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "0"}}})
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream",
                                                            "mcp-session-id": "sess-1"})
        if msg["method"] == "notifications/initialized":
            return httpx.Response(202)
        if msg["method"] == "tools/call":
            assert request.headers["mcp-session-id"] == "sess-1"
            result = self.tool_results[msg["params"]["name"]]
            if callable(result):  # results may depend on the tool arguments
                result = result(msg["params"]["arguments"])
            return httpx.Response(200, text=sse({"jsonrpc": "2.0", "id": msg["id"], "result": result}),
                                  headers={"content-type": "text/event-stream"})
        return httpx.Response(400)


def json_result(items, total=None):
    payload = {"total": len(items) if total is None else total, "items": items}
    return {"content": [{"type": "text", "text": "LogicMonitor Collectors list succeeded."},
                        {"type": "text", "text": "Full LogicMonitor payload:\n" + json.dumps(payload, indent=2)}]}


def test_parse_json_payload():
    parsed = parse_tool_result(json_result([{"id": 1, "isDown": False}], total=12))
    assert parsed["format"] == "json" and parsed["total"] == 12 and parsed["items"][0]["id"] == 1


def test_parse_compact_table_payload():
    table = ("Items (6 of 40):\n| id | description | hostname | status |\n| 11 | col-a | a.example | 1 |\n"
             "| 12 | col-b | b.example | 1 |\n\nFull item details available via: lm_session get ...")
    parsed = parse_tool_result({"content": [{"type": "text", "text": "ok"}, {"type": "text", "text": table}]})
    assert parsed["format"] == "table" and parsed["total"] == 40
    assert parsed["items"][1] == {"id": "12", "description": "col-b", "hostname": "b.example", "status": "1"}


def test_parse_error_result():
    with pytest.raises(MCPError, match="LogicMonitor API error"):
        parse_tool_result({"isError": True, "content": [{"type": "text", "text": "LogicMonitor API error (403)"}]})


def test_client_session_headers_and_no_lm_credentials():
    server = FakeMCPServer({"lm_collector": json_result([])}, require_token="mcp-secret")
    client = MCPClient("http://127.0.0.1:3000/mcp", token="mcp-secret", transport=httpx.MockTransport(server))
    client.call_tool("lm_collector", {"operation": "list"})
    client.close()
    methods = [json.loads(r.content)["method"] for r in server.requests if r.method == "POST"]
    assert methods == ["initialize", "notifications/initialized", "tools/call"]
    call = server.requests[2]
    assert call.headers["mcp-protocol-version"] == "2025-06-18"
    assert "text/event-stream" in call.headers["accept"]
    assert server.requests[-1].method == "DELETE"
    for r in server.requests:  # LogicMonitor credentials stay on the MCP server
        assert not any(h.lower().startswith("x-lm-") for h in r.headers)


def test_client_reports_auth_and_connection_errors():
    server = FakeMCPServer({}, require_token="right")
    client = MCPClient("http://x/mcp", token="wrong", transport=httpx.MockTransport(server))
    with pytest.raises(MCPError, match="SEPB_MCP_TOKEN"):
        client.call_tool("lm_collector", {"operation": "list"})

    def boom(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(MCPError, match="Cannot reach MCP server"):
        MCPClient("http://x/mcp", transport=httpx.MockTransport(boom)).call_tool("lm_collector", {})


def test_mock_mode_is_read_only_and_simulated():
    adapter = LogicMonitorMCPAdapter("mock", FIXTURES)
    assert {a.kind for a in adapter.actions()} == {ActionKind.READ_ONLY}
    assert adapter.verified is False
    result = adapter.execute("list_collectors", {"filter": "isDown:true", "size": 5})
    assert result.simulated and result.data["total"] == 1
    assert result.data["tool"] == "lm_collector" and result.data["arguments"]["operation"] == "list"
    groups = adapter.execute("list_resource_groups", {"filter": 'name:"POV - Quillfeather*"'}).data
    assert groups["items"][0]["numOfHosts"] == 41
    assert {a["mcp_tool"] for a in adapter.describe()["actions"]} >= {"lm_collector", "lm_alert"}
    with pytest.raises(InvalidParams):
        adapter.execute("list_collectors", {"operation": "delete"})


def test_mcp_mode_reads_through_server():
    server = FakeMCPServer({"lm_collector": json_result([{"id": 7, "isDown": False}])})
    adapter = LogicMonitorMCPAdapter("mcp", FIXTURES, url="http://127.0.0.1:3000/mcp",
                                     transport=httpx.MockTransport(server))
    result = adapter.execute("list_collectors", {"size": 1})
    assert result.simulated is False and result.data["items"] == [{"id": 7, "isDown": False}]
    sent = json.loads(server.requests[2].content)["params"]
    assert sent == {"name": "lm_collector", "arguments": {"operation": "list", "size": 1}}


def test_mcp_results_keep_only_safe_fields():
    # Full collector records carry the collector's bearer token and its config files.
    collector = {"id": 7, "description": "c1", "hostname": "c1.example", "isDown": True,
                 "bearerToken": "secret", "collectorConf": "x", "wrapperConf": "y", "customProperties": []}
    group = {"id": 9, "name": "POV", "numOfHosts": 3, "customProperties": [{"name": "snmp.community"}],
             "extra": {}, "rolePrivileges": ["write"]}
    server = FakeMCPServer({"lm_collector": json_result([collector]), "lm_device_group": json_result([group])})
    adapter = LogicMonitorMCPAdapter("mcp", FIXTURES, url="http://127.0.0.1:3000/mcp",
                                     transport=httpx.MockTransport(server))
    items = adapter.execute("list_collectors", {}).data["items"]
    assert items == [{"id": 7, "description": "c1", "hostname": "c1.example", "isDown": True}]
    assert adapter.execute("list_resource_groups", {}).data["items"] == [{"id": 9, "name": "POV", "numOfHosts": 3}]


def test_unrecognised_mcp_output_is_withheld():
    raw = {"content": [{"type": "text", "text": "ok"}, {"type": "text", "text": '{"bearerToken": "secret"}'}]}
    server = FakeMCPServer({"lm_collector": raw})
    adapter = LogicMonitorMCPAdapter("mcp", FIXTURES, url="http://127.0.0.1:3000/mcp",
                                     transport=httpx.MockTransport(server))
    data = adapter.execute("list_collectors", {}).data
    assert "text" not in data and "secret" not in json.dumps(data)
    assert data["items"] == [] and "raw output withheld" in data["summary"]


def test_mock_fixtures_only_use_safe_fields():
    from se_pov_builder.adapters.lm_mcp import SAFE_FIELDS

    fixtures = json.loads((FIXTURES / "lm_mcp.json").read_text())
    for tool, allowed in SAFE_FIELDS.items():
        assert {k for item in fixtures[tool] for k in item} <= allowed, tool


# --- Base contract (kept for future adapters that declare state-changing actions) ----
class _WriteAdapter(Adapter):
    id, name, description, mode = "demo", "Demo", "", "mock"

    def actions(self):
        return [ActionSpec("create_thing", ActionKind.STATE_CHANGING, "", (base.ActionParam("name", required=True),))]

    def _run(self, spec, params):
        return AdapterResult(self.id, spec.name, spec.kind, True, {"applied": False})


def test_state_changing_requires_scoped_unexpired_authorization():
    adapter = _WriteAdapter()
    future = datetime.now(UTC) + timedelta(hours=1)
    with pytest.raises(AuthorizationRequired):
        adapter.execute("create_thing", {"name": "x"})
    for auth in (
        Authorization("Alex", "Lab", ("demo:other",), future),
        Authorization("Alex", "Lab", ("demo:create_thing",), datetime.now(UTC) - timedelta(minutes=1)),
        Authorization("Alex", " ", ("demo:create_thing",), future),
    ):
        with pytest.raises(AuthorizationRequired):
            adapter.execute("create_thing", {"name": "x"}, auth)
    ok = Authorization("Alex", "Lab", ("demo:create_thing",), future)
    assert adapter.execute("create_thing", {"name": "x"}, ok).data == {"applied": False}


def test_api_endpoints(client):
    adapters = client.get("/api/adapters").json()
    assert [a["id"] for a in adapters] == ["lm_mcp"] and adapters[0]["mode"] == "mock"
    r = client.post("/api/adapters/lm_mcp/actions/list_alerts", json={"params": {"filter": "severity:4"}})
    assert r.status_code == 200 and r.json()["simulated"] is True and r.json()["data"]["total"] == 1
    assert client.post("/api/adapters/nope/actions/x", json={}).status_code == 404
    assert client.post("/api/adapters/lm_mcp/actions/delete_everything", json={}).status_code == 404


def test_contract_module_uses_only_stdlib():
    tree = ast.parse(Path(base.__file__).read_text())
    imported = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imported <= {"__future__", "abc", "dataclasses", "datetime", "enum", "typing"}

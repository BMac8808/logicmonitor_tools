import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from se_pov_builder.adapters import base
from se_pov_builder.adapters.base import ActionKind, Authorization, AuthorizationRequired, InvalidParams
from se_pov_builder.adapters.mock import build_registry
from se_pov_builder.config import TOOL_ROOT

FIXTURES = TOOL_ROOT / "adapters" / "mock_responses"


@pytest.fixture
def registry():
    return build_registry(FIXTURES)


def future():
    return datetime.now(UTC) + timedelta(hours=1)


def test_all_adapters_are_mock_and_unverified(registry):
    assert set(registry) == {"lm_rest_api", "lm_powershell", "logicmodule_tools", "lm_mcp"}
    for adapter in registry.values():
        assert adapter.mode == "mock" and adapter.verified is False
        kinds = {a.kind for a in adapter.actions()}
        assert kinds == {ActionKind.READ_ONLY, ActionKind.STATE_CHANGING}


def test_read_only_returns_simulated_data(registry):
    result = registry["lm_rest_api"].execute("list_resources", {"group": "Synthetic Lab/Network"})
    assert result.simulated is True
    assert result.data and all(r["group"] == "Synthetic Lab/Network" for r in result.data)


def test_state_changing_requires_authorization(registry):
    adapter = registry["lm_rest_api"]
    with pytest.raises(AuthorizationRequired):
        adapter.execute("create_resource_group", {"name": "X"})
    wrong_scope = Authorization("Alex", "Testing", ("lm_rest_api:list_resources",), future())
    with pytest.raises(AuthorizationRequired):
        adapter.execute("create_resource_group", {"name": "X"}, wrong_scope)
    expired = Authorization("Alex", "Testing", ("lm_rest_api:create_resource_group",),
                            datetime.now(UTC) - timedelta(minutes=1))
    with pytest.raises(AuthorizationRequired):
        adapter.execute("create_resource_group", {"name": "X"}, expired)
    no_reason = Authorization("Alex", " ", ("lm_rest_api:create_resource_group",), future())
    with pytest.raises(AuthorizationRequired):
        adapter.execute("create_resource_group", {"name": "X"}, no_reason)

    ok = Authorization("Alex", "Lab setup", ("lm_rest_api:create_resource_group",), future())
    result = adapter.execute("create_resource_group", {"name": "X"}, ok)
    assert result.simulated and result.data["applied"] is False


def test_param_validation(registry):
    with pytest.raises(InvalidParams):
        registry["logicmodule_tools"].execute("lint_module", {})
    with pytest.raises(InvalidParams):
        registry["lm_rest_api"].execute("list_resources", {"unexpected": 1})


def test_api_endpoints(client):
    adapters = client.get("/api/adapters").json()
    assert all(a["mode"] == "mock" for a in adapters)
    r = client.post("/api/adapters/lm_rest_api/actions/get_alert_summary", json={})
    assert r.status_code == 200 and r.json()["simulated"] is True
    r = client.post("/api/adapters/lm_rest_api/actions/create_resource_group", json={"params": {"name": "X"}})
    assert r.status_code == 403
    r = client.post("/api/adapters/lm_rest_api/actions/create_resource_group", json={
        "params": {"name": "X"},
        "authorization": {"approved_by": "Alex", "reason": "Lab", "scope": ["lm_rest_api:create_resource_group"],
                          "expires_at": future().isoformat()}})
    assert r.status_code == 200 and r.json()["data"]["applied"] is False
    assert client.post("/api/adapters/nope/actions/x", json={}).status_code == 404
    assert client.post("/api/adapters/lm_rest_api/actions/nope", json={}).status_code == 404


def test_contract_module_uses_only_stdlib():
    tree = ast.parse(Path(base.__file__).read_text())
    imported = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imported <= {"__future__", "abc", "dataclasses", "datetime", "enum", "typing"}

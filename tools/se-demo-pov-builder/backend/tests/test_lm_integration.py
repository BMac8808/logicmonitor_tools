"""Readiness checks (MCP), generated PowerShell setup scripts and the handoff export."""

import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from se_pov_builder.app import create_app
from se_pov_builder.services.handoff import HandoffPackage
from se_pov_builder.services.powershell_script import ps_str

from .test_adapters import FakeMCPServer, json_result


@pytest.fixture
def sample(client):
    deal_id = client.post("/api/sample-data").json()["deal_id"]
    pov_id = client.get(f"/api/deals/{deal_id}/pov-plans").json()[0]["id"]
    return deal_id, pov_id


def checks_by_id(result):
    return {c["id"]: c for c in result["checks"]}


def test_readiness_in_mock_mode_is_simulated(client, sample):
    _, pov_id = sample
    pov = client.get(f"/api/pov-plans/{pov_id}").json()
    assert pov["portal_group"] == "POV - Quillfeather Freight Co. (fictional)"
    result = client.post(f"/api/pov-plans/{pov_id}/readiness").json()
    assert result["simulated"] is True and result["adapter_mode"] == "mock"
    checks = checks_by_id(result)
    assert checks["collectors"]["status"] == "warn" and "1 of 3" in checks["collectors"]["detail"]
    assert checks["pov_group"]["status"] == "ok" and "41 resources" in checks["pov_group"]["detail"]
    assert checks["critical_alerts"]["status"] == "warn"
    assert checks["collectors"]["calls"][1]["arguments"] == {"operation": "list", "filter": "isDown:true", "size": 5}


def test_readiness_reports_missing_group(client, sample):
    _, pov_id = sample
    client.patch(f"/api/pov-plans/{pov_id}", json={"portal_group": "POV - Someone Else"})
    checks = checks_by_id(client.post(f"/api/pov-plans/{pov_id}/readiness").json())
    assert checks["pov_group"]["status"] == "warn" and "setup script" in checks["pov_group"]["detail"]


def test_readiness_live_mode_via_mcp(settings):
    server = FakeMCPServer({
        "lm_collector": lambda args: json_result([] if "isDown:true" in args.get("filter", "") else
                                                 [{"id": 1, "description": "c1", "isDown": False}]),
        "lm_device_group": json_result([]),
        "lm_alert": json_result([], total=0),
    })
    settings.adapter_mode = "mcp"
    with TestClient(create_app(settings, mcp_transport=httpx.MockTransport(server))) as c:
        deal_id = c.post("/api/sample-data").json()["deal_id"]
        pov_id = c.get(f"/api/deals/{deal_id}/pov-plans").json()[0]["id"]
        result = c.post(f"/api/pov-plans/{pov_id}/readiness").json()
    assert result["simulated"] is False
    checks = checks_by_id(result)
    assert checks["collectors"]["status"] == "ok"
    assert checks["pov_group"]["status"] == "warn"
    assert checks["critical_alerts"]["status"] == "ok"
    group_call = next(json.loads(r.content) for r in server.requests
                      if r.method == "POST" and b"lm_device_group" in r.content)
    assert group_call["params"]["arguments"]["filter"] == 'name:"POV - Quillfeather Freight Co. (fictional)"'


def test_readiness_errors_are_reported_per_check(settings):
    def down(request):
        raise httpx.ConnectError("refused")

    settings.adapter_mode = "mcp"
    with TestClient(create_app(settings, mcp_transport=httpx.MockTransport(down))) as c:
        deal_id = c.post("/api/sample-data").json()["deal_id"]
        pov_id = c.get(f"/api/deals/{deal_id}/pov-plans").json()[0]["id"]
        result = c.post(f"/api/pov-plans/{pov_id}/readiness").json()
    assert {c["status"] for c in result["checks"]} == {"error"}
    assert "Cannot reach MCP server" in result["checks"][0]["detail"]


# --- PowerShell setup script ------------------------------------------------------------
def script(client, pov_id, **body):
    r = client.post(f"/api/pov-plans/{pov_id}/setup-script", json=body)
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"].endswith('.ps1"')
    return r.text


def test_setup_script_is_safe_by_default(client, sample):
    _, pov_id = sample
    text = script(client, pov_id, toolkit_ids=["nodata_tasks_by_type", "collector_health"])
    assert "#Requires -Modules Logic.Monitor" in text
    assert "[switch]$Apply" in text and "[DRY RUN] Would:" in text
    # Every change goes through Invoke-Step (dry run unless -Apply).
    for cmd in ("New-LMDeviceGroup", "Import-LMLogicModuleFromFile"):
        for line in text.splitlines():
            if cmd in line and not line.strip().startswith(("#", "Write-")) and "$groupArgs" not in line:
                assert line.startswith(" " * 12), f"{cmd} outside an Invoke-Step block: {line}"
    # Logic.Monitor requires a parent for New-LMDeviceGroup; the POV group goes under the root.
    assert "ParentGroupId = 1 }" in text
    # No credentials embedded; only environment variables or the cached credential.
    assert "$env:LM_ACCESS_KEY" in text and "-UseCachedCredential" in text
    assert not re.search(r"(?i)(AccessKey|BearerToken)\s+'", text)
    # Existing modules are never overwritten.
    assert "Get-LMDatasource" in text and "HandleConflict = 'ERROR'" in text
    assert "Disconnect-LMAccount" in text


def test_setup_script_pins_sources_and_resolves_dependencies(client, sample):
    _, pov_id = sample
    text = script(client, pov_id, toolkit_ids=["nodata_tasks_by_type"])
    assert ("https://raw.githubusercontent.com/stevevillardi/LogicMonitor-Dashboards/"
            "af0b95f0e6cb17ffd39c48803c4020302e27e6d1/POV/NoData_Tasks_By_Type_v2.xml") in text
    assert "ModuleName = 'NoData_Tasks_By_Type_v2'; Type = 'datasources'; Format = 'xml'" in text
    # The required PropertySource cannot be scripted, so it is listed as a manual step.
    manual = text.split("$ManualSteps = @(")[1].split(")\n")[0]
    assert "NoData task-type discovery" in manual
    assert "stevevillardi/LogicMonitor-Dashboards @ af0b95f0e6cb (MPL-2.0)" in text


def test_setup_script_groups_from_context(client, sample):
    _, pov_id = sample
    text = script(client, pov_id)
    assert "$PovGroupName = 'POV - Quillfeather Freight Co. (fictional)'" in text
    assert "$SubGroups = @('Network', 'Servers and Virtualization', 'AWS')" in text
    assert "$Toolkit = @(\n)" in text
    assert "$SubGroups = @()" in script(client, pov_id, include_subgroups=False)


def test_setup_script_rejects_unknown_toolkit(client, sample):
    _, pov_id = sample
    assert client.post(f"/api/pov-plans/{pov_id}/setup-script", json={"toolkit_ids": ["rm_rf"]}).status_code == 422


def test_powershell_literal_escaping():
    assert ps_str("O'Brien") == "'O''Brien'"
    assert ps_str("curly\u2019quote") == "'curly''quote'"
    assert ps_str("line\nbreak; $(evil)") == "'line break; $(evil)'"  # single quotes: no expansion


def test_user_text_cannot_break_out_of_script_strings(client, sample):
    _, pov_id = sample
    client.patch(f"/api/pov-plans/{pov_id}", json={"title": "x'; Remove-Item C:\\ -Recurse; '"})
    text = script(client, pov_id)
    assert "'pov.title' = 'x''; Remove-Item C:\\ -Recurse; '''" in text


# --- Handoff --------------------------------------------------------------------------
def test_handoff_package(client, sample):
    deal_id, _ = sample
    r = client.get(f"/api/deals/{deal_id}/handoff")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    package = HandoffPackage.model_validate(data)  # round-trips through the published model
    assert package.format == "se-demo-pov-builder/handoff" and package.version == 1
    assert package.data_classification == "synthetic"
    assert len(package.contacts) == 5 and package.contacts[0].persona == "Champion"
    assert len(package.challenges) == 6 and package.challenges[0].capabilities[0].verified is False
    assert package.pov and len(package.pov.activities) == 7
    evidence = [e for c in package.pov.success_criteria for e in c.evidence]
    assert {e.simulated for e in evidence} == {True, False}
    assert any(q.key == "budget" and q.status == "assumed" for q in package.qualification)
    assert package.demo_plan and package.demo_plan.scenarios
    assert package.open_actions and package.gaps


def test_handoff_schema_and_bad_plan(client, sample):
    deal_id, _ = sample
    schema = client.get("/api/handoff/schema").json()
    assert schema["title"] == "HandoffPackage" and "pov" in schema["properties"]
    assert client.get(f"/api/deals/{deal_id}/handoff", params={"pov_plan_id": 9999}).status_code == 422


def test_ecosystem_library(client):
    eco = client.get("/api/library/ecosystem").json()
    assert {p["id"] for p in eco["projects"]} >= {"lm_powershell_module", "logicmonitor_api_mcp"}
    item = next(t for t in eco["toolkit"] if t["id"] == "nodata_metrics")
    assert item["import"] == "powershell" and item["license"] == "MPL-2.0"
    assert item["source_url"].startswith("https://github.com/stevevillardi/LogicMonitor-Dashboards/tree/af0b95f")
    assert all(r["source_url"].startswith("https://") for r in eco["references"])


def test_old_plans_report_effective_portal_group(client, sample):
    _, pov_id = sample
    from se_pov_builder.models import PovPlan

    session = client.app.state.session_factory()
    session.get(PovPlan, pov_id).portal_group = None
    session.commit()
    session.close()
    assert client.get(f"/api/pov-plans/{pov_id}").json()["portal_group"] == "POV - Quillfeather Freight Co. (fictional)"

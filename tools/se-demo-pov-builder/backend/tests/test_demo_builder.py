from types import SimpleNamespace as NS

import pytest

from se_pov_builder.services.demo_builder import FIXED_MINUTES, generate_demo_plan


def deal(ctx):
    return NS(technical_context=ctx)


def req(i, title, priority, caps, pain="", qid=None):
    return NS(id=i, title=title, description="", priority=priority, capability_ids=caps, pain_point=pain,
              source_question_id=qid)


def test_requirement_matched_scenarios_ranked_first(kb):
    reqs = [
        req(1, "Reduce alert noise", "must", ["anomaly_detection", "event_correlation"], "alert fatigue"),
        req(2, "Network visibility for branches", "should", ["network_monitoring"], "branch outages"),
    ]
    stakeholders = [NS(id=1, name="Pat", persona_id="practitioner"), NS(id=2, name="Lee", persona_id="champion")]
    plan = generate_demo_plan(kb, deal=deal(["network"]), stakeholders=stakeholders, answers=[],
                              requirements=reqs, duration_minutes=60, max_scenarios=4)
    ids = [s["scenario_id"] for s in plan["segments"]]
    assert ids[0] == "alert_noise_reduction"
    assert "network_health" in ids
    assert all(s["linked_requirements"] or s["matched_keywords"] for s in plan["segments"])
    # Talking points include persona-specific entries for stakeholders present.
    noise = plan["segments"][0]
    audiences = {tp["persona_id"] for tp in noise["talking_points"]}
    assert "practitioner" in audiences
    assert plan["pain_points"][0]["requirement"] == "Reduce alert noise"
    assert plan["generic"] is False


def test_agenda_fits_time_budget(kb):
    reqs = [req(i, f"r{i}", "must", [c]) for i, c in enumerate(
        ["alerting_escalation", "network_monitoring", "cloud_monitoring", "log_analysis", "itsm_integration"])]
    for duration in (30, 45, 60, 90):
        plan = generate_demo_plan(kb, deal=deal(["network", "cloud_aws"]), stakeholders=[], answers=[],
                                  requirements=reqs, duration_minutes=duration, max_scenarios=10)
        assert sum(item["minutes"] for item in plan["agenda"]) == duration
        assert plan["agenda"][0]["kind"] == "opening" and plan["agenda"][-1]["kind"] == "closing"


def test_scenarios_for_unused_technology_are_excluded(kb):
    reqs = [req(1, "Alerting", "must", ["alerting_escalation"])]
    plan = generate_demo_plan(kb, deal=deal(["network"]), stakeholders=[], answers=[], requirements=reqs,
                              duration_minutes=120, max_scenarios=10)
    ids = {s["scenario_id"] for s in plan["segments"]}
    assert "kubernetes_workloads" not in ids or any(
        s["linked_requirements"] for s in plan["segments"] if s["scenario_id"] == "kubernetes_workloads")


def test_generic_plan_when_no_discovery(kb):
    plan = generate_demo_plan(kb, deal=deal([]), stakeholders=[], answers=[], requirements=[],
                              duration_minutes=45)
    assert plan["generic"] is True
    assert plan["segments"], "a generic plan still proposes scenarios"
    assert any("No requirements have been captured" in a for a in plan["assumptions"])
    assert any("business impact" in m for m in plan["missing_evidence"])


def test_assumptions_and_missing_evidence_are_explicit(kb):
    answers = [NS(question_id="tech_alert_noise", answer="maybe 1000 alerts", confidence="assumed")]
    reqs = [req(1, "Fewer alerts", "must", ["alerting_escalation"], pain="", qid="tech_alert_noise"),
            req(2, "Uncovered thing", "must", ["multi_tenancy"])]
    plan = generate_demo_plan(kb, deal=deal(["network"]), stakeholders=[], answers=answers,
                              requirements=reqs, duration_minutes=30, max_scenarios=1)
    assert any("Assumed, not confirmed" in a for a in plan["assumptions"])
    assert any("No Champion identified" in a for a in plan["assumptions"])
    assert any("No pain point recorded" in m for m in plan["missing_evidence"])
    assert any("not backed by a confirmed discovery answer" in m for m in plan["missing_evidence"])
    assert any("not verified" in m for m in plan["missing_evidence"])
    assert {"id": 2, "title": "Uncovered thing", "priority": "must"} in plan["uncovered_requirements"]
    assert plan["prep_tasks"][0].startswith("Verify every capability")


def test_minimum_duration(kb):
    with pytest.raises(ValueError):
        generate_demo_plan(kb, deal=deal([]), stakeholders=[], answers=[], requirements=[],
                           duration_minutes=FIXED_MINUTES)


def test_saved_plan_reports_changes_since_it_was_generated(client):
    deal_id = client.post("/api/sample-data").json()["deal_id"]
    plan = client.post(f"/api/deals/{deal_id}/demo-plans", json={}).json()
    assert client.get(f"/api/demo-plans/{plan['id']}").json()["changes_since"] == []

    reqs = client.get(f"/api/deals/{deal_id}/requirements").json()
    client.post(f"/api/deals/{deal_id}/requirements", json={"title": "Integrate with ServiceNow", "priority": "must"})
    client.patch(f"/api/requirements/{reqs[0]['id']}", json={"priority": "could"})
    client.delete(f"/api/requirements/{reqs[1]['id']}")
    client.delete(f"/api/stakeholders/{client.get(f'/api/deals/{deal_id}/stakeholders').json()[0]['id']}")
    client.put(f"/api/deals/{deal_id}/discovery/answers/tech_logs", json={"answer": "Splunk, rarely used"})
    client.patch(f"/api/deals/{deal_id}", json={"technical_context": ["kubernetes"]})

    assert client.get(f"/api/demo-plans/{plan['id']}").json()["changes_since"] == [
        "1 requirement added", "1 requirement removed", "1 requirement edited", "1 stakeholder removed",
        "discovery answers changed", "technical context changed"]
    newer = client.post(f"/api/deals/{deal_id}/demo-plans", json={}).json()
    assert client.get(f"/api/demo-plans/{newer['id']}").json()["changes_since"] == []

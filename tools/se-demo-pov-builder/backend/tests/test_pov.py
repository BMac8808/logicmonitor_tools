from datetime import date


def setup_reqs(client, deal_id):
    must = client.post(f"/api/deals/{deal_id}/requirements", json={
        "title": "Network visibility", "priority": "must", "capability_ids": ["network_monitoring"]}).json()
    could = client.post(f"/api/deals/{deal_id}/requirements", json={
        "title": "Nice report", "priority": "could", "capability_ids": ["dashboards_reporting"]}).json()
    return must, could


def create_pov(client, deal_id, **kw):
    body = {"title": "POV", "start_date": "2027-01-04", "duration_days": 30, **kw}
    r = client.post(f"/api/deals/{deal_id}/pov-plans", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_pov_creates_milestones_and_draft_criteria(client, deal):
    must, could = setup_reqs(client, deal["id"])
    pov = create_pov(client, deal["id"])
    assert pov["end_date"] == "2027-02-03"
    ms = {m["template_key"]: m for m in pov["milestones"]}
    assert ms["kickoff"]["due_date"] == "2027-01-04"
    assert ms["security_review"]["depends_on"] == [ms["kickoff"]["id"]]
    drafted = {c["requirement_id"] for c in pov["criteria"]}
    assert must["id"] in drafted and could["id"] not in drafted
    assert pov["checklist"][0]["requirement"] == "Network visibility"
    assert pov["checklist"][0]["items"][0]["ready"] is False


def test_milestone_offsets_scale_with_duration(client, deal):
    pov = create_pov(client, deal["id"], duration_days=15)
    ms = {m["template_key"]: m for m in pov["milestones"]}
    assert date.fromisoformat(ms["results_readout"]["due_date"]) <= date.fromisoformat(pov["end_date"])
    assert ms["results_readout"]["due_date"] == "2027-01-18"


def test_milestone_dependency_enforced(client, deal):
    pov = create_pov(client, deal["id"])
    ms = {m["template_key"]: m for m in pov["milestones"]}
    assert client.patch(f"/api/tasks/{ms['security_review']['id']}", json={"status": "done"}).status_code == 409
    client.patch(f"/api/tasks/{ms['kickoff']['id']}", json={"status": "done"})
    assert client.patch(f"/api/tasks/{ms['security_review']['id']}", json={"status": "done"}).status_code == 200


def test_met_requires_real_evidence(client, deal):
    c = client.post(f"/api/deals/{deal['id']}/success-criteria", json={
        "title": "Alert ratio", "measurable_outcome": ">= 50% actionable", "validation_method": "NOC review"}).json()
    assert client.patch(f"/api/success-criteria/{c['id']}", json={"status": "met"}).status_code == 409

    sim = client.post(f"/api/success-criteria/{c['id']}/evidence", json={
        "description": "Lab replay", "is_simulated": True}).json()
    assert sim["is_simulated"] is True
    r = client.patch(f"/api/success-criteria/{c['id']}", json={"status": "met"})
    assert r.status_code == 409, "simulated evidence must not satisfy a criterion"

    real = client.post(f"/api/success-criteria/{c['id']}/evidence", json={
        "description": "NOC lead review of week 2 sample", "evidence_type": "customer_confirmation"}).json()
    assert client.patch(f"/api/success-criteria/{c['id']}", json={"status": "met"}).status_code == 200
    # Removing the last real evidence of a met criterion is refused.
    assert client.delete(f"/api/evidence/{real['id']}").status_code == 409
    assert client.delete(f"/api/evidence/{sim['id']}").status_code == 204


def test_cannot_create_met_criterion_without_evidence(client, deal):
    r = client.post(f"/api/deals/{deal['id']}/success-criteria", json={"title": "X", "status": "met"})
    assert r.status_code == 409


def test_summary_and_export_separate_simulated(client, deal):
    must, _ = setup_reqs(client, deal["id"])
    pov = create_pov(client, deal["id"])
    crit = pov["criteria"][0]
    client.patch(f"/api/success-criteria/{crit['id']}", json={
        "measurable_outcome": "95% devices", "validation_method": "Inventory compare", "owner": "Priya"})
    client.post(f"/api/success-criteria/{crit['id']}/evidence", json={"description": "Simulated run",
                                                                       "is_simulated": True})
    client.post(f"/api/success-criteria/{crit['id']}/evidence", json={"description": "Site 1: 41/42 devices"})
    client.patch(f"/api/success-criteria/{crit['id']}", json={"status": "met"})
    detail = client.get(f"/api/pov-plans/{pov['id']}").json()
    assert detail["summary"]["criteria_met"] == 1
    assert detail["summary"]["must_have_met"] == 1
    assert detail["summary"]["evidence_real"] == 1 and detail["summary"]["evidence_simulated"] == 1
    md = client.get(f"/api/pov-plans/{pov['id']}/export").text
    assert "Simulated items (NOT evidence)" in md
    validated = md.split("## Validated evidence")[1].split("##")[0]
    assert "Site 1: 41/42 devices" in validated and "Simulated run" not in validated


def test_cross_deal_links_rejected(client, deal):
    other_account = client.post("/api/accounts", json={"name": "Other (fictional)"}).json()
    other = client.post("/api/deals", json={"account_id": other_account["id"], "name": "Other"}).json()
    req = client.post(f"/api/deals/{other['id']}/requirements", json={"title": "R", "capability_ids": []}).json()
    r = client.post(f"/api/deals/{deal['id']}/success-criteria", json={"title": "C", "requirement_id": req["id"]})
    assert r.status_code == 422

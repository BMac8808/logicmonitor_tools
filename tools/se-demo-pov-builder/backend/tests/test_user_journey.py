"""End-to-end primary journey through the HTTP API, with no LLM configured:

Create Deal → Identify Stakeholders → Conduct Discovery → Define Success Criteria →
Generate Demo Plan → Build POV Plan → Track Next Actions.
"""


def test_primary_user_journey(client):
    assert client.get("/api/llm/status").json()["enabled"] is False

    # 1. Create a fictional account and deal.
    account = client.post("/api/accounts", json={
        "name": "Tallowmere Health Network (fictional)", "industry": "Healthcare", "region": "EMEA"}).json()
    deal = client.post("/api/deals", json={
        "account_id": account["id"], "name": "Monitoring modernisation",
        "summary": "Replace legacy tools", "technical_context": ["network", "servers_virtualization"],
    })
    assert deal.status_code == 201
    deal = deal.json()
    deal_id = deal["id"]
    r = client.patch(f"/api/deals/{deal_id}", json={"technical_context": ["network", "servers_virtualization",
                                                                         "itsm"]})
    assert "itsm" in r.json()["technical_context"]
    assert any(d["id"] == deal_id for d in client.get("/api/deals").json())

    # 2. Stakeholders with personas.
    people = {}
    for name, persona in [("Avery Holt", "champion"), ("Sam Okoro", "economic_buyer"),
                          ("Rin Takeda", "technical_buyer"), ("Lou Brandt", "practitioner")]:
        r = client.post(f"/api/deals/{deal_id}/stakeholders", json={"name": name, "persona_id": persona})
        assert r.status_code == 201
        people[persona] = r.json()
    r = client.patch(f"/api/stakeholders/{people['practitioner']['id']}", json={"stance": "supporter"})
    assert r.json()["stance"] == "supporter"

    # 3. Discovery: tailored questions, answers persisted, gaps and suggestions.
    qs = client.get(f"/api/deals/{deal_id}/discovery/questions").json()
    ids = {q["id"] for q in qs["questions"]}
    assert {"biz_trigger", "tech_network", "tech_servers", "tech_itsm"} <= ids
    assert "tech_kubernetes" not in ids
    answers = {
        "biz_trigger": ("Clinical app outages last month; renewal in Q2", "confirmed"),
        "biz_impact": ("90 minutes to detect a core switch failure", "confirmed"),
        "tech_alert_noise": ("About 3,000 alerts a week, most ignored; alert fatigue", "confirmed"),
        "tech_network": ("Core and edge switches, firewalls at 12 sites", "confirmed"),
        "qual_budget": ("Probably from the tooling budget", "assumed"),
    }
    for qid, (text, conf) in answers.items():
        r = client.put(f"/api/deals/{deal_id}/discovery/answers/{qid}", json={
            "answer": text, "confidence": conf, "stakeholder_id": people["champion"]["id"],
            "evidence_source": "Discovery call (synthetic)"})
        assert r.status_code == 200
    # Update an existing answer (upsert).
    r = client.put(f"/api/deals/{deal_id}/discovery/answers/biz_trigger", json={
        "answer": "Clinical app outages in the last two months; renewal in Q2", "confidence": "confirmed"})
    assert "two months" in r.json()["answer"]
    qs = client.get(f"/api/deals/{deal_id}/discovery/questions").json()
    assert qs["answered"] == 5

    gaps = client.get(f"/api/deals/{deal_id}/discovery/gaps").json()
    codes = {g["code"] for g in gaps["gaps"]}
    assert "assumed_qualification:budget" in codes
    assert "no_requirements" in codes
    assert not any(c.startswith("missing_persona") for c in codes)
    quals = {q["key"]: q["status"] for q in gaps["qualification"]}
    assert quals["pain"] == "confirmed" and quals["budget"] == "assumed" and quals["timeline"] == "missing"

    # Requirements, auto-mapped to capabilities from text and the source question.
    r1 = client.post(f"/api/deals/{deal_id}/requirements", json={
        "title": "Reduce alert noise for the NOC", "priority": "must", "pain_point": "alert fatigue",
        "source_question_id": "tech_alert_noise"}).json()
    assert {"alerting_escalation", "anomaly_detection"} & set(r1["capability_ids"])
    r2 = client.post(f"/api/deals/{deal_id}/requirements", json={
        "title": "Detect core switch failures across 12 sites", "priority": "must",
        "pain_point": "90 minutes to detect", "source_question_id": "tech_network"}).json()
    assert "network_monitoring" in r2["capability_ids"]
    r3 = client.post(f"/api/deals/{deal_id}/requirements", json={
        "title": "Create tickets automatically", "priority": "should", "capability_ids": ["itsm_integration"]}).json()

    # 4. Success criteria.
    c1 = client.post(f"/api/deals/{deal_id}/success-criteria", json={
        "title": "Actionable alerts", "requirement_id": r1["id"], "owner": "Lou Brandt",
        "measurable_outcome": ">= 50% of pilot alerts rated actionable", "target": ">= 50%",
        "validation_method": "NOC review of weekly alert sample"})
    assert c1.status_code == 201
    c1 = c1.json()
    gaps = {g["code"] for g in client.get(f"/api/deals/{deal_id}/discovery/gaps").json()["gaps"]}
    assert f"must_without_criteria:{r1['id']}" not in gaps
    assert f"must_without_criteria:{r2['id']}" in gaps

    # 5. Demo plan generated from saved discovery.
    plan = client.post(f"/api/deals/{deal_id}/demo-plans", json={"duration_minutes": 60}).json()
    content = plan["content"]
    assert plan["version"] == 1 and content["generic"] is False
    seg_ids = [s["scenario_id"] for s in content["segments"]]
    assert "alert_noise_reduction" in seg_ids and "network_health" in seg_ids
    linked = {r["id"] for s in content["segments"] for r in s["linked_requirements"]}
    assert {r1["id"], r2["id"]} <= linked
    assert sum(a["minutes"] for a in content["agenda"]) == 60
    assert any("Assumed, not confirmed" in a for a in content["assumptions"])
    assert content["audience_focus"]
    md = client.get(f"/api/demo-plans/{plan['id']}/export")
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
    assert "## Agenda" in md.text and "Assumptions" in md.text
    plan2 = client.post(f"/api/deals/{deal_id}/demo-plans", json={"duration_minutes": 45}).json()
    assert plan2["version"] == 2
    assert [p["version"] for p in client.get(f"/api/deals/{deal_id}/demo-plans").json()] == [2, 1]

    # 6. POV plan with milestones, drafted criteria, tracking and evidence.
    pov = client.post(f"/api/deals/{deal_id}/pov-plans", json={
        "title": "Tallowmere POV", "objectives": "Prove alert quality and network visibility",
        "start_date": "2027-02-01", "duration_days": 30}).json()
    assert len(pov["milestones"]) == 7
    crit_reqs = {c["requirement_id"] for c in pov["criteria"]}
    assert {r1["id"], r2["id"], r3["id"]} <= crit_reqs  # c1 attached, others drafted
    drafted = next(c for c in pov["criteria"] if c["requirement_id"] == r2["id"])
    client.patch(f"/api/success-criteria/{drafted['id']}", json={
        "measurable_outcome": "Core switch failure detected within 5 minutes", "target": "<= 5 min",
        "validation_method": "Controlled failover test witnessed by Rin", "owner": "Rin Takeda",
        "status": "in_progress"})
    ev = client.post(f"/api/success-criteria/{c1['id']}/evidence", json={
        "description": "Week 2 NOC review: 58% actionable", "evidence_type": "customer_confirmation",
        "recorded_by": "Lou Brandt"})
    assert ev.status_code == 201
    assert client.patch(f"/api/success-criteria/{c1['id']}", json={"status": "met"}).status_code == 200
    kickoff = next(m for m in pov["milestones"] if m["template_key"] == "kickoff")
    assert client.patch(f"/api/tasks/{kickoff['id']}", json={"status": "done"}).status_code == 200
    detail = client.get(f"/api/pov-plans/{pov['id']}").json()
    assert detail["summary"]["criteria_met"] == 1 and detail["summary"]["milestones_closed"] == 1
    assert client.patch(f"/api/pov-plans/{pov['id']}", json={"status": "active"}).json()["status"] == "active"
    export = client.get(f"/api/pov-plans/{pov['id']}/export").text
    assert "Tallowmere POV" in export and "Criteria met: **1 of 3**" in export
    assert "Week 2 NOC review" in export

    # Workflow tracking.
    run = client.post(f"/api/deals/{deal_id}/workflows", json={"workflow_id": "pov_planning"}).json()
    assert run["workflow_name"] == "POV Planning" and run["current_stage"] == "scope"

    # 7. Next actions: create from a gap suggestion, update, block, complete.
    gap = next(g for g in client.get(f"/api/deals/{deal_id}/discovery/gaps").json()["gaps"]
               if g["code"] == "assumed_qualification:budget")
    t = client.post(f"/api/deals/{deal_id}/tasks", json={
        "title": gap["suggested_action"], "owner": "Account Executive", "due_date": "2027-01-15"}).json()
    assert t["kind"] == "next_action" and t["status"] == "todo"
    t = client.patch(f"/api/tasks/{t['id']}", json={"owner": "Sam Okoro", "due_date": "2027-01-20"}).json()
    assert t["owner"] == "Sam Okoro"
    t = client.patch(f"/api/tasks/{t['id']}", json={"status": "blocked", "blocker": "Sam travelling"}).json()
    assert t["status"] == "blocked"
    t = client.patch(f"/api/tasks/{t['id']}", json={"status": "done"}).json()
    assert t["status"] == "done" and t["completed_at"]
    open_actions = client.get(f"/api/deals/{deal_id}/tasks", params={"kind": "next_action", "open_only": True})
    assert open_actions.json() == []

    metrics = client.get(f"/api/deals/{deal_id}").json()["metrics"]
    assert metrics["stakeholders"] == 4 and metrics["requirements"] == 3
    assert metrics["criteria_met"] == 1 and metrics["demo_plans"] == 2 and metrics["pov_plans"] == 1

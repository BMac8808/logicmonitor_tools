def test_unknown_persona_rejected(client, deal):
    r = client.post(f"/api/deals/{deal['id']}/stakeholders", json={"name": "X", "persona_id": "wizard"})
    assert r.status_code == 422


def test_unknown_context_tag_rejected(client, deal):
    r = client.patch(f"/api/deals/{deal['id']}", json={"technical_context": ["mainframe_magic"]})
    assert r.status_code == 422


def test_unknown_question_and_capability_rejected(client, deal):
    assert client.put(f"/api/deals/{deal['id']}/discovery/answers/nope", json={"answer": "x"}).status_code == 404
    r = client.post(f"/api/deals/{deal['id']}/requirements", json={"title": "R", "capability_ids": ["nope"]})
    assert r.status_code == 422


def test_answer_from_other_deals_stakeholder_rejected(client, deal):
    acc = client.post("/api/accounts", json={"name": "B"}).json()
    other = client.post("/api/deals", json={"account_id": acc["id"], "name": "Other"}).json()
    s = client.post(f"/api/deals/{other['id']}/stakeholders", json={"name": "Y", "persona_id": "champion"}).json()
    r = client.put(f"/api/deals/{deal['id']}/discovery/answers/biz_trigger",
                   json={"answer": "x", "stakeholder_id": s["id"]})
    assert r.status_code == 422


def test_404s(client):
    assert client.get("/api/deals/999").status_code == 404
    assert client.get("/api/pov-plans/999").status_code == 404
    assert client.patch("/api/tasks/999", json={"status": "done"}).status_code == 404


def test_deleting_deal_cascades(client, deal):
    client.post(f"/api/deals/{deal['id']}/stakeholders", json={"name": "X", "persona_id": "champion"})
    client.post(f"/api/deals/{deal['id']}/workflows", json={"workflow_id": "discovery"})
    assert client.delete(f"/api/deals/{deal['id']}").status_code == 204
    assert client.get(f"/api/deals/{deal['id']}").status_code == 404


def test_library_endpoints(client):
    assert len(client.get("/api/library/personas").json()) >= 7
    assert client.get("/api/library/personas/champion").json()["coverage"] == "required"
    caps = client.get("/api/library/capabilities").json()
    assert "Not authoritative" in caps["disclaimer"]
    assert client.get("/api/library/discovery").json()["qualification_checklist"]
    assert client.get("/api/library/demo-scenarios").json()
    assert [w["id"] for w in client.get("/api/library/workflows").json()][0] == "discovery"
    assert client.get("/api/library/pov-template").json()["milestones"]
    m = client.post("/api/library/capabilities/match", json={"text": "kubernetes pods crashing"}).json()
    assert m[0]["capability_id"] == "container_monitoring"
    assert client.post("/api/library/reload").json()["personas"] >= 7

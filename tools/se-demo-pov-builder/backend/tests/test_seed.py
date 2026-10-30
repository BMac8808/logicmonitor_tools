def test_sample_engagement_loads_once_and_is_complete(client):
    first = client.post("/api/sample-data")
    assert first.status_code == 201 and first.json()["created"] is True
    again = client.post("/api/sample-data").json()
    assert again == {"deal_id": first.json()["deal_id"], "created": False}

    deal_id = first.json()["deal_id"]
    deal = client.get(f"/api/deals/{deal_id}").json()
    assert deal["account"]["is_synthetic"] is True
    m = deal["metrics"]
    assert m["stakeholders"] == 5 and m["requirements"] == 6 and m["demo_plans"] == 1 and m["pov_plans"] == 1
    assert m["questions_answered"] >= 10
    assert m["blocked_tasks"] >= 1 and m["overdue_tasks"] >= 1
    assert m["open_next_actions"] == 4 and m["open_tasks"] > m["open_next_actions"]

    pov_id = client.get(f"/api/deals/{deal_id}/pov-plans").json()[0]["id"]
    summary = client.get(f"/api/pov-plans/{pov_id}").json()["summary"]
    assert summary["evidence_simulated"] == 1 and summary["criteria_met"] == 0

    gaps = {g["code"] for g in client.get(f"/api/deals/{deal_id}/discovery/gaps").json()["gaps"]}
    assert "assumed_qualification:budget" in gaps
    assert "unanswered_qualification:decision_criteria" in gaps


def test_sample_data_can_be_disabled(settings):
    from fastapi.testclient import TestClient

    from se_pov_builder.app import create_app

    settings.allow_sample_data = False
    with TestClient(create_app(settings)) as c:
        assert c.post("/api/sample-data").status_code == 403

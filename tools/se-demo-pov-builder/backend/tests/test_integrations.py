"""Inbound opportunity links and the handoff fields a system of record imports."""

from urllib.parse import unquote


def link_body(**overrides):
    body = {
        "system": "lmda",
        "external_id": "006POC000000001",
        "external_url": "http://localhost:3000/opportunity/006POC000000001",
        "import_url_template": "http://localhost:3000/opportunity/006POC000000001/scoping?seBuilderDeal={deal_url}",
        "account": {"name": "Example Freight (fictional)", "industry": "Logistics", "region": "AMER",
                    "is_synthetic": True},
        "opportunity": {"name": "Example - Monitoring consolidation", "stage": "Discovery",
                        "target_close": "2027-03-31", "technical_context": ["network", "not_a_tag"]},
    }
    body.update(overrides)
    return body


def test_link_creates_then_reuses_deal(client):
    first = client.post("/api/integrations/opportunities", json=link_body())
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["created"] is True and data["deal_url"].endswith(f"/#/deals/{data['deal_id']}")

    deal = client.get(f"/api/deals/{data['deal_id']}").json()
    assert deal["external_system"] == "lmda" and deal["external_id"] == "006POC000000001"
    assert deal["technical_context"] == ["network"]  # unknown tags dropped
    assert deal["account"]["is_synthetic"] is True
    link = deal["external_import_link"]
    assert link.startswith("http://localhost:3000/opportunity/006POC000000001/scoping?seBuilderDeal=")
    assert unquote(link.split("seBuilderDeal=")[1]) == data["deal_url"]

    # Planning data entered in this app survives a re-link; the opportunity name follows the source.
    client.patch(f"/api/deals/{data['deal_id']}", json={"summary": "SE notes"})
    again = client.post("/api/integrations/opportunities",
                        json=link_body(opportunity={"name": "Renamed in LMDA", "stage": "Proposal"})).json()
    assert again == {**data, "created": False}
    deal = client.get(f"/api/deals/{data['deal_id']}").json()
    assert deal["summary"] == "SE notes" and deal["name"] == "Renamed in LMDA" and deal["stage"] == "Proposal"


def test_link_rejects_non_http_urls_and_bad_system(client):
    assert client.post("/api/integrations/opportunities",
                       json=link_body(external_url="javascript:alert(1)")).status_code == 422
    assert client.post("/api/integrations/opportunities",
                       json=link_body(import_url_template="file:///etc/passwd")).status_code == 422
    assert client.post("/api/integrations/opportunities", json=link_body(system="LMDA!")).status_code == 422


def test_unlinked_deal_has_no_import_link(client, deal):
    assert client.get(f"/api/deals/{deal['id']}").json()["external_import_link"] is None


def test_handoff_carries_source_email_and_business_impact(client):
    deal_id = client.post("/api/integrations/opportunities", json=link_body()).json()["deal_id"]
    client.post(f"/api/deals/{deal_id}/stakeholders", json={
        "name": "Ari Vance", "persona_id": "champion", "email": "ari.vance@example.invalid"})
    client.post(f"/api/deals/{deal_id}/requirements", json={
        "title": "Reduce alert noise", "priority": "must", "business_impact": "NOC overtime ~20h/week",
        "capability_ids": ["alerting_escalation"]})
    handoff = client.get(f"/api/deals/{deal_id}/handoff").json()
    assert handoff["source"]["deal_id"] == deal_id
    assert handoff["source"]["external_system"] == "lmda"
    assert handoff["source"]["external_id"] == "006POC000000001"
    assert handoff["contacts"][0]["email"] == "ari.vance@example.invalid"
    assert handoff["challenges"][0]["business_impact"] == "NOC overtime ~20h/week"


def test_stakeholder_email_is_validated(client, deal):
    r = client.post(f"/api/deals/{deal['id']}/stakeholders", json={"name": "X", "persona_id": "champion",
                                                                   "email": "not-an-email"})
    assert r.status_code == 422
    ok = client.post(f"/api/deals/{deal['id']}/stakeholders", json={"name": "Y", "persona_id": "champion"})
    assert ok.status_code == 201 and ok.json()["email"] is None

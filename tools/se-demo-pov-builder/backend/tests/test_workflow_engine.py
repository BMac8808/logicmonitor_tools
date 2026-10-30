def start(client, deal_id, wf="discovery"):
    r = client.post(f"/api/deals/{deal_id}/workflows", json={"workflow_id": wf})
    assert r.status_code == 201, r.text
    return r.json()


def by_key(run):
    return {t["template_key"]: t for t in run["tasks"]}


def test_start_run_instantiates_tasks_and_dependencies(client, deal):
    run = start(client, deal["id"])
    tasks = by_key(run)
    assert run["current_stage"] == "prepare" and run["progress"] == 0
    assert tasks["plan_questions"]["depends_on"] == [tasks["map_stakeholders"]["id"]]
    assert tasks["plan_questions"]["waiting_on"] == [tasks["map_stakeholders"]["id"]]


def test_unknown_workflow_rejected(client, deal):
    assert client.post(f"/api/deals/{deal['id']}/workflows", json={"workflow_id": "nope"}).status_code == 422


def test_dependency_blocks_completion(client, deal):
    tasks = by_key(start(client, deal["id"]))
    r = client.patch(f"/api/tasks/{tasks['plan_questions']['id']}", json={"status": "done"})
    assert r.status_code == 409 and "waiting on" in r.json()["detail"]
    assert client.patch(f"/api/tasks/{tasks['map_stakeholders']['id']}", json={"status": "done"}).status_code == 200
    r = client.patch(f"/api/tasks/{tasks['plan_questions']['id']}", json={"status": "done"})
    assert r.status_code == 200 and r.json()["completed_at"]


def test_evidence_required(client, deal):
    tasks = by_key(start(client, deal["id"]))
    for key in ("map_stakeholders", "plan_questions"):
        client.patch(f"/api/tasks/{tasks[key]['id']}", json={"status": "done"})
    call = tasks["discovery_call"]["id"]
    assert client.patch(f"/api/tasks/{call}", json={"status": "done"}).status_code == 409
    r = client.patch(f"/api/tasks/{call}", json={"status": "done", "evidence_note": "Call notes recorded"})
    assert r.status_code == 200


def test_blocked_requires_blocker_and_clears_on_unblock(client, deal):
    t = client.post(f"/api/deals/{deal['id']}/tasks", json={"title": "Get access"}).json()
    assert client.patch(f"/api/tasks/{t['id']}", json={"status": "blocked"}).status_code == 409
    r = client.patch(f"/api/tasks/{t['id']}", json={"status": "blocked", "blocker": "Waiting on firewall rule"})
    assert r.json()["status"] == "blocked" and r.json()["blocker"]
    r = client.patch(f"/api/tasks/{t['id']}", json={"status": "in_progress"})
    assert r.json()["blocker"] == ""


def test_stage_progress(client, deal):
    run = start(client, deal["id"], "technical_handoff")
    tasks = by_key(run)
    for key in ("handoff_doc", "open_items"):
        client.patch(f"/api/tasks/{tasks[key]['id']}", json={"status": "done"})
    run = client.get(f"/api/deals/{deal['id']}/workflows").json()[0]
    stages = {s["id"]: s for s in run["stages"]}
    assert stages["package"]["status"] == "complete"
    assert run["current_stage"] == "transfer"
    assert 0 < run["progress"] < 1


def test_next_action_dependencies_and_cycles(client, deal):
    a = client.post(f"/api/deals/{deal['id']}/tasks", json={"title": "A"}).json()
    b = client.post(f"/api/deals/{deal['id']}/tasks", json={"title": "B", "depends_on": [a["id"]]}).json()
    assert b["waiting_on"] == [a["id"]]
    r = client.patch(f"/api/tasks/{a['id']}", json={"depends_on": [b["id"]]})
    assert r.status_code == 409 and "cycle" in r.json()["detail"]
    assert client.post(f"/api/deals/{deal['id']}/tasks", json={"title": "C", "depends_on": [9999]}).status_code == 409


def test_workflow_tasks_cannot_be_deleted_individually(client, deal):
    task = start(client, deal["id"])["tasks"][0]
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 409

"""Synthetic sample engagement covering the whole workflow.

Every organisation, person and figure below is invented. Dates are relative to today so
the sample always looks current.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from .knowledge import KnowledgeBase
from .models import (
    Account,
    Deal,
    DemoPlan,
    DiscoveryAnswer,
    Evidence,
    Requirement,
    Stakeholder,
    SuccessCriterion,
    Task,
)
from .services.demo_builder import generate_demo_plan
from .services.pov_builder import create_pov_plan
from .services.workflow_engine import start_run

SAMPLE_ACCOUNT_NAME = "Quillfeather Freight Co. (fictional)"
SAMPLE_DEAL_NAME = "Hybrid monitoring consolidation (sample)"
SOURCE_CALL_1 = "Discovery call #1 with Dana Whitlock (synthetic notes)"
SOURCE_CALL_2 = "Technical deep-dive with Priya Raman and Jo Kim (synthetic notes)"


def seed_sample_engagement(session: Session, kb: KnowledgeBase, today: date | None = None) -> int:
    today = today or date.today()
    account = Account(
        name=SAMPLE_ACCOUNT_NAME, industry="Logistics & warehousing", employee_band="5,000–10,000",
        region="North America (fictional)", is_synthetic=True,
        notes="Entirely fictional organisation used to demonstrate the tool.",
    )
    session.add(account)
    session.flush()
    deal = Deal(
        account_id=account.id, name=SAMPLE_DEAL_NAME, stage="pov_planning",
        summary="Replace four overlapping monitoring tools with one platform covering warehouse networks, "
                "data-centre servers and AWS.",
        business_drivers="Shipment delays caused by slow detection of warehouse network outages; "
                         "tool renewals in March.",
        technical_context=["network", "multi_site", "servers_virtualization", "cloud_aws", "logs", "itsm"],
        target_close=today + timedelta(days=120),
    )
    session.add(deal)
    session.flush()

    people = {
        "dana": Stakeholder(deal_id=deal.id, name="Dana Whitlock", title="Director of IT Operations",
                            persona_id="champion", influence="high", stance="supporter",
                            notes="Sponsored the evaluation after the Q3 outages."),
        "marcus": Stakeholder(deal_id=deal.id, name="Marcus Feld", title="CIO", persona_id="economic_buyer",
                              influence="high", stance="neutral", notes="Wants tool consolidation savings."),
        "priya": Stakeholder(deal_id=deal.id, name="Priya Raman", title="Infrastructure Architect",
                             persona_id="technical_buyer", influence="high", stance="neutral",
                             notes="Leads the technical evaluation; owns security review contact."),
        "tomas": Stakeholder(deal_id=deal.id, name="Tomás Reyes", title="Senior Network Engineer",
                             persona_id="detractor", influence="medium", stance="skeptic",
                             notes="Built the current network monitoring setup; worried about migration effort."),
        "jo": Stakeholder(deal_id=deal.id, name="Jo Kim", title="NOC Lead", persona_id="practitioner",
                          influence="medium", stance="supporter", notes="Team handles ~2,500 alerts a week."),
    }
    session.add_all(people.values())
    session.flush()

    answers = [
        ("biz_trigger", "dana", "Two multi-hour warehouse network outages last quarter delayed shipments. "
         "Current monitoring contracts renew in March.", SOURCE_CALL_1, "confirmed"),
        ("biz_impact", "dana", "Last outage took 3h20m to detect and resolve. Dana estimates about 40 delayed "
         "shipments per hour of warehouse system downtime.", SOURCE_CALL_1, "confirmed"),
        ("biz_tool_cost", "dana", "Four tools: network monitoring, server monitoring, cloud-native tooling and a "
         "separate log tool. Combined renewal cost not shared yet.", SOURCE_CALL_1, "confirmed"),
        ("qual_decision_process", "dana", "Priya leads the technical evaluation, security review is required, "
         "Marcus signs.", SOURCE_CALL_1, "confirmed"),
        ("qual_timeline", "dana", "Decision needed before the March renewals.", SOURCE_CALL_1, "confirmed"),
        ("qual_budget", "dana", "Budget expected to come from consolidating existing renewals; not confirmed "
         "with Marcus.", SOURCE_CALL_1, "assumed"),
        ("qual_success", "priya", "Show visibility of pilot warehouse networks and WMS servers, actionable alerts "
         "into the ITSM tool, and faster root cause on a realistic incident.", SOURCE_CALL_2, "confirmed"),
        ("tech_scope", "priya", "About 1,200 network devices across 35 warehouses, ~600 VMware VMs, "
         "3 AWS accounts.", SOURCE_CALL_2, "confirmed"),
        ("tech_alert_noise", "jo", "Roughly 2,500 alerts per week; NOC estimates fewer than 10% are actionable. "
         "Alert fatigue is a real problem.", SOURCE_CALL_2, "confirmed"),
        ("tech_troubleshooting", "jo", "During the last outage the team switched between four tools; logs were "
         "in a separate system; root cause was a firewall configuration change.", SOURCE_CALL_2, "confirmed"),
        ("tech_network", "tomas", "Mixed-vendor switching and firewalls, SNMP v2c and v3, WAN link to every "
         "warehouse. Flow data is not collected today.", SOURCE_CALL_2, "confirmed"),
        ("tech_itsm", "jo", "Incidents live in the ITSM platform; NOC creates tickets manually from alerts.",
         SOURCE_CALL_2, "confirmed"),
        ("tech_cloud", "priya", "AWS hosts the customer portal and EDI integrations; a separate cloud team uses "
         "native tooling.", SOURCE_CALL_2, "confirmed"),
    ]
    for qid, who, text, source, confidence in answers:
        if qid in kb.questions:
            session.add(DiscoveryAnswer(deal_id=deal.id, question_id=qid, stakeholder_id=people[who].id,
                                        answer=text, evidence_source=source, confidence=confidence))

    req_specs = [
        ("Monitor warehouse network devices and WAN links across 35 sites", "must", "technical",
         "Outages are reported by warehouse staff before any tool alerts.", "tech_network",
         ["network_monitoring", "traffic_flow_analysis"]),
        ("Reduce non-actionable alerts", "must", "technical",
         "Fewer than 10% of ~2,500 weekly alerts are actionable; alert fatigue in the NOC.", "tech_alert_noise",
         ["alerting_escalation", "anomaly_detection", "event_correlation"]),
        ("Correlate metrics, logs and configuration changes during incidents", "must", "technical",
         "3h20m outage involved four tools; root cause was a firewall configuration change.",
         "tech_troubleshooting", ["log_analysis", "config_change_tracking", "topology_mapping"]),
        ("Create ITSM incidents automatically from actionable alerts", "should", "technical",
         "Tickets are created manually from alerts.", "tech_itsm", ["itsm_integration"]),
        ("Include AWS resources in the same operational view", "should", "technical",
         "Cloud team uses separate native tooling; no shared view during incidents.", "tech_cloud",
         ["cloud_monitoring"]),
        ("Monthly availability summary for the CIO", "could", "business",
         "Leadership reporting is assembled manually.", None, ["dashboards_reporting", "service_views"]),
    ]
    reqs = []
    for title, priority, category, pain, qid, caps in req_specs:
        r = Requirement(deal_id=deal.id, title=title, priority=priority, category=category, pain_point=pain,
                        source_question_id=qid, capability_ids=caps, status="confirmed" if qid else "draft")
        session.add(r)
        reqs.append(r)
    session.flush()

    session.add(DemoPlan(
        deal_id=deal.id, version=1, title=f"Demo plan v1 — {deal.name}", duration_minutes=60,
        content=generate_demo_plan(kb, deal=deal, stakeholders=list(people.values()),
                                   answers=session.query(DiscoveryAnswer).filter_by(deal_id=deal.id).all(),
                                   requirements=reqs, duration_minutes=60, max_scenarios=4),
    ))

    # Criteria for the first two requirements are fully defined; the rest are drafted by the POV builder.
    c1 = SuccessCriterion(
        deal_id=deal.id, requirement_id=reqs[0].id, title="Pilot warehouse devices visible",
        measurable_outcome="At least 95% of network devices in 3 pilot warehouses report interface metrics",
        target=">= 95% of in-scope devices", owner="Priya Raman", status="in_progress",
        validation_method="Compare the device inventory with the customer's asset list for the 3 pilot sites",
    )
    c2 = SuccessCriterion(
        deal_id=deal.id, requirement_id=reqs[1].id, title="Actionable alert ratio",
        measurable_outcome="NOC rates at least half of alerts in the pilot scope as actionable over two weeks",
        target=">= 50% actionable", owner="Jo Kim", status="not_started",
        validation_method="NOC lead reviews a weekly alert sample and records the actionable share",
    )
    session.add_all([c1, c2])
    session.flush()
    session.add_all([
        Evidence(criterion_id=c1.id, description="Pilot site 1: 41 of 42 devices reporting interface metrics",
                 reference="POV session notes, week 1 (synthetic)", evidence_type="observation",
                 recorded_by="Sales Engineer"),
        Evidence(criterion_id=c2.id, description="Lab replay of anonymised alert data suggested fewer alerts",
                 reference="Demo lab (synthetic data)", evidence_type="metric", is_simulated=True,
                 recorded_by="Sales Engineer"),
    ])

    create_pov_plan(session, kb, deal, title="Quillfeather POV (sample)",
                    objectives="Prove warehouse network visibility, alert quality and faster root cause on "
                               "three pilot warehouses before the March renewal decision.",
                    start_date=today + timedelta(days=7), duration_days=30, draft_criteria=True)

    run = start_run(session, kb, deal, "discovery")
    session.flush()
    status_by_key = {"research_account": "done", "map_stakeholders": "done", "plan_questions": "done",
                     "discovery_call": "done", "capture_requirements": "in_progress"}
    for task in session.query(Task).filter_by(workflow_run_id=run.id):
        if task.template_key in status_by_key:
            task.status = status_by_key[task.template_key]
            task.owner = "Sales Engineer"
        if task.template_key == "discovery_call":
            task.evidence_note = "Answers recorded in Discovery tab with sources."
    start_run(session, kb, deal, "technical_qualification")
    start_run(session, kb, deal, "pov_planning")

    session.add_all([
        Task(deal_id=deal.id, kind="next_action", title="Ask Dana to introduce an executive sponsor",
             owner="Sales Engineer", due_date=today + timedelta(days=3)),
        Task(deal_id=deal.id, kind="next_action", title="Obtain the security questionnaire",
             owner="Priya Raman", due_date=today + timedelta(days=5), status="blocked",
             blocker="Waiting for the security team contact"),
        Task(deal_id=deal.id, kind="next_action", title="Confirm budget source with Marcus",
             description="Budget source is currently an assumption.", owner="Account Executive",
             due_date=today + timedelta(days=10)),
        Task(deal_id=deal.id, kind="next_action", title="Meet Tomás to review current network monitoring workflow",
             description="Invite him to own the network visibility criterion.", owner="Sales Engineer",
             due_date=today - timedelta(days=1)),
    ])
    session.flush()
    return deal.id

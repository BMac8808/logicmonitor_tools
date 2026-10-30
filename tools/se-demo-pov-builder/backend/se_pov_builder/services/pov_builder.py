"""POV builder: create plans with milestones, draft success criteria, build the
validation checklist and summarise results. Simulated evidence never counts."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..knowledge import KnowledgeBase
from ..models import Deal, PovPlan, Requirement, SuccessCriterion, Task
from .workflow_engine import CLOSED

CRITERION_STATUSES = ("not_started", "in_progress", "met", "not_met", "waived")
RESPONSIBLE_LABELS = {"se": "Sales Engineer", "customer": "Customer", "joint": "Joint (SE + customer)"}
DRAFT_NOTE = "Draft created from requirement. Define a measurable outcome, target and validation method."


class EvidenceRuleError(ValueError):
    pass


def create_pov_plan(
    session: Session,
    kb: KnowledgeBase,
    deal: Deal,
    *,
    title: str,
    objectives: str,
    start_date: date,
    duration_days: int | None,
    draft_criteria: bool,
) -> PovPlan:
    template = kb.pov_template
    duration = duration_days or template.default_duration_days
    plan = PovPlan(
        deal_id=deal.id,
        title=title,
        objectives=objectives,
        start_date=start_date,
        end_date=start_date + timedelta(days=duration),
        template_version=template.version,
    )
    session.add(plan)
    session.flush()

    scale = duration / template.default_duration_days
    by_key: dict[str, Task] = {}
    for m in template.milestones:
        task = Task(
            deal_id=deal.id,
            kind="milestone",
            pov_plan_id=plan.id,
            template_key=m.key,
            title=m.title,
            description=m.description,
            owner=RESPONSIBLE_LABELS[m.responsible],
            due_date=start_date + timedelta(days=min(round(m.offset_days * scale), duration)),
            depends_on=[],
        )
        session.add(task)
        by_key[m.key] = task
    session.flush()
    for m in template.milestones:
        by_key[m.key].depends_on = [by_key[d].id for d in m.depends_on]

    # Attach unassigned criteria; optionally draft criteria for uncovered requirements.
    criteria = session.query(SuccessCriterion).filter_by(deal_id=deal.id).all()
    for c in criteria:
        if c.pov_plan_id is None:
            c.pov_plan_id = plan.id
    if draft_criteria:
        covered = {c.requirement_id for c in criteria}
        reqs = session.query(Requirement).filter_by(deal_id=deal.id).order_by(Requirement.id).all()
        for r in reqs:
            if r.priority in ("must", "should") and r.id not in covered:
                session.add(SuccessCriterion(
                    deal_id=deal.id, pov_plan_id=plan.id, requirement_id=r.id,
                    title=f"Validate: {r.title}", notes=DRAFT_NOTE,
                ))
    session.flush()
    return plan


def check_criterion_status(criterion: SuccessCriterion, new_status: str) -> None:
    if new_status not in CRITERION_STATUSES:
        raise EvidenceRuleError(f"Status must be one of {', '.join(CRITERION_STATUSES)}")
    if new_status == "met" and not any(not e.is_simulated for e in criterion.evidence):
        raise EvidenceRuleError(
            "A criterion can only be marked 'met' with at least one real (non-simulated) evidence item"
        )


def criterion_evidence_counts(criterion: SuccessCriterion) -> dict:
    real = sum(1 for e in criterion.evidence if not e.is_simulated)
    return {"real": real, "simulated": len(criterion.evidence) - real}


def build_checklist(criteria: list[SuccessCriterion], requirements: list[Requirement]) -> list[dict]:
    req_by_id = {r.id: r for r in requirements}
    groups: dict[int | None, list[SuccessCriterion]] = {}
    for c in criteria:
        groups.setdefault(c.requirement_id if c.requirement_id in req_by_id else None, []).append(c)
    checklist = []
    order = {"must": 0, "should": 1, "could": 2}
    keys = sorted(
        groups, key=lambda k: (k is None, order.get(req_by_id[k].priority, 3) if k is not None else 0, k or 0)
    )
    for key in keys:
        req = req_by_id.get(key) if key is not None else None
        checklist.append({
            "requirement_id": key,
            "requirement": req.title if req else "Not linked to a requirement",
            "priority": req.priority if req else None,
            "items": [
                {
                    "criterion_id": c.id,
                    "title": c.title,
                    "validation_method": c.validation_method,
                    "target": c.target,
                    "owner": c.owner,
                    "status": c.status,
                    "evidence": criterion_evidence_counts(c),
                    "ready": bool(c.measurable_outcome.strip() and c.validation_method.strip()),
                }
                for c in groups[key]
            ],
        })
    return checklist


def summarise(criteria: list[SuccessCriterion], milestones: list[Task], requirements: list[Requirement]) -> dict:
    by_status = {s: 0 for s in ("not_started", "in_progress", "met", "not_met", "waived")}
    for c in criteria:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    req_priority = {r.id: r.priority for r in requirements}
    must = [c for c in criteria if req_priority.get(c.requirement_id or -1) == "must"]
    counted = [c for c in criteria if c.status != "waived"]
    return {
        "criteria_total": len(criteria),
        "criteria_by_status": by_status,
        "criteria_met": by_status["met"],
        "must_have_total": len(must),
        "must_have_met": sum(1 for c in must if c.status == "met"),
        "completion": round(by_status["met"] / len(counted), 3) if counted else 0.0,
        "milestones_total": len(milestones),
        "milestones_closed": sum(1 for m in milestones if m.status in CLOSED),
        "evidence_real": sum(criterion_evidence_counts(c)["real"] for c in criteria),
        "evidence_simulated": sum(criterion_evidence_counts(c)["simulated"] for c in criteria),
    }

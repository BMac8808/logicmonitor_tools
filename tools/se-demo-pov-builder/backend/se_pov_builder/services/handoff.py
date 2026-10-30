"""Handoff package: a versioned JSON export of one engagement for downstream SE platforms
(for example an internal POV tracker such as LMDA) to import.

The format is owned by this project and documented in docs/HANDOFF_FORMAT.md; its JSON
Schema is served at /api/handoff/schema. Consumers map it into their own model. Simulated
evidence is exported with ``simulated: true`` and must never be presented as a result.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import __version__
from ..knowledge import KnowledgeBase
from ..models import (
    Deal,
    DemoPlan,
    DiscoveryAnswer,
    PovPlan,
    Requirement,
    Stakeholder,
    SuccessCriterion,
    Task,
    utcnow,
)
from .discovery import analyse_gaps
from .pov_readiness import group_name
from .workflow_engine import CLOSED

FORMAT_ID = "se-demo-pov-builder/handoff"
FORMAT_VERSION = 1


class HAccount(BaseModel):
    name: str
    industry: str
    region: str
    employee_band: str
    is_synthetic: bool


class HScope(BaseModel):
    tag: str
    label: str


class HOpportunity(BaseModel):
    name: str
    stage: str
    summary: str
    business_drivers: str
    target_close: date | None
    technical_scope: list[HScope]


class HSource(BaseModel):
    """Where the package came from, so importers can link back and detect re-imports."""
    deal_id: int
    deal_url: str
    external_system: str | None
    external_id: str | None


class HContact(BaseModel):
    name: str
    email: str | None = None
    title: str
    persona_id: str
    persona: str
    influence: str
    stance: str
    notes: str


class HDiscoveryItem(BaseModel):
    question_id: str
    question: str
    category: str
    qualification_key: str | None
    answer: str
    confidence: Literal["confirmed", "assumed"]
    answered_by: str | None
    evidence_source: str


class HQualification(BaseModel):
    key: str
    label: str
    status: Literal["confirmed", "assumed", "missing"]


class HCapability(BaseModel):
    id: str
    name: str
    verified: bool


class HChallenge(BaseModel):
    """A captured requirement and the pain behind it."""
    id: int
    title: str
    description: str
    pain_point: str
    business_impact: str | None = None
    priority: Literal["must", "should", "could"]
    category: Literal["business", "technical"]
    status: str
    capabilities: list[HCapability]
    source_question_id: str | None


class HEvidence(BaseModel):
    description: str
    reference: str
    evidence_type: str
    recorded_by: str
    recorded_at: datetime
    simulated: bool = Field(description="True = produced with mock/simulated data; NOT a customer result")


class HSuccessCriterion(BaseModel):
    id: int
    title: str
    requirement_id: int | None
    measurable_outcome: str
    target: str
    validation_method: str
    owner: str
    status: Literal["not_started", "in_progress", "met", "not_met", "waived"]
    evidence: list[HEvidence]


class HActivity(BaseModel):
    title: str
    description: str
    owner: str
    due_date: date | None
    status: str
    depends_on: list[str]


class HPov(BaseModel):
    title: str
    objectives: str
    start_date: date | None
    end_date: date | None
    status: str
    portal_group: str
    success_criteria: list[HSuccessCriterion]
    activities: list[HActivity]


class HDemoPlan(BaseModel):
    version: int
    title: str
    duration_minutes: int
    scenarios: list[str]
    agenda: list[str]


class HAction(BaseModel):
    title: str
    owner: str
    due_date: date | None
    status: str
    blocker: str


class HGap(BaseModel):
    severity: Literal["high", "medium", "low"]
    message: str


class HandoffPackage(BaseModel):
    format: Literal["se-demo-pov-builder/handoff"] = FORMAT_ID
    version: Literal[1] = FORMAT_VERSION
    generated_at: datetime
    generator: str
    data_classification: Literal["synthetic", "customer"]
    source: HSource | None = None
    account: HAccount
    opportunity: HOpportunity
    contacts: list[HContact]
    discovery: list[HDiscoveryItem]
    qualification: list[HQualification]
    decision_criteria_notes: str | None
    challenges: list[HChallenge]
    pov: HPov | None
    demo_plan: HDemoPlan | None
    open_actions: list[HAction]
    assumptions: list[str]
    gaps: list[HGap]


def deal_url(public_url: str, deal_id: int) -> str:
    return f"{public_url.rstrip('/')}/#/deals/{deal_id}"


def build_handoff(
    session: Session, kb: KnowledgeBase, deal: Deal, pov_plan_id: int | None = None,
    public_url: str = "http://127.0.0.1:8000",
) -> HandoffPackage:
    account = deal.account
    stakeholders = session.query(Stakeholder).filter_by(deal_id=deal.id).order_by(Stakeholder.id).all()
    answers = session.query(DiscoveryAnswer).filter_by(deal_id=deal.id).order_by(DiscoveryAnswer.id).all()
    reqs = session.query(Requirement).filter_by(deal_id=deal.id).order_by(Requirement.id).all()
    criteria_all = session.query(SuccessCriterion).filter_by(deal_id=deal.id).order_by(SuccessCriterion.id).all()
    demo = session.query(DemoPlan).filter_by(deal_id=deal.id).order_by(DemoPlan.version.desc()).first()
    tasks = session.query(Task).filter_by(deal_id=deal.id).order_by(Task.id).all()
    names = {s.id: s.name for s in stakeholders}
    titles = {t.id: t.title for t in tasks}

    plans = session.query(PovPlan).filter_by(deal_id=deal.id).order_by(PovPlan.id.desc())
    plan = plans.filter_by(id=pov_plan_id).first() if pov_plan_id else plans.first()
    if pov_plan_id and plan is None:
        raise ValueError(f"POV plan {pov_plan_id} does not belong to this deal")

    def caps(ids: list[str]) -> list[HCapability]:
        return [HCapability(id=c, name=kb.capabilities[c].name, verified=kb.capabilities[c].verified)
                for c in ids if c in kb.capabilities]

    by_q = {a.question_id: a for a in answers}
    qualification = []
    for item in kb.discovery.qualification_checklist:
        confs = [by_q[q.id].confidence for q in kb.discovery.questions if q.qualification_key == item.key
                 and q.id in by_q]
        status = "confirmed" if "confirmed" in confs else "assumed" if confs else "missing"
        qualification.append(HQualification(key=item.key, label=item.label, status=status))

    pov = None
    if plan is not None:
        criteria = [c for c in criteria_all if c.pov_plan_id == plan.id]
        milestones = sorted((t for t in tasks if t.pov_plan_id == plan.id),
                            key=lambda t: (t.due_date is None, t.due_date, t.id))
        pov = HPov(
            title=plan.title, objectives=plan.objectives, start_date=plan.start_date, end_date=plan.end_date,
            status=plan.status, portal_group=group_name(plan, account),
            success_criteria=[HSuccessCriterion(
                id=c.id, title=c.title, requirement_id=c.requirement_id, measurable_outcome=c.measurable_outcome,
                target=c.target, validation_method=c.validation_method, owner=c.owner, status=c.status,
                evidence=[HEvidence(description=e.description, reference=e.reference, evidence_type=e.evidence_type,
                                    recorded_by=e.recorded_by, recorded_at=e.recorded_at, simulated=e.is_simulated)
                          for e in c.evidence],
            ) for c in criteria],
            activities=[HActivity(title=t.title, description=t.description, owner=t.owner, due_date=t.due_date,
                                  status=t.status, depends_on=[titles[d] for d in t.depends_on if d in titles])
                        for t in milestones],
        )

    assumptions = [f"{kb.questions[a.question_id].text} → {a.answer}" for a in answers
                   if a.confidence == "assumed" and a.question_id in kb.questions]
    if demo:
        assumptions += [a for a in demo.content.get("assumptions", []) if not a.startswith("Assumed, not confirmed")]
    gaps = analyse_gaps(kb, technical_context=deal.technical_context, stakeholders=stakeholders, answers=answers,
                        requirements=reqs, criteria=criteria_all, demo_plans=[demo] if demo else [])
    decision = by_q.get("qual_criteria")

    return HandoffPackage(
        generated_at=utcnow(),
        generator=f"se-demo-pov-builder {__version__}",
        data_classification="synthetic" if account.is_synthetic else "customer",
        source=HSource(deal_id=deal.id, deal_url=deal_url(public_url, deal.id),
                       external_system=deal.external_system, external_id=deal.external_id),
        account=HAccount(name=account.name, industry=account.industry, region=account.region,
                         employee_band=account.employee_band, is_synthetic=account.is_synthetic),
        opportunity=HOpportunity(
            name=deal.name, stage=deal.stage, summary=deal.summary, business_drivers=deal.business_drivers,
            target_close=deal.target_close,
            technical_scope=[HScope(tag=t, label=kb.context_tags[t].label) for t in deal.technical_context
                             if t in kb.context_tags],
        ),
        contacts=[HContact(name=s.name, email=s.email, title=s.title, persona_id=s.persona_id,
                           persona=kb.personas[s.persona_id].name if s.persona_id in kb.personas else s.persona_id,
                           influence=s.influence, stance=s.stance, notes=s.notes) for s in stakeholders],
        discovery=[HDiscoveryItem(
            question_id=a.question_id,
            question=kb.questions[a.question_id].text if a.question_id in kb.questions else a.question_id,
            category=kb.questions[a.question_id].category if a.question_id in kb.questions else "unknown",
            qualification_key=kb.questions[a.question_id].qualification_key if a.question_id in kb.questions else None,
            answer=a.answer, confidence=a.confidence, answered_by=names.get(a.stakeholder_id or -1),
            evidence_source=a.evidence_source,
        ) for a in answers],
        qualification=qualification,
        decision_criteria_notes=decision.answer if decision else None,
        challenges=[HChallenge(id=r.id, title=r.title, description=r.description, pain_point=r.pain_point,
                               business_impact=r.business_impact or None,
                               priority=r.priority, category=r.category, status=r.status,
                               capabilities=caps(r.capability_ids), source_question_id=r.source_question_id)
                    for r in reqs],
        pov=pov,
        demo_plan=HDemoPlan(
            version=demo.version, title=demo.title, duration_minutes=demo.duration_minutes,
            scenarios=[s["title"] for s in demo.content.get("segments", [])],
            agenda=[a["title"] for a in demo.content.get("agenda", [])],
        ) if demo else None,
        open_actions=[HAction(title=t.title, owner=t.owner, due_date=t.due_date, status=t.status, blocker=t.blocker)
                      for t in tasks if t.kind == "next_action" and t.status not in CLOSED],
        assumptions=assumptions,
        gaps=[HGap(severity=g.severity, message=g.message) for g in gaps],
    )

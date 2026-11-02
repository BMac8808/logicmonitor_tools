"""Demo plans, POV plans, success criteria and evidence."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..knowledge import KnowledgeBase
from ..models import (
    Deal,
    DemoPlan,
    DiscoveryAnswer,
    Evidence,
    PovPlan,
    Requirement,
    Stakeholder,
    SuccessCriterion,
    Task,
)
from ..schemas import (
    CriterionIn,
    CriterionOut,
    CriterionPatch,
    DemoPlanIn,
    DemoPlanListItem,
    DemoPlanOut,
    EvidenceIn,
    EvidenceOut,
    PovPlanDetail,
    PovPlanIn,
    PovPlanOut,
    PovPlanPatch,
    SetupScriptIn,
)
from ..services.demo_builder import generate_demo_plan
from ..services.export import demo_plan_markdown, pov_plan_markdown
from ..services.handoff import build_handoff
from ..services.pov_builder import (
    EvidenceRuleError,
    build_checklist,
    check_criterion_status,
    create_pov_plan,
    summarise,
)
from ..services.pov_readiness import group_name, run_readiness
from ..services.powershell_script import ScriptError, generate_setup_script
from .deps import deal_or_404, get_db, get_kb, get_or_404, task_out, tasks_by_id

router = APIRouter()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "export"


def _markdown(text: str, name: str) -> PlainTextResponse:
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{_slug(name)}.md"'})


# --- Demo plans --------------------------------------------------------------
@router.get("/deals/{deal_id}/demo-plans", response_model=list[DemoPlanListItem])
def list_demo_plans(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db)) -> list[DemoPlan]:
    return db.query(DemoPlan).filter_by(deal_id=deal.id).order_by(DemoPlan.version.desc()).all()


@router.post("/deals/{deal_id}/demo-plans", response_model=DemoPlanOut, status_code=201)
def create_demo_plan(body: DemoPlanIn, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                     kb: KnowledgeBase = Depends(get_kb)) -> DemoPlan:
    content = generate_demo_plan(
        kb,
        deal=deal,
        stakeholders=db.query(Stakeholder).filter_by(deal_id=deal.id).all(),
        answers=db.query(DiscoveryAnswer).filter_by(deal_id=deal.id).all(),
        requirements=db.query(Requirement).filter_by(deal_id=deal.id).all(),
        duration_minutes=body.duration_minutes,
        max_scenarios=body.max_scenarios,
    )
    version = (db.query(func.max(DemoPlan.version)).filter_by(deal_id=deal.id).scalar() or 0) + 1
    plan = DemoPlan(deal_id=deal.id, version=version, title=body.title or f"Demo plan v{version} — {deal.name}",
                    duration_minutes=body.duration_minutes, content=content, notes=body.notes)
    db.add(plan)
    db.commit()
    return plan


def _count(n: int, noun: str, what: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'} {what}"


def demo_plan_changes(db: Session, plan: DemoPlan) -> list[str]:
    """What changed in the plan's inputs since it was generated, from the ids the plan
    recorded and the rows' updated_at. Any save counts as an edit."""
    inputs = (plan.content or {}).get("inputs")
    if not inputs:
        return []
    changes: list[str] = []
    for model, key, noun in ((Requirement, "requirement_ids", "requirement"),
                             (Stakeholder, "stakeholder_ids", "stakeholder")):
        rows = db.query(model).filter_by(deal_id=plan.deal_id).all()
        was, now = set(inputs.get(key, [])), {r.id for r in rows}
        edited = sum(r.id in was and r.updated_at > plan.created_at for r in rows)
        for n, what in ((len(now - was), "added"), (len(was - now), "removed"), (edited, "edited")):
            if n:
                changes.append(_count(n, noun, what))
    answers = db.query(DiscoveryAnswer).filter_by(deal_id=plan.deal_id).all()
    if len(answers) != inputs.get("answer_count") or any(a.updated_at > plan.created_at for a in answers):
        changes.append("discovery answers changed")
    deal = db.get(Deal, plan.deal_id)
    if sorted(deal.technical_context or []) != inputs.get("technical_context", []):
        changes.append("technical context changed")
    return changes


@router.get("/demo-plans/{plan_id}", response_model=DemoPlanOut)
def get_demo_plan(plan_id: int, db: Session = Depends(get_db)) -> DemoPlanOut:
    plan = get_or_404(db, DemoPlan, plan_id)
    return DemoPlanOut.model_validate(plan).model_copy(update={"changes_since": demo_plan_changes(db, plan)})


@router.get("/demo-plans/{plan_id}/export")
def export_demo_plan(plan_id: int, db: Session = Depends(get_db)) -> PlainTextResponse:
    plan = get_or_404(db, DemoPlan, plan_id)
    deal = get_or_404(db, Deal, plan.deal_id)
    return _markdown(demo_plan_markdown(plan, deal, deal.account), plan.title)


@router.delete("/demo-plans/{plan_id}", status_code=204)
def delete_demo_plan(plan_id: int, db: Session = Depends(get_db)) -> Response:
    db.delete(get_or_404(db, DemoPlan, plan_id))
    db.commit()
    return Response(status_code=204)


# --- POV plans ---------------------------------------------------------------
def _pov_detail(db: Session, plan: PovPlan) -> PovPlanDetail:
    criteria = db.query(SuccessCriterion).filter_by(pov_plan_id=plan.id).order_by(SuccessCriterion.id).all()
    reqs = db.query(Requirement).filter_by(deal_id=plan.deal_id).all()
    by_id = tasks_by_id(db, plan.deal_id)
    milestones = sorted((t for t in by_id.values() if t.pov_plan_id == plan.id),
                        key=lambda t: (t.due_date is None, t.due_date, t.id))
    base = PovPlanOut.model_validate(plan).model_dump()
    # Plans created before portal_group existed fall back to the default name used by scripts and checks.
    base["portal_group"] = group_name(plan, get_or_404(db, Deal, plan.deal_id).account)
    return PovPlanDetail(
        **base,
        criteria=[CriterionOut.model_validate(c) for c in criteria],
        milestones=[task_out(t, by_id) for t in milestones],
        checklist=build_checklist(criteria, reqs),
        summary=summarise(criteria, milestones, reqs),
    )


@router.get("/deals/{deal_id}/pov-plans", response_model=list[PovPlanOut])
def list_pov_plans(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db)) -> list[PovPlan]:
    return db.query(PovPlan).filter_by(deal_id=deal.id).order_by(PovPlan.id.desc()).all()


@router.post("/deals/{deal_id}/pov-plans", response_model=PovPlanDetail, status_code=201)
def create_pov(body: PovPlanIn, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
               kb: KnowledgeBase = Depends(get_kb)) -> PovPlanDetail:
    plan = create_pov_plan(db, kb, deal, title=body.title, objectives=body.objectives,
                           start_date=body.start_date, duration_days=body.duration_days,
                           draft_criteria=body.draft_criteria_from_requirements, portal_group=body.portal_group)
    db.commit()
    return _pov_detail(db, plan)


@router.get("/pov-plans/{plan_id}", response_model=PovPlanDetail)
def get_pov(plan_id: int, db: Session = Depends(get_db)) -> PovPlanDetail:
    return _pov_detail(db, get_or_404(db, PovPlan, plan_id))


@router.patch("/pov-plans/{plan_id}", response_model=PovPlanDetail)
def update_pov(plan_id: int, body: PovPlanPatch, db: Session = Depends(get_db)) -> PovPlanDetail:
    plan = get_or_404(db, PovPlan, plan_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    db.commit()
    return _pov_detail(db, plan)


@router.get("/pov-plans/{plan_id}/export")
def export_pov(plan_id: int, db: Session = Depends(get_db)) -> PlainTextResponse:
    plan = get_or_404(db, PovPlan, plan_id)
    deal = get_or_404(db, Deal, plan.deal_id)
    criteria = db.query(SuccessCriterion).filter_by(pov_plan_id=plan.id).order_by(SuccessCriterion.id).all()
    milestones = db.query(Task).filter_by(pov_plan_id=plan.id).all()
    reqs = db.query(Requirement).filter_by(deal_id=deal.id).all()
    return _markdown(pov_plan_markdown(plan, deal, deal.account, criteria, milestones, reqs), plan.title)


@router.post("/pov-plans/{plan_id}/readiness")
def pov_readiness(plan_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    """Read-only readiness checks through the LogicMonitor MCP adapter (mock or live)."""
    plan = get_or_404(db, PovPlan, plan_id)
    deal = get_or_404(db, Deal, plan.deal_id)
    return run_readiness(request.app.state.adapters["lm_mcp"], plan, deal.account)


@router.post("/pov-plans/{plan_id}/setup-script")
def pov_setup_script(plan_id: int, body: SetupScriptIn, db: Session = Depends(get_db),
                     kb: KnowledgeBase = Depends(get_kb)) -> PlainTextResponse:
    """Logic.Monitor PowerShell script for a person to review and run (dry run by default)."""
    plan = get_or_404(db, PovPlan, plan_id)
    deal = get_or_404(db, Deal, plan.deal_id)
    try:
        script = generate_setup_script(kb, plan=plan, deal=deal, account=deal.account,
                                       toolkit_ids=body.toolkit_ids, include_subgroups=body.include_subgroups)
    except ScriptError as exc:
        raise HTTPException(422, str(exc)) from exc
    return PlainTextResponse(script, media_type="text/plain; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="pov-setup-{_slug(deal.account.name)}.ps1"'})


@router.get("/deals/{deal_id}/handoff")
def deal_handoff(request: Request, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                 kb: KnowledgeBase = Depends(get_kb), pov_plan_id: int | None = None) -> JSONResponse:
    """Versioned handoff package for downstream SE platforms (see docs/HANDOFF_FORMAT.md)."""
    try:
        package = build_handoff(db, kb, deal, pov_plan_id, request.app.state.settings.public_url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return JSONResponse(package.model_dump(mode="json"), headers={
        "Content-Disposition": f'attachment; filename="handoff-{_slug(deal.name)}.json"'})


@router.delete("/pov-plans/{plan_id}", status_code=204)
def delete_pov(plan_id: int, db: Session = Depends(get_db)) -> Response:
    db.delete(get_or_404(db, PovPlan, plan_id))
    db.commit()
    return Response(status_code=204)


# --- Success criteria & evidence --------------------------------------------
def _check_links(db: Session, deal_id: int, requirement_id: int | None, pov_plan_id: int | None) -> None:
    if requirement_id is not None and get_or_404(db, Requirement, requirement_id).deal_id != deal_id:
        raise HTTPException(422, "Requirement belongs to a different deal")
    if pov_plan_id is not None and get_or_404(db, PovPlan, pov_plan_id).deal_id != deal_id:
        raise HTTPException(422, "POV plan belongs to a different deal")


@router.get("/deals/{deal_id}/success-criteria", response_model=list[CriterionOut])
def list_criteria(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db)) -> list[SuccessCriterion]:
    return db.query(SuccessCriterion).filter_by(deal_id=deal.id).order_by(SuccessCriterion.id).all()


@router.post("/deals/{deal_id}/success-criteria", response_model=CriterionOut, status_code=201)
def create_criterion(body: CriterionIn, deal: Deal = Depends(deal_or_404),
                     db: Session = Depends(get_db)) -> SuccessCriterion:
    _check_links(db, deal.id, body.requirement_id, body.pov_plan_id)
    criterion = SuccessCriterion(deal_id=deal.id, **body.model_dump(exclude={"status"}))
    try:
        check_criterion_status(criterion, body.status)
    except EvidenceRuleError as exc:
        raise HTTPException(409, str(exc)) from exc
    criterion.status = body.status
    db.add(criterion)
    db.commit()
    return criterion


@router.patch("/success-criteria/{criterion_id}", response_model=CriterionOut)
def update_criterion(criterion_id: int, body: CriterionPatch, db: Session = Depends(get_db)) -> SuccessCriterion:
    criterion = get_or_404(db, SuccessCriterion, criterion_id)
    data = body.model_dump(exclude_unset=True)
    _check_links(db, criterion.deal_id, data.get("requirement_id"), data.get("pov_plan_id"))
    if "status" in data:
        try:
            check_criterion_status(criterion, data["status"])
        except EvidenceRuleError as exc:
            raise HTTPException(409, str(exc)) from exc
    for key, value in data.items():
        setattr(criterion, key, value)
    db.commit()
    return criterion


@router.delete("/success-criteria/{criterion_id}", status_code=204)
def delete_criterion(criterion_id: int, db: Session = Depends(get_db)) -> Response:
    db.delete(get_or_404(db, SuccessCriterion, criterion_id))
    db.commit()
    return Response(status_code=204)


@router.post("/success-criteria/{criterion_id}/evidence", response_model=EvidenceOut, status_code=201)
def add_evidence(criterion_id: int, body: EvidenceIn, db: Session = Depends(get_db)) -> Evidence:
    criterion = get_or_404(db, SuccessCriterion, criterion_id)
    evidence = Evidence(criterion_id=criterion.id, **body.model_dump())
    db.add(evidence)
    db.commit()
    return evidence


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: int, db: Session = Depends(get_db)) -> Response:
    evidence = get_or_404(db, Evidence, evidence_id)
    criterion = get_or_404(db, SuccessCriterion, evidence.criterion_id)
    remaining_real = [e for e in criterion.evidence if e.id != evidence.id and not e.is_simulated]
    if criterion.status == "met" and not remaining_real:
        raise HTTPException(409, "This is the last real evidence for a criterion marked 'met'. "
                                 "Change the criterion status first.")
    db.delete(evidence)
    db.commit()
    return Response(status_code=204)

"""Accounts, deals and stakeholders."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..knowledge import KnowledgeBase
from ..models import (
    Account,
    Deal,
    DemoPlan,
    DiscoveryAnswer,
    PovPlan,
    Requirement,
    Stakeholder,
    SuccessCriterion,
    Task,
)
from ..schemas import (
    AccountIn,
    AccountOut,
    AccountPatch,
    DealDetail,
    DealIn,
    DealListItem,
    DealOut,
    DealPatch,
    StakeholderIn,
    StakeholderOut,
    StakeholderPatch,
)
from ..services.accounts import find_account
from ..services.discovery import analyse_gaps, applicable_questions
from ..services.questions import deal_question_index
from ..services.workflow_engine import CLOSED
from .deps import deal_or_404, get_db, get_kb, get_or_404
from .integrations import import_link

router = APIRouter()


def _check_context(kb: KnowledgeBase, tags: list[str] | None) -> None:
    unknown = [t for t in tags or [] if t not in kb.context_tags]
    if unknown:
        raise HTTPException(422, f"Unknown technical context tag(s): {', '.join(unknown)}")


def _check_persona(kb: KnowledgeBase, persona_id: str | None) -> None:
    if persona_id is not None and persona_id not in kb.personas:
        raise HTTPException(422, f"Unknown persona '{persona_id}'. Available: {', '.join(kb.personas)}")


# --- Accounts ----------------------------------------------------------------
@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)) -> list[Account]:
    return db.query(Account).order_by(Account.name).all()


def _check_name_free(db: Session, name: str, exclude_id: int | None = None) -> None:
    existing = find_account(db, name, exclude_id=exclude_id)
    if existing:
        raise HTTPException(409, f"An account named '{existing.name}' already exists. Choose it from the account list.")


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(body: AccountIn, db: Session = Depends(get_db)) -> Account:
    _check_name_free(db, body.name)
    account = Account(**body.model_dump())
    db.add(account)
    db.commit()
    return account


@router.get("/accounts/{account_id}", response_model=AccountOut)
def get_account(account_id: int, db: Session = Depends(get_db)) -> Account:
    return get_or_404(db, Account, account_id)


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, body: AccountPatch, db: Session = Depends(get_db)) -> Account:
    account = get_or_404(db, Account, account_id)
    if body.name is not None:
        _check_name_free(db, body.name, exclude_id=account.id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    db.commit()
    return account


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db)) -> Response:
    db.delete(get_or_404(db, Account, account_id))
    db.commit()
    return Response(status_code=204)


# --- Deals -------------------------------------------------------------------
@router.get("/deals", response_model=list[DealListItem])
def list_deals(db: Session = Depends(get_db)) -> list[DealListItem]:
    deals = db.query(Deal).order_by(Deal.updated_at.desc()).all()
    return [DealListItem(**DealOut.model_validate(d).model_dump(), account_name=d.account.name) for d in deals]


@router.post("/deals", response_model=DealOut, status_code=201)
def create_deal(body: DealIn, db: Session = Depends(get_db), kb: KnowledgeBase = Depends(get_kb)) -> Deal:
    get_or_404(db, Account, body.account_id)
    _check_context(kb, body.technical_context)
    deal = Deal(**body.model_dump())
    db.add(deal)
    db.commit()
    return deal


def deal_metrics(db: Session, kb: KnowledgeBase, deal: Deal) -> dict:
    stakeholders = db.query(Stakeholder).filter_by(deal_id=deal.id).all()
    answers = db.query(DiscoveryAnswer).filter_by(deal_id=deal.id).all()
    reqs = db.query(Requirement).filter_by(deal_id=deal.id).all()
    criteria = db.query(SuccessCriterion).filter_by(deal_id=deal.id).all()
    demo_plans = db.query(DemoPlan).filter_by(deal_id=deal.id).all()
    tasks = db.query(Task).filter_by(deal_id=deal.id).all()
    index = deal_question_index(db, kb, deal.id)
    answered_ids = {a.question_id for a in answers if a.question_id in index}
    suggested = {q.id for q in applicable_questions(kb, [s.persona_id for s in stakeholders], deal.technical_context)}
    # Same scope as the Discovery tab: suggested, custom, or already answered.
    in_scope = {qid for qid, q in index.items() if qid in suggested or q.custom} | answered_ids
    gaps = analyse_gaps(kb, technical_context=deal.technical_context, stakeholders=stakeholders,
                        answers=answers, requirements=reqs, criteria=criteria, demo_plans=demo_plans,
                        questions=index)
    today = date.today()
    open_tasks = [t for t in tasks if t.status not in CLOSED]
    return {
        "stakeholders": len(stakeholders),
        "questions_total": len(in_scope),
        "questions_answered": len(answered_ids),
        "requirements": len(reqs),
        "criteria_total": len(criteria),
        "criteria_met": sum(1 for c in criteria if c.status == "met"),
        "demo_plans": len(demo_plans),
        "pov_plans": db.query(PovPlan).filter_by(deal_id=deal.id).count(),
        "open_tasks": len(open_tasks),
        "open_next_actions": sum(1 for t in open_tasks if t.kind == "next_action"),
        "blocked_tasks": sum(1 for t in open_tasks if t.status == "blocked"),
        "overdue_tasks": sum(1 for t in open_tasks if t.due_date and t.due_date < today),
        "gaps_high": sum(1 for g in gaps if g.severity == "high"),
        "gaps_total": len(gaps),
    }


@router.get("/deals/{deal_id}", response_model=DealDetail)
def get_deal(request: Request, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
             kb: KnowledgeBase = Depends(get_kb)) -> DealDetail:
    return DealDetail(**DealOut.model_validate(deal).model_dump(),
                      account=AccountOut.model_validate(deal.account),
                      metrics=deal_metrics(db, kb, deal),
                      external_import_link=import_link(deal, request.app.state.settings.public_url))


@router.patch("/deals/{deal_id}", response_model=DealOut)
def update_deal(body: DealPatch, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                kb: KnowledgeBase = Depends(get_kb)) -> Deal:
    data = body.model_dump(exclude_unset=True)
    _check_context(kb, data.get("technical_context"))
    for key, value in data.items():
        setattr(deal, key, value)
    db.commit()
    return deal


@router.delete("/deals/{deal_id}", status_code=204)
def delete_deal(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db)) -> Response:
    db.delete(deal)
    db.commit()
    return Response(status_code=204)


# --- Stakeholders ------------------------------------------------------------
@router.get("/deals/{deal_id}/stakeholders", response_model=list[StakeholderOut])
def list_stakeholders(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db)) -> list[Stakeholder]:
    return db.query(Stakeholder).filter_by(deal_id=deal.id).order_by(Stakeholder.id).all()


@router.post("/deals/{deal_id}/stakeholders", response_model=StakeholderOut, status_code=201)
def add_stakeholder(body: StakeholderIn, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                    kb: KnowledgeBase = Depends(get_kb)) -> Stakeholder:
    _check_persona(kb, body.persona_id)
    s = Stakeholder(deal_id=deal.id, **body.model_dump())
    db.add(s)
    db.commit()
    return s


@router.patch("/stakeholders/{stakeholder_id}", response_model=StakeholderOut)
def update_stakeholder(stakeholder_id: int, body: StakeholderPatch, db: Session = Depends(get_db),
                       kb: KnowledgeBase = Depends(get_kb)) -> Stakeholder:
    s = get_or_404(db, Stakeholder, stakeholder_id)
    data = body.model_dump(exclude_unset=True)
    _check_persona(kb, data.get("persona_id"))
    for key, value in data.items():
        setattr(s, key, value)
    db.commit()
    return s


@router.delete("/stakeholders/{stakeholder_id}", status_code=204)
def delete_stakeholder(stakeholder_id: int, db: Session = Depends(get_db)) -> Response:
    db.delete(get_or_404(db, Stakeholder, stakeholder_id))
    db.commit()
    return Response(status_code=204)

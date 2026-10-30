"""Discovery questions, answers, gap analysis and requirements."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..knowledge import KnowledgeBase
from ..models import Deal, DemoPlan, DiscoveryAnswer, Requirement, Stakeholder, SuccessCriterion
from ..schemas import (
    AnswerIn,
    AnswerOut,
    DiscoveryQuestionsOut,
    GapsOut,
    QuestionOut,
    RequirementIn,
    RequirementOut,
    RequirementPatch,
)
from ..services.discovery import analyse_gaps, applicable_questions, match_capabilities
from .deps import deal_or_404, get_db, get_kb, get_or_404

router = APIRouter()


@router.get("/deals/{deal_id}/discovery/questions", response_model=DiscoveryQuestionsOut)
def discovery_questions(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                        kb: KnowledgeBase = Depends(get_kb)) -> DiscoveryQuestionsOut:
    personas = {s.persona_id for s in db.query(Stakeholder).filter_by(deal_id=deal.id)}
    answers = {a.question_id: a for a in db.query(DiscoveryAnswer).filter_by(deal_id=deal.id)}
    questions = applicable_questions(kb, personas, deal.technical_context)
    out = [
        QuestionOut(
            **q.model_dump(include={"id", "text", "category", "purpose", "listen_for",
                                    "suggests_capabilities", "qualification_key", "priority"}),
            relevant_personas=sorted(personas & set(q.personas)) if "all" not in q.personas else ["all"],
            answer=AnswerOut.model_validate(answers[q.id]) if q.id in answers else None,
        )
        for q in questions
    ]
    shown = {q.id for q in questions}
    # Answers to questions no longer selected (e.g. a stakeholder was removed) are kept and shown.
    unmatched = [AnswerOut.model_validate(a) for qid, a in answers.items() if qid not in shown]
    return DiscoveryQuestionsOut(questions=out, answered=sum(1 for q in out if q.answer),
                                 total=len(out), unmatched_answers=unmatched)


@router.put("/deals/{deal_id}/discovery/answers/{question_id}", response_model=AnswerOut)
def save_answer(question_id: str, body: AnswerIn, deal: Deal = Depends(deal_or_404),
                db: Session = Depends(get_db), kb: KnowledgeBase = Depends(get_kb)) -> DiscoveryAnswer:
    if question_id not in kb.questions:
        raise HTTPException(404, f"Unknown question '{question_id}'")
    if body.stakeholder_id is not None:
        s = get_or_404(db, Stakeholder, body.stakeholder_id)
        if s.deal_id != deal.id:
            raise HTTPException(422, "Stakeholder belongs to a different deal")
    answer = db.query(DiscoveryAnswer).filter_by(deal_id=deal.id, question_id=question_id).first()
    if answer is None:
        answer = DiscoveryAnswer(deal_id=deal.id, question_id=question_id, **body.model_dump())
        db.add(answer)
    else:
        for key, value in body.model_dump().items():
            setattr(answer, key, value)
    db.commit()
    return answer


@router.delete("/deals/{deal_id}/discovery/answers/{question_id}", status_code=204)
def delete_answer(question_id: str, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db)) -> Response:
    answer = db.query(DiscoveryAnswer).filter_by(deal_id=deal.id, question_id=question_id).first()
    if answer is None:
        raise HTTPException(404, "Answer not found")
    db.delete(answer)
    db.commit()
    return Response(status_code=204)


@router.get("/deals/{deal_id}/discovery/gaps", response_model=GapsOut)
def discovery_gaps(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                   kb: KnowledgeBase = Depends(get_kb)) -> GapsOut:
    answers = db.query(DiscoveryAnswer).filter_by(deal_id=deal.id).all()
    gaps = analyse_gaps(
        kb,
        technical_context=deal.technical_context,
        stakeholders=db.query(Stakeholder).filter_by(deal_id=deal.id).all(),
        answers=answers,
        requirements=db.query(Requirement).filter_by(deal_id=deal.id).all(),
        criteria=db.query(SuccessCriterion).filter_by(deal_id=deal.id).all(),
        demo_plans=db.query(DemoPlan).filter_by(deal_id=deal.id).all(),
    )
    by_q = {a.question_id: a for a in answers}
    qualification = []
    for item in kb.discovery.qualification_checklist:
        linked = [q.id for q in kb.discovery.questions if q.qualification_key == item.key]
        confs = [by_q[q].confidence for q in linked if q in by_q]
        status = "confirmed" if "confirmed" in confs else "assumed" if confs else "missing"
        qualification.append({**item.model_dump(), "status": status, "question_ids": linked})
    return GapsOut(gaps=[g.as_dict() for g in gaps], qualification=qualification)


# --- Requirements ------------------------------------------------------------
def _check_capabilities(kb: KnowledgeBase, ids: list[str] | None) -> None:
    unknown = [c for c in ids or [] if c not in kb.capabilities]
    if unknown:
        raise HTTPException(422, f"Unknown capability id(s): {', '.join(unknown)}")


@router.get("/deals/{deal_id}/requirements", response_model=list[RequirementOut])
def list_requirements(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db)) -> list[Requirement]:
    return db.query(Requirement).filter_by(deal_id=deal.id).order_by(Requirement.id).all()


@router.post("/deals/{deal_id}/requirements", response_model=RequirementOut, status_code=201)
def create_requirement(body: RequirementIn, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                       kb: KnowledgeBase = Depends(get_kb)) -> Requirement:
    if body.source_question_id and body.source_question_id not in kb.questions:
        raise HTTPException(422, f"Unknown question '{body.source_question_id}'")
    _check_capabilities(kb, body.capability_ids)
    data = body.model_dump()
    if data["capability_ids"] is None:
        text = f"{body.title} {body.description} {body.pain_point}"
        data["capability_ids"] = [m.capability_id for m in match_capabilities(kb, text, body.source_question_id)][:4]
    req = Requirement(deal_id=deal.id, **data)
    db.add(req)
    db.commit()
    return req


@router.patch("/requirements/{requirement_id}", response_model=RequirementOut)
def update_requirement(requirement_id: int, body: RequirementPatch, db: Session = Depends(get_db),
                       kb: KnowledgeBase = Depends(get_kb)) -> Requirement:
    req = get_or_404(db, Requirement, requirement_id)
    data = body.model_dump(exclude_unset=True)
    _check_capabilities(kb, data.get("capability_ids"))
    for key, value in data.items():
        setattr(req, key, value)
    db.commit()
    return req


@router.delete("/requirements/{requirement_id}", status_code=204)
def delete_requirement(requirement_id: int, db: Session = Depends(get_db)) -> Response:
    db.delete(get_or_404(db, Requirement, requirement_id))
    db.commit()
    return Response(status_code=204)

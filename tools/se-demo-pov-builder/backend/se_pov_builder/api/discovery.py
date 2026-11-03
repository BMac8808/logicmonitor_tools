"""Discovery questions, answers, transcript import, gap analysis and requirements."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..knowledge import KnowledgeBase
from ..llm import LLMUnavailable
from ..models import Deal, DealQuestion, DemoPlan, DiscoveryAnswer, Requirement, Stakeholder, SuccessCriterion
from ..schemas import (
    AnswerIn,
    AnswerOut,
    CustomQuestionIn,
    CustomQuestionsBulkIn,
    CustomQuestionsBulkOut,
    DiscoveryQuestionsOut,
    GapsOut,
    NextQuestionOut,
    QuestionListIn,
    QuestionListOut,
    QuestionListProposal,
    QuestionOut,
    RequirementIn,
    RequirementOut,
    RequirementPatch,
    SkippedQuestion,
    TranscriptAcceptIn,
    TranscriptIn,
    TranscriptProposal,
    TranscriptProposalsOut,
)
from ..services import transcript as tx
from ..services.discovery import analyse_gaps, applicable_questions, match_capabilities
from ..services.questions import (
    CATEGORY_ORDER,
    QuestionRef,
    custom_id,
    custom_ref,
    deal_question_index,
    next_questions,
    parse_custom_id,
    qualification_status,
)
from .deps import deal_or_404, get_db, get_kb, get_or_404

router = APIRouter()


def _answers(db: Session, deal_id: int) -> dict[str, DiscoveryAnswer]:
    return {a.question_id: a for a in db.query(DiscoveryAnswer).filter_by(deal_id=deal_id)}


def _question_out(q: QuestionRef, *, personas: set[str], suggested: bool,
                  answer: DiscoveryAnswer | None) -> QuestionOut:
    return QuestionOut(
        id=q.id, text=q.text, category=q.category, purpose=q.purpose, listen_for=list(q.listen_for),
        suggests_capabilities=list(q.suggests_capabilities), qualification_key=q.qualification_key,
        priority=q.priority, suggested=suggested, custom=q.custom,
        relevant_personas=[] if q.custom else ["all"] if "all" in q.personas else sorted(personas & set(q.personas)),
        answer=AnswerOut.model_validate(answer) if answer else None,
    )


def _suggested_ids(db: Session, kb: KnowledgeBase, deal: Deal) -> tuple[set[str], set[str]]:
    personas = {s.persona_id for s in db.query(Stakeholder).filter_by(deal_id=deal.id)}
    return personas, {q.id for q in applicable_questions(kb, personas, deal.technical_context)}


@router.get("/deals/{deal_id}/discovery/questions", response_model=DiscoveryQuestionsOut)
def discovery_questions(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                        kb: KnowledgeBase = Depends(get_kb)) -> DiscoveryQuestionsOut:
    personas, suggested = _suggested_ids(db, kb, deal)
    index = deal_question_index(db, kb, deal.id)
    answers = _answers(db, deal.id)
    position = {qid: n for n, qid in enumerate(index)}
    ordered = sorted(index.values(), key=lambda q: (CATEGORY_ORDER.get(q.category, 9), q.custom,
                                                    q.id not in suggested, q.priority, position[q.id]))
    out = [_question_out(q, personas=personas, suggested=q.id in suggested, answer=answers.get(q.id))
           for q in ordered]
    in_scope = [q for q in out if q.suggested or q.custom or q.answer]
    # Answers whose question no longer exists (e.g. an id removed from the YAML) are kept and shown.
    unmatched = [AnswerOut.model_validate(a) for qid, a in answers.items() if qid not in index]
    return DiscoveryQuestionsOut(
        questions=out, answered=sum(1 for q in in_scope if q.answer), total=len(in_scope),
        bank_total=len(kb.discovery.questions),
        next_up=[NextQuestionOut(question_id=n.question_id, reason=n.reason)
                 for n in next_questions(kb, index, suggested, answers)],
        unmatched_answers=unmatched,
    )


@router.put("/deals/{deal_id}/discovery/answers/{question_id}", response_model=AnswerOut)
def save_answer(question_id: str, body: AnswerIn, deal: Deal = Depends(deal_or_404),
                db: Session = Depends(get_db), kb: KnowledgeBase = Depends(get_kb)) -> DiscoveryAnswer:
    if question_id not in deal_question_index(db, kb, deal.id):
        raise HTTPException(404, f"Unknown question '{question_id}'")
    if body.stakeholder_id is not None:
        s = get_or_404(db, Stakeholder, body.stakeholder_id)
        if s.deal_id != deal.id:
            raise HTTPException(422, "Stakeholder belongs to a different deal")
    return _upsert_answer(db, deal.id, question_id, body.model_dump())


def _upsert_answer(db: Session, deal_id: int, question_id: str, data: dict) -> DiscoveryAnswer:
    answer = db.query(DiscoveryAnswer).filter_by(deal_id=deal_id, question_id=question_id).first()
    if answer is None:
        answer = DiscoveryAnswer(deal_id=deal_id, question_id=question_id, **data)
        db.add(answer)
    else:
        for key, value in data.items():
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


# --- Custom questions (per deal) ------------------------------------------------
def _norm(text: str) -> str:
    return tx.normalise(text).lower().rstrip("?. ")


def _check_custom(kb: KnowledgeBase, body: CustomQuestionIn) -> None:
    keys = {i.key for i in kb.discovery.qualification_checklist}
    if body.qualification_key and body.qualification_key not in keys:
        raise HTTPException(422, f"Unknown qualification key '{body.qualification_key}'")


def _create_custom(db: Session, deal: Deal, body: CustomQuestionIn) -> DealQuestion:
    row = DealQuestion(deal_id=deal.id, text=tx.normalise(body.text), category=body.category,
                       purpose=body.purpose, qualification_key=body.qualification_key or None)
    db.add(row)
    db.flush()
    return row


@router.post("/deals/{deal_id}/discovery/custom-questions", response_model=QuestionOut, status_code=201)
def add_custom_question(body: CustomQuestionIn, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                        kb: KnowledgeBase = Depends(get_kb)) -> QuestionOut:
    _check_custom(kb, body)
    existing = {_norm(q.text): q for q in deal_question_index(db, kb, deal.id).values()}
    if _norm(body.text) in existing:
        dupe = existing[_norm(body.text)]
        raise HTTPException(409, f"This deal already has that question ({'custom' if dupe.custom else dupe.id})")
    row = _create_custom(db, deal, body)
    db.commit()
    return _question_out(custom_ref(row), personas=set(), suggested=False, answer=None)


@router.post("/deals/{deal_id}/discovery/custom-questions/bulk", response_model=CustomQuestionsBulkOut)
def add_custom_questions(body: CustomQuestionsBulkIn, deal: Deal = Depends(deal_or_404),
                         db: Session = Depends(get_db), kb: KnowledgeBase = Depends(get_kb)) -> CustomQuestionsBulkOut:
    for q in body.questions:
        _check_custom(kb, q)
    existing = {_norm(q.text) for q in deal_question_index(db, kb, deal.id).values()}
    created, skipped = [], []
    for q in body.questions:
        if _norm(q.text) in existing:
            skipped.append(SkippedQuestion(text=q.text, reason="Already in this deal's questions"))
            continue
        existing.add(_norm(q.text))
        created.append(_create_custom(db, deal, q))
    db.commit()
    return CustomQuestionsBulkOut(
        created=[_question_out(custom_ref(r), personas=set(), suggested=False, answer=None) for r in created],
        skipped=skipped,
    )


@router.delete("/deals/{deal_id}/discovery/custom-questions/{question_id}", status_code=204)
def delete_custom_question(question_id: str, deal: Deal = Depends(deal_or_404),
                           db: Session = Depends(get_db)) -> Response:
    row_id = parse_custom_id(question_id)
    row = db.get(DealQuestion, row_id) if row_id is not None else None
    if row is None or row.deal_id != deal.id:
        raise HTTPException(404, f"Custom question '{question_id}' not found on this deal")
    db.query(DiscoveryAnswer).filter_by(deal_id=deal.id, question_id=custom_id(row.id)).delete()
    db.delete(row)
    db.commit()
    return Response(status_code=204)


# --- Transcript and question-list import (stateless) ---------------------------
@router.post("/deals/{deal_id}/discovery/transcript/proposals", response_model=TranscriptProposalsOut)
def transcript_proposals(body: TranscriptIn, request: Request, deal: Deal = Depends(deal_or_404),
                         db: Session = Depends(get_db), kb: KnowledgeBase = Depends(get_kb)) -> TranscriptProposalsOut:
    """Propose answers found in a transcript. Nothing is stored: the transcript is discarded
    once the response is sent."""
    fmt, segments = tx.parse_transcript(body.text, body.filename)
    index = deal_question_index(db, kb, deal.id)
    answers = _answers(db, deal.id)
    confirmed = {qid for qid, a in answers.items() if a.confidence == "confirmed"}
    open_questions = {qid: q for qid, q in index.items() if qid not in confirmed}
    notes: list[str] = []
    if confirmed & set(index):
        notes.append(f"{len(confirmed & set(index))} question(s) already confirmed were not searched; "
                     "a transcript never replaces a confirmed answer.")
    if not segments:
        notes.append("No spoken text was found. Paste the transcript text, or a .vtt, .srt or .txt file.")

    proposals = tx.keyword_proposals(kb, open_questions.values(), segments)
    ai_used = False
    llm = request.app.state.llm
    if body.use_ai and segments:
        if not llm.enabled:
            notes.append("AI is not configured, so only keyword matching was used.")
        else:
            try:
                raw = llm.complete(tx.ai_prompt(open_questions.values(), segments), system=tx.AI_SYSTEM)
                ai, rejected = tx.verify_ai_proposals(raw, open_questions, segments)
                ai_used = True
                if rejected:
                    notes.append(f"{rejected} AI suggestion(s) were dropped because their quote is not "
                                 "word for word in the transcript.")
                keyword_keys = {(p.question_id, p.quote) for p in proposals}
                proposals = [p for p in ai if (p.question_id, p.quote) not in keyword_keys] + proposals
            except (LLMUnavailable, ValueError) as exc:
                notes.append(f"AI suggestions unavailable ({exc}); keyword matches are shown.")

    proposals.sort(key=lambda p: (p.segment_index, p.method != "ai"))
    key = request.app.state.receipt_key
    return TranscriptProposalsOut(
        format=fmt, segments=len(segments), ai_used=ai_used, notes=notes,
        proposals=[TranscriptProposal(
            question_id=p.question_id, question=index[p.question_id].text, category=index[p.question_id].category,
            quote=p.quote, speaker=p.speaker, timestamp=p.timestamp, proposed_answer=p.proposed_answer,
            matched=p.matched, method=p.method, score=p.score,
            existing_answer=AnswerOut.model_validate(answers[p.question_id]) if p.question_id in answers else None,
            receipt=tx.proposal_receipt(key, deal.id, p.question_id, p.quote, p.speaker, p.timestamp, body.filename),
        ) for p in proposals],
    )


@router.post("/deals/{deal_id}/discovery/transcript/accept", response_model=AnswerOut)
def accept_transcript_answer(body: TranscriptAcceptIn, request: Request, deal: Deal = Depends(deal_or_404),
                             db: Session = Depends(get_db), kb: KnowledgeBase = Depends(get_kb)) -> DiscoveryAnswer:
    """Save one reviewed proposal as an *assumed* answer with its quote as evidence. The receipt
    must come from .../transcript/proposals on this server, so the quote, speaker, timestamp and
    file it claims are ones this server actually found."""
    expected = tx.proposal_receipt(request.app.state.receipt_key, deal.id, body.question_id, body.quote,
                                   body.speaker, body.timestamp, body.filename)
    if not hmac.compare_digest(expected, body.receipt):
        raise HTTPException(403, "This quote has no valid receipt from Find answers on this server. Run Find answers "
                                 "again (receipts end when SE Builder restarts).")
    if body.question_id not in deal_question_index(db, kb, deal.id):
        raise HTTPException(404, f"Unknown question '{body.question_id}'")
    existing = db.query(DiscoveryAnswer).filter_by(deal_id=deal.id, question_id=body.question_id).first()
    if existing is not None and existing.confidence == "confirmed":
        raise HTTPException(409, "This question already has a confirmed answer; a transcript quote can't replace it. "
                                 "Edit the answer on the Discovery tab instead.")
    speaker = (body.speaker or "").strip()
    stakeholder = None
    if speaker:
        stakeholder = next((s for s in db.query(Stakeholder).filter_by(deal_id=deal.id)
                            if s.name.strip().lower() == speaker.lower()), None)
    where = " @ ".join(x for x in (body.filename.strip() or "call transcript", body.timestamp) if x)
    source = f"Transcript: {where}" + (f" ({speaker})" if speaker else "")
    return _upsert_answer(db, deal.id, body.question_id, {
        "answer": body.answer.strip(), "confidence": "assumed", "evidence_quote": tx.normalise(body.quote),
        "evidence_source": source[:300], "stakeholder_id": stakeholder.id if stakeholder else None,
    })


@router.post("/deals/{deal_id}/discovery/question-list/proposals", response_model=QuestionListOut)
def question_list_proposals(body: QuestionListIn, deal: Deal = Depends(deal_or_404),
                            db: Session = Depends(get_db), kb: KnowledgeBase = Depends(get_kb)) -> QuestionListOut:
    """Split a pasted list into candidate custom questions, flagging ones similar to
    existing questions. Nothing is stored."""
    index = deal_question_index(db, kb, deal.id)
    out = []
    for text in tx.parse_question_list(body.text):
        similar, score = tx.closest_question(text, index.values())
        level = ("likely" if score >= tx.LIKELY_DUPLICATE else
                 "possible" if score >= tx.POSSIBLE_DUPLICATE else None)
        out.append(QuestionListProposal(text=text, category=tx.guess_category(text), duplicate_level=level,
                                        duplicate_of=similar.id if level else None,
                                        duplicate_text=similar.text if level else None))
    return QuestionListOut(proposals=out)


@router.get("/deals/{deal_id}/discovery/gaps", response_model=GapsOut)
def discovery_gaps(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                   kb: KnowledgeBase = Depends(get_kb)) -> GapsOut:
    answers = db.query(DiscoveryAnswer).filter_by(deal_id=deal.id).all()
    index = deal_question_index(db, kb, deal.id)
    gaps = analyse_gaps(
        kb,
        technical_context=deal.technical_context,
        stakeholders=db.query(Stakeholder).filter_by(deal_id=deal.id).all(),
        answers=answers,
        requirements=db.query(Requirement).filter_by(deal_id=deal.id).all(),
        criteria=db.query(SuccessCriterion).filter_by(deal_id=deal.id).all(),
        demo_plans=db.query(DemoPlan).filter_by(deal_id=deal.id).all(),
        questions=index,
    )
    status = qualification_status(kb, index, {a.question_id: a for a in answers})
    qualification = [{**item.model_dump(), "status": status[item.key][0], "question_ids": status[item.key][1]}
                     for item in kb.discovery.qualification_checklist]
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
    if body.source_question_id and body.source_question_id not in deal_question_index(db, kb, deal.id):
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

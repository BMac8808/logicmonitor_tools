"""One view over the shared question bank and a deal's own custom questions.

Bank questions come from ``knowledge/discovery_questions.yaml`` and are shared by every
deal. Custom questions are stored per deal (``DealQuestion``) and use ids ``custom-<n>``.
Everything that labels or counts questions (API, gaps, handoff, AI prompts) goes through
``question_index`` so both kinds behave the same.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..knowledge import KnowledgeBase
from ..models import DealQuestion

CUSTOM_PREFIX = "custom-"
CATEGORY_ORDER = {"business": 0, "qualification": 1, "technical": 2, "process": 3, "stakeholder": 4}
HIGH_PRIORITY_QUALIFICATION = {"pain", "business_impact", "success_criteria", "decision_process"}


@dataclass(frozen=True)
class QuestionRef:
    id: str
    text: str
    category: str
    purpose: str = ""
    qualification_key: str | None = None
    listen_for: tuple[str, ...] = ()
    suggests_capabilities: tuple[str, ...] = ()
    priority: int = 2
    personas: tuple[str, ...] = ("all",)
    custom: bool = False


def custom_id(row_id: int) -> str:
    return f"{CUSTOM_PREFIX}{row_id}"


def parse_custom_id(question_id: str) -> int | None:
    if not question_id.startswith(CUSTOM_PREFIX):
        return None
    tail = question_id.removeprefix(CUSTOM_PREFIX)
    return int(tail) if tail.isdigit() else None


def custom_ref(row: DealQuestion) -> QuestionRef:
    return QuestionRef(id=custom_id(row.id), text=row.text, category=row.category, purpose=row.purpose,
                       qualification_key=row.qualification_key, custom=True)


def question_index(kb: KnowledgeBase, custom_rows: Iterable[DealQuestion] = ()) -> dict[str, QuestionRef]:
    """Bank questions (YAML order) followed by the deal's custom questions."""
    index = {
        q.id: QuestionRef(
            id=q.id, text=q.text, category=q.category, purpose=q.purpose, qualification_key=q.qualification_key,
            listen_for=tuple(q.listen_for), suggests_capabilities=tuple(q.suggests_capabilities),
            priority=q.priority, personas=tuple(q.personas),
        )
        for q in kb.discovery.questions
    }
    index.update({custom_id(r.id): custom_ref(r) for r in custom_rows})
    return index


def deal_question_index(db: Session, kb: KnowledgeBase, deal_id: int) -> dict[str, QuestionRef]:
    rows = db.query(DealQuestion).filter_by(deal_id=deal_id).order_by(DealQuestion.id).all()
    return question_index(kb, rows)


def qualification_status(
    kb: KnowledgeBase, index: Mapping[str, QuestionRef], answers: Mapping[str, object]
) -> dict[str, tuple[str, list[str]]]:
    """key -> (confirmed | assumed | missing, linked question ids). ``answers`` maps question
    id to an object with ``confidence`` and ``answer``."""
    out: dict[str, tuple[str, list[str]]] = {}
    for item in kb.discovery.qualification_checklist:
        linked = [q.id for q in index.values() if q.qualification_key == item.key]
        confs = [answers[q].confidence for q in linked  # type: ignore[attr-defined]
                 if q in answers and str(getattr(answers[q], "answer", "x")).strip()]
        status = "confirmed" if "confirmed" in confs else "assumed" if confs else "missing"
        out[item.key] = (status, linked)
    return out


@dataclass
class NextQuestion:
    question_id: str
    reason: str


def next_questions(
    kb: KnowledgeBase,
    index: Mapping[str, QuestionRef],
    suggested: set[str],
    answers: Mapping[str, object],
    limit: int = 5,
) -> list[NextQuestion]:
    """The few questions most worth asking next, each with the reason.

    Order: questions that cover a checklist item nobody has answered (high-impact items
    first, one question per item), then key questions for this deal's personas and
    technologies, then confirming answers that are only assumed, then the deal's own
    custom questions, then the remaining suggested questions. When few questions are
    suggested (e.g. no stakeholders yet), bank questions covering missing checklist items
    fill the list.
    """
    status = qualification_status(kb, index, answers)
    labels = {i.key: i.label for i in kb.discovery.qualification_checklist}
    candidates: list[tuple[tuple, NextQuestion]] = []
    for position, q in enumerate(index.values()):
        in_scope = q.id in suggested or q.custom
        answer = answers.get(q.id)
        if not in_scope:
            # Outside this deal's personas/technologies: only a fallback for missing checklist items.
            key = q.qualification_key
            if answer is None and key and status[key][0] == "missing":
                candidates.append(((6, q.priority, CATEGORY_ORDER.get(q.category, 9), position),
                                   NextQuestion(q.id, f"Covers checklist item: {labels[key]}")))
            continue
        key = q.qualification_key
        sort_tail = (q.priority, CATEGORY_ORDER.get(q.category, 9), position)
        if answer is None:
            if key and status[key][0] == "missing":
                rank = 0 if key in HIGH_PRIORITY_QUALIFICATION else 1
                candidates.append(((rank, *sort_tail), NextQuestion(q.id, f"Covers checklist item: {labels[key]}")))
            elif q.custom:
                candidates.append(((4, *sort_tail), NextQuestion(q.id, "Your question for this deal")))
            elif q.priority == 1:
                candidates.append(((2, *sort_tail), NextQuestion(q.id, "Key question for this deal")))
            else:
                candidates.append(((5, *sort_tail), NextQuestion(q.id, "Suggested for this deal")))
        elif getattr(answer, "confidence", "") == "assumed" and (not key or status[key][0] != "confirmed"):
            reason = f"Confirm assumed answer ({labels[key]})" if key else "Confirm assumed answer"
            candidates.append(((3, *sort_tail), NextQuestion(q.id, reason)))

    picked: list[NextQuestion] = []
    covered_keys: set[str] = set()
    for _, nq in sorted(candidates, key=lambda c: c[0]):
        key = index[nq.question_id].qualification_key
        if nq.reason.startswith("Covers checklist item") and key in covered_keys:
            continue  # one question per missing checklist item is enough
        if key:
            covered_keys.add(key)
        picked.append(nq)
        if len(picked) == limit:
            break
    return picked

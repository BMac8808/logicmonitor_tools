"""Discovery coach: question selection, capability matching, gap analysis and
suggested next actions. Purely rule-based; no LLM involved."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from ..knowledge import DiscoveryQuestion, KnowledgeBase
from ..models import DemoPlan, DiscoveryAnswer, Requirement, Stakeholder, SuccessCriterion
from .questions import CATEGORY_ORDER, HIGH_PRIORITY_QUALIFICATION, QuestionRef, question_index


def keyword_in(keyword: str, text: str) -> bool:
    """Case-insensitive whole-word/phrase match."""
    return re.search(rf"(?<!\w){re.escape(keyword.lower())}(?!\w)", text) is not None


def applicable_questions(
    kb: KnowledgeBase, persona_ids: Iterable[str], context_tags: Iterable[str]
) -> list[DiscoveryQuestion]:
    personas = set(persona_ids)
    contexts = set(context_tags)
    selected = [
        q
        for q in kb.discovery.questions
        if ("all" in q.personas or personas & set(q.personas))
        and ("any" in q.contexts or contexts & set(q.contexts))
    ]
    return sorted(selected, key=lambda q: (q.priority, CATEGORY_ORDER[q.category]))


@dataclass
class CapabilityMatch:
    capability_id: str
    name: str
    verified: bool
    matched_keywords: list[str]
    from_question: bool
    score: int


def match_capabilities(
    kb: KnowledgeBase, text: str, source_question_id: str | None = None
) -> list[CapabilityMatch]:
    lowered = text.lower()
    hinted: set[str] = set()
    if source_question_id and source_question_id in kb.questions:
        hinted = set(kb.questions[source_question_id].suggests_capabilities)
    matches: list[CapabilityMatch] = []
    for cap in kb.capability_catalog.capabilities:
        hits = [kw for kw in cap.keywords if keyword_in(kw, lowered)]
        from_question = cap.id in hinted
        if hits or from_question:
            matches.append(
                CapabilityMatch(
                    capability_id=cap.id,
                    name=cap.name,
                    verified=cap.verified,
                    matched_keywords=hits,
                    from_question=from_question,
                    score=len(hits) + (2 if from_question else 0),
                )
            )
    return sorted(matches, key=lambda m: (-m.score, m.capability_id))


@dataclass
class Gap:
    code: str
    category: str
    severity: str  # high | medium | low
    message: str
    suggested_action: str

    def as_dict(self) -> dict:
        return asdict(self)


def analyse_gaps(
    kb: KnowledgeBase,
    *,
    technical_context: list[str],
    stakeholders: list[Stakeholder],
    answers: list[DiscoveryAnswer],
    requirements: list[Requirement],
    criteria: list[SuccessCriterion],
    demo_plans: list[DemoPlan],
    questions: dict[str, QuestionRef] | None = None,
) -> list[Gap]:
    """``questions`` is the deal's question index (bank + custom); defaults to the bank."""
    questions = questions if questions is not None else question_index(kb)
    gaps: list[Gap] = []
    persona_ids = {s.persona_id for s in stakeholders}

    if not stakeholders:
        gaps.append(Gap("no_stakeholders", "stakeholders", "high", "No stakeholders recorded.",
                        "Add the people you have met and assign each a persona."))
    for persona in kb.personas.values():
        if persona.coverage == "required" and persona.id not in persona_ids:
            gaps.append(Gap(
                f"missing_persona:{persona.id}", "stakeholders", "high",
                f"No stakeholder identified as {persona.name}.",
                f"Ask your champion who plays the {persona.name} role and request an introduction.",
            ))
    if not technical_context:
        gaps.append(Gap("no_technical_context", "discovery", "medium",
                        "No technical context tags set on the deal; only generic questions are shown.",
                        "Set the technologies in scope on the deal overview."))

    answered = {a.question_id: a for a in answers if a.answer.strip()}
    for item in kb.discovery.qualification_checklist:
        linked = [q.id for q in questions.values() if q.qualification_key == item.key]
        confirmed = [qid for qid in linked if qid in answered and answered[qid].confidence == "confirmed"]
        if confirmed:
            continue
        assumed_only = any(qid in answered for qid in linked)
        severity = "high" if item.key in HIGH_PRIORITY_QUALIFICATION else "medium"
        if assumed_only:
            gaps.append(Gap(f"assumed_qualification:{item.key}", "qualification", "medium",
                            f"{item.label} is based on assumptions only.",
                            f"Confirm {item.label.lower()} directly with a stakeholder."))
        else:
            gaps.append(Gap(f"unanswered_qualification:{item.key}", "qualification", severity,
                            f"Qualification item not covered: {item.label}. {item.description}",
                            f"Cover {item.label.lower()} in the next discovery conversation."))

    for a in answers:
        if a.confidence == "assumed" and a.question_id in questions:
            q = questions[a.question_id]
            if q.qualification_key:
                continue  # already reported at checklist level
            gaps.append(Gap(f"assumed_answer:{a.question_id}", "evidence", "low",
                            f"Answer is assumed, not confirmed: \"{q.text}\"",
                            "Confirm this answer with the relevant stakeholder."))

    if not requirements:
        gaps.append(Gap("no_requirements", "requirements", "high", "No requirements captured yet.",
                        "Turn discovery answers into prioritised requirements."))
    criteria_by_req: dict[int, list[SuccessCriterion]] = {}
    for c in criteria:
        if c.requirement_id is not None:
            criteria_by_req.setdefault(c.requirement_id, []).append(c)
    unverified: set[str] = set()
    for r in requirements:
        if not r.capability_ids:
            gaps.append(Gap(f"requirement_unmapped:{r.id}", "requirements", "medium",
                            f"Requirement \"{r.title}\" is not mapped to any capability.",
                            "Map it to a capability, or record it as a risk if nothing fits."))
        unverified.update(c for c in r.capability_ids if c in kb.capabilities and not kb.capabilities[c].verified)
        if r.priority == "must" and r.id not in criteria_by_req:
            gaps.append(Gap(f"must_without_criteria:{r.id}", "pov", "high",
                            f"Must-have requirement \"{r.title}\" has no success criterion.",
                            "Define a measurable success criterion and how it will be validated."))
    if unverified:
        gaps.append(Gap("unverified_capabilities", "requirements", "low",
                        f"{len(unverified)} mapped capabilities are not verified against official documentation.",
                        "Verify each mapped capability in current official documentation before presenting it."))

    for c in criteria:
        if not c.measurable_outcome.strip() or not c.validation_method.strip():
            gaps.append(Gap(f"criterion_incomplete:{c.id}", "pov", "medium",
                            f"Success criterion \"{c.title}\" lacks a measurable outcome or validation method.",
                            "Agree the measurable outcome and validation method with the customer validator."))
        elif not c.owner.strip():
            gaps.append(Gap(f"criterion_no_owner:{c.id}", "pov", "low",
                            f"Success criterion \"{c.title}\" has no owner.",
                            "Name the customer validator responsible for this criterion."))

    if requirements and not demo_plans:
        gaps.append(Gap("no_demo_plan", "demo", "low", "No demo plan generated yet.",
                        "Generate a demo plan from the saved discovery findings."))

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(gaps, key=lambda g: severity_rank[g.severity])

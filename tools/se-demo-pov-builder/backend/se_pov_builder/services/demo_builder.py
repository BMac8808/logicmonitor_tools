"""Demo builder: choose demo scenarios from saved discovery data and compose an agenda.

Every line of output comes from YAML content or saved deal data. The plan lists its own
assumptions and missing evidence instead of filling gaps with invented detail.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..knowledge import DemoScenario, KnowledgeBase
from ..models import Deal, DiscoveryAnswer, Requirement, Stakeholder, utcnow
from .discovery import keyword_in

GENERATOR_VERSION = "rules-v1"
PRIORITY_WEIGHT = {"must": 3, "should": 2, "could": 1}
OPENING_MINUTES = 5
RECAP_MINUTES = 5
CLOSING_MINUTES = 10
FIXED_MINUTES = OPENING_MINUTES + RECAP_MINUTES + CLOSING_MINUTES


@dataclass(eq=False)
class _Candidate:
    scenario: DemoScenario
    requirements: list[Requirement]
    keywords: list[str]
    context_match: bool
    context_ok: bool = True
    score: float = 0
    reason: str = ""
    linked_answers: list[str] = field(default_factory=list)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def generate_demo_plan(
    kb: KnowledgeBase,
    *,
    deal: Deal,
    stakeholders: list[Stakeholder],
    answers: list[DiscoveryAnswer],
    requirements: list[Requirement],
    duration_minutes: int = 60,
    max_scenarios: int = 4,
) -> dict:
    if duration_minutes < FIXED_MINUTES + 5:
        raise ValueError(f"Duration must be at least {FIXED_MINUTES + 5} minutes")
    deal_context = set(deal.technical_context or [])
    corpus = " ".join(
        [f"{r.title} {r.description} {r.pain_point}" for r in requirements]
        + [a.answer for a in answers]
    ).lower()

    candidates: list[_Candidate] = []
    for scenario in kb.scenario_library.scenarios:
        caps = set(scenario.capabilities)
        reqs = [r for r in requirements if caps & set(r.capability_ids)]
        kws = [kw for kw in scenario.pain_keywords if keyword_in(kw, corpus)]
        specific_contexts = set(scenario.contexts) - {"any"}
        context_match = bool(specific_contexts & deal_context)
        context_ok = "any" in scenario.contexts or context_match
        if not reqs and not context_ok:
            continue  # scenario is for a technology this deal does not use
        cand = _Candidate(scenario, reqs, kws, context_match)
        cand.context_ok = context_ok
        candidates.append(cand)

    available = duration_minutes - FIXED_MINUTES
    selected: list[_Candidate] = []

    def fits(c: _Candidate) -> bool:
        return c not in selected and c.scenario.duration_minutes <= available and len(selected) < max_scenarios

    def take(c: _Candidate, score: float) -> None:
        nonlocal available
        c.score = round(score, 2)
        selected.append(c)
        available -= c.scenario.duration_minutes

    # 1. Greedy coverage at capability level: a scenario earns each requirement's priority weight in
    #    proportion to the share of that requirement's capabilities it shows that are not covered
    #    yet. Scenarios that merely repeat a generic capability (e.g. alerting) therefore do not
    #    crowd out more relevant ones. Scenarios outside the deal's technical context count half.
    remaining = {r.id: set(r.capability_ids) for r in requirements}
    while True:
        best, best_score = None, 0.0
        for c in candidates:
            if not fits(c):
                continue
            caps = set(c.scenario.capabilities)
            gain = sum(
                PRIORITY_WEIGHT.get(r.priority, 1) * len(remaining[r.id] & caps) / max(1, len(r.capability_ids))
                for r in c.requirements
            )
            if gain == 0:
                continue
            score = gain * (1 if c.context_ok else 0.5) + 0.5 * len(c.keywords) + 0.5 * int(c.context_match)
            if score > best_score:
                best, best_score = c, score
        if best is None:
            break
        take(best, best_score)
        for r in best.requirements:
            remaining[r.id] -= set(best.scenario.capabilities)

    # 2. Scenarios supported only by discovery keywords (or redundant requirement coverage).
    keyword_backed = sorted((c for c in candidates if c.keywords and c.context_ok),
                            key=lambda c: -(len(c.keywords) + int(c.context_match)))
    for c in keyword_backed:
        if fits(c):
            take(c, len(c.keywords) + int(c.context_match))

    # 3. Nothing matched discovery: generic overview from the technical context.
    generic = not selected
    if generic:
        for c in sorted(candidates, key=lambda c: -int(c.context_match)):
            if fits(c):
                take(c, int(c.context_match))

    for cand in selected:
        if cand.requirements:
            names = ", ".join(f"'{r.title}' ({r.priority})" for r in cand.requirements)
            cand.reason = f"Addresses requirement(s): {names}"
            if not cand.context_ok:
                cand.reason += " — outside the deal's technical context; confirm relevance"
        elif cand.keywords:
            cand.reason = f"Discovery notes mention: {', '.join(cand.keywords)}"
        else:
            cand.reason = "Generic overview scenario: no discovery match (matches technical context)" \
                if cand.context_match else "Generic overview scenario: no discovery match"

    # Audience: personas present on the deal, with their stakeholders.
    audience: dict[str, list[str]] = {}
    for s in stakeholders:
        audience.setdefault(s.persona_id, []).append(s.name)

    segments = []
    for cand in selected:
        sc = cand.scenario
        talking_points = []
        if sc.audience_talking_points.get("default"):
            talking_points.append({"audience": "Everyone", "persona_id": None, "stakeholders": [],
                                   "points": sc.audience_talking_points["default"]})
        for persona_id, names in audience.items():
            points = sc.audience_talking_points.get(persona_id)
            if points:
                persona = kb.personas.get(persona_id)
                talking_points.append({"audience": persona.name if persona else persona_id,
                                       "persona_id": persona_id, "stakeholders": names, "points": points})
        segments.append({
            "scenario_id": sc.id,
            "title": sc.title,
            "summary": sc.summary,
            "minutes": sc.duration_minutes,
            "selection_reason": cand.reason,
            "score": cand.score,
            "demonstrates": sc.demonstrates,
            "capabilities": [
                {"id": c, "name": kb.capabilities[c].name, "verified": kb.capabilities[c].verified}
                for c in sc.capabilities
            ],
            "linked_requirements": [
                {"id": r.id, "title": r.title, "priority": r.priority, "pain_point": r.pain_point}
                for r in cand.requirements
            ],
            "matched_keywords": cand.keywords,
            "talking_points": talking_points,
            "prerequisites": sc.prerequisites,
            "data_requirements": sc.data_requirements,
            "prep_tasks": sc.prep_tasks,
        })

    pain_points = [
        {"requirement_id": r.id, "requirement": r.title, "priority": r.priority, "pain_point": r.pain_point}
        for r in sorted(requirements, key=lambda r: -PRIORITY_WEIGHT.get(r.priority, 1))
        if r.pain_point.strip()
    ]

    agenda = []
    minute = 0

    def add(title: str, minutes: int, kind: str, ref: str | None = None) -> None:
        nonlocal minute
        agenda.append({"start_minute": minute, "minutes": minutes, "title": title, "kind": kind, "scenario_id": ref})
        minute += minutes

    add("Introductions, objectives and agenda confirmation", OPENING_MINUTES, "opening")
    add("Recap of what we heard in discovery (confirm accuracy)", RECAP_MINUTES, "recap")
    for seg in segments:
        add(seg["title"], seg["minutes"], "scenario", seg["scenario_id"])
    buffer = duration_minutes - minute - CLOSING_MINUTES
    if buffer > 0:
        add("Buffer for questions during scenarios", buffer, "buffer")
    add("Questions, open items and agreed next steps", CLOSING_MINUTES, "closing")

    covered_req_ids = {r["id"] for seg in segments for r in seg["linked_requirements"]}
    uncovered = [
        {"id": r.id, "title": r.title, "priority": r.priority}
        for r in requirements
        if r.id not in covered_req_ids and r.priority in ("must", "should")
    ]

    answers_by_q = {a.question_id: a for a in answers}
    assumptions: list[str] = []
    missing: list[str] = []
    if not requirements:
        assumptions.append(
            "No requirements have been captured, so scenarios were chosen from technical context only. "
            "Complete discovery to tailor this plan."
        )
    if generic and requirements:
        assumptions.append("No captured requirement or discovery note matched a demo scenario; the plan is generic.")
    for a in answers:
        if a.confidence == "assumed" and a.question_id in kb.questions:
            assumptions.append(f"Assumed, not confirmed: \"{kb.questions[a.question_id].text}\" → {a.answer}")
    for persona in kb.personas.values():
        if persona.coverage == "required" and persona.id not in audience:
            assumptions.append(
                f"No {persona.name} identified; content for that role is not tailored to a named person."
            )
    for cand in selected:
        if not cand.requirements and cand.keywords:
            assumptions.append(
                f"'{cand.scenario.title}' was selected from discovery keywords, not a captured requirement."
            )

    linked_reqs = [r for r in requirements if r.id in covered_req_ids]
    for r in linked_reqs:
        if not r.pain_point.strip():
            missing.append(f"No pain point recorded for requirement '{r.title}'.")
        src = answers_by_q.get(r.source_question_id or "")
        if r.source_question_id and (src is None or src.confidence != "confirmed"):
            missing.append(f"Requirement '{r.title}' is not backed by a confirmed discovery answer.")
    impact_questions = [q.id for q in kb.discovery.questions if q.qualification_key == "business_impact"]
    if not any(q in answers_by_q for q in impact_questions):
        missing.append("No quantified business impact recorded; value statements cannot use the customer's numbers.")
    unverified = sorted({c["name"] for seg in segments for c in seg["capabilities"] if not c["verified"]})
    if unverified:
        missing.append(
            f"{len(unverified)} capabilities in this plan are not verified against official documentation: "
            + ", ".join(unverified) + "."
        )

    prep_tasks = _dedupe([t for seg in segments for t in seg["prep_tasks"]])
    if unverified:
        prep_tasks.insert(0, "Verify every capability shown against current official documentation")
    prep_tasks.append("Confirm attendees and agenda with the champion")

    audience_focus = []
    for persona_id, names in audience.items():
        persona = kb.personas.get(persona_id)
        if persona:
            audience_focus.append({
                "persona_id": persona_id, "persona": persona.name, "stakeholders": names,
                "focus": persona.demo_focus, "concerns": persona.technical_concerns[:3],
            })

    return {
        "generator": GENERATOR_VERSION,
        "generated_at": utcnow().isoformat(),
        "duration_minutes": duration_minutes,
        "generic": generic,
        "agenda": agenda,
        "segments": segments,
        "pain_points": pain_points,
        "audience_focus": audience_focus,
        "prerequisites": _dedupe([p for seg in segments for p in seg["prerequisites"]]),
        "data_requirements": _dedupe([d for seg in segments for d in seg["data_requirements"]]),
        "prep_tasks": prep_tasks,
        "uncovered_requirements": uncovered,
        "assumptions": assumptions,
        "missing_evidence": missing,
        "inputs": {
            "stakeholder_ids": [s.id for s in stakeholders],
            "requirement_ids": [r.id for r in requirements],
            "answer_count": len(answers),
            "technical_context": sorted(deal_context),
            "capability_disclaimer": kb.capability_catalog.disclaimer,
        },
    }

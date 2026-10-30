from types import SimpleNamespace as NS

from se_pov_builder.services.discovery import analyse_gaps, applicable_questions, keyword_in, match_capabilities


def test_questions_filtered_by_persona_and_context(kb):
    base = {q.id for q in applicable_questions(kb, [], [])}
    assert "biz_trigger" in base  # personas: all, contexts: any
    assert "tech_network" not in base

    network = {q.id for q in applicable_questions(kb, ["technical_buyer"], ["network"])}
    assert "tech_network" in network
    assert "tech_kubernetes" not in network

    k8s = {q.id for q in applicable_questions(kb, ["practitioner"], ["kubernetes"])}
    assert "tech_kubernetes" in k8s


def test_questions_sorted_by_priority(kb):
    qs = applicable_questions(kb, ["champion", "technical_buyer"], ["network"])
    assert [q.priority for q in qs] == sorted(q.priority for q in qs)


def test_keyword_matching_is_whole_word():
    assert keyword_in("api", "we use the api daily")
    assert not keyword_in("api", "rapid growth")
    assert keyword_in("load balancer", "f5 load balancer pairs")


def test_capability_matching_explains_itself(kb):
    matches = match_capabilities(kb, "Too many alerts and alert fatigue in the NOC")
    top = {m.capability_id: m for m in matches}
    assert "alerting_escalation" in top
    assert "alert fatigue" in top["alerting_escalation"].matched_keywords

    hinted = match_capabilities(kb, "nothing relevant here", source_question_id="tech_kubernetes")
    assert {m.capability_id for m in hinted} == {"container_monitoring", "log_analysis"}
    assert all(m.from_question and not m.matched_keywords for m in hinted)


def _gaps(kb, **kw):
    defaults = dict(technical_context=[], stakeholders=[], answers=[], requirements=[], criteria=[], demo_plans=[])
    defaults.update(kw)
    return {g.code: g for g in analyse_gaps(kb, **defaults)}


def test_gaps_for_empty_deal(kb):
    gaps = _gaps(kb)
    assert "no_stakeholders" in gaps
    assert "missing_persona:champion" in gaps and gaps["missing_persona:champion"].severity == "high"
    assert "missing_persona:detractor" not in gaps  # optional persona
    assert "unanswered_qualification:pain" in gaps
    assert "no_requirements" in gaps
    assert all(g.suggested_action for g in gaps.values())


def test_gaps_resolve_as_discovery_progresses(kb):
    stakeholders = [NS(persona_id=p) for p in ("champion", "economic_buyer", "technical_buyer")]
    answers = [NS(question_id="biz_trigger", answer="Outages", confidence="confirmed"),
               NS(question_id="qual_budget", answer="Maybe", confidence="assumed")]
    req = NS(id=1, title="Network visibility", priority="must", capability_ids=["network_monitoring"])
    criterion = NS(id=5, title="Devices visible", requirement_id=1, measurable_outcome="", validation_method="",
                   owner="")
    gaps = _gaps(kb, technical_context=["network"], stakeholders=stakeholders, answers=answers,
                 requirements=[req], criteria=[criterion])
    assert not any(code.startswith("missing_persona") for code in gaps)
    assert "unanswered_qualification:pain" not in gaps
    assert "assumed_qualification:budget" in gaps
    assert "must_without_criteria:1" not in gaps
    assert "criterion_incomplete:5" in gaps
    assert "unverified_capabilities" in gaps
    assert "no_demo_plan" in gaps

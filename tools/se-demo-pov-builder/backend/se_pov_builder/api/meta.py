"""Health, metadata, content library, adapters, optional LLM and sample data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import __version__
from ..adapters.base import AdapterError, Authorization, AuthorizationRequired, UnknownAction
from ..knowledge import ContentError, KnowledgeBase
from ..llm import AI_LABEL, LLMUnavailable
from ..models import Deal, DiscoveryAnswer, Requirement, Stakeholder
from ..schemas import AdapterActionIn, CapabilityMatchIn, CapabilityMatchOut, LLMDraftOut
from ..seed import SAMPLE_DEAL_NAME, seed_sample_engagement
from ..services.discovery import match_capabilities
from ..services.handoff import HandoffPackage
from ..services.questions import deal_question_index
from .deps import deal_or_404, get_db, get_kb

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/meta")
def meta(request: Request) -> dict:
    s = request.app.state.settings
    return {
        "name": "SE Demo & POV Builder",
        "version": __version__,
        "disclaimer": "Community tool. Not an official LogicMonitor product. Synthetic data only.",
        "adapter_mode": s.adapter_mode,
        "mcp_url": s.mcp_url if s.adapter_mode == "mcp" else "",
        "llm_provider": s.llm_provider,
        "llm_enabled": request.app.state.llm.enabled,
        "auth_required": bool(s.api_token),
        "allow_sample_data": s.allow_sample_data,
    }


@router.post("/sample-data", status_code=201)
def load_sample(request: Request, db: Session = Depends(get_db), kb: KnowledgeBase = Depends(get_kb)) -> dict:
    if not request.app.state.settings.allow_sample_data:
        raise HTTPException(403, "Sample data is disabled (SEPB_ALLOW_SAMPLE_DATA=false)")
    existing = db.query(Deal).filter_by(name=SAMPLE_DEAL_NAME).first()
    if existing:
        return {"deal_id": existing.id, "created": False}
    deal_id = seed_sample_engagement(db, kb)
    db.commit()
    return {"deal_id": deal_id, "created": True}


# --- Library -----------------------------------------------------------------
@router.get("/library/personas")
def personas(kb: KnowledgeBase = Depends(get_kb)) -> list[dict]:
    return [p.model_dump() for p in kb.personas.values()]


@router.get("/library/personas/{persona_id}")
def persona(persona_id: str, kb: KnowledgeBase = Depends(get_kb)) -> dict:
    if persona_id not in kb.personas:
        raise HTTPException(404, f"Persona '{persona_id}' not found")
    return kb.personas[persona_id].model_dump()


@router.get("/library/capabilities")
def capabilities(kb: KnowledgeBase = Depends(get_kb)) -> dict:
    return kb.capability_catalog.model_dump()


@router.post("/library/capabilities/match", response_model=list[CapabilityMatchOut])
def capability_match(body: CapabilityMatchIn, kb: KnowledgeBase = Depends(get_kb)) -> list:
    return [m.__dict__ for m in match_capabilities(kb, body.text, body.source_question_id)]


@router.get("/library/discovery")
def discovery_library(kb: KnowledgeBase = Depends(get_kb)) -> dict:
    return kb.discovery.model_dump()


@router.get("/library/demo-scenarios")
def demo_scenarios(kb: KnowledgeBase = Depends(get_kb)) -> list[dict]:
    return [s.model_dump() for s in kb.scenario_library.scenarios]


@router.get("/library/workflows")
def workflows(kb: KnowledgeBase = Depends(get_kb)) -> list[dict]:
    return [w.model_dump() for w in kb.workflows.values()]


@router.get("/library/pov-template")
def pov_template(kb: KnowledgeBase = Depends(get_kb)) -> dict:
    return kb.pov_template.model_dump()


@router.get("/library/ecosystem")
def ecosystem(kb: KnowledgeBase = Depends(get_kb)) -> dict:
    eco = kb.ecosystem

    def item(i) -> dict:
        data = i.model_dump(by_alias=True)
        data["source_url"] = eco.source_url(i)
        data["project_name"] = eco.project(i.project).name
        data["license"] = eco.project(i.project).license
        return data

    return {
        "projects": [p.model_dump() for p in eco.projects],
        "toolkit": [item(t) for t in eco.toolkit],
        "references": [item(r) for r in eco.references],
    }


@router.get("/handoff/schema")
def handoff_schema() -> dict:
    return HandoffPackage.model_json_schema()


@router.post("/library/reload")
def reload_content(request: Request) -> dict:
    try:
        kb = KnowledgeBase.load(request.app.state.settings.content_dir)
    except ContentError as exc:
        detail = {"message": "Content is invalid; previous content kept", "problems": exc.problems}
        raise HTTPException(422, detail) from exc
    request.app.state.kb = kb
    return {"personas": len(kb.personas), "questions": len(kb.questions), "scenarios": len(kb.scenarios),
            "workflows": len(kb.workflows), "capabilities": len(kb.capabilities)}


# --- Adapters ----------------------------------------------------------------
@router.get("/adapters")
def list_adapters(request: Request) -> list[dict]:
    return [a.describe() for a in request.app.state.adapters.values()]


@router.post("/adapters/{adapter_id}/actions/{action}")
def run_adapter_action(adapter_id: str, action: str, body: AdapterActionIn, request: Request) -> dict:
    adapter = request.app.state.adapters.get(adapter_id)
    if adapter is None:
        raise HTTPException(404, f"Adapter '{adapter_id}' not found")
    auth = None
    if body.authorization:
        a = body.authorization
        auth = Authorization(a.approved_by, a.reason, tuple(a.scope), a.expires_at)
    try:
        return adapter.execute(action, body.params, auth).as_dict()
    except UnknownAction as exc:
        raise HTTPException(404, str(exc)) from exc
    except AuthorizationRequired as exc:
        raise HTTPException(403, str(exc)) from exc
    except AdapterError as exc:
        raise HTTPException(422, str(exc)) from exc


# --- Optional LLM ------------------------------------------------------------
@router.get("/llm/status")
def llm_status(request: Request) -> dict:
    llm = request.app.state.llm
    return {"enabled": llm.enabled, "provider": llm.name, "label": AI_LABEL}


@router.post("/deals/{deal_id}/llm/discovery-summary", response_model=LLMDraftOut)
def discovery_summary(
    request: Request,
    deal: Deal = Depends(deal_or_404),
    db: Session = Depends(get_db),
    kb: KnowledgeBase = Depends(get_kb),
) -> LLMDraftOut:
    llm = request.app.state.llm
    if not llm.enabled:
        raise HTTPException(409, "Optional AI drafting is disabled. All core features work without it.")
    stakeholders = db.query(Stakeholder).filter_by(deal_id=deal.id).all()
    answers = db.query(DiscoveryAnswer).filter_by(deal_id=deal.id).all()
    reqs = db.query(Requirement).filter_by(deal_id=deal.id).all()
    index = deal_question_index(db, kb, deal.id)
    lines = [f"Deal: {deal.name}", f"Summary: {deal.summary}", "Stakeholders:"]
    lines += [f"- {s.name} ({s.title}), persona: {s.persona_id}, stance: {s.stance}" for s in stakeholders]
    lines.append("Discovery answers:")
    lines += [
        f"- Q: {index[a.question_id].text if a.question_id in index else a.question_id}\n"
        f"  A ({a.confidence}): {a.answer}"
        for a in answers
    ]
    lines.append("Requirements:")
    lines += [f"- [{r.priority}] {r.title}: {r.pain_point}" for r in reqs]
    system = (
        "You help a sales engineer summarise discovery notes. Use only the facts provided. "
        "Do not invent product capabilities, numbers or customer statements. Mark anything "
        "labelled 'assumed' as unconfirmed. Output: a short summary, key pains, open questions."
    )
    try:
        draft = llm.complete("\n".join(lines), system=system)
    except LLMUnavailable as exc:
        raise HTTPException(502, str(exc)) from exc
    return LLMDraftOut(draft=draft, label=AI_LABEL, provider=llm.name)

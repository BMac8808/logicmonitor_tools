"""Inbound links from a system of record (for example LMDA).

The system of record sends a neutral opportunity summary; this app creates or updates a
deal linked to it and returns the deal URL to open. Mapping from the system's own data
model happens on its side, so nothing here depends on its internals.
"""

from __future__ import annotations

from datetime import date
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..knowledge import KnowledgeBase
from ..models import Account, Deal
from ..services.handoff import deal_url
from .deps import get_db, get_kb

router = APIRouter()


def _http_url(value: str | None) -> str | None:
    if value and not value.startswith(("http://", "https://")):
        raise ValueError("must be an http(s) URL")
    return value


class LinkedAccount(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    industry: str = ""
    region: str = ""
    is_synthetic: bool = False


class LinkedOpportunity(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    stage: str = ""
    summary: str = ""
    target_close: date | None = None
    technical_context: list[str] = []


class OpportunityLinkIn(BaseModel):
    system: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_-]+$")
    external_id: str = Field(min_length=1, max_length=120)
    external_url: str | None = Field(default=None, max_length=1000)
    # Where to send people to import the deal back; "{deal_url}" is substituted.
    import_url_template: str | None = Field(default=None, max_length=1000)
    account: LinkedAccount
    opportunity: LinkedOpportunity

    _check_urls = field_validator("external_url", "import_url_template")(_http_url)


class OpportunityLinkOut(BaseModel):
    deal_id: int
    deal_url: str
    created: Literal[True, False]


@router.post("/integrations/opportunities", response_model=OpportunityLinkOut)
def link_opportunity(body: OpportunityLinkIn, request: Request, db: Session = Depends(get_db),
                     kb: KnowledgeBase = Depends(get_kb)) -> OpportunityLinkOut:
    """Create (or reuse) the deal linked to an external opportunity. Idempotent per
    (system, external_id); planning data already in the deal is never overwritten."""
    deal = db.query(Deal).filter_by(external_system=body.system, external_id=body.external_id).first()
    created = deal is None
    if deal is None:
        account = db.query(Account).filter_by(name=body.account.name).first()
        if account is None:
            account = Account(name=body.account.name, industry=body.account.industry,
                              region=body.account.region, is_synthetic=body.account.is_synthetic)
            db.add(account)
            db.flush()
        deal = Deal(account_id=account.id, name=body.opportunity.name, summary=body.opportunity.summary,
                    target_close=body.opportunity.target_close,
                    technical_context=[t for t in body.opportunity.technical_context if t in kb.context_tags],
                    external_system=body.system, external_id=body.external_id)
        db.add(deal)
    # Keep the link fresh; the opportunity name/stage in the system of record win.
    deal.name = body.opportunity.name
    if body.opportunity.stage:
        deal.stage = body.opportunity.stage
    deal.external_url = body.external_url
    deal.external_import_url = body.import_url_template
    db.commit()
    return OpportunityLinkOut(deal_id=deal.id, deal_url=deal_url(request.app.state.settings.public_url, deal.id),
                              created=created)


def import_link(deal: Deal, public_url: str) -> str | None:
    if not deal.external_import_url:
        return None
    return deal.external_import_url.replace("{deal_url}", quote(deal_url(public_url, deal.id), safe=""))

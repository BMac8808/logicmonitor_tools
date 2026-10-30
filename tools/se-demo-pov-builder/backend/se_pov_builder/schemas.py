"""Pydantic request/response schemas for the HTTP API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Influence = Literal["high", "medium", "low"]
Stance = Literal["supporter", "neutral", "skeptic", "unknown"]
Confidence = Literal["confirmed", "assumed"]
Priority = Literal["must", "should", "could"]
TaskStatus = Literal["todo", "in_progress", "blocked", "done", "cancelled"]
TaskKind = Literal["next_action", "workflow", "milestone"]
CriterionStatus = Literal["not_started", "in_progress", "met", "not_met", "waived"]
EvidenceType = Literal["observation", "screenshot", "document", "metric", "customer_confirmation"]
PovStatus = Literal["draft", "active", "completed", "closed"]

Name = Field(min_length=1, max_length=200)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Accounts & deals --------------------------------------------------------
class AccountIn(BaseModel):
    name: str = Name
    industry: str = ""
    employee_band: str = ""
    region: str = ""
    notes: str = ""
    is_synthetic: bool = True


class AccountPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    industry: str | None = None
    employee_band: str | None = None
    region: str | None = None
    notes: str | None = None


class AccountOut(ORM):
    id: int
    name: str
    industry: str
    employee_band: str
    region: str
    notes: str
    is_synthetic: bool
    created_at: datetime


class DealIn(BaseModel):
    account_id: int
    name: str = Name
    stage: str = "discovery"
    summary: str = ""
    business_drivers: str = ""
    technical_context: list[str] = []
    target_close: date | None = None


class DealPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    stage: str | None = None
    summary: str | None = None
    business_drivers: str | None = None
    technical_context: list[str] | None = None
    target_close: date | None = None


class DealOut(ORM):
    id: int
    account_id: int
    name: str
    stage: str
    summary: str
    business_drivers: str
    technical_context: list[str]
    target_close: date | None
    created_at: datetime
    updated_at: datetime


class DealListItem(DealOut):
    account_name: str


class DealDetail(DealOut):
    account: AccountOut
    metrics: dict[str, Any]


# --- Stakeholders ------------------------------------------------------------
class StakeholderIn(BaseModel):
    name: str = Name
    title: str = ""
    persona_id: str
    influence: Influence = "medium"
    stance: Stance = "unknown"
    notes: str = ""


class StakeholderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = None
    persona_id: str | None = None
    influence: Influence | None = None
    stance: Stance | None = None
    notes: str | None = None


class StakeholderOut(ORM):
    id: int
    deal_id: int
    name: str
    title: str
    persona_id: str
    influence: str
    stance: str
    notes: str


# --- Discovery ---------------------------------------------------------------
class AnswerIn(BaseModel):
    answer: str = Field(min_length=1)
    stakeholder_id: int | None = None
    evidence_source: str = ""
    confidence: Confidence = "confirmed"


class AnswerOut(ORM):
    id: int
    question_id: str
    stakeholder_id: int | None
    answer: str
    evidence_source: str
    confidence: str
    updated_at: datetime


class QuestionOut(BaseModel):
    id: str
    text: str
    category: str
    purpose: str
    listen_for: list[str]
    suggests_capabilities: list[str]
    qualification_key: str | None
    priority: int
    relevant_personas: list[str]
    answer: AnswerOut | None = None


class DiscoveryQuestionsOut(BaseModel):
    questions: list[QuestionOut]
    answered: int
    total: int
    unmatched_answers: list[AnswerOut]


class GapOut(BaseModel):
    code: str
    category: str
    severity: str
    message: str
    suggested_action: str


class GapsOut(BaseModel):
    gaps: list[GapOut]
    qualification: list[dict[str, Any]]


# --- Requirements & capabilities --------------------------------------------
class RequirementIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    category: Literal["business", "technical"] = "technical"
    priority: Priority = "should"
    pain_point: str = ""
    source_question_id: str | None = None
    capability_ids: list[str] | None = None  # None = auto-suggest
    status: Literal["draft", "confirmed"] = "draft"


class RequirementPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    category: Literal["business", "technical"] | None = None
    priority: Priority | None = None
    pain_point: str | None = None
    capability_ids: list[str] | None = None
    status: Literal["draft", "confirmed"] | None = None


class RequirementOut(ORM):
    id: int
    deal_id: int
    title: str
    description: str
    category: str
    priority: str
    pain_point: str
    source_question_id: str | None
    capability_ids: list[str]
    status: str


class CapabilityMatchIn(BaseModel):
    text: str
    source_question_id: str | None = None


class CapabilityMatchOut(BaseModel):
    capability_id: str
    name: str
    verified: bool
    matched_keywords: list[str]
    from_question: bool
    score: int


# --- Demo plans --------------------------------------------------------------
class DemoPlanIn(BaseModel):
    title: str | None = None
    duration_minutes: int = Field(default=60, ge=25, le=240)
    max_scenarios: int = Field(default=4, ge=1, le=10)
    notes: str = ""


class DemoPlanOut(ORM):
    id: int
    deal_id: int
    version: int
    title: str
    duration_minutes: int
    content: dict[str, Any]
    notes: str
    created_at: datetime


class DemoPlanListItem(ORM):
    id: int
    version: int
    title: str
    duration_minutes: int
    created_at: datetime


# --- POV ---------------------------------------------------------------------
class PovPlanIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    objectives: str = ""
    start_date: date
    duration_days: int | None = Field(default=None, ge=1, le=180)
    draft_criteria_from_requirements: bool = True


class PovPlanPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    objectives: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: PovStatus | None = None
    summary_notes: str | None = None


class EvidenceIn(BaseModel):
    description: str = Field(min_length=1)
    reference: str = ""
    evidence_type: EvidenceType = "observation"
    is_simulated: bool = False
    recorded_by: str = ""


class EvidenceOut(ORM):
    id: int
    criterion_id: int
    description: str
    reference: str
    evidence_type: str
    is_simulated: bool
    recorded_by: str
    recorded_at: datetime


class CriterionIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    pov_plan_id: int | None = None
    requirement_id: int | None = None
    measurable_outcome: str = ""
    target: str = ""
    validation_method: str = ""
    owner: str = ""
    status: CriterionStatus = "not_started"
    notes: str = ""


class CriterionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    pov_plan_id: int | None = None
    requirement_id: int | None = None
    measurable_outcome: str | None = None
    target: str | None = None
    validation_method: str | None = None
    owner: str | None = None
    status: CriterionStatus | None = None
    notes: str | None = None


class CriterionOut(ORM):
    id: int
    deal_id: int
    pov_plan_id: int | None
    requirement_id: int | None
    title: str
    measurable_outcome: str
    target: str
    validation_method: str
    owner: str
    status: str
    notes: str
    evidence: list[EvidenceOut]


class TaskOut(ORM):
    id: int
    deal_id: int
    kind: str
    workflow_run_id: int | None
    pov_plan_id: int | None
    stage_id: str | None
    template_key: str | None
    title: str
    description: str
    owner: str
    due_date: date | None
    status: str
    blocker: str
    depends_on: list[int]
    evidence_required: bool
    evidence_note: str
    completed_at: datetime | None
    waiting_on: list[int] = []


class PovPlanOut(ORM):
    id: int
    deal_id: int
    title: str
    objectives: str
    start_date: date | None
    end_date: date | None
    status: str
    template_version: int
    summary_notes: str
    created_at: datetime


class PovPlanDetail(PovPlanOut):
    criteria: list[CriterionOut]
    milestones: list[TaskOut]
    checklist: list[dict[str, Any]]
    summary: dict[str, Any]


# --- Workflows & tasks -------------------------------------------------------
class WorkflowStartIn(BaseModel):
    workflow_id: str


class WorkflowRunOut(BaseModel):
    id: int
    deal_id: int
    workflow_id: str
    workflow_name: str
    workflow_version: int
    started_at: datetime
    stages: list[dict[str, Any]]
    current_stage: str | None
    progress: float
    complete: bool
    tasks: list[TaskOut]


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    owner: str = ""
    due_date: date | None = None
    status: TaskStatus = "todo"
    blocker: str = ""
    depends_on: list[int] = []
    evidence_required: bool = False
    evidence_note: str = ""


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    owner: str | None = None
    due_date: date | None = None
    status: TaskStatus | None = None
    blocker: str | None = None
    depends_on: list[int] | None = None
    evidence_note: str | None = None


# --- Adapters & LLM ----------------------------------------------------------
class AuthorizationIn(BaseModel):
    approved_by: str
    reason: str
    scope: list[str]
    expires_at: datetime


class AdapterActionIn(BaseModel):
    params: dict[str, Any] = {}
    authorization: AuthorizationIn | None = None


class LLMDraftOut(BaseModel):
    draft: str
    label: str
    provider: str

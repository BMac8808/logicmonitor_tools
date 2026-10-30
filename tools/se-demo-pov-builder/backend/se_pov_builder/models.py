"""SQLAlchemy ORM models. See docs/ARCHITECTURE.md for the data model overview."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(120), default="")
    employee_band: Mapped[str] = mapped_column(String(60), default="")
    region: Mapped[str] = mapped_column(String(120), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)

    deals: Mapped[list[Deal]] = relationship(back_populates="account", cascade="all, delete-orphan")


class Deal(TimestampMixin, Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    stage: Mapped[str] = mapped_column(String(60), default="discovery")
    summary: Mapped[str] = mapped_column(Text, default="")
    business_drivers: Mapped[str] = mapped_column(Text, default="")
    technical_context: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_close: Mapped[date | None] = mapped_column(Date, nullable=True)

    account: Mapped[Account] = relationship(back_populates="deals")
    stakeholders: Mapped[list[Stakeholder]] = relationship(cascade="all, delete-orphan")
    answers: Mapped[list[DiscoveryAnswer]] = relationship(cascade="all, delete-orphan")
    requirements: Mapped[list[Requirement]] = relationship(cascade="all, delete-orphan")
    demo_plans: Mapped[list[DemoPlan]] = relationship(cascade="all, delete-orphan")
    pov_plans: Mapped[list[PovPlan]] = relationship(cascade="all, delete-orphan")
    criteria: Mapped[list[SuccessCriterion]] = relationship(cascade="all, delete-orphan")
    workflow_runs: Mapped[list[WorkflowRun]] = relationship(cascade="all, delete-orphan")
    tasks: Mapped[list[Task]] = relationship(cascade="all, delete-orphan")


class Stakeholder(TimestampMixin, Base):
    __tablename__ = "stakeholders"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200), default="")
    persona_id: Mapped[str] = mapped_column(String(80))
    influence: Mapped[str] = mapped_column(String(20), default="medium")
    stance: Mapped[str] = mapped_column(String(20), default="unknown")
    notes: Mapped[str] = mapped_column(Text, default="")


class DiscoveryAnswer(TimestampMixin, Base):
    __tablename__ = "discovery_answers"
    __table_args__ = (UniqueConstraint("deal_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    question_id: Mapped[str] = mapped_column(String(80))
    stakeholder_id: Mapped[int | None] = mapped_column(
        ForeignKey("stakeholders.id", ondelete="SET NULL"), nullable=True
    )
    answer: Mapped[str] = mapped_column(Text)
    evidence_source: Mapped[str] = mapped_column(String(300), default="")
    confidence: Mapped[str] = mapped_column(String(20), default="confirmed")


class Requirement(TimestampMixin, Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), default="technical")
    priority: Mapped[str] = mapped_column(String(10), default="should")
    pain_point: Mapped[str] = mapped_column(Text, default="")
    source_question_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    capability_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft")


class DemoPlan(TimestampMixin, Base):
    __tablename__ = "demo_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(300))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")


class PovPlan(TimestampMixin, Base):
    __tablename__ = "pov_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    objectives: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    template_version: Mapped[int] = mapped_column(Integer, default=1)
    summary_notes: Mapped[str] = mapped_column(Text, default="")


class SuccessCriterion(TimestampMixin, Base):
    __tablename__ = "success_criteria"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    pov_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("pov_plans.id", ondelete="SET NULL"), nullable=True
    )
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300))
    measurable_outcome: Mapped[str] = mapped_column(Text, default="")
    target: Mapped[str] = mapped_column(String(300), default="")
    validation_method: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="not_started")
    notes: Mapped[str] = mapped_column(Text, default="")

    evidence: Mapped[list[Evidence]] = relationship(
        cascade="all, delete-orphan", order_by="Evidence.id"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("success_criteria.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(String(500), default="")
    evidence_type: Mapped[str] = mapped_column(String(40), default="observation")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_by: Mapped[str] = mapped_column(String(200), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    workflow_id: Mapped[str] = mapped_column(String(80))
    workflow_version: Mapped[int] = mapped_column(Integer)
    # Snapshot of stage ids/names at creation so later YAML edits don't break old runs.
    stages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20), default="next_action")
    workflow_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=True
    )
    pov_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("pov_plans.id", ondelete="CASCADE"), nullable=True
    )
    stage_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    template_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(200), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    blocker: Mapped[str] = mapped_column(Text, default="")
    depends_on: Mapped[list[int]] = mapped_column(JSON, default=list)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_note: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

"""Shared FastAPI dependencies and helpers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TypeVar

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import Base
from ..knowledge import KnowledgeBase
from ..models import Deal, Task
from ..schemas import TaskOut
from ..services.workflow_engine import open_dependencies

M = TypeVar("M", bound=Base)


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_kb(request: Request) -> KnowledgeBase:
    return request.app.state.kb


def get_or_404(session: Session, model: type[M], obj_id: int) -> M:
    obj = session.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} {obj_id} not found")
    return obj


def deal_or_404(deal_id: int, db: Session = Depends(get_db)) -> Deal:
    return get_or_404(db, Deal, deal_id)


def tasks_by_id(db: Session, deal_id: int) -> dict[int, Task]:
    return {t.id: t for t in db.query(Task).filter_by(deal_id=deal_id).all()}


def task_out(task: Task, by_id: dict[int, Task]) -> TaskOut:
    out = TaskOut.model_validate(task)
    out.waiting_on = [t.id for t in open_dependencies(task, by_id)]
    return out

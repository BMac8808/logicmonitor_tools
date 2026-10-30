"""Workflow runs and tasks (workflow tasks, POV milestones and next actions)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..knowledge import KnowledgeBase
from ..models import Deal, Task, WorkflowRun
from ..schemas import TaskIn, TaskKind, TaskOut, TaskPatch, TaskStatus, WorkflowRunOut, WorkflowStartIn
from ..services.workflow_engine import (
    WorkflowRuleError,
    apply_status,
    run_progress,
    start_run,
    validate_dependencies,
)
from .deps import deal_or_404, get_db, get_kb, get_or_404, task_out, tasks_by_id

router = APIRouter()


def _run_out(run: WorkflowRun, by_id: dict[int, Task], kb: KnowledgeBase) -> WorkflowRunOut:
    tasks = sorted((t for t in by_id.values() if t.workflow_run_id == run.id), key=lambda t: t.id)
    wf = kb.workflows.get(run.workflow_id)
    return WorkflowRunOut(
        id=run.id, deal_id=run.deal_id, workflow_id=run.workflow_id,
        workflow_name=wf.name if wf else run.workflow_id, workflow_version=run.workflow_version,
        started_at=run.started_at, tasks=[task_out(t, by_id) for t in tasks], **run_progress(run, tasks),
    )


@router.get("/deals/{deal_id}/workflows", response_model=list[WorkflowRunOut])
def list_runs(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
              kb: KnowledgeBase = Depends(get_kb)) -> list[WorkflowRunOut]:
    by_id = tasks_by_id(db, deal.id)
    runs = db.query(WorkflowRun).filter_by(deal_id=deal.id).order_by(WorkflowRun.id).all()
    return [_run_out(r, by_id, kb) for r in runs]


@router.post("/deals/{deal_id}/workflows", response_model=WorkflowRunOut, status_code=201)
def start_workflow(body: WorkflowStartIn, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
                   kb: KnowledgeBase = Depends(get_kb)) -> WorkflowRunOut:
    try:
        run = start_run(db, kb, deal, body.workflow_id)
    except WorkflowRuleError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return _run_out(run, tasks_by_id(db, deal.id), kb)


@router.delete("/workflow-runs/{run_id}", status_code=204)
def delete_run(run_id: int, db: Session = Depends(get_db)) -> Response:
    run = get_or_404(db, WorkflowRun, run_id)
    db.query(Task).filter_by(workflow_run_id=run.id).delete()
    db.delete(run)
    db.commit()
    return Response(status_code=204)


@router.get("/deals/{deal_id}/tasks", response_model=list[TaskOut])
def list_tasks(deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db),
               status: TaskStatus | None = None, kind: TaskKind | None = None,
               open_only: bool = False) -> list[TaskOut]:
    by_id = tasks_by_id(db, deal.id)
    tasks = [
        t for t in by_id.values()
        if (status is None or t.status == status) and (kind is None or t.kind == kind)
        and (not open_only or t.status not in ("done", "cancelled"))
    ]
    tasks.sort(key=lambda t: (t.due_date is None, t.due_date, t.id))
    return [task_out(t, by_id) for t in tasks]


@router.post("/deals/{deal_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskIn, deal: Deal = Depends(deal_or_404), db: Session = Depends(get_db)) -> TaskOut:
    by_id = tasks_by_id(db, deal.id)
    data = body.model_dump(exclude={"status"})
    task = Task(deal_id=deal.id, kind="next_action", **data, status="todo")
    try:
        validate_dependencies(None, body.depends_on, by_id)
        apply_status(task, body.status, by_id)
    except WorkflowRuleError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.add(task)
    db.commit()
    by_id[task.id] = task
    return task_out(task, by_id)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: TaskPatch, db: Session = Depends(get_db)) -> TaskOut:
    task = get_or_404(db, Task, task_id)
    by_id = tasks_by_id(db, task.deal_id)
    data = body.model_dump(exclude_unset=True)
    try:
        if "depends_on" in data:
            validate_dependencies(task.id, data["depends_on"], by_id)
            task.depends_on = data.pop("depends_on")
        status = data.pop("status", None)
        if status is not None:
            apply_status(task, status, by_id, blocker=data.get("blocker"), evidence_note=data.get("evidence_note"))
        elif task.status == "blocked" and "blocker" in data and not (data["blocker"] or "").strip():
            raise WorkflowRuleError("A blocked task needs a blocker description; change its status first")
    except WorkflowRuleError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    for key, value in data.items():
        setattr(task, key, value)
    db.commit()
    return task_out(task, tasks_by_id(db, task.deal_id))


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> Response:
    task = get_or_404(db, Task, task_id)
    if task.kind != "next_action":
        raise HTTPException(409, "Workflow tasks and milestones are removed with their workflow run or POV plan; "
                                 "set the status to 'cancelled' instead")
    for other in db.query(Task).filter_by(deal_id=task.deal_id).all():
        if task.id in (other.depends_on or []):
            other.depends_on = [d for d in other.depends_on if d != task.id]
    db.delete(task)
    db.commit()
    return Response(status_code=204)

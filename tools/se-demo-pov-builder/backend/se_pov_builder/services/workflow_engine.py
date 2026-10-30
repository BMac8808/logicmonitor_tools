"""Workflow engine: instantiate workflow runs from YAML definitions and enforce task
rules (dependencies, blockers, required evidence). Also used for POV milestones and
ad-hoc next actions, which share the Task table."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from ..knowledge import KnowledgeBase
from ..models import Deal, Task, WorkflowRun, utcnow

TASK_STATUSES = ("todo", "in_progress", "blocked", "done", "cancelled")
CLOSED = {"done", "cancelled"}
OWNER_ROLE_LABELS = {
    "se": "Sales Engineer",
    "customer": "Customer",
    "joint": "Joint (SE + customer)",
    "account_executive": "Account Executive",
}


class WorkflowRuleError(ValueError):
    """Raised when a requested change breaks a workflow rule."""


def start_run(session: Session, kb: KnowledgeBase, deal: Deal, workflow_id: str) -> WorkflowRun:
    if workflow_id not in kb.workflows:
        raise WorkflowRuleError(f"Unknown workflow '{workflow_id}'")
    wf = kb.workflows[workflow_id]
    run = WorkflowRun(
        deal_id=deal.id,
        workflow_id=wf.id,
        workflow_version=wf.version,
        stages=[{"id": s.id, "name": s.name, "exit_criteria": s.exit_criteria} for s in wf.stages],
    )
    session.add(run)
    session.flush()
    by_key: dict[str, Task] = {}
    for stage, tpl in wf.task_templates():
        task = Task(
            deal_id=deal.id,
            kind="workflow",
            workflow_run_id=run.id,
            stage_id=stage.id,
            template_key=tpl.key,
            title=tpl.title,
            description=tpl.description,
            owner=OWNER_ROLE_LABELS.get(tpl.owner_role, tpl.owner_role),
            evidence_required=tpl.evidence_required,
            depends_on=[],
        )
        session.add(task)
        by_key[tpl.key] = task
    session.flush()
    for _, tpl in wf.task_templates():
        by_key[tpl.key].depends_on = [by_key[d].id for d in tpl.depends_on]
    session.flush()
    return run


def open_dependencies(task: Task, tasks_by_id: dict[int, Task]) -> list[Task]:
    return [
        tasks_by_id[d] for d in task.depends_on if d in tasks_by_id and tasks_by_id[d].status not in CLOSED
    ]


def validate_dependencies(task_id: int | None, depends_on: Iterable[int], deal_tasks: dict[int, Task]) -> None:
    """Dependencies must be tasks of the same deal and must not create a cycle."""
    deps = list(depends_on)
    for d in deps:
        if d not in deal_tasks:
            raise WorkflowRuleError(f"Dependency {d} is not a task on this deal")
        if task_id is not None and d == task_id:
            raise WorkflowRuleError("A task cannot depend on itself")
    if task_id is None:
        return
    # Walk dependencies of the proposed deps; reaching task_id means a cycle.
    stack, seen = list(deps), set()
    while stack:
        current = stack.pop()
        if current == task_id:
            raise WorkflowRuleError("Dependency would create a cycle")
        if current in seen or current not in deal_tasks:
            continue
        seen.add(current)
        stack.extend(deal_tasks[current].depends_on)


def apply_status(
    task: Task,
    new_status: str,
    tasks_by_id: dict[int, Task],
    *,
    blocker: str | None = None,
    evidence_note: str | None = None,
) -> None:
    """Validate and apply a status change. ``blocker``/``evidence_note`` are the values
    that will be stored after the update (None = unchanged)."""
    if new_status not in TASK_STATUSES:
        raise WorkflowRuleError(f"Status must be one of {', '.join(TASK_STATUSES)}")
    effective_blocker = task.blocker if blocker is None else blocker
    effective_evidence = task.evidence_note if evidence_note is None else evidence_note
    if new_status == "blocked" and not effective_blocker.strip():
        raise WorkflowRuleError("Describe the blocker before marking a task as blocked")
    if new_status == "done":
        waiting = open_dependencies(task, tasks_by_id)
        if waiting:
            names = ", ".join(f"'{t.title}'" for t in waiting)
            raise WorkflowRuleError(f"Cannot complete: waiting on {names}")
        if task.evidence_required and not effective_evidence.strip():
            raise WorkflowRuleError("This task requires an evidence note before it can be completed")
    if new_status == "done" and task.status != "done":
        task.completed_at = utcnow()
    elif new_status != "done":
        task.completed_at = None
    if new_status != "blocked" and blocker is None and task.status == "blocked":
        task.blocker = ""
    task.status = new_status


def run_progress(run: WorkflowRun, tasks: list[Task]) -> dict:
    stages = []
    current_stage = None
    for stage in run.stages:
        stage_tasks = [t for t in tasks if t.stage_id == stage["id"]]
        closed = sum(1 for t in stage_tasks if t.status in CLOSED)
        if stage_tasks and closed == len(stage_tasks):
            status = "complete"
        elif any(t.status != "todo" for t in stage_tasks):
            status = "in_progress"
        else:
            status = "not_started"
        if status != "complete" and current_stage is None:
            current_stage = stage["id"]
        stages.append({**stage, "status": status, "total": len(stage_tasks), "closed": closed,
                       "blocked": sum(1 for t in stage_tasks if t.status == "blocked")})
    total = len(tasks)
    closed_total = sum(1 for t in tasks if t.status in CLOSED)
    return {
        "stages": stages,
        "current_stage": current_stage,
        "progress": round(closed_total / total, 3) if total else 0.0,
        "complete": total > 0 and closed_total == total,
    }

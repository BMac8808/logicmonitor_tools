"""Versioned YAML content: personas, capabilities, discovery questions, demo scenarios,
workflows and the POV template.

Content is validated as a whole: every problem (bad field, unknown reference, duplicate
id, dependency cycle) is collected and raised together in a ``ContentError``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

Level = Literal["high", "medium", "low"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Objection(_Model):
    objection: str
    approach: str


class Persona(_Model):
    id: str
    name: str
    version: int = 1
    summary: str
    coverage: Literal["required", "recommended", "optional"] = "optional"
    typical_influence: Level = "medium"
    objectives: list[str] = []
    motivations: list[str] = []
    technical_concerns: list[str] = []
    typical_objections: list[Objection] = []
    discovery_signals: list[str] = []
    influence_notes: str = ""
    engagement_approach: list[str] = []
    demo_focus: list[str] = []
    question_categories: list[str] = []


class Capability(_Model):
    id: str
    name: str
    category: str
    description: str
    keywords: list[str] = []
    verified: bool = False
    reference: str = ""


class CapabilityCatalog(_Model):
    version: int
    disclaimer: str
    capabilities: list[Capability]


class ContextTag(_Model):
    id: str
    label: str


class QualificationItem(_Model):
    key: str
    label: str
    description: str = ""


class DiscoveryQuestion(_Model):
    id: str
    text: str
    category: Literal["business", "technical", "process", "qualification", "stakeholder"]
    personas: list[str] = ["all"]
    contexts: list[str] = ["any"]
    purpose: str = ""
    listen_for: list[str] = []
    suggests_capabilities: list[str] = []
    qualification_key: str | None = None
    priority: int = Field(default=2, ge=1, le=3)


class DiscoveryLibrary(_Model):
    version: int
    context_tags: list[ContextTag]
    qualification_checklist: list[QualificationItem]
    questions: list[DiscoveryQuestion]


class DemoScenario(_Model):
    id: str
    title: str
    summary: str
    duration_minutes: int = Field(gt=0)
    capabilities: list[str]
    pain_keywords: list[str] = []
    contexts: list[str] = ["any"]
    demonstrates: list[str] = []
    audience_talking_points: dict[str, list[str]] = {}
    prerequisites: list[str] = []
    data_requirements: list[str] = []
    prep_tasks: list[str] = []


class DemoScenarioLibrary(_Model):
    version: int
    scenarios: list[DemoScenario]


class WorkflowTaskTemplate(_Model):
    key: str
    title: str
    description: str = ""
    owner_role: str = "se"
    depends_on: list[str] = []
    evidence_required: bool = False


class WorkflowStage(_Model):
    id: str
    name: str
    description: str = ""
    tasks: list[WorkflowTaskTemplate]
    exit_criteria: list[str] = []


class WorkflowDefinition(_Model):
    id: str
    name: str
    version: int
    order: int = 100
    description: str = ""
    stages: list[WorkflowStage]

    def task_templates(self) -> list[tuple[WorkflowStage, WorkflowTaskTemplate]]:
        return [(stage, task) for stage in self.stages for task in stage.tasks]


class PovMilestoneTemplate(_Model):
    key: str
    title: str
    description: str = ""
    responsible: Literal["se", "customer", "joint"] = "joint"
    offset_days: int = Field(default=0, ge=0)
    depends_on: list[str] = []


class PovTemplate(_Model):
    version: int
    default_duration_days: int = Field(default=30, gt=0)
    milestones: list[PovMilestoneTemplate]


class ContentError(Exception):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Invalid content:\n- " + "\n- ".join(problems))


def _load_yaml(path: Path) -> object:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _find_cycle(edges: dict[str, list[str]]) -> list[str] | None:
    """Return one dependency cycle (as a list of keys) or None."""
    state: dict[str, int] = {}  # 1 = visiting, 2 = done
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for dep in edges.get(node, []):
            if state.get(dep) == 1:
                return stack[stack.index(dep) :] + [dep]
            if dep in edges and state.get(dep) is None:
                found = visit(dep)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in edges:
        if state.get(node) is None:
            found = visit(node)
            if found:
                return found
    return None


class KnowledgeBase:
    """All validated content, keyed by id."""

    def __init__(
        self,
        personas: dict[str, Persona],
        capabilities: CapabilityCatalog,
        discovery: DiscoveryLibrary,
        scenarios: DemoScenarioLibrary,
        workflows: dict[str, WorkflowDefinition],
        pov_template: PovTemplate,
        content_dir: Path,
    ):
        self.personas = personas
        self.capability_catalog = capabilities
        self.capabilities = {c.id: c for c in capabilities.capabilities}
        self.discovery = discovery
        self.questions = {q.id: q for q in discovery.questions}
        self.context_tags = {t.id: t for t in discovery.context_tags}
        self.scenario_library = scenarios
        self.scenarios = {s.id: s for s in scenarios.scenarios}
        self.workflows = workflows
        self.pov_template = pov_template
        self.content_dir = content_dir

    @classmethod
    def load(cls, content_dir: Path) -> KnowledgeBase:
        problems: list[str] = []

        def parse(model: type[BaseModel], path: Path):
            if not path.exists():
                problems.append(f"{path}: file not found")
                return None
            try:
                return model.model_validate(_load_yaml(path))
            except (ValidationError, yaml.YAMLError) as exc:
                problems.append(f"{path}: {exc}")
                return None

        personas: dict[str, Persona] = {}
        for path in sorted((content_dir / "personas").glob("*.yaml")):
            persona = parse(Persona, path)
            if persona is None:
                continue
            if persona.id in personas:
                problems.append(f"{path}: duplicate persona id '{persona.id}'")
            personas[persona.id] = persona
        if not personas:
            problems.append(f"{content_dir / 'personas'}: no persona files found")

        workflows: dict[str, WorkflowDefinition] = {}
        for path in sorted((content_dir / "workflows").glob("*.yaml")):
            wf = parse(WorkflowDefinition, path)
            if wf is None:
                continue
            if wf.id in workflows:
                problems.append(f"{path}: duplicate workflow id '{wf.id}'")
            workflows[wf.id] = wf

        knowledge = content_dir / "knowledge"
        capabilities = parse(CapabilityCatalog, knowledge / "capabilities.yaml")
        discovery = parse(DiscoveryLibrary, knowledge / "discovery_questions.yaml")
        scenarios = parse(DemoScenarioLibrary, knowledge / "demo_scenarios.yaml")
        pov_template = parse(PovTemplate, knowledge / "pov_template.yaml")

        if problems:
            raise ContentError(problems)

        kb = cls(
            personas=personas,
            capabilities=capabilities,
            discovery=discovery,
            scenarios=scenarios,
            workflows=dict(sorted(workflows.items(), key=lambda kv: (kv[1].order, kv[0]))),
            pov_template=pov_template,
            content_dir=content_dir,
        )
        kb._check_references()
        return kb

    def _check_references(self) -> None:
        problems: list[str] = []

        def dupes(kind: str, ids: list[str]) -> None:
            seen: set[str] = set()
            for i in ids:
                if i in seen:
                    problems.append(f"duplicate {kind} id '{i}'")
                seen.add(i)

        dupes("capability", [c.id for c in self.capability_catalog.capabilities])
        dupes("question", [q.id for q in self.discovery.questions])
        dupes("scenario", [s.id for s in self.scenario_library.scenarios])
        dupes("context tag", [t.id for t in self.discovery.context_tags])
        dupes("qualification", [q.key for q in self.discovery.qualification_checklist])

        qual_keys = {q.key for q in self.discovery.qualification_checklist}
        for q in self.discovery.questions:
            for p in q.personas:
                if p != "all" and p not in self.personas:
                    problems.append(f"question '{q.id}': unknown persona '{p}'")
            for c in q.contexts:
                if c != "any" and c not in self.context_tags:
                    problems.append(f"question '{q.id}': unknown context tag '{c}'")
            for cap in q.suggests_capabilities:
                if cap not in self.capabilities:
                    problems.append(f"question '{q.id}': unknown capability '{cap}'")
            if q.qualification_key and q.qualification_key not in qual_keys:
                problems.append(f"question '{q.id}': unknown qualification key '{q.qualification_key}'")

        for s in self.scenario_library.scenarios:
            for cap in s.capabilities:
                if cap not in self.capabilities:
                    problems.append(f"scenario '{s.id}': unknown capability '{cap}'")
            for c in s.contexts:
                if c != "any" and c not in self.context_tags:
                    problems.append(f"scenario '{s.id}': unknown context tag '{c}'")
            for p in s.audience_talking_points:
                if p != "default" and p not in self.personas:
                    problems.append(f"scenario '{s.id}': unknown persona '{p}' in talking points")

        for wf in self.workflows.values():
            keys = [t.key for _, t in wf.task_templates()]
            dupes(f"task key in workflow '{wf.id}'", keys)
            dupes(f"stage in workflow '{wf.id}'", [s.id for s in wf.stages])
            edges = {t.key: t.depends_on for _, t in wf.task_templates()}
            for key, deps in edges.items():
                for dep in deps:
                    if dep not in edges:
                        problems.append(f"workflow '{wf.id}': task '{key}' depends on unknown task '{dep}'")
            cycle = _find_cycle(edges)
            if cycle:
                problems.append(f"workflow '{wf.id}': dependency cycle {' -> '.join(cycle)}")

        ms_edges = {m.key: m.depends_on for m in self.pov_template.milestones}
        dupes("POV milestone", [m.key for m in self.pov_template.milestones])
        for key, deps in ms_edges.items():
            for dep in deps:
                if dep not in ms_edges:
                    problems.append(f"POV milestone '{key}' depends on unknown milestone '{dep}'")
        cycle = _find_cycle(ms_edges)
        if cycle:
            problems.append(f"POV template: dependency cycle {' -> '.join(cycle)}")

        if problems:
            raise ContentError(problems)

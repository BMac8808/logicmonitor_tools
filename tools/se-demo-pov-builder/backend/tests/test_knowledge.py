import shutil
from pathlib import Path

import pytest
import yaml

from se_pov_builder.config import TOOL_ROOT
from se_pov_builder.knowledge import ContentError, KnowledgeBase
from se_pov_builder.validate_content import main as validate_main

REQUIRED_PERSONAS = {"champion", "economic_buyer", "technical_buyer", "detractor", "influencer",
                     "practitioner", "executive_sponsor"}
REQUIRED_WORKFLOWS = {"discovery", "technical_qualification", "demo_preparation", "pov_planning",
                      "pov_execution", "success_validation", "technical_handoff"}


@pytest.fixture
def content_copy(tmp_path: Path) -> Path:
    for sub in ("personas", "knowledge", "workflows"):
        shutil.copytree(TOOL_ROOT / sub, tmp_path / sub)
    return tmp_path


def test_bundled_content_is_valid(kb):
    assert REQUIRED_PERSONAS <= set(kb.personas)
    assert REQUIRED_WORKFLOWS <= set(kb.workflows)
    assert kb.questions and kb.scenarios and kb.capabilities


def test_personas_define_engagement_fields(kb):
    for p in kb.personas.values():
        assert p.objectives and p.motivations and p.technical_concerns, p.id
        assert p.typical_objections and p.discovery_signals and p.engagement_approach, p.id


def test_bundled_capabilities_are_unverified(kb):
    # Community summaries must not claim verification without a reference.
    assert all(not c.verified or c.reference for c in kb.capabilities.values())


def test_new_persona_and_workflow_need_no_code_change(content_copy):
    (content_copy / "personas" / "procurement.yaml").write_text(yaml.safe_dump({
        "id": "procurement", "name": "Procurement Lead", "summary": "Runs the purchasing process.",
    }))
    (content_copy / "workflows" / "99_custom.yaml").write_text(yaml.safe_dump({
        "id": "custom", "name": "Custom", "version": 1, "order": 99,
        "stages": [{"id": "s1", "name": "Only stage", "tasks": [{"key": "a", "title": "Do A"}]}],
    }))
    kb = KnowledgeBase.load(content_copy)
    assert "procurement" in kb.personas
    assert list(kb.workflows)[-1] == "custom"


def test_broken_references_are_all_reported(content_copy):
    path = content_copy / "knowledge" / "discovery_questions.yaml"
    data = yaml.safe_load(path.read_text())
    data["questions"][0]["personas"] = ["no_such_persona"]
    data["questions"][1]["suggests_capabilities"] = ["no_such_capability"]
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ContentError) as err:
        KnowledgeBase.load(content_copy)
    text = "\n".join(err.value.problems)
    assert "no_such_persona" in text and "no_such_capability" in text


def test_workflow_cycle_detected(content_copy):
    (content_copy / "workflows" / "99_cycle.yaml").write_text(yaml.safe_dump({
        "id": "cyclic", "name": "Cyclic", "version": 1,
        "stages": [{"id": "s", "name": "S", "tasks": [
            {"key": "a", "title": "A", "depends_on": ["b"]},
            {"key": "b", "title": "B", "depends_on": ["a"]},
        ]}],
    }))
    with pytest.raises(ContentError, match="cycle"):
        KnowledgeBase.load(content_copy)


def test_unknown_field_rejected(content_copy):
    path = content_copy / "personas" / "champion.yaml"
    path.write_text(path.read_text() + "\nunexpected_field: true\n")
    with pytest.raises(ContentError, match="unexpected_field"):
        KnowledgeBase.load(content_copy)


def test_validate_cli(content_copy, capsys):
    assert validate_main([str(content_copy)]) == 0
    (content_copy / "personas" / "bad.yaml").write_text("id: [not, a, string]\n")
    assert validate_main([str(content_copy)]) == 1
    assert "INVALID" in capsys.readouterr().out


def test_ecosystem_references_are_validated(content_copy):
    path = content_copy / "knowledge" / "lm_ecosystem.yaml"
    data = yaml.safe_load(path.read_text())
    data["toolkit"][0]["milestones"] = ["no_such_milestone"]
    data["toolkit"][1]["project"] = "no_such_project"
    data["toolkit"][2]["requires"] = ["no_such_item"]
    data["references"][0]["capabilities"] = ["no_such_capability"]
    scripted = next(t for t in data["toolkit"] if t["import"] == "powershell")
    scripted["module_name"] = ""
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ContentError) as err:
        KnowledgeBase.load(content_copy)
    text = "\n".join(err.value.problems)
    for expected in ("no_such_milestone", "no_such_project", "no_such_item", "no_such_capability", "module_name"):
        assert expected in text


def test_ecosystem_projects_are_pinned(kb):
    assert all(len(p.commit) == 40 for p in kb.ecosystem.projects)
    assert all(p.license for p in kb.ecosystem.projects)
    url = kb.ecosystem.raw_url(kb.toolkit["nodata_metrics"])
    assert url.startswith("https://raw.githubusercontent.com/")
    assert kb.ecosystem.project("logicmonitor_dashboards").commit in url

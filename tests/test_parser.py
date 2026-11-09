"""M2 tests: Markdown/PlantUML parsing and requirement normalization (T01-T03)."""

from __future__ import annotations

from pathlib import Path

import pytest

from space_code_agent.core.document_parser import DocumentError, DocumentParser
from space_code_agent.core.requirements import RequirementNormalizer

FIXTURES = Path(__file__).parent / "fixtures" / "Task"
DOC = FIXTURES / "Architecture_Documentation.md"
VIEW = FIXTURES / "Architecture_View.md"


@pytest.fixture(scope="module")
def parser() -> DocumentParser:
    return DocumentParser()


@pytest.fixture(scope="module")
def architecture(parser):
    return parser.parse(DOC, "architecture")


@pytest.fixture(scope="module")
def view(parser):
    return parser.parse(VIEW, "view")


@pytest.fixture(scope="module")
def normalized(architecture, view):
    return RequirementNormalizer().normalize(architecture, view)


def test_architecture_basics(architecture):
    assert architecture.kind == "architecture"
    assert architecture.project_name == "Space Fractions"
    assert architecture.style == "Microservices"
    assert "web-based" in architecture.target
    assert architecture.sha256
    assert architecture.line_count >= 300
    assert len(architecture.sections) >= 20
    assert len(architecture.tables) == 4


def test_architecture_requirements(architecture):
    ids = {req.id for req in architecture.requirements}
    assert {"FR-1", "NFR-1", "ASR-1", "ASR-2"} <= ids
    fr1 = next(req for req in architecture.requirements if req.id == "FR-1")
    assert fr1.title == "Play game"
    assert fr1.components == ["GameComponent"]
    assert fr1.artifacts == ["openapi.yaml"]
    assert "play" in fr1.rationale.lower()
    asr2 = next(req for req in architecture.requirements if req.id == "ASR-2")
    assert asr2.confidence == "inferred"


def test_architecture_components_and_stack(architecture):
    names = {component.name for component in architecture.components}
    assert {"GameComponent", "QuestionComponent", "UserComponent"} <= names
    game = next(component for component in architecture.components if component.name == "GameComponent")
    assert game.technologies["Language/runtime"].startswith("Node.js")
    assert "PostgreSQL" in architecture.tech_stack["technologies"]
    assert len(architecture.assumptions) == 2


def test_architecture_warnings_are_specific(architecture):
    text = " ".join(architecture.warnings)
    assert "追溯矩阵" in text
    assert "测试矩阵为空" in text
    assert "ASR-2" in text
    assert "Redis" in text


def test_view_has_13_plantuml_diagrams(view):
    assert len(view.code_blocks) == 13
    assert len(view.diagrams) == 13
    ids = {diagram.id for diagram in view.diagrams}
    assert len(ids) == 13
    kinds = {diagram.kind for diagram in view.diagrams}
    assert {
        "use_case", "class", "object", "state", "activity", "sequence",
        "collaboration", "package", "component", "deployment", "container",
    } <= kinds


def test_view_semantics(view):
    by_id = {diagram.id: diagram for diagram in view.diagrams}
    use_case = by_id["UseCaseDiagram"]
    assert "Play Game" in use_case.usecases
    assert "End User" in use_case.actors or "EndUser" in use_case.actors
    assert "Admin" in use_case.actors
    sequence = by_id["SequenceDiagram1"]
    assert sequence.messages[0]["text"] == "play()"
    assert {"User", "Game", "Question"} <= set(sequence.elements)
    state = by_id["StateDiagram"]
    assert "Playing" in state.states
    assert any(rel["to"] == "[*]" or rel["from"] == "[*]" for rel in state.relations)
    activity = by_id["ActivityDiagram"]
    assert "play game" in activity.activities
    assert "calculate score" in activity.activities
    assert len(activity.elements) >= 3


def test_view_notation_warnings(view):
    by_id = {diagram.id: diagram for diagram in view.diagrams}
    assert any("participant" in warning for warning in by_id["ObjectDiagram"].warnings)
    assert any("->>" in warning for warning in by_id["CollaborationDiagram1"].warnings)


def test_normalization_derives_usecases(normalized):
    derived = normalized.derived_requirements()
    titles = {req.title for req in derived}
    assert {"View Score", "Update Questions", "View Help"} <= titles
    assert all(req.id.startswith("FR-DERIVED-") for req in derived)
    assert normalized.requirement("FR-DERIVED-2").components == ["QuestionComponent", "AdminComponent"]


def test_normalization_conflicts(normalized):
    messages = " ".join(conflict.message for conflict in normalized.conflicts)
    assert "11" in messages and "13" in messages
    assert "测试矩阵为空" in messages
    assert "Redis" in messages or "重型组件" in messages
    assert any(conflict.severity == "high" for conflict in normalized.conflicts)
    assert len(normalized.conflicts) >= 6


def test_normalization_assumptions(normalized):
    ids = {assumption.id for assumption in normalized.assumptions}
    assert {"A1", "A2", "ASM-01", "ASM-06"} <= ids
    text = " ".join(assumption.text for assumption in normalized.assumptions)
    assert "10 道" in text
    assert "重大偏离" in text


def test_normalization_components_and_stats(normalized):
    names = {component.name for component in normalized.components}
    assert {"GameComponent", "QuestionComponent", "UserComponent", "AdminComponent"} <= names
    stats = normalized.summary_counts()
    assert stats["requirements"] == 7
    assert stats["diagrams"] == 13
    assert stats["derived"] == 3
    assert normalized.coverage()["total"] == 7


def test_prompt_summary(normalized):
    summary = normalized.to_prompt_summary()
    assert "Space Fractions" in summary
    assert "FR-DERIVED-1" in summary
    assert "ObjectDiagram" in summary
    assert len(summary) < 14000


def test_bom_is_handled(tmp_path):
    path = tmp_path / "bom.md"
    path.write_bytes("\ufeff# Title\n\n## Section\nText".encode("utf-8"))
    parsed = DocumentParser().parse(path, "architecture")
    assert parsed.title == "Title"
    assert parsed.encoding == "utf-8-sig"


def test_empty_file_rejected(tmp_path):
    path = tmp_path / "empty.md"
    path.write_bytes(b"")
    with pytest.raises(DocumentError) as info:
        DocumentParser().parse(path)
    assert info.value.code == "empty"


def test_non_utf8_rejected(tmp_path):
    path = tmp_path / "gbk.md"
    path.write_bytes("中文需求".encode("gbk"))
    with pytest.raises(DocumentError) as info:
        DocumentParser().parse(path)
    assert info.value.code == "encoding"


def test_missing_file_rejected(tmp_path):
    with pytest.raises(DocumentError) as info:
        DocumentParser().parse(tmp_path / "nope.md")
    assert info.value.code == "not_found"


def test_size_limit_rejected(tmp_path):
    path = tmp_path / "big.md"
    path.write_text("# Title\n" + "x" * 100, encoding="utf-8")
    with pytest.raises(DocumentError) as info:
        DocumentParser(max_bytes=50).parse(path)
    assert info.value.code == "too_large"

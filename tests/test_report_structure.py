from pathlib import Path


def test_experiment_report_structure_is_documented() -> None:
    project_context = Path("PROJECT_CONTEXT.md").read_text(encoding="utf-8")
    history = Path("EXPERIMENT_HISTORY.md").read_text(encoding="utf-8")
    reports_readme = Path("reports/README.md")
    report_template = Path("reports/EXPERIMENT_REPORT_TEMPLATE.md")

    assert reports_readme.is_file()
    assert report_template.is_file()
    assert "reports/exp012_<slug>/README.md" in project_context
    assert "reports/README.md" in history
    assert "EXPERIMENT_HISTORY_1.md" in reports_readme.read_text(encoding="utf-8")


def test_report_template_contains_human_and_machine_links() -> None:
    template = Path("reports/EXPERIMENT_REPORT_TEMPLATE.md").read_text(
        encoding="utf-8"
    )

    for heading in (
        "## 한눈에 보기",
        "## 핵심 개념과 피처",
        "## 실제 결과",
        "## 해석과 한계",
        "## 재현과 관련 파일",
    ):
        assert heading in template


def test_long_term_roadmap_is_linked_without_changing_history_role() -> None:
    project_context = Path("PROJECT_CONTEXT.md").read_text(encoding="utf-8")
    reports_readme = Path("reports/README.md").read_text(encoding="utf-8")
    roadmap_path = Path("reports/plans/residue_position_hotspot_roadmap.md")

    assert roadmap_path.is_file()
    assert roadmap_path.as_posix() in project_context
    assert "plans/residue_position_hotspot_roadmap.md" in reports_readme

    roadmap = roadmap_path.read_text(encoding="utf-8")
    assert "실제 실행 결과와 점수의 단일 원본" in roadmap
    assert "| A | EXP-067+069 고정 blend |" in roadmap
    assert "EXP-075" in roadmap
    assert "## 결정 변경 이력" in roadmap


def test_position_semantics_audit_is_linked_and_does_not_change_history() -> None:
    project_context = Path("PROJECT_CONTEXT.md").read_text(encoding="utf-8")
    reports_readme = Path("reports/README.md").read_text(encoding="utf-8")
    audit = Path("reports/analysis/residue_position_semantics_qc.md")
    audit_json = Path("reports/analysis/residue_position_semantics_qc.json")

    assert audit.is_file()
    assert audit_json.is_file()
    assert "semantic equivalence" in project_context
    assert "analysis/residue_position_semantics_qc.md" in reports_readme
    assert "새로운 모델 실험이나 점수를 만들지 않습니다" in audit.read_text(
        encoding="utf-8"
    )

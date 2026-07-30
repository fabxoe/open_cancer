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

from pathlib import Path

import yaml


def test_task_issue_form_uses_assignee_metadata_and_optional_defaults() -> None:
    form_path = Path(".github/ISSUE_TEMPLATE/task.yml")
    form = yaml.safe_load(form_path.read_text(encoding="utf-8"))
    fields = {
        item.get("id"): item
        for item in form["body"]
        if item["type"] != "markdown"
    }

    assert "owner" not in fields
    assert fields["purpose"]["validations"]["required"] is True

    for field_id in ("scope", "acceptance"):
        field = fields[field_id]
        assert field["validations"]["required"] is False
        assert field["attributes"]["value"].strip()


def test_artifact_request_form_requires_safety_acknowledgements() -> None:
    form_path = Path(".github/ISSUE_TEMPLATE/artifact_request.yml")
    form = yaml.safe_load(form_path.read_text(encoding="utf-8"))
    fields = {
        item.get("id"): item
        for item in form["body"]
        if item["type"] != "markdown"
    }

    assert fields["experiment_id"]["validations"]["required"] is True
    assert fields["purpose"]["validations"]["required"] is False
    assert len(fields["artifact_kinds"]["attributes"]["options"]) == 5
    assert all(
        option["required"] is True
        for option in fields["safety"]["attributes"]["options"]
    )

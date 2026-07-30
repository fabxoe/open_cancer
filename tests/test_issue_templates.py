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

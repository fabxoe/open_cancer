# EXP-484 재현 절차

`uv sync --frozen` 후 부모 OOF·test 확률을 원래 경로에 배치하고 다음을 실행합니다.

```bash
uv run python scripts/run_exp484_exp374_exp459_blend.py
uv run python scripts/validate_experiment.py
```

# EXP-137 재현 절차

```bash
uv sync --frozen
uv run python scripts/run_exp137_cross_fitted_stacking.py
uv run python scripts/validate_experiment.py
```

두 부모 OOF 확률을 52차원으로 연결하고 outer canonical 5-fold에서 meta learner를 cross-fit합니다.

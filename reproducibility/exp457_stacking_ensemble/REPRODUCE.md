# EXP-457 재현 절차

```bash
uv sync --frozen
uv run python scripts/run_exp457_stacking_ensemble.py
uv run python scripts/check_exp450_test_like_subset.py  # adapt paths for EXP-457
uv run python scripts/validate_experiment.py
```

두 부모(EXP-374, EXP-449) OOF 확률을 52차원으로 연결하고 outer canonical 5-fold에서 meta learner를 cross-fit합니다.

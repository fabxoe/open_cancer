# EXP-634 재현 절차

```bash
uv sync --frozen
uv run python scripts/run_exp634_cross_fitted_stacking_exp527_exp596.py
uv run python scripts/validate_experiment.py
```

두 base(EXP-527, EXP-596) OOF 확률을 52차원으로 연결하고 outer canonical 5-fold에서 L2 Multinomial Logistic Regression meta learner를 cross-fit합니다.

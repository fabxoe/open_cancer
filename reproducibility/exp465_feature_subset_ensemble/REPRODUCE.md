# EXP-465 재현 절차

```bash
uv sync --frozen
uv run python scripts/run_exp465_feature_subset_ensemble.py
uv run python scripts/check_exp465_test_like_subset.py
uv run python scripts/validate_experiment.py
```

hotspot-only(Model A)와 sample-aggregate-burden-only(Model B) 두 XGBoost를 EXP-374의 feature build를 재사용해 column mask로 분리 학습하고, 0.7/0.3이 아닌 0.5/0.5로 블렌드합니다.

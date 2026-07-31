# EXP-030 재현 절차

```bash
uv sync --frozen
uv run python scripts/run_exp030_sparse_variant_xgb.py --config configs/exp030_sparse_variant_xgb.yaml
uv run python scripts/validate_experiment.py
```

원본 CSV는 Git에 포함하지 않고 `data/raw/`에 별도로 배치합니다.

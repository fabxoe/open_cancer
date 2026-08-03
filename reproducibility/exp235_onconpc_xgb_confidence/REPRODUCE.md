# EXP-235 재현 절차

```bash
uv sync --frozen
uv run python scripts/run_exp235_onconpc_xgb_confidence.py --config configs/exp235_onconpc_xgb_confidence.yaml
uv run python scripts/validate_experiment.py
```

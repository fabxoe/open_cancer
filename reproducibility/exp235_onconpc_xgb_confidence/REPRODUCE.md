# EXP-235 재현 절차

원 산출물은 [`exp-235-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-235-repro-v1)에
보관되어 있습니다. bundle SHA-256은
`673d4b49c0adc8c527b6e1ae68ccbb458945cfb5dcf19176a6ba24c43afa4de0`입니다.

```bash
uv run python scripts/fetch_experiment_artifacts.py --experiment EXP-235
```

독립 재학습은 다음 명령으로 수행합니다. 이 Release 복구 과정에서는 재학습으로
기존 결과를 덮어쓰지 않았습니다.

```bash
uv sync --frozen
uv run python scripts/run_exp235_onconpc_xgb_confidence.py --config configs/exp235_onconpc_xgb_confidence.yaml
uv run python scripts/validate_experiment.py
```

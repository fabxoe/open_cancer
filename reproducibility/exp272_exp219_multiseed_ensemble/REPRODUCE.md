# EXP-272 재현 절차

EXP-219과 같은 환경에서 원본 CSV를 배치하고 다음을 실행합니다. 다섯 seed를 모두 재학습하므로 seed를 선택하거나 생략하지 않습니다.

```bash
uv sync --frozen
uv run python scripts/run_exp272_exp219_multiseed_ensemble.py
uv run python scripts/validate_experiment.py
```

# EXP-370 재현 절차

원본 CSV를 `data/raw/`에 배치하고 다음 명령을 실행합니다.

```bash
uv sync --frozen
uv run python scripts/run_exp370_exp223_stop_notation_normalization.py --config configs/exp370_exp223_stop_notation_normalization.yaml
uv run python scripts/validate_experiment.py
```

실험 실행 마지막 단계에서 저장 checkpoint 추론과 제출 SHA-256 일치 검증이 자동 수행됩니다.

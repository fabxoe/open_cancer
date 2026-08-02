# EXP-223 재현 절차

원본 CSV를 `data/raw/`에 배치하고 다음 명령을 실행합니다.

```bash
uv sync --frozen
uv run python scripts/run_exp223_pathway_macro_f1_checkpoint.py
uv run python scripts/validate_experiment.py
```

실험 실행 마지막 단계에서 저장 checkpoint 추론과 제출 SHA-256 일치 검증이 자동 수행됩니다.

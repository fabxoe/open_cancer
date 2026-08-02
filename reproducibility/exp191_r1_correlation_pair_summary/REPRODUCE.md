# EXP-191 재현 절차

원본 CSV 세 파일을 로컬 `data/raw/`에 둔 clean checkout에서 실행한다.

```bash
uv sync --frozen
git switch issue-191-r1-correlation-pair-summary
uv run python scripts/run_exp191_r1_correlation_pair_summary.py
```

마지막으로 저장소 기록을 검증한다.

```bash
uv run python scripts/validate_experiment.py
```

이 기록은 `MANIFEST_COMPLETE`다. 저장 checkpoint와 pair 명세로 독립 inference
비교를 완료하기 전에는 `INFERENCE_VERIFIED`로 승격하지 않는다.

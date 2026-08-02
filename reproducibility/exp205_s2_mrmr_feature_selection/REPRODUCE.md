# EXP-205 재현 절차

원본 CSV 세 파일을 로컬 `data/raw/`에 둔 clean checkout에서 실행한다.

```bash
uv sync --frozen
git switch issue-205-s2-mrmr-feature-selection
uv run python scripts/run_exp205_s2_mrmr_feature_selection.py
```

checkpoint와 fold별 selector mask가 이미 있는 경우에는 다시 학습하지 않고
추론 산출물을 재생성할 수 있다.

```bash
uv run python scripts/run_exp188_c1_phi_jaccard_pruning.py \
  --config configs/exp205_s2_mrmr_feature_selection.yaml \
  --replay-checkpoints
```

마지막으로 저장소 기록을 검증한다.

```bash
uv run python scripts/validate_experiment.py
```

이 기록은 `MANIFEST_COMPLETE`다. 독립 checkpoint inference 비교를 완료하기 전에는
`INFERENCE_VERIFIED`로 승격하지 않는다.

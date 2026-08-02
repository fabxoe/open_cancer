# EXP-190 재현 절차

원본 CSV 세 파일을 로컬 `data/raw/`에 둔 clean checkout에서 실행한다.

```bash
uv sync --frozen
git switch issue-190-c3-broad-correlation-pruning
uv run python scripts/run_exp190_c3_phi_jaccard_pruning.py
```

학습 뒤 checkpoint와 fold별 선택 mask로 산출물을 다시 쓸 때는 다음 명령을 쓴다.

```bash
uv run python scripts/run_exp188_c1_phi_jaccard_pruning.py \
  --config configs/exp190_c3_phi_jaccard_pruning.yaml \
  --replay-checkpoints
```

마지막으로 저장소 기록을 검증한다.

```bash
uv run python scripts/validate_experiment.py
```

재현 상태는 `MANIFEST_COMPLETE`다. checkpoint inference를 원본 확률·제출 파일과
독립적으로 byte-level 비교하기 전에는 `INFERENCE_VERIFIED`로 승격하지 않는다.

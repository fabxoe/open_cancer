# EXP-188 재현 안내

## 원 학습

원 실행 소스 commit `1ff0663af2f682229d715136119e8e1db6bace62`에서 다음 명령으로
canonical 5-fold를 다시 학습한다.

```bash
uv sync --frozen
uv run python scripts/run_exp188_c1_phi_jaccard_pruning.py
```

입력 원본 CSV와 checkpoint는 Git에 포함되지 않는다. 입력·split 해시는
`data_manifest.json`을, fold별 선택 mask와 checkpoint 해시는
`artifact_manifest.json`을 기준으로 확인한다.

## checkpoint 추론 검증

현재 runner는 저장된 checkpoint와 fold별 mask가 있을 때 재학습 없이 OOF/test
확률과 submission을 다시 만든다.

```bash
uv run python scripts/run_exp188_c1_phi_jaccard_pruning.py --replay-checkpoints
```

기대 OOF Macro F1은 `0.41797371692777424`다. 이 문서 작성 시점의 재현 상태는
`INFERENCE_VERIFIED`다. 저장된 fold별 mask와 checkpoint에서 재생성한 OOF·test
확률 및 제출 CSV가 원본과 완전히 일치했다.

제출 파일의 기대 SHA-256은 다음과 같다.

```text
a36bffa5e4d055f99d5fc8584c795a08c9f1b608cc941716d61b5b94428a1d0a
```

상세 수치 비교는 `comparison.json`을 확인한다. 재학습 검증은 별도다.

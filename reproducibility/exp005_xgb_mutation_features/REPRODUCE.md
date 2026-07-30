# EXP-005 추론 재현

이 절차는 재학습이 아니라 저장된 fold 체크포인트 5개로 기존 제출 파일을
동일하게 재생성하는 검증이다.

```bash
uv sync --frozen
uv run python scripts/verify_exp005_inference.py
uv run python scripts/validate_submission.py submissions/exp005_xgb_mutation_features.csv
uv run python scripts/validate_experiment.py
```

검증 스크립트는 원본 데이터, 공용 split, 가공 피처의 SHA-256을 resolved config와
비교한 뒤 체크포인트 추론을 수행한다. 재생성한 임시 제출 파일은 기존 제출 파일과
byte-level SHA-256이 같아야 통과한다. 체크포인트와 대형 예측 파일은 Git에서
제외되며 현재 로컬에만 있다. GitHub Release 보관은 아직 완료되지 않았다.

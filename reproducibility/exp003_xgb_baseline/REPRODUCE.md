# EXP-003 checkpoint 추론 재현

이 검증은 모델을 다시 학습하지 않고 저장된 fold checkpoint 5개로 test 추론만
다시 수행한다.

## 기준

- 학습 소스 commit: `7306182669c3676e7b17024d3cf1f821131d909b`
- 검증 스크립트 commit: `1934c6b69e7aaec5f731f1dd92a1ee4b14ccebb7`
- 기대 제출 SHA-256: `6e8b64726c86b5a6d52ee58f7f042b74b302852aa8a59c9bfe13332bfee424a5`

## 실행

```bash
uv sync --frozen

# artifact_manifest.json에 적힌 SHA-256과 일치하는 checkpoint 5개를
# models/exp003_xgb_baseline/에 배치한다.
uv run python scripts/verify_xgb_baseline_inference.py
```

성공하면 `reproduced_submission.csv`의 SHA-256이 원본
`submissions/exp003_xgb_baseline.csv`와 byte 단위로 같고,
`comparison.json`의 `passed`가 `true`가 된다.

현재 checkpoint의 `storage_uri`가 `null`이면 이 로컬 검증에는 사용되었지만 아직
GitHub Release에 업로드되지 않았다는 뜻이다. 실제 리더보드 제출 모델로 확정할 때
Release asset을 만들고 `artifact_manifest.json`에 URL을 기록한다.

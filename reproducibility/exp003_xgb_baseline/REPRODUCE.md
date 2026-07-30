# EXP-003 checkpoint 추론 재현

이 검증은 모델을 다시 학습하지 않고 저장된 fold checkpoint 5개로 test 추론만
다시 수행한다.

## 기준

- 학습 소스 commit: `e58c5f0a02dff92030d4a2363fdf7622eccb5686`
- 검증 스크립트 commit: `620f92ac6cc33f1409374fe46930445c0638d655`
- 기대 제출 SHA-256: `6e8b64726c86b5a6d52ee58f7f042b74b302852aa8a59c9bfe13332bfee424a5`

## 실행

```bash
uv sync --frozen

# 주최측 공식 경로로 받은 CSV 3개를 data/raw/에 배치한다.
mkdir -p models/exp003_xgb_baseline

curl -fL -o models/exp003_xgb_baseline/fold_00.json \
  https://github.com/fabxoe/open_cancer/releases/download/exp-003-repro-v1/exp003_xgb_baseline_fold_00.json
curl -fL -o models/exp003_xgb_baseline/fold_01.json \
  https://github.com/fabxoe/open_cancer/releases/download/exp-003-repro-v1/exp003_xgb_baseline_fold_01.json
curl -fL -o models/exp003_xgb_baseline/fold_02.json \
  https://github.com/fabxoe/open_cancer/releases/download/exp-003-repro-v1/exp003_xgb_baseline_fold_02.json
curl -fL -o models/exp003_xgb_baseline/fold_03.json \
  https://github.com/fabxoe/open_cancer/releases/download/exp-003-repro-v1/exp003_xgb_baseline_fold_03.json
curl -fL -o models/exp003_xgb_baseline/fold_04.json \
  https://github.com/fabxoe/open_cancer/releases/download/exp-003-repro-v1/exp003_xgb_baseline_fold_04.json

shasum -a 256 -c reproducibility/exp003_xgb_baseline/checksums.sha256
uv run python scripts/verify_xgb_baseline_inference.py
```

성공하면 `reproduced_submission.csv`의 SHA-256이 원본
`submissions/exp003_xgb_baseline.csv`와 byte 단위로 같고,
`comparison.json`의 `passed`가 `true`가 된다.

checkpoint 5개는
[`exp-003-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-003-repro-v1)
Release에 보관되어 있다. 각 파일의 크기, SHA-256과 다운로드 URL은
`artifact_manifest.json`을 따른다.

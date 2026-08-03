# EXP-179 checkpoint inference 재현

이 문서는 원 학습을 다시 실행하는 절차가 아니라, 보관된 EXP-179 checkpoint에서
제출 파일과 OOF/test 확률을 동일하게 재생성하는 절차다.

## 전제

- 원 실행 소스 commit: `704731a20520339e21f4c84eae93708d2e1dfd3e`
- 입력 파일: `data/raw/train.csv`, `data/raw/test.csv`,
  `data/raw/sample_submission.csv`
- split: `data/splits/stratified_5fold_seed42.csv`
- checkpoint: `models/exp179_xgb_feature_spec_v1_smote/fold_00.json`부터
  `fold_04.json`

원본 데이터와 checkpoint는 대회 정책 및 용량 때문에 Git에 포함하지 않는다. 각
파일의 해시는 `data_manifest.json`, `artifact_manifest.json`에서 확인한다.

## 실행

```bash
uv sync --frozen
uv run python scripts/run_exp179_xgb_feature_spec_v1_smote.py --replay-checkpoints
```

## 기대 결과

- `oof/exp179_xgb_feature_spec_v1_smote.csv`
- `preds/exp179_xgb_feature_spec_v1_smote_test_proba.csv`
- `submissions/exp179_xgb_feature_spec_v1_smote.csv`
- `reproducibility/exp179_xgb_feature_spec_v1_smote/comparison.json`

비교 파일의 `passed`가 `true`이고, OOF Macro F1이 `0.4080771374503408`이며,
submission SHA-256이 artifact manifest의 값과 같아야 한다.

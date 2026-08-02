# 최종 후보 제출·재현 체크리스트

이 문서는 팀원 확인 전까지 가능한 최종 후보 준비를 모아 둔 운영 문서입니다.
리더보드에 이미 제출한 파일을 다시 제출하지 않으며, 실제 점수의 원본은
`EXPERIMENT_HISTORY.md`입니다.

## 현재 후보

| 항목 | EXP-125 LightGBM v1 |
|---|---|
| 실험·Issue | EXP-125 / #125 |
| Public 제출 | 이미 제출 완료 |
| Public 점수 | 0.3075810937 |
| 제출 파일 | `submissions/exp125_lightgbm_v1.csv` |
| 제출 SHA-256 | `e76cce6d911616930570bcf0c5c1adc8adb045fbd18e3226d5378bda026d5940` |
| OOF Macro F1 | 0.4189078364 |
| 재현 상태 | `INFERENCE_VERIFIED`; 사람 팀원 확인 전 `TRAINING_VERIFIED` 대기 |
| Release | [`exp-125-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-125-repro-v1) |

## 보존 산출물

- OOF 확률: `oof/exp125_lightgbm_v1.csv`
- Test 확률: `preds/exp125_lightgbm_v1_test_proba.csv`
- Checkpoint: `models/exp125_lightgbm_v1/`
- Resolved config·환경·데이터 manifest: `reproducibility/exp125_lightgbm_v1/`
- 독립 실행 결과: `reports/analysis/g7_training_verification_issue162.*`

## 사람 팀원 확인 후 할 일

1. Issue #162에 fresh clone 재현 결과 확인 댓글 작성
2. `EXPERIMENT_HISTORY.md`의 EXP-125 재현 상태를 `TRAINING_VERIFIED`로 승격
3. 최종 후보 확정 문서와 로드맵 상태 갱신

그 전까지는 추가 리더보드 제출, 가중치 조정, EXP-131 재학습 확장을 하지 않습니다.

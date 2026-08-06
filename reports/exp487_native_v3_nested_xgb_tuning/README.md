# EXP-487 — Parser native-v3 nested XGBoost tuning

## 결론

EXP-479의 parser native-v3 의미 표현을 그대로 유지하고, 각 outer-train 내부의
3-fold CV로 XGBoost 하이퍼파라미터만 선택했다. OOF Macro F1은
`0.4228690293`으로 EXP-479보다 `+0.0141124270` 회복했지만 EXP-374보다
`-0.0039218975` 낮았다.

따라서 native-v3 표현 자체가 무효였다는 결론은 내리지 않는다. 이 결과는
튜닝된 native-v3 기준선과 향후 오류 다양성 비교 자산으로 보존하되, 현재 대표
리더보드 제출 후보로는 채택하지 않는다.

## 실험 계약

- Issue: [#487](https://github.com/fabxoe/open_cancer/issues/487)
- 부모: EXP-479
- canonical split: `data/splits/stratified_5fold_seed42.csv`
- parser representation: `native_v3_semantic_range`
- 고정 피처: mutation presence, parser native-v3 semantic range consequence
  token count, gene consequence presence, sample token count
- 모델: XGBoost `multi:softprob`
- class imbalance: balanced sample weight
- checkpoint: outer validation Macro F1-best
- 실행 환경: RunPod Linux, CUDA XGBoost
- 실행 소스: `ea5278c0b9342e77d6552c2a3b4039ff550ff81a`

## 누출 방지와 튜닝 범위

각 outer fold의 학습 부분만으로 3-fold inner CV를 만들고 TPE 30 trials를
수행했다. trial 목적함수는 inner OOF Macro F1이며 sampler seed는
`42 + outer_fold`이다. outer validation, test, Public LB는 trial·파라미터·피처
선택에 사용하지 않았다.

탐색 대상은 `max_depth`, `min_child_weight`, `subsample`,
`colsample_bytree`, `reg_alpha`, `reg_lambda`, `learning_rate`, `gamma`였다.
fold별 전체 trial과 선택값은 `optuna_outer_00.json`부터
`optuna_outer_04.json`에 보존했다.

## 결과

| 지표 | 값 |
|---|---:|
| OOF Macro F1 | 0.4228690293 |
| fold 평균 | 0.4221127714 |
| fold 표준편차 | 0.0097895767 |
| Accuracy | 0.4184808902 |
| Log Loss | 1.8564265966 |
| 실행 시간 | 23,862.02초 (약 6시간 38분) |

| Fold | Macro F1 | 선택 iteration | inner best trial | inner Macro F1 |
|---:|---:|---:|---:|---:|
| 0 | 0.4199910583 | 448 | 22 | 0.4102802244 |
| 1 | 0.4384034520 | 499 | 18 | 0.4007319988 |
| 2 | 0.4200012784 | 296 | 24 | 0.4000632290 |
| 3 | 0.4079556465 | 233 | 21 | 0.4098383026 |
| 4 | 0.4242124218 | 275 | 28 | 0.3930264139 |

## 비교

| 기준 | OOF Macro F1 | EXP-487 차이 |
|---|---:|---:|
| EXP-479 비튜닝 native-v3 | 0.4087566023 | +0.0141124270 |
| EXP-374 stop+isoform residue mask | 0.4267909268 | -0.0039218975 |
| EXP-512 parser-v4 global counts | 0.4258183004 | -0.0029492711 |

학습 metric인 mlogloss-best checkpoint를 사용했을 때 OOF Macro F1은
`0.4161409876`이었다. validation Macro-F1-best checkpoint는 이를
`+0.0067280417` 개선했다. Log Loss는 1.8471506834에서 1.8564265966으로
악화했으므로, 이 차이는 대회 지표에 맞춘 checkpoint 선택의 trade-off로 본다.

## 재현성과 산출물

- 재현 상태: `INFERENCE_VERIFIED`
- submission: `submissions/exp487_native_v3_nested_xgb_tuning.csv`
- submission SHA-256:
  `446daa39ae8d0cf8737960d28f47072493944ceab7258a4b66bb7231ce8c3cc4`
- checkpoint 재추론 label 일치율: 100%
- test probability 최대 절대 차이: `1.43e-7`
- metrics: `reports/exp487_native_v3_nested_xgb_tuning/metrics.json`
- resolved config:
  `reproducibility/exp487_native_v3_nested_xgb_tuning/config.resolved.yaml`
- comparison:
  `reproducibility/exp487_native_v3_nested_xgb_tuning/comparison.json`

Public LB에는 제출하지 않았다. 따라서 리더보드 제출 점수나 순위는 기록하지
않는다.

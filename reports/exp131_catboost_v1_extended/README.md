# EXP-131 CatBoost v1 extended training

## 결론

EXP-127과 동일한 Feature Spec v1, canonical 5-fold와 balanced sample weight를
유지하고 CatBoost 학습 설정만 확장했습니다. `iterations=2000`,
`learning_rate=0.03`, `l2_leaf_reg=5.0`, `early_stopping_rounds=100`으로
실행한 OOF Macro F1은 **0.4222392962**였습니다.

EXP-127보다 OOF Macro F1은 `+0.0027820668` 개선됐지만, EXP-094 대비 fold
표준편차가 `+0.0061276842`, Log Loss가 `+0.0265740811` 악화됐습니다.
따라서 단독 성능 후보로는 채택하지 않고, 추가 CatBoost iteration 확장은
중단합니다. EXP-127과의 라벨 불일치율은 `0.0596677955`, 오류 상관은
`0.9502667641`로 새 diversity 자산으로도 보존하지 않습니다.

## 무엇을 고정·변경했나

- 고정: EXP-127의 Feature Spec v1, 35,119개 피처, canonical stratified 5-fold,
  26개 클래스 순서, seed 42, balanced sample weight
- 변경: iterations 1,000 → 2,000, learning rate 0.05 → 0.03,
  L2 3.0 → 5.0, early stopping 50 → 100
- 미변경: depth 8, `border_count=32`, Bernoulli subsample 0.8,
  `task_type=GPU`, `devices=0`

## 결과

| 항목 | EXP-131 | EXP-127 | EXP-094 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4222392962 | 0.4194572294 | 0.4168865739 |
| Fold 표준편차 | 0.0140119367 | 0.0136136464 | 0.0078842521 |
| Accuracy | 0.4183196259 | 0.4160619255 | 0.4071923883 |
| Log Loss | 1.8665114104 | 1.8624933825 | 1.8399373293 |

| Fold | Macro F1 | Accuracy | Log Loss | Best iteration |
|---:|---:|---:|---:|---:|
| 0 | 0.4041809389 | 0.4029045643 | 1.8892556416 | 1998 |
| 1 | 0.4466974492 | 0.4241935484 | 1.8921618712 | 1995 |
| 2 | 0.4151827021 | 0.4169354839 | 1.8534822510 | 1999 |
| 3 | 0.4209819717 | 0.4225806452 | 1.8532389727 | 1999 |
| 4 | 0.4246988587 | 0.4245967742 | 1.8444183150 | 1999 |

네 fold가 아니라 사실상 모든 fold가 1,995~1,999 iteration까지 도달해
학습 상한 확장은 실제로 적용됐습니다. 그러나 Log Loss와 fold 안정성은
개선되지 않았습니다.

## 다양성 비교

| 비교 | 라벨 불일치 | 오류 상관 | 확률 Pearson 상관 |
|---|---:|---:|---:|
| EXP-127 | 0.0596677955 | 0.9502667641 | 0.9967572267 |
| EXP-094 | 0.3057571359 | 0.6938450459 | 0.9125405858 |

EXP-094와는 다른 오류를 만들지만, EXP-127과는 예측이 매우 유사합니다.
따라서 CatBoost v1 extended를 별도 ensemble 자산으로 추가하지 않습니다.

## 실행·재현성

- Issue: [#131](https://github.com/fabxoe/open_cancer/issues/131)
- 소스 commit: `b331ce88b854bf4b537b31b69da75b405acae7cf`
- 브랜치: `issue-131-exp-catboost-v1-extended`
- 장비: RunPod Secure Cloud NVIDIA RTX 4090 24GB
- Python: 3.11.10
- CatBoost: 1.2.10
- 실행 시간: 861.4902초
- Config: `configs/exp131_catboost_v1_extended.yaml`
- Resolved config: `reproducibility/exp131_catboost_v1_extended/config.resolved.yaml`
- Metrics: `reports/exp131_catboost_v1_extended/metrics.json`
- OOF: `oof/exp131_catboost_v1_extended.csv`
- Test probability: `preds/exp131_catboost_v1_extended_test_proba.csv`
- Submission: `submissions/exp131_catboost_v1_extended.csv`
- Submission SHA-256: `e8d0863118f1170fd209d465197871eefcd1c0661bb8792c8bd2af60b7ce35d3`
- 재현 상태: `INFERENCE_VERIFIED`

저장 checkpoint 5개에서 OOF·test 확률을 재생성했으며, 라벨 일치율 100%,
확률 최대 절대 차이 0, 제출 CSV byte-level SHA-256 일치를 확인했습니다.
GPU 재학습의 비결정성 때문에 아직 `TRAINING_VERIFIED`로 승격하지 않습니다.

첫 실행은 5-fold 학습 후 RunPod clone의 Git `user.name`이 없어 metadata 단계에서
실패했습니다. Git 사용자 설정 후 동일 commit·config로 재실행한 성공 실행만
공식 결과로 기록합니다.

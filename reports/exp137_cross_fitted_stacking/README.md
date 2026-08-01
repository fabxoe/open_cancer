# EXP-137: cross-fitted stacking of EXP-094 and EXP-125

## 목적과 설계

G5의 고정 0.5/0.5 blend가 최고 단일 모델을 넘지 못해, 두 base 모델의 26개
확률을 연결한 52차원 입력으로 multinomial Logistic Regression meta learner를
검증했습니다. 각 outer fold의 meta learner는 해당 검증 fold를 보지 않고 다른
네 fold의 base OOF 확률로 학습했습니다.

고정 설정은 `C=0.2`, `max_iter=1000`, `class_weight=None`, `random_state=42`이며,
최종 test 예측만 전체 base OOF로 재학습한 모델을 사용했습니다.

## 결과

| 항목 | EXP-137 | EXP-135 blend | EXP-131 최고 단일 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4068626451 | 0.4201772665 | 0.4222392962 |
| Fold 표준편차 | 0.0059257501 | 0.0126953092 | 0.0140119367 |
| Accuracy | 0.4650862764 | 0.4110627318 | 0.4183196259 |
| Log Loss | 1.8272781305 | 1.8083444812 | 1.8665114104 |

Accuracy와 fold 표준편차는 좋아졌지만 Macro F1이 크게 하락했습니다. 특히
DLBC·PAAD·SARC 등 일부 소수 클래스 F1이 붕괴해 대회 지표 기준을 충족하지
못했습니다. 최고 단일 모델 대비 `-0.0153766511`, G6 채택 기준인 `+0.002`에
미달하므로 stack은 기각합니다.

## 재현성

- Issue: [#137](https://github.com/fabxoe/open_cancer/issues/137)
- Branch: `issue-137-exp-cross-fitted-stacking`
- Config: `configs/exp137_cross_fitted_stacking.yaml`
- OOF: `oof/exp137_cross_fitted_stacking.csv`
- Test probability: `preds/exp137_cross_fitted_stacking_test_proba.csv`
- Checkpoints: `models/exp137_cross_fitted_stacking/`
- Reproducibility: `INFERENCE_VERIFIED`

저장한 fold checkpoint와 최종 meta checkpoint로 OOF·test 확률 및 제출 CSV를
재생성했고, 라벨 일치율 100%와 확률 차이 허용범위 통과를 확인했습니다.

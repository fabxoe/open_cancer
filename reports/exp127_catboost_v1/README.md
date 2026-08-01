# EXP-127 동결 Feature Spec v1 CatBoost

## 결론

동결된 EXP-094 Feature Spec v1과 canonical 5-fold는 그대로 두고 모델만
CatBoost로 바꿨습니다. RunPod RTX 4090에서 실행한 OOF Macro F1은
**0.4194572294**로 EXP-125 LightGBM보다 `+0.0005493930`, EXP-094
XGBoost보다 `+0.0025706555` 높아 새로운 Local 최고를 기록했습니다.

다만 EXP-094 대비 Log Loss가 `+0.0225562011`, fold 표준편차가
`+0.0057293943` 악화되어 고정 quality·wildcard gate는 통과하지
못했습니다. 예측 라벨 불일치율은 30.54%, 정오답 상관은 0.6962로
diversity gate를 통과했으므로 단독 최고점과 별개로 후속 blend·stacking에서
가중치를 검증할 가치가 큰 모델입니다.

## 무엇이 달라졌나

- 피처: EXP-094와 동일한 Feature Spec v1, 35,119개
- 모델: XGBoost에서 CatBoost GPU로 교체
- 장비: RunPod NVIDIA RTX 4090 24GB
- canonical stratified 5-fold와 class-balanced sample weight 유지
- 각 outer-fold validation만 early stopping 평가에 사용

## 고정 조건

- `iterations=1000`, `depth=8`, `learning_rate=0.05`
- `l2_leaf_reg=3`, `border_count=32`
- `bootstrap_type=Bernoulli`, `subsample=0.8`
- `task_type=GPU`, `devices=0`
- early stopping 50
- fold별 best iteration: 997, 999, 999, 999, 999
- Public LB: 미제출

## 결과

| 항목 | EXP-127 | EXP-125 | EXP-094 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4194572294 | 0.4189078364 | 0.4168865739 |
| Fold 표준편차 | 0.0136136464 | 0.0081051732 | 0.0078842521 |
| Accuracy | 0.4160619255 | 0.4142880181 | 0.4071923883 |
| Log Loss | 1.8624933825 | 1.8227982418 | 1.8399371814 |

| Fold | Macro F1 | Accuracy | Log Loss | Best iteration |
|---:|---:|---:|---:|---:|
| 0 | 0.4008452894 | 0.3964544722 | 1.8855038345 | 997 |
| 1 | 0.4405650635 | 0.4185483871 | 1.8934036749 | 999 |
| 2 | 0.4173173958 | 0.4177419355 | 1.8448711854 | 999 |
| 3 | 0.4115121069 | 0.4193548387 | 1.8603351769 | 999 |
| 4 | 0.4276474855 | 0.4282258065 | 1.8283344839 | 999 |

EXP-094 대비 26개 중 12개 클래스 F1이 개선됐습니다. 큰 개선은 KIRC
`+0.2535`, LGG `+0.1906`, PAAD `+0.0367`입니다. 반면 ACC `-0.1169`,
BLCA `-0.0979`, TGCT `-0.0642`, STES `-0.0641`은 하락해 클래스별
보완성이 뚜렷합니다.

## 다양성·채택 gate

| 비교 항목 | EXP-094 대비 | EXP-125 대비 |
|---|---:|---:|
| Macro F1 차이 | +0.0025706555 | +0.0005493930 |
| 예측 라벨 불일치율 | 0.3054346073 | 0.3430091921 |
| 정오답 상관 | 0.6961772026 | 0.6908331245 |
| 확률 Pearson 상관 | 0.9136242923 | 0.9041911208 |

- quality gate: 실패
- wildcard gate: 실패
- diversity gate: 통과
- ensemble quality eligible: 아니오(현재 고정 gate 기준)

단독 OOF가 가장 높다는 사실과 ensemble quality gate는 구분합니다. 다음
단계에서는 임의 채택하지 않고 EXP-094·096·125와 OOF blend를 탐색한 뒤
canonical cross-fitting 기준으로 판단합니다.

## 재현성과 실행 메모

- Issue: [#127](https://github.com/fabxoe/open_cancer/issues/127)
- 실행 source commit: `03af58890c1cac9d90e61430e550b7ae6cc7060d`
- Config: `configs/exp127_catboost_v1.yaml`
- Resolved config: `reproducibility/exp127_catboost_v1/config.resolved.yaml`
- Metrics: `reports/exp127_catboost_v1/metrics.json`
- OOF: `oof/exp127_catboost_v1.csv`
- Test probability: `preds/exp127_catboost_v1_test_proba.csv`
- 제출 후보: `submissions/exp127_catboost_v1.csv` (DACON 미제출)
- 제출 SHA-256:
  `f4fdd043a1875a41d333fa88f34911fd0f6f20758a3bd41deea1288d473cb543`
- 재현 상태: `INFERENCE_VERIFIED`

다섯 저장 checkpoint로 OOF와 test를 다시 추론해 라벨 일치율 100%, 확률
최대 절대 차이 0, 제출 CSV byte-level SHA-256 일치를 확인했습니다.
CatBoost GPU 학습은 부동소수점 연산 순서 때문에 재학습 결과가 byte-level로
항상 같다고 보장하지 않으므로 이번 상태는 저장 checkpoint 추론 재현을
증명한 `INFERENCE_VERIFIED`입니다.

첫 실행은 5-fold 학습과 예측 저장을 마친 뒤 RunPod 저장소의 Git 사용자
이름이 비어 있어 manifest 작성 단계에서 종료됐습니다. Git 신원을 설정하고
같은 clean commit·설정으로 공식 실행을 다시 완료했습니다. 두 학습의 제출
해시는 GPU 재학습 비결정성으로 달랐으며, 최종 장부에는 성공한 두 번째
실행만 기록합니다.

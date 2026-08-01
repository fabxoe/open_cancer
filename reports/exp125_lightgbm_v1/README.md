# EXP-125 동결 Feature Spec v1 LightGBM

## 결론

동결된 EXP-094 Feature Spec v1과 canonical 5-fold는 그대로 두고 모델만
LightGBM으로 바꿨습니다. OOF Macro F1은 **0.4189078364**로 기존 Local 최고
EXP-096보다 `+0.0007925284`, 같은 v1 XGBoost 기준 EXP-094보다
`+0.0020212625` 높아져 **새로운 Local 최고 모델**이 됐습니다.

EXP-094 대비 Log Loss도 `-0.0171389395` 개선됐고 예측 라벨은 23.11% 달라
품질·wildcard·다양성 gate를 모두 통과했습니다. 단독 성능 후보이면서 후속
blend·stacking 입력 후보로 채택합니다.

## 무엇이 달라졌나

피처는 EXP-094와 완전히 같습니다. 차이는 모델이 데이터를 읽는 방식입니다.

- XGBoost: 같은 깊이의 트리를 단계적으로 추가하는 방식
- LightGBM: leaf-wise 방식으로 손실이 많이 줄어드는 잎을 우선 분할

같은 피처를 사용해도 나무를 만드는 방식이 달라 서로 다른 오류가 생길 수
있습니다. 이번 실험은 새 파생변수의 효과가 아니라 **모델 family 다양화의
효과**를 측정한 것입니다.

## 고정 조건

- Feature Spec: `v1` = EXP-094, 35,119개 피처
- Feature Spec SHA-256:
  `1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3`
- Split: canonical stratified 5-fold, seed 42
- class-balanced sample weight 사용
- `num_leaves=31`, `learning_rate=0.03`, 최대 1,200 rounds
- early stopping 60, 해당 outer-fold validation만 사용
- fold별 저장 checkpoint tree 수: 145, 150, 144, 132, 132
- Public LB: 미제출

## 결과

| 항목 | EXP-125 | EXP-096 | EXP-094 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4189078364 | 0.4181153080 | 0.4168865739 |
| Fold 표준편차 | 0.0081051732 | 0.0094921177 | 0.0078842521 |
| Accuracy | 0.4142880181 | 0.4078374456 | 0.4071923883 |
| Log Loss | 1.8227982418 | 1.8369342389 | 1.8399371814 |

| Fold | Macro F1 | Accuracy | Log Loss | 저장 tree 수 |
|---:|---:|---:|---:|---:|
| 0 | 0.4102706033 | 0.4069298952 | 1.8515712363 | 145 |
| 1 | 0.4263269667 | 0.4145161290 | 1.8403877298 | 150 |
| 2 | 0.4099375381 | 0.4096774194 | 1.7898548735 | 144 |
| 3 | 0.4143081706 | 0.4177419355 | 1.8329329333 | 132 |
| 4 | 0.4289890827 | 0.4225806452 | 1.7992212322 | 132 |

EXP-094 대비 26개 중 14개 클래스 F1이 개선됐습니다. 큰 개선은 KIRC
`+0.0957`, TGCT `+0.0559`, LGG `+0.0413`, UCEC `+0.0367`, PRAD
`+0.0273`입니다. 반면 SARC `-0.0555`, LAML `-0.0495`, ACC `-0.0415`,
BLCA `-0.0410`은 하락했으므로 후속 앙상블에서 클래스 보완성을 살펴봅니다.

## 다양성·채택 gate

| 비교 항목 | EXP-094 대비 | EXP-096 대비 |
|---|---:|---:|
| Macro F1 차이 | +0.0020212625 | +0.0007925284 |
| Log Loss 차이 | -0.0171389395 | -0.0141359972 |
| Fold 표준편차 차이 | +0.0002209211 | -0.0013869445 |
| 예측 라벨 불일치율 | 0.2310917594 | 0.2410901468 |
| 정오답 상관 | 0.7968772821 | 0.7875825088 |
| 확률 Pearson 상관 | 0.9575965337 | 0.9531280311 |

- quality gate: 통과
- wildcard gate: 통과
- diversity gate: 통과
- ensemble quality eligible: 예

## 재현성과 산출물

- Issue: [#125](https://github.com/fabxoe/open_cancer/issues/125)
- 실행 source commit: `8d4fe9c99e05306c691f1c4f23903066b92f7ddf`
- Config: `configs/exp125_lightgbm_v1.yaml`
- Resolved config: `reproducibility/exp125_lightgbm_v1/config.resolved.yaml`
- Metrics: `reports/exp125_lightgbm_v1/metrics.json`
- OOF: `oof/exp125_lightgbm_v1.csv`
- Test probability: `preds/exp125_lightgbm_v1_test_proba.csv`
- 제출 후보: `submissions/exp125_lightgbm_v1.csv` (DACON 미제출)
- 제출 SHA-256:
  `e76cce6d911616930570bcf0c5c1adc8adb045fbd18e3226d5378bda026d5940`
- 재현 상태: `INFERENCE_VERIFIED`

다섯 저장 checkpoint로 OOF와 test를 다시 추론해 라벨 일치율 100%, 확률 최대
절대 차이 0, 제출 CSV byte-level SHA-256 일치를 확인했습니다.

## 다음 결정

EXP-125를 단독 성능 후보와 ensemble 후보로 모두 채택합니다. 로드맵대로
CatBoost를 독립 실험한 뒤 G4에서 EXP-094·096·125와 기타 보존 OOF를 함께
감사합니다. Public LB 제출 여부는 G4 후보 감사 후 결정합니다.

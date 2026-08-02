# EXP-223 pathway XGBoost Macro F1 checkpoint 선택

## 결론

EXP-096의 fixed pathway burden 피처·XGBoost 설정·canonical 5-fold는 유지하고,
각 fold checkpoint를 validation `mlogloss` 최소가 아니라 validation Macro F1
최대 시점으로 저장했습니다. OOF Macro F1은 **0.4213739476**으로 EXP-096보다
`+0.0032586396` 개선됐고 fold 표준편차도 `-0.0002581124` 감소했습니다.

사전 기준인 Macro F1 `+0.001`, fold 표준편차 악화 `<0.002`, 클래스별 대규모
붕괴 없음 조건을 모두 충족해 **채택**합니다. Public LB에는 아직 제출하지
않았습니다.

## 유일한 변경

- 부모: EXP-096
- 피처: Feature Spec v1 + fixed pathway burden 20개 유지
- 모델·seed·balanced sample weight: EXP-096 유지
- split: canonical stratified 5-fold(seed 42) 유지
- checkpoint 선택: validation mlogloss-best → validation Macro-F1-best
- test와 Public LB는 iteration 선택에 사용하지 않음

## 결과

| 항목 | EXP-223 | EXP-096 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4213739476 | 0.4181153080 | +0.0032586396 |
| Fold 표준편차 | 0.0092340053 | 0.0094921177 | -0.0002581124 |
| Accuracy | 0.4112239961 | 0.4078374456 | +0.0033865506 |
| Log Loss | 1.8441621065 | 1.8369342089 | +0.0072278976 |

| Fold | mlogloss-best iteration | Macro-F1-best iteration | Macro F1 변화 |
|---:|---:|---:|---:|
| 0 | 182 | 193 | +0.0023200234 |
| 1 | 207 | 235 | +0.0028997137 |
| 2 | 287 | 131 | +0.0041349483 |
| 3 | 220 | 222 | +0.0039050905 |
| 4 | 229 | 224 | +0.0023849127 |

클래스별 가장 큰 개선은 LIHC `+0.0222927009`, LAML `+0.0203005956`, HNSC
`+0.0165594001`, CESC `+0.0156986758`였습니다. 가장 큰 하락은 THYM
`-0.0152823920`, BLCA `-0.0141215107`, PCPG `-0.0140961098`, DLBC
`-0.0132275132`로 사전 붕괴 기준에 해당하지 않습니다.

Log Loss는 악화됐지만 대회 공식 지표는 Macro F1입니다. 다만 같은 validation
fold에서 checkpoint를 선택하고 점수를 측정하므로 낙관 편향 가능성은 남아 있으며,
Public 제출이나 독립 반복에서 일반화를 확인해야 합니다.

## 재현성과 산출물

- Issue: [#223](https://github.com/fabxoe/open_cancer/issues/223)
- 실행 source commit: `41eaafc17f286ebc38568d076df5bf16fd0626ac`
- Config: `configs/exp223_pathway_macro_f1_checkpoint.yaml`
- Resolved config: `reproducibility/exp223_pathway_macro_f1_checkpoint/config.resolved.yaml`
- Metrics: `reports/exp223_pathway_macro_f1_checkpoint/metrics.json`
- pathway membership: `reports/exp223_pathway_macro_f1_checkpoint/pathway_membership.json`
- 제출 후보: `submissions/exp223_pathway_macro_f1_checkpoint.csv` (DACON 미제출)
- 제출 SHA-256:
  `74a23b6337b17fc4ed70ae1e3639331065e0d74432bed6b8fcf9dc9344e6c48c`
- 실행시간: 556.44초
- 재현 상태: `INFERENCE_VERIFIED`

저장 checkpoint로 test를 다시 추론해 라벨 일치율 100%, 확률 최대 절대 차이
`1.44e-7`, 제출 CSV byte-level SHA-256 일치를 확인했습니다.

## 후속 실험

다음 후보는 10개 fixed pathway별로 missense·nonsense·frameshift·synonymous·
complex 유전자 수를 분리하는 약 50개 변이 종류 구성 피처입니다. EXP-223을
부모로 사용하되 새 Experiment Issue에서 단독 family 효과를 검증합니다.

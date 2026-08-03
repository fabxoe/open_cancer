# EXP-237 pathway별 변이 종류를 비율로 바꿔 재검증

## 결론

EXP-229의 pathway별 변이종류 raw affected-gene count 50개를 pathway 내부
fraction으로 교체했습니다. OOF Macro F1은 **0.4204138300**으로 EXP-229보다
`-0.0025747446` 하락해 **ARCHIVE**합니다.

fold 표준편차는 개선됐지만 Log Loss가 `+0.0835732222` 크게 악화됐습니다.
공식 지표 개선도 없으므로 fraction이 raw count보다 나은 표현이라고 판단하지
않습니다.

## 유일한 변경

각 pathway와 변이종류에 대해 다음 값을 계산했습니다.

`특정 변이종류가 관찰된 유전자 수 / pathway 전체 변이 유전자 수`

- 분모가 0이면 fraction은 0
- 한 유전자에 여러 변이종류가 있으면 여러 분자에 포함 가능
- 기존 pathway mutated/LoF count 20개는 유지
- 모델·seed·canonical 5-fold·Macro-F1 checkpoint 정책은 EXP-229와 동일
- EXP-232 선택 결과, subclass, test 분포와 Public LB는 피처 정의에 사용하지 않음

semantic equivalence 검사 후 부모 20개를 포함한 pathway 피처 수는 fold별
`63 / 64 / 64 / 64 / 63`개였습니다.

## 결과

| 항목 | EXP-237 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4204138300 | 0.4229885745 | -0.0025747446 |
| Fold 표준편차 | 0.0073981342 | 0.0098679649 | -0.0024698307 |
| Accuracy | 0.4110627318 | 0.4125141106 | -0.0014513788 |
| Log Loss | 1.9345345497 | 1.8509613276 | +0.0835732222 |

| Fold | Macro F1 | best iteration | Log Loss |
|---:|---:|---:|---:|
| 0 | 0.4137518575 | 186 | 1.8751235008 |
| 1 | 0.4216749790 | 32 | 2.1911833286 |
| 2 | 0.4206987516 | 296 | 1.8093844652 |
| 3 | 0.4165303883 | 59 | 1.9796326160 |
| 4 | 0.4352217755 | 186 | 1.8173975945 |

fold 1과 3에서 Macro-F1-best iteration이 지나치게 이르게 선택되면서 Log Loss가
크게 악화됐습니다. Macro F1도 부모보다 낮으므로 이 현상을 유효한 trade-off로
보지 않습니다.

클래스별로 KIRC `+0.0673780757`, LGG `+0.0432729610` 개선이 있었지만,
DLBC `-0.0345260515`, STES `-0.0318418212`, CESC `-0.0300404514` 등
다른 클래스 하락과 전체 Macro F1 하락을 상쇄하지 못했습니다.

## 재현성과 산출물

- Issue: [#237](https://github.com/fabxoe/open_cancer/issues/237)
- 실행 source commit: `bbebdf139bee3002b542015097ce8b2bc46fbe71`
- Config: `configs/exp237_pathway_mutation_fractions.yaml`
- Resolved config: `reproducibility/exp237_pathway_mutation_fractions/config.resolved.yaml`
- Metrics: `reports/exp237_pathway_mutation_fractions/metrics.json`
- 제출 후보: `submissions/exp237_pathway_mutation_fractions.csv` (DACON 미제출)
- 제출 SHA-256:
  `0b7aab3c3cadccb8918c80b6582b8e0e2f871781d2adae163dd32b049f717338`
- 실행시간: 578.67초
- 재현 상태: `INFERENCE_VERIFIED`

저장 checkpoint로 test를 다시 추론해 라벨 일치율 100%, 확률 최대 절대 차이
`1.47e-7`, 제출 CSV byte-level SHA-256 일치를 확인했습니다.

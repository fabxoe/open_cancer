# EXP-229 pathway별 변이 종류 유전자 수

## 결론

현재 부모 EXP-223에 pathway별 변이 종류 구성 피처를 추가한 결과, OOF Macro F1이
**0.4229885745**로 `+0.0016146270` 개선됐습니다. fold 표준편차 악화는
`+0.0006339596`, 클래스별 최대 F1 하락은 LAML `-0.0422523477`로 사전 기준
안에 있어 **조건부 채택**합니다.

다만 Log Loss는 `+0.0067992210` 악화됐고 5개 fold 중 fold 2는 소폭
하락했습니다. 따라서 효과가 크거나 완전히 안정적이라고 단정하지 않고 제출 후보로
보존합니다.

## 무엇을 추가했나

기존 EXP-223은 각 pathway에 변이 유전자가 몇 개인지와 LoF 유전자가 몇 개인지를
셌습니다. 이번 실험은 같은 10개 pathway 안에서 다음 변이 종류가 관찰된 유전자
수를 각각 셌습니다.

- missense
- synonymous
- nonsense
- frameshift
- complex

한 유전자에 같은 종류의 토큰이 여러 개 있어도 해당 종류의 유전자 수는 1로
계산합니다. 외부 환자 데이터나 subclass는 사용하지 않았고, 고정 pathway 목록과
대회 CSV의 변이 토큰만 사용했습니다.

후보는 50개였으며 기존 Feature Spec과 fold-train 값이 완전히 같은 열은 제거했습니다.
부모 pathway 피처 20개를 포함한 최종 pathway 피처 수는 fold별
`62 / 63 / 63 / 63 / 62`개였습니다. 즉 새 후보 중 42~43개가 fold별로
유지됐습니다.

## 결과

| 항목 | EXP-229 | EXP-223 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4229885745 | 0.4213739476 | +0.0016146270 |
| Fold 표준편차 | 0.0098679649 | 0.0092340053 | +0.0006339596 |
| Accuracy | 0.4125141106 | 0.4112239961 | +0.0012901145 |
| Log Loss | 1.8509613276 | 1.8441621065 | +0.0067992210 |

| Fold | EXP-229 | EXP-223 | 변화 |
|---:|---:|---:|---:|
| 0 | 0.4125153614 | 0.4109700215 | +0.0015453399 |
| 1 | 0.4227302800 | 0.4210640745 | +0.0016662055 |
| 2 | 0.4172366349 | 0.4181611577 | -0.0009245228 |
| 3 | 0.4221575240 | 0.4172319385 | +0.0049255855 |
| 4 | 0.4415264445 | 0.4384246233 | +0.0031018212 |

큰 개선은 DLBC `+0.0502645503`, LUAD `+0.0340388007`, UCEC
`+0.0239808153`였습니다. 큰 하락은 LAML `-0.0422523477`, PAAD
`-0.0325077967`, TGCT `-0.0196246430`이었습니다.

## 해석과 주의점

단순히 pathway 안의 전체 변이량만 세는 것보다 변이 종류를 나눠 제공하는 것이
암종 구분에 추가 정보를 준 결과와 일치합니다. 하지만 이 실험만으로 특정 pathway나
변이 종류가 원인이라고 단정할 수는 없습니다. 50개 후보를 묶어서 추가한 ablation이며,
개별 피처 중요도는 별도 fold-safe 분석이 필요합니다.

Public LB는 피처 정의나 채택 판단에 사용하지 않았습니다. 2026-08-03
23:45:30 KST에 제출한 결과는 `0.3203598833`으로, EXP-223의 `0.323243525`보다
`-0.0028836417` 낮았습니다. 따라서 Local 개선은 Public에서 재현되지 않았고 팀
대표 제출은 EXP-223으로 유지합니다. 이 결과를 보고 피처·가중치를 역조정하지
않습니다.

## 재현성과 산출물

- Issue: [#229](https://github.com/fabxoe/open_cancer/issues/229)
- 실행 source commit: `75977326ab526f0b4c34ad5af90b29fb833c44c6`
- Config: `configs/exp229_pathway_mutation_types.yaml`
- Resolved config: `reproducibility/exp229_pathway_mutation_types/config.resolved.yaml`
- Metrics: `reports/exp229_pathway_mutation_types/metrics.json`
- pathway membership: `reports/exp229_pathway_mutation_types/pathway_membership.json`
- 제출: `submissions/exp229_pathway_mutation_types.csv` (제출 ID `1509990`)
- Public Macro F1: `0.3203598833`
- 제출 SHA-256:
  `66f50d7fdd3c0ca65e586f83c4ee4d8cfb3a99d85d03c04ef9b8fbea7b1af61b`
- 실행시간: 582.07초
- 재현 상태: `INFERENCE_VERIFIED`
- Release: [`exp-229-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-229-repro-v1)

저장 checkpoint로 test를 다시 추론해 라벨 일치율 100%, 확률 최대 절대 차이
`1.72e-7`, 제출 CSV byte-level SHA-256 일치를 확인했습니다. Issue #260에서 원본
checkpoint·iteration audit 각 5개와 OOF/test 확률을 deterministic bundle로
보존하고 원격 재다운로드 SHA-256 일치를 확인했습니다.

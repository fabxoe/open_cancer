# EXP-192 — R2 희귀 mutation-presence filter

## 결론

각 outer fold의 학습 행에서 양성 수가 5개 미만인 `GENE__mutated` 열만 제거했다.
OOF Macro F1은 **0.4176058118**로 EXP-094보다 **+0.0007192379** 높았지만,
fold 표준편차가 **+0.0073552678** 악화되어 사전 등록한 안정성 gate를 통과하지
못했다. 따라서 **ARCHIVE**이며 리더보드에는 제출하지 않는다.

## R2 정책

- selector fit 범위: 각 canonical outer fold의 학습 행만 사용
- 제거 기준: outer-train 양성 수 `< 5`인 `GENE__mutated` 열
- 보존 대상: 같은 유전자의 mutation-type, missing, residue-position 열과
  sample aggregate·hotspot 열은 모두 보존
- validation·test: 해당 fold의 학습 행에서 확정·저장한 같은 mask만 적용
- EXP-094와 같은 Feature Spec v1 XGBoost와 balanced sample weight를 사용했고,
  SMOTE는 사용하지 않았다.

## 결과

| 지표 | EXP-192 | EXP-094 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.4176058118 | +0.0007192379 |
| Fold Macro F1 평균 | 0.4175357885 | - |
| Fold 표준편차 | 0.0152395199 | +0.0073552678 |
| Accuracy | 0.4083212385 | - |
| Log Loss | 1.8383198541 | -0.0016174752 |

Fold별 제거 열 수는 `241`, `265`, `246`, `240`, `255`개였다. 이는 4,384개
mutation-presence 열 중 약 5.5~6.0%이며, Feature Spec v1의 나머지 채널은
동일하게 유지했다. 가장 큰 클래스별 F1 하락은 LUAD의 `-0.0316866934`로,
간소화 조건의 `-0.05` 한도 안이었지만 fold 안정성 조건을 만족하지 못했다.

## 판정과 해석

성능 채택에는 Macro F1 `+0.001` 이상, fold 표준편차 악화 `<0.002`, Log Loss
악화 없음이 모두 필요하다. EXP-192는 Log Loss가 개선됐지만 Macro F1 개선 폭이
부족하고 fold 표준편차가 크게 악화됐다. 간소화 후보도 표준편차 조건을 넘지 못해
해당하지 않는다.

따라서 저빈도 mutation-presence 열의 일괄 제거는 현재 Feature Spec v1 XGBoost에서
안정적인 일반화 이득을 주지 못했다. 이 R2 정책은 threshold를 다시 조정하지 않고
보존하며, 다음 사전 등록 단계인 S1 Elastic Net stability selection은 target을
outer-train 내부에서만 사용해 별도로 검증한다.

## 산출물·재현성

- Config: `configs/exp192_r2_rare_mutation_presence_filter.yaml`
- Runner: `scripts/run_exp192_r2_rare_mutation_presence_filter.py`
- Metrics: `reports/exp192_r2_rare_mutation_presence_filter/metrics.json`
- Manifest: `reproducibility/exp192_r2_rare_mutation_presence_filter/`
- fold별 mask: `models/exp192_r2_rare_mutation_presence_filter/fold_*_feature_selection.json`

각 mask에는 outer-train prevalence, 제거 유전자와 순서 해시를 저장한다.
checkpoint, OOF, test 확률, submission은 Git에 커밋하지 않으며 재현 상태는
`MANIFEST_COMPLETE`다.

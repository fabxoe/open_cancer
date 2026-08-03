# EXP-191 — R1 상관 pair 범주형 요약 피처

## 결론

상관된 유전자 pair를 삭제하지 않고, 각 pair의 상태를 `왼쪽만 변이`, `오른쪽만
변이`, `둘 다 변이`라는 세 개의 이진 변수로 추가했다. OOF Macro F1은
**0.4144744818**로 EXP-094보다 **-0.0024120921** 낮아 **ARCHIVE**이며
리더보드에는 제출하지 않는다.

## R1 정책

- pair 선정: 각 outer fold의 학습 행에서만 C2와 같은 기준(Phi ≥ `0.25`,
  Jaccard ≥ `0.15`, 공동 변이 수 ≥ `20`)으로 greedy non-overlap matching
- pair당 추가 변수: `only_left`, `only_right`, `both_mutated`
- 원래 Feature Spec v1의 모든 유전자·mutation type·position·aggregate·hotspot
  피처는 유지한다. 어떤 기존 열도 삭제하지 않는다.
- validation·test에는 해당 fold의 학습 행에서 정한 같은 pair 목록만 적용한다.
- EXP-094와 동일한 XGBoost, canonical 5-fold, balanced sample weight를 쓰며
  SMOTE는 사용하지 않는다.

## 결과

| 지표 | EXP-191 | EXP-094 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.4144744818 | -0.0024120921 |
| Fold Macro F1 평균 | 0.4141461783 | - |
| Fold 표준편차 | 0.0126377260 | +0.0047534740 |
| Accuracy | 0.4052572166 | - |
| Log Loss | 1.8394420338 | -0.0004952955 |

Fold별 pair 수는 `58`, `75`, `61`, `109`, `70`개였고, 이에 따라 추가한 pair
피처 수는 `174`, `225`, `183`, `327`, `210`개였다. 원래 v1 열은 모든 fold에서
그대로 남아 있다.

## 판정과 해석

성능 채택에는 Macro F1 `+0.001` 이상, fold 표준편차 악화 `<0.002`, Log Loss
악화 없음이 모두 필요하다. EXP-191은 Log Loss는 조금 개선됐지만 Macro F1이
하락하고 fold 표준편차가 크게 악화돼 통과하지 못했다. 간소화 후보는 열 수를
줄이는 정책에만 해당하므로 R1에는 적용하지 않는다.

C1~C3의 상관 열 삭제와 R1의 관계 요약이 모두 기준 모델을 넘지 못했다. 이 결과는
단순 pairwise Phi/Jaccard 관계가 현재 Feature Spec v1 XGBoost에 추가적인 안정된
암종 구분 신호를 주지 못했다는 근거로 보존한다. 다음으로는 이 관계 정책을
재조정하지 않고, 별도 사전 등록 정책인 R2 희귀 mutation-presence filter를
검증한다.

## 산출물·재현성

- Config: `configs/exp191_r1_correlation_pair_summary.yaml`
- Runner: `scripts/run_exp191_r1_correlation_pair_summary.py`
- Metrics: `reports/exp191_r1_correlation_pair_summary/metrics.json`
- Manifest: `reproducibility/exp191_r1_correlation_pair_summary/`
- fold별 pair 명세: `models/exp191_r1_correlation_pair_summary/fold_*_pair_features.json`

각 pair 명세는 확장 feature의 순서 해시와 전체 candidate·matched pair 목록을
함께 저장한다. Git metrics에는 결과 요약과 artifact 경로만 남긴다. checkpoint,
OOF, test 확률과 submission은 Git에 커밋하지 않으며 재현 상태는
`MANIFEST_COMPLETE`다.

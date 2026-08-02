# EXP-190 — C3 넓은 Phi/Jaccard 상관 삭제

## 결론

EXP-094 Feature Spec v1에서 가장 넓은 사전 등록 상관 삭제 정책을 검증했다. OOF
Macro F1은 **0.4157643312**로 기준보다 **-0.0011222427** 낮았고, fold 표준편차는
**+0.0045573202** 악화됐다. Log Loss는 개선됐지만 사전 gate를 통과하지 못해
**ARCHIVE**이며 리더보드에는 제출하지 않는다.

이 결과로 C1→C3 Phi/Jaccard 상관 삭제 ladder를 종료한다. 결과를 보고 threshold를
더 낮추거나 같은 정책을 재조정하는 후속 실험은 하지 않는다.

## C3 정책

- Phi ≥ `0.20`
- Jaccard ≥ `0.10`
- 공동 변이 수 ≥ `20`
- 각 outer fold의 학습 행에서만 pair와 mask 계산
- 후보는 Phi → Jaccard → 공동 변이 수 → 유전자명 순으로 정렬
- 한 유전자를 두 pair에 반복 사용하지 않는 greedy non-overlap matching
- 각 pair에서 mutation prevalence가 더 낮은 `GENE__mutated` 열 하나만 제거

validation·test에는 해당 fold가 학습 행에서 확정한 동일 mask만 적용했다. 같은
유전자의 mutation-type·missing·residue-position 및 sample aggregate·hotspot은
삭제하지 않았다. EXP-094와 같은 XGBoost, canonical 5-fold, balanced sample
weight를 유지했고 SMOTE는 사용하지 않았다.

## 결과

| 지표 | EXP-190 | EXP-094 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.4157643312 | -0.0011222427 |
| Fold Macro F1 평균 | 0.4150575208 | - |
| Fold 표준편차 | 0.0124415722 | +0.0045573202 |
| Accuracy | 0.4071923883 | - |
| Log Loss | 1.8381019926 | -0.0018353367 |

Fold별 제거 열 수는 `215`, `213`, `194`, `259`, `226`개였고, 5개 fold에서 한 번이라도
제거된 유전자는 548개였다. 후보/매칭 pair 수는 fold별로 `6790/215`, `10215/213`,
`7471/194`, `15204/259`, `9000/226`이다.

## 판정과 해석

성능 채택에는 Macro F1 `+0.001` 이상, fold 표준편차 악화 `<0.002`, Log Loss
악화 없음이 모두 필요하다. C3는 Log Loss만 좋아졌고 Macro F1과 안정성 조건을
통과하지 못했다. 간소화 후보 기준도 Macro F1 하락이 `0.001`을 조금 넘고 fold
표준편차 악화가 커서 통과하지 못했다.

C1은 Macro F1이 소폭 상승했으나 안정성·Log Loss에서, C2와 C3은 Macro F1과
안정성에서 실패했다. 따라서 이 데이터·Feature Spec v1·XGBoost 조합에서는
mutation-presence의 pairwise 상관을 삭제하는 방식이 신뢰할 만한 개선을 만들지
못했다. 이후에는 열을 더 제거하는 대신, 사전 등록한 관계 자체를 설명하는 R1
범주형 요약 또는 희귀 mutation-presence filter(R2)를 독립 정책으로 검증한다.

## 산출물·재현성

- Config: `configs/exp190_c3_phi_jaccard_pruning.yaml`
- Runner: `scripts/run_exp190_c3_phi_jaccard_pruning.py`
- Metrics: `reports/exp190_c3_phi_jaccard_pruning/metrics.json`
- Manifest: `reproducibility/exp190_c3_phi_jaccard_pruning/`
- fold별 mask: `models/exp190_c3_phi_jaccard_pruning/fold_*_feature_selection.json`

원본 candidate pair·matched pair 목록은 각 fold mask artifact에 저장되어 있으며,
Git metrics에는 개수·제거 유전자·artifact 경로만 남긴다. checkpoint·OOF·test
확률·submission은 Git에 커밋하지 않는다. 재현 상태는 `MANIFEST_COMPLETE`다.

# EXP-188 — C1 보수적 Phi/Jaccard 상관 삭제

## 결론

EXP-094 Feature Spec v1에서 각 outer-fold 학습 행만 사용해, 매우 비슷하게 함께
변이되는 유전자 쌍의 `GENE__mutated` 열 하나를 제거했다. OOF Macro F1은
**0.4179737169**로 기준보다 **+0.0010871430** 높았지만, fold 간 흔들림이 크게
커지고 Log Loss도 소폭 악화됐다. 사전 고정된 gate를 통과하지 못했으므로
**ARCHIVE**이며 리더보드에 제출하지 않는다.

## C1 정책

- Phi ≥ `0.30`
- Jaccard ≥ `0.15`
- 공동 변이 수 ≥ `20`
- 각 outer fold의 학습 행에서만 계산
- 후보는 Phi → Jaccard → 공동 변이 수 → 유전자명 순으로 정렬
- 한 유전자를 두 pair에 반복 사용하지 않는 greedy non-overlap matching
- 각 pair에서 변이 빈도가 더 낮은 `GENE__mutated` 열 하나만 제거

validation과 test에는 해당 fold가 학습 행에서 확정한 mask만 적용했다. 같은
유전자의 mutation-type·missing·residue-position 열 및 sample aggregate·hotspot은
제거하지 않았다. balanced sample weight는 EXP-094와 동일하게 유지했고 SMOTE는
사용하지 않았다.

## 결과

| 지표 | EXP-188 | EXP-094 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.4179737169 | +0.0010871430 |
| Fold Macro F1 평균 | 0.4174682240 | - |
| Fold 표준편차 | 0.0111431892 | +0.0032589371 |
| Accuracy | 0.4075149169 | - |
| Log Loss | 1.8403107969 | +0.0003734676 |

Fold별 제거 열은 `6`, `13`, `8`, `13`, `8`개였다. 5개 fold에서 한 번이라도
제거된 유전자는 32개이며, 이처럼 적은 mask 차이에서도 fold 변동성이 커졌다.

## 판정

성능 채택에는 Macro F1 `+0.001` 이상, fold 표준편차 악화 `<0.002`, Log Loss
악화 없음이 모두 필요하다. EXP-188은 Macro F1만 통과했고 나머지 두 조건을
통과하지 못했다. 설정을 결과에 맞춰 바꾸지 않고 `ARCHIVE`로 남긴다.

사전 등록된 C2·C3은 C1의 결과와 무관한 별도 threshold 실험으로 진행할 수 있다.
C1 자체의 threshold·모델 파라미터를 추가 탐색하지 않는다.

## 산출물·재현성

- Config: `configs/exp188_c1_phi_jaccard_pruning.yaml`
- Runner: `scripts/run_exp188_c1_phi_jaccard_pruning.py`
- Metrics: `reports/exp188_c1_phi_jaccard_pruning/metrics.json`
- Manifest: `reproducibility/exp188_c1_phi_jaccard_pruning/`
- fold별 mask: `models/exp188_c1_phi_jaccard_pruning/fold_*_feature_selection.json`

원 학습의 5개 checkpoint와 fold mask로 OOF/test/submission 산출물을 복구해
manifest까지 기록했다. 아직 독립 inference 비교는 하지 않았으므로 재현 상태는
`MANIFEST_COMPLETE`다. checkpoint·OOF·test 확률·submission은 Git에 커밋하지
않는다.

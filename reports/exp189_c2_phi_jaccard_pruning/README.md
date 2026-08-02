# EXP-189 — C2 중간 Phi/Jaccard 상관 삭제

## 결론

EXP-094 Feature Spec v1에서 fold마다 중간 수준의 양의 상관을 보이는 유전자
mutation-presence 열을 제거했다. OOF Macro F1은 **0.4147096714**로 기준보다
**-0.0021769025** 낮았다. Log Loss는 개선됐지만 fold 변동성 및 한 클래스의 F1
하락이 사전 gate를 넘었으므로 **ARCHIVE**이며 리더보드에 제출하지 않는다.

## C2 정책

- Phi ≥ `0.25`
- Jaccard ≥ `0.15`
- 공동 변이 수 ≥ `20`
- 각 outer fold의 학습 행에서만 pair와 mask 계산
- 후보는 Phi → Jaccard → 공동 변이 수 → 유전자명 순으로 정렬
- 한 유전자를 두 pair에 반복 사용하지 않는 greedy non-overlap matching
- 각 pair에서 mutation prevalence가 더 낮은 `GENE__mutated` 열 하나만 제거

validation·test에는 각 fold에서 저장한 동일 mask를 적용했다. 같은 유전자의
mutation-type·missing·residue-position 열과 sample aggregate·hotspot은 유지했다.
EXP-094와 같은 XGBoost, canonical 5-fold, balanced sample weight를 사용했고
SMOTE는 사용하지 않았다.

## 결과

| 지표 | EXP-189 | EXP-094 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.4147096714 | -0.0021769025 |
| Fold Macro F1 평균 | 0.4143676108 | - |
| Fold 표준편차 | 0.0106384109 | +0.0027541588 |
| Accuracy | 0.4063860668 | - |
| Log Loss | 1.8384075392 | -0.0015297901 |

Fold별 제거 열 수는 `58`, `75`, `61`, `109`, `70`개였고, 5개 fold에서 한 번이라도
제거된 유전자는 220개였다. 후보/매칭 pair 수는 fold별로 `209/58`, `436/75`,
`322/61`, `699/109`, `388/70`이다.

## 판정

성능 채택에는 Macro F1 `+0.001` 이상, fold 표준편차 악화 `<0.002`, Log Loss
악화 없음이 모두 필요하다. EXP-189는 Macro F1이 하락했고 fold 표준편차도
허용치를 넘었다. 간소화 후보 기준에서도 Macro F1 하락 폭과 최저 클래스 F1 하락
(`-0.0568182`)이 허용 범위를 넘으므로 해당하지 않는다.

이 결과는 C1의 결과를 보고 임계값을 변경해 얻은 것이 아니다. C2의 Phi `0.25`
정책은 실행 전에 Issue #189와 로드맵에 고정했다. 다음 C3도 사전 등록된 독립
정책으로만 실행하며, C2의 threshold·모델 파라미터를 추가 튜닝하지 않는다.

## 실행 중 산출물 복구

첫 학습은 5개 checkpoint와 fold mask를 모두 저장한 뒤, 공용 runner의 artifact
필드명 참조 오류로 manifest 작성 단계에서 중단됐다. 점수·OOF·test 확률·submission은
이미 작성된 상태였으며, 수정 후 checkpoint를 다시 읽는 replay만 실행해 manifest를
완성했다. 재학습이나 모델 파라미터 변경은 없었다. 이 경로는 독립 원본과
byte-level 비교를 수행한 것은 아니므로 재현 상태는 `MANIFEST_COMPLETE`로 유지한다.

## 산출물·재현성

- Config: `configs/exp189_c2_phi_jaccard_pruning.yaml`
- Runner: `scripts/run_exp189_c2_phi_jaccard_pruning.py`
- Metrics: `reports/exp189_c2_phi_jaccard_pruning/metrics.json`
- Manifest: `reproducibility/exp189_c2_phi_jaccard_pruning/`
- fold별 mask: `models/exp189_c2_phi_jaccard_pruning/fold_*_feature_selection.json`

checkpoint·OOF·test 확률·submission은 Git에 커밋하지 않는다.

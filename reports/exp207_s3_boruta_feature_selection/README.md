# EXP-207 — S3 Boruta feature selection

## 결론

각 canonical outer fold의 학습 행에서만 Boruta 방식으로 mutation-presence
유전자를 선택했다. fold별 confirmed gene은 15~18개였으며 안전 종료 기준인
10개 이상을 충족해 XGBoost까지 학습했다. 그러나 OOF Macro F1은
**0.3484416378**로 EXP-094보다 **-0.0684449361** 낮았고, DLBC F1은
`0.0`이었다. 따라서 이 정책은 **ARCHIVE**하며 리더보드 제출과 Boruta
파라미터 재탐색을 진행하지 않는다.

## S3 정책

- selector fit 범위: 각 canonical outer fold의 학습 행만 사용
- 입력: raw 4,384개 mutation-presence 유전자
- 모델: `RandomForestClassifier`, tree 500개, 최대 50 iteration
- shadow percentile: 100
- 다중 검정: Bonferroni, `alpha=0.05`
- class weight: `balanced_subsample`, seed 42
- 안전 종료: confirmed gene이 10개 미만이면 XGBoost를 학습하지 않음
- 모델 입력: confirmed gene의 Feature Spec v1 유전자 블록과 모든
  sample aggregate·fixed hotspot
- validation·test에는 outer-train에서 저장한 동일 mask만 적용

SMOTE는 사용하지 않았고 EXP-094와 같은 balanced sample weight와 XGBoost
설정을 사용했다.

## 결과

| 지표 | EXP-207 | EXP-094 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.3484416378 | -0.0684449361 |
| Fold Macro F1 평균 | 0.3475062110 | - |
| Fold 표준편차 | 0.0076597543 | -0.0002244977 |
| Accuracy | 0.3534913724 | - |
| Log Loss | 2.0194741289 | +0.1795367996 |

Fold Macro F1은 `0.3457348416`, `0.3384758616`, `0.3420677438`,
`0.3507670103`, `0.3604855979`였다. fold별 confirmed gene 수는
`18`, `16`, `15`, `18`, `17`이고 최종 입력 피처 수는 각각
`191`, `175`, `167`, `191`, `183`이었다.

클래스별로는 DLBC F1이 `0.0`이었으며 EXP-094 대비 가장 큰 클래스별 F1
하락은 `-0.3773584906`이다. Macro F1이 공식 평가의 중심이므로, fold
표준편차가 소폭 작아진 사실은 이 성능 및 소수 클래스 붕괴를 상쇄하지 못한다.
Log Loss는 보조 진단값으로만 해석한다.

## 해석

Boruta가 매 fold에서 15~18개의 매우 강한 유전자만 confirmed로 남긴 결과,
26개 암종을 구분하는 데 필요한 다수의 약한 보완 신호가 사라졌다. 이는 S1의
512-gene cap과 S2의 top-128보다 더 강한 압축이다. selector가 누출되었거나
안전 종료에 실패한 결과는 아니며, 사전 정의한 정책 자체가 이 문제에 지나치게
보수적이었다고 판단한다.

결과를 본 뒤 `perc`, iteration, confirmed/tentative 규칙을 바꾸지 않는다.
S3을 독립 검증 한 번으로 종료한다. 다음 S4에 앞서 공식 지표와 checkpoint
선택의 정렬을 확인하는 Macro-F1 iteration-selection 통제 실험을 수행한다.

## 산출물·재현성

- Config: `configs/exp207_s3_boruta_feature_selection.yaml`
- Runner: `scripts/run_exp207_s3_boruta_feature_selection.py`
- Metrics: `reports/exp207_s3_boruta_feature_selection/metrics.json`
- Manifest: `reproducibility/exp207_s3_boruta_feature_selection/`
- fold별 mask: `models/exp207_s3_boruta_feature_selection/fold_*_feature_selection.json`

각 mask에는 confirmed gene, hit count, shadow importance와 feature-order hash를
저장한다. checkpoint, OOF/test 확률, submission은 Git에 커밋하지 않는다.
저장 산출물 명세까지만 완료했으므로 재현 상태는 `MANIFEST_COMPLETE`다.

# EXP-205 — S2 mRMR feature selection

## 결론

각 outer fold의 학습 행에서만 다중 클래스 mutual information relevance와
binary normalized mutual information redundancy를 사용해 128개 mutation-presence
유전자를 greedy mRMR-MID로 선택했다. OOF Macro F1은 **0.3976963538**로
EXP-094보다 **-0.0191902201** 낮고 Log Loss도 **+0.0426300069** 악화됐다.
따라서 이 정책은 **ARCHIVE**이며 리더보드에는 제출하지 않는다.

## S2 정책

- selector fit 범위: 각 canonical outer fold의 학습 행만 사용
- 후보: outer-train 양성 수가 5 이상인 `GENE__mutated` 열
- relevance: target 26개 클래스와의 exact discrete mutual information
- redundancy: 두 binary mutation-presence 열의 arithmetic-mean normalized mutual information
- 선택: relevance에서 선택 집합과의 평균 redundancy를 뺀 greedy mRMR-MID 상위 128개
- 모델 입력: 선택 유전자의 v1 유전자 블록 전체와 모든 sample aggregate·fixed hotspot
- validation·test: 해당 fold의 학습 행에서 확정·저장한 같은 mask만 적용
- EXP-094와 같은 Feature Spec v1 XGBoost와 balanced sample weight를 사용했고,
  SMOTE는 사용하지 않았다.

## 결과

| 지표 | EXP-205 | EXP-094 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.3976963538 | -0.0191902201 |
| Fold Macro F1 평균 | 0.3968649447 | - |
| Fold 표준편차 | 0.0105133634 | +0.0026291113 |
| Accuracy | 0.3962264151 | - |
| Log Loss | 1.8825673362 | +0.0426300069 |

Fold Macro F1은 `0.4042948622`, `0.3988811270`, `0.3769138837`,
`0.3976361619`, `0.4065986888`이었다. 가장 큰 클래스별 F1 하락은 BLCA의
`-0.1425120773`이다.

## selector 관찰과 해석

fold별 후보는 4,119~4,144개였고 매 fold에서 정확히 128개를 선택했다. 상위에는
TP53, IDH1, BRAF, VHL, APC, PIK3CA, PTEN, RYR2, CTNNB1처럼 변이 기반 암종
구분에 자연스러운 유전자가 반복해서 나타났다. 다섯 fold 공통 선택 유전자는 76개,
합집합은 230개이며 pairwise Jaccard는 약 `0.5329~0.6000`이다.

따라서 mRMR이 무작위나 fold leakage로 동작한 것은 아니지만, 128개 유전자만
남기는 압축 정책은 이 과제의 26개 암종 구분에 필요한 약한·보완적 변이 신호를
충분히 보존하지 못했다. 이 S2 policy의 gene 수, prevalence threshold, relevance나
redundancy 식을 결과나 Public LB를 보고 다시 조정하지 않는다. S2를 한 번의 독립
검증으로 종료하고, 다음 사전 등록 단계인 S3 Boruta로 진행한다.

## 산출물·재현성

- Config: `configs/exp205_s2_mrmr_feature_selection.yaml`
- Runner: `scripts/run_exp205_s2_mrmr_feature_selection.py`
- Metrics: `reports/exp205_s2_mrmr_feature_selection/metrics.json`
- Manifest: `reproducibility/exp205_s2_mrmr_feature_selection/`
- fold별 mask: `models/exp205_s2_mrmr_feature_selection/fold_*_feature_selection.json`

각 mask에는 후보 수, 선택 유전자·rank별 relevance/redundancy score, feature-order
hash를 저장한다. checkpoint, OOF/test 확률, submission은 Git에 커밋하지 않으며
재현 상태는 `MANIFEST_COMPLETE`다.

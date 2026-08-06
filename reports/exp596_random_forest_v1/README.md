# EXP-596 RandomForest v1 스태킹 다양성 후보

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-596 / #596 |
| 목적 | #505 스태킹 로드맵 S0 다양성 감사용으로, 지금까지 채택된 모든 Feature Spec v1 모델(XGBoost/LightGBM/CatBoost/Logistic)이 boosting 또는 선형 계열이라 bagging 기반 RandomForest가 구조적으로 다른 오류를 만드는지 확인 |
| 핵심 입력 | 동결 Feature Spec v1 (EXP-094와 동일, EXP-123/125/127과 동일 입력) |
| 모델 | scikit-learn `RandomForestClassifier` (n_estimators=500, min_samples_leaf=2, max_features=sqrt) |
| Local OOF Macro F1 | 0.4052772619 |
| Public LB | 미제출 |
| 판단 | 단독 후보 미채택(품질 게이트 미달), **#505 스태킹 다양성 후보로 채택**(다양성 게이트 통과) |

## 실제 결과

- Fold Macro F1: 0.4090, 0.3975, 0.4041, 0.3867, 0.4298
- OOF Macro F1 / fold std: 0.4052772619 / 0.0142867463
- Accuracy / Log Loss: 0.4059022738 / 2.0593712417
- 동일 v1 계열 비교: EXP-123(Logistic) 0.3763324825, EXP-125(LightGBM)
  0.4189078364, EXP-127(CatBoost) 0.4194572294 — EXP-596은 Logistic보다
  높고 CatBoost 최고 대비 `-0.0141799675`
- fold std(0.0143)는 v1 계열 다른 모델(대략 0.004~0.006대)보다 뚜렷하게
  높다 — bagging 특유의 fold별 트리 구성 변동으로 보이며, 오류 다양성
  신호일 수도 단순 불안정성일 수도 있어 이 리포트만으로는 구분하지 않는다
- 클래스별 F1 최저: KIPAN 0.2022

## 해석과 한계

CatBoost/LightGBM보다 낮지만 Logistic보다는 높은, 애매한 위치의 점수였다.
프로젝트의 #505 S0 스태킹 다양성 게이트는 "최고 기준 모델 대비 Macro F1
하락 0.004 이내"뿐 아니라 "오류 상관 0.92 이하 또는 예측 라벨 불일치율
10% 이상"도 별도 통과 조건으로 인정한다.

`scripts/audit_exp596_random_forest_diversity.py`를 EXP-127(CatBoost,
GitHub Release 재현 번들 `exp-127-repro-v1`에서 확보)·EXP-125(LightGBM,
`exp-125-repro-v1`) 실제 OOF로 실행해 최종 판정했다:

- 품질 게이트: `macro_f1_delta -0.0141799675` — **미달**(0.004 초과 하락)
- 다양성 게이트: `correctness_pearson 0.7280577163`(≤0.92 통과),
  `label_disagreement 0.3086598936`(≥10% 통과) — **통과**
- EXP-125(LightGBM)와도 `correctness_pearson 0.6654861621`로 비슷하게
  다양함을 확인

RandomForest는 실제로 boosting/선형 계열과 구조적으로 다른 오류를 만든다는
가설이 확인됐다. **단독 성능 후보로는 채택하지 않되, #505 스태킹 다양성
후보로 채택**한다. 상세 수치는
`reports/analysis/exp596_random_forest_diversity_audit.json`.

## 재현과 관련 파일

- Config: `configs/exp596_random_forest_v1.yaml`
- Resolved config: `reproducibility/exp596_random_forest_v1/config.resolved.yaml`
- Runner: `scripts/run_exp596_random_forest_v1.py`
- Metrics: `reports/exp596_random_forest_v1/metrics.json`
- Submission: `submissions/exp596_random_forest_v1.csv`
- Reproduction status: `INFERENCE_VERIFIED`

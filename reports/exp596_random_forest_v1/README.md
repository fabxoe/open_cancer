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
| 판단 | **판정 보류** — 점수만으로는 기각 근거 불충분, #505 S0 다양성 게이트(오류 상관·라벨 불일치율) 확인 필요 |

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

CatBoost/LightGBM보다 낮지만 Logistic보다는 높은, 애매한 위치의 점수다.
프로젝트의 #505 S0 스태킹 다양성 게이트는 "최고 기준 모델 대비 Macro F1
하락 0.004 이내"뿐 아니라 "오류 상관 0.92 이하 또는 예측 라벨 불일치율
10% 이상"도 별도 통과 조건으로 인정한다. RandomForest는 구조적으로
boosting/선형 계열과 다른 오류를 만들 가능성이 있어 후자 조건을 통과할
수 있지만, 이를 확인하려면 EXP-123/125/127의 실제 OOF 예측(row 단위)이
필요하다. 이 세 실험의 OOF CSV는 `oof/`가 Git 추적 대상이 아니라
로컬에 없어 이 보고서 작성 시점에는 실제 오류 상관·라벨 불일치율을
계산하지 못했다.

## 다음 실험 후보

EXP-123/125/127 중 하나 이상의 OOF CSV(팀 공유 또는 재실행)를 확보해
EXP-596과의 라벨 불일치율·오류 상관을 계산한 뒤 최종 채택/기각을
판정한다.

## 재현과 관련 파일

- Config: `configs/exp596_random_forest_v1.yaml`
- Resolved config: `reproducibility/exp596_random_forest_v1/config.resolved.yaml`
- Runner: `scripts/run_exp596_random_forest_v1.py`
- Metrics: `reports/exp596_random_forest_v1/metrics.json`
- Submission: `submissions/exp596_random_forest_v1.csv`
- Reproduction status: `INFERENCE_VERIFIED`

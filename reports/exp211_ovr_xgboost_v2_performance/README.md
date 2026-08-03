# EXP-211 암종별 전담 XGBoost 다중분류

## 결론

동결 Feature Spec `v2-performance`와 EXP-096 XGBoost tree 설정을 유지하고,
하나의 26-class 모델을 26개의 One-vs-Rest binary 모델로 교체했습니다.
OOF Macro F1은 **0.4112914798**로 EXP-096보다 `-0.0068238282` 낮아
채택 기준을 통과하지 못했습니다.

Fold 표준편차는 `-0.0014385016` 개선됐지만 Log Loss는 `+0.0400049484`
악화됐고 여러 클래스 F1이 하락했습니다. 따라서 **ARCHIVE**하며 제출하거나
OvR 구조를 추가 튜닝하지 않습니다.

## 고정 조건과 변경

- Feature Spec: EXP-096과 동일한 `v2-performance`
- split: canonical stratified 5-fold, seed 42
- tree parameters: EXP-096과 동일
- 유일한 변경: multiclass XGBoost 1개 → 암종별 binary XGBoost 26개
- binary class weight: 각 outer-fold 학습 행에서만 계산
- 26개 양성 확률은 행별 합이 1이 되도록 정규화
- Public LB: 미제출

## 결과

| 항목 | EXP-211 | EXP-096 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4112914798 | 0.4181153080 | -0.0068238282 |
| Fold 표준편차 | 0.0080536160 | 0.0094921177 | -0.0014385016 |
| Accuracy | 0.4091275601 | 0.4078374456 | +0.0012901145 |
| Log Loss | 1.8769391573 | 1.8369342089 | +0.0400049484 |

| Fold | Macro F1 | Accuracy | Log Loss | 최대 best iteration |
|---:|---:|---:|---:|---:|
| 0 | 0.4215797651 | 0.4165995165 | 1.9193412570 | 499 |
| 1 | 0.4019137795 | 0.3983870968 | 1.8782385626 | 499 |
| 2 | 0.4006264832 | 0.4048387097 | 1.8349383862 | 499 |
| 3 | 0.4160726895 | 0.4185483871 | 1.8837226598 | 499 |
| 4 | 0.4097042237 | 0.4072580645 | 1.8684207256 | 499 |

모든 fold에서 적어도 한 binary model이 최대 500 rounds까지 도달했습니다.
그럼에도 Macro F1과 Log Loss가 모두 기준보다 나빠 단순 학습 부족보다는 OvR
구조가 현재 26-class 문제에 적합하지 않은 결과로 해석합니다.

## 재현성과 산출물

- Issue: [#211](https://github.com/fabxoe/open_cancer/issues/211)
- 실행 source commit: `38955bcb7f1a0e8d72e933fd9fa4d48bd1a7873a`
- Config: `configs/exp211_ovr_xgboost_v2_performance.yaml`
- Resolved config: `reproducibility/exp211_ovr_xgboost_v2_performance/config.resolved.yaml`
- Metrics: `reports/exp211_ovr_xgboost_v2_performance/metrics.json`
- 제출 후보: `submissions/exp211_ovr_xgboost_v2_performance.csv` (DACON 미제출)
- 재현 상태: `INFERENCE_VERIFIED`
- 실행시간: 약 93분

저장 checkpoint로 OOF와 test를 다시 추론해 라벨 일치율 100%, 확률 최대 절대
차이 `2.12e-7`, 제출 CSV SHA-256 일치를 확인했습니다.

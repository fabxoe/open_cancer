# EXP-203 — S1 Elastic Net stability selection

## 결론

각 outer fold의 학습 행에서만 Elastic Net stability selection을 수행해 선택한
유전자의 Feature Spec v1 유전자 블록만 XGBoost에 전달했다. OOF Macro F1은
**0.2996289845**로 EXP-094보다 **-0.1172575894** 낮았고, Log Loss도
**+0.3633948103** 악화됐다. 따라서 이 정책은 **ARCHIVE**이며 리더보드에는
제출하지 않는다.

## S1 정책

- selector fit 범위: 각 canonical outer fold의 학습 행만 사용
- 입력: `GENE__mutated` 4,384개 열
- inner CV: 3-fold, `C=[0.01, 0.03, 0.1, 0.3, 1.0]`, `l1_ratio=0.5`,
  one-standard-error 규칙
- stability 반복: 75% stratified subsample 20회, seed `42 + fold*100 + repetition`
- 채택: 16회 이상 선택된 유전자, 최소 50개·최대 512개
- 보존: 선택 유전자의 v1 유전자 블록 전체와 sample aggregate·fixed hotspot 열
- validation·test: 각 outer-train에서 확정해 저장한 동일 mask만 적용
- EXP-094와 같은 Feature Spec v1 XGBoost와 balanced sample weight를 사용했고,
  SMOTE는 사용하지 않았다.

## 결과

| 지표 | EXP-203 | EXP-094 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.2996289845 | -0.1172575894 |
| Fold Macro F1 평균 | 0.2983210763 | - |
| Fold 표준편차 | 0.0112469010 | +0.0033626489 |
| Accuracy | 0.2981777133 | - |
| Log Loss | 2.2033321396 | +0.3633948103 |

Fold Macro F1은 `0.2917453760`, `0.3136269311`, `0.2967567243`,
`0.2819547224`, `0.3075216276`이었다. 가장 큰 클래스별 F1 하락은 ACC의
`-0.4338108453`이었다.

## selector 관찰과 해석

모든 fold에서 inner CV는 `C=1.0`을 선택했다. 이 설정에서는 20회 반복 중 16회
이상 선택된 유전자가 fold별 `4,003~4,038`개로 매우 많았다. 따라서 최대 512개
상한이 매 fold 작동했다. 사전 고정한 순서(선택 빈도 내림차순, 유전자명 오름차순)를
적용한 결과 512개 유전자만 남았고, fold 간 선택 집합 Jaccard는 약 `0.8720~0.9140`,
다섯 fold 공통 유전자는 435개였다.

즉 이 결과는 fold 누출이나 mask 적용 오류가 아니라, 현재 데이터·규제 범위에서
Elastic Net이 충분히 희소한 후보 집합을 만들지 못한 상태에서 상한 절단이 원본
변이 정보를 크게 줄인 결과다. 이 실험의 `C` 범위, frequency threshold 또는
상한을 Public LB나 이 결과를 보고 재조정하지 않는다. S1은 계획대로 한 번의
독립 검증으로 종료하고, 다음 사전 등록 selector인 S2 mRMR로 진행한다.

## 산출물·재현성

- Config: `configs/exp203_s1_elastic_net_stability_selection.yaml`
- Runner: `scripts/run_exp203_s1_elastic_net_stability_selection.py`
- Metrics: `reports/exp203_s1_elastic_net_stability_selection/metrics.json`
- Manifest: `reproducibility/exp203_s1_elastic_net_stability_selection/`
- fold별 mask: `models/exp203_s1_elastic_net_stability_selection/fold_*_feature_selection.json`

각 mask에는 inner-CV 결과, 선택 C, repetition별 selection frequency, 선택 유전자와
feature-order hash를 저장한다. checkpoint, OOF/test 확률, submission은 Git에
커밋하지 않으며 재현 상태는 `MANIFEST_COMPLETE`다.

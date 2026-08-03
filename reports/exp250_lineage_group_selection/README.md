# EXP-250 암종별 변이 패턴 그룹 선택

## 결론

EXP-245의 암종별 변이 패턴 31개를 암종 그룹 단위로 선택한 결과, OOF Macro
F1은 **0.4209182565**였습니다. EXP-245보다 `-0.0004806995`, 채택 기준인
EXP-229보다 `-0.0020703180` 낮아 **ARCHIVE**합니다.

선택기는 fold마다 31개 중 27~31개를 유지해 대부분의 피처를 제거하지 못했고,
fold 표준편차와 Log Loss도 악화됐습니다. 따라서 이 선택 방식으로 일반화 성능이
개선됐다는 근거는 없습니다.

## 무엇을 검증했나

EXP-245에서 정의한 유방암, 난소암, 전립선암, 갑상선암, 방광암, 간암,
자궁경부암, 두경부암 mutation-mechanism proxy를 암종별 한 그룹으로 묶었습니다.
각 outer fold의 학습 데이터 안에서만 3-fold permutation importance를 계산하고,
다음 조건을 모두 만족한 그룹만 해당 outer fold 모델에 넣었습니다.

- 세 inner fold 중 두 곳 이상에서 Macro F1 변화가 양수
- 세 inner fold의 평균 Macro F1 변화가 양수

outer validation, test, Public LB와 EXP-245의 암종별 OOF 변화는 선택에 사용하지
않았습니다. 공용 `stratified_5fold_seed42` split은 변경하지 않았습니다.

## 실제 결과

| 항목 | EXP-250 | EXP-245 | EXP-229 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4209182565 | 0.4213989560 | 0.4229885745 |
| Fold 표준편차 | 0.0130283698 | 0.0083182968 | 0.0098679649 |
| Accuracy | 0.4117077891 | 0.4138042251 | 0.4125141106 |
| Log Loss | 2.0532255173 | 2.0266003609 | 1.8509613276 |

| Fold | Macro F1 | 선택 피처 수 |
|---:|---:|---:|
| 0 | 0.4052276412 | 27 |
| 1 | 0.4162065321 | 27 |
| 2 | 0.4192499206 | 31 |
| 3 | 0.4252393163 | 31 |
| 4 | 0.4447121221 | 27 |

자궁경부암, 두경부암, 방광암, 난소암, 전립선암, 갑상선암 그룹은 5/5 fold,
간암은 4/5 fold, 유방암은 3/5 fold에서 선택됐습니다. 자궁경부암과 두경부암
그룹은 inner-fold 중요도가 가장 일관됐지만, 이 결과는 같은 canonical OOF 안에서
얻었으므로 이를 보고 다음 실험의 고정 피처로 삼으면 검증 과적합 위험이 있습니다.

EXP-245 대비 DLBC, KIRC, LUAD, PAAD 등은 개선됐지만 SARC, STES, HNSC,
UCEC 등의 하락이 상쇄했습니다. fold별 점수 범위도 `0.4052~0.4447`로 넓어졌습니다.

## 판단과 다음 단계

- 암종별 문헌 피처에 일부 신호는 있으나 현재 그룹 선택기는 거의 pruning하지 못했습니다.
- EXP-229를 성능 기준 모델로 유지하고 EXP-245·250은 도메인 신호 분석 자료로 보존합니다.
- 같은 선택 기준을 더 조정하는 실험은 중단합니다.
- 다음 단계는 별도 Experiment Issue에서 피처 선택이 아닌 모델 또는 예측 결합 방향을 검토합니다.

## 재현과 관련 파일

- Issue: [#250](https://github.com/fabxoe/open_cancer/issues/250)
- 실행 source commit: `7f93b2f8be49e3d01cdd6b2442da0a5b6787488c`
- Config: `configs/exp250_lineage_group_selection.yaml`
- Resolved config: `reproducibility/exp250_lineage_group_selection/config.resolved.yaml`
- Metrics: `reports/exp250_lineage_group_selection/metrics.json`
- 그룹별 선택 근거: `reports/exp250_lineage_group_selection/selection_fold_00.json` ~ `selection_fold_04.json`
- 제출 후보: `submissions/exp250_lineage_group_selection.csv` (DACON 미제출)
- 재현 상태: `INFERENCE_VERIFIED`

저장 checkpoint 재추론에서 데이터 hash, 제출 CSV SHA-256과 test label이 일치했고,
test 확률의 최대 절대 차이 `1.1952881e-7`이 허용 오차 `1e-6` 이내임을 확인했습니다.

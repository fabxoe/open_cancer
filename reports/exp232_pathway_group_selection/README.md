# EXP-232 도움이 되는 pathway 변이 피처만 골라 재검증

## 결론

EXP-229의 pathway×변이종류 피처를 outer-fold train 내부의 nested permutation으로
선택했습니다. 후보 피처 수는 fold별 42~43개에서 **4~21개**로 크게 줄었고,
fold 표준편차와 Log Loss는 개선됐습니다.

하지만 OOF Macro F1은 **0.4214874085**로 EXP-229보다 `-0.0015011660`
하락했습니다. 피처 수를 줄이면서 점수를 유지한다는 사전 기준을 충족하지 못해
**ARCHIVE**합니다.

## 선택 방법

각 canonical outer fold마다 해당 outer-train 행만 다시 3개 inner fold로
나눴습니다. 한 pathway의 변이종류 피처들을 함께 섞었을 때 inner validation
Macro F1이 떨어지는 정도를 3회 반복 측정했습니다.

3개 inner fold 중 2개 이상에서 양의 중요도를 보이고 전체 평균도 양수인 pathway만
해당 outer fold의 최종 학습 피처로 사용했습니다. outer validation, test와 Public
LB는 선택에 사용하지 않았습니다.

## 선택 결과

| Outer fold | 선택 pathway | 선택 후보 피처 수 |
|---:|---|---:|
| 0 | cell_cycle | 4 |
| 1 | notch, nrf2, pi3k, rtk_ras | 18 |
| 2 | cell_cycle, notch, tp53 | 13 |
| 3 | cell_cycle, notch, nrf2, rtk_ras, tgf_beta | 21 |
| 4 | cell_cycle, hippo, tgf_beta | 12 |

선택 빈도는 cell_cycle 4회, notch 3회, nrf2·rtk_ras·tgf_beta 각 2회,
hippo·pi3k·tp53 각 1회였습니다. myc와 wnt는 선택되지 않았습니다.

## 성능 결과

| 항목 | EXP-232 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4214874085 | 0.4229885745 | -0.0015011660 |
| Fold 표준편차 | 0.0090327997 | 0.0098679649 | -0.0008351652 |
| Accuracy | 0.4109014675 | 0.4125141106 | -0.0016126431 |
| Log Loss | 1.8429074287 | 1.8509613276 | -0.0080538988 |

EXP-223과 비교하면 Macro F1은 `+0.0001134609`, fold 표준편차는
`-0.0002012055`, Log Loss는 `-0.0012546778`입니다. 즉 EXP-223과는 사실상
동률이지만, 추가 nested 선택 비용을 정당화할 성능 개선은 없습니다.

## 해석과 주의점

이번 결과는 EXP-229의 작은 개선이 소수 pathway만으로 안정적으로 재현되는 구조가
아님을 보여줍니다. 피처를 많이 제거하면 확률 품질과 fold 안정성은 좋아졌지만 공식
지표인 Macro F1은 낮아졌습니다.

cell_cycle이 5개 outer fold 중 4개에서 선택됐지만, 이 빈도는 전체 canonical
OOF 과정에서 나온 사후 관찰입니다. 이를 보고 같은 split에서 cell_cycle만 고정해
다시 평가하면 validation 정보를 간접적으로 재사용하는 선택 편향이 생길 수 있으므로,
이번 결과만으로 후속 고정 피처를 채택하지 않습니다.

## 재현성과 산출물

- Issue: [#232](https://github.com/fabxoe/open_cancer/issues/232)
- 실행 source commit: `7a940bcaae6cd1bb36f3c9d5e5d3296c8ce1b88c`
- Config: `configs/exp232_pathway_group_selection.yaml`
- Resolved config: `reproducibility/exp232_pathway_group_selection/config.resolved.yaml`
- Metrics: `reports/exp232_pathway_group_selection/metrics.json`
- 선택 상세: `reports/exp232_pathway_group_selection/selection_fold_00.json`부터
  `selection_fold_04.json`
- 제출 후보: `submissions/exp232_pathway_group_selection.csv` (DACON 미제출)
- 제출 SHA-256:
  `4b06e897ffc8d5ee8c87d867a35474f4ce8317737961201026263f6dd2c54391`
- 실행시간: 1646.74초
- 재현 상태: `INFERENCE_VERIFIED`

저장 checkpoint로 test를 다시 추론해 라벨 일치율 100%, 확률 최대 절대 차이
`1.36e-7`, 제출 CSV byte-level SHA-256 일치를 확인했습니다.

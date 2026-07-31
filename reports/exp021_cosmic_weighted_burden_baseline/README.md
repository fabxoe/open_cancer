# EXP-021 COSMIC 가중 burden XGBoost baseline

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-021 / #21 |
| 공식 채택 시도 | attempt 3 |
| 입력 | mutation-presence 4,384개 + COSMIC 가중 burden 1개 |
| 모델 | XGBoost, 공용 5-fold |
| Local OOF Macro F1 | 0.349410 |
| Public LB | 0.2544194867 |
| 재현 상태 | `NOT_STARTED` |

## 시도 구성

Issue #21에서는 네 가지 구성을 비교했다. attempt 1, 2, 4는
`exploratory_ablation`이고, 리더보드에 제출한 attempt 3만 EXP-021의
`official` config다.

| 시도 | 역할 | 피처 구성 | OOF Macro F1 |
|---|---|---|---:|
| 1 | 탐색 | COSMIC protect 유전자 361개 | 0.301865 |
| 2 | 탐색 | protect + fold별 상관 상위 200개 | 0.314403 |
| 3 | 공식 채택 | 전체 4,384개 + 가중 burden 1개 | 0.349410 |
| 4 | 탐색 | 전체 4,384개 + 그룹 burden 2개 | 0.344607 |

상관 유전자와 가중치는 각 fold의 학습 구간에서만 계산해 validation label이나
test label을 사용하지 않았다.

## 결과와 판단

공식 attempt 3은 EXP-003보다 OOF와 Public LB가 개선됐지만 EXP-005에는
미치지 못했다. COSMIC 목록으로 원본 feature를 크게 줄이는 것보다 전체
유전자 피처를 유지하면서 요약 burden을 추가하는 편이 나았다.

제출 파일은
`submissions/exp021_cosmic_weighted_burden_baseline.csv`이며 SHA-256은
`cb75da2609631bc86310a637e2d4f2e244bfe85dac71da4f154559ebf19a07b0`이다.

## 재현성과 한계

이 제출은 표준 재현 번들 정책 도입 전에 checkpoint 추론 검증 없이
진행됐다. 따라서 현재 상태는 `NOT_STARTED`이며 최종 후보로 사용할 수 없다.
COSMIC 원본과 유전자 목록은 라이선스 때문에 저장소에 포함하지 않는다.

공식 config와 metrics:

- `configs/exp021_cosmic_weighted_burden_baseline.yaml`
- `reports/exp021_cosmic_weighted_burden_baseline/metrics.json`
- `reproducibility/exp021_cosmic_weighted_burden_baseline/config.resolved.yaml`


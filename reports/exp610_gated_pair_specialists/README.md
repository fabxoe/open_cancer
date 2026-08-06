# EXP-610 — EXP-527 26-class gated pair specialists

## 질문

EXP-527의 26-class 결정을 유지한 채 base top-1이 `KIPAN/KIRC` 또는
`GBMLGG/LGG`에 속할 때만 outer-train binary specialist로 다시 판정하면,
타 노트북에서 관찰된 혼돈쌍 교정 효과가 현재 parser-v4 기준선에도 재현되는가?

## 실험 계약

- 부모: EXP-527
- 고정: EXP-527 fold checkpoint, parser-v4 LOO class-cosine 피처,
  canonical 5-fold, class order
- specialist 학습: 각 outer-train에서 해당 쌍의 행만 사용
- gate: base top-1이 해당 쌍 안에 있을 때만 적용
- 결합: specialist가 base top-1과 다르면 두 클래스 확률을 교환한다.
  따라서 pair mass와 나머지 24개 확률은 정확히 보존되고 specialist 선택이
  최종 top-1이 된다.
- outer validation·test·Public은 specialist 학습이나 설정 선택에 사용하지 않았다.

## 결과

| 지표 | EXP-527 | EXP-610 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4468722707 | 0.4298424283 | -0.0170298424 |
| fold std | 0.0063793185 | 0.0123849202 | +0.0060056017 |
| Accuracy | 0.4339622642 | 0.4123528463 | -0.0216094178 |
| Log Loss | 2.0274887085 | 2.0343379974 | +0.0068492889 |

혼돈쌍 F1:

| 클래스 | EXP-527 | EXP-610 | 변화 |
|---|---:|---:|---:|
| KIPAN | 0.2109181141 | 0.2142857143 | +0.0033676001 |
| KIRC | 0.2812903226 | 0.0890302067 | -0.1922601159 |
| GBMLGG | 0.2848575712 | 0.2933673469 | +0.0085097757 |
| LGG | 0.4888888889 | 0.2264957265 | -0.2623931624 |

모든 fold에서 Macro F1이 하락했다. validation에서 specialist가 바꾼 행은
KIPAN/KIRC 204건, GBMLGG/LGG 137건이었다. 현재 피처의 specialist는 상위
cohort인 KIPAN·GBMLGG 쪽으로 과도하게 되돌리며 KIRC·LGG를 크게 훼손했다.

## 비교 해석

타 노트북은 더 약한 26-class LightGBM에서 같은 형태의 gated reranker로
OOF `0.423140 → 0.430847`을 얻었다. 반면 EXP-527은 이미 parser-v4와
fold-safe class-cosine으로 두 쌍의 정보를 상당 부분 사용한다. 동일한
후처리가 강한 base의 올바른 KIRC·LGG 결정을 덮어써 성능을 낮췄다.

EXP-589의 24-class 병합 개선과도 다르다. EXP-589는 학습 단계에서 겹치는
라벨 경쟁을 제거해 전체 결정경계를 바꿨고, EXP-610은 학습된 26-class
경계는 그대로 둔 채 top-1만 사후 교정했다.

## 판단

`ARCHIVE`. 노트북식 hard gated specialist를 현재 EXP-527에 그대로 적용하는
트랙은 종료한다. Public 제출과 threshold·hyperparameter 재탐색을 하지 않는다.

## 재현

```bash
uv sync --frozen
uv run python scripts/run_exp610_gated_pair_specialists.py
```

- Config: `configs/exp610_gated_pair_specialists.yaml`
- Metrics: `reports/exp610_gated_pair_specialists/metrics.json`
- Submission: `submissions/exp610_gated_pair_specialists.csv`
- 재현 상태: `MANIFEST_COMPLETE`

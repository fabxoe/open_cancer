# EXP-592 — EXP-589 혼돈쌍 fold-safe binary specialist

## 질문

EXP-589가 합친 `KIPAN/KIRC`와 `GBMLGG/LGG` 두 family를 outer-train 전용
binary specialist로 다시 나누면, 24-class 모델의 장점을 유지하면서 원래
26-class 라벨을 복원할 수 있는가?

## 실험 계약

- 부모: EXP-589
- 고정: parser-v4 피처, canonical 5-fold, EXP-589 fold checkpoint와
  24-class base 확률
- specialist:
  - `KIPAN` 대 `KIRC`
  - `GBMLGG` 대 `LGG`
- 각 specialist는 해당 outer fold의 train pair 행만 사용한다.
- outer validation은 학습·하이퍼파라미터 선택에 사용하지 않았다.
- test와 Public 결과는 어떤 선택에도 사용하지 않았다.
- 결합은 base superclass 확률 질량을 binary 조건부 확률로 분배한다.
  나머지 22개 클래스 확률은 유지한다.

## 결과

| 지표 | EXP-589 | EXP-592 | 변화 |
|---|---:|---:|---:|
| 원래 26-class OOF Macro F1 | 0.4533650721 | 0.4393703541 | -0.0139947180 |
| fold 표준편차 | 0.0045090594 | 0.0079793651 | +0.0034703057 |
| Accuracy | 0.4841154652 | 0.4273504274 | -0.0567650379 |

- EXP-592 Log Loss: `1.7712100744`
- fold별 Macro F1:
  `0.4228800434, 0.4421422383, 0.4412556107, 0.4413113491, 0.4452549251`

### 혼돈쌍 F1

| 클래스 | F1 |
|---|---:|
| KIPAN | 0.2103049422 |
| KIRC | 0.0837359098 |
| GBMLGG | 0.3093270366 |
| LGG | 0.2125000000 |

## 왜 악화됐는가

EXP-589에서는 하나의 superclass가 큰 확률 질량을 가진다. EXP-592는 그
질량을 두 원래 클래스에 나누므로 각 클래스의 절대 확률이 낮아지고, 전혀
다른 제3 클래스가 전체 argmax를 가져갈 수 있다. 동시에 binary specialist
자체도 KIRC와 LGG를 충분히 분리하지 못했다.

이를 구분하기 위해 사후 분석으로 먼저 24-class argmax를 고른 뒤, 그
argmax가 두 merged family일 때만 specialist 라벨을 적용하는 hard routing을
측정했다. Macro F1은 `0.4434467829`로 확률 분할보다 높았지만 EXP-589보다
낮았고, KIRC F1도 `0.0860534125`에 그쳤다. 이 값은 공식 EXP-592 결과가
아니며 다음 실험을 열지 않을지 판단하기 위한 진단이다.

## 판단

`ARCHIVE`한다. EXP-589의 개선은 실제이지만, 현재 binary specialist로 네
원래 클래스를 복원하는 방식은 성능과 안정성을 모두 잃는다. 같은 specialist
결과를 이용한 hard-routing 공식 실험도 열지 않는다. 후속은 정상 26-class
모델과 EXP-589의 오류 다양성 분석처럼 다른 경로에서만 검토한다.

## 재현

```bash
uv sync --frozen
uv run python scripts/run_exp592_hierarchical_pair_specialists.py
```

- 재현 상태: `INFERENCE_VERIFIED`
- 제출 SHA-256:
  `d37944dbc616d194d33e9b85966242ffe1e1f61ae770c070f031e803cd7dd001`

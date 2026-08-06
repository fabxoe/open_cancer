# EXP-589 — KIRC→KIPAN·LGG→GBMLGG 24-class XGBoost

## 질문

KIRC/KIPAN과 LGG/GBMLGG 혼돈쌍을 각각 하나의 상위 클래스로 합쳐
24-class로 학습하면, 나머지 암종의 결정경계와 일반화가 개선되는가?

## 실험 계약

- 부모: EXP-527
- 고정: parser-v4 부모 피처, pathway 피처, canonical 5-fold, seed 42,
  XGBoost 파라미터, balanced sample weight
- 변경:
  - `KIRC → KIPAN`
  - `LGG → GBMLGG`
  - class-cosine 중심과 출력 차원을 동일한 24-class 공간으로 재구성
- test와 Public 점수는 모델·체크포인트 선택에 사용하지 않음

체크포인트는 병합된 24-class 점수가 아니라 **원래 대회 26-class Macro
F1**으로 골랐다. 모델이 KIRC와 LGG를 출력할 수 없으므로 두 클래스의 F1은
0이며, 이 손실을 숨기지 않은 점수가 주 지표다.

## 결과

| 지표 | EXP-527 | EXP-589 | 변화 |
|---|---:|---:|---:|
| 원래 26-class OOF Macro F1 | 0.4468722707 | 0.4533650721 | +0.0064928014 |
| fold 표준편차 | 0.0063793185 | 0.0045090594 | -0.0018702591 |
| Accuracy | 0.4339622642 | 0.4841154652 | +0.0501532011 |
| Log Loss | 2.0274887085 (26-class) | 1.4916671515 (24-class) | 평가 공간이 달라 직접 비교 금지 |

- 내부 24-class OOF Macro F1: `0.5086284091`
- 내부 24-class Accuracy: `0.5603934849`
- fold별 정직한 26-class Macro F1:
  `0.4435180697, 0.4544213437, 0.4534737659, 0.4557821054, 0.4548683533`

## 혼돈쌍의 실제 동작

- 원래 KIRC 334명 중 261명이 KIPAN으로 출력됐다.
- 원래 LGG 229명 중 212명이 GBMLGG로 출력됐다.
- KIRC와 LGG는 출력 vocabulary에서 제거됐으므로 두 클래스 F1은 정확히 0이다.
- test 제출 파일도 KIRC와 LGG를 한 건도 포함하지 않는다.

그럼에도 26-class Macro F1이 부모보다 높다는 것은 두 혼돈쌍을 억지로
분리하는 비용이 다른 24개 클래스의 경계에도 악영향을 주고 있었음을
시사한다. 다만 이는 계층 분류가 최종 해법이라는 증명이지, 24-class 제출을
그대로 대표 후보로 쓰라는 뜻은 아니다.

## 판단과 후속

EXP-589는 leakage-safe Local 최고이며 진단 결과는 채택한다. 단독 제출은
KIRC·LGG를 절대 맞힐 수 있어 위험하므로 보류한다.

다음 실험은 두 가지 중 하나여야 한다.

1. 1단계 EXP-589의 상위 예측 후 KIPAN/KIRC 및 GBMLGG/LGG만 구분하는
   fold-safe specialist를 붙인 26-class 계층 모델
2. 정상 26-class 최고 모델과 EXP-589의 OOF 오류 상관을 확인한 뒤, 가중치를
   Public으로 역조정하지 않는 사전 고정 앙상블

## 재현

```bash
uv sync --frozen
uv run python scripts/run_exp589_merged_24class.py
```

- 재현 상태: `INFERENCE_VERIFIED`
- 제출 SHA-256:
  `33cfd8a525a5a885cff64602953939b1112d917d4642bbe54bc6d905d6a8e39a`

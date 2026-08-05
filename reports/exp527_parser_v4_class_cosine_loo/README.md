# EXP-527: Parser-v4 leave-one-out 26-class cosine profile

## 결론

EXP-521의 outer-train 환자가 자기 target class centroid에 자신을 포함하던
self-inclusion을 제거했다. Validation·test는 기존과 동일하게 outer-train 전체
centroid로만 변환했다.

- OOF Macro F1: `0.4468722707`
- EXP-521 대비: `-0.0011202685`
- EXP-374 대비: `+0.0200813439`
- fold 표준편차: `0.0063793185`
- Accuracy / Log Loss: `0.4339622642 / 2.0274887085`
- 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출

Self-inclusion이 EXP-521 OOF를 약 `0.00112` 높인 것은 맞지만, EXP-374 대비
개선 `0.02008`은 유지됐다. 따라서 26-class parser-v4 cosine pattern은 실제
일반화 신호로 판단하며 EXP-527을 leakage-safe 공식 기준선으로 사용한다.

## 정합성 수정

EXP-521에서는 outer-train 행의 정답 class cosine을 계산할 때 그 행 자신도
centroid에 포함됐다. Outer-validation의 target은 사용하지 않았으므로 직접적인
validation leakage는 아니지만, train에만 있는 자기 포함 편향이었다.

EXP-527은 각 outer-train 행 `x`의 target class에 대해 `class_sum - x`로 centroid를
만든다. 다른 25개 class score는 전체 outer-train centroid를 유지한다. Singleton
class는 자기 class LOO score를 0으로 처리한다.

## Fold 결과

| Fold | Macro F1 | Log Loss | Best iteration |
|---:|---:|---:|---:|
| 0 | 0.4343333042 | 2.0824215412 | 34 |
| 1 | 0.4506124547 | 1.8505382538 | 92 |
| 2 | 0.4487400982 | 2.1411995888 | 28 |
| 3 | 0.4500989150 | 1.8709417582 | 64 |
| 4 | 0.4511656678 | 2.1922976971 | 23 |

## 주의점

Macro F1은 매우 높지만 Log Loss는 EXP-374·EXP-521보다 악화됐다. 또한
fold 0과 4의 checkpoint가 빠르게 선택됐다. Public 일반화를 확신하지 않고,
profile score train/test shift·class contribution·OOF error 구조를 먼저 감사한다.

## 재현

```bash
uv run python scripts/run_exp527_parser_v4_class_cosine_loo.py
```

- Config: `configs/exp527_parser_v4_class_cosine_loo.yaml`
- Metrics: `reports/exp527_parser_v4_class_cosine_loo/metrics.json`
- Submission: `submissions/exp527_parser_v4_class_cosine_loo.csv`
- Submission SHA-256: `45f3cd8580e729fec36b00469fbf008b935d2c2cb24703a1f8fa0ee4376391f6`
- Comparison: `reproducibility/exp527_parser_v4_class_cosine_loo/comparison.json`

## 다음 행동

1. EXP-521을 최종 비교 모델에서 제외하고 EXP-527을 대표 class-profile 기준선으로 사용한다.
2. 26개 profile score의 train/test 분포 차이와 adversarial AUC를 감사한다.
3. EXP-374·527의 OOF 오류 상관·클래스별 F1·confidence를 비교한다.

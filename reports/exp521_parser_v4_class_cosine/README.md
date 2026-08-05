# EXP-521: Parser-v4 26-class cosine semantic profile

## 결론

EXP-374의 기존 피처·모델·fold·seed·checkpoint 정책은 그대로 유지하고,
parser-v4가 생성한 환자 의미 벡터와 26개 암종별 outer-train centroid의 cosine
유사도 26개만 추가했다.

- OOF Macro F1: `0.4479925392`
- EXP-374 대비: `+0.0212016124`
- fold 표준편차: `0.0037885371` (EXP-374 대비 `-0.0047146798`)
- Accuracy: `0.4289630705`
- Log Loss: `1.9110684395` (EXP-374 대비 `+0.0670036077`)
- 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출

Macro F1과 fold 안정성은 현재 실험 중 가장 좋았다. 다만 Macro-F1-best
checkpoint가 fold 0·1에서 각각 38·32 iteration으로 빠르게 선택되었고,
Log Loss는 부모보다 악화됐다. 따라서 Local 채택 후보이지만 Public 일반화를
검증하지 않고 최종 모델로 확정하지 않는다.

## 설계

1. raw token을 parser-v4로 의미 판정한다.
2. 환자를 66,242차원 sparse semantic vector로 변환한다.
   - 4,384 gene x 15 semantic-family event count
   - reference amino-acid 20종 count
   - alternate amino-acid 20종 + stop count
   - exact substitution pair `20 x 21`
   - insertion·delins·확정된 first-new peptide amino-acid composition
3. 각 outer fold에서 outer-train만 사용해 26개 암종 centroid를 만든다.
4. validation·test 환자와 각 centroid의 cosine 유사도 26개를 계산한다.
5. 66,242차원 원본 semantic vector는 모델에 직접 넣지 않고, 26개 유사도만
   EXP-374 피처에 추가한다.

이로써 환자별 전역 count만 추가한 EXP-512와 달리, `이 환자가 각 암종의
전형적인 gene×semantic×amino-acid 패턴과 얼마나 닮았는가`를 직접 표현한다.

## Frameshift 보수적 계약

Frameshift는 하나의 변이 event로 세며, 후방의 모든 변경 잔기를 독립 mutation으로
확장하지 않는다. `fsTerN`처럼 종료까지의 거리가 주어진 경우에만 새 reading
frame의 peptide 길이를 알 수 있다.

- `SQ133fs`처럼 first-new residue 후보가 단일 문자 `Q`로 확정되면 `Q` 1회만 세다.
- `SDEL133fs`의 `DEL`은 확정된 후방 peptide가 아니므로 `D/E/L` 3개를 세지 않는다.
- 원본 token과 unresolved provenance는 보존한다.

## Fold 결과

| Fold | Macro F1 | Log Loss | Best iteration |
|---:|---:|---:|---:|
| 0 | 0.4421265043 | 2.0349879265 | 38 |
| 1 | 0.4537929201 | 2.1100029945 | 32 |
| 2 | 0.4484942701 | 1.8954936266 | 60 |
| 3 | 0.4461857691 | 1.7701004744 | 134 |
| 4 | 0.4467389390 | 1.7446569204 | 183 |

## 재현

```bash
uv run python scripts/run_exp521_parser_v4_class_cosine.py
```

- Config: `configs/exp521_parser_v4_class_cosine.yaml`
- Metrics: `reports/exp521_parser_v4_class_cosine/metrics.json`
- Submission: `submissions/exp521_parser_v4_class_cosine.csv`
- Submission SHA-256: `45c9ff42a75ac84c872a0d0ea3de402a3ec0f8450f9486a69b1456eaadb32525`
- Comparison: `reproducibility/exp521_parser_v4_class_cosine/comparison.json`

## 다음 판단

- B단계 cosine 프로필은 채택 후보로 보존한다.
- C단계에서 동일 환자 벡터와 fold-safe class profile을 사용하되, smoothed
  mean log-likelihood 26개로 교체한다.
- C단계를 끝낸 뒤에만 cosine·likelihood 단독/결합을 비교한다.

# EXP-522: Parser-v4 26-class smoothed likelihood profile

## 결론

EXP-521과 동일한 66,242차원 parser-v4 환자 semantic vector를 사용하되, 26개
cosine centroid score를 class-conditional smoothed mean log-likelihood 26개로 교체했다.

- OOF Macro F1: `0.4045242129`
- EXP-374 대비: `-0.0222667140`
- EXP-521 대비: `-0.0434683264`
- fold 표준편차: `0.0091168816`
- Accuracy / Log Loss: `0.4000967586 / 2.3159396648`
- 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출

성능·안정성·Log Loss가 모두 악화되어 `ARCHIVE`한다. 현재 방식의 likelihood
프로필을 제출하거나 alpha만 반복 튜닝하지 않는다.

## 설계

- 부모: EXP-374
- 환자 semantic vector: EXP-521과 동일
- fit 범위: 각 outer-train만
- 클래스 순서: 고정 26-class order
- 가산 smoothing: `alpha=1.0`
- class prior: 제외
- validation·test: transform-only
- 모델에는 26개 mean log-likelihood score만 추가

각 클래스에서 66,242개 token dimension의 count를 합산하고 alpha=1로 평활한 뒤,
환자의 token별 log probability 평균을 26개 암종 score로 사용했다.

## 실패 해석

66,242차원의 대부분은 희소하고, 소수 클래스의 학습 표본도 작다. 모든
vocabulary 열에 alpha=1을 더하면 관찰된 gene×semantic 신호보다 미관찰 가상 count의
총합이 커져 class distribution이 평탄화된다. Fold 0·2·4의 Macro-F1-best
checkpoint가 25·16·17 iteration에서 종료된 것도 이 표현의 불안정성을 보여준다.

반면 EXP-521 cosine은 전체 scale을 제거하고 방향적 패턴만 비교하므로, 이
고차원 희소 count에 더 적합했다.

## Fold 결과

| Fold | Macro F1 | Log Loss | Best iteration |
|---:|---:|---:|---:|
| 0 | 0.3961122583 | 2.3432931900 | 25 |
| 1 | 0.4075343046 | 2.1408958435 | 98 |
| 2 | 0.3970186800 | 2.5336480141 | 16 |
| 3 | 0.4201506820 | 2.0997312069 | 125 |
| 4 | 0.3983945398 | 2.4621083736 | 17 |

## 재현

```bash
uv run python scripts/run_exp522_parser_v4_class_likelihood.py
```

- Config: `configs/exp522_parser_v4_class_likelihood.yaml`
- Metrics: `reports/exp522_parser_v4_class_likelihood/metrics.json`
- Submission: `submissions/exp522_parser_v4_class_likelihood.csv`
- Submission SHA-256: `739f7d583a65047fb6ad9984c05007df838cc40654d121543ea85ddc3e367228`
- Comparison: `reproducibility/exp522_parser_v4_class_likelihood/comparison.json`

## 다음 행동

- B단계 EXP-521 cosine을 선택 후보로 유지한다.
- EXP-522 likelihood는 종료하고 cosine과 결합하지 않는다.
- EXP-521의 OOF/Public 괴리 위험을 줄이기 위해 다음은 profile score의 shift·class
  contribution·OOF error 상관을 감사한다.

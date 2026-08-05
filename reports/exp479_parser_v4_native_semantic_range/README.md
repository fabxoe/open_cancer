# EXP-479 — Parser v4 native semantic range 기준선

## 목적

EXP-469의 비튜닝 native v2 조건을 유지하면서 compact range 표기를 HGVS-derived
의미에 따라 다음 세 consequence로 분리한 모델 기준선을 만든다.

- `range_replacement`: `1436_1437SI>RF`
- `range_stop`: `300_301LE>F*`, `2126_2127WE>*K`, `197_198YQ>**`
- `range_no_change`: `236_237LL>LL`

이 셋은 서로 다른 사건이며 `complex` 또는 하나의 포괄적 range로 다시 합치지
않는다. 점수는 parser correctness가 아니라 현재 feature adapter와 고정 XGBoost
설정의 적합성을 평가한다.

## 통제 설계

- 부모: EXP-469
- canonical stratified 5-fold, seed 42
- XGBoost 파라미터·balanced sample weight·Macro-F1 checkpoint 정책 동일
- mutation presence 유지
- sample 집계는 token count, gene 집계는 consequence presence
- EXP-469의 다섯 consequence 값과 순서 유지:
  `missense`, `no_change`, `nonsense`, `frameshift`, `range_replacement`
- 유일한 모델 schema 추가: `range_stop`, `range_no_change`
- SUBCLASS·test prevalence·Public LB를 schema 선택에 사용하지 않음

## 실행

```bash
uv run python scripts/run_exp479_parser_v4_native_semantic_range.py
```

- Config: `configs/exp479_parser_v4_native_semantic_range.yaml`
- Runner: `scripts/run_exp479_parser_v4_native_semantic_range.py`
- Source commit: `8a6010d6152a1fa8fd4dec795bba866d90137344`
- Metrics: `reports/exp479_parser_v4_native_semantic_range/metrics.json`
- Resolved config: `reproducibility/exp479_parser_v4_native_semantic_range/config.resolved.yaml`
- OOF: `oof/exp479_parser_v4_native_semantic_range.csv`
- Test probability: `preds/exp479_parser_v4_native_semantic_range_test_proba.csv`
- Submission: `submissions/exp479_parser_v4_native_semantic_range.csv`

## 결과

| 지표 | EXP-479 | EXP-469 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.4087566023 | -0.0030251756 |
| Fold 표준편차 | 0.0105763236 | +0.0016671733 |
| Accuracy | 0.4005805515 | -0.0032252862 |
| Log Loss | 1.9471516609 | +0.0251333714 |

Fold Macro F1은 `0.3984987531`, `0.4235728121`, `0.4047336390`,
`0.3981967162`, `0.4190945801`이다.

EXP-469 대비 가장 큰 클래스 하락은 LAML `-0.03836`, BLCA `-0.03589`,
TGCT `-0.03334`였고, 가장 큰 상승은 KIRC `+0.03884`, DLBC `+0.02655`였다.
추가 의미가 모든 클래스에서 같은 방향으로 작동하지 않으며 현재 모델의 feature
competition과 규제가 맞지 않을 가능성을 보여준다.

## 재현성

- 상태: `INFERENCE_VERIFIED`
- 원본·재생성 submission SHA-256:
  `0d74673e4670ef21648a0434bc48a172f61a8d55e8be62742512440f3bd83d6d`
- test label agreement: `1.0`
- test probability max absolute difference: `1.82e-7`
- 허용 오차 `atol=1e-6`, `rtol=1e-6` 통과

## 판단

현재 고정 XGBoost 설정에서는 EXP-469보다 Macro F1·fold 안정성·Log Loss가 모두
악화됐으므로 리더보드 제출 후보로 채택하지 않는다. 그러나 이를 이유로
`range_stop`이나 `range_no_change`를 삭제하지 않는다. EXP-479를 **비튜닝 Parser
v4-native semantic baseline**으로 동결하고, 다음 단계에서 분포·희소도·상관,
adversarial AUC, fold validation TreeSHAP을 먼저 감사한 뒤 native 전용 nested
tuning과 multi-seed 안정성 검증을 수행한다.

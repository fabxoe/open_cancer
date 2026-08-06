# EXP-565: LightGBM parser-v4 parent only

## 결론

EXP-527에서 26개 class-cosine score를 제거하고 parser-v4 부모 피처만
LightGBM에 입력한 결과 OOF Macro F1은 **0.4272525489**였습니다. EXP-527보다
`-0.0196197218` 낮고 fold 표준편차가 `0.0146212064`로 커졌습니다.

따라서 parser-v4 세부 표현만 LightGBM에 제공하는 것은 충분하지 않았습니다.
이 결과는 class-cosine의 추가 효과를 판정하는 L1 기준점으로 사용합니다.

## 고정 조건

- canonical stratified 5-fold, seed 42
- EXP-527의 parser·부모 feature builder·class order 유지
- balanced sample weight 유지
- LightGBM 세 arm 공통 고정 설정
- validation Macro F1 checkpoint 선택
- 유일한 제외 항목: 26개 class-cosine score

## 결과

| 항목 | EXP-565 | EXP-527 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4272525489 | 0.4468722707 | -0.0196197218 |
| Fold std | 0.0146212064 | 0.0063793185 | +0.0082418879 |
| Accuracy | 0.4236413482 | 0.4339622642 | -0.0103209160 |
| Log Loss | 1.8319022146 | 2.0274887085 | -0.1955864939 |

Fold F1은 `0.4129549238`, `0.4284829407`, `0.4192353662`,
`0.4209726006`, `0.4548071621`입니다. Log Loss는 개선됐지만 대회 지표인
Macro F1과 fold 안정성이 악화되어 단독 후보에서는 제외합니다.

EXP-527과 OOF 예측 라벨 불일치율은 `40.0903%`, 정오답 상관은
`0.6196193`입니다. 모델 다양성은 있으나 후속 조합은 L3 결과와 함께 판단합니다.

## 산출물

- Config: `configs/exp565_lightgbm_parser_only.yaml`
- Runner: `scripts/run_exp565_lightgbm_parser_only.py`
- Metrics: `reports/exp565_lightgbm_parser_only/metrics.json`
- Submission: `submissions/exp565_lightgbm_parser_only.csv`
- Reproducibility: `reproducibility/exp565_lightgbm_parser_only/`

재현 상태는 checkpoint 재추론 제출 SHA-256 일치로 `INFERENCE_VERIFIED`입니다.

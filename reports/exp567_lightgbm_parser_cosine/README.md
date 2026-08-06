# EXP-567: LightGBM parser-v4 + 26-class cosine

## 결론

EXP-527의 parser-v4 부모 피처와 leakage-safe class-cosine 26개를 함께
LightGBM에 입력한 결과 OOF Macro F1은 **0.4477416384**였습니다.

- parser-only EXP-565 대비 `+0.0204890896`
- cosine-only EXP-566 대비 `+0.1803355928`
- 동일 피처 XGBoost EXP-527 대비 `+0.0008693677`
- fold std `0.0045984625`로 EXP-527보다 `-0.0017808560`
- Log Loss `1.8136045028`로 EXP-527보다 `-0.2138842057`

따라서 cosine은 parser-v4와 독립적인 충분 표현도 아니고 단순 중복 노이즈도
아닙니다. parser 원시 의미를 암종별 방향으로 재표현하여 LightGBM의 분할을
돕는 **유용한 지도 압축 보조 피처**로 판정합니다.

## 3-arm 비교

| Arm | 입력 | OOF Macro F1 | Fold std | Log Loss | 판단 |
|---|---|---:|---:|---:|---|
| EXP-565 L1 | parser only | 0.4272525489 | 0.0146212064 | 1.8319022146 | 원시 표현 단독 부족 |
| EXP-566 L2 | cosine only | 0.2674060456 | 0.0128339399 | 2.4371772658 | 손실 압축, 대체 불가 |
| EXP-567 L3 | parser + cosine | 0.4477416384 | 0.0045984625 | 1.8136045028 | 상호 보완, 채택 |
| EXP-527 | 동일 L3 + XGBoost | 0.4468722707 | 0.0063793185 | 2.0274887085 | 기존 leakage-safe 기준 |

EXP-567과 EXP-527의 OOF 라벨 불일치율은 `25.5926%`, 정오답 상관은
`0.7529940`입니다. EXP-527만 맞힌 행 369개, EXP-567만 맞힌 행 384개로
모델 다양성도 남아 있습니다. EXP-565와는 라벨이 `38.5583%` 다르고,
EXP-567만 추가로 맞힌 행이 580개입니다.

## 해석 제한

EXP-567의 개선폭은 EXP-527 대비 `+0.0008694`로 작습니다. Public LB 결과를
보기 전 가중치나 피처를 역조정하지 않습니다. 이 실험은 LightGBM에서 cosine의
비중·family drop 효과를 후속 permutation/SHAP으로 확인할 근거를 제공하지만,
cosine이 새로운 생물학적 정보를 추가했다는 뜻은 아닙니다.

## 산출물

- Config: `configs/exp567_lightgbm_parser_cosine.yaml`
- Runner: `scripts/run_exp567_lightgbm_parser_cosine.py`
- Metrics: `reports/exp567_lightgbm_parser_cosine/metrics.json`
- Submission: `submissions/exp567_lightgbm_parser_cosine.csv`
- Reproducibility: `reproducibility/exp567_lightgbm_parser_cosine/`

재현 상태는 checkpoint 재추론 제출 SHA-256 일치로 `INFERENCE_VERIFIED`입니다.

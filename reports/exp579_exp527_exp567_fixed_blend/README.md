# EXP-579: EXP-527·EXP-567 고정 0.5/0.5 확률 평균

## 결론

동일 parser-v4 + leakage-safe 26-class cosine 입력을 사용한 EXP-527
XGBoost와 EXP-567 LightGBM의 test/OOF 확률을 사전에 고정한 `0.5/0.5`로
평균했습니다. OOF Macro F1은 **0.4431736484**로 두 부모보다 모두 낮아
`ARCHIVE`합니다.

| 모델 | OOF Macro F1 | Fold std | Log Loss |
|---|---:|---:|---:|
| EXP-527 XGBoost | 0.4468722707 | 0.0063793185 | 2.0274887085 |
| EXP-567 LightGBM | 0.4477416384 | 0.0045984625 | 1.8136045028 |
| EXP-579 0.5/0.5 blend | 0.4431736484 | 0.0034879454 | 1.8770651386 |

EXP-579는 EXP-567 대비 Macro F1 `-0.0045679900`, fold std
`-0.0011105171`, Log Loss `+0.0634606358`입니다. fold 안정성은 좋아졌지만
주 평가 지표와 확률 품질이 동시에 나빠져 채택 조건을 충족하지 못했습니다.
EXP-527 대비로도 Macro F1은 `-0.0036986223`입니다.

## 해석

EXP-527과 EXP-567은 OOF 라벨이 `25.5926%` 다르고 각각만 맞힌 행도
369개와 384개였지만, 그 차이가 동일 가중치 평균에서 성능 향상으로
전환되지는 않았습니다. 두 모델의 오류 다양성만으로 확률 평균의 개선을
보장할 수 없고, 단순 평균이 각 모델의 올바른 강한 확신까지 희석한 것으로
해석합니다.

이 결과를 보고 가중치를 추가 탐색하지 않습니다. Public LB나 test 분포로
가중치를 역최적화하지 않으며, EXP-567을 독립 Local 후보로 유지합니다.

## 실행 계약

- Issue: #579
- 부모: EXP-527, EXP-567
- 가중치: `0.5 / 0.5` 사전 고정
- Config: `configs/exp579_exp527_exp567_fixed_blend.yaml`
- Runner: `scripts/run_exp579_exp527_exp567_fixed_blend.py`
- Metrics: `reports/exp579_exp527_exp567_fixed_blend/metrics.json`
- Submission: `submissions/exp579_exp527_exp567_fixed_blend.csv`
- 재현 상태: `INFERENCE_VERIFIED`

부모 OOF/test 확률의 ID·class 순서를 검증했고, 제출 CSV의 byte-level
SHA-256 재생성 및 OOF/test 확률 최대 절대 차이 `0`을 확인했습니다.

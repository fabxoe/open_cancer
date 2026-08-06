# EXP-566: LightGBM 26-class cosine only

## 결론

EXP-527의 fold-safe leave-one-out class-cosine 26개만 LightGBM에 입력한 결과
OOF Macro F1은 **0.2674060456**이었습니다. EXP-527보다 `-0.1794662251`,
parser-only EXP-565보다 `-0.1598465033` 낮습니다.

따라서 26개 cosine은 parser-v4 의미 표현을 대체하는 독립 representation이
아닙니다. 암종별 중심과의 관계를 요약한 손실 압축이며, 원시 parser 피처 위에
추가할 때만 의미가 있는지 EXP-567에서 판정합니다.

## 고정 조건

- canonical stratified 5-fold, seed 42
- EXP-527의 parser-v4 semantic vector와 LOO centroid 계산 유지
- outer-train 학습행의 target class는 leave-one-out centroid
- validation/test는 outer-train full centroid transform-only
- 모델 입력은 26개 cosine뿐이며 모든 base/parent 열 제거
- 세 arm 공통 LightGBM과 validation Macro F1 checkpoint

## 결과

| 항목 | EXP-566 | EXP-527 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.2674060456 | 0.4468722707 | -0.1794662251 |
| Fold std | 0.0128339399 | 0.0063793185 | +0.0064546214 |
| Accuracy | 0.2589904854 | 0.4339622642 | -0.1749717787 |
| Log Loss | 2.4371772658 | 2.0274887085 | +0.4096885573 |

Fold F1은 `0.2796613793`, `0.2785440410`, `0.2451800752`,
`0.2748743647`, `0.2647984009`입니다. EXP-527과 라벨 불일치율은
`57.5552%`, 정오답 상관은 `0.4286020`입니다.

## 산출물

- Config: `configs/exp566_lightgbm_cosine_only.yaml`
- Runner: `scripts/run_exp566_lightgbm_cosine_only.py`
- Metrics: `reports/exp566_lightgbm_cosine_only/metrics.json`
- Submission: `submissions/exp566_lightgbm_cosine_only.csv`
- Reproducibility: `reproducibility/exp566_lightgbm_cosine_only/`

재현 상태는 `INFERENCE_VERIFIED`이며 단독 모델은 `ARCHIVE`합니다.

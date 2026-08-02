# EXP-219 — Macro F1 checkpoint 선택 통제 비교

EXP-094와 피처·fold·seed·XGBoost 하이퍼파라미터를 동일하게 유지하고,
각 outer-fold validation에서 체크포인트를 고르는 기준만 `mlogloss` 최소에서
`Macro F1` 최대로 바꾼 통제 실험이다. test와 Public LB는 iteration 선택에
사용하지 않았다.

## 결과

| 기준 | OOF Macro F1 | Fold 표준편차 | Accuracy | Log Loss |
|---|---:|---:|---:|---:|
| 기존 mlogloss-best | 0.4168865739 | 0.0078842521 | 0.4071923883 | 1.8399370909 |
| Macro-F1-best | 0.4222321460 | 0.0067203936 | 0.4097726173 | 1.8476127386 |
| 변화 | **+0.0053455721** | **-0.0011638585** | +0.0025802290 | +0.0076756477 |

fold별 선택 iteration은 다음과 같다.

| Fold | mlogloss-best | Macro-F1-best | Fold Macro F1 변화 |
|---:|---:|---:|---:|
| 0 | 200 | 199 | +0.0016546153 |
| 1 | 207 | 218 | +0.0055020249 |
| 2 | 245 | 256 | +0.0022849598 |
| 3 | 221 | 116 | +0.0152564666 |
| 4 | 214 | 168 | +0.0042356023 |

26개 클래스 중 최악의 F1 변화는 HNSC `-0.0103647851`였고, DLBC는
`0.3773584906 → 0.4285714286`으로 개선됐다. Log Loss는 악화됐지만 이 대회의
평가 지표가 Macro F1이므로 보조 진단값으로 해석한다.

## 판단

Macro-F1 checkpoint 정책을 이후 XGBoost 실험의 기본 후보로 **채택**한다.
OOF Macro F1 향상뿐 아니라 fold 변동성도 감소했고 심각한 클래스 붕괴가 없었다.
과거 실험을 일괄 재학습하지는 않는다. validation fold에서 iteration을 고르는
과정 자체의 낙관 편향 가능성은 있으므로, 새 정책의 일반화는 이후 독립 실험과
Public 결과에서 계속 관찰한다.

저장된 fold checkpoint로 제출 파일을 다시 생성한 결과 SHA-256이 원본과
byte-level로 일치했으며, test 라벨 일치율 100%, 확률 최대 차이
`1.45e-07`로 `INFERENCE_VERIFIED`를 통과했다.

## 산출물

- Config: `configs/exp219_macro_f1_checkpoint_selection.yaml`
- Runner: `scripts/run_exp219_macro_f1_checkpoint_selection.py`
- Metrics: `reports/exp219_macro_f1_checkpoint_selection/metrics.json`
- OOF: `oof/exp219_macro_f1_checkpoint_selection.csv`
- Test probability: `preds/exp219_macro_f1_checkpoint_selection_test_proba.csv`
- Submission: `submissions/exp219_macro_f1_checkpoint_selection.csv`
- Reproducibility: `reproducibility/exp219_macro_f1_checkpoint_selection/`


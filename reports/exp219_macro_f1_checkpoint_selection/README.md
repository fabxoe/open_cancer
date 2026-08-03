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
- Original artifact Release:
  [`exp-219-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-219-repro-v1)
- Release bundle SHA-256:
  `fa293ed92a21508e0752890ca407c6e55cbc8794688262bacff471fd6739bf25`

## 원본 Release 복구

Task Issue #258에서 실행 source Mac에 남아 있던 checkpoint 5개, OOF·test 확률,
submission과 resolved config를 기존 artifact manifest의 SHA-256과 다시 대조했고
모두 일치했다. 이 원본만 결정적 번들로 묶어 `exp-219-repro-v1` Release에
보존했다.

Windows에서 같은 config·seed·패키지 버전으로 수행한 재학습은 OOF Macro F1과
파일 SHA-256이 원본과 달랐으므로 원본 대체물로 사용하지 않았다. 플랫폼 간
XGBoost `hist` 재학습 차이는 Issue #238에서 별도로 추적한다.

# EXP-444 — Parser v4 supported-range hybrid

> Issue: [#444](https://github.com/fabxoe/open_cancer/issues/444)

## 목적

N4 L/C/N 감사에서 사전에 고정한 첫 adapter 수정 실험입니다. EXP-435의 parser
v4 compatibility 5-family와 기존 mutation presence·missing을 그대로 유지하고,
train support가 확인된 v4-native `range_replacement` 의미만 추가했습니다.

추가된 피처는 다음 두 종류뿐입니다.

- 샘플별 range-replacement 발생 유전자 수 1개
- 4,384개 유전자별 range-replacement 존재 여부

train support가 0인 frameshift grammar, parse-status·unresolved 요약, hotspot,
residue-position, pathway, isoform, driver, Optuna는 사용하지 않았습니다. test 분포와
Public 점수는 schema 선택에 사용하지 않았습니다.

## 결과

- Fold Macro F1: `0.4053114668`, `0.4208336691`, `0.4064227415`,
  `0.4005433972`, `0.4259049324`
- OOF Macro F1: **`0.4127201906`**
- Fold std: `0.0097804225`
- Accuracy: `0.4034833091`
- Log Loss: `1.8767832518`
- Runtime: `812.69초`
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

### EXP-435 Compatibility C 대비

- Macro F1: `+0.0016167439`
- Fold std: `+0.0011444725` (허용 한도 `0.002` 이내)
- Accuracy: `-0.0011288502`
- Log Loss: `-0.0654215813` (개선)
- 가장 큰 클래스 하락: KIRC `-0.0541389162`

### EXP-433 Legacy L 대비

- Macro F1: `-0.0005560993`
- Fold std: `+0.0002462190`
- Log Loss: `-0.0768024921` (개선)
- 가장 큰 클래스 하락: PAAD `-0.0414781297`

## 판단

EXP-435 대비 사전 기준인 Macro F1 `+0.001`을 넘었으므로, train-supported
range 의미 자체는 compatibility 표현 위에서 유효한 신호입니다. Legacy L과 비교하면
성능 채택 기준 `+0.001`에는 못 미쳤지만, Macro F1 하락이 `0.001` 이내이고 fold std
악화가 `0.002` 미만이며 모든 클래스 하락이 `0.05` 미만이어서 로드맵의
**정확성 기준선 허용 gate**를 통과했습니다.

따라서 이 결과는 parser v4를 되돌릴 이유가 아니라, native 의미를 support-gated로
좁게 노출하는 방식이 full replacement보다 안전하다는 증거입니다. 다만 compatibility
5-family에 range 하나만 더한 모델이므로 아직 `Parser-native Baseline v1` 동결은 하지
않습니다. 다음 사전 고정 단계는 EXP-438 native schema에서 sample parse-status와
frameshift grammar 같은 provenance summary를 제거해, native consequence 자체와
annotation provenance 경쟁을 분리하는 ablation입니다.

## 재현 정보

- Source commit: `e40c0183937378e0edcb1f66c93878a4da1aff67`
- Config: `configs/exp444_parser_v4_supported_range_hybrid.yaml`
- Runner: `scripts/run_exp444_parser_v4_supported_range_hybrid.py`
- Resolved config:
  `reproducibility/exp444_parser_v4_supported_range_hybrid/config.resolved.yaml`
- Metrics: `reports/exp444_parser_v4_supported_range_hybrid/metrics.json`
- OOF: `oof/exp444_parser_v4_supported_range_hybrid.csv`
- Test probability: `preds/exp444_parser_v4_supported_range_hybrid_test_proba.csv`
- Submission: `submissions/exp444_parser_v4_supported_range_hybrid.csv`

저장 checkpoint 재추론과 독립 재학습 검증은 아직 수행하지 않았으므로 재현 상태를
승격하지 않았습니다.

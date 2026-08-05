# EXP-433 — Parser v4 N4-L Legacy control

> Issue: [#433](https://github.com/fabxoe/open_cancer/issues/433)

## 목적과 통제

N4 L/C/N 비교의 현재 환경 control입니다. stop-v2 parser, mutation presence·missing,
기존 5-family만 사용하고 hotspot·residue-position·pathway·isoform·driver·추가
aggregate·Optuna를 제외했습니다. canonical 5-fold, seed 42, balanced sample weight,
validation Macro F1 checkpoint를 세 arm에서 고정합니다.

## 실행

- Config: `configs/exp433_parser_v4_legacy_control.yaml`
- Runner: `scripts/run_exp433_parser_v4_legacy_control.py`
- Source: `3cd8ec8ea3a4003cd0c693bd5df64dc82807f4cb`
- Runtime: `370.63초` (local macOS CPU)

## 결과

- Fold Macro F1: `0.4030107242`, `0.4271935225`, `0.4078921683`,
  `0.4072246618`, `0.4227851258`
- OOF Macro F1: **`0.4132762899`**
- Fold mean/std: `0.4136212405 / 0.0095342035`
- Accuracy: `0.4029995162`
- Log Loss: `1.9535857439`
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

이 결과는 단독 채택 후보가 아니라 C와 N의 통제군입니다. 상세 수치는
[`metrics.json`](metrics.json)에 있습니다.

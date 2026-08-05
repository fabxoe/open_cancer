# EXP-435 — Parser v4 N4-C Compatibility control

> Issue: [#435](https://github.com/fabxoe/open_cancer/issues/435)

## 목적과 유일한 변경

EXP-433과 같은 data·fold·model·seed·weight·checkpoint에서 기존 5-family 열을
full parser v4 canonical-event compatibility projection으로 교체했습니다.
mutation presence·missing은 보존했고 다른 의미·외부 지식 피처는 사용하지 않았습니다.

## 결과

- Fold Macro F1: `0.4061502785`, `0.4233158955`, `0.4067854760`,
  `0.4000756436`, `0.4187843306`
- OOF Macro F1: **`0.4111034467`** (EXP-433 대비 `-0.0021728433`)
- Fold std: `0.0086359500` (EXP-433 대비 `-0.0008982534`)
- Accuracy: `0.4046121593` (EXP-433 대비 `+0.0016126431`)
- Log Loss: `1.9422048330` (EXP-433 대비 `-0.0113809109`)
- Runtime: `665.39초`
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

## 판단

Compatibility projection은 Macro F1이 하락해 baseline 후보가 아닙니다. Accuracy,
fold 안정성과 Log Loss는 개선되어 단순한 전면 악화도 아닙니다. 이 결과는 parser v4
correctness를 되돌리는 근거가 아니며, 실제 판단 대상은 Native N입니다.

# EXP-438 — Parser v4 N4-N Native semantic baseline

> Issue: [#438](https://github.com/fabxoe/open_cancer/issues/438)

## 목적

EXP-433/435와 같은 data·fold·model·seed·weight·checkpoint에서 기존 5-family를
고정 parser v4-native semantic schema로 교체했습니다. mutation presence·missing은
보존하고 외부 지식·위치·pathway·hotspot·추가 aggregate·Optuna를 제외했습니다.

## 결과

- Fold Macro F1: `0.3980049446`, `0.4217572069`, `0.4086947079`,
  `0.3990173161`, `0.4240081111`
- OOF Macro F1: **`0.4102050373`**
- EXP-433 Legacy L 대비: `-0.0030712527`
- EXP-435 Compatibility C 대비: `-0.0008984094`
- Fold std: `0.0109564971` (L 대비 `+0.0014222936`)
- Accuracy: `0.4021931946`
- Log Loss: `1.9731860161` (L 대비 `+0.0196002722`)
- PAAD F1: `0.1513944223` (L 대비 `-0.0567503741`)
- Runtime: `585.50초`
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

## 판단

첫 native adapter는 성능 gate와 클래스 붕괴 gate를 통과하지 못했습니다. 이는
biologically correct parser를 되돌릴 근거가 아닙니다. 현재 schema가 deletion·insertion·
duplication·delins를 train support 정책 때문에 coarse fallback으로 합치고, 기존
5-family 정보를 6개 consequence로 교체한 표현 설계가 불충분했을 가능성을 우선
검증합니다.

N5 동결은 보류합니다. 다음 단계는 parser semantics를 유지한 채 native family를
additive/replacement 방식으로 분리 ablation하여 어느 표현에서 손실이 생겼는지 찾는
것입니다.

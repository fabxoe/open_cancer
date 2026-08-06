# EXP-596 RandomForest v1 — #505 S0 다양성 게이트 판정

> Issue #596/PR #598 코멘트에서 보류했던 판정입니다. 기존 OOF만 사용했고,
> 새 학습·Public LB 제출을 수행하지 않았습니다.

- 기준 모델: EXP-127 (v1 계열 최고)
- Macro F1 delta: -0.0141799674 (품질 gate 0.004 이내 여부: FAIL)
- 오류(정오답) 상관: 0.7281 (다양성 gate ≤0.92 여부: PASS)
- 라벨 불일치율: 0.3087 (다양성 gate ≥0.10 여부: PASS)
- 종합 다양성 gate: PASS

## 최종 판정: S0 스태킹 후보로 채택

## 보조 비교 (EXP-596 vs 다른 v1 후보)

- EXP-125: 라벨 불일치 0.3422, 정오답 상관 0.6655
- EXP-123: oof file not present locally

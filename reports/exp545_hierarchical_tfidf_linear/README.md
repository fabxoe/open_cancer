# EXP-545 hierarchical TF-IDF row-L2 LinearSVC

Parser-v4 canonical event의 hierarchical detail/global TF-IDF row-L2 비교입니다.

- OOF Macro F1: `0.4396775272`
- Fold 표준편차: `0.0038151877`
- Accuracy: `0.4279954846`
- decision-score softmax Log Loss: `2.7787079811`
- Submission SHA-256: `ef61d71d784b9b277a4161ed6c323f543346c9a35de6417f209118e75e78557a`

EXP-541 row-L2 count와 비교하여 outer-train TF-IDF의 추가 효과를 평가합니다.

## EXP-527과의 다양성

- 예측 라벨 불일치율: `50.7983%`
- 정오답 상관: `0.487465`
- EXP-527만 정답: `12.8689%`
- EXP-545만 정답: `12.2722%`
- EXP-527 대비 개선 상위: DLBC `+0.2941`, TGCT `+0.2102`,
  LAML `+0.0867`, BRCA `+0.0834`
- EXP-527 대비 악화 상위: LGG `-0.2486`, KIRC `-0.2035`,
  CESC `-0.1829`, SKCM `-0.0894`

EXP-545는 EXP-527보다 OOF Macro F1이 `0.0071947435` 낮지만 오류 구조가
충분히 달라 다양성 후보 조건을 통과합니다. 다만 위 Log Loss는 LinearSVC의
decision score를 단순 softmax한 진단값으로, 보정된 예측확률이 아닙니다.
따라서 이 CSV를 확률 앙상블이나 단독 제출에 직접 사용하지 않고 별도의
outer-fold-safe calibration 또는 확률 모델을 먼저 검증합니다.
